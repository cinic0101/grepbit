"""Derived measures: ratio, share of total, growth; derived base table; default
time column; per-measure FILTER when metric filters differ."""

from __future__ import annotations

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import PlanError, QueryPlan

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
            },
            {
                "id": "all_alerts",
                "names": ["告警數"],
                "description": "count of alerts",
                "base_table": "alerts",
                "aggregate": "count",
            },
        ],
        "time_defaults": [
            {"table": "alerts", "column": {"table": "alerts", "column": "raised_at"}}
        ],
    }
)
POLICY = PostgresSqlPolicy(
    tables=frozenset(t.name for t in iot_schema().tables),
    functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
)


def compile_plan(payload: dict, overlay=OVERLAY):
    compiled = PlanCompiler(iot_schema(), overlay=overlay).compile(
        QueryPlan.model_validate(payload), as_of=AS_OF
    )
    POLICY.assert_safe_select_statement(compiled.compiled.physical_sql)
    return compiled


def test_share_of_total_divides_by_the_window_total_over_all_groups() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "share_of_total": True,
                    "alias": "downtime_share",
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "CAST((SUM(alerts.downtime_minutes)) AS DOUBLE PRECISION) / "
        "NULLIF(SUM(SUM(alerts.downtime_minutes)) OVER (), 0) AS downtime_share"
    ) in sql
    assert compiled.output_columns == ("model", "downtime_share")
    assert any(
        "share of the total over all groups" in a.text for a in compiled.assumptions
    )
    assert compiled.lineage.measures[0].startswith("downtime_share = share of total of")


def test_share_within_each_period_when_the_plan_has_a_grain() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "share_of_total": True}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "OVER (PARTITION BY DATE_TRUNC('MONTH', alerts.raised_at "
        "AT TIME ZONE 'Asia/Taipei'))"
    ) in sql
    assert compiled.output_columns == ("period_start", "model", "row_count_share")


def test_ratio_of_two_operands_uses_filter_clauses_when_their_filters_differ():
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "ratio": {
                        "numerator": {"metric": "critical_alerts"},
                        "denominator": {"aggregate": "count"},
                    },
                    "alias": "critical_rate",
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "CAST((COUNT(*) FILTER(WHERE alerts.severity = %(f_0)s)) AS DOUBLE PRECISION)"
        " / NULLIF(COUNT(*), 0) AS critical_rate"
    ) in sql
    # the metric filter lives in the FILTER clause only: no WHERE before GROUP BY
    assert (
        "FROM public.alerts LEFT JOIN public.devices ON alerts.device_id = "
        "devices.device_id GROUP BY devices.model"
    ) in sql
    assert compiled.verification == "unverified_semantics"  # the denominator is raw
    assert any("divides two aggregates" in a.text for a in compiled.assumptions)


def test_two_metrics_with_the_same_filters_still_share_one_where_clause() -> None:
    compiled = compile_plan(
        {"base_table": "alerts", "measures": [{"metric": "critical_alerts"}]}
    )
    sql = compiled.compiled.physical_sql
    assert "WHERE alerts.severity = %(f_0)s" in sql and "FILTER" not in sql
    assert compiled.verification == "verified"


def test_growth_compares_each_period_with_the_previous_one_per_group() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
            },
            "growth": [{"measure": "alerts_n"}],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "CAST((COUNT(*) - LAG(COUNT(*)) OVER (PARTITION BY devices.model ORDER BY "
        "DATE_TRUNC('MONTH', alerts.raised_at AT TIME ZONE 'Asia/Taipei'))) AS DOUBLE "
        "PRECISION) / NULLIF(LAG(COUNT(*)) OVER"
    ) in sql
    assert compiled.output_columns == (
        "period_start",
        "model",
        "alerts_n",
        "alerts_n_growth",
    )
    assert "alerts_n_growth = period-over-period change" in compiled.lineage.measures
    with pytest.raises(ValueError, match="plan_growth_requires_grain"):
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "n"}],
                "growth": [{"measure": "n"}],
            }
        )


