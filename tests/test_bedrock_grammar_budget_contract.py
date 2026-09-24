"""Specification rulers for the observed Bedrock compiled-grammar rejection."""
import json
import unittest

from grepbit import recipe_model
from grepbit.bedrock import converse_schema
from grepbit.clarification import Clarification
from grepbit.contracts import KernelError
from grepbit.gateway import ModelError
from tools import p3_bedrock_candidate_probe as candidate


OLD_WIRE_SHA256 = "93ab99c9162a43412d0588b3ded70cc41a25827582b4d11b8072e3348d201f68"


class BedrockGrammarBudgetContract(unittest.TestCase):
    def test_pinned_recipe_wire_has_compact_action_and_clarification_shapes(self):
        canonical_before = recipe_model.structured_output_identity()
        constraint = recipe_model._structured_output(recipe_model.output_schema())[0]
        wire_format, wire_hash = converse_schema(constraint)
        wire = json.loads(wire_format["structure"]["jsonSchema"]["schema"])

        # v6b (#77) keeps a two-branch coupled root; the flattened clarification from v4 stays.
        self.assertEqual(set(wire), {"anyOf"})
        self.assertEqual(len(wire["anyOf"]), 2)
        clarify = [branch for branch in wire["anyOf"] if branch["properties"]["outcome"].get("const") == "clarify"]
        self.assertEqual(len(clarify), 1)
        clarification = clarify[0]["properties"]["clarification"]
        self.assertNotIn("anyOf", clarification)
        self.assertEqual(len(clarification["properties"]["choices"]["items"]
                             ["properties"]["semantic_value"]["anyOf"]), 4)
        self.assertNotIn('"description"', json.dumps(wire))
        self.assertLess(len(json.dumps(wire, separators=(",", ":")).encode()), 5000)
        self.assertNotEqual(wire_hash, OLD_WIRE_SHA256)
        self.assertEqual(recipe_model.structured_output_identity(), canonical_before)

    def test_named_recipe_schema_drift_fails_closed_and_unrelated_schema_stays_generic(self):
        changed = recipe_model.output_schema()
        changed["oneOf"][0]["properties"]["outcome"] = {"const": "different"}
        with self.assertRaises(ModelError) as caught:
            converse_schema({"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME,
                             "schema": changed})
        self.assertEqual(caught.exception.code, "invalid_input")
        generic, _ = converse_schema({"name": "unrelated_schema", "schema": {
            "type": "object", "additionalProperties": False,
            "required": ["value"], "properties": {"value": {"type": "string"}},
        }})
        self.assertEqual(json.loads(generic["structure"]["jsonSchema"]["schema"]), {
            "type": "object", "additionalProperties": False,
            "required": ["value"], "properties": {"value": {"type": "string"}},
        })

    def test_native_rejects_wire_permitted_recipe_shape_mismatch(self):
        with self.assertRaises(ModelError) as caught:
            recipe_model._proposal({
                "outcome": "request", "recipe_id": "compare", "recipe_version": "0.1",
                "request": {"center_code": "CTR-001", "start": "2025-03-01T00:00:00+08:00",
                            "end": "2025-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"},
            })
        self.assertEqual(caught.exception.code, "invalid_request")

    def test_native_rejects_wire_permitted_clarification_kind_mismatch(self):
        scope = {"center_code": "CTR-001", "start": "2025-03-01T00:00:00+08:00",
                 "end": "2025-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"}
        with self.assertRaises(KernelError) as caught:
            Clarification.from_mapping({"kind": "count_basis", "choices": [
                {"id": "a", "semantic_value": {"type": "center", "request": scope}},
                {"id": "b", "semantic_value": {"type": "center", "request": {
                    **scope, "center_code": "CTR-002"}}},
            ]})
        self.assertEqual(caught.exception.code, "invalid_request")

    def test_new_wire_has_distinct_packet_and_effective_runtime_identity(self):
        self.assertEqual(candidate.GRAMMAR_BUDGET_PACKET_VERSION, "p3-bedrock-candidate-packet-v4")
        self.assertEqual(candidate.GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_VERSION, "p3-bedrock-effective-runtime-v3")
        self.assertNotEqual(candidate.GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256, OLD_WIRE_SHA256)
        self.assertNotEqual(candidate.WIRE_SCHEMA_SHA256, OLD_WIRE_SHA256)
        budget = candidate.effective_runtime_identity(candidate.semantic.semantic_identity(),
                                                      packet_version=candidate.GRAMMAR_BUDGET_PACKET_VERSION)
        self.assertEqual(budget["wire_schema_sha256"], candidate.GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256)
        self.assertEqual(candidate.assets.digest(budget), candidate.GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_SHA256)
        effective = candidate.effective_runtime_identity(candidate.semantic.semantic_identity())
        self.assertEqual(effective["wire_schema_sha256"], candidate.WIRE_SCHEMA_SHA256)
        self.assertEqual(candidate.assets.digest(effective), candidate.EFFECTIVE_RUNTIME_SHA256)


if __name__ == "__main__":
    unittest.main()
