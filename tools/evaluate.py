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
here is promotion. Preparation, binding, readback, recording, replay,
aggregation and the candidate gate are offline; ``--live`` needs the owner's
recorded grant and one exclusive run slot.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model, recipe_model
from grepbit.bedrock import BedrockClient, BedrockConfig
from grepbit.clarification import KINDS, MAX_CHOICES
from grepbit.contracts import KernelError
from grepbit.gateway import GEMMA_12B, MODEL, GatewayClient, GatewayConfig, ModelError
from grepbit.provider import client_from_env
from tools import candidate_registry as registry, p3_admission as admission, p3_assets as assets
from tools import p3_eval as evaluator
from tools import p3_formal_policy as allocation, p3_grading
from tools.history import p3_formal_run as formal
from tools import p3_live_evidence as live, p3_scoring as scoring
from tools import recipe_smoke, smoke

REGISTRY_VERSION = "evaluation-registries-v1"
PACKET_V1 = "evaluation-packet-v1"
PACKET_V2 = "evaluation-packet-v2"
# The version new packets are prepared at; archives keep their own version.
PACKET_VERSION = PACKET_V2
AUTHORIZATION_VERSION = "evaluation-authorization-v1"
MANIFEST_VERSIONS = {PACKET_V1: "evaluation-manifest-v1", PACKET_V2: "evaluation-manifest-v2"}
REPORT_VERSIONS = {PACKET_V1: "evaluation-report-v1", PACKET_V2: "evaluation-report-v2"}
MANIFEST_VERSION = MANIFEST_VERSIONS[PACKET_VERSION]
REPORT_VERSION = REPORT_VERSIONS[PACKET_VERSION]
REPLAY_VERSION = "evaluation-replay-v1"
AGGREGATE_VERSION = "evaluation-aggregate-v2"
GATE_VERSION = "evaluation-gate-v2"
STOP_VERSION = "evaluation-stops-v1"
RUN_RECORD_VERSION = "evaluation-run-record-v1"
PURPOSE = "one_tiered_evaluation_run_never_promotion"
TIERS = ("dev", "regression", "holdout")
CLAIMS = ("development_observation", "observed_regression", "fresh_holdout_observation")
PROVIDERS = ("litellm", "bedrock_converse")
OBSERVATIONS = {PACKET_V1: ("clarification_kind", "clarification_choice_count"),
                PACKET_V2: ("clarification_kind", "clarification_choice_count", "validated_action")}
OBSERVATION_FIELDS = OBSERVATIONS[PACKET_VERSION]
MAX_REPETITION = 99
MAX_ACTION_BYTES = 16384
# Archived action vocabulary is pinned here, not taken from the runtime, so old archives keep reading.
_ACTION_RECIPES = ("overview", "compare", "breakdown")
_CHOICE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}")
_ACTION_DEPTH = 10
_ACTION_STRING = 256
# The owner's recorded grants attest retries, fallback and cache disabled on every route.
ROUTE_POLICY = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
PANELS = ROOT / "evals/panels/index.json"
ROUTES = ROOT / "evals/routes/index.json"
RUNS = ROOT / "evals/runs/index.jsonl"
GRANT = re.compile(r"https://github\.com/cinic0101/grepbit/issues/[1-9][0-9]*#issuecomment-[1-9][0-9]*")
_ID = re.compile(r"[a-z0-9][a-z0-9.-]{2,63}")
_SLOT = re.compile(r"\.artifacts(?:/[A-Za-z0-9._-]+)+")
_SHA = re.compile(r"[0-9a-f]{64}")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
_TRANSPORT = formal._TRANSPORT
_same = formal._same
_hash = formal._hash
_COMPARISON = ("UNCHANGED_CORRECT", "FIXED_KNOWN_FAILURE", "NEW_REGRESSION",
               "UNCHANGED_FAILURE", "OUTCOME_CHANGED_OTHER", "UNASSESSED_OPERATIONAL")
_PANEL_FIELDS = {"panel_id", "tier", "path", "assets", "allocation_policy", "intake", "freeze", "authoring", "note"}
# docs/count-assumption.md: an optional, pinned annex of stated-assumption expectations for dev panels.
ANNEX_VERSION = "count-assumption-annex-v1"
ASSUMPTION = {"count_basis": "booked_seats"}
# The typed Compare orientation of v15 archives (docs/compare-orientation-v15.md), pinned so archives stay
# readable under any later candidate.
ORIENTATIONS = ("stated", "unresolved")
# The typed Overview count reading of v16 archives (docs/count-reading-v16.md), pinned likewise.
UNAVAILABLE_COUNTS = ("known_booking_accounts", "attendance_visits", "distinct_people")
COUNT_REQUESTS = ("none", "booked_seats", "unresolved", *UNAVAILABLE_COUNTS)
_ROUTE_FIELDS = {"route_id", "provider", "model", "region", "call_timeout_seconds", "transport_security", "note"}
_RUN_FIELDS = {"version", "run_id", "recorded_at", "candidate_id", "panel_id", "tier", "route_id", "claim",
               "report_sha256", "slot", "accepted_commit", "grant", "status", "inputs", "correct",
               "families", "families_correct", "outcomes"}
_PACKET_FIELDS_V1 = {
    "version", "state", "purpose", "tier", "claim", "evidence_class", "promotion_eligible", "run_id",
    "accepted_commit", "candidate", "panel", "route", "baseline", "observation_fields", "source_identity",
    "database_sha256", "inputs", "order", "run_index_sha256", "settings", "settings_sha256", "stop_policy",
    "stop_policy_sha256", "gateway_policy", "transport_security", "data_boundary",
    "upstream_inference_attempts", "command_template",
}
_PACKET_FIELDS = {PACKET_V1: _PACKET_FIELDS_V1, PACKET_V2: _PACKET_FIELDS_V1 | {"repetition"}}


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


def _report_digest(path: Path) -> str:
    """Digest of a report archive, which may exceed the asset cap but never the report cap."""
    try:
        smoke._no_symlinks(path)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise assets.P3Error("invalid_asset")
        with path.open("rb") as stream:
            raw = stream.read(evaluator.MAX_REPORT_BYTES + 1)
    except OSError:
        raise assets.P3Error("invalid_asset") from None
    if len(raw) > evaluator.MAX_REPORT_BYTES:
        raise assets.P3Error("invalid_asset")
    return smoke._digest(raw)


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
        if (not isinstance(row, dict) or set(row) not in (_PANEL_FIELDS, _PANEL_FIELDS | {"annex"})
                or _ID.fullmatch(str(row["panel_id"])) is None
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
                or "annex" in row and (row["tier"] != "dev" or not isinstance(row["annex"], dict)
                                       or set(row["annex"]) != {"path", "sha256"}
                                       or not isinstance(row["annex"]["sha256"], str)
                                       or _SHA.fullmatch(row["annex"]["sha256"]) is None)
                or (row["allocation_policy"] is not None) != (row["intake"] is not None)
                or row["tier"] == "holdout" and (row["authoring"] != "independent" or row["freeze"] is None)):
            raise assets.P3Error("invalid_manifest")
        _location(row["path"])
        for key in ("intake", "freeze", "annex"):
            if row.get(key) is not None:
                _location(row[key]["path"])
        seen.add(row["panel_id"])
    # The same frozen assets under a second id would earn a second fresh claim; a
    # holdout's case text must be unique across the whole registry.
    digests = [tuple(sorted(row["assets"].items())) for row in index["panels"]]
    if len(set(digests)) != len(digests):
        raise assets.P3Error("invalid_manifest")
    cases = [row["assets"]["cases"] for row in index["panels"]]
    if any(cases.count(row["assets"]["cases"]) != 1 for row in index["panels"] if row["tier"] == "holdout"):
        raise assets.P3Error("invalid_manifest")
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
    identities = [(row["provider"], row["model"], row["region"]) for row in index["routes"]]
    if len(set(identities)) != len(identities):
        raise assets.P3Error("invalid_manifest")
    return index


