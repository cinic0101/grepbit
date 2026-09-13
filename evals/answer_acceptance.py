"""Opt-in, predeclared interpretation/value oracles; never an intent certifier.

Rules are trusted research annotations, like existing reference SQL. They are
prepared before planning. A matching compiled recipe prevents coincidental
values from legitimizing a different population. No arbitrary column dropping,
model judgment, legacy-score change or runtime dependency on this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grepbit.application.ask import AskResult, _describe
from grepbit.application.overlay import excluded_segments, named_segments
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import CompiledPlan, PlanError, QueryPlan
from grepbit.domain.schema_model import SchemaModel
from grepbit.ports.plan_compiler import PlanCompilerPort

POLICY_REVISION = "disclosed-answer-v1"


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Interpretation(Closed):
    id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    plan: QueryPlan
    reference_sql: str = Field(min_length=1)
    supplementary: list[str] = Field(default_factory=list)
    ordered: bool = False


class CaseRule(Closed):
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: str = Field(min_length=1)
    # Closed means the reviewer has explicitly ruled out unlisted readings.
    closed: bool = False
    refusal_only: bool = False
    interpretations: list[Interpretation] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_alternatives(self):
        if self.refusal_only == bool(self.interpretations):
            raise ValueError("acceptance_requires_answers_or_refusal_only")
        ids = [i.id for i in self.interpretations]
        if len(ids) != len(set(ids)):
            raise ValueError("acceptance_duplicate_interpretation")
        return self


class RuleFile(Closed):
    revision: Literal["disclosed-answer-v1"]
    cases: dict[str, CaseRule]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def context_digest(question, schema, overlay, as_of) -> str:
    """Bind question and effective semantic context, not a DB snapshot."""
    return _digest(
        {
            "revision": POLICY_REVISION,
            "question": question,
            "schema": schema.model_dump(mode="json"),
            "overlay": overlay.model_dump(mode="json") if overlay else None,
            "as_of": as_of.isoformat(),
        }
    )


def _canonical(plan: QueryPlan) -> QueryPlan:
    data = plan.model_dump(mode="json", exclude_none=True)
    used = {d.column for d in plan.dimensions} | {"period_start"}
    names = {}
    for index, (before, measure) in enumerate(zip(plan.measures, data["measures"])):
        alias = f"acceptance_measure_{index}"
        while alias in used:
            alias += "_"
        used.add(alias)
        names[before.output_name] = alias
        names[before.output_name + "_growth"] = alias + "_growth"
        measure["alias"] = alias
    for key, field in (("growth", "measure"), ("having", "field"), ("order", "field")):
        for item in data.get(key, []):
            item[field] = names.get(item[field], item[field])
    return QueryPlan.model_validate(data)


def _recipe(compiled: CompiledPlan) -> str:
    return _digest(compiled.compiled.model_dump(mode="json"))


def _values(rows: list[tuple], ordered: bool) -> list[tuple[str, ...]]:
    # Reuse the legacy cell/precision convention without its column projection
    # or unconditional row sorting. Import lazily to avoid runner import cycles.
    from evals.spike_tier0 import normalize_rows

    normalized = [normalize_rows([row])[0] for row in rows]
    return normalized if ordered else sorted(normalized)


@dataclass(frozen=True)
class Alternative:
    id: str
    evidence_id: str
    recipe: str
    columns: tuple[str, ...]
    supplementary_positions: tuple[int, ...]
    ordered: bool
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class PreparedCase:
    rule: CaseRule
    question: str
    compile: Callable[[QueryPlan], CompiledPlan]
    alternatives: tuple[Alternative, ...]
    context: Callable[[], str]


def prepare(
    rule: CaseRule,
    *,
    question: str,
    schema: SchemaModel,
    overlay: SemanticOverlay | None,
    as_of: datetime,
    compiler: PlanCompilerPort,
    reference: Callable[[str], list[tuple]],
) -> PreparedCase:
    def context():
        return context_digest(question, schema, overlay, as_of)

    if rule.context_sha256 != context():
        raise ValueError("acceptance_context_mismatch")
    exclusions = excluded_segments(question, overlay) if overlay else []
    named_ids = set(named_segments(question, overlay)) if overlay else set()
    named = [s for s in (overlay.segments if overlay else []) if s.id in named_ids]

    def compile_plan(plan):
        return compiler.compile(
            plan, as_of=as_of, exclude_segments=exclusions, named_segments=named
        )

    alternatives = []
    for spec in rule.interpretations:
        if spec.plan.limit is not None:
            raise ValueError("acceptance_limit_oracle_not_supported")
        if spec.plan.order and not spec.ordered:
            raise ValueError("acceptance_explicit_order_requires_ordered_oracle")
        compiled = compile_plan(spec.plan)
        recipe = _recipe(compile_plan(_canonical(spec.plan)))
        if any(a.recipe == recipe for a in alternatives):
            raise ValueError("acceptance_duplicate_recipe")
        columns = compiled.output_columns
        if len(set(spec.supplementary)) != len(spec.supplementary) or not set(
            spec.supplementary
        ) < set(columns):
            if spec.supplementary:
                raise ValueError("acceptance_invalid_supplementary_columns")
        rows = reference(spec.reference_sql)
        if any(len(row) != len(columns) for row in rows):
            raise ValueError("acceptance_reference_column_count")
        alternatives.append(
            Alternative(
                spec.id,
                spec.evidence_id,
                recipe,
                columns,
                tuple(columns.index(c) for c in spec.supplementary),
                spec.ordered,
                _values(rows, spec.ordered),
            )
        )
    return PreparedCase(
        rule.model_copy(deep=True), question, compile_plan, tuple(alternatives), context
    )


def grade(result: AskResult, prepared: PreparedCase) -> dict[str, Any]:
    """Hash/code-only audit result. Unknown readings are not silently called wrong."""
    rule = prepared.rule

    def verdict(outcome, reason, **extra):
        return {
            "policy_revision": POLICY_REVISION,
            "outcome": outcome,
            "reason": reason,
            "rule_evidence_id": rule.evidence_id,
            "rule_sha256": _digest(rule.model_dump(mode="json")),
            "context_sha256": rule.context_sha256,
            **extra,
        }

    if (
        prepared.context() != rule.context_sha256
        or result.question != prepared.question
    ):
        return verdict("unassessed", "context_mismatch")
    if rule.refusal_only:
        if result.status in {"clarify", "semantic_gap", "unsupported"}:
            return verdict("accepted", "appropriate_refusal")
        if result.status == "answered":
            return verdict("rejected", "answer_on_refusal_case")
        return verdict("unassessed", "not_answered")
    if result.status != "answered" or result.plan is None:
        return verdict("unassessed", "not_answered")
    if result.rows_truncated or result.plan.limit is not None:
        return verdict("unassessed", "bounded_result_not_supported")
    try:
        compiled = prepared.compile(result.plan)
        recipe = _recipe(prepared.compile(_canonical(result.plan)))
    except (PlanError, ValueError):
        return verdict("rejected", "invalid_plan")
    if result.sql != compiled.compiled.physical_sql or result.parameters != [
        {"name": p.name, "type": p.type_name, "value": p.value}
        for p in compiled.compiled.execution_parameters
    ]:
        return verdict("rejected", "execution_recipe_mismatch")
    expected = deepcopy(result)
    _describe(expected, compiled, result.question, result.base_repair, result.plan)
    if any(
        getattr(expected, key) != getattr(result, key)
        for key in ("interpretation", "assumptions", "lineage", "excluded_segments")
    ):
        return verdict("rejected", "disclosure_mismatch")
    columns = compiled.output_columns
    if any(set(row) != set(columns) for row in result.rows):
        return verdict("rejected", "output_columns_mismatch")
    matches = [a for a in prepared.alternatives if a.recipe == recipe]
    if not matches:
        return verdict(
            "rejected" if rule.closed else "unassessed", "unlisted_interpretation"
        )
    rows = [tuple(row[c] for c in columns) for row in result.rows]
    for alternative in matches:
        if _values(rows, alternative.ordered) == alternative.rows:
            return verdict(
                "accepted",
                "disclosed_reference_match",
                interpretation_id=alternative.id,
                value_evidence_id=alternative.evidence_id,
                oracle_sha256=_digest(alternative.rows),
                supplementary_output_positions=list(
                    alternative.supplementary_positions
                ),
            )
    return verdict("rejected", "value_mismatch")
