#!/usr/bin/env python3
"""Differential test of the compiler against the reference evaluation.

  .venv/bin/python evals/differential.py --dsn-env <ENV> --datasource-id <id> \
      [--overlay overlays/x.json] [--examples 500] [--seed 1] \
      --output evidence/differential/<name>.json

Plans are generated over the introspected schema (`plan_generator.py`), the
compiled SQL runs on PostgreSQL through the same executor the service uses,
`reference_eval.py` evaluates the same plan in plain Python over the same
tables, and the two row sets are compared as the runner compares an answer
with its reference (values only, sorted, numbers to four decimals). A typed
refusal is a legitimate outcome and is counted by code; a plan the evaluator
does not cover is skipped and counted; a disagreement is recorded with the
plan, the SQL and both row sets. No cell values of a real database should be
run through this without --redact (they are, in the disagreement records).
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

import psycopg
from hypothesis import HealthCheck, Phase, given, settings
from hypothesis import strategies as st
from hypothesis.errors import HypothesisException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_generator import SchemaShape, draw_plan  # noqa: E402
from reference_eval import Unsupported, evaluate  # noqa: E402
from spike_tier0 import normalize_rows  # noqa: E402

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn-env", required=True)
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--examples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1)
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
    tables = load_tables(connect, schema)
    as_of = datetime.fromisoformat(arguments.as_of)
    compiler = PlanCompiler(schema, overlay=overlay)
    executor = PsycopgQueryExecutor(
        connection_factory=connect, active_queries=ActiveQueryRegistry()
    )
    shape = SchemaShape(schema, overlay)
    default_segments = [
        s for s in (overlay.segments if overlay else []) if s.default_exclude
    ]
    rng = random.Random(arguments.seed)

    outcomes: Counter = Counter()
    refusals: Counter = Counter()
    disagreements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_cores: set[str] = set()

    @settings(
        max_examples=arguments.examples,
        deadline=None,
        database=None,
        derandomize=False,
        phases=[Phase.generate],
        suppress_health_check=list(HealthCheck),
    )
    @given(data=st.data())
    def run_one(data) -> None:
        payload = draw_plan(data, shape)
        core = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if core in seen_cores:
            outcomes["duplicate"] += 1
            return
        seen_cores.add(core)
        try:
            plan = QueryPlan.model_validate(payload)
        except (ValidationError, ValueError):
            outcomes["invalid_plan"] += 1
            return
        exclude = [s for s in default_segments if rng.random() < 0.7]
        try:
            compiled = compiler.compile(
                plan, as_of=as_of, exclude_segments=exclude, named_segments=[]
            )
        except PlanError as error:
            outcomes["typed_refusal"] += 1
            refusals[error.code] += 1
            return
        except Exception as error:  # noqa: BLE001
            outcomes["compiler_exception"] += 1
            errors.append(
                {
                    "kind": "compiler_exception",
                    "plan": payload,
                    "error": repr(error)[:300],
                }
            )
            return
        result = executor.execute(
            compiled.compiled,
            max_rows=1000,
            preview_rows=1000,
            statement_timeout_seconds=10,
            run_id="differential",
        )
        if result.error_code:
            outcomes["postgres_error"] += 1
            errors.append(
                {
                    "kind": "postgres_error",
                    "plan": payload,
                    "sql": compiled.compiled.physical_sql,
                    "error": result.error_code,
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
                    "plan": payload,
                    "error": repr(error)[:300],
                }
            )
            return
        columns = list(compiled.output_columns)
        actual = normalize_rows([dict(r) for r in result.rows])
        expected_rows = [tuple(row.get(c) for c in columns) for row in reference]
        if plan.limit is not None or plan.order:
            outcomes["ordered_or_limited_compared_as_sets"] += 1
        if plan.limit is not None:
            # the reference does not apply the limit: compare the actual rows as a
            # subset of the reference when the reference has more rows
            expected = normalize_rows(expected_rows)
            if (
                len(actual) <= len(expected)
                and all(r in expected for r in actual)
                and len(actual) == min(plan.limit, len(expected))
            ):
                outcomes["agree"] += 1
                return
        else:
            expected = normalize_rows(expected_rows)
            if actual == expected:
                outcomes["agree"] += 1
                return
        outcomes["disagree"] += 1
        record = {
            "plan": payload,
            "exclude_segments": [s.id for s in exclude],
            "sql": compiled.compiled.physical_sql,
            "columns": columns,
            "actual_rows": len(actual),
            "reference_rows": len(expected),
        }
        if not arguments.redact:
            record["actual"] = [list(r) for r in actual[:6]]
            record["reference"] = [list(r) for r in expected[:6]]
        disagreements.append(record)

    try:
        run_one()
    except HypothesisException as error:
        print("hypothesis stopped:", error)

    report = {
        "datasource_id": arguments.datasource_id,
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
            {"outcomes": dict(outcomes), "refusals": dict(refusals.most_common(8))},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
