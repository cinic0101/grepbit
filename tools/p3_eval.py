#!/usr/bin/env python3
"""Offline P3 evaluator: default preparation, explicit fake-run and report inspection."""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from copy import deepcopy
import math
from pathlib import Path
import re
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from grepbit.gateway import GatewayClient, GatewayConfig, ModelError
from grepbit.model import canonical_json, strict_json
from grepbit.recipe_model import RecipeInterpretation, interpret_recipe_and_execute
from tools import p3_assets, p3_expectations, p3_formal_policy, p3_grading, p3_scoring, recipe_smoke, smoke
from tools.evaluation_evidence import commit_terminal, stage_terminal
from tools.p3_assets import P3Error, Panel

MANIFEST_VERSION = "p3-manifest-v1"
REPORT_VERSION = "p3-report-v1"
POLICY_MANIFEST_VERSION = "p3-manifest-v2"
POLICY_REPORT_VERSION = "p3-report-v2"
SCRIPT_VERSION = "p3-fake-responses-v1"
DEFAULT_PANEL = ROOT / "evals/p3/development-panel-v1.json"
DEFAULT_RESPONSES = ROOT / "evals/p3/development-responses-v1.json"
MAX_REPORT_BYTES = 16 * 1024 * 1024
NETWORK_CODES = frozenset({"transport_error", "gateway_error", "rate_limited"})
_INTERNAL_ERRORS = recipe_smoke._INTERNAL_ERRORS
_SAFE_ERRORS = (P3Error, smoke.SmokeError, recipe_smoke.RecipeSmokeError, ModelError)
_INPUT_FIELDS = {
    "order", "case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
    "provenance", "semantic_signature", "must_pass", "observational", "oracle_id",
    "question_sha256", "question_reference",
}
_MANIFEST_FIELDS = {
    "manifest_version", "evaluator_version", "panel_id", "panel_kind", "identities",
    "preparation", "acceptance_boundary", "database_sha256", "assets", "fake_responses",
    "settings", "settings_sha256", "stop_policy", "stop_policy_sha256", "order", "inputs",
    "oracles", "upstream_inference_attempts",
}
_ATTEMPT_STATES = {"not_started", "not_returned", "matched", "missing", "invalid", "mismatch"}


def settings(input_count: int) -> dict:
    if type(input_count) is not int or not 1 <= input_count <= p3_assets.MAX_INPUTS:
        raise P3Error("invalid_panel")
    return {
        "model": smoke.MODEL, "response_mode": "json_content", "inputs": input_count,
        "max_client_http_attempts": input_count, "concurrency": 1, "client_retries": 0,
        "repairs": 0, "stream": False, "temperature": 0, "max_tokens": 2048,
        "call_timeout_seconds": 60.0, "panel_timeout_seconds": 60.0 * input_count + 120.0,
        "max_input_bytes": 4096, "max_request_bytes": 32768, "max_response_bytes": 131072,
        "max_database_bytes": 16 * 1024 * 1024, "raw_diagnostics": False,
        "execution": "explicit_mock_transport_only",
    }


def stop_policy() -> dict:
    return {
        **recipe_smoke.stop_policy(), "version": "p3-stops-v1",
        "runtime_attempt_evidence": "Missing, invalid or mismatched counts stop independently of client counts.",
        "unreturned_call": "Keep the durable in-progress reservation; do not label it not_run.",
        "semantic_failures": "Grade every admitted input unless an explicit operational stop occurs.",
        "live": "Not admitted; live attempts are always zero and upstream inference work is unknown.",
    }


def _document(path: Path, maximum: int, code: str) -> dict:
    try:
        smoke._no_symlinks(path)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise P3Error(code)
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise P3Error(code)
        value = strict_json(raw)
        if not isinstance(value, dict):
            raise P3Error(code)
        return value
    except (OSError, ModelError, RecursionError):
        raise P3Error(code) from None


def _admitted(panel: Panel) -> None:
    if panel.kind == "formal":
        raise P3Error("formal_not_admitted")
    if panel.kind != "development" or not 1 <= len(panel.cases) <= p3_assets.MAX_INPUTS:
        raise P3Error("invalid_panel")


