"""Relative time units beyond day and month, and follow-up context in the prompt."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import PreviousTurn, QueryPlan
from grepbit.domain.structured_query import RelativeScope, resolve_time_scope


@pytest.mark.parametrize(
    ("unit", "offset", "length", "label", "start", "end"),
    [
        ("quarter", 0, 1, "2026-Q3", "2026-07-01", "2026-10-01"),
        ("quarter", -1, 1, "2026-Q2", "2026-04-01", "2026-07-01"),
        ("year", 0, 1, "2026", "2026-01-01", "2027-01-01"),
        ("year", -1, 2, "2025..2027", "2025-01-01", "2027-01-01"),
        ("week", 0, 1, "2026-08-10", "2026-08-10", "2026-08-17"),
        ("week", -2, 2, "2026-07-27..2026-08-10", "2026-07-27", "2026-08-10"),
        ("day", -7, 7, "2026-08-08..2026-08-15", "2026-08-08", "2026-08-15"),
    ],
)
def test_relative_units_resolve_in_business_timezone(
    unit, offset, length, label, start, end
) -> None:
    # AS_OF is Saturday 2026-08-15 12:00 Asia/Taipei; weeks start on Monday.
    [period] = resolve_time_scope(
        RelativeScope(unit=unit, offset=offset, length=length),
        as_of=AS_OF,
        business_timezone="Asia/Taipei",
    )
    assert period.label == label
    assert period.start.date().isoformat() == start
    assert period.end_exclusive.date().isoformat() == end
    assert period.start.tzinfo is not None


def test_quarter_and_week_grains_render_as_date_trunc() -> None:
    compiled = PlanCompiler(iot_schema()).compile(
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {
                        "kind": "relative",
                        "unit": "quarter",
                        "offset": -1,
                        "length": 2,
                    },
                    "grain": "week",
                },
            }
        ),
        as_of=AS_OF,
    )
    assert compiled.compiled.physical_sql.startswith(
        "SELECT DATE_TRUNC('WEEK', alerts.raised_at AT TIME ZONE 'Asia/Taipei') "
        "AS period_start"
    )
    assert compiled.periods[0].label == "2026-Q2..2026-Q4"


def test_follow_up_context_is_offered_only_when_present() -> None:
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
                        "measures": [{"aggregate": "count"}],
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
    previous = PreviousTurn(
        question="How many alerts in July 2026?",
        plan=QueryPlan.model_validate(
            {"base_table": "alerts", "measures": [{"aggregate": "count"}]}
        ),
    )
    client.propose(
        "and August?",
        iot_schema(),
        as_of="2026-08-15T12:00:00+08:00",
        previous=previous,
    )
    user = json.loads(fake.calls[0]["messages"][2]["content"])
    assert user["previous_turn"]["question"] == "How many alerts in July 2026?"
    assert user["previous_turn"]["plan"]["base_table"] == "alerts"
    assert (
        "previous_turn holds the last answered question"
        in fake.calls[0]["messages"][0]["content"]
    )
    client.propose("How many devices?", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert "previous_turn" not in json.loads(fake.calls[1]["messages"][2]["content"])
    assert "previous_turn holds" not in fake.calls[1]["messages"][0]["content"]
