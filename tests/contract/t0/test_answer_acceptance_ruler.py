"""Approved rulers; the new grader lives beside the unchanged legacy matcher.

Original strict-xfail evidence is retained in the checkpoint artifacts. The
implementation tests require relevance, value proof and faithful disclosure.
"""

from datetime import date

import pytest
from t0_helpers import AS_OF, ROOT, col

from evals.spike_tier0 import match_reference, normalize_rows
from grepbit.adapters.litellm.plan_client import schema_payload
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.grounding import ValueIndex
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable


def payroll_schema():
    return SchemaModel(
        datasource_id="pos_test",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(
                name="hr_payroll",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC),
                    col("base_salary", ColumnKind.NUMERIC),
                    col("paid_at", ColumnKind.DATE, comment="實發日期"),
                    col("period_start", ColumnKind.DATE, comment="薪資週期起日"),
                ],
            )
        ],
    )


def payroll_plan(metric=False):
    return QueryPlan.model_validate(
        {
            "base_table": "hr_payroll",
            "measures": [
                {"metric": "base_salary_total"}
                if metric
                else {
                    "aggregate": "sum",
                    "column": {"table": "hr_payroll", "column": "base_salary"},
                }
            ],
            "time": {
                "column": {"table": "hr_payroll", "column": "paid_at"},
                "grain": "quarter",
                "scope": {
                    "kind": "range",
                    "start": "2025-01-01",
                    "end_exclusive": "2026-01-01",
                },
            },
        }
    )


def test_both_payroll_column_comments_reach_the_model_payload():
    payload = schema_payload(payroll_schema())
    columns = payload["tables"][0]["columns"]
    assert {c["name"]: c["comment"] for c in columns if c["comment"]} == {
        "paid_at": "實發日期",
        "period_start": "薪資週期起日",
    }


@pytest.mark.parametrize("metric", [False, True])
def test_loading_an_overlay_does_not_force_raw_plans_to_use_its_metric(metric):
    overlay = load_semantic_overlay(ROOT / "evals/fixtures/pos_overlay.json")
    compiled = PlanCompiler(payroll_schema(), overlay=overlay).compile(
        payroll_plan(metric), as_of=AS_OF
    )
    sql = compiled.compiled.physical_sql.replace('"', "")
    assert ("hr_payroll.period_start" in sql) == metric
    assert ("hr_payroll.paid_at" in sql) != metric


def test_partial_name_has_no_verbatim_hint_but_can_resolve_after_literal_miss():
    index = ValueIndex({"store.store_name": ["特約新店遠東"]})
    assert index.mentions("2026年1月新店遠東的營業額") == []
    result = index.resolve("store.store_name", "新店遠東")
    assert result.kind == "unique" and result.value == "特約新店遠東"


def test_partial_name_does_not_auto_resolve_a_tie():
    index = ValueIndex({"store.store_name": ["特約新店遠東", "直營新店遠東"]})
    assert index.resolve("store.store_name", "新店遠東").kind == "ambiguous"


def test_a_column_not_in_the_index_cannot_be_grounded():
    assert ValueIndex({}).resolve("store.store_name", "新店遠東").kind == "none"


def comparison_plan():
    return QueryPlan.model_validate(
        {
            "base_table": "sales",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "sales", "column": "amount"},
                    "alias": "sales",
                }
            ],
            "time": {
                "column": {"table": "sales", "column": "day"},
                "grain": "month",
            },
            "growth": [{"measure": "sales"}],
        }
    )


REFERENCE = [(date(2026, 1, 1), 100), (date(2026, 2, 1), 200)]
WITH_GROWTH = [
    {"period_start": date(2026, 1, 1), "sales": 100, "sales_growth": None},
    {"period_start": date(2026, 2, 1), "sales": 200, "sales_growth": 1},
]


def test_growth_ruler_has_independently_checkable_values_and_same_core_rows():
    assert normalize_rows(
        [(r["period_start"], r["sales"]) for r in WITH_GROWTH]
    ) == normalize_rows(REFERENCE)
    assert WITH_GROWTH[1]["sales_growth"] == (200 - 100) / 100
    assert WITH_GROWTH[0]["sales_growth"] is None


def test_legacy_matcher_remains_unchanged_under_separate_acceptance_policy():
    matched, _ = match_reference(
        WITH_GROWTH, comparison_plan(), [normalize_rows(REFERENCE)]
    )
    assert matched is None, "the new scorer must not rewrite legacy agreement"


@pytest.mark.parametrize("kind", ["wrong_growth", "wrong_core", "missing_row"])
def test_existing_comparator_still_rejects_invalid_comparison_controls(kind):
    rows = [dict(row) for row in WITH_GROWTH]
    if kind == "wrong_growth":
        rows[1]["sales_growth"] = 7
    elif kind == "wrong_core":
        rows[1]["sales"] = 999
    else:
        rows.pop()
    assert (
        match_reference(rows, comparison_plan(), [normalize_rows(REFERENCE)])[0] is None
    )
