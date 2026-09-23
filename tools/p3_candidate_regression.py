#!/usr/bin/env python3
"""Observed 12B regression only. Prepare/bind/read are offline; live needs Issue #58 authority."""
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
from grepbit.gateway import GEMMA_12B, GatewayClient, GatewayConfig
from tools import p3_admission as admission, p3_assets as assets, p3_candidate_model as candidate
from tools import p3_candidate_probe as candidate_probe, p3_eval as evaluator
from tools import p3_formal_policy as allocation, p3_formal_run as formal
from tools import p3_grading, p3_live_evidence as live, p3_scoring as scoring
from tools import recipe_smoke, smoke

PACKET_VERSION = "p3-candidate-regression-packet-v1"
AUTHORIZATION_VERSION = "p3-candidate-regression-authorization-v1"
MANIFEST_VERSION = "p3-candidate-regression-manifest-v1"
REPORT_VERSION = "p3-candidate-regression-report-v1"
STOP_VERSION = "p3-candidate-regression-stops-v1"
PURPOSE = "one_observed_candidate_regression_panel_not_fresh_quality_or_formal_promotion"
_OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/58#issuecomment-[1-9][0-9]*")
_ROUTE = candidate_probe.POLICIES
_TRANSPORT = candidate_probe.TRANSPORT
_PINS = {
    "intake": "3e213bcb0a42c3e20d8cc897abb7ebdb6f3f002b9c7b5ba54391370aa686b02c",
    "cases": "018bfa0bcc65a0225bb3787a7cdabcf64457dd9e1fba2e8ad7671228e9aced47",
    "oracles": "1839a9994922d631618a5e0d1fa7e432b0132bfa86f70dbe06286e6cdf080fa5",
    "panel": "689b81e20d0b2c5b93eaf13698eaaefbf9ea9ebfe0bb8c0b046cdd2e98c39c1f",
}
_DB_SHA = "3887a8624b1a55d8adb4f917ef720f08374e5b5d78861417933d1b561dccbd3d"
_COMPAT_SHA = "03c7c1308918e2a6110fcee290b8eca44b51c30607ed1a8061d2fce5aad8bdf8"
_BASELINE_SHA = "be8c381fb8945fbb621962e07b83c6db5e2e44028a72db15729d428b7a7741da"
_KNOWN_FAILURES = frozenset({"FA11_D04_overview_plus_attendance.zh-TW",
                             "FA11_D04_overview_plus_attendance.ja", "E02_compare.en"})
_ORDER = (
    "FA01_A02_overview_explicit_definitions.zh-TW", "FA01_A02_overview_explicit_definitions.en",
    "FA01_A02_overview_explicit_definitions.ja", "FA04_A04_compare_year_on_baseline_nonadjacent.en",
    "FA09_C02_comparison_roles_symmetric.r2.zh-TW", "FA09_C02_comparison_roles_symmetric.r2.en",
    "FA09_C02_comparison_roles_symmetric.r2.ja", "FA10_D03_two_month_combined_total.zh-TW",
    "FA10_D03_two_month_combined_total.en", "FA10_D03_two_month_combined_total.ja",
    "FA11_D04_overview_plus_attendance.zh-TW", "FA11_D04_overview_plus_attendance.en",
    "FA11_D04_overview_plus_attendance.ja", "E01_overview.zh-TW", "E02_compare.en",
    "E03_share_denominator.ja", "E01_overview.en", "E02_compare.ja",
    "E03_share_denominator.zh-TW", "E01_overview.ja", "E02_compare.zh-TW",
    "E03_share_denominator.en", "P09_empty_overview.ja", "P15_center.en",
    "P16_metric_meaning.zh-TW", "P19_profit.ja", "P20_cash_received.en", "P22_center_compare.ja",
)
_CATEGORIES = ("UNCHANGED_CORRECT", "FIXED_KNOWN_FAILURE", "NEW_REGRESSION",
               "UNCHANGED_FAILURE", "OUTCOME_CHANGED_OTHER", "UNASSESSED_OPERATIONAL")
