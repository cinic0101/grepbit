"""Opt-in research compiler; not wired into ask(), MCP or the web launcher.

Reuse the ordinary compiler for typed predicates, parent joins and each
aggregate. Compose its ASTs, never parse SQL supplied by a model. Existing
SQL policy is run again on the entire resulting statement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlglot
from pydantic import TypeAdapter
from sqlglot import exp

from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
    _sqlglot_parameter_syntax,
)
from grepbit.domain.models import CompiledQuery, QueryParameter
from grepbit.domain.plan import Aggregate, ColumnRef, QueryPlan
from grepbit.domain.query_extension_study import (
    AggregateQuery,
    CombinedQuery,
    RowsQuery,
    StudyQuery,
    UnitBinding,
)

STUDY_COMPILER_REVISION = "query-extension-compiler-study-v1"


class StudyRefusal(ValueError):
    pass


@dataclass(frozen=True)
class StudyCompiled:
    compiled: CompiledQuery
    columns: tuple[str, ...]
    assumptions: tuple[str, ...]
    verification: str = "unverified_semantics"


def column(name: str, table: str | None = None):
    return exp.column(name, table=table, quoted=True)


class StudyCompiler:
    def __init__(self, schema, *, overlay=None, units=(), excluded=(), named=()):
        self.schema, self.overlay = schema, overlay
        self.units = {}
        for raw in units:
            binding = UnitBinding.model_validate(
                raw.model_dump() if isinstance(raw, UnitBinding) else raw
            )
            if binding.column.id in self.units:
                raise StudyRefusal("duplicate_source_unit_binding")
            self.units[binding.column.id] = binding
        self.excluded, self.named = excluded, named
        self.base = PlanCompiler(schema, overlay=overlay)

    def visible(self, table, name=None):
        source = self.schema.table(table)
        return bool(source and (name is None or source.column(name))) and (
            self.overlay is None
            or (
                self.overlay.table_visible(table)
                if name is None
                else self.overlay.visible_column(table, name)
            )
        )

    def compile(self, query: StudyQuery, *, as_of: datetime) -> StudyCompiled:
        query = TypeAdapter(StudyQuery).validate_python(query.model_dump())
        self.params: list[QueryParameter] = []
        self.assumptions = []
        self.parts = []
        self.projected_refs: set[str] = set()
        self.as_of = as_of
        if isinstance(query, RowsQuery):
            tree, outputs = self.rows(query)
        elif isinstance(query, AggregateQuery):
            tree, outputs = self.aggregate(query)
        else:
            tree, outputs = self.combine(query)
        sql = tree.sql(dialect="postgres")
        PostgresSqlPolicy(
            tables={t.name for t in self.schema.tables},
            functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
        ).assert_safe_select_statement(sql)
        template = self.parts[0].compiled
        compiled = template.model_copy(
            update={
                "physical_sql": sql,
                "execution_parameters": self.params,
                "compiler_revision": STUDY_COMPILER_REVISION,
                "semantic_refs": sorted(
                    {r for part in self.parts for r in part.compiled.semantic_refs}
                    | self.projected_refs
                ),
            }
        )
        return StudyCompiled(compiled, tuple(outputs), tuple(self.assumptions))

    def part(self, plan):
        compiled = self.base.compile(
            plan,
            as_of=self.as_of,
            exclude_segments=self.excluded,
            named_segments=self.named,
        )
        prefix = f"p{len(self.parts)}_"
        self.parts.append(compiled)
        self.assumptions.extend(a.text for a in compiled.assumptions)
        tree = sqlglot.parse_one(
            _sqlglot_parameter_syntax(compiled.compiled.physical_sql), read="postgres"
        )
        for node in tree.find_all(exp.Placeholder):
            node.set("this", prefix + node.name)
        self.params.extend(
            p.model_copy(update={"name": prefix + p.name})
            for p in compiled.compiled.execution_parameters
        )
        return tree, list(compiled.output_columns)

    def rows(self, query):
        table = self.schema.table(query.base_table)
        if table is None or not self.visible(query.base_table):
            raise StudyRefusal("unknown_table")
        if not table.primary_key or any(
            not self.visible(table.name, k) for k in table.primary_key
        ):
            raise StudyRefusal("visible_primary_key_required_for_stable_rows")
        refs = (
            [
                ColumnRef(table=table.name, column=c.name)
                for c in table.columns
                if self.visible(table.name, c.name)
            ]
            if query.all_columns
            else query.columns
        )
        if (
            not refs
            or len(refs) > 32
            or any(
                c.table != table.name or not self.visible(c.table, c.column)
                for c in refs
            )
        ):
            raise StudyRefusal("projection_requires_visible_base_columns")
        if any(f.column.table != table.name for f in query.filters):
            raise StudyRefusal("row_filters_require_base_columns")
        self.projected_refs.update(c.id for c in refs)
        # Compile only the row population using existing typed predicates and
        # default segments. Replace the COUNT projection, not its predicates.
        tree, _ = self.part(
            QueryPlan(
                base_table=table.name,
                measures=[{"aggregate": "count"}],
                filters=query.filters,
            )
        )
        tree.set("expressions", [column(c.column, c.table) for c in refs])
        output = [c.column for c in refs]
        for item in query.order:
            if item.field not in output:
                raise StudyRefusal("row_order_requires_projected_column")
            tree = tree.order_by(
                exp.Ordered(
                    this=column(item.field),
                    desc=item.direction == "desc",
                    nulls_first=False,
                )
            )
        ordered = {o.field for o in query.order}
        for key in table.primary_key:
            if key not in ordered:
                tree = tree.order_by(column(key, table.name).asc())
        if query.limit is not None:
            name = "row_limit"
            self.params.append(
                QueryParameter(name=name, type_name="integer", value=query.limit)
            )
            tree = tree.limit(exp.Placeholder(this=name))
        # COUNT skeleton disclosure is not the calculation being returned.
        self.assumptions = [
            a for a in self.assumptions if "COUNT" not in a and "count(*)" not in a
        ]
        self.assumptions.append(
            f"Visible row projection: {', '.join(c.id for c in refs)}; "
            "stable primary-key ordering. No aggregation in this relation."
        )
        self.assumptions.append(
            f"Explicit query LIMIT {query.limit}; this is not all matching rows."
            if query.limit
            else "No SQL LIMIT; serving may still truncate rows and must disclose it."
        )
        return tree, output

    def aggregate(self, query):
        plan = query.plan
        if query.conversion is None:
            return self.part(plan)
        if (
            plan.having
            or plan.growth
            or plan.latest
            or any(m.ratio or m.share_of_total for m in plan.measures)
        ):
            raise StudyRefusal("conversion_combination_unsupported")
        target = next(
            (m for m in plan.measures if m.output_name == query.conversion.field), None
        )
        if target is None:
            raise StudyRefusal("unknown_conversion_output")
        metric = (
            self.overlay.metric(target.metric)
            if self.overlay and target.metric
            else None
        )
        ref = metric.column if metric else target.column
        aggregate = metric.aggregate if metric else target.aggregate
        binding = self.units.get(ref.id) if ref else None
        if binding is None:
            raise StudyRefusal("source_unit_not_bound")
        source, dest = binding.unit, query.conversion.target_unit
        temperature = source in {"celsius", "fahrenheit"}
        allowed = {Aggregate.AVG, Aggregate.MIN, Aggregate.MAX}
        if not temperature:
            allowed.add(Aggregate.SUM)
        if aggregate not in allowed:
            raise StudyRefusal("unit_aggregate_incompatible")
        # These are dimensioned standard conversions, not datasource rules.
        constants = {
            ("celsius", "fahrenheit"): (9, 5, 32),
            ("fahrenheit", "celsius"): (5, 9, -32),
            ("minutes", "hours"): (1, 60, 0),
            ("hours", "minutes"): (60, 1, 0),
        }
        if source != dest and (source, dest) not in constants:
            raise StudyRefusal("unit_dimensions_incompatible")
        inner, outputs = self.part(plan.model_copy(update={"order": [], "limit": None}))
        value = column(target.output_name, "converted")
        if source != dest:
            mul, divisor, offset = constants[source, dest]
            if source == "fahrenheit":
                value = exp.paren(
                    exp.Add(this=value, expression=exp.Literal.number(offset))
                )
            value = exp.Div(
                this=exp.Mul(this=value, expression=exp.Literal.number(f"{mul}.0")),
                expression=exp.Literal.number(f"{divisor}.0"),
            )
            if source == "celsius":
                value = exp.Add(this=value, expression=exp.Literal.number(offset))
        outer = exp.select(
            *[
                (
                    value.copy()
                    if name == target.output_name
                    else column(name, "converted")
                ).as_(name, quoted=True)
                for name in outputs
            ]
        ).from_(inner.subquery("converted"))
        for item in plan.order:
            outer = outer.order_by(
                exp.Ordered(
                    this=column(item.field),
                    desc=item.direction == "desc",
                    nulls_first=False,
                )
            )
        if plan.limit is not None:
            self.params.append(
                QueryParameter(
                    name="conversion_limit", type_name="integer", value=plan.limit
                )
            )
            outer = outer.limit(exp.Placeholder(this="conversion_limit"))
        self.assumptions.append(
            f"{target.output_name}: {source} -> {dest}; standard SQL conversion, "
            f"NULL preserved, no rounding. Source unit evidence: {binding.evidence}."
        )
        return outer, outputs

    def combine(self, query: CombinedQuery):
        entity = self.schema.table(query.entity_table)
        if entity is None or len(entity.primary_key) != 1:
            raise StudyRefusal("combine_requires_single_entity_primary_key")
        key = entity.primary_key[0]
        refs = [ColumnRef(table=entity.name, column=key)]
        for ref in query.entity_columns:
            if ref not in refs:
                refs.append(ref)
        if len({r.column for r in refs}) != len(refs):
            raise StudyRefusal("duplicate_entity_output")
        entity_tree, outputs = self.rows(
            RowsQuery(
                kind="rows",
                base_table=entity.name,
                columns=refs,
                filters=query.entity_filters,
            )
        )
        entity_tree.set("order", None)
        selected = [column(name, "entities") for name in outputs]
        outer = exp.select().from_(entity_tree.subquery("entities"))
        for i, plan in enumerate(query.components):
            measures = [m.output_name for m in plan.measures]
            if any(name in outputs or name.startswith("__study_") for name in measures):
                raise StudyRefusal("colliding_component_output")
            component, _ = self.part(
                plan.model_copy(
                    update={"dimensions": [ColumnRef(table=entity.name, column=key)]}
                )
            )
            alias = f"component_{i}"
            outer = outer.join(
                component.subquery(alias),
                on=exp.EQ(this=column(key, "entities"), expression=column(key, alias)),
                join_type="LEFT",
            )
            for measure in plan.measures:
                metric = (
                    self.overlay.metric(measure.metric)
                    if self.overlay and measure.metric
                    else None
                )
                aggregate = metric.aggregate if metric else measure.aggregate
                expr = column(measure.output_name, alias)
                if aggregate in {Aggregate.COUNT, Aggregate.COUNT_DISTINCT}:
                    expr = exp.Coalesce(this=expr, expressions=[exp.Literal.number(0)])
                selected.append(expr.as_(measure.output_name, quoted=True))
            outputs.extend(measures)
        outer = outer.select(*selected)
        if query.selection:
            field = query.selection.field
            rank_func = exp.Max if query.selection.direction == "max" else exp.Min
            ranked = exp.select(
                *[column(name, "combined") for name in outputs],
                exp.Window(this=rank_func(this=column(field, "combined"))).as_(
                    "__study_extreme"
                ),
            ).from_(outer.subquery("combined"))
            outer = (
                exp.select(*[column(name, "ranked") for name in outputs])
                .from_(ranked.subquery("ranked"))
                .where(
                    exp.EQ(
                        this=column(field, "ranked"),
                        expression=column("__study_extreme", "ranked"),
                    )
                )
            )
            self.assumptions.append(
                f"Select all non-NULL {query.selection.direction} ties of {field}; "
                "missing values of other components never exclude a winner."
            )
        outer = outer.order_by(column(key).asc())
        self.assumptions.append(
            "Independent aggregates joined by entity primary key, not labels; "
            "full filtered entity population. Missing child COUNT is 0; other "
            "missing aggregates remain NULL. Each component keeps its own "
            "explicit time scope."
        )
        return outer, outputs
