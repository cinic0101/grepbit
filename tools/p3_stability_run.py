#!/usr/bin/env python3
"""Frozen P3 stability characterization. Offline prepare/bind/report; separately authorized live only."""
from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.gateway import GatewayClient, GatewayConfig
from tools import p3_assets as assets, p3_eval as evaluator, p3_formal_policy as allocation
from tools import p3_formal_run as formal, p3_scoring, smoke
from tools import p3_live_evidence as live

PACKET_VERSION = "p3-stability-packet-v1"
AUTHORIZATION_VERSION = "p3-stability-authorization-v1"
MANIFEST_VERSION = "p3-stability-manifest-v1"
REPORT_VERSION = "p3-stability-report-v1"
STOP_VERSION = "p3-stability-stops-v1"
PRESELECTION_SHA = "f7cb2076ea68cf5d675d9c12353c47eded88b8bfa85268aeb7c76e988387ec70"
_OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/52#issuecomment-[1-9][0-9]*")
_SELECTED = (
    ("FA01_A02_overview_explicit_definitions.zh-TW", "FA01_A02_overview_explicit_definitions", "answer", "v1"),
    ("FA04_A04_compare_year_on_baseline_nonadjacent.en", "FA04_A04_compare_year_on_baseline_nonadjacent", "answer", "v1"),
    ("E03_share_denominator.ja", "E03_share_denominator", "anchor", "v1"),
    ("FA09_C02_comparison_roles_symmetric.r2.zh-TW", "FA09_C02_comparison_roles_symmetric", "clarify", "v2"),
    ("FA10_D03_two_month_combined_total.ja", "FA10_D03_two_month_combined_total", "decline", "v1"),
    ("FA11_D04_overview_plus_attendance.en", "FA11_D04_overview_plus_attendance", "decline", "v1"),
)
_ASSET_SHA = {
    "cases": "018bfa0bcc65a0225bb3787a7cdabcf64457dd9e1fba2e8ad7671228e9aced47",
    "oracles": "1839a9994922d631618a5e0d1fa7e432b0132bfa86f70dbe06286e6cdf080fa5",
    "panel": "689b81e20d0b2c5b93eaf13698eaaefbf9ea9ebfe0bb8c0b046cdd2e98c39c1f",
}
_ROUTE = {"retries": "enabled", "fallback": "disabled", "cache": "disabled"}
_PACKET_FIELDS = formal._PACKET_FIELDS | {
    "preselection", "selection", "schedule", "schedule_sha256", "comparison_policy",
    "comparison_policy_sha256", "historical_quality",
}


def historical_quality() -> dict:
    """Immutable ancestry, not an input to recompute promotion or extra trials."""
    return {"report_sha256": "be8c381fb8945fbb621962e07b83c6db5e2e44028a72db15729d428b7a7741da",
            "correct_inputs": 25, "total_inputs": 28, "promotion": "failed",
            "quality_promotion_remains_failed": True}


def settings() -> dict:
    return {**evaluator.settings(18), "execution": "owner_authorized_stability_characterization_only",
            "selected_semantic_inputs": 6, "trials_per_input": 3, "max_runtime_invocations": 18,
            "client_fallback": 0, "resend": 0, "continuation": 0, "best_of": 0}


def stop_policy() -> dict:
    return {**formal.stop_policy(), "version": STOP_VERSION,
            "authorization": "Exact stability packet and Issue #52 authorization required before credentials.",
            "semantic_failures": "Grade every scheduled trial; quality failures and instability never stop the run."}


def comparison_policy() -> dict:
    return {"version": "p3-stability-comparison-v1", "pairs": [[1, 2], [1, 3], [2, 3]],
            "possible_pairs": 18, "identity": "frozen_actual_action_and_actual_signature",
            "comparability": "completed_valid_semantics_no_operational_error_or_unsettled_attempt",
            "invalid_missing_unreturned": "excluded_not_agreement_or_flip",
            "correctness": "frozen_p3_scoring_per_input", "diagnostics_overlap": True,
            "gate": {"completed_trials": 18, "correct_trials": 18, "comparable_pairs": 18,
                     "semantic_flips": 0, "checked_wrong_count": 0},
            "claim": "observed_slice_characterization_not_fresh_promotion_or_failure_rate_estimate"}


def data_boundary() -> dict:
    return {**formal.data_boundary(),
            "quality_claim": "observed_stability_only_formal_quality_promotion_remains_failed"}


