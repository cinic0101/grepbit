from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grepbit.domain.schema_model import (
    ColumnKind,
    ForeignKey,
    SchemaColumn,
    SchemaModel,
    SchemaTable,
)

ROOT = Path(__file__).resolve().parents[3]
AS_OF = datetime(2026, 8, 15, 12, 0, tzinfo=ZoneInfo("Asia/Taipei"))


def col(name: str, kind: ColumnKind, *, data_type: str | None = None, **extra):
    default_type = {
        ColumnKind.NUMERIC: "numeric",
        ColumnKind.TEXT: "text",
        ColumnKind.TIMESTAMP: "timestamp with time zone",
        ColumnKind.DATE: "date",
        ColumnKind.BOOLEAN: "boolean",
        ColumnKind.OTHER: "jsonb",
    }[kind]
    return SchemaColumn(
        name=name,
        data_type=data_type or default_type,
        kind=kind,
        nullable=extra.pop("nullable", True),
        **extra,
    )


def iot_schema(*, extra_foreign_keys: list[ForeignKey] | None = None) -> SchemaModel:
    """A star-with-one-snowflake schema: alerts/readings -> devices -> sites."""

    return SchemaModel(
        datasource_id="iot_test",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(
                name="sites",
                primary_key=["site_id"],
                columns=[
                    col("site_id", ColumnKind.TEXT),
                    col("site_name", ColumnKind.TEXT),
                ],
            ),
            SchemaTable(
                name="devices",
                primary_key=["device_id"],
                columns=[
                    col("device_id", ColumnKind.TEXT),
                    col("site_id", ColumnKind.TEXT),
                    col("model", ColumnKind.TEXT, sample_values=["AP-300", "GW-10"]),
                    col("status", ColumnKind.TEXT, sample_values=["offline", "online"]),
                    col("monthly_fee", ColumnKind.NUMERIC),
                    col("installed_on", ColumnKind.DATE),
                    col("is_managed", ColumnKind.BOOLEAN),
                    col("metadata", ColumnKind.OTHER),
                ],
            ),
            SchemaTable(
                name="alerts",
                primary_key=["alert_id"],
                columns=[
                    col("alert_id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("device_id", ColumnKind.TEXT),
                    col("related_device_id", ColumnKind.TEXT),
                    col(
                        "severity",
                        ColumnKind.TEXT,
                        sample_values=["critical", "warning"],
                    ),
                    col("downtime_minutes", ColumnKind.NUMERIC),
                    col("raised_at", ColumnKind.TIMESTAMP, nullable=False),
                    col("resolved_at", ColumnKind.TIMESTAMP),
                ],
            ),
            SchemaTable(
                name="readings",
                primary_key=["reading_id"],
                columns=[
                    col("reading_id", ColumnKind.NUMERIC, data_type="bigint"),
                    col("device_id", ColumnKind.TEXT),
                    col("temperature_c", ColumnKind.NUMERIC),
                    col("measured_at", ColumnKind.TIMESTAMP),
                ],
            ),
        ],
        foreign_keys=[
            ForeignKey(
                table="devices",
                column="site_id",
                referenced_table="sites",
                referenced_column="site_id",
            ),
            ForeignKey(
                table="alerts",
                column="device_id",
                referenced_table="devices",
                referenced_column="device_id",
            ),
            ForeignKey(
                table="readings",
                column="device_id",
                referenced_table="devices",
                referenced_column="device_id",
            ),
            *(extra_foreign_keys or []),
        ],
    )
