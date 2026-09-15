"""Exact measured display subset; canonical wire and default order stay intact."""

import json

import jsonschema
import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.adapters.litellm.plan_wire import shown_schema
from grepbit.domain.plan import OrderSpec


def messages(kind="rows", allow_rows=True):
    return ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="offline"),
        allow_rows=allow_rows,
        query_kind=kind,
    ).build_messages(
        "List device_id by device_id.", iot_schema(), as_of=AS_OF.isoformat()
    )


def display():
    return json.loads(messages()[1]["content"].split(": ", 1)[1])


def test_explicit_display_is_exact_measured_subset_with_optional_direction():
    schema = display()
    full = shown_schema(allow_rows=True)
    p = schema["properties"]["plan"]
    assert set(p["properties"]) == {"base_table", "rows", "filters", "order", "limit"}
    assert p["required"] == ["base_table", "rows"]
    for key, field in p["properties"].items():
        assert field == full["properties"]["plan"]["properties"][key]
    for key in ["reason", "clarification", "decision"]:
        assert schema["properties"][key] == full["properties"][key]
    assert p["properties"]["order"]["items"]["required"] == ["field"]
    assert OrderSpec(field="id").direction == "desc"
    assert (
        json.loads(messages()[2]["content"])["prompt_revision"]
        == "details-schema-only-v21-study"
    )


@pytest.mark.parametrize("allow_rows", [False, True])
def test_default_display_remains_full_and_does_not_pick_explicit_policy(allow_rows):
    result = messages("default", allow_rows)
    assert json.loads(result[1]["content"].split(": ", 1)[1]) == shown_schema(
        allow_rows=allow_rows
    )
    assert (
        json.loads(result[2]["content"])["prompt_revision"]
        != "details-schema-only-v21-study"
    )


@pytest.mark.parametrize(
    "payload,valid",
    [
        ({"decision": "none", "reason": "semantic_gap"}, True),
        ({"decision": "none", "reason": "unsupported"}, True),
        ({"decision": "none", "reason": "ambiguous"}, True),
        ({"decision": "none"}, False),
        ({"decision": "plan"}, False),
        (
            {
                "decision": "plan",
                "plan": {"base_table": "devices", "measures": [{"aggregate": "count"}]},
            },
            False,
        ),
        (
            {
                "decision": "plan",
                "plan": {"base_table": "devices", "rows": {"all_columns": True}},
            },
            True,
        ),
        (
            {
                "decision": "plan",
                "plan": {
                    "base_table": "devices",
                    "rows": {"columns": ["devices.device_id"]},
                    "order": [{"field": "device_id"}],
                },
            },
            True,
        ),
        (
            {
                "decision": "plan",
                "plan": {
                    "base_table": "devices",
                    "rows": {"columns": ["devices.device_id"]},
                    "columns": ["devices.device_id"],
                },
            },
            False,
        ),
    ],
)
def test_display_plan_and_refusal_branch_boundaries(payload, valid):
    assert jsonschema.Draft202012Validator(display()).is_valid(payload) is valid


def test_candidate_reference_forms_remain_bound_and_guided_mode_unchanged():
    full = shown_schema(allow_rows=True, has_candidates=True)
    narrowed = shown_schema(allow_rows=True, has_candidates=True, explicit_rows=True)
    assert (
        narrowed["properties"]["plan"]["properties"]["filters"]
        == full["properties"]["plan"]["properties"]["filters"]
    )
    with pytest.raises(ValueError, match="row_queries_disabled"):
        shown_schema(explicit_rows=True)
    cfg = GroundingModelSettings(
        base_url="http://unused", model="offline", structured_output_mode="json_schema"
    )
    default = ChatCompletionsPlanClient(cfg, allow_rows=True)
    explicit = ChatCompletionsPlanClient(cfg, allow_rows=True, query_kind="rows")
    assert explicit.response_format(has_candidates=True) == default.response_format(
        has_candidates=True
    )