def load_fake_responses(path: Path, panel: Panel) -> tuple[dict, ...]:
    """Validate only the script envelope/order, leaving action parsing to production."""
    _admitted(panel)
    data = _document(path, p3_assets.MAX_ASSET_BYTES, "invalid_fake_script")
    if (set(data) != {"version", "responses"} or data["version"] != SCRIPT_VERSION
            or not isinstance(data["responses"], list) or len(data["responses"]) != len(panel.cases)):
        raise P3Error("invalid_fake_script")
    actions = []
    for item, case in zip(data["responses"], panel.cases):
        if (not isinstance(item, dict) or set(item) != {"case_id", "action"}
                or item["case_id"] != case.case_id or not isinstance(item["action"], dict)):
            raise P3Error("invalid_fake_script")
        actions.append(item["action"])
    return tuple(actions)


def fake_client(panel: Panel, responses_path: Path) -> GatewayClient:
    actions = load_fake_responses(responses_path, panel)
    questions = tuple(case.question for case in panel.cases)
    index = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal index
        try:
            body = strict_json(request.content)
            if index >= len(actions) or body["messages"][1]["content"] != questions[index]:
                raise P3Error("invalid_fake_script")
        except (ModelError, LookupError, TypeError):
            raise P3Error("invalid_fake_script") from None
        action = actions[index]
        index += 1
        return httpx.Response(200, json={
            "model": smoke.MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": canonical_json(action)}}],
        })

    return GatewayClient(GatewayConfig("https://p3-offline.invalid/v1", "p3-synthetic-token"),
                         transport=httpx.MockTransport(respond))


def _pin(path: Path) -> dict:
    try:
        smoke._no_symlinks(path)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise P3Error("source_identity_failure")
        with path.open("rb") as stream:
            raw = stream.read(p3_assets.MAX_ASSET_BYTES + 1)
        if len(raw) > p3_assets.MAX_ASSET_BYTES:
            raise P3Error("source_identity_failure")
        return {"reference": path.name, "sha256": smoke._digest(raw)}
    except OSError:
        raise P3Error("source_identity_failure") from None


def _asset_paths(panel: Panel, responses_path: Path | None) -> dict[str, Path]:
    paths = {"panel": panel.path, "cases": panel.cases_path, "oracles": panel.oracles_path}
    if responses_path is not None:
        paths["responses"] = responses_path
    return paths


def _source_identity(panel: Panel, responses_path: Path | None, formal_freeze: Path | None = None) -> dict:
    identity = recipe_smoke._source_identity()
    identity["evidence_expectations"] = p3_expectations.identity()
    for path in sorted((ROOT / "tools").glob("p3_*.py")):
        identity["files_sha256"][path.relative_to(ROOT).as_posix()] = _pin(path)["sha256"]
    for name in ("pyproject.toml", "uv.lock"):
        identity["files_sha256"][name] = _pin(ROOT / name)["sha256"]
    for name, path in _asset_paths(panel, responses_path).items():
        identity["files_sha256"][f"p3_asset:{name}"] = _pin(path)["sha256"]
    if formal_freeze is not None:
        identity["files_sha256"]["p3_asset:formal_freeze"] = _pin(formal_freeze)["sha256"]
    return identity


def _preparation_panel(database: Path, panel_path: Path, formal_freeze: Path | None,
                       accepted_commit: str | None) -> tuple[Panel, dict | None]:
    if formal_freeze is None:
        return p3_assets.load_panel(panel_path), None
    if accepted_commit is None:
        raise P3Error("formal_not_admitted")
    from tools.p3_admission import load_frozen_panel
    return load_frozen_panel(formal_freeze, database, panel_path, accepted_commit=accepted_commit)


