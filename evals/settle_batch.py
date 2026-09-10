#!/usr/bin/env python3
"""Turn a judged run into a regression case file.

  .venv/bin/python evals/settle_batch.py --report <run.json> --verdicts <filled.yaml> \
      --cases <judged.yaml> --dsn-env <ENV> --datasource-id <id> \
      [--overlay <overlay.json>] [--enum-distinct-limit N] --output <batch.yaml>

For every case judged ``correct`` the plan recorded in the report is
recompiled against the current schema and overlay (it must reproduce the
judged SQL exactly) and the bound values are inlined into a reference SQL.
Cases judged ``refusal_ok`` become refusal cases accepting any typed refusal.
Cases judged wrong, ``refusal_bad`` or ``unsure`` are left out and listed, so
the batch only ever pins what a human accepted. The references are the
system's own output judged correct: a regression guard, not an independent
truth, and the header of the file says so.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.postgres.introspect import introspect_schema
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.overlay import excluded_segments, named_segments
from grepbit.domain.models import QueryParameter
from grepbit.domain.plan import QueryPlan

REFUSALS = ["semantic_gap", "clarify", "unsupported"]


def sql_literal(parameter: QueryParameter) -> str:
    value, type_name = parameter.value, parameter.type_name
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    if type_name in {"timestamptz", "date", "numeric", "boolean"}:
        return f"'{escaped}'::{type_name}"
    return f"'{escaped}'"


def inline_parameters(sql: str, parameters: list[QueryParameter]) -> str:
    for parameter in parameters:
        sql = sql.replace(f"%({parameter.name})s", sql_literal(parameter))
    if "%(" in sql:
        raise ValueError("settle_unbound_placeholder")
    return sql


def settle(
    report: dict[str, Any],
    verdicts: dict[str, Any],
    judged_cases: dict[str, Any],
    compiler: PlanCompiler,
    overlay,
    as_of: datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_case = {r["case_id"]: r for r in report["results"]}
    verdict_of = {e["case_id"]: e["verdict"] for e in verdicts["verdicts"]}
    cases: list[dict[str, Any]] = []
    skipped: list[str] = []
    for source in judged_cases["cases"]:
        case_id = source["case_id"]
        result, verdict = by_case[case_id], verdict_of.get(case_id)
        case: dict[str, Any] = {"case_id": case_id, "question": source["question"]}
        if source.get("follow_up_of"):
            case["follow_up_of"] = source["follow_up_of"]
        if verdict == "correct" and result["status"] == "answered":
            plan = QueryPlan.model_validate(result["plan"])
            exclusions = (
                excluded_segments(source["question"], overlay) if overlay else []
            )
            named_ids = (
                set(named_segments(source["question"], overlay)) if overlay else set()
            )
            named = [
                seg
                for seg in (overlay.segments if overlay else [])
                if seg.id in named_ids
            ]
            compiled = compiler.compile(
                plan, as_of=as_of, exclude_segments=exclusions, named_segments=named
            )
            if compiled.compiled.physical_sql != result["sql"]:
                raise ValueError(f"settle_sql_drift:{case_id}")
            case["expected"] = {"status": "answered"}
            case["reference_sql"] = inline_parameters(
                compiled.compiled.physical_sql, compiled.compiled.execution_parameters
            )
        elif verdict == "refusal_ok":
            case["expected"] = {"status": result["status"]}
            case["accept_statuses"] = REFUSALS
            if result.get("reason"):
                case["note"] = f"judged run reason: {result['reason']}"
        else:
            skipped.append(f"{case_id} ({verdict or 'no verdict'}, {result['status']})")
            continue
        cases.append(case)
    return cases, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verdicts", type=Path, required=True)
    parser.add_argument(
        "--cases", type=Path, required=True, help="the judged case file"
    )
    parser.add_argument("--dsn-env", required=True)
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--enum-distinct-limit", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    import psycopg

    dsn = os.environ.get(arguments.dsn_env)
    if not dsn:
        print(f"SETTLE_BLOCKED code=dsn_env_missing env={arguments.dsn_env}")
        return 2

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection

    judged = yaml.safe_load(arguments.cases.read_text(encoding="utf-8"))
    report = json.loads(arguments.report.read_text(encoding="utf-8"))
    verdicts = yaml.safe_load(arguments.verdicts.read_text(encoding="utf-8"))
    schema = introspect_schema(
        connect,
        datasource_id=arguments.datasource_id,
        enum_distinct_limit=arguments.enum_distinct_limit,
    )
    overlay = load_semantic_overlay(arguments.overlay) if arguments.overlay else None
    compiler = PlanCompiler(schema, overlay=overlay)
    as_of = datetime.fromisoformat(judged["as_of"])
    cases, skipped = settle(report, verdicts, judged, compiler, overlay, as_of)
    header = (
        f"# Settled from {arguments.report.name} with the owner's verdicts on "
        f"{datetime.now().date().isoformat()}. Reference SQL of an answered case\n"
        "# is the SQL the system produced in the judged run, accepted by the judge,\n"
        "# with the bound values inlined: a regression guard, not an independent\n"
        "# truth. Refusal cases accept any typed refusal. Cases judged wrong or\n"
        "# unsure were left out.\n"
    )
    document = {
        "datasource_id": judged["datasource_id"],
        "as_of": judged["as_of"],
        "cases": cases,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        header
        + yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    print(f"settled {len(cases)} cases; skipped {len(skipped)}")
    for item in skipped:
        print("  skipped", item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
