"""Explicit request kind is not datasource capability or intent certification."""

import asyncio
import inspect
import json
from dataclasses import fields, replace

import pytest
import test_ask_contract as h
import test_dev_web as web
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.ask import AskServices, AskSettings, ask

ROW = {
    "decision": "plan",
    "plan": {
        "base_table": "devices",
        "rows": {"columns": [{"table": "devices", "column": "model"}]},
    },
}


def settings():
    value = AskSettings(as_of=AS_OF)
    # Model the future request at the old boundary, so red tests assert behavior
    # rather than failing during construction/import.
    object.__setattr__(value, "query_kind", "rows")
    return value


def services(reply, enabled=True):
    planner, executor = (
        h._Planner(reply),
        h._Executor([{"model": None}, {"model": None}]),
    )
    s = h.services(planner, executor)
    s = replace(s, compiler=PlanCompiler(s.schema, overlay=s.overlay, allow_rows=True))
    s.allow_rows = enabled
    return s


def test_request_and_permission_are_separate_declared_fields():
    assert "query_kind" in {f.name for f in fields(AskSettings)}
    assert "allow_rows" in {f.name for f in fields(AskServices)}
    assert "query_kind" in inspect.signature(ChatCompletionsPlanClient).parameters


def test_disabled_source_stops_before_planning_and_execution():
    s = services(ROW, False)
    r = ask("List device model", s, settings())
    assert (r.status, r.reason) == ("unsupported", "row_queries_disabled")
    assert not s.planner.calls and not s.executor.executed


def test_row_entry_rejects_aggregate_before_compile_or_execution():
    s = services(h.COUNT_OFFLINE)
    r = ask("List offline devices", s, settings())
    assert (r.status, r.reason) == ("failed", "request_query_kind_mismatch")
    assert not s.executor.executed and r.sql is None


def test_explicit_rows_preserve_duplicates_null_and_disclosure():
    s = services(ROW)
    r = ask("List device model", s, settings())
    assert r.status == "answered" and r.rows == [{"model": None}, {"model": None}]
    assert r.plan.rows and r.verification == "unverified_semantics"
    assert r.assumptions and r.lineage["projection"]
    assert getattr(r, "query_kind", None) == "rows"


@pytest.mark.parametrize(
    "reason,status",
    [
        ("semantic_gap", "semantic_gap"),
        ("unsupported", "unsupported"),
        ("ambiguous", "clarify"),
    ],
)
def test_explicit_kind_never_overrides_decline(reason, status):
    s = services({"decision": "none", "reason": reason})
    r = ask("q", s, settings())
    assert r.status == status and not s.executor.executed


def test_old_default_keeps_aggregate_behavior():
    s = services(h.COUNT_OFFLINE, False)
    assert (
        ask("Count offline devices", s, AskSettings(as_of=AS_OF)).status == "answered"
    )


def test_unknown_request_kind_is_rejected_as_input():
    assert "query_kind" in {f.name for f in fields(AskSettings)}
    with pytest.raises(ValueError, match="invalid_query_kind"):
        AskSettings(as_of=AS_OF, query_kind="guess")


def test_constructor_mode_does_not_leak_into_default_messages():
    assert "query_kind" in inspect.signature(ChatCompletionsPlanClient).parameters
    cfg = GroundingModelSettings(base_url="http://unused", model="fake")
    before = ChatCompletionsPlanClient(cfg).build_messages(
        "q", iot_schema(), as_of=AS_OF.isoformat()
    )
    explicit = ChatCompletionsPlanClient(cfg, allow_rows=True, query_kind="rows")
    messages = explicit.build_messages("q", iot_schema(), as_of=AS_OF.isoformat())
    payload = json.loads(messages[2]["content"])
    assert (
        payload["query_kind"] == "rows"
        and payload["prompt_revision"] == "plan-classify-json-v20-parent-rows"
    )
    assert (
        ChatCompletionsPlanClient(cfg).build_messages(
            "q", iot_schema(), as_of=AS_OF.isoformat()
        )
        == before
    )
    assert "query_kind" not in json.loads(before[2]["content"])
    with pytest.raises(ValueError, match="row_queries_disabled"):
        ChatCompletionsPlanClient(cfg, query_kind="rows")


@pytest.mark.parametrize("mode", ["rows", "default"])
def test_web_forwards_explicit_mode_without_another_call(tmp_path, mode):
    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps(
            {
                "datasources": [
                    {"id": "fixture", "dsn_env": "OPAQUE", "allow_rows": True}
                ]
            }
        )
    )
    response, calls = web.run_request(registry, data={**web.QUERY, "query_kind": mode})
    assert response.status_code == 200 and len(calls) == 1
    assert calls[0]["query_kind"] == mode


