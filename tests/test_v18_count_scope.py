"""Candidate v18 rulers (docs/count-scope-v18.md, #152): offline, mock transports only."""
import asyncio
import hashlib
import unittest
from pathlib import Path

import httpx

from grepbit import gateway, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MAX_INPUT_BYTES, MAX_REQUEST_BYTES
from tools import candidate_registry as registry, evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
V17, V18 = "p3-count-directive-v17", "p3-count-scope-v18"
V17_DIRECTIVE = ('With a complete explicit Overview scope, a generic people count (headcount, how many people, '
                 'people who booked) that names no seats, accounts, attendance or distinct individuals is answered '
                 'with the Overview request and count_request "unresolved", not a count_basis clarification.')
# (v17 text, v18 text) for each of the three edits, in instruction order.
EDITS = (
    ('"none" when it asks for no count;',
     '"none" when it asks for no count, including a general overview of bookings that asks for no number of '
     'people;'),
    ('Use count_basis only when the question itself is undecided between named meanings.',
     'Use count_basis only when the user says they are undecided between named meanings.'),
    (V17_DIRECTIVE,
     V17_DIRECTIVE + ' Doubt about which basis the system counts by is not the user being undecided: a people '
     'count that names seats or accounts only in that doubt is also answered with count_request "unresolved", '
     'and the stated assumption tells the basis.'),
)


def superseded():
    """v18 is registered but no longer current (v19, #158). v19 changes only the context's count_basis entry, so the
    three instruction edits and their undo to v17 stay live; the version tuple, the v17-equal context digest and the
    registration stop applying."""
    index = registry.load_index()
    return V18 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V18


class ScopeTests(unittest.TestCase):
    def test_only_the_instruction_changes_from_v17(self):
        text = recipe_model.SYSTEM_INSTRUCTION
        v17_text = text
        for old, new in EDITS:
            self.assertEqual(text.count(new), 1)
            v17_text = v17_text.replace(new, old, 1)
        for old, _ in EDITS[:2]:
            self.assertNotIn(old, text)
        if not superseded():
            self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                              recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                             ("recipe-selection-instruction-v11", "learningops-recipe-context-v6",
                              "recipe-request-json-v5", "recipe-structured-output-v5"))
        v17 = registry.load_entry(V17)
        self.assertEqual(recipe_model.structured_output_identity(), v17["structured_output"])
        live = recipe_model.context_identity()
        if not superseded():
            self.assertEqual(live["context_sha256"], v17["recipe_context"]["context_sha256"])
        self.assertNotEqual(live["instruction_sha256"], v17["recipe_context"]["instruction_sha256"])
        # Undoing the three edits gives back v17's instruction exactly.
        self.assertEqual(hashlib.sha256(v17_text.encode()).hexdigest(), v17["recipe_context"]["instruction_sha256"])

    def test_the_phrases_earlier_rulers_check_as_behaviour_stay(self):
        text = recipe_model.SYSTEM_INSTRUCTION
        self.assertIn("undecided between named meanings", text)
        self.assertEqual(text.count(V17_DIRECTIVE), 1)
        self.assertIn("only when the question explicitly leaves the count basis undecided between named meanings",
                      recipe_model.runtime_context()["clarification"]["count_basis"])

    def test_every_dev_question_and_a_full_input_fit_the_unchanged_request_cap(self):
        self.assertEqual((MAX_INPUT_BYTES, MAX_REQUEST_BYTES), (4096, 32768))
        questions = ["x" * MAX_INPUT_BYTES]
        for entry in [row for row in evaluate.load_panels()["panels"] if row["tier"] == "dev"]:
            questions += [case.question for case in p3_assets.load_panel(ROOT / entry["path"]).cases]
        for question in questions:
            sent = []

            def respond(request):
                sent.append(request)
                return httpx.Response(200, json={"model": gateway.MODEL, "choices": [{
                    "index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"outcome":"declined"}'}}]})

            client = GatewayClient(GatewayConfig("https://v18-size-private.invalid/v1", "dummy-v18-key"),
                                   transport=httpx.MockTransport(respond))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(question, Path("unused.sqlite"), client))
            with self.subTest(question=question[:40]):
                self.assertEqual(result.error.code, "model_declined")
                self.assertEqual(len(sent), 1)
                self.assertLessEqual(len(sent[0].content), MAX_REQUEST_BYTES)


class RegistryTests(unittest.TestCase):
    def test_v18_is_the_registered_current_candidate(self):
        if superseded():
            self.skipTest("v18 superseded; its registration is no longer current")
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V18, V17))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
