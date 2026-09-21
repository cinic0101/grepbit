"""Exposed candidate shape/source checks, not family admission or model evidence."""
from collections import Counter, defaultdict
import copy
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from grepbit.compare import CompareRequest
from grepbit.contracts import KernelError
from tools import p3_assets, recipe_smoke


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "evals/p3"
PANEL = ASSETS / "exposed-panel-v1.json"
BASELINE = "20abb5592262c77c98f9cabeaf7cf4854edb6fbe"
REFERENCE = (
    ".artifacts/p33-offline-5r2c8z2c/exposed-reference-qiDblo/reference-results-v1.json"
)
CONTROL_ALLOCATION = {
    "P09_empty_overview.ja": ("ja", "answer"),
    "P10_required_views.en": ("en", "answer"),
    "P11_nonchronological_roles.zh-TW": ("zh-TW", "answer"),
    "P12_ranked_courses.ja": ("ja", "answer"),
    "P15_center.en": ("en", "clarify"),
    "P16_metric_meaning.zh-TW": ("zh-TW", "clarify"),
    "P19_profit.ja": ("ja", "decline"),
    "P20_cash_received.en": ("en", "decline"),
    "P22_center_compare.ja": ("ja", "decline"),
}
SOURCE_SHA256 = {
    "evals/fixtures/learningops/schema.sql": "ffe372eb37db2ad4d2d3b8407e6eb4cc414f3bfc640b34fc5af42c320df395dc",
    "evals/fixtures/learningops/seed.json": "423473d98ed6d2ad4c2ecbb4fc2a57a625d7bc4cc9a5ed681d21cd93126fcc36",
    "evals/cases/learningops.json": "b287a9de51ef65137b36b2c88a0cba5fb309e7e5a2c54e36f91ddaa6d768cddf",
    "evals/cases/learningops-languages.json": "391680665529c67bb264f9e55c0bcd255714d8d1661ef8fe4ac889b86a3aea30",
    "evals/oracles/learningops.json": "a1dce1c22ce41250ce9bd41f70c5ae0d0e182e498ad7e247e2abc3b596f0b50c",
    "evals/panels/p2-recipe-smoke-v1.json": "93d08e2901e58f324db7eded85f578e7b6ac32a5ac4de912194ac07f705f085f",
    "evals/p3/development-panel-v1.json": "c0180d9beac5cf8536e193dc6242068faf046ce50fd7484b07ea77776db07ceb",
    "evals/p3/development-cases-v1.json": "ed249de6d7d2ddbf5635701d0b0794c4626ad790740374df30436783a546b117",
    "evals/p3/development-oracles-v1.json": "1ba9277d4abd0b64c3a302d36fdd3b828dc68bca70cb905a8474a757ae5dd91a",
    "evals/p3/development-responses-v1.json": "9a35ab8abfd4797befe0b96dffa954153c2184a0727a34130be4b87024091aef",
    "tests/test_p3_grading.py": "75363c66df8de98aef2bea6ec5d85099f3c53c21202dd60a5d6eafee9c8dd551",
    "tests/test_overview.py": "3870d5e79e46e4ced15d9f4f19754af9a645927a403f9b02b79b2bc09cfb7bc7",
    "tests/test_compare.py": "89e3454e0545e54e610c8df7583ff61efa4b9cfc36da72508acca387ee1df3f3",
    "tests/test_breakdown.py": "0403b52bce47914de4a52f99d3d4b8bde64485a6ad73b84c658c43d7a474eefb",
    "tests/test_recipe_clarification.py": "42b0ce5ca722422540deb8ef46517da78c8ff558098fc6d81b6948602b3f0c11",
    "tools/p3_assets.py": "c9835a9350479406bd0d21d96ee1a54bf72c6aaf86a905d8837962b35036fced",
    "tools/p3_grading.py": "50a8afec66c4f1d3f85e673f10fe160fd66c35a2b11dc445f258c6ea02f95b94",
    "tools/p3_expectations.py": "f4513b60b91bd62fdca64840d2eaf1259e37a0b6d3b925ebc1493642d7802745",
    "tools/p3_scoring.py": "927dd43968e9afc83c805b15a0935e230b1ff2da0dc12fd6e89b0d7654679d6e",
}


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class P3ExposedTests(unittest.TestCase):
    def setUp(self):
        for target in (
            "socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
            "socket.getaddrinfo", "httpx.AsyncHTTPTransport",
            "grepbit.gateway.GatewayConfig.from_env", "grepbit.gateway.GatewayClient.complete",
            "sqlite3.connect", "grepbit.execute_facts", "grepbit.kernel.execute_facts",
            "grepbit.execute_grouped_amount", "grepbit.grouped.execute_grouped_amount",
            "grepbit.execute_overview", "grepbit.overview.execute_overview",
            "grepbit.execute_compare", "grepbit.compare.execute_compare",
            "grepbit.execute_breakdown", "grepbit.breakdown.execute_breakdown",
            "grepbit.recipe_model.execute_overview", "grepbit.recipe_model.execute_compare",
            "grepbit.recipe_model.execute_breakdown",
            "grepbit.recipe_model.interpret_recipe_and_execute",
            "grepbit.model.interpret_and_execute",
        ):
            guard = patch(target, side_effect=AssertionError("Exposed assets must stay pure and offline"))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)
        self.panel = p3_assets.load_panel(PANEL)
        self.cases = {case.case_id: case for case in self.panel.cases}
        self.oracles = {
            oracle["oracle_id"]: oracle
            for oracle in read_json("evals/p3/exposed-oracles-v1.json")["oracles"]
        }
        self.development = {
            oracle["oracle_id"]: oracle
            for oracle in read_json("evals/p3/development-oracles-v1.json")["oracles"]
        }
        self.references = {
            oracle["id"]: oracle for oracle in read_json("evals/oracles/learningops.json")
        }

    def test_development_shape_counts_are_proposed_labels_not_novelty(self):
        self.assertEqual(
            (self.panel.panel_id, self.panel.kind),
            ("p3-exposed-development-v1", "development"),
        )
        self.assertEqual((len(self.panel.cases), len(self.panel.oracles)), (18, 12))
        self.assertEqual(len({case.family_id for case in self.panel.cases}), 12)
        self.assertEqual(Counter(case.language for case in self.panel.cases),
                         {"zh-TW": 5, "en": 6, "ja": 7})
        self.assertEqual(Counter(case.cohort for case in self.panel.cases),
                         {"anchor": 9, "answer": 4, "clarify": 2, "decline": 3})
        self.assertEqual(Counter(case.expected_branch for case in self.panel.cases),
                         {"answer": 13, "clarify": 2, "decline": 3})
        family_cohorts = {case.family_id: case.cohort for case in self.panel.cases}
        self.assertEqual(Counter(family_cohorts.values()),
                         {"anchor": 3, "answer": 4, "clarify": 2, "decline": 3})
        self.assertEqual(read_json("evals/p3/exposed-cases-v1.json")["version"], "p3-cases-v1")
        self.assertEqual(read_json("evals/p3/exposed-oracles-v1.json")["version"], "p3-oracles-v1")
        self.assertEqual(read_json("evals/p3/exposed-panel-v1.json")["version"], "p3-panel-v1")

    def test_nine_anchor_objects_order_questions_and_gold_are_unchanged(self):
        exposed = read_json("evals/p3/exposed-cases-v1.json")["cases"]
        development = read_json("evals/p3/development-cases-v1.json")["cases"]
        self.assertEqual(exposed[:9], development[:9])
        previous, historical_gold = recipe_smoke.panel_inputs()
        historical_raw = read_json("evals/panels/p2-recipe-smoke-v1.json")["families"]
        for case, historical in zip(self.panel.cases[:9], previous, strict=True):
            with self.subTest(case=case.case_id):
                self.assertEqual((case.family_id, case.language, case.question),
                                 (historical["family"], historical["language"], historical["question"]))
                self.assertEqual(case.case_id, f'{historical["family"]}.{historical["language"]}')
                oracle = self.oracles[case.oracle_id]
                self.assertEqual(oracle, self.development[case.oracle_id])
                parsed = self.panel.oracle_for(case).to_dict()
                for field in ("recipe_id", "recipe_version", "request", "coverage", "values"):
                    self.assertEqual(oracle[field], historical_raw[case.family_id][field])
                    self.assertEqual(parsed[field], historical_gold[case.family_id][field])
        self.assertEqual(
            [case.case_id for case in self.panel.cases[:9]],
            read_json("evals/p3/development-panel-v1.json")["order"][:9],
        )

    def test_exact_exposed_control_allocation_excludes_reservations_and_p21(self):
        self.assertEqual([case.case_id for case in self.panel.cases[9:]], list(CONTROL_ALLOCATION))
        for case in self.panel.cases[9:]:
            with self.subTest(case=case.case_id):
                self.assertEqual((case.language, case.cohort), CONTROL_ALLOCATION[case.case_id])
                self.assertEqual(case.expected_branch, case.cohort)
                self.assertEqual(case.family_id, case.case_id.rsplit(".", 1)[0])
        self.assertEqual(
            {oracle["capability_category"] for oracle in self.oracles.values()
             if oracle["branch"] == "decline"},
            {"D01", "D02", "D06"},
        )

    def test_all_cases_are_exposed_with_source_and_human_review_boundaries(self):
        for case in self.panel.cases:
            with self.subTest(case=case.case_id):
                self.assertEqual(case.exposure, "exposed_regression")
                self.assertEqual(case.provenance.origin, "historical")
                self.assertEqual(case.provenance.exposure_history, ("exposed_regression",))
                self.assertTrue(case.provenance.seen_by_implementer)
                self.assertTrue(case.must_pass)
                self.assertFalse(case.observational)
                self.assertEqual(self.panel.oracle_for(case).branch, case.expected_branch)
                for reference in case.provenance.references:
                    if reference.startswith(("evals/", "tests/", "docs/")):
                        self.assertTrue((ROOT / reference.split("#", 1)[0]).is_file(), reference)
        for case in self.panel.cases[9:]:
            provenance = "\n".join(case.provenance.references)
            self.assertIn(f"docs/p3-evaluation-contract.md#{case.case_id[:3]}", provenance)
            self.assertIn("Provisional allocation only", provenance)
            self.assertIn("independent human family-distinctness", provenance)
            self.assertIn("not owner approval or novelty certification", provenance)

    def test_matching_historical_wording_is_reused_exactly(self):
        languages = {item["case_id"]: item for item in
                     read_json("evals/cases/learningops-languages.json")["variants"]}
        development = {item["case_id"]: item for item in
                       read_json("evals/p3/development-cases-v1.json")["cases"]}
        for case_id, historical_id, language in (
            ("P12_ranked_courses.ja", "Q13_top_courses", "ja"),
            ("P19_profit.ja", "E07_missing_profit", "ja"),
            ("P20_cash_received.en", "Q06_cash_received", "en"),
        ):
            self.assertEqual(self.cases[case_id].question, languages[historical_id][language])
        self.assertEqual(self.cases["P15_center.en"].question,
                         development["C03_center.en"]["question"])
        self.assertEqual(self.cases["P20_cash_received.en"].question,
                         development["D02_cash_received.en"]["question"])
        self.assertEqual(self.cases["P09_empty_overview.ja"].question,
                         languages["E01_overview"]["ja"].replace("2026", "2030"))

    def test_accepted_source_identities_and_frozen_evaluator_files_are_pinned(self):
        for source, expected in SOURCE_SHA256.items():
            with self.subTest(source=source, accepted_baseline=BASELINE):
                self.assertEqual(hashlib.sha256((ROOT / source).read_bytes()).hexdigest(), expected)

    def test_empty_overview_descends_from_corrected_unit_v2_not_null_count(self):
        oracle = self.oracles["P09_empty_overview.v1"]
        expected = copy.deepcopy(self.development["E01_overview.v1"])
        for field in ("oracle_id", "revision", "provenance"):
            expected[field] = oracle[field]
        expected["request"].update(start="2030-03-01T00:00:00+08:00",
                                   end="2030-04-01T00:00:00+08:00")
        expected["values"] = {"amount": None, "bookings": 0, "seats": None}
        expected["auxiliary_values"] = {"daily_amount": [], "category_amounts": []}
        self.assertEqual(oracle, expected)
        self.assertIs(type(oracle["values"]["bookings"]), int)
        self.assertEqual(set(oracle["slot_states"].values()), {"checked"})
        self.assertIn("unit-empty-overview-v2, revision 2", "\n".join(oracle["provenance"]))

    def test_required_views_change_only_user_obligations_not_native_coverage(self):
        oracle = self.oracles["P10_required_views.v1"]
        expected = copy.deepcopy(self.development["E01_overview.v1"])
        for field in ("oracle_id", "revision", "provenance"):
            expected[field] = oracle[field]
        expected["required_slots"] = ["amount", "bookings", "seats", "daily_amount", "category_amounts"]
        expected["auxiliary_slots"] = []
        self.assertEqual(oracle, expected)
        for role in ("daily_amount", "category_amounts"):
            self.assertEqual(oracle["coverage"]["slots"][role], "optional")
            self.assertIn(role, oracle["required_slots"])

    def test_overview_gold_matches_independent_fixed_seed_ledger(self):
        seed = read_json("evals/fixtures/learningops/seed.json")
        sessions = {row[0]: row[1] for row in seed["sessions"]}
        categories = {row[0]: row[3] for row in seed["courses"]}
        for name, start, end in (
            ("P09_empty_overview.v1", "2030-02-28T16:00:00Z", "2030-03-31T16:00:00Z"),
            ("P10_required_views.v1", "2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z"),
        ):
            with self.subTest(oracle=name):
                bookings = {row[0]: row for row in seed["bookings"]
                            if row[1] == "CA" and row[4] == "confirmed" and start <= row[3] < end}
                items = [row for row in seed["booking_items"] if row[1] in bookings]
                self.assertEqual(self.oracles[name]["values"], {
                    "amount": sum(row[4] * row[5] - row[6] for row in items) if items else None,
                    "bookings": len(bookings),
                    "seats": sum(row[4] for row in items) if items else None,
                })
                daily, category = defaultdict(int), defaultdict(int)
                for row in items:
                    amount = row[4] * row[5] - row[6]
                    day = (datetime.fromisoformat(bookings[row[1]][3]) + timedelta(hours=8)).date()
                    daily[day.isoformat()] += amount
                    category[categories[sessions[row[2]]]] += amount
                for role, groups in (("daily_amount", daily), ("category_amounts", category)):
                    self.assertEqual(self.oracles[name]["auxiliary_values"][role],
                                     [{"key": key, "value": value} for key, value in sorted(groups.items())])

    def test_nonchronological_roles_reuse_accepted_orientation_and_p0_arithmetic(self):
        oracle = self.oracles["P11_nonchronological_roles.v1"]
        original = self.development["E02_compare.v1"]
        self.assertEqual(oracle["request"], {
            "current": original["request"]["baseline"], "baseline": original["request"]["current"],
        })
        admitted = self.development["C02_comparison_roles.v1"]["clarification"]["choices"]
        self.assertIn(oracle["request"], [choice["semantic_value"]["request"] for choice in admitted])
        current = self.references["Q09_previous_amount"]["expected"][0][0]
        baseline = self.references["Q01_booked_amount"]["expected"][0][0]
        growth = Fraction(current - baseline, baseline)
        self.assertEqual(oracle["values"], {
            "current": current, "baseline": baseline, "delta": current - baseline,
            "growth": {"numerator": growth.numerator, "denominator": growth.denominator},
        })
        for field in ("coverage", "required_slots", "auxiliary_slots", "auxiliary_values",
                      "slot_states", "units", "catalog_sha256"):
            self.assertEqual(oracle[field], original[field])

    def test_historical_rank_gold_has_no_invented_share_obligation_or_tie_witness(self):
        oracle = self.oracles["P12_ranked_courses.v1"]
        rows = self.references["Q13_top_courses"]["expected"]
        whole = self.references["Q01_booked_amount"]["expected"][0][0]
        subtotal = sum(value for _, value in rows)
        share = Fraction(subtotal, whole)
        self.assertEqual(oracle["values"], {
            "rows": [{"key": key, "value": value} for key, value in rows],
            "all_amount": whole, "top_subtotal": subtotal,
            "share": {"numerator": share.numerator, "denominator": share.denominator},
        })
        self.assertEqual(oracle["request"]["top_k"], 3)
        self.assertEqual(oracle["coverage"]["group"],
                         {"dimension": "course", "coverage": "top_k", "top_k": 3})
        self.assertEqual(oracle["required_slots"], ["top_courses"])
        self.assertEqual(oracle["auxiliary_slots"], ["all_amount", "top_subtotal", "share"])
        self.assertEqual(set(oracle["coverage"]["slots"].values()), {"required"})
        self.assertEqual([key for key, _ in rows], ["K1", "K3", "K2"])
        self.assertEqual(len({value for _, value in rows}), len(rows))
        provenance = "\n".join(oracle["provenance"])
        self.assertIn("does not exercise a tied cutoff", provenance)
        self.assertIn("Tie-cutoff demonstration is blocked",
                      "\n".join(self.cases["P12_ranked_courses.ja"].provenance.references))
        for field in ("slot_states", "units", "catalog_sha256"):
            self.assertEqual(oracle[field], self.development["E03_share_denominator.v1"][field])

    def test_supplied_center_and_metric_choices_keep_existing_oracles_exactly(self):
        for case_id, oracle_id, kind in (
            ("P15_center.en", "C03_center.v1", "center"),
            ("P16_metric_meaning.zh-TW", "C04_metric_meaning.v1", "metric_meaning"),
        ):
            case = self.cases[case_id]
            self.assertEqual(case.oracle_id, oracle_id)
            self.assertEqual(self.oracles[oracle_id], self.development[oracle_id])
            oracle = self.panel.oracle_for(case)
            self.assertIsInstance(oracle, p3_assets.ClarifyOracle)
            self.assertEqual(oracle.clarification.kind, kind)
            oracle.clarification.validate_question(case.question)
        choices = self.oracles["C04_metric_meaning.v1"]["clarification"]["choices"]
        self.assertEqual({choice["semantic_value"]["value"] for choice in choices},
                         {"confirmed_booked_amount", "cash_received"})

    def test_decline_gold_reuses_d01_d02_and_accepted_center_filter_rejection(self):
        for oracle_id in ("D01_profit.v1", "D02_cash_received.v1"):
            self.assertEqual(self.oracles[oracle_id], self.development[oracle_id])
        oracle = self.oracles["P22_center_compare.v1"]
        self.assertEqual((oracle["branch"], oracle["capability_category"], oracle["designated_control"]),
                         ("decline", "D06", True))
        original = self.development["E02_compare.v1"]["request"]
        CompareRequest.from_mapping(original)
        for role in ("current", "baseline"):
            for center in ("CA", "CTR-A01"):
                request = copy.deepcopy(original)
                request[role]["center_id"] = center
                with self.subTest(role=role, center=center):
                    with self.assertRaises(KernelError) as raised:
                        CompareRequest.from_mapping(request)
                    self.assertEqual(raised.exception.code, "invalid_request")

    def test_new_gold_records_reference_sources_and_unresolved_admission(self):
        for oracle_id in (
            "P09_empty_overview.v1", "P10_required_views.v1",
            "P11_nonchronological_roles.v1", "P12_ranked_courses.v1",
        ):
            provenance = "\n".join(self.oracles[oracle_id]["provenance"])
            self.assertIn(BASELINE, provenance)
            self.assertIn(REFERENCE, provenance)
            self.assertIn("evals/oracles/learningops.json", provenance)
            self.assertIn("independent human", provenance.lower())
        for case_id, anchor in (
            ("P10_required_views.en", "E01"),
            ("P11_nonchronological_roles.zh-TW", "E02"),
            ("P12_ranked_courses.ja", "E03"),
        ):
            provenance = "\n".join(self.cases[case_id].provenance.references)
            self.assertIn(f"versus {anchor}", provenance)
            self.assertIn("review", provenance)
            self.assertIn("pending", provenance)


if __name__ == "__main__":
    unittest.main()
