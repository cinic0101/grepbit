"""Coverage audit client: plan payload, one JSON call, uncovered concepts."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.coverage_client import (
    ChatCompletionsCoverageClient,
    plan_payload,
)
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import CoverageReport, QueryPlan
from grepbit.ports.coverage import CoverageVerifierPort
from grepbit.ports.grounding import GroundingModelError

SETTINGS = GroundingModelSettings(base_url="http://model.local/v1", model="test-model")


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


def compiled_downtime():
    plan = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                }
            ],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "month", "month": "2026-07"},
            },
        }
    )
    return PlanCompiler(iot_schema()).compile(plan, as_of=AS_OF)


def test_plan_payload_carries_lineage_and_the_columns_used_with_comments() -> None:
    payload = plan_payload(compiled_downtime(), iot_schema())
    assert (
        payload["interpretation"]
        == "sum(alerts.downtime_minutes) over alerts; for 2026-07"
    )
    assert payload["measures"] == [
        "sum_downtime_minutes = sum(alerts.downtime_minutes)"
    ]
    assert [c["id"] for c in payload["columns_used"]] == [
        "alerts.downtime_minutes",
        "alerts.raised_at",
    ]
    assert set(payload["columns_used"][0]) == {
        "id",
        "type",
        "comment",
        "table_comment",
        "sample_values",
    }


def test_verify_maps_concepts_and_reports_uncovered_ones() -> None:
    content = json.dumps(
        {
            "concepts": [
                {"concept": "downtime", "mapped_to": "sum(alerts.downtime_minutes)"},
                {"concept": "warranty", "mapped_to": None},
                {
                    "concept": "July 2026",
                    "mapped_to": "time window on alerts.raised_at",
                },
            ]
        }
    )
    fake = _FakeClient(content)
    verifier: CoverageVerifierPort = ChatCompletionsCoverageClient(
        SETTINGS, client=fake
    )
    report = verifier.verify(
        "Total downtime of devices under warranty in July 2026",
        compiled_downtime(),
        iot_schema(),
    )
    assert isinstance(report, CoverageReport)
    assert report.uncovered == ["warranty"]
    assert report.covered is False
    [call] = fake.calls
    assert call["response_format"] == {"type": "json_object"}
    user = json.loads(call["messages"][2]["content"])
    assert user["question"] == "Total downtime of devices under warranty in July 2026"
    assert user["plan"]["base_table"] == "alerts"


def test_verify_rejects_malformed_output() -> None:
    for content in ("nope", json.dumps({"concepts": [{"mapped_to": "x"}]})):
        client = ChatCompletionsCoverageClient(SETTINGS, client=_FakeClient(content))
        with pytest.raises(GroundingModelError) as info:
            client.verify("q", compiled_downtime(), iot_schema())
        assert info.value.code == "invalid_structured_output"
    assert CoverageReport(concepts=[]).covered is True