def build_manifest(
    database: Path, *, panel_path: Path = DEFAULT_PANEL, responses_path: Path | None = None,
    accepted_commit: str | None = None, formal_freeze: Path | None = None,
) -> dict:
    panel, allocation_policy = _preparation_panel(database, panel_path, formal_freeze, accepted_commit)
    if formal_freeze is None:
        _admitted(panel)
    else:
        if panel.kind != "formal" or accepted_commit is None or responses_path is not None:
            raise P3Error("formal_not_admitted")
        from tools.p3_admission import validate_freeze
        validate_freeze(formal_freeze, database, panel_path, accepted_commit=accepted_commit)
    identity = _source_identity(panel, responses_path, formal_freeze)
    if accepted_commit is not None:
        recipe_smoke._accepted(identity, accepted_commit)
    if responses_path is not None:
        load_fake_responses(responses_path, panel)
    limits, policy = settings(len(panel.cases)), stop_policy()
    manifest = {
        "manifest_version": MANIFEST_VERSION, "evaluator_version": p3_grading.VERSION,
        "panel_id": panel.panel_id, "panel_kind": panel.kind, "identities": identity,
        "preparation": {"kind": "accepted" if accepted_commit is not None else "candidate",
                        "accepted_commit": accepted_commit},
        "acceptance_boundary": "Preparation is not owner acceptance or live authorization.",
        "database_sha256": smoke._fixture_identity(database),
        "assets": {name: _pin(path) for name, path in _asset_paths(panel, responses_path).items()},
        "fake_responses": SCRIPT_VERSION if responses_path is not None else None,
        "settings": limits, "settings_sha256": p3_assets.digest(limits),
        "stop_policy": policy, "stop_policy_sha256": p3_assets.digest(policy),
        "order": [case.case_id for case in panel.cases], "inputs": panel.inputs(),
        "oracles": [{"oracle_id": oracle.oracle_id, "revision": oracle.revision,
                     "sha256": p3_assets.digest(oracle.to_dict()), "value": oracle.to_dict()}
                    for oracle in panel.oracles],
        "upstream_inference_attempts": None,
    }
    if formal_freeze is not None:
        manifest["assets"]["formal_freeze"] = _pin(formal_freeze)
        if allocation_policy is not None:
            manifest["manifest_version"] = POLICY_MANIFEST_VERSION
            manifest["allocation_policy"] = allocation_policy
        validate_freeze(formal_freeze, database, panel_path, accepted_commit=accepted_commit)
    if (_source_identity(panel, responses_path, formal_freeze) != identity
            or _preparation_panel(database, panel_path, formal_freeze, accepted_commit) != (panel, allocation_policy)):
        raise P3Error("manifest_drift")
    return manifest


def _empty_grade() -> dict:
    return {"version": p3_grading.VERSION, "outcome": None, "actual_action": None,
            "layers": dict.fromkeys(p3_grading.LAYERS, "not_assessed"), "checked_wrong": False,
            "actual_signature": None, "operational_error": None, "pack_status": None,
            "missing_required_slots": [], "diagnostics": []}


def _new_report(manifest: dict, origin: str) -> dict:
    report = {
        "report_version": REPORT_VERSION, "status": "incomplete", "origin": origin,
        "stop_reason": None, "error_code": None, "manifest_sha256": p3_assets.digest(manifest),
        "panel_id": manifest["panel_id"], "panel_kind": manifest["panel_kind"],
        "preparation": manifest["preparation"],
        "client_http_attempts": 0, "live_model_attempts": 0, "possible_in_flight_attempts": 0,
        "attempt_budget_used": 0, "upstream_inference_attempts": None, "elapsed_seconds": 0.0,
        "network_failure_streak": 0, "timeout_streak": 0,
        "results": [{**item, **_empty_grade(), "status": "pending", "not_run_reason": None,
                     "client_http_attempts": 0, "runtime_http_attempts": None,
                     "runtime_invoked": False, "attempt_evidence_status": "not_started",
                     "attempt_may_be_in_flight": False, "evidence": None, "error_code": None,
                     "runner_error_code": None} for item in manifest["inputs"]],
        "scope": ("Offline formal preparation only; no execution, live authorization or quality result."
                  if manifest["panel_kind"] == "formal" else
                  "Offline development regression evidence, not live quality or formal promotion."),
    }
    if "allocation_policy" in manifest:
        p3_formal_policy.validate_identity(manifest["allocation_policy"])
        report["report_version"] = POLICY_REPORT_VERSION
        report["allocation_policy"] = deepcopy(manifest["allocation_policy"])
    return report


