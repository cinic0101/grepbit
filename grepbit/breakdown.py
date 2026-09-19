"""Fixed course selection and exact share of an independently executed whole."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Literal, Mapping
from uuid import uuid4

from . import composition, grouped, kernel
from .catalog import LEARNINGOPS
from .contracts import ExecutionLimits, Fact, FactRequest, KernelError, utc_text
from .grouped import GroupedAmountFact, GroupedAmountRequest, GroupedAmountRow

_METRIC = "confirmed_booked_amount"


@dataclass(frozen=True)
class BreakdownRequest:
    start: datetime
    end: datetime
    timezone: str
    top_k: int

    def __post_init__(self) -> None:
        GroupedAmountRequest(self._scope(), "course", self.top_k)

    def _scope(self) -> FactRequest:
        return FactRequest((_METRIC,), self.start, self.end, self.timezone)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> BreakdownRequest:
        if not isinstance(data, Mapping) or set(data) != {"start", "end", "timezone", "top_k"}:
            raise KernelError("invalid_request", "Supply exactly start, end, timezone and top_k.")
        top_k = data["top_k"]
        if type(top_k) is not int:
            raise KernelError("invalid_request", "top_k must be an integer from 1 to 3.")
        scope = FactRequest.from_mapping({
            "metrics": [_METRIC], "start": data["start"], "end": data["end"], "timezone": data["timezone"],
        })
        return cls(scope.start, scope.end, scope.timezone, top_k)

    def to_dict(self) -> dict[str, object]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(),
                "timezone": self.timezone, "top_k": self.top_k}


@dataclass(frozen=True)
class BreakdownDerivedFact:
    derivation: Literal["selected_subtotal", "share_of_scope"]
    input_fact_ids: tuple[str] | tuple[str, str]
    value: int | Fraction | None
    unit: str
    snapshot_id: str
    state: Literal["checked", "undefined", "unavailable"]
    reason: Literal["empty_input", "unavailable_subtotal", "zero_total"] | None = None
    fact_id: str = field(default_factory=lambda: str(uuid4()), init=False)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        if isinstance(self.value, Fraction):
            result["value"] = {"numerator": self.value.numerator, "denominator": self.value.denominator}
        return result


@dataclass(frozen=True)
class BreakdownSlotResult:
    slot_id: Literal["top_courses", "all_amount", "top_subtotal", "share"]
    fact_id: str
    state: Literal["checked", "undefined", "unavailable"]
    reason: Literal["empty_input", "unavailable_subtotal", "zero_total"] | None = None
    role: Literal["required"] = field(default="required", init=False)


@dataclass(frozen=True)
class BreakdownAnalysisPack:
    request: BreakdownRequest
    scope: FactRequest
    facts: tuple[Fact]
    grouped_facts: tuple[GroupedAmountFact]
    derived_facts: tuple[BreakdownDerivedFact, BreakdownDerivedFact]
    slots: tuple[BreakdownSlotResult, BreakdownSlotResult, BreakdownSlotResult, BreakdownSlotResult]
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    checks: tuple[str, ...] = (
        "independently_executed_whole_scope_denominator", "bound_course_top_k_coverage",
        "compatible_subset_and_whole", "exact_derivations_and_role_provenance",
        "single_live_transaction_and_global_budget",
    )
    recipe_id: str = field(default="breakdown", init=False)
    recipe_version: str = field(default="0.1", init=False)

    @property
    def status(self) -> Literal["complete", "failed"]:
        return "failed" if any(slot.state == "unavailable" for slot in self.slots) else "complete"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["request"] = self.request.to_dict()
        result["scope"] = self.scope.to_dict()
        result["derived_facts"] = [fact.to_dict() for fact in self.derived_facts]
        result["status"] = self.status
        return result


def _check_inputs(request: BreakdownRequest, total: Fact, top: GroupedAmountFact,
                  snapshot: dict[str, str], snapshot_id: str) -> None:
    if not isinstance(total, Fact) or not isinstance(top, GroupedAmountFact):
        raise KernelError("incompatible_facts", "Breakdown requires its scalar whole and course selection.")
    binding = LEARNINGOPS.metrics[_METRIC]
    for fact in (total, top):
        if (fact.catalog_id != LEARNINGOPS.version or fact.catalog_sha256 != LEARNINGOPS.digest()
                or fact.metric_id != _METRIC or fact.unit != binding.unit
                or fact.grain != kernel._GRAINS[binding.source] or fact.population != kernel._POPULATION
                or fact.time_basis != "bookings.created_at_utc"
                or (fact.start_utc, fact.end_utc) != (utc_text(request.start), utc_text(request.end))
                or fact.business_timezone != request.timezone or fact.filters != {}
                or fact.snapshot_id != snapshot_id or not isinstance(fact.fact_id, str) or not fact.fact_id
                or not isinstance(fact.checks, tuple) or any(not isinstance(check, str) for check in fact.checks)):
            raise KernelError("incompatible_facts", "Breakdown inputs do not match the bound whole-scope amount.")
    if (total.fact_id == top.fact_id or total.completeness != "complete"
            or total.disclosures != binding.disclosures or total.excluded_anonymous_rows is not None
            or not set(kernel._CHECKS) <= set(total.checks)
            or type(total.population_rows) is not int or total.population_rows < 0
            or total.empty_population is not (total.population_rows == 0)
            or (total.value is None) != total.empty_population
            or (total.value is not None and (type(total.value) is not int or not 0 <= total.value < 2**63))):
        raise KernelError("incompatible_facts", "The whole amount is not complete checked integer-or-empty evidence.")
    if (top.dimension != "course" or top.dimension_profile_id != grouped._DIMENSION_PROFILE
            or top.coverage != "top_k" or type(top.top_k) is not int or top.top_k != request.top_k
            or top.ordering != grouped._ORDERING["course"] or top.snapshot != snapshot
            or not isinstance(top.dimension_source_sha256, str) or len(top.dimension_source_sha256) != 64
            or any(char not in "0123456789abcdef" for char in top.dimension_source_sha256)
            or not set(grouped._GROUP_CHECKS + ("dimension_source_keys_and_relationships",)) <= set(top.checks)
            or not isinstance(top.rows, tuple) or len(top.rows) > request.top_k
            or top.empty_population is not (not top.rows) or top.empty_population != total.empty_population
            or len(top.rows) > total.population_rows):
        raise KernelError("incompatible_facts", "Course selection coverage, admission or empty evidence is incompatible.")
    ordering = []
    for row in top.rows:
        if (not isinstance(row, GroupedAmountRow) or not isinstance(row.key, str)
                or type(row.value) is not int or not 0 <= row.value < 2**63):
            raise KernelError("incompatible_facts", "Course selection requires exact nonnegative integer rows.")
        try:
            grouped._check_key(row.key, "course")
        except KernelError as exc:
            raise KernelError("incompatible_facts", "Course selection contains an invalid reviewed key.") from exc
        ordering.append((-row.value, row.key))
    if len({key for _, key in ordering}) != len(ordering) or ordering != sorted(ordering):
        raise KernelError("incompatible_facts", "Course selection keys must be distinct and correctly ranked.")


def _subtotal_value(rows: tuple[GroupedAmountRow, ...]) -> int | None:
    if not rows:
        return None
    value = 0
    for row in rows:
        if type(row.value) is not int or not 0 <= row.value < 2**63:
            raise KernelError("incompatible_facts", "Subtotal requires exact nonnegative integer inputs.")
        value += row.value
        if value >= 2**63:
            raise KernelError("arithmetic_overflow", "Selected subtotal exceeds signed 64-bit integer range.")
    return value


def _selected_subtotal(top: GroupedAmountFact) -> BreakdownDerivedFact:
    value = _subtotal_value(top.rows)
    return BreakdownDerivedFact(
        "selected_subtotal", (top.fact_id,), value, top.unit, top.snapshot_id,
        "checked" if value is not None else "unavailable", None if value is not None else "empty_input",
    )


def _share_of_scope(subtotal: BreakdownDerivedFact, top: GroupedAmountFact, total: Fact, *,
                    all_amount_id: str) -> BreakdownDerivedFact:
    if (not isinstance(subtotal, BreakdownDerivedFact) or not isinstance(total, Fact)
            or subtotal.derivation != "selected_subtotal" or subtotal.input_fact_ids != (top.fact_id,)
            or total.fact_id != all_amount_id or total.fact_id == top.fact_id
            or not isinstance(subtotal.fact_id, str) or not subtotal.fact_id
            or subtotal.fact_id in (top.fact_id, total.fact_id)
            or subtotal.snapshot_id != top.snapshot_id or total.snapshot_id != top.snapshot_id
            or subtotal.unit != top.unit or total.unit != top.unit):
        raise KernelError("incompatible_facts", "Share requires this selection's subtotal and identified whole amount.")
    expected = _subtotal_value(top.rows)
    if (subtotal.value != expected
            or subtotal.state != ("unavailable" if expected is None else "checked")
            or subtotal.reason != ("empty_input" if expected is None else None)
            or (expected is not None and type(subtotal.value) is not int)
            or total.empty_population is not (expected is None)
            or (total.value is None) != total.empty_population
            or (total.value is not None and (type(total.value) is not int or not 0 <= total.value < 2**63))):
        raise KernelError("incompatible_facts", "Subtotal value, provenance or whole-population evidence disagrees.")
    state: Literal["checked", "undefined", "unavailable"]
    reason: Literal["unavailable_subtotal", "zero_total"] | None
    value: Fraction | None
    if expected is None or total.value is None:
        state, reason, value = "unavailable", "unavailable_subtotal", None
    elif expected > total.value:
        raise KernelError("incompatible_facts", "Selected subtotal exceeds the independent whole amount.")
    elif total.value == 0:
        state, reason, value = "undefined", "zero_total", None
    else:
        state, reason, value = "checked", None, Fraction(expected, total.value)
    return BreakdownDerivedFact(
        "share_of_scope", (subtotal.fact_id, total.fact_id), value, "dimensionless", total.snapshot_id, state, reason,
    )


def execute_breakdown(database: Path, request: BreakdownRequest, *,
                      limits: ExecutionLimits = ExecutionLimits()) -> BreakdownAnalysisPack:
    """Execute breakdown@0.1; operational/incompatible failures return no pack."""
    if not isinstance(request, BreakdownRequest) or not isinstance(limits, ExecutionLimits):
        raise KernelError("invalid_request", "Use a typed BreakdownRequest and trusted ExecutionLimits.")
    scope = request._scope()
    need = GroupedAmountRequest(scope, "course", request.top_k)
    budget = kernel._Budget(limits)
    scalar_query = kernel._compile_scope(scope, LEARNINGOPS)
    grouped_query = grouped._compile_grouped(need)
    scalar_identity = scalar_query[0][2], dict(scalar_query[0][3])
    grouped_identity = grouped_query[0], dict(grouped_query[1])
    with composition._read_composition_transaction(database, budget) as (conn, snapshot):
        snapshot_id = snapshot["id"]
        composition._check_boundary(conn, budget, snapshot, snapshot_id)
        facts = kernel._execute_scope(conn, scope, scalar_query, LEARNINGOPS, snapshot_id, budget)
        composition._check_boundary(conn, budget, snapshot, snapshot_id)
        if not isinstance(facts, tuple) or len(facts) != 1 or not isinstance(facts[0], Fact):
            raise KernelError("incompatible_facts", "The independent whole amount is missing.")
        total = facts[0]
        all_amount_id = total.fact_id
        if (total.sql, total.parameters) != scalar_identity:
            raise KernelError("incompatible_facts", "The whole amount must use the independent unranked scope.")
        top = grouped._execute_grouped(conn, need, grouped_query, snapshot, budget)
        composition._check_boundary(conn, budget, snapshot, snapshot_id)
        _check_inputs(request, total, top, snapshot, snapshot_id)
        if (top.sql, top.parameters) != grouped_identity:
            raise KernelError("incompatible_facts", "The selection must use its complete bound top-k query.")
        subtotal = _selected_subtotal(top)
        share = _share_of_scope(subtotal, top, total, all_amount_id=all_amount_id)
        if not isinstance(share.fact_id, str) or not share.fact_id or share.fact_id in (
            top.fact_id, total.fact_id, subtotal.fact_id,
        ):
            raise KernelError("incompatible_facts", "Breakdown fact identities must be distinct.")
        slots = (
            BreakdownSlotResult("top_courses", top.fact_id, "checked"),
            BreakdownSlotResult("all_amount", total.fact_id, "checked"),
            BreakdownSlotResult("top_subtotal", subtotal.fact_id, subtotal.state, subtotal.reason),
            BreakdownSlotResult("share", share.fact_id, share.state, share.reason),
        )
        composition._check_boundary(conn, budget, snapshot, snapshot_id)
    composition._check_finalized_snapshot(snapshot, budget, snapshot_id)
    return BreakdownAnalysisPack(
        request, scope, (total,), (top,), (subtotal, share), slots, snapshot,
        kernel._runtime_evidence(), kernel._execution_evidence(budget),
        kernel._LIMITATIONS + (
            "Course top-k remains subset coverage even when its subtotal equals the whole amount.",
            "Denominator membership relies on independent scalar execution, not the subtotal inequality alone.",
            "All four slots are required; empty inputs yield failed data-condition coverage, not partial output.",
            "Calendar bounds use fixed UTC+08:00, not historical IANA/DST rules.",
            "Grouped counters are cumulative checkpoints; Breakdown counters cover the finalized batch.",
        ),
    )
