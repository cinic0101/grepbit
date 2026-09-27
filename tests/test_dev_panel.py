"""Dev-tier coverage panel rulers (#87 step 3): offline, fixture and mock loop only; no model."""
import asyncio
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tools import evaluate as runner, fixture, p3_assets, p3_eval

ROOT = p3_eval.ROOT
PANEL = ROOT / "evals/dev/dev-panel-v1.json"
RESPONSES = ROOT / "evals/dev/dev-responses-v1.json"
ROWS = ("A1", "A2", "A3", "A4", "A5", "A6", "C1", "C2", "C3", "C4",
        "D1", "D2", "D3", "D4", "D6", "D7", "D8", "D9", "D10")


class DevPanelRulers(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def test_panel_covers_every_matrix_row_in_three_languages_with_registered_pins(self):
        panel = p3_assets.load_panel(PANEL)
        self.assertEqual(panel.kind, "development")
        self.assertEqual(len(panel.cases), 57)
        families = {}
        for case in panel.cases:
            families.setdefault(case.family_id, set()).add(case.language)
            self.assertEqual(case.exposure, "design_seen")
            self.assertEqual(case.provenance.origin, "development")
            self.assertTrue(case.provenance.seen_by_implementer)
        self.assertEqual(set(families), {f"dev-{row}" for row in ROWS})
        self.assertTrue(all(langs == {"zh-TW", "en", "ja"} for langs in families.values()))
        # Every clarify question names the center code its choices bind (word-bounded), by contract.
        for case in panel.cases:
            oracle = panel.oracle_for(case)
            if isinstance(oracle, p3_assets.ClarifyOracle):
                for choice in oracle.clarification.choices:
                    value = choice.semantic_value
                    scope = getattr(value, "scope", None) or (getattr(value, "request", None)
                                                              if value.type == "center" else None)
                    if scope is not None:
                        self.assertRegex(case.question, r"(?<![A-Za-z0-9_-])" + re.escape(scope.center_code)
                                         + r"(?![A-Za-z0-9_-])")
        entry = next(row for row in runner.load_panels()["panels"] if row["panel_id"] == "p3-dev-matrix-v1")
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"]), ("dev", "development", None))
        for name, path in (("panel", PANEL), ("cases", panel.cases_path), ("oracles", panel.oracles_path)):
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        # Answer oracles carry kernel-derived values with the fixture facts the reference SQL documents.
        raw = {o["oracle_id"]: o for o in json.loads(panel.oracles_path.read_text())["oracles"]}
        self.assertEqual(raw["dev-A1.v1"]["values"], {"amount": 68000, "bookings": 4, "seats": 6})
        self.assertEqual(raw["dev-A3.v1"]["values"]["growth"], {"numerator": 54, "denominator": 25})
        self.assertEqual(raw["dev-A4.v1"]["values"], {"current": 20000, "baseline": 50000, "delta": -30000,
                                                      "growth": {"numerator": -3, "denominator": 5}})
        self.assertEqual({o["capability_category"] for o in raw.values() if o["branch"] == "decline"},
                         {"D01", "D02", "D03", "D04", "D06"})

    def test_scripted_correct_actions_grade_every_case_correct_through_the_mock_loop(self):
        with tempfile.TemporaryDirectory(prefix="dev-panel-", dir=ROOT / ".artifacts") as tmp:
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            p3_eval.prepare(database, root / "prep", panel_path=PANEL, responses_path=RESPONSES)
            report = asyncio.run(p3_eval.run_panel(database, root / "run", manifest_path=root / "prep" / "manifest.json",
                                                   panel_path=PANEL, responses_path=RESPONSES))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["outcomes"],
                         {"complete_correct": 18, "correct_clarification": 12, "correct_decline": 27})
        self.assertTrue(all(v["family_all_variants_correct"] for v in report["summary"]["per_family"].values()))
        self.assertEqual(len(report["summary"]["per_family"]), 19)


if __name__ == "__main__":
    unittest.main()
