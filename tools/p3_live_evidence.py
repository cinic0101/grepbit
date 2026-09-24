"""Private shared live evidence projection and archived accounting; no execution admission."""
import asyncio
from copy import deepcopy
from pathlib import Path
import json
import math
import os
import re

from grepbit import model
from grepbit.gateway import _ERRORS, _expected_alias
from grepbit.recipe_model import INVALID_REQUEST_REASONS
from tools import p3_assets as assets, p3_eval as evaluator, p3_grading, p3_admission as admission, smoke

_TRANSPORT = ("unencrypted_http", "tls_verification_enabled")
_PHASES = ("not_started", "reserved", "invoked", "returned", "graded")
_SLOTS = frozenset(slot for slots in assets.ROLES.values() for slot in slots)
_CODES = assets.SAFE_CODES | set(_ERRORS)
_EVIDENCE_FIELDS = {
    "client_http_attempts", "elapsed_seconds", "requested_model", "returned_model", "http_status",
    "transport_security", "usage", "stages", "error_code", "stop_reason", "invalid_request_reason",
}


def _same(left, right):
    return model.canonical_json(left) == model.canonical_json(right)


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise assets.P3Error("invalid_manifest")


def _write_authorization(output_path, value):
    """Exclusive durable binding after the purpose-specific caller validated it."""
    smoke._no_symlinks(output_path)
    try:
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise assets.P3Error("artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io") from None


def _number(value, *, integer=False, maximum=None, optional=True):
    if value is None and not optional:
        raise assets.P3Error("invalid_asset")
    if value is not None and (type(value) not in ((int,) if integer else (int, float))
                              or not math.isfinite(value) or value < 0 or maximum is not None and value > maximum):
        raise assets.P3Error("invalid_asset")


def _evidence(value: dict, *, expected_model=None, requested_profile=None) -> dict:
    """Closed projection only; no proposal, pack, text, choices, facts or bodies."""
    if not isinstance(value, dict):
        raise assets.P3Error("invalid_asset")
    result = {key: deepcopy(value[key]) for key in _EVIDENCE_FIELDS if key in value}
    for key in ("error_code", "stop_reason"):
        if result.get(key) is not None and result[key] not in _CODES:
            raise assets.P3Error("invalid_asset")
    # Historical evidence has no reason. A reason needs the matching failure and
    # the stage record that failure implies: parsed JSON, request validation
    # failed, native execution never run. Contradictory archives fail closed.
    reason = result.get("invalid_request_reason")
    if reason is not None:
        stages = result.get("stages")
        if (reason not in INVALID_REQUEST_REASONS or result.get("error_code") != "invalid_request"
                or not isinstance(stages, dict) or stages.get("json_parse") != "passed"
                or stages.get("request_validation") != "failed"
                or stages.get("kernel_execution") != "not_run"):
            raise assets.P3Error("invalid_asset")
    if requested_profile is not None:
        if (expected_model is not None or type(requested_profile) is not str
                or not requested_profile or "returned_model" not in result
                or result.get("requested_model") != requested_profile
                or result.get("returned_model") is not None):
            raise assets.P3Error("invalid_asset")
    else:
        alias = _expected_alias(expected_model)
        for key in ("requested_model", "returned_model"):
            if result.get(key) not in (None, alias):
                raise assets.P3Error("invalid_asset")
    if result.get("transport_security") not in (None, *_TRANSPORT):
        raise assets.P3Error("invalid_asset")
    _number(result.get("elapsed_seconds"))
    _number(result.get("client_http_attempts"), integer=True, maximum=1)
    status = result.get("http_status")
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise assets.P3Error("invalid_asset")
    if "usage" in result:
        usage = assets.object_fields(result["usage"], {"prompt_tokens", "completion_tokens", "total_tokens"})
        for count in usage.values():
            _number(count, integer=True, maximum=2**63 - 1)
    if "stages" in result:
        stages = assets.object_fields(result["stages"], set(model.STAGES))
        if any(stage not in ("not_run", "passed", "failed") for stage in stages.values()):
            raise assets.P3Error("invalid_asset")
    return result


