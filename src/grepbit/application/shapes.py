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

    if plan.latest is not None or any(m.share_of_total for m in plan.measures):
        # a share asked for one group keeps its dimension: the after-share
        # selection divides by every group (holdout 2 q21 answered 1.232 when
        # the dimension was dropped and the whole-share rule took over)
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


def unmapped_concepts(
    question: str,
    plan: QueryPlan,
    pack: ShapePack,
    overlay,
    named_segment_ids: set[str],
) -> list[tuple[str, str]]:
    """Concepts the question names that the plan leaves no trace of.

    A plan answers 2025年12月退貨金額 with the month's total sales when the
    return concept is dropped (two fixture runs on 2026-09-11). For every
    concept of the pack whose words occur in the question, the plan must
    reference a column whose name carries one of the concept's keywords (in
    a filter, an operand, a dimension, the absence test, the taken columns),
    or a reviewed metric whose id or names carry it, or a default-excluded
    segment the question named. Returns ``(concept id, word)`` pairs.
    """

    if not pack.concepts:
        return []
    normalized = normalize_question(question)
    hits: list[tuple] = []
    for concept in pack.concepts:
        word = next(
            (w for w in concept.words if phrase_in(normalized, normalize_question(w))),
            None,
        )
        if word is not None:
            hits.append((concept, word))
    if not hits:
        return []
    columns: set[str] = {f.column.column.lower() for f in plan.filters}
    metric_ids: set[str] = set()
    for measure in plan.measures:
        operands = (
            [measure.ratio.numerator, measure.ratio.denominator]
            if measure.ratio is not None
            else [measure]
        )
        for operand in operands:
            if operand.column is not None:
                columns.add(operand.column.column.lower())
            if operand.metric is not None:
                metric_ids.add(operand.metric.lower())
            columns |= {f.column.column.lower() for f in operand.filters}
    columns |= {d.column.lower() for d in plan.dimensions}
    if plan.without is not None:
        columns.add(plan.without.table.lower())
        columns |= {f.column.column.lower() for f in plan.without.filters}
    if plan.latest is not None:
        columns |= {ref.column.lower() for ref in plan.latest.take}
    metric_words: set[str] = set()
    segment_words: set[str] = set()
    if overlay is not None:
        for metric in overlay.metrics:
            if metric.id.lower() in metric_ids:
                metric_words |= {normalize_question(n) for n in metric.names}
                columns |= {f.column.column.lower() for f in metric.filters}
        for segment in overlay.segments:
            if segment.id in named_segment_ids:
                segment_words |= {normalize_question(n) for n in segment.names}
    unmapped: list[tuple[str, str]] = []
    for concept, word in hits:
        keys = [k.lower() for k in concept.column_keywords]
        words = {normalize_question(w) for w in concept.words}
        mapped = (
            any(k in c for c in columns for k in keys)
            or any(k in m for m in metric_ids for k in keys)
            or any(w in mw or mw in w for w in words for mw in metric_words)
            or any(w in sw or sw in w for w in words for sw in segment_words)
        )
        if not mapped:
            unmapped.append((concept.id, word))
    return unmapped


def unrequested_growth(question: str, plan: QueryPlan, pack: ShapePack) -> list[str]:
    """Growth measures to drop when nothing in the question asked for a rate.

    上個月和前一個月的營業額比較 wants the two months' values; the model adds a
    growth column on alternate runs (ft_compare_last_two_months flapped all
    day). The prompt's rule 5 says a question that merely compares periods
    wants the per-period values; this makes it deterministic: growth stays
    only when the question carries one of the pack's growth words
    (``rule_triggers.growth``).
    """

    if not plan.growth:
        return []
    words = pack.rule_triggers.get("growth", [])
    if not words:
        return []
    normalized = normalize_question(question)
    if any(phrase_in(normalized, normalize_question(w)) for w in words):
        return []
    return [item.measure for item in plan.growth]


def drop_growth(plan: QueryPlan) -> QueryPlan:
    return plan.model_copy(update={"growth": []})
