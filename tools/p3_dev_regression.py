#!/usr/bin/env python3
"""Observed 31B regression of the frozen formal panel on an accepted dev commit (#79).

Preparation, binding and readback are offline; --live needs the owner's standing
grant. Every input is regression data: the run compares against the accepted P3.5
formal baseline (25/28) and records, for each clarify action, the closed
clarification kind and choice count so a false clarification can be attributed
without persisting any question, choice or completion text.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.clarification import KINDS, MAX_CHOICES
from grepbit.gateway import GatewayClient, GatewayConfig
from tools import p3_admission as admission, p3_assets as assets, p3_eval as evaluator
from tools import p3_candidate_regression as historical, p3_formal_policy as allocation
from tools import p3_formal_run as formal, p3_grading, p3_holdout_run as holdout
from tools import p3_live_evidence as live, p3_scoring as scoring
from tools import recipe_smoke, smoke

PACKET_VERSION = "p3-dev-regression-packet-v1"
AUTHORIZATION_VERSION = "p3-dev-regression-authorization-v1"
MANIFEST_VERSION = "p3-dev-regression-manifest-v1"
REPORT_VERSION = "p3-dev-regression-report-v1"
STOP_VERSION = "p3-dev-regression-stops-v1"
PURPOSE = "one_observed_dev_regression_panel_not_fresh_quality_or_promotion"
EVIDENCE_CLASS = "observed_regression"
PANEL_KIND = "dev_regression"
MAX_INPUTS = 28
# Closed per-row observations of a clarify action; enum and small integer only.
OBSERVATION_FIELDS = ("clarification_kind", "clarification_choice_count")
# The owner's #79 grant attests retries, fallback and cache disabled for this route.
ROUTE = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
OWNER = holdout.OWNER
_TRANSPORT = formal._TRANSPORT
_same = formal._same
_hash = formal._hash
_PACKET_FIELDS = {
    "version", "state", "purpose", "evidence_class", "promotion_eligible", "promotion_result",
    "accepted_commit", "authoring_baseline_sha", "candidate", "source_identity", "database_sha256",
    "locations", "assets", "panel_id", "panel_kind", "order", "order_sha256", "inputs",
    "allocation_policy", "grader_version", "runtime_entry", "historical_31b", "observation_fields",
    "settings", "settings_sha256", "stop_policy", "stop_policy_sha256", "gateway_policy",
    "transport_security", "data_boundary", "upstream_inference_attempts", "command_template",
}


def settings() -> dict:
    return {**evaluator.settings(MAX_INPUTS), "execution": "owner_granted_dev_regression_only",
            "client_fallback": 0, "resend": 0, "continuation": 0, "best_of": 0}


def stop_policy() -> dict:
    return {**evaluator.stop_policy(), "version": STOP_VERSION,
            "live": "Observed client sends count as live attempts; upstream inference attempts remain unknown.",
            "authorization": "Exact packet, Issue #79 grant reference and bound run slot required before credentials.",
            "semantic_failures": "Grade all inputs; wrong quality never stops the panel.",
            "replay": "No resume, retry, repair, fallback or automatic second run."}


def data_boundary() -> dict:
    return {"source": "synthetic_learningops_only", "wire": "individual_question_and_unchanged_runtime_only",
            "evaluator_metadata_on_wire": False, "raw_completion_or_reasoning_persisted": False,
            "observations": "closed clarification kind and choice count per clarify action; no text",
            "quality_claim": "observed_regression_against_the_accepted_31b_baseline_not_fresh_or_promotion"}


def command_template(accepted_commit: str) -> list[str]:
    return [".venv/bin/python", "tools/p3_dev_regression.py", "--live",
            "--packet", "<EXACT_ACCEPTED_PACKET>", "--authorization", "<EXACT_AUTHORIZATION_ENVELOPE>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", accepted_commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>",
            "--gateway-retries", ROUTE["retries"], "--gateway-fallback", ROUTE["fallback"],
            "--gateway-cache", ROUTE["cache"], "--output-dir", "<BOUND_RUN_SLOT>"]


def _order() -> list[str]:
    return list(historical._ORDER)


def _packet_contract(packet: dict) -> None:
    """Archived structural validation; never consults credentials or the current checkout."""
    assets.object_fields(packet, _PACKET_FIELDS)
    if not isinstance(packet["source_identity"], dict):
        raise assets.P3Error("invalid_manifest")
    source = packet["source_identity"]
    if (not isinstance(packet["accepted_commit"], str) or not formal._COMMIT.fullmatch(packet["accepted_commit"])
            or not isinstance(source.get("files_sha256"), dict)):
        raise assets.P3Error("invalid_manifest")
    for path, digest in source["files_sha256"].items():
        assets.text(path)
        _hash(digest)
    _hash(packet["database_sha256"])
    if (packet["version"] != PACKET_VERSION or packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != PURPOSE or packet["evidence_class"] != EVIDENCE_CLASS
            or packet["promotion_eligible"] is not False or packet["promotion_result"] != "not_applicable"
            or packet["authoring_baseline_sha"] != admission.FROZEN_CANDIDATE
            or packet["candidate"] != holdout.candidate_identity(packet["accepted_commit"],
                                                                 packet["authoring_baseline_sha"])
            or source.get("git_commit") != packet["accepted_commit"] or source.get("branch") != "dev"
            or source.get("worktree_dirty") is not False
            or packet["database_sha256"] != historical._DB_SHA
            or packet["panel_kind"] != PANEL_KIND
            or packet["order"] != _order() or packet["order_sha256"] != assets.digest(_order())
            or packet["allocation_policy"] != allocation.identity(allocation.V2)
            or packet["grader_version"] != p3_grading.VERSION
            or packet["runtime_entry"] != "grepbit.recipe_model.interpret_recipe_and_execute"
            or packet["observation_fields"] != list(OBSERVATION_FIELDS)
            or not _same(packet["settings"], settings()) or packet["settings_sha256"] != assets.digest(settings())
            or not _same(packet["stop_policy"], stop_policy())
            or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or packet["gateway_policy"] != smoke.policy_attestation(ROUTE, required=True)
            or packet["transport_security"] not in _TRANSPORT
            or packet["data_boundary"] != data_boundary()
            or packet["upstream_inference_attempts"] is not None
            or packet["command_template"] != command_template(packet["accepted_commit"])):
        raise assets.P3Error("invalid_manifest")
    assets.object_fields(packet["locations"], {"intake", "panel", "historical"})
    for reference in packet["locations"].values():
        historical._reference(reference)
    assets.object_fields(packet["assets"], set(historical._PINS))
    for key, sha in historical._PINS.items():
        formal._pin_fields(packet["assets"][key])
        if packet["assets"][key]["sha256"] != sha:
            raise assets.P3Error("invalid_manifest")
    if (not isinstance(packet["inputs"], list) or len(packet["inputs"]) != MAX_INPUTS
            or any(not isinstance(row, dict) for row in packet["inputs"])
            or [row.get("case_id") for row in packet["inputs"]] != _order()):
        raise assets.P3Error("invalid_manifest")
    for row in packet["inputs"]:
        assets.object_fields(row, evaluator._INPUT_FIELDS)
        _hash(row["question_sha256"])
        assets.Provenance.from_mapping(row["provenance"], row["exposure"])
    allocation.validate_allocation(packet["inputs"], allocation.V2)
    baseline = assets.object_fields(packet["historical_31b"], {"reference", "sha256", "projection"})
    historical._reference(baseline["reference"])
    _hash(baseline["sha256"])
    if baseline["sha256"] != historical._BASELINE_SHA:
        raise assets.P3Error("invalid_manifest")
    historical._validate_baseline(baseline["projection"])


def _sources(database: Path, *, intake_path: Path, panel_path: Path, historical_path: Path,
             accepted_commit: str):
    """Pinned formal panel assets, the accepted dev source and the accepted 31B baseline."""
    source_pins = {"intake": intake_path, "cases": panel_path.parent / "formal-cases-v2-draft.json",
                   "oracles": panel_path.parent / "formal-oracles-v2-draft.json", "panel": panel_path}
    pinned = {key: historical._pin(path, historical._PINS[key]) for key, path in source_pins.items()}
    panel, intake = admission._policy_materials(intake_path, panel_path, allocation.V2)
    if [case.case_id for case in panel.cases] != _order():
        raise assets.P3Error("invalid_panel")
    if smoke._fixture_identity(database) != historical._DB_SHA:
        raise assets.P3Error("db_drift")
    source = evaluator._source_identity(panel, None)
    recipe_smoke._accepted(source, accepted_commit)
    historical._pin(historical_path, historical._BASELINE_SHA)
    baseline = historical._baseline_projection(formal.read_report(historical_path))
    authoring_baseline = intake.get("candidate_freeze_sha") if isinstance(intake, dict) else None
    if authoring_baseline != admission.FROZEN_CANDIDATE:
        raise assets.P3Error("invalid_manifest")
    return panel, pinned, source, baseline, authoring_baseline


def build_packet(database: Path, *, intake_path: Path, panel_path: Path, historical_path: Path,
                 accepted_commit: str, gateway_policies: dict, transport_security: str):
    if gateway_policies != ROUTE or transport_security not in _TRANSPORT:
        raise assets.P3Error("invalid_configuration")
    panel, pinned, source, baseline, authoring_baseline = _sources(
        database, intake_path=intake_path, panel_path=panel_path, historical_path=historical_path,
        accepted_commit=accepted_commit)
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized", "purpose": PURPOSE,
        "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False, "promotion_result": "not_applicable",
        "accepted_commit": accepted_commit, "authoring_baseline_sha": authoring_baseline,
        "candidate": holdout.candidate_identity(accepted_commit, authoring_baseline),
        "source_identity": source, "database_sha256": historical._DB_SHA,
        "locations": {"intake": historical._location(intake_path), "panel": historical._location(panel_path),
                      "historical": historical._location(historical_path)},
        "assets": pinned, "panel_id": panel.panel_id, "panel_kind": PANEL_KIND, "order": _order(),
        "order_sha256": assets.digest(_order()), "inputs": panel.inputs(),
        "allocation_policy": allocation.identity(allocation.V2), "grader_version": p3_grading.VERSION,
        "runtime_entry": "grepbit.recipe_model.interpret_recipe_and_execute",
        "historical_31b": {"reference": historical._location(historical_path),
                           "sha256": historical._BASELINE_SHA, "projection": baseline},
        "observation_fields": list(OBSERVATION_FIELDS),
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(ROUTE, required=True),
        "transport_security": transport_security, "data_boundary": data_boundary(),
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
        database, intake_path=historical._reference(packet["locations"]["intake"]),
        panel_path=historical._reference(packet["locations"]["panel"]),
        historical_path=historical._reference(packet["locations"]["historical"]),
        accepted_commit=accepted_commit, gateway_policies=dict(ROUTE),
        transport_security=packet["transport_security"])
    if not _same(current, packet):
        raise assets.P3Error("manifest_drift")
    return packet, panel


def prepare(database: Path, output_dir: Path, **options) -> dict:
    packet, _ = build_packet(database, **options)
    artifacts = smoke._Artifacts(output_dir, packet)
    report = {"version": PACKET_VERSION, "state": "incomplete", "packet_sha256": evaluator._pin(
        output_dir / "manifest.json")["sha256"], "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts.persist(report)
    validate_packet(output_dir / "manifest.json", database, accepted_commit=packet["accepted_commit"])
    report["state"] = "prepared_not_authorized"
    artifacts.persist(report)
    return report


def _authorization(value: dict, packet_sha: str) -> dict:
    """The envelope binds the packet, the owner's #79 grant comment and exactly one run slot."""
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"})
    if value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha:
        raise assets.P3Error("invalid_manifest")
    _hash(packet_sha)
    holdout._reference(value["owner_authorization_reference"])
    slot = value["run_slot"]
    if (not isinstance(slot, str) or holdout._SLOT.fullmatch(slot) is None
            or any(part in (".", "..") for part in slot.split("/"))):
        raise assets.P3Error("invalid_manifest")
    return value


