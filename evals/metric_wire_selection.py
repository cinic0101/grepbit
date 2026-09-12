"""Research-only occurrence adapter, diagnostics and typed candidate selection."""

from copy import deepcopy
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    create_model,
    model_validator,
)

from evals.concept_pilot import digest
from evals.metric_selection import (
    Interpretation,
    Span,
    _operand,
    validate_interpretation,
)
from grepbit.domain.plan import PlanProposal, QueryPlan


class OccurrenceSpan(BaseModel):
    """Proposed input shape only; resolution is not implemented here."""

    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1)
    occurrence: int = Field(ge=0)
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
    def existing_role_rules(self):
        # Only reuse existing role rules on a local placeholder span. This
        # neither locates its occurrence nor proves what the text means.
        Span.model_validate(
            {
                **self.model_dump(exclude={"occurrence"}),
                "start": 0,
                "end": len(self.text),
            }
        )
        return self


class Selection(BaseModel):
    """Proposed research selection envelope; never a QueryPlan certificate."""

    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["pick", "clarify", "no_candidate"]
    slots: dict[Literal["value", "numerator", "denominator"], str]
    output_label: str | None
    reason: Literal["ambiguous", "missing_definition", "outside_catalog"] | None

    @model_validator(mode="after")
    def closed_forms(self):
        if self.decision == "pick":
            if set(self.slots) not in ({"value"}, {"numerator", "denominator"}):
                raise ValueError("incomplete_selection")
            if self.reason is not None:
                raise ValueError("pick_with_refusal_reason")
            if any(not identifier for identifier in self.slots.values()):
                raise ValueError("empty_candidate_id")
            if len(self.slots.values()) != len(set(self.slots.values())):
                raise ValueError("identical_ratio_candidate")
        else:
            if self.slots or self.output_label is not None:
                raise ValueError("refusal_with_selection")
            allowed = (
                {"ambiguous", "missing_definition"}
                if self.decision == "clarify"
                else {"outside_catalog"}
            )
            if self.reason not in allowed:
                raise ValueError("wrong_refusal_kind")
        return self


OccurrenceInterpretation = create_model(
    "OccurrenceInterpretation",
    __config__=ConfigDict(extra="forbid", strict=True),
    **{
        key: (
            list[OccurrenceSpan] if key == "spans" else field.annotation,
            deepcopy(field),
        )
        for key, field in Interpretation.model_fields.items()
    },
)


def locate(text, occurrence, question):
    if type(occurrence) is not int or occurrence < 0:
        raise ValueError("invalid_occurrence")
    if not isinstance(text, str) or not text:
        raise ValueError("span_not_in_question")
    positions = [i for i in range(len(question)) if question.startswith(text, i)]
    if not positions:
        raise ValueError("span_not_in_question")
    if occurrence >= len(positions):
        raise ValueError("occurrence_out_of_range")
    start = positions[occurrence]
    return start, start + len(text)


def parse_occurrences(payload, question, schema, concepts):
    wire = OccurrenceInterpretation.model_validate(payload)
    canonical = wire.model_dump()
    canonical["spans"] = []
    for span in wire.spans:
        start, end = locate(span.text, span.occurrence, question)
        canonical["spans"].append(
            {
                **span.model_dump(exclude={"occurrence"}),
                "start": start,
                "end": end,
            }
        )
    return validate_interpretation(canonical, question, schema, concepts)


REASONS = frozenset(
    {
        "invalid_span_scope",
        "predicate_requires_concept",
        "nonpredicate_cannot_activate_concept",
        "basis_column_required",
        "state_requires_matching_uncertainty",
        "clear_requires_measure_basis",
        "missing_definition_requires_binding_gap",
        "duplicate_annotation",
        "incomplete_measure_roles",
        "requirement_outside_measure_scope",
        "missing_population_scope",
        "clear_with_unknown_population",
        "population_constraint_mismatch",
        "span_not_in_question",
        "unknown_concept",
        "clear_with_missing_binding",
        "unknown_basis_identifier",
        "label_not_in_question",
        "invalid_occurrence",
        "occurrence_out_of_range",
        "incomplete_selection",
        "pick_with_refusal_reason",
        "empty_candidate_id",
        "identical_ratio_candidate",
        "refusal_with_selection",
        "wrong_refusal_kind",
        "candidate_not_offered",
        "candidate_cross_table",
        "candidate_label_not_in_question",
    }
)
ERROR_TYPES = frozenset(
    {
        "missing",
        "extra_forbidden",
        "literal_error",
        "int_type",
        "greater_than_equal",
        "string_too_short",
        "dict_type",
        "list_type",
        "string_type",
        "none_required",
    }
)
PATH_FIELDS = frozenset(
    set(Interpretation.model_fields)
    | set(Span.model_fields)
    | {
        "occurrence",
        "role",
        "aggregate",
        "entity",
        "column",
        "concept",
        "polarity",
        "population",
        "numerator",
        "denominator",
        "value",
        "decision",
        "slots",
        "reason",
    }
)


