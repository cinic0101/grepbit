"""Closed JP Bedrock candidate packet and one-shot compatibility; no quality scoring."""
from __future__ import annotations

import asyncio
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model, recipe_model
from grepbit.bedrock import (BEDROCK_CALL_TIMEOUT_SECONDS, BEDROCK_ERROR_BODY_BYTES,
                            BedrockClient, BedrockConfig, converse_schema)
from grepbit.provider import client_from_env
from tools import p3_assets as assets, p3_candidate_model as semantic
from tools import p3_candidate_probe as old_candidate, p3_eval, p3_live_evidence as live
from tools import p3_probe as probe, recipe_smoke, smoke

LEGACY_PACKET_VERSION = "p3-bedrock-candidate-packet-v1"
PRIVATE_PACKET_VERSION = "p3-bedrock-candidate-packet-v2"
COMPLEX_CONST_PACKET_VERSION = "p3-bedrock-candidate-packet-v3"
GRAMMAR_BUDGET_PACKET_VERSION = "p3-bedrock-candidate-packet-v4"
PACKET_VERSION = "p3-bedrock-candidate-packet-v5"
AUTHORIZATION_VERSION = "p3-bedrock-candidate-authorization-v1"
MANIFEST_VERSION = "p3-bedrock-candidate-manifest-v1"
REPORT_VERSION = "p3-bedrock-candidate-report-v1"
LEGACY_EFFECTIVE_RUNTIME_VERSION = "p3-bedrock-effective-runtime-v1"
PREVIOUS_EFFECTIVE_RUNTIME_VERSION = "p3-bedrock-effective-runtime-v2"
GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_VERSION = "p3-bedrock-effective-runtime-v3"
EFFECTIVE_RUNTIME_VERSION = "p3-bedrock-effective-runtime-v4"
OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/64#issuecomment-[1-9][0-9]*")
REGION = "ap-northeast-1"
PROFILE = "jp.anthropic.claude-sonnet-4-6"
TRANSPORT = "tls_verification_enabled"
CALL_SECONDS = BEDROCK_CALL_TIMEOUT_SECONDS
PUBLICATION_SECONDS = 420.0
CANONICAL_SCHEMA_SHA256 = "a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00"
LEGACY_WIRE_SCHEMA_SHA256 = "d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f"
PREVIOUS_WIRE_SCHEMA_SHA256 = "93ab99c9162a43412d0588b3ded70cc41a25827582b4d11b8072e3348d201f68"
GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256 = "ea4e03d02732c0c45f9905ccd9b7c0010bedc87a190666e7b31895867c43e53b"
WIRE_SCHEMA_SHA256 = "e377c4f0807d90674e3d30c8274533fc0c70c363d15d6c1a07019849a6a6c456"
LEGACY_EFFECTIVE_RUNTIME_SHA256 = "7af570605c825a70acaae125181703c9d4204d4d74b89abd96aef35a2a9c2c7b"
PREVIOUS_EFFECTIVE_RUNTIME_SHA256 = "f56e90fe54662a2929797623a74508751b25424b666227fbd699ec4d4ebf4a3c"
GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_SHA256 = "4d1f27ded8138dbe9618c6f8c4b32ca4555d8a244ac5e7d94e1287f9de4fb2ed"
EFFECTIVE_RUNTIME_SHA256 = "ef60af9db5fe329603fca28b4c9bc13fc6d3effd2387d9f27140cb1f79ec6480"
POLICIES = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
ENTRY = old_candidate.ENTRY
ANCESTRY = old_candidate.ANCESTRY
COMPATIBILITY = (*probe._COMPATIBILITY, "route_acceptance", "native_execution")
_FIELDS = {"version", "state", "purpose", "candidate", "accepted_commit",
           "behavior_ancestry", "source_identity", "baseline_semantic_identity",
           "baseline_semantic_identity_sha256", "effective_runtime_identity",
           "effective_runtime_identity_sha256",
           "canonical_schema_sha256", "wire_schema_sha256", "database_sha256", "case_id",
           "family_id", "language", "exposure", "question_reference", "question_sha256",
           "runtime_entry", "settings", "settings_sha256", "gateway_policy",
           "transport_security", "upstream_inference_attempts", "data_boundary", "command_template"}
