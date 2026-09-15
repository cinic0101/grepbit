"""Factor isolation rulers; no runtime prompt change."""

import json

import pytest
from t0_helpers import iot_schema

from evals.planner_combination_study import CombinationPlanner, load_panel
from evals.query_kind_study import StudyPlanner
from evals.temporal_repair_study import GUIDANCE
from evals.without_planning_study import COMPOSITION, ORIGINAL
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings


@pytest.mark.parametrize("arm", ["baseline", "time", "composition", "combined"])
def test_factors_change_only_the_frozen_passages_and_revision(arm):
    settings = GroundingModelSettings(base_url="http://unused", model="fake")
    args = ("原文", iot_schema())
    kwargs = {"as_of": "2026-08-15T12:00:00+08:00"}
    before = StudyPlanner(settings, arm="joint").build_messages(*args, **kwargs)
    after = CombinationPlanner(settings, treatment=arm).build_messages(*args, **kwargs)
    expected = before[0]["content"]
    if arm in {"composition", "combined"}:
        expected = expected.replace(ORIGINAL, COMPOSITION)
    if arm in {"time", "combined"}:
        expected += "\n" + GUIDANCE
    assert after[0]["content"] == expected
    assert after[1] == before[1]
    a, b = json.loads(before[2]["content"]), json.loads(after[2]["content"])
    assert b.pop("prompt_revision") == (
        "query-kind-joint-v1" if arm == "baseline" else f"joint-factor-{arm}-v1"
    )
    a.pop("prompt_revision")
    assert a == b
    if arm == "baseline":
        assert after == before


def test_panel_is_deduplicated_without_discarding_conflicting_contracts():
    from collections import Counter

    panel = load_panel()
    assert len(panel) == len({c["case_id"] for c in panel}) == 55
    assert Counter(c["expected_route"] for c in panel) == {
        "legacy": 30,
        "rows": 13,
        "decline": 12,
    }
    assert all(
        c.get("reference_sql") for c in panel if c["expected_route"] != "decline"
    )


def test_unknown_factor_is_rejected():
    with pytest.raises(ValueError, match="unknown_treatment"):
        CombinationPlanner(
            GroundingModelSettings(base_url="http://unused", model="fake"),
            treatment="invented",
        )
