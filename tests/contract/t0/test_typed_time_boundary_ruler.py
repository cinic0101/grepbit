"""Proposed typed-time policy: hand witnesses, no production time oracle.

Default is isolated DuckDB. Set GREPBIT_TIME_RULER_DSN_ENV to an authorized
DSN variable name for readonly PostgreSQL inline VALUES arms. No DB DDL/data
writes or model calls. Policy decisions are in docs/plan/typed-time-boundary.md.
"""

import os
import re
from datetime import datetime, timedelta
from decimal import Decimal

import duckdb
import pytest
from t0_helpers import AS_OF, col

from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.postgres.introspect import column_kind
from grepbit.adapters.sqlglot.plan_check import check_compiled
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import PlanError, QueryPlan
from grepbit.domain.schema_model import ColumnKind, ForeignKey, SchemaModel, SchemaTable

INSTANT = "timestamp with time zone"
CLOCK = "timestamp without time zone"
ZONES = ("UTC", "Asia/Taipei", "America/New_York")
ENGINES = ["duck"] + (
    ["postgres"] if os.environ.get("GREPBIT_TIME_RULER_DSN_ENV") else []
)


def schema(typ=INSTANT, zone="Asia/Taipei"):
    return SchemaModel(
        datasource_id="typed_time_ruler",
        schema_name="public",
        business_timezone=zone,
        tables=[
            SchemaTable(
                name="entities",
                primary_key=["id"],
                columns=[col("id", ColumnKind.NUMERIC, data_type="integer")],
            ),
            SchemaTable(
                name="events",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC, data_type="integer"),
                    col("entity_id", ColumnKind.NUMERIC, data_type="integer"),
                    col("occurred_at", ColumnKind.TIMESTAMP, data_type=typ),
                    col("created_at", ColumnKind.TIMESTAMP, data_type=typ),
                    col("amount", ColumnKind.NUMERIC),
                ],
            ),
        ],
        foreign_keys=[
            ForeignKey(
                table="events",
                column="entity_id",
                referenced_table="entities",
                referenced_column="id",
            )
        ],
    )


def payload(start, end, location="plan", aggregate="count"):
    filters = [
        {
            "column": {"table": "events", "column": "occurred_at"},
            "op": op,
            "values": [v],
        }
        for op, v in [("gte", start), ("lt", end)]
    ]
    measure = {"aggregate": aggregate, "alias": "answer"}
    if aggregate != "count":
        measure["column"] = {
            "table": "events",
            "column": "amount" if aggregate == "sum" else "entity_id",
        }
    p = {"base_table": "events", "measures": [measure]}
    if location == "without":
        p["base_table"] = "entities"
        p["without"] = {"table": "events", "filters": filters}
    elif location == "operand":
        measure["filters"] = filters
    else:
        p["filters"] = filters
    return QueryPlan.model_validate(p)


def witness(typ=INSTANT, date_only=False):
    suffix = "+08:00" if typ == INSTANT else ""
    start = (
        datetime.fromisoformat("2026-07-08T00:00:00" + suffix)
        if date_only
        else datetime.fromisoformat("2026-07-08T12:00:00" + suffix)
    )
    end = start + (timedelta(days=1) if date_only else timedelta(hours=1))
    points = [
        start - timedelta(microseconds=1),
        start,
        start + timedelta(microseconds=1),
        end - timedelta(microseconds=1),
        end,
        end + timedelta(microseconds=1),
        None,
    ]
    rows = [
        {
            "id": i + 1,
            "entity_id": ent,
            "occurred_at": t,
            "created_at": start - timedelta(days=10),
            "amount": amount,
        }
        for i, (ent, t, amount) in enumerate(
            zip(
                [1, 2, 2, 3, 4, 5, 6],
                points,
                [9, 10, None, 20, 40, 80, 160],
                strict=True,
            )
        )
    ]
    return {"entities": [{"id": i} for i in range(1, 8)], "events": rows}


