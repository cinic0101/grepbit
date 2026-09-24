#!/usr/bin/env python3
"""Closed JP Bedrock 28-input observed regression; live requires separate owner scope."""
from __future__ import annotations

import asyncio
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.bedrock import BedrockClient, BedrockConfig
from grepbit.provider import client_from_env
from tools import p3_admission as admission, p3_assets as assets, p3_bedrock_candidate_probe as bedrock_probe
from tools import p3_candidate_regression as historical, p3_eval as evaluator
from tools import p3_formal_policy as allocation, p3_formal_run as formal
from tools import p3_grading, p3_live_evidence as live, smoke

PACKET_VERSION = "p3-bedrock-observed-regression-packet-v1"
AUTHORIZATION_VERSION = "p3-bedrock-observed-regression-authorization-v2"
MANIFEST_VERSION = "p3-bedrock-observed-regression-manifest-v2"
REPORT_VERSION = "p3-bedrock-observed-regression-report-v2"
STOP_VERSION = "p3-bedrock-observed-regression-stops-v1"
PURPOSE = "one_observed_jp_bedrock_regression_panel_not_fresh_or_promotion"
OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/70#issuecomment-[1-9][0-9]*")
PROFILE = bedrock_probe.PROFILE
REGION = bedrock_probe.REGION
POLICIES = bedrock_probe.POLICIES
TRANSPORT = bedrock_probe.TRANSPORT
DB_SHA256 = historical._DB_SHA
COMPATIBILITY_SHA256 = "ea4747388b8c47b6f762e521816f5daeebf4da67901a445e8745cc375f3c49e1"
BASELINE_SHA256 = historical._BASELINE_SHA
PINS = historical._PINS
ORDER = historical._ORDER
_PACKET_FIELDS = {
    "version", "state", "purpose", "evidence_class", "promotion_eligible", "promotion_result",
    "accepted_commit", "candidate", "source_identity", "baseline_semantic_identity_sha256",
    "effective_runtime_identity_sha256", "canonical_schema_sha256", "wire_schema_sha256",
    "database_sha256", "locations", "assets", "panel_id", "order", "order_sha256", "inputs",
    "allocation_policy", "grader_version", "runtime_entry", "compatibility", "historical_31b",
    "settings", "settings_sha256", "stop_policy", "stop_policy_sha256", "gateway_policy",
    "transport_security", "data_boundary", "upstream_inference_attempts", "command_template",
}
_summarize = historical._summarize


def settings() -> dict:
    return {**evaluator.settings(28), "model": PROFILE,
            "response_mode": "bedrock_converse_normalized",
            "call_timeout_seconds": 300.0, "panel_timeout_seconds": 8520.0,
            "execution": "owner_authorized_observed_candidate_regression_only",
            "max_runtime_invocations": 28, "client_fallback": 0, "resend": 0,
            "continuation": 0, "best_of": 0, "resume": False}


def stop_policy() -> dict:
    return {**formal.stop_policy(), "version": STOP_VERSION,
            "authorization": "Exact Bedrock observed packet and Issue #70 reference before credentials.",
            "semantic_failures": "Grade all inputs; wrong quality never stops the panel.",
            "replay": "No resume, retry, repair, fallback or second run."}


def command_template(commit: str) -> list[str]:
    return [".venv/bin/python", "tools/p3_bedrock_observed_regression.py", "--live",
            "--packet", "<EXACT_ACCEPTED_PACKET>", "--authorization", "<EXACT_AUTHORIZATION>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>", "--gateway-retries", "disabled",
            "--gateway-fallback", "disabled", "--gateway-cache", "disabled",
            "--output-dir", "<FRESH_REGRESSION_OUTPUT>"]


def _reference(value: str) -> Path:
    return historical._reference(value)


def _location(path: Path) -> str:
    return historical._location(path)


def _run_slot(path: Path) -> str:
    """Keep the one-shot output identity private to this repository's artifacts."""
    if not isinstance(path, Path):
        raise assets.P3Error("invalid_manifest")
    try:
        slot = path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        raise assets.P3Error("invalid_manifest") from None
    _reference(slot)
    if Path(slot).parts[:1] != (".artifacts",) or len(Path(slot).parts) < 2:
        raise assets.P3Error("invalid_manifest")
    smoke._no_symlinks(path)
    return slot


def _pin(path: Path, expected: str) -> dict:
    return historical._pin(path, expected)


