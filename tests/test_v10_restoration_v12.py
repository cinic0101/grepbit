"""v12 identity ruler: v10's exact runtime restored after the failed v11 step 1 (#79), not a model claim."""
import hashlib
import subprocess
import unittest

from grepbit import gateway
from tools import candidate_registry as registry, p3_eval

CANDIDATE = "p3-v10-restoration-v12"
V10 = "p3-v7-context-restoration-v10"
V11 = "p3-count-cue-policy-v11"
V10_SEMANTIC = "95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb"
V10_RECIPE_MODEL = "90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457"
V10_GATEWAY = "5739e79d9e3c1eaf828eb347e4c5930dfdeb41fd157e9e3c68cc5b61da8e526f"
# Accepted frozen bytes at 20abb55, amended for v11 under #120 and restored here by owner approval (#79).
FROZEN_RECIPE_CLARIFICATION = "42b0ce5ca722422540deb8ef46517da78c8ff558098fc6d81b6948602b3f0c11"
# The merge of the v12 restoration (#127); later candidates may amend the file only with recorded ancestry.
V12_MERGE = "71d0354b7b15995789ec7a8fa88ea920725de1aa"
IDENTITY = ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
            "candidate_sha256", "wire_witnesses", "runtime_files_sha256")
ARCHIVE = {"p3-31b-count-context-v7": "ca7d033978af81ea573970beab4dbacfc6e740642d9c622e2a66d50b9a65bfb1",
           "p3-bound-meaning-context-v8": "f675d4b927ca753b42daba5cd0f23ba87b02ef6a271f0201e6163d647343cb56",
           "p3-generic-count-context-v9": "d323341dfc2bf1e81d2a133ac50514542c41239d80763c8d6af4dc9da68e8ba1",
           V10: "72124fe322213dd77977f90d386f49ed2c67bc5e6593a88fc5fd7aef8ed388e2",
           V11: "1c1bdf0531ae39d84d179ced4e349e7f2c4e6f677ec31093936b2203fc237630"}


def sha(path):
    return hashlib.sha256((registry.ROOT / path).read_bytes()).hexdigest()


class V10RestorationV12Tests(unittest.TestCase):
    def test_live_runtime_is_byte_identical_to_v10(self):
        index = registry.load_index()
        if CANDIDATE in [r["candidate_id"] for r in index["entries"]] and index["current"] != CANDIDATE:
            self.skipTest("v12 superseded; its registered identity remains pinned below")
        v10 = registry.load_entry(V10)
        self.assertFalse((registry.ROOT / "grepbit/count_policy.py").exists())
        self.assertEqual(sha("grepbit/recipe_model.py"), V10_RECIPE_MODEL)
        self.assertEqual(sha("grepbit/gateway.py"), V10_GATEWAY)
        self.assertEqual({name: sha(name) for name in registry.RUNTIME_FILES}, v10["runtime_files_sha256"])
        self.assertEqual(registry._digest(registry.semantic_identity()), V10_SEMANTIC)
        self.assertEqual(gateway.MAX_REQUEST_BYTES, 32768)

    def test_evaluation_defaults_follow_the_restored_runtime(self):
        self.assertEqual(p3_eval.MAX_REQUEST_BYTES, gateway.MAX_REQUEST_BYTES)
        self.assertEqual(p3_eval.settings(1)["max_request_bytes"], gateway.MAX_REQUEST_BYTES)
        self.assertEqual(p3_eval.REQUEST_CAPS, (32768, 40960))
        self.assertEqual(p3_eval.DEFAULT_RESPONSES, registry.ROOT / "evals/p3/development-responses-v1.json")

    def test_frozen_recipe_clarification_source_was_restored_and_later_amendments_keep_its_ancestry(self):
        restored = subprocess.check_output(
            ["git", "--no-optional-locks", "show", f"{V12_MERGE}:tests/test_recipe_clarification.py"],
            cwd=registry.ROOT, timeout=5)
        self.assertEqual(hashlib.sha256(restored).hexdigest(), FROZEN_RECIPE_CLARIFICATION)
        from test_p3_exposed import SOURCE_SHA256, SUPERSEDED_SOURCE_SHA256
        current = sha("tests/test_recipe_clarification.py")
        self.assertEqual(SOURCE_SHA256["tests/test_recipe_clarification.py"], current)
        if current != FROZEN_RECIPE_CLARIFICATION:
            self.assertEqual(SUPERSEDED_SOURCE_SHA256["tests/test_recipe_clarification.py"][0],
                             FROZEN_RECIPE_CLARIFICATION)

    def test_v12_registration_equals_v10_identity_and_preserves_archive(self):
        ids = [r["candidate_id"] for r in registry.load_index()["entries"]]
        self.assertIn(CANDIDATE, ids, "Register the owner-approved v10 restoration candidate")
        self.assertEqual(ids.index(CANDIDATE), ids.index(V11) + 1)
        new, v10, v11 = (registry.load_entry(c) for c in (CANDIDATE, V10, V11))
        self.assertEqual(new["ancestor"], V11)
        self.assertEqual(v10["semantic_identity_sha256"], V10_SEMANTIC)
        for key in IDENTITY:
            self.assertEqual(new[key], v10[key], key)
        self.assertEqual(new["limits"]["request"], 32768)
        self.assertNotEqual(new["semantic_identity_sha256"], v11["semantic_identity_sha256"])
        for candidate, digest in ARCHIVE.items():
            self.assertEqual(hashlib.sha256((registry.DIRECTORY / f"{candidate}.json").read_bytes()).hexdigest(),
                             digest, candidate)


if __name__ == "__main__":
    unittest.main()
