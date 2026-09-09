"""SchemaModel: introspection output is closed, validated, and content-addressed."""

from __future__ import annotations

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.postgres.introspect import (
    column_kind,
    infer_foreign_keys,
    introspect_schema,
)
from grepbit.domain.schema_model import ColumnKind, ForeignKey, SchemaModel


def test_foreign_keys_must_resolve_to_known_tables_and_columns() -> None:
    payload = iot_schema().model_dump(mode="json")
    payload["foreign_keys"].append(
        {
            "table": "alerts",
            "column": "device_id",
            "referenced_table": "ghosts",
            "referenced_column": "ghost_id",
        }
    )
    with pytest.raises(ValueError, match="schema_foreign_key_table_unknown"):
        SchemaModel.model_validate(payload)
    payload["foreign_keys"][-1].update({"referenced_table": "devices"})
    with pytest.raises(ValueError, match="schema_foreign_key_column_unknown"):
        SchemaModel.model_validate(payload)


def test_parent_links_only_leave_the_table_and_digest_is_stable() -> None:
    schema = iot_schema()
    assert [link.referenced_table for link in schema.parent_links("alerts")] == [
        "devices"
    ]
    assert schema.parent_links("sites") == []
    assert schema.parent_link("devices", "sites") == ForeignKey(
        table="devices",
        column="site_id",
        referenced_table="sites",
        referenced_column="site_id",
    )
    assert [c.name for c in schema.time_columns("alerts")] == [
        "raised_at",
        "resolved_at",
    ]
    assert schema.digest() == iot_schema().digest()
    assert schema.digest().startswith("sha256:")


@pytest.mark.parametrize(
    ("data_type", "kind"),
    [
        ("integer", ColumnKind.NUMERIC),
        ("numeric", ColumnKind.NUMERIC),
        ("double precision", ColumnKind.NUMERIC),
        ("character varying", ColumnKind.TEXT),
        ("uuid", ColumnKind.TEXT),
        ("timestamp with time zone", ColumnKind.TIMESTAMP),
        ("timestamp without time zone", ColumnKind.TIMESTAMP),
        ("date", ColumnKind.DATE),
        ("boolean", ColumnKind.BOOLEAN),
        ("jsonb", ColumnKind.OTHER),
        ("ARRAY", ColumnKind.OTHER),
    ],
)
def test_column_kind_maps_postgres_types(data_type: str, kind: ColumnKind) -> None:
    assert column_kind(data_type) is kind


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _ScriptedConnection:
    """Answers the six catalog queries in order, then samples every text column."""

    def __init__(self, *, enum_column: bool = False) -> None:
        def column(table, name, data_type, nullable, position, comment, udt=None):
            return (
                table,
                name,
                data_type,
                nullable,
                position,
                comment,
                "pg_catalog",
                udt,
            )

        columns = [
            column("devices", "device_id", "text", False, 1, None),
            column("devices", "status", "text", True, 2, "online/offline"),
            column("devices", "monthly_fee", "numeric", True, 3, None),
            column("alerts", "alert_id", "bigint", False, 1, None),
            column("alerts", "device_id", "text", True, 2, None),
            column("alerts", "severity", "text", True, 3, None),
            column("alerts", "raised_at", "timestamp with time zone", False, 4, None),
        ]
        enums: list[tuple] = []
        if enum_column:
            columns.append(
                (
                    "alerts",
                    "channel",
                    "USER-DEFINED",
                    True,
                    5,
                    None,
                    "public",
                    "channel_t",
                )
            )
            enums = [("public", "channel_t", "email"), ("public", "channel_t", "sms")]
        self.catalog = [
            columns,
            [("devices", "Managed devices"), ("alerts", None)],  # table comments
            [("devices", 12), ("alerts", 40)],  # row estimates
            [("devices", "device_id"), ("alerts", "alert_id")],  # primary keys
            [("alerts", "device_id", "devices", "device_id")],  # foreign keys
            enums,  # enum labels (type metadata)
        ]
        self.sampled: list[object] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        if isinstance(query, str):
            return _Result(self.catalog.pop(0))
        self.sampled.append(query)
        return _Result([("a",), ("b",)])


