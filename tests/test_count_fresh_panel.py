"""Fresh count panel rulers (docs/count-fresh-panel.md, #152): offline, fixture and mock loop only; no model."""
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tools import evaluate as runner, fixture, p3_assets, p3_eval

ROOT = p3_eval.ROOT
DEV = ROOT / "evals/dev"
PANEL_ID = "p3-dev-count-fresh-v1"
AUTHORED = DEV / "count-fresh-authored-v1.json"
FILES = ("count-fresh-cases-v1.json", "count-fresh-oracles-v1.json", "count-fresh-panel-v1.json",
         "count-fresh-annex-v1.json", "count-fresh-read-responses-v1.json")
TYPES = {"F01": "G", "F02": "G", "F03": "G", "F04": "G", "F05": "G", "F06": "S", "F07": "S", "F08": "U",
         "F09": "U", "F10": "U", "F11": "D", "F12": "D", "F13": "B", "F14": "B", "F15": "B", "F16": "O",
         "F17": "O", "F18": "K"}
TUNED = ("p3-dev-bound-meaning-v2", "p3-dev-mechanism-probe-v2", "p3-dev-matrix-compare-first-v3")
ASSUMPTION = {"count_basis": "booked_seats"}


def _entry():
    return next(row for row in runner.load_panels()["panels"] if row["panel_id"] == PANEL_ID)


def _builder():
    return importlib.import_module("tools.build_count_fresh_panel")