DIAGNOSTIC_CAPTURE = {"http_400_body": "exclusive_private_sidecar", "max_bytes": BEDROCK_ERROR_BODY_BYTES,
                      "location": "sibling_private_directory"}
_SAFE = (probe.ProbeError, *probe._SAFE_ERRORS)


def candidate_identity() -> dict:
    return {"candidate_id": "p3-jp-sonnet-46-bedrock-converse-v1", "provider": "bedrock_converse",
            "endpoint_kind": "bedrock-runtime", "api": "Converse",
            "response_mode": "bedrock_converse_normalized", "calling_region": REGION,
            "model_profile_id": PROFILE, "allowed_destination_regions": ["ap-northeast-1", "ap-northeast-3"],
            "credential_env_name": "GREPBIT_BEDROCK_API_KEY", "served_weight_revision": None,
            "identity_evidence": "requested_profile_only_no_returned_model"}


def settings() -> dict:
    return {"inputs": 1, "max_client_http_attempts": 1, "max_runtime_invocations": 1,
            "concurrency": 1, "call_timeout_seconds": CALL_SECONDS,
            "publication_budget_seconds": PUBLICATION_SECONDS,
            "temperature": 0, "max_tokens": 2048, "stream": False, "retries": 0,
            "repairs": 0, "fallbacks": 0, "resend": 0, "continuation": 0, "best_of": 0,
            "resume": False, "stop": "after_first_reserved_attempt_regardless_of_result"}


def effective_runtime_identity(baseline: dict, *, packet_version: str = PACKET_VERSION) -> dict:
    """Version the candidate's actual runtime envelope separately from 12B ancestry."""
    identity = {
        LEGACY_PACKET_VERSION: (LEGACY_EFFECTIVE_RUNTIME_VERSION, LEGACY_WIRE_SCHEMA_SHA256),
        PRIVATE_PACKET_VERSION: (LEGACY_EFFECTIVE_RUNTIME_VERSION, LEGACY_WIRE_SCHEMA_SHA256),
        COMPLEX_CONST_PACKET_VERSION: (PREVIOUS_EFFECTIVE_RUNTIME_VERSION,
                                       PREVIOUS_WIRE_SCHEMA_SHA256),
        GRAMMAR_BUDGET_PACKET_VERSION: (GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_VERSION,
                                        GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256),
        PACKET_VERSION: (EFFECTIVE_RUNTIME_VERSION, WIRE_SCHEMA_SHA256),
    }
    if packet_version not in identity:
        raise probe.ProbeError("invalid_manifest")
    runtime_version, wire_hash = identity[packet_version]
    return {"version": runtime_version,
            "baseline_semantic_identity_sha256": semantic.SEMANTICS_SHA256,
            "recipe_context": baseline["recipe_context"],
            "structured_output": baseline["structured_output"],
            "p1_context": baseline["p1_context"],
            "limits": {**baseline["limits"], "timeout": CALL_SECONDS},
            "provider": "bedrock_converse", "response_mode": "bedrock_converse_normalized",
            "model_profile_id": PROFILE, "calling_region": REGION,
            "wire_schema_sha256": wire_hash,
            "publication_budget_seconds": PUBLICATION_SECONDS}


def command_template(commit: str, *, capture_http_400_body: bool = True) -> list[str]:
    return [".venv/bin/python", "tools/p3_bedrock_candidate_probe.py", "--live",
            *(["--capture-http-400-body"] if capture_http_400_body else []),
            "--packet", "<EXACT_PACKET>", "--authorization", "<EXACT_AUTHORIZATION>",
            "--db", "<EXACT_DB>", "--accepted-commit", commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>", "--gateway-retries", "disabled",
            "--gateway-fallback", "disabled", "--gateway-cache", "disabled",
            "--output-dir", "<FRESH_OUTPUT>"]


