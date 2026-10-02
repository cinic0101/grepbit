"""Policy A panel versions (#169 step A2): every Overview answer oracle expects the stated count basis. Offline."""
import hashlib
import json
from pathlib import Path
import unittest

from tools import evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTION = {"count_basis": "booked_seats"}
# New panel version -> predecessor. Cases and oracles are reused; only the panel id and the annex change.
REVISED = {"p3-dev-bound-meaning-v4": "p3-dev-bound-meaning-v3",
           "p3-dev-count-fresh-v3": "p3-dev-count-fresh-v2",
           "p3-dev-matrix-compare-first-v4": "p3-dev-matrix-compare-first-v3"}
# The oracles each revision adds to its predecessor's annex (computed from the policy, pinned here for review).
ADDED = {"p3-dev-bound-meaning-v4": ["dev-BM5.v1"],
         "p3-dev-count-fresh-v3": ["dev-CF06.v1", "dev-CF07.v1", "dev-CF16.v1", "dev-CF17.v1", "dev-CF18.v1"],
         "p3-dev-matrix-compare-first-v4": ["dev-A1.v1", "dev-A2.v1"]}
# Already complete under policy A, so it keeps its version.
UNCHANGED = "p3-dev-mechanism-probe-v2"


def entries():
    return {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}


def overview_answers(entry):
    panel = p3_assets.load_panel(ROOT / entry["path"])
    return sorted(oracle.oracle_id for oracle in panel.oracles
                  if oracle.branch == "answer" and oracle.to_dict().get("recipe_id") == "overview")


def annex(entry):
    return json.loads((ROOT / entry["annex"]["path"]).read_text(encoding="utf-8"))["expectations"]


class PolicyAPanelTests(unittest.TestCase):
    def test_each_revision_is_its_predecessor_with_only_the_panel_id_and_the_annex_changed(self):
        registered = entries()
        for new_id, old_id in REVISED.items():
            with self.subTest(panel=new_id):
                new, old = registered[new_id], registered[old_id]
                self.assertEqual((new["tier"], new["authoring"], new["allocation_policy"], new["intake"], new["freeze"]),
                                 ("dev", "development", None, None, None))
                self.assertEqual({k: v for k, v in new["assets"].items() if k != "panel"},
                                 {k: v for k, v in old["assets"].items() if k != "panel"})
                old_text = (ROOT / old["path"]).read_text(encoding="utf-8")
                self.assertEqual((ROOT / new["path"]).read_text(encoding="utf-8"),
                                 old_text.replace(f'"panel_id": "{old_id}"', f'"panel_id": "{new_id}"', 1))
                for name, relative in (("panel", new["path"]),):
                    self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), new["assets"][name])
                self.assertEqual(new["annex"]["sha256"],
                                 hashlib.sha256((ROOT / new["annex"]["path"]).read_bytes()).hexdigest())

    def test_every_overview_answer_oracle_expects_the_stated_basis_and_nothing_else_changes(self):
        registered = entries()
        for new_id, old_id in REVISED.items():
            with self.subTest(panel=new_id):
                new, old = registered[new_id], registered[old_id]
                expected = {oracle_id: ASSUMPTION for oracle_id in overview_answers(new)}
                self.assertEqual(annex(new), expected)
                self.assertEqual(sorted(set(annex(new)) - set(annex(old))), ADDED[new_id])
                self.assertEqual({k: v for k, v in annex(new).items() if k in annex(old)}, annex(old))
                panel = p3_assets.load_panel(ROOT / new["path"])
                self.assertEqual(evaluate.annex_expectations(new, panel), expected)
        unchanged = registered[UNCHANGED]
        self.assertEqual(annex(unchanged), {oracle_id: ASSUMPTION for oracle_id in overview_answers(unchanged)})


if __name__ == "__main__":
    unittest.main()
