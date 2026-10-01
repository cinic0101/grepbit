#!/usr/bin/env python3
"""Routing upper bound (docs/routing-upper-bound.md, routing-upper-bound-v1, #79).

Each dev-panel input is routed by a fixed, oracle-checked table to the production context narrowed to its
analysis type. The reply is graded through the unchanged production pipeline and compared with the current
candidate's classes by the candidate gate's rules. Observational only: never a candidate, a run-index entry, a
gate verdict or promotion evidence.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

import httpx

from grepbit import model as protocol, recipe_model
from grepbit.gateway import MODEL, GatewayClient, GatewayConfig, ModelError
from grepbit.provider import normalize_response
from tools import candidate_registry as registry, evaluate, p3_assets as assets, p3_eval as evaluator
from tools import p3_grading, p3_live_evidence as live, p3_scoring as scoring, smoke
from tools import reading_diagnostic as shared

VERSION = "routing-upper-bound-v1"
AUTHORIZATION_VERSION = "routing-upper-bound-authorization-v1"
EVIDENCE_CLASS = "diagnostic_observation"
SCENARIOS = ("overview", "compare", "breakdown")
KIND_SCENARIOS = {"count_basis": "overview", "center": "overview", "metric_meaning": "overview",
                  "comparison_roles": "compare"}
REFUSALS = ("not_dev_panel", "route", "router_table")
COMPARISON_REFUSALS = ("no_sentinel", "sentinel_incomplete", "candidate_identity", "inputs_differ",
                       "index_mismatch")
# The perfect router: experiment configuration, not an oracle. Answer and clarify families must agree with
# their oracles (checked at preparation); decline families have no recipe and are routed by this table only.
ROUTER_TABLE = {
    "p3-dev-bound-meaning-v1": {
        "E02_compare": "compare", "dev-BM2": "compare", "dev-BM3": "compare", "dev-BM4": "compare",
        "dev-BM5": "overview", "dev-BM6": "overview", "dev-BM7": "overview", "dev-BM8": "overview"},
    "p3-dev-mechanism-probe-v1": {
        "E02_compare": "compare", "dev-MC1": "compare", "dev-MC2": "compare", "dev-MC3": "compare",
        "dev-MC4": "compare", "dev-MC5": "compare", "dev-A3": "compare", "dev-BM2": "compare",
        "dev-MY1": "compare", "dev-MY2": "compare", "dev-BM6": "overview", "dev-MN1": "overview",
        "dev-MN2": "overview", "dev-MN3": "overview"},
}
_GRADED_FIELDS = {"version", "outcome", "actual_action", "layers", "checked_wrong", "actual_signature",
                  "operational_error", "pack_status", "missing_required_slots", "diagnostics"}
_PACKET_FIELDS = {"version", "canonical_packet", "canonical_packet_sha256", "scenarios", "inputs", "max_calls",
                  "call_timeout_seconds", "run_seconds", "evidence_class", "promotion_eligible"}
_INPUT_FIELDS = {"case_id", "family_id", "question_sha256", "scenario", "messages_sha256"}
_MANIFEST_FIELDS = {"version", "packet_sha256", "authorization_sha256", "owner_authorization_reference", "run_slot"}
_ROW_FIELDS = {"case_id", "family_id", "question_sha256", "scenario", "state", "attempt", "http_attempts",
               "elapsed_seconds", "error_code", "validated_action", "graded", "usage"}
_REPORT_FIELDS = {"version", "packet_sha256", "authorization_sha256", "run_slot", "owner_authorization_reference",
                  "status", "stop_reason", "evidence_class", "promotion_eligible", "client_http_attempts",
                  "possible_in_flight_attempts", "elapsed_seconds", "results", "summary"}
_NETWORK_ERRORS = ("gateway_error", "rate_limited", "transport_error")
_sha = shared._sha


class ExperimentRefused(assets.P3Error):
    """The experiment cannot be prepared as asked: the existing safe code, one closed reason."""

    def __init__(self, reason: str):
        super().__init__("invalid_manifest")
        self.reason = reason if reason in REFUSALS else "unknown"


# --------------------------------------------------------------------------- scenarios

def derived_scenario(case: assets.Case, oracle: assets.Oracle) -> str | None:
    """The analysis type an accepted oracle implies; None for a decline, which has no recipe."""
    if case.expected_branch == "answer":
        return oracle.to_dict()["recipe_id"]
    if case.expected_branch == "clarify":
        return KIND_SCENARIOS[oracle.clarification.kind]
    return None


def _kinds(scenario: str) -> set[str]:
    if scenario not in SCENARIOS:
        raise assets.P3Error("invalid_arguments")
    return {kind for kind, target in KIND_SCENARIOS.items() if target == scenario}


def narrowed_schema(scenario: str) -> dict:
    """The production schema's branches that ``scenario`` can produce; each kept branch is a production branch."""
    kinds, branches = _kinds(scenario), []
    for branch in recipe_model.output_schema()["oneOf"]:
        outcome = branch["properties"]["outcome"]["const"]
        if outcome == "request":
            if branch["properties"]["recipe_id"]["const"] == scenario:
                branches.append(branch)
        elif outcome == "declined":
            branches.append(branch)
        else:
            kept = [kind for kind in branch["properties"]["clarification"]["oneOf"]
                    if kind["properties"]["kind"]["const"] in kinds]
            if kept:
                clarify = deepcopy(branch)
                clarify["properties"]["clarification"]["oneOf"] = kept
                branches.append(clarify)
    return {"oneOf": branches}


