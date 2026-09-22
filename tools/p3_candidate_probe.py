"""Closed candidate compatibility: offline packet/binding/reader, separately authorized one-shot live mode."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.gateway import GatewayClient, GatewayConfig, GEMMA_12B
from tools import p3_assets as assets, p3_candidate_model as candidate, p3_eval
from tools import p3_live_evidence as live, p3_probe as probe, recipe_smoke, smoke

PACKET_VERSION = "p3-candidate-compatibility-packet-v1"
AUTHORIZATION_VERSION = "p3-candidate-compatibility-authorization-v1"
MANIFEST_VERSION = "p3-candidate-compatibility-manifest-v1"
REPORT_VERSION = "p3-candidate-compatibility-report-v1"
OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/56#issuecomment-[1-9][0-9]*")
POLICIES = {"retries": "enabled", "fallback": "disabled", "cache": "disabled"}
TRANSPORT = "unencrypted_http"
ENTRY = "grepbit.recipe_model.interpret_recipe_and_execute"
ANCESTRY = "20abb5592262c77c98f9cabeaf7cf4854edb6fbe"
COMPATIBILITY = (*probe._COMPATIBILITY, "model_identity", "native_execution")
_FIELDS = {"version", "state", "purpose", "candidate", "candidate_reference", "accepted_commit",
           "behavior_ancestry", "source_identity", "semantic_identity", "semantic_identity_sha256",
           "database_sha256", "case_id", "family_id", "language", "exposure", "question_reference",
           "question_sha256", "runtime_entry", "settings", "settings_sha256", "gateway_policy",
           "transport_security", "upstream_inference_attempts", "data_boundary", "command_template"}
_SAFE = (probe.ProbeError, *probe._SAFE_ERRORS)


def settings() -> dict:
    return {"inputs": 1, "max_client_http_attempts": 1, "max_runtime_invocations": 1,
            "concurrency": 1, "call_timeout_seconds": 60, "publication_budget_seconds": 180,
            "temperature": 0, "max_tokens": 2048, "stream": False,
            "retries": 0, "repairs": 0, "fallbacks": 0, "resend": 0, "continuation": 0,
            "best_of": 0, "resume": False, "stop": "after_first_reserved_attempt_regardless_of_result"}


def command_template(commit: str) -> list[str]:
    return [".venv/bin/python", "tools/p3_candidate_probe.py", "--live", "--packet", "<EXACT_PACKET>",
            "--authorization", "<EXACT_AUTHORIZATION>", "--db", "<EXACT_DB>", "--accepted-commit", commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>", "--gateway-retries", "enabled",
            "--gateway-fallback", "disabled", "--gateway-cache", "disabled", "--output-dir", "<FRESH_OUTPUT>"]


def _same(left, right):
    return model.canonical_json(left) == model.canonical_json(right)


def _hash(value, length=64):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{%d}" % length, value) is None:
        raise probe.ProbeError("invalid_manifest")


def _reference(value):
    if (not isinstance(value, str) or not value or len(value) > 1024 or Path(value).is_absolute()
            or ".." in Path(value).parts or re.fullmatch(r"[A-Za-z0-9_./-]+", value) is None):
        raise probe.ProbeError("invalid_manifest")
    return value


def _checkout(source, accepted_commit):
    _hash(accepted_commit, 40)
    recipe_smoke._accepted(source, accepted_commit)
    # Local cached refs only; never fetch or contact GitHub/provider from a runner.
    for reference in ("refs/heads/dev", "refs/remotes/origin/dev"):
        try:
            result = subprocess.run(["git", "--no-optional-locks", "rev-parse", "--verify", reference],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            raise probe.ProbeError("source_identity_failure") from None
        if result.returncode or result.stdout.strip() != accepted_commit:
            raise probe.ProbeError("accepted_commit_required")


def _packet_contract(packet):
    """Closed archived validation, independent of the current source checkout."""
    assets.object_fields(packet, _FIELDS)
    candidate.admit_candidate(packet["candidate"])
    _hash(packet["accepted_commit"], 40)
    _hash(packet["database_sha256"])
    _reference(packet["candidate_reference"])
    source = packet["source_identity"]
    if (not isinstance(source, dict) or source.get("git_commit") != packet["accepted_commit"]
            or source.get("branch") != "dev" or source.get("worktree_dirty") is not False
            or not isinstance(source.get("files_sha256"), dict)):
        raise probe.ProbeError("invalid_manifest")
    for name, sha in source["files_sha256"].items():
        assets.text(name, 1024)
        _hash(sha)
    expected_ref = {"asset": "evals/p3/development-cases-v1.json", "case_id": probe.CASE_ID, "field": "question"}
    # Source asset reference is pinned by preparation; no caller-selected case/field.
    if (packet["version"] != PACKET_VERSION or packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != "one_candidate_compatibility_attempt_not_quality"
            or packet["behavior_ancestry"] != ANCESTRY
            or packet["case_id"] != probe.CASE_ID or packet["family_id"] != "E01_overview"
            or packet["language"] != "en" or packet["exposure"] != "exposed_regression"
            or packet["question_reference"] != expected_ref or packet["question_sha256"] != probe.QUESTION_SHA256
            or packet["runtime_entry"] != ENTRY or packet["candidate"] != candidate.identity()
            or not _same(packet["settings"], settings()) or packet["settings_sha256"] != assets.digest(settings())
            or packet["gateway_policy"] != smoke.policy_attestation(POLICIES, required=True)
            or packet["transport_security"] != TRANSPORT or packet["upstream_inference_attempts"] is not None
            or packet["semantic_identity_sha256"] != candidate.SEMANTICS_SHA256
            or assets.digest(packet["semantic_identity"]) != candidate.SEMANTICS_SHA256
            or packet["command_template"] != command_template(packet["accepted_commit"])
            or packet["data_boundary"] != "one_exposed_question_plus_unchanged_runtime_only_no_quality_scoring"):
        raise probe.ProbeError("invalid_manifest")


def build_packet(database: Path, *, candidate_path: Path, accepted_commit: str,
                 gateway_policies: dict, transport_security: str) -> tuple[dict, str]:
    """Zero-write current-source builder. Never uses the legacy frozen-source validator."""
    candidate.load_identity(candidate_path)
    if gateway_policies != POLICIES or transport_security != TRANSPORT:
        raise probe.ProbeError("invalid_configuration")
    semantic = candidate.semantic_identity()
    panel = assets.load_panel(p3_eval.DEFAULT_PANEL)
    cases = [c for c in panel.cases if c.case_id == probe.CASE_ID]
    if (len(cases) != 1 or cases[0].family_id != "E01_overview" or cases[0].language != "en"
            or cases[0].exposure != "exposed_regression"
            or smoke._digest(cases[0].question.encode()) != probe.QUESTION_SHA256):
        raise probe.ProbeError("invalid_probe")
    source = p3_eval._source_identity(panel, None)
    _checkout(source, accepted_commit)
    try:
        smoke._no_symlinks(candidate_path)
        reference = candidate_path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        raise probe.ProbeError("invalid_manifest") from None
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized",
        "purpose": "one_candidate_compatibility_attempt_not_quality",
        "candidate": candidate.identity(), "candidate_reference": _reference(reference),
        "accepted_commit": accepted_commit, "behavior_ancestry": ANCESTRY,
        "source_identity": source, "semantic_identity": semantic,
        "semantic_identity_sha256": assets.digest(semantic), "database_sha256": smoke._fixture_identity(database),
        "case_id": probe.CASE_ID, "family_id": "E01_overview", "language": "en", "exposure": "exposed_regression",
        "question_reference": {"asset": panel.cases_path.relative_to(ROOT).as_posix(),
                               "case_id": probe.CASE_ID, "field": "question"},
        "question_sha256": probe.QUESTION_SHA256, "runtime_entry": ENTRY,
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "gateway_policy": smoke.policy_attestation(gateway_policies, required=True),
        "transport_security": transport_security, "upstream_inference_attempts": None,
        "data_boundary": "one_exposed_question_plus_unchanged_runtime_only_no_quality_scoring",
        "command_template": command_template(accepted_commit),
    }
    _packet_contract(packet)
    return packet, cases[0].question


def validate_packet(path, database, *, accepted_commit):
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise probe.ProbeError("accepted_commit_required")
    current, question = build_packet(database, candidate_path=ROOT / packet["candidate_reference"],
                                     accepted_commit=accepted_commit, gateway_policies=POLICIES,
                                     transport_security=TRANSPORT)
    if not _same(packet, current):
        raise probe.ProbeError("manifest_drift")
    return packet, question


def prepare(database, output_dir, **kwargs):
    packet, _ = build_packet(database, **kwargs)
    artifacts = smoke._Artifacts(output_dir, packet)
    validate_packet(output_dir / "manifest.json", database, accepted_commit=kwargs["accepted_commit"])
    report = {"version": PACKET_VERSION, "state": "prepared_not_authorized",
              "packet_sha256": p3_eval._pin(output_dir / "manifest.json")["sha256"],
              "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts._write("report.json", report)
    return report


def _authorization(value, packet_sha):
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference"})
    if (value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha
            or not isinstance(value["owner_authorization_reference"], str)
            or OWNER.fullmatch(value["owner_authorization_reference"]) is None):
        raise probe.ProbeError("invalid_manifest")
    return value


def bind_authorization(packet_path, reference, output_path):
    _packet_contract(assets.read_asset(packet_path))
    value = _authorization({"version": AUTHORIZATION_VERSION,
                            "packet_sha256": p3_eval._pin(packet_path)["sha256"],
                            "owner_authorization_reference": reference}, p3_eval._pin(packet_path)["sha256"])
    live._write_authorization(output_path, value)
    return {"version": AUTHORIZATION_VERSION, "authorization_sha256": p3_eval._pin(output_path)["sha256"],
            "packet_sha256": value["packet_sha256"]}


def _runner():
    return {"version": REPORT_VERSION, "sha256": p3_eval._pin(Path(__file__))["sha256"]}


class _CandidateProbe(probe._LegacyProbe):
    """No shared caller flag admits a candidate: this caller owns the complete auth gate."""
    def __init__(self, packet_path, authorization_path, accepted_commit, policies):
        super().__init__(packet_path, accepted_commit)
        self.authorization_path, self.policies = authorization_path, policies
        self.snapshots = {}

    def manifest(self):
        value = {"version": MANIFEST_VERSION, "runner": _runner(),
                 "accepted_commit": self.accepted_commit if isinstance(self.accepted_commit, str)
                 and re.fullmatch(r"[0-9a-f]{40}", self.accepted_commit) else None,
                 "candidate": candidate.identity(), "packet_sha256": None, "authorization_sha256": None}
        for field, path in (("packet_sha256", self.path), ("authorization_sha256", self.authorization_path)):
            if isinstance(path, Path):
                try:
                    value[field] = p3_eval._pin(path)["sha256"]
                except probe._SAFE_ERRORS + probe._INTERNAL:
                    pass
        return value

    def report(self, manifest, origin):
        value = probe._report(manifest, origin)
        value.update(version=REPORT_VERSION, requested_model=GEMMA_12B.model_alias,
                     compatibility=dict.fromkeys(COMPATIBILITY, "not_run"))
        return value

    def validate(self, database):
        if not isinstance(self.authorization_path, Path):
            raise probe.ProbeError("invalid_manifest")
        _authorization(assets.read_asset(self.authorization_path), p3_eval._pin(self.path)["sha256"])
        if self.policies != POLICIES:
            raise probe.ProbeError("invalid_configuration")
        return validate_packet(self.path, database, accepted_commit=self.accepted_commit)

    def identity(self, plan):
        return {"candidate": plan["candidate"], "database_sha256": plan["database_sha256"],
                "case_id": probe.CASE_ID, "question_sha256": probe.QUESTION_SHA256,
                "runtime_entry": ENTRY, "semantic_identity_sha256": candidate.SEMANTICS_SHA256}

    def snapshot(self, artifacts, plan):
        # Byte-identical copies: never reserialize an authorized packet/envelope.
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

    def unchanged(self, manifest, plan, database):
        super().unchanged(manifest, plan, database)
        for path, digest in self.snapshots.items():
            if p3_eval._pin(path)["sha256"] != digest:
                raise probe.ProbeError("manifest_drift")

    def client(self, env_file):
        if not isinstance(env_file, Path):
            raise probe.ProbeError("invalid_configuration")
        smoke._no_symlinks(env_file)
        return GatewayClient(GatewayConfig.from_env(env_file=env_file, expected_model=candidate.admit_candidate(candidate.identity())))

    def check_client(self, client, policies):
        if (client.config.expected_model != GEMMA_12B or client.config.model != GEMMA_12B.model_alias
                or client.config.transport_security != TRANSPORT
                or policies != smoke.policy_attestation(POLICIES, required=True)):
            raise probe.ProbeError("invalid_configuration")

    def project(self, report, result, client):
        probe._result(report, result, client, expected_alias=GEMMA_12B.model_alias)
        compatibility = report["compatibility"]
        compatibility["model_identity"] = "passed" if report["observed_model"] == GEMMA_12B.model_alias else "failed"
        compatibility["native_execution"] = result.evidence["stages"]["kernel_execution"]
        report["compatibility_passed"] = (result.error is None and client.http_attempts == 1
                                           and all(v == "passed" for v in compatibility.values()))
        if result.error is None and not report["compatibility_passed"]:
            code = "unexpected_model" if compatibility["model_identity"] != "passed" else "invalid_probe"
            report.update(error_code=code, stop_reason=code)


async def run_probe(database, output_dir, *, packet_path, authorization_path, accepted_commit,
                    gateway_policies, env_file=None, origin="mock", client=None, clock=time.monotonic):
    contract = _CandidateProbe(packet_path, authorization_path, accepted_commit, gateway_policies)
    return await probe._run_probe(database, output_dir, contract=contract, origin=origin, client=client,
                                  gateway_policies=gateway_policies, env_file=env_file, clock=clock)


def read_report(path):
    """Closed archived projection; no current-source validation, configuration or network."""
    try:
        report = assets.read_asset(path)
        manifest = assets.read_asset(path.parent / "manifest.json")
        assets.object_fields(manifest, {"version", "runner", "accepted_commit", "candidate",
                                        "packet_sha256", "authorization_sha256"})
        assets.object_fields(manifest["runner"], {"version", "sha256"})
        _hash(manifest["runner"]["sha256"])
        for field, length in (("accepted_commit", 40), ("packet_sha256", 64), ("authorization_sha256", 64)):
            if manifest[field] is not None:
                _hash(manifest[field], length)
        if (manifest["version"] != MANIFEST_VERSION or manifest["runner"]["version"] != REPORT_VERSION
                or manifest["candidate"] != candidate.identity()):
            raise probe.ProbeError("invalid_evidence")
        template = _CandidateProbe(None, None, None, None).report(manifest, "mock")
        assets.object_fields(report, set(template))
        if (report["version"] != REPORT_VERSION or report["manifest_sha256"] != assets.digest(manifest)
                or report["origin"] not in ("mock", "live")
                or report["status"] not in ("incomplete", "running", "complete", "stopped")
                or report["reservation"] not in ("not_reserved", "in_progress", "settled")
                or report["requested_model"] != GEMMA_12B.model_alias
                or report["observed_model"] not in (None, GEMMA_12B.model_alias)
                or report["upstream_inference_attempts"] is not None):
            raise probe.ProbeError("invalid_evidence")
        for name, keys, states in (("compatibility", COMPATIBILITY, probe._COMPAT_STATES),
                                    ("runtime_stages", model.STAGES, probe._STATES)):
            assets.object_fields(report[name], set(keys))
            if any(v not in states for v in report[name].values()):
                raise probe.ProbeError("invalid_evidence")
        for name in ("client_http_attempts", "live_model_attempts", "runtime_invocations",
                     "possible_in_flight_attempts", "attempt_budget_used"):
            live._number(report[name], integer=True, maximum=1, optional=False)
        if (report["live_model_attempts"] != (report["client_http_attempts"] if report["origin"] == "live" else 0)
                or report["attempt_budget_used"] != int(report["reservation"] != "not_reserved")
                or report["possible_in_flight_attempts"] != int(report["reservation"] == "in_progress")
                or not report["client_http_attempts"] <= report["runtime_invocations"] <= report["attempt_budget_used"]
                or report["reservation"] == "settled" and report["runtime_invocations"] != 1):
            raise probe.ProbeError("invalid_evidence")
        for name in ("error_code", "stop_reason"):
            if report[name] is not None and report[name] not in probe._CODES:
                raise probe.ProbeError("invalid_evidence")
        live._number(report["elapsed_seconds"])
        assets.object_fields(report["usage"], {"prompt_tokens", "completion_tokens", "total_tokens"})
        for value in report["usage"].values():
            live._number(value, integer=True, maximum=2**63 - 1)
        status = report["http_status"]
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise probe.ProbeError("invalid_evidence")
        if (report["transport_security"] not in (None, TRANSPORT)
                or report["http_class"] not in ("not_run", "http_success", "http_failure", "no_response")
                or report["gateway_policy"] not in (smoke.policy_attestation(), smoke.policy_attestation(POLICIES, required=True))
                or type(report["compatibility_passed"]) is not bool
                or report["compatibility_passed"] != (report["status"] == "complete")):
            raise probe.ProbeError("invalid_evidence")
        if report["identity"] is not None:
            packet = assets.read_asset(path.parent / "packet.json")
            _packet_contract(packet)
            if (p3_eval._pin(path.parent / "packet.json")["sha256"] != manifest["packet_sha256"]
                    or p3_eval._pin(path.parent / "authorization.json")["sha256"] != manifest["authorization_sha256"]
                    or packet["accepted_commit"] != manifest["accepted_commit"]
                    or report["identity"] != _CandidateProbe(None, None, None, None).identity(packet)):
                raise probe.ProbeError("invalid_evidence")
            _authorization(assets.read_asset(path.parent / "authorization.json"), manifest["packet_sha256"])
        if report["compatibility_passed"] and (
                report["identity"] is None or report["observed_model"] != GEMMA_12B.model_alias
                or not all(v == "passed" for v in report["runtime_stages"].values())
                or report["http_status"] != 200 or report["http_class"] != "http_success"
                or report["transport_security"] != TRANSPORT
                or report["gateway_policy"] != smoke.policy_attestation(POLICIES, required=True)
                or report["client_http_attempts"] != 1 or report["reservation"] != "settled"
                or report["error_code"] is not None or report["stop_reason"] != "single_attempt_complete"
                or not all(v == "passed" for v in report["compatibility"].values())):
            raise probe.ProbeError("invalid_evidence")
        return {**{k: v for k, v in report.items() if k != "identity"},
                "candidate": manifest["candidate"], "accepted_commit": manifest["accepted_commit"],
                "packet_sha256": manifest["packet_sha256"], "authorization_sha256": manifest["authorization_sha256"],
                "report_sha256": p3_eval._pin(path)["sha256"]}
    except _SAFE + probe._INTERNAL:
        raise probe.ProbeError("invalid_evidence") from None


def main(argv=None):
    parser = smoke._Parser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "bind-authorization", "live", "report"):
        mode.add_argument("--" + name, action="store_true")
    for name in ("candidate-identity", "packet", "authorization", "db", "env-file", "output-dir", "output", "report-path"):
        parser.add_argument("--" + name, type=Path)
    for name in ("accepted-commit", "owner-authorization-reference", "transport-security"):
        parser.add_argument("--" + name)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        common = {"db", "accepted_commit", "output_dir", "gateway_retries", "gateway_fallback", "gateway_cache"}
        required = ({"prepare", "candidate_identity", "transport_security"} | common if args.prepare else
                    {"bind_authorization", "packet", "owner_authorization_reference", "output"} if args.bind_authorization else
                    {"live", "packet", "authorization", "env_file"} | common if args.live else {"report", "report_path"})
        if {k for k, v in vars(args).items() if v is not None and v is not False} != required:
            raise probe.ProbeError("invalid_arguments")
        policies = {k: getattr(args, "gateway_" + k) for k in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, candidate_path=args.candidate_identity,
                             accepted_commit=args.accepted_commit, gateway_policies=policies,
                             transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output)
        elif args.live:
            asyncio.run(run_probe(args.db, args.output_dir, packet_path=args.packet,
                                  authorization_path=args.authorization, accepted_commit=args.accepted_commit,
                                  env_file=args.env_file, gateway_policies=policies, origin="live"))
            result = read_report(args.output_dir / "report.json")
        else:
            result = read_report(args.report_path)
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