def _validate_run_slot(authorization: dict, output_dir: Path) -> None:
    if authorization["run_slot"] != holdout._run_slot(output_dir):
        raise assets.P3Error("invalid_manifest")


def bind_authorization(packet_path: Path, reference: str, output_path: Path, run_output_dir: Path) -> dict:
    packet = assets.read_asset(packet_path)
    _packet_contract(packet)
    digest = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference,
                            "run_slot": holdout._run_slot(run_output_dir)}, digest)
    live._write_authorization(output_path, value)
    return value


def _manifest(packet: dict, packet_sha: str, authorization: dict, authorization_sha: str) -> dict:
    return {
        "manifest_version": MANIFEST_VERSION, "packet_sha256": packet_sha,
        "authorization_sha256": authorization_sha,
        "owner_authorization_reference": authorization["owner_authorization_reference"],
        "run_slot": authorization["run_slot"],
        "accepted_commit": packet["accepted_commit"], "candidate": packet["candidate"],
        "evaluator_version": packet["grader_version"], "panel_id": packet["panel_id"],
        "panel_kind": PANEL_KIND, "inputs": packet["inputs"], "order": packet["order"],
        "allocation_policy": packet["allocation_policy"], "settings": packet["settings"],
        "settings_sha256": packet["settings_sha256"], "stop_policy": packet["stop_policy"],
        "stop_policy_sha256": packet["stop_policy_sha256"], "historical_31b": packet["historical_31b"],
        "observation_fields": packet["observation_fields"],
        "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False, "promotion_result": "not_applicable",
        "preparation": {"kind": "accepted", "accepted_commit": packet["accepted_commit"]},
    }