class FreshPanelRulers(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def test_the_authored_source_has_every_slot_in_three_languages(self):
        authored = json.loads(AUTHORED.read_text(encoding="utf-8"))
        self.assertEqual(authored["version"], "count-fresh-authored-v1")
        slots = authored["slots"]
        self.assertEqual({slot["slot"]: slot["type"] for slot in slots}, TYPES)
        self.assertEqual([slot["slot"] for slot in slots], list(TYPES))
        for slot in slots:
            with self.subTest(slot=slot["slot"]):
                self.assertIn(slot["center_code"], ("CTR-A01", "CTR-A02", "CTR-B01"))
                self.assertIn(slot["month"], ("2026-02", "2026-03", "2026-04"))
                self.assertEqual(set(slot["questions"]), {"zh-TW", "en", "ja"})
                for question in slot["questions"].values():
                    self.assertRegex(question, r"(?<![A-Za-z0-9_-])" + re.escape(slot["center_code"])
                                     + r"(?![A-Za-z0-9_-])")
                    # Every question states its year: a missing year is D05, which is not scored.
                    self.assertIn("2026", question)

    def test_registered_pins_and_the_builder_reproduces_every_committed_byte(self):
        entry = _entry()
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"], entry["intake"],
                          entry["freeze"]), ("dev", "development", None, None, None))
        panel = p3_assets.load_panel(ROOT / entry["path"])
        for name, path in {"panel": ROOT / entry["path"], "cases": panel.cases_path,
                           "oracles": panel.oracles_path}.items():
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        annex = DEV / "count-fresh-annex-v1.json"
        self.assertEqual(entry["annex"], {"path": "evals/dev/count-fresh-annex-v1.json",
                                          "sha256": hashlib.sha256(annex.read_bytes()).hexdigest()})
        with tempfile.TemporaryDirectory(prefix="count-fresh-", dir=ROOT / ".artifacts") as tmp:
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            _builder().build(root / "out", database)
            for name in FILES:
                with self.subTest(file=name):
                    self.assertEqual((root / "out" / name).read_bytes(), (DEV / name).read_bytes())

    def test_the_oracles_and_annex_follow_the_owners_count_rules(self):
        panel = p3_assets.load_panel(ROOT / _entry()["path"])
        self.assertEqual((panel.panel_id, panel.kind, len(panel.cases), len(panel.oracles)),
                         (PANEL_ID, "development", 54, 18))
        authored = {slot["slot"]: slot for slot in json.loads(AUTHORED.read_text(encoding="utf-8"))["slots"]}
        branches = {"G": "answer", "S": "answer", "U": "decline", "D": "clarify", "B": "answer", "O": "answer",
                    "K": "answer"}
        # The loader canonicalizes request instants, so the scope is read from the committed oracle document.
        raw = {row["oracle_id"]: row for row in json.loads((DEV / "count-fresh-oracles-v1.json").read_text())["oracles"]}
        for case in panel.cases:
            slot = authored[case.family_id[len("dev-C"):]]
            oracle = raw[case.oracle_id]
            with self.subTest(case=case.case_id):
                self.assertEqual(case.question, slot["questions"][case.language])
                self.assertEqual((case.expected_branch, case.cohort, case.exposure),
                                 (branches[slot["type"]], branches[slot["type"]], "design_seen"))
                self.assertEqual(oracle["branch"], case.expected_branch)
                if case.expected_branch == "answer":
                    year, month = (int(part) for part in slot["month"].split("-"))
                    following = f"{year + month // 12}-{month % 12 + 1:02d}"
                    self.assertEqual((oracle["recipe_id"], oracle["request"]), ("overview", {
                        "center_code": slot["center_code"], "start": f"{slot['month']}-01T00:00:00+08:00",
                        "end": f"{following}-01T00:00:00+08:00", "timezone": "Asia/Taipei"}))
        self.assertEqual({key: raw[key]["capability_category"] for key in ("dev-CF08.v1", "dev-CF09.v1", "dev-CF10.v1")},
                         {"dev-CF08.v1": "D06", "dev-CF09.v1": "D04", "dev-CF10.v1": "D06"})
        self.assertEqual([c["semantic_value"]["value"] for c in raw["dev-CF11.v1"]["clarification"]["choices"]],
                         ["booked_seats", "known_booking_accounts"])
        self.assertEqual([c["semantic_value"]["value"] for c in raw["dev-CF12.v1"]["clarification"]["choices"]],
                         ["booked_seats", "distinct_people"])
        annex = json.loads((DEV / "count-fresh-annex-v1.json").read_text())
        self.assertEqual(annex, {"version": "count-assumption-annex-v1", "expectations": {
            f"dev-C{slot}.v1": ASSUMPTION for slot, kind in TYPES.items() if kind in ("G", "B")}})
        self.assertEqual(runner.annex_expectations(_entry(), panel), annex["expectations"])
        # The builder builds an Overview oracle as tools/build_dev_panel.py does: CF01 and CF05 have the scopes of
        # the accepted dev-A1.v1 and dev-A2.v1.
        accepted = {row["oracle_id"]: row for row in json.loads((DEV / "dev-oracles-v3.json").read_text())["oracles"]}
        drop = ("oracle_id", "provenance")
        for fresh, old in (("dev-CF01.v1", "dev-A1.v1"), ("dev-CF05.v1", "dev-A2.v1")):
            self.assertEqual({k: v for k, v in raw[fresh].items() if k not in drop},
                             {k: v for k, v in accepted[old].items() if k not in drop})

    def test_scripted_correct_actions_grade_correct_and_state_exactly_the_annexed_assumption(self):
        entry = _entry()
        panel_path = ROOT / entry["path"]
        responses_path = DEV / "count-fresh-read-responses-v1.json"
        expectations = json.loads((DEV / "count-fresh-annex-v1.json").read_text())["expectations"]
        panel = p3_assets.load_panel(panel_path)
        oracle_of = {case.case_id: case.oracle_id for case in panel.cases}
        # Each type's scripted correct action, so that S (booked_seats) and O/K (none) are told apart.
        readings = {"G": "unresolved", "B": "unresolved", "S": "booked_seats", "O": "none", "K": "none"}
        outcomes = {"D": "clarify", "U": "declined"}
        for row in json.loads(responses_path.read_text())["responses"]:
            kind = TYPES[row["case_id"].split(".")[0][len("dev-C"):]]
            with self.subTest(case=row["case_id"]):
                self.assertEqual(runner._stated_assumption(row["action"]),
                                 expectations.get(oracle_of[row["case_id"]]))
                if kind in readings:
                    self.assertEqual((row["action"]["outcome"], row["action"]["count_request"]),
                                     ("request", readings[kind]))
                else:
                    self.assertEqual(row["action"]["outcome"], outcomes[kind])
        with tempfile.TemporaryDirectory(prefix="count-fresh-", dir=ROOT / ".artifacts") as tmp:
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            p3_eval.prepare(database, root / "prep", panel_path=panel_path, responses_path=responses_path)
            report = asyncio.run(p3_eval.run_panel(database, root / "run", manifest_path=root / "prep" / "manifest.json",
                                                   panel_path=panel_path, responses_path=responses_path))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["outcomes"],
                         {"complete_correct": 39, "correct_clarification": 6, "correct_decline": 9})

    def test_no_question_repeats_a_tuned_panel_question(self):
        fresh = {case.question for case in p3_assets.load_panel(ROOT / _entry()["path"]).cases}
        registered = {row["panel_id"]: row for row in runner.load_panels()["panels"]}
        for panel_id in TUNED:
            tuned = {case.question for case in p3_assets.load_panel(ROOT / registered[panel_id]["path"]).cases}
            self.assertEqual(fresh & tuned, set(), panel_id)


if __name__ == "__main__":
    unittest.main()
