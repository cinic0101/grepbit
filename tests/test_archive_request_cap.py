"""Regression for #122: the v11 cap change must not break read-back of pre-v11 archives.

Every packet prepared before the v11 merge records ``max_request_bytes`` 32,768. Owner decision A on
#122 records the cap per candidate: the evaluation settings carry a known cap, historical readers
validate at the historical cap, and v11 alone uses 40,960. After the v12 fallback (#79) new manifests
follow the gateway's 32,768 again; 40,960 stays a known cap so v11 archives read back. Offline only.
"""
import unittest

from grepbit import gateway
from tools import p3_assets, p3_eval
from tools.history import (p3_bedrock_observed_regression, p3_candidate_regression, p3_dev_regression,
                           p3_formal_run, p3_holdout_run, p3_stability_run)


class ArchiveRequestCapTests(unittest.TestCase):
    def test_evaluation_settings_carry_exactly_the_known_caps(self):
        self.assertEqual(p3_eval.HISTORICAL_MAX_REQUEST_BYTES, 32768)
        self.assertEqual(p3_eval.REQUEST_CAPS, (32768, 40960))
        self.assertEqual(p3_eval.MAX_REQUEST_BYTES, gateway.MAX_REQUEST_BYTES)
        self.assertEqual(p3_eval.settings(1)["max_request_bytes"], gateway.MAX_REQUEST_BYTES)
        for cap in p3_eval.REQUEST_CAPS:
            self.assertEqual(p3_eval.settings(1, max_request_bytes=cap),
                             {**p3_eval.settings(1), "max_request_bytes": cap})
        for cap in (32767, 36000, 40961, 65536, "40960", None, True):
            with self.subTest(cap=cap), self.assertRaises(p3_assets.P3Error) as raised:
                p3_eval.settings(1, max_request_bytes=cap)
            self.assertEqual(raised.exception.code, "invalid_manifest")

    def test_recorded_settings_match_only_at_a_known_cap(self):
        for cap in p3_eval.REQUEST_CAPS:
            self.assertTrue(p3_eval.recorded_settings(p3_eval.settings(9, max_request_bytes=cap), 9))
        current = p3_eval.settings(9)
        for value in ({**current, "max_request_bytes": 36000}, {**current, "max_request_bytes": "40960"},
                      {**current, "inputs": 8}, {k: v for k, v in current.items() if k != "max_request_bytes"},
                      [], None):
            with self.subTest(value=value):
                self.assertFalse(p3_eval.recorded_settings(value, 9))

    def test_historical_readers_validate_at_the_historical_cap(self):
        """Their archives all predate v11; they are readers, not the entry for new runs."""
        for module in (p3_formal_run, p3_holdout_run, p3_dev_regression, p3_stability_run,
                       p3_candidate_regression, p3_bedrock_observed_regression):
            with self.subTest(reader=module.__name__):
                self.assertEqual(module.settings()["max_request_bytes"], 32768)


if __name__ == "__main__":
    unittest.main()
