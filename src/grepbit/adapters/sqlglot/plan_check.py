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
from grepbit.domain.schema_model import ColumnKind, ForeignKey, SchemaModel
from grepbit.domain.time_literals import bind_time_literal

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


def _row_joins_match(plan, tree, schema, population_links):
    """Read exact join edges; population provenance is a separate trusted input."""
    joins = tree.args.get("joins") or []
    parents = {r.table for r in plan.rows.columns if r.table != plan.base_table}
    if schema is None:
        return not joins and not parents and not population_links
    base = schema.table(plan.base_table)
    source = tree.args.get("from_")
    source = source.this if source else None
    if (
        base is None
        or base.has_inheritance_children
        or len(parents) > 1
        or not isinstance(source, exp.Table)
        or source.name != plan.base_table
        or source.alias
        or source.db not in {"", schema.schema_name}
        or source.catalog
    ):
        return False
    allowed = {f.referenced_table: f for f in population_links}
    if len(allowed) != len(population_links):
        return False
    for f in population_links:
        target = schema.table(f.referenced_table)
        if (
            f not in schema.foreign_keys
            or (
                f.inferred
                and target is not None
                and target.primary_key != [f.referenced_column]
            )
            or target is None
            or target.has_inheritance_children
        ):
            return False
    for name in parents:
        parent = schema.table(name)
        links = [
            f
            for f in schema.parent_links(plan.base_table)
            if f.referenced_table == name
        ]
        if (
            parent is None
            or parent.has_inheritance_children
            or len(links) != 1
            or links[0].inferred
            or parent.primary_key != [links[0].referenced_column]
        ):
            return False
        if name in allowed and allowed[name] != links[0]:
            return False
        allowed[name] = links[0]
    if len(joins) != len(allowed):
        return False
    seen = {plan.base_table}
    for join in joins:
        table, on = join.this, join.args.get("on")
        if (
            not isinstance(table, exp.Table)
            or table.alias
            or table.catalog
            or table.db not in {"", schema.schema_name}
            or table.name in seen
            or table.name not in allowed
            or join.args.get("side") != "LEFT"
            or join.args.get("kind")
            or join.args.get("method")
            or join.args.get("using")
            or not isinstance(on, exp.EQ)
        ):
            return False
        link = allowed[table.name]
        if link.table not in seen:
            return False
        operands = [on.this, on.expression]
        if not all(
            isinstance(c, exp.Column) and not c.db and not c.catalog for c in operands
        ):
            return False
        if {(c.table, c.name) for c in operands} != {
            (link.table, link.column),
            (link.referenced_table, link.referenced_column),
        }:
            return False
        seen.add(table.name)
    return True


def check_compiled(
    plan: QueryPlan,
    sql: str,
    parameters: Sequence[QueryParameter] | None,
    verification: str,
    *,
    schema: SchemaModel | None = None,
    row_population_joins: Sequence[ForeignKey] = (),
    row_population_sql: str | None = None,
) -> list[str]:
    """Return the invariants the SQL breaks; an empty list means it passed.

    ``parameters`` may be None when only the text is available (an old report);
    the literal-binding check is skipped then.
    """

    tree = sqlglot.parse_one(sql, read="postgres")
    violations: list[str] = []
    # SQLGlot's .name is spelling, not PostgreSQL's resolved identity. Reject
    # case-foldable unquoted identifiers before using those names in invariants.
    # This also covers nested scopes, relation/schema names and output aliases.
    if any(
        not identifier.args.get("quoted")
        and any("A" <= char <= "Z" for char in identifier.name)
        for identifier in tree.find_all(exp.Identifier)
    ):
        violations.append("identifier_case_unquoted")
    if plan.rows is not None:
        if not isinstance(tree, exp.Select):
            violations.append("row_select_required")
        else:
            expected = [(c.table, c.column) for c in plan.rows.columns]
            columns = [
                e.this if isinstance(e, exp.Alias) else e for e in tree.expressions
            ]
            actual = [(c.table, c.name) for c in columns if isinstance(c, exp.Column)]
            if len(actual) != len(tree.expressions) or (
                not plan.rows.all_columns and actual != expected
            ):
                violations.append("row_projection_mismatch")
            if not plan.rows.all_columns and [
                e.alias_or_name for e in tree.expressions
            ] != plan.rows.output_names(plan.base_table):
                violations.append("row_output_name_mismatch")
            if not _row_joins_match(plan, tree, schema, row_population_joins):
                violations.append("row_join_mismatch")
            if row_population_sql is not None:
                population = sqlglot.parse_one(row_population_sql, read="postgres")
                # Compare independently supplied pre-projection population, not
                # an allowlist inferred from the final SQL under examination.
                if tree.args.get("where") != population.args.get("where"):
                    violations.append("row_population_changed")
            if (
                tree.args.get("distinct")
                or tree.find(exp.Group)
                or tree.find(exp.AggFunc)
                or tree.find(exp.Window)
            ):
                violations.append("row_cardinality_changed")
            if tree.args.get("order") is None:
                violations.append("row_order_missing")
            elif plan.order:
                terms = tree.args["order"].expressions[: len(plan.order)]
                if len(terms) != len(plan.order) or any(
                    not isinstance(term, exp.Ordered)
                    or not isinstance(term.this, exp.Column)
                    or term.this.name != spec.field
                    or term.this.table not in {"", plan.base_table}
                    or bool(term.args.get("desc")) != (spec.direction == "desc")
                    or bool(term.args.get("nulls_first"))
                    for term, spec in zip(terms, plan.order)
                ):
                    violations.append("row_order_mismatch")
            limit = tree.args.get("limit")
            if (plan.limit is None) != (limit is None):
                violations.append("row_limit_mismatch")
            if verification != "unverified_semantics":
                violations.append("row_verification_overclaim")
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
                if schema is not None:
                    table = schema.table(item.column.table)
                    column = table.column(item.column.column) if table else None
                    if column and column.kind in {
                        ColumnKind.TIMESTAMP,
                        ColumnKind.DATE,
                    }:
                        # Check the approved canonical binding, never omit time
                        # values from the invariant after representation changes.
                        value = bind_time_literal(
                            column, value, schema.business_timezone
                        )[0]
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