def _report(manifest: dict, packet: dict) -> dict:
    report = evaluator._new_report(manifest, "live")
    report.update(report_version=REPORT_VERSION, runtime_invocations=0, transport_security=None,
                  gateway_policy=packet["gateway_policy"],
                  owner_authorization_reference=manifest["owner_authorization_reference"],
                  run_slot=manifest["run_slot"], candidate=packet["candidate"],
                  historical_31b=packet["historical_31b"], observation_fields=packet["observation_fields"],
                  evidence_class=EVIDENCE_CLASS, promotion_eligible=False, promotion_result="not_applicable",
                  scope="Observed 28-input 31B regression of the frozen formal panel on the accepted dev "
                        "commit; compared with the accepted formal baseline. Not fresh quality, stability, "
                        "promotion or P3 exit evidence.")
    for row in report["results"]:
        row["phase"] = "not_started"
        row.update(dict.fromkeys(OBSERVATION_FIELDS))
    return report


def _observations(results: list[dict]) -> dict:
    """Closed counts of clarify actions by kind; wrong-branch kinds are what a fix must explain."""
    kinds = dict.fromkeys(KINDS, 0)
    false_kinds = dict.fromkeys(KINDS, 0)
    for row in results:
        if (row["status"] == "completed" and row["actual_action"] == "clarify"
                and isinstance(row["clarification_kind"], str) and row["clarification_kind"] in kinds):
            kinds[row["clarification_kind"]] += 1
            if row["outcome"] == "false_clarification":
                false_kinds[row["clarification_kind"]] += 1
    return {"clarify_actions": sum(kinds.values()), "kinds": kinds, "false_clarification_kinds": false_kinds}


