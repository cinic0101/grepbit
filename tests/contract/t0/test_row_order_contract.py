"""Unprojected sort-key rulers; projection and visibility remain unchanged."""

import json

import pytest
import sqlglot
from pydantic import ValidationError
from sqlglot import exp
from t0_helpers import AS_OF, iot_schema

from evals.synthetic import DuckInstance
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    _InvalidOutput,
)
from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import OrderSpec, PlanError, QueryPlan


def plan(field="monthly_fee", direction="desc"):
    return QueryPlan(
        base_table="devices",
        rows={"columns": [{"table": "devices", "column": "model"}]},
        order=[{"field": field, "direction": direction}],
        limit=3,
    )


@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_unprojected_numeric_sort_preserves_values_and_ties(direction):
    data = [
        {"device_id": "d3", "model": "same", "monthly_fee": 10},
        {"device_id": "d1", "model": None, "monthly_fee": 10},
        {"device_id": "d4", "model": "null-fee", "monthly_fee": None},
        {"device_id": "d2", "model": "same", "monthly_fee": 20},
    ]
    instance = DuckInstance(iot_schema(), {"devices": data})
    try:
        compiled = PlanCompiler(iot_schema(), allow_rows=True).compile(
            plan(direction=direction), as_of=AS_OF
        )
        nonnull = sorted(
            sorted(data, key=lambda r: r["device_id"]),
            key=lambda r: (
                r["monthly_fee"] is None,
                -(r["monthly_fee"] or 0)
                if direction == "desc"
                else (r["monthly_fee"] or 0),
            ),
        )
        assert instance.execute(compiled.compiled)[1] == [
            (r["model"],) for r in nonnull[:3]
        ]
        assert compiled.output_columns == ("model",)
        assert compiled.lineage.projection == ("devices.model",)
        assert "devices.monthly_fee" in compiled.compiled.semantic_refs
        assert f"monthly_fee {direction}" in compiled.interpretation
        assert any(p.value == 3 for p in compiled.compiled.execution_parameters)
    finally:
        instance.con.close()


def test_explicit_unprojected_pk_does_not_expand_projection():
    compiled = PlanCompiler(iot_schema(), allow_rows=True).compile(
        plan("device_id", "asc"), as_of=AS_OF
    )
    assert compiled.output_columns == ("model",)
    assert '"devices"."device_id" ASC' in compiled.compiled.physical_sql


@pytest.mark.parametrize("field", ["missing", "sites.site_id", "monthly_fee"])
def test_unavailable_or_hidden_order_refuses(field):
    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="sort",
        column_policies=[
            {"column": {"table": "devices", "column": "monthly_fee"}, "visible": False}
        ],
    )
    p = QueryPlan(
        base_table="devices",
        rows={"columns": [{"table": "devices", "column": "model"}]},
    )
    p = p.model_copy(update={"order": [OrderSpec(field=field)]})
    with pytest.raises(PlanError):
        PlanCompiler(iot_schema(), allow_rows=True, overlay=overlay).compile(
            p, as_of=AS_OF
        )


def test_qualified_order_must_refer_to_base_table():
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fake"), allow_rows=True
    )
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "rows": {"columns": ["devices.model"]},
            "order": [{"field": "devices.monthly_fee", "direction": "desc"}],
        },
    }
    proposed = client._validate(json.dumps(payload), iot_schema())
    assert proposed.plan.order[0].field == "monthly_fee"
    payload["plan"]["order"][0]["field"] = "alerts.monthly_fee"
    with pytest.raises(_InvalidOutput):
        client._validate(json.dumps(payload), iot_schema())


def test_aggregate_order_still_requires_output():
    with pytest.raises(ValidationError, match="plan_order_field_unknown"):
        QueryPlan(
            base_table="devices",
            measures=[{"aggregate": "count"}],
            order=[{"field": "monthly_fee"}],
        )


@pytest.mark.parametrize("mutation", ["column", "direction", "nulls", "foreign"])
def test_selfcheck_detects_wrong_explicit_sort(mutation):
    p = plan()
    compiled = PlanCompiler(iot_schema(), allow_rows=True).compile(p, as_of=AS_OF)
    tree = sqlglot.parse_one(compiled.compiled.physical_sql, read="postgres")
    ordered = tree.args["order"].expressions[0]
    if mutation == "column":
        ordered.set("this", exp.column("device_id", table="devices", quoted=True))
    elif mutation == "direction":
        ordered.set("desc", False)
    elif mutation == "nulls":
        ordered.set("nulls_first", True)
    else:
        ordered.set("this", exp.column("monthly_fee", table="alerts", quoted=True))
    failures = check_compiled(
        p,
        tree.sql(dialect="postgres"),
        compiled.compiled.execution_parameters,
        "unverified_semantics",
    )
    assert "row_order_mismatch" in failures


def test_new_row_prompt_and_historical_study_are_versioned_separately():
    from evals.query_kind_study import StudyPlanner

    settings = GroundingModelSettings(base_url="http://unused", model="fake")
    current = ChatCompletionsPlanClient(settings, allow_rows=True)
    historical = StudyPlanner(settings, arm="direct")
    new = current.build_messages("q", iot_schema(), as_of=AS_OF.isoformat())
    old = historical.build_messages("q", iot_schema(), as_of=AS_OF.isoformat())
    assert "even when not projected" in new[0]["content"]
    assert "Order names projected columns." in old[0]["content"]
    assert json.loads(new[2]["content"])["prompt_revision"] == (
        "plan-classify-json-v17-row-order"
    )
    assert json.loads(old[2]["content"])["prompt_revision"] == (
        "plan-classify-json-v16-rows-pilot"
    )
