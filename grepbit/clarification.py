"""Closed semantic alternatives, not a planner, grounding service or resume API."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal, NoReturn

from .compare import CompareRequest
from .contracts import KernelError
from .overview import OverviewRequest

COUNT_BASES = ("booked_seats", "known_booking_accounts", "attendance_visits", "distinct_people")
METRIC_MEANINGS = ("confirmed_booked_amount", "cash_received", "posted_refunds", "profit")
KINDS = ("count_basis", "comparison_roles", "center", "metric_meaning")
MAX_CHOICES = 4


def _invalid() -> NoReturn:
    raise KernelError("invalid_request", "Invalid bounded clarification contract.")


def _object(data: object, keys: set[str]) -> dict:
    if not isinstance(data, dict) or set(data) != keys:
        _invalid()
    return data


def _choice_id(value: object) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", value) is None:
        _invalid()


@dataclass(frozen=True, repr=False)
class CountBasis:
    scope: OverviewRequest
    value: str
    type: Literal["count_basis"] = field(default="count_basis", init=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.scope, OverviewRequest) or not isinstance(self.value, str)
                or self.value not in COUNT_BASES):
            _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "scope": self.scope.to_dict(), "value": self.value}


@dataclass(frozen=True, repr=False)
class MetricMeaning:
    scope: OverviewRequest
    value: str
    type: Literal["metric_meaning"] = field(default="metric_meaning", init=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.scope, OverviewRequest) or not isinstance(self.value, str)
                or self.value not in METRIC_MEANINGS):
            _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "scope": self.scope.to_dict(), "value": self.value}


@dataclass(frozen=True, repr=False)
class ComparisonRoles:
    request: CompareRequest
    type: Literal["comparison_roles"] = field(default="comparison_roles", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, CompareRequest):
            _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "request": self.request.to_dict()}


@dataclass(frozen=True, repr=False)
class Center:
    request: OverviewRequest
    type: Literal["center"] = field(default="center", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, OverviewRequest):
            _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "request": self.request.to_dict()}


SemanticValue = CountBasis | MetricMeaning | ComparisonRoles | Center


@dataclass(frozen=True, repr=False)
class SemanticChoice:
    id: str
    semantic_value: SemanticValue

    def __post_init__(self) -> None:
        _choice_id(self.id)
        if not isinstance(self.semantic_value, (CountBasis, MetricMeaning, ComparisonRoles, Center)):
            _invalid()

    @classmethod
    def from_mapping(cls, data: object) -> SemanticChoice:
        item = _object(data, {"id", "semantic_value"})
        raw = item["semantic_value"]
        if not isinstance(raw, dict):
            _invalid()
        kind = raw.get("type")
        if not isinstance(kind, str):
            _invalid()
        value: SemanticValue
        if kind in ("count_basis", "metric_meaning"):
            raw = _object(raw, {"type", "scope", "value"})
            scope = OverviewRequest.from_mapping(raw["scope"])
            value = (CountBasis(scope, raw["value"]) if kind == "count_basis"
                     else MetricMeaning(scope, raw["value"]))
        elif kind == "comparison_roles":
            raw = _object(raw, {"type", "request"})
            value = ComparisonRoles(CompareRequest.from_mapping(raw["request"]))
        elif kind == "center":
            raw = _object(raw, {"type", "request"})
            value = Center(OverviewRequest.from_mapping(raw["request"]))
        else:
            _invalid()
        return cls(item["id"], value)

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "semantic_value": self.semantic_value.to_dict()}


@dataclass(frozen=True, repr=False)
class Clarification:
    kind: str
    choices: tuple[SemanticChoice, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, str) or self.kind not in KINDS or not isinstance(self.choices, tuple)
                or not 2 <= len(self.choices) <= MAX_CHOICES
                or any(not isinstance(choice, SemanticChoice) for choice in self.choices)):
            _invalid()
        values = tuple(choice.semantic_value for choice in self.choices)
        if (len({choice.id for choice in self.choices}) != len(self.choices)
                or len(set(values)) != len(values)
                or any(value.type != self.kind for value in values)):
            _invalid()
        first = values[0]
        if isinstance(first, (CountBasis, MetricMeaning)):
            if any(not isinstance(value, (CountBasis, MetricMeaning)) or value.scope != first.scope
                   for value in values):
                _invalid()
            required = "booked_seats" if isinstance(first, CountBasis) else "confirmed_booked_amount"
            if not any(isinstance(value, (CountBasis, MetricMeaning)) and value.value == required
                       for value in values):
                _invalid()
        elif isinstance(first, ComparisonRoles):
            if (len(values) != 2 or not isinstance(values[1], ComparisonRoles)
                    or values[1].request != CompareRequest(first.request.baseline, first.request.current)):
                _invalid()
        elif isinstance(first, Center):
            period = (first.request.start, first.request.end, first.request.timezone)
            if any(not isinstance(value, Center) or (
                    value.request.start, value.request.end, value.request.timezone) != period for value in values):
                _invalid()

    @classmethod
    def from_mapping(cls, data: object) -> Clarification:
        item = _object(data, {"kind", "choices"})
        choices = item["choices"]
        if not isinstance(choices, list) or not 2 <= len(choices) <= MAX_CHOICES:
            _invalid()
        return cls(item["kind"], tuple(SemanticChoice.from_mapping(choice) for choice in choices))

    def validate_question(self, question: str) -> None:
        if not isinstance(question, str):
            _invalid()
        for choice in self.choices:
            value = choice.semantic_value
            scope = value.scope if isinstance(value, (CountBasis, MetricMeaning)) else (
                value.request if isinstance(value, Center) else None)
            if scope is not None and re.search(
                    r"(?<![A-Za-z0-9_-])" + re.escape(scope.center_code) + r"(?![A-Za-z0-9_-])",
                    question) is None:
                _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "choices": [choice.to_dict() for choice in self.choices]}


def clarification_schema(overview: dict, compare: dict) -> dict[str, object]:
    """Reuse native schema objects; cross-choice/native calendar checks remain authoritative."""
    def obj(properties):
        return {"type": "object", "additionalProperties": False,
                "required": list(properties), "properties": properties}

    values = {
        "count_basis": obj({"type": {"const": "count_basis"}, "scope": overview,
                            "value": {"enum": list(COUNT_BASES)}}),
        "comparison_roles": obj({"type": {"const": "comparison_roles"}, "request": compare}),
        "center": obj({"type": {"const": "center"}, "request": overview}),
        "metric_meaning": obj({"type": {"const": "metric_meaning"}, "scope": overview,
                               "value": {"enum": list(METRIC_MEANINGS)}}),
    }
    return obj({"outcome": {"const": "clarify"}, "clarification": {"oneOf": [
        obj({"kind": {"const": kind}, "choices": {
            "type": "array", "minItems": 2, "maxItems": 2 if kind == "comparison_roles" else MAX_CHOICES,
            "items": obj({"id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,31}$"},
                          "semantic_value": value}),
        }}) for kind, value in values.items()
    ]}})
