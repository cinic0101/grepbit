"""Tier-0 query plan: a closed relational algebra the model fills with ids."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from grepbit.domain.assumptions import Assumption
from grepbit.domain.models import CompiledQuery, DomainModel
from grepbit.domain.structured_query import (
    ResolvedPeriod,
    TimeGrain,
    TimeScope,
)

_IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_$]*$"
MAX_PLAN_LIMIT = 200


class Aggregate(StrEnum):
    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class FilterOp(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"


FilterValue = str | int | float | bool


class ColumnRef(DomainModel):
    table: str = Field(pattern=_IDENTIFIER)
    column: str = Field(pattern=_IDENTIFIER)

    @property
    def id(self) -> str:
        return f"{self.table}.{self.column}"


class Operand(DomainModel):
    """One aggregate: a raw aggregate over a column, or a reviewed metric."""

    aggregate: Aggregate | None = None
    column: ColumnRef | None = None
    metric: str | None = Field(default=None, pattern=_IDENTIFIER)
    # the operand's own row restriction (會員交易 among all transactions),
    # compiled as FILTER (WHERE ...) on this aggregate alone
    filters: list[Filter] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def metric_or_aggregate(self) -> Operand:
        if self.metric is not None:
            if self.aggregate is not None or self.column is not None:
                raise ValueError("plan_measure_metric_excludes_aggregate")
            return self
        if self.aggregate is None:
            raise ValueError("plan_measure_requires_aggregate_or_metric")
        if self.column is None and self.aggregate is not Aggregate.COUNT:
            raise ValueError("plan_measure_requires_column")
        return self

    @property
    def default_name(self) -> str:
        if self.metric is not None:
            return self.metric
        if self.column is None:
            return "row_count"
        assert self.aggregate is not None
        return f"{self.aggregate.value}_{self.column.column}"


class Ratio(DomainModel):
    """One aggregate divided by another over the same rows (客單價, 退貨率)."""

    numerator: Operand
    denominator: Operand


class Measure(Operand):
    """An operand, a ratio of two operands, or either as a share of the total.

    ``share_of_total`` divides the measure by the same measure over every
    group (within each period when the plan has a grain); ``ratio`` divides two
    operands. Both are derived arithmetic the server computes in the same
    statement; the model never computes numbers.
    """

    alias: str | None = Field(default=None, pattern=_IDENTIFIER)
    ratio: Ratio | None = None
    share_of_total: bool = False

    @model_validator(mode="after")
    def metric_or_aggregate(self) -> Measure:  # type: ignore[override]
        if self.ratio is not None:
            if self.aggregate is not None or self.column is not None or self.metric:
                raise ValueError("plan_measure_ratio_excludes_aggregate")
            return self
        return super().metric_or_aggregate()  # type: ignore[return-value]

    @property
    def output_name(self) -> str:
        if self.alias:
            return self.alias
        if self.ratio is not None:
            base = (
                f"{self.ratio.numerator.default_name}_per_"
                f"{self.ratio.denominator.default_name}"
            )
        else:
            base = self.default_name
        return f"{base}_share" if self.share_of_total else base


class Filter(DomainModel):
    column: ColumnRef
    op: FilterOp
    values: list[FilterValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def arity_matches_operator(self) -> Filter:
        if self.op in {FilterOp.IS_NULL, FilterOp.NOT_NULL}:
            if self.values:
                raise ValueError("plan_filter_null_op_rejects_values")
        elif self.op is FilterOp.IN:
            if not self.values:
                raise ValueError("plan_filter_in_requires_values")
        elif len(self.values) != 1:
            raise ValueError("plan_filter_requires_one_value")
        return self


class TimeSpec(DomainModel):
    """A time column with a window, a grain, or both.

    ``scope`` may be omitted only together with a ``grain``: "every day" over
    all the data buckets by day without a window. A window without a grain is
    a plain filter; a grain without a window is a plain breakdown.
    """

    column: ColumnRef | None = None
    scope: TimeScope | None = None
    grain: TimeGrain | None = None

    @model_validator(mode="after")
    def window_or_grain(self) -> TimeSpec:
        if self.scope is None and self.grain is None:
            raise ValueError("plan_time_requires_scope_or_grain")
        return self


class OrderSpec(DomainModel):
    field: str = Field(pattern=_IDENTIFIER)
    direction: Literal["asc", "desc"] = "desc"


class GrowthSpec(DomainModel):
    """Period-over-period change of a measure: (m - previous m) / previous m.

    Needs a time grain; the previous period is the previous bucket for the
    same group (LAG over period_start, partitioned by the dimensions).
    """

    measure: str = Field(pattern=_IDENTIFIER)


class HavingSpec(DomainModel):
    """A condition on a measure of each group (stores whose total exceeds N).

    ``field`` is a measure output name; the compiler places the comparison on
    the aggregate expression itself (SQL HAVING), so the threshold from the
    question is never dropped and never mistaken for a row filter.
    """

    field: str = Field(pattern=_IDENTIFIER)
    op: Literal["gt", "gte", "lt", "lte", "eq", "ne"]
    value: int | float


class Absence(DomainModel):
    """Keep only base rows with no matching rows in a child table: the anti-join.

    ``table`` is a table that references the base through a foreign key
    (directly, or through intermediate tables); ``filters`` and ``time``
    describe the rows that must be absent (non-return sales in a window).
    ``time`` is a window only, never a grain. Compiled as ``NOT EXISTS``.
    """

    table: str = Field(pattern=_IDENTIFIER)
    filters: list[Filter] = Field(default_factory=list, max_length=4)
    time: TimeSpec | None = None

    @model_validator(mode="after")
    def window_only(self) -> Absence:
        if self.time is not None and self.time.grain is not None:
            raise ValueError("plan_without_takes_a_window_not_a_grain")
        return self


class OrderedColumn(DomainModel):
    column: ColumnRef
    direction: Literal["asc", "desc"] = "desc"


class LatestSpec(DomainModel):
    """The single most recent base row per group (每位店員最新一筆交易).

    ``order_by`` ranks the rows inside each group (the time column first, then
    the tie-breaker the question names; the compiler adds the primary key
    when only one column is given); ``take`` lists the columns returned from
    the chosen row. Filters, window and segments apply before the choice.
    """

    order_by: list[OrderedColumn] = Field(min_length=1, max_length=3)
    take: list[ColumnRef] = Field(min_length=1, max_length=4)


class QueryPlan(DomainModel):
    """One governed query: an aggregate, or the latest row per group.
    ``base_table`` may be omitted when the measure columns or metrics
    determine it; the compiler derives it then."""

    base_table: str | None = Field(default=None, pattern=_IDENTIFIER)
    measures: list[Measure] = Field(default_factory=list, max_length=4)
    dimensions: list[ColumnRef] = Field(default_factory=list, max_length=3)
    filters: list[Filter] = Field(default_factory=list, max_length=6)
    time: TimeSpec | None = None
    order: list[OrderSpec] = Field(default_factory=list, max_length=2)
    having: list[HavingSpec] = Field(default_factory=list, max_length=2)
    growth: list[GrowthSpec] = Field(default_factory=list, max_length=2)
    limit: int | None = Field(default=None, ge=1, le=MAX_PLAN_LIMIT)
    # entities with no activity: base rows without matching rows in a child table
    without: Absence | None = None
    # the latest row per group instead of aggregates
    latest: LatestSpec | None = None

    @model_validator(mode="after")
    def names_are_unique(self) -> QueryPlan:
        if not self.measures and self.latest is None:
            raise ValueError("plan_measures_required")
        if self.latest is not None:
            if self.measures or self.having or self.growth:
                raise ValueError("plan_latest_excludes_aggregates")
            if self.base_table is None:
                raise ValueError("plan_latest_requires_base_table")
            if self.time is not None and self.time.grain is not None:
                raise ValueError("plan_latest_takes_a_window_not_a_grain")
        outputs = [measure.output_name for measure in self.measures]
        outputs += [dimension.column for dimension in self.dimensions]
        if self.latest is not None:
            outputs += [ref.column for ref in self.latest.take]
        if self.time is not None and self.time.grain is not None:
            outputs.append("period_start")
        if len(outputs) != len(set(outputs)):
            raise ValueError("plan_output_name_duplicate")
        for item in self.order:
            if item.field not in outputs:
                raise ValueError("plan_order_field_unknown")
        measure_names = {measure.output_name for measure in self.measures}
        for item in self.having:
            if item.field not in measure_names:
                raise ValueError("plan_having_field_not_a_measure")
            measure = next(m for m in self.measures if m.output_name == item.field)
            if measure.share_of_total or measure.ratio is not None:
                raise ValueError("plan_having_on_derived_measure")
        for item in self.growth:
            if item.measure not in measure_names:
                raise ValueError("plan_growth_field_not_a_measure")
            if self.time is None or self.time.grain is None:
                raise ValueError("plan_growth_requires_grain")
        if self.base_table is None and not any(
            m.metric or m.column or m.ratio for m in self.measures
        ):
            raise ValueError("plan_base_table_required")
        if self.without is not None and self.base_table is None:
            raise ValueError("plan_without_requires_base_table")
        return self


class PreviousTurn(DomainModel):
    """The last answered question and its plan, offered as follow-up context."""

    question: str = Field(min_length=1)
    plan: QueryPlan


class PlanProposal(DomainModel):
    """Untrusted model output: a plan over offered schema ids, or a decline."""

    decision: Literal["plan", "none"]
    plan: QueryPlan | None = None
    reason: Literal["semantic_gap", "unsupported", "ambiguous"] | None = None
    clarification: str | None = None

    @model_validator(mode="after")
    def decision_payload_is_coherent(self) -> PlanProposal:
        if self.decision == "plan":
            if self.plan is None or self.reason is not None:
                raise ValueError("plan_proposal_requires_plan")
        elif self.plan is not None or self.reason is None:
            raise ValueError("plan_proposal_none_requires_reason")
        return self


_PLAN_ERROR_CODES = frozenset(
    {
        "unknown_table",
        "unknown_column",
        "grain_conflict",
        "aggregate_kind_mismatch",
        "filter_kind_mismatch",
        "time_column_kind_mismatch",
        "time_scope_requires_grain",
        "ambiguous_join_path",
        "unknown_metric",
        "metric_base_table_mismatch",
        "metric_conflict",
        # a past relative window whose end lies beyond the current unit (for
        # example unit week, offset -1, length 7: the model meant days)
        "relative_window_reaches_future",
        # base_table omitted and the measures name several unrelated tables
        "base_table_undetermined",
        # time.column omitted and the base table has no default time column
        "time_column_required",
        # growth asked on a period-to-date window: the previous bucket would be a
        # whole period against a partial one
        "growth_to_date_unsupported",
        # HAVING count = 0 over the base table's own rows: every group has at
        # least one row, so the question is an anti-join the algebra lacks
        "anti_join_required",
        # the compiled SQL broke an invariant of the plan (a filter the plan
        # asked for is missing, a ratio divides an expression by itself, a
        # window without groups): refused rather than served
        "self_check_failed",
        # share_of_total with no groups and no periods: every share would be 1
        # unless the operand carries a filter of its own (the part over the whole)
        "share_requires_groups",
        # without.table does not reference the base table through foreign keys
        "without_table_not_a_child",
        # a without filter names a column outside the child table
        "without_filter_outside_child",
    }
)


class PlanError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        if code not in _PLAN_ERROR_CODES:
            raise ValueError("plan_error_code_invalid")
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Lineage:
    base_table: str
    tables: tuple[str, ...]
    joins: tuple[str, ...]
    measures: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[str, ...]
    time_window: tuple[str, ...]
    having: tuple[str, ...] = ()
    latest: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "base_table": self.base_table,
            "tables": list(self.tables),
            "joins": list(self.joins),
            "measures": list(self.measures),
            "dimensions": list(self.dimensions),
            "filters": list(self.filters),
            "time_window": list(self.time_window),
            "having": list(self.having),
            **({"latest": list(self.latest)} if self.latest else {}),
        }


@dataclass(frozen=True)
class CompiledPlan:
    plan: QueryPlan
    compiled: CompiledQuery
    output_columns: tuple[str, ...]
    lineage: Lineage
    assumptions: tuple[Assumption, ...]
    interpretation: str
    periods: tuple[ResolvedPeriod, ...] = field(default_factory=tuple)
    verification: str = "unverified_semantics"
    applied_segments: tuple[str, ...] = field(default_factory=tuple)
    """Ids of overlay segments whose filter shaped this SQL (WHERE or FILTER)."""


class ConceptMapping(DomainModel):
    """One business concept from the question and the plan element covering it."""

    concept: str = Field(min_length=1)
    mapped_to: str | None = None


class CoverageReport(DomainModel):
    """Untrusted audit of whether a compiled plan expresses every concept asked."""

    concepts: list[ConceptMapping] = Field(default_factory=list)

    @property
    def uncovered(self) -> list[str]:
        return [item.concept for item in self.concepts if not item.mapped_to]

    @property
    def covered(self) -> bool:
        return not self.uncovered