def _current_identities() -> dict:
    """Recompute runtime and schema pins before preparing a new live packet."""
    baseline = bedrock_probe.semantic.semantic_identity()
    effective = bedrock_probe.effective_runtime_identity(baseline)
    try:
        canonical, wire = bedrock_probe._schemas()
    except bedrock_probe.probe.ProbeError:
        raise assets.P3Error("source_identity_failure") from None
    actual = {"baseline_semantic_identity_sha256": assets.digest(baseline),
              "effective_runtime_identity_sha256": assets.digest(effective),
              "canonical_schema_sha256": canonical, "wire_schema_sha256": wire}
    expected = {"baseline_semantic_identity_sha256": bedrock_probe.semantic.SEMANTICS_SHA256,
                "effective_runtime_identity_sha256": bedrock_probe.EFFECTIVE_RUNTIME_SHA256,
                "canonical_schema_sha256": bedrock_probe.CANONICAL_SCHEMA_SHA256,
                "wire_schema_sha256": bedrock_probe.WIRE_SCHEMA_SHA256}
    if actual != expected:
        raise assets.P3Error("source_identity_failure")
    return actual


def _compatible_report(path: Path) -> dict:
    _pin(path, COMPATIBILITY_SHA256)
    try:
        compatible = bedrock_probe.read_report(path)
    except bedrock_probe.probe.ProbeError:
        raise assets.P3Error("invalid_manifest") from None
    if (not compatible["compatibility_passed"] or compatible["status"] != "complete"
            or compatible["origin"] != "live" or compatible["client_http_attempts"] != 1
            or compatible["report_sha256"] != COMPATIBILITY_SHA256
            or compatible["requested_profile"] != PROFILE or compatible["observed_model"] is not None
            or compatible["baseline_semantic_identity_sha256"]
            != bedrock_probe.semantic.SEMANTICS_SHA256
            or compatible["effective_runtime_identity_sha256"]
            != bedrock_probe.EFFECTIVE_RUNTIME_SHA256):
        raise assets.P3Error("invalid_manifest")
    return compatible


def _packet_contract(packet: dict) -> None:
    """Closed archived validation; no current source, DB, env or network access."""
    assets.object_fields(packet, _PACKET_FIELDS)
    source = packet["source_identity"]
    if (not isinstance(source, dict) or not isinstance(source.get("files_sha256"), dict)
            or not isinstance(packet["accepted_commit"], str)
            or re.fullmatch(r"[0-9a-f]{40}", packet["accepted_commit"]) is None):
        raise assets.P3Error("invalid_manifest")
    for name, digest in source["files_sha256"].items():
        assets.text(name)
        formal._hash(digest)
    for name in ("baseline_semantic_identity_sha256", "effective_runtime_identity_sha256",
                 "canonical_schema_sha256", "wire_schema_sha256", "database_sha256", "order_sha256",
                 "settings_sha256", "stop_policy_sha256"):
        formal._hash(packet[name])
    if (packet["version"] != PACKET_VERSION or packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != PURPOSE or packet["evidence_class"] != "observed_regression"
            or packet["promotion_eligible"] is not False or packet["promotion_result"] != "not_applicable"
            or not formal._same(packet["candidate"], bedrock_probe.candidate_identity())
            or source.get("git_commit") != packet["accepted_commit"]
            or source.get("branch") != "dev" or source.get("worktree_dirty") is not False
            or packet["baseline_semantic_identity_sha256"] != bedrock_probe.semantic.SEMANTICS_SHA256
            or packet["effective_runtime_identity_sha256"] != bedrock_probe.EFFECTIVE_RUNTIME_SHA256
            or packet["canonical_schema_sha256"] != bedrock_probe.CANONICAL_SCHEMA_SHA256
            or packet["wire_schema_sha256"] != bedrock_probe.WIRE_SCHEMA_SHA256
            or packet["database_sha256"] != DB_SHA256
            or packet["order"] != list(ORDER) or packet["order_sha256"] != assets.digest(list(ORDER))
            or packet["allocation_policy"] != allocation.identity(allocation.V2)
            or packet["grader_version"] != p3_grading.VERSION
            or packet["runtime_entry"] != bedrock_probe.ENTRY
            or packet["settings"] != settings() or packet["settings_sha256"] != assets.digest(settings())
            or packet["stop_policy"] != stop_policy()
            or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or packet["gateway_policy"] != smoke.policy_attestation(POLICIES, required=True)
            or packet["transport_security"] != TRANSPORT
            or packet["data_boundary"] != "individual_observed_synthetic_question_japan_only_no_fresh_claim"
            or packet["upstream_inference_attempts"] is not None
            or packet["command_template"] != command_template(packet["accepted_commit"])):
        raise assets.P3Error("invalid_manifest")
    assets.object_fields(packet["locations"], {"intake", "panel"})
    for reference in packet["locations"].values():
        _reference(reference)
    assets.object_fields(packet["assets"], set(PINS))
    for name, digest in PINS.items():
        formal._pin_fields(packet["assets"][name])
        if packet["assets"][name]["sha256"] != digest:
            raise assets.P3Error("invalid_manifest")
    if (not isinstance(packet["inputs"], list) or len(packet["inputs"]) != 28
            or [row.get("case_id") for row in packet["inputs"] if isinstance(row, dict)] != list(ORDER)):
        raise assets.P3Error("invalid_manifest")
    for row in packet["inputs"]:
        assets.object_fields(row, evaluator._INPUT_FIELDS)
        formal._hash(row["question_sha256"])
        assets.Provenance.from_mapping(row["provenance"], row["exposure"])
    allocation.validate_allocation(packet["inputs"], allocation.V2)
    for name, digest in (("compatibility", COMPATIBILITY_SHA256),
                         ("historical_31b", BASELINE_SHA256)):
        fields = {"reference", "sha256"} | ({"projection"} if name == "historical_31b" else set())
        assets.object_fields(packet[name], fields)
        _reference(packet[name]["reference"])
        formal._hash(packet[name]["sha256"])
        if packet[name]["sha256"] != digest:
            raise assets.P3Error("invalid_manifest")
    historical._validate_baseline(packet["historical_31b"]["projection"])


