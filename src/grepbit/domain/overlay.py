"""Semantic overlay: reviewed knowledge layered over an introspected schema.

Everything here is data a reviewer signs, never code: metrics as plan fragments
(one aggregate plus the filters that define it), concepts known to be absent
from the datasource, and the names people use for columns. The tier-0 planner
still chooses; the overlay tells the compiler which choices are reviewed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import Aggregate, ColumnRef, Filter

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
    """A concept reviewers confirmed the datasource cannot express."""

    names: list[str] = Field(min_length=1)
    note: str = Field(min_length=1)


class ColumnAlias(DomainModel):
    column: ColumnRef
    names: list[str] = Field(min_length=1)


class SemanticOverlay(DomainModel):
    datasource_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    metrics: list[ReviewedMetric] = Field(default_factory=list)
    absent_concepts: list[AbsentConcept] = Field(default_factory=list)
    column_aliases: list[ColumnAlias] = Field(default_factory=list)

    @model_validator(mode="after")
    def metric_ids_unique(self) -> SemanticOverlay:
        ids = [metric.id for metric in self.metrics]
        if len(ids) != len(set(ids)):
            raise ValueError("overlay_metric_id_duplicate")
        return self

    def metric(self, metric_id: str) -> ReviewedMetric | None:
        return next((m for m in self.metrics if m.id == metric_id), None)

    def aliases_for(self, column_id: str) -> list[str]:
        return [
            name
            for alias in self.column_aliases
            if alias.column.id == column_id
            for name in alias.names
        ]
