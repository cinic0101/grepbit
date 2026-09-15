import json
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from t0_helpers import iot_schema

from evals.temporal_repair_study import TemporalPlanner, temporal_repair_audit
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.domain.plan import QueryPlan
from grepbit.ports.grounding import GroundingModelError


@pytest.mark.parametrize("index", [0, 1])
def test_service_witnesses_independently_detect_each_rounded_endpoint(index):
    fixtures = json.loads(
        Path("evals/fixtures/temporal_service_witnesses.json").read_text()
    )
    fixture = fixtures["instances"][index]
    with duckdb.connect() as con:
        con.execute("CREATE TABLE work_logs (logged_at TIMESTAMPTZ)")
        con.executemany(
            "INSERT INTO work_logs VALUES (?)",
            [(row["logged_at"],) for row in fixture["work_logs"]],
        )
        counts = []
        for start, end in [("12:00:00", "12:00:00"), ("00:00:00", "00:00:00")]:
            counts.append(
                con.execute(
                    "SELECT count(*) FROM work_logs WHERE logged_at >= ?::timestamptz "
                    "AND logged_at < ?::timestamptz",
                    [f"2026-02-02T{start}+08:00", f"2026-02-05T{end}+08:00"],
                ).fetchone()[0]
            )
        assert counts == [
            fixture["expected_exact_count"],
            fixture["expected_rounded_count"],
        ]
        assert counts[0] != counts[1]


def draft():
    return {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": "alerts.raised_at",
                "grain": "day",
                "scope": {
                    "kind": "range",
                    "start": "2026-07-01T00:00:00+08:00",
                    "end_exclusive": "2026-07-08T12:00:00+08:00",
                },
            },
        },
    }


def fixed():
    return {
        "base_table": "alerts",
        "measures": [{"aggregate": "count"}],
        "time": {"column": {"table": "alerts", "column": "raised_at"}, "grain": "day"},
        "filters": [
            {
                "column": {"table": "alerts", "column": "raised_at"},
                "op": op,
                "values": [v],
            }
            for op, v in [
                ("gte", "2026-07-01T00:00:00+08:00"),
                ("lt", "2026-07-08T12:00:00+08:00"),
            ]
        ],
    }


def audit(before, after):
    return temporal_repair_audit(
        json.dumps(before), QueryPlan.model_validate(after), iot_schema()
    )


@pytest.mark.parametrize("change", ["none", "utc", "alias"])
def test_equivalent_filter_representation_retains_instant(change):
    after = fixed()
    if change == "utc":
        after["filters"][0]["values"] = ["2026-06-30T16:00:00Z"]
        after["filters"][1]["values"] = ["2026-07-08T04:00:00Z"]
    if change == "alias":
        after["measures"][0]["alias"] = "renamed"
    assert audit(draft(), after) == "preserved"


@pytest.mark.parametrize(
    "change", ["drop", "round", "operator", "column", "scope", "base"]
)
def test_repair_must_not_lose_bound_scope_column_or_operator(change):
    after = fixed()
    if change == "drop":
        after["filters"].pop()
    elif change == "round":
        after["filters"][1]["values"] = ["2026-07-08T00:00:00+08:00"]
    elif change == "operator":
        after["filters"][1]["op"] = "lte"
    elif change == "column":
        after["filters"][1]["column"]["column"] = "resolved_at"
    elif change == "base":
        after["base_table"] = "devices"
    else:
        after["without"] = {"table": "readings", "filters": after.pop("filters")}
    assert audit(draft(), after) == "changed"


def test_equivalent_midnight_range_is_not_a_precision_loss():
    before = draft()
    before["plan"]["time"]["scope"]["end_exclusive"] = "2026-07-08T16:00:00Z"
    after = fixed()
    after["filters"] = []
    after["time"]["scope"] = {
        "kind": "range",
        "start": "2026-07-01",
        "end_exclusive": "2026-07-09",
    }
    assert audit(before, after) == "preserved"


