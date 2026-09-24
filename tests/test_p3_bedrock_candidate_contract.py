"""Specification rulers retained after the owner-approved #64 implementation."""
from importlib import import_module
from pathlib import Path
import unittest

from grepbit import recipe_model
from grepbit.bedrock import BedrockConfig, converse_schema
from tools import p3_bedrock_candidate_probe as candidate, p3_probe as legacy


ROOT = Path(__file__).resolve().parents[1]
MODEL = "jp.anthropic.claude-sonnet-4-6"
REGION = "ap-northeast-1"
WIRE_HASH = "0bd5db7c524215ba7e76a1423579510e8000efda80004dc7b17ce265d517efef"  # v6b two-branch wire (#77)


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

    def test_cold_schema_timeout_budget_is_one_contract(self):
        baseline = candidate.semantic.semantic_identity()
        self.assertEqual(baseline["limits"]["timeout"], 60)
        effective = candidate.effective_runtime_identity(baseline)
        self.assertEqual(effective["limits"]["timeout"], 300)
        self.assertEqual(effective["baseline_semantic_identity_sha256"],
                         candidate.semantic.SEMANTICS_SHA256)
        self.assertEqual(candidate.settings()["call_timeout_seconds"], 300)
        self.assertEqual(candidate.settings()["publication_budget_seconds"], 420)
        self.assertEqual(BedrockConfig(REGION, MODEL, "placeholder").max_call_timeout_seconds, 300)
        self.assertEqual(effective["limits"]["timeout"], candidate.settings()["call_timeout_seconds"])
        self.assertEqual(candidate._BedrockProbe(None, None, None, None).budgets(), (300, 420))
        self.assertEqual(legacy._LegacyProbe(None, None).budgets(), (60, 180))


if __name__ == "__main__":
    unittest.main()
