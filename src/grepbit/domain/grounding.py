"""Grounding contracts: reviewed question templates and decisions (spec §7)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from grepbit.domain.models import DomainModel
from grepbit.domain.structured_query import StructuredQuery

_IDENTIFIER = r"^[a-z_][a-z0-9_]*$"
_ISO_MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
_MONTH_NAME_YEAR = re.compile(r"^([a-z]+),?\s+([0-9]{4})$")
_MONTH_ZH = re.compile(r"^([0-9]{4})\s*年\s*([0-9]{1,2})\s*月$")
_PLACEHOLDER = re.compile(r"^\{([a-z_][a-z0-9_]*)\}$")
_TRAILING_PUNCTUATION = " ?!.,;:？！。"
MONTH_NUMBERS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


def normalize_question(text: str) -> str:
    """NFKC, casefold, collapse whitespace, and drop trailing punctuation."""

    collapsed = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return collapsed.rstrip(_TRAILING_PUNCTUATION)


def question_digest(normalized_question: str) -> str:
    return "sha256:" + hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class TemplateSlotKind(StrEnum):
    ISO_MONTH = "iso_month"
    MONTH_NAME_YEAR = "month_name_year"
    MONTH_ZH = "month_zh"
    POSITIVE_INTEGER = "positive_integer"


def parse_month(kind: TemplateSlotKind, value: str) -> str | None:
    """Return an ISO month for a reviewed month slot value, or None."""

    if kind is TemplateSlotKind.ISO_MONTH:
        return value if _ISO_MONTH.fullmatch(value) else None
    if kind is TemplateSlotKind.MONTH_NAME_YEAR:
        match = _MONTH_NAME_YEAR.fullmatch(value)
        if match is None:
            return None
        month = MONTH_NUMBERS.get(match.group(1))
        if month is None:
            return None
        return f"{int(match.group(2)):04d}-{month:02d}"
    if kind is TemplateSlotKind.MONTH_ZH:
        match = _MONTH_ZH.fullmatch(value)
        if match is None or not 1 <= int(match.group(2)) <= 12:
            return None
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    return None


def slot_value_is_valid(kind: TemplateSlotKind, value: str) -> bool:
    if kind is TemplateSlotKind.POSITIVE_INTEGER:
        return bool(re.fullmatch(r"[1-9][0-9]{0,3}", value))
    return parse_month(kind, value) is not None


def slot_json_value(kind: TemplateSlotKind, value: str) -> str | int:
    if kind is TemplateSlotKind.POSITIVE_INTEGER:
        return int(value)
    month = parse_month(kind, value)
    if month is None:
        raise ValueError("question_template_slot_value_invalid")
    return month


class TemplateSlot(DomainModel):
    name: str = Field(pattern=_IDENTIFIER)
    kind: TemplateSlotKind


class ReviewedQuestionTemplate(DomainModel):
    """A reviewed literal question shape that grounds with zero model calls."""

    # Literal boundaries carry significant spaces; do not strip them.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    template_id: str = Field(pattern=_IDENTIFIER)
    literals: list[str] = Field(min_length=1)
    slots: list[TemplateSlot] = Field(default_factory=list)
    structured_query: dict[str, Any]
    reviewed_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def template_is_coherent(self) -> ReviewedQuestionTemplate:
        if len(self.literals) != len(self.slots) + 1:
            raise ValueError("question_template_literals_slots_invalid")
        for literal in self.literals:
            if (
                literal
                != " ".join(
                    unicodedata.normalize("NFKC", literal).casefold().split(" ")
                )
                or "  " in literal
            ):
                raise ValueError("question_template_literal_not_normalized")
        if self.literals[0].startswith(" ") or self.literals[-1].endswith(" "):
            raise ValueError("question_template_literal_not_normalized")
        if not any(self.literals):
            raise ValueError("question_template_requires_literal")
        names = [slot.name for slot in self.slots]
        if len(names) != len(set(names)):
            raise ValueError("question_template_slot_duplicate")
        placeholders = _placeholders(self.structured_query)
        if placeholders != set(names):
            raise ValueError("question_template_placeholders_mismatch")
        return self

    def match(self, normalized_question: str) -> dict[str, str] | None:
        """Return slot bindings for exactly one literal match, else None."""

        found: list[dict[str, str]] = []

        def visit(index: int, position: int, bindings: dict[str, str]) -> None:
            literal = self.literals[index]
            if not normalized_question.startswith(literal, position):
                return
            position += len(literal)
            if index == len(self.slots):
                if position == len(normalized_question):
                    found.append(bindings)
                return
            next_literal = self.literals[index + 1]
            for end in range(position, len(normalized_question) + 1):
                if next_literal and not normalized_question.startswith(
                    next_literal, end
                ):
                    continue
                value = normalized_question[position:end]
                if slot_value_is_valid(self.slots[index].kind, value):
                    visit(index + 1, end, {**bindings, self.slots[index].name: value})
                if len(found) > 1:
                    return

        visit(0, 0, {})
        return found[0] if len(found) == 1 else None

    def materialize(self, bindings: dict[str, str]) -> StructuredQuery:
        kinds = {slot.name: slot.kind for slot in self.slots}
        if set(bindings) != set(kinds):
            raise ValueError("question_template_bindings_mismatch")
        values = {name: slot_json_value(kinds[name], bindings[name]) for name in kinds}
        return StructuredQuery.model_validate(
            _substitute(self.structured_query, values)
        )


def _placeholders(node: Any) -> set[str]:
    if isinstance(node, str):
        match = _PLACEHOLDER.fullmatch(node)
        return {match.group(1)} if match else set()
    if isinstance(node, dict):
        return set().union(*(_placeholders(value) for value in node.values()), set())
    if isinstance(node, list):
        return set().union(*(_placeholders(value) for value in node), set())
    return set()


def _substitute(node: Any, values: dict[str, str | int]) -> Any:
    if isinstance(node, str):
        match = _PLACEHOLDER.fullmatch(node)
        return values[match.group(1)] if match else node
    if isinstance(node, dict):
        return {key: _substitute(value, values) for key, value in node.items()}
    if isinstance(node, list):
        return [_substitute(value, values) for value in node]
    return node


class GroundingStatus(StrEnum):
    ANSWERED = "answered"
    CLARIFY = "clarify"
    SEMANTIC_GAP = "semantic_gap"
    UNSUPPORTED = "unsupported"
    UNSAFE = "unsafe"
    FAILED = "failed"


class GroundingPath(StrEnum):
    REVIEWED_LITERAL = "reviewed_literal"
    DETERMINISTIC = "deterministic"
    CLASSIFIED = "classified"


class ClarificationOption(DomainModel):
    label: str = Field(min_length=1)
    metric_id: str = Field(pattern=_IDENTIFIER)
    query_delta: dict[str, Any]


class Clarification(DomainModel):
    question: str = Field(min_length=1)
    options: list[ClarificationOption] = Field(min_length=2)
    pending_query: StructuredQuery | None = None

    def option(self, metric_id: str) -> ClarificationOption | None:
        return next(
            (item for item in self.options if item.metric_id == metric_id), None
        )


class GroundingDecision(DomainModel):
    status: GroundingStatus
    path: GroundingPath
    question_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    catalog_revision: str = Field(min_length=1)
    structured_query: StructuredQuery | None = None
    clarification: Clarification | None = None
    suggestions: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    model_call_count: int = Field(default=0, ge=0)
    candidate_metric_ids: list[str] = Field(default_factory=list)
    candidate_scores: dict[str, float] = Field(default_factory=dict)
    retriever_revision: str | None = None
    template_id: str | None = None

    @model_validator(mode="after")
    def status_payload_is_coherent(self) -> GroundingDecision:
        if self.status is GroundingStatus.ANSWERED:
            if self.structured_query is None or self.clarification is not None:
                raise ValueError("grounding_answered_requires_structured_query")
        elif self.status is GroundingStatus.CLARIFY:
            if self.clarification is None or self.structured_query is not None:
                raise ValueError("grounding_clarify_requires_options")
        elif self.structured_query is not None or self.clarification is not None:
            raise ValueError("grounding_terminal_rejects_payload")
        return self


GROUNDING_PROMPT_SCHEMA_REVISION = "grounding-classify-json-v1"


class CandidateMetric(DomainModel):
    id: str
    description: str
    unit: str
    synonyms: list[str] = Field(default_factory=list)
    supported_shapes: list[str] = Field(default_factory=list)
    ambiguity_group: str | None = None
    disambiguators: list[str] = Field(default_factory=list)
    defaults: list[str] = Field(default_factory=list)


class CandidateDimension(DomainModel):
    id: str
    description: str
    kind: str
    value_ids: list[str] = Field(default_factory=list)
    value_synonyms: dict[str, list[str]] = Field(default_factory=dict)
    synonyms: list[str] = Field(default_factory=list)


class CandidateTimeField(DomainModel):
    id: str
    description: str
    default: bool


class GroundingRequest(DomainModel):
    """Value-free classification input: catalog descriptors only, never data."""

    operation: Literal["ground"] = "ground"
    question: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    business_timezone: str = Field(min_length=1)
    catalog_revision: str = Field(min_length=1)
    prompt_schema_revision: str = GROUNDING_PROMPT_SCHEMA_REVISION
    metrics: list[CandidateMetric] = Field(min_length=1)
    dimensions: list[CandidateDimension] = Field(default_factory=list)
    time_fields: list[CandidateTimeField] = Field(default_factory=list)
    shapes: list[str] = Field(min_length=1)
    max_top_n: int = Field(ge=1)


class GroundingProposal(DomainModel):
    """Untrusted model output; the server validates every identifier."""

    decision: Literal["query", "none"]
    structured_query: StructuredQuery | None = None
    reason: Literal["semantic_gap", "unsupported", "ambiguous"] | None = None
    ambiguous_metric_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def decision_payload_is_coherent(self) -> GroundingProposal:
        if self.decision == "query":
            if self.structured_query is None or self.reason is not None:
                raise ValueError("grounding_proposal_query_requires_structured_query")
        elif self.structured_query is not None or self.reason is None:
            raise ValueError("grounding_proposal_none_requires_reason")
        return self
