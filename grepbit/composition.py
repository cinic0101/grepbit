"""One private fixed required/optional composition shared by trusted entries."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
import sqlite3
from typing import Iterator, Literal

from . import grouped, kernel
from .catalog import LEARNINGOPS
from .contracts import ExecutionLimits, Fact, FactRequest, KernelError, utc_text
from .grouped import GroupedAmountFact, GroupedAmountRequest

_SlotId = Literal["amount", "bookings", "seats", "daily_amount", "category_amounts"]
_UnavailableReason = Literal[
    "unsupported_source", "output_limit_exceeded", "component_timeout", "reconciliation_failed",
]
_REQUIRED: tuple[tuple[_SlotId, str], ...] = (
    ("amount", "confirmed_booked_amount"),
    ("bookings", "confirmed_booking_count"),
    ("seats", "booked_seats"),
)
_OPTIONAL: tuple[tuple[_SlotId, str], ...] = (
    ("daily_amount", "booking_day"), ("category_amounts", "category"),
)
_METRICS = tuple(metric for _, metric in _REQUIRED)


class _ComponentTimeout(KernelError):
    """Trusted operational injection only; no component timer is implemented."""

    def __init__(self) -> None:
        super().__init__("component_timeout", "The optional component exceeded its local deadline.")


@dataclass(frozen=True)
class _CompositionSlot:
    slot_id: _SlotId
    role: Literal["required", "optional"]
    state: Literal["checked", "unavailable"]
    fact_id: str | None = None
    reason: _UnavailableReason | None = None


_CompositionParts = tuple[tuple[Fact, ...], tuple[GroupedAmountFact, ...], tuple[_CompositionSlot, ...]]


@dataclass(frozen=True)
class _CompositionResult:
    facts: tuple[Fact, ...]
    grouped_facts: tuple[GroupedAmountFact, ...]
    slots: tuple[_CompositionSlot, ...]
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    checks: tuple[str, ...] = (
        "fixed_required_coverage", "single_live_transaction_and_global_budget",
        "checked_optional_views_reconciled_to_required_amount",
    )

    @property
    def status(self) -> Literal["complete", "partial"]:
        return "partial" if any(slot.state == "unavailable" for slot in self.slots) else "complete"

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "status": self.status}


def _check_boundary(conn: sqlite3.Connection, budget: kernel._Budget,
                    snapshot: dict[str, str], snapshot_id: str) -> None:
    budget.check()
    if not conn.in_transaction or snapshot.get("id") != snapshot_id:
        raise KernelError("snapshot_lost", "The required analysis snapshot is no longer trustworthy.")
    conn.execute("SELECT 1").fetchone()
    budget.check()


def _check_required(facts: tuple[Fact, ...], scope: FactRequest, snapshot_id: str) -> None:
    if len(facts) != len(_REQUIRED) or any(not isinstance(fact, Fact) for fact in facts):
        raise KernelError("incompatible_facts", "The fixed required scalar core is incomplete.")
    identities = set()
    for fact, metric in zip(facts, _METRICS):
        binding = LEARNINGOPS.metrics[metric]
        if (fact.metric_id != metric or fact.catalog_id != LEARNINGOPS.version
                or fact.catalog_sha256 != LEARNINGOPS.digest() or fact.unit != binding.unit
                or fact.grain != kernel._GRAINS[binding.source]
                or fact.population != facts[0].population
                or fact.time_basis != "bookings.created_at_utc"
                or (fact.start_utc, fact.end_utc) != (utc_text(scope.start), utc_text(scope.end))
                or fact.business_timezone != scope.timezone
                or fact.filters != {"center_id": scope.center_id}
                or fact.snapshot_id != snapshot_id or fact.completeness != "complete"
                or fact.disclosures != binding.disclosures or fact.excluded_anonymous_rows is not None
                or not set(kernel._CHECKS) <= set(fact.checks)
                or not isinstance(fact.fact_id, str) or not fact.fact_id or fact.fact_id in identities):
            raise KernelError("incompatible_facts", "Required facts do not match their checked bound needs.")
        identities.add(fact.fact_id)
        if (type(fact.population_rows) is not int or fact.population_rows < 0
                or fact.empty_population is not (fact.population_rows == 0)
                or (fact.value is not None and (type(fact.value) is not int or not 0 <= fact.value < 2**63))
                or (not fact.empty_population and fact.value is None)
                or (fact.empty_population and
                    fact.value != (0 if metric == "confirmed_booking_count" else None))):
            raise KernelError("incompatible_facts", "Required scalar value and population evidence disagree.")
    if facts[0].population_rows != facts[2].population_rows:
        raise KernelError("incompatible_facts", "Required line-grain populations differ.")


def _reconciles(amount: Fact, fact: GroupedAmountFact, request: GroupedAmountRequest,
                snapshot: dict[str, str]) -> bool:
    axes = (
        "metric_id", "catalog_id", "catalog_sha256", "unit", "grain", "population",
        "time_basis", "start_utc", "end_utc", "business_timezone", "filters", "snapshot_id",
    )
    if (not isinstance(fact, GroupedAmountFact)
            or any(getattr(fact, axis) != getattr(amount, axis) for axis in axes)
            or fact.snapshot != snapshot or fact.dimension != request.dimension
            or fact.dimension_profile_id != grouped._DIMENSION_PROFILE
            or fact.coverage != "all_observed_groups" or fact.top_k is not None
            or fact.ordering != grouped._ORDERING[request.dimension]
            or not set(grouped._GROUP_CHECKS) <= set(fact.checks)
            or not isinstance(fact.fact_id, str) or not fact.fact_id
            or fact.empty_population is not (not fact.rows)):
        raise KernelError("incompatible_facts", "Optional fact semantics, coverage or snapshot are incompatible.")
    if request.dimension == "category" and (
        not fact.dimension_source_sha256 or "dimension_source_keys_and_relationships" not in fact.checks
    ):
        raise KernelError("incompatible_facts", "Category source admission evidence is missing.")
    if (len(fact.rows) > grouped._MAX_GROUP_ROWS
            or any(type(row.value) is not int or not 0 <= row.value < 2**63 for row in fact.rows)):
        raise KernelError("incompatible_facts", "Optional amount rows are not complete bounded integer evidence.")
    if amount.empty_population:
        return fact.empty_population and not fact.rows
    return not fact.empty_population and sum(row.value for row in fact.rows) == amount.value


def _execute_optional(conn: sqlite3.Connection, request: GroupedAmountRequest,
                      snapshot: dict[str, str], budget: kernel._Budget,
                      amount: Fact) -> GroupedAmountFact | _UnavailableReason:
    _check_boundary(conn, budget, snapshot, amount.snapshot_id)
    compiled = grouped._compile_grouped(request)
    try:
        extension_hash = grouped._validate_dimension_source(conn, request.dimension, budget)
    except KernelError as exc:
        if request.dimension != "category" or exc.code != "unsupported_source":
            raise
        _check_boundary(conn, budget, snapshot, amount.snapshot_id)
        return "unsupported_source"
    reason: _UnavailableReason
    try:
        fact = grouped._execute_grouped_query(
            conn, request, compiled, snapshot, budget, extension_hash,
        )
    except _ComponentTimeout:
        reason = "component_timeout"
    except KernelError as exc:
        if exc.code != "output_limit_exceeded":
            raise
        reason = "output_limit_exceeded"
    else:
        _check_boundary(conn, budget, snapshot, amount.snapshot_id)
        return fact if _reconciles(amount, fact, request, snapshot) else "reconciliation_failed"
    _check_boundary(conn, budget, snapshot, amount.snapshot_id)
    return reason


@contextmanager
def _read_composition_transaction(database: Path, budget: kernel._Budget) -> Iterator[
    tuple[sqlite3.Connection, dict[str, str]]
]:
    try:
        with kernel._read_transaction(database, budget) as opened:
            yield opened
    except sqlite3.Error as exc:
        raise KernelError("execution_failure", "The analysis connection could not complete or close safely.") from exc


def _execute_in_transaction(conn: sqlite3.Connection, scope: FactRequest,
                            snapshot: dict[str, str], budget: kernel._Budget,
                            snapshot_id: str) -> _CompositionParts:
    """Compose the fixed bound needs without opening or finalizing a transaction."""
    _check_boundary(conn, budget, snapshot, snapshot_id)
    amount_scope = replace(scope, metrics=("confirmed_booked_amount",))
    optional = tuple((slot, GroupedAmountRequest(amount_scope, dimension))
                     for slot, dimension in _OPTIONAL)
    compiled = kernel._compile_scope(scope, LEARNINGOPS)
    checked_groups = []
    facts = kernel._execute_scope(conn, scope, compiled, LEARNINGOPS, snapshot_id, budget)
    _check_boundary(conn, budget, snapshot, snapshot_id)
    _check_required(facts, scope, snapshot_id)
    identities = {fact.fact_id for fact in facts}
    slots = [_CompositionSlot(slot, "required", "checked", fact.fact_id)
             for (slot, _), fact in zip(_REQUIRED, facts)]
    for slot, request in optional:
        outcome = _execute_optional(conn, request, snapshot, budget, facts[0])
        _check_boundary(conn, budget, snapshot, snapshot_id)
        if isinstance(outcome, GroupedAmountFact):
            if outcome.fact_id in identities:
                raise KernelError("incompatible_facts", "Composition fact identities must be distinct.")
            identities.add(outcome.fact_id)
            checked_groups.append(outcome)
            slots.append(_CompositionSlot(slot, "optional", "checked", outcome.fact_id))
        else:
            slots.append(_CompositionSlot(slot, "optional", "unavailable", reason=outcome))
    _check_boundary(conn, budget, snapshot, snapshot_id)
    return facts, tuple(checked_groups), tuple(slots)


def _finalize_composition(parts: _CompositionParts, snapshot: dict[str, str],
                          budget: kernel._Budget, snapshot_id: str) -> _CompositionResult:
    """Materialize only after successful read-transaction exit."""
    budget.check()
    if snapshot.get("id") != snapshot_id:
        raise KernelError("snapshot_lost", "The completed analysis snapshot identity changed.")
    return _CompositionResult(
        *parts, snapshot,
        kernel._runtime_evidence(), kernel._execution_evidence(budget),
        kernel._LIMITATIONS + (
            "Fixed required/optional composition; callers cannot select slots or their roles.",
            "Optional gaps have only reviewed local causes; required/global failures return no result.",
            "Component timeout semantics are injected; general component timer mechanics are not implemented.",
            "Grouped execution counters are cumulative checkpoints; composition counters cover the whole batch.",
        ),
    )


def _execute_required_optional(database: Path, scope: FactRequest, *,
                               limits: ExecutionLimits = ExecutionLimits()) -> _CompositionResult:
    """Run only the fixed bound-center/month witness; required/global failures raise."""
    if (not isinstance(scope, FactRequest) or scope.metrics != _METRICS
            or scope.center_id is None or not isinstance(limits, ExecutionLimits)):
        raise KernelError("invalid_request", "Supply the fixed scalar core, canonical center and trusted limits.")
    GroupedAmountRequest(replace(scope, metrics=("confirmed_booked_amount",)), "booking_day")
    budget = kernel._Budget(limits)
    with _read_composition_transaction(database, budget) as (conn, snapshot):
        snapshot_id = snapshot["id"]
        parts = _execute_in_transaction(conn, scope, snapshot, budget, snapshot_id)
    return _finalize_composition(parts, snapshot, budget, snapshot_id)
