"""Synthetic accounting/allocation scaffolding, not frozen-fresh case assets.

These metadata-only records contain no questions, gold or runtime expectations.
Exposure labels exercise allocation arithmetic; they certify no fresh cases.
"""

import copy
import json
import unittest

from tools.p3_assets import EXPOSURES, LANGUAGES, OUTCOMES, P3Error
from tools.p3_scoring import required_successes, summarize, validate_formal_allocation


SUCCESS = {"answer": "complete_correct", "clarify": "correct_clarification", "decline": "correct_decline"}
SIGNATURE = "a" * 64
OTHER_SIGNATURE = "b" * 64


def metadata(family="synthetic-1", languages=("en",), *, cohort="answer",
             exposure="design_seen", must_pass=True, observational=False, start=1):
    """Abstract synthetic scaffolding: IDs/references do not identify any assets."""
    return [{
        "order": start + index, "case_id": f"{family}-variant-{index + 1}", "family_id": family,
        "language": language, "expected_branch": "answer" if cohort == "anchor" else cohort,
        "cohort": cohort, "exposure": exposure, "must_pass": must_pass, "observational": observational,
        "semantic_signature": f"synthetic-allocation-only:{family}",
        "provenance": {"origin": "synthetic_allocation_scaffolding", "frozen_case_asset": False},
        "oracle_id": f"synthetic-no-oracle-{family}",
        "question_sha256": "0" * 64,
        "question_reference": {"kind": "synthetic_allocation_scaffolding", "asset": None},
    } for index, language in enumerate(languages)]


def successes(inputs):
    return [{
        "case_id": item["case_id"], "status": "completed", "outcome": SUCCESS[item["expected_branch"]],
        "checked_wrong": False, "actual_signature": SIGNATURE,
    } for item in inputs]


def formal_scaffolding():
    """Only a synthetic allocation matrix, never formal questions/oracles/cases."""
    rows = []
    groups = (
        ("answer", "frozen_fresh", (LANGUAGES, LANGUAGES, LANGUAGES, ("en",), ("zh-TW",),
                                   ("ja",), ("en",), ("zh-TW",))),
        ("answer", "exposed_regression", (("ja",), ("en",), ("zh-TW",), ("ja",))),
        ("clarify", "frozen_fresh", (LANGUAGES, LANGUAGES)),
        ("clarify", "exposed_regression", (("en",), ("zh-TW",))),
        ("decline", "frozen_fresh", (LANGUAGES, LANGUAGES)),
        ("decline", "exposed_regression", (("ja",), ("en",), ("ja",))),
        ("anchor", "exposed_regression", (LANGUAGES, LANGUAGES, LANGUAGES)),
    )
    for cohort, exposure, variants in groups:
        for index, languages in enumerate(variants):
            rows.extend(metadata(f"synthetic-{cohort}-{exposure}-{index}", languages,
                                 cohort=cohort, exposure=exposure, start=len(rows) + 1))
    return rows


class ScoringAssertions(unittest.TestCase):
    def summary(self, inputs, results=None, **options):
        return summarize(inputs, successes(inputs) if results is None else results,
                         panel_kind=options.get("panel_kind", "development"),
                         run_status=options.get("run_status", "complete"))

    def assert_score(self, score, numerator, denominator, fraction=None):
        self.assertEqual((score["numerator"], score["denominator"]), (numerator, denominator))
        if fraction is not None:
            self.assertEqual(score["fraction"], {"numerator": fraction[0], "denominator": fraction[1]})
        elif denominator == 0:
            self.assertIsNone(score["fraction"])

    def assert_invalid(self, inputs, results=None, *, code="invalid_scoring", **options):
        with self.assertRaises(P3Error) as raised:
            self.summary(inputs, results, **options)
        self.assertEqual(str(raised.exception), code)


