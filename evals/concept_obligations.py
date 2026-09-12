"""Research v2: supplied obligations -> bounded predicate/grouping verdict.

Not natural-language verification, a SQL evaluator, or a production gate.
Frozen v1 lives in concept_check.py and is deliberately unchanged.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import QueryPlan

REVISION = "concept-obligations-v2"


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    span: str = Field(min_length=1)


class Requirement(EvidenceSpan):
    concept: str
    polarity: Literal["include", "exclude", "unrestricted"]
    role: Literal["population", "numerator", "denominator"]


class ForbiddenGrouping(EvidenceSpan):
    concept: str


class Unresolved(EvidenceSpan):
    aspect: Literal["measure_basis", "denominator_population", "qualifier"]


class Obligations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[Requirement]
    forbidden_groupings: list[ForbiddenGrouping]
    unresolved: list[Unresolved]

    @model_validator(mode="after")
    def unique_scopes(self):
        for keys in (
            [(r.concept, r.role) for r in self.requirements],
            [r.concept for r in self.forbidden_groupings],
            [r.aspect for r in self.unresolved],
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate_obligation")
        return self


def validate_obligations(payload, question, concepts):
    result = Obligations.model_validate(payload)
    bound = [*result.requirements, *result.forbidden_groupings]
    for entry in bound:
        if entry.concept not in concepts:
            raise ValueError("unknown_concept")
    for entry in [*bound, *result.unresolved]:
        if entry.span not in question:
            raise ValueError("span_not_in_question")
    return result


def core(payload):
    """Ignore evidence-span spelling/order, never merge distinct obligations."""
    return {
        key: sorted(
            [{k: v for k, v in item.items() if k != "span"} for item in payload[key]],
            key=lambda item: tuple(sorted(item.items())),
        )
        for key in ("requirements", "forbidden_groupings", "unresolved")
    }


class OutsideScope(Exception):
    pass


def check_obligations(
    obligations: Obligations,
    plan: QueryPlan,
    concepts: dict,
    overlay: SemanticOverlay | None,
) -> tuple[str, str]:
    """Pass only certifies the obligations GIVEN, not their NL completeness."""
    if obligations.unresolved:
        return "unknown", "unresolved_obligation"
    claims = [*obligations.requirements, *obligations.forbidden_groupings]
    if not claims:
        return "not_applicable", "no_extracted_obligations"
    if any(not concepts.get(r.concept, {}).get("binding") for r in claims):
        return "unknown", "binding_unavailable"
    if (
        (overlay and overlay.segments)
        or plan.time
        or plan.without
        or plan.latest
        or plan.growth
        or plan.having
        or plan.order
        or plan.limit
        or len(plan.measures) != 1
        or plan.measures[0].share_of_total
        or (plan.measures[0].ratio and plan.measures[0].filters)
    ):
        return "unknown", "shape_outside_v2"
    bindings = {
        key: item["binding"] for key, item in concepts.items() if item.get("binding")
    }
    for claim in claims:
        binding = bindings[claim.concept]
        if binding["column"].split(".")[0] != plan.base_table or binding["op"] not in {
            "is_null",
            "not_null",
        }:
            return "unknown", "binding_outside_v2"
    if any(d.table != plan.base_table for d in plan.dimensions):
        return "unknown", "join_outside_v2"
    known_columns = {b["column"] for b in bindings.values()}

    def predicates(filters):
        result = set()
        for f in filters:
            if (
                f.column.table != plan.base_table
                or f.column.id not in known_columns
                or f.op.value not in {"is_null", "not_null"}
                or f.values
            ):
                raise OutsideScope("predicate_outside_v2")
            result.add((f.column.id, f.op.value))
        return result

    def operand_support(operand):
        filters = [*plan.filters, *operand.filters]
        aggregate, column = operand.aggregate, operand.column
        if operand.metric:
            metric = overlay.metric(operand.metric) if overlay else None
            if (
                metric is None
                or metric.review_state.value != "verified"
                or metric.base_table != plan.base_table
            ):
                raise OutsideScope("metric_unavailable")
            filters += metric.filters
            aggregate, column = metric.aggregate, metric.column
        if column and column.table != plan.base_table:
            raise OutsideScope("join_outside_v2")
        result = predicates(filters)
        if column and column.id in known_columns:
            if aggregate.value not in {"count", "count_distinct"}:
                raise OutsideScope("implicit_aggregate_outside_v2")
            result.add((column.id, "not_null"))
        if any(
            (column_id, "is_null") in result and (column_id, "not_null") in result
            for column_id, _ in result
        ):
            raise OutsideScope("conflicting_predicates")
        return result

    measure = plan.measures[0]
    try:
        scopes = (
            {
                "numerator": operand_support(measure.ratio.numerator),
                "denominator": operand_support(measure.ratio.denominator),
            }
            if measure.ratio
            else {"population": operand_support(measure)}
        )
    except OutsideScope as error:
        return "unknown", str(error)
    if any(r.role not in scopes for r in obligations.requirements):
        return "unknown", "operand_scope_outside_v2"
    dimensions = {d.id for d in plan.dimensions}
    if any(
        bindings[r.concept]["column"] in dimensions
        for r in obligations.forbidden_groupings
    ):
        return "fail", "forbidden_grouping"
    for requirement in obligations.requirements:
        binding = bindings[requirement.concept]
        column, operation = binding["column"], binding["op"]
        actual = {op for col, op in scopes[requirement.role] if col == column}
        if requirement.polarity == "unrestricted":
            expected = set()
        else:
            if requirement.polarity == "exclude":
                operation = "is_null" if operation == "not_null" else "not_null"
            expected = {operation}
        if actual != expected:
            return "fail", "predicate_or_scope_mismatch"
    return "pass", "supplied_obligations_only"
