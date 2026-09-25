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
# Pinned registry expectations; a candidate registration PR updates both lines.
EXPECTED_CURRENT = "p33-frozen-20abb559"
EXPECTED_ENTRIES = 1


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
            for bad_note in ("", "x" * 201, "two\nlines", 7):
                with self.assertRaises(registry.RegistryError) as note:
                    with patch.object(recipe_model, "SYSTEM_INSTRUCTION", recipe_model.SYSTEM_INSTRUCTION + " Two."):
                        registry.register("synthetic-note", bad_note, index_path=index_path)
                self.assertEqual(note.exception.code, "invalid_note")

    def test_wire_only_change_is_registrable_and_the_chain_is_strictly_linear(self):
        with tempfile.TemporaryDirectory(prefix="registry-", dir=ROOT / ".artifacts") as tmp:
            index_path = Path(tmp) / "index.json"
            registry.register("synthetic-root", "root", index_path=index_path, now="2026-09-25T00:00:00Z")
            # A change that alters only the wire (here the witness question set) but no semantic
            # surface must be registrable, because check() enforces the wire witnesses too.
            with patch.object(registry, "WITNESS_QUESTIONS", (registry.WITNESS_QUESTIONS[0],
                                                              ("development_wire", "March 2026 bookings."))):
                with self.assertRaises(registry.RegistryError) as stale:
                    registry.check(index_path)
                self.assertEqual(stale.exception.code, "unregistered_candidate")
                second = registry.register("synthetic-wire", "same semantics, new wire", index_path=index_path,
                                           now="2026-09-25T00:00:01Z")
                root = registry.load_entry("synthetic-root", index_path)
                wire = registry.load_entry("synthetic-wire", index_path)
            self.assertEqual(second["semantic_identity_sha256"], root["semantic_identity_sha256"])
            self.assertNotEqual(wire["candidate_sha256"], root["candidate_sha256"])
            index = json.loads(index_path.read_text())
            self.assertEqual(wire["ancestor_sha256"], index["entries"][0]["sha256"])
            # Rewriting the root in place (entry plus index row) invalidates its descendant.
            root_path = Path(tmp) / "synthetic-root.json"
            rewritten = json.loads(root_path.read_text())
            rewritten["note"] = "rewritten history"
            root_path.write_text(json.dumps(rewritten, indent=2, ensure_ascii=False) + "\n")
            index["entries"][0]["sha256"] = hashlib.sha256(root_path.read_bytes()).hexdigest()
            index_path.write_text(json.dumps(index, indent=2) + "\n")
            with self.assertRaises(registry.RegistryError) as broken:
                registry.load_entry("synthetic-wire", index_path)
            self.assertEqual(broken.exception.code, "registry_drift")
            # Forks, second roots, a path not tied to the id, a reordered chain and a bad row digest are refused.
            original = json.loads(index_path.read_text())

            def fork(i): i["entries"][1]["ancestor"] = None
            def bad_path(i): i["entries"][1]["path"] = "other.json"
            def reorder(i): i["entries"].reverse(); i["current"] = "synthetic-root"
            def bad_sha(i): i["entries"][0]["sha256"] = "0" * 64
            def dangling_current(i): i["entries"].pop()

            for mutate in (fork, bad_path, reorder, bad_sha, dangling_current):
                tampered = json.loads(json.dumps(original))
                mutate(tampered)
                index_path.write_text(json.dumps(tampered) + "\n")
                with self.assertRaises(registry.RegistryError):
                    registry.load_entry(tampered["current"], index_path)
            # Tail truncation with current moved back is self-consistent and NOT detectable by the tool;
            # the anchor is the pinned expectation below plus the documented review blocker.
            truncated = json.loads(json.dumps(original))
            truncated["entries"].pop()
            truncated["current"] = "synthetic-root"
            index_path.write_text(json.dumps(truncated) + "\n")
            self.assertEqual(registry.load_entry("synthetic-root", index_path)["candidate_id"], "synthetic-root")
            index_path.write_text(json.dumps(original) + "\n")
            # A hand-edited note with a control character is rejected on load.
            wire_path = Path(tmp) / "synthetic-wire.json"
            edited = json.loads(wire_path.read_text())
            edited["note"] = "tab\tnote"
            wire_path.write_text(json.dumps(edited, indent=2, ensure_ascii=False) + "\n")
            original["entries"][1]["sha256"] = hashlib.sha256(wire_path.read_bytes()).hexdigest()
            index_path.write_text(json.dumps(original) + "\n")
            with self.assertRaises(registry.RegistryError) as control:
                registry.load_entry("synthetic-wire", index_path)
            self.assertEqual(control.exception.code, "registry_drift")

    def test_registry_expectations_are_pinned(self):
        # The anchor against tail truncation: a registration PR updates these two values consciously.
        index = registry.load_index()
        self.assertEqual(index["current"], EXPECTED_CURRENT)
        self.assertEqual(len(index["entries"]), EXPECTED_ENTRIES)

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