def _summarize(report: dict) -> None:
    report["summary"] = p3_formal_policy.summarize(
        report["results"], report["results"], panel_kind=report["panel_kind"], run_status=report["status"],
        allocation_policy=report.get("allocation_policy"))


def _safe(value: dict, client: GatewayClient | None) -> dict:
    if client is not None:
        pending, names = [value], []
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                names.extend(item)
                pending.extend(item.values())
            elif isinstance(item, (tuple, list)):
                pending.extend(item)
        if client.safe_export(value) != value or client.safe_export({"fields": names}) != {"fields": names}:
            raise P3Error("leakage_risk")
    return value


def _persist(artifacts: smoke._Artifacts, report: dict, client: GatewayClient | None) -> None:
    _summarize(report)
    artifacts.persist(_safe(report, client))


def _finish_pending(report: dict, panel: Panel, reason: str) -> None:
    for row, case in zip(report["results"], panel.cases):
        if row["status"] == "pending":
            row.update(p3_grading.grade(None, panel.oracle_for(case), attempted=False))
            row.update(status="not_run", not_run_reason=reason)


def _unchanged(database: Path, manifest: dict, panel: Panel, responses_path: Path | None,
               formal_freeze: Path | None = None) -> None:
    if _source_identity(panel, responses_path, formal_freeze) != manifest["identities"]:
        raise P3Error("manifest_drift")
    if smoke._stable_database(database) != manifest["database_sha256"]:
        raise P3Error("database_drift")


def prepare(
    database: Path, output_dir: Path, *, panel_path: Path = DEFAULT_PANEL,
    responses_path: Path | None = None, accepted_commit: str | None = None,
    formal_freeze: Path | None = None,
) -> dict:
    manifest = build_manifest(database, panel_path=panel_path, responses_path=responses_path,
                              accepted_commit=accepted_commit, formal_freeze=formal_freeze)
    panel, allocation_policy = _preparation_panel(database, panel_path, formal_freeze, accepted_commit)
    if allocation_policy != manifest.get("allocation_policy"):
        raise P3Error("manifest_drift")
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = _new_report(manifest, "preparation")
    _persist(artifacts, report, None)
    _unchanged(database, manifest, panel, responses_path, formal_freeze)
    if formal_freeze is not None:
        from tools.p3_admission import validate_freeze
        validate_freeze(formal_freeze, database, panel_path, accepted_commit=accepted_commit)
    smoke.validate_manifest(artifacts.directory / "manifest.json", manifest)
    report["status"] = "prepared"
    _finish_pending(report, panel, "offline_preparation")
    _persist(artifacts, report, None)
    return report


def _elapsed(started: float, clock: Callable[[], float]) -> float:
    now = clock()
    if type(now) not in (int, float) or type(started) not in (int, float):
        raise P3Error("invalid_configuration")
    elapsed = now - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise P3Error("invalid_configuration")
    return elapsed


def _mock_only(client: GatewayClient | None, *, fresh: bool = False) -> GatewayClient:
    if (not isinstance(client, GatewayClient) or type(getattr(client, "_transport", None)) is not httpx.MockTransport
            or fresh and (type(getattr(client, "http_attempts", None)) is not int or client.http_attempts != 0)):
        raise P3Error("invalid_configuration")
    return client


def _attempts(client: GatewayClient) -> int:
    count = getattr(client, "http_attempts", None)
    if type(count) is not int or count < 0:
        raise P3Error("internal_failure")
    return count


def _stop(report: dict, code: str) -> None:
    report.update(status="incomplete", stop_reason=code, error_code=code)


def _complete_panel(artifacts, report, client, *, validate, remaining) -> dict:
    try:
        candidate = deepcopy(report)
        candidate["status"] = "complete"
        _summarize(candidate)
        _safe(candidate, client)
        pending, target = stage_terminal(artifacts, candidate, validate=validate, remaining=remaining)
    except (KeyboardInterrupt, asyncio.CancelledError):
        _stop(report, "interrupted")
    except _SAFE_ERRORS as exc:
        _stop(report, exc.code)
    except OSError as exc:
        _stop(report, "artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io")
    except _INTERNAL_ERRORS:
        _stop(report, "internal_failure")
    else:
        # Nothing after the publication commit may retract or revalidate the terminal report.
        commit_terminal(pending, target)
        return candidate
    _persist(artifacts, report, client)
    return report


