"""Approved name-binding boundaries; fictional data, no remote services."""

import pytest
from test_negative_name_grounding_ruler import FULL, Harness, occurrence, proposal

from grepbit.application.grounding import ValueIndex
from grepbit.domain.plan import FilterOp

PATHS = ["measure", "numerator", "denominator", "without"]


@pytest.mark.parametrize("path", PATHS)
def test_proposed_nested_positive_binding_keeps_scope(path):
    plan = proposal(path)
    occurrence(plan, path).op = FilterOp.EQ
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL]
    assert occurrence(result.plan, path).op is FilterOp.EQ
    assert len(h.compilations) >= 2 and len(h.policies) >= 2


@pytest.mark.parametrize("path", PATHS)
def test_proposed_missing_nested_positive_name_clarifies(path):
    plan = proposal(path, "ZZZZ9999")
    occurrence(plan, path).op = FilterOp.IN
    h = Harness(plan)
    result = h.run()
    assert (result.status, result.reason) == ("clarify", "filter_value_not_found")
    assert h.executions == 0


@pytest.mark.parametrize("path", PATHS)
def test_exact_nested_positive_control(path):
    plan = proposal(path, FULL)
    occurrence(plan, path).op = FilterOp.EQ
    result = Harness(plan).run()
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL]


@pytest.mark.parametrize("policy", ["unlisted", "off", "personal"])
def test_unapproved_nested_column_remains_outside_proposed_scope(policy):
    plan = proposal("measure")
    occurrence(plan, "measure").op = FilterOp.EQ
    h = Harness(plan, policy=policy)
    result = h.run()
    assert result.status == "answered" and not h.checked
    assert occurrence(result.plan, "measure").values == ["Harbor East"]


@pytest.mark.parametrize(
    "names", [["Harbor-East", "Harbor East"], ["Harbor East", "Harbor-East"]]
)
def test_proposed_distinct_stored_values_with_same_normalization_are_ambiguous(names):
    result = ValueIndex({"places.label": names}).resolve("places.label", "harbor east")
    assert result.kind == "ambiguous"
    assert {c.value for c in result.candidates} == set(names)


def test_larger_catalog_prefix_is_ambiguous():
    names = [f"North Hub {i:03}" for i in range(100)] + [FULL]
    result = ValueIndex({"places.label": names}).resolve("places.label", "North Hub")
    assert result.kind == "ambiguous" and result.value is None


def test_exact_existing_negative_name_does_not_need_collision_resolution():
    h = Harness(proposal(value=FULL))
    h.index = ValueIndex({"facts.label": [FULL.lower(), FULL]})
    result = h.run()
    assert result.status == "answered" and not result.grounding
    assert result.plan.filters[0].values == [FULL]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("mode", ["ambiguous", "unavailable", "stale"])
def test_nested_positive_unresolved_never_executes(path, mode):
    plan = proposal(path, "North Hub" if mode == "ambiguous" else "Harbor East")
    occurrence(plan, path).op = FilterOp.EQ
    h = Harness(plan, index=mode != "unavailable", stale=mode == "stale")
    result = h.run()
    assert result.status == "clarify" and h.executions == 0
    assert result.reason == (
        "filter_value_ambiguous" if mode == "ambiguous" else "filter_value_not_found"
    )


@pytest.mark.parametrize("path", PATHS)
def test_nested_mixed_in_preserves_members_and_scope(path):
    plan = proposal(path)
    item = occurrence(plan, path)
    item.op = FilterOp.IN
    item.values = ["Harbor East", "North Hub Alpha"]
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL, "North Hub Alpha"]
    assert occurrence(result.plan, path).op is FilterOp.IN
    assert result.plan.filters == []


@pytest.mark.parametrize(
    "names", [["Harbor-East", "Harbor East"], ["Harbor East", "Harbor-East"]]
)
def test_collision_keeps_both_mentions_and_exact_identity(names):
    index = ValueIndex({"facts.label": names + [names[0]]})
    assert index.size() == 2
    assert {m.value for m in index.mentions("harbor east total")} == set(names)
    for value in names:
        resolution = index.resolve("facts.label", value)
        assert resolution.kind == "exact" and resolution.value == value


def test_normalized_collision_in_ask_does_not_execute():
    plan = proposal(value="harbor east")
    plan.filters[0].op = FilterOp.EQ
    h = Harness(plan)
    h.index = ValueIndex({"facts.label": ["Harbor-East", "Harbor East"]})
    result = h.run("harbor east total")
    assert result.status == "clarify" and result.reason == "filter_value_ambiguous"
    assert h.executions == 0
    assert {m["value"] for m in result.question_values} == {
        "Harbor-East",
        "Harbor East",
    }
