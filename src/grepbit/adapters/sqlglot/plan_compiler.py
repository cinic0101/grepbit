"""Compile a tier-0 QueryPlan into parameterized SQL with structural validation.

Implements ``grepbit.ports.plan_compiler.PlanCompilerPort`` with sqlglot.

The plan carries only schema identifiers and typed literal values. This module
checks the plan against the introspected SchemaModel (tables exist, joins
follow foreign keys away from the base table, aggregates fit column kinds,
filters are typed) and builds the SQL as a sqlglot AST, never as string
templates. It also derives the lineage and the assumptions the caller sees.
"""

from __future__ import annotations

import json
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
    Operand,
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
        named_segments: Sequence[Segment] = (),
    ) -> CompiledPlan:
        schema = self._schema
        assumptions: list[Assumption] = []
        base_name = plan.base_table or self._derive_base_table(plan, assumptions)
        base = schema.table(base_name)
        if base is None or not self._visible(base_name):
            raise PlanError("unknown_table", base_name)
        joins: dict[str, ForeignKey] = {}

        # Every operand (a measure, or a ratio's numerator and denominator)
        # resolves to an aggregate, its own defining filters (from a reviewed
        # metric) and the metric itself. A metric may prescribe the time column.
        time_override: ColumnRef | None = None

        def resolve_operand(operand: Operand) -> tuple[Operand, ReviewedMetric | None]:
            nonlocal time_override
            if operand.metric is None:
                return operand, None
            metric = self._overlay.metric(operand.metric) if self._overlay else None
            if metric is None:
                raise PlanError("unknown_metric", operand.metric)
            if metric.base_table != base.name:
                raise PlanError("metric_base_table_mismatch", operand.metric)
            if metric.time_column is not None:
                if time_override is not None and time_override != metric.time_column:
                    raise PlanError("metric_conflict", operand.metric)
                time_override = metric.time_column
            expanded = Operand(aggregate=metric.aggregate, column=metric.column)
            return expanded, metric

        # effective: one entry per plan measure, with the resolved operands.
        effective: list[tuple[Measure, list[tuple[Operand, ReviewedMetric | None]]]]
        effective = []
        for measure in plan.measures:
            if measure.ratio is not None:
                parts = [
                    resolve_operand(measure.ratio.numerator),
                    resolve_operand(measure.ratio.denominator),
                ]
            else:
                parts = [resolve_operand(measure)]
            effective.append((measure, parts))
        # Metric filters: when every operand carries the same filters they go in
        # WHERE (one metric, the common case); when operands differ (a ratio
        # of a filtered metric over an unfiltered total, two metrics) each
        # aggregate gets its own FILTER (WHERE ...) so the rows stay shared.
        operand_filters = [
            tuple(
                json.dumps(f.model_dump(mode="json"), sort_keys=True)
                for f in metric.filters
            )
            if metric
            else ()
            for _, parts in effective
            for _, metric in parts
        ]
        shared_filters = len(set(operand_filters)) == 1
        metric_filters: list[tuple[str, Filter]] = []
        if shared_filters:
            for _, parts in effective:
                for _, metric in parts:
                    if metric is not None:
                        metric_filters = [(metric.id, f) for f in metric.filters]
                        break
                if metric_filters:
                    break
        all_metric_filters = [
            (metric.id, f)
            for _, parts in effective
            for _, metric in parts
            if metric is not None
            for f in metric.filters
        ]
        # Default-excluded segments are an operand-level default. A segment
        # whose column the plan itself filters is left alone; a segment that some
        # operand's metric filters reference (a return metric) is excluded from
        # the other operands only, as FILTER clauses, so a ratio of returns over
        # sales keeps gross sales in its denominator; a segment the question names
        # without any operand referencing it is lifted for the whole query;
        # otherwise the exclusion is a WHERE condition. Only segments on the base
        # table or on a table reachable from it apply.
        plan_filter_columns = {f.column.id for f in plan.filters}
        operand_columns = [
            {f.column.id for f in metric.filters} if metric else set()
            for _, parts in effective
            for _, metric in parts
        ]
        segment_filters: list[tuple[Segment, Filter]] = []
        operand_segment_filters: list[tuple[Segment, Filter, set[int]]] = []
        named_ids = {seg.id for seg in named_segments}
        for segment in list(exclude_segments) + list(named_segments):
            column_id = segment.filter.column.id
            if column_id in plan_filter_columns:
                continue
            if segment.table != base.name:
                try:
                    _parent_path(schema, base.name, segment.table)
                except PlanError:
                    continue
            referencing = {
                i for i, cols in enumerate(operand_columns) if column_id in cols
            }
            if referencing:
                others = set(range(len(operand_columns))) - referencing
                if others:
                    operand_segment_filters.append((segment, segment.inverse(), others))
            elif segment.id not in named_ids:
                segment_filters.append((segment, segment.inverse()))

        time_spec = plan.time
        if time_spec is not None and time_spec.column is None:
            default = self._overlay.time_default(base.name) if self._overlay else None
            if default is None and time_override is None:
                raise PlanError("time_column_required", base.name)
            chosen = time_override or default
            time_spec = time_spec.model_copy(update={"column": chosen})
            assumptions.append(
                Assumption(
                    text=(
                        f"Time is measured on {chosen.id}, the default time column "
                        f"of {base.name}; no column was named."
                    ),
                    source=AssumptionSource.REVIEWED,
                    definition_ref=f"overlay.time_defaults.{base.name}",
                )
            )
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
        assert time_spec is None or time_spec.column is not None

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
            if isinstance(scope, RelativeScope):
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

        operand_position = {"i": 0}

        def operand_expression(
            operand: Operand, metric: ReviewedMetric | None
        ) -> exp.Expression:
            position = operand_position["i"]
            operand_position["i"] += 1
            aggregate = self._aggregate(operand, resolve)
            clauses = []
            if metric is not None and metric.filters and not shared_filters:
                for item in metric.filters:
                    clauses.append(self._condition(item, resolve(item.column), bind))
            for _segment, item, others in operand_segment_filters:
                if position in others:
                    clauses.append(self._condition(item, resolve(item.column), bind))
            if clauses:
                aggregate = exp.Filter(
                    this=aggregate, expression=exp.Where(this=exp.and_(*clauses))
                )
            return aggregate

        measure_expressions: dict[str, exp.Expression] = {}
        for measure, parts in effective:
            if measure.ratio is not None:
                numerator = operand_expression(*parts[0])
                denominator = operand_expression(*parts[1])
                expression: exp.Expression = exp.Div(
                    this=exp.paren(numerator),
                    expression=exp.func("NULLIF", denominator, exp.Literal.number(0)),
                )
            else:
                expression = operand_expression(*parts[0])
            if measure.share_of_total:
                total = exp.Window(
                    this=exp.Sum(this=expression.copy()),
                    partition_by=[time_bucket.copy()]
                    if time_bucket is not None
                    else [],
                )
                expression = exp.Div(
                    this=exp.paren(expression),
                    expression=exp.func("NULLIF", total, exp.Literal.number(0)),
                )
            measure_expressions[measure.output_name] = expression
            selects.append(expression.as_(measure.output_name))
            output.append(measure.output_name)
        growth_names: list[str] = []
        for item in plan.growth:
            assert time_bucket is not None  # validated: growth requires a grain
            current = measure_expressions[item.measure]
            previous = exp.Window(
                this=exp.func("LAG", current.copy()),
                partition_by=[
                    exp.column(d.column, table=d.table) for d in plan.dimensions
                ],
                order=exp.Order(expressions=[exp.Ordered(this=time_bucket.copy())]),
            )
            growth = exp.Div(
                this=exp.paren(exp.Sub(this=current.copy(), expression=previous)),
                expression=exp.func("NULLIF", previous.copy(), exp.Literal.number(0)),
            )
            name = f"{item.measure}_growth"
            selects.append(growth.as_(name))
            output.append(name)
            growth_names.append(name)

        conditions: list[exp.Expression] = []
        filter_texts: list[str] = []
        # A share asked for one group (特約永和中正 佔全部門市) must still be
        # taken over all groups: a filter on a grouped column selects which
        # rows come back after the share, it does not shrink the population.
        dimension_ids = {d.id for d in plan.dimensions}
        selection_filters: list[Filter] = (
            [f for f in plan.filters if f.column.id in dimension_ids]
            if any(m.share_of_total for m in plan.measures)
            else []
        )
        for item in plan.filters:
            column = resolve(item.column)
            if item in selection_filters:
                filter_texts.append(f"[after share] {_filter_text(item)}")
                continue
            conditions.append(self._condition(item, column, bind))
            filter_texts.append(_filter_text(item))
        for item in selection_filters:
            assumptions.append(
                Assumption(
                    text=(
                        f"The share is taken over all {item.column.column} groups; "
                        f"the filter on {item.column.id} only selects which groups "
                        "are returned, so it is the subset's share of the whole."
                    ),
                    source=AssumptionSource.DEFAULT,
                    definition_ref="plan.measures.share_of_total",
                )
            )
        for metric_id, item in metric_filters:
            column = resolve(item.column)
            conditions.append(self._condition(item, column, bind))
            filter_texts.append(f"[{metric_id}] {_filter_text(item)}")
        for segment, item, _others in operand_segment_filters:
            filter_texts.append(
                f"[default: exclude {segment.id} from the measures that do not "
                f"reference it] {_filter_text(item)}"
            )
            assumptions.append(
                Assumption(
                    text=(
                        f"Rows of segment '{segment.id}' ({segment.note}) are excluded "
                        "from every measure that does not itself select them, so a "
                        "ratio keeps its denominator free of them."
                    ),
                    source=AssumptionSource.REVIEWED,
                    definition_ref=f"overlay.segments.{segment.id}",
                )
            )
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
        if selection_filters:
            inner = query
            query = exp.select(exp.Star()).from_(inner.subquery("shares"))
            selected = [
                self._condition(
                    item,
                    resolve(item.column),
                    bind,
                    reference=exp.column(item.column.column),
                )
                for item in selection_filters
            ]
            query = query.where(exp.and_(*selected))
        if plan.having:
            conditions_having = []
            for item in plan.having:
                expression = measure_expressions[item.field].copy()
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
                if name in measure_expressions or name in growth_names:
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
        operands = [(m, op, metric) for m, parts in effective for op, metric in parts]
        for measure, operand, metric in operands:
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
            if operand.aggregate in {
                Aggregate.SUM,
                Aggregate.AVG,
                Aggregate.MIN,
                Aggregate.MAX,
            }:
                assumptions.append(
                    Assumption(
                        text=(
                            f"{measure.output_name} = "
                            f"{operand.aggregate.value.upper()} of "
                            f"{operand.column.id if operand.column else base.name}; "
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
        for measure, _parts in effective:
            if measure.ratio is not None:
                assumptions.append(
                    Assumption(
                        text=(
                            f"{measure.output_name} divides two aggregates over the "
                            "same rows; a zero denominator yields NULL."
                        ),
                        source=AssumptionSource.DEFAULT,
                        definition_ref="plan.measures.ratio",
                    )
                )
            if measure.share_of_total:
                assumptions.append(
                    Assumption(
                        text=(
                            f"{measure.output_name} is the share of the total over all "
                            + (
                                "groups within the same period (同期 = each period's "
                                "own total); without a per-period word the whole "
                                "window is one period."
                                if time_bucket is not None
                                else "groups over the same time window and filters "
                                "(同期 = the same window as the group values)."
                            )
                        ),
                        source=AssumptionSource.DEFAULT,
                        definition_ref="plan.measures.share_of_total",
                    )
                )
        for item in plan.growth:
            assumptions.append(
                Assumption(
                    text=(
                        f"{item.measure}_growth compares each period with the previous "
                        "period of the same group; the first period has no previous "
                        "value and is NULL."
                    ),
                    source=AssumptionSource.DEFAULT,
                    definition_ref="plan.growth",
                )
            )
        metrics_used = [metric for _, _, metric in operands if metric is not None]
        if metrics_used and len(metrics_used) == len(operands):
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
            measures=tuple(_measure_text(m, parts) for m, parts in effective)
            + tuple(f"{name} = period-over-period change" for name in growth_names),
            dimensions=tuple(d.id for d in plan.dimensions),
            filters=tuple(filter_texts),
            having=tuple(having_texts),
            time_window=tuple(time_texts),
        )
        semantic_refs = sorted(
            {
                *(op.column.id for _, op, _ in operands if op.column),
                *(d.id for d in plan.dimensions),
                *(f.column.id for f in plan.filters),
                *(f.column.id for _, f in all_metric_filters),
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
            applied_segments=tuple(
                dict.fromkeys(
                    [segment.id for segment, _, _ in operand_segment_filters]
                    + [segment.id for segment, _ in segment_filters]
                )
            ),
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

    def _derive_base_table(self, plan: QueryPlan, assumptions: list[Assumption]) -> str:
        """The base is the table the measures aggregate; a parent of it never is.

        Candidates are the tables of the operand columns and the base tables of
        the metrics. With several candidates the one that reaches all the others
        through foreign keys (the child) is the base. Otherwise the plan cannot
        say what it counts.
        """

        candidates: set[str] = set()
        for measure in plan.measures:
            ops = (
                [measure.ratio.numerator, measure.ratio.denominator]
                if measure.ratio is not None
                else [measure]
            )
            for op in ops:
                if op.metric is not None:
                    metric = self._overlay.metric(op.metric) if self._overlay else None
                    if metric is None:
                        raise PlanError("unknown_metric", op.metric)
                    candidates.add(metric.base_table)
                elif op.column is not None:
                    candidates.add(op.column.table)
        if len(candidates) == 1:
            [base] = candidates
        else:
            reaching = [
                t
                for t in candidates
                if all(t == o or _reaches(self._schema, t, o) for o in candidates)
            ]
            if len(reaching) != 1:
                raise PlanError(
                    "base_table_undetermined", ", ".join(sorted(candidates))
                )
            [base] = reaching
        assumptions.append(
            Assumption(
                text=f"The base table {base} was derived from the measure columns.",
                source=AssumptionSource.DEFAULT,
                definition_ref="plan.base_table",
            )
        )
        return base

    @staticmethod
    def _aggregate(measure: Operand, resolve) -> exp.Expression:
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
    def _condition(
        item: Filter,
        column: SchemaColumn,
        bind,
        reference: exp.Expression | None = None,
    ) -> exp.Expression:
        if reference is None:
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


def _reaches(schema: SchemaModel, start: str, target: str, hops: int = 3) -> bool:
    frontier, seen = {start}, {start}
    for _ in range(hops):
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


def _operand_text(op: Operand, metric: ReviewedMetric | None) -> str:
    if metric is not None:
        column = metric.column.id if metric.column else "*"
        return f"{metric.aggregate.value}({column}) [{metric.id}]"
    column = op.column.id if op.column else "*"
    return f"{op.aggregate.value}({column})"  # type: ignore[union-attr]


def _measure_text(measure: Measure, parts) -> str:
    if measure.ratio is not None:
        body = f"{_operand_text(*parts[0])} / {_operand_text(*parts[1])}"
    else:
        body = _operand_text(*parts[0])
    if measure.share_of_total:
        body = f"share of total of {body}"
    return f"{measure.output_name} = {body}"


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
    def measure_words(m: Measure) -> str:
        def op_words(o: Operand) -> str:
            if o.metric:
                return f"metric {o.metric}"
            return f"{o.aggregate.value}({o.column.id if o.column else '*'})"  # type: ignore[union-attr]

        words = (
            f"{op_words(m.ratio.numerator)} / {op_words(m.ratio.denominator)}"
            if m.ratio is not None
            else op_words(m)
        )
        return f"share of total of {words}" if m.share_of_total else words

    parts = [
        ", ".join(measure_words(m) for m in plan.measures)
        + f" over {plan.base_table or "the measures' table"}"
    ]
    if plan.growth:
        parts.append(
            "growth of "
            + ", ".join(g.measure for g in plan.growth)
            + " versus the previous period"
        )
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
