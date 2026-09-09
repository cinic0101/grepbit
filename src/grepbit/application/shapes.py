"""Deterministic gate: refuse question shapes the algebra cannot express yet."""

from __future__ import annotations

from grepbit.application.text import phrase_in
from grepbit.domain.grounding import normalize_question
from grepbit.domain.language_pack import ShapePack, UnsupportedShape
from grepbit.domain.plan import QueryPlan
from grepbit.domain.structured_query import RelativeScope


def match_unsupported_shape(
    question: str, pack: ShapePack
) -> tuple[UnsupportedShape, str] | None:
    """The first shape whose name occurs in the question, and the name that hit.

    Runs before any model call and costs nothing. A hit is a typed
    ``unsupported`` refusal with the pack's clarification; the words are data
    (``resources/unsupported_shapes.json``), not code, so a datasource or a
    language adds names without touching the gate.
    """

    normalized = normalize_question(question)
    for shape in pack.shapes:
        for name in shape.names:
            if phrase_in(normalized, normalize_question(name)):
                return shape, name
    return None


def single_period_misread(
    question: str, plan: QueryPlan, pack: ShapePack
) -> str | None:
    """The per-period word the plan ignored, if it answered "every X" as "this X".

    Fires only when the question carries a per-period word, the plan sets a
    grain, and its window is the single current unit of that same grain
    (relative, offset 0, length 1): "每天的銷售總額" compiled for today alone.
    The caller turns a hit into ``clarify``; the plan is never rewritten.
    """

    time = plan.time
    if time is None or time.grain is None or time.scope is None:
        return None
    scope = time.scope
    if not (
        isinstance(scope, RelativeScope)
        and scope.offset == 0
        and scope.length == 1
        and scope.unit.value == time.grain.value
    ):
        return None
    normalized = normalize_question(question)
    for word in pack.period_words:
        if phrase_in(normalized, normalize_question(word)):
            return word
    return None
