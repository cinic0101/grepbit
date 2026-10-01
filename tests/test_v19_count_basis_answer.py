"""Candidate v19 rulers (docs/count-basis-answer-v19.md, ADR #158): offline, fixture and mock transports only."""
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
from test_evaluate import BASE, GRANT, KEY, SERVER_ANSWERED, EvaluateHarness
from test_evaluate import envelope as wire_envelope
from test_recipe_model import envelope, period

ROOT = Path(__file__).resolve().parents[1]
V18, V19 = "p3-count-scope-v18", "p3-count-basis-answer-v19"
ASSUMPTION = {"count_basis": "booked_seats"}
SENTENCE = (" The server answers a count_basis clarification with booked seats and states that assumption, because "
            "no other count meaning is executable here.")
QUESTION = "CTR-A01, March 2026: count the people as seats or as booking accounts? I have not decided."


def clarification(kind="count_basis", values=("booked_seats", "known_booking_accounts"), code="CTR-A01"):
    scope = dict(period(), center_code=code)
    if kind == "center":
        choices = [{"type": "center", "request": dict(scope, center_code=c)} for c in ("CTR-A01", "CTR-B01")]
    else:
        choices = [{"type": kind, "scope": dict(scope), "value": value} for value in values]
    return {"outcome": "clarify", "clarification": {
        "kind": kind, "choices": [{"id": f"c{i}", "semantic_value": v} for i, v in enumerate(choices, 1)]}}


class ContextTests(unittest.TestCase):
    def test_only_the_count_basis_context_entry_changes_from_v18(self):
        v18 = registry.load_entry(V18)
        self.assertEqual((recipe_model.INSTRUCTION_VERSION, recipe_model.CONTEXT_VERSION,
                          recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                         ("recipe-selection-instruction-v11", "learningops-recipe-context-v7",
                          "recipe-request-json-v5", "recipe-structured-output-v5"))
        live = recipe_model.context_identity()
        self.assertEqual(live["instruction_sha256"], v18["recipe_context"]["instruction_sha256"])
        self.assertEqual(recipe_model.structured_output_identity(), v18["structured_output"])
        self.assertNotEqual(live["context_sha256"], v18["recipe_context"]["context_sha256"])
        context = recipe_model.runtime_context()
        entry = context["clarification"]["count_basis"]
        self.assertTrue(entry.endswith(SENTENCE))
        # The earlier rulers' phrase stays, and removing the sentence gives back v18's context exactly.
        self.assertIn("only when the question explicitly leaves the count basis undecided between named meanings", entry)
        context["clarification"]["count_basis"] = entry[: -len(SENTENCE)]
        context["version"] = "learningops-recipe-context-v6"
        self.assertEqual(recipe_model._identity(context)["context_sha256"], v18["recipe_context"]["context_sha256"])

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

            client = GatewayClient(GatewayConfig("https://v19-size-private.invalid/v1", "dummy-v19-key"),
                                   transport=httpx.MockTransport(respond))
            result = asyncio.run(recipe_model.interpret_recipe_and_execute(question, Path("unused.sqlite"), client))
            with self.subTest(question=question[:40]):
                self.assertEqual((result.error.code, len(sent)), ("model_declined", 1))
                self.assertLessEqual(len(sent[0].content), MAX_REQUEST_BYTES)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="v19-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.database = Path(tmp.name) / "fixture.sqlite"
        fixture.build(self.database)

    async def run_action(self, action, question=QUESTION):
        def respond(request):
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig("https://v19-private.invalid/v1", "dummy-v19-key"),
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
                # The persisted action is the model's own clarification, so replay rebuilds the answer.
                validated = evaluate._validated_action(result)
                self.assertEqual(model.strict_json(validated), action)
                self.assertEqual(evaluate._stated_assumption(model.strict_json(validated)), ASSUMPTION)

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
        self.assertEqual(failed.evidence["source_clarification"], action["clarification"])
        self.assertEqual(model.strict_json(evaluate._validated_action(failed)), action)
        # A timeout after execution (inside the call) keeps the same pairing as the late timeout path.
        now, original = [0.0], recipe_model.execute_overview

        def slow(*args, **kwargs):
            pack = original(*args, **kwargs)
            now[0] = 1000.0
            return pack

        def respond(request):
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig("https://v19-private.invalid/v1", "dummy-v19-key"),
                               transport=httpx.MockTransport(respond))
        with patch.object(recipe_model, "execute_overview", side_effect=slow):
            timed = await recipe_model.interpret_recipe_and_execute(QUESTION, self.database, client,
                                                                    clock=lambda: now[0])
        self.assertEqual(timed.error.code, "timeout")
        self.assertEqual(timed.evidence["source_clarification"], action["clarification"])
        self.assertEqual(model.strict_json(evaluate._validated_action(timed)), action)

    async def test_an_invalid_count_basis_clarification_fails_before_any_answer(self):
        # A scope whose center the question does not name fails the existing question check.
        result = await self.run_action(clarification(code="CTR-B01"))
        self.assertEqual(result.error.code, "invalid_request")
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.analysis_pack)
        self.assertIsNone(result.source_clarification)


