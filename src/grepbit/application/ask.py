"""One question, one governed answer: the orchestration the runner and the
callable surfaces share.

Deterministic gates run before the model (unsafe words, absent concepts,
per-period misread after the proposal), the planner proposes inside the
closed algebra, shape and base repairs fix form without guessing meaning,
the compiler owns the SQL, literals are checked and grounded, segments are
excluded by default, the policy re-parses the SQL, the executor runs it read
only, and the answer carries its verification level, assumptions, lineage
and parameters or a typed refusal. Nothing here imports an adapter.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from grepbit.application.grounding import Resolution, ValueIndex, resolve_plan_literals
from grepbit.application.literals import LiteralCheck, text_literal_checks
from grepbit.application.overlay import (
    excluded_segments,
    match_absent_concept,
    named_segments,
)
from grepbit.application.plan_repair import repair_base_table
from grepbit.application.shapes import (
    constant_dimensions,
    drop_dimensions,
    drop_grain,
    match_unsupported_shape,
    single_period_misread,
    unrequested_grain,
)
from grepbit.domain.language_pack import ShapePack
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import CompiledPlan, PlanError, PreviousTurn, QueryPlan
from grepbit.domain.schema_model import SchemaModel
from grepbit.ports.ask import (
    CONSTANT_DIMENSION_REPAIR,
    DATE_LITERAL_REPAIR,
    GRAIN_DROP_REPAIR,
    RELATIVE_WINDOW_REPAIR,
    LiteralCheckPort,
    PlannerPort,
    SqlPolicyPort,
    is_meaning_repair,
)
from grepbit.ports.grounding import GroundingModelError
from grepbit.ports.plan_compiler import PlanCompilerPort
from grepbit.ports.query_executor import QueryExecutorPort

ASK_REVISION = "ask-orchestration-v1"
REFUSALS = ("clarify", "semantic_gap", "unsupported", "unsafe")


@dataclass(frozen=True)
class AskSettings:
    as_of: datetime
    max_rows: int = 200
    statement_timeout_seconds: int = 10
    shape_gate: bool = True
    literal_check: bool = True
    grounding: bool = True


@dataclass
class AskServices:
    """Everything ask() needs for one datasource; the caller supplies adapters."""

    schema: SchemaModel
    planner: PlannerPort
    compiler: PlanCompilerPort
    policy: SqlPolicyPort
    executor: QueryExecutorPort
    literal_checker: LiteralCheckPort
    unsafe: Callable[[str], bool]
    overlay: SemanticOverlay | None = None
    shape_pack: ShapePack | None = None
    value_index: ValueIndex | None = None


@dataclass
class AskResult:
    """The served contract in one object; ``status`` is answered or a typed refusal."""

    question: str
    status: str
    reason: str | None = None
    clarification: str | None = None
    plan: QueryPlan | None = None
    sql: str | None = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    lineage: dict[str, Any] | None = None
    assumptions: list[str] = field(default_factory=list)
    interpretation: str | None = None
    verification: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int | None = None
    rows_truncated: bool = False
    warnings: list[str] = field(default_factory=list)
    question_values: list[dict[str, str]] = field(default_factory=list)
    grounding: list[Resolution] = field(default_factory=list)
    missing_literals: list[str] = field(default_factory=list)
    shape_repairs: list[str] = field(default_factory=list)
    grain_dropped: str | None = None
    # dimensions the plan's own equality filters fixed to one value, not returned
    constant_dimensions_dropped: list[str] = field(default_factory=list)
    base_repair: str | None = None
    excluded_segments: list[str] = field(default_factory=list)
    literal_checks: int = 0
    model_retries: int = 0
    # the model's text the first time it failed validation, kept even when the
    # repair turn then produced the plan, so a malformed plan can be classified
    raw_output: str | None = None
    # the repair turn's text when it failed too (status failed)
    raw_output_repair: str | None = None
    # 1 when the planner needed its repair turn
    model_repair_turns: int = 0
    elapsed_seconds: float = 0.0

    @property
    def refused(self) -> bool:
        return self.status in REFUSALS

    @property
    def shape_variants(self) -> list[str]:
        """Departures from the shown wire form that were rewritten: the contract's
        health metric."""
        return [r for r in self.shape_repairs if not is_meaning_repair(r)]

    @property
    def meaning_normalisations(self) -> list[str]:
        """Rules that changed what the plan means, each stated as an assumption."""
        return [r for r in self.shape_repairs if is_meaning_repair(r)]


def empty_result_warning(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "The query matched no rows; the window or filters select nothing."
    if len(rows) == 1 and all(v is None for v in rows[0].values()):
        return (
            "Every value is NULL: the aggregate ran over zero rows (the window or "
            "filters select nothing)."
        )
    return None


def negative_share_warning(plan: QueryPlan, rows: list[dict[str, Any]]) -> str | None:
    """A share below zero means the total is a net of positive and negative rows."""

    names = [m.output_name for m in plan.measures if m.share_of_total]
    negative = sorted(
        {
            name
            for row in rows
            for name in names
            if isinstance(row.get(name), (int, float)) and row[name] < 0
        }
    )
    if not negative:
        return None
    return (
        f"{', '.join(negative)} is negative for some groups: the total is the net of "
        "positive and negative rows, so those groups reduce it and the other shares "
        "are measured against the net."
    )


def _clarify_missing(result: AskResult, misses: list[LiteralCheck]) -> None:
    result.status = "clarify"
    result.reason = "filter_value_not_found"
    result.missing_literals = [f"{m.table}.{m.column} = {m.value!r}" for m in misses]
    result.clarification = (
        "No row matches "
        + "; ".join(result.missing_literals)
        + ". Check the spelling or give the stored value."
    )


def ask(
    question: str,
    services: AskServices,
    settings: AskSettings,
    *,
    previous: PreviousTurn | None = None,
    run_id: str = "ask",
) -> AskResult:
    started = time.monotonic()
    result = AskResult(question=question, status="not_run")
    overlay, index = (
        services.overlay,
        services.value_index if settings.grounding else None,
    )
    try:
        _ask(question, services, settings, previous, run_id, result, overlay, index)
    finally:
        result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result


def _record_planner_trace(result: AskResult, planner: Any) -> None:
    result.raw_output = getattr(planner, "last_raw_output", None)
    result.model_repair_turns = int(getattr(planner, "last_model_repair_turns", 0) or 0)


def _ask(question, services, settings, previous, run_id, result, overlay, index):
    if services.unsafe(question):
        result.status, result.reason = "unsafe", "unsafe_language"
        return
    absent = match_absent_concept(question, overlay) if overlay else None
    if absent is not None:
        result.status, result.reason = "semantic_gap", "absent_concept"
        result.clarification = absent.note
        return
    pack = services.shape_pack if settings.shape_gate else None
    shape = match_unsupported_shape(question, pack) if pack else None
    if shape is not None:
        result.status, result.reason = "unsupported", f"unsupported_shape:{shape[0].id}"
        result.clarification = shape[0].clarification
        return

    hints = index.mentions(question) if index is not None else []
    result.question_values = [{"column": m.column, "value": m.value} for m in hints]
    proposal = None
    for attempt in range(2):
        try:
            proposal = services.planner.propose(
                question,
                services.schema,
                as_of=settings.as_of.isoformat(),
                overlay=overlay,
                previous=previous,
                question_values=result.question_values or None,
            )
            break
        except GroundingModelError as error:
            if error.code != "model_call_failed" or attempt == 1:
                result.status, result.reason = "failed", error.code
                _record_planner_trace(result, services.planner)
                if error.code == "invalid_structured_output":
                    result.raw_output_repair = getattr(
                        services.planner, "last_repair_output", None
                    )
                return
            result.model_retries = attempt + 1
    assert proposal is not None
    _record_planner_trace(result, services.planner)
    result.shape_repairs = list(getattr(services.planner, "last_repairs", []) or [])
    if proposal.decision == "none":
        result.status = {"ambiguous": "clarify"}.get(proposal.reason, proposal.reason)
        result.reason, result.clarification = proposal.reason, proposal.clarification
        return
    assert proposal.plan is not None
    plan, base_repair = repair_base_table(proposal.plan, services.schema, overlay)
    result.plan, result.base_repair = plan, base_repair
    if pack is not None:
        misread = single_period_misread(question, plan, pack)
        if misread is not None:
            result.status, result.reason = "clarify", "per_period_single_window"
            result.clarification = pack.period_clarification
            return
        grain = unrequested_grain(question, plan, pack)
        if grain is not None:
            plan = drop_grain(plan)
            result.plan = plan
            result.shape_repairs.append(
                f"{GRAIN_DROP_REPAIR} {grain}: no per-period word"
            )
            result.grain_dropped = grain
    constants = constant_dimensions(plan)
    if constants:
        plan = drop_dimensions(plan, constants)
        result.plan = plan
        result.constant_dimensions_dropped = constants
        result.shape_repairs.append(
            f"{CONSTANT_DIMENSION_REPAIR}: " + ", ".join(constants)
        )

    exclusions = excluded_segments(question, overlay) if overlay else []
    named_ids = set(named_segments(question, overlay)) if overlay else set()
    named = [s for s in (overlay.segments if overlay else []) if s.id in named_ids]

    def compile_plan(current: QueryPlan) -> CompiledPlan:
        compiled = services.compiler.compile(
            current,
            as_of=settings.as_of,
            exclude_segments=exclusions,
            named_segments=named,
        )
        services.policy.assert_safe_select_statement(compiled.compiled.physical_sql)
        return compiled

    try:
        compiled = compile_plan(plan)
    except PlanError as error:
        result.status, result.reason = "unsupported", f"plan_{error.code}"
        result.clarification = error.detail
        return
    except ValueError as error:
        result.status, result.reason = "unsafe", f"policy:{error}"
        return

    checks = (
        text_literal_checks(plan, services.schema) if settings.literal_check else []
    )
    result.literal_checks = len(checks)
    misses = list(services.literal_checker(checks)) if checks else []
    if misses and index is not None:
        resolved, resolutions = resolve_plan_literals(
            plan, [(f"{m.table}.{m.column}", m.value) for m in misses], index
        )
        result.grounding = resolutions
        if resolved is not plan:
            plan = resolved
            result.plan = plan
            try:
                compiled = compile_plan(plan)
            except (PlanError, ValueError) as error:
                result.status, result.reason = "unsupported", f"plan_{error}"
                return
            checks = text_literal_checks(plan, services.schema)
            misses = list(services.literal_checker(checks)) if checks else []
        ambiguous = [r for r in resolutions if r.kind == "ambiguous"]
        if misses and ambiguous:
            result.status, result.reason = "clarify", "filter_value_ambiguous"
            result.clarification = "; ".join(
                f"{r.column}: did you mean "
                + ", ".join(f"'{c.value}'" for c in r.candidates)
                + f" for '{r.literal}'?"
                for r in ambiguous
            )
            return
    _describe(result, compiled, question, base_repair, plan)
    if misses:
        _clarify_missing(result, misses)
        return

    execution = services.executor.execute(
        compiled.compiled,
        max_rows=settings.max_rows,
        preview_rows=settings.max_rows,
        statement_timeout_seconds=settings.statement_timeout_seconds,
        run_id=run_id,
    )
    if execution.error_code is not None:
        result.status, result.reason = "failed", execution.error_code
        return
    result.status = "answered"
    result.rows = [dict(r) for r in execution.rows]
    result.row_count, result.rows_truncated = execution.row_count, execution.truncated
    for warning in (
        empty_result_warning(result.rows),
        negative_share_warning(plan, result.rows),
    ):
        if warning:
            result.warnings.append(warning)


def _describe(result, compiled, question, base_repair, plan) -> None:
    result.sql = compiled.compiled.physical_sql
    result.parameters = [
        {"name": p.name, "type": p.type_name, "value": p.value}
        for p in compiled.compiled.execution_parameters
    ]
    result.lineage = compiled.lineage.as_dict()
    result.interpretation = compiled.interpretation
    result.verification = compiled.verification
    result.excluded_segments = list(compiled.applied_segments)
    result.assumptions = [a.text for a in compiled.assumptions]
    if base_repair:
        result.assumptions.append(
            "The base table was moved to the table holding the measure columns "
            f"({base_repair}); the grouping and filters are unchanged."
        )
    for column in result.constant_dimensions_dropped:
        result.assumptions.append(
            f"{column} is not returned as a column: the question fixes it to one "
            "value, so it would repeat on every row; the filter still applies."
        )
    if result.grain_dropped:
        result.assumptions.append(
            f"Values are totals over the whole window, not per {result.grain_dropped}; "
            "the question named no period, say 每月 (or 每天, 每週) for a breakdown."
        )
    for repair in result.shape_repairs:
        if repair.startswith(DATE_LITERAL_REPAIR):
            result.assumptions.append(
                "A month, day or year was written as a filter value on a date "
                f"column ({repair}); it was read as that time window, the only "
                "reading such a literal has."
            )
        if repair.startswith(RELATIVE_WINDOW_REPAIR):
            result.assumptions.append(
                "The relative window was written as starting today and running "
                f"forward ({repair}); it was read as the same number of complete "
                "units before as_of, the only reading with data."
            )
    used = {str(v) for f in plan.filters for v in f.values if isinstance(v, str)}
    result.assumptions += [
        f"The question's wording was matched to the stored value '{h['value']}' of "
        f"{h['column']} (spaces, case or punctuation differ); give the exact value to "
        "override."
        for h in result.question_values
        if h["value"] in used and h["value"] not in question
    ]
    result.assumptions += [
        f"'{r.literal}' was read as the stored value '{r.value}' of {r.column} "
        f"(similarity {r.candidates[0].score}); give the exact value to override."
        for r in result.grounding
        if r.kind == "unique"
    ]
