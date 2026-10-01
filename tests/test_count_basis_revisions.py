"""ADR #158 panel revisions (docs/count-assumption.md): bound-meaning v3 and count-fresh v2; offline only."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import evaluate, fixture, p3_assets, p3_eval

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "evals/dev"
ASSUMPTION = {"count_basis": "booked_seats"}
DROP = ("oracle_id", "revision", "provenance")
# (old panel, new panel, file stem, old/new file versions, revised family -> source oracle, old/new responses)
REVISIONS = {
    "bound-meaning": ("p3-dev-bound-meaning-v2", "p3-dev-bound-meaning-v3", "bound-meaning", ("v2", "v3"),
                      {"dev-BM7": "dev-BM6.v2"}, ("v1", "v2")),
    "count-fresh": ("p3-dev-count-fresh-v1", "p3-dev-count-fresh-v2", "count-fresh", ("v1", "v2"),
                    {"dev-CF11": "dev-CF05.v1", "dev-CF12": "dev-CF04.v1"}, ("v1", "v2")),
}
# Families whose scripted correct action becomes a generic count reading, with the oracle whose scope it reads.
# bound-meaning-read-responses-v1 encodes the v1 panel's actions, including dev-BM6.v1's clarification, although
# dev-BM6.v2 has been an answer since ADR #136.
SCRIPTED = {"bound-meaning": {"dev-BM6": "dev-BM6.v2", "dev-BM7": "dev-BM6.v2"},
            "count-fresh": {"dev-CF11": "dev-CF05.v1", "dev-CF12": "dev-CF04.v1"}}


def entry(panel_id):
    return next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)


def load(name):
    return json.loads((DEV / name).read_text(encoding="utf-8"))


class RevisionTests(unittest.TestCase):
    def test_each_new_panel_is_its_predecessor_with_only_the_named_families_revised(self):
        for key, (old_id, new_id, stem, (old, new), revised, (old_r, new_r)) in REVISIONS.items():
            with self.subTest(panel=key):
                before, after = entry(old_id), entry(new_id)
                self.assertEqual((after["tier"], after["authoring"], after["allocation_policy"], after["intake"],
                                  after["freeze"]), ("dev", "development", None, None, None))
                panel_text = (ROOT / before["path"]).read_text(encoding="utf-8")
                self.assertEqual((ROOT / after["path"]).read_text(encoding="utf-8"), panel_text
                                 .replace(f'"panel_id": "{old_id}"', f'"panel_id": "{new_id}"', 1)
                                 .replace(f'"cases": "{stem}-cases-{old}.json"', f'"cases": "{stem}-cases-{new}.json"', 1)
                                 .replace(f'"oracles": "{stem}-oracles-{old}.json"',
                                          f'"oracles": "{stem}-oracles-{new}.json"', 1))
                for name, relative in (("panel", after["path"]), ("cases", f"evals/dev/{stem}-cases-{new}.json"),
                                       ("oracles", f"evals/dev/{stem}-oracles-{new}.json")):
                    self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), after["assets"][name])
                self.assertEqual(after["annex"]["sha256"],
                                 hashlib.sha256((ROOT / after["annex"]["path"]).read_bytes()).hexdigest())
                # Cases: only the revised families change their branch, oracle and signature. The fresh panel
                # counts as exposed after its v18 run (docs/count-fresh-ablation-result.md), so all its cases do.
                old_cases = {c["case_id"]: c for c in load(f"{stem}-cases-{old}.json")["cases"]}
                new_cases = {c["case_id"]: c for c in load(f"{stem}-cases-{new}.json")["cases"]}
                self.assertEqual(list(old_cases), list(new_cases))
                exposure = {"exposure", "provenance"} if key == "count-fresh" else set()
                for case_id, case in new_cases.items():
                    prior = old_cases[case_id]
                    changed = {field for field in case if case[field] != prior[field]}
                    if case["family_id"] in revised:
                        self.assertEqual(changed, {"oracle_id", "expected_branch", "cohort", "semantic_signature"}
                                         | exposure, case_id)
                        self.assertEqual((case["oracle_id"], case["expected_branch"], case["cohort"], case["question"]),
                                         (f"{case['family_id']}.v2", "answer", "answer", prior["question"]))
                    else:
                        self.assertEqual(changed, exposure, case_id)
                    if key == "count-fresh":
                        self.assertEqual((case["exposure"], case["provenance"]["exposure_history"]),
                                         ("exposed_regression", ["design_seen", "exposed_regression"]))
                        self.assertEqual({k: v for k, v in case["provenance"].items() if k != "exposure_history"},
                                         {k: v for k, v in prior["provenance"].items() if k != "exposure_history"})
                # Oracles: each revised clarify oracle becomes the named Overview answer, otherwise identical.
                old_oracles = load(f"{stem}-oracles-{old}.json")["oracles"]
                new_oracles = load(f"{stem}-oracles-{new}.json")["oracles"]
                by_old = {o["oracle_id"]: o for o in old_oracles}
                renamed = {f"{family}.v1": f"{family}.v2" for family in revised}
                self.assertEqual([o["oracle_id"] for o in new_oracles],
                                 [renamed.get(o["oracle_id"], o["oracle_id"]) for o in old_oracles])
                for oracle in new_oracles:
                    family = oracle["oracle_id"].rsplit(".", 1)[0]
                    if family in revised:
                        self.assertEqual(by_old[f"{family}.v1"]["branch"], "clarify")
                        self.assertEqual(by_old[f"{family}.v1"]["clarification"]["kind"], "count_basis")
                        source = by_old[revised[family]]
                        # The named source answers exactly the scope the old clarification's choices bound.
                        self.assertEqual({json.dumps(c["semantic_value"]["scope"], sort_keys=True) for c in
                                          by_old[f"{family}.v1"]["clarification"]["choices"]},
                                         {json.dumps(source["request"], sort_keys=True)})
                        self.assertEqual({k: v for k, v in oracle.items() if k not in DROP},
                                         {k: v for k, v in source.items() if k not in DROP})
                        self.assertEqual((oracle["revision"], list(oracle)), (2, list(source)))
                        self.assertIn("ADR #158", oracle["provenance"][0])
                    else:
                        self.assertEqual(oracle, by_old[oracle["oracle_id"]])
                # The annex adds exactly the revised oracles.
                old_annex = load(f"{stem}-annex-{old}.json")["expectations"]
                new_annex = load(f"{stem}-annex-{new}.json")["expectations"]
                self.assertEqual(new_annex, {**old_annex, **{f"{family}.v2": ASSUMPTION for family in revised}})
                panel = p3_assets.load_panel(ROOT / after["path"])
                self.assertEqual(evaluate.annex_expectations(after, panel), new_annex)
                # Scripted correct actions: the revised families read a generic count; nothing else changes.
                old_actions = {r["case_id"]: r["action"] for r in load(f"{stem}-read-responses-{old_r}.json")["responses"]}
                new_actions = {r["case_id"]: r["action"] for r in load(f"{stem}-read-responses-{new_r}.json")["responses"]}
                self.assertEqual(list(old_actions), list(new_actions))
                for case_id, action in new_actions.items():
                    family = case_id.split(".")[0]
                    if family in SCRIPTED[key]:
                        self.assertEqual(action, {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                                                  "request": by_old[SCRIPTED[key][family]]["request"],
                                                  "count_request": "unresolved"})
                    else:
                        self.assertEqual(action, old_actions[case_id])

    def test_scripted_correct_actions_grade_correct_and_state_exactly_the_annexed_assumption(self):
        for key, (_, new_id, stem, _, _, (_, new_r)) in REVISIONS.items():
            with self.subTest(panel=key):
                after = entry(new_id)
                panel_path = ROOT / after["path"]
                responses_path = DEV / f"{stem}-read-responses-{new_r}.json"
                panel = p3_assets.load_panel(panel_path)
                expectations = evaluate.annex_expectations(after, panel)
                oracle_of = {case.case_id: case.oracle_id for case in panel.cases}
                for row in load(responses_path.name)["responses"]:
                    self.assertEqual(evaluate._stated_assumption(row["action"]),
                                     expectations.get(oracle_of[row["case_id"]]), row["case_id"])
                with tempfile.TemporaryDirectory(prefix="count-basis-", dir=ROOT / ".artifacts") as tmp:
                    root = Path(tmp)
                    database = root / "fixture.sqlite"
                    fixture.build(database)
                    p3_eval.prepare(database, root / "prep", panel_path=panel_path, responses_path=responses_path)
                    report = asyncio.run(p3_eval.run_panel(database, root / "run",
                                                           manifest_path=root / "prep" / "manifest.json",
                                                           panel_path=panel_path, responses_path=responses_path))
                self.assertEqual(report["status"], "complete")
                outcomes = report["summary"]["outcomes"]
                self.assertEqual(sum(outcomes.values()), len(panel.cases))
                self.assertEqual(set(outcomes) - {"complete_correct", "correct_clarification", "correct_decline"},
                                 set())
                self.assertNotIn("count_basis", {oracle.to_dict().get("clarification", {}).get("kind")
                                                 for oracle in panel.oracles})


if __name__ == "__main__":
    unittest.main()
