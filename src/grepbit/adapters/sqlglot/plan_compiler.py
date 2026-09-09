"""Compile a tier-0 QueryPlan into parameterized SQL with structural validation.

Implements ``grepbit.ports.plan_compiler.PlanCompilerPort`` with sqlglot.

The plan carries only schema identifiers and typed literal values. This module
checks the plan against the introspected SchemaModel (tables exist, joins
follow foreign keys away from the base table, aggregates fit column kinds,
filters are typed) and builds the SQL as a sqlglot AST, never as string
templates. It also derives the lineage and the assumptions the caller sees.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlglot import exp

from grepbit.domain.assumptions import Assumption, AssumptionSource
from grepbit.domain.models import (
    CompiledQuery,
    ParameterMode,
    QueryParameter,
    SemanticRefSource,
)
from grepbit.domain.overlay import (
    ReviewedMetric,
    ReviewState,
    Segment,
    SemanticOverlay,
)
from grepbit.domain.plan import (
    Aggregate,
    ColumnRef,
    CompiledPlan,
    Filter,
    FilterOp,
    Lineage,
    Measure,
    PlanError,
    QueryPlan,
)
from grepbit.domain.schema_model import (
    ColumnKind,
    ForeignKey,
    SchemaColumn,
    SchemaModel,
)
from grepbit.domain.structured_query import (
    RelativeScope,
    ResolvedPeriod,
    current_unit_end,
    resolve_time_scope,
)

COMPILER_REVISION = "plan-compiler-sqlglot-v1"
PERIOD_COLUMN = "period_start"
_AGGREGATE_FUNCTIONS = {
    Aggregate.SUM: "SUM",
    Aggregate.AVG: "AVG",
    Aggregate.MIN: "MIN",
    Aggregate.MAX: "MAX",
    Aggregate.COUNT: "COUNT",
}
_NUMERIC_ONLY = {Aggregate.SUM, Aggregate.AVG}
_ORDERED_KINDS = {
    ColumnKind.NUMERIC,
    ColumnKind.TEXT,
    ColumnKind.TIMESTAMP,
    ColumnKind.DATE,
}


class PlanCompiler:
    def __init__(
        self, schema: SchemaModel, *, overlay: SemanticOverlay | None = None
    ) -> None:
        self._schema = schema
        self._overlay = overlay

    def compile(
        self,
        plan: QueryPlan,
        *,
        as_of: datetime,
        exclude_segments: Sequence[Segment] = (),
    ) -> CompiledPlan:
        schema = self._schema
        base = schema.table(plan.base_table)
        if base is None or not self._visible(plan.base_table):
            raise PlanError("unknown_table", plan.base_table)
        joins: dict[str, ForeignKey] = {}
        assumptions: list[Assumption] = []

        # Reviewed metrics expand into their aggregate, their defining filters,
        # and possibly the time column the definition prescribes.
        effective: list[tuple[Measure, ReviewedMetric | None]] = []
        metric_filters: list[tuple[str, Filter]] = []
        time_override: ColumnRef | None = None
        for measure in plan.measures:
            if measure.metric is None:
                effective.append((measure, None))
                continue
            metric = self._overlay.metric(measure.metric) if self._overlay else None
            if metric is None:
                raise PlanError("unknown_metric", measure.metric)
            if metric.base_table != base.name:
                raise PlanError("metric_base_table_mismatch", measure.metric)
            if metric.time_column is not None:
                if time_override is not None and time_override != metric.time_column:
                    raise PlanError("metric_conflict", measure.metric)
                time_override = metric.time_column
            effective.append(
                (
                    measure.model_copy(
                        update={
                            "aggregate": metric.aggregate,
                            "column": metric.column,
                            "metric": None,
                            "alias": measure.alias or metric.id,
                        }
                    ),
                    metric,
                )
            )
            metric_filters.extend((metric.id, item) for item in metric.filters)
        # Default-excluded segments: applied when the segment's table is the base
        # table or reachable from it, and nothing in the plan already filters on
        # the segment's column (a return metric must keep its own rows).
        referenced = {f.column.id for f in plan.filters} | {
            f.column.id for _, f in metric_filters
        }
        segment_filters: list[tuple[Segment, Filter]] = []
        for segment in exclude_segments:
            if segment.filter.column.id in referenced:
                continue
            if segment.table != base.name:
                try:
                    _parent_path(schema, base.name, segment.table)
                except PlanError:
                    continue
            segment_filters.append((segment, segment.inverse()))

        time_spec = plan.time
        if (
            time_spec is not None
            and time_override is not None
            and time_spec.column != time_override
        ):
            time_spec = time_spec.model_copy(update={"column": time_override})
            assumptions.append(
                Assumption(
                    text=(
                        f"Time is measured on {time_override.id} as the reviewed "
                        f"definition prescribes, not on {plan.time.column.id}."
                    ),
                    source=AssumptionSource.REVIEWED,
                    definition_ref="overlay.metrics.time_column",
                )
            )

        def resolve(ref: ColumnRef) -> SchemaColumn:
            table = schema.table(ref.table)
            if table is None or not self._visible(ref.table):
                raise PlanError("unknown_table", ref.table)
            if not self._visible(ref.table, ref.column):
                raise PlanError("unknown_column", ref.id)
            column = table.column(ref.column)
            if column is None:
                raise PlanError("unknown_column", ref.id)
            if ref.table != base.name and ref.table not in joins:
                # Only walk foreign keys away from the base table: every hop is
                # many-to-one, so the base grain is preserved and nothing fans out.
                for link in _parent_path(schema, base.name, ref.table):
                    joins.setdefault(link.referenced_table, link)
            return column

        parameters: list[QueryParameter] = []

        def bind(prefix: str, value: object, type_name: str) -> exp.Placeholder:
            name = f"{prefix}{len(parameters)}"
            parameters.append(
                QueryParameter(name=name, type_name=type_name, value=value)  # type: ignore[arg-type]
            )
            return exp.Placeholder(this=name)

        selects: list[exp.Expression] = []
        group_by: list[exp.Expression] = []
        output: list[str] = []

        time_bucket: exp.Expression | None = None
        periods: tuple[ResolvedPeriod, ...] = ()
        time_column: SchemaColumn | None = None
        if time_spec is not None:
            time_column = resolve(time_spec.column)
            if time_column.kind not in {ColumnKind.TIMESTAMP, ColumnKind.DATE}:
                raise PlanError("time_column_kind_mismatch", time_spec.column.id)
            scope = time_spec.scope
            if scope is not None:
                periods = tuple(
                    resolve_time_scope(
                        scope,
                        as_of=as_of,
                        business_timezone=schema.business_timezone,
                    )
                )
            if len(periods) > 1 and time_spec.grain is None:
                raise PlanError("time_scope_requires_grain")
            if isinstance(scope, RelativeScope) and scope.offset < 0:
                limit = current_unit_end(as_of, scope.unit, schema.business_timezone)
                if periods[-1].end_exclusive > limit:
                    raise PlanError(
                        "relative_window_reaches_future",
                        f"{scope.unit.value} offset {scope.offset} length "
                        f"{scope.length} ends {periods[-1].end_exclusive.date()}",
                    )
            if time_spec.grain is not None:
                column_expression = exp.column(
                    time_spec.column.column, table=time_spec.column.table
                )
                if time_column.kind is ColumnKind.TIMESTAMP:
                    column_expression = exp.AtTimeZone(
                        this=column_expression,
                        zone=exp.Literal.string(schema.business_timezone),
                    )
                time_bucket = exp.func(
                    "DATE_TRUNC",
                    exp.Literal.string(time_spec.grain.value),
                    column_expression,
                )
                if time_column.kind is ColumnKind.DATE:
                    # PostgreSQL would pick the timestamptz overload for a date
                    # and truncate in the session time zone; keep the bucket a DATE.
                    time_bucket = exp.cast(time_bucket, exp.DataType.Type.DATE)
                selects.append(time_bucket.as_(PERIOD_COLUMN))
                group_by.append(time_bucket)
                output.append(PERIOD_COLUMN)

        for dimension in plan.dimensions:
            resolve(dimension)
            expression = exp.column(dimension.column, table=dimension.table)
            selects.append(expression.as_(dimension.column))
            group_by.append(expression)
            output.append(dimension.column)

        for measure, _metric in effective:
            selects.append(self._aggregate(measure, resolve).as_(measure.output_name))
            output.append(measure.output_name)

        conditions: list[exp.Expression] = []
        filter_texts: list[str] = []
        for item in plan.filters:
            column = resolve(item.column)
            conditions.append(self._condition(item, column, bind))
            filter_texts.append(_filter_text(item))
        for metric_id, item in metric_filters:
            column = resolve(item.column)
            conditions.append(self._condition(item, column, bind))
            filter_texts.append(f"[{metric_id}] {_filter_text(item)}")
        for segment, item in segment_filters:
            column = resolve(item.column)
            conditions.append(self._condition(item, column, bind))
            filter_texts.append(f"[default: exclude {segment.id}] {_filter_text(item)}")
            assumptions.append(
                Assumption(
                    text=(
                        f"Rows of segment '{segment.id}' ({segment.note}) are "
                        f"excluded by default; say '{segment.names[0]}' to include "
                        "them."
                    ),
                    source=AssumptionSource.REVIEWED,
                    definition_ref=f"overlay.segments.{segment.id}",
                )
            )
        time_texts: list[str] = []
        if time_spec is not None and periods:
            reference = exp.column(
                time_spec.column.column, table=time_spec.column.table
            )
            windows = []
            for index, period in enumerate(periods, start=1):
                start = bind(
                    f"p{index}_start_", period.start.isoformat(), "timestamptz"
                )
                end = bind(
                    f"p{index}_end_", period.end_exclusive.isoformat(), "timestamptz"
                )
                windows.append(exp.and_(reference >= start, reference < end))
                time_texts.append(
                    f"{time_spec.column.id} in [{period.start.isoformat()}, "
                    f"{period.end_exclusive.isoformat()})"
                )
            conditions.append(windows[0] if len(windows) == 1 else exp.or_(*windows))

        query = exp.select(*selects).from_(exp.table_(base.name, db=schema.schema_name))
        for parent_name, link in joins.items():
            query = query.join(
                exp.table_(parent_name, db=schema.schema_name),
                on=exp.column(link.column, table=link.table).eq(
                    exp.column(link.referenced_column, table=parent_name)
                ),
                join_type="left",
            )
        if conditions:
            query = query.where(exp.and_(*conditions))
        if group_by:
            query = query.group_by(*group_by)
        having_texts: list[str] = []
        if plan.having:
            aggregates = {
                measure.output_name: self._aggregate(measure, resolve)
                for measure, _ in effective
            }
            conditions_having = []
            for item in plan.having:
                expression = aggregates[item.field]
                placeholder = bind("h_", item.value, "numeric")
                conditions_having.append(
                    {
                        "gt": expression > placeholder,
                        "gte": expression >= placeholder,
                        "lt": expression < placeholder,
                        "lte": expression <= placeholder,
                        "eq": expression.eq(placeholder),
                        "ne": expression.neq(placeholder),
                    }[item.op]
                )
                having_texts.append(f"{item.field} {item.op} {item.value}")
            query = query.having(exp.and_(*conditions_having))
        if plan.order:
            for item in plan.order:
                column = exp.column(item.field)
                query = query.order_by(
                    column.desc() if item.direction == "desc" else column.asc()
                )
        elif group_by:
            for name in output:
                if name in {measure.output_name for measure, _ in effective}:
                    continue
                query = query.order_by(exp.column(name).asc())
        if plan.limit is not None:
            query = query.limit(bind("limit_", plan.limit, "integer"))

        for parent_name, link in joins.items():
            assumptions.append(
                Assumption(
                    text=(
                        f"{base.name} rows are joined to {parent_name} through "
                        f"{link.table}.{link.column}; rows without a matching "
                        f"{parent_name} row keep NULL there."
                    ),
                    source=AssumptionSource.DEFAULT,
                    definition_ref=f"foreign_keys.{link.table}.{link.column}",
                )
            )
            if link.inferred:
                assumptions.append(
                    Assumption(
                        text=(
                            f"The join {link.id} is inferred, not a declared "
                            f"foreign key: {link.evidence or 'no evidence recorded'}."
                        ),
                        source=AssumptionSource.CANDIDATE,
                        definition_ref=(
                            f"inferred_foreign_keys.{link.table}.{link.column}"
                        ),
                    )
                )
        for measure, metric in effective:
            if metric is not None:
                assumptions.append(
                    Assumption(
                        text=f"{measure.output_name} = {metric.description}",
                        source=AssumptionSource.REVIEWED
                        if metric.review_state is ReviewState.VERIFIED
                        else AssumptionSource.CANDIDATE,
                        definition_ref=f"overlay.metrics.{metric.id}",
                    )
                )
                continue
            if measure.aggregate in {
                Aggregate.SUM,
                Aggregate.AVG,
                Aggregate.MIN,
                Aggregate.MAX,
            }:
                assumptions.append(
                    Assumption(
                        text=(
                            f"{measure.output_name} = "
                            f"{measure.aggregate.value.upper()} of "
                            f"{measure.column.id if measure.column else base.name}; "
                            "NULL values are ignored by the aggregate."
                        ),
                        source=AssumptionSource.DEFAULT,
                        definition_ref=f"plan.measures.{measure.output_name}",
                    )
                )
        if not plan.filters:
            assumptions.append(
                Assumption(
                    text=(
                        f"No row filter was applied beyond the time window; every "
                        f"{base.name} row counts, including any status the question "
                        "did not mention."
                    ),
                    source=AssumptionSource.DEFAULT,
                    definition_ref=f"plan.base_table.{base.name}",
                )
            )
        if time_spec is not None and periods:
            prefix = (
                f"Relative period resolved from as_of {as_of.isoformat()}: "
                if isinstance(time_spec.scope, RelativeScope)
                else ""
            )
            for period in periods:
                assumptions.append(
                    Assumption(
                        text=(
                            f"{prefix}{period.label} is [{period.start.isoformat()}, "
                            f"{period.end_exclusive.isoformat()}) in "
                            f"{schema.business_timezone} on {time_spec.column.id}."
                        ),
                        source=AssumptionSource.DEFAULT,
                        definition_ref=f"time_spec.{time_spec.column.id}",
                    )
                )
        elif time_spec is None:
            assumptions.append(
                Assumption(
                    text="No time window was applied; all rows count.",
                    source=AssumptionSource.DEFAULT,
                    definition_ref=f"plan.base_table.{base.name}",
                )
            )
        metrics_used = [metric for _, metric in effective if metric is not None]
        if metrics_used and len(metrics_used) == len(effective):
            all_verified = all(
                m.review_state is ReviewState.VERIFIED for m in metrics_used
            )
            verification = (
                "verified"
                if all_verified and not plan.filters
                else "partially_verified"
            )
            if verification == "partially_verified":
                assumptions.append(
                    Assumption(
                        text=(
                            "Measures follow reviewed definitions; the extra filters "
                            "taken from the question are checked for structure only."
                        ),
                        source=AssumptionSource.CANDIDATE,
                        definition_ref=f"schema.{schema.datasource_id}",
                    )
                )
        else:
            verification = "unverified_semantics"
            assumptions.append(
                Assumption(
                    text=(
                        "Column meanings come from the schema only; no reviewed "
                        "business definition was applied."
                    ),
                    source=AssumptionSource.CANDIDATE,
                    definition_ref=f"schema.{schema.datasource_id}",
                )
            )

        lineage = Lineage(
            base_table=base.name,
            tables=(base.name, *joins.keys()),
            joins=tuple(
                link.id + (" (inferred)" if link.inferred else "")
                for link in joins.values()
            ),
            measures=tuple(
                f"{m.output_name} = {m.aggregate.value}"
                f"({m.column.id if m.column else '*'})"
                + (f" [{metric.id}]" if metric else "")
                for m, metric in effective
            ),
            dimensions=tuple(d.id for d in plan.dimensions),
            filters=tuple(filter_texts),
            having=tuple(having_texts),
            time_window=tuple(time_texts),
        )
        semantic_refs = sorted(
            {
                *(m.column.id for m, _ in effective if m.column),
                *(d.id for d in plan.dimensions),
                *(f.column.id for f in plan.filters),
                *(f.column.id for _, f in metric_filters),
                *([time_spec.column.id] if time_spec else []),
            }
        )
        compiled = CompiledQuery(
            physical_sql=query.sql(dialect="postgres"),
            execution_parameters=parameters,
            parameter_mode=ParameterMode.PRESERVED_BINDING,
            semantic_refs=semantic_refs,
            semantic_ref_source=SemanticRefSource.COMPILER_RESOLVED,
            compiler_revision=COMPILER_REVISION,
        )
        return CompiledPlan(
            plan=plan,
            compiled=compiled,
            output_columns=tuple(output),
            lineage=lineage,
            assumptions=tuple(assumptions),
            interpretation=_interpretation(plan, periods),
            periods=periods,
            verification=verification,
        )

    def _visible(self, table: str, column: str | None = None) -> bool:
        """Hidden tables and columns (overlay policies) do not exist for a plan.

        Key columns stay usable for joins through the foreign-key walk, which
        does not go through ``resolve``; only what the plan names is checked.
        """

        if self._overlay is None:
            return True
        if column is None:
            return self._overlay.table_visible(table)
        return self._overlay.visible_column(table, column)

    @staticmethod
    def _aggregate(measure: Measure, resolve) -> exp.Expression:
        assert measure.aggregate is not None  # metrics were expanded already
        if measure.column is None:
            return exp.Count(this=exp.Star())
        column = resolve(measure.column)
        reference = exp.column(measure.column.column, table=measure.column.table)
        if measure.aggregate in _NUMERIC_ONLY and column.kind is not ColumnKind.NUMERIC:
            raise PlanError("aggregate_kind_mismatch", measure.column.id)
        if (
            measure.aggregate in {Aggregate.MIN, Aggregate.MAX}
            and column.kind not in _ORDERED_KINDS
        ):
            raise PlanError("aggregate_kind_mismatch", measure.column.id)
        if measure.aggregate is Aggregate.COUNT_DISTINCT:
            return exp.Count(this=exp.Distinct(expressions=[reference]))
        return exp.func(_AGGREGATE_FUNCTIONS[measure.aggregate], reference)

    @staticmethod
    def _condition(item: Filter, column: SchemaColumn, bind) -> exp.Expression:
        reference = exp.column(item.column.column, table=item.column.table)
        if item.op is FilterOp.IS_NULL:
            return reference.is_(exp.Null())
        if item.op is FilterOp.NOT_NULL:
            return exp.Not(this=reference.is_(exp.Null()))
        type_name = _bind_type(column, item.values)
        placeholders = [bind("f_", value, type_name) for value in item.values]
        if column.is_enum:
            # An enum compared with a literal outside its labels raises in
            # PostgreSQL; compared as text it simply matches no row.
            reference = exp.cast(reference, "text")
        if item.op is FilterOp.IN:
            return reference.isin(*placeholders)
        [placeholder] = placeholders
        return {
            FilterOp.EQ: reference.eq(placeholder),
            FilterOp.NE: reference.neq(placeholder),
            FilterOp.GT: reference > placeholder,
            FilterOp.GTE: reference >= placeholder,
            FilterOp.LT: reference < placeholder,
            FilterOp.LTE: reference <= placeholder,
        }[item.op]


def _parent_path(schema: SchemaModel, base: str, target: str) -> list[ForeignKey]:
    """Shortest chain of foreign keys from ``base`` to ``target`` (max 3 hops)."""

    frontier: list[tuple[str, list[ForeignKey]]] = [(base, [])]
    seen = {base}
    for _ in range(3):
        next_frontier: list[tuple[str, list[ForeignKey]]] = []
        hits: list[list[ForeignKey]] = []
        for table, path in frontier:
            links = schema.parent_links(table)
            hits.extend(
                [*path, link] for link in links if link.referenced_table == target
            )
            for link in links:
                if link.referenced_table not in seen:
                    seen.add(link.referenced_table)
                    next_frontier.append((link.referenced_table, [*path, link]))
        if len(hits) > 1:
            # Two different chains reach the target at the same depth (for
            # example an assignment's employee's department versus its
            # project's department): the plan cannot say which one it means.
            raise PlanError("ambiguous_join_path", target)
        if hits:
            return hits[0]
        frontier = next_frontier
    raise PlanError("grain_conflict", target)


def _bind_type(column: SchemaColumn, values: list[object]) -> str:
    if column.kind is ColumnKind.NUMERIC:
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in values
        ):
            raise PlanError("filter_kind_mismatch", column.name)
        return "numeric"
    if column.kind is ColumnKind.BOOLEAN:
        if not all(isinstance(v, bool) for v in values):
            raise PlanError("filter_kind_mismatch", column.name)
        return "boolean"
    if not all(isinstance(v, str) for v in values):
        raise PlanError("filter_kind_mismatch", column.name)
    if column.kind is ColumnKind.TIMESTAMP:
        return "timestamptz"
    if column.kind is ColumnKind.DATE:
        return "date"
    return "text"


def _filter_text(item: Filter) -> str:
    if item.op in {FilterOp.IS_NULL, FilterOp.NOT_NULL}:
        return f"{item.column.id} {item.op.value}"
    values = ", ".join(str(v) for v in item.values)
    return f"{item.column.id} {item.op.value} {values}"


def _interpretation(plan: QueryPlan, periods: tuple[ResolvedPeriod, ...]) -> str:
    parts = [
        ", ".join(
            f"metric {m.metric}"
            if m.metric
            else f"{m.aggregate.value}({m.column.id if m.column else '*'})"  # type: ignore[union-attr]
            for m in plan.measures
        )
        + f" over {plan.base_table}"
    ]
    if plan.dimensions:
        parts.append("by " + ", ".join(d.id for d in plan.dimensions))
    if plan.time is not None and plan.time.grain is not None:
        parts.append(f"per {plan.time.grain.value}")
    if periods:
        parts.append("for " + ", ".join(p.label for p in periods))
    elif plan.time is not None:
        parts.append("over all data")
    if plan.filters:
        parts.append("where " + " and ".join(_filter_text(f) for f in plan.filters))
    if plan.having:
        parts.append(
            "having " + " and ".join(f"{h.field} {h.op} {h.value}" for h in plan.having)
        )
    if plan.limit is not None:
        parts.append(f"limit {plan.limit}")
    return "; ".join(parts)


__all__ = ["COMPILER_REVISION", "PERIOD_COLUMN", "PlanCompiler"]
