"""Research-only routing rulers; production contracts remain unchanged."""

import json

import pytest
from t0_helpers import AS_OF, iot_schema

from evals.query_kind_study import StudyPlanner, assess
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.application.ask import AskResult
from grepbit.application.request_lifecycle import RequestControl, RequestStopped
from grepbit.ports.grounding import GroundingModelError


def planner(arm, replies, control=None):
    obj = StudyPlanner(
        GroundingModelSettings(base_url="http://unused", model="fake", repair_turns=0),
        arm=arm,
        client=object(),
        control=control,
    )
    calls = []

    def complete(client, messages, **kw):
        calls.append(messages)
        return json.dumps(replies[len(calls) - 1])

    obj._complete = complete
    return obj, calls


def test_split_decline_does_not_construct():
    p, calls = planner("split", [{"route": "decline", "reason": "semantic_gap"}])
    assert (
        p.propose("q", iot_schema(), as_of=AS_OF.isoformat()).reason == "semantic_gap"
    )
    assert len(calls) == 1


def test_split_row_route_cannot_promote_an_aggregate():
    p, calls = planner(
        "split",
        [
            {"route": "rows"},
            {
                "decision": "plan",
                "plan": {"base_table": "devices", "measures": [{"aggregate": "count"}]},
            },
        ],
    )
    with pytest.raises(GroundingModelError, match="invalid_structured_output"):
        p.propose("q", iot_schema(), as_of=AS_OF.isoformat())
    assert p.study_error == "route_kind_mismatch"
    assert len(calls) == 2


def test_router_approval_does_not_override_builder_refusal():
    p, calls = planner(
        "split", [{"route": "rows"}, {"decision": "none", "reason": "semantic_gap"}]
    )
    assert (
        p.propose("q", iot_schema(), as_of=AS_OF.isoformat()).reason == "semantic_gap"
    )
    assert len(calls) == 2


def test_cancel_stops_second_call():
    control = RequestControl(30)
    p, calls = planner("split", [{"route": "rows"}], control)
    original = p._complete

    def complete(*a, **kw):
        reply = original(*a, **kw)
        control.stop("request_cancelled")
        return reply

    p._complete = complete
    with pytest.raises(RequestStopped):
        p.propose("q", iot_schema(), as_of=AS_OF.isoformat())
    assert len(calls) == 1


def test_joint_uses_same_context_and_wire_not_an_added_call():
    reply = {"decision": "none", "reason": "semantic_gap"}
    a, ca = planner("direct", [reply])
    b, cb = planner("joint", [reply])
    for p in [a, b]:
        p.propose("原文", iot_schema(), as_of=AS_OF.isoformat())
    assert len(ca) == len(cb) == 1
    assert ca[0][1] == cb[0][1]
    x, y = [json.loads(c[0][2]["content"]) for c in [ca, cb]]
    x.pop("prompt_revision")
    y.pop("prompt_revision")
    assert x == y


@pytest.mark.parametrize(
    "status,outcome",
    [
        ("answered", "wrong_answer"),
        ("semantic_gap", "necessary_refusal"),
        ("failed", "operational_failure"),
    ],
)
def test_missing_definition_scoring(status, outcome):
    assert (
        assess(
            AskResult(question="q", status=status), {"expected_route": "decline"}, None
        )["outcome"]
        == outcome
    )


def test_rows_are_not_sets_and_null_is_not_a_string():
    case = {"expected_route": "rows", "ordered": True}
    result = AskResult(question="q", status="answered", rows=[{"x": None}, {"x": None}])
    gold = (["x"], [(None,), (None,)])
    assert assess(result, case, gold)["outcome"] == "correct_answer"
    assert assess(result, case, (["x"], [(None,)]))["outcome"] == "wrong_answer"
    assert (
        assess(result, case, (["x"], [("None",), ("None",)]))["outcome"]
        == "wrong_answer"
    )


def test_wrong_order_and_names_cannot_match():
    case = {"expected_route": "rows", "ordered": True}
    result = AskResult(question="q", status="answered", rows=[{"x": 2}, {"x": 1}])
    assert assess(result, case, (["x"], [(1,), (2,)]))["outcome"] == "wrong_answer"
    assert assess(result, case, (["y"], [(2,), (1,)]))["outcome"] == "wrong_answer"


def test_bad_router_json_is_failure_not_decline():
    p, calls = planner("split", [{"route": "decline"}])
    with pytest.raises(GroundingModelError, match="invalid_structured_output"):
        p.propose("q", iot_schema(), as_of=AS_OF.isoformat())
    assert p.study_error == "invalid_route_output" and len(calls) == 1
