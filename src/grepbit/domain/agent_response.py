"""Agent-facing response contract for one single-shot ask (spec Section 8)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from grepbit.domain.assumptions import Assumption
from grepbit.domain.grounding import Clarification
from grepbit.domain.models import DomainModel
from grepbit.domain.structured_query import StructuredQuery

ResponseStatus = Literal[
    "answered", "clarify", "semantic_gap", "unsupported", "unsafe", "failed"
]
Verification = Literal[
    "verified",
    "partially_verified",
    "unverified_semantics",
    "inconclusive",
    "unverified",
    "blocked",
]


class InterpretationView(DomainModel):
    text: str = Field(min_length=1)
    structured_query: StructuredQuery


class ResultView(DomainModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int = Field(ge=0)
    truncated: bool


class ValidationView(DomainModel):
    validator: str
    status: str


class UsageView(DomainModel):
    model_calls: int = Field(ge=0)
    queries: int = Field(ge=0)
    wall_clock_seconds: float = Field(ge=0)


class AgentResponse(DomainModel):
    """The response contract for upstream agents (spec Section 8)."""

    run_id: str = Field(min_length=1)
    status: ResponseStatus
    grounding_path: str | None = None
    interpretation: InterpretationView | None = None
    assumptions: list[Assumption] = Field(default_factory=list)
    clarification: Clarification | None = None
    suggestions: list[str] = Field(default_factory=list)
    result: ResultView | None = None
    sql: str | None = None
    verification: Verification | None = None
    validations: list[ValidationView] = Field(default_factory=list)
    usage: UsageView
    evidence_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
