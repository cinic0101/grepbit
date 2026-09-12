"""Read the compiled SQL back and check it against the plan it came from.

The compiler's meaning of a construct next to another construct is whatever
its code paths do; twice on 2026-09-11 a combination the validator used to
reject compiled to a wrong number that nothing exposed (an operand filter
dropped by the metric expansion: total / total = 1.0 marked verified; a
filtered count with share_of_total and no groups: filtered / filtered = 1.0).
This module is the independent reader: it parses the SQL text, not the
compiler's tree, and knows only the plan and a few invariants every correct
compilation satisfies. A violation refuses the answer (``self_check_failed``)
instead of serving it, and is counted, so an unknown combination shows up as
a refusal in the regression rather than as a number.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlglot
from sqlglot import exp

from grepbit.domain.models import QueryParameter
from grepbit.domain.plan import Filter, FilterOp, Operand, QueryPlan

_PREDICATE_KINDS: dict[FilterOp, type[exp.Expression]] = {
    FilterOp.EQ: exp.EQ,
    FilterOp.NE: exp.NEQ,
    FilterOp.GT: exp.GT,
    FilterOp.GTE: exp.GTE,
    FilterOp.LT: exp.LT,
    FilterOp.LTE: exp.LTE,
    FilterOp.IN: exp.In,
    FilterOp.IS_NULL: exp.Is,
    FilterOp.NOT_NULL: exp.Is,
}


def _operands(plan: QueryPlan) -> list[Operand]:
    found: list[Operand] = []
    for measure in plan.measures:
        if measure.ratio is not None:
            found.extend([measure.ratio.numerator, measure.ratio.denominator])
        else:
            found.append(measure)
    return found


def _question_filters(plan: QueryPlan) -> list[Filter]:
    filters = list(plan.filters)
    for operand in _operands(plan):
        filters.extend(operand.filters)
    if plan.without is not None:
        filters.extend(plan.without.filters)
    return filters


def _columns(node: exp.Expression) -> set[tuple[str, str]]:
    return {(c.table, c.name) for c in node.find_all(exp.Column)}


def _predicate_matches(predicate: exp.Expression, item: Filter) -> bool:
    if not isinstance(predicate, _PREDICATE_KINDS[item.op]):
        return False
    negated = isinstance(predicate.parent, exp.Not)
    if item.op is FilterOp.NOT_NULL and not negated:
        return False
    if item.op is FilterOp.IS_NULL and negated:
        return False
    # the after-share outer query names grouped columns without a table
    return any(
        name == item.column.column and table in ("", item.column.table)
        for table, name in _columns(predicate)
    )


def _strip(node: exp.Expression) -> exp.Expression:
    """Unwrap parentheses, CAST and NULLIF(x, 0) down to the operand itself."""

    while True:
        if isinstance(node, exp.Paren):
            node = node.this
        elif isinstance(node, exp.Cast):
            node = node.this
        elif isinstance(node, exp.Anonymous) and node.name.upper() == "NULLIF":
            node = node.expressions[0]
        elif isinstance(node, exp.Nullif):
            node = node.this
        else:
            return node


def check_compiled(
    plan: QueryPlan,
    sql: str,
    parameters: Sequence[QueryParameter] | None,
    verification: str,
) -> list[str]:
    """Return the invariants the SQL breaks; an empty list means it passed.

    ``parameters`` may be None when only the text is available (an old report);
    the literal-binding check is skipped then.
    """

    tree = sqlglot.parse_one(sql, read="postgres")
    violations: list[str] = []
    if any(m.ratio is not None and m.filters for m in plan.measures):
        violations.append("ratio_wrapper_filters_unsupported")
    predicates = list(tree.find_all(exp.Predicate))

    # 1. every filter the plan asked for is a predicate of the right kind on
    #    its column somewhere in the SQL (WHERE, FILTER, NOT EXISTS, outer WHERE)
    for item in _question_filters(plan):
        if not any(_predicate_matches(p, item) for p in predicates):
            violations.append(f"filter_not_applied {item.column.id} {item.op.value}")

    # 2. every literal a filter carries is bound as a parameter
    if parameters is not None:
        bound = [str(p.value) for p in parameters]
        for item in _question_filters(plan):
            for value in item.values:
                if str(value) in bound:
                    bound.remove(str(value))
                else:
                    violations.append(f"literal_not_bound {item.column.id} {value!r}")

    # 3. a ratio never divides an expression by itself
    for division in tree.find_all(exp.Div):
        if _strip(division.this).sql() == _strip(division.expression).sql():
            violations.append(f"ratio_operands_identical {division.this.sql()[:60]}")

    # 4. no window function without groups, a grain or growth: a share of
    #    total would be the value over itself
    grouped = bool(plan.dimensions) or (
        plan.time is not None and plan.time.grain is not None
    )
    if plan.latest is None and not grouped and not plan.growth:
        if any(True for _ in tree.find_all(exp.Window)):
            violations.append("window_without_groups")

    # 5. GROUP BY lists exactly the dimensions (and the period bucket)
    if plan.latest is None:
        grouped_names = {
            name
            for group in tree.find_all(exp.Group)
            for expression in group.expressions
            for _, name in _columns(expression)
        }
        for dimension in plan.dimensions:
            if dimension.column not in grouped_names:
                violations.append(f"dimension_not_grouped {dimension.id}")
        if not grouped and grouped_names:
            violations.append("group_without_dimensions")

    # 6. a HAVING in the plan is a HAVING in the SQL, or, beside a share or a
    #    growth measure, an outer predicate on the measure's output name
    if plan.having and tree.find(exp.Having) is None:
        named = {
            c.name for p in predicates for c in p.find_all(exp.Column) if not c.table
        }
        if not all(item.field in named for item in plan.having):
            violations.append("having_missing")

    # 7. a reviewed answer is fully verified only when the plan added no rows
    #    filters of its own
    if verification == "verified" and _question_filters(plan):
        violations.append("verified_with_question_filters")

    return violations