def command_template(accepted_commit: str, policies: dict) -> list[str]:
    argv = formal.command_template(accepted_commit, policies)
    argv[1] = "tools/p3_stability_run.py"
    argv[-1] = "<FRESH_STABILITY_OUTPUT>"
    return argv


def trial_schedule(selected: list[dict]) -> list[dict]:
    """Resolve only the owner-fixed identities; never rename semantic cases/oracles."""
    preselection = allocation.stability_preselection()
    if preselection["sha256"] != PRESELECTION_SHA or not isinstance(selected, list) or len(selected) != 6:
        raise assets.P3Error("invalid_panel")
    for row, (case_id, family_id, cohort, revision), slot in zip(selected, _SELECTED, preselection["inputs"]):
        if (row.get("case_id") != case_id or row.get("family_id") != family_id
                or row.get("language") != slot["language"] or row.get("cohort") != cohort
                or row.get("expected_branch") != ("answer" if cohort == "anchor" else cohort)
                or row.get("oracle_id") != family_id + "." + revision
                or row.get("exposure") != ("exposed_regression" if cohort == "anchor" else "frozen_fresh")
                or row.get("must_pass") is not True or row.get("observational") is not False):
            raise assets.P3Error("invalid_panel")
    return [{**deepcopy(row), "trial_number": trial, "round_number": trial,
             "execution_order": (trial - 1) * 6 + index}
            for trial in range(1, 4) for index, row in enumerate(selected, 1)]


def _selection(inputs):
    lookup = {row["case_id"]: row for row in inputs}
    if len(lookup) != len(inputs) or any(item[0] not in lookup for item in _SELECTED):
        raise assets.P3Error("invalid_panel")
    selected = [deepcopy(lookup[item[0]]) for item in _SELECTED]
    trial_schedule(selected)
    return selected


def _comparable(row):
    return (row["status"] == "completed" and row.get("phase") == "graded"
            and row["actual_action"] in assets.BRANCHES and row["actual_signature"] is not None
            and row["outcome"] not in ("invalid_output", "operational_failure", "not_run", None)
            and row.get("operational_error") is None and row.get("runner_error_code") is None
            and row.get("error_code") in (None, "model_declined")
            and row.get("attempt_evidence_status") == "matched"
            and not row.get("attempt_may_be_in_flight") and not row.get("diagnostics"))


def summarize(report: dict) -> dict:
    """Aggregate frozen grades/signatures, never another quality grader or promotion."""
    rows = report["results"]
    if len(rows) != 18:
        raise assets.P3Error("invalid_scoring")
    # The frozen scorer already defines per-input correctness. Reuse its neutral
    # accounting separately for each unique-case round; discard promotion/family
    # summaries. No invented semantic case IDs and no duplicated success list.
    correctness = []
    for offset in (0, 6, 12):
        batch = [{**row, "order": index} for index, row in enumerate(rows[offset:offset + 6], 1)]
        scored = p3_scoring.summarize(batch, batch, panel_kind="development", run_status=report["status"])
        correctness.extend(row["correct"] for row in scored["per_input"])
    counts = dict.fromkeys(("comparable_pairs", "semantic_flips", "false_refusal_flips",
                           "clarification_flips", "recipe_request_flips"), 0)
    pairs = []
    for index in range(6):
        trials = [rows[index + offset] for offset in (0, 6, 12)]
        for left, right in combinations(trials, 2):
            comparable = _comparable(left) and _comparable(right)
            flip = (left["actual_action"] != right["actual_action"]
                    or left["actual_signature"] != right["actual_signature"]) if comparable else None
            counts["comparable_pairs"] += int(comparable)
            counts["semantic_flips"] += int(flip is True)
            actions = {left["actual_action"], right["actual_action"]}
            if flip:
                counts["false_refusal_flips"] += int(left["expected_branch"] == "answer"
                                                    and actions == {"answer", "decline"})
                counts["clarification_flips"] += int("clarify" in actions)
                counts["recipe_request_flips"] += int(actions == {"answer"})
            pairs.append({"case_id": left["case_id"], "trials": [left["trial_number"], right["trial_number"]],
                          "comparable": comparable, "semantic_flip": flip})
    status = Counter(row["status"] for row in rows)
    wrong = sum(row["checked_wrong"] for row in rows)
    gates = {"all_completed": status["completed"] == 18, "all_correct": sum(correctness) == 18,
             "all_pairs_comparable": counts["comparable_pairs"] == 18,
             "no_semantic_flips": counts["semantic_flips"] == 0, "no_checked_wrong": wrong == 0}
    return {"semantic_families": 6, "selected_inputs": 6, "trial_executions": 18,
            "completed_trials": status["completed"], "correct_trials": sum(correctness),
            "possible_pairs": 18, **counts, "checked_wrong_count": wrong,
            "invalid_trials": sum(row["outcome"] == "invalid_output" for row in rows),
            "operational_failures": sum(row["outcome"] == "operational_failure"
                                        or row.get("operational_error") is not None
                                        and row["outcome"] != "invalid_output" for row in rows),
            "not_run_trials": status["not_run"], "pending_trials": status["pending"],
            "in_progress_trials": status["in_progress"], "pairs": pairs,
            "flip_rate": p3_scoring._score(counts["semantic_flips"], counts["comparable_pairs"])["fraction"],
            "gates": gates, "stability_passed": report["status"] == "complete" and all(gates.values()),
            "quality_promotion_remains_failed": True}


