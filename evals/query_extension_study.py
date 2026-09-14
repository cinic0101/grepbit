"""Serial, synthetic-only query capability experiment. Not a served endpoint.

Independent reference SQL is executed BEFORE model calls, never sent to the
model. Source units are trusted study metadata, not model-supplied assertions.
No claim that this separate path preserves all production gate/grounding or
request-lifecycle behavior; promotion must implement and test those explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import yaml

from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from grepbit.adapters.litellm.plan_client import schema_payload
from grepbit.adapters.mcp_server import bind_datasource
from grepbit.adapters.sqlglot.query_extension_study import StudyCompiler, StudyRefusal
from grepbit.application.overlay import excluded_segments, named_segments
from grepbit.domain.datasource import DatasourceRegistration
from grepbit.domain.plan import PlanError
from grepbit.domain.query_extension_study import StudyProposal

ROOT = Path(__file__).resolve().parents[1]
PROMPT_REVISION = "query-extension-planner-study"
RULES = """Propose a typed governed query, never SQL, formulas or computed values.
Use only supplied schema identifiers; never infer missing business definitions.
Choose kind rows for listing records (columns or all_columns, never both).
Row columns/filters must belong to the base table; ordering uses output column
names. Use all_columns only when all visible details were requested. An explicit
limit is not all records. Do not invent a count measure to simulate a row list.
Choose aggregate for ordinary QueryPlan aggregation. If a different output
unit was requested, use conversion {field: output alias, target_unit: allowed
unit}. Source unit comes exclusively from unit_bindings. Never just rename an
unconverted value. Each aggregate measure can use an alias. No formulas.
Choose combine when distinct fact populations contribute metrics at a common
entity: entity_table gives the complete entity population and its primary key
is always output first. entity_columns adds only requested labels (do not add
the key twice). Each component is a simple QueryPlan: base_table, measures,
optional filters and time scope; NO dimensions, limit, order, having, latest,
without, growth or ratio/share. The server injects the entity-key grouping.
Give component measures distinct meaningful aliases, in the requested output
order. Count(*) counts that component's rows, not entity rows. Missing child
count=0; missing SUM/AVG=NULL. Each component uses its own requested time scope.
Use selection {field: component output alias, direction: max|min, ties: all}
to select an entity by one component's extremum while reporting the other
metrics. All tied non-NULL winners remain, including winners missing another
metric. Mean temperature means mean of readings, not mean of device means.
Only use ordinary aggregate for controls requiring no new construct; do not
invent a window when the question says all data or gives no window. Report a
typed none decision if units are incompatible or business meaning is absent.
ColumnRefs are objects {table: table_name, column: column_name}, not strings.
Return one JSON object conforming to the supplied schema. This is a planning
proposal, not a certificate that its interpretation matches user intent."""


def study_schema(wire="v1"):
    schema = StudyProposal.model_json_schema()
    if wire == "v2":
        # Narrow the shown component contract to what the validator already
        # accepts. No compiler semantics or question-specific example changed.
        component = json.loads(json.dumps(schema["$defs"]["QueryPlan"]))
        allowed = {"base_table", "measures", "filters", "time"}
        component["properties"] = {
            k: v for k, v in component["properties"].items() if k in allowed
        }
        component["required"] = ["base_table", "measures"]
        component["title"] = "UngroupedComponent"
        schema["$defs"]["UngroupedComponent"] = component
        schema["$defs"]["CombinedQuery"]["properties"]["components"]["items"] = {
            "$ref": "#/$defs/UngroupedComponent"
        }
        schema["$defs"]["AggregateQuery"]["required"].append("conversion")
    return schema


def parse_proposal(raw, wire="v1"):
    payload = json.loads(raw)
    query = payload.get("query") or {}
    if wire == "v2" and query.get("kind") == "aggregate" and "conversion" not in query:
        raise ValueError("explicit_conversion_or_null_required")
    return StudyProposal.model_validate(payload)


def visible_units(bindings, schema, overlay):
    return [
        b
        for b in bindings
        if schema.table(b["column"]["table"])
        and schema.table(b["column"]["table"]).column(b["column"]["column"])
        and (
            overlay is None
            or overlay.visible_column(b["column"]["table"], b["column"]["column"])
        )
    ]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def normalized(rows):
    def cell(value):
        if value is None:
            return None
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return str(Decimal(str(value)).quantize(Decimal("0.0001")))
        return str(value)

    return [tuple(cell(v) for v in row) for row in rows]


def matches(actual, expected, *, ordered=False):
    a, b = normalized(actual), normalized(expected)
    return a == b if ordered else Counter(a) == Counter(b)


def execute(connect, sql, parameters=None):
    with connect() as connection:
        connection.execute("BEGIN READ ONLY")
        connection.execute("SET LOCAL statement_timeout='5s'")
        result = connection.execute(sql, parameters or {})
        names = [c.name for c in result.description]
        rows = result.fetchmany(201)
        if len(rows) > 200:
            raise ValueError("study_result_over_200_not_scored")
        return names, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-synthetic-fixtures", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "evals/cases/query_extensions.yaml"
    )
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--wire", choices=["v1", "v2"], default="v1")
    parser.add_argument("--question-last", action="store_true")
    args = parser.parse_args()
    if not args.confirm_synthetic_fixtures or args.output.exists():
        parser.error("require synthetic scope and a fresh output path")
    if bool(args.live) == bool(args.replay):
        parser.error("choose --live or --replay")
    panel = yaml.safe_load(args.cases.read_text())
    if not 1 <= len(panel["cases"]) <= 32:
        parser.error("one run is bounded to 32 model calls")
    registry = ROOT / "evals/fixtures/dev_web_datasources.json"
    registrations = json.loads(registry.read_text())["datasources"]
    bound, connects = {}, {}
    for raw in registrations:
        if (
            raw["id"] not in {"iot_spike", "service_test"}
            or raw["enum_distinct_limit"] != 0
        ):
            parser.error("only the two sampled-zero synthetic fixture profiles")
        registration = DatasourceRegistration.model_validate(raw)
        bound[registration.id] = bind_datasource(registration, registry)
        connects[registration.id] = lambda key=registration.dsn_env: psycopg.connect(
            os.environ[key], connect_timeout=5
        )
    units = json.loads((ROOT / "evals/fixtures/query_extension_units.json").read_text())
    records = []
    for case in panel["cases"]:
        if case["source"] not in bound:
            parser.error("case source outside synthetic scope")
        item = dict(case)
        if case.get("sql"):
            names, result = execute(connects[case["source"]], case["sql"])
            item.update(oracle_columns=names, oracle=result)
            item["oracle_alternatives"] = [
                execute(connects[case["source"]], sql)[1]
                for sql in case.get("alternatives", [])
            ]
        records.append(item)
    prior = (
        {r["id"]: r for r in json.loads(args.replay.read_text())["records"]}
        if args.replay
        else {}
    )
    settings = GroundingModelSettings.from_environment()
    client = (
        ChatCompletionsGroundingClient(settings)._create_client() if args.live else None
    )
    report = {
        "revision": f"{PROMPT_REVISION}-{args.wire}"
        + ("-question-last" if args.question_last else ""),
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_hashes": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in [
                "evals/query_extension_study.py",
                "src/grepbit/domain/query_extension_study.py",
                "src/grepbit/adapters/sqlglot/query_extension_study.py",
            ]
        },
        "panel_sha256": digest(panel),
        "unit_bindings_sha256": digest(units),
        "evaluator_revision": "query-extension-values-v2",
        "model": settings.model,
        "temperature": 0,
        "thinking": False,
        "actual_calls": 0,
        "repairs": 0,
        "sample_limit": 0,
        "synthetic_only": True,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the path so a concurrent/repeated invocation cannot overwrite it.
    with args.output.open("x") as stream:
        json.dump(report, stream, default=str)
    for item in records:
        services = bound[item["source"]].services
        date = (
            "2026-08-15T12:00:00+08:00"
            if item["source"] == "iot_spike"
            else "2026-04-15T12:00:00+08:00"
        )
        payload = {
            "question": item["question"],
            "as_of": date,
            "schema": schema_payload(services.schema, services.overlay),
            "unit_bindings": visible_units(
                units[item["source"]], services.schema, services.overlay
            ),
        }
        if args.question_last:
            # One experimental variable: same content, question serialized last.
            payload["question"] = payload.pop("question")
        rules = RULES
        if args.wire == "v2":
            rules += (
                " Every aggregate query MUST explicitly include query.conversion: "
                "the requested conversion object, or null when no conversion is "
                "requested. It belongs beside query.plan, not inside plan or "
                "beside the top-level decision. A combine component has no "
                "dimensions field; the entity_table determines the requested "
                "entity, not an unrelated higher-level group."
            )
        messages = [
            {"role": "system", "content": rules},
            {
                "role": "system",
                "content": json.dumps(study_schema(args.wire)),
            },
            {"role": "user", "content": json.dumps(payload)},
        ]
        item.update(
            messages_sha256=digest(messages),
            schema_sha256=digest(payload["schema"]),
            as_of=date,
        )
        started = time.monotonic()
        try:
            if args.live:
                report["actual_calls"] += 1
                reply = client.chat.completions.create(
                    model=settings.model,
                    messages=messages,
                    temperature=0,
                    max_tokens=1800,
                    response_format={"type": "json_object"},
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
                raw = reply.choices[0].message.content
            else:
                raw = prior[item["id"]]["raw_output"]
            item["raw_output"] = raw
            proposal = parse_proposal(raw, args.wire)
            item["proposal"] = proposal.model_dump(mode="json", exclude_none=True)
            if proposal.decision == "none":
                item.update(
                    status=proposal.reason,
                    outcome="necessary_refusal"
                    if item.get("refusal")
                    else "refusal_on_answerable",
                )
            else:
                overlay = services.overlay
                named = named_segments(item["question"], overlay) if overlay else []
                compiler = StudyCompiler(
                    services.schema,
                    overlay=overlay,
                    units=units[item["source"]],
                    excluded=excluded_segments(item["question"], overlay)
                    if overlay
                    else (),
                    named=[s for s in overlay.segments if s.id in named]
                    if overlay
                    else (),
                )
                compiled = compiler.compile(
                    proposal.query, as_of=datetime.fromisoformat(date)
                )
                names, values = execute(
                    connects[item["source"]],
                    compiled.compiled.physical_sql,
                    {p.name: p.value for p in compiled.compiled.execution_parameters},
                )
                item.update(
                    status="answered",
                    columns=names,
                    rows=values,
                    compiled=compiled.compiled.model_dump(mode="json"),
                    assumptions=compiled.assumptions,
                    verification=compiled.verification,
                )
                item["outcome"] = (
                    "unexpected_answer"
                    if item.get("refusal")
                    else (
                        "reference_match"
                        if any(
                            matches(values, oracle, ordered=item["family"] == "rows")
                            for oracle in [item["oracle"], *item["oracle_alternatives"]]
                        )
                        else "reference_mismatch"
                    )
                )
        except (StudyRefusal, PlanError) as error:
            item.update(
                status="unsupported",
                outcome="necessary_refusal"
                if item.get("refusal")
                else "refusal_on_answerable",
                error_type=type(error).__name__,
                error_code=str(error),
            )
        except Exception as error:
            item.update(
                status="failed",
                outcome="not_scored_failure",
                error_type=type(error).__name__,
            )
            # Never serialize connection/transport exceptions or credentials.
            if type(error).__name__ in {"StudyRefusal", "PlanError"}:
                item["error_code"] = str(error)
        item["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["summary"] = dict(Counter(r.get("outcome", "pending") for r in records))
        args.output.write_text(
            json.dumps(report, default=str, ensure_ascii=False, indent=2)
        )
        print(item["id"], item["outcome"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
