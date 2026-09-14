"""Loopback-only development UI over the real stdio MCP client."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from grepbit.adapters.datasource_registry import load_registry
from grepbit.adapters.mcp_server import PUBLIC_RESULT_FIELDS

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).with_name("dev_web")
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; "
    "style-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'",
}
FIELDS = {
    *PUBLIC_RESULT_FIELDS,
    "rows",
    "plan",
    "grounding",
    "request_id",
    "relay_rules",
}
STATUSES = {"answered", "clarify", "semantic_gap", "unsupported", "unsafe", "failed"}


def event(kind, data):
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def error(code, status=400):
    return JSONResponse({"error": code}, status_code=status, headers=HEADERS)


def public_result(payload):
    if (
        not isinstance(payload, dict)
        or payload.get("status") not in STATUSES
        or not isinstance(payload.get("request_id"), str)
        or not payload["request_id"]
        or not isinstance(payload.get("rows"), list)
    ):
        raise ValueError("invalid_tool_result")
    return {k: v for k, v in payload.items() if k in FIELDS}


def child_environment(registry, path, environ):
    # No shell, admin environment, browser-supplied settings or credential copying.
    names = {r.dsn_env for r in registry.datasources}
    names |= {
        "PATH",
        "GREPBIT_MODEL_BASE_URL",
        "GREPBIT_MODEL_NAME",
        "GREPBIT_MODEL_THINKING",
        "GREPBIT_MODEL_TEMPERATURE",
        "GREPBIT_MODEL_TIMEOUT_SECONDS",
        "GREPBIT_MODEL_MAX_TOKENS",
        "GREPBIT_MODEL_REPAIR_TURNS",
        "GREPBIT_MODEL_CREDENTIAL_ENV",
        environ.get("GREPBIT_MODEL_CREDENTIAL_ENV", "LITELLM_API_KEY"),
    }
    return {k: environ[k] for k in names if k in environ} | {
        "GREPBIT_DATASOURCES": str(path),
        "GREPBIT_REQUEST_TIMEOUT_SECONDS": "30",
    }


def create_app(registry_path, *, port=8765, ask_call=None, bridge_timeout=35):
    """ask_call is an offline fault-test seam; CLI always uses real MCP stdio."""
    path = Path(registry_path).resolve()
    registry = load_registry(path)
    if any(r.enum_distinct_limit != 0 for r in registry.datasources):
        raise ValueError("sampling_must_be_zero")
    ids = {r.id for r in registry.datasources}
    authority = f"127.0.0.1:{port}"
    origin = f"http://{authority}"
    active = None

    def release(token):
        nonlocal active
        if active is token:
            active = None

    async def invoke(arguments):
        if ask_call is not None:
            return await ask_call(arguments)
        # A dev request owns its process/session. No shared session to corrupt or
        # close on cancellation; the next request starts fresh after a crash.
        with open(os.devnull, "w") as sink:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "grepbit.adapters.mcp_server"],
                env=child_environment(registry, path, os.environ),
                cwd=str(ROOT),
            )
            async with stdio_client(params, errlog=sink) as streams:
                async with ClientSession(*streams) as session:
                    async with asyncio.timeout(10):
                        await session.initialize()
                    response = await session.call_tool("ask", arguments)
        if response.is_error:
            raise RuntimeError("tool_failed")
        return response.structured_content

    async def query(request: Request):
        nonlocal active
        if (
            request.headers.get("origin") != origin
            or request.headers.get("x-grepbit-local") != "1"
        ):
            return error("same_origin_required", 403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return error("json_required", 415)
        try:
            body = bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        return error("body_too_large", 413)
            data = json.loads(body)
            if not isinstance(data, dict) or set(data) != {
                "datasource_id",
                "question",
                "as_of",
            }:
                return error("invalid_fields")
            if not all(isinstance(v, str) for v in data.values()):
                return error("invalid_fields")
            if data["datasource_id"] not in ids:
                return error("unknown_datasource")
            if not data["question"].strip() or len(data["question"]) > 4000:
                return error("invalid_question")
            datetime.fromisoformat(data["as_of"])
        except (ValueError, UnicodeError, TimeoutError):
            return error("invalid_request")
        if active is not None:
            return error("query_busy", 429)
        token = active = object()

        async def stream():
            task = None
            try:
                yield event("progress", {"state": "accepted"})
                task = asyncio.create_task(invoke(data))
                async with asyncio.timeout(bridge_timeout):
                    while not task.done():
                        await asyncio.wait({task}, timeout=1)
                        if not task.done():
                            yield event("progress", {"state": "waiting"})
                    yield event("result", public_result(task.result()))
            except TimeoutError:
                yield event("error", {"code": "bridge_timeout"})
            except Exception:
                yield event("error", {"code": "backend_unavailable"})
            finally:
                if task is not None:
                    task.cancel()
                    # SDK cancellation and cleanup concern this request only.
                    with suppress(asyncio.CancelledError, Exception):
                        await task
                release(token)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers=HEADERS,
            background=BackgroundTask(release, token),
        )

    async def config(request):
        return JSONResponse({"datasources": sorted(ids)}, headers=HEADERS)

    async def asset(request):
        name, mime = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }[request.url.path]
        return Response((ASSETS / name).read_bytes(), media_type=mime, headers=HEADERS)

    app = Starlette(
        routes=[
            Route("/query", query, methods=["POST"]),
            Route("/config", config),
            *(Route(p, asset) for p in ("/", "/app.js", "/style.css")),
        ],
    )

    async def secure(request, call_next):
        if request.headers.get("host") != authority:
            return error("invalid_host", 403)
        if request.headers.get("origin", origin) != origin:
            return error("same_origin_required", 403)
        try:
            response = await call_next(request)
        except Exception:
            response = error("request_failed", 500)
        response.headers.update(HEADERS)
        return response

    app.add_middleware(BaseHTTPMiddleware, dispatch=secure)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument(
        "--confirm-synthetic-fixtures", action="store_true", required=True
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        app = create_app(args.registry, port=args.port)
    except Exception:
        parser.error(
            "invalid registry; explicit synthetic sources and sampling 0 required"
        )
    import uvicorn

    print(f"Grepbit local E2E: http://127.0.0.1:{args.port}", flush=True)
    uvicorn.run(
        app, host="127.0.0.1", port=args.port, access_log=False, log_config=None
    )


if __name__ == "__main__":
    main()