def diagnostics(error):
    """Emit only fixed codes/paths; never provider text, arbitrary keys or input."""
    entries = (
        error.errors()
        if isinstance(error, ValidationError)
        else [{"type": "value_error", "loc": (), "ctx": {"error": error}}]
    )
    result = []
    for entry in entries[:8]:
        reason = entry.get("ctx", {}).get("error")
        args = reason.args if isinstance(reason, ValueError) else ()
        code = (
            args[0]
            if len(args) == 1 and isinstance(args[0], str) and args[0] in REASONS
            else entry["type"]
        )
        if code not in REASONS | ERROR_TYPES:
            code = "unclassified_validation"
        path = [
            item
            if (type(item) is int and 0 <= item <= 1000)
            or (isinstance(item, str) and item in PATH_FIELDS)
            else "unknown_field"
            for item in entry.get("loc", ())
        ]
        result.append(
            {"stage": "validation", "code": code, "schema_path": path, "count": 1}
        )
    return result


def semantic_diagnostic(payload, question, schema, concepts):
    """Valid semantic fields only, explicitly NOT an accepted interpretation."""
    if not isinstance(payload, dict):
        return None
    try:
        return validate_interpretation(
            {**payload, "spans": []}, question, schema, concepts
        ).model_dump(exclude={"spans"})
    except (ValueError, TypeError):
        return None


def signature(operand, base, schema, overlay):
    plan = QueryPlan.model_validate({"base_table": base, "measures": [operand]})
    basis, predicates = _operand(plan.measures[0], plan, overlay, schema)
    return {"basis": basis, "predicates": sorted(predicates)}


def catalog(schema, overlay):
    """Question/gold/row-independent enumeration. No truncation or fuzzy meaning."""
    grouped = {}

    def add(base, operand, reviewed=None):
        core = signature(operand, base, schema, overlay)
        key = digest(core)
        if key not in grouped:
            grouped[key] = {
                "id": "c_" + key[:16],
                "base_table": base,
                "operand": deepcopy(operand),
                "operation": core["basis"][0],
                "column": core["basis"][2],
                "population": [
                    {"column": col, "op": op} for col, op in core["predicates"]
                ],
                "reviewed_metrics": [],
            }
        if reviewed is not None:
            grouped[key]["reviewed_metrics"].append(
                {
                    "id": reviewed.id,
                    "names": reviewed.names,
                    "description": reviewed.description,
                    "review_state": reviewed.review_state.value,
                }
            )

    for metric in sorted(overlay.metrics, key=lambda m: m.id):
        add(metric.base_table, {"metric": metric.id}, metric)
    for table in schema.tables:
        if any(c.sample_values for c in table.columns):
            raise ValueError("sample_values_forbidden")
        bases = [{"aggregate": "count"}]
        for column in table.columns:
            ref = {"table": table.name, "column": column.name}
            if column.kind.value == "numeric":
                bases.append({"aggregate": "sum", "column": ref})
            if column.kind.value in {"numeric", "text", "date", "timestamp", "boolean"}:
                bases.append({"aggregate": "count_distinct", "column": ref})
        filters = [[]] + [
            [{"column": {"table": table.name, "column": c.name}, "op": op}]
            for c in table.columns
            if c.nullable
            for op in ("is_null", "not_null")
        ]
        for operand in bases:
            for predicate in filters:
                add(table.name, {**operand, "filters": predicate})
    result = sorted(grouped.values(), key=lambda c: c["id"])
    if len(result) > 64:
        raise ValueError("catalog_capacity_exceeded")
    if len({c["id"] for c in result}) != len(result):
        raise ValueError("candidate_id_collision")
    return result


class SelectedProposal(BaseModel):
    selection: Selection
    proposal: PlanProposal


def bind_selection(payload, candidates, question):
    selection = Selection.model_validate(payload)
    if selection.decision != "pick":
        reason = {
            "ambiguous": "ambiguous",
            "missing_definition": "semantic_gap",
            "outside_catalog": "unsupported",
        }[selection.reason]
        return SelectedProposal(
            selection=selection,
            proposal=PlanProposal(
                decision="none",
                reason=reason,
                clarification=selection.reason,
            ),
        )
    offered = {c["id"]: c for c in candidates}
    if len(offered) != len(candidates) or any(
        i not in offered for i in selection.slots.values()
    ):
        raise ValueError("candidate_not_offered")
    chosen = {role: offered[i] for role, i in selection.slots.items()}
    bases = {c["base_table"] for c in chosen.values()}
    if len(bases) != 1:
        raise ValueError("candidate_cross_table")
    if selection.output_label is not None and selection.output_label not in question:
        raise ValueError("candidate_label_not_in_question")
    measure = (
        deepcopy(chosen["value"]["operand"])
        if "value" in chosen
        else {"ratio": {role: deepcopy(c["operand"]) for role, c in chosen.items()}}
    )
    measure["alias"] = selection.output_label
    return SelectedProposal(
        selection=selection,
        proposal=PlanProposal.model_validate(
            {
                "decision": "plan",
                "plan": {"base_table": next(iter(bases)), "measures": [measure]},
            }
        ),
    )
