"""Three-run baseline rulers (#168, docs/candidate-gate.md v3): offline, synthetic reports only."""
import unittest

from tools import evaluate


def report(outcome, *, correct, status="completed"):
    """One synthetic single-input report, enough for the class rule."""
    row = {"case_id": "X1.en", "family_id": "X1", "status": status, "outcome": outcome, "actual_action": "answer",
           "actual_signature": None, "validated_action": None, "operational_error": None, "runner_error_code": None}
    return {"results": [row], "summary": {"per_input": [{"correct": correct}]}}


RIGHT = ("complete_correct", True)
WRONG = ("false_refusal", False)
DOWN = ("operational_failure", False)


def classed(*runs):
    reports = [report(outcome, correct=correct, status="not_completed" if outcome == "operational_failure"
                      else "completed") for outcome, correct in runs]
    return evaluate._input_classes(reports)[0]["class"]


class ClassRuleTests(unittest.TestCase):
    def test_a_stable_class_needs_three_assessed_runs(self):
        self.assertEqual(evaluate.STABLE_MIN_ASSESSED, 3)
        self.assertEqual(classed(RIGHT, RIGHT), "insufficient")
        self.assertEqual(classed(WRONG, WRONG), "insufficient")
        self.assertEqual(classed(RIGHT, RIGHT, RIGHT), "stable_correct")
        self.assertEqual(classed(WRONG, WRONG, WRONG), "stable_wrong")
        # An unassessed run does not count towards the three.
        self.assertEqual(classed(RIGHT, RIGHT, DOWN), "insufficient")
        self.assertEqual(classed(RIGHT, RIGHT, DOWN, RIGHT), "stable_correct")
        # No assessed run at all is never a class to break or fix.
        self.assertEqual(classed(DOWN, DOWN, DOWN), "insufficient")

    def test_one_right_and_one_wrong_is_flaky_at_any_count(self):
        self.assertEqual(classed(RIGHT, WRONG), "flaky")
        self.assertEqual(classed(RIGHT, RIGHT, WRONG), "flaky")
        self.assertEqual(classed(RIGHT), "insufficient")

    def test_the_gate_excludes_what_the_baseline_cannot_class(self):
        # dev-BM2.en's case (#162, #167): two correct baseline runs are no longer a stable class to break.
        self.assertEqual(evaluate._gate_class("insufficient", "wrong", True), "excluded")
        self.assertEqual(evaluate._gate_class("insufficient", "correct", True), "excluded")
        self.assertEqual(evaluate._gate_class("stable_correct", "wrong", True), "broke")

    def test_the_gate_and_aggregate_contracts_are_versioned(self):
        self.assertEqual((evaluate.GATE_VERSION, evaluate.AGGREGATE_VERSION),
                         ("evaluation-gate-v3", "evaluation-aggregate-v3"))


if __name__ == "__main__":
    unittest.main()