def narrowed_context(scenario: str) -> dict:
    context = recipe_model.runtime_context()
    kinds = _kinds(scenario) | {"boundary"}
    context["recipes"] = [recipe for recipe in context["recipes"] if recipe["id"] == scenario]
    context["clarification"] = {kind: text for kind, text in context["clarification"].items() if kind in kinds}
    context["output_schema"] = narrowed_schema(scenario)
    return context


def schema_name(scenario: str) -> str:
    """The production schema name, so that only the narrowed context and schema vary."""
    _kinds(scenario)
    return recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME


def messages(scenario: str, question: str) -> list[dict[str, str]]:
    return recipe_model._messages(question, narrowed_context(scenario))


# --------------------------------------------------------------------------- packet

def _plan(database: Path, *, panel_id: str, route_id: str, accepted_commit: str, panels_path: Path | None = None,
          routes_path: Path | None = None, runs_path: Path | None = None,
          candidates_index: Path | None = None) -> tuple[dict, assets.Panel]:
    if any(not isinstance(value, str) or not value for value in (panel_id, route_id, accepted_commit)):
        raise assets.P3Error("invalid_arguments")
    if evaluate._entry(evaluate.load_panels(panels_path), "panels", panel_id, "panel_id")["tier"] != "dev":
        raise ExperimentRefused("not_dev_panel")
    route = evaluate._entry(evaluate.load_routes(routes_path), "routes", route_id, "route_id")
    # The replay client that grades the reply is the 31B LiteLLM client; other routes are out of scope for v1.
    if route["provider"] != "litellm" or route["model"] != MODEL:
        raise ExperimentRefused("route")
    table = ROUTER_TABLE.get(panel_id)
    if table is None:
        raise ExperimentRefused("router_table")
    canonical, panel = evaluate.build_packet(
        database, candidate_id=registry.current(candidates_index)["candidate_id"], panel_id=panel_id,
        route_id=route_id, accepted_commit=accepted_commit, gateway_policies=dict(evaluate.ROUTE_POLICY),
        panels_path=panels_path, routes_path=routes_path, runs_path=runs_path, candidates_index=candidates_index)
    if set(table) != {case.family_id for case in panel.cases}:
        raise ExperimentRefused("router_table")
    inputs = []
    for case, item in zip(panel.cases, canonical["inputs"]):
        scenario, derived = table[case.family_id], derived_scenario(case, panel.oracle_for(case))
        if scenario not in SCENARIOS or derived is not None and derived != scenario:
            raise ExperimentRefused("router_table")
        inputs.append({"case_id": case.case_id, "family_id": case.family_id,
                       "question_sha256": item["question_sha256"], "scenario": scenario,
                       "messages_sha256": _sha(messages(scenario, case.question))})
    used = [scenario for scenario in SCENARIOS if any(row["scenario"] == scenario for row in inputs)]
    timeout = canonical["settings"]["call_timeout_seconds"]
    packet = {
        "version": VERSION, "canonical_packet": canonical, "canonical_packet_sha256": _sha(canonical),
        "scenarios": {scenario: _scenario_pins(scenario) for scenario in used}, "inputs": inputs,
        "max_calls": len(inputs), "call_timeout_seconds": timeout, "run_seconds": len(inputs) * timeout + 120,
        "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False,
    }
    return packet, panel


