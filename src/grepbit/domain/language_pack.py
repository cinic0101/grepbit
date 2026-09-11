"""Cross-datasource language packs: data the deterministic gates match against."""

from __future__ import annotations

from pydantic import Field

from grepbit.domain.models import DomainModel


class UnsupportedShape(DomainModel):
    """A question shape the algebra cannot compile yet (a ratio, a growth rate).

    ``names`` are the words that signal the shape in any language; the
    ``clarification`` tells the caller what the service can answer instead.
    """

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    names: list[str] = Field(min_length=1)
    clarification: str = Field(min_length=1)


class ConceptWords(DomainModel):
    """A business concept the question may name (退貨, 會員, 折扣) and the column
    name fragments that would show the plan took it into account. A plan that
    answers a question naming the concept while referencing none of them
    answered a broader question; the check turns it into a clarify."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    words: list[str] = Field(min_length=1)
    column_keywords: list[str] = Field(min_length=1)


class ShapePack(DomainModel):
    revision: str = Field(min_length=1)
    shapes: list[UnsupportedShape] = Field(default_factory=list)
    # Words that ask for one value per period (每天, monthly); a plan that
    # answers such a question with a single current-period window misread it.
    period_words: list[str] = Field(default_factory=list)
    # Words that switch a planner rule pack on (entities with no activity,
    # the latest row per entity, the latest period with data); a rule the
    # question does not need stays out of the prompt.
    rule_triggers: dict[str, list[str]] = Field(default_factory=dict)
    # Business concepts whose mention must leave a trace in the plan
    concepts: list[ConceptWords] = Field(default_factory=list)
    period_clarification: str = (
        "The question asks for one value per period, but the plan covered only "
        "the current period."
    )
