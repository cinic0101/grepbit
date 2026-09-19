"""Deterministic Overview with exact code binding in the composition snapshot."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Literal, Mapping

from . import composition, kernel
from .contracts import ExecutionLimits, Fact, FactRequest, KernelError
from .grouped import GroupedAmountFact, GroupedAmountRequest

_MAX_CENTER_CODE_BYTES = 64


@dataclass(frozen=True)
class OverviewRequest:
    center_code: str
    start: datetime
    end: datetime
    timezone: str

    def __post_init__(self) -> None:
        if not isinstance(self.center_code, str) or not 1 <= len(self.center_code) <= _MAX_CENTER_CODE_BYTES:
            raise KernelError("invalid_request", "Center code must contain 1 to 64 UTF-8 bytes.")
        try:
            size = len(self.center_code.encode("utf-8"))
        except UnicodeError as exc:
            raise KernelError("invalid_request", "Center code must be valid UTF-8 text.") from exc
        if size > _MAX_CENTER_CODE_BYTES:
            raise KernelError("invalid_request", "Center code must contain 1 to 64 UTF-8 bytes.")
        period = FactRequest(("confirmed_booked_amount",), self.start, self.end, self.timezone)
        GroupedAmountRequest(period, "booking_day")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> OverviewRequest:
        if not isinstance(data, Mapping) or set(data) != {"center_code", "start", "end", "timezone"}:
            raise KernelError("invalid_request", "Supply exactly center_code, start, end and timezone.")
        code = data["center_code"]
        if not isinstance(code, str):
            raise KernelError("invalid_request", "Center code must be text.")
        period = FactRequest.from_mapping({
            "metrics": ["confirmed_booked_amount"], "start": data["start"],
            "end": data["end"], "timezone": data["timezone"],
        })
        return cls(code, period.start, period.end, period.timezone)

    def to_dict(self) -> dict[str, object]:
        return {"center_code": self.center_code, "start": self.start.isoformat(),
                "end": self.end.isoformat(), "timezone": self.timezone}


@dataclass(frozen=True)
class OverviewCenterBinding:
    center_code: str
    center_id: str
    snapshot_id: str
    method: Literal["exact_unique_code"] = field(default="exact_unique_code", init=False)


@dataclass(frozen=True)
class OverviewSlotResult:
    slot_id: Literal["amount", "bookings", "seats", "daily_amount", "category_amounts"]
    role: Literal["required", "optional"]
    state: Literal["checked", "unavailable"]
    fact_id: str | None = None
    reason: Literal[
        "unsupported_source", "output_limit_exceeded", "component_timeout", "reconciliation_failed",
    ] | None = None


@dataclass(frozen=True)
class OverviewAnalysisPack:
    request: OverviewRequest
    binding: OverviewCenterBinding
    scope: FactRequest
    facts: tuple[Fact, ...]
    grouped_facts: tuple[GroupedAmountFact, ...]
    slots: tuple[OverviewSlotResult, ...]
    status: Literal["complete", "partial"]
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    checks: tuple[str, ...]
    recipe_id: str = field(default="overview", init=False)
    recipe_version: str = field(default="0.1", init=False)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["request"] = self.request.to_dict()
        result["scope"] = self.scope.to_dict()
        return result


def _bind_center_code(conn: sqlite3.Connection, code: str, snapshot: dict[str, str],
                      budget: kernel._Budget, snapshot_id: str) -> OverviewCenterBinding:
    composition._check_boundary(conn, budget, snapshot, snapshot_id)
    rows = conn.execute(
        "SELECT center_id FROM main.centers WHERE code=? LIMIT 2", (code,),
    ).fetchall()
    for _ in rows:
        budget.source_row()
    composition._check_boundary(conn, budget, snapshot, snapshot_id)
    if not rows:
        raise KernelError("unknown_entity", "Center code does not match a reviewed center.")
    if len(rows) != 1:
        raise KernelError("ambiguous_entity", "Center code matches more than one reviewed center.")
    center_id = rows[0][0]
    if not isinstance(center_id, str):
        raise KernelError("unsupported_source", "The matched center must have a canonical text ID.")
    return OverviewCenterBinding(code, center_id, snapshot_id)


def execute_overview(database: Path, request: OverviewRequest, *,
                     limits: ExecutionLimits = ExecutionLimits()) -> OverviewAnalysisPack:
    """Bind and execute overview@0.1; binding/required/global failures return no pack."""
    if not isinstance(request, OverviewRequest) or not isinstance(limits, ExecutionLimits):
        raise KernelError("invalid_request", "Use a typed OverviewRequest and trusted ExecutionLimits.")
    budget = kernel._Budget(limits)
    with composition._read_composition_transaction(database, budget) as (conn, snapshot):
        snapshot_id = snapshot["id"]
        binding = _bind_center_code(conn, request.center_code, snapshot, budget, snapshot_id)
        scope = FactRequest(composition._METRICS, request.start, request.end, request.timezone, binding.center_id)
        parts = composition._execute_in_transaction(conn, scope, snapshot, budget, snapshot_id)
    result = composition._finalize_composition(parts, snapshot, budget, snapshot_id)
    return OverviewAnalysisPack(
        request, binding, scope, result.facts, result.grouped_facts,
        tuple(OverviewSlotResult(slot.slot_id, slot.role, slot.state, slot.fact_id, slot.reason)
              for slot in result.slots),
        result.status, result.snapshot, result.runtime, result.execution,
        result.limitations + (
            "Center codes bind by exact unique match; names, IDs and fuzzy alternatives are not fallbacks.",
            "Overview calendar bounds and daily grouping use fixed UTC+08:00, not historical IANA/DST rules.",
        ),
        result.checks + ("exact_unique_center_code_binding",),
    )