def _scenario_pins(scenario: str) -> dict:
    return {"context_sha256": _sha(narrowed_context(scenario)), "schema_name": schema_name(scenario),
            "schema_sha256": _sha(narrowed_schema(scenario))}


def build_packet(database: Path, **options) -> dict:
    return _plan(database, **options)[0]


def _options(packet: dict) -> dict:
    canonical = packet["canonical_packet"]
    return {"panel_id": canonical["panel"]["panel_id"], "route_id": canonical["route"]["route_id"],
            "accepted_commit": canonical["accepted_commit"]}


def _packet_contract(packet: object) -> dict:
    assets.object_fields(packet, _PACKET_FIELDS, "invalid_manifest")
    canonical, inputs = packet["canonical_packet"], packet["inputs"]
    evaluate._packet_contract(canonical)
    if (packet["version"] != VERSION or packet["canonical_packet_sha256"] != _sha(canonical)
            or packet["evidence_class"] != EVIDENCE_CLASS or packet["promotion_eligible"] is not False
            or not isinstance(inputs, list)
            or [row.get("case_id") if isinstance(row, dict) else None for row in inputs] != canonical["order"]
            or packet["max_calls"] != len(inputs)
            or packet["call_timeout_seconds"] != canonical["settings"]["call_timeout_seconds"]
            or packet["run_seconds"] != len(inputs) * packet["call_timeout_seconds"] + 120):
        raise assets.P3Error("invalid_manifest")
    for row in inputs:
        assets.object_fields(row, _INPUT_FIELDS, "invalid_manifest")
        if row["scenario"] not in SCENARIOS:
            raise assets.P3Error("invalid_manifest")
    used = [scenario for scenario in SCENARIOS if any(row["scenario"] == scenario for row in inputs)]
    if not isinstance(packet["scenarios"], dict) or list(packet["scenarios"]) != used or any(
            packet["scenarios"][scenario] != _scenario_pins(scenario) for scenario in used):
        raise assets.P3Error("invalid_manifest")
    return packet


def prepare(database: Path, output_path: Path, **options) -> dict:
    if not isinstance(output_path, Path) or output_path.name != "packet.json":
        raise assets.P3Error("invalid_arguments")
    packet = build_packet(database, **options)
    live._write_authorization(output_path, packet)
    return {"version": VERSION, "state": "prepared_not_authorized",
            "packet_sha256": evaluator._pin(output_path)["sha256"], "inputs": len(packet["inputs"]),
            "scenarios": list(packet["scenarios"])}


# --------------------------------------------------------------------------- authorization

def _authorization(value: object, packet_sha: str) -> dict:
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"},
                         "invalid_manifest")
    reference, slot = value["owner_authorization_reference"], value["run_slot"]
    if (value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha
            or not isinstance(reference, str) or evaluate.GRANT.fullmatch(reference) is None
            or not isinstance(slot, str) or evaluate._SLOT.fullmatch(slot) is None
            or any(part in (".", "..") for part in slot.split("/"))):
        raise assets.P3Error("invalid_manifest")
    return value


def bind_authorization(packet_path: Path, reference: str, output_path: Path, run_output_dir: Path) -> dict:
    _packet_contract(assets.read_asset(packet_path))
    digest = evaluator._pin(packet_path)["sha256"]
    if not isinstance(reference, str) or evaluate.GRANT.fullmatch(reference) is None:
        raise assets.P3Error("invalid_arguments")
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference,
                            "run_slot": evaluate._run_slot(run_output_dir)}, digest)
    live._write_authorization(output_path, value)
    return value


# --------------------------------------------------------------------------- live

