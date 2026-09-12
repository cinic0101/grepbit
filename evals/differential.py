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
from hypothesis import HealthCheck, Phase, given, seed, settings
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


def generate_plans(
    shape: SchemaShape, examples: int, seed_value: int
) -> list[dict[str, Any]]:
    """Distinct plan payloads the plan itself accepts; one seed, one list."""

    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()

    @seed(seed_value)
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


REDACTED = "<redacted>"


def plans_carry_data(
    enum_distinct_limit: int, source_report: dict[str, Any] | None = None
) -> bool:
    """Whether a generated plan can hold a value read from the rows.

    The generator's only channel from the database to a plan is the
    introspected ``sample_values`` of text columns; numbers, dates and the
    fallback texts are constants of ``plan_generator``. With sampling off
    (``0``, the real-DB setting) ``sample_values`` holds only the labels of
    PostgreSQL enum types, which are schema, not data; a redacted report then
    keeps its plans as they are and stays replayable.
    """

    if source_report is not None:
        # Replay does not generate literals from current introspection. Preserve
        # provenance through successive replays; legacy/unknown inputs are not
        # made safe merely by running with today's default sampling limit of 0.
        if "plans_carry_data" in source_report:
            return source_report["plans_carry_data"] is not False
        limit = source_report.get("enum_distinct_limit")
        return not (type(limit) is int and limit == 0)
    return enum_distinct_limit > 0


Entry = tuple[dict, list[str] | None]  # plan payload, recorded segment exclusion


def replayable(recorded: list[dict]) -> tuple[list[Entry], int]:
    """Plans from an earlier report that can be re-checked, with the segment
    exclusion drawn for each (reports before 0a40a98 recorded bare plans; the
    exclusion is then drawn again), and the count of plans whose literals were
    redacted (they compile to a kind mismatch, not to the original plan;
    regenerate from the report's seed instead)."""

    def redacted(payload: Any) -> bool:
        if isinstance(payload, dict):
            return any(redacted(v) for v in payload.values())
        if isinstance(payload, list):
            return any(redacted(v) for v in payload)
        return payload == REDACTED

    entries: list[Entry] = []
    for item in recorded:
        if "plan" in item and "exclude_segments" in item:
            entries.append((item["plan"], list(item["exclude_segments"])))
        else:
            entries.append((item, None))
    kept = [entry for entry in entries if not redacted(entry[0])]
    return kept, len(entries) - len(kept)


