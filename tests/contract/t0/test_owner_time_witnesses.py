"""Distinguish boundary/month mistakes without mutating active Web data.

Optional GREPBIT_TIME_WITNESS_DSN_ENV names a SELECT-only connection variable.
PostgreSQL executes bound inline VALUES, not setup DDL or customer rows.
"""

import os
from datetime import datetime

import pytest
from t0_helpers import AS_OF, col

from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

ENGINES = ["duck"]
if os.environ.get("GREPBIT_TIME_WITNESS_DSN_ENV"):
    ENGINES += ["UTC", "America/Los_Angeles", "Asia/Taipei"]


def run(engine, points, scope, aggregate):
    schema = SchemaModel(
        datasource_id="time_witness",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(
                name="events",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC, data_type="integer"),
                    col(
                        "occurred_at",
                        ColumnKind.TIMESTAMP,
                        data_type="timestamp with time zone",
                    ),
                    col("amount", ColumnKind.NUMERIC),
                ],
            )
        ],
        foreign_keys=[],
    )
    rows = [
        {"id": i, "occurred_at": datetime.fromisoformat(t), "amount": a}
        for i, (t, a) in enumerate(points, 1)
    ]
    payload = {
        "base_table": "events",
        "measures": [
            {
                "aggregate": aggregate,
                **(
                    {"column": {"table": "events", "column": "amount"}}
                    if aggregate == "avg"
                    else {}
                ),
            }
        ],
    }
    if scope:
        payload["time"] = {
            "column": {"table": "events", "column": "occurred_at"},
            "scope": scope,
        }
    compiled = (
        PlanCompiler(schema)
        .compile(QueryPlan.model_validate(payload), as_of=AS_OF)
        .compiled
    )
    if engine == "duck":
        instance = DuckInstance(schema, {"events": rows})
        try:
            return instance.execute(compiled)[1][0][0]
        finally:
            instance.con.close()
    import psycopg

    params = {p.name: p.value for p in compiled.execution_parameters}
    tuples = []
    for i, row in enumerate(rows):
        fields = []
        for key, typ in [
            ("id", "integer"),
            ("occurred_at", "timestamptz"),
            ("amount", "numeric"),
        ]:
            name = f"w_{i}_{key}"
            params[name] = row[key]
            fields.append(f"%({name})s::{typ}")
        tuples.append("(" + ",".join(fields) + ")")
    assert compiled.physical_sql.count("public.events") == 1
    sql = compiled.physical_sql.replace(
        "public.events", f"(VALUES {','.join(tuples)}) AS events(id,occurred_at,amount)"
    )
    try:
        with psycopg.connect(
            os.environ[os.environ["GREPBIT_TIME_WITNESS_DSN_ENV"]], connect_timeout=5
        ) as con:
            con.execute("BEGIN READ ONLY")
            assert con.execute("SELECT current_user").fetchone()[0] == "grepbit_ro"
            con.execute("SELECT set_config('TimeZone', %s, true)", (engine,))
            con.execute("SELECT set_config('statement_timeout', '5000', true)")
            return con.execute(sql, params).fetchone()[0]
    except psycopg.Error as exc:
        pytest.fail(
            f"postgres_witness:{exc.sqlstate or type(exc).__name__}", pytrace=False
        )


@pytest.mark.parametrize("engine", ENGINES)
def test_last_microsecond_included_next_midnight_excluded(engine):
    points = [
        ("2026-06-30T23:59:59.999999+08:00", 1),
        ("2026-07-01T00:00:00+08:00", 1),
        ("2026-07-07T23:59:59.999999+08:00", 1),
        ("2026-07-08T00:00:00+08:00", 1),
    ]

    def scope(end):
        return {"kind": "range", "start": "2026-07-01", "end_exclusive": end}

    assert run(engine, points, scope("2026-07-08"), "count") == 2
    assert run(engine, points, scope("2026-07-07"), "count") == 1
    assert run(engine, points, scope("2026-07-09"), "count") == 3
    assert run(engine, points, None, "count") == 4


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("amounts", [(10, 30, 90), (20, 60, 200)])
def test_month_average_distinguishes_missing_and_wrong_month(engine, amounts):
    points = list(
        zip(
            [
                "2026-07-01T00:00:00+08:00",
                "2026-07-31T23:59:59.999999+08:00",
                "2026-08-01T00:00:00+08:00",
            ],
            amounts,
            strict=True,
        )
    )
    july = run(engine, points, {"kind": "month", "month": "2026-07"}, "avg")
    assert july == (amounts[0] + amounts[1]) / 2
    assert (
        run(engine, points, {"kind": "month", "month": "2026-08"}, "avg") == amounts[2]
    )
    assert run(engine, points, None, "avg") != july
