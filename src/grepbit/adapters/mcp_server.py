"""The callable surface: an MCP server (stdio) with two tools, ask and capabilities.

Composition lives here because it wires adapters together; the orchestration
itself is ``application.ask``. Datasources come from ``datasources.json``;
connection strings come only from the environment variables it names.

  GREPBIT_DATASOURCES=/path/to/datasources.json  (default: ./datasources.json)
  GREPBIT_MODEL_BASE_URL, GREPBIT_MODEL_NAME, LITELLM_API_KEY  (planner)
  <dsn_env per datasource>  (read-only role)

  .venv/bin/python -m grepbit.adapters.mcp_server
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from grepbit.adapters.datasource_registry import load_registry, overlay_path
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    PLAN_PROMPT_REVISION,
    ChatCompletionsPlanClient,
)
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.postgres.executor import PsycopgQueryExecutor
from grepbit.adapters.postgres.introspect import introspect_schema
from grepbit.adapters.postgres.value_check import missing_literals
from grepbit.adapters.postgres.value_index import load_column_values
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.application.active_queries import ActiveQueryRegistry
from grepbit.application.ask import (
    ASK_REVISION,
    AskResult,
    AskServices,
    AskSettings,
    ask,
)
from grepbit.application.grounding import ValueIndex
from grepbit.application.overlay import overlay_problems
from grepbit.domain.datasource import DatasourceRegistration
from grepbit.domain.grounding import normalize_question

SERVER_REVISION = "mcp-server-v1"
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
RELAY_RULES = (
    "Relay rules for the calling agent: quote only numbers that appear in rows; "
    "restate every assumption that affects the reading; when status is not "
    "'answered', say that the question was refused and repeat the reason and "
    "clarification instead of inventing an answer; verification tells how much of "
    "the meaning was reviewed by a human (verified, partially_verified, "
    "unverified_semantics)."
)


def unsafe(question: str) -> bool:
    normalized = normalize_question(question)
    return any(
        re.search(rf"(?<![a-z0-9_]){re.escape(p)}(?![a-z0-9_])", normalized)
        if p.isascii()
        else p in normalized
        for p in UNSAFE_PATTERNS
    )


@dataclass
class BoundDatasource:
    registration: DatasourceRegistration
    services: AskServices
    business_timezone: str
    value_index_skipped: list[str] = field(default_factory=list)


def bind_datasource(
    registration: DatasourceRegistration, registry_path: Path, environ=os.environ
) -> BoundDatasource:
    """Introspect once, load the overlay and the value index, build the services."""

    import psycopg

    dsn = environ.get(registration.dsn_env)
    if not dsn:
        raise RuntimeError(f"dsn_env_missing:{registration.dsn_env}")

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection

    schema = introspect_schema(
        connect,
        datasource_id=registration.id,
        schema_name=registration.schema_name,
        business_timezone=registration.business_timezone,
        enum_distinct_limit=registration.enum_distinct_limit,
    )
    overlay = None
    path = overlay_path(registry_path, registration)
    if path is not None:
        overlay = load_semantic_overlay(path)
        problems = overlay_problems(overlay, schema)
        if problems:
            raise RuntimeError("overlay_invalid: " + "; ".join(problems))
    index, skipped = None, []
    if overlay is not None and overlay.groundable_columns():
        values, skipped = load_column_values(
            connect, schema, overlay.groundable_columns()
        )
        index = ValueIndex(values)
    settings = GroundingModelSettings.from_environment(environ)
    services = AskServices(
        schema=schema,
        planner=ChatCompletionsPlanClient(settings),
        compiler=PlanCompiler(schema, overlay=overlay),
        policy=PostgresSqlPolicy(
            tables=frozenset(t.name for t in schema.tables),
            functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
        ),
        executor=PsycopgQueryExecutor(
            connection_factory=connect, active_queries=ActiveQueryRegistry()
        ),
        literal_checker=lambda checks: missing_literals(
            connect, schema.schema_name, checks
        ),
        unsafe=unsafe,
        overlay=overlay,
        shape_pack=load_shape_pack(),
        value_index=index,
    )
    return BoundDatasource(
        registration, services, registration.business_timezone, skipped
    )


def capabilities_payload(bound: dict[str, BoundDatasource]) -> dict[str, Any]:
    """What a caller may ask: datasources, their visible tables, reviewed metrics,
    segments and the concepts known to be absent. No values, no rows."""

    out = []
    for ds in bound.values():
        overlay, schema = ds.services.overlay, ds.services.schema
        out.append(
            {
                "id": ds.registration.id,
                "description": ds.registration.description,
                "business_timezone": ds.business_timezone,
                "tables": [
                    {
                        "name": t.name,
                        "comment": t.comment,
                        "aliases": overlay.table_names(t.name) if overlay else [],
                        "columns": [
                            c.name
                            for c in t.columns
                            if overlay is None or overlay.visible_column(t.name, c.name)
                        ],
                    }
                    for t in schema.tables
                    if overlay is None or overlay.table_visible(t.name)
                ],
                "reviewed_metrics": [
                    {
                        "id": m.id,
                        "names": m.names,
                        "description": m.description,
                        "review_state": m.review_state.value,
                    }
                    for m in (overlay.metrics if overlay else [])
                ],
                "segments": [
                    {
                        "id": s.id,
                        "names": s.names,
                        "excluded_by_default": s.default_exclude,
                        "note": s.note,
                    }
                    for s in (overlay.segments if overlay else [])
                ],
                "absent_concepts": [
                    {"names": c.names, "note": c.note}
                    for c in (overlay.absent_concepts if overlay else [])
                ],
                "groundable_columns": [
                    c.id for c in (overlay.groundable_columns() if overlay else [])
                ],
            }
        )
    return {
        "datasources": out,
        "shapes": (
            "one aggregate query: sums, counts, averages, min, max, distinct "
            "counts, ratios, shares of total, period-over-period growth, group "
            "thresholds (having), entities with no activity (without), time "
            "windows and grains; no free text, no forecasts, no row lookups"
        ),
        "revisions": {
            "ask": ASK_REVISION,
            "prompt": PLAN_PROMPT_REVISION,
            "server": SERVER_REVISION,
        },
        "relay_rules": RELAY_RULES,
    }


def result_payload(result: AskResult, *, max_rows: int) -> dict[str, Any]:
    payload = asdict(result)
    payload["rows"] = [
        {
            k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
            for k, v in r.items()
        }
        for r in result.rows[:max_rows]
    ]
    payload["plan"] = (
        result.plan.model_dump(mode="json", exclude_none=True) if result.plan else None
    )
    payload["grounding"] = [g.model_dump(mode="json") for g in result.grounding]
    payload["relay_rules"] = RELAY_RULES
    return payload


def bind_error_text(error: BaseException) -> str:
    """The reason a datasource could not bind, without any connection detail.

    Our own reasons (``dsn_env_missing:<VAR>``, ``overlay_invalid: ...``) are
    passed through; a driver error is reduced to its class name so a host or a
    password in its message never reaches the caller.
    """

    text = str(error)
    if isinstance(error, RuntimeError) and text.split(":")[0] in (
        "dsn_env_missing",
        "overlay_invalid",
    ):
        return text
    return f"bind_failed:{type(error).__name__}"


def collect_capabilities(
    registrations: Sequence[DatasourceRegistration],
    get: Callable[[str], BoundDatasource],
    bound: dict[str, BoundDatasource],
) -> dict[str, Any]:
    """Capabilities of every datasource that binds; the others listed by reason.

    One datasource whose environment variable is missing must not hide the
    rest: the payload carries the bound ones under ``datasources`` and the
    unbound ones under ``unavailable`` as ``{id: reason}``.
    """

    unavailable: dict[str, str] = {}
    for registration in registrations:
        try:
            get(registration.id)
        except Exception as error:
            bound.pop(registration.id, None)
            unavailable[registration.id] = bind_error_text(error)
    payload = capabilities_payload(bound)
    if unavailable:
        payload["unavailable"] = unavailable
    return payload


def build_server(registry_path: Path, environ=os.environ, *, lazy: bool = True):
    from mcp.server.mcpserver import MCPServer

    registry = load_registry(registry_path)
    bound: dict[str, BoundDatasource] = {}

    def get(datasource_id: str) -> BoundDatasource:
        if datasource_id not in bound:
            registration = registry.get(datasource_id)
            if registration is None:
                raise ValueError(f"unknown datasource: {datasource_id}")
            bound[datasource_id] = bind_datasource(registration, registry_path, environ)
        return bound[datasource_id]

    if not lazy:
        for registration in registry.datasources:
            get(registration.id)

    server = MCPServer(
        name="grepbit",
        instructions=(
            "grepbit answers one analytics question with one governed aggregate query "
            "over a registered datasource. Call capabilities first to see datasources, "
            "reviewed metrics and segments. " + RELAY_RULES
        ),
    )

    @server.tool(
        name="capabilities",
        description=(
            "Datasources, tables, reviewed metrics, segments, absent concepts, "
            "supported shapes and relay rules."
        ),
    )
    def capabilities() -> dict[str, Any]:
        return collect_capabilities(registry.datasources, get, bound)

    @server.tool(
        name="ask",
        description=(
            "Ask one analytics question of a datasource. Returns status (answered "
            "or a typed refusal: clarify, semantic_gap, unsupported, unsafe, "
            "failed), SQL with bound parameters, lineage, assumptions, verification "
            "level, up to 200 rows, and warnings. " + RELAY_RULES
        ),
    )
    def ask_tool(
        datasource_id: str, question: str, as_of: str | None = None
    ) -> dict[str, Any]:
        ds = get(datasource_id)
        zone = ZoneInfo(ds.business_timezone)
        moment = datetime.fromisoformat(as_of) if as_of else datetime.now(zone)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=zone)
        result = ask(
            question,
            ds.services,
            AskSettings(as_of=moment),
            run_id=f"mcp-{datasource_id}",
        )
        return result_payload(result, max_rows=200)

    return server


def main() -> int:
    registry_path = Path(
        os.environ.get("GREPBIT_DATASOURCES", "datasources.json")
    ).resolve()
    server = build_server(registry_path)
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