_PACKET_FIELDS = {
    "version", "state", "purpose", "evidence_class", "promotion_eligible", "promotion_result",
    "accepted_commit", "candidate", "candidate_reference", "behavior_ancestry", "source_identity",
    "semantic_identity_sha256", "database_sha256", "locations", "assets", "panel_id", "order",
    "order_sha256", "inputs", "allocation_policy", "grader_version", "runtime_entry",
    "compatibility", "historical_31b", "settings", "settings_sha256", "stop_policy",
    "stop_policy_sha256", "gateway_policy", "transport_security", "data_boundary",
    "upstream_inference_attempts", "command_template",
}


def settings() -> dict:
    return {**evaluator.settings(28), "model": GEMMA_12B.model_alias,
            "execution": "owner_authorized_observed_candidate_regression_only",
            "max_runtime_invocations": 28, "client_fallback": 0, "resend": 0,
            "continuation": 0, "best_of": 0, "resume": False}


def stop_policy() -> dict:
    return {**formal.stop_policy(), "version": STOP_VERSION,
            "authorization": "Exact candidate regression packet and Issue #58 authorization before credentials.",
            "semantic_failures": "Grade all inputs; wrong quality never stops the panel.",
            "replay": "No resume, retry, repair, fallback or second run."}


def command_template(commit: str) -> list[str]:
    return [".venv/bin/python", "tools/p3_candidate_regression.py", "--live",
            "--packet", "<EXACT_ACCEPTED_PACKET>", "--authorization", "<EXACT_AUTHORIZATION>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>", "--gateway-retries", "enabled",
            "--gateway-fallback", "disabled", "--gateway-cache", "disabled",
            "--output-dir", "<FRESH_REGRESSION_OUTPUT>"]


def _reference(value: str) -> Path:
    try:
        candidate_probe._reference(value)
    except candidate_probe.probe.ProbeError:
        raise assets.P3Error("invalid_manifest") from None
    return ROOT / value


def _location(path: Path) -> str:
    try:
        value = path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        raise assets.P3Error("invalid_manifest") from None
    _reference(value)
    return value


def _pin(path: Path, expected: str) -> dict:
    pin = evaluator._pin(path)
    if pin["sha256"] != expected:
        raise assets.P3Error("manifest_drift")
    return pin


def _baseline_projection(report: dict) -> dict:
    if (report["status"] != "complete" or report["summary"]["promotion"]["passed"]
            or report["summary"]["checked_wrong_count"] != 0):
        raise assets.P3Error("invalid_manifest")
    rows = []
    per_input = report["summary"]["per_input"]
    for result, score in zip(report["results"], per_input):
        rows.append({key: result[key] for key in ("case_id", "family_id", "status", "outcome",
                                                      "actual_action", "checked_wrong")}
                    | {"correct": score["correct"]})
    projection = {"inputs": rows, "family_correct": {
        key: value["family_all_variants_correct"] for key, value in report["summary"]["per_family"].items()}}
    _validate_baseline(projection)
    return projection


def _validate_baseline(value: dict) -> None:
    assets.object_fields(value, {"inputs", "family_correct"})
    rows = value["inputs"]
    if (not isinstance(rows, list) or len(rows) != 28 or any(not isinstance(row, dict) for row in rows)
            or [row.get("case_id") for row in rows] != list(_ORDER)
            or sum(row.get("correct") is True for row in rows) != 25
            or {row["case_id"] for row in rows if row.get("correct") is False} != _KNOWN_FAILURES
            or any(row["outcome"] != "false_clarification" or row["actual_action"] != "clarify"
                   for row in rows if row["case_id"] in _KNOWN_FAILURES)
            or any(set(row) != {"case_id", "family_id", "status", "outcome", "actual_action",
                                    "checked_wrong", "correct"}
                   or row["status"] != "completed" or row["checked_wrong"] is not False
                   or type(row["correct"]) is not bool or row["actual_action"] not in assets.BRANCHES
                   or row["outcome"] not in assets.OUTCOMES for row in rows)
            or not isinstance(value["family_correct"], dict) or len(value["family_correct"]) != 14
            or set(value["family_correct"]) != {row["family_id"] for row in rows}
            or sum(flag is True for flag in value["family_correct"].values()) != 12
            or any(type(flag) is not bool for flag in value["family_correct"].values())):
        raise assets.P3Error("invalid_manifest")


