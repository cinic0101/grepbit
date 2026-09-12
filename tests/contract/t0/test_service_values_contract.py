"""Hand-counted non-POS rulers; neither engine supplies the expected answer."""

from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
import pytest
import yaml
from hypothesis import find, settings
from hypothesis import strategies as st
from t0_helpers import ROOT

from evals.differential import compare
from evals.plan_generator import SchemaShape, draw_plan
from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import PlanError, QueryPlan
from grepbit.domain.schema_model import SchemaModel

AS_OF = datetime.fromisoformat("2026-04-15T12:00:00+08:00")


def service_data():
    """Read the checked-in fictional DDL, including its non-PK FK targets."""
    folder = ROOT / "evals/fixtures/service_v1"
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Taipei'")
        con.execute((folder / "schema.sql").read_text())
        con.execute((folder / "seed.sql").read_text())
        constraints = con.execute(
            "SELECT table_name, constraint_type, constraint_column_names, "
            "referenced_table, referenced_column_names FROM duckdb_constraints()"
        ).fetchall()
        tables, data = [], {}
        for (name,) in con.execute("SHOW TABLES").fetchall():
            columns = []
            for column, dtype, nullable, *_ in con.execute(
                f'DESCRIBE "{name}"'
            ).fetchall():
                kind = (
                    "timestamp"
                    if dtype.startswith("TIMESTAMP")
                    else "text"
                    if dtype == "VARCHAR"
                    else "numeric"
                )
                columns.append(
                    dict(
                        name=column,
                        data_type=dtype,
                        kind=kind,
                        nullable=nullable == "YES",
                    )
                )
            pk = next(c[2] for c in constraints if c[:2] == (name, "PRIMARY KEY"))
            tables.append(dict(name=name, primary_key=pk, columns=columns))
            cursor = con.execute(f'SELECT * FROM "{name}"')
            names = [item[0] for item in cursor.description]
            data[name] = [
                dict(zip(names, row, strict=True)) for row in cursor.fetchall()
            ]
        fks = [
            dict(
                table=t,
                column=cols[0],
                referenced_table=parent,
                referenced_column=refs[0],
            )
            for t, kind, cols, parent, refs in constraints
            if kind == "FOREIGN KEY"
        ]
    return SchemaModel.model_validate(
        dict(
            datasource_id="service_test",
            schema_name="public",
            business_timezone="Asia/Taipei",
            tables=tables,
            foreign_keys=fks,
        )
    ), data


def ref(table, column):
    return dict(table=table, column=column)


def measure(aggregate="count", column=None, **extra):
    result = dict(aggregate=aggregate, **extra)
    if column is not None:
        result["column"] = ref(*column)
    return result


def plan(base, measures=None, **extra):
    return dict(base_table=base, measures=measures or [measure(alias="n")], **extra)


