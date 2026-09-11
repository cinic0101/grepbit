"""Plan client: one strict call, value-free schema payload, validated output."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from t0_helpers import iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    PLAN_PROMPT_REVISION,
    ChatCompletionsPlanClient,
    repair_column_refs,
    schema_payload,
)
from grepbit.domain.plan import PlanProposal
from grepbit.ports.grounding import GroundingModelError

SETTINGS = GroundingModelSettings(base_url="http://model.local/v1", model="test-model")
NO_REPAIR = GroundingModelSettings(
    base_url="http://model.local/v1", model="test-model", repair_turns=0
)


class _FakeClient:
    """Returns ``content`` on every call, or the items of a list in turn."""

    def __init__(self, content: str | list[str]) -> None:
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._contents = [content] if isinstance(content, str) else list(content)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents[min(len(self.calls) - 1, len(self._contents) - 1)]
        message = SimpleNamespace(content=content)
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
        client = ChatCompletionsPlanClient(NO_REPAIR, client=_FakeClient(content))
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
    # devices.model is the shown form and is not a repair; the three bare names are
    assert len(repairs) == 3
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
    # a qualified column inside its own reference is an unambiguous way to write
    # it (owner's decision 2026-09-11): rewritten, not counted
    assert "devices.model -> model" not in repairs


def test_repair_reanchors_a_current_window_longer_than_one_unit() -> None:
    def payload(scope):
        return {
            "decision": "plan",
            "plan": {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": scope,
                },
            },
        }

    forward = {"kind": "relative", "unit": "day", "offset": 0, "length": 30}
    repaired, repairs = repair_column_refs(payload(forward), iot_schema())
    assert repaired["plan"]["time"]["scope"]["offset"] == -30
    assert repairs == ["relative window offset 0 length 30 -> offset -30"]
    # month to date and the current unit alone are what they say
    for scope in (
        {
            "kind": "relative",
            "unit": "month",
            "offset": 0,
            "length": 1,
            "to_date": True,
        },
        {"kind": "relative", "unit": "day", "offset": 0, "length": 1},
        {"kind": "relative", "unit": "day", "offset": -7, "length": 7},
    ):
        untouched, repairs = repair_column_refs(payload(dict(scope)), iot_schema())
        assert untouched["plan"]["time"]["scope"]["offset"] == scope["offset"]
        assert repairs == []


def test_repair_drops_a_bare_aggregate_written_beside_a_ratio() -> None:
    ratio = {
        "numerator": {
            "aggregate": "count",
            "column": {"table": "alerts", "column": "device_id"},
        },
        "denominator": {"aggregate": "count"},
    }
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "share", "ratio": ratio}],
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert "aggregate" not in repaired["plan"]["measures"][0]
    assert repairs == ["dropped aggregate count beside ratio"]
    # an aggregate with its own column beside a ratio stays: two measures in one
    payload["plan"]["measures"] = [
        {
            "aggregate": "sum",
            "column": {"table": "alerts", "column": "downtime_minutes"},
            "ratio": ratio,
        }
    ]
    untouched, repairs = repair_column_refs(payload, iot_schema())
    assert untouched["plan"]["measures"][0]["aggregate"] == "sum" and repairs == []


def test_repair_lifts_a_plan_level_ratio_into_a_measure() -> None:
    # the shape seen for 會員交易佔比: both operands spelled out as measures,
    # the ratio written beside them on the plan
    member = {
        "aggregate": "count",
        "filters": [
            {"column": {"table": "alerts", "column": "device_id"}, "op": "not_null"}
        ],
    }
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                dict(member, alias="member_count"),
                {"aggregate": "count", "alias": "total_count"},
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                },
            ],
            "ratio": {"numerator": member, "denominator": {"aggregate": "count"}},
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    plan = repaired["plan"]
    assert "ratio" not in plan
    assert plan["measures"] == [
        {
            "aggregate": "sum",
            "column": {"table": "alerts", "column": "downtime_minutes"},
        },
        {"ratio": {"numerator": member, "denominator": {"aggregate": "count"}}},
    ]
    assert repairs == [
        "dropped measure member_count spelled inside the ratio",
        "dropped measure total_count spelled inside the ratio",
        "lifted plan-level ratio into a measure",
    ]
    PlanProposal.model_validate(repaired)

    # a measure that already carries a ratio: nothing moves, validation fails as before
    twice = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {"ratio": {"numerator": member, "denominator": {"aggregate": "count"}}}
            ],
            "ratio": {"numerator": member, "denominator": {"aggregate": "count"}},
        },
    }
    untouched, repairs = repair_column_refs(twice, iot_schema())
    assert "ratio" in untouched["plan"] and repairs == []
    with pytest.raises(ValidationError):
        PlanProposal.model_validate(untouched)


def test_propose_keeps_the_raw_text_of_a_malformed_output() -> None:
    client = ChatCompletionsPlanClient(NO_REPAIR, client=_FakeClient("not json"))
    with pytest.raises(GroundingModelError):
        client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert client.last_raw_output == "not json"
    assert client.last_model_repair_turns == 0
    # a valid call clears it
    good = json.dumps(
        {
            "decision": "plan",
            "plan": {"base_table": "alerts", "measures": [{"aggregate": "count"}]},
        }
    )
    client = ChatCompletionsPlanClient(SETTINGS, client=_FakeClient(good))
    client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert client.last_raw_output is None


def test_repair_takes_a_missing_relative_unit_from_the_grain() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
                "scope": {
                    "kind": "relative",
                    "offset": 0,
                    "length": 1,
                    "to_date": True,
                },
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert repaired["plan"]["time"]["scope"]["unit"] == "month"
    assert repairs == ["relative window without unit -> unit month (from grain)"]
    del payload["plan"]["time"]["grain"]
    del payload["plan"]["time"]["scope"]["unit"]
    _, repairs = repair_column_refs(payload, iot_schema())
    assert (
        repairs == []
    )  # nothing to take the unit from: validation will fail as before


def test_repair_reaches_into_without() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "measures": [{"aggregate": "count"}],
            "without": {
                "table": "alerts",
                "filters": [{"column": "severity", "op": "eq", "values": ["critical"]}],
                "time": {
                    "column": "raised_at",
                    "scope": {"kind": "month", "month": "2026-07"},
                },
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    without = repaired["plan"]["without"]
    assert without["filters"][0]["column"] == {"table": "alerts", "column": "severity"}
    assert without["time"]["column"] == {"table": "alerts", "column": "raised_at"}
    assert set(repairs) == {
        "severity -> alerts.severity",
        "raised_at -> alerts.raised_at",
    }


def test_repair_reaches_into_latest() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [{"table": "devices", "column": "model"}],
            "latest": {
                "order_by": [{"column": "raised_at", "direction": "desc"}],
                "take": ["severity", "alerts.raised_at"],
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    latest = repaired["plan"]["latest"]
    assert latest["order_by"][0]["column"] == {"table": "alerts", "column": "raised_at"}
    assert latest["take"] == [
        {"table": "alerts", "column": "severity"},
        {"table": "alerts", "column": "raised_at"},
    ]
    # the two bare names are variants; a qualified string is the shown form
    assert len(repairs) == 2


def test_repair_mends_references_anywhere_in_the_plan() -> None:
    """The three slips holdout 3 run 5 produced: a sibling table beside a string
    column inside latest.order_by, a qualified column inside a take reference,
    and a qualified column inside without.time.column."""

    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [{"table": "devices", "column": "devices.model"}],
            "latest": {
                "order_by": [
                    {"column": "raised_at", "table": "alerts", "direction": "desc"}
                ],
                "take": [{"column": "alerts.severity", "table": "alerts"}],
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    plan = repaired["plan"]
    assert plan["dimensions"] == [{"table": "devices", "column": "model"}]
    assert plan["latest"]["order_by"][0] == {
        "column": {"table": "alerts", "column": "raised_at"},
        "direction": "desc",
    }
    assert plan["latest"]["take"] == [{"table": "alerts", "column": "severity"}]
    assert set(repairs) == {
        "raised_at + table alerts -> alerts.raised_at",
    }
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "measures": [{"aggregate": "count"}],
            "without": {
                "table": "alerts",
                "time": {
                    "column": {"column": "alerts.raised_at", "table": "alerts"},
                    "scope": {"kind": "month", "month": "2026-07"},
                },
            },
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert repaired["plan"]["without"]["time"]["column"] == {
        "table": "alerts",
        "column": "raised_at",
    }
    assert repairs == []
    # a ratio operand written as a string column is coerced too
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "alias": "share",
                    "ratio": {
                        "numerator": {"aggregate": "sum", "column": "downtime_minutes"},
                        "denominator": {"aggregate": "count"},
                    },
                }
            ],
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    numerator = repaired["plan"]["measures"][0]["ratio"]["numerator"]
    assert numerator["column"] == {"table": "alerts", "column": "downtime_minutes"}


def test_repair_unwraps_a_dimension_written_like_an_order_by_item() -> None:
    """Prompt v13 taught {"column": <ref>} for latest.order_by; the model then
    wrote dimensions the same way and every grouped question failed."""

    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "dimensions": [
                {"column": {"table": "devices", "column": "model"}, "table": "devices"}
            ],
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    assert repaired["plan"]["dimensions"] == [{"table": "devices", "column": "model"}]
    assert repairs == ["dimensions: unwrapped column reference"]


def test_repair_strips_a_qualified_output_name_in_order_and_having() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [{"table": "devices", "column": "devices.model"}],
            "measures": [{"aggregate": "count", "alias": "alerts_n"}],
            "order": [
                {"field": "alerts_n", "direction": "desc"},
                {"field": "devices.model", "direction": "asc"},
            ],
            "having": [{"field": "alerts.alerts_n", "op": "gt", "value": 3}],
        },
    }
    repaired, repairs = repair_column_refs(payload, iot_schema())
    plan = repaired["plan"]
    assert plan["order"][1]["field"] == "model"
    assert plan["having"][0]["field"] == "alerts_n"
    # qualified output names are rewritten without a record (unambiguous)
    assert not any(r.startswith(("order.field", "having.field")) for r in repairs)
    # a qualified name that is not an output stays for validation to reject
    payload["plan"]["order"] = [{"field": "devices.site_id", "direction": "asc"}]
    _, repairs = repair_column_refs(payload, iot_schema())
    assert not any(r.startswith("order.field") for r in repairs)


def test_a_malformed_plan_gets_one_repair_turn_with_the_validation_errors() -> None:
    # an aggregate outside the enum and a ratio missing its denominator: shapes
    # no normalisation accepts (q49's numerator-beside-ratio is accepted since
    # contract v2, see test_plan_wire_contract.py)
    slipped = json.dumps(
        {
            "decision": "plan",
            "plan": {
                "base_table": "alerts",
                "measures": [
                    {
                        "alias": "r",
                        "aggregate": "total",
                        "column": "alerts.downtime_minutes",
                        "ratio": {"numerator": {"aggregate": "count"}},
                    }
                ],
            },
        }
    )
    fixed = json.dumps(
        {
            "decision": "plan",
            "plan": {
                "base_table": "alerts",
                "measures": [
                    {
                        "alias": "r",
                        "ratio": {
                            "numerator": {
                                "aggregate": "count_distinct",
                                "column": "alerts.device_id",
                            },
                            "denominator": {"aggregate": "count"},
                        },
                    }
                ],
            },
        }
    )
    fake = _FakeClient([slipped, fixed])
    client = ChatCompletionsPlanClient(SETTINGS, client=fake)
    proposal = client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert proposal.plan is not None and proposal.plan.measures[0].ratio is not None
    assert len(fake.calls) == 2
    assert client.last_model_repair_turns == 1
    assert client.last_raw_output == slipped  # the slip is kept for classification
    assert client.last_repair_output is None
    repair_messages = fake.calls[1]["messages"]
    assert (
        repair_messages[: len(fake.calls[0]["messages"])] == fake.calls[0]["messages"]
    )
    assert repair_messages[-2] == {"role": "assistant", "content": slipped}
    errors = repair_messages[-1]["content"]
    assert repair_messages[-1]["role"] == "user"
    assert "did not validate" in errors
    assert "plan.measures.0.ratio.denominator: Field required" in errors
    assert "plan.measures.0.aggregate: Input should be" in errors

    # a second malformed answer is the end of the road: both texts kept
    fake = _FakeClient([slipped, "still not json"])
    client = ChatCompletionsPlanClient(SETTINGS, client=fake)
    with pytest.raises(GroundingModelError) as info:
        client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert info.value.code == "invalid_structured_output"
    assert len(fake.calls) == 2
    assert client.last_raw_output == slipped
    assert client.last_repair_output == "still not json"
    assert client.last_model_repair_turns == 1

    # repair_turns=0 is the old behaviour: one call, no repair
    fake = _FakeClient([slipped, fixed])
    client = ChatCompletionsPlanClient(NO_REPAIR, client=fake)
    with pytest.raises(GroundingModelError):
        client.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert len(fake.calls) == 1
