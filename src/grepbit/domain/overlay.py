"""Semantic overlay: reviewed knowledge layered over an introspected schema.

Everything here is data a reviewer signs, never code: metrics as plan fragments
(one aggregate plus the filters that define it), concepts known to be absent
from the datasource, the names people use for tables, columns and stored
values, the default time column of a table, and segments (named row subsets
the server may exclude by default). The tier-0 planner still chooses; the
overlay tells the compiler which choices are reviewed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import Aggregate, ColumnRef, Filter, FilterOp

_IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_$]*$"


class ReviewState(StrEnum):
    VERIFIED = "verified"
    CANDIDATE = "candidate"


class ReviewedMetric(DomainModel):
    id: str = Field(pattern=_IDENTIFIER)
    names: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    base_table: str = Field(pattern=_IDENTIFIER)
    aggregate: Aggregate
    column: ColumnRef | None = None
    filters: list[Filter] = Field(default_factory=list)
    time_column: ColumnRef | None = None
    review_state: ReviewState = ReviewState.VERIFIED

    @model_validator(mode="after")
    def count_star_only_without_column(self) -> ReviewedMetric:
        if self.column is None and self.aggregate is not Aggregate.COUNT:
            raise ValueError("overlay_metric_requires_column")
        return self


class AbsentConcept(DomainModel):
    """A concept reviewers confirmed the datasource cannot express.

    ``names`` match as phrases; each list in ``all_of`` matches when every word
    in it occurs anywhere in the question (訂單 and 狀態 in either order), for
    phrasings that split the concept across the sentence.
    """

    names: list[str] = Field(min_length=1)
    note: str = Field(min_length=1)
    all_of: list[list[str]] = Field(default_factory=list)


class ColumnAlias(DomainModel):
    column: ColumnRef
    names: list[str] = Field(min_length=1)


class TableAlias(DomainModel):
    """Business names of a table (訂單 -> pos_sale), shown to the planner."""

    table: str = Field(pattern=_IDENTIFIER)
    names: list[str] = Field(min_length=1)


class ValueName(DomainModel):
    value: str = Field(min_length=1)
    names: list[str] = Field(min_length=1)


class ValueAlias(DomainModel):
    """Reviewed stored values of a column and the names people use for them.

    The PII-safe substitute for sampling: a reviewer lists the values that may
    be shown to the planner, which then uses the stored spelling as the literal.
    """

    column: ColumnRef
    values: list[ValueName] = Field(min_length=1)


class TimeDefault(DomainModel):
    """The time column questions about a table usually mean."""

    table: str = Field(pattern=_IDENTIFIER)
    column: ColumnRef


_SEGMENT_OPS = {FilterOp.IS_NULL, FilterOp.NOT_NULL, FilterOp.EQ, FilterOp.NE}


class Segment(DomainModel):
    """A named row subset of a table, defined by one invertible filter.

    With ``default_exclude`` the server removes the subset from every plan
    over that table (or a table that reaches it through foreign keys) unless
    the question names the segment or the plan already filters on its column;
    the exclusion is stated as a reviewed assumption.
    """

    id: str = Field(pattern=_IDENTIFIER)
    names: list[str] = Field(min_length=1)
    table: str = Field(pattern=_IDENTIFIER)
    filter: Filter
    default_exclude: bool = False
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def filter_is_invertible_and_on_the_table(self) -> Segment:
        if self.filter.op not in _SEGMENT_OPS:
            raise ValueError("overlay_segment_filter_not_invertible")
        if self.filter.column.table != self.table:
            raise ValueError("overlay_segment_filter_table_mismatch")
        return self

    def inverse(self) -> Filter:
        opposite = {
            FilterOp.IS_NULL: FilterOp.NOT_NULL,
            FilterOp.NOT_NULL: FilterOp.IS_NULL,
            FilterOp.EQ: FilterOp.NE,
            FilterOp.NE: FilterOp.EQ,
        }[self.filter.op]
        return self.filter.model_copy(update={"op": opposite})


class Sensitivity(StrEnum):
    PUBLIC = "public"
    PERSONAL = "personal"


class ColumnPolicy(DomainModel):
    """One reviewed fact about a column and three switches derived from it.

    ``sensitivity`` sets the defaults: public columns may be sampled for the
    planner (subject to the cardinality limit), grounded (candidates looked up
    and shown) and are visible; personal columns are visible but never sampled
    nor grounded. Each switch can be overridden per column. Being in the
    overlay is the review: proposals live in a separate file the runtime
    never loads.
    """

    column: ColumnRef
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    sample: bool | None = None
    ground: bool | None = None
    visible: bool | None = None

    def switches(self) -> tuple[bool, bool, bool]:
        public = self.sensitivity is Sensitivity.PUBLIC
        return (
            public if self.sample is None else self.sample,
            public if self.ground is None else self.ground,
            True if self.visible is None else self.visible,
        )


class TablePolicy(DomainModel):
    """A table hidden from the planner is not offered and cannot be referenced."""

    table: str = Field(pattern=_IDENTIFIER)
    visible: bool = True


class SemanticOverlay(DomainModel):
    datasource_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    metrics: list[ReviewedMetric] = Field(default_factory=list)
    absent_concepts: list[AbsentConcept] = Field(default_factory=list)
    column_aliases: list[ColumnAlias] = Field(default_factory=list)
    table_aliases: list[TableAlias] = Field(default_factory=list)
    value_aliases: list[ValueAlias] = Field(default_factory=list)
    time_defaults: list[TimeDefault] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    column_policies: list[ColumnPolicy] = Field(default_factory=list)
    table_policies: list[TablePolicy] = Field(default_factory=list)

    @model_validator(mode="after")
    def metric_ids_unique(self) -> SemanticOverlay:
        ids = [metric.id for metric in self.metrics]
        if len(ids) != len(set(ids)):
            raise ValueError("overlay_metric_id_duplicate")
        segment_ids = [segment.id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("overlay_segment_id_duplicate")
        tables = [default.table for default in self.time_defaults]
        if len(tables) != len(set(tables)):
            raise ValueError("overlay_time_default_duplicate")
        policy_columns = [policy.column.id for policy in self.column_policies]
        if len(policy_columns) != len(set(policy_columns)):
            raise ValueError("overlay_column_policy_duplicate")
        policy_tables = [policy.table for policy in self.table_policies]
        if len(policy_tables) != len(set(policy_tables)):
            raise ValueError("overlay_table_policy_duplicate")
        return self

    def column_switches(self, column_id: str) -> tuple[bool, bool, bool]:
        """(sample, ground, visible) for a column; unlisted columns are public."""

        policy = next(
            (p for p in self.column_policies if p.column.id == column_id), None
        )
        return (True, True, True) if policy is None else policy.switches()

    def table_visible(self, table: str) -> bool:
        policy = next((p for p in self.table_policies if p.table == table), None)
        return True if policy is None else policy.visible

    def visible_column(self, table: str, column: str) -> bool:
        return (
            self.table_visible(table) and self.column_switches(f"{table}.{column}")[2]
        )

    def groundable_columns(self) -> list[ColumnRef]:
        """Columns whose ground switch is on; only listed columns qualify.

        Grounding reads and may show stored values, so it is opt-in per column:
        an unlisted column is visible and samplable but never grounded.
        """

        return [
            p.column
            for p in self.column_policies
            if p.switches()[1] and self.visible_column(p.column.table, p.column.column)
        ]

    def table_names(self, table: str) -> list[str]:
        return [
            n
            for alias in self.table_aliases
            if alias.table == table
            for n in alias.names
        ]

    def values_for(self, column_id: str) -> list[ValueName]:
        return [
            value
            for alias in self.value_aliases
            if alias.column.id == column_id
            for value in alias.values
        ]

    def time_default(self, table: str) -> ColumnRef | None:
        return next((d.column for d in self.time_defaults if d.table == table), None)

    def metric(self, metric_id: str) -> ReviewedMetric | None:
        return next((m for m in self.metrics if m.id == metric_id), None)

    def aliases_for(self, column_id: str) -> list[str]:
        return [
            name
            for alias in self.column_aliases
            if alias.column.id == column_id
            for name in alias.names
        ]
