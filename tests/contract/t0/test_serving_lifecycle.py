"""Serving rulers: public projection and isolated invocation ownership."""

import asyncio
import json

import pytest
import test_ask_contract as h

from grepbit.adapters import mcp_server as server
from grepbit.application.active_queries import ActiveQueryRegistry
from grepbit.application.ask import AskResult
from grepbit.application.request_lifecycle import RequestControl
from grepbit.ports.active_query_lifecycle import ActiveQueryHandle


def build(monkeypatch, tmp_path, planner=None, executor=None):
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"datasources": [{"id": "iot_test", "dsn_env": "OPAQUE_TEST_DSN"}]})
    )
    services = h.services(
        planner or h._Planner(h.COUNT_OFFLINE),
        executor or h._Executor([{"row_count": 3}]),
    )
    monkeypatch.setattr(
        server,
        "bind_datasource",
        lambda *a, **kw: server.BoundDatasource(a[0], services, "Asia/Taipei"),
    )
    return server.build_server(registry), services


async def call(s, question="Count offline devices"):
    return await s.call_tool(
        "ask",
        {
            "datasource_id": "iot_test",
            "question": question,
            "as_of": h.AS_OF.isoformat(),
        },
    )


def test_public_allowlist_excludes_debug_and_future_internal_fields():
    result = AskResult(
        question="q",
        status="failed",
        raw_output="PRIVATE_DEBUG",
        raw_output_repair="PRIVATE_REPAIR",
        question_values=[{"value": "UNUSED_CANDIDATE"}],
    )
    result.future_internal_field = "INTERNAL"
    payload = server.result_payload(result, max_rows=200)
    assert not (
        {"raw_output", "raw_output_repair", "question_values", "future_internal_field"}
        & payload.keys()
    )
    assert payload["status"] == "failed" and payload["relay_rules"]


def test_each_invocation_has_a_distinct_public_identity(monkeypatch, tmp_path):
    s, _ = build(monkeypatch, tmp_path, h._Planner(h.COUNT_OFFLINE, h.COUNT_OFFLINE))
    a = asyncio.run(call(s)).structured_content
    b = asyncio.run(call(s)).structured_content
    assert (
        a.get("request_id")
        and b.get("request_id")
        and a["request_id"] != b["request_id"]
    )


def test_duplicate_active_identity_rejects_without_replacing_owner():
    registry = ActiveQueryRegistry()
    calls = []
    registry.register(ActiveQueryHandle("a", lambda: calls.append("a")))
    with pytest.raises(ValueError, match="duplicate_active_run_id"):
        registry.register(ActiveQueryHandle("a", lambda: calls.append("b")))
    registry.cancel("a")
    assert calls == ["a"]


def test_unexpected_backend_failure_is_safe_failed(monkeypatch, tmp_path):
    class Broken(h._Executor):
        def execute(self, *args, **kwargs):
            raise RuntimeError("PRIVATE_CONNECTION_DETAILS")

    s, _ = build(monkeypatch, tmp_path, executor=Broken([]))
    result = asyncio.run(call(s))
    assert not result.is_error
    assert result.structured_content["status"] == "failed"
    assert "PRIVATE_CONNECTION_DETAILS" not in str(result)


def test_projection_preserves_values_and_disclosure_with_truthful_truncation():
    result = AskResult(
        question="q",
        status="answered",
        rows=[{"n": 1}, {"n": 2}],
        row_count=2,
        assumptions=["scope"],
        verification="unverified_semantics",
    )
    payload = server.result_payload(result, max_rows=1)
    assert payload["rows"] == [{"n": 1}] and payload["rows_truncated"]
    assert (
        payload["assumptions"] == ["scope"]
        and payload["verification"] == result.verification
    )


def test_bound_factory_owns_mutable_planner_and_runtime_ports(monkeypatch, tmp_path):
    from grepbit.domain.datasource import DatasourceRegistration

    monkeypatch.setattr(server, "introspect_schema", lambda *a, **kw: h.SCHEMA)
    ds = server.bind_datasource(
        DatasourceRegistration(id="iot_test", dsn_env="OPAQUE_TEST_DSN"),
        tmp_path / "registry.json",
        {
            "OPAQUE_TEST_DSN": "not-opened",
            "GREPBIT_MODEL_BASE_URL": "http://unused",
            "GREPBIT_MODEL_NAME": "fake",
        },
    )
    a, b = (
        ds.request_factory(RequestControl(10)),
        ds.request_factory(RequestControl(10)),
    )
    assert a.planner is not b.planner and a.executor is not b.executor
    assert a.schema is b.schema and a.compiler is b.compiler
    a.planner.last_raw_output = "synthetic_a"
    assert b.planner.last_raw_output is None


def test_cold_binding_occurs_once_for_overlapping_requests(monkeypatch, tmp_path):
    import threading

    from test_request_control import wait_event

    s, services = build(monkeypatch, tmp_path)
    count = []
    entered, release = threading.Event(), threading.Event()

    def binder(registration, *args, **kwargs):
        count.append(True)
        entered.set()
        assert release.wait(2)

        def factory(control):
            from dataclasses import replace

            return replace(services, planner=h._Planner(h.COUNT_OFFLINE))

        return server.BoundDatasource(
            registration, services, "Asia/Taipei", request_factory=factory
        )

    monkeypatch.setattr(server, "bind_datasource", binder)

    async def scenario():
        a = asyncio.create_task(call(s))
        await wait_event(entered)
        b = asyncio.create_task(call(s))
        await asyncio.sleep(0.02)
        release.set()
        results = await asyncio.gather(a, b)
        assert all(r.structured_content["status"] == "answered" for r in results)

    try:
        asyncio.run(scenario())
    finally:
        release.set()
    assert len(count) == 1
