"""Small P0 review regressions; no NLP verifier or product capability is added."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import unittest

from tools import fixture

ROOT = Path(__file__).resolve().parents[1]

# Deliberately narrow surface guards, not a general multilingual parser.
# Changing these review assets legitimately requires reviewing these terms too.
PROTECTED = {
    "Q06_cash_received": {
        "zh-TW": ("2026年3月入帳", "成功收款", "不依報名狀態排除"),
        "en": ("successful payments posted in March 2026", "without excluding any based on booking status"),
        "ja": ("2026年3月に計上", "支払ステータスが「成功」", "申込の状態による除外をせず"),
    },
    "Q07_posted_refunds": {
        "zh-TW": ("2026年3月成功入帳",),
        "en": ("successful refunds posted in March 2026",),
        "ja": ("2026年3月に計上", "返金ステータスが「成功」"),
    },
    "Q08_cohort_refunds": {
        "zh-TW": ("截至2026年4月1日零時",),
        "en": ("as of midnight at the start of April 1, 2026",),
        "ja": ("2026年4月1日午前0時時点",),
    },
    "Q16_cohort_net_amount": {
        "zh-TW": ("截至2026年4月1日零時",),
        "en": ("as of midnight at the start of April 1, 2026",),
        "ja": ("2026年4月1日午前0時時点",),
    },
    "Q13_top_courses": {
        "zh-TW": ("前三個課程", "課程ID升冪"),
        "en": ("Which three courses", "course ID in ascending order"),
        "ja": ("上位3件", "講座IDの昇順"),
    },
    "E03_share_denominator": {
        "zh-TW": ("前兩名課程", "全部金額"),
        "en": ("top two courses", "share of the total booking amount"),
        "ja": ("上位2講座", "全体の申込金額"),
    },
    "E09_unit_conversion": {
        "zh-TW": ("S01場次", "幾小時"),
        "en": ("session S01", "in hours"),
        "ja": ("開催回S01", "所要時間", "何時間"),
    },
}


def question_map():
    base = fixture.load(fixture.CASES)
    supplement = fixture.load(ROOT / "evals/cases/learningops-languages.json")
    questions = {case["id"]: {"zh-TW": case["question"]} for case in base["cases"]}
    for variant in supplement["variants"]:
        questions[variant["case_id"]].update({lang: variant[lang] for lang in ("en", "ja")})
    return questions


class ReviewWordingTests(unittest.TestCase):
    def assert_protected(self, questions):
        for case, languages in PROTECTED.items():
            for lang, terms in languages.items():
                for term in terms:
                    self.assertIn(term, questions[case][lang], f"{case}/{lang}: {term}")

    def test_selected_cutoffs_top_k_posting_and_session_terms(self):
        self.assert_protected(question_map())

    def test_guards_reject_date_and_top_k_drifts_without_using_sheet(self):
        # A coordinated change to the sheet cannot rescue these question mutations.
        changes = (
            ("Q08_cohort_refunds", "zh-TW", "4月1日", "4月2日"),
            ("Q08_cohort_refunds", "en", "April 1, 2026", "April 2, 2026"),
            ("Q08_cohort_refunds", "ja", "4月1日", "4月2日"),
            ("Q16_cohort_net_amount", "en", "midnight", "noon"),
            ("Q13_top_courses", "zh-TW", "前三個", "前四個"),
            ("Q13_top_courses", "en", "three courses", "four courses"),
            ("Q13_top_courses", "ja", "上位3件", "上位4件"),
            ("E03_share_denominator", "en", "top two", "top three"),
        )
        original = question_map()
        for case, lang, before, after in changes:
            with self.subTest(case=case, language=lang, after=after):
                mutant = deepcopy(original)
                self.assertIn(before, mutant[case][lang])
                mutant[case][lang] = mutant[case][lang].replace(before, after)
                with self.assertRaises(AssertionError):
                    self.assert_protected(mutant)

    def test_guards_reject_processing_completion_as_posting(self):
        original = question_map()
        for case in ("Q06_cash_received", "Q07_posted_refunds"):
            with self.subTest(case=case):
                mutant = deepcopy(original)
                mutant[case]["ja"] = mutant[case]["ja"].replace("計上された", "処理が完了した")
                with self.assertRaises(AssertionError):
                    self.assert_protected(mutant)


class RankingWitnessTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        fixture.populate(self.conn)
        self.ref = next(r for r in fixture.load(fixture.ORACLES) if r["id"] == "Q13_top_courses")
        self.conn.execute("INSERT INTO bookings VALUES ('BX_RANK','CC','L6',"
                          "'2026-03-21T04:00:00Z','confirmed','TWD')")
        self.conn.execute("INSERT INTO booking_items VALUES "
                          "('IX_RANK','BX_RANK','S11','CC',1,30000,0)")
        # K1=68000, K3=60000, K2=30000, K4=30000. K2 wins the cutoff tie.
        self.expected = [["K1", 68000], ["K3", 60000], ["K2", 30000]]

    def query(self, sql):
        return [list(row) for row in self.conn.execute(sql, self.ref["params"])]

    def test_fourth_course_cutoff_tie_and_source_isolation(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.query(self.ref["sql"]), self.expected)
        with closing(sqlite3.connect(":memory:")) as clean:
            fixture.populate(clean)
            self.assertEqual(clean.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], 13)
            self.assertEqual([list(row) for row in clean.execute(self.ref["sql"], self.ref["params"])],
                             self.ref["expected"])

    def test_missing_limit_and_limit_four_are_distinguished(self):
        self.assertEqual(self.ref["sql"].count("LIMIT 3"), 1)
        for replacement in ("", "LIMIT 4"):
            with self.subTest(replacement=replacement):
                rows = self.query(self.ref["sql"].replace("LIMIT 3", replacement))
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[-1], ["K4", 30000])
                self.assertNotEqual(rows, self.expected)

    def test_descending_tie_break_changes_cutoff_member(self):
        self.assertEqual(self.ref["sql"].count("s.course_id LIMIT 3"), 1)
        rows = self.query(self.ref["sql"].replace("s.course_id LIMIT 3", "s.course_id DESC LIMIT 3"))
        self.assertEqual(rows, [["K1", 68000], ["K3", 60000], ["K4", 30000]])
        self.assertNotEqual(rows, self.expected)


if __name__ == "__main__":
    unittest.main()
