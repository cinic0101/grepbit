"""Ports the ask orchestration depends on; adapters implement them."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import PlanProposal, PreviousTurn
from grepbit.domain.schema_model import SchemaModel


class PlannerPort(Protocol):
    """One model call: a question and the value-free schema in, a proposal out."""

    last_repairs: list[str]

    def propose(
        self,
        question: str,
        model: SchemaModel,
        *,
        as_of: str,
        overlay: SemanticOverlay | None = None,
        previous: PreviousTurn | None = None,
        question_values: list[dict[str, str]] | None = None,
    ) -> PlanProposal: ...


class LiteralLike(Protocol):
    """A filter literal to check: its column and the value from the question."""

    table: str
    column: str
    value: str
    is_enum: bool


class LiteralCheckPort(Protocol):
    """Which of the given literals match no row of their column."""

    def __call__(self, checks: Sequence[LiteralLike]) -> list[LiteralLike]: ...


class SqlPolicyPort(Protocol):
    def assert_safe_select_statement(self, sql: str) -> str: ...


# Label a planner adapter prefixes on a shape repair that re-anchored a relative
# window ("offset 0 length L" read as offset -L); the ask core states it as an
# assumption when it sees the label.
RELATIVE_WINDOW_REPAIR = "relative window"
# a month, day or year written as a filter literal on a date column, read as
# the time window it can only mean
DATE_LITERAL_REPAIR = "date literal"