def scrub(payload: Any) -> Any:
    """The plan with every filter literal replaced, for reports on real data
    where literals were sampled from the database."""

    if isinstance(payload, dict):
        return {
            k: (
                [REDACTED] * len(v)
                if k == "values" and isinstance(v, list)
                else scrub(v)
            )
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [scrub(v) for v in payload]
    return payload


def localize(rows: list[tuple], zone: ZoneInfo) -> list[tuple]:
    def fix(value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(zone)
        return value

    return [tuple(fix(v) for v in row) for row in rows]


def _sort_key(value, direction: str):
    """SQL order: NULLS FIRST for ascending, NULLS LAST for descending (as compiled)."""
    is_null = value is None
    if direction == "asc":
        return (0 if is_null else 1, "" if is_null else _orderable(value))
    return (1 if is_null else 0, "" if is_null else _Desc(_orderable(value)))


def _orderable(value):
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return float(value)
    return str(value)


class _Desc:
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        return self.v > other.v

    def __eq__(self, other):
        return self.v == other.v


def compare(
    plan: QueryPlan,
    columns: list[str],
    actual_rows: list[tuple],
    reference_rows: list[tuple],
    zone: ZoneInfo,
) -> bool:
    """Whether the compiled result matches the reference evaluation.

    Without a limit the two row sets must be equal. With a limit the reference
    is ordered as the SQL orders (the plan's order, else the grouping columns
    ascending, NULLS FIRST ascending and NULLS LAST descending) and the actual
    rows must be the first k of it, except that rows tied with the boundary
    row on the ordering key may stand in for one another: that choice is the
    database's, everything else is not.
    """

    actual = normalize_rows(localize(actual_rows, zone))
    expected_all = normalize_rows(localize(reference_rows, zone))
    if plan.limit is None:
        return actual == expected_all
    k = plan.limit
    order = [(item.field, item.direction) for item in plan.order] or [
        (c, "asc") for c in columns if c not in {m.output_name for m in plan.measures}
    ]
    positions = {name: i for i, name in enumerate(columns)}
    localized = localize(reference_rows, zone)

    def key(row):
        return tuple(
            _sort_key(row[positions[f]], d) for f, d in order if f in positions
        )

    ordered = sorted(localized, key=key)
    if len(ordered) <= k:
        return actual == expected_all
    boundary = key(ordered[k - 1])
    required = [r for r in ordered[:k] if key(r) != boundary]
    tied = [r for r in ordered if key(r) == boundary]
    required_n = normalize_rows(required)
    tied_n = normalize_rows(tied)
    actual_sorted = sorted(actual)
    # every strictly-better row must be present, the rest come from the tied rows
    remaining = list(actual_sorted)
    for r in required_n:
        if r not in remaining:
            return False
        remaining.remove(r)
    if len(remaining) != k - len(required_n):
        return False
    tied_pool = list(tied_n)
    for r in remaining:
        if r not in tied_pool:
            return False
        tied_pool.remove(r)
    return True


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
    parser.add_argument(
        "--enum-distinct-limit",
        type=int,
        default=0,
        help="text values sampled per column for generated literals; 0 on real data",
    )
    parser.add_argument(
        "--replay",
        type=Path,
        help="re-check the plans recorded in an earlier report instead of generating",
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
        connect,
        datasource_id=arguments.datasource_id,
        enum_distinct_limit=arguments.enum_distinct_limit,
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

    replay_note: dict[str, Any] = {}
    earlier: dict[str, Any] | None = None
    if arguments.replay is not None:
        earlier = json.loads(arguments.replay.read_text(encoding="utf-8"))
        entries, redacted_count = replayable(earlier["plans"])
        replay_note = {
            "replayed_from": str(arguments.replay),
            "replay_schema_digest_matches": earlier.get("schema_digest")
            == schema.digest(),
            "redacted_not_replayed": redacted_count,
        }
        if redacted_count:
            print(
                f"NOTE {redacted_count} plans carry redacted literals and are not"
                f" replayed; regenerate with --seed {earlier.get('seed')} instead"
            )
    else:
        entries = [
            (payload, None)
            for payload in generate_plans(shape, arguments.examples, arguments.seed)
        ]
    carries_data = plans_carry_data(arguments.enum_distinct_limit, earlier)
    redact_plans = arguments.redact and carries_data
    outcomes: Counter = Counter({"generated": len(entries)})
    refusals: Counter = Counter()
    disagreements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    # compile once per plan; execution and evaluation run per data set
    compiled_plans = []
    records: list[dict[str, Any]] = []  # every plan with its exclusion, for --replay
    for payload, recorded_exclusion in entries:
        plan = QueryPlan.model_validate(payload)
        if recorded_exclusion is None:
            exclude = [s for s in default_segments if rng.random() < 0.7]
        else:
            exclude = [s for s in default_segments if s.id in recorded_exclusion]
        records.append(
            {
                "plan": scrub(payload) if redact_plans else payload,
                "exclude_segments": [s.id for s in exclude],
            }
        )
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
                    "plan": scrub(payload) if redact_plans else payload,
                    "error": type(error).__name__
                    if arguments.redact
                    else repr(error)[:300],
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
                    "plan": scrub(payload) if redact_plans else payload,
                    "sql": compiled.compiled.physical_sql,
                    "error": "database_error_details_redacted"
                    if arguments.redact
                    else error,
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
                    "plan": scrub(payload) if redact_plans else payload,
                    "error": type(error).__name__
                    if arguments.redact
                    else repr(error)[:300],
                }
            )
            return
        out_columns = list(compiled.output_columns)
        expected_rows = [tuple(row.get(c) for c in out_columns) for row in reference]
        if compare(plan, out_columns, actual_rows, expected_rows, zone):
            outcomes["agree"] += 1
            return
        outcomes["disagree"] += 1
        record: dict[str, Any] = {
            "instance": label,
            "plan": scrub(payload) if redact_plans else payload,
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
                max_rows=20000,
                preview_rows=20000,
                statement_timeout_seconds=10,
                run_id="differential",
            )
            if result.error_code:
                return list(result.columns), [], result.error_code
            if result.truncated:
                return list(result.columns), [], "truncated_result"
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

    import subprocess

    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        git_sha = None
    report = {
        "datasource_id": arguments.datasource_id,
        "engine": arguments.engine,
        "git_sha": git_sha,
        "seed": arguments.seed,
        "schema_digest": schema.digest(),
        "enum_distinct_limit": arguments.enum_distinct_limit,
        "plans_carry_data": carries_data,
        "plans_redacted": redact_plans,
        **replay_note,
        "plans": records,
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