def _check_grade(row):
    if (row["version"] != p3_grading.VERSION or row["outcome"] not in (None, *assets.OUTCOMES)
            or row["actual_action"] not in (None, *assets.BRANCHES)
            or type(row["checked_wrong"]) is not bool or row["pack_status"] not in (None, "complete", "partial")
            or set(row["layers"]) != set(p3_grading.LAYERS)
            or any(v not in ("passed", "failed", "not_assessed") for v in row["layers"].values())
            or not isinstance(row["diagnostics"], list)
            or not isinstance(row["missing_required_slots"], list)
            or any(slot not in _SLOTS for slot in row["missing_required_slots"])):
        raise assets.P3Error("invalid_asset")
    if row["actual_signature"] is not None:
        _hash(row["actual_signature"])
    for diagnostic in row["diagnostics"]:
        assets.object_fields(diagnostic, {"layer", "reason"})
        if diagnostic["layer"] not in (*p3_grading.LAYERS, "agreement") or diagnostic["reason"] != "invalid_native_shape":
            raise assets.P3Error("invalid_asset")
    for key in ("operational_error", "error_code", "runner_error_code"):
        if row[key] is not None and row[key] not in _CODES | {"missing_result"}:
            raise assets.P3Error("invalid_asset")


class _PerInputClient:
    """One-use delegator; shared GatewayClient still owns HTTP/config/security."""
    def __init__(self, client, maximum=28):
        self.client, self.used, self.before = client, False, evaluator._attempts(client)
        self.maximum = maximum

    @property
    def config(self):
        return self.client.config

    @property
    def http_attempts(self):
        return self.client.http_attempts

    def safe_export(self, value):
        return self.client.safe_export(value)

    async def complete(self, *args, **kwargs):
        if self.used or self.http_attempts != self.before or self.http_attempts >= self.maximum:
            raise assets.P3Error("attempt_budget")
        self.used = True
        return await self.client.complete(*args, **kwargs)


class _LiveEvidence:
    origin = "live"
    maximum = 28
    summarize = staticmethod(evaluator._summarize)

    def __init__(self, expected_model=None, *, requested_profile=None):
        self.expected_model = expected_model
        self.requested_profile = requested_profile
        if requested_profile is None:
            _expected_alias(expected_model)
        elif expected_model is not None or type(requested_profile) is not str or not requested_profile:
            raise assets.P3Error("invalid_configuration")

    def project(self, evidence, client):
        return evaluator._safe(_evidence(evidence, expected_model=self.expected_model,
                                         requested_profile=self.requested_profile), client)

    def timeout_identity(self):
        # The outer deadline has no response to inspect, but its admitted route is known.
        return ({"requested_model": self.requested_profile, "returned_model": None}
                if self.requested_profile is not None else {})

    def invocation_client(self, client):
        return _PerInputClient(client, self.maximum)

    def check_report(self, report):
        for row in report["results"]:
            _check_grade(row)
            if row["evidence"] is not None and not _same(
                    _evidence(row["evidence"], expected_model=self.expected_model,
                              requested_profile=self.requested_profile), row["evidence"]):
                raise assets.P3Error("leakage_risk")


