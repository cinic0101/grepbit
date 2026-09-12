"""Test-only disagreement/accounting contract; no live comparator or client."""

import json
from collections import Counter
from copy import deepcopy

import pytest
from t0_helpers import ROOT
from test_metric_selection_ruler import DRAFT, EXPECTED, INSTANCES, PLANS, results

from evals.stability import plan_core

RULER = json.loads((ROOT / "tests/fixtures/cross_language_rulers.json").read_text())


def test_budget_is_bound_to_all_twelve_development_cases():
    cases = [c for c in DRAFT["cases"] if c["split"] == RULER["case_split"]]
    assert len(cases) == len({c["id"] for c in cases}) == RULER["case_count"] == 12
    assert set(Counter(c["family"] for c in cases).values()) == {2}
    assert len({c["family"] for c in cases}) == 6
    assert set(RULER["slots"]) == {"Z1", "Z2", "T", "E"}
    assert len(cases) * len(RULER["slots"]) == RULER["max_attempts"] == 48


@pytest.mark.parametrize("row", RULER["accounting"], ids=lambda r: r["id"])
def test_accounting_ruler_never_certifies_or_credits_unknown_fidelity(row):
    # Specification only; do not import this test function into a live harness.
    different = row["pair"] == "witnessed_difference"
    faithful = row["fidelity"] in {"reference_exact", "human_confirmed"}
    credit = row["original"] == "wrong" and faithful and different
    incremental = credit and row["repeat"] == "equivalent_in_fragment"
    false_alarm = row["original"] == "correct" and different
    assert (credit, incremental, false_alarm) == (
        row["credit"],
        row["incremental"],
        row["false_alarm"],
    )
    assert row["certified"] is False


@pytest.mark.parametrize("row", RULER["equivalence_laws"], ids=lambda r: r["law"])
def test_structural_difference_alone_would_false_flag_known_equivalent_forms(row):
    assert plan_core(PLANS[row["left"]]) != plan_core(PLANS[row["right"]])
    # These named algebra laws justify equality; the values are regression
    # controls, not a proof of equivalence from three coincidental instances.
    assert EXPECTED[row["left"]] == EXPECTED[row["right"]]
    for instance in INSTANCES:
        assert results(row["left"], instance) == results(row["right"], instance)


@pytest.mark.parametrize("row", RULER["witnesses"], ids=lambda r: r["left"])
def test_hand_witness_proves_computational_difference_in_both_engines(row):
    instance_index = list(INSTANCES).index(row["instance"])
    for side in ("left", "right"):
        assert EXPECTED[row[side]][instance_index] == row[f"{side}_value"]
        for output in results(row[side], row["instance"]):
            assert len(output) == 1 and len(output[0]) == 1
            assert float(output[0][0]) == pytest.approx(row[f"{side}_value"])
    assert row["left_value"] != row["right_value"]


def test_no_witness_on_one_instance_is_not_equivalence():
    row = RULER["coincidence"]
    assert results(row["left"], row["instance"]) == results(
        row["right"], row["instance"]
    )
    assert results(row["left"], "asymmetric") != results(row["right"], "asymmetric")


def test_identical_wrong_plans_remain_wrong_against_independent_gold():
    case = next(c for c in DRAFT["cases"] if c["id"] == "output_count_all")
    wrong = "returns_count_metric"
    assert wrong in case["wrong"] and wrong not in case["correct"]
    copy = deepcopy(PLANS[wrong])
    assert plan_core(copy) == plan_core(PLANS[wrong])
    for instance in INSTANCES:
        assert results(wrong, instance) != results(case["correct"][0], instance)


def test_alias_agreement_does_not_establish_requested_output_label():
    case = next(c for c in DRAFT["cases"] if c["id"] == "label_only")
    right = deepcopy(PLANS["all_count"])
    wrong = deepcopy(right)
    right["measures"][0]["alias"] = case["labels"]["zh"]
    wrong["measures"][0]["alias"] = "wrong_label"
    assert plan_core(right) == plan_core(wrong)
    assert right["measures"][0]["alias"] != wrong["measures"][0]["alias"]


def test_missing_pairs_stay_in_accounting_denominator():
    rows = RULER["accounting"]
    available = [r for r in rows if r["pair"] != "unavailable"]
    assert len(rows) == 13 and len(available) == 12
    assert sum(r["credit"] for r in rows) == 4
    assert sum(r["incremental"] for r in rows) == 2
    assert sum(r["false_alarm"] for r in rows) == 2
    assert not any(r["certified"] for r in rows)


@pytest.mark.parametrize("row", RULER["advancement"], ids=lambda r: r["id"])
def test_confirmation_screen_cannot_win_with_missing_correct_controls(row):
    # Proposed screen only, not an implementation or a product release gate.
    may_advance = (
        row["incremental"] >= 1
        and row["correct_controls"] > 0
        and row["comparable_correct"] == row["correct_controls"]
        and row["false_alarms"] == 0
        and row["accounted_slots"] == RULER["case_count"]
        and row["fidelity_unreviewed"] == 0
    )
    assert may_advance is row["may_advance"]
