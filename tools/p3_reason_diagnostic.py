#!/usr/bin/env python3
"""Closed eight-input reason diagnostic for the JP Bedrock observed failures (#74).

Diagnostic regression data only: not fresh quality, stability, promotion or
candidate admission. One attempt per pinned input, closed public evidence and a
private raw-completion capture that never enters the public report.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.bedrock import BedrockClient, BedrockConfig, normalize_converse_response
from grepbit.clarification import KINDS
from grepbit.gateway import GatewayResponse, ModelError
from grepbit.provider import client_from_env
from grepbit.recipe_model import INVALID_REQUEST_REASONS, interpret_recipe_and_execute
from tools import p3_admission as admission, p3_assets as assets, p3_bedrock_candidate_probe as bedrock_probe
from tools import p3_bedrock_observed_regression as observed, p3_candidate_regression as historical
from tools import p3_eval as evaluator, p3_formal_policy as allocation, p3_grading, p3_live_evidence as live
from tools import smoke

VERSION = "p3-reason-diagnostic-v1"
FINGERPRINT_VERSION = "recipe-output-structure-v1"
PURPOSE = "attribute_eight_observed_failures_not_quality_or_promotion"
EVIDENCE_CLASS = "diagnostic_regression_data"
OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/74#issuecomment-[1-9][0-9]*")
SOURCE_REPORT = ".artifacts/p370-bedrock-observed-live-FYyH0G/run/report.json"
SOURCE_REPORT_SHA256 = "5fa060f21f7cf0d3b72aba88fda4eba427ead102cf33b5da45bb2c241dd8825d"
INTAKE = ".artifacts/p35-stage-c-pIKdCM/input-bundle/intake.json"
PANEL = ".artifacts/p35-stage-c-pIKdCM/input-bundle/formal-panel-v2-draft.json"
CASE_IDS = (
    "FA04_A04_compare_year_on_baseline_nonadjacent.en",
    "FA09_C02_comparison_roles_symmetric.r2.zh-TW",
    "FA09_C02_comparison_roles_symmetric.r2.en",
    "FA09_C02_comparison_roles_symmetric.r2.ja",
    "E02_compare.en",
    "P15_center.en",
    "P16_metric_meaning.zh-TW",
    "P22_center_compare.ja",
)
QUESTION_SHA256 = {
    "FA04_A04_compare_year_on_baseline_nonadjacent.en":
        "3233ec0a2eea20443d7adf0f53658d1dacbed69ea37efe765bbf9fe9083000f8",
    "FA09_C02_comparison_roles_symmetric.r2.zh-TW":
        "8026c6eccb54029ec0dde8c691c4e01bc8dc7f2bce531f1c4030615ebaf9131b",
    "FA09_C02_comparison_roles_symmetric.r2.en":
        "1e31cb9016198b77249c8e904f128f00ae25b7bbaa11f71203029d59abf342d5",
    "FA09_C02_comparison_roles_symmetric.r2.ja":
        "e46e54be00ae19a564d3b37ea5d247bab878d493c5b738d3da34784682bbffcd",
    "E02_compare.en": "04dd7de67bf16c2cd759dd70f6ee450d224f731c0a71d661fe25d1913d6d504c",
    "P15_center.en": "6f28114d903cbc34c29a98d5b975c6bf5c0c9e48b00b752240db9f3f22f25ecd",
    "P16_metric_meaning.zh-TW": "854d50f0fe2cec199d55514ade5572374c02d1e40017f8239eb1a8c2cfff6d01",
    "P22_center_compare.ja": "c2d18ae99624c7f2196a39ba7a3d76c7594a987a278178a9f7398ea45bb6a750",
}
MAX_CALLS = 8
CALL_SECONDS = 300.0
RUN_SECONDS = MAX_CALLS * CALL_SECONDS + 120.0
PROFILE = observed.PROFILE
REGION = observed.REGION
TRANSPORT = observed.TRANSPORT
POLICIES = observed.POLICIES
ROOT_KEYS = ("outcome", "recipe_id", "recipe_version", "request", "clarification")
REQUEST_KEYS = ("center_code", "start", "end", "timezone", "current", "baseline", "top_k")
SCOPE_KEYS = ("metrics", "start", "end", "timezone", "center_id")
VALUE_KEYS = ("type", "scope", "value", "request")
OUTCOMES = ("request", "clarify", "declined")
RECIPES = ("overview", "compare", "breakdown")
_ROW_METADATA = ("case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
                 "oracle_id", "question_sha256")
_PRIVATE_NAME = re.compile(r"[0-9]{2}-[A-Za-z0-9_.-]{1,80}\.json")
_STATUSES = ("pending", "in_progress", "completed", "not_run")
_ROW_FIELDS = ("order", "case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
               "oracle_id", "question_sha256", "status", "runtime_invoked", "client_http_attempts",
               "outcome", "actual_action", "checked_wrong", "operational_error", "error_code",
               "invalid_request_reason", "evidence", "fingerprint", "private_capture", "runner_error_code")


def settings() -> dict:
    return {"version": VERSION, "model": PROFILE, "response_mode": "bedrock_converse_normalized",
            "max_runtime_invocations": MAX_CALLS, "max_client_http_attempts": MAX_CALLS,
            "attempts_per_input": 1, "call_timeout_seconds": CALL_SECONDS,
            "run_timeout_seconds": RUN_SECONDS, "max_output_tokens": 2048, "concurrency": 1,
            "client_retries": 0, "client_fallback": 0, "resend": 0, "repair": 0,
            "continuation": 0, "resume": False,
            "execution": "owner_granted_diagnostic_regression_data_only"}


def stop_policy() -> dict:
    return {"version": VERSION,
            "admission": "Source, DB, asset, question, identity, provider and route drift stop before credentials.",
            "attempts": "One client attempt per input; no retry, resend, repair, fallback, resume or second run.",
            "streaks": "Two consecutive network failures or timeouts stop the run.",
            "budget": "Remaining run budget below one call stops before the next send.",
            "preservation": "A stopped or interrupted run is preserved, never rerun for a cleaner result.",
            "evidence": "Public report is closed evidence; raw completions stay in the private sidecar only."}


def command_template(commit: str) -> list[str]:
    return [".venv/bin/python", "tools/p3_reason_diagnostic.py", "--live",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", commit,
            "--owner-authorization-reference", "<ISSUE_74_COMMENT_URL>",
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>", "--gateway-retries", "disabled",
            "--gateway-fallback", "disabled", "--gateway-cache", "disabled",
            "--output-dir", "<FRESH_DIAGNOSTIC_OUTPUT>"]


def _hash(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise assets.P3Error("invalid_manifest")
    return value


def _enum(item: dict, key: str, values: tuple[str, ...]) -> str:
    if key not in item:
        return "missing"
    value = item[key]
    return value if isinstance(value, str) and value in values else "other"


def _keys(item: dict, known: tuple[str, ...]) -> tuple[list[str], int]:
    return (sorted(key for key in item if key in known),
            sum(1 for key in item if key not in known))


def fingerprint(content: str | None) -> dict:
    """Closed structure of a completion: contract key names, enum-or-other values and counts only."""
    result: dict = {"version": FINGERPRINT_VERSION, "normalized": content is not None, "parsed": False}
    if content is None:
        return result
    try:
        data = model.strict_json(content)
    except ModelError:
        return result
    result["parsed"] = True
    result["root_type"] = {dict: "object", list: "array", str: "string", bool: "boolean",
                           type(None): "null"}.get(type(data), "number")
    if not isinstance(data, dict):
        return result
    result["root_known_keys"], result["root_unknown_key_count"] = _keys(data, ROOT_KEYS)
    result["outcome"] = _enum(data, "outcome", OUTCOMES)
    result["recipe_id"] = _enum(data, "recipe_id", RECIPES)
    request = data.get("request")
    if isinstance(request, dict):
        result["request_known_keys"], result["request_unknown_key_count"] = _keys(request, REQUEST_KEYS)
        scopes = {}
        for role in ("current", "baseline"):
            scope = request.get(role)
            if isinstance(scope, dict):
                known, unknown = _keys(scope, SCOPE_KEYS)
                scopes[role] = {"known_keys": known, "unknown_key_count": unknown}
        result["scopes"] = scopes
    clarification = data.get("clarification")
    if isinstance(clarification, dict):
        result["kind"] = _enum(clarification, "kind", KINDS)
        choices = clarification.get("choices")
        result["choice_count"] = len(choices) if isinstance(choices, list) else None
        if isinstance(choices, list):
            result["choice_key_sets_valid"] = all(
                isinstance(choice, dict) and set(choice) == {"id", "semantic_value"} for choice in choices)
            types, unknown = [], 0
            for choice in choices:
                value = choice.get("semantic_value") if isinstance(choice, dict) else None
                if isinstance(value, dict):
                    types.append(_enum(value, "type", KINDS))
                    unknown += _keys(value, VALUE_KEYS)[1]
                else:
                    types.append("missing")
            result["semantic_value_types"] = types
            result["semantic_value_unknown_key_count"] = unknown
    return result


def _check_fingerprint(value: object) -> None:
    allowed = {"version", "normalized", "parsed", "root_type", "root_known_keys", "root_unknown_key_count",
               "outcome", "recipe_id", "request_known_keys", "request_unknown_key_count", "scopes",
               "kind", "choice_count", "choice_key_sets_valid", "semantic_value_types",
               "semantic_value_unknown_key_count"}
    if (not isinstance(value, dict) or not set(value) <= allowed or value.get("version") != FINGERPRINT_VERSION
            or type(value.get("normalized")) is not bool or type(value.get("parsed")) is not bool):
        raise assets.P3Error("invalid_asset")
    enums = {"root_type": ("object", "array", "string", "number", "boolean", "null"),
             "outcome": (*OUTCOMES, "other", "missing"), "recipe_id": (*RECIPES, "other", "missing"),
             "kind": (*KINDS, "other", "missing")}
    for key, values in enums.items():
        if key in value and value[key] not in values:
            raise assets.P3Error("invalid_asset")
    for key, known in (("root_known_keys", ROOT_KEYS), ("request_known_keys", REQUEST_KEYS)):
        if key in value and (not isinstance(value[key], list) or not set(value[key]) <= set(known)):
            raise assets.P3Error("invalid_asset")
    for key in ("root_unknown_key_count", "request_unknown_key_count", "semantic_value_unknown_key_count"):
        if key in value and (type(value[key]) is not int or value[key] < 0):
            raise assets.P3Error("invalid_asset")
    if "choice_count" in value and value["choice_count"] is not None and (
            type(value["choice_count"]) is not int or value["choice_count"] < 0):
        raise assets.P3Error("invalid_asset")
    if "choice_key_sets_valid" in value and type(value["choice_key_sets_valid"]) is not bool:
        raise assets.P3Error("invalid_asset")
    if "semantic_value_types" in value and (
            not isinstance(value["semantic_value_types"], list)
            or any(item not in (*KINDS, "other", "missing") for item in value["semantic_value_types"])):
        raise assets.P3Error("invalid_asset")
    if "scopes" in value:
        if not isinstance(value["scopes"], dict) or not set(value["scopes"]) <= {"current", "baseline"}:
            raise assets.P3Error("invalid_asset")
        for scope in value["scopes"].values():
            if (not isinstance(scope, dict) or set(scope) != {"known_keys", "unknown_key_count"}
                    or not isinstance(scope["known_keys"], list)
                    or not set(scope["known_keys"]) <= set(SCOPE_KEYS)
                    or type(scope["unknown_key_count"]) is not int or scope["unknown_key_count"] < 0):
                raise assets.P3Error("invalid_asset")


def _completion_text(body: bytes) -> str | None:
    try:
        normalized = normalize_converse_response(GatewayResponse(body, 200))
        data = model.strict_json(normalized.body, code="invalid_response")
        return data["choices"][0]["message"]["content"]
    except (ModelError, LookupError, TypeError):
        return None


def _private_dir(output_dir: Path) -> Path:
    return output_dir.with_name(output_dir.name + "-private")


def _create_private_dir(output_dir: Path) -> Path:
    private_dir = _private_dir(output_dir)
    smoke._no_symlinks(private_dir)
    try:
        private_dir.mkdir(mode=0o700)
    except FileExistsError:
        raise assets.P3Error("artifact_conflict") from None
    except OSError:
        raise assets.P3Error("artifact_io") from None
    return private_dir


def _write_private(private_dir: Path, order: int, case_id: str, body: bytes) -> tuple[dict, str | None]:
    """Exclusive 0600 sidecar; the public report keeps only its digest, size and name."""
    name = f"{order:02d}-{case_id}.json"
    if _PRIVATE_NAME.fullmatch(name) is None:
        raise assets.P3Error("invalid_manifest")
    text = _completion_text(body)
    payload = {"case_id": case_id, "body_sha256": hashlib.sha256(body).hexdigest(),
               "completion_text": text,
               "raw_body_utf8": None if text is not None else body.decode("utf-8", errors="replace")}
    smoke._no_symlinks(private_dir)
    info = private_dir.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise assets.P3Error("artifact_conflict")
    try:
        fd = os.open(private_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(model.canonical_json(payload) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise assets.P3Error("artifact_conflict") from None
    except OSError:
        raise assets.P3Error("artifact_io") from None
    return {"reference": name, "sha256": payload["body_sha256"], "bytes": len(body),
            "text_captured": text is not None}, text


class _CapturingClient:
    """One attempt for one input; the raw response body goes to the private sink only."""

    def __init__(self, client, sink):
        self.client, self.sink, self.used = client, sink, False

    @property
    def config(self):
        return self.client.config

    @property
    def http_attempts(self):
        return self.client.http_attempts

    def safe_export(self, value):
        return self.client.safe_export(value)

    async def complete(self, *args, **kwargs):
        if self.used or self.http_attempts >= MAX_CALLS:
            raise assets.P3Error("attempt_budget")
        self.used = True
        response = await self.client.complete(*args, **kwargs)
        self.sink(response.body)
        return response


def _materials():
    intake_path, panel_path = historical._reference(INTAKE), historical._reference(PANEL)
    source_paths = {"intake": intake_path, "cases": panel_path.parent / "formal-cases-v2-draft.json",
                    "oracles": panel_path.parent / "formal-oracles-v2-draft.json", "panel": panel_path}
    pinned = {name: historical._pin(path, observed.PINS[name]) for name, path in source_paths.items()}
    panel, _ = admission._policy_materials(intake_path, panel_path, allocation.V2)
    return panel, pinned


def _select_cases(panel) -> tuple:
    by_id = {case.case_id: case for case in panel.cases}
    if len(set(CASE_IDS)) != MAX_CALLS or set(CASE_IDS) != set(QUESTION_SHA256):
        raise assets.P3Error("invalid_manifest")
    cases = []
    for case_id in CASE_IDS:
        case = by_id.get(case_id)
        if case is None or hashlib.sha256(case.question.encode()).hexdigest() != QUESTION_SHA256[case_id]:
            raise assets.P3Error("manifest_drift")
        cases.append(case)
    return tuple(cases)


def _verify_archive() -> dict:
    """The archived #70 rows must carry the same questions; read-only, no reinterpretation."""
    path = historical._reference(SOURCE_REPORT)
    pin = historical._pin(path, SOURCE_REPORT_SHA256)
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    rows = {row.get("case_id"): row for row in report.get("results", []) if isinstance(row, dict)}
    for case_id in CASE_IDS:
        row = rows.get(case_id)
        if row is None or row.get("question_sha256") != QUESTION_SHA256[case_id]:
            raise assets.P3Error("manifest_drift")
    return {"reference": historical._location(path), "sha256": pin["sha256"]}


