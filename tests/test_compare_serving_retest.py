"""Serving retest admission rulers; exact exposed projection, no live traffic."""
import hashlib
import json
import unittest

from tools import evaluate, p3_assets

PANEL = "p3-dev-compare-retest-v1"
IDS = ["dev-A3.en", "dev-C2.zh-TW", "dev-C2.en"]
PROFILE = evaluate.ROOT / "evals/routes/gemma-31b-xgrammar-compact-v1.json"


class CompareServingRetestTests(unittest.TestCase):
    def test_exact_three_input_projection_preserves_existing_cases_and_oracles(self):
        entries = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL, entries, "Register the bounded three-input retest")
        original = p3_assets.load_panel(evaluate.ROOT / entries["p3-dev-matrix-v1"]["path"])
        entry = entries[PANEL]
        panel = p3_assets.load_panel(evaluate.ROOT / entry["path"])
        self.assertEqual([case.case_id for case in panel.cases], IDS)
        by_id = {case.case_id: case for case in original.cases}
        self.assertEqual(list(panel.cases), [by_id[key] for key in IDS])
        self.assertEqual({oracle.oracle_id: oracle for oracle in panel.oracles},
                         {original.oracle_for(by_id[key]).oracle_id: original.oracle_for(by_id[key]) for key in IDS})
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"]),
                         ("dev", "development", None))
        for name, path in (("panel", panel.path), ("cases", panel.cases_path), ("oracles", panel.oracles_path)):
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_route_binds_observed_profile_and_retains_normal_budget(self):
        self.assertTrue(PROFILE.exists(), "Record the new serving profile identity")
        profile = json.loads(PROFILE.read_text())
        route = next(row for row in evaluate.load_routes()["routes"] if row["route_id"] == "litellm-gemma-4-31b")
        self.assertIn(hashlib.sha256(PROFILE.read_bytes()).hexdigest(), route["note"])
        self.assertEqual(profile["structured_outputs_config"], {"backend": "xgrammar", "disable_any_whitespace": True})
        self.assertEqual(profile["infra_commit"], "fdb1f05353fb9ab0ff63b359cc92cb6d4c83a7ec")
        self.assertEqual(profile["serving_sha256"], "ac01cea858c9029f26f92a8dd1f4a4f208af59f52e8adf974d585b7ff0aa0e59")
        for count, bound in ((3, 300.0), (54, 3360.0)):
            settings = evaluate.settings(route, count)
            self.assertEqual(settings["call_timeout_seconds"], 60.0)
            self.assertEqual(settings["panel_timeout_seconds"], bound)
            self.assertEqual(settings["max_runtime_invocations"], count)
        self.assertEqual(evaluate.derive_claim("holdout", "p3-holdout-a-v2", route["route_id"], evaluate.load_runs()),
                         "observed_regression")
