#!/usr/bin/env python3
"""Single tiered evaluation runner (#87 step 2).

One packet, envelope, manifest and report contract for every evaluation run.
The inputs are registry entries, not modules: a registered candidate
(``evals/candidates``), a registered panel with a tier (``evals/panels``), a
registered route (``evals/routes``) and the append-only run index
(``evals/runs/index.jsonl``). The claim a run may make is derived from the tier
and the run index, never chosen: a dev panel is a development observation, a
regression panel an observed regression, a holdout panel a fresh observation
exactly once per (panel, route) and an observed regression afterwards. Nothing
here is promotion. Preparation, binding, readback and recording are offline;
``--live`` needs the owner's recorded grant and one exclusive run slot.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.bedrock import BedrockClient, BedrockConfig
from grepbit.clarification import KINDS, MAX_CHOICES
from grepbit.gateway import GEMMA_12B, MODEL, GatewayClient, GatewayConfig
from grepbit.provider import client_from_env
from tools import candidate_registry as registry, p3_admission as admission, p3_assets as assets
from tools import p3_eval as evaluator
from tools import p3_formal_policy as allocation, p3_formal_run as formal, p3_grading
from tools import p3_live_evidence as live, p3_scoring as scoring
from tools import recipe_smoke, smoke

REGISTRY_VERSION = "evaluation-registries-v1"
PACKET_VERSION = "evaluation-packet-v1"
AUTHORIZATION_VERSION = "evaluation-authorization-v1"
MANIFEST_VERSION = "evaluation-manifest-v1"
REPORT_VERSION = "evaluation-report-v1"
STOP_VERSION = "evaluation-stops-v1"
RUN_RECORD_VERSION = "evaluation-run-record-v1"
PURPOSE = "one_tiered_evaluation_run_never_promotion"
TIERS = ("dev", "regression", "holdout")
CLAIMS = ("development_observation", "observed_regression", "fresh_holdout_observation")
PROVIDERS = ("litellm", "bedrock_converse")
OBSERVATION_FIELDS = ("clarification_kind", "clarification_choice_count")
# The owner's recorded grants attest retries, fallback and cache disabled on every route.
ROUTE_POLICY = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
PANELS = ROOT / "evals/panels/index.json"
ROUTES = ROOT / "evals/routes/index.json"
RUNS = ROOT / "evals/runs/index.jsonl"
GRANT = re.compile(r"https://github\.com/cinic0101/grepbit/issues/[1-9][0-9]*#issuecomment-[1-9][0-9]*")
_ID = re.compile(r"[a-z0-9][a-z0-9.-]{2,63}")
_SLOT = re.compile(r"\.artifacts(?:/[A-Za-z0-9._-]+)+")
_SHA = re.compile(r"[0-9a-f]{64}")
_TRANSPORT = formal._TRANSPORT
_same = formal._same
_hash = formal._hash
_COMPARISON = ("UNCHANGED_CORRECT", "FIXED_KNOWN_FAILURE", "NEW_REGRESSION",
               "UNCHANGED_FAILURE", "OUTCOME_CHANGED_OTHER", "UNASSESSED_OPERATIONAL")
_PANEL_FIELDS = {"panel_id", "tier", "path", "assets", "allocation_policy", "intake", "freeze", "authoring", "note"}
_ROUTE_FIELDS = {"route_id", "provider", "model", "region", "call_timeout_seconds", "transport_security", "note"}
_RUN_FIELDS = {"version", "run_id", "recorded_at", "candidate_id", "panel_id", "tier", "route_id", "claim",
               "report_sha256", "slot", "accepted_commit", "grant", "status", "inputs", "correct",
               "families", "families_correct", "outcomes"}
_PACKET_FIELDS = {
    "version", "state", "purpose", "tier", "claim", "evidence_class", "promotion_eligible", "run_id",
    "accepted_commit", "candidate", "panel", "route", "baseline", "observation_fields", "source_identity",
    "database_sha256", "inputs", "order", "run_index_sha256", "settings", "settings_sha256", "stop_policy",
    "stop_policy_sha256", "gateway_policy", "transport_security", "data_boundary",
    "upstream_inference_attempts", "command_template",
}


# --------------------------------------------------------------------------- registries

def _read_json(path: Path, code: str = "invalid_manifest") -> dict:
    try:
        smoke._no_symlinks(path)
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise assets.P3Error(code) from None
    if not isinstance(value, dict):
        raise assets.P3Error(code)
    return value


def _location(value: object) -> Path:
    """A repository-relative file path; local archives under .artifacts are allowed."""
    if (not isinstance(value, str) or not value or len(value) > 512 or value.startswith("/")
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise assets.P3Error("invalid_manifest")
    return ROOT / value


def load_panels(path: Path | None = None) -> dict:
    index = _read_json(PANELS if path is None else path)
    if set(index) != {"registry_version", "panels"} or index["registry_version"] != REGISTRY_VERSION:
        raise assets.P3Error("invalid_manifest")
    seen = set()
    for row in index["panels"]:
        if (not isinstance(row, dict) or set(row) != _PANEL_FIELDS or _ID.fullmatch(str(row["panel_id"])) is None
                or row["panel_id"] in seen or row["tier"] not in TIERS
                or row["authoring"] not in ("development", "historical", "independent")
                or not isinstance(row["note"], str) or len(row["note"]) > 200 or not row["note"].isprintable()
                or set(row["assets"]) != {"panel", "cases", "oracles"}
                or any(not isinstance(v, str) or _SHA.fullmatch(v) is None for v in row["assets"].values())
                or row["allocation_policy"] not in (None, *allocation.VERSIONS)
                or any(row[key] is not None and (not isinstance(row[key], dict) or set(row[key]) != {"path", "sha256"}
                                                 or not isinstance(row[key]["sha256"], str)
                                                 or _SHA.fullmatch(row[key]["sha256"]) is None)
                       for key in ("intake", "freeze"))
                or (row["allocation_policy"] is not None) != (row["intake"] is not None)
                or row["tier"] == "holdout" and (row["authoring"] != "independent" or row["freeze"] is None)):
            raise assets.P3Error("invalid_manifest")
        _location(row["path"])
        for key in ("intake", "freeze"):
            if row[key] is not None:
                _location(row[key]["path"])
        seen.add(row["panel_id"])
    return index


def load_routes(path: Path | None = None) -> dict:
    index = _read_json(ROUTES if path is None else path)
    if set(index) != {"registry_version", "routes"} or index["registry_version"] != REGISTRY_VERSION:
        raise assets.P3Error("invalid_manifest")
    seen = set()
    for row in index["routes"]:
        if (not isinstance(row, dict) or set(row) != _ROUTE_FIELDS or _ID.fullmatch(str(row["route_id"])) is None
                or row["route_id"] in seen or row["provider"] not in PROVIDERS
                or not isinstance(row["model"], str) or not row["model"]
                or type(row["call_timeout_seconds"]) not in (int, float)
                or not 0 < row["call_timeout_seconds"] <= 300.0
                or row["transport_security"] not in _TRANSPORT
                or not isinstance(row["note"], str) or len(row["note"]) > 200
                or (row["provider"] == "bedrock_converse") != isinstance(row["region"], str)
                or row["provider"] == "litellm" and row["model"] not in (MODEL, GEMMA_12B.model_alias)
                or row["provider"] == "bedrock_converse" and row["transport_security"] != "tls_verification_enabled"):
            raise assets.P3Error("invalid_manifest")
        seen.add(row["route_id"])
    return index


def _entry(index: dict, key: str, ident: str, name: str) -> dict:
    for row in index[key]:
        if row[name] == ident:
            return row
    raise assets.P3Error("invalid_panel" if name == "panel_id" else "invalid_configuration")


def load_runs(path: Path | None = None) -> list[dict]:
    path = RUNS if path is None else path
    if not path.exists():
        return []
    try:
        smoke._no_symlinks(path)
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        raise assets.P3Error("invalid_manifest") from None
    runs, ids = [], set()
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise assets.P3Error("invalid_manifest") from None
        _run_record(row)
        if row["run_id"] in ids:
            raise assets.P3Error("invalid_manifest")
        ids.add(row["run_id"])
        runs.append(row)
    return runs


def _run_record(row: object) -> dict:
    if (not isinstance(row, dict) or set(row) != _RUN_FIELDS or row["version"] != RUN_RECORD_VERSION
            or row["tier"] not in TIERS or row["claim"] not in CLAIMS or row["status"] not in ("complete", "incomplete")
            or not isinstance(row["report_sha256"], str) or _SHA.fullmatch(row["report_sha256"]) is None
            or not isinstance(row["outcomes"], dict)
            or any(type(row[key]) is not int or row[key] < 0 for key in ("inputs", "correct", "families",
                                                                          "families_correct"))
            or row["grant"] is not None and (not isinstance(row["grant"], str) or GRANT.fullmatch(row["grant"]) is None)):
        raise assets.P3Error("invalid_manifest")
    return row


def derive_claim(tier: str, panel_id: str, route_id: str, runs: list[dict]) -> str:
    if tier == "dev":
        return "development_observation"
    if tier == "regression":
        return "observed_regression"
    consumed = any(run["panel_id"] == panel_id and run["route_id"] == route_id and run["claim"] == "fresh_holdout_observation"
                   for run in runs)
    return "observed_regression" if consumed else "fresh_holdout_observation"


def load_panel_entry(panel_id: str, database: Path, *, panels_path: Path | None = None) -> tuple[dict, assets.Panel, dict]:
    """Pinned panel assets, the loaded panel, and freeze metadata (holdout independence) when present."""
    entry = _entry(load_panels(panels_path), "panels", panel_id, "panel_id")
    panel_path = _location(entry["path"])
    freeze_meta = {"owner_review_reference": None, "freeze_sha256": None, "intake_sha256": None}
    if entry["allocation_policy"] is None:
        panel = assets.load_panel(panel_path)
    else:
        # Allocated panels (formal V2, holdouts) load through the reviewed intake, as the P3 tools do.
        intake_path = _location(entry["intake"]["path"])
        if evaluator._pin(intake_path)["sha256"] != entry["intake"]["sha256"]:
            raise assets.P3Error("manifest_drift")
        panel, _ = admission._policy_materials(intake_path, panel_path, entry["allocation_policy"])
        freeze_meta["intake_sha256"] = entry["intake"]["sha256"]
    pins = {"panel": panel_path, "cases": panel.cases_path, "oracles": panel.oracles_path}
    for name, path in pins.items():
        if evaluator._pin(path)["sha256"] != entry["assets"][name]:
            raise assets.P3Error("manifest_drift")
    inputs = panel.inputs()
    if entry["allocation_policy"] is not None:
        allocation.validate_allocation(inputs, entry["allocation_policy"])
    if entry["freeze"] is not None:
        freeze_path = _location(entry["freeze"]["path"])
        if evaluator._pin(freeze_path)["sha256"] != entry["freeze"]["sha256"]:
            raise assets.P3Error("manifest_drift")
        frozen = _read_json(freeze_path, "invalid_asset")
        frozen_assets = frozen.get("assets")
        if (not isinstance(frozen_assets, dict)
                or any(not isinstance(frozen_assets.get(name), dict)
                       or frozen_assets[name].get("sha256") != entry["assets"][name] for name in pins)
                or frozen.get("order") != [case.case_id for case in panel.cases]):
            raise assets.P3Error("manifest_drift")
        reference = frozen.get("owner_review_reference")
        if entry["tier"] == "holdout" and (not isinstance(reference, str) or GRANT.fullmatch(reference) is None):
            raise assets.P3Error("invalid_asset")
        freeze_meta.update(owner_review_reference=reference, freeze_sha256=entry["freeze"]["sha256"])
    smoke._fixture_identity(database)
    return entry, panel, freeze_meta


# --------------------------------------------------------------------------- packet

def settings(route: dict, input_count: int) -> dict:
    base = evaluator.settings(input_count)
    timeout = float(route["call_timeout_seconds"])
    return {**base, "model": route["model"],
            "response_mode": "bedrock_converse_normalized" if route["provider"] == "bedrock_converse" else "json_content",
            "call_timeout_seconds": timeout, "panel_timeout_seconds": timeout * input_count + 120.0,
            "execution": "owner_granted_tiered_evaluation_only", "max_runtime_invocations": input_count,
            "client_fallback": 0, "resend": 0, "continuation": 0, "best_of": 0, "resume": False}


def stop_policy() -> dict:
    return {**evaluator.stop_policy(), "version": STOP_VERSION,
            "live": "Observed client sends count as live attempts; upstream inference attempts remain unknown.",
            "authorization": "Exact packet, recorded owner grant reference and bound run slot required before credentials.",
            "semantic_failures": "Grade all inputs; wrong quality never stops the panel.",
            "claim": "Derived from tier and run index at preparation; a drifted index is manifest_drift at live.",
            "replay": "No resume, retry, repair, fallback or automatic second run."}


def data_boundary() -> dict:
    return {"source": "synthetic_learningops_only", "wire": "individual_question_and_unchanged_runtime_only",
            "evaluator_metadata_on_wire": False, "raw_completion_or_reasoning_persisted": False,
            "observations": "closed clarification kind and choice count per clarify action; no text",
            "quality_claim": "tier_and_index_derived_never_promotion"}


def command_template(accepted_commit: str) -> list[str]:
    return [".venv/bin/python", "tools/evaluate.py", "--live",
            "--packet", "<EXACT_PACKET>", "--authorization", "<EXACT_AUTHORIZATION_ENVELOPE>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", accepted_commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>",
            "--gateway-retries", ROUTE_POLICY["retries"], "--gateway-fallback", ROUTE_POLICY["fallback"],
            "--gateway-cache", ROUTE_POLICY["cache"], "--output-dir", "<BOUND_RUN_SLOT>"]


def _baseline_projection(path: Path) -> dict:
    """Per-input correctness of a prior report of the same panel; read through its own reader."""
    raw = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    version = raw.get("report_version")
    report = read_report(path) if version == REPORT_VERSION else formal.read_report(path) if version == formal.REPORT_VERSION else None
    if report is None or report["status"] != "complete":
        raise assets.P3Error("invalid_asset")
    rows = [{key: result[key] for key in ("case_id", "family_id", "outcome", "actual_action", "checked_wrong")}
            | {"correct": score["correct"]}
            for result, score in zip(report["results"], report["summary"]["per_input"])]
    families = {key: value["family_all_variants_correct"] for key, value in report["summary"]["per_family"].items()}
    return {"reference": path.absolute().relative_to(ROOT).as_posix() if path.absolute().is_relative_to(ROOT) else str(path),
            "sha256": evaluator._pin(path)["sha256"], "report_version": version,
            "inputs": rows, "family_correct": families}


def _comparison(baseline: dict, results: list[dict], scored: dict) -> dict:
    rows, counts, action_changes, outcome_changes = [], dict.fromkeys(_COMPARISON, 0), [], []
    if [row["case_id"] for row in baseline["inputs"]] != [row["case_id"] for row in results]:
        raise assets.P3Error("invalid_scoring")
    for old, result, current in zip(baseline["inputs"], results, scored["per_input"]):
        unassessed = (result["status"] != "completed" or result["outcome"] in ("operational_failure", "not_run")
                      or result.get("operational_error") is not None or result.get("runner_error_code") is not None)
        if unassessed:
            category = "UNASSESSED_OPERATIONAL"
        elif old["correct"] and current["correct"]:
            category = "UNCHANGED_CORRECT"
        elif old["correct"]:
            category = "NEW_REGRESSION"
        elif current["correct"]:
            category = "FIXED_KNOWN_FAILURE"
        elif result["outcome"] == old["outcome"] and result["actual_action"] == old["actual_action"]:
            category = "UNCHANGED_FAILURE"
        else:
            category = "OUTCOME_CHANGED_OTHER"
        counts[category] += 1
        if not unassessed and result["actual_action"] != old["actual_action"]:
            action_changes.append(old["case_id"])
        if not unassessed and result["outcome"] != old["outcome"]:
            outcome_changes.append(old["case_id"])
        rows.append({"case_id": old["case_id"], "category": category, "old_action": old["actual_action"],
                     "new_action": result["actual_action"], "old_outcome": old["outcome"],
                     "new_outcome": result["outcome"]})
    return {"baseline_sha256": baseline["sha256"], "taxonomy": rows, "category_counts": counts,
            "known_failures_fixed": counts["FIXED_KNOWN_FAILURE"],
            "known_failures_total": sum(not row["correct"] for row in baseline["inputs"]),
            "new_regressions": counts["NEW_REGRESSION"],
            "previously_correct_total": sum(row["correct"] for row in baseline["inputs"]),
            "family_delta": {key: {"baseline_passed": baseline["family_correct"].get(key),
                                   "current_passed": value["family_all_variants_correct"]}
                             for key, value in scored["per_family"].items()},
            "action_changes": action_changes, "outcome_changes": outcome_changes}


def _observations(results: list[dict]) -> dict:
    kinds, false_kinds = dict.fromkeys(KINDS, 0), dict.fromkeys(KINDS, 0)
    for row in results:
        kind = row["clarification_kind"]
        if row["status"] == "completed" and row["actual_action"] == "clarify" and isinstance(kind, str) and kind in kinds:
            kinds[kind] += 1
            if row["outcome"] == "false_clarification":
                false_kinds[kind] += 1
    return {"clarify_actions": sum(kinds.values()), "kinds": kinds, "false_clarification_kinds": false_kinds}


def _run_id(candidate_id: str, panel_id: str, route_id: str, source_sha: str) -> str:
    return f"{panel_id}--{route_id}--{candidate_id}--{source_sha[:12]}"


def _packet_contract(packet: dict) -> None:
    """Archived structural validation; never consults registries, credentials or the checkout."""
    assets.object_fields(packet, _PACKET_FIELDS)
    source = packet["source_identity"]
    if (packet["version"] != PACKET_VERSION or packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != PURPOSE or packet["tier"] not in TIERS or packet["claim"] not in CLAIMS
            or packet["evidence_class"] != packet["claim"] or packet["promotion_eligible"] is not False
            or (packet["tier"] == "dev") != (packet["claim"] == "development_observation")
            or packet["tier"] == "regression" and packet["claim"] != "observed_regression"
            or not isinstance(packet["accepted_commit"], str) or not formal._COMMIT.fullmatch(packet["accepted_commit"])
            or not isinstance(source, dict) or source.get("git_commit") != packet["accepted_commit"]
            or source.get("branch") != "dev" or source.get("worktree_dirty") is not False
            or not isinstance(source.get("files_sha256"), dict)
            or packet["observation_fields"] != list(OBSERVATION_FIELDS)
            or packet["gateway_policy"] != smoke.policy_attestation(ROUTE_POLICY, required=True)
            or packet["transport_security"] not in _TRANSPORT or packet["upstream_inference_attempts"] is not None
            or packet["data_boundary"] != data_boundary()
            or packet["command_template"] != command_template(packet["accepted_commit"])
            or not _same(packet["stop_policy"], stop_policy())
            or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or packet["settings_sha256"] != assets.digest(packet["settings"])):
        raise assets.P3Error("invalid_manifest")
    for path, digest in source["files_sha256"].items():
        assets.text(path)
        _hash(digest)
    _hash(packet["database_sha256"])
    _hash(packet["run_index_sha256"])
    candidate = assets.object_fields(packet["candidate"], {"candidate_id", "candidate_sha256", "semantic_identity_sha256"})
    if _ID.fullmatch(str(candidate["candidate_id"])) is None:
        raise assets.P3Error("invalid_manifest")
    _hash(candidate["candidate_sha256"])
    _hash(candidate["semantic_identity_sha256"])
    panel = assets.object_fields(packet["panel"], {"panel_id", "tier", "authoring", "assets", "allocation_policy",
                                                    "intake_sha256", "freeze_sha256", "owner_review_reference",
                                                    "input_count"})
    if (panel["tier"] != packet["tier"] or panel["authoring"] not in ("development", "historical", "independent")
            or set(panel["assets"]) != {"panel", "cases", "oracles"}
            or panel["allocation_policy"] not in (None, *allocation.VERSIONS)
            or panel["tier"] == "holdout" and (panel["authoring"] != "independent" or panel["freeze_sha256"] is None
                                               or not isinstance(panel["owner_review_reference"], str)
                                               or GRANT.fullmatch(panel["owner_review_reference"]) is None)
            or type(panel["input_count"]) is not int or panel["input_count"] != len(packet["inputs"])):
        raise assets.P3Error("invalid_manifest")
    for digest in panel["assets"].values():
        _hash(digest)
    for key in ("freeze_sha256", "intake_sha256"):
        if panel[key] is not None:
            _hash(panel[key])
    if (panel["allocation_policy"] is not None) != (panel["intake_sha256"] is not None):
        raise assets.P3Error("invalid_manifest")
    route = assets.object_fields(packet["route"], _ROUTE_FIELDS)
    if (route["provider"] not in PROVIDERS or route["transport_security"] != packet["transport_security"]
            or not _same(packet["settings"], settings(route, len(packet["inputs"])))):
        raise assets.P3Error("invalid_manifest")
    if packet["run_id"] != _run_id(candidate["candidate_id"], panel["panel_id"], route["route_id"],
                                   assets.digest(source)):
        raise assets.P3Error("invalid_manifest")
    if (not isinstance(packet["inputs"], list) or not 1 <= len(packet["inputs"]) <= assets.MAX_INPUTS
            or any(not isinstance(row, dict) for row in packet["inputs"])
            or packet["order"] != [row.get("case_id") for row in packet["inputs"]]):
        raise assets.P3Error("invalid_manifest")
    for row in packet["inputs"]:
        assets.object_fields(row, evaluator._INPUT_FIELDS)
        _hash(row["question_sha256"])
        assets.Provenance.from_mapping(row["provenance"], row["exposure"])
    if panel["allocation_policy"] is not None:
        allocation.validate_allocation(packet["inputs"], panel["allocation_policy"])
    if packet["tier"] == "holdout" and any(row["exposure"] != "frozen_fresh" for row in packet["inputs"]):
        raise assets.P3Error("invalid_manifest")
    baseline = packet["baseline"]
    if baseline is not None:
        assets.object_fields(baseline, {"reference", "sha256", "report_version", "inputs", "family_correct"})
        _hash(baseline["sha256"])
        if (baseline["report_version"] not in (REPORT_VERSION, formal.REPORT_VERSION)
                or [row.get("case_id") for row in baseline["inputs"]] != packet["order"]
                or any(set(row) != {"case_id", "family_id", "outcome", "actual_action", "checked_wrong", "correct"}
                       or type(row["correct"]) is not bool for row in baseline["inputs"])
                or not isinstance(baseline["family_correct"], dict)):
            raise assets.P3Error("invalid_manifest")


def build_packet(database: Path, *, candidate_id: str, panel_id: str, route_id: str, accepted_commit: str,
                 gateway_policies: dict, baseline_path: Path | None = None,
                 panels_path: Path | None = None, routes_path: Path | None = None,
                 runs_path: Path | None = None, candidates_index: Path | None = None) -> tuple[dict, assets.Panel]:
    if gateway_policies != ROUTE_POLICY:
        raise assets.P3Error("invalid_configuration")
    try:
        checked = registry.check(candidates_index)
        candidate = registry.current(candidates_index)
    except registry.RegistryError:
        raise assets.P3Error("source_identity_failure") from None
    if checked["candidate_id"] != candidate_id:
        raise assets.P3Error("source_identity_failure")
    entry, panel, freeze_meta = load_panel_entry(panel_id, database, panels_path=panels_path)
    route = _entry(load_routes(routes_path), "routes", route_id, "route_id")
    source = evaluator._source_identity(panel, None)
    recipe_smoke._accepted(source, accepted_commit)
    runs_file = RUNS if runs_path is None else runs_path
    runs = load_runs(runs_file)
    run_index_sha = evaluator._pin(runs_file)["sha256"] if runs_file.exists() else assets.digest([])
    claim = derive_claim(entry["tier"], panel_id, route_id, runs)
    inputs = panel.inputs()
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized", "purpose": PURPOSE,
        "tier": entry["tier"], "claim": claim, "evidence_class": claim, "promotion_eligible": False,
        "run_id": _run_id(candidate_id, panel_id, route_id, assets.digest(source)),
        "accepted_commit": accepted_commit,
        "candidate": {"candidate_id": candidate_id, "candidate_sha256": candidate["candidate_sha256"],
                      "semantic_identity_sha256": candidate["semantic_identity_sha256"]},
        "panel": {"panel_id": panel_id, "tier": entry["tier"], "authoring": entry["authoring"],
                  "assets": dict(entry["assets"]), "allocation_policy": entry["allocation_policy"],
                  "intake_sha256": freeze_meta["intake_sha256"], "freeze_sha256": freeze_meta["freeze_sha256"],
                  "owner_review_reference": freeze_meta["owner_review_reference"], "input_count": len(inputs)},
        "route": dict(route),
        "baseline": _baseline_projection(baseline_path) if baseline_path is not None else None,
        "observation_fields": list(OBSERVATION_FIELDS), "source_identity": source,
        "database_sha256": smoke._fixture_identity(database), "inputs": inputs,
        "order": [case.case_id for case in panel.cases], "run_index_sha256": run_index_sha,
        "settings": settings(route, len(inputs)), "settings_sha256": assets.digest(settings(route, len(inputs))),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(ROUTE_POLICY, required=True),
        "transport_security": route["transport_security"], "data_boundary": data_boundary(),
        "upstream_inference_attempts": None, "command_template": command_template(accepted_commit),
    }
    _packet_contract(packet)
    return packet, panel


def validate_packet(path: Path, database: Path, *, accepted_commit: str, **registries) -> tuple[dict, assets.Panel]:
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise assets.P3Error("accepted_commit_required")
    baseline_path = None if packet["baseline"] is None else _location(packet["baseline"]["reference"])
    current, panel = build_packet(database, candidate_id=packet["candidate"]["candidate_id"],
                                  panel_id=packet["panel"]["panel_id"], route_id=packet["route"]["route_id"],
                                  accepted_commit=accepted_commit, gateway_policies=dict(ROUTE_POLICY),
                                  baseline_path=baseline_path, **registries)
    if not _same(current, packet):
        raise assets.P3Error("manifest_drift")
    return packet, panel


def prepare(database: Path, output_dir: Path, **options) -> dict:
    packet, _ = build_packet(database, **options)
    artifacts = smoke._Artifacts(output_dir, packet)
    report = {"version": PACKET_VERSION, "state": "incomplete", "packet_sha256": evaluator._pin(
        output_dir / "manifest.json")["sha256"], "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts.persist(report)
    registries = {key: options[key] for key in ("panels_path", "routes_path", "runs_path", "candidates_index")
                  if key in options}
    validate_packet(output_dir / "manifest.json", database, accepted_commit=packet["accepted_commit"], **registries)
    report.update(state="prepared_not_authorized", run_id=packet["run_id"], tier=packet["tier"], claim=packet["claim"])
    artifacts.persist(report)
    return report


# --------------------------------------------------------------------------- authorization and live

def _run_slot(path: Path) -> str:
    if not isinstance(path, Path):
        raise assets.P3Error("invalid_manifest")
    try:
        slot = path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        raise assets.P3Error("invalid_manifest") from None
    if _SLOT.fullmatch(slot) is None or any(part in (".", "..") for part in slot.split("/")):
        raise assets.P3Error("invalid_manifest")
    smoke._no_symlinks(path)
    return slot


def _authorization(value: dict, packet_sha: str) -> dict:
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"})
    if value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha:
        raise assets.P3Error("invalid_manifest")
    _hash(packet_sha)
    reference, slot = value["owner_authorization_reference"], value["run_slot"]
    if (not isinstance(reference, str) or GRANT.fullmatch(reference) is None or not isinstance(slot, str)
            or _SLOT.fullmatch(slot) is None or any(part in (".", "..") for part in slot.split("/"))):
        raise assets.P3Error("invalid_manifest")
    return value


def _validate_run_slot(authorization: dict, output_dir: Path) -> None:
    if authorization["run_slot"] != _run_slot(output_dir):
        raise assets.P3Error("invalid_manifest")


def bind_authorization(packet_path: Path, reference: str, output_path: Path, run_output_dir: Path) -> dict:
    packet = assets.read_asset(packet_path)
    _packet_contract(packet)
    digest = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference, "run_slot": _run_slot(run_output_dir)}, digest)
    live._write_authorization(output_path, value)
    return value


def _manifest(packet: dict, packet_sha: str, authorization: dict, authorization_sha: str) -> dict:
    return {
        "manifest_version": MANIFEST_VERSION, "packet_sha256": packet_sha, "authorization_sha256": authorization_sha,
        "owner_authorization_reference": authorization["owner_authorization_reference"],
        "run_slot": authorization["run_slot"], "run_id": packet["run_id"], "tier": packet["tier"],
        "claim": packet["claim"], "accepted_commit": packet["accepted_commit"], "candidate": packet["candidate"],
        "route": packet["route"], "evaluator_version": p3_grading.VERSION, "panel_id": packet["panel"]["panel_id"],
        "panel_kind": "evaluation", "inputs": packet["inputs"], "order": packet["order"],
        "allocation_policy": (allocation.identity(packet["panel"]["allocation_policy"])
                              if packet["panel"]["allocation_policy"] else None),
        "settings": packet["settings"], "settings_sha256": packet["settings_sha256"],
        "stop_policy": packet["stop_policy"], "stop_policy_sha256": packet["stop_policy_sha256"],
        "baseline": packet["baseline"], "observation_fields": packet["observation_fields"],
        "evidence_class": packet["claim"], "promotion_eligible": False,
        "preparation": {"kind": "accepted", "accepted_commit": packet["accepted_commit"]},
    }


def _report(manifest: dict, packet: dict) -> dict:
    header = {key: manifest[key] for key in ("manifest_version", "evaluator_version", "panel_id", "panel_kind",
                                             "inputs", "order", "settings", "settings_sha256", "stop_policy",
                                             "stop_policy_sha256", "preparation")}
    report = evaluator._new_report(header, "live")
    report["allocation_policy"] = manifest["allocation_policy"]
    report.update(report_version=REPORT_VERSION, runtime_invocations=0, transport_security=None,
                  gateway_policy=packet["gateway_policy"],
                  owner_authorization_reference=manifest["owner_authorization_reference"],
                  run_slot=manifest["run_slot"], run_id=manifest["run_id"], tier=manifest["tier"],
                  claim=manifest["claim"], candidate=manifest["candidate"], route=manifest["route"],
                  panel=packet["panel"], baseline=manifest["baseline"],
                  observation_fields=manifest["observation_fields"], evidence_class=manifest["claim"],
                  promotion_eligible=False,
                  scope=f"One {manifest['tier']} tier evaluation run ({manifest['claim']}); never promotion.")
    report["manifest_sha256"] = assets.digest(manifest)
    for row in report["results"]:
        row["phase"] = "not_started"
        row.update(dict.fromkeys(OBSERVATION_FIELDS))
    return report


def _summarize(report: dict) -> None:
    value = scoring.summarize(report["results"], report["results"], panel_kind="development",
                              run_status=report["status"])
    diagnostics = value.pop("promotion")["gates"]
    value.update(panel_kind="evaluation", tier=report["tier"], claim=report["claim"],
                 evidence_class=report["claim"], promotion_eligible=False, diagnostic_gates=diagnostics,
                 observations=_observations(report["results"]),
                 comparison=(_comparison(report["baseline"], report["results"], value)
                             if report["baseline"] is not None else None))
    report["summary"] = value


def _check_observation(row: dict) -> None:
    kind, count = row["clarification_kind"], row["clarification_choice_count"]
    if kind is not None and kind not in KINDS:
        raise assets.P3Error("invalid_asset")
    if count is not None and (type(count) is not int or not 2 <= count <= MAX_CHOICES
                              or kind == "comparison_roles" and count != 2):
        raise assets.P3Error("invalid_asset")
    clarified = row["status"] == "completed" and row["actual_action"] == "clarify"
    if clarified != (kind is not None) or clarified != (count is not None):
        raise assets.P3Error("invalid_asset")


@dataclass(frozen=True)
class _Route:
    provider: str
    model: str
    region: str | None
    call_timeout_seconds: float
    transport_security: str

    @property
    def expected_model(self):
        return GEMMA_12B if self.provider == "litellm" and self.model == GEMMA_12B.model_alias else None

    @property
    def requested_profile(self):
        return self.model if self.provider == "bedrock_converse" else None


def _route(packet: dict) -> _Route:
    route = packet["route"]
    return _Route(route["provider"], route["model"], route["region"], float(route["call_timeout_seconds"]),
                  route["transport_security"])


class _LiveEvidence(live._LiveEvidence):
    summarize = staticmethod(_summarize)
    observation_fields = OBSERVATION_FIELDS

    def __init__(self, route: _Route | None = None):
        if not isinstance(route, _Route):
            raise assets.P3Error("invalid_configuration")
        super().__init__(route.expected_model, requested_profile=route.requested_profile)
        self.route = route
        self.maximum = assets.MAX_INPUTS

    @staticmethod
    def observe_result(result) -> dict:
        clarification = getattr(result, "clarification", None)
        if clarification is None:
            return dict.fromkeys(OBSERVATION_FIELDS)
        return {"clarification_kind": clarification.kind, "clarification_choice_count": len(clarification.choices)}

    def check_report(self, report):
        super().check_report(report)
        for row in report["results"]:
            _check_observation(row)


def _entries(panel, packet):
    return evaluator._panel_entries(panel)


def _expected_model(packet):
    _packet_contract(packet)
    return _route(packet)


def _admitted_client(packet, env_file):
    """The route decides the provider client; the packet has no live override."""
    _packet_contract(packet)
    route = _route(packet)
    if route.provider == "bedrock_converse":
        client = client_from_env(env_file=env_file)
        if (type(client) is not BedrockClient or type(client.config) is not BedrockConfig
                or client.config.region != route.region or client.config.model != route.model
                or client.config.max_call_timeout_seconds < route.call_timeout_seconds):
            raise assets.P3Error("invalid_configuration")
        return client
    config = (GatewayConfig.from_env(env_file=env_file) if route.expected_model is None
              else GatewayConfig.from_env(env_file=env_file, expected_model=route.expected_model))
    if config.model != route.model:
        raise assets.P3Error("invalid_configuration")
    return GatewayClient(config)


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict, clock=time.monotonic) -> dict:
    return await live._run_live(database, output_dir, packet_path=packet_path, authorization_path=authorization_path,
                                accepted_commit=accepted_commit, env_file=env_file,
                                gateway_policies=gateway_policies, clock=clock, contract=sys.modules[__name__])


def read_report(path: Path) -> dict:
    """Offline archive verification; no registries, checkout, DB or configuration access."""
    if path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    packet = assets.read_asset(path.parent / "packet.json")
    _packet_contract(packet)
    packet_sha = evaluator._pin(path.parent / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(path.parent / "authorization.json"), packet_sha)
    _validate_run_slot(authorization, path.parent)
    expected_manifest = _manifest(packet, packet_sha, authorization,
                                  evaluator._pin(path.parent / "authorization.json")["sha256"])
    manifest = assets.read_asset(path.parent / "manifest.json")
    if not _same(manifest, expected_manifest):
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    expected = _report(manifest, packet)
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != len(packet["inputs"]):
        raise assets.P3Error("invalid_asset")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(expected["results"][0]):
            raise assets.P3Error("invalid_asset")
        _check_observation(row)
    route = _route(packet)
    live._validate_report(report, manifest, expected, packet["inputs"], maximum=len(packet["inputs"]),
                          transport_security=packet["transport_security"], summarize=_summarize,
                          expected_model=route.expected_model, requested_profile=route.requested_profile)
    _LiveEvidence(route).check_report(report)
    for key in ("run_slot", "run_id", "tier", "claim", "candidate", "route", "panel", "baseline",
                "observation_fields", "evidence_class", "promotion_eligible"):
        if not _same(report[key], expected[key]):
            raise assets.P3Error("invalid_asset")
    summary = report["summary"]
    if (summary["panel_kind"] != "evaluation" or summary["promotion_eligible"] is not False
            or "promotion" in summary or summary["claim"] != packet["claim"]):
        raise assets.P3Error("invalid_asset")
    return report


def record(report_path: Path, *, runs_path: Path | None = None, now: str | None = None) -> dict:
    """Append one run to the append-only index after offline readback; refuses a duplicate run id."""
    report = read_report(report_path)
    runs_file = RUNS if runs_path is None else runs_path
    runs = load_runs(runs_file)
    if any(run["run_id"] == report["run_id"] for run in runs):
        raise assets.P3Error("artifact_conflict")
    summary = report["summary"]
    row = {"version": RUN_RECORD_VERSION, "run_id": report["run_id"],
           "recorded_at": now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "candidate_id": report["candidate"]["candidate_id"], "panel_id": report["panel"]["panel_id"],
           "tier": report["tier"], "route_id": report["route"]["route_id"], "claim": report["claim"],
           "report_sha256": evaluator._pin(report_path)["sha256"], "slot": report["run_slot"],
           "accepted_commit": report["preparation"]["accepted_commit"],
           "grant": report["owner_authorization_reference"], "status": report["status"],
           "inputs": summary["input_count"], "correct": sum(r["correct"] for r in summary["per_input"]),
           "families": len(summary["per_family"]),
           "families_correct": sum(v["family_all_variants_correct"] for v in summary["per_family"].values()),
           "outcomes": summary["outcomes"]}
    _run_record(row)
    runs_file.parent.mkdir(parents=True, exist_ok=True)
    with runs_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def main(argv=None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report", "record"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "run-output-dir",
                 "baseline", "report-path"):
        parser.add_argument("--" + name, type=Path)
    for name in ("candidate", "panel", "route", "accepted-commit", "owner-authorization-reference"):
        parser.add_argument("--" + name)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "candidate", "panel", "route"} | common | ({"baseline"} if args.baseline else set())
                   if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"} if args.report else {"record", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, candidate_id=args.candidate, panel_id=args.panel,
                             route_id=args.route, accepted_commit=args.accepted_commit, gateway_policies=policies,
                             baseline_path=args.baseline)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output, args.run_output_dir)
        elif args.record:
            result = record(args.report_path)
        else:
            if args.live:
                asyncio.run(run_live(args.db, args.output_dir, packet_path=args.packet,
                                     authorization_path=args.authorization, accepted_commit=args.accepted_commit,
                                     env_file=args.env_file, gateway_policies=policies))
            report = read_report(args.output_dir / "report.json" if args.live else args.report_path)
            result = {key: report[key] for key in (
                "report_version", "run_id", "tier", "claim", "status", "stop_reason", "error_code",
                "client_http_attempts", "live_model_attempts", "runtime_invocations", "possible_in_flight_attempts",
                "upstream_inference_attempts", "transport_security", "evidence_class", "promotion_eligible", "summary")}
        print(model.canonical_json(result))
        return 0 if result.get("status") in (None, "complete") else 1
    except evaluator._SAFE_ERRORS as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except registry.RegistryError as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": "source_identity_failure",
                                    "registry_error": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, *evaluator._INTERNAL_ERRORS):
        print('{"status":"incomplete","error_code":"invalid_manifest"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
