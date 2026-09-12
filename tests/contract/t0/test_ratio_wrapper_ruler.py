"""Owner-approved ratio-wrapper rejection; original red evidence is retained."""

from copy import deepcopy

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from t0_helpers import AS_OF, iot_schema

from evals.plan_generator import SchemaShape, draw_filters
from grepbit.adapters.litellm.plan_client import repair_column_refs
from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import Filter, PlanError, PlanProposal, QueryPlan

FILTER = {
    "column": {"table": "events", "column": "parent_id"},
    "op": "not_null",
}
RATIO = {
    "base_table": "events",
    "measures": [
        {
            "ratio": {
                "numerator": {"aggregate": "count", "filters": [FILTER]},
                "denominator": {"aggregate": "count"},
            }
        }
    ],
}


@pytest.mark.parametrize("form", ["raw", "metric", "share"])
def test_ratio_wrapper_filters_are_rejected_not_given_an_invented_scope(form):
    raw = deepcopy(RATIO)
    measure = raw["measures"][0]
    measure["filters"] = [deepcopy(FILTER)]
    if form == "metric":
        measure["ratio"]["numerator"] = {"metric": "reviewed_subset"}
        measure["ratio"]["denominator"] = {"metric": "reviewed_total"}
    elif form == "share":
        measure["share_of_total"] = True
    with pytest.raises(ValidationError, match="plan_ratio_wrapper_filters_unsupported"):
        QueryPlan.model_validate(raw)


@pytest.mark.parametrize("position", ["empty_wrapper", "operand", "plan"])
def test_supported_filter_positions_remain_accepted(position):
    raw = deepcopy(RATIO)
    if position == "empty_wrapper":
        raw["measures"][0]["filters"] = []
    elif position == "plan":
        raw["filters"] = [deepcopy(FILTER)]
    plan = QueryPlan.model_validate(raw)
    assert plan.measures[0].ratio.numerator.filters
    assert not plan.measures[0].filters


def unchecked_wrapper():
    raw = deepcopy(RATIO)
    raw["base_table"] = "alerts"
    raw["measures"][0]["ratio"]["numerator"]["filters"][0]["column"] = {
        "table": "alerts",
        "column": "device_id",
    }
    plan = QueryPlan.model_validate(raw)
    plan.measures[0] = plan.measures[0].model_copy(
        update={
            "filters": [
                Filter.model_validate(
                    {
                        "column": {"table": "alerts", "column": "severity"},
                        "op": "eq",
                        "values": ["critical"],
                    }
                )
            ],
        }
    )
    return plan


def test_compiler_rejects_unchecked_in_memory_wrapper_before_emitting_sql():
    with pytest.raises(PlanError) as info:
        PlanCompiler(iot_schema()).compile(unchecked_wrapper(), as_of=AS_OF)
    assert info.value.code == "ratio_wrapper_filters_unsupported"


def test_selfcheck_refuses_wrapper_even_if_its_predicate_appears_somewhere():
    sql = "SELECT COUNT(*) FROM public.alerts WHERE alerts.severity = 'critical'"
    assert "ratio_wrapper_filters_unsupported" in check_compiled(
        unchecked_wrapper(),
        sql,
        None,
        "unverified_semantics",
    )


@pytest.mark.parametrize("flat", [False, True])
@pytest.mark.parametrize("grouped_share", [False, True])
def test_wire_normalization_does_not_drop_the_wrapper_filter(flat, grouped_share):
    plan = unchecked_wrapper().model_dump(mode="json", exclude_none=True)
    measure = plan["measures"][0]
    if grouped_share:
        measure["share_of_total"] = True
        plan["dimensions"] = [{"table": "alerts", "column": "severity"}]
    if flat:
        measure.update(measure.pop("ratio"))
    payload, _ = repair_column_refs({"decision": "plan", "plan": plan}, iot_schema())
    assert payload["plan"]["measures"][0]["filters"]
    with pytest.raises(ValidationError, match="plan_ratio_wrapper_filters_unsupported"):
        PlanProposal.model_validate(payload)


def test_restatement_repair_cannot_erase_nonempty_wrapper_filters():
    plan = unchecked_wrapper().model_dump(mode="json", exclude_none=True)
    measure = plan["measures"][0]
    measure.update(measure.pop("ratio"))
    measure["aggregate"] = "count"
    measure["filters"] = deepcopy(measure["numerator"]["filters"])
    payload, _ = repair_column_refs({"decision": "plan", "plan": plan}, iot_schema())
    assert payload["plan"]["measures"][0]["filters"]
    with pytest.raises(ValidationError, match="plan_ratio_wrapper_filters_unsupported"):
        PlanProposal.model_validate(payload)


@settings(max_examples=100, deadline=None)
@given(st.data())
def test_schema_driven_filter_mutants_never_become_valid_wrappers(data):
    filters = draw_filters(data, SchemaShape(iot_schema()), "alerts", 2)
    if not filters:
        return
    raw = unchecked_wrapper().model_dump(mode="json")
    raw["measures"][0]["filters"] = filters
    with pytest.raises(ValidationError, match="plan_ratio_wrapper_filters_unsupported"):
        QueryPlan.model_validate(raw)
