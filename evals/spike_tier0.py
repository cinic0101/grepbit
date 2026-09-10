#!/usr/bin/env python3
"""Tier-0 generalization spike: introspect, plan with the model, compile, run.

  export GREPBIT_SPIKE_DSN=postgresql://ro_role:...@host/db      # read-only role
  .venv/bin/python evals/spike_tier0.py --dsn-env GREPBIT_SPIKE_DSN \
      --datasource-id iot_spike --cases evals/cases/tier0/iot.yaml \
      --output <dir>/iot.json [--live]

Without --live the runner introspects, compiles every case's reference SQL,
and reports the schema summary only. With --live it asks the GREPBIT_MODEL_*
classifier for a plan per question, compiles and executes it through the SQL
policy and the read-only executor, and compares the rows with the reference
SQL. Reports carry statuses, lineage, latencies, and mismatch categories; no
credentials.

A case without ``expected`` is judged by a human instead of a reference: the
runner marks it ``correct: null``, ``--review-sheet`` writes one readable page
per case (with rows) for the judge, ``--verdicts`` writes the skeleton the
judge fills, and ``evals/tally_verdicts.py`` turns the filled skeleton into
the four stage-2 numbers. ``--redact-rows`` keeps result rows out of the JSON
report so an artifact of a real database can be kept under version control.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    PLAN_PROMPT_REVISION,
    ChatCompletionsPlanClient,
)
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.postgres.executor import PsycopgQueryExecutor
from grepbit.adapters.postgres.introspect import infer_foreign_keys, introspect_schema
from grepbit.adapters.postgres.value_check import missing_literals
from grepbit.adapters.postgres.value_index import load_column_values
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.application.active_queries import ActiveQueryRegistry
from grepbit.application.ask import AskServices, AskSettings, ask
from grepbit.application.grounding import ValueIndex
from grepbit.application.overlay import (
    overlay_problems,
)
from grepbit.application.policies import PROPOSER_REVISION, propose_policies
from grepbit.domain.grounding import normalize_question
from grepbit.domain.plan import PreviousTurn, QueryPlan

ROOT = Path(__file__).resolve().parents[1]
# Language-pack style policy list; deliberately catalog independent.
UNSAFE_PATTERNS = (
    "delete",
    "drop",
    "truncate",
    "insert",
    "update",
    "alter",
    "grant",
    "pg_sleep",
    "刪除",
    "清空",
    "刪掉",
)


def load_cases(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
        raise ValueError("tier0_cases_invalid")
    return document


def unsafe(question: str) -> bool:
    normalized = normalize_question(question)
    return any(
        re.search(rf"(?<![a-z0-9_]){re.escape(p)}(?![a-z0-9_])", normalized)
        if p.isascii()
        else p in normalized
        for p in UNSAFE_PATTERNS
    )


def normalize_rows(rows: list[dict[str, Any]] | list[tuple]) -> list[tuple[str, ...]]:
    def cell(value: Any) -> str:
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal("0.0001")).normalize(), "f")
        if isinstance(value, float):
            return format(
                Decimal(str(value)).quantize(Decimal("0.0001")).normalize(), "f"
            )
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return "NULL" if value is None else str(value)

    normalized = []
    for row in rows:
        values = row.values() if isinstance(row, dict) else row
        normalized.append(tuple(cell(v) for v in values))
    return sorted(normalized)


def perturb_schema(schema, kind: str):
    """Reorder what the planner sees without changing what it means.

    A plan that flips under a reordering was chosen for the order, not the
    question; the compiler and the references are untouched, so a flip shows
    up as a changed plan core or a wrong answer against the same reference.
    """

    import random

    tables = list(schema.tables)
    if kind == "tables_reversed":
        tables = tables[::-1]
    elif kind == "tables_shuffled":
        random.Random(20260910).shuffle(tables)
    elif kind == "columns_reversed":
        tables = [t.model_copy(update={"columns": t.columns[::-1]}) for t in tables]
    return schema.model_copy(update={"tables": tables})


def report_detail(result) -> dict[str, Any]:
    """Map an AskResult onto the report's historical keys (no bound values)."""

    detail: dict[str, Any] = {}
    if result.reason:
        detail["reason"] = result.reason
    if result.clarification:
        detail["clarification"] = result.clarification
    if result.plan is not None:
        detail["plan"] = result.plan.model_dump(mode="json", exclude_none=True)
    if result.shape_repairs:
        detail["shape_repairs"] = list(result.shape_repairs)
    if result.base_repair:
        detail["base_repair"] = result.base_repair
    if result.question_values:
        detail["question_values"] = list(result.question_values)
    if result.sql is not None:
        detail["sql"] = result.sql
        detail["lineage"] = result.lineage
        detail["interpretation"] = result.interpretation
        detail["assumptions"] = list(result.assumptions)
        detail["verification"] = result.verification
        detail["excluded_segments"] = list(result.excluded_segments)
        detail["literal_checks"] = result.literal_checks
    if result.grounding:
        detail["grounding"] = [g.model_dump(mode="json") for g in result.grounding]
    if result.missing_literals:
        detail["missing_literals"] = list(result.missing_literals)
    if result.model_retries:
        detail["model_retries"] = result.model_retries
    if result.status == "answered":
        detail["row_count"] = result.row_count
        detail["rows_truncated"] = result.rows_truncated
        if result.warnings:
            detail["warnings"] = list(result.warnings)
        detail["rows"] = [
            {k: (str(v) if not isinstance(v, (int, str)) else v) for k, v in r.items()}
            for r in result.rows[:20]
        ]
    return detail


