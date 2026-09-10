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
    assert sql.startswith("SELECT * FROM (SELECT devices.model AS model")
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
