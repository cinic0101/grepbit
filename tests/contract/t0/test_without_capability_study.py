"""Predeclared research invariants; no production routing change."""

import hashlib
import json
from datetime import datetime

import pytest
import yaml
from t0_helpers import ROOT, iot_schema

from evals.query_kind_study import load_cases
from evals.synthetic import DuckInstance
from evals.without_planning_study import COMPOSITION, ORIGINAL, CompositionPlanner
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings


def test_historical_date_bank_is_not_regraded():
    assert (
        hashlib.sha256((ROOT / "evals/cases/tier0/iot.yaml").read_bytes()).hexdigest()
        == "3d450d29fb404a97c324ba2d51db606cd2fdc360a50903b21be80e96ef295458"
    )


def test_without_panel_has_predeclared_positive_and_negative_controls():
    cases = load_cases(ROOT / "evals/cases/without_capability_study.yaml")
    assert len(cases) == 24
    assert sum(c["expected_route"] == "decline" for c in cases) == 6
    assert sum(c["expected_route"] == "rows" for c in cases) == 3
    assert len({c["case_id"] for c in cases}) == len(cases)


@pytest.mark.parametrize("case_index,counts", [(0, [1, 4]), (1, [1]), (2, [1, 2])])
def test_prospective_date_oracles_distinguish_endpoint_semantics(case_index, counts):
    dates = [
        "2026-06-30T23:59:59+08:00",  # before start
        "2026-07-01T00:00:00+08:00",  # start included
        "2026-07-08T00:00:00+08:00",  # exclusive date boundary
        "2026-07-08T11:59:59+08:00",  # before precise timestamp
        "2026-07-08T12:00:00+08:00",  # timestamp boundary
        "2026-07-08T23:59:59+08:00",  # inclusive end date
        "2026-07-09T00:00:00+08:00",  # next day excluded
    ]
    instance = DuckInstance(
        iot_schema(),
        {
            "alerts": [
                {"alert_id": i, "raised_at": datetime.fromisoformat(d)}
                for i, d in enumerate(dates)
            ]
        },
    )
    try:
        instance.con.execute("SET schema = 'public'")
        bank = yaml.safe_load(
            (ROOT / "evals/cases/tier0/iot_date_acceptance.yaml").read_text()
        )
        rows = instance.con.execute(
            bank["cases"][case_index]["reference_sql"]
        ).fetchall()
        assert [r[1] for r in rows] == counts
    finally:
        instance.con.close()


def test_composition_changes_only_one_capability_passage_and_revision():
    from evals.query_kind_study import StudyPlanner

    settings = GroundingModelSettings(base_url="http://unused", model="fake")
    old = StudyPlanner(settings, arm="joint")
    new = CompositionPlanner(settings)
    args = ("原文", iot_schema())
    kwargs = {"as_of": "2026-08-15T12:00:00+08:00"}
    a, b = old.build_messages(*args, **kwargs), new.build_messages(*args, **kwargs)
    assert a[0]["content"].replace(ORIGINAL, COMPOSITION) == b[0]["content"]
    assert a[1] == b[1]
    x, y = json.loads(a[2]["content"]), json.loads(b[2]["content"])
    assert y.pop("prompt_revision") == "query-kind-without-composition-v1"
    assert x.pop("prompt_revision") == "query-kind-joint-v1"
    assert x == y


def test_composition_uses_one_proposal_not_a_router_or_fallback():
    settings = GroundingModelSettings(base_url="http://unused", model="fake")
    planner = CompositionPlanner(settings, client=object())
    calls = []

    def complete(*args, **kwargs):
        calls.append(args)
        return '{"decision":"none","reason":"semantic_gap"}'

    planner._complete = complete
    result = planner.propose("q", iot_schema(), as_of="2026-08-15T12:00:00+08:00")
    assert result.reason == "semantic_gap"
    assert len(calls) == 1
