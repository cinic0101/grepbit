"""Deterministic single-select presentation referencing authoritative semantic choices."""
from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from typing import Literal
from zoneinfo import ZoneInfo

from .clarification import (
    Center, Clarification, ComparisonRoles, CountBasis, MAX_CHOICES, MetricMeaning,
    _choice_id, _invalid, _object,
)

PRESENTATION_VERSION = "clarification-presentation-v1"


def _text(value: object) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        _invalid()
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        _invalid()
    if size > 256:
        _invalid()


@dataclass(frozen=True, repr=False)
class ChoiceOption:
    choice_id: str
    label: str

    def __post_init__(self) -> None:
        _choice_id(self.choice_id)
        _text(self.label)

    def to_dict(self) -> dict[str, str]:
        return {"choice_id": self.choice_id, "label": self.label}


@dataclass(frozen=True, repr=False)
class ChoicesBlock:
    options: tuple[ChoiceOption, ...]
    type: Literal["choices"] = field(default="choices", init=False)
    selection: Literal["single"] = field(default="single", init=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.options, tuple) or not 2 <= len(self.options) <= MAX_CHOICES
                or any(not isinstance(option, ChoiceOption) for option in self.options)
                or len({option.choice_id for option in self.options}) != len(self.options)):
            _invalid()

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "selection": self.selection,
                "options": [option.to_dict() for option in self.options]}


@dataclass(frozen=True, repr=False)
class ClarificationPresentation:
    text: str
    blocks: tuple[ChoicesBlock, ...]
    clarification: InitVar[Clarification]

    def __post_init__(self, clarification: Clarification) -> None:
        _text(self.text)
        if (not isinstance(clarification, Clarification) or not isinstance(self.blocks, tuple)
                or len(self.blocks) != 1 or not isinstance(self.blocks[0], ChoicesBlock)
                or {option.choice_id for option in self.blocks[0].options}
                != {choice.id for choice in clarification.choices}):
            _invalid()

    @classmethod
    def from_mapping(cls, data: object, clarification: Clarification) -> ClarificationPresentation:
        item = _object(data, {"text", "blocks"})
        blocks = item["blocks"]
        if not isinstance(blocks, list) or len(blocks) != 1:
            _invalid()
        block = _object(blocks[0], {"type", "selection", "options"})
        if (not isinstance(block["type"], str) or block["type"] != "choices"
                or not isinstance(block["selection"], str) or block["selection"] != "single"):
            _invalid()
        raw_options = block["options"]
        if not isinstance(raw_options, list) or not 2 <= len(raw_options) <= MAX_CHOICES:
            _invalid()
        options = []
        for raw in raw_options:
            option = _object(raw, {"choice_id", "label"})
            options.append(ChoiceOption(option["choice_id"], option["label"]))
        return cls(item["text"], (ChoicesBlock(tuple(options)),), clarification)

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "blocks": [block.to_dict() for block in self.blocks]}


def render_clarification(clarification: Clarification) -> ClarificationPresentation:
    if not isinstance(clarification, Clarification):
        _invalid()
    questions = {
        "count_basis": "What do you mean by people in this overview?",
        "comparison_roles": "Which comparison direction do you mean?",
        "center": "Which supplied center do you mean?",
        "metric_meaning": "Which amount meaning do you intend?",
    }
    count_labels = {
        "booked_seats": "Booked seats",
        "known_booking_accounts": "Distinct known booking accounts, excluding anonymous (not available through the recipe entry)",
        "attendance_visits": "Attendance visits (not available through the recipe entry)",
        "distinct_people": "Distinct people (not available through the recipe entry)",
    }
    metric_labels = {
        "confirmed_booked_amount": "Confirmed booked amount before refunds",
        "cash_received": "Posted cash received (not available through the recipe entry)",
        "posted_refunds": "Posted refunds (not available through the recipe entry)",
        "profit": "Profit (not available through the recipe entry)",
    }
    options = []
    for choice in clarification.choices:
        value = choice.semantic_value
        if isinstance(value, CountBasis):
            label = count_labels[value.value]
        elif isinstance(value, MetricMeaning):
            label = metric_labels[value.value]
        elif isinstance(value, Center):
            label = value.request.center_code
        elif isinstance(value, ComparisonRoles):
            current = value.request.current.start.astimezone(ZoneInfo("Asia/Taipei")).strftime("%Y-%m")
            baseline = value.request.baseline.start.astimezone(ZoneInfo("Asia/Taipei")).strftime("%Y-%m")
            label = f"Current {current}; baseline {baseline}"
        else:
            _invalid()
        options.append(ChoiceOption(choice.id, label))
    return ClarificationPresentation(questions[clarification.kind], (ChoicesBlock(tuple(options)),), clarification)
