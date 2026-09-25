"""Holdout A allocation policy rulers (#79): metadata only, no payloads, no model calls."""
import copy
import unittest
from unittest.mock import patch

from tools import p3_assets, p3_formal_policy as policy

LANGUAGES = ("zh-TW", "en", "ja")
V2_SHA256 = "58b47dff3e2f"  # prefix of the archived p370 allocation identity; must not move


def holdout_scaffolding(families=((("answer", 1), ("clarify", 3), ("decline", 2)))):
    """Synthetic metadata in the holdout shape; never real holdout questions."""
    rows, order = [], 0
    for cohort, count in families:
        for index in range(count):
            family = f"synthetic-holdout-{cohort}-{index}"
            for language in LANGUAGES:
                order += 1
                rows.append({"order": order, "case_id": f"{family}.{language}", "family_id": family,
                             "language": language, "expected_branch": cohort, "cohort": cohort,
                             "exposure": "frozen_fresh", "must_pass": True, "observational": False,
                             "semantic_signature": f"{cohort}|synthetic|{index}", "oracle_id": f"{family}.v1"})
    return rows


def successes(rows):
    outcome = {"answer": "complete_correct", "clarify": "correct_clarification", "decline": "correct_decline"}
    return [{"case_id": row["case_id"], "status": "completed", "outcome": outcome[row["cohort"]],
             "actual_signature": "a" * 64, "checked_wrong": False} for row in rows]


class HoldoutPolicyTests(unittest.TestCase):
    def setUp(self):
        for target in ("tools.p3_assets.read_asset", "socket.socket.connect", "socket.getaddrinfo",
                       "sqlite3.connect", "grepbit.gateway.GatewayClient.complete"):
            guard = patch(target, side_effect=AssertionError("Metadata policy must not read payloads or execute"))
            guard.start()
            self.addCleanup(guard.stop)

    def test_holdout_identity_is_new_and_historical_identities_are_unchanged(self):
        self.assertEqual(policy.HOLDOUT_A, "p3-holdout-a-allocation-v2")
        self.assertIn(policy.HOLDOUT_A, policy.VERSIONS)
        self.assertEqual(policy.HOLDOUT_VERSIONS, (policy.HOLDOUT_A,))
        self.assertTrue(policy.identity(policy.V2)["sha256"].startswith(V2_SHA256))
        self.assertNotEqual(policy.identity(policy.HOLDOUT_A)["sha256"], policy.identity(policy.V2)["sha256"])
        self.assertEqual(policy.validate_identity(policy.identity(policy.HOLDOUT_A)), policy.HOLDOUT_A)

    def test_holdout_allocation_is_exactly_six_fresh_families_in_three_languages(self):
        rows = holdout_scaffolding()
        policy.validate_allocation(rows, policy.HOLDOUT_A)
        for name, mutate in (
            ("missing_family", lambda r: [x for x in r if x["family_id"] != "synthetic-holdout-decline-1"]),
            ("v1_shape", lambda r: holdout_scaffolding(((("answer", 2), ("clarify", 3), ("decline", 2))))),
            ("exposed_family", lambda r: [{**x, "exposure": "exposed_regression"} if x["family_id"].endswith("answer-0") else x for x in r]),
            ("missing_language", lambda r: [x for x in r if not (x["family_id"].endswith("clarify-2") and x["language"] == "ja")]),
            ("observational", lambda r: [{**x, "observational": True} if x["order"] == 1 else x for x in r]),
            ("anchor_cohort", lambda r: [{**x, "cohort": "anchor"} if x["family_id"].endswith("decline-0") else x for x in r]),
            ("wrong_shape", lambda r: holdout_scaffolding(((("answer", 2), ("clarify", 3), ("decline", 2))))),
        ):
            with self.subTest(mutation=name), self.assertRaises(p3_assets.P3Error):
                policy.validate_allocation(mutate(copy.deepcopy(rows)), policy.HOLDOUT_A)
        with self.assertRaises(p3_assets.P3Error):
            policy.validate_allocation(rows, policy.V2)

    def test_holdout_summary_is_family_weighted_and_never_promotion_eligible(self):
        rows = holdout_scaffolding()
        identity = policy.identity(policy.HOLDOUT_A)
        summary = policy.summarize(rows, successes(rows), panel_kind="holdout", run_status="complete",
                                   allocation_policy=identity)
        self.assertEqual(summary["panel_kind"], "holdout")
        self.assertEqual(summary["allocation_policy"], identity)
        self.assertFalse(summary["promotion"]["eligible"])
        self.assertFalse(summary["promotion"]["passed"])
        self.assertEqual(summary["outcomes"]["complete_correct"], 3)
        self.assertEqual(summary["outcomes"]["correct_clarification"], 9)
        self.assertEqual(summary["outcomes"]["correct_decline"], 6)
        # The frozen holdout panel carries the formal asset format; the summary still says holdout.
        formal_labelled = policy.summarize(rows, successes(rows), panel_kind="formal", run_status="complete",
                                           allocation_policy=identity)
        self.assertEqual(formal_labelled["panel_kind"], "holdout")
        self.assertFalse(formal_labelled["promotion"]["eligible"])
        with self.assertRaises(p3_assets.P3Error):
            policy.summarize(rows, successes(rows), panel_kind="development", run_status="complete",
                             allocation_policy=identity)
        # A formal V2 summary must not be reachable with the holdout shape either.
        with self.assertRaises(p3_assets.P3Error):
            policy.summarize(rows, successes(rows), panel_kind="formal", run_status="complete",
                             allocation_policy=policy.identity(policy.V2))


if __name__ == "__main__":
    unittest.main()
