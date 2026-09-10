"""Semantic overlay: reviewed metrics expand in the compiler, absent concepts refuse."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    schema_payload,
)
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.overlay import match_absent_concept, overlay_problems
from grepbit.domain.assumptions import AssumptionSource
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import Measure, PlanError, QueryPlan

OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "test-overlay-v1",
        "metrics": [
            {
                "id": "critical_alerts",
                "names": ["critical alerts", "嚴重告警"],
                "description": "Count of alerts whose severity is critical.",
                "base_table": "alerts",
                "aggregate": "count",
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "severity"},
                        "op": "eq",
                        "values": ["critical"],
                    }
                ],
                "time_column": {"table": "alerts", "column": "raised_at"},
            },
            {
                "id": "offline_fee",
                "names": ["offline fee"],
                "description": "Sum of monthly_fee over offline devices.",
                "base_table": "devices",
                "aggregate": "sum",
                "column": {"table": "devices", "column": "monthly_fee"},
                "filters": [
                    {
                        "column": {"table": "devices", "column": "status"},
                        "op": "eq",
                        "values": ["offline"],
                    }
                ],
                "review_state": "candidate",
            },
        ],
        "absent_concepts": [
            {"names": ["保固", "warranty"], "note": "No warranty data exists."}
        ],
        "column_aliases": [
            {"column": {"table": "devices", "column": "model"}, "names": ["型號"]}
        ],
    }
)


def compile_with_overlay(payload: dict):
    compiler = PlanCompiler(iot_schema(), overlay=OVERLAY)
    return compiler.compile(QueryPlan.model_validate(payload), as_of=AS_OF)


def test_measure_is_either_a_metric_or_an_aggregate() -> None:
    assert Measure(metric="critical_alerts").output_name == "critical_alerts"
    with pytest.raises(ValueError, match="plan_measure_metric_excludes_aggregate"):
        Measure(metric="critical_alerts", aggregate="count")
    with pytest.raises(ValueError, match="plan_measure_requires_aggregate_or_metric"):
        Measure()


def test_reviewed_metric_expands_with_its_filters_and_is_verified() -> None:
    compiled = compile_with_overlay(
        {
            "base_table": "alerts",
            "measures": [{"metric": "critical_alerts"}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "time": {
                "column": {"table": "alerts", "column": "resolved_at"},
                "scope": {"kind": "month", "month": "2026-07"},
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert "COUNT(*) AS critical_alerts" in sql
    assert "alerts.severity = %(f_0)s" in sql
    # The metric prescribes raised_at even though the plan named resolved_at.
    assert "alerts.raised_at >= %(p1_start_1)s" in sql
    assert "resolved_at" not in sql
    assert compiled.verification == "verified"
    assert compiled.lineage.filters == (
        "[critical_alerts] alerts.severity eq critical",
    )
    assert compiled.lineage.measures == (
        "critical_alerts = count(*) [critical_alerts]",
    )
    reviewed = [
        a for a in compiled.assumptions if a.source is AssumptionSource.REVIEWED
    ]
    assert any(
        "critical_alerts = Count of alerts whose severity" in a.text for a in reviewed
    )
    assert any("Time is measured on alerts.raised_at" in a.text for a in reviewed)
    assert not any(
        "Column meanings come from the schema only" in a.text
        for a in compiled.assumptions
    )
    assert compiled.interpretation.startswith("metric critical_alerts over alerts")


def test_extra_question_filters_or_candidate_metrics_are_only_partially_verified() -> (
    None
):
    with_filter = compile_with_overlay(
        {
            "base_table": "alerts",
            "measures": [{"metric": "critical_alerts"}],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "op": "gt",
                    "values": [0],
                }
            ],
        }
    )
    assert with_filter.verification == "partially_verified"
    candidate = compile_with_overlay(
        {"base_table": "devices", "measures": [{"metric": "offline_fee"}]}
    )
    assert candidate.verification == "partially_verified"
    assert any(
        a.source is AssumptionSource.CANDIDATE and "offline_fee =" in a.text
        for a in candidate.assumptions
    )
    mixed = compile_with_overlay(
        {
            "base_table": "alerts",
            "measures": [
                {"metric": "critical_alerts"},
                {"aggregate": "count", "alias": "all_alerts"},
            ],
        }
    )
    assert mixed.verification == "unverified_semantics"


def test_metric_errors_have_stable_codes() -> None:
    with pytest.raises(PlanError) as unknown:
        compile_with_overlay({"base_table": "alerts", "measures": [{"metric": "nope"}]})
    assert unknown.value.code == "unknown_metric"
    with pytest.raises(PlanError) as mismatch:
        compile_with_overlay(
            {"base_table": "devices", "measures": [{"metric": "critical_alerts"}]}
        )
    assert mismatch.value.code == "metric_base_table_mismatch"
    without_overlay = PlanCompiler(iot_schema())
    with pytest.raises(PlanError) as missing:
        without_overlay.compile(
            QueryPlan.model_validate(
                {"base_table": "alerts", "measures": [{"metric": "critical_alerts"}]}
            ),
            as_of=AS_OF,
        )
    assert missing.value.code == "unknown_metric"


def test_overlay_problems_name_every_unknown_identifier() -> None:
    assert overlay_problems(OVERLAY, iot_schema()) == []
    broken = OVERLAY.model_copy(
        update={
            "metrics": [
                OVERLAY.metrics[0].model_copy(update={"base_table": "ghosts"}),
            ]
        }
    )
    assert overlay_problems(broken, iot_schema()) == [
        "metrics.critical_alerts: unknown table ghosts"
    ]


def test_absent_concepts_match_deterministically_across_scripts() -> None:
    assert match_absent_concept("保固內裝置的停機分鐘", OVERLAY) is not None
    assert (
        match_absent_concept("Devices under warranty last month", OVERLAY) is not None
    )
    assert match_absent_concept("Warranties are unrelated words", OVERLAY) is None
    assert match_absent_concept("各型號的告警數", OVERLAY) is None


def test_plan_client_offers_metrics_and_aliases_only_with_an_overlay() -> None:
    plain = schema_payload(iot_schema())
    assert "reviewed_metrics" not in plain
    enriched = schema_payload(iot_schema(), OVERLAY)
    assert [m["id"] for m in enriched["reviewed_metrics"]] == [
        "critical_alerts",
        "offline_fee",
    ]
    devices = next(t for t in enriched["tables"] if t["name"] == "devices")
    assert next(c for c in devices["columns"] if c["name"] == "model")["aliases"] == [
        "型號"
    ]

    class _Fake:
        def __init__(self):
            self.calls = []
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            self.calls.append(kwargs)
            content = json.dumps(
                {
                    "decision": "plan",
                    "plan": {
                        "base_table": "alerts",
                        "measures": [{"metric": "critical_alerts"}],
                    },
                }
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    fake = _Fake()
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://model.local/v1", model="m"), client=fake
    )
    proposal = client.propose(
        "嚴重告警", iot_schema(), as_of="2026-08-15T12:00:00+08:00", overlay=OVERLAY
    )
    assert (
        proposal.plan is not None
        and proposal.plan.measures[0].metric == "critical_alerts"
    )
    assert (
        "reviewed_metrics are business definitions"
        in fake.calls[0]["messages"][0]["content"]
    )
    client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert (
        "reviewed_metrics are business definitions"
        not in fake.calls[1]["messages"][0]["content"]
    )


def test_absent_concept_all_of_matches_split_phrasings_in_any_order() -> None:
    from grepbit.application.overlay import match_absent_concept
    from grepbit.domain.overlay import SemanticOverlay

    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "d",
            "revision": "t",
            "absent_concepts": [
                {
                    "names": ["訂單狀態"],
                    "note": "no order status",
                    "all_of": [["訂單", "狀態"], ["order", "status"]],
                }
            ],
        }
    )
    assert match_absent_concept("訂單筆數最多的狀態是哪一種？", overlay) is not None
    assert (
        match_absent_concept("What is the status of most orders?", overlay) is not None
    )
    assert match_absent_concept("各門市的訂單筆數", overlay) is None  # 狀態 absent
    assert match_absent_concept("各運送狀態的紀錄筆數", overlay) is None  # 訂單 absent