def _summarize(report):
    report["summary"] = summarize(report)


def _packet_contract(packet):
    assets.object_fields(packet, _PACKET_FIELDS)
    if (packet["version"] != PACKET_VERSION or packet["purpose"] != "one_frozen_stability_characterization"
            or not formal._same(packet["preselection"], allocation.stability_preselection())
            or not formal._same(packet["selection"], _selection(packet["inputs"]))
            or not formal._same(packet["schedule"], trial_schedule(packet["selection"]))
            or packet["schedule_sha256"] != assets.digest(packet["schedule"])
            or not formal._same(packet["historical_quality"], historical_quality())
            or not formal._same(packet["settings"], settings()) or packet["settings_sha256"] != assets.digest(settings())
            or not formal._same(packet["stop_policy"], stop_policy()) or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or not formal._same(packet["comparison_policy"], comparison_policy())
            or packet["comparison_policy_sha256"] != assets.digest(comparison_policy())
            or not formal._same(packet["data_boundary"], data_boundary())
            or packet["command_template"] != command_template(packet["accepted_commit"], _ROUTE)
            or packet["gateway_policy"] != smoke.policy_attestation(_ROUTE, required=True)
            or packet["transport_security"] != "unencrypted_http"
            or any(packet["assets"][key]["sha256"] != value for key, value in _ASSET_SHA.items())):
        raise assets.P3Error("invalid_manifest")
    # Reuse archived formal SOURCE membership validation, not its execution
    # semantics or 28-attempt authorization. The emitted packet is stability-only.
    source = {key: packet[key] for key in formal._PACKET_FIELDS}
    source.update(version=formal.PACKET_VERSION, purpose="one_formal_quality_panel",
                  settings=formal.settings(), settings_sha256=assets.digest(formal.settings()),
                  stop_policy=formal.stop_policy(), stop_policy_sha256=assets.digest(formal.stop_policy()),
                  data_boundary=formal.data_boundary(), command_template=formal.command_template(
                      packet["accepted_commit"], _ROUTE))
    formal._packet_contract(source)


def build_packet(database: Path, *, freeze_path: Path, preparation_path: Path, accepted_commit: str,
                 gateway_policies: dict, transport_security: str):
    if gateway_policies != _ROUTE or transport_security != "unencrypted_http":
        raise assets.P3Error("invalid_configuration")
    source, panel = formal.build_packet(database, freeze_path=freeze_path, preparation_path=preparation_path,
                                       accepted_commit=accepted_commit, gateway_policies=gateway_policies,
                                       transport_security=transport_security)
    selected = _selection(source["inputs"])
    schedule = trial_schedule(selected)
    packet = {**source, "version": PACKET_VERSION, "purpose": "one_frozen_stability_characterization",
              "preselection": allocation.stability_preselection(), "selection": selected, "schedule": schedule,
              "schedule_sha256": assets.digest(schedule), "historical_quality": historical_quality(),
              "settings": settings(), "settings_sha256": assets.digest(settings()),
              "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
              "comparison_policy": comparison_policy(), "comparison_policy_sha256": assets.digest(comparison_policy()),
              "data_boundary": data_boundary(), "command_template": command_template(accepted_commit, _ROUTE)}
    _packet_contract(packet)
    return packet, panel


