#!/usr/bin/env python3
"""One owner-granted, three-call Compare completion observation; no grading."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import ClassVar

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError, MODEL
from tools import evaluate, p3_assets as assets, p3_eval, p3_live_evidence as live, smoke

ROOT = evaluate.ROOT
VERSION = "compare-completion-diagnostic-v1"
GRANT = "https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855110091"
CASE_IDS = ("dev-A3.en", "dev-C2.zh-TW", "dev-C2.en")
CANDIDATE = "p3-31b-instruction-v3"
PANEL = "p3-dev-matrix-v1"
ROUTE = "litellm-gemma-4-31b"
CALL_SECONDS = 90
RUN_SECONDS = 390
MAX_CALLS = 3
SLOT = ".artifacts/compare-completion-" + hashlib.sha256(GRANT.encode()).hexdigest()[:20]
SHA = re.compile(r"[0-9a-f]{64}\Z")
STATES = ("not_started", "reserved", "returned", "failed")
ERRORS = frozenset({"timeout", "transport_error", "gateway_error", "rate_limited",
                    "auth_failed", "http_configuration", "redirect_blocked", "unsupported_output",
                    "response_too_large", "invalid_response", "unexpected_model", "invalid_input",
                    "input_too_large", "invalid_configuration", "invalid_envelope", "panel_budget",
                    "artifact_io", "artifact_conflict", "interrupted"})
STOPS = frozenset({"complete", "timeout_streak", "network_streak", "anomaly", "budget",
                   "interrupted"})
FINISH = frozenset({"stop", "length", "content_filter", "tool_calls", "function_call"})
ROOT_TYPES = frozenset({"object", "array", "string", "number", "boolean", "null"})
OUTCOMES = frozenset({"request", "clarify", "declined"})
RECIPES = frozenset({"overview", "compare", "breakdown"})
OBS_FIELDS = {"returned_model", "finish_reason", "http_status", "usage", "content_bytes",
              "reasoning_bytes", "json_parse", "json_error_category", "json_error_position",
              "root_type", "known_keys", "unknown_key_count", "outcome", "recipe_id",
              "max_repeated_32_char_block_count"}
ROW_FIELDS = {"case_id", "state", "attempt", "http_attempts", "elapsed_seconds", "error_code", "observation"}
REPORT_FIELDS = {"version", "packet_sha256", "authorization_sha256", "run_slot", "grant",
                 "status", "stop_reason", "client_http_attempts", "possible_in_flight_attempts",
                 "upstream_inference_attempts", "elapsed_seconds", "results", "summary",
                 "evidence_class", "promotion_eligible"}
PACKET_FIELDS = {"version", "canonical_packet", "source_pins", "selected", "case_ids",
                 "candidate_id", "panel_id", "route_id", "canonical_call_timeout_seconds",
                 "diagnostic_call_timeout_seconds", "run_timeout_seconds", "max_calls",
                 "max_output_tokens", "raw_text_persisted", "promotion_eligible", "run_slot"}


class DiagnosticError(Exception):
    def __init__(self, code: str):
        self.code = code if code in ERRORS | {"invalid_asset", "invalid_manifest", "manifest_drift",
                                               "accepted_commit_required", "invalid_arguments"} else "invalid_manifest"
        super().__init__(self.code)


def _fail(code="invalid_asset"):
    raise DiagnosticError(code)


def describe() -> dict:
    return {"version": VERSION, "case_ids": list(CASE_IDS), "candidate_id": CANDIDATE,
            "route_id": ROUTE, "canonical_call_timeout_seconds": 60,
            "diagnostic_call_timeout_seconds": CALL_SECONDS, "run_timeout_seconds": RUN_SECONDS,
            "max_calls": MAX_CALLS, "max_output_tokens": 2048, "raw_text_persisted": False,
            "promotion_eligible": False}


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _check_hash(value):
    if type(value) is not str or SHA.fullmatch(value) is None:
        _fail()


def _bounded_int(value, maximum, *, optional=False):
    if value is None and optional:
        return
    if type(value) is not int or not 0 <= value <= maximum:
        _fail()


def _bounded_seconds(value, maximum, *, optional=False):
    if value is None and optional:
        return
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        _fail()


def _source_pins() -> dict[str, str]:
    pins = {}
    for name in ("tools/evaluate.py", "tools/candidate_registry.py", "tools/p3_completion_diagnostic.py"):
        path = ROOT / name
        smoke._no_symlinks(path)
        pins[name] = _hash(path.read_bytes())
    return pins


def _wire(question: str) -> bytes:
    messages = recipe_model._messages(question, recipe_model.runtime_context())
    constraint, _ = recipe_model._structured_output(recipe_model.output_schema())
    from grepbit.gateway import json_schema_response_format
    return _json({"model": MODEL, "messages": messages, "temperature": 0,
                  "max_tokens": 2048, "stream": False,
                  "response_format": json_schema_response_format(constraint)})


def _questions(panel) -> dict[str, str]:
    result = {case.case_id: case.question for case in panel.cases if case.case_id in CASE_IDS}
    if len(result) != MAX_CALLS:
        _fail("manifest_drift")
    return result


def build_packet(database: Path, accepted_commit: str) -> dict:
    canonical, panel = evaluate.build_packet(database, candidate_id=CANDIDATE, panel_id=PANEL,
                                              route_id=ROUTE, accepted_commit=accepted_commit,
                                              gateway_policies=dict(evaluate.ROUTE_POLICY))
    questions = _questions(panel)
    inputs = {row["case_id"]: row for row in canonical["inputs"]}
    selected = []
    for case_id in CASE_IDS:
        question = questions[case_id]
        if _hash(question.encode()) != inputs[case_id]["question_sha256"]:
            _fail("manifest_drift")
        wire = _wire(question)
        if len(question.encode()) > 4096 or len(wire) > 32768:
            _fail("manifest_drift")
        selected.append({"case_id": case_id, "question_sha256": _hash(question.encode()),
                         "request_sha256": _hash(wire)})
    packet = {**describe(), "canonical_packet": canonical, "source_pins": _source_pins(),
              "selected": selected, "panel_id": PANEL, "run_slot": SLOT}
    _packet(packet)
    return packet


def _packet(packet):
    assets.object_fields(packet, PACKET_FIELDS)
    for key, value in describe().items():
        if packet[key] != value:
            _fail()
    if packet["panel_id"] != PANEL or packet["run_slot"] != SLOT:
        _fail()
    canonical = packet["canonical_packet"]
    evaluate._packet_contract(canonical)
    if (canonical["candidate"]["candidate_id"] != CANDIDATE
            or canonical["panel"]["panel_id"] != PANEL
            or canonical["route"]["route_id"] != ROUTE
            or canonical["route"]["call_timeout_seconds"] != 60
            or canonical["route"]["model"] != MODEL
            or canonical["gateway_policy"] != smoke.policy_attestation(evaluate.ROUTE_POLICY, required=True)):
        _fail()
    if set(packet["source_pins"]) != {"tools/evaluate.py", "tools/candidate_registry.py",
                                      "tools/p3_completion_diagnostic.py"}:
        _fail()
    for value in packet["source_pins"].values():
        _check_hash(value)
    if type(packet["selected"]) is not list or len(packet["selected"]) != MAX_CALLS:
        _fail()
    inputs = {row["case_id"]: row for row in canonical["inputs"]}
    for index, item in enumerate(packet["selected"]):
        assets.object_fields(item, {"case_id", "question_sha256", "request_sha256"})
        if item["case_id"] != CASE_IDS[index] or item["case_id"] not in inputs or item["question_sha256"] != inputs[item["case_id"]]["question_sha256"]:
            _fail()
        _check_hash(item["request_sha256"])


def _read(path: Path) -> dict:
    return assets.read_asset(path)


def _packet_file(path: Path) -> tuple[dict, str]:
    packet = _read(path)
    _packet(packet)
    return packet, p3_eval._pin(path)["sha256"]


def prepare(database: Path, packet_path: Path, *, accepted_commit: str) -> dict:
    packet = build_packet(database, accepted_commit)
    if packet_path.name != "packet.json":
        _fail("invalid_arguments")
    live._write_authorization(packet_path, packet)
    return {"version": VERSION, "state": "prepared_not_authorized", "packet_sha256": p3_eval._pin(packet_path)["sha256"],
            "run_slot": SLOT, "selected": packet["selected"]}


def bind_authorization(packet_path: Path, output_path: Path, reference: str) -> dict:
    _, packet_sha = _packet_file(packet_path)
    if reference != GRANT or output_path.name != "authorization.json":
        _fail("invalid_arguments")
    value = {"version": VERSION, "packet_sha256": packet_sha,
             "owner_authorization_reference": GRANT, "run_slot": SLOT}
    live._write_authorization(output_path, value)
    return value


def _authorization(value, packet_sha):
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"})
    if (value["version"] != VERSION or value["packet_sha256"] != packet_sha
            or value["owner_authorization_reference"] != GRANT or value["run_slot"] != SLOT):
        _fail()


@dataclass(frozen=True)
class DiagnosticGatewayConfig(GatewayConfig):
    max_call_timeout_seconds: ClassVar[float] = CALL_SECONDS


class DiagnosticGatewayClient(GatewayClient):
    def __init__(self, config: DiagnosticGatewayConfig, expected_sha: str, **kwargs):
        super().__init__(config, **kwargs)
        self.expected_sha = expected_sha

    async def _post_json(self, body: bytes, timeout_seconds: float):
        if _hash(body) != self.expected_sha:
            raise ModelError("invalid_input")
        return await super()._post_json(body, timeout_seconds)


def _client(env_file: Path, expected_sha: str) -> DiagnosticGatewayClient:
    smoke._no_symlinks(env_file)
    config = DiagnosticGatewayConfig.from_env(env_file=env_file)
    if config.model != MODEL or config.transport_security != "unencrypted_http":
        _fail("invalid_configuration")
    return DiagnosticGatewayClient(config, expected_sha)


def _empty_row(case_id: str) -> dict:
    return {"case_id": case_id, "state": "not_started", "attempt": 0, "http_attempts": 0,
            "elapsed_seconds": None, "error_code": None, "observation": None}


def _summary(rows: list[dict]) -> dict:
    return {"selected": MAX_CALLS, "reserved": sum(row["state"] == "reserved" for row in rows),
            "returned": sum(row["state"] == "returned" for row in rows),
            "failed": sum(row["state"] == "failed" for row in rows)}


def _new_report(packet_sha: str, auth_sha: str) -> dict:
    rows = [_empty_row(case_id) for case_id in CASE_IDS]
    return {"version": VERSION, "packet_sha256": packet_sha, "authorization_sha256": auth_sha,
            "run_slot": SLOT, "grant": GRANT, "status": "incomplete", "stop_reason": None,
            "evidence_class": "diagnostic_observation", "promotion_eligible": False,
            "client_http_attempts": 0, "possible_in_flight_attempts": 0,
            "upstream_inference_attempts": None, "elapsed_seconds": 0.0,
            "results": rows, "summary": _summary(rows)}


def _persist(artifacts: smoke._Artifacts, report: dict) -> None:
    report["summary"] = _summary(report["results"])
    artifacts.persist(report)


def _root_type(value):
    if value is None: return "null"
    if isinstance(value, dict): return "object"
    if isinstance(value, list): return "array"
    if isinstance(value, str): return "string"
    if isinstance(value, bool): return "boolean"
    return "number"


def _repetition(value: str) -> int:
    # Bounded O(n) rolling observation; only numeric counts leave memory.
    positions: dict[str, list[int]] = {}
    maximum = 0
    for index in range(max(0, len(value) - 31)):
        block = value[index:index + 32]
        prior = positions.get(block)
        if prior is None:
            positions[block] = [index, 1]
        elif index - prior[0] >= 32:
            prior[0] = index
            prior[1] += 1
            maximum = max(maximum, prior[1])
    return maximum


def _usage(value):
    result = dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"))
    if value is None:
        return result
    if not isinstance(value, dict):
        _fail("invalid_envelope")
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if key in value and value[key] is not None:
            if type(value[key]) is not int or not 0 <= value[key] <= 1_000_000:
                _fail("invalid_envelope")
            result[key] = value[key]
    if result["completion_tokens"] is not None and result["completion_tokens"] > 2048:
        _fail("invalid_envelope")
    details = value.get("completion_tokens_details")
    if details is not None:
        if not isinstance(details, dict):
            _fail("invalid_envelope")
        if "reasoning_tokens" in details and details["reasoning_tokens"] is not None:
            if type(details["reasoning_tokens"]) is not int or not 0 <= details["reasoning_tokens"] <= 1_000_000:
                _fail("invalid_envelope")
            result["reasoning_tokens"] = details["reasoning_tokens"]
    return result


def observe(raw: bytes, http_status: int) -> dict:
    if type(raw) is not bytes or len(raw) > 131072:
        _fail("invalid_envelope")
    try:
        envelope = model.strict_json(raw)
    except (ModelError, UnicodeError, RecursionError):
        _fail("invalid_envelope")
    if (not isinstance(envelope, dict) or envelope.get("model") != MODEL
            or not isinstance(envelope.get("choices"), list) or len(envelope["choices"]) != 1):
        _fail("invalid_envelope")
    choice = envelope["choices"][0]
    if (not isinstance(choice, dict) or type(choice.get("index")) is not int or choice["index"] != 0
            or type(choice.get("finish_reason")) is not str or choice["finish_reason"] not in FINISH):
        _fail("invalid_envelope")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        _fail("invalid_envelope")
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    alternate_reasoning = message.get("reasoning")
    if (content is not None and not isinstance(content, str)
            or reasoning is not None and not isinstance(reasoning, str)
            or alternate_reasoning is not None and not isinstance(alternate_reasoning, str)):
        _fail("invalid_envelope")
    if content is None and reasoning is None and alternate_reasoning is None:
        _fail("invalid_envelope")
    parse = "absent"
    category = position = root_type = outcome = recipe_id = None
    known_keys: list[str] = []
    unknown_count = 0
    repetition = 0
    if content is not None:
        repetition = _repetition(content)
        try:
            parsed = json.loads(content, object_pairs_hook=model._pairs,
                                parse_constant=model._nonfinite, parse_float=model._float)
            model.canonical_json(parsed).encode("utf-8")
        except json.JSONDecodeError as exc:
            parse, category, position = "error", "syntax", min(exc.pos, 131072)
        except (ValueError, UnicodeError, RecursionError):
            parse, category, position = "error", "invalid_value", None
        else:
            parse, root_type = "valid", _root_type(parsed)
            if isinstance(parsed, dict):
                known = {"outcome", "recipe_id", "recipe_version", "request", "kind", "choices"}
                known_keys = sorted(set(parsed) & known)
                unknown_count = len(set(parsed) - known)
                if type(parsed.get("outcome")) is str and parsed["outcome"] in OUTCOMES:
                    outcome = parsed["outcome"]
                if type(parsed.get("recipe_id")) is str and parsed["recipe_id"] in RECIPES:
                    recipe_id = parsed["recipe_id"]
    return {"returned_model": MODEL, "finish_reason": choice["finish_reason"],
            "http_status": http_status, "usage": _usage(envelope.get("usage")),
            "content_bytes": None if content is None else len(content.encode()),
            "reasoning_bytes": (None if reasoning is None and alternate_reasoning is None else
                                len((reasoning or "").encode()) + len((alternate_reasoning or "").encode())),
            "json_parse": parse, "json_error_category": category,
            "json_error_position": position, "root_type": root_type,
            "known_keys": known_keys, "unknown_key_count": unknown_count,
            "outcome": outcome, "recipe_id": recipe_id,
            "max_repeated_32_char_block_count": repetition}


def _observation(value):
    assets.object_fields(value, OBS_FIELDS)
    if (value["returned_model"] != MODEL or type(value["finish_reason"]) is not str
            or value["finish_reason"] not in FINISH or value["http_status"] != 200):
        _fail()
    usage = assets.object_fields(value["usage"], {"prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"})
    for item in usage.values(): _bounded_int(item, 1_000_000, optional=True)
    if usage["completion_tokens"] is not None and usage["completion_tokens"] > 2048:
        _fail()
    for key in ("content_bytes", "reasoning_bytes"):
        _bounded_int(value[key], 131072, optional=True)
    if value["content_bytes"] is None and value["reasoning_bytes"] is None:
        _fail()
    if value["json_parse"] not in ("absent", "error", "valid"):
        _fail()
    if value["json_error_category"] not in (None, "syntax", "invalid_value"):
        _fail()
    _bounded_int(value["json_error_position"], 131072, optional=True)
    if value["root_type"] not in (None, *ROOT_TYPES):
        _fail()
    if (value["json_parse"] == "valid") != (value["root_type"] is not None):
        _fail()
    if value["json_parse"] == "absent":
        if (value["content_bytes"] is not None or value["json_error_category"] is not None
                or value["json_error_position"] is not None):
            _fail()
    elif value["json_parse"] == "error":
        if value["content_bytes"] is None or value["json_error_category"] is None:
            _fail()
        if (value["json_error_category"] == "syntax") != (value["json_error_position"] is not None):
            _fail()
    elif (value["content_bytes"] is None or value["json_error_category"] is not None
          or value["json_error_position"] is not None):
        _fail()
    if (not isinstance(value["known_keys"], list)
            or any(type(key) is not str or key not in {"outcome", "recipe_id", "recipe_version", "request", "kind", "choices"}
                   for key in value["known_keys"])
            or value["known_keys"] != sorted(set(value["known_keys"]))):
        _fail()
    _bounded_int(value["unknown_key_count"], 131072)
    if value["outcome"] not in (None, *OUTCOMES) or value["recipe_id"] not in (None, *RECIPES):
        _fail()
    if value["root_type"] != "object" and (value["known_keys"] or value["unknown_key_count"]
                                          or value["outcome"] is not None or value["recipe_id"] is not None):
        _fail()
    if (value["outcome"] is not None and "outcome" not in value["known_keys"]
            or value["recipe_id"] is not None and "recipe_id" not in value["known_keys"]):
        _fail()
    _bounded_int(value["max_repeated_32_char_block_count"], 4096)
    if (value["content_bytes"] is None and value["max_repeated_32_char_block_count"] != 0
            or value["content_bytes"] is not None and value["max_repeated_32_char_block_count"] > value["content_bytes"] // 32):
        _fail()


def _report(report, packet_sha, auth_sha):
    assets.object_fields(report, REPORT_FIELDS)
    if (report["version"] != VERSION or report["packet_sha256"] != packet_sha
            or report["authorization_sha256"] != auth_sha or report["run_slot"] != SLOT
            or report["grant"] != GRANT or report["status"] not in ("incomplete", "complete")
            or report["stop_reason"] not in (None, *STOPS)
            or report["upstream_inference_attempts"] is not None
            or report["evidence_class"] != "diagnostic_observation"
            or report["promotion_eligible"] is not False):
        _fail()
    _bounded_seconds(report["elapsed_seconds"], 86400)
    _bounded_int(report["client_http_attempts"], MAX_CALLS)
    _bounded_int(report["possible_in_flight_attempts"], MAX_CALLS)
    rows = report["results"]
    if not isinstance(rows, list) or len(rows) != MAX_CALLS:
        _fail()
    reserved = failed = returned = 0
    seen_pending = False
    for index, row in enumerate(rows):
        assets.object_fields(row, ROW_FIELDS)
        if row["case_id"] != CASE_IDS[index] or row["state"] not in STATES:
            _fail()
        _bounded_int(row["attempt"], 1)
        _bounded_int(row["http_attempts"], 1)
        _bounded_seconds(row["elapsed_seconds"], 86400, optional=True)
        if row["state"] == "not_started":
            seen_pending = True
            if row["attempt"] or row["http_attempts"] or row["elapsed_seconds"] is not None or row["error_code"] is not None or row["observation"] is not None:
                _fail()
        else:
            if seen_pending or row["attempt"] != 1:
                _fail()
            if row["state"] == "reserved":
                reserved += 1
                seen_pending = True
                if row["observation"] is not None or row["error_code"] is not None or row["elapsed_seconds"] is not None:
                    _fail()
            else:
                if row["elapsed_seconds"] is None:
                    _fail()
                if row["state"] == "returned":
                    returned += 1
                    if row["error_code"] is not None or row["http_attempts"] != 1: _fail()
                    _observation(row["observation"])
                else:
                    failed += 1
                    if (type(row["error_code"]) is not str or row["error_code"] not in ERRORS
                            or row["observation"] is not None): _fail()
    if reserved > 1:
        _fail()
    if (report["client_http_attempts"] != sum(row["http_attempts"] for row in rows)
            or report["possible_in_flight_attempts"] != reserved
            or report["summary"] != _summary(rows)):
        _fail()
    if (report["status"] == "complete") != (report["stop_reason"] == "complete"):
        _fail()
    if report["status"] == "complete" and (returned + failed != MAX_CALLS or reserved):
        _fail()
    timeout_streak = network_streak = 0
    required_stop = None
    for row in rows:
        if required_stop is not None and row["state"] != "not_started":
            _fail()
        if row["state"] not in ("returned", "failed"):
            continue
        code = row["error_code"]
        timeout_streak = timeout_streak + 1 if code == "timeout" else 0
        network_streak = network_streak + 1 if code in ("transport_error", "gateway_error", "rate_limited") else 0
        if code in ("timeout", "transport_error", "gateway_error", "rate_limited") and row["http_attempts"] != 1:
            _fail()
        if code == "panel_budget":
            required_stop = "budget"
        elif code is not None and code not in ("timeout", "transport_error", "gateway_error", "rate_limited"):
            required_stop = "anomaly"
        elif timeout_streak >= 2:
            required_stop = "timeout_streak"
        elif network_streak >= 2:
            required_stop = "network_streak"
    if required_stop is not None and report["stop_reason"] != required_stop:
        if report["stop_reason"] != "budget" or report["elapsed_seconds"] < RUN_SECONDS:
            _fail()
    if required_stop is None and report["stop_reason"] in ("timeout_streak", "network_streak"):
        _fail()
    if report["status"] == "complete" and report["elapsed_seconds"] >= RUN_SECONDS:
        _fail()
    if report["stop_reason"] == "budget" and report["elapsed_seconds"] < RUN_SECONDS:
        _fail()
    if report["stop_reason"] == "interrupted" and reserved != 1:
        _fail()


def read_report(path: Path) -> dict:
    if path.name != "report.json" or path.parent.resolve() != ROOT / SLOT:
        _fail()
    smoke._no_symlinks(path.parent)
    names = {item.name for item in path.parent.iterdir()}
    fixed = {"manifest.json", "packet.json", "authorization.json", "report.json"}
    checkpoints = sorted(names - fixed)
    if (not fixed <= names or not checkpoints or len(checkpoints) > 12
            or checkpoints != [f"checkpoint-{index:04d}.json" for index in range(len(checkpoints))]):
        _fail()
    for name in names:
        smoke._no_symlinks(path.parent / name)
    packet, packet_sha = _packet_file(path.parent / "packet.json")
    if not evaluate._same(packet, _read(path.parent / "manifest.json")):
        _fail()
    auth_path = path.parent / "authorization.json"
    authorization = _read(auth_path)
    _authorization(authorization, packet_sha)
    auth_sha = p3_eval._pin(auth_path)["sha256"]
    report = _read(path)
    _report(report, packet_sha, auth_sha)
    previous = None
    for name in checkpoints:
        snapshot = _read(path.parent / name)
        _report(snapshot, packet_sha, auth_sha)
        if previous is not None:
            for before, after in zip(previous["results"], snapshot["results"]):
                if (before["state"] in ("returned", "failed") and before != after
                        or before["state"] == "reserved" and after["state"] == "not_started"):
                    _fail()
            if snapshot["client_http_attempts"] < previous["client_http_attempts"]:
                _fail()
        previous = snapshot
    if not evaluate._same(previous, report):
        _fail()
    return report


async def run_live(database: Path, packet_path: Path, authorization_path: Path, *,
                   accepted_commit: str, env_file: Path, clock=time.monotonic,
                   client_factory=_client) -> dict:
    packet, packet_sha = _packet_file(packet_path)
    authorization = _read(authorization_path)
    _authorization(authorization, packet_sha)
    auth_sha = p3_eval._pin(authorization_path)["sha256"]
    # All drift checks precede grant consumption and credential reads.
    current = build_packet(database, accepted_commit)
    if not evaluate._same(packet, current):
        _fail("manifest_drift")
    panel = evaluate.load_panel_entry(PANEL, database)[1]
    questions = _questions(panel)
    run_dir = ROOT / SLOT
    artifacts = smoke._Artifacts(run_dir, packet)
    # Manifest is the packet; preserve exact input files as exclusive local copies.
    artifacts._write("packet.json", packet)
    artifacts._write("authorization.json", authorization)
    report = _new_report(packet_sha, auth_sha)
    _persist(artifacts, report)
    started = clock()
    timeout_streak = network_streak = 0
    for index, selected in enumerate(packet["selected"]):
        elapsed = clock() - started
        if elapsed >= RUN_SECONDS:
            report.update(stop_reason="budget", elapsed_seconds=elapsed)
            _persist(artifacts, report)
            break
        try:
            unchanged = evaluate._same(packet, build_packet(database, accepted_commit))
        except Exception:
            unchanged = False
        if not unchanged:
            report.update(stop_reason="anomaly", elapsed_seconds=clock() - started)
            _persist(artifacts, report)
            break
        # Each reservation is durable before a constructor may inspect credentials.
        row = report["results"][index]
        row.update(state="reserved", attempt=1)
        report["possible_in_flight_attempts"] = 1
        report["elapsed_seconds"] = elapsed
        _persist(artifacts, report)
        client = None
        call_start = clock()
        try:
            smoke._no_symlinks(env_file)
            client = client_factory(env_file, selected["request_sha256"])
            if (client.config.model != MODEL
                    or client.config.transport_security != packet["canonical_packet"]["transport_security"]
                    or client.http_attempts != 0):
                raise DiagnosticError("invalid_configuration")
            if clock() - started >= RUN_SECONDS:
                raise DiagnosticError("panel_budget")
            constraint, _ = recipe_model._structured_output(recipe_model.output_schema())
            messages = recipe_model._messages(questions[selected["case_id"]], recipe_model.runtime_context())
            remaining = RUN_SECONDS - (clock() - started)
            if remaining <= 0:
                raise DiagnosticError("panel_budget")
            response = await client.complete(messages,
                                             timeout_seconds=min(CALL_SECONDS, remaining),
                                             json_schema_constraint=constraint)
            observation = observe(response.body, response.status_code)
            row.update(state="returned", observation=observation)
            timeout_streak = network_streak = 0
        except ModelError as exc:
            row.update(state="failed", error_code=exc.code)
            timeout_streak = timeout_streak + 1 if exc.code == "timeout" else 0
            network_streak = network_streak + 1 if exc.code in ("transport_error", "gateway_error", "rate_limited") else 0
            if exc.code not in ("timeout", "transport_error", "gateway_error", "rate_limited"):
                report["stop_reason"] = "anomaly"
        except DiagnosticError as exc:
            row.update(state="failed", error_code=exc.code)
            report["stop_reason"] = "budget" if exc.code == "panel_budget" else "anomaly"
        except smoke.SmokeError as exc:
            row.update(state="failed", error_code=exc.code)
            report["stop_reason"] = "anomaly"
        except (KeyboardInterrupt, asyncio.CancelledError):
            row["http_attempts"] = client.http_attempts if client is not None else 0
            report["client_http_attempts"] += row["http_attempts"]
            report.update(stop_reason="interrupted", elapsed_seconds=clock() - started)
            _persist(artifacts, report)
            raise
        row["elapsed_seconds"] = max(0, clock() - call_start)
        row["http_attempts"] = client.http_attempts if client is not None else 0
        report["client_http_attempts"] += row["http_attempts"]
        report["possible_in_flight_attempts"] = 0
        report["elapsed_seconds"] = max(0, clock() - started)
        if timeout_streak >= 2: report["stop_reason"] = "timeout_streak"
        if network_streak >= 2: report["stop_reason"] = "network_streak"
        if report["elapsed_seconds"] >= RUN_SECONDS: report["stop_reason"] = "budget"
        _persist(artifacts, report)
        if report["stop_reason"] is not None:
            break
    final_elapsed = max(0, clock() - started)
    if final_elapsed >= RUN_SECONDS:
        report["stop_reason"] = "budget"
    elif report["stop_reason"] is None:
        report["status"] = "complete"
        report["stop_reason"] = "complete"
    report["elapsed_seconds"] = final_elapsed
    _persist(artifacts, report)
    published_elapsed = max(0, clock() - started)
    if published_elapsed >= RUN_SECONDS and report["status"] == "complete":
        report.update(status="incomplete", stop_reason="budget", elapsed_seconds=published_elapsed)
        _persist(artifacts, report)
    return read_report(run_dir / "report.json")


def main(argv=None) -> int:
    parser = p3_eval._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("describe", "prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("db", "packet", "authorization", "output", "env-file", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        allowed = ({"describe"} if args.describe else
                   {"prepare", "db", "output", "accepted_commit"} if args.prepare else
                   {"bind_authorization", "packet", "output", "owner_authorization_reference"} if args.bind_authorization else
                   {"live", "db", "packet", "authorization", "accepted_commit", "env_file"} if args.live else
                   {"report", "report_path"})
        if present != allowed: _fail("invalid_arguments")
        if args.describe: result = describe()
        elif args.prepare: result = prepare(args.db, args.output, accepted_commit=args.accepted_commit)
        elif args.bind_authorization: result = bind_authorization(args.packet, args.output, args.owner_authorization_reference)
        elif args.live: result = asyncio.run(run_live(args.db, args.packet, args.authorization,
                                                       accepted_commit=args.accepted_commit, env_file=args.env_file))
        else: result = read_report(args.report_path)
        print(model.canonical_json(result if args.describe or args.prepare or args.bind_authorization else
                                   {key: result[key] for key in ("version", "status", "stop_reason", "client_http_attempts",
                                                                    "possible_in_flight_attempts", "evidence_class",
                                                                    "promotion_eligible", "summary")}))
        return 0 if result.get("status", "complete") == "complete" else 1
    except (DiagnosticError, assets.P3Error, smoke.SmokeError, ModelError) as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, LookupError, RecursionError):
        print('{"status":"incomplete","error_code":"invalid_manifest"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
