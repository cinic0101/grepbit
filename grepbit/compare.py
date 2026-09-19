"""Finite offline Compare composition over the shared scalar execution path."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Literal, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo

from . import kernel
from .catalog import LEARNINGOPS
from .contracts import ExecutionLimits, Fact, FactRequest, KernelError, utc_text


@dataclass(frozen=True)
class CompareRequest:
    current: FactRequest
    baseline: FactRequest

    def __post_init__(self) -> None:
        for scope in (self.current, self.baseline):
            if (not isinstance(scope, FactRequest)
                    or scope.metrics != ("confirmed_booked_amount",)
                    or scope.center_id is not None or scope.timezone != "Asia/Taipei"):
                raise KernelError("invalid_request", "Compare requires all-center booked amount in Asia/Taipei.")
            try:
                start = scope.start.astimezone(ZoneInfo("Asia/Taipei"))
                end = scope.end.astimezone(ZoneInfo("Asia/Taipei"))
            except (ValueError, OverflowError) as exc:
                raise KernelError("invalid_request", "Compare month is outside the supported calendar.") from exc
            if (any((value.day, value.hour, value.minute, value.second, value.microsecond)
                    != (1, 0, 0, 0, 0) for value in (start, end))
                    or end.year * 12 + end.month != start.year * 12 + start.month + 1):
                raise KernelError("invalid_request", "Both Compare scopes must be explicit full calendar months.")
        if self.current.start == self.baseline.start:
            raise KernelError("invalid_request", "Compare requires two distinct explicitly supplied months.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> CompareRequest:
        if not isinstance(data, Mapping) or set(data) != {"current", "baseline"}:
            raise KernelError("invalid_request", "Supply exactly current and baseline scopes.")
        current, baseline = data["current"], data["baseline"]
        if not isinstance(current, Mapping) or not isinstance(baseline, Mapping):
            raise KernelError("invalid_request", "Both Compare scopes must be explicit request objects.")
        return cls(FactRequest.from_mapping(current), FactRequest.from_mapping(baseline))

    def to_dict(self) -> dict[str, object]:
        return {"current": self.current.to_dict(), "baseline": self.baseline.to_dict()}


@dataclass(frozen=True)
class DerivedFact:
    derivation: Literal["difference", "relative_change"]
    input_fact_ids: tuple[str, str]
    value: int | Fraction | None
    unit: str
    snapshot_id: str
    state: Literal["checked", "undefined", "unavailable"]
    reason: str | None = None
    fact_id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        if isinstance(self.value, Fraction):
            result["value"] = {"numerator": self.value.numerator, "denominator": self.value.denominator}
        return result


@dataclass(frozen=True)
class SlotResult:
    slot_id: Literal["current", "baseline", "delta", "growth"]
    fact_id: str
    state: Literal["checked", "undefined", "unavailable"]
    reason: str | None = None


@dataclass(frozen=True)
class AnalysisPack:
    request: CompareRequest
    facts: tuple[Fact, Fact]
    derived_facts: tuple[DerivedFact, DerivedFact]
    slots: tuple[SlotResult, SlotResult, SlotResult, SlotResult]
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    recipe_id: str = field(default="compare", init=False)
    recipe_version: str = field(default="0.1", init=False)

    @property
    def status(self) -> Literal["complete", "failed"]:
        return "failed" if any(slot.state == "unavailable" for slot in self.slots) else "complete"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["request"] = self.request.to_dict()
        result["derived_facts"] = [fact.to_dict() for fact in self.derived_facts]
        result["status"] = self.status
        return result


def _check_compatibility(request: CompareRequest, current: Fact, baseline: Fact,
                         snapshot_id: str) -> None:
    axes = (
        "catalog_id", "catalog_sha256", "metric_id", "unit", "population", "grain",
        "filters", "time_basis", "business_timezone", "completeness", "snapshot_id",
        "excluded_anonymous_rows", "disclosures",
    )
    if any(getattr(current, axis) != getattr(baseline, axis) for axis in axes):
        raise KernelError("incompatible_facts", "Compare input semantics, coverage or snapshots differ.")
    for fact, scope in ((current, request.current), (baseline, request.baseline)):
        if (fact.catalog_id != LEARNINGOPS.version or fact.catalog_sha256 != LEARNINGOPS.digest()
                or fact.metric_id != "confirmed_booked_amount" or fact.unit != "TWD_minor"
                or fact.filters != {} or fact.business_timezone != "Asia/Taipei"
                or fact.snapshot_id != snapshot_id or fact.completeness != "complete"
                or not set(kernel._CHECKS) <= set(fact.checks)
                or (fact.start_utc, fact.end_utc) != (utc_text(scope.start), utc_text(scope.end))
                or not fact.fact_id or current.fact_id == baseline.fact_id):
            raise KernelError("incompatible_facts", "Compare requires identified checked facts for its bound scopes.")
        if (type(fact.population_rows) is not int or fact.population_rows < 0
                or fact.empty_population is not (fact.population_rows == 0)
                or (fact.value is None) != fact.empty_population
                or (fact.value is not None and
                    (type(fact.value) is not int or not -(2**63) <= fact.value < 2**63))):
            raise KernelError("incompatible_facts", "Compare requires exact integer-or-empty amount evidence.")


def _difference(current: Fact, baseline: Fact) -> DerivedFact:
    value = None
    if current.value is not None and baseline.value is not None:
        value = current.value - baseline.value
        if not -(2**63) <= value < 2**63:
            raise KernelError("arithmetic_overflow", "Compare difference exceeds signed 64-bit integer range.")
    return DerivedFact(
        "difference", (current.fact_id, baseline.fact_id), value, current.unit, current.snapshot_id,
        "checked" if value is not None else "unavailable",
        None if value is not None else "empty_input",
    )


def _relative_change(delta: DerivedFact, baseline: Fact) -> DerivedFact:
    if (delta.derivation != "difference" or delta.input_fact_ids[1] != baseline.fact_id
            or delta.snapshot_id != baseline.snapshot_id or delta.unit != baseline.unit
            or (delta.state == "checked" and type(delta.value) is not int)):
        raise KernelError("incompatible_facts", "Growth requires the checked difference for this baseline.")
    state: Literal["checked", "undefined", "unavailable"]
    reason: str | None
    value: Fraction | None
    if delta.state != "checked" or not isinstance(delta.value, int) or baseline.value is None:
        state, reason, value = "unavailable", "unavailable_difference", None
    elif baseline.value == 0:
        state, reason, value = "undefined", "zero_baseline", None
    else:
        state, reason, value = "checked", None, Fraction(delta.value, baseline.value)
    return DerivedFact(
        "relative_change", (delta.fact_id, baseline.fact_id), value, "dimensionless",
        baseline.snapshot_id, state, reason,
    )


def execute_compare(database: Path, request: CompareRequest, *,
                    limits: ExecutionLimits = ExecutionLimits()) -> AnalysisPack:
    """Execute compare@0.1; source/budget/compatibility failures raise KernelError."""
    if not isinstance(request, CompareRequest) or not isinstance(limits, ExecutionLimits):
        raise KernelError("invalid_request", "Use a typed CompareRequest and trusted ExecutionLimits.")
    budget = kernel._Budget(limits)
    current_queries = kernel._compile_scope(request.current, LEARNINGOPS)
    baseline_queries = kernel._compile_scope(request.baseline, LEARNINGOPS)
    with kernel._read_transaction(database, budget) as (conn, snapshot):
        current, = kernel._execute_scope(
            conn, request.current, current_queries, LEARNINGOPS, snapshot["id"], budget,
        )
        baseline, = kernel._execute_scope(
            conn, request.baseline, baseline_queries, LEARNINGOPS, snapshot["id"], budget,
        )
        _check_compatibility(request, current, baseline, snapshot["id"])
        delta = _difference(current, baseline)
        growth = _relative_change(delta, baseline)
        slots = (
            SlotResult("current", current.fact_id, "checked"),
            SlotResult("baseline", baseline.fact_id, "checked"),
            SlotResult("delta", delta.fact_id, delta.state, delta.reason),
            SlotResult("growth", growth.fact_id, growth.state, growth.reason),
        )
    return AnalysisPack(
        request, (current, baseline), (delta, growth), slots, snapshot,
        kernel._runtime_evidence(), kernel._execution_evidence(budget),
        kernel._LIMITATIONS + (
            "Compare uses whole calendar-month totals without per-day normalization.",
            "All four Compare slots are required; no optional or partial analysis is implemented.",
        ),
    )
