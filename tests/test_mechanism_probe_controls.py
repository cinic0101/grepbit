"""Mechanism-probe control identity and evaluator plumbing, not model obedience."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import evaluate, fixture, p3_assets, p3_eval

ROOT = p3_eval.ROOT
PANEL_ID = "p3-dev-mechanism-probe-v1"
PANEL = ROOT / "evals/dev/mechanism-probe-panel-v1.json"
# v11 runs count cases from cued actions (docs/count-cue-policy.md).
RESPONSES = ROOT / "evals/dev/mechanism-probe-cued-responses-v1.json"
ORDER = ["E02_compare.en", *[f"dev-MC{i}.en" for i in range(1, 6)], "dev-A3.en",
         "dev-BM2.en", "dev-MY1.en", "dev-MY2.en",
         *[f"{family}.{lang}" for family in ("dev-BM6", "dev-MN1", "dev-MN2", "dev-MN3")
           for lang in ("zh-TW", "en", "ja")]]
REUSED = {  # case id -> (source cases, source oracles, oracle id); equal as parsed JSON, not bytes
    "E02_compare.en": ("evals/p3/development-cases-v1.json", "evals/p3/development-oracles-v1.json",
                       "E02_compare.v1"),
    "dev-A3.en": ("evals/dev/dev-cases-v2.json", "evals/dev/dev-oracles-v2.json", "dev-A3.v1"),
    "dev-BM2.en": ("evals/dev/bound-meaning-cases-v1.json", "evals/dev/bound-meaning-oracles-v1.json",
                   "dev-BM2.v1"),
    **{f"dev-BM6.{lang}": ("evals/dev/bound-meaning-cases-v1.json",
                           "evals/dev/bound-meaning-oracles-v1.json", "dev-BM6.v1")
       for lang in ("zh-TW", "en", "ja")},
}


def _rows(path, key):
    return json.loads((ROOT / path).read_text())[key]


class MechanismProbeControlsTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def test_registered_probe_scope_and_exact_reuse(self):
        entries = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL_ID, entries, "Register the semantically accepted probe before observation")
        entry = entries[PANEL_ID]
        panel = p3_assets.load_panel(PANEL)
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"], entry["freeze"]),
                         ("dev", "development", None, None))
        self.assertEqual([c.case_id for c in panel.cases], ORDER)
        self.assertTrue(all(c.exposure == "exposed_regression" and c.provenance.seen_by_implementer
                            and c.must_pass and not c.observational for c in panel.cases))
        for name, path in (("panel", PANEL), ("cases", panel.cases_path), ("oracles", panel.oracles_path)):
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        cases = {c["case_id"]: c for c in json.loads(panel.cases_path.read_text())["cases"]}
        oracles = {o["oracle_id"]: o for o in json.loads(panel.oracles_path.read_text())["oracles"]}
        questions = [{key: cases[case_id][key] for key in ("case_id", "language", "question")}
                     for case_id in ORDER]
        self.assertEqual(hashlib.sha256((json.dumps(questions, ensure_ascii=False, indent=2) + "\n")
                                        .encode()).hexdigest(),
                         "be1a9c8a590bbc5388a548e07b81d233505119973e6f51f7b8cb050182bd8abe")
        for case_id, (case_path, oracle_path, oracle_id) in REUSED.items():
            source = next(c for c in _rows(case_path, "cases") if c["case_id"] == case_id)
            self.assertEqual(cases[case_id], source)
            self.assertEqual(oracles[oracle_id],
                             next(o for o in _rows(oracle_path, "oracles") if o["oracle_id"] == oracle_id))
        meaning = {k: v for k, v in oracles["dev-A3.v1"].items() if k not in ("oracle_id", "provenance")}
        for family in ("dev-MC1", "dev-MC2", "dev-MC3", "dev-MC4", "dev-MC5", "dev-MY1", "dev-MY2"):
            self.assertEqual({k: v for k, v in oracles[f"{family}.v1"].items()
                              if k not in ("oracle_id", "provenance")}, meaning)

    def test_scripted_actions_cover_answers_and_clarifications(self):
        with tempfile.TemporaryDirectory(prefix="mechanism-probe-", dir=ROOT / ".artifacts") as tmp:
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            p3_eval.prepare(database, root / "prep", panel_path=PANEL, responses_path=RESPONSES)
            report = asyncio.run(p3_eval.run_panel(database, root / "run",
                manifest_path=root / "prep/manifest.json", panel_path=PANEL, responses_path=RESPONSES))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["outcomes"],
                         {"complete_correct": 10, "correct_clarification": 12})
        self.assertEqual(len(report["results"]), 22)
        self.assertTrue(all(v["family_all_variants_correct"]
                            for v in report["summary"]["per_family"].values()))


if __name__ == "__main__":
    unittest.main()