class _Skip(Exception):
    """Leave the compile-and-execute block after a deterministic clarify."""


_ROW_FIELDS = ("rows", "reference_rows")
VERDICTS = (
    "correct",
    "wrong_exposed",
    "wrong_silent",
    "refusal_ok",
    "refusal_bad",
    "unsure",
)


def empty_result_warning(rows: Any) -> str | None:
    """A deterministic note when an answer carries no data.

    No rows, or a single row whose measure columns are all NULL (an aggregate
    over zero rows), is reported as an answer but usually means the window or
    filters matched nothing; the note travels with the answer so the caller does
    not read NULL as a number.
    """

    rows = list(rows)
    if not rows:
        return "The query matched no rows; the window or filters select nothing."
    if len(rows) == 1 and all(v is None for v in rows[0].values()):
        return (
            "Every value is NULL: the aggregate ran over zero rows (the window or "
            "filters select nothing)."
        )
    return None


def redact_rows(result: dict[str, Any]) -> dict[str, Any]:
    """Drop every cell value from a result row; counts and SQL stay."""

    return {k: v for k, v in result.items() if k not in _ROW_FIELDS}


def review_sheet(summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    """One readable page per case for a human judge. Holds rows: keep out of git."""

    lines = [
        f"# Review sheet: {summary['datasource_id']}",
        "",
        f"- cases: `{summary['cases_file']}`, as_of {summary['as_of']}, "
        f"prompt {summary['prompt_revision']}",
        f"- {summary['cases']} cases, statuses {summary['status_counts']}, "
        f"P50 {summary['p50_seconds']} s, P95 {summary['p95_seconds']} s",
        "- verdicts: " + ", ".join(VERDICTS),
        "",
    ]
    for index, r in enumerate(results, 1):
        lines += [
            f"## {index}. {r['case_id']}",
            "",
            f"**Question**: {r['question']}",
            "",
        ]
        if r.get("follow_up_of"):
            lines += [f"**Follow-up of**: {r['follow_up_of']}", ""]
        verification = f" ({r['verification']})" if r.get("verification") else ""
        lines += [
            f"**Status**: {r['status']}{verification}, {r['elapsed_seconds']} s",
            "",
        ]
        if r.get("reason"):
            lines += [f"**Reason**: {r['reason']}", ""]
        if r.get("clarification"):
            lines += [f"**Clarification**: {r['clarification']}", ""]
        if r.get("interpretation"):
            lines += [f"**Interpretation**: {r['interpretation']}", ""]
        if r.get("assumptions"):
            lines += ["**Assumptions**:", *(f"- {a}" for a in r["assumptions"]), ""]
        if r.get("sql"):
            lines += ["**SQL**:", "", "```sql", r["sql"], "```", ""]
        if r.get("rows") is not None:
            rows = r["rows"]
            lines.append(
                f"**Rows** ({len(rows)} shown of {r.get('row_count', len(rows))}):"
            )
            lines.append("")
            if rows:
                columns = list(rows[0].keys())
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("|" + "---|" * len(columns))
                lines += [
                    "| " + " | ".join(str(row.get(c, "")) for c in columns) + " |"
                    for row in rows
                ]
            else:
                lines.append("(no rows)")
            lines.append("")
    return "\n".join(lines)


def verdict_skeleton(report: Path, results: list[dict[str, Any]]) -> str:
    """YAML the judge fills: one verdict per case, read back by tally_verdicts.py."""

    document = {
        "report": str(report),
        "verdict_values": list(VERDICTS),
        "verdicts": [
            {
                "case_id": r["case_id"],
                "question": r["question"],
                "status": r["status"],
                "verdict": None,
                "note": "",
            }
            for r in results
        ],
    }
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn-env", required=True)
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--infer-joins", action="store_true")
    parser.add_argument("--verify-coverage", action="store_true")
    parser.add_argument("--overlay", type=Path)
    parser.add_argument(
        "--enum-distinct-limit",
        type=int,
        default=20,
        help="distinct values sampled per non-key text column; 0 disables sampling",
    )
    parser.add_argument(
        "--no-shape-gate",
        action="store_true",
        help="ablation: do not refuse share/growth shapes before the model call",
    )
    parser.add_argument(
        "--no-literal-check",
        action="store_true",
        help="ablation: do not check eq/in text literals against the column",
    )
    parser.add_argument(
        "--perturb",
        choices=["tables_reversed", "columns_reversed", "tables_shuffled"],
        help="metamorphic perturbation of the schema payload (meaning unchanged)",
    )
    parser.add_argument(
        "--no-grounding",
        action="store_true",
        help="ablation: no value index, no question hints, no literal resolution",
    )
    parser.add_argument(
        "--propose-policies",
        type=Path,
        help=(
            "write deterministic column-policy proposals (a draft the runtime "
            "never loads) and continue"
        ),
    )
    parser.add_argument(
        "--redact-rows",
        action="store_true",
        help="keep result and reference rows out of the JSON report (real data)",
    )
    parser.add_argument(
        "--review-sheet",
        type=Path,
        help="write a readable page per case, rows included, for a human judge",
    )
    parser.add_argument(
        "--verdicts",
        type=Path,
        help="write the verdict skeleton (YAML) the judge fills in",
    )
    arguments = parser.parse_args(argv)

    import psycopg

    dsn = os.environ.get(arguments.dsn_env)
    if not dsn:
        print(f"SPIKE_BLOCKED code=dsn_env_missing env={arguments.dsn_env}")
        return 2

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection

    document = load_cases(arguments.cases)
    as_of = datetime.fromisoformat(document["as_of"])
    started_intro = time.monotonic()
    schema = introspect_schema(
        connect,
        datasource_id=arguments.datasource_id,
        enum_distinct_limit=arguments.enum_distinct_limit,
    )
    if arguments.infer_joins:
        schema = infer_foreign_keys(connect, schema)
    if arguments.perturb:
        schema = perturb_schema(schema, arguments.perturb)
    introspection_seconds = round(time.monotonic() - started_intro, 3)
    inferred_keys = [fk.id for fk in schema.foreign_keys if fk.inferred]
    if inferred_keys:
        print("inferred joins:", *inferred_keys, sep="\n  ")
    if arguments.propose_policies is not None:
        proposals = propose_policies(schema)
        arguments.propose_policies.parent.mkdir(parents=True, exist_ok=True)
        arguments.propose_policies.write_text(
            json.dumps(
                {
                    "datasource_id": arguments.datasource_id,
                    "proposer": PROPOSER_REVISION,
                    "note": "draft; copy approved entries into the datasource overlay",
                    "column_policies": [
                        p.model_dump(mode="json", exclude_none=True) for p in proposals
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"policy proposals: {len(proposals)} -> {arguments.propose_policies}")
    overlay = None
    if arguments.overlay is not None:
        overlay = load_semantic_overlay(arguments.overlay)
        problems = overlay_problems(overlay, schema)
        if problems:
            print("SPIKE_BLOCKED code=overlay_invalid", *problems, sep="\n  ")
            return 2
        print(
            f"overlay {overlay.revision}: {len(overlay.metrics)} metrics, "
            f"{len(overlay.absent_concepts)} absent concepts, "
            f"{len(overlay.column_aliases)} aliased columns"
        )
    shape_pack = None if arguments.no_shape_gate else load_shape_pack()
    index: ValueIndex | None = None
    index_skipped: list[str] = []
    if overlay is not None and not arguments.no_grounding:
        groundable = overlay.groundable_columns()
        if groundable:
            values, index_skipped = load_column_values(connect, schema, groundable)
            index = ValueIndex(values)
            print(
                f"value index: {len(index.columns)} columns, {index.size()} values"
                + (
                    f", skipped for size: {', '.join(index_skipped)}"
                    if index_skipped
                    else ""
                )
            )
    compiler = PlanCompiler(schema, overlay=overlay)
    policy = PostgresSqlPolicy(
        tables=frozenset(t.name for t in schema.tables),
        functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
    )
    executor = PsycopgQueryExecutor(
        connection_factory=connect, active_queries=ActiveQueryRegistry()
    )
    client = None
    if arguments.live:
        settings = GroundingModelSettings.from_environment()
        client = ChatCompletionsPlanClient(settings)

    def reference_rows(sql: str) -> list[tuple[str, ...]]:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '10s'")
                cursor.execute(sql)
                return normalize_rows(cursor.fetchall())

    results: list[dict[str, Any]] = []
    answered_plans: dict[str, tuple[str, QueryPlan]] = {}
    ask_settings = AskSettings(
        as_of=as_of,
        max_rows=1000,  # evaluation fetches whole results for reference comparison
        statement_timeout_seconds=10,
        shape_gate=not arguments.no_shape_gate,
        literal_check=not arguments.no_literal_check,
        grounding=not arguments.no_grounding,
    )
    services = (
        AskServices(
            schema=schema,
            planner=client,
            compiler=compiler,
            policy=policy,
            executor=executor,
            literal_checker=lambda checks: missing_literals(
                connect, schema.schema_name, checks
            ),
            unsafe=unsafe,
            overlay=overlay,
            shape_pack=shape_pack,
            value_index=index,
        )
        if client is not None
        else None
    )
    if arguments.verify_coverage:
        print("coverage audit: not available on the ask core; flag ignored")
    for case in document["cases"]:
        question = case["question"]
        previous = None
        if case.get("follow_up_of") in answered_plans:
            prior_question, prior_plan = answered_plans[case["follow_up_of"]]
            previous = PreviousTurn(question=prior_question, plan=prior_plan)
        # No expected status: a human judges the case from the review sheet.
        expected = (case.get("expected") or {}).get("status")
        accepted = set(case.get("accept_statuses", [expected] if expected else []))
        row: dict[str, Any] = {
            "case_id": case["case_id"],
            "question": question,
            "expected_status": expected,
            "accepted_statuses": sorted(accepted),
            "follow_up_of": case.get("follow_up_of"),
        }
        detail: dict[str, Any] = {}
        if services is None:
            status, elapsed = "not_run", 0.0
        else:
            result = ask(
                question,
                services,
                ask_settings,
                previous=previous,
                run_id=f"spike-{case['case_id']}",
            )
            status, elapsed = result.status, result.elapsed_seconds
            detail = report_detail(result)
            if result.plan is not None:
                answered_plans[case["case_id"]] = (question, result.plan)
            if status == "answered" and "reference_sql" in case:
                actual = normalize_rows(result.rows)
                references = [
                    reference_rows(sql)
                    for sql in (
                        case["reference_sql"],
                        *case.get("reference_sql_alternatives", []),
                    )
                ]
                matched = next(
                    (i for i, r in enumerate(references) if r == actual), None
                )
                detail["rows_match_reference"] = matched is not None
                detail["matched_reference_index"] = matched
                if matched is None:
                    detail["reference_rows"] = references[0][:10]
        detail["status_without_coverage"] = status
        if status == "answered":
            detail.setdefault("verification", "unverified_semantics")
        correct: bool | None
        if expected is None:
            correct = None
        else:
            correct = status in accepted and (
                status != "answered" or detail.get("rows_match_reference", True)
            )
        row.update(
            {"status": status, "correct": correct, "elapsed_seconds": elapsed, **detail}
        )
        results.append(row)
        marker = "?? " if correct is None else ("OK " if correct else "XX ")
        reason = detail.get("reason") or ""
        print(
            f"{marker}{case['case_id']:36} {expected or '(judge)':12}->{status:12} "
            f"{elapsed:5.1f}s {reason}"
        )

    judged = [r for r in results if r["expected_status"] is not None]
    answerable = [r for r in judged if r["expected_status"] == "answered"]
    refusals = [r for r in judged if r["expected_status"] != "answered"]
    latencies = sorted(
        r["elapsed_seconds"]
        for r in results
        if r["status"] not in {"not_run", "unsafe"}
    ) or [0.0]
    summary = {
        "datasource_id": arguments.datasource_id,
        "cases_file": str(arguments.cases),
        "prompt_revision": PLAN_PROMPT_REVISION if arguments.live else None,
        "output_mode": client.settings.structured_output_mode if client else None,
        "overlay_revision": overlay.revision if overlay is not None else None,
        "perturbation": arguments.perturb,
        "as_of": as_of.isoformat(),
        "cases": len(results),
        "judged": len(judged),
        "unjudged": len(results) - len(judged),
        "correct": sum(1 for r in judged if r["correct"]),
        "answerable_correct": sum(r["correct"] for r in answerable),
        "answerable_total": len(answerable),
        "answered_but_wrong_rows": sum(
            1
            for r in answerable
            if r["status"] == "answered" and not r.get("rows_match_reference", True)
        ),
        "refusals_correct": sum(1 for r in refusals if r["correct"]),
        "refusals_total": len(refusals),
        "false_answers_on_refusal_cases": sum(
            1 for r in refusals if r["status"] == "answered"
        ),
        "model_failures": sum(1 for r in results if r["status"] == "failed"),
        "model_retries": sum(r.get("model_retries", 0) for r in results),
        "p50_seconds": latencies[len(latencies) // 2],
        "p95_seconds": latencies[
            min(len(latencies) - 1, int(round(0.95 * (len(latencies) - 1))))
        ],
        "introspection_seconds": introspection_seconds,
        "schema": {
            "tables": len(schema.tables),
            "columns": sum(len(t.columns) for t in schema.tables),
            "foreign_keys": len(schema.foreign_keys) - len(inferred_keys),
            "inferred_foreign_keys": inferred_keys,
            "enum_distinct_limit": arguments.enum_distinct_limit,
            "sampled_columns": sum(
                1
                for t in schema.tables
                for c in t.columns
                if c.sample_values and not c.is_enum
            ),
            "enum_columns": sum(
                1 for t in schema.tables for c in t.columns if c.is_enum
            ),
        },
        "status_counts": {
            name: sum(1 for r in results if r["status"] == name)
            for name in sorted({r["status"] for r in results})
        },
        "rows_redacted": arguments.redact_rows,
        "incorrect_case_ids": [r["case_id"] for r in judged if not r["correct"]],
        "verification_counts": {
            level: sum(1 for r in results if r.get("verification") == level)
            for level in ("verified", "partially_verified", "unverified_semantics")
        },
        "shape_repairs": sum(1 for r in results if r.get("shape_repairs")),
        "base_repairs": sum(1 for r in results if r.get("base_repair")),
        # Which compile-time refusals recur decides the next deterministic repair.
        "plan_error_counts": {
            code: sum(1 for r in results if r.get("reason") == code)
            for code in sorted(
                {
                    r["reason"]
                    for r in results
                    if str(r.get("reason") or "").startswith("plan_")
                }
            )
        },
        "zero_call_refusals": sum(
            1
            for r in results
            if r["status"] == "unsafe"
            or r.get("reason") == "absent_concept"
            or str(r.get("reason") or "").startswith("unsupported_shape:")
        ),
        "shape_gate_refusals": sum(
            1
            for r in results
            if str(r.get("reason") or "").startswith("unsupported_shape:")
        ),
        "per_period_clarifies": sum(
            1 for r in results if r.get("reason") == "per_period_single_window"
        ),
        "literal_checks": sum(r.get("literal_checks", 0) for r in results),
        "literal_misses": sum(1 for r in results if r.get("missing_literals")),
        "grounding": {
            "columns": index.columns if index is not None else [],
            "values": index.size() if index is not None else 0,
            "skipped_for_size": index_skipped,
            "hinted_cases": sum(1 for r in results if r.get("question_values")),
            "resolved_cases": sum(
                1
                for r in results
                if any(g["kind"] == "unique" for g in r.get("grounding") or [])
            ),
            "ambiguous_cases": sum(
                1 for r in results if r.get("reason") == "filter_value_ambiguous"
            ),
        },
        "empty_result_warnings": sum(
            1
            for r in results
            if any("select" in w and "nothing" in w for w in r.get("warnings") or [])
        ),
        "negative_share_warnings": sum(
            1
            for r in results
            if any("is negative for some groups" in w for w in r.get("warnings") or [])
        ),
        "segment_exclusions": sum(1 for r in results if r.get("excluded_segments")),
    }
    if arguments.verify_coverage:
        flagged = [
            r
            for r in results
            if r.get("status_without_coverage") == "answered"
            and (r.get("coverage") or {}).get("uncovered")
        ]
        summary["coverage"] = {
            "audited": sum(1 for r in results if "coverage" in r),
            "flagged_case_ids": [r["case_id"] for r in flagged],
            "false_flags": [
                r["case_id"]
                for r in flagged
                if r["expected_status"] == "answered"
                and r.get("rows_match_reference", True)
            ],
            "planner_drops": [
                r["case_id"]
                for r in results
                if r["expected_status"] != "answered"
                and r.get("status_without_coverage") == "answered"
            ],
            "drops_caught": [
                r["case_id"] for r in flagged if r["expected_status"] != "answered"
            ],
            "audit_p95_seconds": (
                sorted(
                    r["coverage"]["seconds"]
                    for r in results
                    if r.get("coverage", {}).get("seconds") is not None
                )
                or [0.0]
            )[-1],
        }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    reported = [redact_rows(r) for r in results] if arguments.redact_rows else results
    arguments.output.write_text(
        json.dumps(
            {"summary": summary, "results": reported},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    if arguments.review_sheet is not None:
        arguments.review_sheet.parent.mkdir(parents=True, exist_ok=True)
        arguments.review_sheet.write_text(
            review_sheet(summary, results), encoding="utf-8"
        )
    if arguments.verdicts is not None:
        arguments.verdicts.parent.mkdir(parents=True, exist_ok=True)
        arguments.verdicts.write_text(
            verdict_skeleton(arguments.output, results), encoding="utf-8"
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