class P3ScoringTests(ScoringAssertions):
    def test_translations_count_as_one_family_but_three_language_inputs(self):
        inputs = metadata(languages=LANGUAGES)
        report = self.summary(inputs)
        self.assertEqual((report["semantic_families"], report["input_count"]), (1, 3))
        self.assert_score(report["answer_score"], 1, 1, (1, 1))
        family = report["per_family"]["synthetic-1"]
        self.assertTrue(family["family_all_variants_correct"])
        self.assertTrue(family["family_all_variants_agree"])
        for language in LANGUAGES:
            self.assert_score(report["per_language"][language]["input_score"], 1, 1, (1, 1))

    def test_one_failed_required_variant_fails_family_without_dropping_input(self):
        inputs = metadata(languages=LANGUAGES)
        results = successes(inputs)
        results[1].update(outcome="wrong_value", actual_signature=OTHER_SIGNATURE)
        report = self.summary(inputs, results)
        self.assert_score(report["answer_score"], 0, 1, (0, 1))
        self.assertEqual(sum(report["outcomes"].values()), 3)
        self.assertFalse(report["per_family"]["synthetic-1"]["family_all_variants_correct"])
        self.assertFalse(report["per_family"]["synthetic-1"]["family_all_variants_agree"])

    def test_identical_wrong_outcomes_with_different_values_disagree(self):
        inputs = metadata(languages=("en", "ja"))
        results = successes(inputs)
        for row, signature in zip(results, (SIGNATURE, OTHER_SIGNATURE)):
            row.update(outcome="wrong_value", actual_signature=signature)
        family = self.summary(inputs, results)["per_family"]["synthetic-1"]
        self.assertFalse(family["family_all_variants_correct"])
        self.assertFalse(family["family_all_variants_agree"])

    def test_all_wrong_same_actual_meaning_agrees_without_becoming_correct(self):
        inputs = metadata(languages=LANGUAGES)
        results = successes(inputs)
        for row in results:
            row["outcome"] = "wrong_request"
        family = self.summary(inputs, results)["per_family"]["synthetic-1"]
        self.assertFalse(family["family_all_variants_correct"])
        self.assertTrue(family["family_all_variants_agree"])

    def test_agreement_is_not_comparison_of_primary_outcome_labels(self):
        inputs = metadata(languages=("en", "ja"))
        results = successes(inputs)
        results[0]["outcome"] = "wrong_coverage"
        results[1]["outcome"] = "wrong_value"
        family = self.summary(inputs, results)["per_family"]["synthetic-1"]
        self.assertTrue(family["family_all_variants_agree"])
        self.assertFalse(family["family_all_variants_correct"])

    def test_missing_signature_is_unassessed_not_agreement_or_invented_failure(self):
        inputs = metadata(languages=LANGUAGES)
        results = successes(inputs)
        results[1]["actual_signature"] = None
        family = self.summary(inputs, results)["per_family"]["synthetic-1"]
        self.assertTrue(family["family_all_variants_correct"])
        self.assertIsNone(family["family_all_variants_agree"])
        for row in results:
            row.update(outcome="invalid_output", actual_signature=None)
        family = self.summary(inputs, results)["per_family"]["synthetic-1"]
        self.assertFalse(family["family_all_variants_correct"])
        self.assertIsNone(family["family_all_variants_agree"])

    def test_single_variant_agreement_requires_an_actual_signature(self):
        inputs = metadata()
        results = successes(inputs)
        self.assertTrue(self.summary(inputs, results)["per_family"]["synthetic-1"]["family_all_variants_agree"])
        results[0]["actual_signature"] = None
        self.assertIsNone(self.summary(inputs, results)["per_family"]["synthetic-1"]["family_all_variants_agree"])

    def test_explicit_families_are_not_automatically_deduplicated_by_signature(self):
        inputs = metadata("synthetic-1") + metadata("synthetic-2", start=2)
        inputs[1]["semantic_signature"] = inputs[0]["semantic_signature"]
        report = self.summary(inputs)
        self.assertEqual(report["semantic_families"], 2)
        self.assert_score(report["answer_score"], 2, 2, (1, 1))

    def test_distinct_same_language_variants_remain_required(self):
        inputs = metadata(languages=("en", "en"))
        results = successes(inputs)
        results[1]["outcome"] = "partial"
        report = self.summary(inputs, results)
        self.assert_score(report["answer_score"], 0, 1)
        self.assert_score(report["per_language"]["en"]["input_score"], 1, 2, (1, 2))
        self.assertEqual(report["per_family"]["synthetic-1"]["case_ids"], [row["case_id"] for row in inputs])

    def test_nonmandatory_family_does_not_make_its_failed_variant_optional(self):
        inputs = metadata(languages=LANGUAGES, must_pass=False)
        results = successes(inputs)
        results[1]["outcome"] = "false_refusal"
        report = self.summary(inputs, results)
        self.assert_score(report["answer_score"], 0, 1)
        self.assert_score(report["by_cohort"]["answer"]["mandatory_score"], 0, 0)

    def test_observational_successes_and_failures_never_inflate_scored_groups(self):
        inputs = metadata("synthetic-scored") + metadata(
            "synthetic-observed", LANGUAGES, observational=True, start=2)
        for observed_outcome in ("complete_correct", "wrong_request"):
            with self.subTest(outcome=observed_outcome):
                results = successes(inputs)
                results[0]["outcome"] = "partial"
                for row in results[1:]:
                    row["outcome"] = observed_outcome
                report = self.summary(inputs, results)
                self.assertEqual((report["scored_families"], report["observational_families"]), (1, 1))
                self.assert_score(report["answer_score"], 0, 1)
                self.assert_score(report["by_exposure"]["design_seen"]["family_score"], 0, 1)
                self.assertEqual(report["input_count"], 4)
                self.assertEqual(report["per_language"]["ja"]["outcomes"], {observed_outcome: 1})
                self.assert_score(report["per_language"]["ja"]["input_score"], 0, 0)
                self.assertEqual(report["per_language"]["ja"]["observational_input_count"], 1)

    def test_checked_wrong_veto_includes_observational_rows(self):
        inputs = metadata(observational=True)
        results = successes(inputs)
        results[0]["checked_wrong"] = True
        report = self.summary(inputs, results)
        self.assertTrue(report["checked_wrong_veto"])
        self.assertEqual(report["checked_wrong_count"], 1)
        self.assertEqual(report["checked_wrong_case_ids"], [inputs[0]["case_id"]])
        self.assertFalse(report["promotion"]["gates"]["no_checked_wrong"])
        self.assert_score(report["answer_score"], 0, 0)

    def test_cohorts_and_exposures_have_separate_denominators(self):
        inputs = []
        for cohort in ("answer", "clarify", "decline", "anchor"):
            for exposure in EXPOSURES:
                inputs.extend(metadata(f"synthetic-{cohort}-{exposure}", LANGUAGES,
                                       cohort=cohort, exposure=exposure, start=len(inputs) + 1))
        report = self.summary(inputs)
        self.assert_score(report["answer_score"], 3, 3)
        self.assert_score(report["fresh_answer_score"], 1, 1)
        for cohort in ("answer", "clarify", "decline", "anchor"):
            self.assert_score(report["by_cohort"][cohort]["family_score"], 3, 3)
            for exposure in EXPOSURES:
                self.assert_score(report["by_cohort"][cohort]["by_exposure"][exposure]["family_score"], 1, 1)
        for exposure in EXPOSURES:
            self.assert_score(report["by_exposure"][exposure]["family_score"], 4, 4)
        for language in LANGUAGES:
            for cohort in ("answer", "clarify", "decline", "anchor"):
                self.assert_score(report["per_language"][language]["by_cohort"][cohort], 3, 3)

    def test_wrong_branch_success_label_does_not_score(self):
        for cohort, wrong in (("answer", "correct_decline"), ("clarify", "complete_correct"),
                              ("decline", "correct_clarification"), ("anchor", "correct_decline")):
            with self.subTest(cohort=cohort):
                inputs = metadata(cohort=cohort)
                results = successes(inputs)
                results[0]["outcome"] = wrong
                self.assert_score(self.summary(inputs, results)["by_cohort"][cohort]["family_score"], 0, 1)

    def test_all_failure_outcomes_stay_in_denominator(self):
        inputs = metadata()
        for outcome in OUTCOMES:
            if outcome in ("complete_correct", "synthesis_error"):
                continue
            with self.subTest(outcome=outcome):
                results = successes(inputs)
                results[0].update(outcome=outcome, status="not_run" if outcome == "not_run" else "completed",
                                  actual_signature=None if outcome == "not_run" else SIGNATURE)
                report = self.summary(inputs, results)
                self.assert_score(report["answer_score"], 0, 1, (0, 1))
                self.assertEqual(report["outcomes"], {outcome: 1})

    def test_empty_groups_have_null_fractions_and_cannot_pass(self):
        report = self.summary([])
        self.assert_score(report["answer_score"], 0, 0)
        self.assert_score(report["fresh_answer_score"], 0, 0)
        self.assertEqual(report["outcomes"], {})
        for language in LANGUAGES:
            self.assert_score(report["per_language"][language]["input_score"], 0, 0)
        self.assertFalse(report["promotion"]["eligible"])
        self.assertFalse(report["promotion"]["passed"])
        self.assertFalse(report["promotion"]["gates"]["fresh_answer_threshold"])

    def test_exact_reduced_fraction_keeps_unreduced_count_denominator(self):
        inputs = []
        for index in range(4):
            inputs.extend(metadata(f"synthetic-{index}", start=len(inputs) + 1))
        results = successes(inputs)
        for row in results[2:]:
            row["outcome"] = "partial"
        report = self.summary(inputs, results)
        self.assert_score(report["answer_score"], 2, 4, (1, 2))
        self.assert_score(report["per_language"]["en"]["input_score"], 2, 4, (1, 2))

    def test_unresolved_rows_keep_status_and_null_outcome_not_not_run(self):
        inputs = metadata(languages=LANGUAGES)
        results = successes(inputs)
        results[0].update(status="pending", outcome=None, actual_signature=None)
        results[1].update(status="in_progress", outcome=None, actual_signature=None)
        for run_status in ("pending", "prepared", "in_progress", "incomplete", "complete"):
            with self.subTest(run_status=run_status):
                report = self.summary(inputs, results, run_status=run_status)
                self.assertEqual(report["outcomes"], {"complete_correct": 1})
                self.assertEqual(report["statuses"], {"pending": 1, "in_progress": 1, "completed": 1, "not_run": 0})
                self.assertIsNone(report["per_input"][0]["outcome"])
                self.assert_score(report["answer_score"], 0, 1)
                self.assertIsNone(report["per_family"]["synthetic-1"]["family_all_variants_agree"])
                self.assertFalse(report["promotion"]["passed"])
                self.assertFalse(report["promotion"]["gates"]["complete_run"])

    def test_frozen_interleaved_order_is_preserved(self):
        inputs = metadata("synthetic-a", ("en", "ja")) + metadata("synthetic-b", ("zh-TW",), start=3)
        inputs = [inputs[0], inputs[2], inputs[1]]
        for index, row in enumerate(inputs, 1):
            row["order"] = index
        report = self.summary(inputs)
        self.assertEqual([row["case_id"] for row in report["per_input"]], [row["case_id"] for row in inputs])
        self.assertEqual(report["per_family"]["synthetic-a"]["case_ids"], [inputs[0]["case_id"], inputs[2]["case_id"]])

    def test_pure_deterministic_json_output_ignores_unrelated_runtime_fields(self):
        inputs = metadata(languages=LANGUAGES)
        results = successes(inputs)
        results[0]["unrelated_runtime_field"] = {"not_accounting": [1, 2]}
        before = copy.deepcopy((inputs, results))
        first = self.summary(inputs, results)
        self.assertEqual(first, self.summary(inputs, results))
        self.assertEqual(json.loads(json.dumps(first, allow_nan=False)), first)
        self.assertEqual((inputs, results), before)
        self.assertNotIn("unrelated_runtime_field", first["per_input"][0])
        first["per_family"]["synthetic-1"]["case_ids"].clear()
        first["per_input"][0]["case_id"] = "changed-output"
        self.assertEqual((inputs, results), before)

    def test_input_container_and_records_are_strict(self):
        for inputs in (None, {}, (), "inputs", [None], [[]], [1]):
            with self.subTest(inputs=inputs):
                self.assert_invalid(inputs, [])

    def test_required_scoring_metadata_cannot_be_missing(self):
        for field in ("case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
                      "must_pass", "observational", "semantic_signature", "order"):
            with self.subTest(field=field):
                inputs = metadata()
                results = successes(inputs)
                del inputs[0][field]
                self.assert_invalid(inputs, results)

    def test_ids_signatures_booleans_and_labels_reject_invalid_types(self):
        mutations = {
            "case_id": (None, 1, [], "", "two words"),
            "family_id": (None, 1, {}, "", " family"),
            "language": (None, [], 1, "zh", "EN"),
            "cohort": (None, [], 1, "control"),
            "expected_branch": (None, [], 1, "request"),
            "exposure": (None, [], 1, "fresh"),
            "must_pass": (None, 0, 1, "true"),
            "observational": (None, 0, 1, "false"),
            "semantic_signature": (None, [], 1, "", " \n"),
        }
        for field, values in mutations.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    inputs = metadata()
                    results = successes(inputs)
                    inputs[0][field] = value
                    self.assert_invalid(inputs, results)

    def test_duplicate_case_ids_are_rejected_even_across_families(self):
        inputs = metadata("synthetic-a") + metadata("synthetic-b", start=2)
        inputs[1]["case_id"] = inputs[0]["case_id"]
        self.assert_invalid(inputs, successes(inputs))

    def test_input_order_is_exact_one_based_and_never_bool(self):
        for order in (0, 2, True, 1.0, "1", None):
            with self.subTest(order=order):
                inputs = metadata()
                inputs[0]["order"] = order
                self.assert_invalid(inputs, successes(inputs))
        inputs = metadata(languages=("en", "ja"))
        inputs.reverse()
        self.assert_invalid(inputs, successes(inputs))

    def test_family_metadata_cannot_mix_status_or_meaning(self):
        mutations = {
            "cohort": "anchor", "exposure": "exposed_regression", "must_pass": False,
            "observational": True, "semantic_signature": "different",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                inputs = metadata(languages=LANGUAGES)
                inputs[1][field] = value
                self.assert_invalid(inputs, successes(inputs))
        inputs = metadata(languages=LANGUAGES)
        inputs[1].update(expected_branch="clarify", cohort="clarify")
        self.assert_invalid(inputs, successes(inputs))

    def test_branch_cohort_pairing_is_explicit(self):
        for cohort in ("answer", "clarify", "decline", "anchor"):
            for branch in SUCCESS:
                if branch == ("answer" if cohort == "anchor" else cohort):
                    continue
                with self.subTest(cohort=cohort, branch=branch):
                    inputs = metadata(cohort=cohort)
                    inputs[0]["expected_branch"] = branch
                    self.assert_invalid(inputs, successes(inputs))

    def test_result_inventory_cannot_drop_duplicate_add_or_reorder_variants(self):
        inputs = metadata(languages=LANGUAGES)
        valid = successes(inputs)
        mutations = (valid[:-1], valid + [valid[0]], [valid[0], valid[0], valid[2]], list(reversed(valid)))
        for results in mutations:
            with self.subTest(results=results):
                self.assert_invalid(inputs, results)
        results = successes(inputs)
        results[1]["case_id"] = "unknown-case"
        self.assert_invalid(inputs, results)

    def test_result_types_and_required_fields_reject(self):
        inputs = metadata()
        for results in ({}, (), "results", [None], [[]], [1]):
            with self.subTest(results=results):
                self.assert_invalid(inputs, results)
        with self.assertRaises(P3Error):
            summarize(inputs, None, panel_kind="development", run_status="prepared")
        for field in ("case_id", "outcome", "status", "checked_wrong", "actual_signature"):
            with self.subTest(field=field):
                results = successes(inputs)
                del results[0][field]
                self.assert_invalid(inputs, results)

    def test_result_echoed_order_cannot_disagree(self):
        inputs = metadata()
        for order in (0, 2, True, 1.0, "1", None):
            with self.subTest(order=order):
                results = successes(inputs)
                results[0]["order"] = order
                self.assert_invalid(inputs, results)
        results = successes(inputs)
        results[0]["order"] = 1
        self.assert_score(self.summary(inputs, results)["answer_score"], 1, 1)

    def test_completed_outcome_must_be_first_slice_and_non_null(self):
        inputs = metadata()
        for outcome in (None, [], {}, 1, "", "synthesis_error", "correct", "not_assessed", "not_implemented", "not_run"):
            with self.subTest(outcome=outcome):
                results = successes(inputs)
                results[0]["outcome"] = outcome
                self.assert_invalid(inputs, results)

    def test_status_and_outcome_consistency_is_enforced(self):
        inputs = metadata()
        for status in ("pending", "in_progress", "not_run", "complete", "unknown", None, [], 1):
            with self.subTest(status=status):
                results = successes(inputs)
                results[0]["status"] = status
                self.assert_invalid(inputs, results)
        for mutation in ({"actual_signature": SIGNATURE}, {"checked_wrong": True}, {"outcome": None}):
            with self.subTest(mutation=mutation):
                results = successes(inputs)
                results[0].update(status="not_run", outcome="not_run", actual_signature=None)
                results[0].update(mutation)
                self.assert_invalid(inputs, results)

    def test_checked_wrong_requires_a_boolean(self):
        inputs = metadata()
        for flag in (None, 0, 1, "true", [], {}):
            with self.subTest(flag=flag):
                results = successes(inputs)
                results[0]["checked_wrong"] = flag
                self.assert_invalid(inputs, results)

    def test_actual_signatures_are_sha256_or_null_not_arbitrary_strings(self):
        inputs = metadata()
        for signature in ("", "semantic-name", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 1, [], {}):
            with self.subTest(signature=signature):
                results = successes(inputs)
                results[0]["actual_signature"] = signature
                self.assert_invalid(inputs, results)

    def test_unknown_panel_kind_and_run_status_reject(self):
        inputs = metadata()
        for kind in (None, [], 1, "", "live", "dev"):
            with self.subTest(kind=kind):
                self.assert_invalid(inputs, panel_kind=kind)
        for status in (None, [], 1, "", "completed", "success"):
            with self.subTest(status=status):
                self.assert_invalid(inputs, run_status=status)

    def test_threshold_ceiling_is_exact_for_small_and_large_counts(self):
        for total, required in ((0, 0), (1, 1), (8, 8), (10, 9), (12, 11), (20, 18),
                                (21, 19), (10**30 + 1, 9 * 10**29 + 1)):
            with self.subTest(total=total):
                self.assertEqual(required_successes(total), required)
        for total in (-1, 8.0, True, False, "8", None, []):
            with self.subTest(total=total), self.assertRaises(P3Error) as raised:
                required_successes(total)
            self.assertEqual(str(raised.exception), "invalid_scoring")


class P3FormalScoringTests(ScoringAssertions):
    def formal_summary(self, inputs=None, results=None, *, run_status="complete", panel_kind="formal"):
        inputs = formal_scaffolding() if inputs is None else inputs
        return self.summary(inputs, results, panel_kind=panel_kind, run_status=run_status)

    def assert_invalid_panel(self, inputs):
        with self.assertRaises(P3Error) as raised:
            validate_formal_allocation(inputs)
        self.assertEqual(str(raised.exception), "invalid_panel")

    def test_synthetic_allocation_is_metadata_only_and_matches_all_marginals(self):
        inputs = formal_scaffolding()
        self.assertIsNone(validate_formal_allocation(inputs))
        self.assertEqual((len({row["family_id"] for row in inputs}), len(inputs)), (24, 44))
        self.assertFalse(any("question" in row for row in inputs))
        self.assertTrue(all(row["provenance"]["origin"] == "synthetic_allocation_scaffolding" for row in inputs))
        self.assertTrue(all(row["provenance"]["frozen_case_asset"] is False for row in inputs))
        report = self.formal_summary(inputs)
        self.assertEqual({key: group["input_count"] for key, group in report["per_language"].items()},
                         {"zh-TW": 14, "en": 15, "ja": 15})
        self.assertEqual((report["by_exposure"]["frozen_fresh"]["family_count"],
                          report["by_exposure"]["frozen_fresh"]["input_count"]), (12, 26))
        self.assertEqual((report["by_exposure"]["exposed_regression"]["family_count"],
                          report["by_exposure"]["exposed_regression"]["input_count"]), (12, 18))

    def test_perfect_formal_allocation_passes_separate_gates(self):
        report = self.formal_summary()
        self.assertTrue(report["promotion"]["eligible"])
        self.assertTrue(report["promotion"]["passed"])
        self.assertTrue(all(report["promotion"]["gates"].values()))
        self.assert_score(report["answer_score"], 12, 12, (1, 1))
        self.assert_score(report["fresh_answer_score"], 8, 8, (1, 1))
        self.assertEqual(report["promotion"]["required_answer_successes"], 11)
        self.assertEqual(report["promotion"]["required_fresh_answer_successes"], 8)
        for cohort, count in (("clarify", 4), ("decline", 5), ("anchor", 3)):
            self.assert_score(report["by_cohort"][cohort]["family_score"], count, count)

    def test_one_fresh_failure_cannot_hide_behind_eleven_of_twelve_answers(self):
        inputs = formal_scaffolding()
        results = successes(inputs)
        results[0]["outcome"] = "wrong_value"
        report = self.formal_summary(inputs, results)
        self.assert_score(report["answer_score"], 11, 12, (11, 12))
        self.assert_score(report["fresh_answer_score"], 7, 8, (7, 8))
        self.assertTrue(report["promotion"]["gates"]["answer_threshold"])
        self.assertFalse(report["promotion"]["gates"]["fresh_answer_threshold"])
        self.assertFalse(report["promotion"]["passed"])

    def test_one_exposed_answer_failure_is_mandatory_despite_threshold_pass(self):
        inputs = formal_scaffolding()
        results = successes(inputs)
        index = next(index for index, row in enumerate(inputs)
                     if row["cohort"] == "answer" and row["exposure"] == "exposed_regression")
        results[index]["outcome"] = "false_refusal"
        report = self.formal_summary(inputs, results)
        self.assert_score(report["answer_score"], 11, 12)
        self.assert_score(report["fresh_answer_score"], 8, 8)
        self.assertTrue(report["promotion"]["gates"]["answer_threshold"])
        self.assertTrue(report["promotion"]["gates"]["fresh_answer_threshold"])
        self.assertFalse(report["promotion"]["gates"]["exposed_answer_controls"])
        self.assertFalse(report["promotion"]["passed"])

    def test_each_control_variant_is_mandatory_and_controls_never_boost_answers(self):
        inputs = formal_scaffolding()
        for cohort, gate in (("clarify", "clarification_controls"), ("decline", "decline_controls"),
                             ("anchor", "anchors")):
            indices = [index for index, row in enumerate(inputs) if row["cohort"] == cohort]
            for index in indices:
                with self.subTest(cohort=cohort, index=index):
                    results = successes(inputs)
                    results[index]["outcome"] = "wrong_action"
                    report = self.formal_summary(inputs, results)
                    self.assert_score(report["answer_score"], 12, 12)
                    self.assert_score(report["fresh_answer_score"], 8, 8)
                    self.assertFalse(report["promotion"]["gates"][gate])
                    self.assertFalse(report["promotion"]["passed"])

    def test_checked_wrong_veto_is_independent_of_perfect_primary_outcomes(self):
        inputs = formal_scaffolding()
        for cohort in ("answer", "clarify", "decline", "anchor"):
            with self.subTest(cohort=cohort):
                results = successes(inputs)
                index = next(index for index, row in enumerate(inputs) if row["cohort"] == cohort)
                results[index]["checked_wrong"] = True
                report = self.formal_summary(inputs, results)
                self.assert_score(report["answer_score"], 12, 12)
                self.assertTrue(report["checked_wrong_veto"])
                self.assertFalse(report["promotion"]["gates"]["no_checked_wrong"])
                self.assertFalse(report["promotion"]["passed"])

    def test_formal_failure_taxonomy_never_changes_fixed_denominators(self):
        inputs = formal_scaffolding()
        for outcome in OUTCOMES:
            if outcome in ("complete_correct", "synthesis_error"):
                continue
            with self.subTest(outcome=outcome):
                results = successes(inputs)
                results[0].update(outcome=outcome, status="not_run" if outcome == "not_run" else "completed",
                                  actual_signature=None if outcome == "not_run" else SIGNATURE)
                report = self.formal_summary(inputs, results)
                self.assert_score(report["answer_score"], 11, 12)
                self.assert_score(report["fresh_answer_score"], 7, 8)
                self.assertEqual((report["input_count"], report["semantic_families"]), (44, 24))
                self.assertFalse(report["promotion"]["passed"])

    def test_prepared_incomplete_and_unresolved_formal_runs_cannot_pass(self):
        inputs = formal_scaffolding()
        for run_status in ("prepared", "pending", "in_progress", "incomplete"):
            with self.subTest(run_status=run_status):
                report = self.formal_summary(inputs, run_status=run_status)
                self.assertTrue(report["promotion"]["eligible"])
                self.assertFalse(report["promotion"]["passed"])
        for status in ("pending", "in_progress", "not_run"):
            with self.subTest(status=status):
                results = successes(inputs)
                results[0].update(status=status, outcome="not_run" if status == "not_run" else None,
                                  actual_signature=None)
                report = self.formal_summary(inputs, results)
                self.assertFalse(report["promotion"]["passed"])
                self.assertFalse(report["promotion"]["gates"]["complete_run"])
                self.assert_score(report["fresh_answer_score"], 7, 8)

    def test_development_never_eligible_even_with_perfect_allocation(self):
        report = self.formal_summary(panel_kind="development")
        self.assertTrue(all(report["promotion"]["gates"].values()))
        self.assertFalse(report["promotion"]["eligible"])
        self.assertFalse(report["promotion"]["passed"])

    def test_formal_requires_all_inputs_and_families(self):
        inputs = formal_scaffolding()
        self.assert_invalid_panel(inputs[:-1])
        extra = copy.deepcopy(inputs[-1])
        extra.update(case_id="synthetic-extra", order=45)
        self.assert_invalid_panel(inputs + [extra])
        inputs[-1]["family_id"] = "synthetic-extra-family"
        self.assert_invalid_panel(inputs)
        self.assert_invalid(metadata(), panel_kind="formal", code="invalid_panel")

    def test_formal_cohort_and_exposure_cross_allocation_cannot_be_swapped(self):
        inputs = formal_scaffolding()
        answer = next(row["family_id"] for row in inputs if row["cohort"] == "answer"
                      and row["exposure"] == "frozen_fresh"
                      and sum(other["family_id"] == row["family_id"] for other in inputs) == 1)
        clarification = next(row["family_id"] for row in inputs if row["cohort"] == "clarify"
                             and row["exposure"] == "exposed_regression")
        for row in inputs:
            if row["family_id"] == answer:
                row["exposure"] = "exposed_regression"
            elif row["family_id"] == clarification:
                row["exposure"] = "frozen_fresh"
        self.assert_invalid_panel(inputs)

    def test_formal_exposure_input_counts_are_checked_separately(self):
        inputs = formal_scaffolding()
        source = inputs[0]
        target = next(row for row in inputs if row["cohort"] == "answer"
                      and row["exposure"] == "exposed_regression")
        for field in ("family_id", "exposure", "semantic_signature"):
            source[field] = target[field]
        self.assert_invalid_panel(inputs)

    def test_formal_input_counts_are_checked_not_only_family_counts(self):
        inputs = formal_scaffolding()
        source = next(row for row in inputs if row["cohort"] == "anchor")
        target = next(row for row in inputs if row["cohort"] == "answer"
                      and row["exposure"] == "exposed_regression")
        for field in ("family_id", "cohort", "semantic_signature"):
            source[field] = target[field]
        self.assert_invalid_panel(inputs)

    def test_formal_language_totals_are_fixed(self):
        inputs = formal_scaffolding()
        inputs[0]["language"] = "en"
        self.assert_invalid_panel(inputs)

    def test_formal_disallows_design_seen_observational_and_nonmandatory(self):
        for field, value in (("exposure", "design_seen"), ("observational", True), ("must_pass", False)):
            with self.subTest(field=field):
                inputs = formal_scaffolding()
                family = inputs[0]["family_id"]
                for row in inputs:
                    if row["family_id"] == family:
                        row[field] = value
                self.assert_invalid_panel(inputs)

    def test_exact_deferred_p21_family_case_and_slot_cannot_be_scored(self):
        for field in ("family_id", "case_id", "slot"):
            with self.subTest(field=field):
                inputs = formal_scaffolding()
                family = inputs[0]["family_id"]
                if field == "family_id":
                    for row in inputs:
                        if row["family_id"] == family:
                            row[field] = "P21"
                else:
                    inputs[0][field] = "P21"
                self.assert_invalid_panel(inputs)
        inputs = formal_scaffolding()
        inputs[0]["case_id"] = "P210"
        inputs[0]["slot"] = "P210"
        self.assertIsNone(validate_formal_allocation(inputs))

    def test_formal_malformed_metadata_has_fixed_panel_error(self):
        for inputs in (None, {}, [], [None]):
            with self.subTest(inputs=inputs):
                self.assert_invalid_panel(inputs)
        inputs = formal_scaffolding()
        inputs[0]["observational"] = 0
        self.assert_invalid_panel(inputs)


if __name__ == "__main__":
    unittest.main()
