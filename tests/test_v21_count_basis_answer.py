"""Candidate v21 rulers (docs/count-basis-answer-v21.md, #164): offline, fixture and mock transports only."""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import gateway, model, recipe_model
from grepbit.contracts import KernelError
from grepbit.gateway import GatewayClient, GatewayConfig, MAX_INPUT_BYTES, MAX_REQUEST_BYTES, MODEL
from tools import candidate_registry as registry, evaluate, fixture, p3_assets, reading_diagnostic
from tools import routing_upper_bound as routing
from test_evaluate import BASE, GRANT, KEY, EvaluateHarness
from test_evaluate import envelope as wire_envelope
from test_recipe_model import envelope, period

ROOT = Path(__file__).resolve().parents[1]
V20, V21 = "p3-v18-restoration-v20", "p3-count-basis-answer-v21"
ASSUMPTION = {"count_basis": "booked_seats"}
QUESTION = "CTR-A01, March 2026: count the people as seats or as booking accounts? I have not decided."
# The synthetic harness copies p3-development-v1, whose C01 oracle is a count_basis clarification (history).
ANSWERED = "C01_count_basis.en"
V19_FIXTURE = ROOT / "tests/fixtures/v19_recipe_model.py"
# v21's runtime is v19's with exactly these two model-facing lines back at v18's (and v20's) bytes.
CONTEXT_LINES = (
    ('CONTEXT_VERSION = "learningops-recipe-context-v7"', 'CONTEXT_VERSION = "learningops-recipe-context-v6"'),
    ("                'booked_seats is executable through this recipe. The server answers a count_basis clarification '\n"
     "                'with booked seats and states that assumption, because no other count meaning is executable here.'\n",
     "                'booked_seats is executable through this recipe.'\n"),
)
MODEL_INPUT = ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
               "candidate_sha256", "wire_witnesses")


def superseded():
    """v21 is registered but no longer current: its runtime, context, archive and current-registration checks stop
    applying; its registration identity and the evaluator checks stay."""
    index = registry.load_index()
    return V21 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V21


def clarification(kind="count_basis", values=("booked_seats", "known_booking_accounts"), code="CTR-A01"):
    scope = dict(period(), center_code=code)
    if kind == "center":
        choices = [{"type": "center", "request": dict(scope, center_code=c)} for c in ("CTR-A01", "CTR-B01")]
    else:
        choices = [{"type": kind, "scope": dict(scope), "value": value} for value in values]
    return {"outcome": "clarify", "clarification": {
        "kind": kind, "choices": [{"id": f"c{i}", "semantic_value": v} for i, v in enumerate(choices, 1)]}}


