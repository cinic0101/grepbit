"""Exposed mutation controls for evaluator sensitivity, not fresh semantic cases."""
from contextlib import closing
import copy
from dataclasses import replace
from datetime import timezone
import importlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from grepbit import grouped, kernel, recipe_model
from grepbit.clarification import Clarification, CountBasis, SemanticChoice
from grepbit.gateway import ModelError
from grepbit.presentation import ClarificationPresentation, render_clarification
from grepbit.recipe_model import RecipeInterpretation, RecipeProposal
from tools import fixture, p3_expectations, p3_grading
from tools.p3_assets import AnswerOracle, ClarifyOracle, DeclineOracle, load_panel, parse_oracle


ROOT = Path(__file__).resolve().parents[1]
EXPECTATION_IDENTITY = {
    "version": "p3-evidence-expectations-v1",
    "sha256": "70354f181c66dad53acb5b163af128ba78a11d4eeecaa800f234c6058183934a",
}


class P3GradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT / ".artifacts")
        cls.database = Path(cls.temporary.name) / "fixture.sqlite"
        fixture.build(cls.database)
        cls.panel = load_panel(ROOT / "evals/p3/development-panel-v1.json")
        cls.answers = {oracle.to_dict()["recipe_id"]: oracle for oracle in cls.panel.oracles
                       if isinstance(oracle, AnswerOracle)}
        cls.clarifies = {oracle.clarification.kind: oracle for oracle in cls.panel.oracles
                        if isinstance(oracle, ClarifyOracle)}
        cls.decline = next(oracle for oracle in cls.panel.oracles if isinstance(oracle, DeclineOracle))
        cls.native = {}
        for recipe, oracle in cls.answers.items():
            pack = getattr(recipe_model, f"execute_{recipe}")(cls.database, oracle.request)
            cls.native[recipe] = RecipeInterpretation(RecipeProposal(recipe, oracle.request), pack, None, {})

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def assess(self, result, oracle, outcome, *, checked_wrong=False):
        with (patch("sqlite3.connect", side_effect=AssertionError("A grader must not query")),
              patch.object(recipe_model, "interpret_recipe_and_execute",
                           side_effect=AssertionError("A grader must not reinterpret"))):
            grade = p3_grading.grade(result, oracle)
        self.assertEqual(grade["outcome"], outcome)
        self.assertEqual(grade["checked_wrong"], checked_wrong)
        self.assertEqual(set(grade["layers"]), set(p3_grading.LAYERS))
        self.assertTrue(set(grade["layers"].values()) <= {"passed", "failed", "not_assessed"})
        return grade

    def clarify(self, kind="count_basis"):
        semantic = self.clarifies[kind].clarification
        semantic = Clarification(semantic.kind, tuple(
            SemanticChoice(f"runtime_{index}", choice.semantic_value)
            for index, choice in enumerate(semantic.choices)))
        return RecipeInterpretation(None, None, None, {}, semantic, render_clarification(semantic))

    def partial(self):
        result = self.native["overview"]
        pack = result.analysis_pack
        slots = tuple(replace(slot, state="unavailable", fact_id=None, reason="component_timeout")
                      if slot.slot_id == "daily_amount" else slot for slot in pack.slots)
        partial = replace(pack, grouped_facts=tuple(fact for fact in pack.grouped_facts
                                                   if fact.dimension != "booking_day"),
                          slots=slots, status="partial")
        return replace(result, analysis_pack=partial)

    def test_all_three_reviewed_answer_oracles_pass_without_grader_execution(self):
        for recipe, result in self.native.items():
            with self.subTest(recipe=recipe):
                grade = self.assess(result, self.answers[recipe], "complete_correct")
                self.assertEqual({grade["layers"][key] for key in (
                    "action", "recipe", "request", "execution", "coverage", "fact_selection", "values")}, {"passed"})
                self.assertEqual(len(grade["actual_signature"]), 64)

    def test_evidence_expectations_have_a_pinned_independent_identity(self):
                self.assertEqual(p3_expectations.identity(), EXPECTATION_IDENTITY)
                self.assertEqual(set(p3_expectations.PROVENANCE), {
                    "scalar_required_checks", "grouped_required_checks", "dimension_profile_id", "ordering"})
                for references in p3_expectations.PROVENANCE.values():
                    self.assertTrue(references)
                    self.assertTrue(all(ref.startswith("e8c3a455bd4e09a266a772be599fe851d405df78:")
                                        for ref in references))
                with self.assertRaises(TypeError):
                    p3_expectations.ORDERING["course"] = ("value_asc",)

    def test_import_time_expectations_ignore_corrupted_product_constants(self):
                mutations = (
                    ("scalar_checks", kernel, "_CHECKS", ("corrupted_scalar_check",)),
                    ("grouped_checks", grouped, "_GROUP_CHECKS", ("corrupted_grouped_check",)),
                    ("category_ordering", grouped, "_ORDERING",
                     {**grouped._ORDERING, "category": ("key_desc",)}),
                    ("course_ordering", grouped, "_ORDERING",
                     {**grouped._ORDERING, "course": ("value_asc", "key_asc")}),
                    ("dimension_profile", grouped, "_DIMENSION_PROFILE", "corrupted_dimension_profile"),
                )
                for name, owner, attribute, corrupted in mutations:
                    with self.subTest(mutation=name):
                        try:
                            with patch.object(owner, attribute, corrupted):
                                importlib.reload(p3_expectations)
                                self.assertEqual(p3_expectations.identity(), EXPECTATION_IDENTITY)
                        finally:
                            importlib.reload(p3_expectations)

    def assert_co_drift_rejected(self, recipe, owner, attribute, corrupted, pack):
                original = self.native[recipe]
                mutant = replace(original, analysis_pack=pack)
                self.assess(mutant, self.answers[recipe], "wrong_coverage", checked_wrong=True)
                with patch.object(owner, attribute, corrupted):
                    self.assess(original, self.answers[recipe], "complete_correct")
                    self.assess(mutant, self.answers[recipe], "wrong_coverage", checked_wrong=True)

    def test_scalar_required_check_cannot_co_drift_with_runtime(self):
                missing = "read_only_single_transaction"
                self.assertIn(missing, kernel._CHECKS)
                corrupted = tuple(check for check in kernel._CHECKS if check != missing)
                pack = self.native["compare"].analysis_pack
                facts = tuple(replace(fact, checks=tuple(check for check in fact.checks if check != missing))
                              for fact in pack.facts)
                for fact in facts:
                    self.assertNotIn(missing, fact.checks)
                self.assert_co_drift_rejected("compare", kernel, "_CHECKS", corrupted, replace(pack, facts=facts))

    def test_grouped_required_check_cannot_co_drift_with_runtime(self):
                missing = "reviewed_dimension_binding"
                self.assertIn(missing, grouped._GROUP_CHECKS)
                corrupted = tuple(check for check in grouped._GROUP_CHECKS if check != missing)
                pack = self.native["overview"].analysis_pack
                groups = tuple(replace(fact, checks=tuple(check for check in fact.checks if check != missing))
                               for fact in pack.grouped_facts)
                for fact in groups:
                    self.assertNotIn(missing, fact.checks)
                self.assert_co_drift_rejected(
                    "overview", grouped, "_GROUP_CHECKS", corrupted, replace(pack, grouped_facts=groups))

    def assert_ordering_co_drift_rejected(self, recipe, dimension, ordering):
                self.assertNotEqual(grouped._ORDERING[dimension], ordering)
                corrupted = {**grouped._ORDERING, dimension: ordering}
                pack = self.native[recipe].analysis_pack
                groups = tuple(replace(fact, ordering=ordering) if fact.dimension == dimension else fact
                               for fact in pack.grouped_facts)
                self.assertEqual([fact.ordering for fact in groups if fact.dimension == dimension], [ordering])
                self.assert_co_drift_rejected(
                    recipe, grouped, "_ORDERING", corrupted, replace(pack, grouped_facts=groups))

    def test_category_ordering_cannot_co_drift_with_runtime(self):
                self.assert_ordering_co_drift_rejected("overview", "category", ("key_desc",))

    def test_course_ordering_cannot_co_drift_with_runtime(self):
                self.assert_ordering_co_drift_rejected("breakdown", "course", ("value_asc", "key_asc"))

    def test_dimension_profile_cannot_co_drift_with_runtime(self):
                corrupted = "corrupted_dimension_profile"
                self.assertNotEqual(grouped._DIMENSION_PROFILE, corrupted)
                pack = copy.deepcopy(self.native["overview"].analysis_pack)
                for fact in pack.grouped_facts:
                    object.__setattr__(fact, "dimension_profile_id", corrupted)
                    self.assertEqual(fact.dimension_profile_id, corrupted)
                self.assert_co_drift_rejected("overview", grouped, "_DIMENSION_PROFILE", corrupted, pack)

    def test_additional_compatible_checks_remain_allowed(self):
                pack = self.native["overview"].analysis_pack
                extra = ("additional_compatible_check",)
                facts = tuple(replace(fact, checks=(*fact.checks, *extra)) for fact in pack.facts)
                groups = tuple(replace(fact, checks=(*fact.checks, *extra)) for fact in pack.grouped_facts)
                self.assess(replace(self.native["overview"], analysis_pack=replace(
                    pack, facts=facts, grouped_facts=groups)), self.answers["overview"], "complete_correct")

    def test_wrong_recipe_remains_primary_while_later_execution_is_observed(self):
        grade = self.assess(self.native["overview"], self.answers["compare"], "wrong_recipe", checked_wrong=True)
        self.assertEqual(grade["layers"]["recipe"], "failed")
        self.assertEqual(grade["layers"]["execution"], "passed")
        self.assertEqual(grade["layers"]["values"], "failed")

    def test_wrong_valid_request_wins_even_when_numbers_and_later_layers_agree(self):
        result = self.native["compare"]
        request = replace(result.proposal.request, current=result.proposal.request.baseline,
                          baseline=result.proposal.request.current)
        collision = replace(result, proposal=replace(result.proposal, request=request),
                            analysis_pack=replace(result.analysis_pack, request=request))
        grade = self.assess(collision, self.answers["compare"], "wrong_request", checked_wrong=True)
        self.assertEqual(grade["layers"]["request"], "failed")
        self.assertEqual(grade["layers"]["execution"], "passed")
        self.assertEqual(grade["layers"]["values"], "passed")

    def test_wrong_code_and_k_are_not_normalized_to_gold(self):
        for recipe, field, value in (("overview", "center_code", "CTR-A02"), ("breakdown", "top_k", 1)):
            with self.subTest(recipe=recipe):
                result = self.native[recipe]
                wrong = replace(result.proposal.request, **{field: value})
                candidate = replace(result, proposal=replace(result.proposal, request=wrong),
                                    analysis_pack=replace(result.analysis_pack, request=wrong))
                self.assess(candidate, self.answers[recipe], "wrong_request", checked_wrong=True)

    def test_equivalent_native_request_offsets_match_without_changing_roles(self):
        result = self.native["compare"]
        old = result.proposal.request
        request = replace(old, current=replace(old.current, start=old.current.start.astimezone(timezone.utc),
                                               end=old.current.end.astimezone(timezone.utc)),
                          baseline=replace(old.baseline, start=old.baseline.start.astimezone(timezone.utc),
                                           end=old.baseline.end.astimezone(timezone.utc)))
        candidate = replace(result, proposal=replace(result.proposal, request=request),
                            analysis_pack=replace(result.analysis_pack, request=request))
        self.assess(candidate, self.answers["compare"], "complete_correct")

    def test_wrong_request_precedes_later_native_error_and_retains_it(self):
        result = self.native["breakdown"]
        wrong = replace(result.proposal.request, top_k=1)
        candidate = replace(result, proposal=replace(result.proposal, request=wrong),
                            analysis_pack=None, error=ModelError("source_failure"))
        grade = self.assess(candidate, self.answers["breakdown"], "wrong_request")
        self.assertEqual(grade["operational_error"], "source_failure")
        self.assertEqual(grade["layers"]["execution"], "failed")

    def test_correct_request_operational_failure_is_not_not_run(self):
        result = replace(self.native["compare"], analysis_pack=None, error=ModelError("timeout"))
        grade = self.assess(result, self.answers["compare"], "operational_failure")
        self.assertEqual(grade["actual_action"], "answer")
        self.assertEqual(grade["operational_error"], "timeout")

    def test_missing_result_and_unattempted_are_distinct(self):
        self.assess(None, self.answers["compare"], "operational_failure")
        grade = p3_grading.grade(None, self.answers["compare"], attempted=False)
        self.assertEqual(grade["outcome"], "not_run")
        self.assertFalse(grade["checked_wrong"])
        self.assertEqual(set(grade["layers"].values()), {"not_assessed"})
        with self.assertRaises(ValueError):
            p3_grading.grade(self.native["compare"], self.answers["compare"], attempted=False)

    def test_malformed_content_and_envelope_are_invalid_output_not_decline(self):
        for code in ("invalid_response", "unsupported_output", "invalid_json", "invalid_request"):
            with self.subTest(code=code):
                result = RecipeInterpretation(None, None, ModelError(code), {})
                grade = self.assess(result, self.answers["compare"], "invalid_output")
                self.assertEqual(grade["operational_error"], code)

    def test_resource_and_provider_errors_without_usable_action_remain_operational(self):
        for code in ("response_too_large", "output_token_budget", "truncated_output",
                     "unexpected_model", "http_configuration", "transport_error", "timeout"):
            with self.subTest(code=code):
                result = RecipeInterpretation(None, None, ModelError(code), {})
                self.assess(result, self.answers["compare"], "operational_failure")

    def test_all_action_mismatch_classes_and_checked_wrong_are_separate(self):
        decline = RecipeInterpretation(None, None, ModelError("model_declined"), {})
        self.assess(decline, self.answers["compare"], "false_refusal")
        self.assess(self.clarify(), self.answers["overview"], "false_clarification")
        self.assess(self.native["overview"], self.clarifies["count_basis"], "missed_clarification",
                    checked_wrong=True)
        self.assess(decline, self.clarifies["count_basis"], "wrong_action")
        self.assess(self.native["compare"], self.decline, "wrong_action", checked_wrong=True)
        self.assess(self.clarify(), self.decline, "false_clarification")

    def test_missing_coverage_role_cannot_be_rescued_by_matching_values(self):
        result = self.native["overview"]
        pack = replace(result.analysis_pack, slots=result.analysis_pack.slots[:-1])
        grade = self.assess(replace(result, analysis_pack=pack), self.answers["overview"],
                            "wrong_coverage", checked_wrong=True)
        self.assertEqual(grade["layers"]["values"], "passed")

    def test_wrong_population_time_scope_and_grain_fail_coverage(self):
        for field, value in (("population", "Paid bookings"), ("time_basis", "payments.posted_at_utc"),
                             ("start_utc", "2026-03-01T00:00:00Z"), ("grain", "person"),
                             ("filters", {"center_id": "different"})):
            with self.subTest(field=field):
                result = self.native["compare"]
                facts = (replace(result.analysis_pack.facts[0], **{field: value}), result.analysis_pack.facts[1])
                pack = replace(result.analysis_pack, facts=facts)
                self.assess(replace(result, analysis_pack=pack), self.answers["compare"],
                            "wrong_coverage", checked_wrong=True)

    def test_bound_pack_scope_and_undeclared_exclusions_cannot_hide_behind_correct_facts(self):
        for recipe in ("overview", "breakdown"):
            with self.subTest(recipe=recipe):
                result = self.native[recipe]
                pack = result.analysis_pack
                scope = replace(pack.scope, center_id="unexpected-center")
                changed = self.assess(replace(result, analysis_pack=replace(pack, scope=scope)),
                                      self.answers[recipe], "wrong_coverage", checked_wrong=True)
                original = self.assess(result, self.answers[recipe], "complete_correct")
                self.assertNotEqual(changed["actual_signature"], original["actual_signature"])
        result = self.native["compare"]
        fact = replace(result.analysis_pack.facts[0], excluded_anonymous_rows=1)
        self.assess(replace(result, analysis_pack=replace(
            result.analysis_pack, facts=(fact, result.analysis_pack.facts[1]))),
                    self.answers["compare"], "wrong_coverage", checked_wrong=True)

    def test_empty_overview_gold_keeps_null_distinct_from_measured_zero(self):
        raw = self.answers["overview"].to_dict()
        request = replace(self.answers["overview"].request,
                          start=self.answers["overview"].request.start.replace(year=2030),
                          end=self.answers["overview"].request.end.replace(year=2030))
        raw.update(oracle_id="unit-empty-overview-v2", revision=2, request=request.to_dict(),
                   provenance=["docs/fact-kernel.md:103-106; tests/test_overview.py:308-314; "
                               "empty SUM is null, empty COUNT is zero; supersedes mistaken unit v1."],
                   values={"amount": None, "bookings": 0, "seats": None},
                   auxiliary_values={"daily_amount": [], "category_amounts": []})
        oracle = parse_oracle(raw)
        pack = recipe_model.execute_overview(self.database, request)
        result = RecipeInterpretation(RecipeProposal("overview", request), pack, None, {})
        self.assess(result, oracle, "complete_correct")
        zero = replace(pack.facts[0], value=0)
        self.assess(replace(result, analysis_pack=replace(pack, facts=(zero, *pack.facts[1:]))),
                    oracle, "wrong_value", checked_wrong=True)
        missing_count = replace(pack.facts[1], value=None)
        self.assess(replace(result, analysis_pack=replace(
            pack, facts=(pack.facts[0], missing_count, pack.facts[2]))),
                    oracle, "wrong_value", checked_wrong=True)

    def test_defined_undefined_ratio_requires_explicit_gold_state_and_null(self):
        raw = self.answers["compare"].to_dict()
        raw.update(oracle_id="unit-zero-baseline",
                   provenance=["Exposed zero-baseline contract; test-owned February zero-price fixture variant."])
        raw["values"] = {"current": 158000, "baseline": 0, "delta": 158000, "growth": None}
        raw["slot_states"]["growth"] = "undefined"
        oracle = parse_oracle(raw)
        with tempfile.TemporaryDirectory(dir=ROOT / ".artifacts") as directory:
            database = Path(directory) / "zero-baseline.sqlite"
            shutil.copyfile(self.database, database)
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute(
                    "UPDATE booking_items SET unit_price_minor=0, discount_minor=0 "
                    "WHERE booking_id IN (SELECT booking_id FROM bookings "
                    "WHERE created_at_utc >= ? AND created_at_utc < ?)",
                    ("2026-01-31T16:00:00Z", "2026-02-28T16:00:00Z"))
            pack = recipe_model.execute_compare(database, oracle.request)
        result = RecipeInterpretation(RecipeProposal("compare", oracle.request), pack, None, {})
        self.assess(result, oracle, "complete_correct")
        wrong = replace(pack.derived_facts[-1], state="checked", value=0, reason=None)
        slots = tuple(replace(slot, fact_id=wrong.fact_id, state="checked", reason=None)
                      if slot.slot_id == "growth" else slot for slot in pack.slots)
        self.assess(replace(result, analysis_pack=replace(
            pack, derived_facts=(pack.derived_facts[0], wrong), slots=slots)),
                    oracle, "wrong_value", checked_wrong=True)

    def test_swapped_checked_slot_links_are_fact_selection_not_coverage(self):
        result = self.native["compare"]
        pack = result.analysis_pack
        slots = (replace(pack.slots[0], fact_id=pack.slots[1].fact_id),
                 replace(pack.slots[1], fact_id=pack.slots[0].fact_id), *pack.slots[2:])
        grade = self.assess(replace(result, analysis_pack=replace(pack, slots=slots)),
                            self.answers["compare"], "wrong_fact_selection", checked_wrong=True)
        self.assertEqual(grade["layers"]["coverage"], "passed")
        self.assertEqual(grade["layers"]["values"], "passed")

    def test_derived_fact_sources_and_denominator_roles_are_semantic_not_numeric(self):
        for recipe in ("compare", "breakdown"):
            with self.subTest(recipe=recipe):
                result = self.native[recipe]
                pack = result.analysis_pack
                derived = replace(pack.derived_facts[-1], input_fact_ids=(
                    pack.derived_facts[-1].input_fact_ids[0], pack.derived_facts[0].fact_id))
                slots = tuple(replace(slot, fact_id=derived.fact_id)
                              if slot.fact_id == pack.derived_facts[-1].fact_id else slot for slot in pack.slots)
                candidate = replace(result, analysis_pack=replace(
                    pack, derived_facts=(pack.derived_facts[0], derived), slots=slots))
                grade = self.assess(candidate, self.answers[recipe], "wrong_fact_selection", checked_wrong=True)
                self.assertEqual(grade["layers"]["coverage"], "passed")
                self.assertEqual(grade["layers"]["values"], "passed")

    def test_wrong_metric_identity_and_invented_fact_fail_selection(self):
        result = self.native["compare"]
        pack = result.analysis_pack
        wrong = replace(pack.facts[0], metric_id="booked_seats")
        candidate = replace(result, analysis_pack=replace(pack, facts=(wrong, pack.facts[1])))
        self.assess(candidate, self.answers["compare"], "wrong_fact_selection", checked_wrong=True)
        extra = replace(pack.facts[0], fact_id="synthetic-invented-fact")
        candidate = replace(result, analysis_pack=replace(pack, facts=(*pack.facts, extra)))
        self.assess(candidate, self.answers["compare"], "wrong_fact_selection", checked_wrong=True)

    def test_wrong_units_values_rational_and_group_order_fail_values(self):
        result = self.native["compare"]
        for fact in (replace(result.analysis_pack.facts[0], unit="TWD_major"),
                     replace(result.analysis_pack.facts[0], value=158001),
                     replace(result.analysis_pack.facts[0], value=True)):
            candidate = replace(result, analysis_pack=replace(
                result.analysis_pack, facts=(fact, result.analysis_pack.facts[1])))
            self.assess(candidate, self.answers["compare"], "wrong_value", checked_wrong=True)
        pack = result.analysis_pack
        derived = replace(pack.derived_facts[-1], value=2.16)
        slots = tuple(replace(slot, fact_id=derived.fact_id)
                      if slot.fact_id == pack.derived_facts[-1].fact_id else slot for slot in pack.slots)
        self.assess(replace(result, analysis_pack=replace(
            pack, derived_facts=(pack.derived_facts[0], derived), slots=slots)),
                    self.answers["compare"], "wrong_value", checked_wrong=True)
        result = self.native["breakdown"]
        group = replace(result.analysis_pack.grouped_facts[0],
                        rows=tuple(reversed(result.analysis_pack.grouped_facts[0].rows)))
        self.assess(replace(result, analysis_pack=replace(result.analysis_pack, grouped_facts=(group,))),
                    self.answers["breakdown"], "wrong_value", checked_wrong=True)

    def test_auxiliary_available_values_are_not_ungraded_free_passes(self):
        result = self.native["overview"]
        pack = result.analysis_pack
        group = pack.grouped_facts[0]
        wrong = replace(group, rows=(replace(group.rows[0], value=group.rows[0].value + 1), *group.rows[1:]))
        candidate = replace(result, analysis_pack=replace(pack, grouped_facts=(wrong, *pack.grouped_facts[1:])))
        self.assess(candidate, self.answers["overview"], "wrong_value", checked_wrong=True)

    def test_disclosed_optional_gap_is_partial_not_complete(self):
        grade = self.assess(self.partial(), self.answers["overview"], "partial")
        self.assertEqual(grade["pack_status"], "partial")
        self.assertEqual(grade["layers"]["values"], "passed")

    def test_user_required_optional_slot_missing_stays_explicit_partial(self):
        raw = self.answers["overview"].to_dict()
        raw["required_slots"] = list(raw["coverage"]["slots"])
        raw["auxiliary_slots"] = []
        grade = self.assess(self.partial(), parse_oracle(raw), "partial")
        self.assertEqual(grade["missing_required_slots"], ["daily_amount"])

    def test_partial_cannot_hide_wrong_available_value_selection_or_request(self):
        result = self.partial()
        pack = result.analysis_pack
        fact = replace(pack.facts[0], value=pack.facts[0].value + 1)
        candidate = replace(result, analysis_pack=replace(pack, facts=(fact, *pack.facts[1:])))
        self.assess(candidate, self.answers["overview"], "wrong_value")
        slots = tuple(replace(slot, fact_id=pack.facts[0].fact_id) if slot.slot_id == "category_amounts"
                      else slot for slot in pack.slots)
        self.assess(replace(result, analysis_pack=replace(pack, slots=slots)),
                    self.answers["overview"], "wrong_fact_selection")
        wrong = replace(result.proposal.request, center_code="CTR-A02")
        self.assess(replace(result, proposal=replace(result.proposal, request=wrong)),
                    self.answers["overview"], "wrong_request")

    def test_all_four_clarification_kinds_match_meaning_not_oracle_ids(self):
        for kind, oracle in self.clarifies.items():
            with self.subTest(kind=kind):
                grade = self.assess(self.clarify(kind), oracle, "correct_clarification")
                self.assertEqual({grade["layers"][key] for key in (
                    "action", "clarification_kind", "semantic_choices", "presentation")}, {"passed"})

    def test_clarification_kind_and_bound_month_are_semantic(self):
        self.assess(self.clarify("metric_meaning"), self.clarifies["count_basis"], "wrong_action")
        result = self.clarify()
        choices = []
        for choice in result.clarification.choices:
            value = choice.semantic_value
            scope = replace(value.scope, start=value.scope.start.replace(month=4), end=value.scope.end.replace(month=5))
            choices.append(SemanticChoice(choice.id, replace(value, scope=scope)))
        changed = Clarification("count_basis", tuple(choices))
        self.assess(replace(result, clarification=changed, presentation=render_clarification(changed)),
                    self.clarifies["count_basis"], "wrong_action")

    def test_missing_and_extra_semantic_alternatives_fail_even_when_structurally_valid(self):
        result = self.clarify()
        scope = result.clarification.choices[0].semantic_value.scope
        existing = {choice.semantic_value.value for choice in result.clarification.choices}
        alternative = next(value for value in ("attendance_visits", "distinct_people", "known_booking_accounts")
                           if value not in existing)
        extra = SemanticChoice("extra", CountBasis(scope, alternative))
        expanded = Clarification("count_basis", (*result.clarification.choices, extra))
        self.assess(replace(result, clarification=expanded, presentation=render_clarification(expanded)),
                    self.clarifies["count_basis"], "wrong_action")
        expected = self.clarifies["count_basis"].to_dict()
        expected["clarification"] = expanded.to_dict()
        self.assess(result, parse_oracle(expected), "wrong_action")

    def test_choice_order_and_localized_labels_do_not_change_semantic_grade_or_agreement(self):
        result = self.clarify()
        baseline = self.assess(result, self.clarifies["count_basis"], "correct_clarification")
        choices = replace(result.clarification, choices=tuple(reversed(result.clarification.choices)))
        values = {choice.id: choice.semantic_value.value for choice in choices.choices}
        for label in ("Booked seats", "席次", "예약 좌석"):
            with self.subTest(label=label):
                raw = render_clarification(choices).to_dict()
                raw["text"] = "請選擇"
                for option in raw["blocks"][0]["options"]:
                    if values[option["choice_id"]] == "booked_seats":
                        option["label"] = label
                raw["blocks"][0]["options"].reverse()
                presentation = ClarificationPresentation.from_mapping(raw, choices)
                changed = replace(result, clarification=choices, presentation=presentation)
                grade = self.assess(changed, self.clarifies["count_basis"], "correct_clarification")
                self.assertEqual(grade["actual_signature"], baseline["actual_signature"])

    def test_broken_presentation_is_separate_from_correct_semantic_choices(self):
        result = self.clarify()
        scope = result.clarification.choices[0].semantic_value.scope
        choices = Clarification("count_basis", (
            *result.clarification.choices, SemanticChoice("visits", CountBasis(scope, "attendance_visits"))))
        result = replace(result, clarification=choices, presentation=render_clarification(choices))
        expected = self.clarifies["count_basis"].to_dict()
        expected["clarification"] = choices.to_dict()
        bad = copy.deepcopy(result.presentation.to_dict())
        bad["blocks"][0]["options"].pop()
        with patch.object(ClarificationPresentation, "to_dict", return_value=bad):
            grade = self.assess(result, parse_oracle(expected), "wrong_action")
        self.assertEqual(grade["layers"]["semantic_choices"], "passed")
        self.assertEqual(grade["layers"]["presentation"], "failed")

    def test_designated_decline_needs_no_model_reason_but_deferred_never_gets_credit(self):
        result = RecipeInterpretation(None, None, ModelError("model_declined"), {})
        self.assess(result, self.decline, "correct_decline")
        raw = self.decline.to_dict()
        raw.update(designated_control=False, capability_category="D05")
        grade = self.assess(result, parse_oracle(raw), "wrong_action")
        self.assertEqual(grade["layers"]["decline_eligibility"], "failed")

    def test_runtime_uuid_and_snapshot_identity_do_not_define_semantic_agreement(self):
        oracle = self.answers["compare"]
        first = self.assess(self.native["compare"], oracle, "complete_correct")
        pack = recipe_model.execute_compare(self.database, oracle.request)
        second = self.assess(replace(self.native["compare"], analysis_pack=pack), oracle, "complete_correct")
        self.assertNotEqual(pack.snapshot["id"], self.native["compare"].analysis_pack.snapshot["id"])
        self.assertEqual(first["actual_signature"], second["actual_signature"])

    def test_agreement_distinguishes_different_wrong_values_not_just_primary_outcome(self):
        result = self.native["compare"]
        signatures = []
        for value in (158001, 158002):
            fact = replace(result.analysis_pack.facts[0], value=value)
            candidate = replace(result, analysis_pack=replace(
                result.analysis_pack, facts=(fact, result.analysis_pack.facts[1])))
            grade = self.assess(candidate, self.answers["compare"], "wrong_value", checked_wrong=True)
            signatures.append(grade["actual_signature"])
        self.assertNotEqual(signatures[0], signatures[1])