CASES = [
    (
        "three_hop_natural_keys",
        plan(
            "work_logs",
            [measure("sum", ("work_logs", "minutes"), alias="n")],
            dimensions=[ref("teams", "team_code")],
        ),
        [("T-N", 349), ("T-S", 150)],
    ),
    (
        "logs_are_not_tickets",
        plan(
            "work_logs",
            [
                measure(alias="logs"),
                measure("count_distinct", ("work_logs", "ticket_id"), alias="tickets"),
            ],
        ),
        [(10, 7)],
    ),
    (
        "events_are_not_tickets",
        plan(
            "ticket_events",
            [
                measure(alias="events"),
                measure(
                    "count_distinct", ("ticket_events", "ticket_id"), alias="tickets"
                ),
            ],
        ),
        [(9, 5)],
    ),
    (
        "two_hop_without",
        plan(
            "projects",
            without={"table": "work_logs"},
            dimensions=[ref("projects", "project_key")],
        ),
        [("EMPTY", 1)],
    ),
    (
        "three_hop_without",
        plan(
            "teams",
            without={"table": "work_logs"},
            dimensions=[ref("teams", "team_code")],
        ),
        [("T-E", 1)],
    ),
    (
        "without_child_window",
        plan(
            "teams",
            without={
                "table": "work_logs",
                "time": {
                    "column": ref("work_logs", "logged_at"),
                    "scope": {"kind": "month", "month": "2026-02"},
                },
            },
            dimensions=[ref("teams", "team_code")],
        ),
        [("T-E", 1), ("T-N", 1)],
    ),
    (
        "without_child_filter",
        plan(
            "projects",
            without={
                "table": "ticket_events",
                "filters": [
                    {
                        "column": ref("ticket_events", "event_type"),
                        "op": "eq",
                        "values": ["closed"],
                    }
                ],
            },
            dimensions=[ref("projects", "project_key")],
        ),
        [("EMPTY", 1), ("PN-2", 1)],
    ),
    (
        "without_sum",
        plan(
            "tickets",
            [measure("sum", ("tickets", "estimate_minutes"), alias="n")],
            without={"table": "ticket_events"},
        ),
        [(99,)],
    ),
    (
        "created_feb",
        plan(
            "tickets",
            time={
                "column": ref("tickets", "created_at"),
                "scope": {"kind": "month", "month": "2026-02"},
            },
        ),
        [(1,)],
    ),
    (
        "closed_feb",
        plan(
            "tickets",
            time={
                "column": ref("tickets", "closed_at"),
                "scope": {"kind": "month", "month": "2026-02"},
            },
        ),
        [(2,)],
    ),
    (
        "filtered_share",
        plan(
            "tickets",
            [
                measure(
                    alias="fraction",
                    share_of_total=True,
                    filters=[
                        {
                            "column": ref("tickets", "status"),
                            "op": "eq",
                            "values": ["open"],
                        }
                    ],
                )
            ],
        ),
        [(0.5,)],
    ),
    (
        "ratio_filter",
        plan(
            "tickets",
            [
                {
                    "alias": "fraction",
                    "ratio": {
                        "numerator": measure(
                            filters=[
                                {
                                    "column": ref("tickets", "status"),
                                    "op": "eq",
                                    "values": ["open"],
                                }
                            ]
                        ),
                        "denominator": measure(),
                    },
                }
            ],
        ),
        [(0.5,)],
    ),
]


CASES.extend(
    [
        (
            "without_ratio",
            plan(
                "tickets",
                [
                    {
                        "alias": "n",
                        "ratio": {
                            "numerator": measure(
                                "sum", ("tickets", "estimate_minutes")
                            ),
                            "denominator": measure(),
                        },
                    }
                ],
                without={"table": "ticket_events"},
            ),
            [(33.0,)],
        ),
        (
            "without_share",
            plan(
                "tickets",
                [measure(alias="fraction", share_of_total=True)],
                without={"table": "ticket_events"},
                dimensions=[ref("tickets", "project_key")],
            ),
            [("PN-1", 1 / 3), ("PN-2", 2 / 3)],
        ),
        (
            "without_having",
            plan(
                "tickets",
                without={"table": "ticket_events"},
                dimensions=[ref("tickets", "project_key")],
                having=[{"field": "n", "op": "gt", "value": 1}],
            ),
            [("PN-2", 2)],
        ),
        (
            "without_order_limit",
            plan(
                "tickets",
                without={"table": "ticket_events"},
                dimensions=[ref("tickets", "id")],
                order=[{"field": "id", "direction": "desc"}],
                limit=1,
            ),
            [(8, 1)],
        ),
        (
            "without_null_sum",
            plan(
                "tickets",
                [measure("sum", ("tickets", "estimate_minutes"), alias="n")],
                without={"table": "work_logs"},
            ),
            [(None,)],
        ),
        (
            "without_growth",
            plan(
                "tickets",
                without={"table": "ticket_events"},
                time={"column": ref("tickets", "created_at"), "grain": "month"},
                growth=[{"measure": "n"}],
            ),
            [(datetime(2026, 1, 1), 1, None), (datetime(2026, 3, 1), 1, None)],
        ),
    ]
)


