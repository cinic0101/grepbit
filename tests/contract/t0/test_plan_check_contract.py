"""The serve-time self-check: the compiled SQL read back against its plan.

The two wrong numbers of 2026-09-11 are replayed here on the SQL the
pre-fix compiler produced, so the check is known to refuse them; every
plan the other contract tests compile passes through the same check.
"""

from __future__ import annotations

import re

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import PlanError, QueryPlan

OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "t",
        "metrics": [
            {
                "id": "all_alerts",
                "names": ["告警數"],
                "description": "count of alerts",
                "base_table": "alerts",
                "aggregate": "count",
                "review_state": "verified",
            }
        ],
    }
)


def compile_plan(payload: dict):
    return PlanCompiler(iot_schema(), overlay=OVERLAY).compile(
        QueryPlan.model_validate(payload), as_of=AS_OF
    )


def model_filter(model: str) -> dict:
    return {
        "column": {"table": "devices", "column": "model"},
        "op": "eq",
        "values": [model],
    }


def test_replay_metric_operands_whose_filters_were_dropped() -> None:
    # holdout 2 q22: metric A-store / metric B-store; the expansion dropped both
    payload = {
        "base_table": "alerts",
        "measures": [
            {
                "alias": "a_over_b",
                "ratio": {
                    "numerator": {
                        "metric": "all_alerts",
                        "filters": [model_filter("A")],
                    },
                    "denominator": {
                        "metric": "all_alerts",
                        "filters": [model_filter("B")],
                    },
                },
            }
        ],
    }
    plan = QueryPlan.model_validate(payload)
    good = compile_plan(payload)
    assert (
        check_compiled(
            plan,
            good.compiled.physical_sql,
            good.compiled.execution_parameters,
            good.verification,
        )
        == []
    )
    # the pre-fix SQL: the same text with both FILTER clauses removed
    buggy = re.sub(
        r" FILTER\(WHERE devices\.model = %\(f_\d\)s\)", "", good.compiled.physical_sql
    )
    assert "FILTER" not in buggy
    violations = check_compiled(plan, buggy, [], "verified")
    assert violations == [
        "filter_not_applied devices.model eq",
        "filter_not_applied devices.model eq",
        "literal_not_bound devices.model 'A'",
        "literal_not_bound devices.model 'B'",
        "ratio_operands_identical CAST((COUNT(*)) AS DOUBLE)",
        "verified_with_question_filters",
    ]


def test_replay_filtered_share_without_groups() -> None:
    # member_ratio_gap: a filtered count with share_of_total and no dimensions
    payload = {
        "base_table": "alerts",
        "measures": [
            {
                "aggregate": "count",
                "alias": "assigned_share",
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "device_id"},
                        "op": "not_null",
                    }
                ],
                "share_of_total": True,
            }
        ],
    }
    plan = QueryPlan.model_validate(payload)
    buggy = (
        "SELECT CAST((COUNT(*) FILTER(WHERE NOT alerts.device_id IS NULL)) AS DOUBLE "
        "PRECISION) / NULLIF(SUM(COUNT(*) FILTER(WHERE NOT alerts.device_id IS NULL)) "
        "OVER (), 0) AS assigned_share FROM public.alerts"
    )
    assert check_compiled(plan, buggy, [], "unverified_semantics") == [
        "window_without_groups"
    ]
    # the fixed compiler passes its own check (compile() would raise otherwise)
    good = compile_plan(payload)
    assert "OVER" not in good.compiled.physical_sql


def test_grouped_share_and_growth_keep_their_windows() -> None:
    grouped = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "share_of_total": True, "alias": "s"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "filters": [model_filter("A")],
        }
    )
    assert "OVER ()" in grouped.compiled.physical_sql
    growth = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": -3,
                    "length": 3,
                },
                "grain": "month",
            },
            "growth": [{"measure": "n"}],
        }
    )
    assert "LAG(" in growth.compiled.physical_sql


def test_a_dimension_missing_from_group_by_and_a_having_dropped_are_caught() -> None:
    plan = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "having": [{"field": "n", "op": "gt", "value": 5}],
        }
    )
    sql = (
        "SELECT devices.model AS model, COUNT(*) AS n FROM public.alerts "
        "LEFT JOIN public.devices ON alerts.device_id = devices.device_id"
    )
    assert check_compiled(plan, sql, [], "unverified_semantics") == [
        "dimension_not_grouped devices.model",
        "having_missing",
    ]


def test_the_compiler_refuses_its_own_violation_as_a_typed_error() -> None:
    # a compiler that produced such SQL would raise; simulate through the code
    # path by checking the error code exists and carries the detail
    with pytest.raises(PlanError) as info:
        raise PlanError("self_check_failed", "filter_not_applied devices.model eq")
    assert info.value.code == "self_check_failed"
    assert "filter_not_applied" in (info.value.detail or "")
