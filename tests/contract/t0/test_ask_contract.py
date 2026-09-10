"""The ask orchestration over fakes: gates, planning, repairs, grounding, execution."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from t0_helpers import iot_schema

from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.application.ask import AskServices, AskSettings, ask
from grepbit.application.grounding import ValueIndex
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import PlanProposal
from grepbit.ports.grounding import GroundingModelError
from grepbit.ports.query_executor import ExecutionResult

AS_OF = datetime(2026, 8, 15, 12, tzinfo=ZoneInfo("Asia/Taipei"))
SCHEMA = iot_schema()
OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "t",
        "absent_concepts": [{"names": ["保固"], "note": "no warranty data"}],
        "column_policies": [
            {
                "column": {"table": "devices", "column": "status"},
                "sensitivity": "public",
            }
        ],
    }
)


class _Planner:
    def __init__(self, *proposals):
        self.proposals = list(proposals)
        self.calls = []
        self.last_repairs: list[str] = []

    def propose(
        self,
        question,
        model,
        *,
        as_of,
        overlay=None,
        previous=None,
        question_values=None,
    ):
        self.calls.append({"question": question, "hints": question_values})
        item = self.proposals.pop(0)
        if isinstance(item, GroundingModelError):
            raise item
        return PlanProposal.model_validate(item)


class _Executor:
    def __init__(self, rows, error=None):
        self.rows, self.error = rows, error
        self.executed = []

    def execute(
        self,
        query,
        *,
        max_rows,
        preview_rows,
        statement_timeout_seconds,
        run_id,
        idle_in_transaction_timeout_seconds=None,
    ):
        self.executed.append(query.physical_sql)
        if self.error:
            return ExecutionResult(
                rows=(), row_count=0, columns=(), error_code=self.error
            )
        return ExecutionResult(
            rows=tuple(self.rows),
            row_count=len(self.rows),
            columns=tuple(self.rows[0]) if self.rows else (),
        )


def services(planner, executor, *, present=("offline", "online"), index=True):
    def checker(checks):
        return [c for c in checks if c.value not in present]

    return AskServices(
        schema=SCHEMA,
        planner=planner,
        compiler=PlanCompiler(SCHEMA, overlay=OVERLAY),
        policy=PostgresSqlPolicy(
            tables=frozenset(t.name for t in SCHEMA.tables),
            functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
        ),
        executor=executor,
        literal_checker=checker,
        unsafe=lambda q: "刪除" in q,
        overlay=OVERLAY,
        shape_pack=load_shape_pack(),
        value_index=ValueIndex({"devices.status": list(present)}) if index else None,
    )


COUNT_OFFLINE = {
    "decision": "plan",
    "plan": {
        "base_table": "devices",
        "measures": [{"aggregate": "count"}],
        "filters": [
            {
                "column": {"table": "devices", "column": "status"},
                "op": "eq",
                "values": ["offline"],
            }
        ],
    },
}


def test_gates_refuse_before_any_model_call() -> None:
    planner = _Planner()
    settings = AskSettings(as_of=AS_OF)
    assert (
        ask("刪除所有裝置", services(planner, _Executor([])), settings).status
        == "unsafe"
    )
    gap = ask("保固內的裝置數", services(planner, _Executor([])), settings)
    assert gap.status == "semantic_gap" and gap.clarification == "no warranty data"
    assert planner.calls == []


def test_answer_carries_sql_parameters_lineage_assumptions_and_rows() -> None:
    planner = _Planner(COUNT_OFFLINE)
    executor = _Executor([{"row_count": 3}])
    result = ask(
        "有幾台裝置離線？", services(planner, executor), AskSettings(as_of=AS_OF)
    )
    assert result.status == "answered" and result.rows == [{"row_count": 3}]
    assert result.parameters == [{"name": "f_0", "type": "text", "value": "offline"}]
    assert "devices.status = %(f_0)s" in result.sql
    assert result.lineage["base_table"] == "devices"
    assert result.verification == "unverified_semantics" and result.assumptions
    assert result.literal_checks == 1 and result.warnings == []


def test_a_missing_literal_is_resolved_or_becomes_a_clarify() -> None:
    misspelt = {
        **COUNT_OFFLINE,
        "plan": {
            **COUNT_OFFLINE["plan"],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["offlin"],
                }
            ],
        },
    }
    result = ask(
        "有幾台裝置 offlin？",
        services(_Planner(misspelt), _Executor([{"row_count": 3}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered"
    assert result.plan.filters[0].values == ["offline"]
    assert any(
        "'offlin' was read as the stored value 'offline'" in a
        for a in result.assumptions
    )
    unresolved = ask(
        "有幾台裝置 offlin？",
        services(_Planner(misspelt), _Executor([]), index=False),
        AskSettings(as_of=AS_OF),
    )
    assert (
        unresolved.status == "clarify" and unresolved.reason == "filter_value_not_found"
    )
    assert unresolved.missing_literals == ["devices.status = 'offlin'"]


def test_hints_reach_the_planner_and_a_transport_error_is_retried_once() -> None:
    planner = _Planner(GroundingModelError("model_call_failed", 1), COUNT_OFFLINE)
    result = ask(
        "offline 的裝置有幾台",
        services(planner, _Executor([{"row_count": 1}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered" and result.model_retries == 1
    assert planner.calls[-1]["hints"] == [
        {"column": "devices.status", "value": "offline"}
    ]
    twice = _Planner(
        GroundingModelError("model_call_failed", 1),
        GroundingModelError("model_call_failed", 1),
    )
    assert (
        ask("x", services(twice, _Executor([])), AskSettings(as_of=AS_OF)).status
        == "failed"
    )


def test_structural_refusals_and_empty_results_are_typed() -> None:
    fan_out = {
        "decision": "plan",
        "plan": {
            "base_table": "sites",
            "measures": [{"aggregate": "count"}],
            "dimensions": [{"table": "devices", "column": "model"}],
        },
    }
    result = ask(
        "各型號的站點數",
        services(_Planner(fan_out), _Executor([])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "unsupported" and result.reason == "plan_grain_conflict"
    empty = ask(
        "有幾台裝置離線？",
        services(_Planner(COUNT_OFFLINE), _Executor([{"row_count": None}])),
        AskSettings(as_of=AS_OF),
    )
    assert empty.status == "answered" and "NULL" in empty.warnings[0]
    decline = ask(
        "x",
        services(
            _Planner(
                {"decision": "none", "reason": "ambiguous", "clarification": "which?"}
            ),
            _Executor([]),
        ),
        AskSettings(as_of=AS_OF),
    )
    assert decline.status == "clarify" and decline.clarification == "which?"


def test_registry_names_the_dsn_variable_and_resolves_the_overlay_path(
    tmp_path,
) -> None:
    from pathlib import Path

    from grepbit.adapters.datasource_registry import load_registry, overlay_path

    registry = load_registry(Path("datasources.json"))
    pos = registry.get("pos_real")
    assert pos is not None and pos.dsn_env == "GREPBIT_POS_REAL_DSN"
    assert overlay_path(Path("datasources.json"), pos).name == "pos_real.json"
    assert registry.get("iot_spike").overlay is None
    assert registry.get("nowhere") is None


def test_mcp_payloads_list_capabilities_without_values_and_serialize_results():
    from pathlib import Path

    from grepbit.adapters.datasource_registry import load_registry
    from grepbit.adapters.mcp_server import (
        BoundDatasource,
        capabilities_payload,
        result_payload,
    )

    registration = load_registry(Path("datasources.json")).get("iot_spike")
    bound = {
        "iot_spike": BoundDatasource(
            registration, services(_Planner(), _Executor([])), "Asia/Taipei"
        )
    }
    payload = capabilities_payload(bound)
    ds = payload["datasources"][0]
    assert ds["id"] == "iot_spike" and "devices" in [t["name"] for t in ds["tables"]]
    assert ds["absent_concepts"][0]["names"] == ["保固"]
    assert ds["groundable_columns"] == ["devices.status"]
    assert "relay_rules" in payload and payload["revisions"]["prompt"].startswith(
        "plan-classify-json-"
    )
    assert "offline" not in str(payload)  # no stored value leaves through capabilities
    result = ask(
        "有幾台裝置離線？",
        services(_Planner(COUNT_OFFLINE), _Executor([{"row_count": 3}])),
        AskSettings(as_of=AS_OF),
    )
    out = result_payload(result, max_rows=200)
    assert out["status"] == "answered" and out["rows"] == [{"row_count": 3}]
    assert (
        out["parameters"][0]["value"] == "offline"
        and out["plan"]["base_table"] == "devices"
    )
    assert out["relay_rules"]