def _schemas() -> tuple[str, str]:
    identity = recipe_model.structured_output_identity()
    constraint = recipe_model._structured_output(recipe_model.output_schema())[0]
    wire_hash = converse_schema(constraint)[1]
    if identity["schema_sha256"] != CANONICAL_SCHEMA_SHA256 or wire_hash != WIRE_SCHEMA_SHA256:
        raise probe.ProbeError("source_identity_failure")
    return CANONICAL_SCHEMA_SHA256, WIRE_SCHEMA_SHA256


def _packet_contract(packet: object) -> dict:
    if not isinstance(packet, dict):
        raise probe.ProbeError("invalid_manifest")
    version = packet.get("version")
    if version not in (PACKET_VERSION, GRAMMAR_BUDGET_PACKET_VERSION, COMPLEX_CONST_PACKET_VERSION,
                       PRIVATE_PACKET_VERSION, LEGACY_PACKET_VERSION):
        raise probe.ProbeError("invalid_manifest")
    capture = version != LEGACY_PACKET_VERSION
    expected_wire = {LEGACY_PACKET_VERSION: LEGACY_WIRE_SCHEMA_SHA256,
                     PRIVATE_PACKET_VERSION: LEGACY_WIRE_SCHEMA_SHA256,
                     COMPLEX_CONST_PACKET_VERSION: PREVIOUS_WIRE_SCHEMA_SHA256,
                     GRAMMAR_BUDGET_PACKET_VERSION: GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256,
                     PACKET_VERSION: WIRE_SCHEMA_SHA256}[version]
    expected_effective = {LEGACY_PACKET_VERSION: LEGACY_EFFECTIVE_RUNTIME_SHA256,
                          PRIVATE_PACKET_VERSION: LEGACY_EFFECTIVE_RUNTIME_SHA256,
                          COMPLEX_CONST_PACKET_VERSION: PREVIOUS_EFFECTIVE_RUNTIME_SHA256,
                          GRAMMAR_BUDGET_PACKET_VERSION: GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_SHA256,
                          PACKET_VERSION: EFFECTIVE_RUNTIME_SHA256}[version]
    value = assets.object_fields(packet, _FIELDS | ({"diagnostic_capture"} if capture else set()))
    old_candidate._hash(value["accepted_commit"], 40)
    for key in ("baseline_semantic_identity_sha256", "effective_runtime_identity_sha256",
                "canonical_schema_sha256", "wire_schema_sha256",
                "database_sha256", "question_sha256", "settings_sha256"):
        old_candidate._hash(value[key])
    source = value["source_identity"]
    if (not isinstance(source, dict) or source.get("git_commit") != value["accepted_commit"]
            or source.get("branch") != "dev" or source.get("worktree_dirty") is not False
            or not isinstance(source.get("files_sha256"), dict)):
        raise probe.ProbeError("invalid_manifest")
    for name, sha in source["files_sha256"].items():
        assets.text(name, 1024)
        old_candidate._hash(sha)
    if (value["state"] != "prepared_not_authorized"
            or capture and not old_candidate._same(value["diagnostic_capture"], DIAGNOSTIC_CAPTURE)
            or value["purpose"] != "one_jp_bedrock_compatibility_attempt_not_quality"
            or not old_candidate._same(value["candidate"], candidate_identity())
            or value["behavior_ancestry"] != ANCESTRY
            or value["baseline_semantic_identity_sha256"] != semantic.SEMANTICS_SHA256
            or assets.digest(value["baseline_semantic_identity"]) != semantic.SEMANTICS_SHA256
            or value["effective_runtime_identity_sha256"] != expected_effective
            or assets.digest(value["effective_runtime_identity"]) != expected_effective
            or not old_candidate._same(value["effective_runtime_identity"],
                                       effective_runtime_identity(value["baseline_semantic_identity"],
                                                                  packet_version=version))
            or value["effective_runtime_identity"]["limits"]["timeout"] != value["settings"]["call_timeout_seconds"]
            or value["effective_runtime_identity"]["limits"]["timeout"] != BedrockConfig.max_call_timeout_seconds
            or value["effective_runtime_identity"]["publication_budget_seconds"] != value["settings"]["publication_budget_seconds"]
            or value["canonical_schema_sha256"] != CANONICAL_SCHEMA_SHA256
            or value["wire_schema_sha256"] != expected_wire
            or value["case_id"] != probe.CASE_ID or value["family_id"] != "E01_overview"
            or value["language"] != "en" or value["exposure"] != "exposed_regression"
            or value["question_reference"] != {"asset": "evals/p3/development-cases-v1.json",
                                                "case_id": probe.CASE_ID, "field": "question"}
            or value["question_sha256"] != probe.QUESTION_SHA256 or value["runtime_entry"] != ENTRY
            or not old_candidate._same(value["settings"], settings())
            or value["settings_sha256"] != assets.digest(settings())
            or value["gateway_policy"] != smoke.policy_attestation(POLICIES, required=True)
            or value["transport_security"] != TRANSPORT or value["upstream_inference_attempts"] is not None
            or value["data_boundary"] != "one_exposed_synthetic_question_japan_only_no_gold_no_quality"
            or value["command_template"] != command_template(
                value["accepted_commit"], capture_http_400_body=capture)):
        raise probe.ProbeError("invalid_manifest")
    return value