def test_web_cannot_enable_disabled_source(tmp_path):
    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps({"datasources": [{"id": "fixture", "dsn_env": "OPAQUE"}]})
    )
    response, calls = web.run_request(
        registry, data={**web.QUERY, "query_kind": "rows"}
    )
    assert response.json()["error"] == "row_queries_disabled" and not calls


def test_mcp_disabled_source_rejects_before_binding(monkeypatch, tmp_path):
    from grepbit.adapters import mcp_server as mcp

    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps({"datasources": [{"id": "fixture", "dsn_env": "OPAQUE"}]})
    )

    def forbidden(*args, **kwargs):
        pytest.fail("disabled rows must not bind the database")

    monkeypatch.setattr(mcp, "bind_datasource", forbidden)
    server = mcp.build_server(registry)
    r = asyncio.run(
        server.call_tool(
            "ask",
            {
                "datasource_id": "fixture",
                "question": "List records",
                "query_kind": "rows",
            },
        )
    )
    assert r.structured_content["reason"] == "row_queries_disabled"
    assert r.structured_content["query_kind"] == "rows"


@pytest.mark.parametrize("mode", ["auto", "ROWS", "", None, True, []])
def test_web_rejects_unknown_mode_without_call(tmp_path, mode):
    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps({"datasources": [{"id": "fixture", "dsn_env": "OPAQUE"}]})
    )
    response, calls = web.run_request(registry, data={**web.QUERY, "query_kind": mode})
    assert response.status_code == 400 and not calls


def test_factory_keeps_modes_request_local(monkeypatch, tmp_path):
    from grepbit.adapters import mcp_server as mcp
    from grepbit.application.request_lifecycle import RequestControl
    from grepbit.domain.datasource import DatasourceRegistration

    monkeypatch.setattr(mcp, "introspect_schema", lambda *a, **kw: h.SCHEMA)
    ds = mcp.bind_datasource(
        DatasourceRegistration(id="iot_test", dsn_env="OPAQUE", allow_rows=True),
        tmp_path / "registry.json",
        {
            "OPAQUE": "not-a-real-connection",
            "GREPBIT_MODEL_BASE_URL": "http://unused",
            "GREPBIT_MODEL_NAME": "fake",
        },
    )
    row = ds.request_factory(RequestControl(10), query_kind="rows")
    default = ds.request_factory(RequestControl(10))
    assert row.allow_rows and default.allow_rows
    assert row.planner is not default.planner and row.executor is not default.executor
    assert row.compiler is default.compiler
    for service, expected in [(row, "rows"), (default, None), (row, "rows")]:
        payload = json.loads(
            service.planner.build_messages("q", h.SCHEMA, as_of=AS_OF.isoformat())[2][
                "content"
            ]
        )
        assert payload.get("query_kind") == expected


def test_request_stop_preserves_mode():
    from grepbit.application.request_lifecycle import RequestControl

    control = RequestControl(10)
    control.stop("request_cancelled")
    s = services(ROW)
    result = ask("q", s, settings(), control=control)
    assert result.status == "failed" and result.query_kind == "rows"
    assert not s.planner.calls


def test_mcp_enabled_mode_is_forwarded_and_guarded(monkeypatch, tmp_path):
    from grepbit.adapters import mcp_server as mcp

    registry = tmp_path / "sources.json"
    registry.write_text(
        json.dumps(
            {
                "datasources": [
                    {"id": "fixture", "dsn_env": "OPAQUE", "allow_rows": True}
                ]
            }
        )
    )
    s = services(h.COUNT_OFFLINE)
    modes = []

    def bind(registration, *args, **kwargs):
        def factory(control, *, query_kind="default"):
            modes.append(query_kind)
            return s

        return mcp.BoundDatasource(
            registration, s, "Asia/Taipei", request_factory=factory
        )

    monkeypatch.setattr(mcp, "bind_datasource", bind)
    server = mcp.build_server(registry)
    r = asyncio.run(
        server.call_tool(
            "ask",
            {
                "datasource_id": "fixture",
                "question": "List devices",
                "query_kind": "rows",
            },
        )
    )
    assert modes == ["rows"] and not s.executor.executed
    assert r.structured_content["reason"] == "request_query_kind_mismatch"
    assert r.structured_content["query_kind"] == "rows"