def _validate_report(report, manifest, expected, inputs, *, maximum, transport_security,
                     summarize=evaluator._summarize, expected_model=None, requested_profile=None):
    """Shared safe lifecycle/accounting validation, never current source/config access."""
    if (set(report) != set(expected) | {"summary"} or report["report_version"] != expected["report_version"]
            or report["manifest_sha256"] != assets.digest(manifest)
            or report["status"] not in ("incomplete", "complete") or report["origin"] != "live"
            or report["upstream_inference_attempts"] is not None
            or report["transport_security"] not in (None, transport_security)
            or len(report["results"]) != maximum):
        raise assets.P3Error("invalid_asset")
    for key in ("panel_id", "panel_kind", "preparation", "allocation_policy", "gateway_policy",
                "owner_authorization_reference", "scope"):
        if report[key] != expected[key]:
            raise assets.P3Error("invalid_asset")
    for key in ("stop_reason", "error_code"):
        if report[key] is not None and report[key] not in assets.SAFE_CODES:
            raise assets.P3Error("invalid_asset")
    _number(report["elapsed_seconds"])
    for row, shape, metadata in zip(report["results"], expected["results"], inputs):
        if (set(row) != set(shape) or not _same({key: row[key] for key in metadata}, metadata)
                or row["phase"] not in _PHASES or row["status"] not in ("pending", "in_progress", "completed", "not_run")
                or type(row["runtime_invoked"]) is not bool or type(row["attempt_may_be_in_flight"]) is not bool
                or row["attempt_evidence_status"] not in evaluator._ATTEMPT_STATES
                or row["not_run_reason"] is not None and row["not_run_reason"] not in assets.SAFE_CODES | {"panel_complete"}
                or row["status"] == "completed" and (
                    row["phase"] != "graded" or not row["runtime_invoked"] or row["outcome"] in (None, "not_run"))
                or row["status"] in ("pending", "not_run") and row["phase"] != "not_started"
                or row["status"] == "in_progress" and row["phase"] not in ("reserved", "invoked", "returned")
                or row["phase"] in ("invoked", "returned", "graded") and not row["runtime_invoked"]
                or row["phase"] == "reserved" and (row["runtime_invoked"] or row["client_http_attempts"] != 0)
                or row["phase"] in ("returned", "graded") and row["attempt_may_be_in_flight"]
                or row["phase"] in ("reserved", "invoked") and not row["attempt_may_be_in_flight"]
                or row["phase"] == "not_started" and (row["runtime_invoked"] or row["client_http_attempts"] != 0
                                                       or row["evidence"] is not None)
                or row["attempt_evidence_status"] == "matched" and (
                    row["runtime_http_attempts"] is None or row["runtime_http_attempts"] != row["client_http_attempts"]
                    or not isinstance(row["evidence"], dict)
                    or row["evidence"].get("client_http_attempts") != row["runtime_http_attempts"])):
            raise assets.P3Error("invalid_asset")
        _number(row["client_http_attempts"], integer=True, maximum=1)
        _number(row["runtime_http_attempts"], integer=True, maximum=1)
    _LiveEvidence(expected_model, requested_profile=requested_profile).check_report(report)
    counts = [row["client_http_attempts"] for row in report["results"]]
    total = None if None in counts else sum(counts)
    if (report["client_http_attempts"] != total or report["live_model_attempts"] != total
            or report["runtime_invocations"] != sum(row["runtime_invoked"] for row in report["results"])
            or report["possible_in_flight_attempts"] != sum(row["attempt_may_be_in_flight"] for row in report["results"])
            or report["possible_in_flight_attempts"] not in (0, 1)):
        raise assets.P3Error("invalid_asset")
    for key in ("client_http_attempts", "live_model_attempts", "runtime_invocations", "attempt_budget_used"):
        _number(report[key], integer=True, maximum=maximum,
                optional=key in ("client_http_attempts", "live_model_attempts"))
    _number(report["possible_in_flight_attempts"], integer=True, maximum=1, optional=False)
    for key in ("network_failure_streak", "timeout_streak"):
        _number(report[key], integer=True, maximum=2, optional=False)
    # An interrupted reservation may have zero observed sends but consumes one
    # possible attempt. Unknown client counters remain unknown, not zero.
    reserved_budget = sum(max(row["client_http_attempts"] or 0, int(row["attempt_may_be_in_flight"]))
                          for row in report["results"])
    if (total is not None and report["attempt_budget_used"] != reserved_budget
            or report["status"] == "complete" and (
                report["stop_reason"] is not None or report["error_code"] is not None or total is None
                or report["runtime_invocations"] != maximum or report["possible_in_flight_attempts"] != 0
                or any(row["status"] != "completed" or row["attempt_evidence_status"] != "matched"
                       or row["runner_error_code"] is not None for row in report["results"]))):
        raise assets.P3Error("invalid_asset")
    summary = report["summary"]
    summarize(report)
    if not _same(summary, report["summary"]):
        raise assets.P3Error("invalid_asset")


