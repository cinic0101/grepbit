"""Candidate v16 rulers (docs/count-reading-v16.md, ADR #146): offline, fixture DB and mock transports only."""
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
V16 = "p3-count-reading-v16"
COUNTS = ["none", "booked_seats", "unresolved", "known_booking_accounts", "attendance_visits", "distinct_people"]
ASSUMPTION = {"count_basis": "booked_seats"}
STATEMENT = {"count_basis": "booked_seats", "reported_as": "confirmed booked seats",
             "unavailable": ["known_booking_accounts", "attendance_visits", "distinct_people"]}
OVERVIEW = {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00",
            "timezone": "Asia/Taipei"}
SCOPE = {"metrics": ["confirmed_booked_amount"], "timezone": "Asia/Taipei", "center_id": None}
COMPARE = {"current": {**SCOPE, "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00"},
           "baseline": {**SCOPE, "start": "2026-02-01T00:00:00+08:00", "end": "2026-03-01T00:00:00+08:00"}}


def superseded():
    """v16 is registered but no longer current (v17, #146). Only its identity-bound checks stop applying:
    the count reading behaviour stays live in v17 and stays checked here."""
    index = registry.load_index()
    return V16 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V16


def _overview(value="none", **extra):
    """An Overview action; ``value`` None omits count_request, and ``extra`` may set any raw key."""
    action = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": dict(OVERVIEW)}
    if value is not None:
        action["count_request"] = value
    return {**action, **extra}


def _panel(panel_id):
    entry = next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)
    panel = p3_assets.load_panel(ROOT / entry["path"])
    return panel, evaluate.annex_expectations(entry, panel)


def _case(panel, case_id):
    case = next(case for case in panel.cases if case.case_id == case_id)
    return case, next(oracle for oracle in panel.oracles if oracle.oracle_id == case.oracle_id)


def _run(question, action, database):
    return asyncio.run(recipe_model.interpret_recipe_and_execute(
        question, database, evaluate._replay_client(model.canonical_json(action), [])))


class ProposalTests(unittest.TestCase):
    def test_overview_requires_one_typed_count_reading_and_no_other_recipe_takes_it(self):
        for value in COUNTS:
            parsed = recipe_model._proposal(_overview(value))
            self.assertEqual(parsed.count_request, value)
            self.assertEqual(parsed.to_dict(), _overview(value))
            self.assertEqual(parsed.assumption, ASSUMPTION if value == "unresolved" else None)
        bad = [_overview(None), _overview(None, count_request=None), _overview("people"), _overview("NONE"),
               _overview(None, count_request=["none"]), _overview("unresolved", assumption=dict(ASSUMPTION)),
               _overview(None, assumption=dict(ASSUMPTION)),
               {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE,
                "orientation": "stated", "count_request": "none"},
               {"outcome": "request", "recipe_id": "breakdown", "recipe_version": "0.1", "count_request": "none",
                "request": {"start": OVERVIEW["start"], "end": OVERVIEW["end"], "timezone": "Asia/Taipei",
                            "top_k": 2}}]
        for action in bad:
            with self.subTest(action=action), self.assertRaises(ModelError) as refused:
                recipe_model._proposal(action)
            self.assertEqual((refused.exception.code, refused.exception.reason), ("invalid_request", "root_shape"))

    def test_direct_construction_keeps_the_legacy_shape_and_refuses_other_values(self):
        request = recipe_model._proposal(_overview()).request
        legacy = recipe_model.RecipeProposal("overview", request)
        self.assertIsNone(legacy.count_request)
        self.assertIsNone(legacy.assumption)
        self.assertNotIn("count_request", legacy.to_dict())
        hash(legacy)
        compare = recipe_model._proposal({"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1",
                                          "request": COMPARE, "orientation": "stated"}).request
        for recipe, native, value in (("overview", request, "people"), ("compare", compare, "none")):
            with self.subTest(recipe=recipe, value=value), self.assertRaises(ValueError):
                recipe_model.RecipeProposal(recipe, native, count_request=value)