def test_base_table_is_derived_from_the_measure_columns_or_metrics() -> None:
    compiled = compile_plan(
        {
            "measures": [
                {
                    "aggregate": "avg",
                    "column": {"table": "readings", "column": "temperature_c"},
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
        }
    )
    assert compiled.lineage.base_table == "readings"
    assert any(
        "base table readings was derived" in a.text for a in compiled.assumptions
    )
    from_metric = compile_plan({"measures": [{"metric": "all_alerts"}]})
    assert from_metric.lineage.base_table == "alerts"
    # measures on unrelated tables cannot decide a base
    with pytest.raises(PlanError) as error:
        compile_plan(
            {
                "measures": [
                    {
                        "aggregate": "avg",
                        "column": {"table": "readings", "column": "temperature_c"},
                    },
                    {
                        "aggregate": "sum",
                        "column": {"table": "alerts", "column": "downtime_minutes"},
                    },
                ]
            }
        )
    assert error.value.code == "base_table_undetermined"
    with pytest.raises(ValueError, match="plan_base_table_required"):
        QueryPlan.model_validate({"measures": [{"aggregate": "count"}]})


def test_time_column_defaults_to_the_overlay_time_default_of_the_base() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {"scope": {"kind": "month", "month": "2026-07"}},
        }
    )
    assert "alerts.raised_at >= %(p1_start_0)s" in compiled.compiled.physical_sql
    assert any("default time column of alerts" in a.text for a in compiled.assumptions)
    with pytest.raises(PlanError) as error:
        compile_plan(
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "time": {"scope": {"kind": "month", "month": "2026-07"}},
            }
        )
    assert error.value.code == "time_column_required"


def test_having_cannot_target_a_derived_measure() -> None:
    with pytest.raises(ValueError, match="plan_having_on_derived_measure"):
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [
                    {"aggregate": "count", "share_of_total": True, "alias": "s"}
                ],
                "having": [{"field": "s", "op": "gt", "value": 0.5}],
            }
        )


def test_share_filtered_on_its_own_dimension_is_the_subset_share_of_the_whole():
    """特約永和中正 佔全部門市: the filter picks the row after the share, the
    window total still covers every group."""

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "share_of_total": True}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "model"},
                    "op": "eq",
                    "values": ["X1"],
                },
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "eq",
                    "values": ["critical"],
                },
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    inner, outer = sql.split(") AS shares")
    assert "devices.model = " not in inner  # the population keeps every model
    assert "alerts.severity = " in inner  # other filters still shape the population
    assert outer.strip().startswith("WHERE model = %(f_")
    assert sql.startswith(
        "SELECT model, row_count_share FROM (SELECT devices.model AS model"
    )
    assert "[after share] devices.model eq X1" in compiled.lineage.filters
    assert any("subset's share of the whole" in a.text for a in compiled.assumptions)
    assert compiled.output_columns == ("model", "row_count_share")


def test_a_current_window_longer_than_its_unit_is_refused_as_future() -> None:
    with pytest.raises(PlanError) as error:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {
                        "kind": "relative",
                        "unit": "day",
                        "offset": 0,
                        "length": 30,
                    },
                },
            }
        )
    assert error.value.code == "relative_window_reaches_future"


def test_growth_on_a_single_period_window_widens_it_to_include_the_previous_one():
    """上週各門市成長率: the window is last week alone, so LAG has nothing;
    the compiler widens it by one grain unit and says so."""

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {
                    "kind": "relative",
                    "unit": "week",
                    "offset": -1,
                    "length": 1,
                },
                "grain": "week",
            },
            "growth": [{"measure": "alerts_n"}],
        }
    )
    params = {p.name: p.value for p in compiled.compiled.execution_parameters}
    # AS_OF is a Tuesday in the fixture helpers: last week plus the one before
    assert params["p1_start_0"] < params["p1_end_1"]
    assert compiled.periods[0].label.endswith("..") is False
    assert any("widened by one week" in a.text for a in compiled.assumptions)
    start, end = compiled.periods[0].start, compiled.periods[0].end_exclusive
    assert (end - start).days == 14
    # a calendar month with grain month is widened the same way, as a range
    monthly = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "month", "month": "2026-07"},
                "grain": "month",
            },
            "growth": [{"measure": "alerts_n"}],
        }
    )
    assert (
        monthly.periods[0].start.month == 6
        and monthly.periods[0].end_exclusive.month == 8
    )
    # a window that already spans two units is left alone
    two = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": -2,
                    "length": 2,
                },
                "grain": "month",
            },
            "growth": [{"measure": "alerts_n"}],
        }
    )
    assert not any("widened" in a.text for a in two.assumptions)


