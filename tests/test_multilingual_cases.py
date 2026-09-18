"""Paired-input asset checks, not translation validation or model evaluation."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "evals/cases"


class MultilingualCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_bytes = (CASE_DIR / "learningops.json").read_bytes()
        cls.base = json.loads(cls.base_bytes)
        cls.cases = {c["id"]: c for c in cls.base["cases"]}
        cls.languages = json.loads((CASE_DIR / "learningops-languages.json").read_text(encoding="utf-8"))
        cls.variants = cls.languages["variants"]
        cls.sheet = (CASE_DIR / "learningops-language-review.md").read_text(encoding="utf-8")

    def test_supplement_is_pinned_to_base_catalog(self):
        self.assertEqual(self.languages["base_catalog"], "learningops.json")
        self.assertEqual(self.languages["base_catalog_sha256"], hashlib.sha256(self.base_bytes).hexdigest())

    def test_exact_one_variant_record_per_semantic_family(self):
        ids = [v["case_id"] for v in self.variants]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(self.cases))
        refs = json.loads((ROOT / "evals/oracles/learningops.json").read_text(encoding="utf-8"))
        self.assertEqual({c["reference_id"] for c in self.cases.values() if "reference_id" in c},
                         {r["id"] for r in refs})

    def test_all_three_inputs_are_present_without_variant_specific_gold(self):
        self.assertEqual(self.languages["source_language"], "zh-TW")
        self.assertEqual(self.languages["comparison_languages"], ["zh-TW", "en", "ja"])
        for v in self.variants:
            with self.subTest(case=v["case_id"]):
                self.assertEqual(set(v), {"case_id", "input_kind", "en", "ja"})
                for text in (self.cases[v["case_id"]]["question"], v["en"], v["ja"]):
                    self.assertIsInstance(text, str)
                    self.assertTrue(text.strip())
                    self.assertEqual(text, text.strip())
                    self.assertNotIn("\ufffd", text)

    def test_stable_entity_literals_are_not_localized(self):
        pattern = re.compile(r"CTR-[A-Z][0-9]{2}|S[0-9]{2}|星河中心")
        for v in self.variants:
            expected = set(pattern.findall(self.cases[v["case_id"]]["question"]))
            for language in ("en", "ja"):
                with self.subTest(case=v["case_id"], language=language):
                    self.assertEqual(set(pattern.findall(v[language])), expected)

    def test_explicit_years_are_preserved_and_not_added(self):
        # Surface guard only: this cannot prove time-boundary semantics.
        pattern = re.compile(r"(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])")
        for v in self.variants:
            expected = set(pattern.findall(self.cases[v["case_id"]]["question"]))
            for language in ("en", "ja"):
                with self.subTest(case=v["case_id"], language=language):
                    self.assertEqual(set(pattern.findall(v[language])), expected)

    def test_operational_scenario_is_not_a_user_question(self):
        for v in self.variants:
            expected = "scenario_description" if self.cases[v["case_id"]]["layer"] == "operational_control" else "question"
            self.assertEqual(v["input_kind"], expected)
        self.assertEqual([v["case_id"] for v in self.variants if v["input_kind"] == "scenario_description"],
                         ["E10_budget_partial"])

    def test_review_sheet_matches_inputs_and_does_not_claim_reviewed(self):
        self.assertEqual(self.languages["review_status"], "revised_pending_local_recheck")
        for v in self.variants:
            values = [self.cases[v["case_id"]]["question"], v["en"], v["ja"]]
            row = f'| `{v["case_id"]}` / {v["input_kind"]} | ' + " | ".join(values) + " |"
            self.assertIn(row, self.sheet)


if __name__ == "__main__":
    unittest.main()
