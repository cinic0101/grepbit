#!/usr/bin/env python3
"""Count ablation diagnostic (docs/count-ablation.md, count-ablation-v1, #152).

Pre-registered dev inputs are sent with the production system message changed by exactly one pre-registered variant:
renamed count_request labels, or the count_basis and either/or rules scoped to the user's own undecided choice. Each
reply is graded through the unchanged production pipeline and compared with the current candidate's recorded runs.
Observational only: never a candidate, a run-index entry, a gate verdict or promotion evidence.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time

from grepbit import model as protocol, recipe_model
from grepbit.gateway import MODEL, ModelError
from grepbit.provider import normalize_response
from tools import candidate_registry as registry, evaluate, p3_assets as assets, p3_eval as evaluator
from tools import p3_grading, p3_live_evidence as live, p3_scoring as scoring, smoke
from tools import reading_diagnostic as shared, routing_upper_bound as routing

VERSION = "count-ablation-v1"
AUTHORIZATION_VERSION = "count-ablation-authorization-v1"
EVIDENCE_CLASS = "diagnostic_observation"
VARIANTS = ("labels", "rules")
REFUSALS = ("not_dev_panel", "route", "selection", "variant_text")
COMPARISON_REFUSALS = ("no_baseline", "baseline_unavailable", "candidate_identity", "inputs_differ", "index_mismatch")
# The pre-registered inputs: every case of these families, in panel order.
SELECTION = {
    "p3-dev-bound-meaning-v2": ("dev-BM5", "dev-BM6", "dev-BM7"),
    "p3-dev-mechanism-probe-v2": ("dev-MN2",),
    "p3-dev-matrix-compare-first-v3": ("dev-A1", "dev-A2", "dev-C1"),
}
LABELS = {"none": "no_people_count", "unresolved": "generic_people_count"}
INVERSE_LABELS = {new: old for old, new in LABELS.items()}
LABEL_EDITS = (
    ('"unresolved" when it asks for a count whose meaning it leaves open',
     '"generic_people_count" when it asks for a count whose meaning it leaves open'),
    ('"none" when it asks for no count, including', '"no_people_count" when it asks for no count, including'),
    ("so it is none, never known_booking_accounts", "so it is no_people_count, never known_booking_accounts"),
    ("the server answers an unresolved count with booked seats",
     "the server answers a generic_people_count reading with booked seats"),
    ('Overview request and count_request "unresolved", not a count_basis clarification.',
     'Overview request and count_request "generic_people_count", not a count_basis clarification.'),
    ('is also answered with count_request "unresolved", and the stated assumption',
     'is also answered with count_request "generic_people_count", and the stated assumption'),
)
RULE_EDITS = (
    ("An explicit either/or contrast restricts the open interpretations to that contrast, even after an earlier "
     "generic noun.",
     "An explicit either/or contrast restricts the open interpretations to that contrast, even after an earlier "
     "generic noun; a question about which count basis the system uses is not such a contrast."),
)
COUNT_BASIS_EDIT = (
    "Use count_basis only when the question explicitly leaves the count basis undecided between named meanings, "
    "offering exactly those meanings.",
    "Use count_basis only when the user says they themselves have not decided between named meanings, offering "
    "exactly those meanings; a user who doubts which basis the system counts by has not left it undecided.")
_PACKET_FIELDS = {"version", "canonical_packet", "canonical_packet_sha256", "variants", "inputs", "max_calls",
                  "call_timeout_seconds", "run_seconds", "evidence_class", "promotion_eligible"}
_INPUT_FIELDS = {"case_id", "family_id", "question_sha256", "variant", "messages_sha256"}
_MANIFEST_FIELDS = {"version", "packet_sha256", "authorization_sha256", "owner_authorization_reference", "run_slot"}
_ROW_FIELDS = {"case_id", "family_id", "question_sha256", "variant", "state", "attempt", "http_attempts",
               "elapsed_seconds", "error_code", "validated_action", "graded", "annex", "reading", "mapped", "usage"}
_REPORT_FIELDS = {"version", "packet_sha256", "authorization_sha256", "run_slot", "owner_authorization_reference",
                  "status", "stop_reason", "evidence_class", "promotion_eligible", "client_http_attempts",
                  "possible_in_flight_attempts", "elapsed_seconds", "results", "summary"}
_READING_FIELDS = {"outcome", "count_request", "clarification_kind", "choices"}
_NETWORK_ERRORS = routing._NETWORK_ERRORS
_sha = shared._sha


class ExperimentRefused(assets.P3Error):
    """The ablation cannot be prepared as asked: the existing safe code, one closed reason."""

    def __init__(self, reason: str):
        super().__init__("invalid_manifest")
        self.reason = reason if reason in REFUSALS else "unknown"


# --------------------------------------------------------------------------- variants

def _edited(text: str, edits: tuple) -> str:
    for old, new in edits:
        if text.count(old) != 1:
            raise ExperimentRefused("variant_text")
        text = text.replace(old, new, 1)
    return text


def _variant(variant: str) -> None:
    if variant not in VARIANTS:
        raise assets.P3Error("invalid_arguments")


def variant_instruction(variant: str) -> str:
    _variant(variant)
    return _edited(recipe_model.SYSTEM_INSTRUCTION, LABEL_EDITS if variant == "labels" else RULE_EDITS)


def variant_schema(variant: str) -> dict:
    """The production schema; under ``labels`` the Overview count_request enum carries the renamed labels."""
    _variant(variant)
    schema = recipe_model.output_schema()
    if variant == "rules":
        return schema
    renamed = 0
    for branch in schema["oneOf"]:
        properties = branch["properties"]
        if properties["outcome"]["const"] == "request" and properties["recipe_id"]["const"] == "overview":
            enum = properties["count_request"]["enum"]
            if not set(LABELS) <= set(enum) or set(INVERSE_LABELS) & set(enum):
                raise ExperimentRefused("variant_text")
            properties["count_request"]["enum"] = [LABELS.get(value, value) for value in enum]
            renamed += 1
    if renamed != 1:
        raise ExperimentRefused("variant_text")
    return schema


def variant_context(variant: str) -> dict:
    _variant(variant)
    context = recipe_model.runtime_context()
    if variant == "labels":
        context["output_schema"] = variant_schema(variant)
    else:
        context["clarification"]["count_basis"] = _edited(context["clarification"]["count_basis"], (COUNT_BASIS_EDIT,))
    return context


def messages(variant: str, question: str) -> list[dict[str, str]]:
    if not isinstance(question, str):
        raise ModelError("invalid_input")
    return [{"role": "system", "content": variant_instruction(variant) + "\n"
             + protocol.canonical_json(variant_context(variant))},
            {"role": "user", "content": question}]


def map_back(variant: str, body: bytes) -> bytes:
    """Under ``labels``, the reply's Overview count_request label maps back to the production value; every other
    reply, and every ``rules`` reply, is returned byte for byte.

    The envelope and the content are parsed with the production parser (protocol.strict_json), so a reply that
    production would reject (duplicate keys, non-finite numbers, lone surrogates, excessive nesting) is never
    mapped: it passes through unchanged and the unchanged pipeline grades it. Mapping never raises."""
    _variant(variant)
    if variant != "labels":
        return body
    try:
        envelope = protocol.strict_json(body)
        message = envelope["choices"][0]["message"]
        action = protocol.strict_json(message["content"])
        if (not isinstance(action, dict) or action.get("outcome") != "request"
                or action.get("recipe_id") != "overview" or action.get("count_request") not in INVERSE_LABELS):
            return body
        action["count_request"] = INVERSE_LABELS[action["count_request"]]
        message["content"] = protocol.canonical_json(action)
        return protocol.canonical_json(envelope).encode("utf-8")
    except (ModelError, TypeError, LookupError, ValueError, UnicodeError, RecursionError):
        return body


def _variant_pins(variant: str) -> dict:
    edits = LABEL_EDITS if variant == "labels" else RULE_EDITS + (COUNT_BASIS_EDIT,)
    return {"instruction_sha256": _sha(variant_instruction(variant)), "context_sha256": _sha(variant_context(variant)),
            "schema_name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME, "schema_sha256": _sha(variant_schema(variant)),
            "edits": [list(edit) for edit in edits]}


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
    families = SELECTION.get(panel_id)
    if families is None:
        raise ExperimentRefused("selection")
    # The variants are checked against the current runtime before anything else is built.
    variants = {variant: _variant_pins(variant) for variant in VARIANTS}
    canonical, panel = evaluate.build_packet(
        database, candidate_id=registry.current(candidates_index)["candidate_id"], panel_id=panel_id,
        route_id=route_id, accepted_commit=accepted_commit, gateway_policies=dict(evaluate.ROUTE_POLICY),
        panels_path=panels_path, routes_path=routes_path, runs_path=runs_path, candidates_index=candidates_index)
    if not set(families) <= {case.family_id for case in panel.cases}:
        raise ExperimentRefused("selection")
    inputs = []
    for case, item in zip(panel.cases, canonical["inputs"]):
        if case.family_id not in families:
            continue
        for variant in VARIANTS:
            inputs.append({"case_id": case.case_id, "family_id": case.family_id,
                           "question_sha256": item["question_sha256"], "variant": variant,
                           "messages_sha256": _sha(messages(variant, case.question))})
    timeout = canonical["settings"]["call_timeout_seconds"]
    packet = {
        "version": VERSION, "canonical_packet": canonical, "canonical_packet_sha256": _sha(canonical),
        "variants": variants, "inputs": inputs, "max_calls": len(inputs), "call_timeout_seconds": timeout,
        "run_seconds": len(inputs) * timeout + 120, "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False,
    }
    return packet, panel


def build_packet(database: Path, **options) -> dict:
    return _plan(database, **options)[0]


def _options(packet: dict) -> dict:
    canonical = packet["canonical_packet"]
    return {"panel_id": canonical["panel"]["panel_id"], "route_id": canonical["route"]["route_id"],
            "accepted_commit": canonical["accepted_commit"]}


def _expected_inputs(canonical: dict) -> list:
    """Each pre-registered case once per variant, in canonical order, from the digest-pinned canonical packet."""
    families = SELECTION.get(canonical["panel"]["panel_id"], ())
    items = [item for item in canonical["inputs"] if item["family_id"] in families]
    if not families or {item["family_id"] for item in items} != set(families):
        raise assets.P3Error("invalid_manifest")
    return [(item["case_id"], item["family_id"], item["question_sha256"], variant) for item in items
            for variant in VARIANTS]


def _packet_contract(packet: object) -> dict:
    assets.object_fields(packet, _PACKET_FIELDS, "invalid_manifest")
    canonical, inputs = packet["canonical_packet"], packet["inputs"]
    evaluate._packet_contract(canonical)
    if (packet["version"] != VERSION or packet["canonical_packet_sha256"] != _sha(canonical)
            or packet["evidence_class"] != EVIDENCE_CLASS or packet["promotion_eligible"] is not False
            or not isinstance(inputs, list)
            or [(row.get("case_id"), row.get("family_id"), row.get("question_sha256"), row.get("variant"))
                if isinstance(row, dict) else None for row in inputs] != _expected_inputs(canonical)
            or packet["max_calls"] != len(inputs)
            or packet["call_timeout_seconds"] != canonical["settings"]["call_timeout_seconds"]
            or packet["run_seconds"] != len(inputs) * packet["call_timeout_seconds"] + 120
            or not isinstance(packet["variants"], dict) or list(packet["variants"]) != list(VARIANTS)
            or any(packet["variants"][variant] != _variant_pins(variant) for variant in VARIANTS)):
        raise assets.P3Error("invalid_manifest")
    for row in inputs:
        assets.object_fields(row, _INPUT_FIELDS, "invalid_manifest")
    return packet


def prepare(database: Path, output_path: Path, **options) -> dict:
    if not isinstance(output_path, Path) or output_path.name != "packet.json":
        raise assets.P3Error("invalid_arguments")
    packet = build_packet(database, **options)
    live._write_authorization(output_path, packet)
    return {"version": VERSION, "state": "prepared_not_authorized",
            "packet_sha256": evaluator._pin(output_path)["sha256"], "inputs": len(packet["inputs"]),
            "variants": list(packet["variants"])}


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

def _reading(text: str | None) -> dict | None:
    if text is None:
        return None
    action = protocol.strict_json(text)
    clarification = action.get("clarification") if isinstance(action.get("clarification"), dict) else None
    return {"outcome": action["outcome"], "count_request": action.get("count_request"),
            "clarification_kind": clarification["kind"] if clarification else None,
            "choices": len(clarification["choices"]) if clarification else None}


def _annex(entry: dict, panel: assets.Panel) -> dict | None:
    return evaluate.annex_expectations(entry, panel) if entry.get("annex") is not None else None


def _unassessed(graded: dict) -> bool:
    """The candidate gate's rule: an operational failure is no model result, never a wrong one."""
    return evaluate._gate_unassessed({"status": "completed", "outcome": graded["outcome"],
                                      "operational_error": graded.get("operational_error"),
                                      "runner_error_code": None})


