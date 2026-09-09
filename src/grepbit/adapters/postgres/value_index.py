"""Load distinct values of groundable columns for the in-memory value index."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from typing import Any

from grepbit.domain.plan import ColumnRef
from grepbit.domain.schema_model import SchemaModel

VALUE_INDEX_REVISION = "value-index-loader-v1"
DEFAULT_VALUE_CAP = 5000


def load_column_values(
    connection_factory: Callable[[], AbstractContextManager[Any]],
    schema: SchemaModel,
    columns: Iterable[ColumnRef],
    *,
    cap: int = DEFAULT_VALUE_CAP,
    statement_timeout_seconds: int = 10,
) -> tuple[dict[str, list[str]], list[str]]:
    """Distinct non-null values per column, and the columns skipped for size.

    One ``SELECT DISTINCT`` per column inside a read-only transaction with a
    statement timeout; a column with more than ``cap`` distinct values is not
    indexed and is reported, so grounding never scans an identifier column.
    Enum columns are read as text.
    """

    from psycopg import sql

    values: dict[str, list[str]] = {}
    skipped: list[str] = []
    refs = list(columns)
    if not refs:
        return values, skipped
    with connection_factory() as connection:
        connection.execute("BEGIN READ ONLY")
        connection.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_seconds}s",),
        )
        for ref in refs:
            table = schema.table(ref.table)
            column = table.column(ref.column) if table is not None else None
            if column is None:
                skipped.append(ref.id)
                continue
            expression: Any = sql.Identifier(ref.column)
            if column.is_enum:
                expression = sql.SQL("{}::text").format(expression)
            query = sql.SQL(
                "SELECT DISTINCT {column} FROM {table} "
                "WHERE {column} IS NOT NULL LIMIT {limit}"
            ).format(
                column=expression,
                table=sql.Identifier(schema.schema_name, ref.table),
                limit=sql.Literal(cap + 1),
            )
            rows = [str(row[0]) for row in connection.execute(query).fetchall()]
            if len(rows) > cap:
                skipped.append(ref.id)
                continue
            values[ref.id] = rows
        connection.rollback()
    return values, skipped
