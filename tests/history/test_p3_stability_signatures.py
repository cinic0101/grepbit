"""Use exposed native objects to prove the frozen semantic identity used by stability."""
from dataclasses import replace
from datetime import timezone
import unittest
from unittest.mock import patch

from grepbit import recipe_model
from grepbit.clarification import Clarification, SemanticChoice
from grepbit.gateway import ModelError
from grepbit.presentation import render_clarification
from tools import p3_grading
import test_p3_grading as grading_fixtures


class StabilitySignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        grading_fixtures.P3GradingTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        for target in ("socket.create_connection", "socket.getaddrinfo", "grepbit.gateway.GatewayConfig.from_env",
                       "grepbit.gateway.GatewayClient.complete"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Offline signatures only")))
            self.addCleanup(guard.assert_not_called)

    def clarify(self, kind="count_basis"):
        return grading_fixtures.P3GradingTests.clarify(self, kind)

    def test_same_clarify_ids_order_and_rendering_are_not_semantics(self):
        result = self.clarify()
        before = p3_grading.actual_signature(result, "clarify")
        changed = Clarification(result.clarification.kind, tuple(
            SemanticChoice(f"new-{i}", choice.semantic_value)
            for i, choice in enumerate(reversed(result.clarification.choices))))
        self.assertEqual(before, p3_grading.actual_signature(replace(
            result, clarification=changed, presentation=render_clarification(changed)), "clarify"))

    def test_clarify_kind_and_typed_bundle_change_signature(self):
        result = self.clarify()
        before = p3_grading.actual_signature(result, "clarify")
        self.assertNotEqual(before, p3_grading.actual_signature(self.clarify("comparison_roles"), "clarify"))
        changed = Clarification(result.clarification.kind, tuple(
            replace(choice, semantic_value=replace(choice.semantic_value,
                scope=replace(choice.semantic_value.scope, center_code="CTR-A02")))
            for choice in result.clarification.choices))
        self.assertNotEqual(before, p3_grading.actual_signature(replace(result, clarification=changed), "clarify"))

    def test_decline_signature_has_no_prose_or_category_dimension(self):
        result = recipe_model.RecipeInterpretation(None, None, ModelError("model_declined"), {})
        changed = replace(result, evidence={"ignored_mock_only": "different decline prose"})
        self.assertEqual(p3_grading.actual_signature(result, "decline"),
                         p3_grading.actual_signature(changed, "decline"))

    def test_answer_uuid_snapshot_do_not_flip_but_recipe_request_values_do(self):
        result = self.native["overview"]
        before = p3_grading.actual_signature(result, "answer")
        again = recipe_model.execute_overview(self.database, result.proposal.request)
        self.assertEqual(before, p3_grading.actual_signature(replace(result, analysis_pack=again), "answer"))
        self.assertNotEqual(before, p3_grading.actual_signature(self.native["compare"], "answer"))
        proposal = replace(result.proposal, request=replace(result.proposal.request, center_code="CTR-A02"))
        self.assertNotEqual(before, p3_grading.actual_signature(replace(result, proposal=proposal), "answer"))
        pack = result.analysis_pack
        fact = replace(pack.facts[0], value=pack.facts[0].value + 1)
        self.assertNotEqual(before, p3_grading.actual_signature(replace(result, analysis_pack=replace(
            pack, facts=(fact, *pack.facts[1:]))), "answer"))

    def test_equivalent_timestamp_offsets_do_not_flip(self):
        result = self.native["compare"]
        old = result.proposal.request
        request = replace(old, current=replace(old.current, start=old.current.start.astimezone(timezone.utc),
                                               end=old.current.end.astimezone(timezone.utc)),
                          baseline=replace(old.baseline, start=old.baseline.start.astimezone(timezone.utc),
                                           end=old.baseline.end.astimezone(timezone.utc)))
        changed = replace(result, proposal=replace(result.proposal, request=request),
                          analysis_pack=replace(result.analysis_pack, request=request))
        self.assertEqual(p3_grading.actual_signature(result, "answer"),
                         p3_grading.actual_signature(changed, "answer"))


if __name__ == "__main__":
    unittest.main()