@pytest.fixture(scope="module")
def fixture():
    return service_data()


@pytest.mark.parametrize("engine", ["compiled", "reference"])
@pytest.mark.parametrize("case_id,payload,expected", CASES, ids=[c[0] for c in CASES])
def test_service_hand_counted_values(fixture, engine, case_id, payload, expected):
    schema, tables = fixture
    query = QueryPlan.model_validate(payload)
    if engine == "reference":
        rows = evaluate(query, schema, None, AS_OF, tables)
        values = [tuple(row.values()) for row in rows]
        if case_id == "without_order_limit":
            # The reference deliberately returns the full population. LIMIT
            # belongs to differential.compare, which must reject the wrong top-1.
            assert sorted(values) == [(4, 1), (7, 1), (8, 1)]
            assert compare(
                query, ["id", "n"], expected, values, ZoneInfo("Asia/Taipei")
            )
            assert not compare(
                query, ["id", "n"], [(4, 1)], values, ZoneInfo("Asia/Taipei")
            )
            return
    else:
        compiled = PlanCompiler(schema).compile(query, as_of=AS_OF)
        instance = DuckInstance(schema, tables)
        try:
            _, values = instance.execute(compiled.compiled)
        finally:
            instance.con.close()
    assert sorted(values) == sorted(expected), case_id


@pytest.mark.parametrize(
    "payload,code",
    [
        (
            plan("team_links", dimensions=[ref("teams", "team_name")]),
            "ambiguous_join_path",
        ),
        (
            plan(
                "work_logs",
                [
                    measure("sum", ("work_logs", "minutes")),
                    measure("count_distinct", ("ticket_events", "id")),
                ],
            ),
            "grain_conflict",
        ),
    ],
)
def test_service_ambiguous_and_fanout_joins_refuse(fixture, payload, code):
    with pytest.raises(PlanError) as caught:
        PlanCompiler(fixture[0]).compile(QueryPlan.model_validate(payload), as_of=AS_OF)
    assert caught.value.code == code


def test_service_generator_reaches_multihop_activity(fixture):
    shape = SchemaShape(fixture[0])
    assert {"tickets", "work_logs", "ticket_events"} <= set(shape.children("teams"))
    assert "teams" not in shape.children("teams")


def test_service_generator_does_not_reduce_absence_to_count_only(fixture):
    shape = SchemaShape(fixture[0])

    @st.composite
    def plans(draw):
        class Choices:
            def draw(self, strategy):
                return draw(strategy)

        return draw_plan(Choices(), shape)

    result = find(
        plans(),
        lambda p: (
            bool(p.get("without"))
            and any(m.get("aggregate") != "count" for m in p.get("measures", []))
        ),
        settings=settings(
            max_examples=500, deadline=None, database=None, derandomize=True
        ),
    )
    assert result["without"] and result["measures"]


def test_service_adversarial_goldens_are_hand_counted():
    folder = ROOT / "evals/fixtures/service_v1"
    cases = yaml.safe_load(
        (ROOT / "evals/cases/tier0/service_adversarial.yaml").read_text()
    )["cases"]
    assert len(cases) == 12
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Taipei'")
        con.execute((folder / "schema.sql").read_text())
        con.execute((folder / "seed.sql").read_text())
        for case in cases:
            expected = (
                [(99,)]
                if case["case_id"].startswith("svc_absent_sum_")
                else [("北區／維運中心（第二期）", 1), ("東京・検証専用チーム", 1)]
                if case["case_id"].startswith("svc_absent_feb_")
                else [(10, 7)]
                if case["case_id"].startswith("svc_units_")
                else [(2,)]
            )
            assert sorted(con.execute(case["reference_sql"]).fetchall()) == sorted(
                expected
            )