def execute(compiled, model, data, zone, engine):
    """Independent physical types; intentionally not production DuckInstance."""
    params = {p.name: p.value for p in compiled.execution_parameters}
    if engine == "duck":
        with duckdb.connect() as con:
            con.execute(f"SET TimeZone='{zone}'")
            con.execute("CREATE SCHEMA public")
            for table in model.tables:
                columns = ", ".join(f'"{c.name}" {c.data_type}' for c in table.columns)
                con.execute(f'CREATE TABLE public."{table.name}" ({columns})')
                con.executemany(
                    f'INSERT INTO public."{table.name}" VALUES '
                    f"({', '.join('?' for _ in table.columns)})",
                    [[r.get(c.name) for c in table.columns] for r in data[table.name]],
                )
            sql = re.sub(r"%\((\w+)\)s", r"$\1", compiled.physical_sql)
            return con.execute(sql, params).fetchall()
    import psycopg

    sql = compiled.physical_sql
    for table in model.tables:
        target = f"public.{table.name}"
        if target not in sql:
            continue
        tuples = []
        for i, row in enumerate(data[table.name]):
            fields = []
            for c in table.columns:
                key = f"ruler_{table.name}_{i}_{c.name}"
                params[key] = row.get(c.name)
                fields.append(f"%({key})s::{c.data_type}")
            tuples.append("(" + ", ".join(fields) + ")")
        relation = (
            f"(VALUES {', '.join(tuples)}) AS {table.name} "
            f"({', '.join(c.name for c in table.columns)})"
        )
        sql = sql.replace(target, relation)
    try:
        with psycopg.connect(
            os.environ[os.environ["GREPBIT_TIME_RULER_DSN_ENV"]], connect_timeout=5
        ) as con:
            con.execute("BEGIN READ ONLY")
            assert con.execute("SELECT current_user").fetchone()[0] == "grepbit_ro"
            con.execute("SELECT set_config('TimeZone',%s,true)", (zone,))
            con.execute("SELECT set_config('statement_timeout','5000',true)")
            return con.execute(sql, params).fetchall()
    except psycopg.Error as exc:
        pytest.fail(
            f"postgres_ruler_error:{exc.sqlstate or type(exc).__name__}", pytrace=False
        )


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
@pytest.mark.parametrize("form", ["offset", "naive", "date"])
@pytest.mark.parametrize("location", ["plan", "operand", "without"])
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("engine", ENGINES)
def test_defined_interval_selects_same_population_across_sessions(
    typ, form, location, zone, engine
):
    start, end = (
        ("2026-07-08", "2026-07-09")
        if form == "date"
        else ("2026-07-08T12:00:00", "2026-07-08T13:00:00")
    )
    if form == "offset":
        start += "+08:00"
        end += "+08:00"
    plan = payload(start, end, location)
    compiler = PlanCompiler(schema(typ))
    if typ == CLOCK and form == "offset":
        with pytest.raises(PlanError) as error:
            compiler.compile(plan, as_of=AS_OF)
        assert error.value.code == "timestamp_zone_binding_required"
        return
    compiled = compiler.compile(plan, as_of=AS_OF).compiled
    assert execute(
        compiled, schema(typ), witness(typ, form == "date"), zone, engine
    ) == [(5 if location == "without" else 3,)]


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
def test_synthetic_fixture_preserves_source_timestamp_type(typ):
    instance = DuckInstance(schema(typ), witness(typ))
    try:
        actual = instance.con.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='events' "
            "AND column_name='occurred_at'"
        ).fetchone()[0]
        assert actual == ("TIMESTAMP WITH TIME ZONE" if typ == INSTANT else "TIMESTAMP")
    finally:
        instance.con.close()


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
def test_introspection_keeps_full_type_despite_shared_kind(typ):
    assert column_kind(typ) == ColumnKind.TIMESTAMP
    assert schema(typ).table("events").column("occurred_at").data_type == typ


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
def test_source_type_case_does_not_change_storage_semantics(typ):
    model = schema(typ)
    for name in ["occurred_at", "created_at"]:
        model.table("events").column(name).data_type = typ.upper()
    plan = payload("2026-07-08T12:00:00", "2026-07-08T13:00:00")
    compiled = PlanCompiler(model).compile(plan, as_of=AS_OF)
    assert execute(compiled.compiled, model, witness(typ), "UTC", "duck") == [(3,)]
    instance = DuckInstance(model, witness(typ))
    try:
        assert instance.execute(compiled.compiled)[1] == [(3,)]
    finally:
        instance.con.close()


@pytest.mark.parametrize("location", ["plan", "operand", "without"])
@pytest.mark.parametrize(
    "literal,code",
    [
        ("2026-03-08T02:30:00", "timestamp_local_nonexistent"),
        ("2026-11-01T01:30:00", "timestamp_local_ambiguous"),
        ("2026-07-08T12:00:00.1234567+08:00", "timestamp_precision_unsupported"),
    ],
)
def test_lossy_or_unresolved_instant_is_a_typed_refusal(location, literal, code):
    with pytest.raises(PlanError) as error:
        PlanCompiler(schema(INSTANT, "America/New_York")).compile(
            payload(literal, "2026-12-01T00:00:00-05:00", location), as_of=AS_OF
        )
    assert error.value.code == code


