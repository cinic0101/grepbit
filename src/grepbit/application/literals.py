"""Which filter literals of a plan deserve a server-side existence check."""

from __future__ import annotations

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import FilterOp, QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel


class LiteralCheck(DomainModel):
    table: str
    column: str
    value: str
    is_enum: bool = False


def text_literal_checks(plan: QueryPlan, schema: SchemaModel) -> list[LiteralCheck]:
    """Every ``eq`` or ``in`` text literal the plan filters on, in plan order.

    A text literal that matches no row turns a question into an empty
    aggregate (``SUM`` of nothing is NULL) that reads like an answer. Checking
    each literal against its column before execution lets the caller return
    ``clarify`` instead. Numeric, boolean and temporal literals are left alone:
    a zero-row window is a legitimate answer. Metric (overlay) filters are
    reviewed and not checked. Unknown columns are skipped here; the compiler
    reports them.
    """

    checks: list[LiteralCheck] = []
    for item in plan.filters:
        if item.op not in {FilterOp.EQ, FilterOp.IN}:
            continue
        table = schema.table(item.column.table)
        column = table.column(item.column.column) if table is not None else None
        if column is None or column.kind is not ColumnKind.TEXT:
            continue
        for value in item.values:
            if isinstance(value, str):
                checks.append(
                    LiteralCheck(
                        table=item.column.table,
                        column=item.column.column,
                        value=value,
                        is_enum=column.is_enum,
                    )
                )
    return checks
