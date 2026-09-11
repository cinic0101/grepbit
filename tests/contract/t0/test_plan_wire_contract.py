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


def test_share_filter_on_a_grouped_column_becomes_the_after_share_selection() -> None:
    # holdout 2 q25 under v14: count where category = X, share of total, by
    # category: 1.0 for X and 0 elsewhere; the after-share selection is the reading
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": ["devices.model"],
            "measures": [
                {
                    "aggregate": "count",
                    "alias": "n",
                    "share_of_total": True,
                    "filters": [
                        {"column": "devices.model", "op": "eq", "values": ["AP-300"]}
                    ],
                }
            ],
        },
    }
    out, repairs = repair_column_refs(payload, iot_schema())
    plan = PlanProposal.model_validate(out).plan
    assert plan is not None and plan.measures[0].filters == []
    assert [f.column.id for f in plan.filters] == ["devices.model"]
    assert repairs == [
        "share filter on a grouped column -> plan filter (after-share selection)"
    ]


def test_plan_level_operands_and_a_restating_aggregate_are_folded() -> None:
    critical = {"column": "alerts.severity", "op": "eq", "values": ["critical"]}
    # holdout 2 q23, first text: operands spelled out as measures, the ratio on the plan
    q23 = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "alias": "a",
                    "column": "alerts.downtime_minutes",
                    "filters": [critical],
                },
                {"aggregate": "sum", "alias": "b", "column": "alerts.downtime_minutes"},
            ],
            "numerator": {
                "aggregate": "sum",
                "column": "alerts.downtime_minutes",
                "filters": [critical],
            },
            "denominator": {"aggregate": "sum", "column": "alerts.downtime_minutes"},
        },
    }
    out, repairs = repair_column_refs(q23, iot_schema())
    plan = PlanProposal.model_validate(out).plan
    assert (
        plan is not None
        and len(plan.measures) == 1
        and plan.measures[0].ratio is not None
    )
    assert repairs == [
        "dropped measures spelled inside the plan-level ratio",
        "lifted plan-level numerator/denominator into a measure",
    ]
    # the repair turn's text: aggregate and column beside numerator/denominator
    # that restate the denominator
    again = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "alias": "share",
                    "column": "alerts.downtime_minutes",
                    "numerator": {
                        "aggregate": "sum",
                        "column": "alerts.downtime_minutes",
                        "filters": [critical],
                    },
                    "denominator": {
                        "aggregate": "sum",
                        "column": "alerts.downtime_minutes",
                    },
                }
            ],
        },
    }
    out, repairs = repair_column_refs(again, iot_schema())
    plan = PlanProposal.model_validate(out).plan
    assert plan is not None and plan.measures[0].ratio is not None
    assert repairs == ["dropped aggregate restating a ratio operand"]


def test_a_non_identifier_alias_becomes_one_and_its_references_follow() -> None:
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "alerts",
            "dimensions": ["devices.model"],
            "measures": [{"aggregate": "count", "alias": "告警數"}],
            "order": [{"field": "告警數", "direction": "desc"}],
            "having": [{"field": "告警數", "op": "gt", "value": 3}],
        },
    }
    out, repairs = repair_column_refs(payload, iot_schema())
    plan = PlanProposal.model_validate(out).plan
    assert plan is not None and plan.measures[0].alias == "measure_1"
    assert plan.order[0].field == "measure_1" and plan.having[0].field == "measure_1"
    assert repairs == ["alias '告警數' -> measure_1 (not an identifier)"]


def test_a_month_day_or_year_literal_on_a_date_column_becomes_the_window() -> None:
    # gemma-4-12b-it: sale_date IN ('2025-12'), which PostgreSQL rejects with 22007
    def plan_with(values, op="in", column="alerts.raised_at", time=None):
        plan = {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "alias": "n"}],
            "filters": [{"column": column, "op": op, "values": values}],
        }
        if time:
            plan["time"] = time
        out, repairs = repair_column_refs(
            {"decision": "plan", "plan": plan}, iot_schema()
        )
        return PlanProposal.model_validate(out).plan, repairs

    plan, repairs = plan_with(["2026-07"])
    assert plan is not None and plan.filters == [] and plan.time is not None
    assert plan.time.scope is not None and plan.time.scope.model_dump(mode="json") == {
        "kind": "month",
        "month": "2026-07",
    }
    assert plan.time.column is not None and plan.time.column.id == "alerts.raised_at"
    assert repairs == ["date literal alerts.raised_at = '2026-07' -> time scope"]
    plan, _ = plan_with(["2026-07-15"], op="eq")
    assert plan.time.scope.model_dump(mode="json") == {
        "kind": "range",
        "start": "2026-07-15",
        "end_exclusive": "2026-07-16",
    }
    plan, _ = plan_with(["2026"], op="eq")
    assert plan.time.scope.model_dump(mode="json") == {
        "kind": "range",
        "start": "2026-01-01",
        "end_exclusive": "2027-01-01",
    }
    # a time column named by the plan is kept; a text column is untouched
    plan, _ = plan_with(
        ["2026-07"], time={"column": "alerts.resolved_at", "grain": "day"}
    )
    assert plan.time.column.id == "alerts.resolved_at" and plan.time.grain == "day"
    plan, repairs = plan_with(["2026-07"], op="eq", column="alerts.severity")
    assert len(plan.filters) == 1 and repairs == []
