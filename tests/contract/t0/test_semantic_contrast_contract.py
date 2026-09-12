"""Instrument and fixed-input guards, not evidence of model correctness."""

import json
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest

from evals import semantic_contrast as study
from evals.concept_obligations import core, validate_obligations
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings


@pytest.mark.parametrize(
    "phase,count", [("development", 36), ("challenge", 12), ("legacy", 36)]
)
def test_frozen_inputs_have_valid_gold_and_scoped_sources(phase, count):
    ruler, fixture, _ = study.load_study(phase)
    assert sum(len(f["questions"]) for f in ruler["families"]) == count
    for family in ruler["families"]:
        context, _ = study.pilot.study_context(family["id"], ruler, fixture)
        for question in family["questions"].values():
            validate_obligations(
                study.pilot.gold_payload(family, question),
                question,
                context["concepts"],
            )
    assert all(
        p["expected"] == p["verdict"]
        for p in study.pilot.oracle_records(ruler, fixture)
    )


def test_whole_pairs_stay_in_development_and_challenge_is_not_a_relabel():
    _, _, data = study.load_study()
    counts = Counter(f["pair"] for f in data["families"] if f["split"] == "development")
    assert len(counts) == 6 and set(counts.values()) == {2}
    assert len({f["id"] for f in data["families"]}) == 16
    assert all("pair" not in f for f in data["families"] if f["split"] == "challenge")


def test_each_arm_changes_only_its_declared_surface_and_never_exposes_labels():
    ruler, fixture, data = study.load_study()
    family = ruler["families"][0]
    question = family["questions"]["en"]
    context, _ = study.pilot.study_context(family["id"], ruler, fixture)
    original = deepcopy(context)
    base = study.messages(question, context, "baseline", data["definitions"])
    assert base == study.pilot.messages(question, context)
    task = study.messages(question, context, "task", data["definitions"])
    assert task[:1] + task[2:] == base
    definitions = study.messages(question, context, "definitions", data["definitions"])
    assert definitions[:2] == base[:2]
    payload = json.loads(definitions[-1]["content"])
    for key in payload["concepts"]:
        assert (
            payload["concepts"][key]["binding"] == context["concepts"][key]["binding"]
        )
        payload["concepts"][key]["definition"] = context["concepts"][key]["definition"]
    assert payload == json.loads(base[-1]["content"])
    assert context == original
    assert not set(payload) & {
        "plans",
        "rows",
        "correct_answers",
        "wrong_answers",
        "pairs",
        "gold",
    }


def test_selection_requires_gain_without_new_errors_or_escapes():
    baseline = dict(
        intent_exact=20,
        correct_controls_allowed=20,
        wrong_allowed=0,
        unresolved_allowed=0,
        wrong_full_answer_no_block=3,
        failed_extractions=0,
    )
    better = {**baseline, "intent_exact": 22}
    assert study.select_candidate({"baseline": baseline, "task": better}) == "task"
    assert study.select_candidate({"baseline": baseline, "task": baseline}) is None
    for key in (
        "wrong_allowed",
        "unresolved_allowed",
        "wrong_full_answer_no_block",
        "failed_extractions",
    ):
        assert (
            study.select_candidate(
                {"baseline": baseline, "task": {**better, key: baseline[key] + 1}}
            )
            is None
        )
    assert (
        study.select_candidate(
            {"baseline": baseline, "task": {**better, "correct_controls_allowed": 19}}
        )
        is None
    )


def test_gold_input_is_not_full_answer_certification():
    ruler, fixture, _ = study.load_study()
    family = ruler["families"][0]
    question = family["questions"]["en"]
    call = dict(
        family_id=family["id"],
        case_id=family["id"] + "_en",
        language="en",
        arm="baseline",
        round=1,
        status="ok",
        seconds=1,
        result=study.pilot.gold_payload(family, question),
    )
    summary = study.analyze([call], ruler, fixture)["summaries"]["baseline"]
    assert summary["wrong_allowed"] == 0
    assert summary["wrong_full_answer_no_block"] == 1
    assert summary["wrong_full_answer_pass"] == 0
    assert core(call["result"]) == {
        "requirements": [],
        "forbidden_groupings": [],
        "unresolved": [],
    }


@pytest.mark.parametrize("failure", [False, True])
def test_fake_live_budget_freshness_and_sanitized_transport(
    tmp_path, monkeypatch, failure
):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        if failure:
            raise RuntimeError("PRIVATE_SENTINEL")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "requirements": [],
                                "forbidden_groupings": [],
                                "unresolved": [],
                            }
                        ),
                        reasoning_content="PRIVATE_SENTINEL",
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=lambda: None,
    )
    monkeypatch.setattr(
        study.GroundingModelSettings,
        "from_environment",
        classmethod(
            lambda cls: GroundingModelSettings(base_url="unused", model="fake")
        ),
    )
    monkeypatch.setattr(
        study.ChatCompletionsGroundingClient, "_create_client", lambda self: client
    )
    path = tmp_path / "run.json"
    assert study.run(path, live=True) is (not failure)
    result = json.loads(path.read_text())
    assert len(requests) == len(result["calls"]) == (3 if failure else 108)
    assert all(
        r["max_tokens"] == 4096
        and r["temperature"] == 0
        and r["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
        for r in requests
    )
    assert (
        "PRIVATE_SENTINEL"
        not in path.read_text() + path.with_suffix(".jsonl").read_text()
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="fresh_outputs"):
        study.run(path, live=True)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="prior_screen_required"):
        study.run(tmp_path / "later.json", phase="replicate")


def test_dry_run_never_invents_model_results(tmp_path):
    output = tmp_path / "dry.json"
    assert study.run(output)
    report = json.loads(output.read_text())
    assert report["calls"] == [] and report["analysis"] is None
    assert len(report["schedule"]) == 108
