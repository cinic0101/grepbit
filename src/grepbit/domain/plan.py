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


class Measure(DomainModel):
    """Either a raw aggregate over a column or a reference to a reviewed metric."""

    aggregate: Aggregate | None = None
    column: ColumnRef | None = None
    metric: str | None = Field(default=None, pattern=_IDENTIFIER)
    alias: str | None = Field(default=None, pattern=_IDENTIFIER)

    @model_validator(mode="after")
    def metric_or_aggregate(self) -> Measure:
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
    def output_name(self) -> str:
        if self.alias:
            return self.alias
        if self.metric is not None:
            return self.metric
        if self.column is None:
            return "row_count"
        assert self.aggregate is not None
        return f"{self.aggregate.value}_{self.column.column}"


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

    column: ColumnRef
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


class QueryPlan(DomainModel):
    base_table: str = Field(pattern=_IDENTIFIER)
    measures: list[Measure] = Field(min_length=1, max_length=4)
    dimensions: list[ColumnRef] = Field(default_factory=list, max_length=3)
    filters: list[Filter] = Field(default_factory=list, max_length=6)
    time: TimeSpec | None = None
    order: list[OrderSpec] = Field(default_factory=list, max_length=2)
    limit: int | None = Field(default=None, ge=1, le=MAX_PLAN_LIMIT)

    @model_validator(mode="after")
    def names_are_unique(self) -> QueryPlan:
        outputs = [measure.output_name for measure in self.measures]
        outputs += [dimension.column for dimension in self.dimensions]
        if self.time is not None and self.time.grain is not None:
            outputs.append("period_start")
        if len(outputs) != len(set(outputs)):
            raise ValueError("plan_output_name_duplicate")
        for item in self.order:
            if item.field not in outputs:
                raise ValueError("plan_order_field_unknown")
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

    def as_dict(self) -> dict[str, object]:
        return {
            "base_table": self.base_table,
            "tables": list(self.tables),
            "joins": list(self.joins),
            "measures": list(self.measures),
            "dimensions": list(self.dimensions),
            "filters": list(self.filters),
            "time_window": list(self.time_window),
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