def _annex_verdict(validated: str | None, graded: dict, case: assets.Case, expectations: dict | None) -> str | None:
    if expectations is None:
        return None
    if _unassessed(graded):
        return "unassessed"
    frozen_correct = graded["outcome"] == scoring._SUCCESS[case.expected_branch]
    return evaluate.annexed({"validated_action": validated, "oracle_id": case.oracle_id}, frozen_correct,
                            expectations)


def _summary(rows: list[dict]) -> dict:
    by_variant = {}
    for variant in VARIANTS:
        selected = [row for row in rows if row["variant"] == variant]
        returned = [row for row in selected if row["state"] == "returned"]
        by_variant[variant] = {
            "inputs": len(selected), **{state: sum(row["state"] == state for row in selected) for state in shared.STATES},
            "outcomes": evaluate._tally(row["graded"]["outcome"] for row in returned),
            "annex": evaluate._tally(row["annex"] for row in returned if row["annex"] is not None)}
    return {"inputs": len(rows), "by_variant": by_variant}


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
    entry, _ = shared.pinned_panel(packet["canonical_packet"]["panel"]["panel_id"], panels_path)
    expectations = _annex(entry, panel)
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
             "variant": item["variant"], "state": "not_started", "attempt": 0, "http_attempts": 0,
             "elapsed_seconds": None, "error_code": None, "validated_action": None, "graded": None, "annex": None,
             "reading": None, "mapped": None, "usage": None} for item in packet["inputs"]]
    report = {key: manifest[key] for key in manifest if key != "version"}
    report.update(version=VERSION, status="incomplete", stop_reason=None, evidence_class=EVIDENCE_CLASS,
                  promotion_eligible=False, client_http_attempts=0, possible_in_flight_attempts=0,
                  elapsed_seconds=0.0, results=rows, summary=_summary(rows))
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
        report.update(possible_in_flight_attempts=1, summary=_summary(rows))
        artifacts.persist(report)
        before, call_start, code = (client.http_attempts if client is not None else 0), clock(), None
        try:
            if client is None:
                client = evaluate._admitted_client(packet["canonical_packet"], env_file)
                before = client.http_attempts
                # The same transport check as tools/evaluate.py --live: a route change is an anomaly.
                if client.config.transport_security != packet["canonical_packet"]["transport_security"]:
                    raise assets.P3Error("invalid_configuration")
            wire = messages(item["variant"], case.question)
            if _sha(wire) != item["messages_sha256"]:
                raise assets.P3Error("invalid_manifest")
            remaining = packet["run_seconds"] - (clock() - started)
            if remaining <= 0:
                raise assets.P3Error("panel_budget")
            response = await client.complete(
                wire, timeout_seconds=min(packet["call_timeout_seconds"], remaining),
                json_schema_constraint={"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME,
                                        "schema": variant_schema(item["variant"])})
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
            served = map_back(item["variant"], response.body)
            result = await recipe_model.interpret_recipe_and_execute(
                case.question, database, routing._body_replay_client(served), timeout_seconds=left)
            validated = evaluate._validated_action(result)
            graded = p3_grading.grade(result, panel.oracle_for(case))
            row.update(state="returned", validated_action=validated, graded=graded,
                       annex=_annex_verdict(validated, graded, case, expectations), reading=_reading(validated),
                       mapped=served != response.body, usage=usage)
        except (ModelError, assets.P3Error, smoke.SmokeError) as exc:
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
        report["summary"] = _summary(rows)
        artifacts.persist(report)
        if report["stop_reason"] is not None:
            break
    if report["stop_reason"] is None:
        report.update(status="complete", stop_reason="complete")
    report.update(possible_in_flight_attempts=0, elapsed_seconds=max(0.0, clock() - started), summary=_summary(rows))
    artifacts.persist(report)
    return read_report(output_dir / "report.json", **registries)


