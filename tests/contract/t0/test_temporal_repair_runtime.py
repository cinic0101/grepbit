"""Serving repair contract: invalid range repairs cannot silently lose anchors."""

import json

import pytest
from t0_helpers import iot_schema
from test_temporal_repair_study import draft, fixed

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.ports.grounding import GroundingModelError


def planner_for(responses):
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fake"), client=object()
    )
    queue = [json.dumps(r) for r in responses]
    planner._complete = lambda *a, **kw: queue.pop(0)
    return planner, queue


@pytest.mark.parametrize("change", ["round", "missing_identity"])
def test_runtime_does_not_serve_changed_or_unverifiable_range_repair(change):
    before, after = draft(), fixed()
    if change == "round":
        after["filters"][1]["values"] = ["2026-07-08T00:00:00+08:00"]
    else:
        before["plan"]["time"].pop("column")
    planner, queue = planner_for([before, {"decision": "plan", "plan": after}])
    with pytest.raises(GroundingModelError, match="invalid_structured_output"):
        planner.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert planner.last_temporal_repair_audit == (
        "changed" if change == "round" else "unverifiable"
    )
    assert planner.last_repair_output is not None
    assert not queue and planner.last_model_repair_turns == 1


@pytest.mark.parametrize(
    "storage", ["timestamp with time zone", "timestamp without time zone"]
)
def test_runtime_preserves_naive_repairs_and_resets_request_audit(storage):
    before, after = draft(), fixed()
    for key in ("start", "end_exclusive"):
        before["plan"]["time"]["scope"][key] = before["plan"]["time"]["scope"][key][:-6]
    for f in after["filters"]:
        f["values"][0] = f["values"][0][:-6]
    answer = {"decision": "plan", "plan": after}
    planner, queue = planner_for([before, answer, answer])
    schema = iot_schema()
    schema.table("alerts").column("raised_at").data_type = storage
    assert planner.propose("q", schema, as_of="2026-08-15T12:00:00+08:00").plan
    assert planner.last_temporal_repair_audit == "preserved"
    assert planner.propose("q2", schema, as_of="2026-08-15T12:00:00+08:00").plan
    assert planner.last_temporal_repair_audit == "not_applicable"
    assert not queue and planner.last_model_repair_turns == 0


@pytest.mark.parametrize("kind", ["decline", "unrelated"])
def test_runtime_guard_does_not_invent_new_refusal_or_block_ordinary_repair(kind):
    before = draft()
    if kind == "decline":
        after = {"decision": "none", "reason": "unsupported"}
    else:
        before = {
            "decision": "plan",
            "plan": {"base_table": "alerts", "measures": [{"aggregate": "bogus"}]},
        }
        after = {
            "decision": "plan",
            "plan": {"base_table": "alerts", "measures": [{"aggregate": "count"}]},
        }
    planner, queue = planner_for([before, after])
    assert (
        planner.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00").decision
        == after["decision"]
    )
    assert (
        getattr(planner, "last_temporal_repair_audit", "not_applicable")
        == "not_applicable"
    )
    assert not queue
