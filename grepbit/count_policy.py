"""Typed Overview count cues and one deterministic count policy (#120); never reads question text."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .clarification import COUNT_BASES, Clarification, CountBasis, SemanticChoice
from .contracts import KernelError
from .overview import OverviewRequest

READINGS = ("none", "bound", "contrast", "generic")
EVENTS = ("booking", "none")
# First matching rule applies; docs/count-cue-policy.md is the table of record.
RULES = ("other_unsupported", "bound_seats", "bound_unsupported", "contrast_unexecutable", "contrast",
         "generic_booking", "generic_unframed")
CUE_REASONS = ("count_cue_shape", "count_cue_values", "count_cue_binding")
_FIELDS = {"bound": "meaning", "contrast": "meanings", "generic": "event"}
_SCOPE = {"center_code", "start", "end", "timezone"}
_BOOKING_MEANINGS = ("booked_seats", "known_booking_accounts", "distinct_people")


class CueError(ValueError):
    """A rejected cue with one closed reason; no fallback action exists."""

    def __init__(self, reason: str):
        if reason not in CUE_REASONS:
            raise ValueError("Unknown count-cue reason.")
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, repr=False)
class CountCue:
    reading: str
    value: str | tuple[str, ...]
    other_unsupported: bool
    scope: OverviewRequest

    def to_dict(self) -> dict[str, object]:
        value = list(self.value) if isinstance(self.value, tuple) else self.value
        return {"overview_count": self.reading, _FIELDS[self.reading]: value,
                "other_unsupported": self.other_unsupported, "scope": self.scope.to_dict()}


@dataclass(frozen=True, repr=False)
class CountDecision:
    rule: str
    action: str
    request: OverviewRequest | None = None
    clarification: Clarification | None = None


def parse_cue(data: object, question: str) -> CountCue:
    """Validate shape, values and question binding of one bound/contrast/generic cue."""
    reading = data.get("overview_count") if isinstance(data, dict) else None
    if reading not in _FIELDS or not isinstance(question, str):
        raise CueError("count_cue_shape")
    field = _FIELDS[reading]
    if set(data) != {"overview_count", field, "other_unsupported", "scope"}:
        raise CueError("count_cue_shape")
    value, other, scope = data[field], data["other_unsupported"], data["scope"]
    typed = (isinstance(value, list) and all(isinstance(item, str) for item in value) if reading == "contrast"
             else isinstance(value, str))
    if not typed or type(other) is not bool or not isinstance(scope, dict) or set(scope) != _SCOPE:
        raise CueError("count_cue_shape")
    if (reading == "bound" and value not in COUNT_BASES
            or reading == "contrast" and (not 2 <= len(value) <= len(COUNT_BASES) or len(set(value)) != len(value)
                                          or any(item not in COUNT_BASES for item in value))
            or reading == "generic" and value not in EVENTS):
        raise CueError("count_cue_values")
    try:
        request = OverviewRequest.from_mapping(scope)
    except KernelError:
        raise CueError("count_cue_values") from None
    # The same literal center-code binding that Clarification.validate_question applies.
    if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(request.center_code) + r"(?![A-Za-z0-9_-])",
                 question) is None:
        raise CueError("count_cue_binding")
    return CountCue(reading, tuple(value) if reading == "contrast" else value, other, request)


def _clarify(rule: str, scope: OverviewRequest, meanings: tuple[str, ...]) -> CountDecision:
    values = tuple(basis for basis in COUNT_BASES if basis in meanings)
    return CountDecision(rule, "clarify", clarification=Clarification(
        "count_basis", tuple(SemanticChoice(value, CountBasis(scope, value)) for value in values)))


def decide(cue: CountCue) -> CountDecision:
    if cue.other_unsupported:
        return CountDecision("other_unsupported", "declined")
    if cue.reading == "bound":
        if cue.value == "booked_seats":
            return CountDecision("bound_seats", "request", request=cue.scope)
        return CountDecision("bound_unsupported", "declined")
    if cue.reading == "contrast":
        if "booked_seats" not in cue.value:
            return CountDecision("contrast_unexecutable", "declined")
        return _clarify("contrast", cue.scope, cue.value)
    if cue.value == "booking":
        return _clarify("generic_booking", cue.scope, _BOOKING_MEANINGS)
    return _clarify("generic_unframed", cue.scope, COUNT_BASES)
