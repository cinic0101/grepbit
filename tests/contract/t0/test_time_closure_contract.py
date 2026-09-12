"""The time closure (root-cause program, B5): every time shape the plan can
carry, what the compiler does with it. One cell per row of the table in
`docs/knowledge/tier0-contract.md`."""

from __future__ import annotations

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import PlanError, QueryPlan

COMPILER = PlanCompiler(iot_schema())
RAISED_AT = {"table": "alerts", "column": "raised_at"}


def compile_time(time: dict, growth: list | None = None):
    payload = {
        "base_table": "alerts",
        "measures": [{"aggregate": "count", "alias": "n"}],
        "time": time,
    }
    if growth:
        payload["growth"] = growth
    return COMPILER.compile(QueryPlan.model_validate(payload), as_of=AS_OF)


def bounds(compiled) -> list[tuple[str, str]]:
    return [(str(p.start)[:10], str(p.end_exclusive)[:10]) for p in compiled.periods]


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        (
            {"column": RAISED_AT, "scope": {"kind": "month", "month": "2026-07"}},
            [("2026-07-01", "2026-08-01")],
        ),
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "range",
                    "start": "2026-06-01",
                    "end_exclusive": "2026-08-01",
                },
            },
            [("2026-06-01", "2026-08-01")],
        ),
        # a range written past as_of is clamped to the end of as_of's day
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "range",
                    "start": "2026-01-01",
                    "end_exclusive": "2060-01-01",
                },
            },
            [("2026-01-01", "2026-08-16")],
        ),
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "week",
                    "offset": -1,
                    "length": 1,
                },
            },
            [("2026-08-03", "2026-08-10")],
        ),
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": 0,
                    "length": 1,
                },
            },
            [("2026-08-01", "2026-09-01")],
        ),
        # one unit to date: clamped to the end of as_of's day
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": 0,
                    "length": 1,
                    "to_date": True,
                },
            },
            [("2026-08-01", "2026-08-16")],
        ),
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "periods",
                    "periods": [
                        {"kind": "month", "month": "2026-06"},
                        {"kind": "month", "month": "2026-07"},
                    ],
                },
                "grain": "day",
            },
            [("2026-06-01", "2026-07-01"), ("2026-07-01", "2026-08-01")],
        ),
        # a grain alone buckets every row: no window
        ({"column": RAISED_AT, "grain": "month"}, []),
        # the latest unit with data is resolved in SQL, not against as_of
        ({"column": RAISED_AT, "scope": {"kind": "latest", "unit": "day"}}, []),
    ],
)
def test_windows_resolve_as_the_table_says(time, expected) -> None:
    assert bounds(compile_time(time)) == expected


def test_a_range_clamped_to_as_of_says_so() -> None:
    compiled = compile_time(
        {
            "column": RAISED_AT,
            "scope": {
                "kind": "range",
                "start": "2026-01-01",
                "end_exclusive": "2060-01-01",
            },
        }
    )
    assert any("clamped to the end of as_of" in a.text for a in compiled.assumptions)


@pytest.mark.parametrize(
    ("time", "growth", "code"),
    [
        # a current-anchored window longer than one unit runs into the future (the
        # planner re-anchors it first; the compiler is the safety net)
        (
            {
                "column": RAISED_AT,
                "scope": {"kind": "relative", "unit": "day", "offset": 0, "length": 30},
            },
            None,
            "relative_window_reaches_future",
        ),
        # the same wearing the to_date flag
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "day",
                    "offset": 0,
                    "length": 30,
                    "to_date": True,
                },
            },
            None,
            "relative_window_reaches_future",
        ),
        # last week written as seven weeks
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "week",
                    "offset": -1,
                    "length": 7,
                },
            },
            None,
            "relative_window_reaches_future",
        ),
        # several periods need a grain
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "periods",
                    "periods": [
                        {"kind": "month", "month": "2026-06"},
                        {"kind": "month", "month": "2026-07"},
                    ],
                },
            },
            None,
            "time_scope_requires_grain",
        ),
        # growth against a partial period, or against the latest unit
        (
            {
                "column": RAISED_AT,
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": 0,
                    "length": 1,
                    "to_date": True,
                },
                "grain": "month",
            },
            [{"measure": "n"}],
            "growth_to_date_unsupported",
        ),
        (
            {
                "column": RAISED_AT,
                "scope": {"kind": "latest", "unit": "month"},
                "grain": "month",
            },
            [{"measure": "n"}],
            "growth_to_date_unsupported",
        ),
    ],
)
def test_shapes_the_compiler_refuses_with_a_typed_error(time, growth, code) -> None:
    with pytest.raises(PlanError) as info:
        compile_time(time, growth)
    assert info.value.code == code


def test_growth_over_one_period_is_widened_to_include_the_previous_one() -> None:
    compiled = compile_time(
        {
            "column": RAISED_AT,
            "scope": {"kind": "month", "month": "2026-07"},
            "grain": "month",
        },
        [{"measure": "n"}],
    )
    assert bounds(compiled) == [("2026-06-01", "2026-08-01")]
    assert any("widened by one" in a.text for a in compiled.assumptions)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "n"}],
                "time": {
                    "column": RAISED_AT,
                    "scope": {"kind": "month", "month": "2026-07"},
                },
                "growth": [{"measure": "n"}],
            },
            "plan_growth_requires_grain",
        ),
        (
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "without": {
                    "table": "alerts",
                    "time": {"column": RAISED_AT, "grain": "month"},
                },
            },
            "plan_without_takes_a_window_not_a_grain",
        ),
        (
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "without": {
                    "table": "alerts",
                    "time": {
                        "column": RAISED_AT,
                        "scope": {"kind": "latest", "unit": "day"},
                    },
                },
            },
            "plan_without_takes_no_latest_scope",
        ),
        (
            {
                "base_table": "alerts",
                "dimensions": [{"table": "devices", "column": "model"}],
                "latest": {
                    "order_by": [{"column": RAISED_AT}],
                    "take": [{"table": "alerts", "column": "severity"}],
                },
                "time": {"column": RAISED_AT, "grain": "day"},
            },
            "plan_latest_takes_a_window_not_a_grain",
        ),
    ],
)
def test_shapes_the_plan_itself_rejects(payload, code) -> None:
    with pytest.raises(ValueError, match=code):
        QueryPlan.model_validate(payload)


def test_a_period_breakdown_leaves_out_rows_without_a_time_value() -> None:
    # found by the differential: a NULL time value formed its own bucket and
    # took part in growth as the last period
    compiled = compile_time({"column": RAISED_AT, "grain": "month"})
    sql = compiled.compiled.physical_sql
    assert "WHERE NOT alerts.raised_at IS NULL" in sql
    assert any("are in no period" in a.text for a in compiled.assumptions)
    # a plain window (no grain) keeps the comparison as its only condition
    windowed = compile_time(
        {"column": RAISED_AT, "scope": {"kind": "month", "month": "2026-07"}}
    )
    assert "IS NULL" not in windowed.compiled.physical_sql


def test_growth_remains_a_sparse_query_without_calendar_expansion() -> None:
    # The owner chose NULL growth across a gap, not zero-filled periods.
    # This structural assertion does not prove adjacency: the independent
    # value rulers are in test_period_semantics_ruler.py.
    compiled = compile_time(
        {
            "column": RAISED_AT,
            "scope": {
                "kind": "range",
                "start": "2026-01-01",
                "end_exclusive": "2026-04-01",
            },
            "grain": "month",
        },
        [{"measure": "n"}],
    )
    sql = compiled.compiled.physical_sql
    assert "LAG(" in sql and "generate_series" not in sql.lower()