def test_introspection_builds_keys_kinds_and_samples_only_non_key_text() -> None:
    connection = _ScriptedConnection()
    schema = introspect_schema(lambda: connection, datasource_id="ds")
    assert [t.name for t in schema.tables] == ["devices", "alerts"]
    devices = schema.table("devices")
    assert devices is not None
    assert devices.primary_key == ["device_id"]
    assert devices.row_estimate == 12 and devices.comment == "Managed devices"
    assert devices.column("device_id").sample_values == []  # key: never sampled
    assert devices.column("status").sample_values == ["a", "b"]
    assert devices.column("status").comment == "online/offline"
    assert devices.column("monthly_fee").kind is ColumnKind.NUMERIC
    alerts = schema.table("alerts")
    assert alerts.column("device_id").sample_values == []  # foreign key: never sampled
    assert alerts.column("severity").sample_values == ["a", "b"]
    assert alerts.column("raised_at").kind is ColumnKind.TIMESTAMP
    assert not alerts.column("raised_at").nullable
    assert schema.foreign_keys == [
        ForeignKey(
            table="alerts",
            column="device_id",
            referenced_table="devices",
            referenced_column="device_id",
        )
    ]
    assert len(connection.sampled) == 2


def test_introspection_with_limit_zero_never_reads_a_cell_value() -> None:
    connection = _ScriptedConnection()
    schema = introspect_schema(
        lambda: connection, datasource_id="ds", enum_distinct_limit=0
    )
    assert connection.sampled == []  # no sampling query was issued at all
    assert schema.table("devices").column("status").sample_values == []
    assert schema.table("alerts").column("severity").sample_values == []
    assert schema.table("devices").column("status").distinct_estimate is None
    assert schema.foreign_keys[0].referenced_table == "devices"  # structure intact


def test_enum_columns_are_text_with_catalog_labels_and_are_never_sampled() -> None:
    connection = _ScriptedConnection(enum_column=True)
    schema = introspect_schema(
        lambda: connection, datasource_id="ds", enum_distinct_limit=0
    )
    channel = schema.table("alerts").column("channel")
    assert channel.kind is ColumnKind.TEXT and channel.is_enum
    assert channel.data_type == "channel_t"
    assert channel.sample_values == ["email", "sms"]  # labels, shown at limit 0
    assert channel.distinct_estimate == 2
    assert connection.sampled == []  # labels came from pg_enum, no row was read
    assert not schema.table("devices").column("status").is_enum


def test_inference_needs_a_name_match_and_zero_orphans_and_one_parent() -> None:
    from t0_helpers import col

    from grepbit.domain.schema_model import SchemaTable

    base = iot_schema()
    undeclared = base.model_copy(
        update={
            "foreign_keys": [],
            "tables": [
                *base.tables,
                SchemaTable(
                    name="staff",
                    primary_key=["staff_id"],
                    columns=[
                        col("staff_id", ColumnKind.TEXT),
                        col("site_id", ColumnKind.TEXT),  # named like sites.site_id
                    ],
                ),
            ],
        }
    )
    asked: list[tuple[str, str, str]] = []

    def fake_containment(_conn, _schema, table, column, parent, _key, _limit):
        asked.append((table, column, parent))
        if (table, column) == ("staff", "site_id"):
            return 4, 4  # staff.site_id values are not site ids: orphans
        return 5, 0

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    inferred = infer_foreign_keys(
        lambda: _Conn(), undeclared, containment=fake_containment
    )
    found = {fk.id: fk for fk in inferred.foreign_keys}
    assert set(found) == {
        "devices.site_id -> sites.site_id",
        "alerts.device_id -> devices.device_id",
        "readings.device_id -> devices.device_id",
        "alerts.related_device_id -> devices.device_id",
    }
    assert all(
        fk.inferred and "sampled distinct values" in (fk.evidence or "")
        for fk in found.values()
    )
    assert ("staff", "site_id", "sites") in asked  # checked, then rejected by the data
    # Declared keys are never re-inferred and primary keys are never children.
    again = infer_foreign_keys(lambda: _Conn(), inferred, containment=fake_containment)
    assert len(again.foreign_keys) == len(inferred.foreign_keys)