def build_packet(database: Path, *, accepted_commit: str,
                 gateway_policies: dict, transport_security: str) -> tuple[dict, str]:
    """Zero-write preparation; never reads the env file or contacts AWS."""
    if gateway_policies != POLICIES or transport_security != TRANSPORT:
        raise probe.ProbeError("invalid_configuration")
    panel = assets.load_panel(p3_eval.DEFAULT_PANEL)
    cases = [case for case in panel.cases if case.case_id == probe.CASE_ID]
    if (len(cases) != 1 or cases[0].family_id != "E01_overview" or cases[0].language != "en"
            or cases[0].exposure != "exposed_regression"
            or smoke._digest(cases[0].question.encode()) != probe.QUESTION_SHA256):
        raise probe.ProbeError("invalid_probe")
    source = p3_eval._source_identity(panel, None)
    old_candidate._checkout(source, accepted_commit)
    baseline = semantic.semantic_identity()
    effective = effective_runtime_identity(baseline)
    canonical, wire = _schemas()
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized",
        "purpose": "one_jp_bedrock_compatibility_attempt_not_quality",
        "candidate": candidate_identity(), "accepted_commit": accepted_commit,
        "behavior_ancestry": ANCESTRY, "source_identity": source,
        "baseline_semantic_identity": baseline,
        "baseline_semantic_identity_sha256": assets.digest(baseline),
        "effective_runtime_identity": effective,
        "effective_runtime_identity_sha256": assets.digest(effective),
        "canonical_schema_sha256": canonical, "wire_schema_sha256": wire,
        "database_sha256": smoke._fixture_identity(database),
        "case_id": probe.CASE_ID, "family_id": "E01_overview", "language": "en",
        "exposure": "exposed_regression",
        "question_reference": {"asset": panel.cases_path.relative_to(ROOT).as_posix(),
                               "case_id": probe.CASE_ID, "field": "question"},
        "question_sha256": probe.QUESTION_SHA256, "runtime_entry": ENTRY,
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "gateway_policy": smoke.policy_attestation(gateway_policies, required=True),
        "transport_security": transport_security, "upstream_inference_attempts": None,
        "data_boundary": "one_exposed_synthetic_question_japan_only_no_gold_no_quality",
        "diagnostic_capture": DIAGNOSTIC_CAPTURE,
        "command_template": command_template(accepted_commit),
    }
    _packet_contract(packet)
    return packet, cases[0].question


def validate_packet(path: Path, database: Path, *, accepted_commit: str) -> tuple[dict, str]:
    packet = _packet_contract(assets.read_asset(path))
    if packet["version"] != PACKET_VERSION:
        raise probe.ProbeError("manifest_drift")
    if packet["accepted_commit"] != accepted_commit:
        raise probe.ProbeError("accepted_commit_required")
    current, question = build_packet(database, accepted_commit=accepted_commit,
                                     gateway_policies=POLICIES, transport_security=TRANSPORT)
    if not old_candidate._same(packet, current):
        raise probe.ProbeError("manifest_drift")
    return packet, question