def _verify_source(database: Path, panel, accepted_commit: str) -> dict:
    if smoke._fixture_identity(database) != observed.DB_SHA256:
        raise assets.P3Error("db_drift")
    source = evaluator._source_identity(panel, None)
    bedrock_probe.old_candidate._checkout(source, accepted_commit)
    return source


def _admitted_client(env_file: Path):
    client = client_from_env(env_file=env_file)
    if (type(client) is not BedrockClient or type(client.config) is not BedrockConfig
            or client.config.region != REGION or client.config.model != PROFILE
            or client.config.expected_model is not None
            or client.config.max_call_timeout_seconds != CALL_SECONDS
            or client.config.transport_security != TRANSPORT):
        raise assets.P3Error("invalid_configuration")
    if evaluator._attempts(client) != 0:
        raise assets.P3Error("attempt_budget")
    return client


def _row(order: int, case) -> dict:
    return {"order": order, "case_id": case.case_id, "family_id": case.family_id, "language": case.language,
            "expected_branch": case.expected_branch, "cohort": case.cohort, "exposure": case.exposure,
            "oracle_id": case.oracle_id, "question_sha256": QUESTION_SHA256[case.case_id],
            "status": "pending", "runtime_invoked": False, "client_http_attempts": 0,
            "outcome": None, "actual_action": None, "checked_wrong": None, "operational_error": None,
            "error_code": None, "invalid_request_reason": None, "evidence": None,
            "fingerprint": None, "private_capture": None, "runner_error_code": None}


