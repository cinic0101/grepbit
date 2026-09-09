"""Column and table policies: switches, hiding in payload and compiler, proposer."""

from __future__ import annotations

import pytest
from t0_helpers import AS_OF, col, iot_schema

from grepbit.adapters.litellm.plan_client import schema_payload
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.overlay import overlay_problems
from grepbit.application.policies import propose_policies
from grepbit.domain.overlay import ColumnPolicy, SemanticOverlay
from grepbit.domain.plan import PlanError, QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "t",
        "column_policies": [
            {
                "column": {"table": "devices", "column": "model"},
                "sensitivity": "public",
            },
            {
                "column": {"table": "devices", "column": "status"},
                "sensitivity": "personal",
                "visible": False,
            },
            {
                "column": {"table": "alerts", "column": "severity"},
                "sensitivity": "public",
                "sample": False,
            },
        ],
        "table_policies": [{"table": "readings", "visible": False}],
    }
)


def test_sensitivity_sets_the_switch_defaults_and_overrides_win() -> None:
    public = ColumnPolicy.model_validate({"column": {"table": "t", "column": "c"}})
    assert public.switches() == (True, True, True)
    personal = ColumnPolicy.model_validate(
        {"column": {"table": "t", "column": "c"}, "sensitivity": "personal"}
    )
    assert personal.switches() == (False, False, True)
    opened = ColumnPolicy.model_validate(
        {
            "column": {"table": "t", "column": "c"},
            "sensitivity": "personal",
            "ground": True,
        }
    )
    assert opened.switches() == (False, True, True)
    assert OVERLAY.column_switches("devices.nothing_listed") == (True, True, True)
    # a public column with sampling switched off is still groundable by default
    assert [c.id for c in OVERLAY.groundable_columns()] == [
        "devices.model",
        "alerts.severity",
    ]


def test_payload_hides_tables_and_columns_and_drops_samples_by_policy() -> None:
    payload = schema_payload(iot_schema(), OVERLAY)
    names = [t["name"] for t in payload["tables"]]
    assert "readings" not in names and "devices" in names
    devices = next(t for t in payload["tables"] if t["name"] == "devices")
    assert "status" not in [c["name"] for c in devices["columns"]]
    alerts = next(t for t in payload["tables"] if t["name"] == "alerts")
    severity = next(c for c in alerts["columns"] if c["name"] == "severity")
    assert (
        severity["sample_values"] is None
    )  # sampled in the schema, withheld by policy
    assert all("readings" not in fk for fk in payload["foreign_keys"])


def test_compiler_treats_hidden_identifiers_as_unknown() -> None:
    compiler = PlanCompiler(iot_schema(), overlay=OVERLAY)
    with pytest.raises(PlanError) as error:
        compiler.compile(
            QueryPlan.model_validate(
                {
                    "base_table": "alerts",
                    "measures": [{"aggregate": "count"}],
                    "dimensions": [{"table": "devices", "column": "status"}],
                }
            ),
            as_of=AS_OF,
        )
    assert error.value.code == "unknown_column"
    with pytest.raises(PlanError) as error:
        compiler.compile(
            QueryPlan.model_validate(
                {
                    "base_table": "readings",
                    "measures": [
                        {
                            "aggregate": "avg",
                            "column": {"table": "readings", "column": "temperature_c"},
                        }
                    ],
                }
            ),
            as_of=AS_OF,
        )
    assert error.value.code == "unknown_table"
    # the visible sibling column still compiles
    compiler.compile(
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "dimensions": [{"table": "devices", "column": "model"}],
            }
        ),
        as_of=AS_OF,
    )


def test_validation_rejects_a_table_with_no_visible_column() -> None:
    broken = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
            "column_policies": [
                {"column": {"table": "sites", "column": c}, "visible": False}
                for c in ("site_id", "site_name")
            ],
        }
    )
    assert any(
        "sites has no visible column" in p
        for p in overlay_problems(broken, iot_schema())
    )
    assert overlay_problems(OVERLAY, iot_schema()) == []


def test_proposer_marks_people_personal_keys_ungrounded_and_things_public() -> None:
    schema = SchemaModel(
        datasource_id="ds",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(
                name="store",
                primary_key=["store_id"],
                columns=[
                    col("store_id", ColumnKind.TEXT),
                    col("store_name", ColumnKind.TEXT, comment="門市名稱"),
                    col("manager_name", ColumnKind.TEXT, comment="店長姓名"),
                    col("phone", ColumnKind.TEXT),
                    col("opened_on", ColumnKind.DATE),
                    col("tags", ColumnKind.TEXT, distinct_estimate=9000),
                ],
            )
        ],
    )
    by_id = {p.column.id: p for p in propose_policies(schema)}
    assert by_id["store.store_id"].switches() == (
        True,
        False,
        True,
    )  # key: not grounded
    assert by_id["store.store_name"].sensitivity.value == "public"
    assert by_id["store.store_name"].switches()[1] is True
    assert by_id["store.manager_name"].sensitivity.value == "personal"
    assert by_id["store.phone"].sensitivity.value == "personal"
    assert "store.opened_on" not in by_id  # not a text column
    assert by_id["store.tags"].switches()[1] is False  # too many distinct values