def _body_replay_client(body: bytes) -> GatewayClient:
    """Serves the route's exact response body, so the production pipeline parses it as it would have."""
    def respond(request):
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return GatewayClient(GatewayConfig(evaluate._REPLAY_BASE, evaluate._REPLAY_TOKEN, MODEL),
                         transport=httpx.MockTransport(respond))


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, panels_path: Path | None = None,
                   routes_path: Path | None = None, runs_path: Path | None = None,
                   candidates_index: Path | None = None, clock=time.monotonic) -> dict:
    registries = {"panels_path": panels_path, "routes_path": routes_path, "runs_path": runs_path,
                  "candidates_index": candidates_index}
    packet = _packet_contract(assets.read_asset(packet_path))
    packet_sha = evaluator._pin(packet_path)["sha256"]
    authorization = _authorization(assets.read_asset(authorization_path), packet_sha)
    if (authorization["run_slot"] != evaluate._run_slot(output_dir)
            or accepted_commit != packet["canonical_packet"]["accepted_commit"]):
        raise assets.P3Error("invalid_manifest")
    rebuilt, panel = _plan(database, **_options(packet), **registries)
    if not evaluate._same(packet, rebuilt):
        raise assets.P3Error("manifest_drift")
    authorization_sha = evaluator._pin(authorization_path)["sha256"]
    manifest = {"version": VERSION, "packet_sha256": packet_sha, "authorization_sha256": authorization_sha,
                "owner_authorization_reference": authorization["owner_authorization_reference"],
                "run_slot": authorization["run_slot"]}
    artifacts = smoke._Artifacts(output_dir, manifest)
    shared._copy(packet_path, output_dir / "packet.json")
    shared._copy(authorization_path, output_dir / "authorization.json")
    if (evaluator._pin(output_dir / "packet.json")["sha256"] != packet_sha
            or evaluator._pin(output_dir / "authorization.json")["sha256"] != authorization_sha):
        raise assets.P3Error("manifest_drift")
    rows = [{"case_id": item["case_id"], "family_id": item["family_id"], "question_sha256": item["question_sha256"],
             "scenario": item["scenario"], "state": "not_started", "attempt": 0, "http_attempts": 0,
             "elapsed_seconds": None, "error_code": None, "validated_action": None, "graded": None, "usage": None}
            for item in packet["inputs"]]
    report = {key: manifest[key] for key in manifest if key != "version"}
    report.update(version=VERSION, status="incomplete", stop_reason=None, evidence_class=EVIDENCE_CLASS,
                  promotion_eligible=False, client_http_attempts=0, possible_in_flight_attempts=0,
                  elapsed_seconds=0.0, results=rows, summary=shared._summary(rows))
    artifacts.persist(report)
    cases = {case.case_id: case for case in panel.cases}
    client, timeouts, network = None, 0, 0
    started = clock()
    for index, item in enumerate(packet["inputs"]):
        if clock() - started >= packet["run_seconds"]:
            report["stop_reason"] = "budget"
            break
        row, case = rows[index], cases[item["case_id"]]
        # Each reservation is durable before a client constructor may read credentials.
        row.update(state="reserved", attempt=1)
        report.update(possible_in_flight_attempts=1, summary=shared._summary(rows))
        artifacts.persist(report)
        before, call_start, code = (client.http_attempts if client is not None else 0), clock(), None
        try:
            if client is None:
                client = evaluate._admitted_client(packet["canonical_packet"], env_file)
                before = client.http_attempts
                # The same transport check as tools/evaluate.py --live: a route change is an anomaly.
                if client.config.transport_security != packet["canonical_packet"]["transport_security"]:
                    raise assets.P3Error("invalid_configuration")
            wire = messages(item["scenario"], case.question)
            if _sha(wire) != item["messages_sha256"]:
                raise assets.P3Error("invalid_manifest")
            remaining = packet["run_seconds"] - (clock() - started)
            if remaining <= 0:
                raise assets.P3Error("panel_budget")
            response = await client.complete(
                wire, timeout_seconds=min(packet["call_timeout_seconds"], remaining),
                json_schema_constraint={"name": schema_name(item["scenario"]),
                                        "schema": narrowed_schema(item["scenario"])})
            response = normalize_response(client.config, response)
            evidence: dict = {}
            try:
                # Envelope and route anomalies stop the run; a model refusal is the model's answer.
                protocol._content(response.body, evidence, expected_model=client.config.expected_model)
            except ModelError as exc:
                if exc.code != "model_declined":
                    raise
            usage = {key: (evidence.get("usage") or {}).get(key) for key in shared._USAGE_FIELDS}
            row["http_attempts"] = client.http_attempts - before
            # The production pipeline counts model latency and kernel time against one call budget.
            left = packet["call_timeout_seconds"] - (clock() - call_start)
            if left <= 0:
                raise ModelError("timeout")
            result = await recipe_model.interpret_recipe_and_execute(
                case.question, database, _body_replay_client(response.body), timeout_seconds=left)
            row.update(state="returned", validated_action=evaluate._validated_action(result),
                       graded=p3_grading.grade(result, panel.oracle_for(case)), usage=usage)
        except (ModelError, assets.P3Error, smoke.SmokeError) as exc:
            code = exc.code
            row.update(state="failed", error_code=code)
        except (KeyboardInterrupt, asyncio.CancelledError):
            row["http_attempts"] = (client.http_attempts - before) if client is not None else 0
            report["client_http_attempts"] += row["http_attempts"]
            row.update(state="failed", error_code="interrupted", elapsed_seconds=max(0.0, clock() - call_start))
            report.update(stop_reason="interrupted", possible_in_flight_attempts=0,
                          elapsed_seconds=max(0.0, clock() - started), summary=shared._summary(rows))
            artifacts.persist(report)
            raise
        row["http_attempts"] = (client.http_attempts - before) if client is not None else 0
        row["elapsed_seconds"] = max(0.0, clock() - call_start)
        report["client_http_attempts"] += row["http_attempts"]
        report.update(possible_in_flight_attempts=0, elapsed_seconds=max(0.0, clock() - started))
        timeouts = timeouts + 1 if code == "timeout" else 0
        network = network + 1 if code in _NETWORK_ERRORS else 0
        if code == "panel_budget":
            report["stop_reason"] = "budget"
        elif code is not None and code not in ("timeout",) + _NETWORK_ERRORS:
            report["stop_reason"] = "anomaly"
        elif timeouts >= 2:
            report["stop_reason"] = "timeout_streak"
        elif network >= 2:
            report["stop_reason"] = "network_streak"
        report["summary"] = shared._summary(rows)
        artifacts.persist(report)
        if report["stop_reason"] is not None:
            break
    if report["stop_reason"] is None:
        report.update(status="complete", stop_reason="complete")
    report.update(possible_in_flight_attempts=0, elapsed_seconds=max(0.0, clock() - started),
                  summary=shared._summary(rows))
    artifacts.persist(report)
    return read_report(output_dir / "report.json", **registries)


