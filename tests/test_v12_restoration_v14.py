"""v14 identity ruler: v12's exact runtime restored after v13's gate regression (#136, #79), not a model claim."""
import hashlib
import unittest

from grepbit import gateway
from tools import candidate_registry as registry

CANDIDATE = "p3-v12-restoration-v14"
V12 = "p3-v10-restoration-v12"
V13 = "p3-count-assumption-v13"
V12_SEMANTIC = "95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb"
V12_CANDIDATE = "6d707b8dc2d58915f2a794d97404faf85be72ab5ac7e27545bd2d9d0c428e536"
V12_RECIPE_MODEL = "90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457"
# Accepted frozen bytes at 20abb55, amended for v13 under #136 and restored here by owner approval (#79).
FROZEN_RECIPE_CLARIFICATION = "42b0ce5ca722422540deb8ef46517da78c8ff558098fc6d81b6948602b3f0c11"
IDENTITY = ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
            "candidate_sha256", "wire_witnesses", "runtime_files_sha256")


def sha(path):
    return hashlib.sha256((registry.ROOT / path).read_bytes()).hexdigest()


def superseded():
    """v14 is registered but no longer current: its runtime checks no longer apply."""
    index = registry.load_index()
    return CANDIDATE in [r["candidate_id"] for r in index["entries"]] and index["current"] != CANDIDATE


class V12RestorationV14Tests(unittest.TestCase):
    def test_live_runtime_is_byte_identical_to_v12(self):
        if superseded():
            self.skipTest("v14 superseded; its registered identity remains pinned below")
        v12 = registry.load_entry(V12)
        self.assertEqual(sha("grepbit/recipe_model.py"), V12_RECIPE_MODEL)
        self.assertEqual({name: sha(name) for name in registry.RUNTIME_FILES}, v12["runtime_files_sha256"])
        self.assertEqual(registry._digest(registry.semantic_identity()), V12_SEMANTIC)
        self.assertEqual(gateway.MAX_REQUEST_BYTES, 32768)
        self.assertEqual(registry.check()["candidate_id"], CANDIDATE)

    def test_frozen_recipe_clarification_source_is_restored(self):
        if superseded():
            self.skipTest("v14 superseded; a later candidate may amend the frozen test with recorded ancestry")
        self.assertEqual(sha("tests/test_recipe_clarification.py"), FROZEN_RECIPE_CLARIFICATION)

    def test_v14_registration_equals_v12_identity_after_v13(self):
        ids = [r["candidate_id"] for r in registry.load_index()["entries"]]
        self.assertIn(CANDIDATE, ids, "Register the owner-approved v12 restoration candidate")
        self.assertEqual(ids.index(CANDIDATE), ids.index(V13) + 1)
        new, v12, v13 = (registry.load_entry(c) for c in (CANDIDATE, V12, V13))
        self.assertEqual(new["ancestor"], V13)
        self.assertEqual((v12["semantic_identity_sha256"], v12["candidate_sha256"]), (V12_SEMANTIC, V12_CANDIDATE))
        for key in IDENTITY:
            self.assertEqual(new[key], v12[key], key)
        self.assertEqual(new["limits"]["request"], 32768)
        self.assertNotEqual(new["candidate_sha256"], v13["candidate_sha256"])


if __name__ == "__main__":
    unittest.main()