def _comparison(baseline: dict, results: list[dict], scored: dict) -> dict:
    """Observed deltas only. Correctness comes exclusively from the accepted scorer."""
    _validate_baseline(baseline)
    if len(results) != 28 or len(scored["per_input"]) != 28:
        raise assets.P3Error("invalid_scoring")
    rows, counts, action_changes, outcome_changes = [], dict.fromkeys(_CATEGORIES, 0), [], []
    for old, result, current in zip(baseline["inputs"], results, scored["per_input"]):
        if result["case_id"] != old["case_id"] or current["case_id"] != old["case_id"]:
            raise assets.P3Error("invalid_scoring")
        unassessed = (result["status"] != "completed" or result["outcome"] in ("operational_failure", "not_run")
                      or result.get("operational_error") is not None or result.get("runner_error_code") is not None)
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
        rows.append({"case_id": old["case_id"], "category": category,
                     "old_action": old["actual_action"], "new_action": result["actual_action"],
                     "old_outcome": old["outcome"], "new_outcome": result["outcome"]})
    family_delta = {key: {"historical_passed": baseline["family_correct"][key],
                          "candidate_passed": value["family_all_variants_correct"]}
                    for key, value in scored["per_family"].items()}
    return {"taxonomy": rows, "category_counts": counts,
            "known_failures_fixed": counts["FIXED_KNOWN_FAILURE"], "known_failures_total": 3,
            "new_regressions": counts["NEW_REGRESSION"], "previously_correct_total": 25,
            "checked_wrong_delta": scored["checked_wrong_count"],
            "family_delta": family_delta, "action_changes": action_changes,
            "outcome_changes": outcome_changes,
            "operational_count": sum(row["outcome"] == "operational_failure"
                                     or row.get("operational_error") is not None for row in results),
            "not_run_count": sum(row["status"] == "not_run" for row in results)}


def _summarize(report: dict) -> None:
    allocation.validate_allocation(report["results"], allocation.V2)
    value = scoring.summarize(report["results"], report["results"], panel_kind="development",
                              run_status=report["status"])
    diagnostics = value.pop("promotion")["gates"]
    value.update(panel_kind="candidate_regression", evidence_class="observed_regression",
                 promotion_eligible=False, promotion_result="not_applicable",
                 diagnostic_gates=diagnostics,
                 comparison=_comparison(report["historical_31b"]["projection"], report["results"], value))
    report["summary"] = value


