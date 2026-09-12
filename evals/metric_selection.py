"""Approved bounded metric-selection research contract and deterministic checker.

No natural-language inference, production integration or finite-row equivalence.
"""

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Span(ClosedModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)
    role: Literal[
        "output_action",
        "business_predicate",
        "mention_only",
        "grouping_constraint",
        "unresolved",
    ]
    scope: Literal[
        "output", "output_label", "population", "numerator", "denominator", "grouping"
    ]
    concept: str | None = None

    @model_validator(mode="after")
    def role_scope(self):
        allowed = {
            "output_action": {"output"},
            "mention_only": {"output_label"},
            "grouping_constraint": {"grouping"},
            "business_predicate": {"population", "numerator", "denominator"},
            "unresolved": {"population", "numerator", "denominator"},
        }
        if self.end <= self.start or self.scope not in allowed[self.role]:
            raise ValueError("invalid_span_scope")
        if self.role == "business_predicate" and self.concept is None:
            raise ValueError("predicate_requires_concept")
        if (
            self.role in {"output_action", "mention_only", "grouping_constraint"}
            and self.concept
        ):
            raise ValueError("nonpredicate_cannot_activate_concept")
        return self


class Basis(ClosedModel):
    role: Literal["value", "numerator", "denominator"]
    aggregate: Literal["count", "sum", "count_distinct"]
    entity: str
    column: str | None

    @model_validator(mode="after")
    def column_required(self):
        if self.aggregate != "count" and self.column is None:
            raise ValueError("basis_column_required")
        return self


class Requirement(ClosedModel):
    concept: str
    polarity: Literal["include", "exclude", "unrestricted"]
    role: Literal["population", "numerator", "denominator"]


