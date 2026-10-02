"""Candidate v22 rulers (docs/overview-basis-v22.md, #169 step A3): offline, fixture and mock transports only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig
from tools import candidate_registry as registry, fixture
from test_recipe_model import envelope, period, proposal

ROOT = Path(__file__).resolve().parents[1]
V21, V22 = "p3-count-basis-answer-v21", "p3-overview-basis-v22"
ASSUMPTION = {"count_basis": "booked_seats"}
QUESTION = "CTR-A01, March 2026 bookings overview."
MODEL_INPUT = ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
               "candidate_sha256", "wire_witnesses")
# v22's one runtime change against v21's registered grepbit/recipe_model.py.
V21_PROPERTY = ('        """The owner\'s count assumption, stated exactly when the count reading is unresolved."""\n'
                '        return dict(ASSUMPTION) if self.count_request == "unresolved" else None\n')
V22_PROPERTY = ('        """The owner\'s count assumption. Policy A (#169): every executed Overview states it; a named\n'
                '        unavailable count is declined by the server before execution, so it states none."""\n'
                '        return (dict(ASSUMPTION) if self.recipe_id == "overview" and self.count_request not in UNAVAILABLE_COUNTS\n'
                '                else None)\n')


def superseded():
    """v22 is registered but no longer current: its runtime and current-registration checks stop applying."""
    index = registry.load_index()
    return V22 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V22


def overview(count_request=None):
    action = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
              "request": dict(period(), center_code="CTR-A01")}
    if count_request is not None:
        action["count_request"] = count_request
    return action


class RuntimeFileTests(unittest.TestCase):
    def setUp(self):
        if superseded():
            self.skipTest("v22 superseded; the live runtime is no longer v22's")

    def test_the_runtime_is_v21s_with_one_property_changed(self):
        text = (ROOT / "grepbit/recipe_model.py").read_text(encoding="utf-8")
        self.assertEqual(text.count(V22_PROPERTY), 1)
        restored = text.replace(V22_PROPERTY, V21_PROPERTY)
        self.assertEqual(hashlib.sha256(restored.encode("utf-8")).hexdigest(),
                         registry.load_entry(V21)["runtime_files_sha256"]["grepbit/recipe_model.py"])

    def test_the_model_input_is_v21s(self):
        v21, live = registry.load_entry(V21), registry.live_identity()
        for key in MODEL_INPUT:
            self.assertEqual(live[key], v21[key], key)
        self.assertNotEqual(registry.behavior_identity(live), registry.behavior_identity(v21))


class StatementTests(unittest.IsolatedAsyncioTestCase):
    """Policy A's behaviour, not v22's identity: it stays checked after v22 is superseded."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="v22-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.database = Path(tmp.name) / "fixture.sqlite"
        fixture.build(self.database)

    async def run_action(self, action, question=QUESTION):
        def respond(request):
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig("https://v22-private.invalid/v1", "dummy-v22-key"),
                               transport=httpx.MockTransport(respond))
        return await recipe_model.interpret_recipe_and_execute(question, self.database, client)

    async def test_every_executed_overview_states_the_basis(self):
        # An Overview action always carries a count reading (v16); one without fails request validation.
        for reading in ("none", "booked_seats", "unresolved"):
            with self.subTest(reading=reading):
                result = await self.run_action(overview(reading))
                self.assertIsNone(result.error)
                self.assertEqual(result.proposal.assumption, ASSUMPTION)
                statement = result.evidence["count_assumption"]
                self.assertEqual(statement["count_basis"], "booked_seats")
                self.assertEqual(statement["unavailable"],
                                 ["known_booking_accounts", "attendance_visits", "distinct_people"])

    async def test_a_named_unavailable_count_is_declined_with_no_statement(self):
        request = recipe_model._proposal(overview("none")).request
        for reading in recipe_model.UNAVAILABLE_COUNTS:
            with self.subTest(reading=reading):
                # The rule itself excludes it, not only the server's decline before execution.
                self.assertIsNone(recipe_model.RecipeProposal("overview", request, count_request=reading).assumption)
                result = await self.run_action(overview(reading))
                self.assertEqual(result.error.code, "model_declined")
                self.assertIsNone(result.evidence["count_assumption"])

    async def test_executed_compare_and_breakdown_state_none(self):
        for recipe in ("compare", "breakdown"):
            with self.subTest(recipe=recipe):
                result = await self.run_action(proposal(recipe))
                self.assertIsNone(result.error)
                self.assertEqual(result.proposal.recipe_id, recipe)
                self.assertIsNone(result.proposal.assumption)
                self.assertIsNone(result.evidence["count_assumption"])


class RegistrationTests(unittest.TestCase):
    def test_v22s_registration_has_v21s_model_input_and_its_own_behaviour(self):
        v21, v22 = registry.load_entry(V21), registry.load_entry(V22)
        self.assertEqual(v22["ancestor"], V21)
        for key in MODEL_INPUT:
            self.assertEqual(v22[key], v21[key], key)
        self.assertEqual([name for name in v22["runtime_files_sha256"]
                          if v22["runtime_files_sha256"][name] != v21["runtime_files_sha256"].get(name)],
                         ["grepbit/recipe_model.py"])

    def test_v22_is_the_registered_current_candidate(self):
        if superseded():
            self.skipTest("v22 superseded; its registration is no longer current")
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V22, V21))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