class ContractTextTests(unittest.TestCase):
    def test_the_schema_requires_the_count_reading_on_overview_only(self):
        branches = recipe_model.output_schema()["oneOf"]
        requests = {branch["properties"]["recipe_id"]["const"]: branch for branch in branches
                    if branch["properties"]["outcome"]["const"] == "request"}
        self.assertEqual(requests["overview"]["properties"]["count_request"], {"enum": COUNTS})
        self.assertIn("count_request", requests["overview"]["required"])
        self.assertEqual(requests["compare"]["properties"]["orientation"], {"enum": ["stated", "unresolved"]})
        for recipe in ("compare", "breakdown"):
            self.assertNotIn("count_request", requests[recipe]["properties"])
        clarify = next(branch for branch in branches if branch["properties"]["outcome"]["const"] == "clarify")
        self.assertEqual([kind["properties"]["kind"]["const"] for kind in clarify["properties"]["clarification"]["oneOf"]],
                         ["count_basis", "center", "metric_meaning"])

    def test_the_instruction_and_context_state_the_count_rule(self):
        text = recipe_model.SYSTEM_INSTRUCTION
        for phrase in ("Every Overview request carries count_request",
                       "whose meaning it leaves open", "the server answers an unresolved count with booked seats",
                       "declines a named unavailable count", "undecided between named meanings",
                       "a count of bookings is the Overview bookings output, so it is none, never "
                       "known_booking_accounts"):
            self.assertIn(phrase, text)
        context = recipe_model.runtime_context()
        self.assertIn("only when the question explicitly leaves the count basis undecided between named meanings",
                      context["clarification"]["count_basis"])
        overview = next(recipe for recipe in context["recipes"] if recipe["id"] == "overview")
        self.assertNotIn("people counts", overview["unsupported"])
        self.assertIn("named account/attendance/distinct-people counts", overview["unsupported"])
        if not superseded():
            self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                              recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                             ("recipe-selection-instruction-v9", "learningops-recipe-context-v6",
                              "recipe-request-json-v5", "recipe-structured-output-v5"))

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

            client = GatewayClient(GatewayConfig("https://v16-size-private.invalid/v1", "dummy-v16-key"),
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
        cls._tmp = tempfile.TemporaryDirectory(prefix="v16-", dir=ROOT / ".artifacts")
        cls.database = Path(cls._tmp.name) / "fixture.sqlite"
        fixture.build(cls.database)
        # dev-BM5/6/8 are on the bound-meaning panel; dev-MN1-3 on the mechanism probe.
        cls.panels = {"bound-meaning": _panel("p3-dev-bound-meaning-v2"),
                      "mechanism-probe": _panel("p3-dev-mechanism-probe-v2")}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def graded(self, case_id, action, panel="bound-meaning"):
        panel, expectations = self.panels[panel]
        case, oracle = _case(panel, case_id)
        result = _run(case.question, action, self.database)
        grade = p3_grading.grade(result, oracle)
        row = {"oracle_id": oracle.oracle_id, "validated_action": evaluate._validated_action(result)}
        annex = evaluate.annexed(row, grade["outcome"] in ("complete_correct", "correct_clarification",
                                                            "correct_decline"), expectations)
        return result, grade, row, annex

    def test_a_generic_count_is_answered_with_the_stated_assumption(self):
        for case_id, panel in (("dev-MN2.en", "mechanism-probe"), ("dev-MN3.ja", "mechanism-probe")):
            with self.subTest(case_id=case_id):
                _, grade, _, annex = self.graded(case_id, _overview("unresolved"), panel)
                self.assertEqual((grade["outcome"], annex), ("complete_correct", "correct"))
        result, grade, row, annex = self.graded("dev-BM6.en", _overview("unresolved"))
        self.assertIsNone(result.error)
        self.assertEqual(result.analysis_pack.recipe_id, "overview")
        self.assertEqual(result.evidence["count_assumption"], STATEMENT)
        self.assertEqual((grade["outcome"], annex), ("complete_correct", "correct"))
        self.assertEqual(row["validated_action"], model.canonical_json(_overview("unresolved")))

    def test_a_named_seats_count_is_answered_without_an_assumption(self):
        for value in ("booked_seats", "none"):
            with self.subTest(value=value):
                result, grade, _, annex = self.graded("dev-BM5.en", _overview(value))
                self.assertIsNone(result.error)
                self.assertIsNone(result.evidence["count_assumption"])
                self.assertEqual((grade["outcome"], annex), ("complete_correct", "correct"))
        # The same reading on a generic-count question is the missing assumption the annex rejects.
        _, grade, _, annex = self.graded("dev-BM6.en", _overview("booked_seats"))
        self.assertEqual((grade["outcome"], annex), ("complete_correct", "wrong"))

    def test_a_named_unavailable_count_is_a_server_decline_that_replays(self):
        for value in ("known_booking_accounts", "attendance_visits", "distinct_people"):
            with self.subTest(value=value):
                action = _overview(value)
                result, grade, row, annex = self.graded("dev-BM8.en", action)
                self.assertEqual(result.error.code, "model_declined")
                self.assertIsNone(result.proposal)
                self.assertIsNone(result.analysis_pack)
                self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
                self.assertEqual(result.source_proposal.to_dict(), action)
                self.assertEqual((result.evidence["model_outcome"], result.evidence["count_request"]),
                                 ("declined", value))
                self.assertEqual((grade["outcome"], annex), ("correct_decline", "correct"))
                self.assertEqual(row["validated_action"], model.canonical_json(action))
                case, _ = _case(self.panels["bound-meaning"][0], "dev-BM8.en")
                replayed = _run(case.question, json.loads(row["validated_action"]), self.database)
                self.assertEqual((replayed.error.code, replayed.source_proposal.to_dict()), ("model_declined", action))

    def test_the_persisted_action_shape_readback_and_annex_read_the_count(self):
        for value in COUNTS:
            self.assertTrue(evaluate._action_shape(_overview(value)))
        self.assertTrue(evaluate._action_shape(_overview(None, assumption=dict(ASSUMPTION))))
        for action in (_overview("people"), _overview(None, count_request=None),
                       _overview("unresolved", assumption=dict(ASSUMPTION)), _overview("none", orientation="stated"),
                       {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE,
                        "orientation": "stated", "count_request": "none"}):
            with self.subTest(action=action):
                self.assertFalse(evaluate._action_shape(action))
        row = {"validated_action": model.canonical_json(_overview("distinct_people")), "status": "completed",
               "actual_action": "decline", "clarification_kind": None, "clarification_choice_count": None,
               "runner_error_code": None, "evidence": {"error_code": "model_declined",
                                                       "stages": {"request_validation": "failed"}}}
        self.assertFalse(evaluate._check_action(row))
        for changed in ({"actual_action": "answer"}, {"evidence": {"error_code": None, "stages": {}}}):
            with self.subTest(changed=changed), self.assertRaises(p3_assets.P3Error):
                evaluate._check_action({**row, **changed})
        answered = {**row, "validated_action": model.canonical_json(_overview("unresolved")), "actual_action": "answer",
                    "evidence": {"stages": {"request_validation": "passed"}}}
        self.assertFalse(evaluate._check_action(answered))
        with self.assertRaises(p3_assets.P3Error):
            evaluate._check_action({**answered, "actual_action": "decline"})
        expected = {"dev-MN1.v2": ASSUMPTION}
        for value, verdict in (("unresolved", "correct"), ("booked_seats", "wrong"), ("none", "wrong")):
            with self.subTest(value=value):
                annexed = evaluate.annexed({"oracle_id": "dev-MN1.v2",
                                            "validated_action": model.canonical_json(_overview(value))}, True, expected)
                self.assertEqual(annexed, verdict)


class ToolReadbackTests(unittest.TestCase):
    def test_the_diagnostic_and_routing_tools_read_a_named_unavailable_count_as_a_decline(self):
        from tools import reading_diagnostic, routing_upper_bound
        for value in COUNTS:
            text = model.canonical_json(_overview(value))
            decline = value in ("known_booking_accounts", "attendance_visits", "distinct_people")
            with self.subTest(value=value):
                self.assertEqual(reading_diagnostic._recorded(text), ("decline", None) if decline else ("answer", None))
                routing_upper_bound._check_validated_action(text, {"actual_action": "decline" if decline else "answer"})
                with self.assertRaises(p3_assets.P3Error):
                    routing_upper_bound._check_validated_action(
                        text, {"actual_action": "answer" if decline else "decline"})


class ReadScriptTests(unittest.TestCase):
    def test_each_read_script_is_derived_byte_for_byte_from_its_immutable_v1_script(self):
        import oriented_actions
        self.assertEqual(len(oriented_actions.READ_SIBLINGS), 4)
        for source, target in oriented_actions.READ_SIBLINGS.items():
            with self.subTest(target=target):
                self.assertEqual((ROOT / target).read_text(encoding="utf-8"),
                                 oriented_actions.render(oriented_actions.read_script(source)))

    def test_the_read_derivation_changes_only_overview_requests(self):
        from oriented_actions import read
        self.assertEqual(read(_overview(None)), _overview("none"))
        self.assertEqual(read(_overview("unresolved")), _overview("unresolved"))
        compare = {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE,
                   "orientation": "stated"}
        for unchanged in ({"outcome": "declined"}, compare,
                          {"outcome": "clarify", "clarification": {"kind": "count_basis", "choices": []}}):
            self.assertEqual(read(unchanged), unchanged)


class RegistryTests(unittest.TestCase):
    def test_v16_is_the_registered_current_candidate(self):
        if superseded():
            self.skipTest("v16 superseded; its registration is no longer current")
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V16, "p3-compare-orientation-v15"))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