def _new_report(manifest: dict, cases) -> dict:
    return {"version": VERSION, "purpose": PURPOSE, "evidence_class": EVIDENCE_CLASS,
            "promotion_eligible": False, "status": "incomplete", "origin": "live",
            "stop_reason": None, "error_code": None, "manifest_sha256": assets.digest(manifest),
            "accepted_commit": manifest["accepted_commit"],
            "owner_authorization_reference": manifest["owner_authorization_reference"],
            "requested_profile": PROFILE, "returned_model": None, "transport_security": None,
            "runtime_invocations": 0, "client_http_attempts": 0, "attempt_budget_used": 0,
            "upstream_inference_attempts": None, "elapsed_seconds": 0.0,
            "network_failure_streak": 0, "timeout_streak": 0,
            "private_capture": {"directory": manifest["private_directory"], "files": 0},
            "results": [_row(index + 1, case) for index, case in enumerate(cases)],
            "scope": "Eight-input reason diagnostic; regression data only, not quality or promotion evidence."}


def _summary(report: dict) -> dict:
    rows = report["results"]
    completed = [row for row in rows if row["status"] == "completed"]
    return {"completed_inputs": len(completed), "input_count": len(rows),
            "outcomes": {name: sum(1 for row in completed if row["outcome"] == name)
                         for name in sorted({row["outcome"] for row in completed if row["outcome"]})},
            "invalid_request_reasons": {name: sum(1 for row in completed if row["invalid_request_reason"] == name)
                                        for name in sorted({row["invalid_request_reason"] for row in completed
                                                            if row["invalid_request_reason"]})},
            "checked_wrong": sum(1 for row in completed if row["checked_wrong"]),
            "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False}


def _stop(report: dict, code: str) -> None:
    report.update(status="incomplete", stop_reason=code, error_code=code)


def _persist(artifacts, report: dict, client) -> None:
    report["summary"] = _summary(report)
    artifacts.persist(evaluator._safe(report, client))


async def run_live(database: Path, output_dir: Path, *, accepted_commit: str, owner_reference: str,
                   env_file: Path, gateway_policies: dict, clock=time.monotonic) -> dict:
    started = clock()
    if not isinstance(accepted_commit, str) or re.fullmatch(r"[0-9a-f]{40}", accepted_commit) is None:
        raise assets.P3Error("invalid_manifest")
    if not isinstance(owner_reference, str) or OWNER.fullmatch(owner_reference) is None:
        raise assets.P3Error("invalid_manifest")
    attestation = smoke.policy_attestation(gateway_policies, required=True)
    if attestation != smoke.policy_attestation(POLICIES, required=True) or not isinstance(env_file, Path):
        raise assets.P3Error("invalid_configuration")
    panel, pinned = _materials()
    cases = _select_cases(panel)
    archive = _verify_archive()
    source = _verify_source(database, panel, accepted_commit)
    identities = observed._current_identities()
    run_slot = observed._run_slot(output_dir)
    manifest = {"version": VERSION, "purpose": PURPOSE, "evidence_class": EVIDENCE_CLASS,
                "promotion_eligible": False, "accepted_commit": accepted_commit,
                "owner_authorization_reference": owner_reference, "run_slot": run_slot,
                "private_directory": observed._run_slot(_private_dir(output_dir)),
                "candidate": bedrock_probe.candidate_identity(), "source_identity": source, **identities,
                "database_sha256": observed.DB_SHA256, "assets": pinned, "source_report": archive,
                "panel_id": panel.panel_id, "case_ids": list(CASE_IDS),
                "question_sha256": dict(QUESTION_SHA256), "grader_version": p3_grading.VERSION,
                "settings": settings(), "settings_sha256": assets.digest(settings()),
                "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
                "gateway_policy": attestation, "transport_security": TRANSPORT,
                "data_boundary": "eight_observed_synthetic_questions_japan_only_regression_data",
                "upstream_inference_attempts": None, "command_template": command_template(accepted_commit)}
    artifacts = smoke._Artifacts(output_dir, manifest)
    private_dir = _create_private_dir(output_dir)
    report = _new_report(manifest, cases)
    _persist(artifacts, report, None)
    client = None
    active = None
    try:
        smoke._no_symlinks(env_file)
        client = _admitted_client(env_file)
        evaluator._safe(manifest, client)
        report["transport_security"] = client.config.transport_security
        _persist(artifacts, report, client)
        for index, case in enumerate(cases):
            remaining = RUN_SECONDS - (clock() - started)
            if remaining < CALL_SECONDS:
                raise assets.P3Error("panel_budget")
            active = report["results"][index]
            before = evaluator._attempts(client)
            captured: list[bytes] = []
            active.update(status="in_progress", runtime_invoked=True)
            report["runtime_invocations"] += 1
            _persist(artifacts, report, client)
            wrapper = _CapturingClient(client, captured.append)
            result = await interpret_recipe_and_execute(case.question, database, wrapper,
                                                        timeout_seconds=CALL_SECONDS, clock=clock)
            count = evaluator._attempts(client)
            if count - before not in (0, 1) or count > MAX_CALLS or len(captured) != count - before:
                raise assets.P3Error("attempt_budget")
            grade = p3_grading.grade(result, panel.oracle_for(case))
            evidence = live._evidence(result.evidence, requested_profile=PROFILE)
            text = None
            if captured:
                active["private_capture"], text = _write_private(private_dir, index + 1, case.case_id, captured[0])
                report["private_capture"]["files"] += 1
            active.update(status="completed", client_http_attempts=count - before,
                          outcome=grade["outcome"], actual_action=grade["actual_action"],
                          checked_wrong=grade["checked_wrong"], operational_error=grade["operational_error"],
                          error_code=result.error.code if result.error else None,
                          invalid_request_reason=evidence.get("invalid_request_reason"),
                          evidence=evidence, fingerprint=fingerprint(text) if captured else None)
            report.update(client_http_attempts=count, attempt_budget_used=count)
            code = active["error_code"]
            report["network_failure_streak"] = report["network_failure_streak"] + 1 if code in evaluator.NETWORK_CODES else 0
            report["timeout_streak"] = report["timeout_streak"] + 1 if code == "timeout" else 0
            _persist(artifacts, report, client)
            active = None
            if result.error is not None and result.error.stop_reason:
                raise assets.P3Error(result.error.stop_reason)
            if report["network_failure_streak"] >= 2:
                raise assets.P3Error("consecutive_network_failures")
            if report["timeout_streak"] >= 2:
                raise assets.P3Error("consecutive_timeouts")
        report["status"] = "complete"
    except (KeyboardInterrupt, asyncio.CancelledError):
        _stop(report, "interrupted")
    except evaluator._SAFE_ERRORS as exc:
        _stop(report, exc.stop_reason or exc.code if isinstance(exc, ModelError) else exc.code)
    except OSError as exc:
        _stop(report, "artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io")
    except evaluator._INTERNAL_ERRORS:
        _stop(report, "internal_failure")
    finally:
        if active is not None:
            active["runner_error_code"] = report["stop_reason"]
            active["status"] = "completed" if active["evidence"] is not None else "not_run"
            if client is not None:
                active["client_http_attempts"] = min(1, max(0, evaluator._attempts(client) - before))
        for row in report["results"]:
            if row["status"] == "pending":
                row["status"] = "not_run"
        if client is not None:
            count = evaluator._attempts(client)
            report.update(client_http_attempts=count, attempt_budget_used=count)
        report["elapsed_seconds"] = round(max(0.0, clock() - started), 6)
        try:
            _persist(artifacts, report, client)
        except evaluator._SAFE_ERRORS:
            pass
    return report


def read_report(path: Path) -> dict:
    """Closed archived validation; needs no source checkout, DB, credentials, network or private sidecar."""
    if path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    manifest = assets.read_asset(path.parent / "manifest.json")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    for value in (manifest, report):
        if "completion_text" in model.canonical_json(value) or "raw_body_utf8" in model.canonical_json(value):
            raise assets.P3Error("leakage_risk")
    if (manifest.get("version") != VERSION or manifest.get("evidence_class") != EVIDENCE_CLASS
            or manifest.get("promotion_eligible") is not False or manifest.get("case_ids") != list(CASE_IDS)
            or manifest.get("question_sha256") != QUESTION_SHA256 or manifest.get("settings") != settings()
            or manifest.get("stop_policy") != stop_policy()
            or manifest.get("gateway_policy") != smoke.policy_attestation(POLICIES, required=True)
            or not isinstance(manifest.get("owner_authorization_reference"), str)
            or OWNER.fullmatch(manifest["owner_authorization_reference"]) is None
            or manifest.get("run_slot") != observed._run_slot(path.parent)
            or manifest.get("private_directory") != observed._run_slot(_private_dir(path.parent))):
        raise assets.P3Error("invalid_manifest")
    expected = {"version", "purpose", "evidence_class", "promotion_eligible", "status", "origin", "stop_reason",
                "error_code", "manifest_sha256", "accepted_commit", "owner_authorization_reference",
                "requested_profile", "returned_model", "transport_security", "runtime_invocations",
                "client_http_attempts", "attempt_budget_used", "upstream_inference_attempts", "elapsed_seconds",
                "network_failure_streak", "timeout_streak", "private_capture", "results", "scope", "summary"}
    if (set(report) != expected or report["version"] != VERSION or report["evidence_class"] != EVIDENCE_CLASS
            or report["promotion_eligible"] is not False or report["origin"] != "live"
            or report["manifest_sha256"] != assets.digest(manifest)
            or report["accepted_commit"] != manifest["accepted_commit"]
            or report["owner_authorization_reference"] != manifest["owner_authorization_reference"]
            or report["requested_profile"] != PROFILE or report["returned_model"] is not None
            or report["transport_security"] not in (None, TRANSPORT)
            or report["status"] not in ("incomplete", "complete")
            or report["upstream_inference_attempts"] is not None
            or any(report[key] is not None and report[key] not in assets.SAFE_CODES | set(live._ERRORS)
                   for key in ("stop_reason", "error_code"))
            or not isinstance(report["private_capture"], dict)
            or set(report["private_capture"]) != {"directory", "files"}
            or report["private_capture"]["directory"] != manifest["private_directory"]
            or len(report["results"]) != MAX_CALLS):
        raise assets.P3Error("invalid_asset")
    for key in ("runtime_invocations", "client_http_attempts", "attempt_budget_used"):
        live._number(report[key], integer=True, maximum=MAX_CALLS, optional=False)
    live._number(report["elapsed_seconds"], optional=False)
    for key in ("network_failure_streak", "timeout_streak"):
        live._number(report[key], integer=True, maximum=2, optional=False)
    live._number(report["private_capture"]["files"], integer=True, maximum=MAX_CALLS, optional=False)
    completed = 0
    captures = 0
    for index, (row, case_id) in enumerate(zip(report["results"], CASE_IDS)):
        if (set(row) != set(_ROW_FIELDS) or row["order"] != index + 1 or row["case_id"] != case_id
                or row["question_sha256"] != QUESTION_SHA256[case_id] or row["status"] not in _STATUSES
                or type(row["runtime_invoked"]) is not bool
                or row["outcome"] not in (None, *assets.OUTCOMES)
                or row["actual_action"] not in (None, *assets.BRANCHES)
                or row["checked_wrong"] not in (None, True, False)
                or any(row[key] is not None and row[key] not in assets.SAFE_CODES | set(live._ERRORS)
                       for key in ("operational_error", "error_code", "runner_error_code"))
                or row["invalid_request_reason"] not in (None, *INVALID_REQUEST_REASONS)):
            raise assets.P3Error("invalid_asset")
        live._number(row["client_http_attempts"], integer=True, maximum=1, optional=False)
        if row["evidence"] is not None:
            if not live._same(live._evidence(row["evidence"], requested_profile=PROFILE), row["evidence"]):
                raise assets.P3Error("leakage_risk")
            if row["evidence"].get("invalid_request_reason") != row["invalid_request_reason"]:
                raise assets.P3Error("invalid_asset")
        if row["fingerprint"] is not None:
            _check_fingerprint(row["fingerprint"])
        if row["private_capture"] is not None:
            capture = row["private_capture"]
            if (not isinstance(capture, dict)
                    or set(capture) != {"reference", "sha256", "bytes", "text_captured"}
                    or capture["reference"] != f"{index + 1:02d}-{case_id}.json"
                    or type(capture["bytes"]) is not int or capture["bytes"] < 0
                    or type(capture["text_captured"]) is not bool):
                raise assets.P3Error("invalid_asset")
            _hash(capture["sha256"])
            captures += 1
        if row["status"] == "completed":
            completed += 1
            if not row["runtime_invoked"] or row["outcome"] is None:
                raise assets.P3Error("invalid_asset")
        elif row["status"] in ("pending", "not_run") and row["evidence"] is not None:
            raise assets.P3Error("invalid_asset")
        if row["private_capture"] is not None and row["client_http_attempts"] != 1:
            raise assets.P3Error("invalid_asset")
    if (report["private_capture"]["files"] != captures
            or report["client_http_attempts"] != sum(row["client_http_attempts"] for row in report["results"])
            or report["runtime_invocations"] != sum(row["runtime_invoked"] for row in report["results"])
            or report["status"] == "complete" and (
                completed != MAX_CALLS or report["stop_reason"] is not None or report["error_code"] is not None)):
        raise assets.P3Error("invalid_asset")
    summary = report["summary"]
    if not live._same(summary, _summary(report)):
        raise assets.P3Error("invalid_asset")
    return report


def main(argv=None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("db", "env-file", "output-dir", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        allowed = ({"live", "db", "env_file", "output_dir", "accepted_commit", "owner_authorization_reference",
                    "gateway_retries", "gateway_fallback", "gateway_cache"} if args.live
                   else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        if args.live:
            policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
            asyncio.run(run_live(args.db, args.output_dir, accepted_commit=args.accepted_commit,
                                 owner_reference=args.owner_authorization_reference,
                                 env_file=args.env_file, gateway_policies=policies))
        report = read_report(args.output_dir / "report.json" if args.live else args.report_path)
        result = {key: report[key] for key in (
            "version", "status", "stop_reason", "error_code", "runtime_invocations", "client_http_attempts",
            "requested_profile", "returned_model", "evidence_class", "promotion_eligible", "summary")}
        result["results"] = [{key: row[key] for key in (
            "case_id", "expected_branch", "outcome", "actual_action", "error_code",
            "invalid_request_reason", "fingerprint")} for row in report["results"]]
        print(model.canonical_json(result))
        return 0 if result["status"] == "complete" else 1
    except (*evaluator._SAFE_ERRORS, bedrock_probe.probe.ProbeError) as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, *evaluator._INTERNAL_ERRORS):
        print('{"status":"incomplete","error_code":"invalid_manifest"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
