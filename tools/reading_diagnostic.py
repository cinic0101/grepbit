#!/usr/bin/env python3
"""Reading diagnostic (docs/reading-diagnostic.md, reading-diagnostic-v1, #79).

One closed-code self-report per dev-panel input: how the model read the question. The system message is the
production one, the user message a fixed template, the response a closed JSON object. Observational only:
never a candidate, a gate input, a run-index entry or promotion evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import sys
import time

from grepbit import model as protocol, recipe_model
from grepbit.gateway import _ERRORS as GATEWAY_ERRORS, MAX_INPUT_BYTES, ModelError
from grepbit.provider import normalize_response
from tools import candidate_registry as registry, evaluate, p3_assets as assets, p3_eval as evaluator
from tools import p3_live_evidence as live, smoke

VERSION = "reading-diagnostic-v1"
AUTHORIZATION_VERSION = "reading-diagnostic-authorization-v1"
PROMPT_VERSION = "reading-prompt-v1"
SCHEMA_NAME = "grepbit_reading_diagnostic"
EVIDENCE_CLASS = "diagnostic_observation"
VARIANTS = ("replayed", "fresh")
REFUSALS = ("not_dev_panel", "source_run", "source_actions", "message_size")


def _enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


# Key order matters: "reading" precedes "verdict" both as declared and alphabetically.
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["reading", "verdict"],
    "properties": {
        "reading": {
            "type": "object", "additionalProperties": False,
            "required": ["analysis", "count_request", "count_event", "orientation", "unsupported"],
            "properties": {
                "analysis": _enum("overview", "compare", "breakdown", "none"),
                "count_request": _enum("none", "booked_seats", "known_booking_accounts", "attendance_visits",
                                       "distinct_people", "unresolved"),
                "count_event": _enum("not_applicable", "booking", "attendance", "unspecified"),
                "orientation": _enum("not_applicable", "stated", "unresolved"),
                "unsupported": _enum("none", "count_meaning", "metric", "period", "scope", "other")}},
        "verdict": {
            "type": "object", "additionalProperties": False, "required": ["decision", "reason"],
            "properties": {
                "decision": _enum("answer", "clarify", "decline"),
                "reason": _enum("all_supported", "count_basis_unresolved", "orientation_unresolved",
                                "center_unresolved", "metric_meaning_unresolved", "unsupported_requirement",
                                "other")}}},
}
_GROUPS = {group: {name: tuple(spec["enum"]) for name, spec in SCHEMA["properties"][group]["properties"].items()}
           for group in ("reading", "verdict")}
KIND_REASONS = {"count_basis": "count_basis_unresolved", "comparison_roles": "orientation_unresolved",
                "center": "center_unresolved", "metric_meaning": "metric_meaning_unresolved"}
_ACTIONS = {"request": "answer", "clarify": "clarify", "declined": "decline"}
_MATCHES = ("decision_matches_expected", "decision_matches_recorded", "reason_matches_expected_kind")

_FIELD_LINES = """Fields:
- reading.analysis: the supported analysis the question asks for, or none.
- reading.count_request: the count the question asks for; unresolved when it asks for a count whose meaning it leaves open; none when it asks for no count.
- reading.count_event: the event the requested count is about.
- reading.orientation: for a comparison of two periods, whether the question states which period is evaluated and which is the reference.
- reading.unsupported: the requirement in the question that the available recipes cannot meet, or none.
"""
_FRESH = ("Diagnostic request. Do not answer the question below. Report only how you read it, as the JSON object "
          "required by the response schema.\n\nQuestion:\n{question}\n\n" + _FIELD_LINES
          + "- verdict.decision: the action you would take for this question.\n"
            "- verdict.reason: the main reason for that action.")
_REPLAYED = ("Diagnostic request. Below are a question and the answer you gave to it. Do not change or repeat that "
             "answer. Report only how you read the question when you gave it, as the JSON object required by the "
             "response schema.\n\nQuestion:\n{question}\n\nYour answer:\n{action}\n\n" + _FIELD_LINES
             + "- verdict.decision: the action your answer took.\n"
               "- verdict.reason: the main reason for that action.")

STATES = ("not_started", "reserved", "returned", "failed")
STOPS = ("complete", "timeout_streak", "network_streak", "budget", "anomaly", "interrupted")
_CONTENT_ERRORS = ("invalid_json", "invalid_reading")
_NETWORK_ERRORS = ("gateway_error", "rate_limited", "transport_error")
_ROW_ERRORS = frozenset(GATEWAY_ERRORS) | {"invalid_reading", "panel_budget", "interrupted", "invalid_manifest",
                                           "invalid_asset", "artifact_io", "artifact_conflict"}
_PACKET_FIELDS = {"version", "variant", "prompt_version", "canonical_packet", "canonical_packet_sha256",
                  "source_run", "schema_name", "schema", "schema_sha256", "inputs", "max_calls",
                  "call_timeout_seconds", "run_seconds", "evidence_class", "promotion_eligible"}
_INPUT_FIELDS = {"case_id", "family_id", "question_sha256", "messages_sha256"}
_MANIFEST_FIELDS = {"version", "packet_sha256", "authorization_sha256", "owner_authorization_reference",
                    "run_slot", "variant"}
_ROW_FIELDS = {"case_id", "family_id", "question_sha256", "state", "attempt", "http_attempts", "elapsed_seconds",
               "error_code", "reading", "usage"}
_USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")
_REPORT_FIELDS = {"version", "packet_sha256", "authorization_sha256", "run_slot", "owner_authorization_reference",
                  "variant", "status", "stop_reason", "evidence_class", "promotion_eligible", "client_http_attempts",
                  "possible_in_flight_attempts", "elapsed_seconds", "results", "summary"}


class DiagnosticRefused(assets.P3Error):
    """The diagnostic cannot be prepared as asked: the existing safe code, one closed reason."""

    def __init__(self, reason: str):
        super().__init__("invalid_manifest")
        self.reason = reason if reason in REFUSALS else "unknown"


class _ReadingError(Exception):
    code = "invalid_reading"


def _sha(value: object) -> str:
    return hashlib.sha256(protocol.canonical_json(value).encode("utf-8")).hexdigest()


def messages(variant: str, question: str, action: str | None) -> list[dict[str, str]]:
    """The two wire messages: the production system message and the fixed diagnostic template."""
    if (variant not in VARIANTS or not isinstance(question, str) or not question
            or (variant == "fresh") != (action is None) or action is not None and not isinstance(action, str)):
        raise assets.P3Error("invalid_arguments")
    head, tail = (_FRESH if variant == "fresh" else _REPLAYED).split("{question}")
    if variant == "replayed":
        middle, tail = tail.split("{action}")
        user = head + question + middle + action + tail
    else:
        user = head + question + tail
    system = recipe_model.messages_for(question)[0]
    return [{"role": system["role"], "content": system["content"]}, {"role": "user", "content": user}]


def closed_reading(value: object) -> dict:
    """Exactly the closed object of the schema, or ``_ReadingError``."""
    if not isinstance(value, dict) or set(value) != set(_GROUPS):
        raise _ReadingError()
    result = {}
    for group, fields in _GROUPS.items():
        part = value[group]
        if not isinstance(part, dict) or set(part) != set(fields):
            raise _ReadingError()
        for name, codes in fields.items():
            if not isinstance(part[name], str) or part[name] not in codes:
                raise _ReadingError()
        result[group] = {name: part[name] for name in fields}
    return result


def _recorded(action: object) -> tuple[str | None, str | None]:
    if action is None:
        return None, None
    try:
        value = protocol.strict_json(action)
    except ModelError:
        raise assets.P3Error("invalid_asset") from None
    outcome = value.get("outcome") if isinstance(value, dict) else None
    if outcome not in _ACTIONS:
        raise assets.P3Error("invalid_asset")
    kind = value["clarification"]["kind"] if outcome == "clarify" else None
    return _ACTIONS[outcome], kind


# --------------------------------------------------------------------------- packet

def _source(run_id: str, panel_id: str, route_id: str, target: str, canonical: dict,
            runs_path: Path | None, candidates_index: Path | None) -> tuple[dict, dict]:
    runs = [run for run in evaluate.load_runs(runs_path) if run["run_id"] == run_id]
    if len(runs) != 1:
        raise DiagnosticRefused("source_run")
    run = runs[0]
    if ((run["panel_id"], run["route_id"], run["status"]) != (panel_id, route_id, "complete")
            or registry.load_entry(run["candidate_id"], candidates_index)["candidate_sha256"] != target):
        raise DiagnosticRefused("source_run")
    [report] = evaluate._archived_reports([run])
    if (report.get("report_version") != evaluate.REPORT_VERSIONS[evaluate.PACKET_V2]
            or report["status"] != "complete" or report["candidate"]["candidate_sha256"] != target
            or report["panel"]["assets"] != canonical["panel"]["assets"] or report["route"] != canonical["route"]
            or [(row["case_id"], row["question_sha256"]) for row in report["results"]]
            != [(row["case_id"], row["question_sha256"]) for row in canonical["inputs"]]):
        raise DiagnosticRefused("source_run")
    return run, report


def _plan(database: Path, *, variant: str, panel_id: str, route_id: str, source_run_id: str, accepted_commit: str,
          panels_path: Path | None = None, routes_path: Path | None = None, runs_path: Path | None = None,
          candidates_index: Path | None = None):
    if variant not in VARIANTS or any(not isinstance(value, str) or not value
                                      for value in (panel_id, route_id, source_run_id, accepted_commit)):
        raise assets.P3Error("invalid_arguments")
    if evaluate._entry(evaluate.load_panels(panels_path), "panels", panel_id, "panel_id")["tier"] != "dev":
        raise DiagnosticRefused("not_dev_panel")
    current = registry.current(candidates_index)["candidate_id"]
    canonical, panel = evaluate.build_packet(
        database, candidate_id=current, panel_id=panel_id, route_id=route_id, accepted_commit=accepted_commit,
        gateway_policies=dict(evaluate.ROUTE_POLICY), panels_path=panels_path, routes_path=routes_path,
        runs_path=runs_path, candidates_index=candidates_index)
    run, report = _source(source_run_id, panel_id, route_id, canonical["candidate"]["candidate_sha256"], canonical,
                          runs_path, candidates_index)
    return variant, canonical, panel, run, report


def _assemble(variant: str, canonical: dict, panel: assets.Panel, run: dict, report: dict) -> dict:
    inputs = []
    for case, row in zip(panel.cases, report["results"]):
        action = row["validated_action"] if variant == "replayed" else None
        if variant == "replayed" and action is None:
            raise DiagnosticRefused("source_actions")
        wire = messages(variant, case.question, action)
        if len(wire[1]["content"].encode("utf-8")) > MAX_INPUT_BYTES:
            raise DiagnosticRefused("message_size")
        inputs.append({"case_id": case.case_id, "family_id": case.family_id,
                       "question_sha256": row["question_sha256"], "messages_sha256": _sha(wire)})
    timeout = canonical["settings"]["call_timeout_seconds"]
    return {
        "version": VERSION, "variant": variant, "prompt_version": PROMPT_VERSION,
        "canonical_packet": canonical, "canonical_packet_sha256": _sha(canonical),
        "source_run": {"run_id": run["run_id"], "report_sha256": run["report_sha256"], "slot": run["slot"]},
        "schema_name": SCHEMA_NAME, "schema": SCHEMA, "schema_sha256": _sha(SCHEMA), "inputs": inputs,
        "max_calls": len(inputs), "call_timeout_seconds": timeout, "run_seconds": len(inputs) * timeout + 120,
        "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False,
    }


def build_packet(database: Path, **options) -> dict:
    return _assemble(*_plan(database, **options))


def _options(packet: dict) -> dict:
    canonical = packet["canonical_packet"]
    return {"variant": packet["variant"], "panel_id": canonical["panel"]["panel_id"],
            "route_id": canonical["route"]["route_id"], "source_run_id": packet["source_run"]["run_id"],
            "accepted_commit": canonical["accepted_commit"]}


def _packet_contract(packet: object) -> dict:
    assets.object_fields(packet, _PACKET_FIELDS, "invalid_manifest")
    canonical = packet["canonical_packet"]
    evaluate._packet_contract(canonical)
    inputs = packet["inputs"]
    if (packet["version"] != VERSION or packet["variant"] not in VARIANTS or packet["prompt_version"] != PROMPT_VERSION
            or packet["schema_name"] != SCHEMA_NAME or packet["schema"] != SCHEMA
            or packet["schema_sha256"] != _sha(SCHEMA) or packet["canonical_packet_sha256"] != _sha(canonical)
            or packet["evidence_class"] != EVIDENCE_CLASS or packet["promotion_eligible"] is not False
            or not isinstance(inputs, list) or [row.get("case_id") if isinstance(row, dict) else None
                                                for row in inputs] != canonical["order"]
            or packet["max_calls"] != len(inputs)
            or packet["call_timeout_seconds"] != canonical["settings"]["call_timeout_seconds"]
            or packet["run_seconds"] != len(inputs) * packet["call_timeout_seconds"] + 120):
        raise assets.P3Error("invalid_manifest")
    assets.object_fields(packet["source_run"], {"run_id", "report_sha256", "slot"}, "invalid_manifest")
    for row in inputs:
        assets.object_fields(row, _INPUT_FIELDS, "invalid_manifest")
    return packet


def prepare(database: Path, output_path: Path, **options) -> dict:
    if not isinstance(output_path, Path) or output_path.name != "packet.json":
        raise assets.P3Error("invalid_arguments")
    packet = build_packet(database, **options)
    live._write_authorization(output_path, packet)
    return {"version": VERSION, "state": "prepared_not_authorized", "variant": packet["variant"],
            "packet_sha256": evaluator._pin(output_path)["sha256"], "inputs": len(packet["inputs"]),
            "source_run": packet["source_run"]["run_id"]}


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


def _copy(source: Path, target: Path) -> None:
    """Byte-exact exclusive copy, so the run slot carries the pinned packet and envelope."""
    smoke._no_symlinks(source)
    smoke._no_symlinks(target)
    try:
        raw = source.read_bytes()
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise assets.P3Error("artifact_conflict") from None
    except OSError:
        raise assets.P3Error("artifact_io") from None


# --------------------------------------------------------------------------- live

def _summary(rows: list[dict]) -> dict:
    return {"inputs": len(rows), **{state: sum(row["state"] == state for row in rows) for state in STATES}}


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
    variant, canonical, panel, run, source = _plan(database, **_options(packet), **registries)
    if not evaluate._same(packet, _assemble(variant, canonical, panel, run, source)):
        raise assets.P3Error("manifest_drift")
    authorization_sha = evaluator._pin(authorization_path)["sha256"]
    manifest = {"version": VERSION, "packet_sha256": packet_sha, "authorization_sha256": authorization_sha,
                "owner_authorization_reference": authorization["owner_authorization_reference"],
                "run_slot": authorization["run_slot"], "variant": variant}
    artifacts = smoke._Artifacts(output_dir, manifest)
    _copy(packet_path, output_dir / "packet.json")
    _copy(authorization_path, output_dir / "authorization.json")
    if (evaluator._pin(output_dir / "packet.json")["sha256"] != packet_sha
            or evaluator._pin(output_dir / "authorization.json")["sha256"] != authorization_sha):
        raise assets.P3Error("manifest_drift")
    rows = [{"case_id": item["case_id"], "family_id": item["family_id"], "question_sha256": item["question_sha256"],
             "state": "not_started", "attempt": 0, "http_attempts": 0, "elapsed_seconds": None,
             "error_code": None, "reading": None, "usage": None} for item in packet["inputs"]]
    report = {key: manifest[key] for key in manifest if key != "version"}
    report.update(version=VERSION, status="incomplete", stop_reason=None, evidence_class=EVIDENCE_CLASS,
                  promotion_eligible=False, client_http_attempts=0, possible_in_flight_attempts=0,
                  elapsed_seconds=0.0, results=rows, summary=_summary(rows))
    artifacts.persist(report)
    cases = {case.case_id: case for case in panel.cases}
    constraint = {"name": SCHEMA_NAME, "schema": SCHEMA}
    client, timeouts, network = None, 0, 0
    started = clock()
    for index, item in enumerate(packet["inputs"]):
        if clock() - started >= packet["run_seconds"]:
            report["stop_reason"] = "budget"
            break
        row = rows[index]
        # Each reservation is durable before a client constructor may read credentials.
        row.update(state="reserved", attempt=1)
        report["possible_in_flight_attempts"] = 1
        report["summary"] = _summary(rows)
        artifacts.persist(report)
        before, call_start, code = (client.http_attempts if client is not None else 0), clock(), None
        try:
            if client is None:
                client = evaluate._admitted_client(canonical, env_file)
                before = client.http_attempts
                # The same transport check as tools/evaluate.py --live: a route change is an anomaly.
                if client.config.transport_security != canonical["transport_security"]:
                    raise assets.P3Error("invalid_configuration")
            action = source["results"][index]["validated_action"] if variant == "replayed" else None
            wire = messages(variant, cases[item["case_id"]].question, action)
            if _sha(wire) != item["messages_sha256"]:
                raise assets.P3Error("invalid_manifest")
            remaining = packet["run_seconds"] - (clock() - started)
            if remaining <= 0:
                raise assets.P3Error("panel_budget")
            response = await client.complete(wire, timeout_seconds=min(packet["call_timeout_seconds"], remaining),
                                             json_schema_constraint=constraint)
            response = normalize_response(client.config, response)
            evidence: dict = {}
            content = protocol._content(response.body, evidence, expected_model=client.config.expected_model)
            usage = {key: (evidence.get("usage") or {}).get(key) for key in _USAGE_FIELDS}
            row.update(state="returned", reading=closed_reading(protocol.strict_json(content)), usage=usage)
        except (ModelError, assets.P3Error, smoke.SmokeError, _ReadingError) as exc:
            code = exc.code
            row.update(state="failed", error_code=code)
        except (KeyboardInterrupt, asyncio.CancelledError):
            row["http_attempts"] = (client.http_attempts - before) if client is not None else 0
            report["client_http_attempts"] += row["http_attempts"]
            row.update(state="failed", error_code="interrupted", elapsed_seconds=max(0.0, clock() - call_start))
            report.update(stop_reason="interrupted", possible_in_flight_attempts=0,
                          elapsed_seconds=max(0.0, clock() - started), summary=_summary(rows))
            artifacts.persist(report)
            raise
        row["http_attempts"] = (client.http_attempts - before) if client is not None else 0
        row["elapsed_seconds"] = max(0.0, clock() - call_start)
        report["client_http_attempts"] += row["http_attempts"]
        report["possible_in_flight_attempts"] = 0
        report["elapsed_seconds"] = max(0.0, clock() - started)
        timeouts = timeouts + 1 if code == "timeout" else 0
        network = network + 1 if code in _NETWORK_ERRORS else 0
        if code == "panel_budget":
            report["stop_reason"] = "budget"
        elif code is not None and code not in _CONTENT_ERRORS + ("timeout",) + _NETWORK_ERRORS:
            report["stop_reason"] = "anomaly"
        elif timeouts >= 2:
            report["stop_reason"] = "timeout_streak"
        elif network >= 2:
            report["stop_reason"] = "network_streak"
        report["summary"] = _summary(rows)
        artifacts.persist(report)
        if report["stop_reason"] is not None:
            break
    if report["stop_reason"] is None:
        report.update(status="complete", stop_reason="complete")
    report.update(possible_in_flight_attempts=0, elapsed_seconds=max(0.0, clock() - started),
                  summary=_summary(rows))
    artifacts.persist(report)
    return read_report(output_dir / "report.json", **registries)


# --------------------------------------------------------------------------- readback

def _check_row(row: object, item: dict) -> None:
    assets.object_fields(row, _ROW_FIELDS)
    if ((row["case_id"], row["family_id"], row["question_sha256"])
            != (item["case_id"], item["family_id"], item["question_sha256"])
            or row["state"] not in STATES or type(row["attempt"]) is not int or row["attempt"] not in (0, 1)
            or type(row["http_attempts"]) is not int or not 0 <= row["http_attempts"] <= 1
            or row["elapsed_seconds"] is not None and (type(row["elapsed_seconds"]) not in (int, float)
                                                       or row["elapsed_seconds"] < 0)
            or row["error_code"] is not None and row["error_code"] not in _ROW_ERRORS):
        raise assets.P3Error("invalid_asset")
    if row["reading"] is not None:
        try:
            if closed_reading(row["reading"]) != row["reading"]:
                raise assets.P3Error("invalid_asset")
        except _ReadingError:
            raise assets.P3Error("invalid_asset") from None
    usage = row["usage"]
    if usage is not None and (not isinstance(usage, dict) or set(usage) != set(_USAGE_FIELDS) or any(
            value is not None and (type(value) is not int or value < 0) for value in usage.values())):
        raise assets.P3Error("invalid_asset")
    shape = {"not_started": (0, False, False), "reserved": (1, False, False),
             "returned": (1, True, False), "failed": (1, False, True)}[row["state"]]
    if ((row["attempt"], row["reading"] is not None, row["error_code"] is not None) != shape
            or (usage is not None) != (row["state"] == "returned")
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
            or report["stop_reason"] is not None and report["stop_reason"] not in STOPS
            or not isinstance(rows, list) or len(rows) != len(packet["inputs"])):
        raise assets.P3Error("invalid_asset")
    for row, item in zip(rows, packet["inputs"]):
        _check_row(row, item)
    reserved = sum(row["state"] == "reserved" for row in rows)
    states = [row["state"] for row in rows]
    first_unsent = states.index("not_started") if "not_started" in states else len(states)
    if (type(report["client_http_attempts"]) is not int or type(report["possible_in_flight_attempts"]) is not int
            or any(state != "not_started" for state in states[first_unsent:])
            or report["status"] == "complete" and any(
                row["state"] == "failed" and row["error_code"] not in _CONTENT_ERRORS + ("timeout",) + _NETWORK_ERRORS
                for row in rows)
            or report["client_http_attempts"] != sum(row["http_attempts"] for row in rows)
            or report["client_http_attempts"] > packet["max_calls"]
            or report["possible_in_flight_attempts"] != reserved
            or type(report["elapsed_seconds"]) not in (int, float) or report["elapsed_seconds"] < 0
            or report["summary"] != _summary(rows)
            or (report["status"] == "complete") != (report["stop_reason"] == "complete")
            or report["status"] == "complete" and any(row["state"] in ("not_started", "reserved") for row in rows)):
        raise assets.P3Error("invalid_asset")


def pinned_panel(panel_id: str, panels_path: Path | None) -> tuple[dict, assets.Panel]:
    """A registered dev panel whose panel, cases and oracles files match their registry digests."""
    entry = evaluate._entry(evaluate.load_panels(panels_path), "panels", panel_id, "panel_id")
    if entry["tier"] != "dev" or entry["allocation_policy"] is not None:
        raise assets.P3Error("invalid_manifest")
    panel_path = evaluate._location(entry["path"])
    panel = assets.load_panel(panel_path)
    for name, path in {"panel": panel_path, "cases": panel.cases_path, "oracles": panel.oracles_path}.items():
        if evaluator._pin(path)["sha256"] != entry["assets"][name]:
            raise assets.P3Error("manifest_drift")
    return entry, panel


def _compare(report: dict, packet: dict, panels_path: Path | None, runs_path: Path | None) -> tuple[list, dict]:
    canonical = packet["canonical_packet"]
    # The panel, cases and oracles are pinned against the registry, and the registry against the packet.
    entry, panel = pinned_panel(canonical["panel"]["panel_id"], panels_path)
    if (entry["assets"] != canonical["panel"]["assets"]
            or [(item["case_id"], item["question_sha256"]) for item in panel.inputs()]
            != [(item["case_id"], item["question_sha256"]) for item in packet["inputs"]]):
        raise assets.P3Error("manifest_drift")
    runs = [run for run in evaluate.load_runs(runs_path) if run["run_id"] == packet["source_run"]["run_id"]]
    if len(runs) != 1 or runs[0]["report_sha256"] != packet["source_run"]["report_sha256"]:
        raise assets.P3Error("manifest_drift")
    [source] = evaluate._archived_reports(runs)
    comparisons = []
    if not len(report["results"]) == len(panel.cases) == len(source["results"]):
        raise assets.P3Error("manifest_drift")
    for row, case, recorded in zip(report["results"], panel.cases, source["results"]):
        if case.case_id != row["case_id"] or recorded["case_id"] != row["case_id"]:
            raise assets.P3Error("manifest_drift")
        kind = panel.oracle_for(case).clarification.kind if case.expected_branch == "clarify" else None
        action, recorded_kind = _recorded(recorded["validated_action"])
        verdict = row["reading"]["verdict"] if row["reading"] is not None else None
        comparisons.append({
            "case_id": row["case_id"], "expected_branch": case.expected_branch, "expected_kind": kind,
            "recorded_action": action, "recorded_kind": recorded_kind,
            "decision_matches_expected": None if verdict is None else verdict["decision"] == case.expected_branch,
            "decision_matches_recorded": None if verdict is None or action is None
            else verdict["decision"] == action,
            "reason_matches_expected_kind": None if verdict is None or kind is None
            else verdict["reason"] == KIND_REASONS[kind]})
    readings = [row["reading"] for row in report["results"] if row["reading"] is not None]
    fields = {name: {code: sum(reading[group][name] == code for reading in readings) for code in codes}
              for group, names in _GROUPS.items() for name, codes in names.items()}
    matches = {name: {"true": sum(item[name] is True for item in comparisons),
                      "false": sum(item[name] is False for item in comparisons),
                      "null": sum(item[name] is None for item in comparisons)} for name in _MATCHES}
    return comparisons, {"fields": fields, "matches": matches}


def read_report(path: Path, *, panels_path: Path | None = None, routes_path: Path | None = None,
                runs_path: Path | None = None, candidates_index: Path | None = None) -> dict:
    """Archive verification plus the comparisons derived from the panel, its oracles and the source run."""
    if not isinstance(path, Path) or path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    slot = path.parent
    packet = _packet_contract(assets.read_asset(slot / "packet.json"))
    packet_sha = evaluator._pin(slot / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(slot / "authorization.json"), packet_sha)
    if authorization["run_slot"] != evaluate._run_slot(slot):
        raise assets.P3Error("invalid_manifest")
    manifest = assets.object_fields(assets.read_asset(slot / "manifest.json"), _MANIFEST_FIELDS, "invalid_manifest")
    expected = {"version": VERSION, "packet_sha256": packet_sha,
                "authorization_sha256": evaluator._pin(slot / "authorization.json")["sha256"],
                "owner_authorization_reference": authorization["owner_authorization_reference"],
                "run_slot": authorization["run_slot"], "variant": packet["variant"]}
    if manifest != expected:
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    _check_report(report, manifest, packet)
    comparisons, summary = _compare(report, packet, panels_path, runs_path)
    return {**report, "comparisons": comparisons, "reading_summary": summary}


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("db", "output", "packet", "authorization", "run-output-dir", "env-file", "output-dir",
                 "report-path"):
        parser.add_argument("--" + name, type=Path)
    for name in ("variant", "panel", "route", "source-run", "accepted-commit", "owner-authorization-reference"):
        parser.add_argument("--" + name)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        allowed = ({"prepare", "variant", "panel", "route", "source_run", "db", "accepted_commit", "output"}
                   if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else
                   {"live", "packet", "authorization", "db", "accepted_commit", "env_file", "output_dir"}
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        if args.prepare:
            result = prepare(args.db, args.output, variant=args.variant, panel_id=args.panel, route_id=args.route,
                             source_run_id=args.source_run, accepted_commit=args.accepted_commit)
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
            result = {key: report[key] for key in ("version", "variant", "status", "stop_reason",
                                                   "client_http_attempts", "possible_in_flight_attempts",
                                                   "evidence_class", "promotion_eligible", "summary",
                                                   "reading_summary")}
        print(protocol.canonical_json(result))
        return 0 if result.get("status", "complete") == "complete" else 1
    except DiagnosticRefused as exc:
        print(protocol.canonical_json({"status": "incomplete", "error_code": exc.code,
                                       "diagnostic_refusal": exc.reason}), file=sys.stderr)
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