def validate_packet(path: Path, database: Path, *, accepted_commit: str):
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise assets.P3Error("accepted_commit_required")
    current, panel = build_packet(database, freeze_path=Path(packet["locations"]["freeze"]),
                                 preparation_path=Path(packet["locations"]["preparation"]),
                                 accepted_commit=accepted_commit, gateway_policies=_ROUTE,
                                 transport_security="unencrypted_http")
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


def _authorization(value, packet_sha):
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference"})
    if (value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha
            or not isinstance(value["owner_authorization_reference"], str)
            or not _OWNER.fullmatch(value["owner_authorization_reference"])):
        raise assets.P3Error("invalid_manifest")
    formal._hash(packet_sha)
    return value


def bind_authorization(packet_path: Path, reference: str, output_path: Path):
    packet = assets.read_asset(packet_path)
    _packet_contract(packet)
    digest = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference}, digest)
    live._write_authorization(output_path, value)
    return value


def _manifest(packet, packet_sha, authorization, authorization_sha):
    return {**formal._manifest(packet, packet_sha, authorization, authorization_sha),
            "manifest_version": MANIFEST_VERSION, "panel_kind": "stability",
            "inputs": packet["schedule"], "order": [row["case_id"] for row in packet["schedule"]],
            "preselection": packet["preselection"], "selection": packet["selection"],
            "schedule_sha256": packet["schedule_sha256"], "historical_quality": packet["historical_quality"]}


def _report(manifest, packet):
    report = formal._report(manifest, packet)
    report.update(report_version=REPORT_VERSION,
                  scope="Observed frozen stability slice only; P3.5 quality promotion remains failed.",
                  **{key: manifest[key] for key in (
                      "preselection", "selection", "schedule_sha256", "historical_quality")})
    return report


def _entries(panel, packet):
    cases = {case.case_id: case for case in panel.cases}
    return tuple(evaluator._ExecutionEntry(cases[row["case_id"]], panel.oracle_for(cases[row["case_id"]]), row)
                 for row in packet["schedule"])


def _expected_model(packet):
    """The accepted stability slice is a 31B-only historical contract."""
    _packet_contract(packet)
    return None


class _LiveEvidence(live._LiveEvidence):
    maximum = 18
    summarize = staticmethod(_summarize)


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict, clock=time.monotonic):
    return await live._run_live(database, output_dir, packet_path=packet_path, authorization_path=authorization_path,
                                accepted_commit=accepted_commit, env_file=env_file,
                                gateway_policies=gateway_policies, clock=clock, contract=sys.modules[__name__])


def read_report(path: Path):
    """Archive-only inspection; never needs current checkout, DB, env or fresh payloads."""
    # Terminal candidates/checkpoints are durable failure evidence, not published
    # results. Only commit_terminal promotes a candidate to this authoritative name.
    if path.name != "report.json":
        raise assets.P3Error("invalid_asset")
    packet = assets.read_asset(path.parent / "packet.json")
    _packet_contract(packet)
    packet_sha = evaluator._pin(path.parent / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(path.parent / "authorization.json"), packet_sha)
    expected_manifest = _manifest(packet, packet_sha, authorization,
                                  evaluator._pin(path.parent / "authorization.json")["sha256"])
    manifest = assets.read_asset(path.parent / "manifest.json")
    if not formal._same(manifest, expected_manifest):
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    expected = _report(manifest, packet)
    live._validate_report(report, manifest, expected, packet["schedule"], maximum=18,
                          transport_security=packet["transport_security"], summarize=_summarize)
    if any(not formal._same(report[key], expected[key]) for key in (
            "preselection", "selection", "schedule_sha256", "historical_quality")):
        raise assets.P3Error("invalid_asset")
    return report


def main(argv=None):
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "freeze",
                 "preparation", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    parser.add_argument("--transport-security", choices=("unencrypted_http",))
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"prepare", "freeze", "preparation", "transport_security"} | common if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output"} if args.bind_authorization else
                   {"live", "packet", "authorization", "env_file"} | common if args.live else
                   {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.prepare:
            result = prepare(args.db, args.output_dir, freeze_path=args.freeze, preparation_path=args.preparation,
                             accepted_commit=args.accepted_commit, gateway_policies=policies,
                             transport_security=args.transport_security)
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
                "upstream_inference_attempts", "transport_security", "summary")}
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