def _read_annex(path: Path) -> dict:
    """The closed annex document: each listed oracle expects the one stated count assumption.

    An empty listing is admitted: no oracle of the panel expects one (docs/count-assumption.md)."""
    data = assets.read_asset(path)
    if (not isinstance(data, dict) or set(data) != {"version", "expectations"} or data["version"] != ANNEX_VERSION
            or not isinstance(data["expectations"], dict)
            or any(not isinstance(key, str) or value != ASSUMPTION for key, value in data["expectations"].items())):
        raise assets.P3Error("invalid_asset")
    return data["expectations"]


def annex_expectations(entry: dict, panel: assets.Panel) -> dict:
    """A registered panel's pinned annex; every listed oracle is one of the panel's Overview answers."""
    path = _location(entry["annex"]["path"])
    if evaluator._pin(path)["sha256"] != entry["annex"]["sha256"]:
        raise assets.P3Error("manifest_drift")
    expectations = _read_annex(path)
    oracles = {oracle.oracle_id: oracle for oracle in panel.oracles}
    if any(name not in oracles or oracles[name].branch != "answer" or oracles[name].to_dict()["recipe_id"] != "overview"
           for name in expectations):
        raise assets.P3Error("invalid_asset")
    return expectations


def _panel_annex(panel_block: object, panels_path: Path | None = None) -> dict | None:
    """The annex a report's panel identity pins, re-read through the registry and checked; None without one."""
    sha = panel_block.get("annex_sha256") if isinstance(panel_block, dict) else None
    if sha is None:
        return None
    entry = _entry(load_panels(panels_path), "panels", panel_block["panel_id"], "panel_id")
    if entry.get("annex") is None or entry["annex"]["sha256"] != sha:
        raise assets.P3Error("manifest_drift")
    path = _location(entry["annex"]["path"])
    if evaluator._pin(path)["sha256"] != sha:
        raise assets.P3Error("manifest_drift")
    return _read_annex(path)


def _count_basis_clarification(action: object) -> bool:
    return (isinstance(action, dict) and action.get("outcome") == "clarify"
            and isinstance(action.get("clarification"), dict) and action["clarification"].get("kind") == "count_basis")


def _stated_assumption(action: object, actual_action: str | None = None) -> dict | None:
    """The count assumption a persisted request states: v13's explicit key, or v16's unresolved count reading.

    A model count_basis clarification states the assumption only on a row whose recorded ``actual_action`` is
    ``answer``: v19's server answer (ADR #158). On a ``clarify`` row, or with no recorded row, it is the
    clarification it was and states none; no current runtime is consulted (v20, docs/v18-restoration-v20.md)."""
    if _count_basis_clarification(action):
        return dict(ASSUMPTION) if actual_action == "answer" else None
    if not isinstance(action, dict) or action.get("outcome") != "request":
        return None
    if "assumption" in action:
        return action["assumption"]
    return dict(ASSUMPTION) if action.get("count_request") == "unresolved" else None


def annexed(row: dict, frozen_correct: bool, expectations: dict | None) -> str | None:
    """The annex verdict on one graded row: None when no annex applies, else correct, wrong or unassessed.

    The frozen grade stays as recorded. A frozen-correct answer is correct only if its persisted validated action
    carries exactly the expected assumption (none when the oracle is not listed); without a persisted action the
    assumption cannot be checked."""
    if expectations is None:
        return None
    if not frozen_correct:
        return "wrong"
    text = row.get("validated_action")
    if text is None:
        return "unassessed"
    try:
        action = model.strict_json(text)
    except ModelError:
        raise assets.P3Error("invalid_asset") from None
    stated = _stated_assumption(action, row.get("actual_action"))
    return "correct" if stated == expectations.get(row["oracle_id"]) else "wrong"


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
    fresh = [(run["panel_id"], run["route_id"]) for run in runs if run["claim"] == "fresh_holdout_observation"]
    if len(set(fresh)) != len(fresh):
        raise assets.P3Error("invalid_manifest")
    return runs


