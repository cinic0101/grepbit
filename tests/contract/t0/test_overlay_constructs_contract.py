"""Overlay v2 constructs: table/value aliases, time defaults, segments; to-date and
future-window rules in the compiler."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.plan_client import schema_payload
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.overlay import excluded_segments, overlay_problems
from grepbit.domain.assumptions import AssumptionSource
from grepbit.domain.overlay import Segment, SemanticOverlay
from grepbit.domain.plan import ColumnRef, PlanError, QueryPlan
from grepbit.domain.structured_query import RelativeScope, resolve_time_scope

OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "t",
        "metrics": [
            {
                "id": "critical_alerts",
                "names": ["嚴重告警"],
                "description": "count of critical alerts",
                "base_table": "alerts",
                "aggregate": "count",
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "severity"},
                        "op": "eq",
                        "values": ["critical"],
                    }
                ],
            }
        ],
        "table_aliases": [{"table": "alerts", "names": ["告警", "alarms"]}],
        "value_aliases": [
            {
                "column": {"table": "alerts", "column": "severity"},
                "values": [{"value": "critical", "names": ["嚴重", "critical"]}],
            }
        ],
        "time_defaults": [
            {"table": "alerts", "column": {"table": "alerts", "column": "raised_at"}}
        ],
        "segments": [
            {
                "id": "test_alerts",
                "names": ["測試", "test alerts"],
                "table": "alerts",
                "filter": {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "eq",
                    "values": ["test"],
                },
                "default_exclude": True,
                "note": "alerts raised by the test harness",
            }
        ],
    }
)


def test_overlay_validation_catches_unknown_identifiers_and_non_time_defaults():
    assert overlay_problems(OVERLAY, iot_schema()) == []
    broken = OVERLAY.model_copy(
        update={
            "table_aliases": [
                OVERLAY.table_aliases[0].model_copy(update={"table": "nowhere"})
            ],
            "time_defaults": [
                OVERLAY.time_defaults[0].model_copy(
                    update={"column": ColumnRef(table="alerts", column="severity")}
                )
            ],
        }
    )
    problems = overlay_problems(
        SemanticOverlay.model_validate(broken.model_dump()), iot_schema()
    )
    assert any("table_aliases: unknown table nowhere" in p for p in problems)
    assert any("alerts.severity is not a timestamp" in p for p in problems)


def test_segment_filters_must_be_invertible_and_on_their_table() -> None:
    with pytest.raises(ValueError, match="overlay_segment_filter_not_invertible"):
        Segment.model_validate(
            {
                "id": "s",
                "names": ["x"],
                "table": "alerts",
                "filter": {
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "op": "gt",
                    "values": [1],
                },
                "note": "n",
            }
        )
    with pytest.raises(ValueError, match="overlay_segment_filter_table_mismatch"):
        Segment.model_validate(
            {
                "id": "s",
                "names": ["x"],
                "table": "devices",
                "filter": {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "is_null",
                },
                "note": "n",
            }
        )
    assert OVERLAY.segments[0].inverse().op.value == "ne"


def test_payload_carries_table_aliases_value_aliases_defaults_and_segments():
    payload = schema_payload(iot_schema(), OVERLAY)
    alerts = next(t for t in payload["tables"] if t["name"] == "alerts")
    assert alerts["aliases"] == ["告警", "alarms"]
    assert alerts["default_time_column"] == "alerts.raised_at"
    severity = next(c for c in alerts["columns"] if c["name"] == "severity")
    assert severity["value_aliases"] == [
        {"value": "critical", "names": ["嚴重", "critical"]}
    ]
    assert payload["segments"] == [
        {
            "id": "test_alerts",
            "names": ["測試", "test alerts"],
            "table": "alerts",
            "excluded_by_default": True,
            "note": "alerts raised by the test harness",
        }
    ]


def test_excluded_segments_are_lifted_when_the_question_names_them() -> None:
    assert [s.id for s in excluded_segments("有幾個告警？", OVERLAY)] == ["test_alerts"]
    assert excluded_segments("測試告警有幾個？", OVERLAY) == []
    assert excluded_segments("How many test alerts?", OVERLAY) == []


def _compile(plan: dict, *, exclude=()):
    return PlanCompiler(iot_schema(), overlay=OVERLAY).compile(
        QueryPlan.model_validate(plan), as_of=AS_OF, exclude_segments=exclude
    )


def test_default_exclusion_adds_the_inverse_filter_and_a_reviewed_assumption():
    compiled = _compile(
        {"base_table": "alerts", "measures": [{"aggregate": "count"}]},
        exclude=OVERLAY.segments,
    )
    sql = compiled.compiled.physical_sql
    assert "WHERE alerts.severity <> %(f_0)s" in sql
    assert compiled.compiled.execution_parameters[0].value == "test"
    assert any(
        a.source is AssumptionSource.REVIEWED
        and a.definition_ref == "overlay.segments.test_alerts"
        and "excluded by default" in a.text
        for a in compiled.assumptions
    )
    assert "[default: exclude test_alerts] alerts.severity ne test" in (
        compiled.lineage.filters
    )
    assert compiled.applied_segments == ("test_alerts",)


def test_default_exclusion_is_skipped_when_the_plan_filters_the_segment_column():
    # a reviewed metric on the same column keeps its own rows
    compiled = _compile(
        {"base_table": "alerts", "measures": [{"metric": "critical_alerts"}]},
        exclude=OVERLAY.segments,
    )
    assert "<>" not in compiled.compiled.physical_sql
    assert compiled.applied_segments == ()  # the caller must not report it
    # a question filter on the column also lifts it
    compiled = _compile(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "eq",
                    "values": ["warning"],
                }
            ],
        },
        exclude=OVERLAY.segments,
    )
    assert "<>" not in compiled.compiled.physical_sql


def test_default_exclusion_reaches_a_parent_table_but_not_an_unrelated_one():
    # readings -> devices; the segment table alerts is not reachable from readings
    compiled = _compile(
        {
            "base_table": "readings",
            "measures": [
                {
                    "aggregate": "avg",
                    "column": {"table": "readings", "column": "temperature_c"},
                }
            ],
        },
        exclude=OVERLAY.segments,
    )
    assert "alerts" not in compiled.compiled.physical_sql
    # a segment on devices applies to alerts (alerts -> devices) through the join
    devices_segment = Segment.model_validate(
        {
            "id": "unmanaged",
            "names": ["未納管"],
            "table": "devices",
            "filter": {
                "column": {"table": "devices", "column": "is_managed"},
                "op": "eq",
                "values": [False],
            },
            "default_exclude": True,
            "note": "devices outside the managed fleet",
        }
    )
    compiled = _compile(
        {"base_table": "alerts", "measures": [{"aggregate": "count"}]},
        exclude=[devices_segment],
    )
    sql = compiled.compiled.physical_sql
    assert "LEFT JOIN public.devices" in sql and "devices.is_managed <> %(f_0)s" in sql


def test_past_relative_window_that_reaches_the_future_is_a_plan_error() -> None:
    plan = {
        "base_table": "alerts",
        "measures": [{"aggregate": "count"}],
        "time": {
            "column": {"table": "alerts", "column": "raised_at"},
            "scope": {"kind": "relative", "unit": "week", "offset": -1, "length": 7},
            "grain": "day",
        },
    }
    with pytest.raises(PlanError) as error:
        _compile(plan)
    assert error.value.code == "relative_window_reaches_future"
    assert "week offset -1 length 7" in (error.value.detail or "")
    plan["time"]["scope"]["length"] = 1  # last week proper compiles
    compiled = _compile(plan)
    assert compiled.periods[0].label == "2026-08-03"  # Monday before AS_OF (Sat 15th)
    # a window anchored at the current unit may extend forward (this month)
    plan["time"]["scope"] = {
        "kind": "relative",
        "unit": "month",
        "offset": 0,
        "length": 1,
    }
    plan["time"].pop("grain")
    assert _compile(plan).periods[0].label == "2026-08"


def test_to_date_clamps_the_window_to_the_end_of_as_of_day() -> None:
    as_of = datetime(2026, 2, 4, 18, tzinfo=ZoneInfo("Asia/Taipei"))
    [period] = resolve_time_scope(
        RelativeScope(unit="month", offset=0, length=1, to_date=True),
        as_of=as_of,
        business_timezone="Asia/Taipei",
    )
    assert period.label == "2026-02 to 2026-02-04"
    assert period.end_exclusive == datetime(2026, 2, 5, tzinfo=ZoneInfo("Asia/Taipei"))
    [past] = resolve_time_scope(
        RelativeScope(unit="month", offset=-1, length=1, to_date=True),
        as_of=as_of,
        business_timezone="Asia/Taipei",
    )
    assert past.label == "2026-01"  # to_date does not touch a window already past


def test_grain_without_a_scope_buckets_all_data_without_a_window() -> None:
    compiled = _compile(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "day",
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert "DATE_TRUNC('DAY'" in sql and ">=" not in sql
    assert compiled.periods == ()
    assert compiled.output_columns[0] == "period_start"
    assert "per day; over all data" in compiled.interpretation
    with pytest.raises(ValueError, match="plan_time_requires_scope_or_grain"):
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {"column": {"table": "alerts", "column": "raised_at"}},
            }
        )


def test_default_segment_becomes_operand_level_when_one_operand_selects_it() -> None:
    """A ratio of a segment metric over a plain total keeps the total free of
    the segment: the exclusion moves into FILTER clauses on the other operands."""

    from grepbit.domain.plan import PlanError as _PlanError  # noqa: F401

    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
            "metrics": [
                {
                    "id": "test_alert_count",
                    "names": ["測試告警數"],
                    "description": "count of test alerts",
                    "base_table": "alerts",
                    "aggregate": "count",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "severity"},
                            "op": "eq",
                            "values": ["test"],
                        }
                    ],
                }
            ],
            "segments": [
                {
                    "id": "test_alerts",
                    "names": ["測試"],
                    "table": "alerts",
                    "filter": {
                        "column": {"table": "alerts", "column": "severity"},
                        "op": "eq",
                        "values": ["test"],
                    },
                    "default_exclude": True,
                    "note": "alerts raised by the test harness",
                }
            ],
        }
    )
    compiler = PlanCompiler(iot_schema(), overlay=overlay)
    ratio = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "ratio": {
                        "numerator": {"metric": "test_alert_count"},
                        "denominator": {"aggregate": "count"},
                    },
                    "alias": "test_share",
                }
            ],
        }
    )
    # the question names the segment (測試), so it arrives as a named segment
    compiled = compiler.compile(
        ratio, as_of=AS_OF, exclude_segments=[], named_segments=overlay.segments
    )
    sql = compiled.compiled.physical_sql
    assert "COUNT(*) FILTER(WHERE alerts.severity = %(f_0)s)" in sql  # numerator
    assert (
        "NULLIF(COUNT(*) FILTER(WHERE alerts.severity <> %(f_1)s), 0)" in sql
    )  # denominator
    assert "WHERE alerts.severity" not in sql.split("FROM")[1]  # nothing query-wide
    assert any("free of them" in a.text for a in compiled.assumptions)
    assert compiled.applied_segments == ("test_alerts",)
    # the question names the segment and no operand selects it: lifted entirely
    plain = QueryPlan.model_validate(
        {"base_table": "alerts", "measures": [{"aggregate": "count"}]}
    )
    lifted = compiler.compile(
        plain, as_of=AS_OF, exclude_segments=[], named_segments=overlay.segments
    )
    assert "severity" not in lifted.compiled.physical_sql
    assert lifted.applied_segments == ()
    # not named at all: the exclusion is a WHERE condition as before
    excluded = compiler.compile(plain, as_of=AS_OF, exclude_segments=overlay.segments)
    assert "WHERE alerts.severity <> %(f_0)s" in excluded.compiled.physical_sql
