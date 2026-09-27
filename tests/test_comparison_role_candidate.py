"""Archived v5 instruction scope ruler; not a model-quality acceptance test."""
import hashlib
import unittest
from unittest.mock import patch
from tools import candidate_registry as registry

CANDIDATE = "p3-31b-instruction-v5"
INSTRUCTION_SHA256 = "1452ddbbe34297e66a33a0174aa900aaa4074afc745eaf1dc59cd4cadaa6bbc8"


class ComparisonRoleCandidateTests(unittest.TestCase):
    def test_v5_is_exact_role_wording_change_with_other_surfaces_preserved(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Offline only")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("Offline only")):
            self.assertIn(CANDIDATE, [r["candidate_id"] for r in registry.load_index()["entries"]],
                          "The approved third candidate must be registered")
            new = registry.load_entry(CANDIDATE)
            old = registry.load_entry("p3-31b-instruction-v4")
        self.assertEqual(new["ancestor"], old["candidate_id"])
        self.assertEqual(new["recipe_context"]["instruction_version"], "recipe-selection-instruction-v5")
        self.assertEqual(new["recipe_context"]["instruction_sha256"], INSTRUCTION_SHA256)
        self.assertEqual({k for k in new["recipe_context"] if new["recipe_context"][k] != old["recipe_context"][k]},
                         {"instruction_version", "instruction_sha256", "system_message_sha256"})
        for key in ("structured_output", "p1_context", "limits"):
            self.assertEqual(new[key], old[key], key)
        self.assertEqual(set(new["runtime_files_sha256"]), set(old["runtime_files_sha256"]))
        self.assertEqual({k for k in new["runtime_files_sha256"]
                          if new["runtime_files_sha256"][k] != old["runtime_files_sha256"][k]},
                         {"grepbit/recipe_model.py"})
        self.assertNotEqual(new["semantic_identity_sha256"], old["semantic_identity_sha256"])
        self.assertEqual(len(new["wire_witnesses"]), len(old["wire_witnesses"]))
        for a, b in zip(new["wire_witnesses"], old["wire_witnesses"]):
            for key in ("label", "question_sha256", "p1_body_sha256", "p1_body_bytes"):
                if key in b:
                    self.assertEqual(a[key], b[key])
            self.assertNotEqual(a["recipe_body_sha256"], b["recipe_body_sha256"])
            self.assertLessEqual(a["recipe_body_bytes"], new["limits"]["request"])
        self.assertEqual(hashlib.sha256((registry.DIRECTORY / "p3-31b-instruction-v4.json").read_bytes()).hexdigest(),
                         "71e2ab072e0a43a803a61f994860f24ceb240615d9976c42e5d29e988e14961b")
