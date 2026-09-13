"""Which filter literals of a plan deserve a server-side existence check."""

from __future__ import annotations

from collections.abc import Iterator

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import Filter, FilterOp, QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel


class LiteralCheck(DomainModel):
    table: str
    column: str
    value: str
    is_enum: bool = False


def binding_filters(
    plan: QueryPlan, *, grounded_columns: frozenset[str] = frozenset()
) -> Iterator[Filter]:
    """Plan EQ/IN plus opted-in EQ/IN/NE in model-authored scopes.

    Selection and replacement share this walk so a lookup cannot accidentally
    rewrite a sibling scope or a reviewed definition. Nested occurrences and
    negative predicates require an explicitly groundable column.
    """
    for item in plan.filters:
        if item.op in {FilterOp.EQ, FilterOp.IN} or (
            item.op is FilterOp.NE and item.column.id in grounded_columns
        ):
            yield item
    for measure in plan.measures:
        operands = (
            [measure.ratio.numerator, measure.ratio.denominator]
            if measure.ratio
            else [measure]
        )
        for operand in operands:
            for item in operand.filters:
                if (
                    item.op in {FilterOp.EQ, FilterOp.IN, FilterOp.NE}
                    and item.column.id in grounded_columns
                ):
                    yield item
    if plan.without:
        for item in plan.without.filters:
            if (
                item.op in {FilterOp.EQ, FilterOp.IN, FilterOp.NE}
                and item.column.id in grounded_columns
            ):
                yield item


def text_literal_checks(
    plan: QueryPlan,
    schema: SchemaModel,
    *,
    grounded_columns: frozenset[str] = frozenset(),
) -> list[LiteralCheck]:
    """Plan EQ/IN literals and opted-in scoped name bindings.

    A text literal that matches no row turns a question into an empty
    aggregate (``SUM`` of nothing is NULL) that reads like an answer. Checking
    each literal against its column before execution lets the caller return
    ``clarify`` instead. Numeric, boolean and temporal literals are left alone:
    a zero-row window is a legitimate answer. Metric (overlay) filters are
    reviewed and not checked. Unknown columns are skipped here; the compiler
    reports them.
    """

    checks: list[LiteralCheck] = []
    for item in binding_filters(plan, grounded_columns=grounded_columns):
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
