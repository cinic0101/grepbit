"""Pending parent-projection checkpoint, deliberately not in default discovery.

Run explicitly with tools/verify.py focused --tests <this file>. These are real
red acceptance rulers, not skips or xfails. Rename to test_parent_rows.py when
the contract is approved and implemented. No live database/model is required.
"""

import pytest
from pydantic import ValidationError
from t0_helpers import AS_OF, col

from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import ColumnRef, PlanError, QueryPlan, RowProjection
from grepbit.domain.schema_model import ColumnKind, ForeignKey, SchemaModel, SchemaTable


def schema():
    return SchemaModel(
        datasource_id="parent_ruler",
        schema_name="public",
        business_timezone="UTC",
        tables=[
            SchemaTable(
                name="records",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("parent_id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("other_parent_id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("name", ColumnKind.TEXT),
                ],
            ),
            SchemaTable(
                name="parents",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("name", ColumnKind.TEXT),
                ],
            ),
        ],
        foreign_keys=[
            ForeignKey(
                table="records",
                column="parent_id",
                referenced_table="parents",
                referenced_column="id",
            )
        ],
    )


def wire(**extra):
    return {
        "base_table": "records",
        "rows": {
            "columns": [
                {"table": "records", "column": "name"},
                {"table": "parents", "column": "name"},
            ]
        },
        **extra,
    }


def compile_wire(payload, *, source=None, overlay=None, enabled=True):
    return PlanCompiler(
        source or schema(), overlay=overlay, allow_rows=enabled
    ).compile(
        QueryPlan.model_validate(payload),
        as_of=AS_OF,
    )


def accepted(payload, **kwargs):
    try:
        return compile_wire(payload, **kwargs)
    except (ValidationError, PlanError) as exc:
        pytest.fail(f"Unique parent projection must be accepted, got: {exc}")


@pytest.mark.parametrize("variant", ["shared", "null_name", "empty_parent"])
def test_parent_projection_preserves_base_records_and_nulls(variant):
    # Both records referencing parent 1 must survive; parent_id=NULL is valid
    # under a declared FK and must not vanish through an INNER JOIN.
    data = {
        "records": [
            {"id": 1, "parent_id": 1, "name": "same"},
            {"id": 2, "parent_id": 1, "name": "same"},
            {"id": 3, "parent_id": None, "name": None},
        ],
        "parents": [{"id": 1, "name": "P"}],
    }
    if variant == "null_name":
        data["parents"][0]["name"] = None
    if variant == "empty_parent":
        data["parents"] = []
        for row in data["records"]:
            row["parent_id"] = None
    compiled = accepted(wire())
    instance = DuckInstance(schema(), data)
    try:
        columns, rows = instance.execute(compiled.compiled)
        parent_name = "P" if variant == "shared" else None
        assert columns == ["name", "parents.name"]
        assert rows == [("same", parent_name), ("same", parent_name), (None, None)]
    finally:
        instance.con.close()
    assert compiled.output_columns == ("name", "parents.name")
    assert compiled.lineage.projection == ("records.name", "parents.name")
    assert compiled.verification == "unverified_semantics"


def test_base_filter_and_unprojected_order_keep_their_scope():
    compiled = accepted(
        wire(
            filters=[
                {
                    "column": {"table": "records", "column": "id"},
                    "op": "gte",
                    "values": [2],
                }
            ],
            order=[{"field": "id", "direction": "desc"}],
            limit=1,
        )
    )
    instance = DuckInstance(
        schema(),
        {
            "records": [
                {"id": 1, "parent_id": 1, "name": "first"},
                {"id": 2, "parent_id": 1, "name": "second"},
                {"id": 3, "parent_id": None, "name": "third"},
            ],
            "parents": [{"id": 1, "name": "P"}],
        },
    )
    try:
        assert instance.execute(compiled.compiled)[1] == [("third", None)]
    finally:
        instance.con.close()


def test_parent_only_projection_does_not_change_record_unit():
    result = accepted(wire(rows={"columns": [{"table": "parents", "column": "id"}]}))
    assert result.output_columns == ("parents.id",)
    assert "DISTINCT" not in result.compiled.physical_sql


def test_all_columns_remains_base_only():
    result = compile_wire(wire(rows={"all_columns": True}))
    assert result.output_columns == ("id", "parent_id", "other_parent_id", "name")
    assert not any(r.startswith("parents.") for r in result.lineage.projection)