class ContextTests(unittest.TestCase):
    def setUp(self):
        if superseded():
            self.skipTest("v21 superseded; the live runtime is no longer v21's")

    def test_the_runtime_is_v19s_with_v18s_two_context_lines(self):
        text = V19_FIXTURE.read_text(encoding="utf-8")
        for old, new in CONTEXT_LINES:
            self.assertEqual(text.count(old), 1)
            text = text.replace(old, new)
        self.assertEqual((ROOT / "grepbit/recipe_model.py").read_text(encoding="utf-8"), text)

    def test_the_model_input_is_v20s(self):
        v20, live = registry.load_entry(V20), registry.live_identity()
        for key in MODEL_INPUT:
            self.assertEqual(live[key], v20[key], key)
        self.assertEqual(recipe_model.CONTEXT_VERSION, "learningops-recipe-context-v6")
        self.assertNotEqual(registry.behavior_identity(live), registry.behavior_identity(v20))

    def test_every_dev_question_and_a_full_input_fit_the_unchanged_request_cap(self):
        self.assertEqual((MAX_INPUT_BYTES, MAX_REQUEST_BYTES), (4096, 32768))
        questions = ["x" * MAX_INPUT_BYTES]
        for row in [row for row in evaluate.load_panels()["panels"] if row["tier"] == "dev"]:
            questions += [case.question for case in p3_assets.load_panel(ROOT / row["path"]).cases]
        for question in questions:
            sent = []

            def respond(request):
                sent.append(request)
                return httpx.Response(200, json={"model": gateway.MODEL, "choices": [{
                    "index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"outcome":"declined"}'}}]})

            client = GatewayClient(GatewayConfig("https://v21-size-private.invalid/v1", "dummy-v21-key"),
                                   transport=httpx.MockTransport(respond))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(question, Path("unused.sqlite"), client))
            with self.subTest(question=question[:40]):
                self.assertEqual((result.error.code, len(sent)), ("model_declined", 1))
                self.assertLessEqual(len(sent[0].content), MAX_REQUEST_BYTES)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if superseded():
            self.skipTest("v21 superseded; the live runtime is no longer v21's")
        tmp = tempfile.TemporaryDirectory(prefix="v21-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.database = Path(tmp.name) / "fixture.sqlite"
        fixture.build(self.database)

    async def run_action(self, action, question=QUESTION):
        def respond(request):
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig("https://v21-private.invalid/v1", "dummy-v21-key"),
                               transport=httpx.MockTransport(respond))
        return await recipe_model.interpret_recipe_and_execute(question, self.database, client)

    async def test_a_count_basis_clarification_is_answered_with_booked_seats_and_the_stated_assumption(self):
        for values in (("booked_seats", "known_booking_accounts"), ("booked_seats", "distinct_people"),
                       ("booked_seats", "known_booking_accounts", "attendance_visits", "distinct_people")):
            action = clarification(values=values)
            with self.subTest(values=values):
                result = await self.run_action(action)
                self.assertIsNone(result.error)
                self.assertIsNone(result.clarification)
                self.assertIsNone(result.presentation)
                self.assertEqual((result.proposal.recipe_id, result.proposal.count_request), ("overview", "unresolved"))
                self.assertEqual(result.proposal.request.to_dict(), dict(period(), center_code="CTR-A01"))
                self.assertEqual(result.analysis_pack.status, "complete")
                self.assertEqual(result.source_clarification.to_dict(), action["clarification"])
                self.assertEqual(result.evidence["source_clarification"], action["clarification"])
                self.assertEqual(result.evidence["count_assumption"]["count_basis"], "booked_seats")
                self.assertEqual(result.evidence["count_assumption"]["unavailable"],
                                 ["known_booking_accounts", "attendance_visits", "distinct_people"])
                validated = evaluate._validated_action(result)
                self.assertEqual(model.strict_json(validated), action)

    async def test_other_clarification_kinds_still_clarify_without_execution(self):
        for action, question in ((clarification("center"), "CTR-A01 or CTR-B01, March 2026?"),
                                 (clarification("metric_meaning", ("confirmed_booked_amount", "cash_received")),
                                  QUESTION)):
            with self.subTest(kind=action["clarification"]["kind"]):
                result = await self.run_action(action, question)
                self.assertIsNone(result.error)
                self.assertEqual(result.clarification.to_dict(), action["clarification"])
                self.assertIsNone(result.proposal)
                self.assertIsNone(result.analysis_pack)
                self.assertIsNone(result.source_clarification)
                self.assertIsNone(result.evidence["source_clarification"])

    async def test_a_failed_answer_still_persists_the_models_own_clarification(self):
        action = clarification()
        with patch.object(recipe_model, "execute_overview", side_effect=KernelError("execution_failure", "synthetic")):
            failed = await self.run_action(action)
        self.assertEqual(failed.error.code, "kernel_failure")
        self.assertIsNone(failed.analysis_pack)
        self.assertEqual(failed.source_clarification.to_dict(), action["clarification"])
        self.assertEqual(model.strict_json(evaluate._validated_action(failed)), action)
        now, original = [0.0], recipe_model.execute_overview

        def slow(*args, **kwargs):
            pack = original(*args, **kwargs)
            now[0] = 1000.0
            return pack

        def respond(request):
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig("https://v21-private.invalid/v1", "dummy-v21-key"),
                               transport=httpx.MockTransport(respond))
        with patch.object(recipe_model, "execute_overview", side_effect=slow):
            timed = await recipe_model.interpret_recipe_and_execute(QUESTION, self.database, client,
                                                                    clock=lambda: now[0])
        self.assertEqual(timed.error.code, "timeout")
        self.assertEqual(timed.evidence["source_clarification"], action["clarification"])
        self.assertEqual(model.strict_json(evaluate._validated_action(timed)), action)

    async def test_an_invalid_count_basis_clarification_fails_before_any_answer(self):
        result = await self.run_action(clarification(code="CTR-B01"))
        self.assertEqual(result.error.code, "invalid_request")
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.analysis_pack)
        self.assertIsNone(result.source_clarification)


class EvaluatorTests(unittest.TestCase):
    def test_the_recorded_row_decides_and_no_row_states_no_assumption(self):
        text = evaluate._action_text(clarification())
        routing._check_validated_action(text, {"actual_action": "answer", "outcome": "complete_correct"})
        routing._check_validated_action(text, {"actual_action": "clarify", "outcome": "correct_clarification"})
        self.assertEqual(evaluate._stated_assumption(clarification(), "answer"), ASSUMPTION)
        self.assertIsNone(evaluate._stated_assumption(clarification(), "clarify"))
        self.assertIsNone(evaluate._stated_assumption(clarification()))
        self.assertEqual(reading_diagnostic._recorded(text, "answer"), ("answer", None))
        self.assertEqual(reading_diagnostic._recorded(text, "clarify"), ("clarify", "count_basis"))


class PreV21ArchiveTests(EvaluateHarness):
    """A v20-shaped archive (a real count_basis clarification row) reads back, aggregates and gates against v21."""

    def setUp(self):
        if superseded():
            self.skipTest("v21 superseded; its candidate run would be recorded under another current candidate")
        super().setUp()

    @contextmanager
    def as_v20(self):
        entry = registry.load_entry(V20)
        checked = {"candidate_id": V20, "semantic_identity_sha256": entry["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        # v20's runtime presented a count_basis clarification; v21 answers it.
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=entry), patch.object(self, "candidate", V20), \
                patch.object(recipe_model, "_server_answers", return_value=False):
            yield

    def client(self):
        cases = self.panel.cases

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            return httpx.Response(200, json=wire_envelope(json.dumps(self.by_oracle[case.oracle_id])))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def observe(self, grant, *, v20=False):
        self.serial_runs = getattr(self, "serial_runs", 0) + 1
        context = self.as_v20() if v20 else contextmanager(lambda: (yield))()
        with context:
            packet = self.prepare(repetition=self.serial_runs)
            output = self.output()
            authorization = self.root / f"authorization-{output.name}.json"
            evaluate.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
            await self.run_mock(packet, output, authorization, client=self.client())
        return evaluate.record(output / "report.json", runs_path=self.runs,
                               now=f"2026-10-01T11:{self.serial_runs:02d}:00Z"), output

    async def test_a_v20_archive_reads_back_and_gates_against_v21(self):
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        baseline = [await self.observe(3001, v20=True), await self.observe(3002, v20=True)]
        sentinel = await self.observe(3050, v20=True)
        for run, output in (*baseline, sentinel):
            report = evaluate.read_report(output / "report.json")
            row = next(row for row in report["results"] if row["case_id"] == ANSWERED)
            self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                             ("clarify", "correct_clarification", "count_basis"))
            self.assertEqual((run["candidate_id"], run["correct"]), (V20, len(self.panel.cases)))
        candidate, output = await self.observe(3050)
        row = next(row for row in evaluate.read_report(output / "report.json")["results"] if row["case_id"] == ANSWERED)
        self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                         ("answer", "missed_clarification", None))
        self.assertEqual(candidate["candidate_id"], V21)
        aggregate = evaluate.aggregate("synthetic-dev", "litellm-31b", V20, runs_path=self.runs,
                                       panels_path=self.panels)
        self.assertEqual({row["class"] for row in aggregate["inputs"]}, {"stable_correct"})
        result = evaluate.gate(V21, V20, "litellm-31b", f"{GRANT}3050", ["synthetic-dev"],
                               runs_path=self.runs, panels_path=self.panels)
        self.assertEqual(result["candidate"]["candidate_sha256"], result["baseline"]["candidate_sha256"])
        self.assertNotEqual(result["candidate"]["behavior_sha256"], result["baseline"]["behavior_sha256"])
        [panel] = result["panels"]
        classes = {row["case_id"]: row["class"] for row in panel["inputs"]}
        # Against the historical clarify oracle, v21's answer is a break: the gate runs and says so.
        self.assertEqual(classes.pop(ANSWERED), "broke")
        self.assertEqual(set(classes.values()), {"unchanged_correct"})
        self.assertEqual(result["verdict"], "regression")


class RegistrationTests(unittest.TestCase):
    def test_v21s_registration_has_v20s_model_input_and_its_own_behaviour(self):
        # Immutable registry entries only, so this stays checked after v21 is superseded.
        v20, v21 = registry.load_entry(V20), registry.load_entry(V21)
        self.assertEqual(v21["ancestor"], V20)
        for key in MODEL_INPUT:
            self.assertEqual(v21[key], v20[key], key)
        self.assertNotEqual(registry.behavior_identity(v21), registry.behavior_identity(v20))
        self.assertEqual([name for name in v21["runtime_files_sha256"]
                          if v21["runtime_files_sha256"][name] != v20["runtime_files_sha256"].get(name)],
                         ["grepbit/recipe_model.py"])

    def test_v21_is_the_registered_current_candidate(self):
        if superseded():
            self.skipTest("v21 superseded; its registration is no longer current")
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V21, V20))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
