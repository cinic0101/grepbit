"""A reference evaluation of a QueryPlan in plain Python, written from the
contract (`docs/knowledge/tier0-contract.md`), not from the compiler.

It joins parents along foreign keys, applies filters with SQL's three-valued
logic, resolves the window and the grain in the business time zone, groups,
aggregates, derives ratios, shares and growth, applies having, order and
limit, and evaluates the two row shapes (the latest row per group, entities
with no activity). The differential (`evals/differential.py`) runs the
compiled SQL on PostgreSQL and this on the same tables; any disagreement is a
defect in one of the two, and the compiler is the one that serves users.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from grepbit.domain.overlay import Segment, SemanticOverlay
from grepbit.domain.plan import Filter, FilterOp, Operand, QueryPlan
from grepbit.domain.schema_model import SchemaModel
from grepbit.domain.structured_query import (
    LatestScope,
    RangeScope,
    resolve_time_scope,
    widened_for_previous_period,
)

Row = dict[str, Any]  # "table.column" -> value
UNIT_MONTHS = {"month": 1, "quarter": 3, "year": 12}


class Unsupported(Exception):
    """The evaluator does not cover this plan; the differential skips it."""


# ----------------------------------------------------------------- joins
def _parent_paths(schema: SchemaModel, base: str, hops: int = 3) -> dict[str, list]:
    """table -> the chain of foreign keys from base to it (unique path or absent)."""

    paths: dict[str, list] = {base: []}
    frontier = [base]
    for _ in range(hops):
        step = []
        for table in frontier:
            for fk in schema.foreign_keys:
                if fk.table != table or fk.referenced_table in paths:
                    continue
                paths[fk.referenced_table] = [*paths[table], fk]
                step.append(fk.referenced_table)
        frontier = step
    return paths


def _joined_rows(
    schema: SchemaModel, tables: dict[str, list[dict]], base: str
) -> list[Row]:
    """Base rows with every reachable parent's columns attached (LEFT JOIN)."""

    paths = _parent_paths(schema, base)
    indexes: dict[str, dict[Any, dict]] = {}
    for table_name in paths:
        if table_name == base:
            continue
        table = schema.table(table_name)
        key = table.primary_key[0] if table and table.primary_key else None
        if key is None:
            continue
        indexes[table_name] = {r[key]: r for r in tables.get(table_name, [])}
    rows: list[Row] = []
    for raw in tables.get(base, []):
        row: Row = {f"{base}.{k}": v for k, v in raw.items()}
        for table_name, chain in paths.items():
            if table_name == base:
                continue
            current = raw
            current_table = base
            for fk in chain:
                if current is None:
                    break
                value = current.get(fk.column) if current_table == fk.table else None
                current = indexes.get(fk.referenced_table, {}).get(value)
                current_table = fk.referenced_table
            table = schema.table(table_name)
            for column in table.columns if table else []:
                row[f"{table_name}.{column.name}"] = (
                    None if current is None else current.get(column.name)
                )
        rows.append(row)
    return rows


# ----------------------------------------------------------------- filters
def _truth(item: Filter, row: Row, kinds: dict[str, str]) -> bool | None:
    """SQL three-valued truth of one filter on one row."""

    value = row.get(item.column.id)
    if item.op is FilterOp.IS_NULL:
        return value is None
    if item.op is FilterOp.NOT_NULL:
        return value is not None
    if value is None:
        return None
    kind = kinds.get(item.column.id, "text")
    literals = [_coerce(v, kind) for v in item.values]
    if kind in ("timestamp", "date"):
        value = _as_datetime(value)
        literals = [_as_datetime(v) for v in literals]
    if item.op is FilterOp.IN:
        return value in literals
    [literal] = literals
    if kind == "text" and not isinstance(value, str):
        value = str(value)
    return {
        FilterOp.EQ: value == literal,
        FilterOp.NE: value != literal,
        FilterOp.GT: value > literal,
        FilterOp.GTE: value >= literal,
        FilterOp.LT: value < literal,
        FilterOp.LTE: value <= literal,
    }[item.op]