def prepare(database: Path, output_dir: Path, **kwargs) -> dict:
    packet, _ = build_packet(database, **kwargs)
    artifacts = smoke._Artifacts(output_dir, packet)
    validate_packet(output_dir / "manifest.json", database, accepted_commit=kwargs["accepted_commit"])
    report = {"version": PACKET_VERSION, "state": "prepared_not_authorized",
              "packet_sha256": p3_eval._pin(output_dir / "manifest.json")["sha256"],
              "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts._write("report.json", report)
    return report


def _authorization(value: object, packet_sha: str) -> dict:
    entry = assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference"})
    if (entry["version"] != AUTHORIZATION_VERSION or entry["packet_sha256"] != packet_sha
            or not isinstance(entry["owner_authorization_reference"], str)
            or OWNER.fullmatch(entry["owner_authorization_reference"]) is None):
        raise probe.ProbeError("invalid_manifest")
    return entry


def bind_authorization(packet_path: Path, reference: str, output_path: Path) -> dict:
    packet = _packet_contract(assets.read_asset(packet_path))
    if packet["version"] != PACKET_VERSION:
        raise probe.ProbeError("manifest_drift")
    sha = p3_eval._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": sha,
                            "owner_authorization_reference": reference}, sha)
    live._write_authorization(output_path, value)
    return {"version": AUTHORIZATION_VERSION, "authorization_sha256": p3_eval._pin(output_path)["sha256"],
            "packet_sha256": sha}


