"""Reviewer counterexamples: compare both populations; unknown is not changed."""

import json
from copy import deepcopy

import pytest
from t0_helpers import iot_schema
from test_temporal_repair_runtime import planner_for
from test_temporal_repair_study import draft, fixed

from grepbit.domain.plan import QueryPlan
from grepbit.domain.temporal_repair import temporal_repair_audit


def examples(location, op="gte", value="2026-07-02T00:00:00+08:00"):
    before, after = draft(), fixed()
    extra = {"column": "alerts.raised_at", "op": op, "values": [value]}
    before["plan"]["filters"] = [extra]
    after["filters"].append(
        {**extra, "column": {"table": "alerts", "column": "raised_at"}}
    )
    if location == "without":
        before["plan"]["base_table"] = after["base_table"] = "devices"
        before["plan"]["without"] = {
            "table": "alerts",
            "time": before["plan"].pop("time"),
            "filters": before["plan"].pop("filters"),
        }
        after.pop("time")
        after["without"] = {"table": "alerts", "filters": after.pop("filters")}
    return before, after


def audit(before, after):
    return temporal_repair_audit(
        json.dumps(before), QueryPlan.model_validate(after), iot_schema()
    )


@pytest.mark.parametrize("location", ["plan", "without"])
@pytest.mark.parametrize(
    "op,value",
    [
        ("gte", "2026-07-02T00:00:00+08:00"),
        ("lt", "2026-07-07T12:00:00+08:00"),
        ("gt", "2026-07-01T00:00:00+08:00"),
        ("gte", "2026-06-01T00:00:00+08:00"),
    ],
)
def test_existing_same_scope_bound_is_preserved(location, op, value):
    before, after = examples(location, op, value)
    assert audit(before, after) == "preserved"


@pytest.mark.parametrize("location", ["plan", "without"])
def test_dropping_the_original_stronger_bound_is_changed(location):
    before, after = examples(location)
    target = after if location == "plan" else after["without"]
    target["filters"].pop()
    assert audit(before, after) == "changed"


@pytest.mark.parametrize(
    "bad",
    [
        "missing_column",
        "unparsed_value",
        "unsupported_op",
        "malformed_list",
        "invalid_op_type",
    ],
)
def test_unrecognized_original_bound_is_unknown_not_confirmed_changed(bad):
    before, after = examples("plan")
    filters = before["plan"]["filters"]
    if bad == "missing_column":
        filters[0].pop("column")
    elif bad == "unparsed_value":
        filters[0]["values"] = ["tomorrow"]
    elif bad == "unsupported_op":
        filters[0]["op"] = "between"
    elif bad == "invalid_op_type":
        filters[0]["op"] = []
    else:
        before["plan"]["filters"] = {"op": "gte"}
    assert audit(before, after) == "unverifiable"


@pytest.mark.parametrize("identity", [None, "not_a_table", []])
def test_without_missing_or_unresolved_child_identity_is_unknown(identity):
    before, after = examples("without")
    before["plan"]["without"]["table"] = identity
    assert audit(before, after) == "unverifiable"


def test_actual_runtime_retains_legal_stronger_bound_repair():
    before, after = examples("plan")
    planner, queue = planner_for(
        [before, {"decision": "plan", "plan": deepcopy(after)}]
    )
    proposal = planner.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert proposal.plan is not None
    assert planner.last_temporal_repair_audit == "preserved"
    assert not queue
