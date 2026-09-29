"""Archived v7 context identity/scope ruler; not model-behavior evidence."""
import hashlib
import unittest
from unittest.mock import patch

from tools import candidate_registry as registry

CANDIDATE = "p3-31b-count-context-v7"
CONTEXT_SHA256 = "d9edaf450dd088cf5975704d6504d1019a437fbf51c91502fd9fc023d6e027d7"


class CountContextCandidateTests(unittest.TestCase):
    def test_v7_changes_context_only_and_preserves_archived_v6(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Offline only")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("Offline only")):
            self.assertIn(CANDIDATE, [r["candidate_id"] for r in registry.load_index()["entries"]],
                          "Register the authorized bound-count context candidate")
            new = registry.load_entry(CANDIDATE)
            old = registry.load_entry("p3-31b-instruction-v6")
        self.assertEqual(new["ancestor"], old["candidate_id"])
        self.assertEqual(new["recipe_context"]["context_version"], "learningops-recipe-context-v3")
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
        self.assertEqual(hashlib.sha256((registry.DIRECTORY / "p3-31b-instruction-v6.json").read_bytes()).hexdigest(),
                         "362248a0e2ae0dc3f4f98f271b0db3e764c94b3620250b0b45aed429fce6d840")