def _packet_contract(packet: dict) -> None:
    """Self-contained archived contract; no current checkout or credential access."""
    assets.object_fields(packet, _PACKET_FIELDS)
    candidate.admit_candidate(packet["candidate"])
    if not isinstance(packet["source_identity"], dict):
        raise assets.P3Error("invalid_manifest")
    source = packet["source_identity"]
    formal._hash(packet["semantic_identity_sha256"])
    formal._hash(packet["database_sha256"])
    if (not isinstance(packet["accepted_commit"], str)
            or re.fullmatch(r"[0-9a-f]{40}", packet["accepted_commit"]) is None
            or not isinstance(source.get("files_sha256"), dict)):
        raise assets.P3Error("invalid_manifest")
    for path, digest in source["files_sha256"].items():
        assets.text(path)
        formal._hash(digest)
    if (packet["version"] != PACKET_VERSION or packet["state"] != "prepared_not_authorized"
            or packet["purpose"] != PURPOSE or packet["evidence_class"] != "observed_regression"
            or packet["promotion_eligible"] is not False or packet["promotion_result"] != "not_applicable"
            or packet["candidate"] != candidate.identity()
            or packet["behavior_ancestry"] != candidate_probe.ANCESTRY
            or source.get("git_commit") != packet["accepted_commit"]
            or source.get("branch") != "dev"
            or source.get("worktree_dirty") is not False
            or packet["semantic_identity_sha256"] != candidate.SEMANTICS_SHA256
            or packet["database_sha256"] != _DB_SHA
            or packet["order"] != list(_ORDER) or packet["order_sha256"] != assets.digest(list(_ORDER))
            or packet["allocation_policy"] != allocation.identity(allocation.V2)
            or packet["grader_version"] != p3_grading.VERSION
            or packet["runtime_entry"] != candidate_probe.ENTRY
            or packet["settings"] != settings() or packet["settings_sha256"] != assets.digest(settings())
            or packet["stop_policy"] != stop_policy() or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or packet["gateway_policy"] != smoke.policy_attestation(_ROUTE, required=True)
            or packet["transport_security"] != _TRANSPORT
            or packet["data_boundary"] != "individual_observed_question_plus_unchanged_runtime_no_fresh_claim"
            or packet["upstream_inference_attempts"] is not None
            or packet["command_template"] != command_template(packet["accepted_commit"])):
        raise assets.P3Error("invalid_manifest")
    assets.object_fields(packet["locations"], {"intake", "panel"})
    for reference in (*packet["locations"].values(), packet["candidate_reference"]):
        _reference(reference)
    assets.object_fields(packet["assets"], set(_PINS))
    for key, sha in _PINS.items():
        formal._pin_fields(packet["assets"][key])
        if packet["assets"][key]["sha256"] != sha:
            raise assets.P3Error("invalid_manifest")
    if (not isinstance(packet["inputs"], list) or len(packet["inputs"]) != 28
            or any(not isinstance(row, dict) for row in packet["inputs"])
            or [row.get("case_id") for row in packet["inputs"]] != list(_ORDER)):
        raise assets.P3Error("invalid_manifest")
    for row in packet["inputs"]:
        assets.object_fields(row, evaluator._INPUT_FIELDS)
        formal._hash(row["question_sha256"])
        assets.Provenance.from_mapping(row["provenance"], row["exposure"])
    allocation.validate_allocation(packet["inputs"], allocation.V2)
    for name, sha in (("compatibility", _COMPAT_SHA), ("historical_31b", _BASELINE_SHA)):
        assets.object_fields(packet[name], {"reference", "sha256"} |
                             ({"projection"} if name == "historical_31b" else set()))
        _reference(packet[name]["reference"])
        formal._hash(packet[name]["sha256"])
        if packet[name]["sha256"] != sha:
            raise assets.P3Error("invalid_manifest")
    _validate_baseline(packet["historical_31b"]["projection"])


def _sources(database: Path, *, intake_path: Path, panel_path: Path, candidate_path: Path,
             compatibility_path: Path, historical_path: Path, accepted_commit: str):
    candidate.load_identity(candidate_path)
    if _pin(candidate_path, GEMMA_12B.candidate_identity_sha256)["sha256"] != GEMMA_12B.candidate_identity_sha256:
        raise assets.P3Error("manifest_drift")
    source_pins = {"intake": intake_path, "cases": panel_path.parent / "formal-cases-v2-draft.json",
                   "oracles": panel_path.parent / "formal-oracles-v2-draft.json", "panel": panel_path}
    pinned = {key: _pin(path, _PINS[key]) for key, path in source_pins.items()}
    panel, _ = admission._policy_materials(intake_path, panel_path, allocation.V2)
    if [case.case_id for case in panel.cases] != list(_ORDER):
        raise assets.P3Error("invalid_panel")
    if smoke._fixture_identity(database) != _DB_SHA:
        raise assets.P3Error("db_drift")
    semantic = candidate.semantic_identity()
    if assets.digest(semantic) != candidate.SEMANTICS_SHA256:
        raise assets.P3Error("source_identity_failure")
    source = evaluator._source_identity(panel, None)
    candidate_probe._checkout(source, accepted_commit)
    _pin(compatibility_path, _COMPAT_SHA)
    try:
        compatibility = candidate_probe.read_report(compatibility_path)
    except candidate_probe.probe.ProbeError:
        raise assets.P3Error("invalid_manifest") from None
    if not compatibility["compatibility_passed"] or compatibility["candidate"] != candidate.identity():
        raise assets.P3Error("invalid_manifest")
    _pin(historical_path, _BASELINE_SHA)
    baseline = formal.read_report(historical_path)
    return panel, pinned, source, _baseline_projection(baseline)


