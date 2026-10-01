"""Restoration v20 rulers (docs/v18-restoration-v20.md, #158): offline, fixture and mock transports only."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate, p3_assets, p3_eval
from test_evaluate import BASE, GRANT, KEY, EvaluateHarness
from test_evaluate import envelope as wire_envelope
from test_recipe_model import period

ROOT = Path(__file__).resolve().parents[1]
V18, V19, V20 = "p3-count-scope-v18", "p3-count-basis-answer-v19", "p3-v18-restoration-v20"
ASSUMPTION = {"count_basis": "booked_seats"}
# The synthetic harness copies p3-development-v1, whose C01 oracle is a count_basis clarification (history).
ANSWERED = "C01_count_basis.en"
V19_FIXTURE = ROOT / "tests/fixtures/v19_recipe_model.py"
IDENTITY = ("candidate_sha256", "semantic_identity_sha256", "recipe_context", "structured_output", "p1_context",
            "limits", "wire_witnesses", "runtime_files_sha256")
# The frozen pair, owner-approved back at its bytes at ba7e556 (#158 #issuecomment-5932833755). The 19 other tests
# #160 changed return to their ba7e556 bytes too; that is verified on the PR, not pinned here, so later edits to
# them stay possible.
FROZEN = {
    "tests/test_recipe_clarification.py": "36c3a189bfd3499c086eee83683c715490fb1d3fb10e44523029007e9923cc24",
    "tests/test_p3_exposed.py": "693addaa05d1530dddd12ee5d6b43d330c358349b85707d077deda2f8d9fd085",
}


def superseded():
    """v20 is registered but no longer current. Its runtime, frozen-pair, registration and end-to-end gate checks
    stop applying; the evaluator checks and the fixture's digest stay."""
    index = registry.load_index()
    return V20 in [r["candidate_id"] for r in index["entries"]] and index["current"] != V20


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clarification(kind="count_basis"):
    scope = dict(period(), center_code="CTR-A01")
    if kind == "center":
        choices = [{"type": "center", "request": dict(scope, center_code=c)} for c in ("CTR-A01", "CTR-B01")]
    else:
        choices = [{"type": kind, "scope": dict(scope), "value": v} for v in ("booked_seats", "known_booking_accounts")]
    return {"outcome": "clarify", "clarification": {
        "kind": kind, "choices": [{"id": f"c{i}", "semantic_value": v} for i, v in enumerate(choices, 1)]}}


def v19_drift():
    """The runtime files besides recipe_model.py whose bytes differ from v19's registration. The fixture reproduces
    v19 only together with them."""
    registered = registry.load_entry(V19)["runtime_files_sha256"]
    live = registry.live_identity()["runtime_files_sha256"]
    return sorted(name for name in set(registered) | set(live)
                  if name != "grepbit/recipe_model.py" and registered.get(name) != live.get(name))


def v19_runtime():
    """v19's frozen grepbit/recipe_model.py, loaded inside the grepbit package under a private name (ruler only)."""
    name = "grepbit._v19_recipe_model"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, V19_FIXTURE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


class IdentityTests(unittest.TestCase):
    def setUp(self):
        if superseded():
            self.skipTest("v20 superseded; the live runtime, frozen pair and registration are no longer v20's")

    def test_the_runtime_is_v18s_bytes_with_no_server_answer(self):
        v18 = registry.load_entry(V18)
        self.assertEqual(sha256(ROOT / "grepbit/recipe_model.py"), v18["runtime_files_sha256"]["grepbit/recipe_model.py"])
        self.assertEqual(recipe_model.CONTEXT_VERSION, "learningops-recipe-context-v6")
        self.assertFalse(hasattr(recipe_model, "_server_answers"))
        self.assertNotIn("source_clarification", recipe_model.RecipeInterpretation.__dataclass_fields__)

    def test_v20_is_the_registered_current_candidate_with_v18s_identity(self):
        v18, v20 = registry.load_entry(V18), registry.load_entry(V20)
        current = registry.current()
        self.assertEqual((current["candidate_id"], current["ancestor"]), (V20, V19))
        for key in IDENTITY:
            self.assertEqual(v20[key], v18[key], key)
        self.assertEqual(registry.check()["runtime_files_changed"], [])

    def test_the_frozen_pair_has_its_v18_bytes(self):
        for path, digest in FROZEN.items():
            self.assertEqual(sha256(ROOT / path), digest, path)
        import test_p3_exposed
        self.assertEqual(test_p3_exposed.SOURCE_SHA256["tests/test_recipe_clarification.py"],
                         FROZEN["tests/test_recipe_clarification.py"])


