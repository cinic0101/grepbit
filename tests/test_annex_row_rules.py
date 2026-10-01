"""#161 rulers: the annex verdict follows the graded row it describes (docs/count-assumption.md). Replay's replayed
verdict reads the replayed row and honours its panels registry; the count ablation's verdict reads the graded row.
Offline, synthetic panels and mock transports only."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from grepbit import recipe_model
from tools import count_ablation, evaluate, p3_assets
from test_evaluate import EvaluateHarness
from test_recipe_model import period

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTION = {"count_basis": "booked_seats"}
# The synthetic harness copies p3-development-v1: C01's oracle is a count_basis clarification (history), which the
# current runtime answers; E01 is an Overview answer.
ANSWERED = "C01_count_basis.en"


def count_basis_clarification():
    scope = dict(period(), center_code="CTR-A01")
    choices = [{"type": "count_basis", "scope": dict(scope), "value": v} for v in ("booked_seats", "known_booking_accounts")]
    return evaluate._action_text({"outcome": "clarify", "clarification": {
        "kind": "count_basis", "choices": [{"id": f"c{i}", "semantic_value": v} for i, v in enumerate(choices, 1)]}})


class ReplayAnnexTests(EvaluateHarness):
    async def test_the_replayed_annex_verdict_follows_the_replayed_row(self):
        annex = self.root / "annex.json"
        annex.write_text(json.dumps({"version": "count-assumption-annex-v1",
                                     "expectations": {"E01_overview.v1": ASSUMPTION}}))
        index = json.loads(self.panels.read_text())
        index["panels"][0]["annex"] = {"path": f"{self.relative}/annex.json",
                                       "sha256": hashlib.sha256(annex.read_bytes()).hexdigest()}
        self.panels.write_text(json.dumps(index))
        panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        packet = self.prepare()
        output = self.output()
        await self.run_mock(packet, output, self.bind(packet, output),
                            client=self.litellm_client(scripted=True, cases=panel.cases))
        # A runtime-only change with the same model input: the server no longer answers the clarification.
        with patch.object(recipe_model, "_server_answers", return_value=False):
            replayed = await evaluate.replay(output / "report.json", self.database, self.root / "replay.json",
                                             panels_path=self.panels)
        row = next(item for item in replayed["rows"] if item["case_id"] == ANSWERED)
        self.assertEqual((row["archived"]["actual_action"], row["replayed"]["actual_action"]), ("answer", "clarify"))
        self.assertEqual(row["class"], "replayed_changed")
        # C01 is not listed, so it expects no assumption: the archived answer is frozen-wrong, and the replayed
        # clarification is frozen-correct and states none.
        self.assertEqual(row["annex"], {"archived": "wrong", "replayed": "correct"})


class AblationAnnexTests(unittest.TestCase):
    def test_the_ablation_annex_verdict_follows_the_graded_row(self):
        panel = p3_assets.load_panel(ROOT / "evals/p3/development-panel-v1.json")
        overview = next(case for case in panel.cases if case.case_id == "E01_overview.en")
        clarify = next(case for case in panel.cases if case.case_id == ANSWERED)
        expectations = {overview.oracle_id: ASSUMPTION}
        text = count_basis_clarification()
        # A server answer to the model's count_basis clarification states the assumption (v19, v21).
        self.assertEqual(count_ablation._annex_verdict(
            text, {"outcome": "complete_correct", "actual_action": "answer"}, overview, expectations), "correct")
        # A real clarification row (v18, v20) states none.
        self.assertEqual(count_ablation._annex_verdict(
            text, {"outcome": "correct_clarification", "actual_action": "clarify"}, clarify, expectations), "correct")
        self.assertEqual(count_ablation._annex_verdict(
            text, {"outcome": "complete_correct", "actual_action": "clarify"}, overview, expectations), "wrong")


if __name__ == "__main__":
    unittest.main()
