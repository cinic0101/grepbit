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


class ShapePack(DomainModel):
    revision: str = Field(min_length=1)
    shapes: list[UnsupportedShape] = Field(default_factory=list)
