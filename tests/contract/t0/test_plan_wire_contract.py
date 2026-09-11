"""Contract v2: the compact flat schema the planner is shown, the variants the
normaliser accepts, and the rule packs a question switches on."""

from __future__ import annotations

import json

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.litellm.plan_client import (
    PLAN_PROMPT_REVISION,
    repair_column_refs,
    rules_for,
)
from grepbit.adapters.litellm.plan_wire import shown_schema, shown_schema_text
from grepbit.domain.plan import PlanProposal

jsonschema = pytest.importorskip("jsonschema")

CANONICAL = [
    # a grouped sum with a window
    {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": "alerts.downtime_minutes",
                    "alias": "downtime",
                }
            ],
            "dimensions": ["devices.model"],
            "filters": [
                {"column": "alerts.severity", "op": "eq", "values": ["critical"]}
            ],
            "time": {
                "column": "alerts.raised_at",
                "scope": {"kind": "month", "month": "2026-07"},
            },
            "order": [{"field": "downtime", "direction": "desc"}],
            "limit": 3,
        },
    },
    # a ratio with operand filters, written flat
    {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "alias": "critical_share",
                    "numerator": {
                        "aggregate": "count",
                        "filters": [
                            {
                                "column": "alerts.severity",
                                "op": "eq",
                                "values": ["critical"],
                            }
                        ],
                    },
                    "denominator": {"aggregate": "count"},
                }
            ],
        },
    },
    # the latest row per entity
    {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": ["devices.model"],
            "latest": {
                "order_by": [{"column": "alerts.raised_at", "direction": "desc"}],
                "take": ["alerts.severity", "alerts.raised_at"],
            },
        },
    },
    # entities with no activity
    {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "dimensions": ["devices.model"],
            "measures": [{"aggregate": "count", "alias": "device_count"}],
            "without": {
                "table": "alerts",
                "time": {
                    "column": "alerts.raised_at",
                    "scope": {
                        "kind": "relative",
                        "unit": "day",
                        "offset": -30,
                        "length": 30,
                    },
                },
            },
        },
    },
    {"decision": "none", "reason": "ambiguous", "clarification": "avg or max?"},
]


def test_the_shown_schema_is_compact_and_accepts_every_canonical_example() -> None:
    text = shown_schema_text()
    assert len(text) < 7000  # the pydantic schema was 11,838 characters
    assert "title" not in text and "description" not in text
    validator = jsonschema.Draft202012Validator(shown_schema())
    for example in CANONICAL:
        validator.validate(example)
        # and every shown-form example is a valid plan after normalisation
        payload, repairs = repair_column_refs(
            json.loads(json.dumps(example)), iot_schema()
        )
        PlanProposal.model_validate(payload)
        assert repairs == [], (example, repairs)


def test_accepted_variants_normalise_without_guessing() -> None:
    # batch 1 q49, five runs in a row: numerator beside a partial ratio
    q49 = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [{"column": "model", "table": "devices"}],
            "measures": [
                {
                    "alias": "critical_rate",
                    "ratio": {"denominator": {"aggregate": "count"}},
                    "numerator": {
                        "aggregate": "count",
                        "filters": [
                            {
                                "column": {"column": "severity", "table": "alerts"},
                                "op": "eq",
                                "values": ["critical"],
                            }
                        ],
                    },
                }
            ],
        },
    }
    payload, repairs = repair_column_refs(q49, iot_schema())
    plan = PlanProposal.model_validate(payload).plan
    assert plan is not None and plan.measures[0].ratio is not None
    assert plan.measures[0].ratio.numerator.filters[0].column.id == "alerts.severity"
    # {"column": "model", "table": "devices"} is a plain reference, not a variant
    assert repairs == []

    # fu_base_payment, two runs: a redundant table beside a reference on a measure
    # and a dimension wrapped like an order_by item
    fu = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [
                {"column": {"table": "devices", "column": "model"}, "table": "devices"}
            ],
            "measures": [
                {
                    "aggregate": "sum",
                    "alias": "downtime",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "table": "alerts",
                }
            ],
        },
    }
    payload, repairs = repair_column_refs(fu, iot_schema())
    PlanProposal.model_validate(payload)
    assert repairs == [
        "measures: dropped table beside the column reference",
        "dimensions: unwrapped column reference",
    ]

    # the 12B control model: an alias on a dimension, a grain on the plan
    small = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": [
                {"column": {"column": "model", "table": "devices"}, "alias": "型號"}
            ],
            "measures": [{"aggregate": "count", "alias": "n"}],
            "time": {
                "column": "alerts.raised_at",
                "scope": {"kind": "month", "month": "2026-07"},
            },
            "grain": "day",
        },
    }
    payload, repairs = repair_column_refs(small, iot_schema())
    plan = PlanProposal.model_validate(payload).plan
    assert plan is not None and plan.time is not None and plan.time.grain == "day"
    assert plan.dimensions[0].id == "devices.model"
    assert repairs == [
        "plan.grain moved into time.grain",
        "dimensions: dropped alias",
        "dimensions: unwrapped column reference",
    ]

    # a sibling table that names another table is not guessed away
    wrong = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "table": "devices",
                }
            ],
        },
    }
    payload, repairs = repair_column_refs(wrong, iot_schema())
    assert payload["plan"]["measures"][0]["table"] == "devices" and repairs == []


def test_rule_packs_enter_the_prompt_only_on_their_trigger_words() -> None:
    assert PLAN_PROMPT_REVISION == "plan-classify-json-v14"
    plain = rules_for("2026年1月各門市的營業額")
    assert "(8) Entities with no activity" not in plain
    assert "(9) The latest row per entity" not in plain
    assert "(10) The most recent period" not in plain
    assert plain.endswith("(11) Return only one JSON object.")
    assert "(7) If the question asks" in plain

    without = rules_for("2026年1月沒有任何交易的門市")
    assert "(8) Entities with no activity" in without
    assert "(9) The latest row" not in without

    latest = rules_for("每位店員最新一筆交易的金額")
    assert "(9) The latest row per entity" in latest
    assert "(10) The most recent period" not in latest

    latest_day = rules_for("最新營業日的營業額")
    assert "(9) The latest row per entity" in latest_day  # 最新 switches both on
    assert "(10) The most recent period that has data" in latest_day

    english = rules_for("products never sold in the last 30 days")
    assert "(8) Entities with no activity" in english
    # 'no' inside a longer word does not trigger
    assert "(8) Entities" not in rules_for("monthly sales by store")
