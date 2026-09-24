"""Specification rulers for the coupled Bedrock wire schema (#77): outcome binds its required fields."""
import json
import unittest

from grepbit import recipe_model
from grepbit.bedrock import converse_schema
from tools import p3_bedrock_candidate_probe as candidate

GRAMMAR_BUDGET_WIRE_SHA256 = "ea4e03d02732c0c45f9905ccd9b7c0010bedc87a190666e7b31895867c43e53b"
GRAMMAR_BUDGET_EFFECTIVE_SHA256 = "4d1f27ded8138dbe9618c6f8c4b32ca4555d8a244ac5e7d94e1287f9de4fb2ed"
PERIOD = {"start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"}
SCOPE = {"metrics": ["confirmed_booked_amount"], **PERIOD}
BASELINE = {"metrics": ["confirmed_booked_amount"], "start": "2026-02-01T00:00:00+08:00",
            "end": "2026-03-01T00:00:00+08:00", "timezone": "Asia/Taipei"}
OVERVIEW = {"center_code": "CTR-A01", **PERIOD}
COMPARE = {"current": SCOPE, "baseline": BASELINE}
# The exact structures the #74 diagnostic observed six times: a clarify signal on a request body.
DIAGNOSTIC_SHAPES = (
    {"outcome": "clarify", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE},
    {"outcome": "clarify", "recipe_id": "overview", "recipe_version": "0.1", "request": OVERVIEW},
)
VALID = (
    {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": OVERVIEW},
    {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": COMPARE},
    {"outcome": "request", "recipe_id": "breakdown", "recipe_version": "0.1", "request": {**PERIOD, "top_k": 2}},
    {"outcome": "declined"},
    {"outcome": "clarify", "clarification": {"kind": "center", "choices": [
        {"id": "a", "semantic_value": {"type": "center", "request": OVERVIEW}},
        {"id": "b", "semantic_value": {"type": "center", "request": {**OVERVIEW, "center_code": "CTR-B01"}}}]}},
)


def admits(schema, value) -> bool:
    """Minimal validator for the closed keyword subset the Bedrock wire uses."""
    if "anyOf" in schema:
        return any(admits(branch, value) for branch in schema["anyOf"])
    if "const" in schema:
        return value == schema["const"]
    if "enum" in schema:
        return value in schema["enum"]
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        if any(name not in value for name in schema.get("required", ())):
            return False
        return all(admits(properties[name], item) for name, item in value.items() if name in properties)
    if kind == "array":
        if not isinstance(value, list) or len(value) < schema.get("minItems", 0):
            return False
        return all(admits(schema["items"], item) for item in value) if "items" in schema else True
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return type(value) is int
    if kind == "null":
        return value is None
    return kind is None


def wire():
    constraint = recipe_model._structured_output(recipe_model.output_schema())[0]
    wire_format, wire_hash = converse_schema(constraint)
    return json.loads(wire_format["structure"]["jsonSchema"]["schema"]), wire_hash


class BedrockWireCouplingRulers(unittest.TestCase):
    def test_root_branches_couple_outcome_to_required_fields(self):
        schema, _ = wire()
        self.assertEqual(set(schema), {"anyOf"})
        branches = schema["anyOf"]
        self.assertEqual(len(branches), 5)
        outcomes = []
        for branch in branches:
            self.assertEqual(branch["type"], "object")
            self.assertIs(branch["additionalProperties"], False)
            self.assertIn("outcome", branch["required"])
            outcomes.append(branch["properties"]["outcome"]["const"])
        self.assertEqual(sorted(outcomes), ["clarify", "declined", "request", "request", "request"])
        for branch in branches:
            outcome = branch["properties"]["outcome"]["const"]
            if outcome == "request":
                self.assertEqual(set(branch["required"]), {"outcome", "recipe_id", "recipe_version", "request"})
                self.assertEqual(set(branch["properties"]), {"outcome", "recipe_id", "recipe_version", "request"})
                self.assertIn(branch["properties"]["recipe_id"]["const"], ("overview", "compare", "breakdown"))
                self.assertEqual(branch["properties"]["recipe_version"]["const"], "0.1")
                self.assertNotIn("anyOf", branch["properties"]["request"])
            elif outcome == "declined":
                self.assertEqual(set(branch["properties"]), {"outcome"})
            else:
                self.assertEqual(set(branch["required"]), {"outcome", "clarification"})
                self.assertEqual(set(branch["properties"]), {"outcome", "clarification"})
                clarification = branch["properties"]["clarification"]
                self.assertNotIn("anyOf", clarification)
                self.assertEqual(set(clarification["properties"]["kind"]["enum"]),
                                 {"count_basis", "comparison_roles", "center", "metric_meaning"})
                self.assertEqual(clarification["properties"]["choices"]["minItems"], 1)
                self.assertEqual(len(clarification["properties"]["choices"]["items"]
                                     ["properties"]["semantic_value"]["anyOf"]), 4)
        self.assertNotIn('"description"', json.dumps(schema))

    def test_recipe_id_is_bound_to_its_own_request_shape(self):
        schema, _ = wire()
        shapes = {branch["properties"]["recipe_id"]["const"]: branch["properties"]["request"]
                  for branch in schema["anyOf"] if branch["properties"]["outcome"]["const"] == "request"}
        self.assertEqual(set(shapes["overview"]["required"]), {"center_code", "start", "end", "timezone"})
        self.assertEqual(set(shapes["compare"]["required"]), {"current", "baseline"})
        self.assertEqual(set(shapes["breakdown"]["required"]), {"start", "end", "timezone", "top_k"})
        self.assertFalse(admits(schema, {"outcome": "request", "recipe_id": "compare",
                                         "recipe_version": "0.1", "request": OVERVIEW}))

    def test_wire_rejects_the_diagnostic_shapes_and_admits_the_contract(self):
        schema, wire_hash = wire()
        for shape in DIAGNOSTIC_SHAPES:
            with self.subTest(recipe=shape["recipe_id"]):
                self.assertFalse(admits(schema, shape))
        for value in VALID:
            with self.subTest(outcome=value["outcome"], recipe=value.get("recipe_id")):
                self.assertTrue(admits(schema, value))
        for bad in ({"outcome": "clarify"}, {"outcome": "request"}, {"outcome": "declined", "request": OVERVIEW},
                    {"outcome": "clarify", "clarification": {"kind": "center", "choices": []}},
                    {"outcome": "other"}, {}):
            with self.subTest(bad=json.dumps(bad)[:40]):
                self.assertFalse(admits(schema, bad))
        self.assertNotEqual(wire_hash, GRAMMAR_BUDGET_WIRE_SHA256)
        self.assertLess(len(json.dumps(schema, separators=(",", ":")).encode()), 5000)

    def test_the_v4_wire_admitted_the_diagnostic_shapes(self):
        """Documents the defect: the historical flattened root accepted a clarify signal on a request body."""
        from grepbit.bedrock import _compact_recipe_schema, _schema_node
        translated = _schema_node(recipe_model.output_schema())
        v4_like = {"type": "object", "additionalProperties": False, "required": ["outcome"], "properties": {
            "outcome": {"enum": ["request", "clarify", "declined"]},
            "recipe_id": {"enum": ["overview", "compare", "breakdown"]}, "recipe_version": {"const": "0.1"},
            "request": {"anyOf": [branch["properties"]["request"] for branch in translated["anyOf"][:3]]},
            "clarification": {"type": "object"}}}
        for shape in DIAGNOSTIC_SHAPES:
            self.assertTrue(admits(v4_like, shape))
        self.assertTrue(callable(_compact_recipe_schema))

    def test_new_identities_keep_the_v4_witness_readable(self):
        self.assertEqual(candidate.PACKET_VERSION, "p3-bedrock-candidate-packet-v5")
        self.assertEqual(candidate.GRAMMAR_BUDGET_PACKET_VERSION, "p3-bedrock-candidate-packet-v4")
        self.assertEqual(candidate.EFFECTIVE_RUNTIME_VERSION, "p3-bedrock-effective-runtime-v4")
        self.assertEqual(candidate.GRAMMAR_BUDGET_WIRE_SCHEMA_SHA256, GRAMMAR_BUDGET_WIRE_SHA256)
        self.assertEqual(candidate.GRAMMAR_BUDGET_EFFECTIVE_RUNTIME_SHA256, GRAMMAR_BUDGET_EFFECTIVE_SHA256)
        self.assertNotEqual(candidate.WIRE_SCHEMA_SHA256, GRAMMAR_BUDGET_WIRE_SHA256)
        self.assertNotEqual(candidate.EFFECTIVE_RUNTIME_SHA256, GRAMMAR_BUDGET_EFFECTIVE_SHA256)
        _, wire_hash = wire()
        self.assertEqual(wire_hash, candidate.WIRE_SCHEMA_SHA256)
        baseline = candidate.semantic.semantic_identity()
        current = candidate.effective_runtime_identity(baseline)
        self.assertEqual(current["wire_schema_sha256"], candidate.WIRE_SCHEMA_SHA256)
        self.assertEqual(candidate.assets.digest(current), candidate.EFFECTIVE_RUNTIME_SHA256)
        previous = candidate.effective_runtime_identity(baseline, packet_version=candidate.GRAMMAR_BUDGET_PACKET_VERSION)
        self.assertEqual(previous["wire_schema_sha256"], GRAMMAR_BUDGET_WIRE_SHA256)
        self.assertEqual(candidate.assets.digest(previous), GRAMMAR_BUDGET_EFFECTIVE_SHA256)


if __name__ == "__main__":
    unittest.main()
