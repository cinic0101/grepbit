"""An empty annex and the compare-first v3 panel (docs/count-assumption.md, ADR #146): offline only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
V2, V3 = "p3-dev-matrix-compare-first-v2", "p3-dev-matrix-compare-first-v3"
ASSUMPTION = {"count_basis": "booked_seats"}


def entry(panel_id):
    return next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)


class EmptyAnnexTests(unittest.TestCase):
    def test_an_empty_annex_is_admitted_and_malformed_ones_are_not(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".artifacts") as tmp:
            def read(document):
                path = Path(tmp) / f"annex-{hashlib.sha256(json.dumps(document).encode()).hexdigest()[:8]}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                return evaluate._read_annex(path)

            self.assertEqual(read({"version": evaluate.ANNEX_VERSION, "expectations": {}}), {})
            for bad in ({"version": evaluate.ANNEX_VERSION}, {"version": "other", "expectations": {}},
                        {"version": evaluate.ANNEX_VERSION, "expectations": []},
                        {"version": evaluate.ANNEX_VERSION, "expectations": {"x": {"count_basis": "distinct_people"}}},
                        {"version": evaluate.ANNEX_VERSION, "expectations": {}, "note": "x"}):
                with self.subTest(bad=bad), self.assertRaises(p3_assets.P3Error):
                    read(bad)

    def test_under_an_empty_annex_every_stated_assumption_is_wrong(self):
        for action, verdict in (({"outcome": "request", "recipe_id": "overview", "count_request": "none"}, "correct"),
                                ({"outcome": "request", "recipe_id": "overview", "count_request": "unresolved"}, "wrong"),
                                ({"outcome": "request", "recipe_id": "overview", "assumption": ASSUMPTION}, "wrong"),
                                ({"outcome": "declined"}, "correct")):
            row = {"oracle_id": "dev-A2.v1", "validated_action": json.dumps(action)}
            with self.subTest(action=action):
                self.assertEqual(evaluate.annexed(row, True, {}), verdict)
        self.assertEqual(evaluate.annexed({"oracle_id": "dev-A2.v1", "validated_action": None}, True, {}), "unassessed")


class CompareFirstV3PanelTests(unittest.TestCase):
    def test_v3_is_v2_with_an_empty_annex(self):
        old, new = entry(V2), entry(V3)
        self.assertEqual((new["tier"], new["authoring"], new["allocation_policy"], new["intake"], new["freeze"]),
                         ("dev", "development", None, None, None))
        self.assertEqual((new["assets"]["cases"], new["assets"]["oracles"]),
                         (old["assets"]["cases"], old["assets"]["oracles"]))
        self.assertNotIn("annex", old)
        v2_panel = json.loads((ROOT / old["path"]).read_text(encoding="utf-8"))
        v3_panel = json.loads((ROOT / new["path"]).read_text(encoding="utf-8"))
        self.assertEqual(v3_panel, {**v2_panel, "panel_id": V3})
        panel = p3_assets.load_panel(ROOT / new["path"])
        self.assertEqual(panel.panel_id, V3)
        self.assertEqual(evaluate.annex_expectations(new, panel), {})
        annex = ROOT / new["annex"]["path"]
        self.assertEqual(json.loads(annex.read_text(encoding="utf-8")),
                         {"version": evaluate.ANNEX_VERSION, "expectations": {}})
        self.assertEqual(hashlib.sha256(annex.read_bytes()).hexdigest(), new["annex"]["sha256"])


if __name__ == "__main__":
    unittest.main()
