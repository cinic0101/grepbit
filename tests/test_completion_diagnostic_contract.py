"""Owner-approved diagnostic checkpoint; offline, no credential or model access."""
import contextlib
import io
import json
import unittest
from tools import evaluate


class CompletionDiagnosticContractTests(unittest.TestCase):
    def test_explicit_diagnostic_describes_closed_bounds_without_environment(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = evaluate.main(["--completion-diagnostic", "--describe"])
        self.assertEqual(status, 0, "The approved opt-in diagnostic entry is not implemented")
        self.assertEqual(json.loads(output.getvalue()), {
            "version": "compare-completion-diagnostic-v1",
            "case_ids": ["dev-A3.en", "dev-C2.zh-TW", "dev-C2.en"],
            "candidate_id": "p3-31b-instruction-v3",
            "route_id": "litellm-gemma-4-31b",
            "canonical_call_timeout_seconds": 60,
            "diagnostic_call_timeout_seconds": 90,
            "run_timeout_seconds": 390,
            "max_calls": 3, "max_output_tokens": 2048,
            "raw_text_persisted": False,
            "promotion_eligible": False,
        })


if __name__ == "__main__":
    unittest.main()
