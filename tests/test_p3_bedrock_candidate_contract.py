"""Specification rulers retained after the owner-approved #64 implementation."""
from importlib import import_module
from pathlib import Path
import unittest

from grepbit import recipe_model
from grepbit.bedrock import BedrockConfig, converse_schema


ROOT = Path(__file__).resolve().parents[1]
MODEL = "jp.anthropic.claude-sonnet-4-6"
REGION = "ap-northeast-1"
WIRE_HASH = "d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f"


class JPBedrockCandidateContract(unittest.TestCase):
    def test_existing_adapter_route_and_schema_identity(self):
        config = BedrockConfig(REGION, MODEL, "placeholder")
        self.assertEqual(config.model, MODEL)
        self.assertEqual(config.region, REGION)
        self.assertIsNone(config.expected_model)
        constraint = recipe_model._structured_output(recipe_model.output_schema())[0]
        self.assertEqual(converse_schema(constraint)[1], WIRE_HASH)

    def test_purpose_specific_candidate_runner_is_required(self):
        # A static ruler is intentional: no model or credential is available in
        # the specification phase, and a fake successful call would not prove
        # that a governed Bedrock candidate packet/authorization exists.
        path = ROOT / "tools/p3_bedrock_candidate_probe.py"
        self.assertTrue(path.is_file(), "Bedrock candidate admission/runner is absent")
        module = import_module("tools.p3_bedrock_candidate_probe")
        for name in ("build_packet", "validate_packet", "bind_authorization",
                     "run_probe", "read_report"):
            self.assertTrue(callable(getattr(module, name, None)), name)


if __name__ == "__main__":
    unittest.main()