def _run_record(row: object) -> dict:
    if (not isinstance(row, dict) or set(row) != _RUN_FIELDS or row["version"] != RUN_RECORD_VERSION
            or row["tier"] not in TIERS or row["claim"] not in CLAIMS or row["status"] not in ("complete", "incomplete")
            or (row["tier"] == "dev") != (row["claim"] == "development_observation")
            or row["tier"] == "regression" and row["claim"] != "observed_regression"
            or not isinstance(row["report_sha256"], str) or _SHA.fullmatch(row["report_sha256"]) is None
            or not isinstance(row["accepted_commit"], str) or formal._COMMIT.fullmatch(row["accepted_commit"]) is None
            or not isinstance(row["slot"], str) or _SLOT.fullmatch(row["slot"]) is None
            or not isinstance(row["recorded_at"], str) or _TIMESTAMP.fullmatch(row["recorded_at"]) is None
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
    if entry.get("annex") is not None:
        annex_expectations(entry, panel)
        freeze_meta["annex_sha256"] = entry["annex"]["sha256"]
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

def settings(route: dict, input_count: int, max_request_bytes: int = evaluator.MAX_REQUEST_BYTES) -> dict:
    base = evaluator.settings(input_count, max_request_bytes)
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


def data_boundary(version: str) -> dict:
    value = {"source": "synthetic_learningops_only", "wire": "individual_question_and_unchanged_runtime_only",
             "evaluator_metadata_on_wire": False, "raw_completion_or_reasoning_persisted": False,
             "observations": "closed clarification kind and choice count per clarify action; no text",
             "quality_claim": "tier_and_index_derived_never_promotion"}
    if version == PACKET_V2:
        value.update(validated_action_persisted=True, observations=(
            "closed clarification kind and choice count per clarify action; the runtime-validated typed "
            "action as closed canonical JSON; no raw completion, reasoning or presentation text"))
    elif version != PACKET_V1:
        raise assets.P3Error("invalid_manifest")
    return value


def command_template(accepted_commit: str) -> list[str]:
    return [".venv/bin/python", "tools/evaluate.py", "--live",
            "--packet", "<EXACT_PACKET>", "--authorization", "<EXACT_AUTHORIZATION_ENVELOPE>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", accepted_commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>",
            "--gateway-retries", ROUTE_POLICY["retries"], "--gateway-fallback", ROUTE_POLICY["fallback"],
            "--gateway-cache", ROUTE_POLICY["cache"], "--output-dir", "<BOUND_RUN_SLOT>"]


def _read_archived(path: Path) -> dict:
    """A recorded report read through its own reader: evaluation v1/v2 or the P3.5 formal reader."""
    raw = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    version = raw.get("report_version")
    if version in REPORT_VERSIONS.values():
        return read_report(path)
    if version == formal.REPORT_VERSION:
        return formal.read_report(path)
    raise assets.P3Error("invalid_asset")


def _baseline_projection(path: Path) -> dict:
    """Per-input correctness of a prior report of the same panel; read through its own reader."""
    report = _read_archived(path)
    if report["status"] != "complete":
        raise assets.P3Error("invalid_asset")
    rows = [{key: result[key] for key in ("case_id", "family_id", "outcome", "actual_action", "checked_wrong")}
            | {"correct": score["correct"]}
            for result, score in zip(report["results"], report["summary"]["per_input"])]
    families = {key: value["family_all_variants_correct"] for key, value in report["summary"]["per_family"].items()}
    return {"reference": _reference(path), "sha256": _report_digest(path), "report_version": report["report_version"],
            "inputs": rows, "family_correct": families}


def _unassessed(result: dict) -> bool:
    return (result["status"] != "completed" or result["outcome"] in ("operational_failure", "not_run")
            or result.get("operational_error") is not None or result.get("runner_error_code") is not None)


def _comparison(baseline: dict, results: list[dict], scored: dict) -> dict:
    rows, counts, action_changes, outcome_changes = [], dict.fromkeys(_COMPARISON, 0), [], []
    if [row["case_id"] for row in baseline["inputs"]] != [row["case_id"] for row in results]:
        raise assets.P3Error("invalid_scoring")
    for old, result, current in zip(baseline["inputs"], results, scored["per_input"]):
        unassessed = _unassessed(result)
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


def _run_id(candidate_id: str, panel_id: str, route_id: str, source_sha: str, repetition: int | None = None) -> str:
    base = f"{panel_id}--{route_id}--{candidate_id}--{source_sha[:12]}"
    return base if repetition is None else f"{base}--r{repetition}"


def _repetition(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_REPETITION:
        raise assets.P3Error("invalid_manifest")
    return value


def _packet_contract(packet: dict) -> None:
    """Archived structural validation; never consults registries, credentials or the checkout."""
    version = packet.get("version") if isinstance(packet, dict) else None
    if version not in _PACKET_FIELDS:
        raise assets.P3Error("invalid_manifest")
    assets.object_fields(packet, _PACKET_FIELDS[version])
    repetition = _repetition(packet["repetition"]) if version == PACKET_V2 else None
    source = packet["source_identity"]
    if (packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != PURPOSE or packet["tier"] not in TIERS or packet["claim"] not in CLAIMS
            or packet["evidence_class"] != packet["claim"] or packet["promotion_eligible"] is not False
            or (packet["tier"] == "dev") != (packet["claim"] == "development_observation")
            or packet["tier"] == "regression" and packet["claim"] != "observed_regression"
            or not isinstance(packet["accepted_commit"], str) or not formal._COMMIT.fullmatch(packet["accepted_commit"])
            or not isinstance(source, dict) or source.get("git_commit") != packet["accepted_commit"]
            or source.get("branch") != "dev" or source.get("worktree_dirty") is not False
            or not isinstance(source.get("files_sha256"), dict)
            or packet["observation_fields"] != list(OBSERVATIONS[version])
            or packet["gateway_policy"] != smoke.policy_attestation(ROUTE_POLICY, required=True)
            or packet["transport_security"] not in _TRANSPORT or packet["upstream_inference_attempts"] is not None
            or packet["data_boundary"] != data_boundary(version)
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
    panel_fields = {"panel_id", "tier", "authoring", "assets", "allocation_policy", "intake_sha256", "freeze_sha256",
                    "owner_review_reference", "input_count"}
    panel = assets.object_fields(packet["panel"], panel_fields | (
        {"annex_sha256"} if isinstance(packet["panel"], dict) and "annex_sha256" in packet["panel"] else set()))
    if "annex_sha256" in panel and (panel["tier"] != "dev" or not isinstance(panel["annex_sha256"], str)):
        raise assets.P3Error("invalid_manifest")
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
    for key in ("freeze_sha256", "intake_sha256", "annex_sha256"):
        if panel.get(key) is not None:
            _hash(panel[key])
    if (panel["allocation_policy"] is not None) != (panel["intake_sha256"] is not None):
        raise assets.P3Error("invalid_manifest")
    route = assets.object_fields(packet["route"], _ROUTE_FIELDS)
    cap = packet["settings"].get("max_request_bytes") if isinstance(packet["settings"], dict) else None
    if (route["provider"] not in PROVIDERS or route["transport_security"] != packet["transport_security"]
            or type(cap) is not int or cap not in evaluator.REQUEST_CAPS
            or not _same(packet["settings"], settings(route, len(packet["inputs"]), cap))):
        raise assets.P3Error("invalid_manifest")
    if packet["run_id"] != _run_id(candidate["candidate_id"], panel["panel_id"], route["route_id"],
                                   assets.digest(source), repetition):
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
        if (baseline["report_version"] not in (*REPORT_VERSIONS.values(), formal.REPORT_VERSION)
                or [row.get("case_id") for row in baseline["inputs"]] != packet["order"]
                or any(set(row) != {"case_id", "family_id", "outcome", "actual_action", "checked_wrong", "correct"}
                       or type(row["correct"]) is not bool for row in baseline["inputs"])
                or not isinstance(baseline["family_correct"], dict)):
            raise assets.P3Error("invalid_manifest")


def build_packet(database: Path, *, candidate_id: str, panel_id: str, route_id: str, accepted_commit: str,
                 gateway_policies: dict, baseline_path: Path | None = None,
                 panels_path: Path | None = None, routes_path: Path | None = None,
                 runs_path: Path | None = None, candidates_index: Path | None = None,
                 repetition: int = 1) -> tuple[dict, assets.Panel]:
    version = PACKET_VERSION
    if (gateway_policies != ROUTE_POLICY or type(repetition) is not int or not 1 <= repetition <= MAX_REPETITION
            or version == PACKET_V1 and repetition != 1):
        raise assets.P3Error("invalid_configuration")
    try:
        checked = registry.check(candidates_index)
        candidate = registry.current(candidates_index)
    except registry.RegistryError:
        raise assets.P3Error("source_identity_failure") from None
    if checked["candidate_id"] != candidate_id:
        raise assets.P3Error("source_identity_failure")
    # A run is attributed to its candidate's behaviour identity, so the runtime files must be the registered ones
    # too (ADR #164, docs/behavior-identity.md).
    if checked["runtime_files_changed"]:
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
    limits = settings(route, len(inputs), candidate["limits"]["request"])
    packet = {
        "version": version, "state": "prepared_not_authorized", "purpose": PURPOSE,
        "tier": entry["tier"], "claim": claim, "evidence_class": claim, "promotion_eligible": False,
        "run_id": _run_id(candidate_id, panel_id, route_id, assets.digest(source),
                          repetition if version == PACKET_V2 else None),
        "accepted_commit": accepted_commit,
        "candidate": {"candidate_id": candidate_id, "candidate_sha256": candidate["candidate_sha256"],
                      "semantic_identity_sha256": candidate["semantic_identity_sha256"]},
        "panel": {"panel_id": panel_id, "tier": entry["tier"], "authoring": entry["authoring"],
                  "assets": dict(entry["assets"]), "allocation_policy": entry["allocation_policy"],
                  "intake_sha256": freeze_meta["intake_sha256"], "freeze_sha256": freeze_meta["freeze_sha256"],
                  "owner_review_reference": freeze_meta["owner_review_reference"], "input_count": len(inputs),
                  **({"annex_sha256": freeze_meta["annex_sha256"]} if "annex_sha256" in freeze_meta else {})},
        "route": dict(route),
        "baseline": _baseline_projection(baseline_path) if baseline_path is not None else None,
        "observation_fields": list(OBSERVATIONS[version]), "source_identity": source,
        "database_sha256": smoke._fixture_identity(database), "inputs": inputs,
        "order": [case.case_id for case in panel.cases], "run_index_sha256": run_index_sha,
        "settings": limits, "settings_sha256": assets.digest(limits),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(ROUTE_POLICY, required=True),
        "transport_security": route["transport_security"], "data_boundary": data_boundary(version),
        "upstream_inference_attempts": None, "command_template": command_template(accepted_commit),
    }
    if version == PACKET_V2:
        packet["repetition"] = repetition
    _packet_contract(packet)
    return packet, panel


def validate_packet(path: Path, database: Path, *, accepted_commit: str, **registries) -> tuple[dict, assets.Panel]:
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise assets.P3Error("accepted_commit_required")
    baseline_path = None if packet["baseline"] is None else _location(packet["baseline"]["reference"])
    # The rebuild is at the current packet version, so an archived older packet drifts before live.
    current, panel = build_packet(database, candidate_id=packet["candidate"]["candidate_id"],
                                  panel_id=packet["panel"]["panel_id"], route_id=packet["route"]["route_id"],
                                  accepted_commit=accepted_commit, gateway_policies=dict(ROUTE_POLICY),
                                  baseline_path=baseline_path, repetition=packet.get("repetition", 1), **registries)
    if not _same(current, packet):
        raise assets.P3Error("manifest_drift")
    return packet, panel


def prepare(database: Path, output_dir: Path, **options) -> dict:
    packet, _ = build_packet(database, **options)
    artifacts = smoke._Artifacts(output_dir, packet)
    report = {"version": packet["version"], "state": "incomplete", "packet_sha256": evaluator._pin(
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
        "manifest_version": MANIFEST_VERSIONS[packet["version"]], "packet_sha256": packet_sha,
        "authorization_sha256": authorization_sha,
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
    report.update(report_version=REPORT_VERSIONS[packet["version"]], runtime_invocations=0, transport_security=None,
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
        row.update(dict.fromkeys(OBSERVATIONS[packet["version"]]))
    return report


def _summarize(report: dict) -> None:
    value = scoring.summarize(report["results"], report["results"], panel_kind="development",
                              run_status=report["status"])
    diagnostics = value.pop("promotion")["gates"]
    observations = _observations(report["results"])
    if report["report_version"] == REPORT_VERSIONS[PACKET_V2]:
        observations["validated_actions"] = sum(row["validated_action"] is not None for row in report["results"])
    value.update(panel_kind="evaluation", tier=report["tier"], claim=report["claim"],
                 evidence_class=report["claim"], promotion_eligible=False, diagnostic_gates=diagnostics,
                 observations=observations,
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


def _action_values(value: object, depth: int) -> bool:
    if depth > _ACTION_DEPTH:
        return False
    if isinstance(value, dict):
        return all(isinstance(key, str) and len(key) <= _ACTION_STRING and _action_values(item, depth + 1)
                   for key, item in value.items())
    if isinstance(value, list):
        return all(_action_values(item, depth + 1) for item in value)
    if isinstance(value, str):
        return len(value) <= _ACTION_STRING
    return value is None or type(value) in (int, bool)


def _action_shape(action: object) -> bool:
    """Closed structural shape of a persisted validated action; semantics stay with the runtime validators."""
    if not isinstance(action, dict) or not _action_values(action, 1):
        return False
    outcome = action.get("outcome")
    if outcome == "declined":
        return action == {"outcome": "declined"}
    if outcome == "request":
        # An Overview proposal may carry the one stated count assumption (v13, docs/count-assumption.md) or one
        # typed count reading (v16, docs/count-reading-v16.md), and a Compare proposal one typed orientation
        # (v15, docs/compare-orientation-v15.md).
        base = {"outcome", "recipe_id", "recipe_version", "request"}
        return (set(action) in (base, base | {"assumption"}, base | {"orientation"}, base | {"count_request"})
                and isinstance(action["recipe_id"], str) and action["recipe_id"] in _ACTION_RECIPES
                and action["recipe_version"] == "0.1" and isinstance(action["request"], dict)
                and ("assumption" not in action
                     or action["recipe_id"] == "overview" and action["assumption"] == ASSUMPTION)
                and ("orientation" not in action
                     or action["recipe_id"] == "compare" and action["orientation"] in ORIENTATIONS)
                and ("count_request" not in action
                     or action["recipe_id"] == "overview" and action["count_request"] in COUNT_REQUESTS))
    if outcome != "clarify" or set(action) != {"outcome", "clarification"}:
        return False
    clarification = action["clarification"]
    if (not isinstance(clarification, dict) or set(clarification) != {"kind", "choices"}
            or not isinstance(clarification["kind"], str) or clarification["kind"] not in KINDS
            or not isinstance(clarification["choices"], list)
            or not 2 <= len(clarification["choices"]) <= MAX_CHOICES):
        return False
    return all(isinstance(choice, dict) and set(choice) == {"id", "semantic_value"}
               and isinstance(choice["id"], str) and _CHOICE_ID.fullmatch(choice["id"]) is not None
               and isinstance(choice["semantic_value"], dict) for choice in clarification["choices"])


def _action_text(action: object) -> str | None:
    """Canonical JSON of a closed action, or None when it does not fit the persisted shape."""
    if not _action_shape(action):
        return None
    try:
        text = model.canonical_json(action)
    except (TypeError, ValueError):
        return None
    return text if len(text.encode("utf-8")) <= MAX_ACTION_BYTES else None


def _validated_action(result) -> str | None:
    """The action that passed the runtime validators, in the grader's priority order; never raw text."""
    proposal = getattr(result, "proposal", None)
    clarification = getattr(result, "clarification", None)
    source = getattr(result, "source_proposal", None)
    error = getattr(result, "error", None)
    source_clarification = getattr(result, "source_clarification", None)
    try:
        if proposal is not None and source_clarification is not None:
            # A server answer to a model count_basis clarification persists the model's own action (ADR #158).
            action = {"outcome": "clarify", "clarification": source_clarification.to_dict()}
        elif proposal is not None:
            action = proposal.to_dict()
        elif clarification is not None and source is not None:
            # A server-built clarification persists the model's own action, so replay rebuilds it.
            action = source.to_dict()
        elif source is not None and error is not None and error.code == "model_declined":
            # So does a server decline of a named unavailable count (docs/count-reading-v16.md).
            action = source.to_dict()
        elif clarification is not None:
            action = {"outcome": "clarify", "clarification": clarification.to_dict()}
        elif error is not None and error.code == "model_declined":
            action = {"outcome": "declined"}
        else:
            return None
    except (AttributeError, TypeError, ValueError, KernelError):
        return None
    return _action_text(action)


_ACTION_OUTCOMES = {"request": "answer", "clarify": "clarify", "declined": "decline"}


def _check_action(row: dict, stop_reason: str | None = None) -> bool:
    """Structural readback of one persisted action; True when the evidence checks were relaxed."""
    text = row["validated_action"]
    if text is None:
        return False
    if (not isinstance(text, str) or len(text.encode("utf-8")) > MAX_ACTION_BYTES
            or row["status"] != "completed"):
        raise assets.P3Error("invalid_asset")
    try:
        action = json.loads(text)
    except (ValueError, RecursionError):
        raise assets.P3Error("invalid_asset") from None
    # An unresolved Compare orientation is the model's action behind a server-built roles clarification.
    derived = (isinstance(action, dict) and action.get("outcome") == "request"
               and action.get("orientation") == "unresolved")
    # A named unavailable count reading is the model's action behind a server decline (v16).
    declined = (isinstance(action, dict) and action.get("outcome") == "request"
                and action.get("count_request") in UNAVAILABLE_COUNTS)
    # A model count_basis clarification is the model's action behind a server answer from v19 on (ADR #158);
    # before v19 it was a real clarification row. The recorded actual action decides which, never the action alone.
    answered = _count_basis_clarification(action) and row["actual_action"] == "answer"
    expected = "clarify" if derived else "decline" if declined else "answer" if answered else None
    if (_action_text(action) != text
            or (expected or _ACTION_OUTCOMES[action["outcome"]]) != row["actual_action"]):
        raise assets.P3Error("invalid_asset")
    if action["outcome"] == "clarify" and not answered and (
            action["clarification"]["kind"] != row["clarification_kind"]
            or len(action["clarification"]["choices"]) != row["clarification_choice_count"]):
        raise assets.P3Error("invalid_asset")
    if derived and (row["clarification_kind"], row["clarification_choice_count"]) != ("comparison_roles", 2):
        raise assets.P3Error("invalid_asset")
    if answered and (row["clarification_kind"], row["clarification_choice_count"]) != (None, None):
        raise assets.P3Error("invalid_asset")
    evidence = row["evidence"]
    if evidence is None and stop_reason is not None and row["runner_error_code"] == stop_reason:
        # The run stopped on this row before its evidence was projected; the stop is the evidence,
        # and such a row is neither assessed nor replayable.
        return True
    evidence = evidence if isinstance(evidence, dict) else {}
    stages = evidence.get("stages") if isinstance(evidence.get("stages"), dict) else {}
    if action["outcome"] == "declined" or declined:
        if evidence.get("error_code") != "model_declined":
            raise assets.P3Error("invalid_asset")
        return False
    if stages.get("request_validation") != "passed":
        raise assets.P3Error("invalid_asset")
    return False


@dataclass(frozen=True)
class _Route:
    provider: str
    model: str
    region: str | None
    call_timeout_seconds: float
    transport_security: str
    packet_version: str = PACKET_V1

    @property
    def expected_model(self):
        return GEMMA_12B if self.provider == "litellm" and self.model == GEMMA_12B.model_alias else None

    @property
    def requested_profile(self):
        return self.model if self.provider == "bedrock_converse" else None


def _route(packet: dict) -> _Route:
    route = packet["route"]
    return _Route(route["provider"], route["model"], route["region"], float(route["call_timeout_seconds"]),
                  route["transport_security"], packet["version"])


class _LiveEvidence(live._LiveEvidence):
    summarize = staticmethod(_summarize)
    observation_fields = OBSERVATION_FIELDS

    def __init__(self, route: _Route | None = None):
        if not isinstance(route, _Route) or route.packet_version not in OBSERVATIONS:
            raise assets.P3Error("invalid_configuration")
        super().__init__(route.expected_model, requested_profile=route.requested_profile)
        self.route = route
        self.maximum = assets.MAX_INPUTS
        self.observation_fields = OBSERVATIONS[route.packet_version]
        self._admitted = None

    def invocation_client(self, client):
        self._admitted = client
        return super().invocation_client(client)

    def _exportable(self, text: str) -> bool:
        """The report's own leak check, applied before the value lands; without the admitted client, nothing lands."""
        if self._admitted is None:
            return False
        try:
            evaluator._safe({"validated_action": text}, self._admitted)
        except assets.P3Error:
            return False
        return True

    def observe_result(self, result) -> dict:
        observed = dict.fromkeys(self.observation_fields)
        clarification = getattr(result, "clarification", None)
        if clarification is not None:
            observed.update(clarification_kind=clarification.kind,
                            clarification_choice_count=len(clarification.choices))
        if "validated_action" in observed:
            text = _validated_action(result)
            observed["validated_action"] = text if text is not None and self._exportable(text) else None
        return observed

    def check_report(self, report):
        super().check_report(report)
        relaxed = 0
        for row in report["results"]:
            _check_observation(row)
            if "validated_action" in self.observation_fields:
                relaxed += _check_action(row, report["stop_reason"])
        if relaxed > 1:
            raise assets.P3Error("invalid_asset")


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


def _counts(report: dict, summary: dict, panels_path: Path | None = None) -> tuple[int, int]:
    """Correct inputs and fully correct families; on an annex panel, a row counts only if the annex agrees."""
    frozen = [bool(item["correct"]) for item in summary["per_input"]]
    expectations = _panel_annex(report.get("panel"), panels_path)
    if expectations is None:
        return sum(frozen), sum(v["family_all_variants_correct"] for v in summary["per_family"].values())
    verdicts = [annexed(row, correct, expectations) == "correct" for row, correct in zip(report["results"], frozen)]
    families: dict[str, bool] = {}
    for row, verdict in zip(report["results"], verdicts):
        families[row["family_id"]] = families.get(row["family_id"], True) and verdict
    return sum(verdicts), sum(families.values())


def record(report_path: Path, *, runs_path: Path | None = None, now: str | None = None,
           panels_path: Path | None = None) -> dict:
    """Append one run to the append-only index after offline readback; refuses a duplicate run id."""
    report = read_report(report_path)
    runs_file = RUNS if runs_path is None else runs_path
    runs = load_runs(runs_file)
    if any(run["run_id"] == report["run_id"] for run in runs):
        raise assets.P3Error("artifact_conflict")
    # The claim must still be derivable from the index the record joins: a second
    # fresh observation of the same (panel, route), however prepared, is refused.
    if derive_claim(report["tier"], report["panel"]["panel_id"], report["route"]["route_id"], runs) != report["claim"]:
        raise assets.P3Error("artifact_conflict")
    summary = report["summary"]
    correct, families_correct = _counts(report, summary, panels_path)
    row = {"version": RUN_RECORD_VERSION, "run_id": report["run_id"],
           "recorded_at": now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "candidate_id": report["candidate"]["candidate_id"], "panel_id": report["panel"]["panel_id"],
           "tier": report["tier"], "route_id": report["route"]["route_id"], "claim": report["claim"],
           "report_sha256": _report_digest(report_path), "slot": report["run_slot"],
           "accepted_commit": report["preparation"]["accepted_commit"],
           "grant": report["owner_authorization_reference"], "status": report["status"],
           "inputs": summary["input_count"], "correct": correct,
           "families": len(summary["per_family"]), "families_correct": families_correct,
           "outcomes": summary["outcomes"]}
    _run_record(row)
    runs_file.parent.mkdir(parents=True, exist_ok=True)
    with runs_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


# --------------------------------------------------------------------------- replay and aggregate

REPLAY_REFUSALS = ("report_version", "candidate_bytes", "panel_assets", "inputs", "database")
_REPLAY_BASE = "https://replay.invalid/v1"
_REPLAY_TOKEN = "replay-synthetic-token"
_REPLAY_CLASSES = ("replayed_same", "replayed_changed", "not_replayable")
_AGGREGATE_CLASSES = ("stable_correct", "stable_wrong", "flaky", "insufficient")
GATE_REFUSALS = ("same_bytes", "not_dev_panel", "no_baseline_runs", "no_sentinel", "sentinel_incomplete",
                 "no_candidate_run", "multiple_candidate_runs", "candidate_identity", "inputs_differ",
                 "index_mismatch")
_GATE_CLASSES = ("fixed", "broke", "unchanged_correct", "unchanged_wrong", "excluded", "unassessed")
# Errors raised on the model's own content after the envelope was accepted: the model's answer, graded wrong.
_GATE_MODEL_ERRORS = ("invalid_json", "invalid_request", "constraint_conflict")


class ReplayRefused(assets.P3Error):
    """Recorded actions are not representative of the current source: the existing safe code, one closed reason."""

    def __init__(self, reason: str):
        super().__init__("manifest_drift")
        self.reason = reason if reason in REPLAY_REFUSALS else "unknown"


class GateRefused(assets.P3Error):
    """A candidate cannot be gated against its baseline as indexed: the existing safe code, one closed reason."""

    def __init__(self, reason: str):
        super().__init__("invalid_manifest")
        self.reason = reason if reason in GATE_REFUSALS else "unknown"


def _reference(path: Path) -> str:
    return path.absolute().relative_to(ROOT).as_posix() if path.absolute().is_relative_to(ROOT) else str(path)


def _write_new(path: Path, value: dict) -> None:
    smoke._no_symlinks(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise assets.P3Error("artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io") from None


def _replayable(row: dict) -> bool:
    evidence = row["evidence"] if isinstance(row["evidence"], dict) else {}
    stages = evidence.get("stages") if isinstance(evidence.get("stages"), dict) else {}
    return (row["status"] == "completed" and row["validated_action"] is not None
            and row["runner_error_code"] is None and stages.get("transport") == "passed")


def _replay_client(action_text: str, calls: list) -> GatewayClient:
    """A mock transport returning exactly the recorded action; no credentials, environment or network."""
    def respond(request):
        calls.append(1)
        return httpx.Response(200, json={"model": MODEL, "choices": [{
            "index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": action_text}}]})

    return GatewayClient(GatewayConfig(_REPLAY_BASE, _REPLAY_TOKEN, MODEL), transport=httpx.MockTransport(respond))


@dataclass(frozen=True)
class _ReplayPlan:
    report_path: Path
    report: dict
    database: Path
    database_sha: str
    output_path: Path
    checked: dict
    current: dict
    panel: object
    entries: list
    panels_path: Path | None = None


async def replay(report_path: Path, database: Path, output_path: Path, *, candidates_index: Path | None = None,
                 panels_path: Path | None = None) -> dict:
    """Zero-call offline replay: recorded validated actions through the current kernel and grader."""
    return await _replay_execute(_replay_plan(report_path, database, output_path, candidates_index=candidates_index,
                                              panels_path=panels_path))


def _replay_plan(report_path: Path, database: Path, output_path: Path, *, candidates_index: Path | None = None,
                 panels_path: Path | None = None) -> _ReplayPlan:
    """Every refusal is decided here, synchronously, before any replay work starts."""
    report = read_report(report_path)
    if report["report_version"] != REPORT_VERSIONS[PACKET_V2]:
        raise ReplayRefused("report_version")
    packet = assets.read_asset(report_path.parent / "packet.json")
    try:
        checked = registry.check(candidates_index)
        current = registry.current(candidates_index)
    except registry.RegistryError:
        raise assets.P3Error("source_identity_failure") from None
    if checked["candidate_id"] != current["candidate_id"]:
        raise assets.P3Error("source_identity_failure")
    if current["candidate_sha256"] != packet["candidate"]["candidate_sha256"]:
        raise ReplayRefused("candidate_bytes")
    entry, panel, _ = load_panel_entry(packet["panel"]["panel_id"], database, panels_path=panels_path)
    if entry["assets"] != packet["panel"]["assets"]:
        raise ReplayRefused("panel_assets")
    entries = evaluator._panel_entries(panel)
    if (not _same(panel.inputs(), packet["inputs"]) or not _same([item.metadata for item in entries], packet["inputs"])
            or len(entries) != len(report["results"])):
        raise ReplayRefused("inputs")
    database_sha = smoke._fixture_identity(database)
    if database_sha != packet["database_sha256"]:
        raise ReplayRefused("database")
    if output_path.exists() or output_path.is_symlink():
        raise assets.P3Error("artifact_conflict")
    return _ReplayPlan(report_path, report, database, database_sha, output_path, checked, current, panel, entries,
                       panels_path)


async def _replay_execute(plan: _ReplayPlan) -> dict:
    report_path, report, database, database_sha = plan.report_path, plan.report, plan.database, plan.database_sha
    checked, current, panel, entries = plan.checked, plan.current, plan.panel, plan.entries
    calls, classes, replayed = [], [], deepcopy(report["results"])
    actions = [None] * len(report["results"])
    for position, (row, item, target) in enumerate(zip(report["results"], entries, replayed)):
        if not _replayable(row):
            classes.append("not_replayable")
            continue
        result = await recipe_model.interpret_recipe_and_execute(
            item.case.question, database, _replay_client(row["validated_action"], calls))
        graded = p3_grading.grade(result, item.oracle)
        actions[position] = _validated_action(result)
        classes.append("replayed_same" if all(_same(graded[key], row[key]) for key in graded) else "replayed_changed")
        target.update(graded)
    scored = scoring.summarize(replayed, replayed, panel_kind="development", run_status=report["status"])
    archived = report["summary"]["per_input"]
    # On an annex panel a row is replayed_same only if its annex verdict is unchanged too (docs/count-assumption.md).
    expectations = _panel_annex(report.get("panel"), plan.panels_path)
    verdicts = [None] * len(classes)
    if expectations is not None:
        for position, (row, target, old, new) in enumerate(zip(report["results"], replayed, archived,
                                                               scored["per_input"])):
            if classes[position] == "not_replayable":
                continue
            # Each verdict reads its own row: the replayed one carries the replayed actual action (#161).
            verdicts[position] = (annexed(row, bool(old["correct"]), expectations),
                                  annexed({**target, "validated_action": actions[position]}, bool(new["correct"]),
                                          expectations))
            if classes[position] == "replayed_same" and verdicts[position][0] != verdicts[position][1]:
                classes[position] = "replayed_changed"
    rows = []
    for row, target, kind, old, new, verdict in zip(report["results"], replayed, classes, archived,
                                                    scored["per_input"], verdicts):
        entry = {"case_id": row["case_id"], "class": kind,
                 "archived": {"outcome": row["outcome"], "actual_action": row["actual_action"],
                              "correct": old["correct"]},
                 "replayed": None if kind == "not_replayable" else {
                     "outcome": target["outcome"], "actual_action": target["actual_action"],
                     "correct": new["correct"]}}
        if expectations is not None:
            entry["annex"] = None if verdict is None else {"archived": verdict[0], "replayed": verdict[1]}
        rows.append(entry)
    value = {
        "version": REPLAY_VERSION, "claim": "offline_replay_observation", "promotion_eligible": False,
        "live_model_attempts": 0, "mock_transport_calls": len(calls),
        "counts": {kind: classes.count(kind) for kind in _REPLAY_CLASSES}, "rows": rows,
        "source": {"reference": _reference(report_path), "sha256": _report_digest(report_path),
                   "run_id": report["run_id"], "report_version": report["report_version"],
                   "candidate": report["candidate"]},
        "replay_identity": {"candidate_id": checked["candidate_id"], "candidate_sha256": current["candidate_sha256"],
                            "runtime_files_changed": checked["runtime_files_changed"],
                            "source_identity": evaluator._source_identity(panel, None),
                            "evaluator_version": p3_grading.VERSION, "database_sha256": database_sha},
        "archived_correct": sum(item["correct"] for item in archived),
        "replayed_correct": sum(item["correct"] for item in scored["per_input"]),
        "comparison": (_comparison(_baseline_projection(report_path), replayed, scored)
                       if report["status"] == "complete" else None),
    }
    if expectations is not None:
        value["annex_sha256"] = report["panel"]["annex_sha256"]
    _write_new(plan.output_path, value)
    return value


def _matching_runs(panel_id: str, route_id: str, target: str, runs: list[dict], identities: dict,
                   candidates_index: Path | None, identity) -> list[dict]:
    selected = []
    for run in runs:
        if run["panel_id"] != panel_id or run["route_id"] != route_id:
            continue
        if run["candidate_id"] not in identities:
            identities[run["candidate_id"]] = identity(registry.load_entry(run["candidate_id"], candidates_index))
        if identities[run["candidate_id"]] == target:
            selected.append(run)
    return selected


def _same_bytes_runs(panel_id: str, route_id: str, target: str, runs: list[dict], identities: dict,
                     candidates_index: Path | None) -> list[dict]:
    """Indexed runs of the panel and route whose candidate's model-input identity (``candidate_sha256``) equals
    ``target``, in index order. The diagnostics select by it."""
    return _matching_runs(panel_id, route_id, target, runs, identities, candidates_index,
                          lambda entry: entry["candidate_sha256"])


def _same_behavior_runs(panel_id: str, route_id: str, target: str, runs: list[dict], identities: dict,
                        candidates_index: Path | None) -> list[dict]:
    """Indexed runs of the panel and route whose candidate's behaviour identity equals ``target``, in index order.
    The gate and the aggregate select by it (ADR #164)."""
    return _matching_runs(panel_id, route_id, target, runs, identities, candidates_index, registry.behavior_identity)


def _archived_reports(selected: list[dict]) -> list[dict]:
    """Each indexed run's report, read through its own reader and matched to its index digest and run id."""
    reports = []
    for run in selected:
        path = _location(run["slot"] + "/report.json")
        if _report_digest(path) != run["report_sha256"]:
            raise assets.P3Error("manifest_drift")
        report = _read_archived(path)
        if report.get("run_id", run["run_id"]) != run["run_id"]:
            raise assets.P3Error("manifest_drift")
        reports.append(report)
    return reports


def _input_classes(reports: list[dict], expectations: dict | None = None) -> list[dict]:
    order = [row["case_id"] for row in reports[0]["results"]]
    if any([row["case_id"] for row in report["results"]] != order for report in reports):
        raise assets.P3Error("invalid_scoring")
    inputs = []
    for index, case_id in enumerate(order):
        rows = [report["results"][index] for report in reports]
        scores = [report["summary"]["per_input"][index]["correct"] for report in reports]
        assessed = [not _unassessed(row) for row in rows]
        if expectations is not None:
            # On an annex panel a row counts as its annex verdict; an uncheckable assumption is unassessed.
            verdicts = [annexed(row, bool(score), expectations) if seen else None
                        for row, score, seen in zip(rows, scores, assessed)]
            assessed = [verdict in ("correct", "wrong") for verdict in verdicts]
            scores = [verdict == "correct" for verdict in verdicts]
        correct = sum(bool(score) for score, seen in zip(scores, assessed) if seen)
        actions = [row.get("validated_action") for row in rows if row.get("validated_action") is not None]
        count = sum(assessed)
        kind = ("insufficient" if count < 2 else "stable_correct" if correct == count
                else "stable_wrong" if correct == 0 else "flaky")
        inputs.append({
            "case_id": case_id, "family_id": rows[0]["family_id"], "observations": len(rows), "assessed": count,
            "correct": correct, "unassessed": len(rows) - count,
            "outcomes": _tally(row["outcome"] for row in rows),
            "actions": _tally(row["actual_action"] for row in rows),
            "distinct_signatures": len({row["actual_signature"] for row in rows
                                        if row.get("actual_signature") is not None}),
            "validated_actions": len(actions), "distinct_validated_actions": len(set(actions)), "class": kind})
    return inputs


def _shared_annex(reports: list[dict], panels_path: Path | None = None) -> dict | None:
    """The annex every report pins, or none; reports that disagree about their annex cannot be pooled."""
    pinned = {(report.get("panel") or {}).get("annex_sha256") for report in reports}
    if len(pinned) != 1:
        raise assets.P3Error("invalid_scoring")
    return _panel_annex(reports[0].get("panel"), panels_path)


def aggregate(panel_id: str, route_id: str, candidate_id: str, *, runs_path: Path | None = None,
              candidates_index: Path | None = None, panels_path: Path | None = None) -> dict:
    """Every indexed run of the panel and route with the same behaviour identity (ADR #164); selection by identity
    only."""
    entry = registry.load_entry(candidate_id, candidates_index)
    target = registry.behavior_identity(entry)
    runs_file = RUNS if runs_path is None else runs_path
    included = _same_behavior_runs(panel_id, route_id, target, load_runs(runs_file), {}, candidates_index)
    if not included:
        raise assets.P3Error("invalid_manifest")
    reports = _archived_reports(included)
    inputs = _input_classes(reports, _shared_annex(reports, panels_path))
    return {
        "version": AGGREGATE_VERSION, "promotion_eligible": False, "panel_id": panel_id, "route_id": route_id,
        "candidate": {"candidate_id": candidate_id, "candidate_sha256": entry["candidate_sha256"],
                      "behavior_sha256": target},
        "run_index_sha256": evaluator._pin(runs_file)["sha256"],
        "runs": [{"run_id": run["run_id"], "candidate_id": run["candidate_id"],
                  "report_sha256": run["report_sha256"], "report_version": report["report_version"],
                  "accepted_commit": run["accepted_commit"], "evaluator_version": report.get("evaluator_version"),
                  "status": report["status"],
                  "correct": _counts(report, report["summary"], panels_path)[0]}
                 for run, report in zip(included, reports)],
        "inputs": inputs,
        "class_counts": {kind: sum(row["class"] == kind for row in inputs) for kind in _AGGREGATE_CLASSES},
    }


def _tally(values) -> dict:
    counts = {}
    for value in values:
        key = "none" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _gate_view(report: dict) -> tuple:
    """Candidate bytes and inputs of an evaluation report; a formal archive carries neither."""
    if report["report_version"] not in REPORT_VERSIONS.values():
        return None, None
    return report["candidate"]["candidate_sha256"], (
        report["panel"]["panel_id"], report["panel"]["assets"], report["panel"].get("annex_sha256"),
        [(row["case_id"], row["question_sha256"]) for row in report["results"]])


def _gate_unassessed(result: dict) -> bool:
    """No usable model result. A graded row whose error was raised on the model's own content, such as
    invalid_json, is the model's answer; an envelope, gateway, transport, budget, kernel or source error is not."""
    error = result.get("operational_error")
    return (result["status"] != "completed" or result["outcome"] in ("operational_failure", "not_run")
            or result.get("runner_error_code") is not None
            or error is not None and error not in _GATE_MODEL_ERRORS)


def _gate_class(baseline: str, candidate: str, sentinel_assessed: bool) -> str:
    if candidate == "unassessed":
        return "unassessed"
    if baseline == "stable_correct":
        return "unchanged_correct" if candidate == "correct" else "broke"
    if baseline == "stable_wrong" and candidate == "correct":
        # A fix needs same-session evidence that the baseline still gets the input wrong.
        return "fixed" if sentinel_assessed else "excluded"
    if baseline == "stable_wrong":
        return "unchanged_wrong"
    return "excluded"


def _gate_verdict(counts: dict) -> str:
    return ("regression" if counts["broke"] else "inconclusive" if counts["unassessed"]
            else "passed" if counts["fixed"] else "no_fix")


def gate(candidate_id: str, baseline_id: str, route_id: str, reference: str, panel_ids: list[str], *,
         runs_path: Path | None = None, panels_path: Path | None = None,
         candidates_index: Path | None = None) -> dict:
    """The pre-registered acceptance rule (docs/candidate-gate.md): one candidate run against the
    measured classes of its baseline, with a sentinel under the same owner authorization. Offline."""
    if (not isinstance(reference, str) or GRANT.fullmatch(reference) is None or not panel_ids
            or len(set(panel_ids)) != len(panel_ids)):
        raise assets.P3Error("invalid_arguments")
    registered = load_panels(panels_path)
    if any(_entry(registered, "panels", panel_id, "panel_id")["tier"] != "dev" for panel_id in panel_ids):
        raise GateRefused("not_dev_panel")
    target_entry = registry.load_entry(candidate_id, candidates_index)
    base_entry = registry.load_entry(baseline_id, candidates_index)
    target, base = target_entry["candidate_sha256"], base_entry["candidate_sha256"]
    # Runs pool, and the candidate must differ, by behaviour identity (ADR #164); `same_bytes` keeps its name.
    target_behavior, base_behavior = registry.behavior_identity(target_entry), registry.behavior_identity(base_entry)
    if target_behavior == base_behavior:
        raise GateRefused("same_bytes")
    runs_file = RUNS if runs_path is None else runs_path
    runs = load_runs(runs_file)
    identities, behaviors, panels = {}, {}, []
    for panel_id in panel_ids:
        baseline = _same_behavior_runs(panel_id, route_id, base_behavior, runs, behaviors, candidates_index)
        if not baseline:
            raise GateRefused("no_baseline_runs")
        sentinels = [position for position, run in enumerate(baseline) if run["grant"] == reference]
        if not sentinels:
            raise GateRefused("no_sentinel")
        if all(baseline[position]["status"] != "complete" for position in sentinels):
            raise GateRefused("sentinel_incomplete")
        same_behavior = _same_behavior_runs(panel_id, route_id, target_behavior, runs, behaviors, candidates_index)
        candidates = [run for run in same_behavior if run["grant"] == reference]
        if not candidates:
            raise GateRefused("no_candidate_run")
        if len(candidates) > 1:
            raise GateRefused("multiple_candidate_runs")
        selected = [*baseline, *candidates]
        # Each report.json records only the model-input identity, so its check stays on candidate_sha256.
        for run in selected:
            if run["candidate_id"] not in identities:
                identities[run["candidate_id"]] = registry.load_entry(run["candidate_id"],
                                                                      candidates_index)["candidate_sha256"]
        reports = _archived_reports(selected)
        views = [_gate_view(report) for report in reports]
        if any(sha != identities[run["candidate_id"]] for run, (sha, _) in zip(selected, views)):
            raise GateRefused("candidate_identity")
        if any(inputs != views[-1][1] for _, inputs in views[:-1]):
            raise GateRefused("inputs_differ")
        if any((report["owner_authorization_reference"], report["panel"]["panel_id"], report["route"]["route_id"],
                report["status"]) != (run["grant"], panel_id, route_id, run["status"])
               for run, report in zip(selected, reports)):
            raise GateRefused("index_mismatch")
        report, inputs = reports[-1], []
        # The inputs check above makes every report pin the same annex, if any (docs/count-assumption.md).
        expectations = _panel_annex(report["panel"], panels_path)

        def assessed(archived: dict, position: int) -> bool:
            row = archived["results"][position]
            return not _unassessed(row) and (expectations is None or annexed(
                row, bool(archived["summary"]["per_input"][position]["correct"]), expectations) != "unassessed")

        for position, (row, score, measured) in enumerate(zip(report["results"], report["summary"]["per_input"],
                                                              _input_classes(reports[:-1], expectations))):
            observed = "unassessed" if _gate_unassessed(row) else "correct" if score["correct"] else "wrong"
            if expectations is not None and observed != "unassessed":
                observed = annexed(row, observed == "correct", expectations)
            seen = any(assessed(reports[sentinel], position) for sentinel in sentinels)
            inputs.append({"case_id": row["case_id"], "family_id": row["family_id"],
                           "baseline_class": measured["class"], "sentinel_assessed": seen, "candidate": observed,
                           "outcome": row["outcome"], "class": _gate_class(measured["class"], observed, seen)})
        counts = {kind: sum(item["class"] == kind for item in inputs) for kind in _GATE_CLASSES}
        panels.append({"panel_id": panel_id, "baseline_runs": [run["run_id"] for run in baseline],
                       "sentinel_runs": [baseline[position]["run_id"] for position in sentinels],
                       "candidate_run": candidates[0]["run_id"],
                       "recorded_at": {"sentinel_runs": [baseline[position]["recorded_at"] for position in sentinels],
                                       "candidate_run": candidates[0]["recorded_at"]},
                       "other_candidate_runs": [run["run_id"] for run in same_behavior if run["grant"] != reference],
                       "inputs": inputs, "counts": counts,
                       **{kind: [item["case_id"] for item in inputs if item["class"] == kind]
                          for kind in ("fixed", "broke", "excluded", "unassessed")},
                       "verdict": _gate_verdict(counts)})
    counts = {kind: sum(panel["counts"][kind] for panel in panels) for kind in _GATE_CLASSES}
    return {"version": GATE_VERSION, "promotion_eligible": False, "claim": "development_observation",
            "route_id": route_id, "owner_authorization_reference": reference,
            "candidate": {"candidate_id": candidate_id, "candidate_sha256": target, "behavior_sha256": target_behavior},
            "baseline": {"candidate_id": baseline_id, "candidate_sha256": base, "behavior_sha256": base_behavior},
            "run_index_sha256": evaluator._pin(runs_file)["sha256"],
            "panels": panels, "counts": counts, "verdict": _gate_verdict(counts)}


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--routing-upper-bound":
        from tools import routing_upper_bound
        return routing_upper_bound.main(argv[1:])
    if argv and argv[0] == "--reading-diagnostic":
        from tools import reading_diagnostic
        return reading_diagnostic.main(argv[1:])
    if argv and argv[0] == "--completion-diagnostic":
        from tools import p3_completion_diagnostic
        return p3_completion_diagnostic.main(argv[1:])
    if argv and argv[0] == "--completion-diagnostic-v2":
        from tools import p3_completion_diagnostic
        return p3_completion_diagnostic.main(argv[1:], profile=p3_completion_diagnostic.V2)
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report", "record", "replay", "aggregate", "gate"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "run-output-dir",
                 "baseline", "report-path"):
        parser.add_argument("--" + name, type=Path)
    for name in ("candidate", "baseline-candidate", "panel", "route", "accepted-commit",
                 "owner-authorization-reference"):
        parser.add_argument("--" + name)
    parser.add_argument("--panels", nargs="+", action="extend")
    parser.add_argument("--repetition", type=int)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "candidate", "panel", "route"} | common | ({"baseline"} if args.baseline else set())
                   | ({"repetition"} if args.repetition is not None else set())
                   if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"} if args.report else
                   {"replay", "report_path", "db", "output"} if args.replay else
                   {"aggregate", "panel", "route", "candidate"} if args.aggregate else
                   {"gate", "candidate", "baseline_candidate", "route", "owner_authorization_reference", "panels"}
                   if args.gate else {"record", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            repetition = {} if args.repetition is None else {"repetition": args.repetition}
            result = prepare(args.db, args.output_dir, candidate_id=args.candidate, panel_id=args.panel,
                             route_id=args.route, accepted_commit=args.accepted_commit, gateway_policies=policies,
                             baseline_path=args.baseline, **repetition)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output, args.run_output_dir)
        elif args.record:
            result = record(args.report_path)
        elif args.replay:
            result = asyncio.run(_replay_execute(_replay_plan(args.report_path, args.db, args.output)))
        elif args.aggregate:
            result = aggregate(args.panel, args.route, args.candidate)
        elif args.gate:
            result = gate(args.candidate, args.baseline_candidate, args.route, args.owner_authorization_reference,
                          args.panels)
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
        refusal = ({"replay_refusal": exc.reason} if isinstance(exc, ReplayRefused) else
                   {"gate_refusal": exc.reason} if isinstance(exc, GateRefused) else {})
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code, **refusal}), file=sys.stderr)
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
