"""Archived instruction-only candidate boundaries; not a model-quality oracle."""
import unittest
from unittest.mock import patch

from tools import candidate_registry as registry

CANDIDATE = "p3-31b-instruction-v3"


class InstructionCandidateV3Tests(unittest.TestCase):
    def test_registered_v3_changes_instruction_only_and_preserves_prior_surfaces(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Offline only")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("Offline only")):
            self.assertIn(CANDIDATE, [row["candidate_id"] for row in registry.load_index()["entries"]],
                          "The instruction candidate must have its own archived registry entry")
            candidate = registry.load_entry(CANDIDATE)
            frozen = registry.load_entry(registry.FROZEN_CANDIDATE_ID)
        self.assertEqual(candidate["ancestor"], registry.FROZEN_CANDIDATE_ID)
        identity = candidate["recipe_context"]
        prior = frozen["recipe_context"]
        self.assertEqual(identity["instruction_version"], "recipe-selection-instruction-v3")
        changed = {key for key in identity if identity[key] != prior[key]}
        self.assertEqual(changed, {"instruction_version", "instruction_sha256", "system_message_sha256"})
        for surface in ("structured_output", "p1_context", "limits"):
            self.assertEqual(candidate[surface], frozen[surface], surface)
        self.assertNotEqual(candidate["semantic_identity_sha256"], frozen["semantic_identity_sha256"])
        current_files, old_files = candidate["runtime_files_sha256"], frozen["runtime_files_sha256"]
        self.assertEqual(set(current_files), set(old_files))
        self.assertEqual({name for name in current_files if current_files[name] != old_files[name]},
                         {"grepbit/recipe_model.py"})
        self.assertEqual(len(candidate["wire_witnesses"]), len(frozen["wire_witnesses"]))
        for wire, old in zip(candidate["wire_witnesses"], frozen["wire_witnesses"]):
            for key in ("label", "question_sha256", "p1_body_sha256", "p1_body_bytes"):
                self.assertEqual(wire[key], old[key], key)
            self.assertNotEqual(wire["recipe_body_sha256"], old["recipe_body_sha256"])
            self.assertGreater(wire["recipe_body_bytes"], old["recipe_body_bytes"])
            self.assertLessEqual(wire["recipe_body_bytes"], candidate["limits"]["request"])


if __name__ == "__main__":
    unittest.main()