def build_packet(database: Path, *, intake_path: Path, panel_path: Path, candidate_path: Path,
                 compatibility_path: Path, historical_path: Path, accepted_commit: str,
                 gateway_policies: dict, transport_security: str):
    if gateway_policies != _ROUTE or transport_security != _TRANSPORT:
        raise assets.P3Error("invalid_configuration")
    panel, pinned, source, baseline = _sources(
        database, intake_path=intake_path, panel_path=panel_path, candidate_path=candidate_path,
        compatibility_path=compatibility_path, historical_path=historical_path,
        accepted_commit=accepted_commit)
    packet = {
        "version": PACKET_VERSION, "state": "prepared_not_authorized", "purpose": PURPOSE,
        "evidence_class": "observed_regression", "promotion_eligible": False,
        "promotion_result": "not_applicable", "accepted_commit": accepted_commit,
        "candidate": candidate.identity(), "candidate_reference": _location(candidate_path),
        "behavior_ancestry": candidate_probe.ANCESTRY, "source_identity": source,
        "semantic_identity_sha256": candidate.SEMANTICS_SHA256, "database_sha256": _DB_SHA,
        "locations": {"intake": _location(intake_path), "panel": _location(panel_path)},
        "assets": pinned, "panel_id": panel.panel_id, "order": list(_ORDER),
        "order_sha256": assets.digest(list(_ORDER)), "inputs": panel.inputs(),
        "allocation_policy": allocation.identity(allocation.V2), "grader_version": p3_grading.VERSION,
        "runtime_entry": candidate_probe.ENTRY,
        "compatibility": {"reference": _location(compatibility_path), "sha256": _COMPAT_SHA},
        "historical_31b": {"reference": _location(historical_path), "sha256": _BASELINE_SHA,
                           "projection": baseline},
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(_ROUTE, required=True),
        "transport_security": _TRANSPORT,
        "data_boundary": "individual_observed_question_plus_unchanged_runtime_no_fresh_claim",
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
        candidate_path=_reference(packet["candidate_reference"]),
        compatibility_path=_reference(packet["compatibility"]["reference"]),
        historical_path=_reference(packet["historical_31b"]["reference"]),
        accepted_commit=accepted_commit, gateway_policies=_ROUTE, transport_security=_TRANSPORT)
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
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference"})
    if (value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha
            or not isinstance(value["owner_authorization_reference"], str)
            or _OWNER.fullmatch(value["owner_authorization_reference"]) is None):
        raise assets.P3Error("invalid_manifest")
    formal._hash(packet_sha)
    return value


def bind_authorization(packet_path: Path, reference: str, output_path: Path):
    _packet_contract(assets.read_asset(packet_path))
    pin = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": pin,
                            "owner_authorization_reference": reference}, pin)
    live._write_authorization(output_path, value)
    return value


def _expected_model(packet):
    _packet_contract(packet)
    return candidate.admit_candidate(packet["candidate"])


