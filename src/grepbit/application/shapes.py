"""Deterministic gate: refuse question shapes the algebra cannot express yet."""

from __future__ import annotations

from grepbit.application.text import phrase_in
from grepbit.domain.grounding import normalize_question
from grepbit.domain.language_pack import ShapePack, UnsupportedShape


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
