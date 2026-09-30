"""Candidate v13 rulers (docs/count-assumption-v13.md, ADR #136): offline, fixture DB and mock transports only."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from grepbit import bedrock, gateway, model, recipe_model
from grepbit.clarification import COUNT_BASES
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError, MAX_INPUT_BYTES, MAX_REQUEST_BYTES
from tools import candidate_registry as registry, evaluate, fixture, p3_assets

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTION = {"count_basis": "booked_seats"}
OVERVIEW = {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00",
            "timezone": "Asia/Taipei"}
COMPARE_SCOPE = {"metrics": ["confirmed_booked_amount"], "timezone": "Asia/Taipei", "center_id": None}
COMPARE = {"current": {**COMPARE_SCOPE, "start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00"},
           "baseline": {**COMPARE_SCOPE, "start": "2026-02-01T00:00:00+08:00", "end": "2026-03-01T00:00:00+08:00"}}


def _overview(**extra):
    return {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": dict(OVERVIEW), **extra}


class ProposalTests(unittest.TestCase):
    def test_only_an_overview_proposal_may_state_the_one_assumption(self):
        stated = recipe_model._proposal(_overview(assumption=dict(ASSUMPTION)))
        self.assertEqual(stated.assumption, ASSUMPTION)
        self.assertEqual(stated.to_dict(), _overview(assumption=ASSUMPTION))
        plain = recipe_model._proposal(_overview())
        self.assertIsNone(plain.assumption)
        self.assertNotIn("assumption", plain.to_dict())
        for bad in (_overview(assumption={"count_basis": "distinct_people"}),
                    _overview(assumption={"count_basis": "booked_seats", "label": "x"}),
                    _overview(assumption=None), _overview(assumption="booked_seats"),
                    {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE,
                     "assumption": dict(ASSUMPTION)}):
            with self.subTest(bad=bad.get("assumption")), self.assertRaises(ModelError) as refused:
                recipe_model._proposal(bad)
            self.assertEqual((refused.exception.code, refused.exception.reason), ("invalid_request", "root_shape"))

    def test_the_persisted_action_carries_the_assumption_in_the_closed_shape(self):
        stated = recipe_model._proposal(_overview(assumption=dict(ASSUMPTION))).to_dict()
        self.assertTrue(evaluate._action_shape(stated))
        self.assertTrue(evaluate._action_shape(recipe_model._proposal(_overview()).to_dict()))

    def test_the_statement_names_confirmed_booked_seats_and_the_unavailable_meanings(self):
        stated = recipe_model._proposal(_overview(assumption=dict(ASSUMPTION)))
        self.assertEqual(recipe_model.assumption_statement(stated), {
            "count_basis": "booked_seats", "reported_as": "confirmed booked seats",
            "unavailable": [basis for basis in COUNT_BASES if basis != "booked_seats"]})
        self.assertEqual(recipe_model.assumption_statement(stated)["unavailable"],
                         ["known_booking_accounts", "attendance_visits", "distinct_people"])
        self.assertIsNone(recipe_model.assumption_statement(recipe_model._proposal(_overview())))
        self.assertIsNone(recipe_model.assumption_statement(None))


class ContractTextTests(unittest.TestCase):
    def test_the_schema_admits_the_assumption_only_on_the_overview_branch(self):
        branches = recipe_model.output_schema()["oneOf"]
        requests = {branch["properties"]["recipe_id"]["const"]: branch for branch in branches
                    if branch["properties"]["outcome"]["const"] == "request"}
        overview = requests["overview"]
        self.assertEqual(overview["properties"]["assumption"], {
            "type": "object", "additionalProperties": False, "required": ["count_basis"],
            "properties": {"count_basis": {"const": "booked_seats"}}})
        self.assertEqual(overview["required"], ["outcome", "recipe_id", "recipe_version", "request"])
        for recipe in ("compare", "breakdown"):
            self.assertNotIn("assumption", requests[recipe]["properties"])
        for branch in branches:
            if branch["properties"]["outcome"]["const"] != "request":
                self.assertNotIn("assumption", branch["properties"])

    def test_the_instruction_and_context_state_the_rule(self):
        text = recipe_model.SYSTEM_INSTRUCTION
        for phrase in ('assumption:{"count_basis":"booked_seats"}', "headcount",
                       "undecided between named meanings"):
            self.assertIn(phrase, text)
        context = recipe_model.runtime_context()
        self.assertEqual(context["count_assumption"], {
            "assumption": ASSUMPTION, "applies_to": "overview", "reports": "confirmed booked seats",
            "unavailable": ["known_booking_accounts", "attendance_visits", "distinct_people"]})
        self.assertIn("only when the question explicitly leaves the count basis undecided between named meanings",
                      context["clarification"]["count_basis"])
        overview = next(recipe for recipe in context["recipes"] if recipe["id"] == "overview")
        self.assertNotIn("people counts", overview["unsupported"])
        self.assertIn("required account/attendance/distinct-people counts", overview["unsupported"])
        self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                          recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                         ("recipe-selection-instruction-v7", "learningops-recipe-context-v4",
                          "recipe-request-json-v3", "recipe-structured-output-v3"))

    def test_every_dev_question_and_a_full_input_fit_the_unchanged_request_cap(self):
        self.assertEqual((MAX_INPUT_BYTES, MAX_REQUEST_BYTES), (4096, 32768))
        questions = ["x" * MAX_INPUT_BYTES]
        for panel_id in ("p3-dev-bound-meaning-v2", "p3-dev-mechanism-probe-v2", "p3-dev-matrix-v1"):
            entry = next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)
            questions += [case.question for case in p3_assets.load_panel(ROOT / entry["path"]).cases]
        for question in questions:
            sent = []

            def respond(request):
                sent.append(request)
                return httpx.Response(200, json={"model": gateway.MODEL, "choices": [{
                    "index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"outcome":"declined"}'}}]})

            client = GatewayClient(GatewayConfig("https://v13-size-private.invalid/v1", "dummy-v13-key"),
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


class RegistryAndPipelineTests(unittest.TestCase):
    def test_v13_is_the_registered_current_candidate(self):
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]),
                         ("p3-count-assumption-v13", "p3-v10-restoration-v12"))
        self.assertEqual(registry.check()["runtime_files_changed"], [])

    def test_a_stated_answer_runs_the_unchanged_kernel_and_is_annex_correct(self):
        with tempfile.TemporaryDirectory(prefix="v13-", dir=ROOT / ".artifacts") as tmp:
            database = Path(tmp) / "fixture.sqlite"
            fixture.build(database)
            action = model.canonical_json(_overview(assumption=ASSUMPTION))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(
                "Give me the March 2026 overview for CTR-A01, including the headcount.", database,
                evaluate._replay_client(action, [])))
        self.assertIsNone(result.error)
        self.assertEqual(result.proposal.assumption, ASSUMPTION)
        self.assertEqual(evaluate._validated_action(result), action)
        seats = next(slot for slot in result.analysis_pack.slots if slot.slot_id == "seats")
        self.assertEqual(seats.state, "checked")
        row = {"oracle_id": "dev-MN1.v2", "validated_action": evaluate._validated_action(result)}
        self.assertEqual(evaluate.annexed(row, True, {"dev-MN1.v2": ASSUMPTION}), "correct")


if __name__ == "__main__":
    unittest.main()
