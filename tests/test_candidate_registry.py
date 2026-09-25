"""Candidate registry rulers (#87): registered identities are byte-stable, the live runtime is registered."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from grepbit import recipe_model
from tools import candidate_registry as registry, p3_candidate_model

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "tests/fixtures/p310_identity_baseline.json").read_bytes())


class CandidateRegistryRulers(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def test_index_and_entries_are_consistent_and_byte_stable(self):
        index = registry.load_index()
        self.assertEqual(index["registry_version"], "candidate-registry-v1")
        self.assertEqual(index["entries"][0]["candidate_id"], registry.FROZEN_CANDIDATE_ID)
        self.assertIsNone(index["entries"][0]["ancestor"])
        for row in index["entries"]:
            entry = registry.load_entry(row["candidate_id"])
            self.assertEqual(entry["candidate_id"], row["candidate_id"])
            self.assertEqual(hashlib.sha256((registry.DIRECTORY / row["path"]).read_bytes()).hexdigest(),
                             row["sha256"])
            self.assertEqual(set(entry), registry._ENTRY_FIELDS)
            self.assertEqual(len(entry["wire_witnesses"]), len(registry.WITNESS_QUESTIONS))
        self.assertEqual(index["current"], index["entries"][-1]["candidate_id"])

    def test_frozen_entry_is_the_p310_fixture_identity_and_the_historical_semantic_digest(self):
        entry = registry.load_entry(registry.FROZEN_CANDIDATE_ID)
        for key in ("recipe_context", "structured_output", "p1_context", "limits"):
            self.assertEqual(entry[key], BASELINE[key])
        witness = registry.witness(entry, BASELINE["wire"]["question"])
        self.assertEqual(witness["recipe_body_sha256"], BASELINE["wire"]["recipe_body_sha256"])
        self.assertEqual(witness["recipe_body_bytes"], BASELINE["wire"]["recipe_body_bytes"])
        self.assertEqual(witness["p1_body_sha256"], BASELINE["wire"]["p1_body_sha256"])
        self.assertEqual(witness["p1_body_bytes"], BASELINE["wire"]["p1_body_bytes"])
        self.assertEqual(entry["semantic_identity_sha256"], p3_candidate_model.SEMANTICS_SHA256)
        self.assertEqual(entry["recipe_context"]["instruction_version"], "recipe-selection-instruction-v2")

    def test_live_runtime_is_the_registered_current_candidate(self):
        result = registry.check()
        self.assertEqual(result["candidate_id"], registry.current()["candidate_id"])
        self.assertEqual(result["semantic_identity_sha256"], registry.current()["semantic_identity_sha256"])
        live = registry.live_identity()
        self.assertEqual(live["recipe_context"], recipe_model.context_identity())
        self.assertEqual(live["wire_witnesses"], registry.current()["wire_witnesses"])

    def test_unregistered_prompt_change_fails_check_and_registers_only_as_a_new_candidate(self):
        with tempfile.TemporaryDirectory(prefix="registry-", dir=ROOT / ".artifacts") as tmp:
            index_path = Path(tmp) / "index.json"
            first = registry.register("synthetic-frozen", "synthetic copy of the live identity", index_path=index_path,
                                      now="2026-09-25T00:00:00Z")
            self.assertEqual(first["candidate_id"], "synthetic-frozen")
            with self.assertRaises(registry.RegistryError) as unchanged:
                registry.register("synthetic-again", "same identity", index_path=index_path)
            self.assertEqual(unchanged.exception.code, "identity_unchanged")
            with self.assertRaises(registry.RegistryError) as duplicate:
                with patch.object(recipe_model, "SYSTEM_INSTRUCTION", recipe_model.SYSTEM_INSTRUCTION + " Restated."):
                    registry.register("synthetic-frozen", "duplicate id", index_path=index_path)
            self.assertEqual(duplicate.exception.code, "duplicate_candidate_id")
            with patch.object(recipe_model, "SYSTEM_INSTRUCTION", recipe_model.SYSTEM_INSTRUCTION + " Restated."), \
                    patch.object(recipe_model, "INSTRUCTION_VERSION", "recipe-selection-instruction-synthetic"):
                with self.assertRaises(registry.RegistryError) as unregistered:
                    registry.check(index_path)
                self.assertEqual(unregistered.exception.code, "unregistered_candidate")
                second = registry.register("synthetic-restated", "one general restatement", index_path=index_path,
                                           now="2026-09-25T00:00:01Z")
                self.assertEqual(registry.check(index_path)["candidate_id"], "synthetic-restated")
                entry = registry.load_entry("synthetic-restated", index_path)
            self.assertEqual(entry["ancestor"], "synthetic-frozen")
            self.assertNotEqual(second["semantic_identity_sha256"], first["semantic_identity_sha256"])
            self.assertEqual(entry["recipe_context"]["instruction_version"], "recipe-selection-instruction-synthetic")
            self.assertNotEqual(registry.witness(entry, registry.WITNESS_QUESTIONS[0][1])["recipe_body_sha256"],
                                registry.witness(registry.load_entry("synthetic-frozen", index_path),
                                                 registry.WITNESS_QUESTIONS[0][1])["recipe_body_sha256"])
            # Back on the unchanged live identity, the restated entry is current and check fails closed.
            with self.assertRaises(registry.RegistryError) as stale:
                registry.check(index_path)
            self.assertEqual(stale.exception.code, "unregistered_candidate")
            # Tampering with an entry or the index is detected.
            path = Path(tmp) / "synthetic-restated.json"
            tampered = json.loads(path.read_text())
            tampered["note"] = "edited"
            path.write_text(json.dumps(tampered))
            with self.assertRaises(registry.RegistryError) as drift:
                registry.load_entry("synthetic-restated", index_path)
            self.assertEqual(drift.exception.code, "registry_drift")
            for bad in ("not-valid ID", "", "A-upper"):
                with self.assertRaises(registry.RegistryError):
                    registry.register(bad, "note", index_path=index_path)

    def test_witness_lookup_is_by_question_digest_only(self):
        entry = registry.current()
        self.assertEqual(registry.witness(entry, "March 2026 bookings; 三月預訂.")["label"],
                         "development_wire")
        with self.assertRaises(registry.RegistryError):
            registry.witness(entry, "never registered")
        for _, question in registry.WITNESS_QUESTIONS:
            self.assertNotIn(question, json.dumps(entry, ensure_ascii=False))

    def test_cli_is_closed_and_offline(self):
        with patch("sys.stdout"), patch("sys.stderr"):
            self.assertEqual(registry.main(["check"]), 0)
            self.assertEqual(registry.main(["show"]), 0)
            with patch.object(registry, "INDEX", ROOT / ".artifacts" / "missing-registry" / "index.json"):
                self.assertEqual(registry.main(["check"]), 2)
            with self.assertRaises(SystemExit):
                registry.main(["register"])


if __name__ == "__main__":
    unittest.main()