async def run_panel(
    database: Path, output_dir: Path, *, manifest_path: Path | None,
    panel_path: Path = DEFAULT_PANEL, responses_path: Path | None = None,
    client: GatewayClient | None = None, origin: str = "mock",
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    if origin != "mock":
        raise P3Error("live_not_admitted")
    if client is not None and responses_path is not None:
        raise P3Error("invalid_configuration")
    panel = p3_assets.load_panel(panel_path)
    _admitted(panel)
    if responses_path is None:
        client = _mock_only(client, fresh=True)
    started = clock()
    prepared = recipe_smoke._prepared(manifest_path)
    manifest = build_manifest(database, panel_path=panel_path, responses_path=responses_path,
                              accepted_commit=prepared["preparation"]["accepted_commit"])
    if responses_path is not None:
        client = fake_client(panel, responses_path)
    client = _mock_only(client, fresh=True)
    _safe(manifest, client)
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = _new_report(manifest, origin)
    _persist(artifacts, report, client)
    active = None
    before = 0
    invoked = False
    completed = False

    def validate() -> None:
        _mock_only(client)
        smoke.validate_manifest(manifest_path, manifest)
        smoke.validate_manifest(artifacts.directory / "manifest.json", manifest)
        _unchanged(database, manifest, panel, responses_path)

    def remaining() -> float:
        return manifest["settings"]["panel_timeout_seconds"] - _elapsed(started, clock)

    try:
        validate()
        if panel.inputs() != manifest["inputs"]:
            raise P3Error("manifest_drift")
        for row, case in zip(report["results"], panel.cases):
            validate()
            _mock_only(client)
            before, invoked = _attempts(client), False
            if before != report["client_http_attempts"] or before >= len(panel.cases):
                raise P3Error("attempt_budget")
            if remaining() <= 0:
                raise P3Error("panel_budget")
            active = row
            active.update(status="in_progress", attempt_may_be_in_flight=True)
            report.update(possible_in_flight_attempts=1, attempt_budget_used=before + 1)
            _persist(artifacts, report, client)
            validate()
            _mock_only(client)
            if _attempts(client) != before:
                raise P3Error("attempt_budget")
            timeout = min(60.0, remaining())
            if timeout <= 0:
                raise P3Error("panel_budget")
            invoked = True
            active.update(runtime_invoked=True, attempt_evidence_status="not_returned")
            try:
                async with asyncio.timeout(timeout):
                    result = await interpret_recipe_and_execute(
                        case.question, database, client, timeout_seconds=timeout, clock=clock)
            except TimeoutError:
                result = RecipeInterpretation(None, None, ModelError("timeout"), {
                    "client_http_attempts": _attempts(client) - before, "error_code": "timeout",
                    "elapsed_seconds": timeout,
                })
            active.update(p3_grading.grade(result, panel.oracle_for(case)))
            active.update(status="completed", attempt_may_be_in_flight=False)
            report["possible_in_flight_attempts"] = 0
            count = _attempts(client)
            active["client_http_attempts"] = count - before
            report.update(client_http_attempts=count, attempt_budget_used=count)
            if result is None:
                raise P3Error("internal_failure")
            active["error_code"] = result.error.code if result.error else None
            evidence = _safe(result.evidence, client)
            if not isinstance(evidence, dict):
                raise P3Error("internal_failure")
            active["evidence"] = evidence
            if count - before not in (0, 1) or count > len(panel.cases):
                raise P3Error("attempt_budget")
            attempt = evidence.get("client_http_attempts")
            if "client_http_attempts" not in evidence:
                active["attempt_evidence_status"] = "missing"
                raise P3Error("internal_failure")
            if type(attempt) is not int or attempt not in (0, 1):
                active["attempt_evidence_status"] = "invalid"
                raise P3Error("internal_failure")
            active["runtime_http_attempts"] = attempt
            active["attempt_evidence_status"] = "matched" if attempt == count - before else "mismatch"
            if attempt != count - before or attempt == 0 and result.error is None:
                raise P3Error("internal_failure")
            validate()
            code = active["error_code"]
            report["network_failure_streak"] = report["network_failure_streak"] + 1 if code in NETWORK_CODES else 0
            report["timeout_streak"] = report["timeout_streak"] + 1 if code == "timeout" else 0
            _persist(artifacts, report, client)
            active = None
            if result.error is not None and result.error.stop_reason:
                raise P3Error(result.error.stop_reason)
            if report["network_failure_streak"] >= 2:
                raise P3Error("consecutive_network_failures")
            if report["timeout_streak"] >= 2:
                raise P3Error("consecutive_timeouts")
            if remaining() <= 0:
                raise P3Error("panel_budget")
        completed = True
    except (KeyboardInterrupt, asyncio.CancelledError):
        _stop(report, "interrupted")
    except _SAFE_ERRORS as exc:
        _stop(report, exc.stop_reason or exc.code if isinstance(exc, ModelError) else exc.code)
    except OSError as exc:
        _stop(report, "artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io")
    except _INTERNAL_ERRORS:
        _stop(report, "internal_failure")
    finally:
        if active is not None:
            active["runner_error_code"] = report["stop_reason"]
            if not invoked:
                active.update(status="pending", attempt_may_be_in_flight=False)
                report["possible_in_flight_attempts"] = 0
            try:
                count = _attempts(client)
                active["client_http_attempts"] = count - before
                report.update(client_http_attempts=count, attempt_budget_used=max(
                    count, before + int(active["attempt_may_be_in_flight"])))
            except P3Error:
                active["client_http_attempts"] = None
                report["client_http_attempts"] = None
        try:
            report["elapsed_seconds"] = round(_elapsed(started, clock), 6)
        except P3Error:
            report["elapsed_seconds"] = None
            if report["stop_reason"] is None:
                _stop(report, "invalid_configuration")
        _finish_pending(report, panel, report["stop_reason"] or "panel_complete")
        _persist(artifacts, report, client)
    if completed and report["stop_reason"] is None:
        return _complete_panel(artifacts, report, client, validate=validate, remaining=remaining)
    return report


def read_report(path: Path, *, manifest_path: Path | None = None) -> dict:
    """Inspect an archived report without a DB, current-checkout or environment dependency."""
    manifest = _document(manifest_path or path.parent / "manifest.json", p3_assets.MAX_ASSET_BYTES,
                         "invalid_manifest")
    report = _document(path, MAX_REPORT_BYTES, "invalid_asset")
    try:
        fields = _MANIFEST_FIELDS
        if manifest.get("manifest_version") == POLICY_MANIFEST_VERSION:
            fields = fields | {"allocation_policy"}
            p3_formal_policy.validate_identity(manifest.get("allocation_policy"))
            if manifest["panel_kind"] != "formal":
                raise P3Error("invalid_manifest")
        elif manifest.get("manifest_version") != MANIFEST_VERSION:
            raise P3Error("invalid_manifest")
        if (set(manifest) != fields
                or manifest["evaluator_version"] != p3_grading.VERSION
                or manifest["panel_kind"] not in ("development", "formal")
                or manifest["upstream_inference_attempts"] is not None
                or manifest["settings"] != settings(len(manifest["inputs"]))
                or manifest["settings_sha256"] != p3_assets.digest(manifest["settings"])
                or manifest["stop_policy_sha256"] != p3_assets.digest(manifest["stop_policy"])
                or manifest["stop_policy"] != stop_policy()
                or manifest["order"] != [item["case_id"] for item in manifest["inputs"]]):
            raise P3Error("invalid_manifest")
        preparation = manifest["preparation"]
        if (set(preparation) != {"kind", "accepted_commit"} or preparation["kind"] not in ("candidate", "accepted")
                or (preparation["kind"] == "candidate") != (preparation["accepted_commit"] is None)):
            raise P3Error("invalid_manifest")
        if preparation["kind"] == "accepted":
            recipe_smoke._accepted(manifest["identities"], preparation["accepted_commit"])
        if manifest["panel_kind"] == "formal" and (
                preparation["kind"] != "accepted" or manifest["fake_responses"] is not None
                or report["status"] not in ("incomplete", "prepared") or report["origin"] != "preparation"
                or report["client_http_attempts"] != 0 or report["attempt_budget_used"] != 0
                or report["possible_in_flight_attempts"] != 0
                or any(row["runtime_invoked"] or row["attempt_may_be_in_flight"] for row in report["results"])):
            raise P3Error("formal_not_admitted")
        for item in manifest["inputs"]:
            if (set(item) != _INPUT_FIELDS or not isinstance(item["question_sha256"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", item["question_sha256"]) is None
                    or set(item["question_reference"]) != {"asset", "case_id", "field"}
                    or item["question_reference"]["case_id"] != item["case_id"]
                    or item["question_reference"]["field"] != "question"):
                raise P3Error("invalid_manifest")
            p3_assets.Provenance.from_mapping(item["provenance"], item["exposure"])
        oracle_ids = set()
        for pin in manifest["oracles"]:
            oracle = p3_assets.parse_oracle(pin["value"])
            if (set(pin) != {"oracle_id", "revision", "sha256", "value"}
                    or pin["oracle_id"] != oracle.oracle_id or pin["revision"] != oracle.revision
                    or pin["sha256"] != p3_assets.digest(oracle.to_dict()) or oracle.oracle_id in oracle_ids):
                raise P3Error("invalid_manifest")
            oracle_ids.add(oracle.oracle_id)
        if oracle_ids != {item["oracle_id"] for item in manifest["inputs"]}:
            raise P3Error("invalid_manifest")
        asset_names = {"panel", "cases", "oracles"}
        if manifest["panel_kind"] == "formal":
            asset_names.add("formal_freeze")
        if manifest["fake_responses"] is not None:
            if manifest["fake_responses"] != SCRIPT_VERSION:
                raise P3Error("invalid_manifest")
            asset_names.add("responses")
        if set(manifest["assets"]) != asset_names:
            raise P3Error("invalid_manifest")
        for name, pin in manifest["assets"].items():
            if (set(pin) != {"reference", "sha256"} or not isinstance(pin["reference"], str)
                    or Path(pin["reference"]).name != pin["reference"]
                    or not isinstance(pin["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]) is None
                    or manifest["identities"]["files_sha256"][f"p3_asset:{name}"] != pin["sha256"]):
                raise P3Error("invalid_manifest")
        expected = _new_report(manifest, report["origin"])
        if (set(report) != set(expected) | {"summary"} or report["report_version"] != expected["report_version"]
                or report.get("allocation_policy") != manifest.get("allocation_policy")
                or report["manifest_sha256"] != p3_assets.digest(manifest)
                or report["status"] not in ("incomplete", "prepared", "complete")
                or report["origin"] not in ("mock", "preparation")
                or report["preparation"] != manifest["preparation"]
                or report["panel_id"] != manifest["panel_id"] or report["panel_kind"] != manifest["panel_kind"]
                or type(report["live_model_attempts"]) is not int or report["live_model_attempts"] != 0
                or report["upstream_inference_attempts"] is not None
                or any(report[key] is not None and report[key] not in p3_assets.SAFE_CODES
                       for key in ("stop_reason", "error_code"))
                or any(type(report[key]) is not int or report[key] < 0 for key in (
                    "attempt_budget_used", "possible_in_flight_attempts", "network_failure_streak", "timeout_streak"))
                or report["elapsed_seconds"] is not None and (
                    type(report["elapsed_seconds"]) not in (int, float)
                    or not math.isfinite(report["elapsed_seconds"]) or report["elapsed_seconds"] < 0)
                or len(report["results"]) != len(manifest["inputs"])):
            raise P3Error("invalid_asset")
        for row, item, shape in zip(report["results"], manifest["inputs"], expected["results"]):
            if (set(row) != set(shape) or any(row[key] != value for key, value in item.items())
                    or row["version"] != p3_grading.VERSION or set(row["layers"]) != set(p3_grading.LAYERS)
                    or any(value not in ("passed", "failed", "not_assessed") for value in row["layers"].values())
                    or type(row["runtime_invoked"]) is not bool
                    or type(row["attempt_may_be_in_flight"]) is not bool
                    or row["attempt_evidence_status"] not in _ATTEMPT_STATES
                    or row["runtime_http_attempts"] is not None and (
                        type(row["runtime_http_attempts"]) is not int or row["runtime_http_attempts"] not in (0, 1))
                    or row["attempt_evidence_status"] == "matched" and (
                        row["runtime_http_attempts"] is None
                        or row["runtime_http_attempts"] != row["client_http_attempts"])
                    or row["attempt_may_be_in_flight"] != (row["status"] == "in_progress")
                    or row["status"] in ("pending", "not_run") and (
                        row["runtime_invoked"] or row["client_http_attempts"] != 0 or row["evidence"] is not None
                        or row["runtime_http_attempts"] is not None or row["attempt_evidence_status"] != "not_started")
                    or row["status"] == "completed" and not row["runtime_invoked"]):
                raise P3Error("invalid_asset")
        counts = [row["client_http_attempts"] for row in report["results"]]
        if (any(count is not None and (type(count) is not int or count < 0) for count in counts)
                or report["client_http_attempts"] != (None if None in counts else sum(counts))
                or report["possible_in_flight_attempts"] != sum(
                    row["attempt_may_be_in_flight"] for row in report["results"])
                or report["possible_in_flight_attempts"] not in (0, 1)
                or report["attempt_budget_used"] < sum(count for count in counts if count is not None)
                or None not in counts and report["attempt_budget_used"] != max(
                    sum(counts), max((sum(counts[:index]) + 1 for index, row in enumerate(report["results"])
                                     if row["attempt_may_be_in_flight"]), default=0))
                or report["status"] == "complete" and (
                    report["origin"] != "mock" or report["stop_reason"] is not None
                    or report["error_code"] is not None or None in counts
                    or report["client_http_attempts"] > len(report["results"])
                    or any(row["status"] != "completed" or row["runner_error_code"] is not None
                           or row["attempt_evidence_status"] != "matched" for row in report["results"]))
                or report["status"] == "prepared" and (
                    report["origin"] != "preparation" or report["client_http_attempts"] != 0
                    or report["stop_reason"] is not None or report["error_code"] is not None
                    or any(row["status"] != "not_run" for row in report["results"]))):
            raise P3Error("invalid_asset")
        summary = report["summary"]
        _summarize(report)
        if summary != report["summary"]:
            raise P3Error("invalid_asset")
        return report
    except (LookupError, TypeError, ValueError, RecursionError):
        raise P3Error("invalid_asset") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise P3Error("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("prepare", "fake-run", "report"), default="prepare")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--panel", type=Path)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--formal-freeze", type=Path)
    try:
        args = parser.parse_args(argv)
        if args.mode == "report":
            if (args.report is None or args.db or args.output_dir or args.accepted_commit
                    or args.panel or args.responses or args.formal_freeze):
                raise P3Error("invalid_arguments")
            report = read_report(args.report, manifest_path=args.manifest)
        else:
            if args.db is None or args.output_dir is None or args.report is not None:
                raise P3Error("invalid_arguments")
            if args.mode == "prepare":
                if args.manifest is not None or args.formal_freeze is not None and args.responses is not None:
                    raise P3Error("invalid_arguments")
                report = prepare(args.db, args.output_dir, panel_path=args.panel or DEFAULT_PANEL,
                                 responses_path=None if args.formal_freeze else args.responses or DEFAULT_RESPONSES,
                                 accepted_commit=args.accepted_commit, formal_freeze=args.formal_freeze)
            else:
                if args.manifest is None or args.accepted_commit is not None or args.formal_freeze is not None:
                    raise P3Error("invalid_arguments")
                report = asyncio.run(run_panel(args.db, args.output_dir, manifest_path=args.manifest,
                                              panel_path=args.panel or DEFAULT_PANEL,
                                              responses_path=args.responses or DEFAULT_RESPONSES))
        print(canonical_json({key: report[key] for key in (
            "status", "origin", "stop_reason", "client_http_attempts", "live_model_attempts")}))
        return 0 if report["status"] in ("prepared", "complete") else 1
    except _SAFE_ERRORS as exc:
        print(canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except _INTERNAL_ERRORS:
        print('{"status":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
