#!/usr/bin/env python3
"""Prepare the fixed recipe panel offline; --live needs separate owner authorization.

Default preparation is candidate/test evidence, never a live manifest.
Only --accepted-commit SHA on that clean dev checkout prepares Gate B evidence.
No automatic environment loading, health checks, retries or semantic repairs.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Mapping
from fractions import Fraction
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import (
    BreakdownAnalysisPack, BreakdownRequest, CompareAnalysisPack, CompareRequest,
    OverviewAnalysisPack, OverviewRequest,
)
from grepbit.contracts import KernelError, utc_text
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError
from grepbit.model import canonical_json, normalized_request, strict_json
from grepbit.recipe_model import RecipeInterpretation, context_identity, interpret_recipe_and_execute
from tools import smoke

PANEL_ASSET = "evals/panels/p2-recipe-smoke-v1.json"
PANEL_ID = "p2-recipe-smoke-v1"
VERSION = "p2.7-recipe-smoke-v1"
FAMILIES = ("E01_overview", "E02_compare", "E03_share_denominator")
LANGUAGES = ("zh-TW", "en", "ja")
ORDER = tuple((family, LANGUAGES[(round_index + index) % 3])
              for round_index in range(3) for index, family in enumerate(FAMILIES))
MAX_ATTEMPTS = 9
PANEL_SECONDS = 720.0
GRADING_STAGES = ("recipe", "request", "execution", "coverage", "value_agreement")
NETWORK_CODES = frozenset({"transport_error", "gateway_error", "rate_limited"})
SAFE_CODES = smoke.SAFE_CODES | {
    "accepted_commit_required", "consecutive_network_failures", "consecutive_timeouts", "leakage_risk",
}
_Request = OverviewRequest | CompareRequest | BreakdownRequest
_Pack = OverviewAnalysisPack | CompareAnalysisPack | BreakdownAnalysisPack
_INTERNAL_ERRORS = (RuntimeError, TypeError, LookupError, ArithmeticError, AttributeError,
                    OSError, ValueError, sqlite3.Error)


class RecipeSmokeError(Exception):
    def __init__(self, code: str):
        self.code = code if code in SAFE_CODES else "internal_failure"
        super().__init__(self.code)


def settings() -> dict[str, object]:
    return {
        "model": smoke.MODEL, "response_mode": "json_content", "inputs": 9, "semantic_families": 3,
        "max_client_http_attempts": MAX_ATTEMPTS, "concurrency": 1, "client_retries": 0, "repairs": 0,
        "stream": False, "temperature": 0, "max_tokens": 2048,
        "call_timeout_seconds": smoke.CALL_TIMEOUT_SECONDS, "panel_timeout_seconds": PANEL_SECONDS,
        "max_input_bytes": smoke.MAX_INPUT_BYTES, "max_request_bytes": smoke.MAX_REQUEST_BYTES,
        "max_response_bytes": smoke.MAX_RESPONSE_BYTES, "max_database_bytes": smoke.MAX_DATABASE_BYTES,
        "constraints": None, "raw_diagnostics": False,
    }


def stop_policy() -> dict[str, object]:
    return {
        "version": "p2.7-stops-v1", "network_codes": sorted(NETWORK_CODES),
        "consecutive_network_limit": 2, "timeout_code": "timeout", "consecutive_timeout_limit": 2,
        "reset": "Each streak resets on a result outside its own code set.",
        "immediate_adapter_stops": ["configuration_failure", "envelope_incompatibility", "budget_exhausted"],
        "runner_stops": ["panel_budget", "attempt_budget", "manifest_drift", "database_drift",
                         "source_identity_failure", "artifact_conflict", "artifact_io", "leakage_risk"],
        "timeout_origin": "Unknown; timeout is not evidence of a network failure.",
    }


def canonical_request(request: _Request) -> dict[str, object]:
    if isinstance(request, CompareRequest):
        return {"current": normalized_request(request.current), "baseline": normalized_request(request.baseline)}
    return {**request.to_dict(), "start": utc_text(request.start), "end": utc_text(request.end)}


def _expected_request(recipe: str, data: object) -> _Request:
    if recipe == "overview":
        return OverviewRequest.from_mapping(data)
    if recipe == "compare":
        return CompareRequest.from_mapping(data)
    if recipe == "breakdown":
        return BreakdownRequest.from_mapping(data)
    raise RecipeSmokeError("source_identity_failure")


def panel_inputs() -> tuple[list[dict], dict]:
    """Evaluator-only loading; questions are passed separately from all expectations."""
    try:
        smoke._no_symlinks(ROOT / PANEL_ASSET)
        with (ROOT / PANEL_ASSET).open("rb") as stream:
            raw = stream.read(65_537)
        if len(raw) > 65_536:
            raise RecipeSmokeError("source_identity_failure")
        panel = strict_json(raw)
        if (set(panel) != {"panel_id", "order", "families"} or panel["panel_id"] != PANEL_ID
                or panel["order"] != [list(pair) for pair in ORDER]
                or set(panel["families"]) != set(FAMILIES)):
            raise RecipeSmokeError("source_identity_failure")
        oracle = panel["families"]
        for family, recipe in zip(FAMILIES, ("overview", "compare", "breakdown")):
            item = oracle[family]
            if (set(item) != {"recipe_id", "recipe_version", "request", "coverage", "values"}
                    or item["recipe_id"] != recipe or item["recipe_version"] != "0.1"):
                raise RecipeSmokeError("source_identity_failure")
            item["request"] = canonical_request(_expected_request(recipe, item["request"]))
            coverage = item["coverage"]
            extra = {"binding_center_id"} if recipe == "overview" else {"group"} if recipe == "breakdown" else set()
            value_keys = (
                {"amount", "bookings", "seats"} if recipe == "overview" else
                {"current", "baseline", "delta", "growth"} if recipe == "compare" else
                {"rows", "all_amount", "top_subtotal", "share"}
            )
            if (set(coverage) != {"status", "slots", "states"} | extra
                    or coverage["status"] != "complete" or not isinstance(coverage["slots"], dict)
                    or coverage["states"] != (["checked"] if recipe == "overview" else ["checked", "undefined"])
                    or set(item["values"]) != value_keys):
                raise RecipeSmokeError("source_identity_failure")
        base = strict_json((ROOT / smoke.ASSETS[0]).read_bytes())
        languages = strict_json((ROOT / smoke.ASSETS[1]).read_bytes())
        if (languages["base_catalog_sha256"] != smoke._digest((ROOT / smoke.ASSETS[0]).read_bytes())
                or languages["comparison_languages"] != list(LANGUAGES)):
            raise RecipeSmokeError("source_identity_failure")
        cases = {case["id"]: case for case in base["cases"]}
        translations = {case["case_id"]: case for case in languages["variants"]}
        entries = []
        for family, language in ORDER:
            question = cases[family]["question"] if language == "zh-TW" else translations[family][language]
            if not isinstance(question, str) or not 0 < len(question.encode()) <= smoke.MAX_INPUT_BYTES:
                raise RecipeSmokeError("source_identity_failure")
            entries.append({
                "order": len(entries) + 1, "case_id": family, "family": family, "language": language,
                "question": question, "question_sha256": smoke._digest(question.encode()),
                "question_reference": {"asset": smoke.ASSETS[0] if language == "zh-TW" else smoke.ASSETS[1],
                                       "case_id": family, "field": "question" if language == "zh-TW" else language},
            })
        return entries, oracle
    except (OSError, ValueError, TypeError, LookupError, KernelError, ModelError):
        raise RecipeSmokeError("source_identity_failure") from None


def _source_identity() -> dict:
    identity = smoke._source_identity()
    try:
        for name in ("tools/recipe_smoke.py", PANEL_ASSET):
            smoke._no_symlinks(ROOT / name)
            identity["files_sha256"][name] = smoke._digest((ROOT / name).read_bytes())
        identity["branch"] = subprocess.run(
            ["git", "--no-optional-locks", "branch", "--show-current"], cwd=ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise RecipeSmokeError("source_identity_failure") from None
    identity["context"] = context_identity()
    return identity


def _accepted(identity: dict, commit: str) -> None:
    if (not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)
            or identity["git_commit"] != commit or identity["worktree_dirty"] is not False
            or identity["branch"] != "dev"):
        raise RecipeSmokeError("accepted_commit_required")


def build_manifest(database: Path, *, accepted_commit: str | None = None) -> dict:
    identity = _source_identity()
    if accepted_commit is not None:
        _accepted(identity, accepted_commit)
    inputs, oracle = panel_inputs()
    manifest = {
        "manifest_version": VERSION, "panel_id": PANEL_ID, "identities": identity,
        "preparation": {"kind": "accepted" if accepted_commit is not None else "candidate",
                        "accepted_commit": accepted_commit},
        "acceptance_boundary": "Explicit owner-supplied accepted dev commit; not automatic approval or live authorization.",
        "database_sha256": smoke._fixture_identity(database), "settings": settings(),
        "settings_sha256": smoke._digest(canonical_json(settings()).encode()),
        "stop_policy": stop_policy(), "stop_policy_sha256": smoke._digest(canonical_json(stop_policy()).encode()),
        "order": [list(pair) for pair in ORDER],
        "inputs": [{key: value for key, value in entry.items() if key != "question"} for entry in inputs],
        "oracle": oracle, "gateway_policy": smoke.policy_attestation(), "upstream_inference_attempts": None,
    }
    if _source_identity() != identity:
        raise RecipeSmokeError("manifest_drift")
    return manifest


def _prepared(path: Path | None) -> dict:
    if path is None:
        raise RecipeSmokeError("missing_manifest")
    smoke._no_symlinks(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(1_048_577)
        value = strict_json(raw)
        if len(raw) > 1_048_576 or not isinstance(value, dict):
            raise RecipeSmokeError("invalid_manifest")
        preparation = value["preparation"]
        if (set(preparation) != {"kind", "accepted_commit"} or preparation["kind"] not in ("candidate", "accepted")
                or (preparation["kind"] == "candidate") != (preparation["accepted_commit"] is None)):
            raise RecipeSmokeError("invalid_manifest")
        return value
    except (OSError, ValueError, TypeError, LookupError, ModelError):
        raise RecipeSmokeError("invalid_manifest") from None


def live_preflight(manifest_path: Path | None, current: dict, *, gateway_policies: Mapping[str, str] | None,
                   env_file: Path | None, environ: Mapping[str, str] | None = None) -> GatewayConfig:
    smoke.validate_manifest(manifest_path, current)
    if current["preparation"]["kind"] != "accepted":
        raise RecipeSmokeError("accepted_commit_required")
    _accepted(current["identities"], current["preparation"]["accepted_commit"])
    smoke.policy_attestation(gateway_policies, required=True)
    if not isinstance(env_file, Path):
        raise RecipeSmokeError("invalid_configuration")
    smoke._no_symlinks(env_file)
    return GatewayConfig.from_env(environ=environ, env_file=env_file)


def _coverage(pack: _Pack, expected: dict) -> bool:
    roles = {slot.slot_id: "required" if isinstance(pack, CompareAnalysisPack) else slot.role for slot in pack.slots}
    facts = list(pack.facts)
    groups = list(pack.grouped_facts) if isinstance(pack, (OverviewAnalysisPack, BreakdownAnalysisPack)) else []
    derived = list(pack.derived_facts) if isinstance(pack, (CompareAnalysisPack, BreakdownAnalysisPack)) else []
    facts += groups + derived
    sizes = ((3, 2, 0) if isinstance(pack, OverviewAnalysisPack) else
             (2, 0, 2) if isinstance(pack, CompareAnalysisPack) else (1, 1, 2))
    if ((len(pack.facts), len(groups), len(derived)) != sizes
            or len({fact.fact_id for fact in facts}) != len(facts)
            or len({slot.fact_id for slot in pack.slots}) != len(pack.slots)
            or pack.status != expected["status"] or roles != expected["slots"] or len(roles) != len(pack.slots)
            or any(slot.state not in expected["states"] or slot.fact_id not in {fact.fact_id for fact in facts}
                   for slot in pack.slots)):
        return False
    native_roles = (
        ("amount", "bookings", "seats", "daily_amount", "category_amounts")
        if isinstance(pack, OverviewAnalysisPack) else
        ("current", "baseline", "delta", "growth") if isinstance(pack, CompareAnalysisPack) else
        ("all_amount", "top_courses", "top_subtotal", "share")
    )
    # Membership alone would accept a slot pointing to another role's checked fact.
    if {slot.slot_id: slot.fact_id for slot in pack.slots} != dict(
            zip(native_roles, (fact.fact_id for fact in facts))):
        return False
    if isinstance(pack, OverviewAnalysisPack):
        return pack.binding.center_id == expected["binding_center_id"]
    if isinstance(pack, BreakdownAnalysisPack):
        group = pack.grouped_facts[0]
        return len(pack.grouped_facts) == 1 and {
            "dimension": group.dimension, "coverage": group.coverage, "top_k": group.top_k,
        } == expected["group"]
    return True


def _values(pack: _Pack) -> dict:
    def exact(value):
        return {"numerator": value.numerator, "denominator": value.denominator} if isinstance(value, Fraction) else value
    if isinstance(pack, OverviewAnalysisPack):
        return dict(zip(("amount", "bookings", "seats"), (fact.value for fact in pack.facts)))
    if isinstance(pack, CompareAnalysisPack):
        return dict(zip(("current", "baseline", "delta", "growth"),
                        (exact(fact.value) for fact in (*pack.facts, *pack.derived_facts))))
    return {"rows": [{"key": row.key, "value": row.value} for row in pack.grouped_facts[0].rows],
            "all_amount": pack.facts[0].value, "top_subtotal": pack.derived_facts[0].value,
            "share": exact(pack.derived_facts[1].value)}


def grade(result: RecipeInterpretation, oracle: dict) -> tuple[str, dict[str, str]]:
    grading = dict.fromkeys(GRADING_STAGES, "not_run")
    if result.proposal is not None:
        proposal = result.proposal
        grading["recipe"] = "passed" if (proposal.recipe_id, proposal.recipe_version) == (
            oracle["recipe_id"], oracle["recipe_version"]) else "failed"
        if grading["recipe"] == "failed":
            return "wrong_recipe", grading
        grading["request"] = "passed" if canonical_request(proposal.request) == oracle["request"] else "failed"
        if grading["request"] == "failed":
            return "wrong_request", grading
    if result.error:
        code = result.error.code
        if code == "model_declined":
            return "false_refusal", grading
        if code in {"invalid_json", "invalid_request"}:
            return "invalid_output", grading
        grading["execution"] = "failed"
        return "operational_failure", grading
    pack = result.analysis_pack
    if (result.proposal is None or pack is None or (pack.recipe_id, pack.recipe_version) != (
            oracle["recipe_id"], oracle["recipe_version"])
            or canonical_request(pack.request) != canonical_request(result.proposal.request)):
        grading["execution"] = "failed"
        return "operational_failure", grading
    grading["execution"] = "passed"
    grading["coverage"] = "passed" if _coverage(pack, oracle["coverage"]) else "failed"
    if grading["coverage"] == "failed":
        return "wrong_coverage", grading
    grading["value_agreement"] = "passed" if canonical_json(_values(pack)) == canonical_json(oracle["values"]) else "failed"
    return "correct" if grading["value_agreement"] == "passed" else "wrong_value", grading


def _new_report(manifest: dict, origin: str) -> dict:
    return {
        "report_version": VERSION, "status": "incomplete", "origin": origin, "stop_reason": None,
        "error_code": None, "manifest_sha256": smoke._digest(canonical_json(manifest).encode()),
        "preparation": manifest["preparation"], "gateway_policy": smoke.policy_attestation(),
        "client_http_attempts": 0, "live_model_attempts": 0, "possible_in_flight_attempts": 0,
        "attempt_budget_used": 0, "elapsed_seconds": 0.0, "upstream_inference_attempts": None,
        "network_failure_streak": 0, "timeout_streak": 0,
        "results": [{**entry, "status": "pending", "outcome": None, "not_run_reason": None,
                     "client_http_attempts": 0, "attempt_may_be_in_flight": False, "evidence": None,
                     "proposal": None, "pack_status": None, "error_code": None, "runner_error_code": None,
                     "grading": dict.fromkeys(GRADING_STAGES, "not_run")} for entry in manifest["inputs"]],
        "scope": "Nine paired inputs, three synthetic semantic families; mock/preparation is not live model evidence.",
    }


def _summarize(report: dict) -> None:
    entries = report["results"]
    def counts(rows):
        return {"total": len(rows), "outcomes": dict(Counter(row["outcome"] or "unassessed" for row in rows)),
                "statuses": dict(Counter(row["status"] for row in rows))}
    families = {}
    for family in FAMILIES:
        rows = [row for row in entries if row["family"] == family]
        families[family] = {**counts(rows), "all_three_correct": all(row["outcome"] == "correct" for row in rows),
                            "at_least_one_correct": any(row["outcome"] == "correct" for row in rows)}
    totals = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens", "elapsed_seconds"):
        values = [(row["evidence"] or {}).get("elapsed_seconds") if name == "elapsed_seconds"
                  else (row["evidence"] or {}).get("usage", {}).get(name) for row in entries]
        known = [value for value in values if type(value) in (int, float) and math.isfinite(value) and value >= 0]
        totals[name] = {"known_total": sum(known) if known else None, "known_inputs": len(known),
                        "unknown_inputs": len(entries) - len(known)}
    report["summary"] = {
        **counts(entries), "semantic_families": 3, "paired_inputs": 9, "per_family": families,
        "per_language": {language: counts([row for row in entries if row["language"] == language])
                         for language in LANGUAGES},
        "all_three_correct_families": sum(row["all_three_correct"] for row in families.values()),
        "at_least_one_correct_families": sum(row["at_least_one_correct"] for row in families.values()),
        "usage_latency": totals, "client_http_attempts": report["client_http_attempts"],
        "live_model_attempts": report["live_model_attempts"],
        "possible_in_flight_attempts": report["possible_in_flight_attempts"], "upstream_inference_attempts": None,
    }


def _finish_pending(report: dict, reason: str) -> None:
    for row in report["results"]:
        if row["status"] == "pending":
            row.update(status="not_run", outcome="not_run", not_run_reason=reason)
    _summarize(report)


def _persist(artifacts, report: dict, client: GatewayClient | None = None) -> None:
    _summarize(report)
    safe = client.safe_export(report) if client else report
    if safe != report:
        raise RecipeSmokeError("leakage_risk")
    if client:
        pending, names = [report], []
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                names.extend(value)
                pending.extend(value.values())
            elif isinstance(value, (list, tuple)):
                pending.extend(value)
        fields = {"field_names": names}
        if client.safe_export(fields) != fields:
            raise RecipeSmokeError("leakage_risk")
    artifacts.persist(safe)


def prepare(database: Path, output_dir: Path, *, accepted_commit: str | None = None) -> dict:
    manifest = build_manifest(database, accepted_commit=accepted_commit)
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = _new_report(manifest, "preparation")
    _persist(artifacts, report)
    report["status"] = "prepared"
    _finish_pending(report, "offline_preparation")
    _persist(artifacts, report)
    return report


def _remaining(started: float, clock: Callable[[], float]) -> float:
    elapsed = clock() - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise RecipeSmokeError("invalid_configuration")
    return PANEL_SECONDS - elapsed


def _unchanged(database: Path, manifest: dict) -> None:
    if _source_identity() != manifest["identities"]:
        raise RecipeSmokeError("manifest_drift")
    if smoke._stable_database(database) != manifest["database_sha256"]:
        raise RecipeSmokeError("database_drift")


async def run_panel(
    database: Path, output_dir: Path, *, manifest_path: Path | None,
    client: GatewayClient | None = None, origin: str = "mock",
    clock: Callable[[], float] = time.monotonic, gateway_policies: Mapping[str, str] | None = None,
    env_file: Path | None = None, environ: Mapping[str, str] | None = None,
) -> dict:
    if origin not in ("mock", "live"):
        raise RecipeSmokeError("invalid_configuration")
    started = clock()
    prepared = _prepared(manifest_path)
    manifest = build_manifest(database, accepted_commit=prepared["preparation"]["accepted_commit"])
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = _new_report(manifest, origin)
    _persist(artifacts, report)
    active = None
    attempts_before = 0
    send_started = False
    try:
        smoke.validate_manifest(manifest_path, manifest)
        if origin == "live":
            if client is not None:
                raise RecipeSmokeError("invalid_configuration")
            config = live_preflight(manifest_path, manifest, gateway_policies=gateway_policies,
                                    env_file=env_file, environ=environ)
            client = GatewayClient(config)
        if client is None or client.http_attempts != 0 or origin == "mock" and client._transport is None:
            raise RecipeSmokeError("invalid_configuration")
        report["gateway_policy"] = smoke.policy_attestation(gateway_policies, required=origin == "live")
        questions, _ = panel_inputs()
        if len(questions) != len(report["results"]) or len(questions) != 9:
            raise RecipeSmokeError("manifest_drift")
        for entry, question in zip(report["results"], questions):
            if (any(question[key] != entry[key] for key in manifest["inputs"][0])
                    or smoke._digest(question["question"].encode()) != entry["question_sha256"]):
                raise RecipeSmokeError("manifest_drift")
            _unchanged(database, manifest)
            if client.http_attempts >= MAX_ATTEMPTS:
                raise RecipeSmokeError("attempt_budget")
            if _remaining(started, clock) <= 0:
                raise RecipeSmokeError("panel_budget")
            active, attempts_before, send_started = entry, client.http_attempts, False
            active.update(status="in_progress", attempt_may_be_in_flight=True)
            report.update(possible_in_flight_attempts=1, attempt_budget_used=attempts_before + 1)
            _persist(artifacts, report, client)
            _unchanged(database, manifest)
            remaining = _remaining(started, clock)
            if remaining <= 0:
                active.update(status="pending", attempt_may_be_in_flight=False)
                active = None
                report.update(possible_in_flight_attempts=0, attempt_budget_used=client.http_attempts)
                raise RecipeSmokeError("panel_budget")
            timeout = min(smoke.CALL_TIMEOUT_SECONDS, remaining)
            call_started = clock()
            send_started = True
            try:
                async with asyncio.timeout(timeout):
                    result = await interpret_recipe_and_execute(
                        question["question"], database, client, timeout_seconds=timeout, clock=clock,
                    )
            except TimeoutError:
                legacy = smoke._timeout_result(client, attempts_before, max(0.0, clock() - call_started))
                result = RecipeInterpretation(None, None, legacy.error, {
                    **{key: value for key, value in legacy.evidence.items() if key not in ("request", "fact_pack")},
                    "context_identity": manifest["identities"]["context"], "model_outcome": None,
                    "proposal": None, "analysis_pack": None, "pack_status": None,
                })
            evidence = client.safe_export(result.evidence)
            active.update(status="completed", attempt_may_be_in_flight=False, evidence=evidence,
                          proposal=evidence.get("proposal"), pack_status=evidence.get("pack_status"),
                          error_code=result.error.code if result.error else None,
                          client_http_attempts=client.http_attempts - attempts_before)
            report.update(client_http_attempts=client.http_attempts, possible_in_flight_attempts=0,
                          attempt_budget_used=client.http_attempts,
                          live_model_attempts=client.http_attempts if origin == "live" else 0,
                          elapsed_seconds=round(max(0.0, clock() - started), 6))
            active["outcome"], active["grading"] = grade(result, manifest["oracle"][entry["family"]])
            if active["outcome"] == "operational_failure" and result.error is None:
                raise RecipeSmokeError("internal_failure")
            if evidence != result.evidence:
                raise RecipeSmokeError("leakage_risk")
            if result.proposal and client.safe_export(result.proposal.to_dict()) != result.proposal.to_dict():
                raise RecipeSmokeError("leakage_risk")
            _unchanged(database, manifest)
            if active["client_http_attempts"] not in (0, 1) or client.http_attempts > MAX_ATTEMPTS:
                raise RecipeSmokeError("attempt_budget")
            code = result.error.code if result.error else None
            report["network_failure_streak"] = report["network_failure_streak"] + 1 if code in NETWORK_CODES else 0
            report["timeout_streak"] = report["timeout_streak"] + 1 if code == "timeout" else 0
            _persist(artifacts, report, client)
            active = None
            if result.error and result.error.stop_reason:
                raise RecipeSmokeError(result.error.stop_reason)
            if report["network_failure_streak"] >= 2:
                raise RecipeSmokeError("consecutive_network_failures")
            if report["timeout_streak"] >= 2:
                raise RecipeSmokeError("consecutive_timeouts")
            if _remaining(started, clock) <= 0:
                raise RecipeSmokeError("panel_budget")
        report["status"] = "complete"
    except (KeyboardInterrupt, asyncio.CancelledError):
        report.update(status="incomplete", stop_reason="interrupted", error_code="interrupted")
    except (RecipeSmokeError, smoke.SmokeError, ModelError) as exc:
        report.update(status="stopped", stop_reason=exc.code if not isinstance(exc, ModelError) else "configuration_failure",
                      error_code=exc.code)
    except _INTERNAL_ERRORS:
        report.update(status="incomplete", stop_reason="internal_failure", error_code="internal_failure")
    finally:
        if active is not None:
            active["runner_error_code"] = report["stop_reason"]
            if not send_started:
                active.update(status="pending", attempt_may_be_in_flight=False)
                report["possible_in_flight_attempts"] = 0
            elif active["outcome"] not in ("wrong_recipe", "wrong_request"):
                active["outcome"] = "operational_failure"
                active["grading"].update(execution="failed", coverage="not_run", value_agreement="not_run")
            if client is not None:
                active["client_http_attempts"] = client.http_attempts - attempts_before
                report.update(client_http_attempts=client.http_attempts,
                              live_model_attempts=client.http_attempts if origin == "live" else 0,
                              attempt_budget_used=max(client.http_attempts,
                                                      attempts_before + int(active["attempt_may_be_in_flight"])))
        elapsed = clock() - started
        report["elapsed_seconds"] = round(elapsed, 6) if math.isfinite(elapsed) and elapsed >= 0 else None
        _finish_pending(report, report["stop_reason"] or "panel_complete")
        _persist(artifacts, report, client)
        if report["status"] == "complete":
            elapsed = clock() - started
            reason = ("invalid_configuration" if not math.isfinite(elapsed) or elapsed < 0
                      else "panel_budget" if elapsed >= PANEL_SECONDS else None)
            if reason:
                report.update(status="stopped", stop_reason=reason, error_code=reason,
                              elapsed_seconds=round(elapsed, 6) if math.isfinite(elapsed) and elapsed >= 0 else None)
                _persist(artifacts, report, client)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = smoke._Parser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--env-file", type=Path)
    for key in smoke.POLICY_KEYS:
        parser.add_argument(f"--gateway-{key}", choices=("disabled", "enabled"))
    try:
        args = parser.parse_args(argv)
        policies = {key: getattr(args, f"gateway_{key}") for key in smoke.POLICY_KEYS}
        if not args.live:
            if args.manifest is not None or args.env_file is not None or any(policies.values()):
                raise RecipeSmokeError("invalid_arguments")
            report = prepare(args.db, args.output_dir, accepted_commit=args.accepted_commit)
        else:
            if args.accepted_commit is not None:
                raise RecipeSmokeError("invalid_arguments")
            report = asyncio.run(run_panel(args.db, args.output_dir, manifest_path=args.manifest, origin="live",
                                          gateway_policies=policies, env_file=args.env_file))
        print(canonical_json({key: report[key] for key in (
            "status", "origin", "stop_reason", "client_http_attempts", "live_model_attempts")}))
        return 0 if report["status"] in ("prepared", "complete") else 1
    except (RecipeSmokeError, smoke.SmokeError, ModelError) as exc:
        print(canonical_json({"status": "stopped", "error_code": exc.code}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except _INTERNAL_ERRORS:
        print('{"status":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
