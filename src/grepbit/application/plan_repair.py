"""Structural plan repairs that need no judgment about meaning.

The planner sometimes names as ``base_table`` an entity the question groups
by (category) while every measure sits on that entity's child table
(product.price, or a metric whose base is pos_payment). Compiled as written
the plan would fan out or mismatch, so the compiler refuses it. The repair is
mechanical: when all operands name one table that reaches the chosen base
through foreign keys, that table is the base; dimensions, filters and time
columns on the old base stay valid because it is now a parent. Anything else
is left for the compiler to judge.
"""

from __future__ import annotations

from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import SchemaModel

MAX_HOPS = 3
BASE_REPAIR_REVISION = "base-repair-child-measure-v2"


def _reaches(schema: SchemaModel, start: str, target: str) -> bool:
    """True when ``target`` is a parent of ``start`` within MAX_HOPS foreign keys."""

    frontier = {start}
    seen = {start}
    for _ in range(MAX_HOPS):
        step = {
            fk.referenced_table
            for fk in schema.foreign_keys
            if fk.table in frontier and fk.referenced_table not in seen
        }
        if target in step:
            return True
        seen |= step
        frontier = step
        if not frontier:
            break
    return False


def repair_base_table(
    plan: QueryPlan,
    schema: SchemaModel,
    overlay: SemanticOverlay | None = None,
) -> tuple[QueryPlan, str | None]:
    """Move the base to the operands' table when the base is only a parent of it.

    Applies when every operand names one table, through its column or through
    its metric's base table, that table differs from the plan's base, and the
    base is reachable from it through foreign keys. ``count(*)`` names no
    table and operands on several tables leave the plan alone; a plan without
    a base is left to the compiler's derivation. Returns the (possibly
    repaired) plan and a note describing the repair.
    """

    if plan.base_table is None:
        return plan, None
    operands = []
    for measure in plan.measures:
        if measure.ratio is not None:
            operands += [measure.ratio.numerator, measure.ratio.denominator]
        else:
            operands.append(measure)
    tables: set[str] = set()
    for op in operands:
        if op.metric is not None:
            metric = overlay.metric(op.metric) if overlay else None
            if metric is None:
                return plan, None
            tables.add(metric.base_table)
        elif op.column is not None:
            tables.add(op.column.table)
        else:
            return plan, None  # count(*) names no table
    if len(tables) != 1:
        return plan, None
    [measure_table] = tables
    if measure_table == plan.base_table or schema.table(measure_table) is None:
        return plan, None
    if not _reaches(schema, measure_table, plan.base_table):
        return plan, None
    repaired = plan.model_copy(update={"base_table": measure_table})
    return repaired, (
        f"base_table {plan.base_table} -> {measure_table}: the measures live on "
        f"{measure_table}, which references {plan.base_table}"
    )
