"""Bounded psycopg execution for already-authorized physical SQL."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg

from grepbit.domain.models import CompiledQuery, ParameterMode
from grepbit.ports.active_query_lifecycle import (
    ActiveQueryHandle,
    ActiveQueryLifecyclePort,
)
from grepbit.ports.query_executor import ExecutionResult


class PsycopgQueryExecutor:
    """Own and verify safe physical execution with preserved named bindings.

    Transaction safety is established or verified here, while a named cursor
    keeps physical-result buffering bounded during the fixed-query drain.
    """

    def __init__(
        self,
        *,
        connection_factory: Callable[[], AbstractContextManager[Any]],
        active_queries: ActiveQueryLifecyclePort,
    ) -> None:
        self._connection_factory = connection_factory
        self._active_queries = active_queries

    def execute(
        self,
        compiled_query: CompiledQuery,
        *,
        max_rows: int,
        preview_rows: int,
        statement_timeout_seconds: int,
        idle_in_transaction_timeout_seconds: int | None = None,
        run_id: str,
    ) -> ExecutionResult:
        if compiled_query.parameter_mode is not ParameterMode.PRESERVED_BINDING:
            raise ValueError("physical execution requires preserved parameter binding")
        if preview_rows > max_rows:
            raise ValueError("preview_rows must not exceed max_rows")
        idle_timeout_seconds = (
            statement_timeout_seconds
            if idle_in_transaction_timeout_seconds is None
            else idle_in_transaction_timeout_seconds
        )
        if statement_timeout_seconds < 1 or idle_timeout_seconds < 1:
            raise ValueError("postgres_timeout_seconds_must_be_positive")

        parameters = {
            parameter.name: parameter.value
            for parameter in compiled_query.execution_parameters
        }
        try:
            with self._connection_factory() as connection:
                self._active_queries.register(
                    ActiveQueryHandle(run_id=run_id, cancel_safe=connection.cancel_safe)
                )
                with connection.cursor() as setup_cursor:
                    if (
                        connection.info.transaction_status
                        == psycopg.pq.TransactionStatus.IDLE
                    ):
                        setup_cursor.execute("BEGIN READ ONLY")
                    setup_cursor.execute("SHOW transaction_read_only")
                    if setup_cursor.fetchone() != ("on",):
                        raise PermissionError(
                            "physical execution requires read-only transaction"
                        )
                    setup_cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (f"{statement_timeout_seconds}s",),
                    )
                    setup_cursor.execute(
                        "SELECT set_config("
                        "'idle_in_transaction_session_timeout', %s, true)",
                        (f"{idle_timeout_seconds}s",),
                    )
                    setup_cursor.execute("SET LOCAL search_path = pg_catalog, public")
                with connection.cursor(name="grepbit_physical_query") as query_cursor:
                    query_cursor.execute(compiled_query.physical_sql, parameters)
                    columns = tuple(
                        description.name for description in query_cursor.description
                    )
                    public_rows: list[dict[str, object]] = []
                    row_count = 0
                    while rows := query_cursor.fetchmany(128):
                        row_count += len(rows)
                        if len(public_rows) < max_rows:
                            public_rows.extend(
                                dict(zip(columns, row, strict=True))
                                for row in rows[: max_rows - len(public_rows)]
                            )
        except psycopg.Error as error:
            return ExecutionResult(
                rows=(),
                row_count=0,
                columns=(),
                error_code=error.sqlstate or type(error).__name__,
            )
        finally:
            self._active_queries.revoke(run_id, completion_recorded=False)

        return ExecutionResult(
            rows=tuple(public_rows),
            row_count=row_count,
            columns=columns,
            truncated=row_count > max_rows,
        )
