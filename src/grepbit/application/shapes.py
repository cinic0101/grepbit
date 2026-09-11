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


def unrequested_grain(question: str, plan: QueryPlan, pack: ShapePack) -> str | None:
    """The grain to drop when the plan buckets by period but nothing asked for it.

    Fires only for a grain without a window (a plain breakdown, "share within
    each month") when the question carries none of the pack's period words
    (每月, 趨勢, by month). The plain reading of such a question is one value
    per group over the whole window (同期); a compare-periods window, which
    needs a grain, has a scope and is left alone. Returns the grain's name, or
    ``None``.
    """

    time = plan.time
    if time is None or time.grain is None or time.scope is not None:
        return None
    normalized = normalize_question(question)
    for word in pack.period_words:
        if phrase_in(normalized, normalize_question(word)):
            return None
    return time.grain.value


def drop_grain(plan: QueryPlan) -> QueryPlan:
    """The plan without its time bucket; a column-only time spec is removed."""

    assert plan.time is not None
    if plan.time.scope is None:
        return plan.model_copy(update={"time": None})
    return plan.model_copy(
        update={"time": plan.time.model_copy(update={"grain": None})}
    )


def constant_dimensions(plan: QueryPlan) -> list[str]:
    """Dimensions the plan's own filters fix to one value (owner's decision,
    2026-09-11): ``by store_name`` beside ``store_name = X`` would return the
    same value on every row. Returns their ids; latest-row plans are left alone."""

    if plan.latest is not None:
        return []
    fixed = {
        f.column.id for f in plan.filters if f.op.value == "eq" and len(f.values) == 1
    }
    return [d.id for d in plan.dimensions if d.id in fixed]


def drop_dimensions(plan: QueryPlan, ids: list[str]) -> QueryPlan:
    """The plan without those dimensions and without order items naming them."""

    kept = [d for d in plan.dimensions if d.id not in ids]
    dropped_names = {d.column for d in plan.dimensions if d.id in ids}
    order = [o for o in plan.order if o.field not in dropped_names]
    return plan.model_copy(update={"dimensions": kept, "order": order})