class EvaluatorTests(unittest.TestCase):
    def test_the_answered_clarification_maps_to_an_answer_everywhere(self):
        text = evaluate._action_text(clarification())
        graded = {"actual_action": "answer"}
        routing._check_validated_action(text, {**graded, "outcome": "complete_correct"})
        # Before v19 the same action was a real clarification: the recorded actual action decides (ADR #158).
        routing._check_validated_action(text, {"actual_action": "clarify", "outcome": "correct_clarification"})
        with self.assertRaises(p3_assets.P3Error):
            routing._check_validated_action(text, {"actual_action": "decline", "outcome": "false_refusal"})
        center = evaluate._action_text(clarification("center"))
        routing._check_validated_action(center, {"actual_action": "clarify", "outcome": "correct_clarification"})
        with self.assertRaises(p3_assets.P3Error):
            routing._check_validated_action(center, {"actual_action": "answer", "outcome": "complete_correct"})
        self.assertEqual(evaluate._stated_assumption(clarification()), ASSUMPTION)
        self.assertEqual(evaluate._stated_assumption(clarification(), "answer"), ASSUMPTION)
        self.assertIsNone(evaluate._stated_assumption(clarification(), "clarify"))
        self.assertIsNone(evaluate._stated_assumption(clarification("center")))
        self.assertEqual(reading_diagnostic._recorded(text, "answer"), ("answer", None))
        self.assertEqual(reading_diagnostic._recorded(text, "clarify"), ("clarify", "count_basis"))
        # The annex verdict follows the row too: a pre-v19 clarification states no assumption.
        expected_none = {"o.v1": {"count_basis": "booked_seats"}}
        self.assertEqual(evaluate.annexed({"oracle_id": "o.v1", "validated_action": text, "actual_action": "clarify"},
                                          True, {}), "correct")
        self.assertEqual(evaluate.annexed({"oracle_id": "o.v1", "validated_action": text, "actual_action": "answer"},
                                          True, expected_none), "correct")


class PreV19ArchiveTests(EvaluateHarness):
    """A v18-shaped archive (a real count_basis clarification row) reads back, aggregates and gates against v19."""

    @contextmanager
    def as_v18(self):
        entry = registry.load_entry(V18)
        checked = {"candidate_id": V18, "semantic_identity_sha256": entry["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        # The v18 runtime presented a count_basis clarification; v19 answers it (ADR #158).
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=entry), patch.object(self, "candidate", V18), \
                patch.object(recipe_model, "_server_answers", return_value=False):
            yield

    def client(self):
        cases = self.panel.cases

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            return httpx.Response(200, json=wire_envelope(json.dumps(self.by_oracle[case.oracle_id])))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def observe(self, grant, *, v18=False):
        self.serial_runs = getattr(self, "serial_runs", 0) + 1
        context = self.as_v18() if v18 else contextmanager(lambda: (yield))()
        with context:
            packet = self.prepare(repetition=self.serial_runs)
            output = self.output()
            authorization = self.root / f"authorization-{output.name}.json"
            evaluate.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
            await self.run_mock(packet, output, authorization, client=self.client())
        return evaluate.record(output / "report.json", runs_path=self.runs,
                               now=f"2026-10-01T09:{self.serial_runs:02d}:00Z"), output

    async def test_a_v18_archive_reads_back_and_gates_against_v19(self):
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        [answered] = SERVER_ANSWERED
        baseline = [await self.observe(1001, v18=True), await self.observe(1002, v18=True)]
        sentinel = await self.observe(1050, v18=True)
        for run, output in (*baseline, sentinel):
            report = evaluate.read_report(output / "report.json")
            row = next(row for row in report["results"] if row["case_id"] == answered)
            # The pre-v19 row is the real clarification it was, and reads back as one.
            self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                             ("clarify", "correct_clarification", "count_basis"))
            self.assertEqual(run["correct"], len(self.panel.cases))
        candidate, output = await self.observe(1050)
        row = next(row for row in evaluate.read_report(output / "report.json")["results"] if row["case_id"] == answered)
        self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                         ("answer", "missed_clarification", None))
        self.assertEqual(model.strict_json(row["validated_action"])["clarification"]["kind"], "count_basis")
        aggregate = evaluate.aggregate("synthetic-dev", "litellm-31b", registry.load_entry(V18)["candidate_id"],
                                       runs_path=self.runs, panels_path=self.panels)
        self.assertEqual({row["class"] for row in aggregate["inputs"]}, {"stable_correct"})
        result = evaluate.gate(V19, V18, "litellm-31b", f"{GRANT}1050", ["synthetic-dev"],
                               runs_path=self.runs, panels_path=self.panels)
        [panel] = result["panels"]
        classes = {row["case_id"]: row["class"] for row in panel["inputs"]}
        # Against the historical clarify oracle, v19's answer is a break: the gate runs and says so.
        self.assertEqual(classes[answered], "broke")
        self.assertEqual({kind for case, kind in classes.items() if case != answered}, {"unchanged_correct"})
        self.assertEqual(result["verdict"], "regression")


class RegistryTests(unittest.TestCase):
    def test_v19_is_the_registered_current_candidate(self):
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V19, V18))
        self.assertEqual(registry.check()["runtime_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