def test_growth_on_a_to_date_window_is_refused() -> None:
    with pytest.raises(PlanError) as error:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "alerts_n"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {
                        "kind": "relative",
                        "unit": "month",
                        "offset": 0,
                        "length": 1,
                        "to_date": True,
                    },
                    "grain": "month",
                },
                "growth": [{"measure": "alerts_n"}],
            }
        )
    assert error.value.code == "growth_to_date_unsupported"


def test_having_count_zero_over_base_rows_is_an_anti_join_refusal() -> None:
    """哪些商品從未出現在銷售明細: every group has a row, so COUNT(*) = 0 never
    matches; refuse with the reason instead of returning nothing."""

    plan = {
        "base_table": "alerts",
        "measures": [{"aggregate": "count", "alias": "alerts_n"}],
        "dimensions": [{"table": "devices", "column": "model"}],
        "having": [{"field": "alerts_n", "op": "eq", "value": 0}],
    }
    with pytest.raises(PlanError) as error:
        compile_plan(plan)
    assert error.value.code == "anti_join_required"
    assert "anti-join" in (error.value.detail or "")
    # counting a nullable column can legitimately be zero for a group
    nullable = dict(plan)
    nullable["measures"] = [
        {
            "aggregate": "count",
            "column": {"table": "alerts", "column": "resolved_at"},
            "alias": "acked",
        }
    ]
    nullable["having"] = [{"field": "acked", "op": "eq", "value": 0}]
    compile_plan(nullable)
    # a non-nullable base column counts every row too: refused like COUNT(*)
    non_null = dict(plan)
    non_null["measures"] = [
        {
            "aggregate": "count",
            "column": {"table": "alerts", "column": "raised_at"},
            "alias": "raised",
        }
    ]
    non_null["having"] = [{"field": "raised", "op": "lte", "value": 0}]
    with pytest.raises(PlanError, match="anti_join_required"):
        compile_plan(non_null)
    # and a threshold other than zero is an ordinary HAVING
    plan["having"] = [{"field": "alerts_n", "op": "lt", "value": 5}]
    compile_plan(plan)


