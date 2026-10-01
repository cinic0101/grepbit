"""Development control identity and evaluator plumbing, not model obedience."""
import asyncio
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from tools import evaluate, fixture, p3_assets, p3_eval

ROOT = p3_eval.ROOT
PANEL_ID = "p3-dev-bound-meaning-v1"
PANEL = ROOT / "evals/dev/bound-meaning-panel-v1.json"
# v16 needs typed Compare and count readings; the derived script is tests/oriented_actions.py (ADR #146).
RESPONSES = ROOT / "evals/dev/bound-meaning-read-responses-v1.json"


class BoundMeaningControlsTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def test_registered_control_scope_and_exposed_e02_are_preserved(self):
        entries = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL_ID, entries, "Register the semantically accepted controls before observation")
        entry = entries[PANEL_ID]
        panel = p3_assets.load_panel(PANEL)
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"], entry["freeze"]),
                         ("dev", "development", None, None))
        families = ["E02_compare", *[f"dev-BM{i}" for i in range(2, 9)]]
        self.assertEqual([c.case_id for c in panel.cases],
                         [f"{family}.{lang}" for family in families for lang in ("zh-TW", "en", "ja")])
        self.assertTrue(all(c.exposure == "exposed_regression" and c.provenance.seen_by_implementer
                            and c.must_pass and not c.observational for c in panel.cases))
        old_cases = json.loads((ROOT / "evals/p3/development-cases-v1.json").read_text())["cases"]
        new_cases = json.loads(panel.cases_path.read_text())["cases"]
        questions = [{key: c[key] for key in ("case_id", "language", "question")} for c in new_cases]
        self.assertEqual(hashlib.sha256((json.dumps(questions, ensure_ascii=False, indent=2) + "\n").encode()).hexdigest(),
                         "470ddaf1122d5ce1d60befbeeb771739b642aa69459da9427df0a5a1bae4634e")
        self.assertEqual({c["case_id"]: c for c in new_cases if c["family_id"] == "E02_compare"},
                         {c["case_id"]: c for c in old_cases if c["family_id"] == "E02_compare"})
        old_oracles = json.loads((ROOT / "evals/p3/development-oracles-v1.json").read_text())["oracles"]
        new_oracles = {o["oracle_id"]: o for o in json.loads(panel.oracles_path.read_text())["oracles"]}
        self.assertEqual(new_oracles["E02_compare.v1"],
                         next(o for o in old_oracles if o["oracle_id"] == "E02_compare.v1"))
        for name, path in (("panel", PANEL), ("cases", panel.cases_path), ("oracles", panel.oracles_path)):
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(new_oracles["dev-BM3.v1"]["values"],
                         {"current": 50000, "baseline": 158000, "delta": -108000,
                          "growth": {"numerator": -54, "denominator": 79}})
        self.assertEqual({c["semantic_value"]["value"] for c in
                          new_oracles["dev-BM7.v1"]["clarification"]["choices"]},
                         {"booked_seats", "known_booking_accounts"})
        self.assertEqual({c["semantic_value"]["value"] for c in
                          new_oracles["dev-BM6.v1"]["clarification"]["choices"]},
                         {"booked_seats", "known_booking_accounts", "distinct_people"})

    def test_scripted_actions_match_fixture_values_and_all_branches(self):
        with tempfile.TemporaryDirectory(prefix="bound-controls-", dir=ROOT / ".artifacts") as tmp:
            from pathlib import Path
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            p3_eval.prepare(database, root / "prep", panel_path=PANEL, responses_path=RESPONSES)
            report = asyncio.run(p3_eval.run_panel(database, root / "run",
                manifest_path=root / "prep/manifest.json", panel_path=PANEL, responses_path=RESPONSES))
        self.assertEqual(report["status"], "complete")
        # v19 (ADR #158) answers a scripted count_basis clarification on the server; this panel's oracles predate
        # #158 and still expect the clarification, so those rows grade missed_clarification.
        self.assertEqual(report["summary"]["outcomes"], {"complete_correct": 12, "correct_clarification": 3,
                                                         "missed_clarification": 6, "correct_decline": 3})
        self.assertEqual(len(report["results"]), 24)
        self.assertEqual({k for k, v in report["summary"]["per_family"].items() if not v["family_all_variants_correct"]},
                         {"dev-BM6", "dev-BM7"})