@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("offset", ["-04:00", "-05:00"])
def test_explicit_offsets_distinguish_dst_fold_occurrences(zone, engine, offset):
    model = schema(INSTANT, "America/New_York")
    data = witness()
    data["events"] = [
        {
            "id": i,
            "entity_id": 1,
            "occurred_at": datetime.fromisoformat("2026-11-01T01:30:00" + off),
            "created_at": None,
            "amount": i,
        }
        for i, off in enumerate(["-04:00", "-05:00"], 1)
    ]
    plan = payload(
        "2026-11-01T01:30:00" + offset,
        "2026-11-01T01:30:00.000001" + offset,
        aggregate="sum",
    )
    compiled = PlanCompiler(model).compile(plan, as_of=AS_OF).compiled
    assert execute(compiled, model, data, zone, engine) == [
        (1 if offset == "-04:00" else 2,)
    ]


@pytest.mark.parametrize(
    "aggregate,expected", [("count", 3), ("count_distinct", 2), ("sum", Decimal(30))]
)
def test_reference_respects_business_zone_and_distinguishes_aggregates(
    aggregate, expected
):
    plan = payload("2026-07-08T12:00:00", "2026-07-08T13:00:00", aggregate=aggregate)
    rows = evaluate(plan, schema(), None, AS_OF, witness())
    assert [tuple(r.values()) for r in rows] == [(expected,)]


def test_naive_instant_default_is_disclosed():
    compiled = PlanCompiler(schema()).compile(
        payload("2026-07-08T12:00:00", "2026-07-08T13:00:00"), as_of=AS_OF
    )
    assert any(
        a.definition_ref == "events.occurred_at" and "Asia/Taipei" in a.text
        for a in compiled.assumptions
    )


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("location", ["plan", "without"])
def test_calendar_scope_and_grain_use_source_type(typ, zone, engine, location):
    p = payload("2026-07-08", "2026-07-09", location).model_dump(mode="json")
    target = p if location == "plan" else p["without"]
    target["filters"] = []
    target["time"] = {
        "column": {"table": "events", "column": "occurred_at"},
        "scope": {
            "kind": "range",
            "start": "2026-07-08",
            "end_exclusive": "2026-07-09",
        },
    }
    if location == "plan":
        target["time"]["grain"] = "day"
    compiled = PlanCompiler(schema(typ)).compile(
        QueryPlan.model_validate(p), as_of=AS_OF
    )
    expected = [(datetime(2026, 7, 8), 3)] if location == "plan" else [(5,)]
    assert (
        execute(compiled.compiled, schema(typ), witness(typ, True), zone, engine)
        == expected
    )


def test_date_column_does_not_discard_timestamp_precision():
    model = schema()
    c = model.table("events").column("occurred_at")
    c.kind = ColumnKind.DATE
    c.data_type = "date"
    with pytest.raises(PlanError) as error:
        PlanCompiler(model).compile(
            payload("2026-07-08T12:00:00+08:00", "2026-07-09"), as_of=AS_OF
        )
    assert error.value.code == "date_literal_precision_loss"


def test_selfcheck_verifies_canonical_time_values_not_just_their_presence():
    model = schema()
    plan = payload("2026-07-08T12:00:00", "2026-07-08T13:00:00")
    compiled = PlanCompiler(model).compile(plan, as_of=AS_OF).compiled
    assert not check_compiled(
        plan,
        compiled.physical_sql,
        compiled.execution_parameters,
        "unverified_semantics",
        schema=model,
    )
    parameters = list(compiled.execution_parameters)
    parameters[0] = parameters[0].model_copy(
        update={"value": "2026-07-08T00:00:00+08:00"}
    )
    assert any(
        v.startswith("literal_not_bound")
        for v in check_compiled(
            plan,
            compiled.physical_sql,
            parameters,
            "unverified_semantics",
            schema=model,
        )
    )


@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("engine", ENGINES)
def test_row_filter_and_unprojected_order_retain_typed_time(typ, zone, engine):
    p = payload("2026-07-08T12:00:00", "2026-07-08T13:00:00").model_dump(mode="json")
    p["measures"] = []
    p["rows"] = {"columns": [{"table": "events", "column": "amount"}]}
    p["order"] = [{"field": "occurred_at", "direction": "desc"}]
    p["limit"] = 2
    compiled = PlanCompiler(schema(typ), allow_rows=True).compile(
        QueryPlan.model_validate(p), as_of=AS_OF
    )
    assert execute(compiled.compiled, schema(typ), witness(typ), zone, engine) == [
        (20,),
        (None,),
    ]


@pytest.mark.parametrize("location", ["plan", "operand", "without"])
@pytest.mark.parametrize("typ", [INSTANT, CLOCK])
def test_reference_population_uses_physical_type_at_every_scope(location, typ):
    rows = evaluate(
        payload("2026-07-08T12:00:00", "2026-07-08T13:00:00", location),
        schema(typ),
        None,
        AS_OF,
        witness(typ),
    )
    assert [tuple(r.values()) for r in rows] == [(5 if location == "without" else 3,)]
