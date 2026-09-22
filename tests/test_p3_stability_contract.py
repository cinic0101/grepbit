"""Owner-approved P3.7 rulers. Metadata only; never fresh payloads or transport."""
from collections import Counter
import hashlib
import importlib
import unittest

from tools import p3_assets, p3_eval, p3_formal_policy, p3_scoring
from test_p3_formal_policy import revised_scaffolding

IDS = (
    "FA01_A02_overview_explicit_definitions.zh-TW",
    "FA04_A04_compare_year_on_baseline_nonadjacent.en",
    "E03_share_denominator.ja",
    "FA09_C02_comparison_roles_symmetric.r2.zh-TW",
    "FA10_D03_two_month_combined_total.ja",
    "FA11_D04_overview_plus_attendance.en",
)


def selected_metadata():
    """Synthetic metadata with accepted identifiers, not reviewed payloads."""
    rows = revised_scaffolding()
    targets = (("answer", "zh-TW"), ("answer", "en"), ("anchor", "ja"),
               ("clarify", "zh-TW"), ("decline", "ja"), ("decline", "en"))
    selected = []
    used = set()
    for index, (case_id, (cohort, language)) in enumerate(zip(IDS, targets), 1):
        source = next(r for r in rows if r["cohort"] == cohort and r["family_id"] not in used)
        used.add(source["family_id"])
        family = case_id.rsplit(".", 1)[0].removesuffix(".r2")
        selected.append({**source, "order": index, "case_id": case_id, "family_id": family,
                         "language": language, "cohort": cohort,
                         "exposure": "exposed_regression" if cohort == "anchor" else "frozen_fresh",
                         "oracle_id": family + (".v2" if index == 4 else ".v1")})
    return selected


