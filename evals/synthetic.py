"""Random instances of a schema, loaded into DuckDB, for the differential.

A fixture has one shape of data: a column with one value, an empty month, a
parent every child references. A rule that is wrong only when the data is
otherwise never shows. ``random_instance`` draws rows for every table of an
introspected schema (parents first, children referencing random parents, a
share of NULLs and a few dangling references), ``DuckInstance`` loads them
into an in-memory DuckDB and runs the compiled PostgreSQL SQL there with its
bound parameters, so the same plan can be checked against the reference
evaluation on data no one arranged.
"""

from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

from grepbit.domain.models import CompiledQuery
from grepbit.domain.schema_model import ColumnKind, SchemaModel

VOCABULARY = [
    "A",
    "B",
    "C",
    "critical",
    "warning",
    "info",
    "offline",
    "online",
    "x y",
    "北區",
]
_PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def _dependency_order(schema: SchemaModel) -> list[str]:
    remaining = {t.name for t in schema.tables}
    parents = {
        t.name: {
            fk.referenced_table
            for fk in schema.foreign_keys
            if fk.table == t.name and fk.referenced_table != t.name
        }
        for t in schema.tables
    }
    ordered: list[str] = []
    while remaining:
        ready = sorted(t for t in remaining if parents[t] <= set(ordered))
        if not ready:
            ready = sorted(remaining)  # a cycle: break it arbitrarily
        ordered.extend(ready)
        remaining -= set(ready)
    return ordered


def random_instance(
    schema: SchemaModel, rng: random.Random, *, scale: float = 1.0
) -> dict[str, list[dict[str, Any]]]:
    zone = ZoneInfo(schema.business_timezone)
    tables: dict[str, list[dict[str, Any]]] = {}
    fk_of = {(fk.table, fk.column): fk for fk in schema.foreign_keys}
    for name in _dependency_order(schema):
        table = schema.table(name)
        is_child = any(fk.table == name for fk in schema.foreign_keys)
        count = rng.randint(20, 80) if is_child else rng.randint(3, 12)
        count = max(1, int(count * scale))
        rows = []
        for i in range(count):
            row: dict[str, Any] = {}
            for column in table.columns:
                key = (name, column.name)
                if column.name in table.primary_key:
                    row[column.name] = (
                        i + 1
                        if column.kind is ColumnKind.NUMERIC
                        else f"{name[:3]}{i + 1:03d}"
                    )
                    continue
                if key in fk_of:
                    fk = fk_of[key]
                    parent_rows = tables.get(fk.referenced_table, [])
                    roll = rng.random()
                    if not parent_rows or roll < 0.08:
                        row[column.name] = None
                    elif roll < 0.12:
                        row[column.name] = (
                            "dangling"
                            if column.kind is not ColumnKind.NUMERIC
                            else 999999
                        )
                    else:
                        row[column.name] = rng.choice(parent_rows)[fk.referenced_column]
                    continue
                if not column.nullable:
                    null_share = 0.0
                else:
                    null_share = 0.1
                if rng.random() < null_share:
                    row[column.name] = None
                elif column.kind is ColumnKind.TEXT:
                    pool = list(column.sample_values or []) + VOCABULARY
                    row[column.name] = rng.choice(pool)
                elif column.kind is ColumnKind.NUMERIC:
                    if column.data_type in ("bigint", "integer", "smallint"):
                        row[column.name] = rng.choice([0, 1, 2, 5, 10, 100, -3])
                    else:
                        row[column.name] = Decimal(
                            str(rng.choice([0, 1, 2.5, 10, 99.99, 100, 360, -5, 0.5]))
                        )
                elif column.kind is ColumnKind.TIMESTAMP:
                    start = datetime(2025, 6, 1, tzinfo=zone)
                    row[column.name] = start + timedelta(
                        minutes=rng.randint(0, 440 * 24 * 60)
                    )
                elif column.kind is ColumnKind.DATE:
                    row[column.name] = date(2025, 6, 1) + timedelta(
                        days=rng.randint(0, 440)
                    )
                elif column.kind is ColumnKind.BOOLEAN:
                    row[column.name] = rng.random() < 0.5
                else:
                    row[column.name] = None
            rows.append(row)
        tables[name] = rows
    return tables


_DUCK_TYPES = {
    ColumnKind.TEXT: "VARCHAR",
    ColumnKind.NUMERIC: "DECIMAL(18,4)",
    ColumnKind.TIMESTAMP: "TIMESTAMPTZ",
    ColumnKind.DATE: "DATE",
    ColumnKind.BOOLEAN: "BOOLEAN",
    ColumnKind.OTHER: "VARCHAR",
}


class DuckInstance:
    """One random instance loaded into DuckDB."""

    def __init__(self, schema: SchemaModel, tables: dict[str, list[dict[str, Any]]]):
        self.schema = schema
        self.tables = tables
        self.zone = ZoneInfo(schema.business_timezone)
        self.con = duckdb.connect()
        self.con.execute(f"SET TimeZone='{schema.business_timezone}'")
        self.con.execute("CREATE SCHEMA public")
        for table in schema.tables:
            columns = []
            for column in table.columns:
                duck_type = _DUCK_TYPES[column.kind]
                if column.kind is ColumnKind.NUMERIC and column.data_type in (
                    "bigint",
                    "integer",
                    "smallint",
                ):
                    duck_type = "BIGINT"
                columns.append(f'"{column.name}" {duck_type}')
            self.con.execute(
                f'CREATE TABLE public."{table.name}" ({", ".join(columns)})'
            )
            rows = tables.get(table.name, [])
            if rows:
                names = [c.name for c in table.columns]
                self.con.executemany(
                    f'INSERT INTO public."{table.name}" '
                    f"VALUES ({', '.join('?' for _ in names)})",
                    [[row.get(n) for n in names] for row in rows],
                )

    def execute(self, compiled: CompiledQuery) -> tuple[list[str], list[tuple]]:
        sql = _PLACEHOLDER.sub(r"$\1", compiled.physical_sql)
        params: dict[str, Any] = {}
        for p in compiled.execution_parameters:
            value = p.value
            if p.type_name in ("timestamptz", "timestamp") and isinstance(value, str):
                value = datetime.fromisoformat(value)
            elif p.type_name == "date" and isinstance(value, str):
                value = date.fromisoformat(value)
            params[p.name] = value
        cursor = self.con.execute(sql, params)
        names = [d[0] for d in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append(tuple(self._local(v) for v in row))
        return names, rows

    def _local(self, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(self.zone)
        return value