def _sources(database: Path, *, intake_path: Path, panel_path: Path,
             compatibility_path: Path, historical_path: Path, accepted_commit: str):
    source_paths = {"intake": intake_path, "cases": panel_path.parent / "formal-cases-v2-draft.json",
                    "oracles": panel_path.parent / "formal-oracles-v2-draft.json", "panel": panel_path}
    pinned = {name: _pin(path, PINS[name]) for name, path in source_paths.items()}
    panel, _ = admission._policy_materials(intake_path, panel_path, allocation.V2)
    if [case.case_id for case in panel.cases] != list(ORDER):
        raise assets.P3Error("invalid_panel")
    if smoke._fixture_identity(database) != DB_SHA256:
        raise assets.P3Error("db_drift")
    source = evaluator._source_identity(panel, None)
    bedrock_probe.old_candidate._checkout(source, accepted_commit)
    _compatible_report(compatibility_path)
    _pin(historical_path, BASELINE_SHA256)
    baseline = formal.read_report(historical_path)
    return panel, pinned, source, historical._baseline_projection(baseline)


def build_packet(database: Path, *, intake_path: Path, panel_path: Path,
                 compatibility_path: Path, historical_path: Path, accepted_commit: str,
                 gateway_policies: dict, transport_security: str):
    if gateway_policies != POLICIES or transport_security != TRANSPORT:
        raise assets.P3Error("invalid_configuration")
    panel, pinned, source, baseline = _sources(
        database, intake_path=intake_path, panel_path=panel_path,
        compatibility_path=compatibility_path, historical_path=historical_path,
        accepted_commit=accepted_commit)
    identities = _current_identities()
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized", "purpose": PURPOSE,
        "evidence_class": "observed_regression", "promotion_eligible": False,
        "promotion_result": "not_applicable", "accepted_commit": accepted_commit,
        "candidate": bedrock_probe.candidate_identity(), "source_identity": source,
        **identities,
        "database_sha256": DB_SHA256,
        "locations": {"intake": _location(intake_path), "panel": _location(panel_path)},
        "assets": pinned, "panel_id": panel.panel_id, "order": list(ORDER),
        "order_sha256": assets.digest(list(ORDER)), "inputs": panel.inputs(),
        "allocation_policy": allocation.identity(allocation.V2), "grader_version": p3_grading.VERSION,
        "runtime_entry": bedrock_probe.ENTRY,
        "compatibility": {"reference": _location(compatibility_path), "sha256": COMPATIBILITY_SHA256},
        "historical_31b": {"reference": _location(historical_path), "sha256": BASELINE_SHA256,
                           "projection": baseline},
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(POLICIES, required=True),
        "transport_security": TRANSPORT,
        "data_boundary": "individual_observed_synthetic_question_japan_only_no_fresh_claim",
        "upstream_inference_attempts": None, "command_template": command_template(accepted_commit),
    }
    _packet_contract(packet)
    return packet, panel


