"""Bounded research-only predicate checker. Never imported by production.

Checks qualifier polarity and population/operand placement, NOT whether an
aggregate, time scope or arbitrary plan answers a natural-language question.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grepbit.application.text import phrase_in
from grepbit.domain.grounding import normalize_question
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import QueryPlan

Verdict = Literal["pass", "fail", "unknown", "not_applicable"]


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept: str
    polarity: Literal["include", "exclude", "unknown"]
    role: Literal["population", "numerator", "unknown"]
    span: str = Field(min_length=1)


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["required", "not_requested", "ambiguous"]
    requirements: list[Requirement]

    @model_validator(mode="after")
    def consistent(self):
        if bool(self.requirements) != (self.intent == "required"):
            raise ValueError("intent_requirement_mismatch")
        ids = [r.concept for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_concept")
        return self


class Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Verdict


def validate_intent(payload, question, concepts):
    result = Intent.model_validate(payload)
    for requirement in result.requirements:
        if requirement.concept not in concepts:
            raise ValueError("unknown_concept")
        if requirement.span not in question:
            raise ValueError("span_not_in_question")
    return result


def lexical_intent(question, pack, concepts):
    """The baseline has no polarity/role knowledge; never supply gold labels."""
    normalized = normalize_question(question)
    requirements = []
    for concept in pack.concepts:
        if concept.id in concepts and any(
            phrase_in(normalized, normalize_question(w)) for w in concept.words
        ):
            requirements.append(
                Requirement(
                    concept=concept.id,
                    polarity="unknown",
                    role="unknown",
                    span=question,
                )
            )
    return Intent(
        intent="required" if requirements else "not_requested",
        requirements=requirements,
    )


def _predicate_signature(filters):
    return {(f.column.id, f.op.value, tuple(f.values)) for f in filters}


def check_bindings(
    intent: Intent, plan: QueryPlan, concepts: dict, overlay: SemanticOverlay | None
):
    """Return (verdict, bounded reason); pass is only a predicate claim.

    No-request is not_applicable, never proof that a plan is correct. Unknown
    shapes/definitions/conflicting predicates do not silently become passes.
    """
    if intent.intent == "ambiguous":
        return "unknown", "ambiguous_intent"
    if intent.intent == "not_requested":
        return "not_applicable", "no_requested_qualifier"
    if overlay and overlay.segments:
        return "unknown", "segments_outside_pilot"
    if (
        plan.time
        or plan.without
        or plan.latest
        or plan.growth
        or plan.having
        or plan.order
        or plan.limit
    ):
        return "unknown", "shape_outside_pilot"
    if len(plan.measures) != 1:
        return "unknown", "multiple_measures_outside_pilot"

    def expand(operand):
        filters = list(operand.filters)
        if operand.metric:
            metric = overlay.metric(operand.metric) if overlay else None
            if metric is None or metric.review_state.value != "verified":
                return None
            if metric.base_table != plan.base_table:
                return None
            filters += metric.filters
        return _predicate_signature(filters)

    measure = plan.measures[0]
    base = _predicate_signature(plan.filters)
    outcomes = []
    for requirement in intent.requirements:
        definition = concepts.get(requirement.concept, {})
        binding = definition.get("binding")
        if not binding:
            outcomes.append(("unknown", "binding_unavailable"))
            continue
        if requirement.role == "unknown" or requirement.polarity == "unknown":
            outcomes.append(("unknown", "requirement_incomplete"))
            continue
        column, op = binding["column"], binding["op"]
        if column.split(".")[0] != plan.base_table or op not in {"is_null", "not_null"}:
            outcomes.append(("unknown", "binding_outside_pilot"))
            continue
        if requirement.polarity == "exclude":
            op = "not_null" if op == "is_null" else "is_null"
        expected = (column, op, ())
        if (
            requirement.role == "population"
            and not measure.ratio
            and not measure.share_of_total
        ):
            filters = expand(measure)
            numerator = None if filters is None else base | filters
            denominator = set()
        elif (
            requirement.role == "numerator"
            and measure.ratio
            and not measure.share_of_total
        ):
            left, right = (
                expand(measure.ratio.numerator),
                expand(measure.ratio.denominator),
            )
            numerator = None if left is None else base | left
            denominator = None if right is None else base | right
        elif (
            requirement.role == "numerator"
            and measure.share_of_total
            and not measure.ratio
            and not plan.dimensions
        ):
            filters = expand(measure)
            numerator = None if filters is None else base | filters
            # Metric definition filters belong to the whole as well, not just
            # the part. This is distinct from the operand's explicit filters.
            metric_filters = (
                filters - _predicate_signature(measure.filters)
                if filters is not None
                else None
            )
            if measure.metric and filters is not None:
                metric_filters = _predicate_signature(
                    overlay.metric(measure.metric).filters
                )
            denominator = None if metric_filters is None else base | metric_filters
        else:
            outcomes.append(("unknown", "operand_shape_outside_pilot"))
            continue
        if numerator is None or denominator is None:
            outcomes.append(("unknown", "metric_unavailable"))
            continue
        all_filters = numerator | denominator
        if any(
            c != column or operation not in {"is_null", "not_null"} or values
            for c, operation, values in all_filters
        ):
            outcomes.append(("unknown", "additional_predicate_outside_pilot"))
        elif any(
            len({f[1] for f in group if f[0] == column}) > 1
            for group in (numerator, denominator)
        ):
            outcomes.append(("unknown", "conflicting_predicates"))
        elif expected not in numerator or denominator:
            outcomes.append(("fail", "predicate_or_operand_mismatch"))
        elif plan.dimensions:
            outcomes.append(("unknown", "grouping_outside_pilot"))
        else:
            outcomes.append(("pass", "predicate_binding_only"))
    return next(
        (r for r in outcomes if r[0] == "fail"),
        next(
            (r for r in outcomes if r[0] == "unknown"),
            ("pass", "predicate_binding_only"),
        ),
    )