# --------------------------------------------------------------------------- readback

def _check_row(row: object, item: dict, case: assets.Case, expectations: dict | None) -> None:
    assets.object_fields(row, _ROW_FIELDS)
    if ((row["case_id"], row["family_id"], row["question_sha256"], row["variant"])
            != (item["case_id"], item["family_id"], item["question_sha256"], item["variant"])
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
        routing._check_graded(row["graded"])
    routing._check_validated_action(row["validated_action"], row["graded"])
    usage = row["usage"]
    if usage is not None and (not isinstance(usage, dict) or set(usage) != set(shared._USAGE_FIELDS) or any(
            value is not None and (type(value) is not int or value < 0) for value in usage.values())):
        raise assets.P3Error("invalid_asset")
    returned = row["state"] == "returned"
    # The annex verdict and the reading are recomputed from the persisted action, never trusted.
    if (row["annex"] != (_annex_verdict(row["validated_action"], row["graded"], case, expectations) if returned
                         else None)
            or row["reading"] != (_reading(row["validated_action"]) if returned else None)
            or row["reading"] is not None and set(row["reading"]) != _READING_FIELDS
            # Only a labels reply can have been mapped back; the flag is recorded, not recomputable.
            or (type(row["mapped"]) is not bool if returned else row["mapped"] is not None)
            or row["mapped"] is True and row["variant"] != "labels"):
        raise assets.P3Error("invalid_asset")
    shape = {"not_started": (0, False, False), "reserved": (1, False, False),
             "returned": (1, True, False), "failed": (1, False, True)}[row["state"]]
    if ((row["attempt"], row["graded"] is not None, row["error_code"] is not None) != shape
            or (usage is not None) != returned
            or not returned and row["validated_action"] is not None
            or row["state"] == "not_started" and (row["http_attempts"] or row["elapsed_seconds"] is not None)
            or returned and (row["http_attempts"] != 1 or row["elapsed_seconds"] is None)
            or row["state"] == "failed" and row["elapsed_seconds"] is None):
        raise assets.P3Error("invalid_asset")


def _check_report(report: dict, manifest: dict, packet: dict, panel: assets.Panel, expectations: dict | None) -> None:
    assets.object_fields(report, _REPORT_FIELDS)
    rows = report["results"]
    if (any(report[key] != manifest[key] for key in _MANIFEST_FIELDS - {"version"})
            or report["version"] != VERSION or report["evidence_class"] != EVIDENCE_CLASS
            or report["promotion_eligible"] is not False or report["status"] not in ("complete", "incomplete")
            or report["stop_reason"] is not None and report["stop_reason"] not in shared.STOPS
            or not isinstance(rows, list) or len(rows) != len(packet["inputs"])):
        raise assets.P3Error("invalid_asset")
    cases = {case.case_id: case for case in panel.cases}
    for row, item in zip(rows, packet["inputs"]):
        _check_row(row, item, cases[item["case_id"]], expectations)
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
            or report["summary"] != _summary(rows)
            or (report["status"] == "complete") != (report["stop_reason"] == "complete")
            or report["status"] == "complete" and any(row["state"] in ("not_started", "reserved") for row in rows)):
        raise assets.P3Error("invalid_asset")