# --------------------------------------------------------------------------- readback

def _check_graded(graded: object) -> None:
    assets.object_fields(graded, _GRADED_FIELDS)
    if (graded["version"] != p3_grading.VERSION or graded["outcome"] not in assets.OUTCOMES
            or graded["actual_action"] not in (None, "answer", "clarify", "decline")
            or not isinstance(graded["layers"], dict) or set(graded["layers"]) != set(p3_grading.LAYERS)
            or any(value not in ("passed", "failed", "not_assessed") for value in graded["layers"].values())
            or graded["operational_error"] is not None and not isinstance(graded["operational_error"], str)
            or type(graded["checked_wrong"]) is not bool or not isinstance(graded["diagnostics"], list)
            or not isinstance(graded["missing_required_slots"], list)):
        raise assets.P3Error("invalid_asset")


def _check_validated_action(text: str | None, graded: dict | None) -> None:
    """The persisted action has evaluation v2's closed shape and agrees with the graded action."""
    if text is None:
        return
    try:
        action = protocol.strict_json(text)
    except ModelError:
        raise assets.P3Error("invalid_asset") from None
    if not evaluate._action_shape(action) or protocol.canonical_json(action) != text or graded is None:
        raise assets.P3Error("invalid_asset")
    # A v15 unresolved Compare orientation is the model's request behind a server-built roles clarification.
    derived = action["outcome"] == "request" and action.get("orientation") == "unresolved"
    # A v16 named unavailable count reading is the model's action behind a server decline.
    declined = action["outcome"] == "request" and action.get("count_request") in evaluate.UNAVAILABLE_COUNTS
    # A v19 model count_basis clarification is the model's action behind a server answer (ADR #158); before v19
    # it was a real clarification, so the graded actual action decides.
    answered = evaluate._count_basis_clarification(action) and graded["actual_action"] == "answer"
    if ("clarify" if derived else "decline" if declined else "answer" if answered else
            {"request": "answer", "clarify": "clarify", "declined": "decline"}[action["outcome"]]
            ) != graded["actual_action"]:
        raise assets.P3Error("invalid_asset")