def _write_private_error_body(private_dir: Path, raw: bytes) -> None:
    if len(raw) > DIAGNOSTIC_CAPTURE["max_bytes"]:
        return
    private_path = private_dir / "http-400-body.json"
    smoke._no_symlinks(private_path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(private_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                           | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(directory_fd)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != os.getuid()):
            raise OSError("private diagnostic directory changed")
        fd = os.open(private_path.name, flags, 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.unlink(private_path.name, dir_fd=directory_fd)
            except OSError:
                pass
            raise
    finally:
        os.close(directory_fd)


class _BedrockProbe(probe._LegacyProbe):
    def __init__(self, packet_path, authorization_path, accepted_commit, policies,
                 *, capture_http_400_body=False, output_dir=None):
        super().__init__(packet_path, accepted_commit)
        self.authorization_path, self.policies = authorization_path, policies
        self.capture_http_400_body, self.output_dir = capture_http_400_body, output_dir
        self.snapshots: dict[Path, str] = {}

    def budgets(self):
        return CALL_SECONDS, PUBLICATION_SECONDS

    def manifest(self):
        value = {"version": MANIFEST_VERSION,
                 "runner": {"version": REPORT_VERSION, "sha256": p3_eval._pin(Path(__file__))["sha256"]},
                 "accepted_commit": self.accepted_commit if isinstance(self.accepted_commit, str)
                 and re.fullmatch(r"[0-9a-f]{40}", self.accepted_commit) else None,
                 "candidate": candidate_identity(), "packet_sha256": None, "authorization_sha256": None}
        for field, path in (("packet_sha256", self.path), ("authorization_sha256", self.authorization_path)):
            if isinstance(path, Path):
                try:
                    value[field] = p3_eval._pin(path)["sha256"]
                except _SAFE + probe._INTERNAL:
                    pass
        return value

    def report(self, manifest, origin):
        result = probe._report(manifest, origin)
        result.update(version=REPORT_VERSION, requested_model=PROFILE, requested_profile=PROFILE,
                      model_identity="unobserved", compatibility=dict.fromkeys(COMPATIBILITY, "not_run"))
        return result

    def validate(self, database):
        if not isinstance(self.authorization_path, Path):
            raise probe.ProbeError("invalid_manifest")
        _authorization(assets.read_asset(self.authorization_path), p3_eval._pin(self.path)["sha256"])
        if self.policies != POLICIES:
            raise probe.ProbeError("invalid_configuration")
        packet, question = validate_packet(self.path, database, accepted_commit=self.accepted_commit)
        if self.capture_http_400_body is not True or not isinstance(self.output_dir, Path):
            raise probe.ProbeError("invalid_configuration")
        return packet, question

    def identity(self, packet):
        return {"candidate": packet["candidate"], "database_sha256": packet["database_sha256"],
                "case_id": probe.CASE_ID, "question_sha256": probe.QUESTION_SHA256,
                "runtime_entry": ENTRY,
                "baseline_semantic_identity_sha256": packet["baseline_semantic_identity_sha256"],
                "effective_runtime_identity_sha256": packet["effective_runtime_identity_sha256"],
                "canonical_schema_sha256": packet["canonical_schema_sha256"],
                "wire_schema_sha256": packet["wire_schema_sha256"]}

    def snapshot(self, artifacts, packet):
        for name, source in (("packet.json", self.path), ("authorization.json", self.authorization_path)):
            smoke._no_symlinks(source)
            with source.open("rb") as stream:
                raw = stream.read(assets.MAX_ASSET_BYTES + 1)
            if len(raw) > assets.MAX_ASSET_BYTES:
                raise probe.ProbeError("invalid_asset")
            try:
                fd = os.open(artifacts.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                raise probe.ProbeError("artifact_io") from None
            self.snapshots[artifacts.directory / name] = smoke._digest(raw)

    def unchanged(self, manifest, packet, database):
        super().unchanged(manifest, packet, database)
        for path, digest in self.snapshots.items():
            if p3_eval._pin(path)["sha256"] != digest:
                raise probe.ProbeError("manifest_drift")

    def client(self, env_file):
        if not isinstance(env_file, Path):
            raise probe.ProbeError("invalid_configuration")
        smoke._no_symlinks(env_file)
        private_dir = self.output_dir.with_name(self.output_dir.name + "-private")
        smoke._no_symlinks(private_dir)
        try:
            private_dir.mkdir(mode=0o700)
            info = private_dir.stat()
            if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                    or info.st_uid != os.getuid()):
                raise probe.ProbeError("artifact_io")
        except FileExistsError:
            raise probe.ProbeError("artifact_conflict") from None
        except OSError:
            raise probe.ProbeError("artifact_io") from None
        return client_from_env(env_file=env_file,
                               bedrock_error_body_sink=lambda raw: _write_private_error_body(private_dir, raw))

    def check_client(self, client, policies):
        if (type(client) is not BedrockClient or type(client.config) is not BedrockConfig
                or client.config.region != REGION or client.config.model != PROFILE
                or client.config.expected_model is not None
                or client.config.transport_security != TRANSPORT
                or client.config.max_call_timeout_seconds != CALL_SECONDS
                or policies != smoke.policy_attestation(POLICIES, required=True)):
            raise probe.ProbeError("invalid_configuration")

    def project(self, report, result, client):
        probe._result(report, result, client, expected_alias=PROFILE)
        if report["observed_model"] is not None:
            raise probe.ProbeError("invalid_evidence")
        compat = report["compatibility"]
        compat["route_acceptance"] = ("passed" if report["http_status"] == 200 else
                                      "unknown" if client.http_attempts else "not_run")
        compat["native_execution"] = result.evidence["stages"]["kernel_execution"]
        report["compatibility_passed"] = (result.error is None and client.http_attempts == 1
                                           and all(value == "passed" for value in compat.values()))
        if result.error is None and not report["compatibility_passed"]:
            report.update(error_code="invalid_probe", stop_reason="invalid_probe")


async def run_probe(database: Path, output_dir: Path, *, packet_path: Path,
                    authorization_path: Path, accepted_commit: str, gateway_policies: dict,
                    env_file: Path | None = None, origin: str = "mock", client=None,
                    clock=time.monotonic, capture_http_400_body: bool = False) -> dict:
    return await probe._run_probe(database, output_dir,
                                  contract=_BedrockProbe(packet_path, authorization_path,
                                                         accepted_commit, gateway_policies,
                                                         capture_http_400_body=capture_http_400_body,
                                                         output_dir=output_dir),
                                  origin=origin, client=client, gateway_policies=gateway_policies,
                                  env_file=env_file, clock=clock)


def read_report(path: Path) -> dict:
    """Validate archived safe evidence without env, current checkout or AWS access."""
    try:
        report = assets.read_asset(path)
        manifest = assets.object_fields(assets.read_asset(path.parent / "manifest.json"),
                                        {"version", "runner", "accepted_commit", "candidate",
                                         "packet_sha256", "authorization_sha256"})
        runner = assets.object_fields(manifest["runner"], {"version", "sha256"})
        old_candidate._hash(runner["sha256"])
        for key, size in (("accepted_commit", 40), ("packet_sha256", 64), ("authorization_sha256", 64)):
            if manifest[key] is not None:
                old_candidate._hash(manifest[key], size)
        if (manifest["version"] != MANIFEST_VERSION or runner["version"] != REPORT_VERSION
                or not old_candidate._same(manifest["candidate"], candidate_identity())):
            raise probe.ProbeError("invalid_evidence")
        template = _BedrockProbe(None, None, None, None).report(manifest, "mock")
        assets.object_fields(report, set(template))
        if (report["version"] != REPORT_VERSION or report["manifest_sha256"] != assets.digest(manifest)
                or report["origin"] not in ("mock", "live")
                or report["status"] not in ("incomplete", "running", "complete", "stopped")
                or report["reservation"] not in ("not_reserved", "in_progress", "settled")
                or report["requested_model"] != PROFILE or report["requested_profile"] != PROFILE
                or report["observed_model"] is not None or report["model_identity"] != "unobserved"
                or report["upstream_inference_attempts"] is not None
                or report["transport_security"] not in (None, TRANSPORT)
                or report["http_class"] not in ("not_run", "http_success", "http_failure", "no_response")):
            raise probe.ProbeError("invalid_evidence")
        for key in ("client_http_attempts", "live_model_attempts", "possible_in_flight_attempts",
                    "attempt_budget_used", "runtime_invocations"):
            if type(report[key]) is not int or report[key] not in (0, 1):
                raise probe.ProbeError("invalid_evidence")
        if (report["live_model_attempts"] != (report["client_http_attempts"] if report["origin"] == "live" else 0)
                or report["attempt_budget_used"] != int(report["reservation"] != "not_reserved")
                or report["possible_in_flight_attempts"] != int(report["reservation"] == "in_progress")
                or report["client_http_attempts"] > report["runtime_invocations"]
                or report["runtime_invocations"] > report["attempt_budget_used"]
                or report["reservation"] == "settled" and report["runtime_invocations"] != 1):
            raise probe.ProbeError("invalid_evidence")
        for key, keys, states in (("compatibility", COMPATIBILITY, probe._COMPAT_STATES),
                                  ("runtime_stages", model.STAGES, probe._STATES)):
            value = assets.object_fields(report[key], set(keys))
            if any(state not in states for state in value.values()):
                raise probe.ProbeError("invalid_evidence")
        for key in ("error_code", "stop_reason"):
            if report[key] is not None and report[key] not in probe._CODES:
                raise probe.ProbeError("invalid_evidence")
        if (type(report["compatibility_passed"]) is not bool
                or report["compatibility_passed"] != (report["status"] == "complete")
                or report["compatibility_passed"] and
                (report["client_http_attempts"] != 1 or report["reservation"] != "settled"
                 or report["error_code"] is not None or report["stop_reason"] != "single_attempt_complete"
                 or any(value != "passed" for value in report["compatibility"].values()))):
            raise probe.ProbeError("invalid_evidence")
        if report["http_status"] is not None and (type(report["http_status"]) is not int
                                                 or not 100 <= report["http_status"] <= 599):
            raise probe.ProbeError("invalid_evidence")
        latency = report["elapsed_seconds"]
        if latency is not None and (type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0):
            raise probe.ProbeError("invalid_evidence")
        usage = assets.object_fields(report["usage"], {"prompt_tokens", "completion_tokens", "total_tokens"})
        if any(value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1)
               for value in usage.values()):
            raise probe.ProbeError("invalid_evidence")
        if report["gateway_policy"] not in (smoke.policy_attestation(),
                                              smoke.policy_attestation(POLICIES, required=True)):
            raise probe.ProbeError("invalid_evidence")
        if report["identity"] is not None:
            packet = _packet_contract(assets.read_asset(path.parent / "packet.json"))
            if (manifest["packet_sha256"] != p3_eval._pin(path.parent / "packet.json")["sha256"]
                    or manifest["authorization_sha256"] != p3_eval._pin(path.parent / "authorization.json")["sha256"]
                    or packet["accepted_commit"] != manifest["accepted_commit"]
                    or not old_candidate._same(report["identity"], _BedrockProbe(None, None, None, None).identity(packet))):
                raise probe.ProbeError("invalid_evidence")
            _authorization(assets.read_asset(path.parent / "authorization.json"), manifest["packet_sha256"])
        elif report["status"] == "complete":
            raise probe.ProbeError("invalid_evidence")
        if report["compatibility_passed"] and (
                any(value != "passed" for value in report["runtime_stages"].values())
                or report["http_status"] != 200 or report["http_class"] != "http_success"
                or report["transport_security"] != TRANSPORT
                or report["gateway_policy"] != smoke.policy_attestation(POLICIES, required=True)):
            raise probe.ProbeError("invalid_evidence")
        return {"version": REPORT_VERSION, "status": report["status"], "origin": report["origin"],
                "runner": runner, "accepted_commit": manifest["accepted_commit"],
                "packet_sha256": manifest["packet_sha256"], "requested_profile": PROFILE,
                "baseline_semantic_identity_sha256": (report["identity"] or {}).get("baseline_semantic_identity_sha256"),
                "effective_runtime_identity_sha256": (report["identity"] or {}).get("effective_runtime_identity_sha256"),
                "observed_model": None, "model_identity": "unobserved",
                "compatibility": report["compatibility"], "compatibility_passed": report["compatibility_passed"],
                "runtime_stages": report["runtime_stages"], "client_http_attempts": report["client_http_attempts"],
                "live_model_attempts": report["live_model_attempts"], "usage": usage,
                "elapsed_seconds": latency, "error_code": report["error_code"],
                "stop_reason": report["stop_reason"], "report_sha256": p3_eval._pin(path)["sha256"]}
    except probe.ProbeError:
        raise
    except (*probe._SAFE_ERRORS, *probe._INTERNAL):
        raise probe.ProbeError("invalid_evidence") from None


def main(argv=None) -> int:
    parser = smoke._Parser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "bind-authorization", "live", "report"):
        actions.add_argument("--" + name, action="store_true")
    parser.add_argument("--capture-http-400-body", action="store_true")
    for name in ("db", "accepted-commit", "output-dir", "packet", "authorization", "env-file",
                 "owner-authorization-reference", "output", "report-path", "transport-security"):
        parser.add_argument("--" + name)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        common = {"db", "accepted_commit", "output_dir", "gateway_retries", "gateway_fallback", "gateway_cache"}
        required = ({"prepare", "transport_security"} | common if args.prepare else
                    {"bind_authorization", "packet", "owner_authorization_reference", "output"}
                    if args.bind_authorization else
                    {"live", "capture_http_400_body", "packet", "authorization", "env_file"} | common if args.live else
                    {"report", "report_path"})
        if {key for key, value in vars(args).items() if value is not None and value is not False} != required:
            raise probe.ProbeError("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(Path(args.db), Path(args.output_dir), accepted_commit=args.accepted_commit,
                             gateway_policies=policies, transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(Path(args.packet), args.owner_authorization_reference, Path(args.output))
        elif args.live:
            asyncio.run(run_probe(Path(args.db), Path(args.output_dir), packet_path=Path(args.packet),
                                  authorization_path=Path(args.authorization), accepted_commit=args.accepted_commit,
                                  env_file=Path(args.env_file), gateway_policies=policies, origin="live",
                                  capture_http_400_body=args.capture_http_400_body))
            result = read_report(Path(args.output_dir) / "report.json")
        else:
            result = read_report(Path(args.report_path))
        print(model.canonical_json(result))
        return 1 if args.live and result["status"] != "complete" else 0
    except _SAFE as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except probe._INTERNAL:
        print('{"status":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
