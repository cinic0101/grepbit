"""Candidate v17 rulers (docs/count-directive-v17.md, #146): offline, mock transports only."""
import asyncio
import hashlib
import unittest
from pathlib import Path

import httpx

from grepbit import gateway, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MAX_INPUT_BYTES, MAX_REQUEST_BYTES
from tools import candidate_registry as registry, evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
V16, V17 = "p3-count-reading-v16", "p3-count-directive-v17"
DIRECTIVE = ('With a complete explicit Overview scope, a generic people count (headcount, how many people, people '
             'who booked) that names no seats, accounts, attendance or distinct individuals is answered with the '
             'Overview request and count_request "unresolved", not a count_basis clarification.')


def superseded():
    """v17 is registered but no longer current (v18, #152). Only its identity-bound checks stop applying:
    the directive stays live in v18 and stays checked here."""
    index = registry.load_index()
    return V17 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V17


class DirectiveTests(unittest.TestCase):
    def test_only_the_instruction_changes_from_v16(self):
        self.assertEqual(recipe_model.SYSTEM_INSTRUCTION.count(DIRECTIVE), 1)
        v16_text = recipe_model.SYSTEM_INSTRUCTION.replace(" " + DIRECTIVE, "", 1)
        if not superseded():
            self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                              recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                             ("recipe-selection-instruction-v10", "learningops-recipe-context-v6",
                              "recipe-request-json-v5", "recipe-structured-output-v5"))
        v16 = registry.load_entry(V16)
        self.assertEqual(recipe_model.structured_output_identity(), v16["structured_output"])
        live = recipe_model.context_identity()
        self.assertEqual(live["context_sha256"], v16["recipe_context"]["context_sha256"])
        self.assertNotEqual(live["instruction_sha256"], v16["recipe_context"]["instruction_sha256"])
        # Removing the one sentence gives back v16's instruction exactly.
        if not superseded():
            self.assertEqual(hashlib.sha256(v16_text.encode()).hexdigest(),
                             v16["recipe_context"]["instruction_sha256"])

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

            client = GatewayClient(GatewayConfig("https://v17-size-private.invalid/v1", "dummy-v17-key"),
                                   transport=httpx.MockTransport(respond))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(question, Path("unused.sqlite"), client))
            with self.subTest(question=question[:40]):
                self.assertEqual(result.error.code, "model_declined")
                self.assertEqual(len(sent), 1)
                self.assertLessEqual(len(sent[0].content), MAX_REQUEST_BYTES)


class RegistryTests(unittest.TestCase):
    def test_v17_is_the_registered_current_candidate(self):
        if superseded():
            self.skipTest("v17 superseded; its registration is no longer current")
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V17, V16))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