def _manifest(packet, packet_sha, authorization, authorization_sha):
    return {"manifest_version": MANIFEST_VERSION, "packet_sha256": packet_sha,
            "authorization_sha256": authorization_sha,
            "owner_authorization_reference": authorization["owner_authorization_reference"],
            "accepted_commit": packet["accepted_commit"], "candidate": packet["candidate"],
            "evaluator_version": packet["grader_version"], "panel_id": packet["panel_id"],
            "panel_kind": "candidate_regression", "inputs": packet["inputs"], "order": packet["order"],
            "allocation_policy": packet["allocation_policy"], "settings": packet["settings"],
            "settings_sha256": packet["settings_sha256"], "stop_policy": packet["stop_policy"],
            "stop_policy_sha256": packet["stop_policy_sha256"], "historical_31b": packet["historical_31b"],
            "evidence_class": "observed_regression", "promotion_eligible": False,
            "promotion_result": "not_applicable",
            "preparation": {"kind": "accepted", "accepted_commit": packet["accepted_commit"]}}


def _report(manifest, packet):
    report = evaluator._new_report(manifest, "live")
    report.update(report_version=REPORT_VERSION, runtime_invocations=0, transport_security=None,
                  gateway_policy=packet["gateway_policy"],
                  owner_authorization_reference=manifest["owner_authorization_reference"],
                  scope="Observed 28-case candidate regression only; not fresh quality or P3 promotion.",
                  candidate=packet["candidate"], historical_31b=packet["historical_31b"],
                  evidence_class="observed_regression", promotion_eligible=False,
                  promotion_result="not_applicable")
    for row in report["results"]:
        row["phase"] = "not_started"
    return report


class _LiveEvidence(live._LiveEvidence):
    maximum = 28
    summarize = staticmethod(_summarize)

    def check_report(self, report):
        super().check_report(report)
        # A valid typed semantic result must carry exact observed 12B identity.
        # Transport/invalid-output failures may have no returned model at all.
        for row in report["results"]:
            if (row["status"] == "completed" and row["actual_action"] is not None
                    and row["operational_error"] is None
                    and (not isinstance(row["evidence"], dict)
                         or row["evidence"].get("requested_model") != GEMMA_12B.model_alias
                         or row["evidence"].get("returned_model") != GEMMA_12B.model_alias)):
                raise assets.P3Error("invalid_asset")


def _entries(panel, packet):
    return evaluator._panel_entries(panel)


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict, clock=time.monotonic):
    return await live._run_live(database, output_dir, packet_path=packet_path, authorization_path=authorization_path,
                                accepted_commit=accepted_commit, env_file=env_file,
                                gateway_policies=gateway_policies, clock=clock, contract=sys.modules[__name__])


def read_report(path: Path):
    """Purpose-specific archive validation without current checkout, DB, env or network."""
    if path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    packet = assets.read_asset(path.parent / "packet.json")
    _packet_contract(packet)
    packet_sha = evaluator._pin(path.parent / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(path.parent / "authorization.json"), packet_sha)
    manifest = assets.read_asset(path.parent / "manifest.json")
    expected_manifest = _manifest(packet, packet_sha, authorization,
                                  evaluator._pin(path.parent / "authorization.json")["sha256"])
    if not formal._same(manifest, expected_manifest):
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    expected = _report(manifest, packet)
    live._validate_report(report, manifest, expected, packet["inputs"], maximum=28,
                          transport_security=packet["transport_security"], summarize=_summarize,
                          expected_model=GEMMA_12B)
    _LiveEvidence(GEMMA_12B).check_report(report)
    for key in ("candidate", "historical_31b", "evidence_class", "promotion_eligible", "promotion_result"):
        if not formal._same(report[key], expected[key]):
            raise assets.P3Error("invalid_asset")
    return report


def main(argv=None):
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "intake",
                 "panel", "candidate-identity", "compatibility-report", "historical-report", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    parser.add_argument("--transport-security", choices=(_TRANSPORT,))
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "intake", "panel", "candidate_identity", "compatibility_report",
                    "historical_report", "transport_security"} | common if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, intake_path=args.intake, panel_path=args.panel,
                             candidate_path=args.candidate_identity, compatibility_path=args.compatibility_report,
                             historical_path=args.historical_report, accepted_commit=args.accepted_commit,
                             gateway_policies=policies, transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output)
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
    except (*evaluator._SAFE_ERRORS, candidate_probe.probe.ProbeError) as exc:
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