class EvaluatorTests(unittest.TestCase):
    def test_only_a_recorded_server_answer_states_the_assumption(self):
        action = clarification()
        self.assertIsNone(evaluate._stated_assumption(action))
        self.assertIsNone(evaluate._stated_assumption(action, "clarify"))
        self.assertEqual(evaluate._stated_assumption(action, "answer"), ASSUMPTION)
        self.assertIsNone(evaluate._stated_assumption(clarification("center"), "answer"))

    def test_check_action_reads_both_kinds_of_count_basis_row(self):
        text = evaluate._action_text(clarification())
        row = {"validated_action": text, "status": "completed", "runner_error_code": None,
               "evidence": {"stages": {"request_validation": "passed"}}}
        evaluate._check_action({**row, "actual_action": "answer", "clarification_kind": None,
                                "clarification_choice_count": None})
        evaluate._check_action({**row, "actual_action": "clarify", "clarification_kind": "count_basis",
                                "clarification_choice_count": 2})
        for bad in ({"actual_action": "answer", "clarification_kind": "count_basis", "clarification_choice_count": 2},
                    {"actual_action": "clarify", "clarification_kind": None, "clarification_choice_count": None},
                    {"actual_action": "decline", "clarification_kind": None, "clarification_choice_count": None}):
            with self.subTest(**bad), self.assertRaises(p3_assets.P3Error):
                evaluate._check_action({**row, **bad})
        center = evaluate._action_text(clarification("center"))
        with self.assertRaises(p3_assets.P3Error):
            evaluate._check_action({**row, "validated_action": center, "actual_action": "answer",
                                    "clarification_kind": None, "clarification_choice_count": None})


class V19ArchiveTests(EvaluateHarness):
    """v19's archives, made by its frozen runtime, read back, aggregate and gate against v20."""

    def test_the_fixture_is_v19s_registered_runtime(self):
        self.assertEqual(sha256(V19_FIXTURE), registry.load_entry(V19)["runtime_files_sha256"]["grepbit/recipe_model.py"])
        self.assertTrue(v19_runtime()._server_answers(recipe_model.Clarification.from_mapping(
            clarification()["clarification"])))

    @contextmanager
    def as_v19(self):
        entry = registry.load_entry(V19)
        checked = {"candidate_id": V19, "semantic_identity_sha256": entry["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=entry), patch.object(self, "candidate", V19), \
                patch.object(p3_eval, "interpret_recipe_and_execute", v19_runtime().interpret_recipe_and_execute):
            yield

    def client(self):
        cases = self.panel.cases

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            return httpx.Response(200, json=wire_envelope(json.dumps(self.by_oracle[case.oracle_id])))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def observe(self, grant, *, v19=False):
        self.serial_runs = getattr(self, "serial_runs", 0) + 1
        context = self.as_v19() if v19 else contextmanager(lambda: (yield))()
        with context:
            packet = self.prepare(repetition=self.serial_runs)
            output = self.output()
            authorization = self.root / f"authorization-{output.name}.json"
            evaluate.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
            await self.run_mock(packet, output, authorization, client=self.client())
        return evaluate.record(output / "report.json", runs_path=self.runs,
                               now=f"2026-10-01T10:{self.serial_runs:02d}:00Z"), output

    def answered_row(self, output):
        return next(row for row in evaluate.read_report(output / "report.json")["results"]
                    if row["case_id"] == ANSWERED)

    async def test_v19_archives_read_back_aggregate_and_gate_against_v20(self):
        if superseded():
            self.skipTest("v20 superseded; its candidate run would be recorded under another current candidate")
        if v19_drift():
            self.skipTest(f"runtime files differ from v19's registration, so the fixture is not v19: {v19_drift()}")
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        baseline = [await self.observe(2001, v19=True), await self.observe(2002, v19=True)]
        sentinel = await self.observe(2050, v19=True)
        for run, output in (*baseline, sentinel):
            row = self.answered_row(output)
            # The v19 row is the server's answer to the model's own count_basis clarification.
            self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                             ("answer", "missed_clarification", None))
            self.assertEqual(model.strict_json(row["validated_action"])["clarification"]["kind"], "count_basis")
            self.assertEqual((run["candidate_id"], run["correct"]), (V19, len(self.panel.cases) - 1))
        candidate, output = await self.observe(2050)
        row = self.answered_row(output)
        self.assertEqual((row["actual_action"], row["outcome"], row["clarification_kind"]),
                         ("clarify", "correct_clarification", "count_basis"))
        self.assertEqual((candidate["candidate_id"], candidate["correct"]), (V20, len(self.panel.cases)))
        aggregate = evaluate.aggregate("synthetic-dev", "litellm-31b", V19, runs_path=self.runs,
                                       panels_path=self.panels)
        classes = {row["case_id"]: row["class"] for row in aggregate["inputs"]}
        self.assertEqual(classes.pop(ANSWERED), "stable_wrong")
        self.assertEqual(set(classes.values()), {"stable_correct"})
        result = evaluate.gate(V20, V19, "litellm-31b", f"{GRANT}2050", ["synthetic-dev"],
                               runs_path=self.runs, panels_path=self.panels)
        [panel] = result["panels"]
        classes = {row["case_id"]: row["class"] for row in panel["inputs"]}
        self.assertEqual(classes.pop(ANSWERED), "fixed")
        self.assertEqual(set(classes.values()), {"unchanged_correct"})
        self.assertEqual(result["verdict"], "passed")


if __name__ == "__main__":
    unittest.main()
