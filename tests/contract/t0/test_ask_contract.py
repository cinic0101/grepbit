"""The ask orchestration over fakes: gates, planning, repairs, grounding, execution."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
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
        self.last_raw_output: str | None = None
        self.last_repair_output: str | None = None
        self.last_model_repair_turns = 0

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


def test_no_window_growth_survives_unlisted_period_wording():
    proposal = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
            },
            "growth": [{"measure": "n"}],
        },
    }
    executor = _Executor([])
    result = ask(
        "每個月的告警數與月成長率",
        services(_Planner(proposal), executor),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered"
    assert not any(r.startswith("dropped grain") for r in result.shape_repairs)
    assert result.plan.time.grain is not None and result.plan.growth
    assert executor.executed


@pytest.mark.parametrize(
    "question",
    [
        "每個月的告警數",
        "各月のアラート件数",
        "Monthly alert counts",
        "告警數",
        "unlisted wording",
    ],
)
@pytest.mark.parametrize("kind", ["count", "share", "growth"])
def test_grain_is_not_deleted_by_absent_language_pack_words(question, kind):
    plan = {
        "base_table": "alerts",
        "measures": [{"aggregate": "count", "alias": "n"}],
        "time": {
            "column": {"table": "alerts", "column": "raised_at"},
            "grain": "month",
        },
        "order": [{"field": "period_start", "direction": "asc"}],
    }
    if kind == "share":
        plan["measures"][0]["share_of_total"] = True
        plan["dimensions"] = [{"table": "devices", "column": "model"}]
    if kind == "growth":
        plan["growth"] = [{"measure": "n"}]
    executor = _Executor([])
    result = ask(
        question,
        services(_Planner({"decision": "plan", "plan": plan}), executor),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered"
    assert result.plan.time is not None and result.plan.time.grain.value == "month"
    assert result.plan.order[0].field == "period_start"
    assert not any(r.startswith("dropped grain") for r in result.shape_repairs)
    assert not any("question named no period" in a for a in result.assumptions)
    assert result.interpretation and result.assumptions and executor.executed


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


def test_a_malformed_plan_fails_with_its_raw_text_kept() -> None:
    planner = _Planner(GroundingModelError("invalid_structured_output", 2))
    planner.last_raw_output = '{"decision": "plan", "ratio": {}}'
    planner.last_repair_output = "still wrong"
    planner.last_model_repair_turns = 1
    result = ask("x", services(planner, _Executor([])), AskSettings(as_of=AS_OF))
    assert result.status == "failed" and result.reason == "invalid_structured_output"
    assert result.raw_output == '{"decision": "plan", "ratio": {}}'
    assert result.raw_output_repair == "still wrong"
    assert result.model_repair_turns == 1
    assert result.model_retries == 0


def test_a_plan_from_the_repair_turn_answers_and_keeps_the_slip() -> None:
    planner = _Planner(COUNT_OFFLINE)
    planner.last_raw_output = "{slipped"
    planner.last_model_repair_turns = 1
    result = ask(
        "offline 的裝置有幾台",
        services(planner, _Executor([{"row_count": 1}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered"
    assert result.model_repair_turns == 1 and result.raw_output == "{slipped"


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


def test_capabilities_list_the_bound_datasources_and_name_the_unbound_by_reason():
    from pathlib import Path

    from grepbit.adapters.datasource_registry import load_registry
    from grepbit.adapters.mcp_server import BoundDatasource, collect_capabilities

    registry = load_registry(Path("datasources.json"))
    iot = registry.get("iot_spike")
    ready = BoundDatasource(iot, services(_Planner(), _Executor([])), "Asia/Taipei")
    bound: dict = {}

    def get(datasource_id: str) -> BoundDatasource:
        if datasource_id == "iot_spike":
            bound[datasource_id] = ready
            return ready
        if datasource_id == "pos_test":
            raise RuntimeError("dsn_env_missing:GREPBIT_POS_TEST_DSN")
        raise ConnectionError("password=secret host=db.internal")  # driver-style

    payload = collect_capabilities(registry.datasources, get, bound)
    assert [d["id"] for d in payload["datasources"]] == ["iot_spike"]
    assert payload["unavailable"]["pos_test"] == "dsn_env_missing:GREPBIT_POS_TEST_DSN"
    assert payload["unavailable"]["pos_real"] == "bind_failed:ConnectionError"
    assert "secret" not in str(payload) and "db.internal" not in str(payload)


def test_a_negative_share_is_flagged_as_a_net_total() -> None:
    from decimal import Decimal

    from grepbit.application.ask import negative_share_warning
    from grepbit.domain.plan import QueryPlan

    plan = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "share_of_total": True,
                    "alias": "downtime_share",
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
        }
    )
    rows = [
        {"model": "A", "downtime_share": 1.02},
        {"model": "B", "downtime_share": -0.02},
    ]
    warning = negative_share_warning(plan, rows)
    assert warning is not None and warning.startswith("downtime_share is negative")
    assert negative_share_warning(plan, [{"model": "A", "downtime_share": 1.0}]) is None
    assert (
        negative_share_warning(plan, [{"model": "A", "downtime_share": None}]) is None
    )
    assert (
        negative_share_warning(plan, [{"model": "A", "downtime_share": Decimal("0.5")}])
        is None
    )


def test_a_dimension_fixed_by_an_equality_filter_is_dropped_with_an_assumption() -> (
    None
):
    # store_partial_name_jan: by store_name beside store_name = X returns the same
    # value on every row (owner's decision, 2026-09-11)
    plan = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "dimensions": [{"table": "devices", "column": "status"}],
            "measures": [{"aggregate": "count", "alias": "n"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["offline"],
                }
            ],
        },
    }
    result = ask(
        "offline 的裝置有幾台",
        services(_Planner(plan), _Executor([{"n": 1}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered" and result.plan is not None
    assert result.plan.dimensions == []
    assert result.constant_dimensions_dropped == ["devices.status"]
    assert "GROUP BY" not in (result.sql or "")
    assert any(
        "devices.status is not returned as a column" in a for a in result.assumptions
    )


def test_a_share_asked_for_one_group_keeps_its_dimension() -> None:
    # holdout 2 q21: by store, share of total, where store = X. Dropping the
    # constant dimension left an ungrouped share and answered 1.232; the
    # after-share selection over every store is the reading
    plan = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "dimensions": [{"table": "devices", "column": "status"}],
            "measures": [{"aggregate": "count", "alias": "n", "share_of_total": True}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["offline"],
                }
            ],
        },
    }
    result = ask(
        "offline 的裝置佔比",
        services(_Planner(plan), _Executor([{"status": "offline", "n": 0.4}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered" and result.plan is not None
    assert [d.id for d in result.plan.dimensions] == ["devices.status"]
    assert result.constant_dimensions_dropped == []
    assert "[after share]" in " ".join(result.lineage["filters"])


def test_repairs_split_into_shape_variants_and_meaning_normalisations() -> None:
    plan = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "dimensions": [{"table": "devices", "column": "status"}],
            "measures": [{"aggregate": "count", "alias": "n"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["offline"],
                }
            ],
        },
    }
    planner = _Planner(plan)
    planner.last_repairs = ["status -> devices.status"]
    result = ask(
        "offline 的裝置有幾台",
        services(planner, _Executor([{"n": 1}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.shape_variants == ["status -> devices.status"]
    assert result.meaning_normalisations == [
        "dropped constant dimensions: devices.status"
    ]


def test_a_named_concept_the_plan_leaves_no_trace_of_is_a_clarify() -> None:
    """returns_dec_gap, twice on 2026-09-11: 2025年12月退貨金額 answered as the month's
    total sales. The concept words come from the shape pack; the plan must
    reference a column, metric or named segment that carries the concept."""

    import dataclasses

    from grepbit.domain.language_pack import ShapePack

    pack = ShapePack.model_validate(
        {
            "revision": "t",
            "concepts": [
                {
                    "id": "critical",
                    "words": ["嚴重", "critical"],
                    "column_keywords": ["severity", "critical"],
                }
            ],
        }
    )
    dropped = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
        },
    }
    svc = dataclasses.replace(
        services(_Planner(dropped), _Executor([{"n": 9}])), shape_pack=pack
    )
    result = ask("2026年7月嚴重告警數", svc, AskSettings(as_of=AS_OF))
    assert result.status == "clarify" and result.reason == "concept_not_mapped"
    assert result.unmapped_concepts == ["critical"]
    assert "'嚴重'" in (result.clarification or "")
    # a filter on a column carrying the keyword maps it
    filtered = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "eq",
                    "values": ["critical"],
                }
            ],
        },
    }
    svc = dataclasses.replace(
        services(
            _Planner(filtered),
            _Executor([{"n": 2}]),
            present=("offline", "online", "critical"),
        ),
        shape_pack=pack,
    )
    assert ask("critical alerts", svc, AskSettings(as_of=AS_OF)).status == "answered"
    # a reviewed metric whose name carries the concept maps it too (checked on
    # the function: this file's overlay has no such metric to compile)
    from grepbit.application.shapes import unmapped_concepts
    from grepbit.domain.plan import QueryPlan

    named_overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
            "metrics": [
                {
                    "id": "urgent_count",
                    "names": ["嚴重告警數"],
                    "description": "count of critical alerts",
                    "base_table": "alerts",
                    "aggregate": "count",
                }
            ],
        }
    )
    metric_plan = QueryPlan.model_validate(
        {"base_table": "alerts", "measures": [{"metric": "urgent_count"}]}
    )
    assert (
        unmapped_concepts("嚴重告警數", metric_plan, pack, named_overlay, set()) == []
    )
    assert unmapped_concepts("嚴重告警數", metric_plan, pack, None, set()) == [
        ("critical", "嚴重")
    ]
    # a question without the concept word is untouched
    svc = dataclasses.replace(
        services(_Planner(dropped), _Executor([{"n": 9}])), shape_pack=pack
    )
    assert ask("告警數", svc, AskSettings(as_of=AS_OF)).status == "answered"


def test_growth_is_not_deleted_by_lexical_absence_even_in_a_legacy_pack() -> None:
    """Owner-approved ruler: a missing rate word is not evidence of intent.

    Supersedes the narrow-rule opt-in test. This remains red until the
    production deletion mechanism is retired after the ruler checkpoint.
    """

    import dataclasses

    from grepbit.domain.language_pack import ShapePack

    def plan_with_growth():
        return {
            "decision": "plan",
            "plan": {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "n"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {
                        "kind": "relative",
                        "unit": "month",
                        "offset": -2,
                        "length": 2,
                    },
                    "grain": "month",
                },
                "growth": [{"measure": "n"}],
            },
        }

    rows = [{"period_start": "x", "n": 1}]
    # default pack: the model's growth stays, whatever the wording
    kept = ask(
        "上個月和前一個月的告警數比較",
        services(_Planner(plan_with_growth()), _Executor(rows)),
        AskSettings(as_of=AS_OF),
    )
    assert kept.plan is not None and len(kept.plan.growth) == 1
    # Even a legacy pack naming comparison words must not delete growth.
    pack = ShapePack.model_validate(
        {
            "revision": "t",
            "rule_triggers": {
                "growth_comparison": ["比較", "compare"],
                "growth": ["成長率", "百分之", "growth"],
            },
        }
    )
    svc = dataclasses.replace(
        services(_Planner(plan_with_growth()), _Executor(rows)), shape_pack=pack
    )
    compared = ask("上個月和前一個月的告警數比較", svc, AskSettings(as_of=AS_OF))
    assert compared.plan is not None and len(compared.plan.growth) == 1
    assert "LAG(" in (compared.sql or "")
    assert not any(
        item.startswith("dropped growth") for item in compared.meaning_normalisations
    )
    svc = dataclasses.replace(
        services(_Planner(plan_with_growth()), _Executor(rows)), shape_pack=pack
    )
    rate = ask("本月告警數比上月多百分之幾", svc, AskSettings(as_of=AS_OF))
    assert rate.plan is not None and len(rate.plan.growth) == 1
    svc = dataclasses.replace(
        services(_Planner(plan_with_growth()), _Executor(rows)), shape_pack=pack
    )
    plain_growth = ask("本月告警數的成長", svc, AskSettings(as_of=AS_OF))
    assert plain_growth.plan is not None and len(plain_growth.plan.growth) == 1
