"""Archived formatting-only candidate and order-only panel; no quality claim."""
import hashlib
import unittest
from unittest.mock import patch

from tools import candidate_registry as registry, evaluate, p3_assets

CANDIDATE = "p3-31b-instruction-v4"
PANEL = "p3-dev-matrix-compare-first-v1"
FIRST = ["dev-A3.en", "dev-C2.zh-TW", "dev-C2.en"]
INSTRUCTION_SHA256 = "a3fbde4d95d61939ca9a80f621539165161458d33147eb8d185ec988c87af4f1"


class CompactJsonCandidateTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.getaddrinfo"):
            self.enterContext(patch(target, side_effect=AssertionError("Offline only")))

    def test_registered_v4_is_only_the_accepted_formatting_instruction_change(self):
        self.assertIn(CANDIDATE, [row["candidate_id"] for row in registry.load_index()["entries"]],
                      "The approved compact JSON candidate must be registered")
        candidate = registry.load_entry(CANDIDATE)
        prior = registry.load_entry("p3-31b-instruction-v3")
        self.assertEqual(candidate["ancestor"], prior["candidate_id"])
        context = candidate["recipe_context"]
        self.assertEqual(context["instruction_version"], "recipe-selection-instruction-v4")
        self.assertEqual(context["instruction_sha256"], INSTRUCTION_SHA256)
        self.assertEqual({key for key in context if context[key] != prior["recipe_context"][key]},
                         {"instruction_version", "instruction_sha256", "system_message_sha256"})
        for surface in ("structured_output", "p1_context", "limits"):
            self.assertEqual(candidate[surface], prior[surface], surface)
        self.assertEqual({key for key in candidate["runtime_files_sha256"]
                          if candidate["runtime_files_sha256"][key] != prior["runtime_files_sha256"][key]},
                         {"grepbit/recipe_model.py"})
        self.assertNotEqual(candidate["semantic_identity_sha256"], prior["semantic_identity_sha256"])
        for wire, old in zip(candidate["wire_witnesses"], prior["wire_witnesses"]):
            for key in ("label", "question_sha256", "p1_body_sha256", "p1_body_bytes"):
                if key in old:
                    self.assertEqual(wire[key], old[key], key)
            self.assertNotEqual(wire["recipe_body_sha256"], old["recipe_body_sha256"])
            self.assertLessEqual(wire["recipe_body_bytes"], candidate["limits"]["request"])

    def test_compare_first_panel_preserves_all_inputs_and_shared_assets(self):
        entries = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL, entries, "The approved order-only dev panel must be registered")
        entry = entries[PANEL]
        original = p3_assets.load_panel(evaluate.ROOT / entries["p3-dev-matrix-v1"]["path"])
        panel = p3_assets.load_panel(evaluate.ROOT / entry["path"])
        ids = [case.case_id for case in original.cases]
        compare = [case.case_id for case in original.cases if case.family_id in {"dev-A3", "dev-A4", "dev-C2"}]
        expected = FIRST + [case for case in compare if case not in FIRST] + [case for case in ids if case not in compare]
        self.assertEqual([case.case_id for case in panel.cases], expected)
        self.assertEqual(len(panel.cases), 54)
        self.assertEqual({case.case_id: case for case in panel.cases},
                         {case.case_id: case for case in original.cases})
        self.assertEqual((panel.cases_path, panel.oracles_path), (original.cases_path, original.oracles_path))
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"]),
                         ("dev", "development", None))
        for name, path in (("panel", evaluate.ROOT / entry["path"]),
                           ("cases", panel.cases_path), ("oracles", panel.oracles_path)):
            self.assertEqual(entry["assets"][name], hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