@pytest.mark.parametrize(
    "hazard", ["inferred", "ambiguous", "nonkey", "composite", "reverse"]
)
def test_unproved_or_ambiguous_parent_is_rejected(hazard):
    source = schema()
    if hazard == "inferred":
        source.foreign_keys[0].inferred = True
    elif hazard == "ambiguous":
        source.foreign_keys.append(
            source.foreign_keys[0].model_copy(update={"column": "other_parent_id"})
        )
    elif hazard == "nonkey":
        source.tables[1].primary_key = []
    elif hazard == "composite":
        source.tables[1].primary_key = ["id", "name"]
    else:
        source.foreign_keys = [
            ForeignKey(
                table="parents",
                column="id",
                referenced_table="records",
                referenced_column="id",
            )
        ]
    with pytest.raises((ValidationError, PlanError)):
        compile_wire(wire(), source=source)


@pytest.mark.parametrize("hidden", ["name", "id"])
def test_hidden_parent_projection_or_join_key_cannot_leak(hidden):
    overlay = SemanticOverlay(
        datasource_id="parent_ruler",
        revision="ruler",
        column_policies=[
            {"column": {"table": "parents", "column": hidden}, "visible": False}
        ],
    )
    with pytest.raises((ValidationError, PlanError)):
        compile_wire(wire(), overlay=overlay)


@pytest.mark.parametrize(
    "extra",
    [
        {
            "filters": [
                {
                    "column": {"table": "parents", "column": "name"},
                    "op": "eq",
                    "values": ["P"],
                }
            ]
        },
        {"order": [{"field": "parents.name"}]},
        {"without": {"table": "parents"}},
    ],
)
def test_parent_projection_does_not_enable_other_constructs(extra):
    with pytest.raises((ValidationError, PlanError)):
        compile_wire(wire(**extra))


def test_disabled_rows_permission_stays_closed():
    with pytest.raises((ValidationError, PlanError)):
        compile_wire(wire(), enabled=False)


def test_checker_accepts_qualified_parent_alias_without_certifying_intent():
    # Typed specification independent of current parser's base-only restriction.
    plan = QueryPlan.model_construct(
        base_table="records",
        rows=RowProjection(
            columns=[
                ColumnRef(table="records", column="name"),
                ColumnRef(table="parents", column="name"),
            ]
        ),
    )
    sql = (
        'SELECT records.name, parents.name AS "parents.name" FROM records '
        "LEFT JOIN parents ON records.parent_id = parents.id ORDER BY records.id"
    )
    assert check_compiled(plan, sql, [], "unverified_semantics", schema=schema()) == []


def test_catalog_query_does_not_flatten_composite_or_cross_schema_edges():
    # Static checkpoint: the adapter currently exposes one-column ForeignKey,
    # so require the catalog selection to exclude relations it cannot represent.
    import inspect

    from grepbit.adapters.postgres.introspect import introspect_schema

    source = inspect.getsource(introspect_schema)
    assert "cardinality(con.conkey) = 1" in source
    assert "cardinality(con.confkey) = 1" in source
    assert "rcl.relnamespace = cl.relnamespace" in source


@pytest.mark.parametrize(
    "join",
    [
        "INNER JOIN parents ON records.parent_id = parents.id",
        "LEFT JOIN parents ON records.other_parent_id = parents.id",
        "CROSS JOIN parents",
        "LEFT JOIN parents ON records.parent_id = parents.id "
        "LEFT JOIN parents AS extra ON records.parent_id = extra.id",
    ],
)
def test_checker_rejects_unproved_join_even_with_base_only_projection(join):
    plan = QueryPlan.model_validate(
        {
            "base_table": "records",
            "rows": {"columns": [{"table": "records", "column": "name"}]},
        }
    )
    sql = f"SELECT records.name FROM records {join} ORDER BY records.id"
    assert check_compiled(plan, sql, [], "unverified_semantics", schema=schema()), (
        "Rows self-check must reject extra/unproved joins, not only inspect SELECT"
    )


def test_reference_fixture_distinguishes_inner_join_and_deduplication():
    instance = DuckInstance(
        schema(),
        {
            "records": [
                {"id": 1, "parent_id": 1, "name": "same"},
                {"id": 2, "parent_id": 1, "name": "same"},
                {"id": 3, "parent_id": None, "name": None},
            ],
            "parents": [{"id": 1, "name": "P"}],
        },
    )
    try:
        sql = (
            "SELECT records.name, parents.name FROM public.records "
            "LEFT JOIN public.parents ON records.parent_id = parents.id"
        )
        gold = instance.con.execute(sql).fetchall()
        assert sorted(gold, key=str) == sorted(
            [("same", "P"), ("same", "P"), (None, None)], key=str
        )
        assert (
            instance.con.execute(sql.replace("LEFT JOIN", "INNER JOIN")).fetchall()
            != gold
        )
        assert (
            instance.con.execute(sql.replace("SELECT", "SELECT DISTINCT")).fetchall()
            != gold
        )
    finally:
        instance.con.close()