def validate_packet(path: Path, database: Path, *, accepted_commit: str):
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise assets.P3Error("accepted_commit_required")
    current, panel = build_packet(
        database, intake_path=_reference(packet["locations"]["intake"]),
        panel_path=_reference(packet["locations"]["panel"]),
        compatibility_path=_reference(packet["compatibility"]["reference"]),
        historical_path=_reference(packet["historical_31b"]["reference"]),
        accepted_commit=accepted_commit, gateway_policies=POLICIES, transport_security=TRANSPORT)
    if not formal._same(current, packet):
        raise assets.P3Error("manifest_drift")
    return packet, panel


def prepare(database: Path, output_dir: Path, **options):
    packet, _ = build_packet(database, **options)
    artifacts = smoke._Artifacts(output_dir, packet)
    report = {"version": PACKET_VERSION, "state": "incomplete",
              "packet_sha256": evaluator._pin(output_dir / "manifest.json")["sha256"],
              "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts.persist(report)
    validate_packet(output_dir / "manifest.json", database, accepted_commit=packet["accepted_commit"])
    report["state"] = "prepared_not_authorized"
    artifacts.persist(report)
    return report


def _authorization(value: dict, packet_sha: str) -> dict:
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"})
    if (value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha
            or not isinstance(value["owner_authorization_reference"], str)
            or OWNER.fullmatch(value["owner_authorization_reference"]) is None
            or not isinstance(value["run_slot"], str)
            or Path(value["run_slot"]).parts[:1] != (".artifacts",)
            or len(Path(value["run_slot"]).parts) < 2
            or Path(value["run_slot"]).as_posix() != value["run_slot"]):
        raise assets.P3Error("invalid_manifest")
    _reference(value["run_slot"])
    formal._hash(packet_sha)
    return value


def _validate_run_slot(authorization: dict, output_dir: Path) -> None:
    if authorization["run_slot"] != _run_slot(output_dir):
        raise assets.P3Error("invalid_manifest")


def bind_authorization(packet_path: Path, reference: str, output_path: Path, run_output_dir: Path):
    _packet_contract(assets.read_asset(packet_path))
    digest = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference,
                            "run_slot": _run_slot(run_output_dir)}, digest)
    live._write_authorization(output_path, value)
    return value


def _expected_model(packet):
    _packet_contract(packet)
    # Converse does not return observed model identity.
    return None


def _admitted_client(packet, env_file):
    _packet_contract(packet)
    client = client_from_env(env_file=env_file)
    if (type(client) is not BedrockClient or type(client.config) is not BedrockConfig
            or client.config.region != REGION or client.config.model != PROFILE
            or client.config.expected_model is not None
            or client.config.max_call_timeout_seconds != 300.0
            or client.config.transport_security != TRANSPORT):
        raise assets.P3Error("invalid_configuration")
    return client


def _manifest(packet, packet_sha, authorization, authorization_sha):
    return {"manifest_version": MANIFEST_VERSION, "packet_sha256": packet_sha,
            "authorization_sha256": authorization_sha,
            "owner_authorization_reference": authorization["owner_authorization_reference"],
            "run_slot": authorization["run_slot"],
            "accepted_commit": packet["accepted_commit"], "candidate": packet["candidate"],
            "evaluator_version": packet["grader_version"], "panel_id": packet["panel_id"],
            "panel_kind": "candidate_regression", "inputs": packet["inputs"], "order": packet["order"],
            "allocation_policy": packet["allocation_policy"], "settings": packet["settings"],
            "settings_sha256": packet["settings_sha256"], "stop_policy": packet["stop_policy"],
            "stop_policy_sha256": packet["stop_policy_sha256"], "historical_31b": packet["historical_31b"],
            "compatibility": packet["compatibility"],
            "baseline_semantic_identity_sha256": packet["baseline_semantic_identity_sha256"],
            "effective_runtime_identity_sha256": packet["effective_runtime_identity_sha256"],
            "canonical_schema_sha256": packet["canonical_schema_sha256"],
            "wire_schema_sha256": packet["wire_schema_sha256"],
            "evidence_class": "observed_regression", "promotion_eligible": False,
            "promotion_result": "not_applicable",
            "preparation": {"kind": "accepted", "accepted_commit": packet["accepted_commit"]}}