class Interpretation(ClosedModel):
    """Approved bounded research annotation; never a production certificate."""

    state: Literal["clear", "ambiguous", "missing_definition"]
    populations: dict[
        Literal["population", "numerator", "denominator"],
        Literal["all_rows", "constrained", "unresolved"],
    ]
    basis: list[Basis]
    requirements: list[Requirement]
    grouping: Literal["none", "unspecified"]
    unresolved: list[
        Literal["measure_basis", "denominator_population", "business_binding"]
    ]
    spans: list[Span]
    output_label: str | None

    @model_validator(mode="after")
    def structural_contract(self):
        if (self.state == "clear") != (not self.unresolved):
            raise ValueError("state_requires_matching_uncertainty")
        if self.state == "clear" and not self.basis:
            raise ValueError("clear_requires_measure_basis")
        if (
            self.state == "missing_definition"
            and "business_binding" not in self.unresolved
        ):
            raise ValueError("missing_definition_requires_binding_gap")
        for keys in (
            [b.role for b in self.basis],
            [(r.concept, r.role) for r in self.requirements],
            [(s.start, s.end) for s in self.spans],
            self.unresolved,
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate_annotation")
        roles = {b.role for b in self.basis}
        if roles and roles not in ({"value"}, {"numerator", "denominator"}):
            raise ValueError("incomplete_measure_roles")
        if self.state == "clear":
            scopes = {"population"} if roles == {"value"} else roles
            if any(r.role not in scopes for r in self.requirements):
                raise ValueError("requirement_outside_measure_scope")
            if set(self.populations) != scopes:
                raise ValueError("missing_population_scope")
            for scope, policy in self.populations.items():
                restrictions = [
                    r
                    for r in self.requirements
                    if r.role == scope and r.polarity != "unrestricted"
                ]
                if policy == "unresolved":
                    raise ValueError("clear_with_unknown_population")
                if (policy == "constrained") != bool(restrictions):
                    raise ValueError("population_constraint_mismatch")
        return self


def validate_interpretation(payload, question, schema, concepts):
    """Integrity only: a well-formed interpretation may still be wrong."""
    parsed = Interpretation.model_validate(payload)
    for span in parsed.spans:
        if span.end > len(question) or question[span.start : span.end] != span.text:
            raise ValueError("span_not_in_question")
        if span.concept is not None and span.concept not in concepts:
            raise ValueError("unknown_concept")
    for requirement in parsed.requirements:
        if requirement.concept not in concepts:
            raise ValueError("unknown_concept")
        if parsed.state == "clear" and concepts[requirement.concept] is None:
            raise ValueError("clear_with_missing_binding")
    for basis in parsed.basis:
        table = schema.table(basis.entity)
        if table is None or (
            basis.column
            and basis.column not in {f"{table.name}.{c.name}" for c in table.columns}
        ):
            raise ValueError("unknown_basis_identifier")
    if parsed.output_label is not None and parsed.output_label not in question:
        raise ValueError("label_not_in_question")
    return parsed


def annotation_core(annotation):
    """Semantic fields separate from exact occurrence annotation accuracy."""
    payload = annotation.model_dump(mode="json")
    payload.pop("spans")
    for key in ("basis", "requirements", "unresolved"):
        payload[key] = sorted(payload[key], key=repr)
    return payload


class OutsideFragment(ValueError):
    pass


def _column(schema, reference, base):
    table_name, name = reference.rsplit(".", 1)
    table = schema.table(table_name)
    if table_name != base or table is None or table.column(name) is None:
        raise OutsideFragment("outside_base_table")
    return table.column(name)


def _predicates(filters, schema, base):
    predicates = set()
    for item in filters:
        column = _column(schema, item.column.id, base)
        if item.op not in {"is_null", "not_null"} or item.values:
            raise OutsideFragment("unsupported_predicate")
        if item.op == "not_null" and not column.nullable:
            continue
        predicates.add((item.column.id, item.op.value))
    return predicates


def _operand(operand, plan, overlay, schema):
    base = plan.base_table
    aggregate, column = operand.aggregate, operand.column
    filters = list(plan.filters) + list(operand.filters)
    if operand.metric:
        metric = overlay.metric(operand.metric) if overlay else None
        if metric is None or metric.base_table != base:
            raise OutsideFragment("unknown_metric")
        aggregate, column = metric.aggregate, metric.column
        filters += metric.filters
    if aggregate not in {"count", "sum", "count_distinct"}:
        raise OutsideFragment("unsupported_aggregate")
    predicates = _predicates(filters, schema, base)
    column_id = column.id if column else None
    if column:
        definition = _column(schema, column_id, base)
        if aggregate == "sum" and definition.kind.value != "numeric":
            raise OutsideFragment("unsupported_sum_kind")
        if aggregate in {"count", "count_distinct"}:
            if definition.nullable:
                predicates.add((column_id, "not_null"))
            unique = schema.table(base).primary_key == [column.column]
            if aggregate == "count" or (unique and not definition.nullable):
                aggregate = type(aggregate)("count")
                column_id = None
    return (aggregate.value, base, column_id), predicates


def check_plan(annotation, plan, schema, concepts, overlay):
    """Compare explicit claims, not NL truth. Fail/unknown are never passes."""
    if annotation.state != "clear":
        return {"verdict": "unknown", "reason": "unresolved_interpretation"}
    if any(concepts.get(r.concept) is None for r in annotation.requirements):
        return {"verdict": "unknown", "reason": "missing_binding"}
    if (
        plan.base_table is None
        or schema.table(plan.base_table) is None
        or len(plan.measures) != 1
        or any(
            (plan.time, plan.having, plan.growth, plan.without, plan.latest, plan.order)
        )
        or plan.limit is not None
        or plan.measures[0].share_of_total
        or (overlay and overlay.segments)
    ):
        return {"verdict": "unknown", "reason": "outside_fragment"}
    if plan.dimensions:
        return {
            "verdict": "fail" if annotation.grouping == "none" else "unknown",
            "reason": "grouping",
        }
    measure = plan.measures[0]
    operands = (
        {"numerator": measure.ratio.numerator, "denominator": measure.ratio.denominator}
        if measure.ratio
        else {"value": measure}
    )
    expected_basis = {b.role: b for b in annotation.basis}
    if set(operands) != set(expected_basis):
        return {"verdict": "fail", "reason": "measure_roles"}
    try:
        for role, operand in operands.items():
            actual_basis, actual_predicates = _operand(operand, plan, overlay, schema)
            basis = expected_basis[role]
            scope = "population" if role == "value" else role
            wanted = set()
            for requirement in annotation.requirements:
                if requirement.role != scope or requirement.polarity == "unrestricted":
                    continue
                binding = concepts[requirement.concept]
                if binding["op"] != "not_null":
                    raise OutsideFragment("unsupported_binding")
                op = "not_null" if requirement.polarity == "include" else "is_null"
                if (
                    op == "is_null"
                    or _column(schema, binding["column"], basis.entity).nullable
                ):
                    wanted.add((binding["column"], op))
            expected_column = basis.column
            expected_aggregate = basis.aggregate
            if expected_column and basis.aggregate in {"count", "count_distinct"}:
                definition = _column(schema, expected_column, basis.entity)
                if definition.nullable:
                    wanted.add((expected_column, "not_null"))
                unique = schema.table(basis.entity).primary_key == [
                    expected_column.rsplit(".", 1)[1]
                ]
                if basis.aggregate == "count" or (unique and not definition.nullable):
                    expected_aggregate = "count"
                    expected_column = None
            if actual_basis != (expected_aggregate, basis.entity, expected_column):
                return {"verdict": "fail", "reason": "measure_basis"}
            if actual_predicates != wanted:
                return {"verdict": "fail", "reason": "population"}
    except OutsideFragment:
        return {"verdict": "unknown", "reason": "outside_fragment"}
    if annotation.output_label is not None and measure.alias != annotation.output_label:
        return {"verdict": "fail", "reason": "output_label"}
    return {"verdict": "pass", "reason": "bounded_match"}


def authored_annotation(ruler, case, language):
    """Offline gold only; not an inference-time extractor or payload builder."""
    spans = []
    question = case["questions"][language]
    for locator in case["spans"][language]:
        entry = dict(locator)
        occurrence = entry.pop("occurrence", 0)
        start = -1
        for _ in range(occurrence + 1):
            start = question.index(entry["text"], start + 1)
        spans.append({**entry, "start": start, "end": start + len(entry["text"])})
    return Interpretation.model_validate(
        {
            **deepcopy(ruler["profiles"][case["profile"]]),
            "spans": spans,
            "output_label": case.get("labels", {}).get(language),
        }
    )
