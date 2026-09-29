"""Archived v8 identity ruler, not a claim about model role understanding."""
import hashlib
import unittest

from tools import candidate_registry as registry

CANDIDATE = "p3-bound-meaning-context-v8"
CONTEXT_SHA256 = "441f901b63d9dfdb6f622351a1e13b8ad3b9308d4c2185fa20a870fb8537ee8f"


class BoundCompareContextCandidateTests(unittest.TestCase):
    def test_v8_changes_only_context_and_preserves_v7_archive(self):
        self.assertIn(CANDIDATE, [r["candidate_id"] for r in registry.load_index()["entries"]],
                      "Register the authorized narrowed comparison context candidate")
        new = registry.load_entry(CANDIDATE)
        old = registry.load_entry("p3-31b-count-context-v7")
        self.assertEqual(new["ancestor"], old["candidate_id"])
        self.assertEqual(new["recipe_context"]["context_version"], "learningops-recipe-context-v4")
        self.assertEqual(new["recipe_context"]["context_sha256"], CONTEXT_SHA256)
        self.assertEqual({k for k in new["recipe_context"] if new["recipe_context"][k] != old["recipe_context"][k]},
                         {"context_version", "context_sha256", "system_message_sha256"})
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
        self.assertEqual(hashlib.sha256((registry.DIRECTORY / "p3-31b-count-context-v7.json").read_bytes()).hexdigest(),
                         "ca7d033978af81ea573970beab4dbacfc6e740642d9c622e2a66d50b9a65bfb1")
