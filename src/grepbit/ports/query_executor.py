from dataclasses import dataclass
from typing import Protocol

from grepbit.domain.models import CompiledQuery


@dataclass(frozen=True)
class ExecutionResult:
    rows: tuple[dict[str, object], ...]
    row_count: int
    columns: tuple[str, ...]
    truncated: bool = False
    error_code: str | None = None


class QueryExecutorPort(Protocol):
    def execute(
        self,
        query: CompiledQuery,
        *,
        max_rows: int,
        preview_rows: int,
        statement_timeout_seconds: int,
        idle_in_transaction_timeout_seconds: int | None = None,
        run_id: str,
    ) -> ExecutionResult: ...