def _compare(report: dict, packet: dict, panel: assets.Panel, expectations: dict | None,
             runs_path: Path | None, candidates_index: Path | None) -> dict:
    """Each row beside the current candidate's own recorded runs of the same bytes on the panel; no verdict."""
    canonical = packet["canonical_packet"]
    panel_id, route_id = canonical["panel"]["panel_id"], canonical["route"]["route_id"]
    baseline = evaluate._same_bytes_runs(panel_id, route_id, canonical["candidate"]["candidate_sha256"],
                                         evaluate.load_runs(runs_path), {}, candidates_index)
    runs_file = evaluate.RUNS if runs_path is None else runs_path
    value = {"run_index_sha256": evaluator._pin(runs_file)["sha256"] if runs_file.exists() else None,
             "baseline_runs": [run["run_id"] for run in baseline], "inputs": [], "refusal": None}
    if not baseline:
        value["refusal"] = "no_baseline"
        return value
    # A clean clone lacks the archives; the comparison is then re-read where they are, never failed.
    if any(not evaluate._location(run["slot"] + "/report.json").is_file() for run in baseline):
        value["refusal"] = "baseline_unavailable"
        return value
    reports = evaluate._archived_reports(baseline)
    # The candidate gate's integrity checks, in routing_upper_bound's order: bytes, inputs, then index agreement.
    target = canonical["candidate"]["candidate_sha256"]
    expected_inputs = (panel_id, canonical["panel"]["assets"], canonical["panel"].get("annex_sha256"),
                       [(item["case_id"], item["question_sha256"]) for item in canonical["inputs"]])
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
    measured = {row["case_id"]: row for row in evaluate._input_classes(reports, expectations)}
    cases = {case.case_id: case for case in panel.cases}
    for row in report["results"]:
        case = cases[row["case_id"]]
        returned = row["state"] == "returned"
        frozen = returned and row["graded"]["outcome"] == scoring._SUCCESS[case.expected_branch]
        verdict = (None if not returned else "unassessed" if _unassessed(row["graded"])
                   else row["annex"] if row["annex"] is not None else "correct" if frozen else "wrong")
        value["inputs"].append({"case_id": row["case_id"], "variant": row["variant"],
                                "baseline_assessed": measured[row["case_id"]]["assessed"],
                                "baseline_correct": measured[row["case_id"]]["correct"],
                                "variant_verdict": verdict})
    return value