def _report(manifest, packet):
    report = evaluator._new_report(manifest, "live")
    report.update(report_version=REPORT_VERSION, runtime_invocations=0, transport_security=None,
                  gateway_policy=packet["gateway_policy"],
                  owner_authorization_reference=manifest["owner_authorization_reference"],
                  run_slot=manifest["run_slot"],
                  scope="Observed 28-case JP Bedrock regression only; not fresh quality or P3 promotion.",
                  candidate=packet["candidate"], historical_31b=packet["historical_31b"],
                  compatibility=packet["compatibility"],
                  baseline_semantic_identity_sha256=packet["baseline_semantic_identity_sha256"],
                  effective_runtime_identity_sha256=packet["effective_runtime_identity_sha256"],
                  canonical_schema_sha256=packet["canonical_schema_sha256"],
                  wire_schema_sha256=packet["wire_schema_sha256"],
                  evidence_class="observed_regression", promotion_eligible=False,
                  promotion_result="not_applicable")
    for row in report["results"]:
        row["phase"] = "not_started"
    return report


class _LiveEvidence(live._LiveEvidence):
    maximum = 28
    summarize = staticmethod(_summarize)

    def __init__(self, expected_model=None):
        if expected_model is not None:
            raise assets.P3Error("invalid_configuration")
        super().__init__(requested_profile=PROFILE)

    def check_report(self, report):
        super().check_report(report)
        for row in report["results"]:
            if (row["status"] == "completed" and row["actual_action"] is not None
                    and row["operational_error"] is None
                    and (not isinstance(row["evidence"], dict)
                         or row["evidence"].get("requested_model") != PROFILE
                         or row["evidence"].get("returned_model") is not None)):
                raise assets.P3Error("invalid_asset")


def _entries(panel, packet):
    return evaluator._panel_entries(panel)


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict, clock=time.monotonic):
    return await live._run_live(database, output_dir, packet_path=packet_path,
                                authorization_path=authorization_path, accepted_commit=accepted_commit,
                                env_file=env_file, gateway_policies=gateway_policies,
                                clock=clock, contract=sys.modules[__name__])


def read_report(path: Path):
    """Validate closed archived evidence without source checkout, DB, env or AWS."""
    if path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    packet = assets.read_asset(path.parent / "packet.json")
    _packet_contract(packet)
    packet_sha = evaluator._pin(path.parent / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(path.parent / "authorization.json"), packet_sha)
    _validate_run_slot(authorization, path.parent)
    manifest = assets.read_asset(path.parent / "manifest.json")
    expected_manifest = _manifest(packet, packet_sha, authorization,
                                  evaluator._pin(path.parent / "authorization.json")["sha256"])
    if not formal._same(manifest, expected_manifest):
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    expected = _report(manifest, packet)
    live._validate_report(report, manifest, expected, packet["inputs"], maximum=28,
                          transport_security=TRANSPORT, summarize=_summarize,
                          requested_profile=PROFILE)
    _LiveEvidence().check_report(report)
    for key in ("run_slot", "candidate", "historical_31b", "compatibility", "evidence_class",
                "promotion_eligible", "promotion_result", "baseline_semantic_identity_sha256",
                "effective_runtime_identity_sha256", "canonical_schema_sha256", "wire_schema_sha256"):
        if not formal._same(report[key], expected[key]):
            raise assets.P3Error("invalid_asset")
    return report


def main(argv=None):
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "run-output-dir", "intake",
                 "panel", "compatibility-report", "historical-report", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    parser.add_argument("--transport-security", choices=(TRANSPORT,))
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "intake", "panel", "compatibility_report", "historical_report",
                    "transport_security"} | common if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, intake_path=args.intake, panel_path=args.panel,
                             compatibility_path=args.compatibility_report,
                             historical_path=args.historical_report, accepted_commit=args.accepted_commit,
                             gateway_policies=policies, transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference,
                                        args.output, args.run_output_dir)
        else:
            if args.live:
                asyncio.run(run_live(args.db, args.output_dir, packet_path=args.packet,
                                     authorization_path=args.authorization, accepted_commit=args.accepted_commit,
                                     env_file=args.env_file, gateway_policies=policies))
            report = read_report(args.output_dir / "report.json" if args.live else args.report_path)
            result = {key: report[key] for key in ("report_version", "status", "stop_reason", "error_code",
                "client_http_attempts", "live_model_attempts", "runtime_invocations", "possible_in_flight_attempts",
                "upstream_inference_attempts", "transport_security", "evidence_class", "promotion_eligible",
                "promotion_result", "summary")}
        print(model.canonical_json(result))
        return 0 if result.get("status") in (None, "complete") else 1
    except (*evaluator._SAFE_ERRORS, bedrock_probe.probe.ProbeError) as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, *evaluator._INTERNAL_ERRORS):
        print('{"status":"incomplete","error_code":"invalid_manifest"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