class StabilityContractTests(unittest.TestCase):
    def runner(self):
        self.assertTrue((p3_eval.ROOT / "tools/p3_stability_run.py").is_file(),
                        "Missing accepted capability: a narrow stability runner, not a formal panel mutation")
        return importlib.import_module("tools.p3_stability_run")

    def test_versions_and_fixed_preselection(self):
        runner = self.runner()
        for key, value in (("PACKET_VERSION", "p3-stability-packet-v1"),
                           ("AUTHORIZATION_VERSION", "p3-stability-authorization-v1"),
                           ("MANIFEST_VERSION", "p3-stability-manifest-v1"),
                           ("REPORT_VERSION", "p3-stability-report-v1"),
                           ("STOP_VERSION", "p3-stability-stops-v1")):
            self.assertEqual(getattr(runner, key), value)
        self.assertEqual(p3_formal_policy.stability_preselection()["sha256"],
                         "f7cb2076ea68cf5d675d9c12353c47eded88b8bfa85268aeb7c76e988387ec70")

    def test_exact_schedule_original_ids_and_trial_identity(self):
        schedule = self.runner().trial_schedule(selected_metadata())
        self.assertEqual(len(schedule), 18)
        self.assertEqual([r["case_id"] for r in schedule], list(IDS) * 3)
        self.assertEqual(Counter(r["case_id"] for r in schedule), dict.fromkeys(IDS, 3))
        self.assertEqual(len({r["family_id"] for r in schedule}), 6)
        for order, row in enumerate(schedule, 1):
            self.assertEqual(row["execution_order"], order)
            self.assertEqual(row["trial_number"], (order - 1) // 6 + 1)
            self.assertEqual(row["round_number"], row["trial_number"])

    def test_wrong_selection_order_or_branch_rejected(self):
        runner = self.runner()
        for mutate in (lambda rows: rows.reverse(), lambda rows: rows.pop(),
                       lambda rows: rows[5].update(case_id="FA11_D04_overview_plus_attendance.ja"),
                       lambda rows: rows[0].update(expected_branch="decline"),
                       lambda rows: rows[3].update(oracle_id="old.v1")):
            rows = selected_metadata()
            mutate(rows)
            with self.assertRaises(p3_assets.P3Error):
                runner.trial_schedule(rows)

    def test_bounds_characterization_and_no_formal_promotion(self):
        runner = self.runner()
        settings = runner.settings()
        self.assertEqual(settings["max_client_http_attempts"], 18)
        self.assertEqual(settings["max_runtime_invocations"], 18)
        self.assertEqual(settings["panel_timeout_seconds"], 1200)
        self.assertEqual(settings["concurrency"], 1)
        self.assertEqual(runner.historical_quality()["report_sha256"],
                         "be8c381fb8945fbb621962e07b83c6db5e2e44028a72db15729d428b7a7741da")
        self.assertTrue(runner.historical_quality()["quality_promotion_remains_failed"])

    def completed(self):
        rows = self.runner().trial_schedule(selected_metadata())
        for row in rows:
            row.update(p3_eval._empty_grade())
            row.update(status="completed", phase="graded", runtime_invoked=True,
                       attempt_may_be_in_flight=False, attempt_evidence_status="matched",
                       client_http_attempts=1, runtime_http_attempts=1, error_code=None,
                       runner_error_code=None, actual_action=row["expected_branch"],
                       outcome=p3_scoring._SUCCESS[row["expected_branch"]],
                       actual_signature=hashlib.sha256(row["case_id"].encode()).hexdigest())
        return {"status": "complete", "results": rows}

    def test_all_correct_gate_and_independent_formal_result(self):
        summary = self.runner().summarize(self.completed())
        self.assertEqual(summary["correct_trials"], 18)
        self.assertEqual(summary["comparable_pairs"], 18)
        self.assertEqual(summary["semantic_flips"], 0)
        self.assertTrue(summary["stability_passed"])
        self.assertTrue(summary["quality_promotion_remains_failed"])

    def test_identically_wrong_valid_is_stable_but_not_correct(self):
        report = self.completed()
        for row in report["results"]:
            row.update(actual_action="answer", outcome="wrong_request", actual_signature="a" * 64)
        result = self.runner().summarize(report)
        self.assertEqual(result["comparable_pairs"], 18)
        self.assertEqual(result["semantic_flips"], 0)
        self.assertEqual(result["correct_trials"], 0)
        self.assertFalse(result["stability_passed"])

    def test_two_same_one_different_creates_two_flips(self):
        report = self.completed()
        report["results"][12].update(actual_signature="f" * 64, outcome="wrong_request")
        result = self.runner().summarize(report)
        self.assertEqual(result["comparable_pairs"], 18)
        self.assertEqual(result["semantic_flips"], 2)
        self.assertEqual(result["recipe_request_flips"], 2)
        self.assertFalse(result["stability_passed"])

    def test_action_and_clarification_flip_diagnostics(self):
        for action, diagnostic in (("decline", "false_refusal_flips"), ("clarify", "clarification_flips")):
            report = self.completed()
            report["results"][0].update(actual_action=action, actual_signature="b"*64,
                                         outcome="false_refusal" if action == "decline" else "false_clarification")
            result = self.runner().summarize(report)
            self.assertEqual(result["semantic_flips"], 2)
            self.assertEqual(result[diagnostic], 2)
        report = self.completed()
        report["results"][3].update(actual_signature="c"*64, outcome="wrong_action")
        result = self.runner().summarize(report)
        self.assertEqual(result["semantic_flips"], 2)
        self.assertEqual(result["clarification_flips"], 2)

    def test_noncomparable_never_fabricates_agreement_or_flips(self):
        for changes in ({"outcome": "invalid_output", "actual_signature": None},
                        {"outcome": "operational_failure", "operational_error": "timeout"},
                        {"actual_signature": None}, {"actual_signature": "bad"},
                        {"status": "not_run", "outcome": "not_run", "actual_signature": None},
                        {"status": "in_progress", "outcome": None, "phase": "invoked",
                         "attempt_may_be_in_flight": True}):
            report = self.completed()
            report["results"][0].update(changes)
            if changes == {"actual_signature": "bad"}:
                # Malformed archive evidence fails closed, not a synthetic agreement.
                with self.assertRaises(p3_assets.P3Error):
                    self.runner().summarize(report)
                continue
            result = self.runner().summarize(report)
            self.assertEqual(result["comparable_pairs"], 16)
            self.assertEqual(result["semantic_flips"], 0)
            self.assertFalse(result["stability_passed"])

    def test_checked_wrong_and_incomplete_publication_each_veto_gate(self):
        report = self.completed()
        report["results"][0]["checked_wrong"] = True
        self.assertFalse(self.runner().summarize(report)["stability_passed"])
        report = self.completed()
        report["status"] = "incomplete"
        self.assertFalse(self.runner().summarize(report)["stability_passed"])

    def test_flip_and_missing_signature_each_veto_otherwise_correct_gate(self):
        for change in ({"actual_signature": "f"*64}, {"actual_signature": None}):
            report = self.completed()
            report["results"][0].update(change)
            summary = self.runner().summarize(report)
            self.assertEqual(summary["correct_trials"], 18)
            self.assertEqual(summary["checked_wrong_count"], 0)
            self.assertFalse(summary["stability_passed"])

    def test_action_disagreement_is_flip_even_if_hash_claims_equality(self):
        report = self.completed()
        report["results"][0].update(actual_action="decline", outcome="false_refusal")
        result = self.runner().summarize(report)
        self.assertEqual(result["semantic_flips"], 2)
        self.assertEqual(result["false_refusal_flips"], 2)


if __name__ == "__main__":
    unittest.main()