def _registered(packet: dict, panel: assets.Panel) -> None:
    """The packet's selection is the registered panel's: its canonical inputs equal the pinned panel's inputs, and
    every row names a registered case with its question and its variant messages."""
    questions = {case.case_id: case.question for case in panel.cases}
    shas = {item["case_id"]: item["question_sha256"] for item in panel.inputs()}
    if packet["canonical_packet"]["inputs"] != panel.inputs() or any(
            row["case_id"] not in questions or shas[row["case_id"]] != row["question_sha256"]
            or _sha(messages(row["variant"], questions[row["case_id"]])) != row["messages_sha256"]
            for row in packet["inputs"]):
        raise assets.P3Error("manifest_drift")


def read_report(path: Path, *, panels_path: Path | None = None, routes_path: Path | None = None,
                runs_path: Path | None = None, candidates_index: Path | None = None) -> dict:
    """Archive verification plus the comparison with the current candidate's runs, recomputed from the index."""
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
    canonical = packet["canonical_packet"]
    # The panel, cases, oracles and annex are pinned against the registry, and the registry against the packet.
    entry, panel = shared.pinned_panel(canonical["panel"]["panel_id"], panels_path)
    if (entry["assets"] != canonical["panel"]["assets"]
            or (entry.get("annex") or {}).get("sha256") != canonical["panel"].get("annex_sha256")):
        raise assets.P3Error("manifest_drift")
    expectations = _annex(entry, panel)
    _registered(packet, panel)
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    _check_report(report, manifest, packet, panel, expectations)
    return {**report, "comparison": _compare(report, packet, panel, expectations, runs_path, candidates_index)}


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
            result["comparison"] = {key: report["comparison"][key] for key in ("baseline_runs", "inputs", "refusal")}
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