def _summarize(report: dict) -> None:
    allocation.validate_allocation(report["results"], allocation.V2)
    value = scoring.summarize(report["results"], report["results"], panel_kind="development",
                              run_status=report["status"])
    diagnostics = value.pop("promotion")["gates"]
    value.update(panel_kind=PANEL_KIND, evidence_class=EVIDENCE_CLASS, promotion_eligible=False,
                 promotion_result="not_applicable", diagnostic_gates=diagnostics,
                 comparison=historical._comparison(report["historical_31b"]["projection"], report["results"], value),
                 observations=_observations(report["results"]))
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


class _LiveEvidence(live._LiveEvidence):
    maximum = MAX_INPUTS
    summarize = staticmethod(_summarize)
    observation_fields = OBSERVATION_FIELDS

    @staticmethod
    def observe_result(result) -> dict:
        clarification = getattr(result, "clarification", None)
        if clarification is None:
            return dict.fromkeys(OBSERVATION_FIELDS)
        return {"clarification_kind": clarification.kind,
                "clarification_choice_count": len(clarification.choices)}

    def check_report(self, report):
        super().check_report(report)
        for row in report["results"]:
            _check_observation(row)


def _entries(panel, packet):
    return evaluator._panel_entries(panel)


def _expected_model(packet):
    """The default 31B LiteLLM identity, like the formal and holdout runners."""
    _packet_contract(packet)
    return None


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict,
                   clock=time.monotonic) -> dict:
    return await live._run_live(database, output_dir, packet_path=packet_path, authorization_path=authorization_path,
                                accepted_commit=accepted_commit, env_file=env_file,
                                gateway_policies=gateway_policies, clock=clock, contract=sys.modules[__name__])


