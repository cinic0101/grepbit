#!/usr/bin/env python3
"""Differential test of the compiler against the reference evaluation.

  .venv/bin/python evals/differential.py --dsn-env <ENV> --datasource-id <id> \
      [--overlay overlays/x.json] [--examples 500] [--seed 1] \
      [--engine postgres | --engine duckdb --instances 3] \
      --output evidence/differential/<name>.json

Plans are generated over the introspected schema (`plan_generator.py`).
With the postgres engine the compiled SQL runs on the database itself
through the service's executor and `reference_eval.py` evaluates the same
plan over a copy of its tables. With the duckdb engine the schema is the
same but the data is random (`synthetic.py`): each plan runs on every
instance, so a coincidence of one fixture's data cannot hide a difference.
Row sets are compared as the runner compares an answer with its reference
(values only, sorted, numbers to four decimals). A typed refusal is a
legitimate outcome counted by code; a plan the evaluator does not cover is
skipped and counted; a disagreement, a database error or an exception is
recorded with the plan and the SQL (cell values included unless --redact).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from hypothesis import HealthCheck, Phase, given, settings
from hypothesis import strategies as st
from hypothesis.errors import HypothesisException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_generator import SchemaShape, draw_plan  # noqa: E402
from reference_eval import Unsupported, evaluate  # noqa: E402
from spike_tier0 import normalize_rows  # noqa: E402
from synthetic import DuckInstance, random_instance  # noqa: E402

from grepbit.adapters.overlay_store import load_semantic_overlay  # noqa: E402
from grepbit.adapters.postgres.executor import PsycopgQueryExecutor  # noqa: E402
from grepbit.adapters.postgres.introspect import introspect_schema  # noqa: E402
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler  # noqa: E402
from grepbit.application.active_queries import ActiveQueryRegistry  # noqa: E402
from grepbit.domain.plan import PlanError, QueryPlan  # noqa: E402


def load_tables(connect, schema) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN READ ONLY")
            for table in schema.tables:
                cursor.execute(f'SELECT * FROM public."{table.name}"')
                names = [d.name for d in cursor.description]
                tables[table.name] = [
                    dict(zip(names, row)) for row in cursor.fetchall()
                ]
    return tables


def generate_plans(shape: SchemaShape, examples: int) -> list[dict[str, Any]]:
    """Distinct plan payloads that the plan itself accepts."""

    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()

    @settings(
        max_examples=examples,
        deadline=None,
        database=None,
        phases=[Phase.generate],
        suppress_health_check=list(HealthCheck),
    )
    @given(data=st.data())
    def draw(data) -> None:
        payload = draw_plan(data, shape)
        core = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if core in seen:
            return
        seen.add(core)
        try:
            QueryPlan.model_validate(payload)
        except (ValidationError, ValueError):
            return
        payloads.append(payload)

    try:
        draw()
    except HypothesisException as error:
        print("hypothesis stopped:", error)
    return payloads


def localize(rows: list[tuple], zone: ZoneInfo) -> list[tuple]:
    def fix(value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(zone)
        return value

    return [tuple(fix(v) for v in row) for row in rows]


def compare(
    plan: QueryPlan,
    actual_rows: list[tuple],
    reference_rows: list[tuple],
    zone: ZoneInfo,
) -> bool:
    actual = normalize_rows(localize(actual_rows, zone))
    expected = normalize_rows(localize(reference_rows, zone))
    if plan.limit is not None:
        # the reference does not apply the limit: the actual rows must be a
        # subset of the right size (ties at the boundary are the database's call)
        return len(actual) == min(plan.limit, len(expected)) and all(
            r in expected for r in actual
        )
    return actual == expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn-env",
        required=True,
        help="schema source; the postgres engine also runs there",
    )
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--examples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--engine", choices=["postgres", "duckdb"], default="postgres")
    parser.add_argument(
        "--instances", type=int, default=3, help="duckdb: random instances"
    )
    parser.add_argument("--as-of", default="2026-08-15T12:00:00+08:00")
    parser.add_argument(
        "--redact", action="store_true", help="keep cell values out of the report"
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    dsn = os.environ.get(arguments.dsn_env)
    if not dsn:
        print(f"BLOCKED dsn_env_missing env={arguments.dsn_env}")
        return 2

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection

    schema = introspect_schema(
        connect, datasource_id=arguments.datasource_id, enum_distinct_limit=20
    )
    overlay = load_semantic_overlay(arguments.overlay) if arguments.overlay else None
    as_of = datetime.fromisoformat(arguments.as_of)
    zone = ZoneInfo(schema.business_timezone)
    compiler = PlanCompiler(schema, overlay=overlay)
    shape = SchemaShape(schema, overlay)
    default_segments = [
        s for s in (overlay.segments if overlay else []) if s.default_exclude
    ]
    rng = random.Random(arguments.seed)

    payloads = generate_plans(shape, arguments.examples)
    outcomes: Counter = Counter({"generated": len(payloads)})
    refusals: Counter = Counter()
    disagreements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    # compile once per plan; execution and evaluation run per data set
    compiled_plans = []
    for payload in payloads:
        plan = QueryPlan.model_validate(payload)
        exclude = [s for s in default_segments if rng.random() < 0.7]
        try:
            compiled = compiler.compile(
                plan, as_of=as_of, exclude_segments=exclude, named_segments=[]
            )
        except PlanError as error:
            outcomes["typed_refusal"] += 1
            refusals[error.code] += 1
            continue
        except Exception as error:  # noqa: BLE001
            outcomes["compiler_exception"] += 1
            errors.append(
                {
                    "kind": "compiler_exception",
                    "plan": payload,
                    "error": repr(error)[:300],
                }
            )
            continue
        compiled_plans.append((payload, plan, exclude, compiled))

    def check(payload, plan, exclude, compiled, tables, run_sql, label: str) -> None:
        columns, actual_rows, error = run_sql(compiled.compiled)
        if error:
            outcomes["database_error"] += 1
            errors.append(
                {
                    "kind": "database_error",
                    "instance": label,
                    "plan": payload,
                    "sql": compiled.compiled.physical_sql,
                    "error": error,
                }
            )
            return
        try:
            reference = evaluate(
                plan, schema, overlay, as_of, tables, exclude_segments=exclude
            )
        except Unsupported as why:
            outcomes["evaluator_unsupported"] += 1
            refusals[f"unsupported:{why}"] += 1
            return
        except Exception as error:  # noqa: BLE001
            outcomes["evaluator_exception"] += 1
            errors.append(
                {
                    "kind": "evaluator_exception",
                    "instance": label,
                    "plan": payload,
                    "error": repr(error)[:300],
                }
            )
            return
        out_columns = list(compiled.output_columns)
        expected_rows = [tuple(row.get(c) for c in out_columns) for row in reference]
        if compare(plan, actual_rows, expected_rows, zone):
            outcomes["agree"] += 1
            return
        outcomes["disagree"] += 1
        record: dict[str, Any] = {
            "instance": label,
            "plan": payload,
            "exclude_segments": [s.id for s in exclude],
            "sql": compiled.compiled.physical_sql,
            "columns": out_columns,
            "actual_rows": len(actual_rows),
            "reference_rows": len(expected_rows),
        }
        if not arguments.redact:
            record["actual"] = [
                list(r) for r in normalize_rows(localize(actual_rows, zone))[:8]
            ]
            record["reference"] = [
                list(r) for r in normalize_rows(localize(expected_rows, zone))[:8]
            ]
        disagreements.append(record)

    if arguments.engine == "postgres":
        tables = load_tables(connect, schema)
        executor = PsycopgQueryExecutor(
            connection_factory=connect, active_queries=ActiveQueryRegistry()
        )

        def run_pg(compiled_query):
            result = executor.execute(
                compiled_query,
                max_rows=2000,
                preview_rows=2000,
                statement_timeout_seconds=10,
                run_id="differential",
            )
            if result.error_code:
                return list(result.columns), [], result.error_code
            return list(result.columns), [tuple(r.values()) for r in result.rows], None

        for payload, plan, exclude, compiled in compiled_plans:
            check(payload, plan, exclude, compiled, tables, run_pg, "postgres")
    else:
        for k in range(arguments.instances):
            tables = random_instance(schema, random.Random(arguments.seed * 1000 + k))
            instance = DuckInstance(schema, tables)

            def run_duck(compiled_query, instance=instance):
                try:
                    names, rows = instance.execute(compiled_query)
                except Exception as error:  # noqa: BLE001
                    return [], [], repr(error)[:200]
                return names, rows, None

            for payload, plan, exclude, compiled in compiled_plans:
                check(payload, plan, exclude, compiled, tables, run_duck, f"duckdb-{k}")

    report = {
        "datasource_id": arguments.datasource_id,
        "engine": arguments.engine,
        "instances": arguments.instances if arguments.engine == "duckdb" else 1,
        "overlay_revision": overlay.revision if overlay else None,
        "examples_requested": arguments.examples,
        "as_of": as_of.isoformat(),
        "outcomes": dict(outcomes),
        "typed_refusals": dict(refusals.most_common()),
        "disagreements": disagreements,
        "errors": errors,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "engine": arguments.engine,
                "outcomes": dict(outcomes),
                "refusals": dict(refusals.most_common(6)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
