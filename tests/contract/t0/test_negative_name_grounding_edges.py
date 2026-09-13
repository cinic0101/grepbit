"""Implementation edge controls supplementing the unchanged approval rulers."""

import pytest
from test_negative_name_grounding_ruler import (
    FULL,
    PATHS,
    Harness,
    occurrence,
    predicate,
    proposal,
)

from grepbit.application.grounding import ValueIndex, resolve_plan_literals
from grepbit.application.literals import text_literal_checks
from grepbit.domain.plan import Filter, FilterOp


def test_same_missing_literal_does_not_rewrite_nested_positive_sibling():
    plan = proposal("numerator")
    plan.measures[0].ratio.denominator.filters = [
        Filter.model_validate(predicate("Harbor East", op="eq"))
    ]
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered"
    assert occurrence(result.plan, "numerator").values == [FULL]
    assert occurrence(result.plan, "denominator").values == ["Harbor East"]
    assert occurrence(result.plan, "denominator").op is FilterOp.EQ
    assert all(c[2] != "Harbor East" for c in h.checked[1:])


@pytest.mark.parametrize("path", PATHS)
def test_normalized_negative_binding_disclosure_in_each_scope(path):
    h = Harness(proposal(path, "harbor east terminal"))
    result = h.run()
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL]
    assert any("'harbor east terminal' was read as" in a for a in result.assumptions)


def test_positive_normalized_exact_disclosure_is_not_incidentally_changed():
    plan = proposal(value="harbor east terminal")
    plan.filters[0].op = FilterOp.EQ
    result = Harness(plan).run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == [FULL]
    assert not any(
        "'harbor east terminal' was read as" in a for a in result.assumptions
    )


def test_repeated_bindings_keep_separate_occurrences_and_input_unchanged():
    plan = proposal("measure")
    plan.filters = [Filter.model_validate(predicate("Harbor East"))]
    before = plan.model_dump(mode="json")
    resolved, _ = resolve_plan_literals(
        plan,
        [("facts.label", "Harbor East")],
        ValueIndex({"facts.label": [FULL]}),
        negative_columns=frozenset({"facts.label"}),
    )
    assert plan.model_dump(mode="json") == before
    assert resolved.filters[0].values == [FULL]
    assert resolved.measures[0].filters[0].values == [FULL]
    assert resolved.filters[0] is not resolved.measures[0].filters[0]


def test_same_literal_in_another_column_is_not_cross_bound():
    plan = proposal("without")
    plan.filters = [Filter.model_validate(predicate("Harbor East"))]
    resolved, _ = resolve_plan_literals(
        plan,
        [("events.label", "Harbor East")],
        ValueIndex({"events.label": [FULL], "facts.label": ["Harbor East Annex"]}),
        negative_columns=frozenset({"events.label", "facts.label"}),
    )
    assert resolved.without.filters[0].values == [FULL]
    assert resolved.filters[0].values == ["Harbor East"]


def test_other_text_operator_is_not_checked_or_rewritten():
    plan = proposal()
    plan.filters[0].op = FilterOp.GT
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == ["Harbor East"]
    assert h.checked == [] and result.grounding == []


def test_numeric_column_remains_excluded_even_if_groundable():
    from test_negative_name_grounding_ruler import SCHEMA

    plan = proposal(value="100")
    plan.filters[0].column.column = "amount"
    assert (
        text_literal_checks(plan, SCHEMA, negative_columns=frozenset({"facts.amount"}))
        == []
    )


def test_recompiled_query_policy_failure_prevents_execution():
    h = Harness(proposal())
    original = h.assert_safe_select_statement

    def reject_second(sql):
        if h.policies:
            raise ValueError("test_policy_rejected")
        return original(sql)

    h.assert_safe_select_statement = reject_second
    result = h.run()
    assert result.status != "answered"
    assert h.executions == 0 and len(h.compilations) == 2