def read_report(path: Path) -> dict:
    """Offline archive verification; no current checkout, DB or configuration access."""
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
    # Observation shape first, so a malformed archive fails closed as invalid_asset
    # before the recomputed summary touches the rows.
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != MAX_INPUTS:
        raise assets.P3Error("invalid_asset")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(expected["results"][0]):
            raise assets.P3Error("invalid_asset")
        _check_observation(row)
    live._validate_report(report, manifest, expected, packet["inputs"], maximum=MAX_INPUTS,
                          transport_security=packet["transport_security"], summarize=_summarize)
    _LiveEvidence().check_report(report)
    for key in ("run_slot", "candidate", "historical_31b", "observation_fields", "evidence_class",
                "promotion_eligible", "promotion_result"):
        if not _same(report[key], expected[key]):
            raise assets.P3Error("invalid_asset")
    summary = report["summary"]
    if (summary["panel_kind"] != PANEL_KIND or summary["promotion_eligible"] is not False
            or summary["promotion_result"] != "not_applicable" or "promotion" in summary):
        raise assets.P3Error("invalid_asset")
    return report


def main(argv=None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "run-output-dir",
                 "intake", "panel", "historical-report", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    parser.add_argument("--transport-security", choices=_TRANSPORT)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "intake", "panel", "historical_report", "transport_security"} | common
                   if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, intake_path=args.intake, panel_path=args.panel,
                             historical_path=args.historical_report, accepted_commit=args.accepted_commit,
                             gateway_policies=policies, transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output,
                                        args.run_output_dir)
        else:
            if args.live:
                asyncio.run(run_live(args.db, args.output_dir, packet_path=args.packet,
                                     authorization_path=args.authorization, accepted_commit=args.accepted_commit,
                                     env_file=args.env_file, gateway_policies=policies))
            report = read_report(args.output_dir / "report.json" if args.live else args.report_path)
            result = {key: report[key] for key in (
                "report_version", "status", "stop_reason", "error_code", "client_http_attempts",
                "live_model_attempts", "runtime_invocations", "possible_in_flight_attempts",
                "upstream_inference_attempts", "transport_security", "evidence_class", "promotion_eligible",
                "promotion_result", "summary")}
        print(model.canonical_json(result))
        return 0 if result.get("status") in (None, "complete") else 1
    except evaluator._SAFE_ERRORS as exc:
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
