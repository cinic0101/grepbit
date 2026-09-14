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

import math
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from threading import Lock
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
from grepbit.adapters.postgres.request_connection import request_connection
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
from grepbit.application.request_lifecycle import RequestControl, RequestStopped
from grepbit.domain.datasource import DatasourceRegistration
from grepbit.domain.grounding import normalize_question

SERVER_REVISION = "mcp-server-v2"
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
    "restate every assumption that affects the reading; when status is 'failed', "
    "report an operational failure, not a semantic refusal; for other statuses "
    "besides 'answered', say that the question was refused and repeat the reason and "
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
    request_factory: Callable[[RequestControl], AskServices] | None = None


def bind_datasource(
    registration: DatasourceRegistration,
    registry_path: Path,
    environ=os.environ,
    *,
    control: RequestControl | None = None,
) -> BoundDatasource:
    """Introspect once, load the overlay and the value index, build the services."""

    dsn = environ.get(registration.dsn_env)
    if not dsn:
        raise RuntimeError(f"dsn_env_missing:{registration.dsn_env}")

    def connect():
        return request_connection(dsn, control)

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

    def unscoped_connect():
        return request_connection(dsn)

    services = AskServices(
        schema=schema,
        planner=ChatCompletionsPlanClient(settings),
        compiler=PlanCompiler(schema, overlay=overlay),
        policy=PostgresSqlPolicy(
            tables=frozenset(t.name for t in schema.tables),
            functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
        ),
        executor=PsycopgQueryExecutor(
            connection_factory=unscoped_connect, active_queries=ActiveQueryRegistry()
        ),
        literal_checker=lambda checks: missing_literals(
            unscoped_connect, schema.schema_name, checks
        ),
        unsafe=unsafe,
        overlay=overlay,
        shape_pack=load_shape_pack(),
        value_index=index,
    )

    def request_services(request: RequestControl) -> AskServices:
        def request_connect():
            return request_connection(dsn, request)

        return replace(
            services,
            planner=ChatCompletionsPlanClient(settings, control=request),
            executor=PsycopgQueryExecutor(
                connection_factory=request_connect,
                active_queries=ActiveQueryRegistry(),
                control=request,
            ),
            literal_checker=lambda checks: missing_literals(
                request_connect,
                schema.schema_name,
                checks,
                statement_timeout_seconds=min(
                    5, max(1, math.ceil(request.remaining(5)))
                ),
            ),
        )

    return BoundDatasource(
        registration,
        services,
        registration.business_timezone,
        skipped,
        request_services,
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
            "thresholds (having), entities with no activity (without), the latest "
            "row per entity (latest) and the latest period with data, time "
            "windows and grains; no free text, no forecasts"
        ),
        "revisions": {
            "ask": ASK_REVISION,
            "prompt": PLAN_PROMPT_REVISION,
            "server": SERVER_REVISION,
        },
        "relay_rules": RELAY_RULES,
    }


PUBLIC_RESULT_FIELDS = (
    "question",
    "status",
    "reason",
    "clarification",
    "sql",
    "parameters",
    "lineage",
    "assumptions",
    "interpretation",
    "verification",
    "row_count",
    "rows_truncated",
    "warnings",
    "value_references",
    "value_reference_errors",
    "missing_literals",
    "shape_repairs",
    "constant_dimensions_dropped",
    "unmapped_concepts",
    "base_repair",
    "excluded_segments",
    "literal_checks",
    "model_retries",
    "model_repair_turns",
    "elapsed_seconds",
)


def result_payload(result: AskResult, *, max_rows: int) -> dict[str, Any]:
    payload = {name: deepcopy(getattr(result, name)) for name in PUBLIC_RESULT_FIELDS}
    payload["rows_truncated"] = result.rows_truncated or len(result.rows) > max_rows
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
            unavailable[registration.id] = bind_error_text(error)
    payload = capabilities_payload(dict(bound))
    if unavailable:
        payload["unavailable"] = unavailable
    return payload


def build_server(registry_path: Path, environ=os.environ, *, lazy: bool = True):
    from mcp.server.mcpserver import MCPServer

    registry = load_registry(registry_path)
    bound: dict[str, BoundDatasource] = {}
    timeout = float(environ.get("GREPBIT_REQUEST_TIMEOUT_SECONDS", "30"))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("request_timeout_must_be_finite_positive")
    locks = {r.id: Lock() for r in registry.datasources}

    def get(
        datasource_id: str, control: RequestControl | None = None
    ) -> BoundDatasource:
        if datasource_id not in bound:
            registration = registry.get(datasource_id)
            if registration is None:
                raise ValueError(f"unknown datasource: {datasource_id}")
            lock = locks[datasource_id]
            while not lock.acquire(
                timeout=min(0.05, control.remaining()) if control else 0.05
            ):
                if control:
                    control.check()
            try:
                if datasource_id not in bound:
                    ds = bind_datasource(
                        registration, registry_path, environ, control=control
                    )
                    if control:
                        control.check()
                    bound[datasource_id] = ds
            finally:
                lock.release()
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
    async def ask_tool(
        datasource_id: str, question: str, as_of: str | None = None
    ) -> dict[str, Any]:
        # Invalid tool input stays an input error, not an operational failure.
        if registry.get(datasource_id) is None:
            raise ValueError("unknown_datasource")
        try:
            parsed = datetime.fromisoformat(as_of) if as_of else None
        except ValueError:
            raise ValueError("invalid_as_of") from None

        def work(control):
            ds = get(datasource_id, control)
            zone = ZoneInfo(ds.business_timezone)
            moment = parsed or datetime.now(zone)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=zone)
            services = (
                ds.request_factory(control) if ds.request_factory else ds.services
            )
            result = ask(
                question,
                services,
                AskSettings(as_of=moment),
                run_id=control.run_id,
                control=control,
            )
            control.check()
            return result_payload(result, max_rows=200)

        return await run_request(question, work, timeout_seconds=timeout)

    return server


async def run_request(
    question: str, work: Callable[[RequestControl], dict], *, timeout_seconds: float
) -> dict:
    """Bound the response wait and stop only this invocation's physical work."""
    import anyio

    started = time.monotonic()
    control = RequestControl(timeout_seconds)

    async def stop(reason):
        callback = control.stop(reason)
        if callback:
            with anyio.move_on_after(2, shield=True):
                try:
                    await anyio.to_thread.run_sync(callback, abandon_on_cancel=True)
                except Exception:
                    pass  # Native statement timeout remains the fallback.

    try:
        with anyio.fail_after(control.remaining()):
            payload = await anyio.to_thread.run_sync(
                lambda: work(control), abandon_on_cancel=True
            )
            control.finish()
    except anyio.get_cancelled_exc_class():
        await stop("request_cancelled")
        raise
    except (TimeoutError, RequestStopped):
        await stop("request_timeout")
        payload = result_payload(
            AskResult(
                question=question,
                status="failed",
                reason="request_timeout",
                elapsed_seconds=round(time.monotonic() - started, 3),
            ),
            max_rows=200,
        )
    except Exception:
        await stop("request_failed")
        payload = result_payload(
            AskResult(
                question=question,
                status="failed",
                reason="request_failed",
                elapsed_seconds=round(time.monotonic() - started, 3),
            ),
            max_rows=200,
        )
    payload["request_id"] = control.run_id
    return payload


def main() -> int:
    registry_path = Path(
        os.environ.get("GREPBIT_DATASOURCES", "datasources.json")
    ).resolve()
    server = build_server(registry_path)
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