def _check_row(row: object, item: dict) -> None:
    assets.object_fields(row, _ROW_FIELDS)
    if ((row["case_id"], row["family_id"], row["question_sha256"], row["scenario"])
            != (item["case_id"], item["family_id"], item["question_sha256"], item["scenario"])
            or row["state"] not in shared.STATES or type(row["attempt"]) is not int or row["attempt"] not in (0, 1)
            or type(row["http_attempts"]) is not int or not 0 <= row["http_attempts"] <= 1
            or row["elapsed_seconds"] is not None and (type(row["elapsed_seconds"]) not in (int, float)
                                                       or row["elapsed_seconds"] < 0)
            or row["error_code"] is not None and (row["error_code"] not in shared._ROW_ERRORS
                                                  or row["error_code"] in ("invalid_json", "invalid_reading"))
            or row["validated_action"] is not None and (not isinstance(row["validated_action"], str)
                                                        or len(row["validated_action"].encode()) > 16384)):
        raise assets.P3Error("invalid_asset")
    if row["graded"] is not None:
        _check_graded(row["graded"])
    _check_validated_action(row["validated_action"], row["graded"])
    usage = row["usage"]
    if usage is not None and (not isinstance(usage, dict) or set(usage) != set(shared._USAGE_FIELDS) or any(
            value is not None and (type(value) is not int or value < 0) for value in usage.values())):
        raise assets.P3Error("invalid_asset")
    shape = {"not_started": (0, False, False), "reserved": (1, False, False),
             "returned": (1, True, False), "failed": (1, False, True)}[row["state"]]
    if ((row["attempt"], row["graded"] is not None, row["error_code"] is not None) != shape
            or (usage is not None) != (row["state"] == "returned")
            or row["state"] != "returned" and row["validated_action"] is not None
            or row["state"] == "not_started" and (row["http_attempts"] or row["elapsed_seconds"] is not None)
            or row["state"] == "returned" and (row["http_attempts"] != 1 or row["elapsed_seconds"] is None)
            or row["state"] == "failed" and row["elapsed_seconds"] is None):
        raise assets.P3Error("invalid_asset")


def _check_report(report: dict, manifest: dict, packet: dict) -> None:
    assets.object_fields(report, _REPORT_FIELDS)
    rows = report["results"]
    if (any(report[key] != manifest[key] for key in _MANIFEST_FIELDS - {"version"})
            or report["version"] != VERSION or report["evidence_class"] != EVIDENCE_CLASS
            or report["promotion_eligible"] is not False or report["status"] not in ("complete", "incomplete")
            or report["stop_reason"] is not None and report["stop_reason"] not in shared.STOPS
            or not isinstance(rows, list) or len(rows) != len(packet["inputs"])):
        raise assets.P3Error("invalid_asset")
    for row, item in zip(rows, packet["inputs"]):
        _check_row(row, item)
    states = [row["state"] for row in rows]
    first_unsent = states.index("not_started") if "not_started" in states else len(states)
    if (type(report["client_http_attempts"]) is not int or type(report["possible_in_flight_attempts"]) is not int
            or any(state != "not_started" for state in states[first_unsent:])
            or report["status"] == "complete" and any(
                row["state"] == "failed" and row["error_code"] not in ("timeout",) + _NETWORK_ERRORS for row in rows)
            or report["client_http_attempts"] != sum(row["http_attempts"] for row in rows)
            or report["client_http_attempts"] > packet["max_calls"]
            or report["possible_in_flight_attempts"] != sum(row["state"] == "reserved" for row in rows)
            or type(report["elapsed_seconds"]) not in (int, float) or report["elapsed_seconds"] < 0
            or report["summary"] != shared._summary(rows)
            or (report["status"] == "complete") != (report["stop_reason"] == "complete")
            or report["status"] == "complete" and any(row["state"] in ("not_started", "reserved") for row in rows)):
        raise assets.P3Error("invalid_asset")


