"""Recorded count assumption rulers (docs/recorded-count-assumption.md, #169 step A1): offline, synthetic only."""
import hashlib
import json
from unittest.mock import patch

from grepbit import model, recipe_model
from tools import evaluate, p3_assets, p3_live_evidence as live
from test_evaluate import EvaluateHarness
from test_recipe_model import period

import narrow_assumption
import unittest

ASSUMPTION = {"count_basis": "booked_seats"}
STATEMENT = {"count_basis": "booked_seats", "reported_as": "confirmed booked seats",
             "unavailable": ["known_booking_accounts", "attendance_visits", "distinct_people"]}


def policy_a(action, actual_action):
    """Policy A's statement (#169, v22): every answered Overview, and v19's server answer to a model count_basis
    clarification."""
    if actual_action != "answer" or not isinstance(action, dict):
        return None
    if evaluate._count_basis_clarification(action):
        return dict(ASSUMPTION)
    return dict(ASSUMPTION) if action.get("outcome") == "request" and action.get("recipe_id") == "overview" else None


def overview(count_request):
    return evaluate._action_text({"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                                  "request": dict(period(), center_code="CTR-A01"), "count_request": count_request})


class ProjectionTests(unittest.TestCase):
    def test_the_projection_keeps_only_the_archived_statement_or_null(self):
        self.assertEqual(live.ARCHIVED_COUNT_ASSUMPTION, STATEMENT)
        self.assertEqual(live._evidence({"count_assumption": STATEMENT})["count_assumption"], STATEMENT)
        self.assertIsNone(live._evidence({"count_assumption": None})["count_assumption"])
        self.assertNotIn("count_assumption", live._evidence({}))
        with self.assertRaises(p3_assets.P3Error):
            live._evidence({"count_assumption": STATEMENT, "error_code": "kernel_failure"})
        self.assertIsNone(live._evidence({"count_assumption": None, "error_code": "kernel_failure"})["count_assumption"])
        for bad in ({"count_basis": "distinct_people"}, dict(STATEMENT, reported_as="people"), "booked_seats", []):
            with self.subTest(bad=bad), self.assertRaises(p3_assets.P3Error):
                live._evidence({"count_assumption": bad})


class VerdictTests(unittest.TestCase):
    def verdict(self, action, evidence):
        row = {"oracle_id": "o.v1", "validated_action": action, "actual_action": "answer"}
        if evidence is not None:
            row["evidence"] = evidence
        return evaluate.annexed(row, True, {"o.v1": ASSUMPTION})

    def test_the_recorded_statement_wins_over_the_derivation_both_ways(self):
        self.assertEqual(self.verdict(overview("none"), {"count_assumption": STATEMENT}), "correct")
        self.assertEqual(self.verdict(overview("unresolved"), {"count_assumption": None}), "wrong")
        # Without the key, the derivation from the action stays.
        self.assertEqual(self.verdict(overview("unresolved"), {"stages": {}}), "correct")
        self.assertEqual(self.verdict(overview("none"), None), "wrong")


class LiveAndReplayTests(EvaluateHarness):
    def annex(self):
        annex = self.root / "annex.json"
        annex.write_text(json.dumps({"version": "count-assumption-annex-v1",
                                     "expectations": {"E01_overview.v1": ASSUMPTION}}))
        index = json.loads(self.panels.read_text())
        index["panels"][0]["annex"] = {"path": f"{self.relative}/annex.json",
                                       "sha256": hashlib.sha256(annex.read_bytes()).hexdigest()}
        self.panels.write_text(json.dumps(index))

    async def run_once(self):
        panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        packet = self.prepare()
        output = self.output()
        await self.run_mock(packet, output, self.bind(packet, output),
                            client=self.litellm_client(scripted=True, cases=panel.cases))
        return output

    async def test_the_live_path_records_the_statement_the_registered_rule_expects(self):
        # The archived pin equals the runtime's statement (the archived-vocabulary rule, docs/count-cue-policy.md).
        self.assertEqual(recipe_model.ASSUMPTION_STATEMENT, live.ARCHIVED_COUNT_ASSUMPTION)
        output = await self.run_once()
        report = evaluate.read_report(output / "report.json")
        self.assertEqual(report["status"], "complete")
        # Before policy A the recorded statement equals the evaluator's derivation; once v22 is registered every
        # answered Overview records it, where the derivation would miss the none and booked_seats readings. The rule
        # comes from the registry, never from the runtime under test.
        derive = policy_a if narrow_assumption.policy_a_registered() else evaluate._stated_assumption
        stated = 0
        for row in report["results"]:
            self.assertIsNotNone(row["evidence"], row["case_id"])
            self.assertIn("count_assumption", row["evidence"], row["case_id"])
            if row["validated_action"] is None:
                continue
            # Every completed row, frozen-correct or not: the recorded statement equals the rule's. A row that
            # answered and then failed states none under either rule (the runtime records it only without an error).
            recorded = row["evidence"]["count_assumption"]
            derived = (None if row["evidence"].get("error_code") else
                       derive(model.strict_json(row["validated_action"]), row["actual_action"]))
            self.assertEqual({"count_basis": recorded["count_basis"]} if recorded else None, derived, row["case_id"])
            stated += recorded is not None
        # The server answer to the scripted C01 count_basis clarification states the assumption.
        self.assertGreater(stated, 0)

    async def test_replay_reads_the_replayed_runs_statement(self):
        self.annex()
        output = await self.run_once()
        # A runtime that states the assumption on every Overview, as policy A does (#169, v22).
        every_overview = property(lambda proposal: dict(recipe_model.ASSUMPTION)
                                  if proposal.recipe_id == "overview" else None)
        # Replay under the rule the registry says the live runtime does not use, so the statement flips under either.
        narrow = not narrow_assumption.policy_a_registered()
        flipped = every_overview if narrow else property(narrow_assumption.narrow)
        with patch.object(recipe_model.RecipeProposal, "assumption", flipped):
            replayed = await evaluate.replay(output / "report.json", self.database, self.root / "replay.json",
                                             panels_path=self.panels)
        row = next(item for item in replayed["rows"] if item["case_id"] == "E01_overview.en")
        self.assertEqual(row["class"], "replayed_changed")
        # E01 expects the assumption: the run that states it is correct, the one that states none is wrong.
        self.assertEqual(row["annex"], {"archived": "wrong", "replayed": "correct"} if narrow else
                         {"archived": "correct", "replayed": "wrong"})
        # A replayed statement is validated like an archived one: a wrong shape fails.
        drifted = dict(recipe_model.ASSUMPTION_STATEMENT, reported_as="people")
        with patch.object(recipe_model, "ASSUMPTION_STATEMENT", drifted), \
                patch.object(recipe_model.RecipeProposal, "assumption", every_overview), \
                self.assertRaises(p3_assets.P3Error) as refused:
            await evaluate.replay(output / "report.json", self.database, self.root / "replay-drift.json",
                                  panels_path=self.panels)
        self.assertEqual(refused.exception.code, "invalid_asset")


if __name__ == "__main__":
    unittest.main()
