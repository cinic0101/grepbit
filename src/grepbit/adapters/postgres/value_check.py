"""Bounded existence checks for filter literals, with the read-only role."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from typing import Any

from grepbit.application.literals import LiteralCheck

VALUE_CHECK_REVISION = "literal-exists-v1"


def missing_literals(
    connection_factory: Callable[[], AbstractContextManager[Any]],
    schema_name: str,
    checks: Iterable[LiteralCheck],
    *,
    statement_timeout_seconds: int = 5,
) -> list[LiteralCheck]:
    """Return the checks whose literal matches no row of its column.

    One ``SELECT EXISTS`` per literal, the literal bound as a parameter, inside
    a read-only transaction with a statement timeout. Enum columns are compared
    as text so a literal outside the labels is a miss, not an error. Only the
    literal from the question travels; no stored value is read back.
    """

    from psycopg import sql

    checks = list(checks)
    if not checks:
        return []
    misses: list[LiteralCheck] = []
    with connection_factory() as connection:
        connection.execute("BEGIN READ ONLY")
        connection.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_seconds}s",),
        )
        for check in checks:
            column: Any = sql.Identifier(check.table, check.column)
            if check.is_enum:
                column = sql.SQL("{}::text").format(column)
            query = sql.SQL(
                "SELECT EXISTS (SELECT 1 FROM {table} WHERE {column} = %s)"
            ).format(table=sql.Identifier(schema_name, check.table), column=column)
            (exists,) = connection.execute(query, (check.value,)).fetchone()
            if not exists:
                misses.append(check)
        connection.rollback()
    return misses