def test_retained_literal_does_not_hide_a_stronger_rounded_constraint():
    after = fixed()
    after["time"]["scope"] = {
        "kind": "range",
        "start": "2026-07-01",
        "end_exclusive": "2026-07-08",
    }
    assert audit(draft(), after) == "changed"


def test_redundant_weaker_bound_preserves_the_effective_instant():
    after = fixed()
    after["filters"].append(
        {
            "column": {"table": "alerts", "column": "raised_at"},
            "op": "lte",
            "values": ["2026-07-09T00:00:00+08:00"],
        }
    )
    assert audit(draft(), after) == "preserved"


def test_without_bounds_stay_in_the_same_child_scope():
    before = draft()
    before["plan"]["base_table"] = "devices"
    before["plan"]["without"] = {"table": "alerts", "time": before["plan"].pop("time")}
    before["plan"]["without"]["time"].pop("grain")
    after = {
        "base_table": "devices",
        "measures": [{"aggregate": "count"}],
        "without": {"table": "alerts", "filters": fixed()["filters"]},
    }
    assert audit(before, after) == "preserved"
    after["without"]["table"] = "readings"
    assert audit(before, after) == "changed"


@pytest.mark.parametrize("change", ["column", "zone"])
def test_unresolved_anchor_is_not_certified(change):
    before = draft()
    if change == "column":
        del before["plan"]["time"]["column"]
    else:
        before["plan"]["time"]["scope"]["end_exclusive"] = "2026-07-08T12:00:00"
    assert audit(before, fixed()) == "unverifiable"


def test_malformed_qualified_identity_is_unverifiable_not_an_exception():
    before = draft()
    before["plan"]["time"]["column"] = {"table": "public.alerts", "column": "raised_at"}
    assert audit(before, fixed()) == "unverifiable"


@pytest.mark.parametrize("guard", [False, True])
def test_actual_two_turn_path_exposes_or_blocks_the_recorded_loss(guard):
    before = draft()
    repaired = deepcopy(before)
    repaired["plan"]["time"]["scope"] = {
        "kind": "range",
        "start": "2026-07-01",
        "end_exclusive": "2026-07-08",
    }
    responses = [json.dumps(before), json.dumps(repaired)]
    settings = GroundingModelSettings(base_url="http://unused", model="fake")
    planner = TemporalPlanner(settings, guard=guard, client=object())
    planner._complete = lambda *a, **kw: responses.pop(0)
    args = ("q", iot_schema())
    if guard:
        with pytest.raises(GroundingModelError, match="invalid_structured_output"):
            planner.propose(*args, as_of="2026-08-15T12:00:00+08:00")
        assert planner.temporal_audit == "changed"
    else:
        assert (
            planner.propose(*args, as_of="2026-08-15T12:00:00+08:00").plan is not None
        )
    assert not responses
    assert planner.last_model_repair_turns == 1


@pytest.mark.parametrize("repair", ["filters", "decline", "ordinary"])
def test_guard_preserves_valid_repairs_and_safe_declines(repair):
    before = draft()
    answer = {"decision": "plan", "plan": fixed()}
    if repair == "decline":
        answer = {"decision": "none", "reason": "unsupported"}
    if repair == "ordinary":
        before = {
            "decision": "plan",
            "plan": {"base_table": "alerts", "measures": [{"aggregate": "bogus"}]},
        }
        answer = {
            "decision": "plan",
            "plan": {"base_table": "alerts", "measures": [{"aggregate": "count"}]},
        }
    responses = [json.dumps(before), json.dumps(answer)]
    planner = TemporalPlanner(
        GroundingModelSettings(base_url="http://unused", model="fake"),
        guard=True,
        client=object(),
    )
    planner._complete = lambda *a, **kw: responses.pop(0)
    result = planner.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert result.decision == answer["decision"]
    assert not responses
    assert planner.temporal_audit == (
        "preserved" if repair == "filters" else "not_applicable"
    )