def _experiment_class(row: dict, expected_branch: str) -> str:
    if row["state"] != "returned":
        return "unassessed"
    graded = row["graded"]
    if evaluate._gate_unassessed({"status": "completed", "outcome": graded["outcome"],
                                  "operational_error": graded["operational_error"], "runner_error_code": None}):
        return "unassessed"
    return "correct" if graded["outcome"] == scoring._SUCCESS[expected_branch] else "wrong"


def _compare(report: dict, packet: dict, panels_path: Path | None, runs_path: Path | None,
             candidates_index: Path | None) -> dict:
    canonical = packet["canonical_packet"]
    panel_id, route_id = canonical["panel"]["panel_id"], canonical["route"]["route_id"]
    # The panel, cases and oracles are pinned against the registry, and the registry against the packet.
    entry, panel = shared.pinned_panel(panel_id, panels_path)
    if (entry["assets"] != canonical["panel"]["assets"]
            or [(item["case_id"], item["question_sha256"]) for item in panel.inputs()]
            != [(item["case_id"], item["question_sha256"]) for item in packet["inputs"]]):
        raise assets.P3Error("manifest_drift")
    behavior = registry.behavior_identity(registry.load_entry(canonical["candidate"]["candidate_id"],
                                                              candidates_index))
    # Graded outcomes depend on the runtime, so the baseline pools by behaviour (ADR #164).
    baseline = evaluate._same_behavior_runs(panel_id, route_id, behavior, evaluate.load_runs(runs_path), {},
                                            candidates_index)
    sentinels = [position for position, run in enumerate(baseline)
                 if run["grant"] == report["owner_authorization_reference"]]
    runs_file = evaluate.RUNS if runs_path is None else runs_path
    value = {"run_index_sha256": evaluator._pin(runs_file)["sha256"],
             "baseline_runs": [run["run_id"] for run in baseline],
             "sentinel_runs": [baseline[position]["run_id"] for position in sentinels],
             "recorded_at": {"sentinel_runs": [baseline[position]["recorded_at"] for position in sentinels]},
             "inputs": [], "fixed": [], "broke": [], "excluded": [], "unassessed": [],
             "counts": None, "verdict": None, "refusal": None}
    if not sentinels:
        value["refusal"] = "no_sentinel"
        return value
    if all(baseline[position]["status"] != "complete" for position in sentinels):
        value["refusal"] = "sentinel_incomplete"
        return value
    reports = evaluate._archived_reports(baseline)
    # The candidate gate's integrity checks, in its order: bytes, inputs, then index agreement.
    target = canonical["candidate"]["candidate_sha256"]
    expected_inputs = (panel_id, canonical["panel"]["assets"], canonical["panel"].get("annex_sha256"),
                       [(item["case_id"], item["question_sha256"]) for item in packet["inputs"]])
    views = [evaluate._gate_view(archived) for archived in reports]
    if any(sha != target for sha, _ in views):
        value["refusal"] = "candidate_identity"
        return value
    if any(inputs != expected_inputs for _, inputs in views):
        value["refusal"] = "inputs_differ"
        return value
    if any((archived["owner_authorization_reference"], archived["panel"]["panel_id"],
            archived["route"]["route_id"], archived["status"]) != (run["grant"], panel_id, route_id, run["status"])
           for run, archived in zip(baseline, reports)):
        value["refusal"] = "index_mismatch"
        return value
    measured_classes = evaluate._input_classes(reports)
    if not len(report["results"]) == len(panel.cases) == len(measured_classes):
        raise assets.P3Error("manifest_drift")
    for position, (row, case, measured) in enumerate(zip(report["results"], panel.cases, measured_classes)):
        experiment = _experiment_class(row, case.expected_branch)
        seen = any(not evaluate._unassessed(reports[sentinel]["results"][position]) for sentinel in sentinels)
        value["inputs"].append({
            "case_id": row["case_id"], "scenario": row["scenario"], "baseline_class": measured["class"],
            "sentinel_assessed": seen, "experiment": experiment,
            "outcome": row["graded"]["outcome"] if row["graded"] is not None else None,
            "class": evaluate._gate_class(measured["class"], experiment, seen)})
    counts = {kind: sum(item["class"] == kind for item in value["inputs"]) for kind in evaluate._GATE_CLASSES}
    for kind in ("fixed", "broke", "excluded", "unassessed"):
        value[kind] = [item["case_id"] for item in value["inputs"] if item["class"] == kind]
    value.update(counts=counts, verdict=evaluate._gate_verdict(counts))
    return value