def test_without_compiles_an_anti_join_with_window_filters_and_segments() -> None:
    """哪些裝置本月沒有任何告警: devices with no alerts row in the window; the
    default-excluded test alerts do not count as activity."""

    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
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
            "time_defaults": [
                {
                    "table": "alerts",
                    "column": {"table": "alerts", "column": "raised_at"},
                }
            ],
        }
    )
    plan = QueryPlan.model_validate(
        {
            "base_table": "devices",
            "measures": [{"aggregate": "count", "alias": "device_count"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "without": {
                "table": "alerts",
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "downtime_minutes"},
                        "op": "gt",
                        "values": [0],
                    }
                ],
                "time": {"scope": {"kind": "month", "month": "2026-07"}},
            },
        }
    )
    compiled = PlanCompiler(iot_schema(), overlay=overlay).compile(
        plan, as_of=AS_OF, exclude_segments=overlay.segments
    )
    sql = compiled.compiled.physical_sql
    POLICY.assert_safe_select_statement(sql)
    assert "WHERE NOT EXISTS(SELECT 1 FROM public.alerts WHERE " in sql
    assert "alerts.device_id = devices.device_id" in sql
    assert "alerts.downtime_minutes > %(f_0)s" in sql  # the child's own filter
    assert (
        "alerts.raised_at >= %(w1_start_" in sql
    )  # window from the default time column
    assert "alerts.severity <> %(f_" in sql  # the segment inside the test
    assert "GROUP BY devices.model" in sql
    assert any("[no rows in alerts]" in text for text in compiled.lineage.filters)
    assert any("NOT EXISTS" in a.text for a in compiled.assumptions)
    assert any("do not count as activity" in a.text for a in compiled.assumptions)
    assert compiled.interpretation.endswith("with no alerts rows")
    # a default segment on a table the child reaches applies inside the test too:
    # sites with no alerts, where alerts of decommissioned devices are not activity
    parent_segment = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
            "segments": [
                {
                    "id": "decommissioned",
                    "names": ["已除役"],
                    "table": "devices",
                    "filter": {
                        "column": {"table": "devices", "column": "status"},
                        "op": "eq",
                        "values": ["decommissioned"],
                    },
                    "default_exclude": True,
                    "note": "devices taken out of service",
                }
            ],
        }
    )
    reached = PlanCompiler(iot_schema(), overlay=parent_segment).compile(
        QueryPlan.model_validate(
            {
                "base_table": "sites",
                "measures": [{"aggregate": "count"}],
                "without": {"table": "alerts"},
            }
        ),
        as_of=AS_OF,
        exclude_segments=parent_segment.segments,
    )
    reached_sql = reached.compiled.physical_sql
    assert (
        "NOT EXISTS(SELECT 1 FROM public.alerts INNER JOIN public.devices ON"
        in reached_sql
    )
    assert "devices.status <> %(f_0)s" in reached_sql
    assert "devices.site_id = sites.site_id" in reached_sql
    # a without filter on the segment column lifts the default, as in the main query
    lifted = PlanCompiler(iot_schema(), overlay=overlay).compile(
        QueryPlan.model_validate(
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "without": {
                    "table": "alerts",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "severity"},
                            "op": "eq",
                            "values": ["critical"],
                        }
                    ],
                },
            }
        ),
        as_of=AS_OF,
        exclude_segments=overlay.segments,
    )
    assert "<>" not in lifted.compiled.physical_sql
    # readings reach sites through devices (two hops): allowed. alerts are not
    # referenced by readings at all: refused.
    two_hops = compile_plan(
        {
            "base_table": "sites",
            "measures": [{"aggregate": "count"}],
            "without": {"table": "readings"},
        }
    )
    assert "JOIN public.devices ON readings.device_id = devices.device_id" in (
        two_hops.compiled.physical_sql
    )
    assert "devices.site_id = sites.site_id" in two_hops.compiled.physical_sql
    with pytest.raises(PlanError, match="without_table_not_a_child"):
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "without": {"table": "readings"},
            }
        )
    with pytest.raises(PlanError, match="without_filter_outside_child"):
        compile_plan(
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "without": {
                    "table": "alerts",
                    "filters": [
                        {
                            "column": {"table": "devices", "column": "model"},
                            "op": "eq",
                            "values": ["X1"],
                        }
                    ],
                },
            }
        )
    with pytest.raises(ValueError, match="plan_without_takes_a_window_not_a_grain"):
        QueryPlan.model_validate(
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "without": {
                    "table": "alerts",
                    "time": {
                        "column": {"table": "alerts", "column": "raised_at"},
                        "grain": "month",
                    },
                },
            }
        )


