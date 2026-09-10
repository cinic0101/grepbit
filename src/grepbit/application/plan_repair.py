"""Structural plan repairs that need no judgment about meaning.

The planner sometimes names as ``base_table`` an entity the question groups
by (category) while every measure column sits on that entity's child table
(product.price). Compiled as written the plan would fan out, so the compiler
refuses it. The repair is mechanical: when all raw measure columns sit on one
table that reaches the chosen base through foreign keys, that table is the
base; dimensions, filters and time columns on the old base stay valid because
it is now a parent. Anything else is left for the compiler to judge.
"""

from __future__ import annotations

from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import SchemaModel

MAX_HOPS = 3
BASE_REPAIR_REVISION = "base-repair-child-measure-v1"


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
    plan: QueryPlan, schema: SchemaModel
) -> tuple[QueryPlan, str | None]:
    """Move the base to the measures' table when the base is only a parent of it.

    Applies only when every measure is a raw aggregate over a column, all of
    those columns sit on one table other than the base, and the base is
    reachable from that table through foreign keys. Metrics carry their own
    base and ``count(*)`` names no table, so those plans are left alone.
    Returns the (possibly repaired) plan and a note describing the repair.
    """

    if any(m.metric is not None or m.column is None for m in plan.measures):
        return plan, None
    tables = {m.column.table for m in plan.measures if m.column is not None}
    if len(tables) != 1:
        return plan, None
    [measure_table] = tables
    if measure_table == plan.base_table or schema.table(measure_table) is None:
        return plan, None
    if not _reaches(schema, measure_table, plan.base_table):
        return plan, None
    repaired = plan.model_copy(update={"base_table": measure_table})
    return repaired, (
        f"base_table {plan.base_table} -> {measure_table}: the measure columns live "
        f"on {measure_table}, which references {plan.base_table}"
    )
