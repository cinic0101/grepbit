"""HTTP boundary tests; injected backend is never live model evidence."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from tools.dev_web import create_app, event, public_result

ORIGIN = "http://127.0.0.1:8765"
HEADERS = {"Origin": ORIGIN, "X-Grepbit-Local": "1"}
QUERY = {"datasource_id": "fixture", "question": "Count records", "as_of": "2026-08-15"}
PAYLOAD = {
    "status": "answered",
    "request_id": "r1",
    "rows": [{"n": 0}],
    "verification": "unverified_semantics",
    "assumptions": ["No window"],
}


class Client:
    """Minimal ASGI request driver; socket/browser evidence is separate."""

    def __init__(self, app, base_url=ORIGIN):
        self.app, self.base_url = app, base_url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, path):
        return await self.request(path, "GET", b"", {})

    async def post(self, path, *, json, headers):
        body = __import__("json").dumps(json).encode()
        return await self.request(path, "POST", body, headers)

    async def request(self, path, method, body, headers):
        url = urlsplit(self.base_url)
        h = {"host": url.netloc, "content-type": "application/json"}
        h.update({k.lower(): v for k, v in headers.items()})
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "http_version": "1.1",
            "server": ("127.0.0.1", 8765),
            "client": ("127.0.0.1", 12345),
            "headers": [(k.encode(), v.encode()) for k, v in h.items()],
        }
        sent = False
        messages = []

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.Event().wait()

        async def send(message):
            messages.append(message)

        await self.app(scope, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        text = b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        ).decode()
        return SimpleNamespace(
            status_code=start["status"],
            text=text,
            headers={k.decode(): v.decode() for k, v in start["headers"]},
            json=lambda: json.loads(text),
        )


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"datasources": [{"id": "fixture", "dsn_env": "FIXTURE_DSN"}]})
    )
    return path


def run_request(registry, *, data=QUERY, headers=HEADERS, origin=ORIGIN, **kwargs):
    calls = []

    async def call(args):
        calls.append(args)
        return PAYLOAD | {"raw_output": "SECRET", "future_secret": "SECRET"}

    async def run():
        app = create_app(registry, ask_call=call)
        async with Client(app, origin) as client:
            return await client.post("/query", json=data, headers=headers, **kwargs)

    return asyncio.run(run()), calls


@pytest.mark.parametrize(
    "headers,origin",
    [
        ({}, ORIGIN),
        ({"Origin": "null", "X-Grepbit-Local": "1"}, ORIGIN),
        ({"Origin": "https://evil.test", "X-Grepbit-Local": "1"}, ORIGIN),
        ({"Origin": ORIGIN}, ORIGIN),
        (HEADERS, "http://evil.test:8765"),
    ],
)
def test_rejects_cross_site_before_mcp(registry, headers, origin):
    response, calls = run_request(registry, headers=headers, origin=origin)
    assert response.status_code == 403 and not calls
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "data",
    [
        QUERY | {"dsn": "not-accepted"},
        QUERY | {"as_of": "bad"},
        QUERY | {"question": ""},
        QUERY | {"question": "x" * 4001},
        QUERY | {"datasource_id": "other"},
        QUERY | {"as_of": None},
        [],
    ],
)
def test_invalid_requests_never_reach_mcp(registry, data):
    response, calls = run_request(registry, data=data)
    assert response.status_code == 400 and not calls


def test_body_and_mime_boundaries(registry):
    response, calls = run_request(registry, data=QUERY | {"question": "x" * 17000})
    assert response.status_code == 413 and not calls
    response, calls = run_request(
        registry, headers=HEADERS | {"Content-Type": "text/plain"}
    )
    assert response.status_code == 415 and not calls


def test_sse_framing_preserves_public_result_and_security_headers(registry):
    response, calls = run_request(registry)
    assert calls == [QUERY]
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    blocks = response.text.strip().split("\n\n")
    assert len(blocks) == 2 and blocks[0].startswith("event: progress")
    assert json.loads(blocks[1].split("data: ")[1]) == PAYLOAD
    assert "SECRET" not in response.text
    assert event("result", {"s": "a\nb"}).count("\n\n") == 1


@pytest.mark.parametrize("fail", ["timeout", "exception", "invalid"])
def test_failed_call_is_safe_and_next_request_works(registry, fail):
    count = 0

    async def call(args):
        nonlocal count
        count += 1
        if count > 1:
            return PAYLOAD
        if fail == "timeout":
            await asyncio.sleep(1)
        if fail == "exception":
            raise RuntimeError("PRIVATE PASSWORD")
        return {"oops": "PRIVATE PASSWORD"}

    async def run():
        app = create_app(registry, ask_call=call, bridge_timeout=0.02)
        async with Client(app) as client:
            a = await client.post("/query", json=QUERY, headers=HEADERS)
            b = await client.post("/query", json=QUERY, headers=HEADERS)
        assert "event: error" in a.text and "PRIVATE" not in a.text
        assert "event: result" not in a.text and "event: result" in b.text

    asyncio.run(run())


def test_concurrent_request_rejected_and_cancel_releases_slot(registry):
    async def run():
        entered, cancelled = asyncio.Event(), asyncio.Event()
        count = 0

        async def call(args):
            nonlocal count
            count += 1
            if count > 1:
                return PAYLOAD
            entered.set()
            try:
                await asyncio.sleep(20)
            finally:
                cancelled.set()

        app = create_app(registry, ask_call=call)
        async with Client(app) as client:
            first = asyncio.create_task(
                client.post("/query", json=QUERY, headers=HEADERS)
            )
            await asyncio.wait_for(entered.wait(), 1)
            second = await client.post("/query", json=QUERY, headers=HEADERS)
            assert second.status_code == 429 and count == 1
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            await asyncio.wait_for(cancelled.wait(), 1)
            third = await client.post("/query", json=QUERY, headers=HEADERS)
            assert "event: result" in third.text

    asyncio.run(run())


def test_only_named_assets_no_registry_environment_or_debug(registry):
    async def run():
        app = create_app(registry, ask_call=lambda args: None)
        async with Client(app) as client:
            assert (await client.get("/config")).json() == {
                "datasources": ["fixture"],
                "row_datasources": [],
            }
            for path in ("/.env", "/registry.json", "/tools/dev_web.py"):
                assert (await client.get(path)).status_code == 404
            page = await client.get("/")
            assert (
                page.status_code == 200 and "Assumptions and limitations" in page.text
            )
            assert '<html lang="en">' in page.text
            guides = (await client.get("/examples.json")).json()
            assert guides["iot_spike"]["as_of"] == "2026-08-15T12:00:00+08:00"
            assert guides["service_test"]["as_of"] == "2026-04-15T12:00:00+08:00"
            assert all(len(g["questions"]) == 3 for g in guides.values())

    asyncio.run(run())


def test_sampled_registry_is_refused(registry):
    doc = json.loads(registry.read_text())
    doc["datasources"][0]["enum_distinct_limit"] = 1
    registry.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="sampling_must_be_zero"):
        create_app(registry)


def test_projection_rejects_non_result_payload():
    with pytest.raises(ValueError):
        public_result({"status": "made_up", "request_id": "r", "rows": []})


@pytest.mark.parametrize("failure", ["die", "startup", "slow"])
def test_real_stdio_child_failure_does_not_poison_next_query(
    registry, monkeypatch, failure
):
    from tools import dev_web

    native = dev_web.StdioServerParameters
    starts = 0

    def parameters(**kwargs):
        nonlocal starts
        starts += 1
        kwargs["args"] = [str(Path(__file__).parents[2] / "fixtures/dev_web_mcp.py")]
        if failure == "startup" and starts == 1:
            kwargs["args"] = ["-c", "raise SystemExit(8)"]
        return native(**kwargs)

    monkeypatch.setattr(dev_web, "StdioServerParameters", parameters)

    async def run():
        app = create_app(registry, bridge_timeout=1.5)
        async with Client(app) as client:
            first = await client.post(
                "/query", json=QUERY | {"question": failure}, headers=HEADERS
            )
            second = await client.post("/query", json=QUERY, headers=HEADERS)
        assert "event: error" in first.text and "event: result" not in first.text
        assert "event: result" in second.text
        assert starts == 2

    asyncio.run(run())