def test_latest_row_per_group_ranks_rows_and_returns_the_taken_columns() -> None:
    """每台裝置最新一筆告警的嚴重度與時間: ROW_NUMBER over the device, the
    primary key breaks ties when only the time column orders."""

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "dimensions": [{"table": "devices", "column": "model"}],
            "latest": {
                "order_by": [{"column": {"table": "alerts", "column": "raised_at"}}],
                "take": [
                    {"table": "alerts", "column": "severity"},
                    {"table": "alerts", "column": "raised_at"},
                ],
            },
            "filters": [
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "ne",
                    "values": ["test"],
                }
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    assert sql.startswith(
        "SELECT model, severity, raised_at FROM (SELECT devices.model AS model"
    )
    assert (
        "ROW_NUMBER() OVER (PARTITION BY devices.model ORDER BY alerts.raised_at DESC "
        "NULLS LAST, alerts.alert_id DESC NULLS LAST) AS latest_rank"
    ) in sql
    assert "WHERE alerts.severity <> %(f_0)s" in sql  # filters before the choice
    assert sql.endswith("AS latest WHERE latest_rank = 1 ORDER BY model NULLS FIRST")
    assert "GROUP BY" not in sql
    assert compiled.output_columns == ("model", "severity", "raised_at")
    assert compiled.lineage.latest == (
        "latest alerts row per devices.model by alerts.raised_at desc, alerts.alert_id "
        "desc; taking alerts.severity, alerts.raised_at",
    )
    assert any("primary key" in a.text for a in compiled.assumptions)
    assert compiled.interpretation.startswith(
        "latest alerts row by alerts.raised_at desc"
    )
    assert compiled.verification == "unverified_semantics"
    # a named tie-breaker is kept as given and no default is added
    named = compile_plan(
        {
            "base_table": "alerts",
            "dimensions": [{"table": "devices", "column": "model"}],
            "latest": {
                "order_by": [
                    {"column": {"table": "alerts", "column": "raised_at"}},
                    {"column": {"table": "alerts", "column": "downtime_minutes"}},
                ],
                "take": [{"table": "alerts", "column": "severity"}],
            },
        }
    )
    assert "alerts.downtime_minutes DESC NULLS LAST) AS latest_rank" in (
        named.compiled.physical_sql
    )
    assert not any("primary key" in a.text for a in named.assumptions)
    # shape rules
    for bad, message in (
        ({"measures": [{"aggregate": "count"}]}, "plan_latest_excludes_aggregates"),
        (
            {
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "grain": "day",
                }
            },
            "plan_latest_takes_a_window_not_a_grain",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            QueryPlan.model_validate(
                {
                    "base_table": "alerts",
                    "latest": {
                        "order_by": [
                            {"column": {"table": "alerts", "column": "raised_at"}}
                        ],
                        "take": [{"table": "alerts", "column": "severity"}],
                    },
                    **bad,
                }
            )
    with pytest.raises(ValueError, match="plan_measures_required"):
        QueryPlan.model_validate({"base_table": "alerts"})


def test_latest_period_with_data_is_resolved_against_the_data_not_as_of() -> None:
    """最新營業日的告警數: the day of the maximum raised_at after the same filters."""

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "model"},
                    "op": "eq",
                    "values": ["X1"],
                }
            ],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "latest", "unit": "day"},
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "alerts.raised_at AT TIME ZONE 'Asia/Taipei' >= DATE_TRUNC('DAY', (SELECT "
        "MAX(alerts.raised_at AT TIME ZONE 'Asia/Taipei') FROM public.alerts LEFT JOIN "
        "public.devices ON alerts.device_id = devices.device_id WHERE devices.model = "
        "%(f_0)s))"
    ) in sql
    assert "< (DATE_TRUNC('DAY', (SELECT MAX(" in sql and "+ INTERVAL '1 day')" in sql
    assert compiled.periods == ()
    assert compiled.lineage.time_window == (
        "alerts.raised_at in the latest day that has rows after the filters "
        "(resolved against the data, not as_of)",
    )
    assert any("most recent day" in a.text for a in compiled.assumptions)
    assert "for the latest day with data" in compiled.interpretation
    # a quarter spans three months; growth cannot look back inside one latest unit
    quarter = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "latest", "unit": "quarter"},
            },
        }
    )
    assert "+ INTERVAL '3 month'" in quarter.compiled.physical_sql
    with pytest.raises(PlanError, match="growth_to_date_unsupported"):
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "alerts_n"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {"kind": "latest", "unit": "month"},
                    "grain": "month",
                },
                "growth": [{"measure": "alerts_n"}],
            }
        )


def test_an_operand_may_carry_its_own_filters_as_a_filter_clause() -> None:
    """會員交易佔比: count of member transactions over count of all, written
    as a ratio whose numerator restricts itself."""

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "alias": "critical_share",
                    "ratio": {
                        "numerator": {
                            "aggregate": "count",
                            "filters": [
                                {
                                    "column": {"table": "alerts", "column": "severity"},
                                    "op": "eq",
                                    "values": ["critical"],
                                }
                            ],
                        },
                        "denominator": {"aggregate": "count"},
                    },
                }
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "CAST((COUNT(*) FILTER(WHERE alerts.severity = %(f_0)s)) AS DOUBLE "
        "PRECISION) / NULLIF(COUNT(*), 0) AS critical_share"
    ) in sql
    assert "WHERE" not in sql.split("FROM")[1]  # the restriction is the operand's alone
    assert (
        "count(*) where alerts.severity eq critical / count(*)"
        in (compiled.lineage.measures[0])
    )
    # a plain measure with its own filter is a FILTER clause too
    single = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "count",
                    "alias": "critical_n",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "severity"},
                            "op": "eq",
                            "values": ["critical"],
                        }
                    ],
                },
                {"aggregate": "count", "alias": "all_n"},
            ],
        }
    )
    assert (
        "COUNT(*) FILTER(WHERE alerts.severity = %(f_0)s) AS critical_n, "
        "COUNT(*) AS all_n" in single.compiled.physical_sql
    )


