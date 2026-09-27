"""Identity/projection ruler for independently reviewed C4 dev revision."""
import hashlib
import json
import unittest
from tools import evaluate, p3_assets

PANEL = "p3-dev-matrix-compare-first-v2"
QUESTIONS_SHA256 = "c047a34a849a486e8a79cdd64406488ccda67437307a48ec6e12b4444b9327cc"


class C4SemanticRevisionTests(unittest.TestCase):
    def test_versioned_panel_changes_only_c4_and_preserves_historical_assets(self):
        entries = {x["panel_id"]: x for x in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL, entries, "Register the independently accepted C4 revision")
        original = p3_assets.load_panel(evaluate.ROOT / entries["p3-dev-matrix-compare-first-v1"]["path"])
        entry = entries[PANEL]
        new = p3_assets.load_panel(evaluate.ROOT / entry["path"])
        self.assertEqual(len(new.cases), 54)
        self.assertEqual([c.case_id for c in new.cases],
                         [c.case_id.replace("dev-C4.", "dev-C4-v2.") for c in original.cases])
        self.assertEqual([c for c in new.cases if c.family_id != "dev-C4-v2"],
                         [c for c in original.cases if c.family_id != "dev-C4"])
        self.assertEqual([o for o in new.oracles if o.oracle_id != "dev-C4.v2"],
                         [o for o in original.oracles if o.oracle_id != "dev-C4.v1"])
        changed = [c for c in new.cases if c.family_id == "dev-C4-v2"]
        questions = {c.language: c.question for c in changed}
        canonical = json.dumps(questions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), QUESTIONS_SHA256)
        for c in changed:
            self.assertEqual((c.expected_branch, c.oracle_id, c.exposure),
                             ("clarify", "dev-C4.v2", "exposed_regression"))
            self.assertTrue(c.provenance.seen_by_implementer)
            oracle = new.oracle_for(c)
            self.assertEqual(oracle.clarification.kind, "metric_meaning")
            self.assertEqual({x.semantic_value.value for x in oracle.clarification.choices},
                             {"confirmed_booked_amount", "cash_received"})
            prior = original.oracle_for(next(x for x in original.cases if x.family_id == "dev-C4"))
            self.assertEqual(oracle.clarification, prior.clarification)
        self.assertEqual((entry["tier"], entry["authoring"]), ("dev", "development"))
        for key, path in (("panel", new.path), ("cases", new.cases_path), ("oracles", new.oracles_path)):
            self.assertEqual(entry["assets"][key], hashlib.sha256(path.read_bytes()).hexdigest())
        for path, sha in ((original.cases_path, "997d0068941534749d73e27648ceccfb54a46109df7ddc89fd7aee4a322c7fa6"),
                          (original.oracles_path, "508e3a221a083df981d13ae8af8a678bdd92686a87db92dcb2679498b6802aec")):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha)