async def _run_live(database, output_dir, *, packet_path, authorization_path, accepted_commit,
                    env_file, gateway_policies, clock, contract):
    """Private bootstrap for separately admitted callers, never a CLI policy switch."""
    started = clock()
    # Both envelopes and all source/DB/freeze gates precede any credential access.
    packet_pin = evaluator._pin(packet_path)
    authorization = contract._authorization(assets.read_asset(authorization_path), packet_pin["sha256"])
    validate_run_slot = getattr(contract, "_validate_run_slot", None)
    if validate_run_slot is not None:
        validate_run_slot(authorization, output_dir)
    authorization_pin = evaluator._pin(authorization_path)
    packet, panel = contract.validate_packet(packet_path, database, accepted_commit=accepted_commit)
    if (smoke.policy_attestation(gateway_policies, required=True) != packet["gateway_policy"]
            or not isinstance(env_file, Path)):
        raise assets.P3Error("invalid_configuration")
    manifest = contract._manifest(packet, packet_pin["sha256"], authorization, authorization_pin["sha256"])
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = contract._report(manifest, packet)
    expected_model = contract._expected_model(packet)
    policy = contract._LiveEvidence(expected_model)
    entries = contract._entries(panel, packet)
    evaluator._persist(artifacts, report, None, summarize=policy.summarize)
    client = None

    def validate():
        if (evaluator._pin(packet_path) != packet_pin or evaluator._pin(authorization_path) != authorization_pin
                or not _same(assets.read_asset(authorization_path), authorization)
                or evaluator._pin(output_dir / "packet.json")["sha256"] != packet_pin["sha256"]
                or evaluator._pin(output_dir / "authorization.json")["sha256"] != authorization_pin["sha256"]):
            raise assets.P3Error("manifest_drift")
        current, current_panel = contract.validate_packet(packet_path, database, accepted_commit=accepted_commit)
        if not _same(current, packet) or current_panel != panel:
            raise assets.P3Error("manifest_drift")
        smoke.validate_manifest(output_dir / "manifest.json", manifest)

    try:
        admission._snapshot(artifacts, packet_path, {"reference": "packet.json", "sha256": packet_pin["sha256"]})
        admission._snapshot(artifacts, authorization_path,
                            {"reference": "authorization.json", "sha256": authorization_pin["sha256"]})
        validate()
        smoke._no_symlinks(env_file)
        # Preserve the historical default call exactly; only a closed caller
        # may supply a typed admitted candidate after packet validation.
        admitted_client = getattr(contract, "_admitted_client", None)
        if admitted_client is None:
            config = (contract.GatewayConfig.from_env(env_file=env_file) if expected_model is None else
                      contract.GatewayConfig.from_env(env_file=env_file, expected_model=expected_model))
            if config.transport_security != packet["transport_security"]:
                raise assets.P3Error("invalid_configuration")
            client = contract.GatewayClient(config)
        else:
            # Only a purpose-specific, already validated caller may supply a
            # provider client. The packet has no live provider/model override.
            client = admitted_client(packet, env_file)
            config = client.config
            if config.transport_security != packet["transport_security"]:
                raise assets.P3Error("invalid_configuration")
        if evaluator._attempts(client) != 0:
            raise assets.P3Error("attempt_budget")
        evaluator._safe(manifest, client)
        report["transport_security"] = config.transport_security
        validate()
    except (KeyboardInterrupt, asyncio.CancelledError):
        evaluator._stop(report, "interrupted")
    except evaluator._SAFE_ERRORS as exc:
        evaluator._stop(report, exc.code)
    except OSError as exc:
        evaluator._stop(report, "artifact_conflict" if isinstance(exc, FileExistsError) else "artifact_io")
    except evaluator._INTERNAL_ERRORS:
        evaluator._stop(report, "internal_failure")
    else:
        # Engine owns terminal commit. No wrapper catches/retracts a committed report.
        return await evaluator._execute_panel(database, panel, manifest, artifacts, report, client,
                                              validate=validate, policy=policy, started=started, clock=clock,
                                              entries=entries)
    evaluator._finish_entries(report, entries, report["stop_reason"])
    evaluator._persist(artifacts, report, client, summarize=policy.summarize)
    return report