def test_a_share_with_no_groups_is_the_filtered_part_over_the_whole() -> None:
    # 會員交易佔比 came back as a filtered count with share_of_total and no
    # dimensions: the window total was the same filtered count, so the share
    # was 1.0 (pos-22, reference 0.4643)
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "count",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "device_id"},
                            "op": "not_null",
                        }
                    ],
                    "share_of_total": True,
                    "alias": "assigned_share",
                }
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "CAST((COUNT(*) FILTER(WHERE NOT alerts.device_id IS NULL)) AS DOUBLE "
        "PRECISION) / NULLIF(COUNT(*), 0) AS assigned_share"
    ) in sql
    assert "OVER" not in sql
    assert any("part over the whole" in a.text for a in compiled.assumptions)
    assert compiled.lineage.measures == (
        "assigned_share = count(*) where alerts.device_id not_null"
        " / count(*) [the whole]",
    )
    assert compiled.interpretation.startswith(
        "count(*) where alerts.device_id not_null over all rows"
    )

    # a reviewed metric's defining filters do not make a part: gross_sales
    # excludes returns, and over net sales the "share" came out 1.232
    # (holdout 2 q21); such a plan is refused like an unfiltered one
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"metric": "critical_alerts", "share_of_total": True}],
            }
        )
    assert info.value.code == "share_requires_groups"
    # a metric operand with a filter of its own is the part over that metric
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "metric": "critical_alerts",
                    "share_of_total": True,
                    "filters": [
                        {
                            "column": {"table": "devices", "column": "model"},
                            "op": "eq",
                            "values": ["AP-300"],
                        }
                    ],
                }
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    assert "FILTER(WHERE devices.model = %(f_0)s)" in sql
    assert ") / NULLIF(COUNT(*), 0) AS critical_alerts_share" in sql
    assert sql.endswith("WHERE alerts.severity = %(f_1)s")

    # a share with groups keeps the window total; with a grain, each period's total
    grouped = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "count",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "device_id"},
                            "op": "not_null",
                        }
                    ],
                    "share_of_total": True,
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
        }
    )
    assert "OVER ()" in grouped.compiled.physical_sql

    # without a filter every share would be 1: refused with the remedy in the detail
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "share_of_total": True}],
            }
        )
    assert info.value.code == "share_requires_groups"
    assert "name the groups" in (info.value.detail or "")


def test_a_metric_operand_keeps_its_own_filters() -> None:
    """holdout 2 q22 (店A的銷售額是店B的幾倍) came back as a ratio of the
    gross_sales metric filtered on store A over the same metric filtered on
    store B; the metric expansion dropped both filters, the SQL divided the
    total by itself and answered 1.0 marked verified."""

    def operand(model: str) -> dict:
        return {
            "metric": "critical_alerts",
            "filters": [
                {
                    "column": {"table": "devices", "column": "model"},
                    "op": "eq",
                    "values": [model],
                }
            ],
        }

    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "alias": "a_over_b",
                    "ratio": {"numerator": operand("A"), "denominator": operand("B")},
                }
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    # the metric's own filter is shared by both operands and stays in WHERE;
    # each operand's store filter restricts its aggregate alone
    assert (
        "CAST((COUNT(*) FILTER(WHERE devices.model = %(f_0)s)) AS DOUBLE PRECISION)"
        " / NULLIF(COUNT(*) FILTER(WHERE devices.model = %(f_1)s), 0) AS a_over_b"
    ) in sql
    assert sql.endswith("WHERE alerts.severity = %(f_2)s")
    params = {p.name: p.value for p in compiled.compiled.execution_parameters}
    assert params["f_0"] == "A" and params["f_1"] == "B"
    assert compiled.lineage.measures[0] == (
        "a_over_b = count(*) [critical_alerts] where devices.model eq A / "
        "count(*) [critical_alerts] where devices.model eq B"
    )
    # the plan added filters of its own, so the answer is no longer fully verified
    assert compiled.verification == "partially_verified"


def test_a_literal_that_is_not_a_date_on_a_date_column_is_refused_before_execution():
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "raised_at"},
                        "op": "eq",
                        "values": ["last week"],
                    }
                ],
            }
        )
    assert info.value.code == "filter_kind_mismatch"
    assert "'last week'" in (info.value.detail or "")


def test_a_ratio_of_identical_operands_is_refused_at_validation() -> None:
    # found by the generated-plan properties: count / count is 1 for every row
    with pytest.raises(ValueError, match="plan_ratio_operands_identical"):
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [
                    {
                        "ratio": {
                            "numerator": {"aggregate": "count"},
                            "denominator": {"aggregate": "count"},
                        }
                    }
                ],
            }
        )