def read_report(path: Path, *, panels_path: Path | None = None, routes_path: Path | None = None,
                runs_path: Path | None = None, candidates_index: Path | None = None) -> dict:
    """Archive verification plus the comparison with the current candidate, recomputed from the run index."""
    if not isinstance(path, Path) or path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    slot = path.parent
    packet = _packet_contract(assets.read_asset(slot / "packet.json"))
    packet_sha = evaluator._pin(slot / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(slot / "authorization.json"), packet_sha)
    if authorization["run_slot"] != evaluate._run_slot(slot):
        raise assets.P3Error("invalid_manifest")
    manifest = assets.object_fields(assets.read_asset(slot / "manifest.json"), _MANIFEST_FIELDS, "invalid_manifest")
    if manifest != {"version": VERSION, "packet_sha256": packet_sha,
                    "authorization_sha256": evaluator._pin(slot / "authorization.json")["sha256"],
                    "owner_authorization_reference": authorization["owner_authorization_reference"],
                    "run_slot": authorization["run_slot"]}:
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    _check_report(report, manifest, packet)
    return {**report, "comparison": _compare(report, packet, panels_path, runs_path, candidates_index)}


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("db", "output", "packet", "authorization", "run-output-dir", "env-file", "output-dir",
                 "report-path"):
        parser.add_argument("--" + name, type=Path)
    for name in ("panel", "route", "accepted-commit", "owner-authorization-reference"):
        parser.add_argument("--" + name)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        allowed = ({"prepare", "panel", "route", "db", "accepted_commit", "output"} if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else
                   {"live", "packet", "authorization", "db", "accepted_commit", "env_file", "output_dir"}
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        if args.prepare:
            result = prepare(args.db, args.output, panel_id=args.panel, route_id=args.route,
                             accepted_commit=args.accepted_commit)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output,
                                        args.run_output_dir)
        else:
            if args.live:
                smoke._no_symlinks(args.env_file)
                report = asyncio.run(run_live(args.db, args.output_dir, packet_path=args.packet,
                                              authorization_path=args.authorization,
                                              accepted_commit=args.accepted_commit, env_file=args.env_file))
            else:
                report = read_report(args.report_path)
            result = {key: report[key] for key in ("version", "status", "stop_reason", "client_http_attempts",
                                                   "possible_in_flight_attempts", "evidence_class",
                                                   "promotion_eligible", "summary")}
            result["comparison"] = {key: report["comparison"][key] for key in (
                "baseline_runs", "sentinel_runs", "fixed", "broke", "excluded", "unassessed", "counts",
                "verdict", "refusal")}
        print(protocol.canonical_json(result))
        return 0 if result.get("status", "complete") == "complete" else 1
    except ExperimentRefused as exc:
        print(protocol.canonical_json({"status": "incomplete", "error_code": exc.code,
                                       "experiment_refusal": exc.reason}), file=sys.stderr)
        return 2
    except evaluator._SAFE_ERRORS as exc:
        print(protocol.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"error_code":"interrupted","status":"incomplete"}', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, LookupError, RecursionError):
        print('{"error_code":"invalid_manifest","status":"incomplete"}', file=sys.stderr)
        return 2
    except (RuntimeError, AttributeError, ArithmeticError):
        print('{"error_code":"internal_failure","status":"incomplete"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
