"""v9 identity ruler: v7 context plus one generic-count sentence, not a claim about model behavior."""
import copy
import hashlib
import unittest

from grepbit import model as protocol
from grepbit import recipe_model
from tools import candidate_registry as registry

CANDIDATE = "p3-generic-count-context-v9"
V7 = "p3-31b-count-context-v7"
V8 = "p3-bound-meaning-context-v8"
CONTEXT_VERSION = "learningops-recipe-context-v5"
CONTEXT_SHA256 = "fda52fcfa93210dbe80632ac218db73d1221ab024c0572b9fe70d40c3b89c68e"
V7_SCOPE = "Distinct explicit current and baseline months; no center filter."
V7_ROLES = "Two explicit months without orientation; preserve both months and offer both roles."
DECLINE = ("If the question requires attendance_visits, distinct_people or known_booking_accounts, decline the whole "
           "request, including when it also requires a supported Overview.")
GENERIC = ("A generic people or count noun alone, without a stated attendance event, deduplication of actual persons "
           "or a booking-account basis, requires none of those meanings and leaves the count meanings unresolved.")
ARCHIVE = {V7: "ca7d033978af81ea573970beab4dbacfc6e740642d9c622e2a66d50b9a65bfb1",
           V8: "f675d4b927ca753b42daba5cd0f23ba87b02ef6a271f0201e6163d647343cb56"}


def _sha(context: dict) -> str:
    return hashlib.sha256(protocol.canonical_json(context).encode()).hexdigest()


class GenericCountContextCandidateTests(unittest.TestCase):
    def test_runtime_is_v7_context_plus_one_generic_count_sentence(self):
        index = registry.load_index()
        if CANDIDATE in [r["candidate_id"] for r in index["entries"]] and index["current"] != CANDIDATE:
            self.skipTest("v9 superseded; its registered identity remains pinned below")
        context = recipe_model.runtime_context()
        self.assertEqual(context["version"], CONTEXT_VERSION)
        self.assertEqual(context["recipes"][1]["id"], "compare")
        self.assertEqual(context["recipes"][1]["scope"], V7_SCOPE)
        self.assertEqual(context["clarification"]["comparison_roles"], V7_ROLES)
        count_basis = context["clarification"]["count_basis"]
        self.assertEqual(count_basis.count(GENERIC), 1)
        self.assertEqual(count_basis.count(DECLINE + " " + GENERIC + " "), 1)
        self.assertEqual(_sha(context), CONTEXT_SHA256)
        # Removing the sentence and restoring the version reproduces the registered v7 context byte for byte.
        restored = copy.deepcopy(context)
        restored["version"] = "learningops-recipe-context-v3"
        restored["clarification"]["count_basis"] = count_basis.replace(" " + GENERIC, "", 1)
        self.assertEqual(_sha(restored), registry.load_entry(V7)["recipe_context"]["context_sha256"])

    def test_v9_registration_changes_only_recipe_context_and_preserves_archive(self):
        self.assertIn(CANDIDATE, [r["candidate_id"] for r in registry.load_index()["entries"]],
                      "Register the authorized generic-count context candidate")
        new, v8, v7 = (registry.load_entry(c) for c in (CANDIDATE, V8, V7))
        self.assertEqual(new["ancestor"], V8)
        self.assertEqual(new["recipe_context"]["context_version"], CONTEXT_VERSION)
        self.assertEqual(new["recipe_context"]["context_sha256"], CONTEXT_SHA256)
        for old in (v7, v8):
            self.assertEqual({k for k in new["recipe_context"] if new["recipe_context"][k] != old["recipe_context"][k]},
                             {"context_version", "context_sha256", "system_message_sha256"})
            for key in ("structured_output", "p1_context", "limits"):
                self.assertEqual(new[key], old[key], key)
            self.assertNotEqual(new["semantic_identity_sha256"], old["semantic_identity_sha256"])
        self.assertEqual(set(new["runtime_files_sha256"]), set(v8["runtime_files_sha256"]))
        self.assertEqual({k for k in new["runtime_files_sha256"]
                          if new["runtime_files_sha256"][k] != v8["runtime_files_sha256"][k]},
                         {"grepbit/recipe_model.py"})
        self.assertEqual(len(new["wire_witnesses"]), len(v8["wire_witnesses"]))
        for a, b in zip(new["wire_witnesses"], v8["wire_witnesses"]):
            for key in ("label", "question_sha256", "p1_body_sha256", "p1_body_bytes"):
                if key in b:
                    self.assertEqual(a[key], b[key])
            self.assertNotEqual(a["recipe_body_sha256"], b["recipe_body_sha256"])
            self.assertLessEqual(a["recipe_body_bytes"], new["limits"]["request"])
        for candidate, digest in ARCHIVE.items():
            self.assertEqual(hashlib.sha256((registry.DIRECTORY / f"{candidate}.json").read_bytes()).hexdigest(),
                             digest, candidate)
