"""Count-assumption evaluation rulers (count-assumption-eval-v1, ADR #136): offline, fixture DB only."""
import asyncio
import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from grepbit import model, recipe_model
from tools import evaluate, fixture, p3_assets, p3_grading

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "evals/dev"
ASSUMPTION = {"count_basis": "booked_seats"}
CHANGED = {"p3-dev-bound-meaning": ("dev-BM6",),
           "p3-dev-mechanism-probe": ("dev-BM6", "dev-MN1", "dev-MN2", "dev-MN3")}
FILES = {"p3-dev-bound-meaning": "bound-meaning", "p3-dev-mechanism-probe": "mechanism-probe"}


def _oracles(name):
    return {oracle["oracle_id"]: oracle for oracle in json.loads((DEV / name).read_text())["oracles"]}


def _bm5():
    return _oracles("bound-meaning-oracles-v1.json")["dev-BM5.v1"]


class OracleFieldTests(unittest.TestCase):
    def test_only_overview_answer_oracles_accept_the_closed_assumption(self):
        oracle = p3_assets.parse_oracle(dict(_bm5(), assumption=ASSUMPTION))
        self.assertEqual(oracle.to_dict()["assumption"], ASSUMPTION)
        self.assertNotIn("assumption", p3_assets.parse_oracle(_bm5()).to_dict())
        compare = _oracles("bound-meaning-oracles-v1.json")["dev-BM2.v1"]
        clarify = _oracles("bound-meaning-oracles-v1.json")["dev-BM7.v1"]
        for bad in (dict(_bm5(), assumption={"count_basis": "distinct_people"}),
                    dict(_bm5(), assumption={"count_basis": "booked_seats", "note": "x"}),
                    dict(_bm5(), assumption="booked_seats"), dict(_bm5(), assumption=None),
                    dict(compare, assumption=ASSUMPTION), dict(clarify, assumption=ASSUMPTION)):
            with self.subTest(bad=bad.get("assumption")), self.assertRaises(p3_assets.P3Error) as refused:
                p3_assets.parse_oracle(bad)
            self.assertEqual(refused.exception.code, "invalid_oracle")


class GradingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="count-assumption-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.database = Path(tmp.name) / "fixture.sqlite"
        fixture.build(self.database)
        action = json.dumps({"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                             "request": _bm5()["request"]})
        self.result = asyncio.run(recipe_model.interpret_recipe_and_execute(
            "BM6-shaped question", self.database, evaluate._replay_client(action, [])))
        self.plain = p3_assets.parse_oracle(_bm5())
        self.assumed = p3_assets.parse_oracle(dict(_bm5(), oracle_id="dev-BM6.v2", revision=2,
                                                   assumption=ASSUMPTION))

    def with_assumption(self, value):
        proposal = self.result.proposal
        fake = SimpleNamespace(recipe_id=proposal.recipe_id, recipe_version=proposal.recipe_version,
                               request=proposal.request, assumption=value,
                               to_dict=lambda: {**proposal.to_dict(), "assumption": value})
        return dataclasses.replace(self.result, proposal=fake)

    def test_without_an_assumption_on_either_side_the_grade_is_unchanged(self):
        graded = p3_grading.grade(self.result, self.plain)
        self.assertEqual((graded["outcome"], graded["layers"]["request"]), ("complete_correct", "passed"))
        self.assertEqual(p3_grading.VERSION, "p3-evaluator-v1")

    def test_a_missing_assumption_is_a_silent_substitution(self):
        graded = p3_grading.grade(self.result, self.assumed)
        self.assertEqual(graded["layers"]["request"], "failed")
        self.assertNotEqual(graded["outcome"], "complete_correct")

    def test_the_assumption_passes_only_where_the_oracle_expects_it(self):
        graded = p3_grading.grade(self.with_assumption(ASSUMPTION), self.assumed)
        self.assertEqual((graded["outcome"], graded["layers"]["request"]), ("complete_correct", "passed"))
        graded = p3_grading.grade(self.with_assumption(ASSUMPTION), self.plain)
        self.assertEqual(graded["layers"]["request"], "failed")
        graded = p3_grading.grade(self.with_assumption({"count_basis": "distinct_people"}), self.assumed)
        self.assertEqual(graded["layers"]["request"], "failed")


class PanelTests(unittest.TestCase):
    def test_the_v2_panels_differ_from_v1_only_where_the_rule_table_says(self):
        registered = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        bm5 = {key: value for key, value in _bm5().items() if key not in ("oracle_id", "revision", "provenance")}
        for stem, families in CHANGED.items():
            with self.subTest(panel=stem):
                old_entry, new_entry = registered[f"{stem}-v1"], registered[f"{stem}-v2"]
                self.assertEqual((new_entry["tier"], new_entry["authoring"], new_entry["allocation_policy"]),
                                 ("dev", "development", None))
                old = p3_assets.load_panel(ROOT / old_entry["path"])
                new = p3_assets.load_panel(ROOT / new_entry["path"])
                for name, path in {"panel": ROOT / new_entry["path"], "cases": new.cases_path,
                                   "oracles": new.oracles_path}.items():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), new_entry["assets"][name])
                self.assertEqual([case.case_id for case in new.cases], [case.case_id for case in old.cases])
                raw_old = {case["case_id"]: case for case in
                           json.loads(old.cases_path.read_text())["cases"]}
                raw_new = {case["case_id"]: case for case in
                           json.loads(new.cases_path.read_text())["cases"]}
                for case in old.cases:
                    before, after = raw_old[case.case_id], raw_new[case.case_id]
                    self.assertEqual(after["question"], before["question"])
                    if case.family_id in families:
                        changed = {key for key in before if before[key] != after[key]}
                        self.assertEqual(changed, {"oracle_id", "expected_branch", "cohort", "semantic_signature"})
                        self.assertEqual((after["oracle_id"], after["expected_branch"], after["cohort"]),
                                         (f"{case.family_id}.v2", "answer", "answer"))
                        oracle = new.oracle_for(new.cases[[c.case_id for c in new.cases].index(case.case_id)])
                        data = oracle.to_dict()
                        self.assertEqual((data["oracle_id"], data["revision"]), (f"{case.family_id}.v2", 2))
                        self.assertEqual({k: v for k, v in data.items()
                                          if k not in ("oracle_id", "revision", "provenance")},
                                         {**bm5, "assumption": ASSUMPTION})
                    else:
                        self.assertEqual(after, before)
                        self.assertEqual(model.canonical_json(new.oracle_for(case).to_dict()),
                                         model.canonical_json(old.oracle_for(case).to_dict()))
                # The v1 identity is untouched: its files still match their registry pins.
                for name, path in {"panel": ROOT / old_entry["path"], "cases": old.cases_path,
                                   "oracles": old.oracles_path}.items():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), old_entry["assets"][name])


if __name__ == "__main__":
    unittest.main()
