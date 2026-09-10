"""Plan client: one strict call, value-free schema payload, validated output."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    PLAN_PROMPT_REVISION,
    ChatCompletionsPlanClient,
    repair_column_refs,
    schema_payload,
)
from grepbit.ports.grounding import GroundingModelError

SETTINGS = GroundingModelSettings(base_url="http://model.local/v1", model="test-model")


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_schema_payload_offers_identifiers_kinds_and_enum_samples_only() -> None:
    payload = schema_payload(iot_schema())
    assert payload["foreign_keys"] == [
        "devices.site_id -> sites.site_id",
        "alerts.device_id -> devices.device_id",
        "readings.device_id -> devices.device_id",
    ]
    devices = next(t for t in payload["tables"] if t["name"] == "devices")
    status = next(c for c in devices["columns"] if c["name"] == "status")
    assert status == {
        "name": "status",
        "kind": "text",
        "type": "text",
        "nullable": True,
        "comment": None,
        "sample_values": ["offline", "online"],
    }
    assert set(devices) == {"name", "comment", "primary_key", "columns"}


def test_propose_makes_one_json_mode_call_and_validates_the_plan() -> None:
    plan = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "month", "month": "2026-07"},
            },
        },
    }
    fake = _FakeClient(json.dumps(plan))
    client = ChatCompletionsPlanClient(SETTINGS, client=fake)
    proposal = client.propose(
        "How many alerts in July 2026?", iot_schema(), as_of="2026-08-15T12:00:00+08:00"
    )
    assert proposal.decision == "plan" and proposal.plan is not None
    assert proposal.plan.base_table == "alerts"
    [call] = fake.calls
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}
    system, schema_message, user = call["messages"]
    assert system["role"] == "system" and "never invent" in system["content"]
    assert schema_message["content"].startswith("Conform exactly to this JSON Schema: ")
    payload = json.loads(user["content"])
    assert payload["prompt_revision"] == PLAN_PROMPT_REVISION
    assert payload["question"] == "How many alerts in July 2026?"
    assert payload["schema"] == schema_payload(iot_schema())


def test_schema_payload_marks_enum_columns_and_lists_their_labels() -> None:
    from t0_helpers import col

    from grepbit.domain.schema_model import ColumnKind

    schema = iot_schema()
    devices = schema.table("devices")
    assert devices is not None
    channel = col(
        "channel",
        ColumnKind.TEXT,
        data_type="channel_t",
        sample_values=["email", "sms"],
        is_enum=True,
    )
    devices = devices.model_copy(update={"columns": [*devices.columns, channel]})
    payload = schema_payload(schema.model_copy(update={"tables": [devices]}))
    entry = next(c for c in payload["tables"][0]["columns"] if c["name"] == "channel")
    assert entry["kind"] == "text" and entry["type"] == "enum channel_t"
    assert entry["sample_values"] == ["email", "sms"]


def test_repair_folds_a_sibling_table_key_into_the_column_reference() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {"column": "status", "table": "devices", "op": "eq", "values": ["x"]},
                {"column": "status", "table": "nowhere", "op": "eq", "values": ["x"]},
            ],
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    first, second = repaired["plan"]["filters"]
    assert first == {
        "column": {"table": "devices", "column": "status"},
        "op": "eq",
        "values": ["x"],
    }
    assert repairs == ["status + table devices -> devices.status"]
    # an unknown table is not guessed away: the sibling key stays and validation fails
    assert second["table"] == "nowhere" and second["column"] == "status"


def test_propose_returns_declines_and_rejects_incoherent_or_malformed_output() -> None:
    decline = json.dumps(
        {"decision": "none", "reason": "ambiguous", "clarification": "avg or max?"}
    )
    proposal = ChatCompletionsPlanClient(SETTINGS, client=_FakeClient(decline)).propose(
        "temperature last month?", iot_schema(), as_of="2026-08-15T12:00:00+08:00"
    )
    assert proposal.decision == "none" and proposal.reason == "ambiguous"
    assert proposal.clarification == "avg or max?"

    for content in (
        "not json",
        json.dumps({"decision": "plan"}),
        json.dumps({"decision": "none"}),
        json.dumps(
            {
                "decision": "plan",
                "plan": {
                    "base_table": "alerts; DROP",
                    "measures": [{"aggregate": "count"}],
                },
            }
        ),
    ):
        client = ChatCompletionsPlanClient(SETTINGS, client=_FakeClient(content))
        with pytest.raises(GroundingModelError) as info:
            client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
        assert info.value.code == "invalid_structured_output"


def test_string_column_references_are_repaired_only_when_unambiguous() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "sum", "column": "downtime_minutes"}],
            "dimensions": ["devices.model"],
            "filters": [{"column": "device_id", "op": "not_null"}],
            "time": {
                "column": "raised_at",
                "scope": {"kind": "month", "month": "2026-07"},
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    plan = repaired["plan"]
    assert plan["measures"][0]["column"] == {
        "table": "alerts",
        "column": "downtime_minutes",
    }
    assert plan["dimensions"] == [{"table": "devices", "column": "model"}]
    # device_id exists in alerts, devices and readings: the base table wins.
    assert plan["filters"][0]["column"] == {"table": "alerts", "column": "device_id"}
    assert plan["time"]["column"] == {"table": "alerts", "column": "raised_at"}
    assert len(repairs) == 4
    # site_id exists in two tables, neither is the base: left alone, so
    # validation fails.
    ambiguous = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "dimensions": ["site_id"],
        },
    }
    still, repairs = repair_column_refs(ambiguous, iot_schema())
    assert still["plan"]["dimensions"] == ["site_id"] and repairs == []
    client = ChatCompletionsPlanClient(
        SETTINGS, client=_FakeClient(json.dumps(ambiguous))
    )
    with pytest.raises(GroundingModelError):
        client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")


def test_repair_drops_null_valued_extra_keys_the_model_adds_to_a_plan() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n", "column": None}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "reason": None,
            "clarification": None,
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert "reason" not in repaired["plan"] and "clarification" not in repaired["plan"]
    assert "column" not in repaired["plan"]["measures"][0]
    assert (
        "dropped null keys: plan.reason, plan.clarification, measures.column" in repairs
    )
    # a null that is not an extra key (a real field left empty) is left alone
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": None,
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert repaired["plan"]["time"] is None and repairs == []


def test_response_format_follows_the_output_mode_setting() -> None:
    loose = ChatCompletionsPlanClient(SETTINGS)
    assert loose.response_format() == {"type": "json_object"}
    strict = ChatCompletionsPlanClient(
        GroundingModelSettings(
            base_url="http://model.local/v1",
            model="test-model",
            structured_output_mode="json_schema",
        )
    )
    fmt = strict.response_format()
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert (
        fmt["json_schema"]["schema"]["$defs"]["QueryPlan"]["additionalProperties"]
        is False
    )


def test_repair_strips_a_qualified_column_and_drops_an_empty_time_object() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "alerts.downtime_minutes"},
                }
            ],
            "dimensions": [{"table": "devices", "column": "devices.model"}],
            "time": {"column": {"table": "alerts", "column": "raised_at"}},
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert repaired["plan"]["measures"][0]["column"]["column"] == "downtime_minutes"
    assert repaired["plan"]["dimensions"][0]["column"] == "model"
    assert "time" not in repaired["plan"]
    assert "dropped time without scope or grain" in repairs
    assert "devices.model -> model" in repairs
