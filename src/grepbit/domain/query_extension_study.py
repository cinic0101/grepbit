"""Experimental contracts; NOT accepted by the production QueryPlan/MCP.

Only the opt-in query-extension study imports this module. No SQL, formulas,
result rows or source-unit assertions are accepted from the planner.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import ColumnRef, Filter, OrderSpec, QueryPlan

IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_$]*$"
Unit = Literal["celsius", "fahrenheit", "minutes", "hours"]


class RowsQuery(DomainModel):
    kind: Literal["rows"]
    base_table: str = Field(pattern=IDENTIFIER)
    columns: list[ColumnRef] = Field(default_factory=list, max_length=32)
    all_columns: bool = False
    filters: list[Filter] = Field(default_factory=list, max_length=6)
    order: list[OrderSpec] = Field(default_factory=list, max_length=2)
    limit: int | None = Field(default=None, ge=1, le=200)

    @model_validator(mode="after")
    def one_projection(self):
        if bool(self.columns) == self.all_columns:
            raise ValueError("choose_explicit_columns_or_all_columns")
        if len({c.id for c in self.columns}) != len(self.columns):
            raise ValueError("duplicate_projection")
        return self


class Conversion(DomainModel):
    field: str
    target_unit: Unit


class AggregateQuery(DomainModel):
    kind: Literal["aggregate"]
    plan: QueryPlan
    conversion: Conversion | None = None

    @model_validator(mode="after")
    def no_nested_rows(self):
        if self.plan.rows is not None:
            raise ValueError("aggregate_query_cannot_contain_rows")
        return self


class Extremum(DomainModel):
    field: str
    direction: Literal["max", "min"]
    ties: Literal["all"] = "all"


class CombinedQuery(DomainModel):
    kind: Literal["combine"]
    entity_table: str = Field(pattern=IDENTIFIER)
    entity_columns: list[ColumnRef] = Field(default_factory=list, max_length=3)
    entity_filters: list[Filter] = Field(default_factory=list, max_length=6)
    components: list[QueryPlan] = Field(min_length=1, max_length=3)
    selection: Extremum | None = None

    @model_validator(mode="after")
    def simple_components(self):
        for plan in self.components:
            if (
                plan.base_table is None
                or plan.dimensions
                or plan.having
                or plan.order
                or plan.limit is not None
                or plan.growth
                or plan.latest
                or plan.rows
                or plan.without
                or (plan.time and plan.time.grain)
                or any(m.ratio or m.share_of_total for m in plan.measures)
            ):
                raise ValueError("combine_requires_simple_unlimited_components")
        names = [m.output_name for p in self.components for m in p.measures]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_component_output")
        if self.selection and self.selection.field not in names:
            raise ValueError("unknown_selection_output")
        return self


StudyQuery = Annotated[
    RowsQuery | AggregateQuery | CombinedQuery, Field(discriminator="kind")
]


class StudyProposal(DomainModel):
    decision: Literal["plan", "none"]
    query: StudyQuery | None = None
    reason: Literal["unsupported", "semantic_gap", "ambiguous"] | None = None
    clarification: str | None = None

    @model_validator(mode="after")
    def decision_matches(self):
        if self.decision == "plan":
            if self.query is None or self.reason is not None:
                raise ValueError("plan_requires_query_without_refusal")
        elif self.query is not None or self.reason is None:
            raise ValueError("refusal_requires_reason_without_query")
        return self


class UnitBinding(DomainModel):
    """Trusted researcher/overlay input, never fields authored by the planner."""

    column: ColumnRef
    unit: Unit
    evidence: str = Field(min_length=1)
