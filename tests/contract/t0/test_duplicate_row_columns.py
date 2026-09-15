"""A traced exact duplicate is not permission to discard conflicting extras."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    repair_column_refs,
)
from grepbit.adapters.litellm.plan_wire import normalize_variants
from grepbit.domain.plan import PlanProposal
from grepbit.ports.ask import is_meaning_repair

LABEL = "dropped exact duplicate plan.columns matching rows.columns"


def wire(columns=None):
    columns = columns if columns is not None else ["devices.device_id", "devices.model"]
    return {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "columns": deepcopy(columns),
            "rows": {"columns": deepcopy(columns)},
        },
    }


@pytest.mark.parametrize(
    "columns",
    [
        ["devices.device_id", "devices.model"],
        [
            {"table": "devices", "column": "device_id"},
            {"table": "devices", "column": "model"},
        ],
    ],
)
def test_only_exact_duplicate_is_removed_and_counted(columns):
    raw = wire(columns)
    expected = deepcopy(raw)
    del expected["plan"]["columns"]
    repairs = []
    normalize_variants(raw["plan"], repairs)
    assert raw == expected
    assert repairs == [LABEL]
    assert not is_meaning_repair(LABEL)
    normalize_variants(raw["plan"], repairs)
    assert repairs == [LABEL]  # idempotent, one event
    converted, _ = repair_column_refs(raw, iot_schema())
    assert PlanProposal.model_validate(converted).plan.rows is not None


@pytest.mark.parametrize(
    "case",
    [
        "different",
        "reordered",
        "top_only",
        "all_columns",
        "empty",
        "malformed",
        "extra_reference_key",
        "unqualified",
        "non_list",
        "all_columns_invalid",
    ],
)
def test_ambiguous_or_invalid_redundancy_is_not_dropped(case):
    raw = wire()
    p = raw["plan"]
    if case == "different":
        p["columns"] = ["devices.status"]
    elif case == "reordered":
        p["columns"].reverse()
    elif case == "top_only":
        del p["rows"]
    elif case == "all_columns":
        p["rows"]["all_columns"] = True
    elif case == "all_columns_invalid":
        p["rows"]["all_columns"] = "false"
    elif case in {
        "empty",
        "malformed",
        "extra_reference_key",
        "unqualified",
        "non_list",
    }:
        columns = {
            "empty": [],
            "malformed": [True],
            "extra_reference_key": [
                {"table": "devices", "column": "model", "scope": "all"}
            ],
            "unqualified": ["model"],
            "non_list": "devices.model",
        }[case]
        p["columns"] = deepcopy(columns)
        p["rows"]["columns"] = deepcopy(columns)
    repairs = []
    normalize_variants(p, repairs)
    assert "columns" in p and LABEL not in repairs
    converted, _ = repair_column_refs(raw, iot_schema())
    with pytest.raises((ValidationError, ValueError)):
        PlanProposal.model_validate(converted)


def test_other_extra_requirements_still_fail_validation():
    raw = wire()
    raw["plan"]["unknown_scope"] = "required"
    converted, repairs = repair_column_refs(raw, iot_schema())
    assert repairs == [LABEL]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PlanProposal.model_validate(converted)


def test_shared_planner_uses_one_response_and_keeps_permission_guard():
    cfg = GroundingModelSettings(base_url="http://unused", model="fake", repair_turns=0)
    calls = []
    planner = ChatCompletionsPlanClient(cfg, allow_rows=True, query_kind="rows")

    def complete(*args, **kwargs):
        calls.append(1)
        return json.dumps(wire())

    planner._complete = complete
    proposal = planner._propose(
        None,
        "List devices",
        iot_schema(),
        as_of=AS_OF.isoformat(),
        overlay=None,
        previous=None,
        question_values=None,
    )
    assert proposal.plan.rows and len(calls) == 1
    assert planner.last_repairs == [LABEL] and planner.last_model_repair_turns == 0
    disabled = ChatCompletionsPlanClient(cfg, allow_rows=False)
    disabled._complete = complete
    from grepbit.adapters.litellm.grounding_client import GroundingModelError

    with pytest.raises(GroundingModelError):
        disabled._propose(
            None,
            "List devices",
            iot_schema(),
            as_of=AS_OF.isoformat(),
            overlay=None,
            previous=None,
            question_values=None,
        )