def _coerce(value: Any, kind: str) -> Any:
    if (
        kind == "numeric"
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        return Decimal(str(value))
    if kind in ("timestamp", "date") and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
    if isinstance(value, date):
        return datetime.combine(value, time(), tzinfo=ZoneInfo("UTC"))
    return value


def _all_true(filters: list[Filter], row: Row, kinds: dict[str, str]) -> bool:
    return all(_truth(f, row, kinds) is True for f in filters)


def _inverse(item: Filter) -> Filter:
    inverse = {
        FilterOp.EQ: FilterOp.NE,
        FilterOp.NE: FilterOp.EQ,
        FilterOp.GT: FilterOp.LTE,
        FilterOp.LTE: FilterOp.GT,
        FilterOp.GTE: FilterOp.LT,
        FilterOp.LT: FilterOp.GTE,
        FilterOp.IS_NULL: FilterOp.NOT_NULL,
        FilterOp.NOT_NULL: FilterOp.IS_NULL,
    }
    if item.op is FilterOp.IN:
        raise Unsupported("segment with IN filter")
    return item.model_copy(update={"op": inverse[item.op]})


# ----------------------------------------------------------------- time
def _zone(schema: SchemaModel) -> ZoneInfo:
    return ZoneInfo(schema.business_timezone)


def _local(value: Any, zone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(zone) if value.tzinfo else value.replace(tzinfo=zone)
    if isinstance(value, date):
        return datetime.combine(value, time(), tzinfo=zone)
    return None


def _bucket_start(moment: datetime, grain: str) -> datetime:
    zone = moment.tzinfo
    if grain == "day":
        return datetime.combine(moment.date(), time(), tzinfo=zone)
    if grain == "week":
        monday = moment.date() - timedelta(days=moment.weekday())
        return datetime.combine(monday, time(), tzinfo=zone)
    if grain == "month":
        return datetime(moment.year, moment.month, 1, tzinfo=zone)
    if grain == "quarter":
        return datetime(moment.year, 3 * ((moment.month - 1) // 3) + 1, 1, tzinfo=zone)
    return datetime(moment.year, 1, 1, tzinfo=zone)


def _add_units(start: datetime, unit: str, n: int) -> datetime:
    if unit == "day":
        return start + timedelta(days=n)
    if unit == "week":
        return start + timedelta(weeks=n)
    months = UNIT_MONTHS[unit] * n
    year, month = start.year, start.month - 1 + months
    year += month // 12
    month = month % 12 + 1
    return start.replace(year=year, month=month)


def _period_output(start: datetime, column_kind: str) -> Any:
    """What SQL returns for the bucket: a date for date columns, else a naive
    timestamp."""

    if start is None:
        return None
    return start.date() if column_kind == "date" else start.replace(tzinfo=None)


# ----------------------------------------------------------------- aggregates
def _aggregate(kind: str, values: list[Any]) -> Any:
    present = [v for v in values if v is not None]
    if kind == "count":
        return len(values)
    if kind == "count_distinct":
        return len(set(present))
    if not present:
        return None
    if kind == "sum":
        return (
            sum(present, Decimal(0))
            if all(isinstance(v, (Decimal, int)) for v in present)
            else sum(present)
        )
    if kind == "avg":
        total = sum((Decimal(str(v)) for v in present), Decimal(0))
        return total / Decimal(len(present))
    if kind == "min":
        return min(present)
    return max(present)


def _divide(numerator: Any, denominator: Any) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


# ----------------------------------------------------------------- the evaluation
def evaluate(
    plan: QueryPlan,
    schema: SchemaModel,
    overlay: SemanticOverlay | None,
    as_of: datetime,
    tables: dict[str, list[dict]],
    exclude_segments: list[Segment] = (),
    named_segments: list[Segment] = (),
) -> list[dict[str, Any]]:
    """Rows as dicts keyed by output name (dimension column, period_start, measure)."""

    base = plan.base_table
    if base is None:
        raise Unsupported("derived base table")
    zone = _zone(schema)
    kinds = {
        f"{t.name}.{c.name}": c.kind.value for t in schema.tables for c in t.columns
    }
    rows = _joined_rows(schema, tables, base)
    reachable = set(_parent_paths(schema, base))

    # ---- operands: metric expansion
    def resolve(operand: Operand) -> tuple[str, str | None, list[Filter], list[Filter]]:
        """(aggregate, column id, defining filters of the metric, the operand's own)."""
        if operand.metric is not None:
            metric = overlay.metric(operand.metric) if overlay else None
            if metric is None:
                raise Unsupported("unknown metric")
            column = metric.column.id if metric.column else None
            return (
                metric.aggregate.value,
                column,
                list(metric.filters),
                list(operand.filters),
            )
        column = operand.column.id if operand.column else None
        return operand.aggregate.value, column, [], list(operand.filters)

    resolved = []  # per measure: list of operand tuples
    for measure in plan.measures:
        parts = (
            [measure.ratio.numerator, measure.ratio.denominator]
            if measure.ratio
            else [measure]
        )
        resolved.append([resolve(op) for op in parts])
    defining_sets = [
        tuple(sorted(f.model_dump_json() for f in defining))
        for parts in resolved
        for (_, _, defining, _) in parts
    ]
    shared_defining: list[Filter] = []
    if defining_sets and len(set(defining_sets)) == 1 and defining_sets[0]:
        # one reviewed definition for every operand: its filters act on the rows
        # (the contract: a single metric keeps its filters in WHERE)
        shared_defining = list(resolved[0][0][2])
        resolved = [
            [(agg, col, [], own) for (agg, col, _, own) in parts] for parts in resolved
        ]
    metric_time = None
    for parts in resolved:
        for op in [plan.measures[resolved.index(parts)]] if False else []:
            pass
    for measure in plan.measures:
        for op in (
            [measure.ratio.numerator, measure.ratio.denominator]
            if measure.ratio
            else [measure]
        ):
            if op.metric and overlay:
                m = overlay.metric(op.metric)
                if m is not None and m.time_column is not None:
                    metric_time = m.time_column.id

    # ---- default segments (contract: query-wide unless an operand references
    # the column, then operand-level on the other operands; skipped when the
    # plan filters the column or the table is unreachable)
    plan_filter_columns = {f.column.id for f in plan.filters}
    operand_columns = [
        {f.column.id for f in own} | {f.column.id for f in defining}
        for parts in resolved
        for (_, _, defining, own) in parts
    ]
    row_segment_filters: list[Filter] = []
    operand_segment_filters: list[tuple[Filter, set[int]]] = []
    for segment in exclude_segments:
        column_id = segment.filter.column.id
        if column_id in plan_filter_columns or segment.table not in reachable:
            continue
        referencing = {i for i, cols in enumerate(operand_columns) if column_id in cols}
        inverse = _inverse(segment.filter)
        if referencing:
            others = set(range(len(operand_columns))) - referencing
            operand_segment_filters.append((inverse, others))
        else:
            row_segment_filters.append(inverse)

    # ---- time column and window
    time_spec = plan.time
    time_column = None
    if time_spec is not None:
        time_column = time_spec.column.id if time_spec.column else None
    if time_spec is not None and metric_time is not None:
        time_column = metric_time  # the reviewed definition prescribes it
    if time_column is None and time_spec is not None:
        default = overlay.time_default(base) if overlay else None
        time_column = default.id if default is not None else None
        if time_column is None:
            raise Unsupported("no time column")
    grain = time_spec.grain.value if time_spec and time_spec.grain else None
    scope = time_spec.scope if time_spec else None
    if (
        plan.growth
        and scope is not None
        and grain is not None
        and not isinstance(scope, LatestScope)
    ):
        widened = widened_for_previous_period(scope, time_spec.grain)
        if widened is not None:
            scope = widened

    share_selection = [
        f
        for f in plan.filters
        if any(m.share_of_total for m in plan.measures)
        and f.column.id in {d.id for d in plan.dimensions}
    ]
    row_filters = [f for f in plan.filters if f not in share_selection]

    def base_rows_pass(row: Row) -> bool:
        return (
            _all_true(row_filters, row, kinds)
            and _all_true(shared_defining, row, kinds)
            and _all_true(row_segment_filters, row, kinds)
        )

    candidate = [r for r in rows if base_rows_pass(r)]

    periods: list[tuple[datetime, datetime]] = []
    if scope is not None:
        if isinstance(scope, LatestScope):
            moments = [_local(r.get(time_column), zone) for r in candidate]
            moments = [m for m in moments if m is not None]
            if moments:
                start = _bucket_start(max(moments), scope.unit.value)
                periods = [(start, _add_units(start, scope.unit.value, 1))]
            else:
                periods = [
                    (
                        datetime(1900, 1, 1, tzinfo=zone),
                        datetime(1900, 1, 1, tzinfo=zone),
                    )
                ]
        else:
            resolved_periods = resolve_time_scope(
                scope, as_of=as_of, business_timezone=schema.business_timezone
            )
            periods = [(p.start, p.end_exclusive) for p in resolved_periods]
            if isinstance(scope, RangeScope) and periods:
                anchor = as_of.astimezone(zone)
                day_end = datetime.combine(
                    anchor.date() + timedelta(days=1), time(), tzinfo=zone
                )
                s, e = periods[-1]
                if e > day_end and s < day_end:
                    periods[-1] = (s, day_end)
    if time_column is not None and periods:

        def in_window(row: Row) -> bool:
            moment = _local(row.get(time_column), zone)
            return moment is not None and any(s <= moment < e for s, e in periods)

        candidate = [r for r in candidate if in_window(r)]
    if time_column is not None and grain is not None:
        # a period breakdown holds no row without a time value (contract: the
        # compiler adds `time IS NOT NULL` with a grain)
        candidate = [r for r in candidate if r.get(time_column) is not None]

    # ---- the two row shapes
    if plan.without is not None:
        return _evaluate_without(
            plan,
            schema,
            overlay,
            as_of,
            tables,
            exclude_segments,
            candidate,
            kinds,
            zone,
        )
    if plan.latest is not None:
        return _evaluate_latest(plan, schema, candidate, kinds, zone)

    # ---- grouping
    dims = [d.id for d in plan.dimensions]
    time_kind = kinds.get(time_column, "timestamp") if time_column else "timestamp"

    def group_key(row: Row) -> tuple:
        key: list[Any] = []
        if grain is not None:
            moment = _local(row.get(time_column), zone)
            key.append(None if moment is None else _bucket_start(moment, grain))
        key.extend(row.get(d) for d in dims)
        return tuple(key)

    groups: dict[tuple, list[Row]] = defaultdict(list)
    if grain is None and not dims:
        groups[()] = list(candidate)
    else:
        for row in candidate:
            # a NULL time value truncates to NULL and forms its own bucket (only
            # reachable without a window, which would have dropped the row)
            groups[group_key(row)].append(row)

    # ---- aggregates per group
    def operand_value(
        parts_index: int, position: int, rows_in: list[Row], own: bool = True
    ) -> Any:
        agg, column, defining, own_filters = resolved[parts_index][position]
        pos_flat = sum(len(p) for p in resolved[:parts_index]) + position
        keep = []
        for row in rows_in:
            if not _all_true(defining, row, kinds):
                continue
            if own and not _all_true(own_filters, row, kinds):
                continue
            if any(
                pos_flat in others and _truth(seg, row, kinds) is not True
                for seg, others in operand_segment_filters
            ):
                continue
            keep.append(row)
        values = [row.get(column) for row in keep] if column else [1] * len(keep)
        return _aggregate(agg, values)

    ungrouped = grain is None and not dims
    table_rows: list[dict[str, Any]] = []
    raw_measure_values: dict[str, dict[tuple, Any]] = defaultdict(dict)
    for key, rows_in in groups.items():
        out: dict[str, Any] = {}
        if grain is not None:
            out["period_start"] = _period_output(key[0], time_kind)
        for d, value in zip(dims, key[1:] if grain is not None else key):
            out[d.split(".")[1]] = value
        for i, measure in enumerate(plan.measures):
            if measure.ratio is not None:
                num = operand_value(i, 0, rows_in)
                den = operand_value(i, 1, rows_in)
                value: Any = _divide(num, den)
            else:
                value = operand_value(i, 0, rows_in)
            raw_measure_values[measure.output_name][key] = value
            out[measure.output_name] = value
        out["__key__"] = key
        table_rows.append(out)

    # ---- shares: the window total per period, or the part over the whole
    for measure in plan.measures:
        if not measure.share_of_total:
            continue
        name = measure.output_name
        if ungrouped:
            [(key, rows_in)] = groups.items()
            agg, column, defining, own_filters = resolved[plan.measures.index(measure)][
                0
            ]
            if measure.ratio is not None or not own_filters:
                raise Unsupported("share without groups and without an operand filter")
            part = raw_measure_values[name][key]
            whole = operand_value(plan.measures.index(measure), 0, rows_in, own=False)
            table_rows[0][name] = _divide(part, whole)
            continue
        totals: dict[Any, Any] = defaultdict(lambda: None)
        for out in table_rows:
            period = out["__key__"][0] if grain is not None else None
            v = raw_measure_values[name][out["__key__"]]
            if v is not None:
                totals[period] = v if totals[period] is None else totals[period] + v
        for out in table_rows:
            period = out["__key__"][0] if grain is not None else None
            out[name] = _divide(
                raw_measure_values[name][out["__key__"]], totals[period]
            )

    # ---- after-share selection
    if share_selection:
        table_rows = [
            out
            for out in table_rows
            if all(
                _truth(f, {f.column.id: out.get(f.column.column)}, kinds) is True
                for f in share_selection
            )
        ]

    # ---- growth per group over periods
    growth_names = []
    if plan.growth:
        by_group: dict[tuple, list[dict]] = defaultdict(list)
        for out in table_rows:
            by_group[out["__key__"][1:]].append(out)
        for item in plan.growth:
            gname = f"{item.measure}_growth"
            growth_names.append(gname)
            for series in by_group.values():
                series.sort(
                    key=lambda o: (
                        o["__key__"][0] is not None,
                        o["__key__"][0] or datetime(1, 1, 1, tzinfo=zone),
                    )
                )
                previous = None
                for out in series:
                    current = out[item.measure]
                    out[gname] = (
                        None
                        if previous is None or previous == 0 or current is None
                        else (float(current) - float(previous)) / float(previous)
                    )
                    previous = current

    # ---- having
    for item in plan.having:

        def passes(out: dict) -> bool:
            v = out.get(item.field)
            if v is None:
                return False
            t = Decimal(str(item.value))
            v = Decimal(str(v))
            return {
                "gt": v > t,
                "gte": v >= t,
                "lt": v < t,
                "lte": v <= t,
                "eq": v == t,
                "ne": v != t,
            }[item.op]

        table_rows = [out for out in table_rows if passes(out)]

    for out in table_rows:
        del out["__key__"]
    return table_rows


def _evaluate_without(
    plan, schema, overlay, as_of, tables, exclude_segments, base_rows, kinds, zone
):
    without = plan.without
    child = without.table
    child_rows = _joined_rows(schema, tables, child)
    child_reach = set(_parent_paths(schema, child))
    if plan.base_table not in child_reach:
        raise Unsupported("without table does not reach the base")
    filters = list(without.filters)
    for segment in exclude_segments:
        if segment.table in child_reach and segment.filter.column.id not in {
            f.column.id for f in filters
        }:
            filters.append(_inverse(segment.filter))
    child_rows = [r for r in child_rows if _all_true(filters, r, kinds)]
    if without.time is not None and without.time.scope is not None:
        column = (
            without.time.column.id
            if without.time.column
            else (
                overlay.time_default(child).id
                if overlay and overlay.time_default(child)
                else None
            )
        )
        if column is None:
            raise Unsupported("child window without a column")
        periods = [
            (p.start, p.end_exclusive)
            for p in resolve_time_scope(
                without.time.scope,
                as_of=as_of,
                business_timezone=schema.business_timezone,
            )
        ]
        child_rows = [
            r
            for r in child_rows
            if (m := _local(r.get(column), zone)) is not None
            and any(s <= m < e for s, e in periods)
        ]
    base_table = schema.table(plan.base_table)
    pk = f"{plan.base_table}.{base_table.primary_key[0]}"
    active = {r.get(pk) for r in child_rows}
    kept = [r for r in base_rows if r.get(pk) not in active]
    dims = [d.id for d in plan.dimensions]
    groups: dict[tuple, int] = defaultdict(int)
    for r in kept:
        groups[tuple(r.get(d) for d in dims)] += 1
    if not dims:
        groups[()] = len(kept)
    out_rows = []
    for key, n in groups.items():
        out = {d.split(".")[1]: v for d, v in zip(dims, key)}
        for measure in plan.measures:
            out[measure.output_name] = n
        out_rows.append(out)
    return out_rows


def _evaluate_latest(plan, schema, candidate, kinds, zone):
    latest = plan.latest
    dims = [d.id for d in plan.dimensions]
    table = schema.table(plan.base_table)
    pk = f"{plan.base_table}.{table.primary_key[0]}"
    groups: dict[tuple, list[Row]] = defaultdict(list)
    for r in candidate:
        groups[tuple(r.get(d) for d in dims)].append(r)
    out_rows = []
    for key, rows_in in groups.items():

        def sort_key(r: Row):
            parts = []
            for o in latest.order_by:
                v = r.get(o.column.id)
                v = _local(v, zone) if isinstance(v, (datetime, date)) else v
                parts.append((v is None, v if o.direction == "asc" else _negate(v)))
            parts.append(_negate(r.get(pk)))
            return parts

        try:
            best = sorted(rows_in, key=sort_key)[0]
        except TypeError:
            raise Unsupported("unorderable latest values") from None
        out = {d.split(".")[1]: v for d, v in zip(dims, key)}
        for ref in latest.take:
            out[ref.column] = best.get(ref.id)
        out_rows.append(out)
    return out_rows


class _Neg:
    """Reverse ordering wrapper for descending sort keys."""

    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        return self.v > other.v

    def __eq__(self, other):
        return self.v == other.v


def _negate(v):
    return _Neg(v)
