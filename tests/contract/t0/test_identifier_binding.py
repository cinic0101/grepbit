"""Exact PostgreSQL identifier identity, not SQLGlot spelling alone."""

import pytest
import sqlglot
from sqlglot import exp
from t0_helpers import AS_OF, col

from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, ForeignKey, SchemaModel, SchemaTable


def source():
    return SchemaModel(
        datasource_id="identifier_ruler",
        schema_name="MixedSchema",
        business_timezone="UTC",
        tables=[
            SchemaTable(
                name="Records",
                primary_key=["Id"],
                columns=[
                    col(n, ColumnKind.NUMERIC, data_type="bigint")
                    for n in ["Id", "ParentId", "parentid", "Value", "value"]
                ]
                + [col("RecordedAt", ColumnKind.DATE, data_type="date")],
            ),
            SchemaTable(
                name="Parents",
                primary_key=["Id"],
                columns=[
                    col("Id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("Label", ColumnKind.TEXT),
                ],
            ),
        ],
        foreign_keys=[
            ForeignKey(
                table="Records",
                column="ParentId",
                referenced_table="Parents",
                referenced_column="Id",
            )
        ],
    )


def ref(table, column):
    return {"table": table, "column": column}


def payload(kind):
    p = {"base_table": "Records"}
    value_filter = {"column": ref("Records", "Value"), "op": "gt", "values": [5]}
    if kind == "rows":
        p.update(rows={"columns": [ref("Records", "Id"), ref("Parents", "Label")]})
    elif kind == "aggregate":
        p.update(
            measures=[
                {
                    "aggregate": "sum",
                    "column": ref("Records", "Value"),
                    "alias": "Total",
                }
            ],
            dimensions=[ref("Parents", "Label")],
        )
    elif kind == "operand":
        p.update(
            measures=[
                {"aggregate": "count", "alias": "Total", "filters": [value_filter]}
            ]
        )
    elif kind == "without":
        p.update(
            base_table="Parents",
            dimensions=[ref("Parents", "Label")],
            measures=[{"aggregate": "count", "alias": "Total"}],
            without={"table": "Records", "filters": [value_filter]},
        )
    elif kind == "latest":
        p.update(
            dimensions=[ref("Parents", "Label")],
            latest={
                "order_by": [
                    {"column": ref("Records", "RecordedAt"), "direction": "desc"}
                ],
                "take": [ref("Records", "Value")],
            },
        )
    elif kind == "latest_scope":
        p.update(
            measures=[
                {
                    "aggregate": "sum",
                    "column": ref("Records", "Value"),
                    "alias": "Total",
                }
            ],
            dimensions=[ref("Parents", "Label")],
            time={
                "column": ref("Records", "RecordedAt"),
                "scope": {"kind": "latest", "unit": "month"},
            },
        )
    else:
        raise AssertionError(kind)
    return p


KINDS = ["rows", "aggregate", "operand", "without", "latest", "latest_scope"]


@pytest.mark.parametrize("kind", KINDS)
def test_all_paths_preserve_case_sensitive_identifiers(kind):
    plan = QueryPlan.model_validate(payload(kind))
    compiled = PlanCompiler(source(), allow_rows=True).compile(plan, as_of=AS_OF)
    tree = sqlglot.parse_one(compiled.compiled.physical_sql, read="postgres")
    unsafe = [
        i.name
        for i in tree.find_all(exp.Identifier)
        if any("A" <= c <= "Z" for c in i.name) and not i.args.get("quoted")
    ]
    assert unsafe == [], unsafe
    assert (
        check_compiled(
            plan,
            compiled.compiled.physical_sql,
            compiled.compiled.execution_parameters,
            compiled.verification,
            schema=source(),
        )
        == []
    )


@pytest.mark.parametrize("kind", KINDS)
def test_selfcheck_rejects_removing_each_necessary_quote(kind):
    plan = QueryPlan.model_validate(payload(kind))
    compiled = PlanCompiler(source(), allow_rows=True).compile(plan, as_of=AS_OF)
    # Independently establish the correctly quoted SQL even before the repair.
    tree = sqlglot.parse_one(compiled.compiled.physical_sql, read="postgres")
    for node in tree.find_all(exp.Identifier):
        if any("A" <= c <= "Z" for c in node.name):
            node.set("quoted", True)
    targets = [
        i
        for i in tree.find_all(exp.Identifier)
        if any("A" <= c <= "Z" for c in i.name) and "." not in i.name
    ]
    assert targets
    for target in targets:
        target.set("quoted", False)
        violations = check_compiled(
            plan,
            tree.sql(dialect="postgres"),
            compiled.compiled.execution_parameters,
            compiled.verification,
            schema=source(),
        )
        assert "identifier_case_unquoted" in violations, (kind, target.name, violations)
        target.set("quoted", True)


def test_lowercase_unquoted_identifiers_remain_legal():
    plan = QueryPlan.model_validate(
        {"base_table": "records", "measures": [{"aggregate": "count"}]}
    )
    assert (
        check_compiled(
            plan,
            "SELECT COUNT(*) AS count_rows FROM public.records",
            [],
            "unverified_semantics",
        )
        == []
    )
