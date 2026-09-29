"""v10 identity ruler: v7's exact runtime restored after v9, not a claim about model behavior."""
import hashlib
import unittest

from tools import candidate_registry as registry

CANDIDATE = "p3-v7-context-restoration-v10"
V7 = "p3-31b-count-context-v7"
V9 = "p3-generic-count-context-v9"
V7_SEMANTIC = "95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb"
V7_RECIPE_MODEL = "90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457"
IDENTITY = ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
            "candidate_sha256", "wire_witnesses", "runtime_files_sha256")
ARCHIVE = {V7: "ca7d033978af81ea573970beab4dbacfc6e740642d9c622e2a66d50b9a65bfb1",
           "p3-bound-meaning-context-v8": "f675d4b927ca753b42daba5cd0f23ba87b02ef6a271f0201e6163d647343cb56",
           V9: "d323341dfc2bf1e81d2a133ac50514542c41239d80763c8d6af4dc9da68e8ba1"}


class V7RestorationCandidateTests(unittest.TestCase):
    def test_live_runtime_is_byte_identical_to_v7(self):
        index = registry.load_index()
        if CANDIDATE in [r["candidate_id"] for r in index["entries"]] and index["current"] != CANDIDATE:
            self.skipTest("v10 superseded; its registered identity remains pinned below")
        self.assertEqual(hashlib.sha256((registry.ROOT / "grepbit/recipe_model.py").read_bytes()).hexdigest(),
                         V7_RECIPE_MODEL)
        self.assertEqual(registry.semantic_identity()["recipe_context"],
                         registry.load_entry(V7)["recipe_context"])
        self.assertEqual(registry._digest(registry.semantic_identity()), V7_SEMANTIC)

    def test_v10_registration_equals_v7_identity_and_preserves_archive(self):
        ids = [r["candidate_id"] for r in registry.load_index()["entries"]]
        self.assertIn(CANDIDATE, ids, "Register the owner-approved v7 restoration candidate")
        self.assertEqual(ids.index(CANDIDATE), ids.index(V9) + 1)
        new, v7, v9 = (registry.load_entry(c) for c in (CANDIDATE, V7, V9))
        self.assertEqual(new["ancestor"], V9)
        self.assertEqual(v7["semantic_identity_sha256"], V7_SEMANTIC)
        self.assertEqual(v7["runtime_files_sha256"]["grepbit/recipe_model.py"], V7_RECIPE_MODEL)
        for key in IDENTITY:
            self.assertEqual(new[key], v7[key], key)
        self.assertNotEqual(new["semantic_identity_sha256"], v9["semantic_identity_sha256"])
        for candidate, digest in ARCHIVE.items():
            self.assertEqual(hashlib.sha256((registry.DIRECTORY / f"{candidate}.json").read_bytes()).hexdigest(),
                             digest, candidate)
