"""Candidate v15 rulers (docs/compare-orientation-v15.md, ADR #142): offline, fixture DB and mock transports only."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from grepbit import bedrock, gateway, model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError, MAX_INPUT_BYTES, MAX_REQUEST_BYTES
from tools import candidate_registry as registry, evaluate, fixture, p3_assets, p3_grading

ROOT = Path(__file__).resolve().parents[1]
V15 = "p3-compare-orientation-v15"
SCOPE = {"metrics": ["confirmed_booked_amount"], "timezone": "Asia/Taipei", "center_id": None}
MARCH = {**SCOPE, "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00"}
FEBRUARY = {**SCOPE, "start": "2026-02-01T00:00:00+08:00", "end": "2026-03-01T00:00:00+08:00"}
OVERVIEW = {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00",
            "timezone": "Asia/Taipei"}


def _compare(orientation="stated", current=MARCH, baseline=FEBRUARY, **extra):
    action = {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1",
              "request": {"current": dict(current), "baseline": dict(baseline)}, **extra}
    if orientation is not None:
        action["orientation"] = orientation
    return action


def _panel(panel_id):
    entry = next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)
    return p3_assets.load_panel(ROOT / entry["path"])


def _case(panel, case_id):
    case = next(case for case in panel.cases if case.case_id == case_id)
    return case, next(oracle for oracle in panel.oracles if oracle.oracle_id == case.oracle_id)


def _run(question, action, database):
    return asyncio.run(recipe_model.interpret_recipe_and_execute(
        question, database, evaluate._replay_client(model.canonical_json(action), [])))


class ProposalTests(unittest.TestCase):
    def test_compare_requires_one_typed_orientation_and_no_other_recipe_takes_it(self):
        for orientation in ("stated", "unresolved"):
            parsed = recipe_model._proposal(_compare(orientation))
            self.assertEqual(parsed.orientation, orientation)
            self.assertEqual(parsed.to_dict(), _compare(orientation))
        bad = [_compare(None), _compare("none"), _compare(None, orientation=None), _compare("STATED"),
               _compare(None, orientation=1), _compare(None, orientation=["stated"]),
               {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": OVERVIEW,
                "orientation": "stated"},
               {"outcome": "request", "recipe_id": "breakdown", "recipe_version": "0.1", "orientation": "stated",
                "request": {"start": OVERVIEW["start"], "end": OVERVIEW["end"], "timezone": "Asia/Taipei",
                            "top_k": 2}}]
        for action in bad:
            with self.subTest(action=action), self.assertRaises(ModelError) as refused:
                recipe_model._proposal(action)
            self.assertEqual((refused.exception.code, refused.exception.reason), ("invalid_request", "root_shape"))

    def test_direct_construction_keeps_the_legacy_shape_and_refuses_other_values(self):
        request = recipe_model._proposal(_compare()).request
        legacy = recipe_model.RecipeProposal("compare", request)
        self.assertIsNone(legacy.orientation)
        self.assertNotIn("orientation", legacy.to_dict())
        hash(legacy)
        overview = recipe_model._proposal({"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                                           "request": OVERVIEW}).request
        for recipe, native, orientation in (("compare", request, "sideways"), ("overview", overview, "stated")):
            with self.subTest(recipe=recipe, orientation=orientation), self.assertRaises(ValueError):
                recipe_model.RecipeProposal(recipe, native, orientation)


class ContractTextTests(unittest.TestCase):
    def test_the_schema_requires_orientation_on_compare_and_drops_model_comparison_roles(self):
        branches = recipe_model.output_schema()["oneOf"]
        requests = {branch["properties"]["recipe_id"]["const"]: branch for branch in branches
                    if branch["properties"]["outcome"]["const"] == "request"}
        compare = requests["compare"]
        self.assertEqual(compare["properties"]["orientation"], {"enum": ["stated", "unresolved"]})
        self.assertIn("orientation", compare["required"])
        for recipe in ("overview", "breakdown"):
            self.assertNotIn("orientation", requests[recipe]["properties"])
        clarify = next(branch for branch in branches if branch["properties"]["outcome"]["const"] == "clarify")
        kinds = [kind["properties"]["kind"]["const"]
                 for kind in clarify["properties"]["clarification"]["oneOf"]]
        self.assertEqual(kinds, ["count_basis", "center", "metric_meaning"])

    def test_the_instruction_and_context_state_the_orientation_rule(self):
        text = recipe_model.SYSTEM_INSTRUCTION
        for phrase in ('orientation:"stated"', 'orientation:"unresolved"',
                       "whether the question states which period is evaluated and which is the reference",
                       "the server offers both assignments", "never return comparison_roles"):
            self.assertIn(phrase, text)
        self.assertNotIn("use comparison_roles only when", text)
        context = recipe_model.runtime_context()
        self.assertIn("server-built", context["clarification"]["comparison_roles"])
        self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                          recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                         ("recipe-selection-instruction-v8", "learningops-recipe-context-v5",
                          "recipe-request-json-v4", "recipe-structured-output-v4"))

    def test_every_dev_question_and_a_full_input_fit_the_unchanged_request_cap(self):
        self.assertEqual((MAX_INPUT_BYTES, MAX_REQUEST_BYTES), (4096, 32768))
        questions = ["x" * MAX_INPUT_BYTES]
        panels = [row for row in evaluate.load_panels()["panels"] if row["tier"] == "dev"]
        self.assertGreaterEqual(len(panels), 9)
        for entry in panels:
            questions += [case.question for case in p3_assets.load_panel(ROOT / entry["path"]).cases]
        for question in questions:
            sent = []

            def respond(request):
                sent.append(request)
                return httpx.Response(200, json={"model": gateway.MODEL, "choices": [{
                    "index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"outcome":"declined"}'}}]})

            client = GatewayClient(GatewayConfig("https://v15-size-private.invalid/v1", "dummy-v15-key"),
                                   transport=httpx.MockTransport(respond))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(question, Path("unused.sqlite"), client))
            with self.subTest(question=question[:40]):
                self.assertEqual(result.error.code, "model_declined")
                self.assertEqual(len(sent), 1)
                self.assertLessEqual(len(sent[0].content), MAX_REQUEST_BYTES)

    def test_bedrock_fails_closed_on_the_changed_schema(self):
        constraint, _ = recipe_model._structured_output(recipe_model.output_schema())
        with self.assertRaises(ModelError) as refused:
            bedrock.converse_schema(constraint)
        self.assertEqual(refused.exception.code, "invalid_input")


class RuntimeAndEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="v15-", dir=ROOT / ".artifacts")
        cls.database = Path(cls._tmp.name) / "fixture.sqlite"
        fixture.build(cls.database)
        cls.panel = _panel("p3-dev-bound-meaning-v2")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a_stated_orientation_executes_the_compare_request_as_before(self):
        case, oracle = _case(self.panel, "dev-BM2.en")
        action = _compare("stated")
        result = _run(case.question, action, self.database)
        self.assertIsNone(result.error)
        self.assertIsNone(result.clarification)
        self.assertIsNone(result.source_proposal)
        self.assertEqual((result.proposal.orientation, result.analysis_pack.recipe_id), ("stated", "compare"))
        self.assertEqual(result.evidence["compare_orientation"], "stated")
        self.assertEqual(p3_grading.grade(result, oracle)["outcome"], "complete_correct")
        self.assertEqual(evaluate._validated_action(result), model.canonical_json(action))

    def test_an_unresolved_orientation_is_a_server_built_roles_clarification(self):
        case, oracle = _case(self.panel, "dev-BM4.en")
        for current, baseline in ((MARCH, FEBRUARY), (FEBRUARY, MARCH)):
            action = _compare("unresolved", current, baseline)
            with self.subTest(current=current["start"]):
                result = _run(case.question, action, self.database)
                self.assertIsNone(result.error)
                self.assertIsNone(result.proposal)
                self.assertIsNone(result.analysis_pack)
                self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
                self.assertEqual(result.clarification.kind, "comparison_roles")
                self.assertEqual([choice.id for choice in result.clarification.choices], ["as_proposed", "reversed"])
                values = [choice.semantic_value.request.to_dict() for choice in result.clarification.choices]
                self.assertEqual(values, [{"current": current, "baseline": baseline},
                                          {"current": baseline, "baseline": current}])
                self.assertIsNotNone(result.presentation)
                self.assertEqual(result.source_proposal.to_dict(), action)
                self.assertEqual((result.evidence["model_outcome"], result.evidence["compare_orientation"],
                                  result.evidence["source_proposal"]), ("clarify", "unresolved", action))
                self.assertEqual(p3_grading.grade(result, oracle)["outcome"], "correct_clarification")
                persisted = evaluate._validated_action(result)
                self.assertEqual(persisted, model.canonical_json(action))
                # Replay at the recording source feeds the model's own action and rebuilds the same result.
                replayed = _run(case.question, json.loads(persisted), self.database)
                self.assertEqual(replayed.clarification.to_dict(), result.clarification.to_dict())

    def test_a_model_emitted_roles_clarification_is_refused(self):
        case, _ = _case(self.panel, "dev-BM4.en")
        emitted = {"outcome": "clarify", "clarification": {"kind": "comparison_roles", "choices": [
            {"id": "c1", "semantic_value": {"type": "comparison_roles",
                                            "request": {"current": MARCH, "baseline": FEBRUARY}}},
            {"id": "c2", "semantic_value": {"type": "comparison_roles",
                                            "request": {"current": FEBRUARY, "baseline": MARCH}}}]}}
        result = _run(case.question, emitted, self.database)
        self.assertEqual((result.error.code, result.evidence["invalid_request_reason"]),
                         ("invalid_request", "clarification_shape"))
        self.assertIsNone(result.clarification)

    def test_the_persisted_action_shape_and_readback_admit_the_orientation(self):
        for orientation in ("stated", "unresolved"):
            self.assertTrue(evaluate._action_shape(_compare(orientation)))
        self.assertTrue(evaluate._action_shape(_compare(None)))
        for action in (_compare("none"), _compare(None, orientation=None),
                       {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                        "request": OVERVIEW, "orientation": "stated"}):
            with self.subTest(action=action):
                self.assertFalse(evaluate._action_shape(action))
        row = {"validated_action": model.canonical_json(_compare("unresolved")), "status": "completed",
               "actual_action": "clarify", "clarification_kind": "comparison_roles",
               "clarification_choice_count": 2, "runner_error_code": None,
               "evidence": {"stages": {"request_validation": "passed"}}}
        self.assertFalse(evaluate._check_action(row))
        for changed in ({"actual_action": "answer"}, {"clarification_kind": "center"},
                        {"clarification_choice_count": 3}):
            with self.subTest(changed=changed), self.assertRaises(p3_assets.P3Error):
                evaluate._check_action({**row, **changed})
        stated = {**row, "validated_action": model.canonical_json(_compare("stated")), "actual_action": "answer",
                  "clarification_kind": None, "clarification_choice_count": None}
        self.assertFalse(evaluate._check_action(stated))
        with self.assertRaises(p3_assets.P3Error):
            evaluate._check_action({**stated, "actual_action": "clarify"})


class RegistryTests(unittest.TestCase):
    def test_v15_is_the_registered_current_candidate(self):
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V15, "p3-v12-restoration-v14"))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
