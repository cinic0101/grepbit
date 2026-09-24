"""Rulers for the Bedrock complex-const rejection observed in #64."""
import json
import unittest

from grepbit import recipe_model
from grepbit.bedrock import converse_schema
from grepbit.gateway import ModelError
from tools import p3_bedrock_candidate_probe as candidate


OLD_WIRE_SHA256 = "d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f"


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


class BedrockComplexConstContract(unittest.TestCase):
    def test_recipe_wire_replaces_only_four_singleton_array_consts(self):
        canonical = recipe_model.output_schema()
        canonical_hash = recipe_model.structured_output_identity()["schema_sha256"]
        self.assertEqual(canonical_hash, candidate.CANONICAL_SCHEMA_SHA256)
        constraint = recipe_model._structured_output(canonical)[0]
        format_value, wire_hash = converse_schema(constraint)
        wire = json.loads(format_value["structure"]["jsonSchema"]["schema"])
        self.assertEqual(sum(node.get("const") == ["confirmed_booked_amount"]
                             for node in nodes(canonical)), 4)
        self.assertFalse(any(isinstance(node.get("const"), (list, dict)) for node in nodes(wire)))
        self.assertEqual(sum(node.get("type") == "array" and node.get("minItems") == 1
                             and node.get("items") == {"const": "confirmed_booked_amount"}
                             for node in nodes(wire)), 4)
        self.assertNotEqual(wire_hash, OLD_WIRE_SHA256)
        self.assertEqual(recipe_model.structured_output_identity()["schema_sha256"], canonical_hash)

    def test_other_complex_consts_fail_before_wire_serialization(self):
        for value in ({"a": 1}, ["a", "b"], []):
            with self.subTest(value=value):
                with self.assertRaises(ModelError) as caught:
                    converse_schema({"name": "closed_test", "schema": {"const": value}})
                self.assertEqual(caught.exception.code, "invalid_input")

    def test_new_packet_identity_keeps_old_wire_hash_as_ancestry_only(self):
        self.assertEqual(candidate.LEGACY_PACKET_VERSION, "p3-bedrock-candidate-packet-v1")
        self.assertEqual(candidate.COMPLEX_CONST_PACKET_VERSION, "p3-bedrock-candidate-packet-v3")
        self.assertNotEqual(candidate.PREVIOUS_WIRE_SCHEMA_SHA256, OLD_WIRE_SHA256)
        effective = candidate.effective_runtime_identity(
            candidate.semantic.semantic_identity(), packet_version=candidate.COMPLEX_CONST_PACKET_VERSION)
        self.assertEqual(effective["wire_schema_sha256"], candidate.PREVIOUS_WIRE_SCHEMA_SHA256)
        self.assertEqual(candidate.assets.digest(effective), candidate.PREVIOUS_EFFECTIVE_RUNTIME_SHA256)


if __name__ == "__main__":
    unittest.main()
