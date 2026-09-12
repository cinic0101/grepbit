"""Search instrument and existing-contract blind spots; no revised gold labels."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from evals import concept_search as search
from evals.concept_check import Intent, check_bindings
from evals.concept_pilot import call, context_for, digest, label_core, load_inputs
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.domain.plan import QueryPlan

PILOT, FIXTURE = load_inputs()


def candidate(concept="member", polarity="include", role="population", span="member"):
    return {
        "status": "ok",
        "result": {
            "intent": "required",
            "requirements": [
                {"concept": concept, "polarity": polarity, "role": role, "span": span}
            ],
        },
        "seconds": 1,
    }


def test_existing_input_and_grading_identity_is_frozen():
    assert (
        digest([PILOT, FIXTURE])
        == "47665256c0d3eb8a0f178c569a2e6a471f145be682c270403529523adb360eb8"
    )
    assert len(search.ARMS) == 10 and search.MAX_CALLS == 432


@pytest.mark.parametrize("unanimous", [False, True])
def test_votes_ignore_valid_span_variation_only(unanimous):
    pool = [
        candidate(span=s)
        for s in ("member", "member transactions", "Count member transactions")
    ]
    result = search.vote(pool, unanimous=unanimous)
    assert result is pool[0]
    assert label_core(result["result"]) == label_core(pool[-1]["result"])


def test_invalid_samples_do_not_shrink_voting_denominator():
    invalid = {"status": "format_error"}
    assert search.vote([candidate(), invalid, invalid])["status"] == "abstain"
    assert search.vote([candidate(), candidate(), invalid])["status"] == "ok"
    assert (
        search.vote([candidate(), candidate(), invalid], unanimous=True)["status"]
        == "abstain"
    )


def test_ties_and_fieldwise_frankenstein_candidates_never_win():
    pool = [candidate(), candidate(polarity="exclude"), candidate(role="numerator")]
    assert search.vote(pool)["status"] == "abstain"
    assert search.vote(pool[:2])["status"] == "abstain"
    assert search.vote([])["status"] == "abstain"


def test_selector_only_receives_valid_unique_candidates_without_frequencies_or_gold():
    context, _ = context_for("pos", PILOT, FIXTURE)
    pool = [
        candidate(),
        candidate(),
        {"status": "format_error", "expected": "SENTINEL"},
    ]
    request, offered = search.select_messages("Count members", context, pool, 5)
    payload = json.loads(request[-1]["content"])
    assert len(offered) == 1 and set(offered) == {"c0"}
    assert set(payload) == {
        "question",
        "schema",
        "concepts",
        "metrics",
        "default_segments",
        "candidates",
    }
    assert "SENTINEL" not in json.dumps(request)
    assert search.validate_selection({"selected": None}, offered).selected is None
    assert search.validate_selection({"selected": "c0"}, offered).selected == "c0"
    with pytest.raises(ValueError):
        search.validate_selection({"selected": "c9"}, offered)
    with pytest.raises(ValueError):
        search.validate_selection({"selected": "c0", "replacement": {}}, offered)


def test_metric_facts_expand_predicates_without_changing_measure_or_grouping():
    _, overlay = context_for("pos", PILOT, FIXTURE)
    metric = search.plan_facts(
        QueryPlan.model_validate(FIXTURE["plans"]["return_metric"]), overlay
    )
    raw = search.plan_facts(
        QueryPlan.model_validate(FIXTURE["plans"]["return_raw"]), overlay
    )
    assert metric == raw
    assert metric["measures"][0]["aggregate"] == "sum"
    assert metric["measures"][0]["column"] == "pos_sale.total_amount"
    assert not metric["measures"][0]["no_row_restriction"]
    dimension = search.plan_facts(
        QueryPlan.model_validate(FIXTURE["plans"]["member_dimension_only"]), overlay
    )
    assert dimension["group_by_not_row_restrictions"] == ["pos_sale.member_id"]
    assert dimension["measures"][0]["no_row_restriction"]


def test_ratio_facts_keep_base_and_operand_scopes_separate():
    _, overlay = context_for("pos", PILOT, FIXTURE)
    payload = deepcopy(FIXTURE["plans"]["member_ratio"])
    facts = search.plan_facts(QueryPlan.model_validate(payload), overlay)["measures"][0]
    assert not facts["numerator"]["no_row_restriction"]
    assert facts["denominator"]["no_row_restriction"]
    payload["filters"] = FIXTURE["plans"]["return_raw"]["filters"]
    facts = search.plan_facts(QueryPlan.model_validate(payload), overlay)["measures"][0]
    assert len(facts["numerator"]["effective_row_predicates"]) == 2
    assert len(facts["denominator"]["effective_row_predicates"]) == 1


@pytest.mark.parametrize("plan_id", ["member_whole_share", "unknown_metric", "time"])
def test_facts_fail_locally_instead_of_dropping_unsupported_parts(plan_id):
    _, overlay = context_for("pos", PILOT, FIXTURE)
    if plan_id == "member_whole_share":
        payload = FIXTURE["plans"][plan_id]
    else:
        payload = deepcopy(FIXTURE["plans"]["return_metric"])
        if plan_id == "time":
            payload["time"] = {
                "column": {"table": "pos_sale", "column": "sale_date"},
                "grain": "month",
            }
        else:
            payload["measures"] = [{"metric": "unknown"}]
    with pytest.raises(ValueError):
        search.plan_facts(QueryPlan.model_validate(payload), overlay)


def test_existing_no_requirement_bypass_cannot_enforce_no_restriction():
    # Characterization, NOT a new fail/pass golden or a desired runtime rule.
    context, overlay = context_for("pos", PILOT, FIXTURE)
    intent = Intent(intent="not_requested", requirements=[])
    for plan_id in (
        "count_all",
        "member_count",
        "nonmember_count",
        "member_dimension_only",
    ):
        assert (
            check_bindings(
                intent,
                QueryPlan.model_validate(FIXTURE["plans"][plan_id]),
                context["concepts"],
                overlay,
            )[0]
            == "not_applicable"
        )


@pytest.mark.parametrize("missing", ["unrestricted", "denominator", "multiple_roles"])
def test_existing_intent_cannot_encode_these_distinctions(missing):
    payload = candidate()["result"]
    if missing == "unrestricted":
        payload["requirements"][0]["polarity"] = "unrestricted"
    elif missing == "denominator":
        payload["requirements"][0]["role"] = "denominator"
    else:
        payload["requirements"].append(
            {**payload["requirements"][0], "role": "numerator"}
        )
    with pytest.raises(ValueError):
        Intent.model_validate(payload)


@pytest.mark.parametrize("temperature", [0, 0.6])
def test_temperature_is_forwarded_without_affecting_private_output_handling(
    temperature,
):
    captured = []

    def create(**kwargs):
        captured.append(kwargs)
        raise RuntimeError("PRIVATE secret sentinel")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    result = call(
        client,
        GroundingModelSettings(base_url="unused", model="fake"),
        [],
        Intent.model_validate,
        temperature=temperature,
    )
    assert captured[0]["temperature"] == temperature
    assert result["status"] == "transport_error"
    assert "PRIVATE" not in json.dumps(result)


def test_adaptive_replay_uses_no_gold_and_counts_untriggered_wrong_agreement():
    family = next(f for f in PILOT["families"] if f["family_id"] == "return_amount")
    cid = "return_amount_en"
    wrong = {
        "status": "ok",
        "result": {"intent": "not_requested", "requirements": []},
        "seconds": 1,
    }
    right = candidate(concept="returns")
    c = {name: deepcopy(wrong) for name, _, _ in search.ARMS}
    c["on0"] = right
    c["off_sample_1"] = right
    audit = {"status": "ok", "result": {"verdict": "unknown"}, "seconds": 1}
    row = {
        "case_id": cid,
        "complete": True,
        "candidates": c,
        "selected": right,
        "audits": {
            p: {"audit_raw": audit, "audit_facts": audit}
            for p, _ in FIXTURE["pairs"][family["family_id"]]
        },
    }
    report = {"cases": [row], "calls": []}
    result = search.analyze(report, PILOT, FIXTURE)
    assert (
        result["strategies"]["route_disagreement"]["pair_metrics"]["wrong_allowed"] == 1
    )
    assert all(
        not r["trigger"] and r["calls"] == 2
        for r in result["routing"]
        if r["policy"] == "route_disagreement"
    )
    available = next(r for r in result["availability"] if r["pool"] == "off")
    assert available["correct_at_n"] == [False, True, True]
    assert available["selector_correct"]
    poisoned = deepcopy(PILOT)
    for f in poisoned["families"]:
        f["intent"], f["requirements"] = "not_requested", []
    rerun = search.analyze(report, poisoned, FIXTURE)
    assert [(r["trigger"], r["calls"]) for r in result["routing"]] == [
        (r["trigger"], r["calls"]) for r in rerun["routing"]
    ]


@pytest.mark.parametrize("failure", [False, True])
def test_full_fake_run_enforces_budget_preserves_evidence_and_never_retries(
    tmp_path, monkeypatch, failure
):
    requested = []

    def create(**kwargs):
        requested.append(kwargs)
        if failure:
            raise RuntimeError("PRIVATE secret sentinel")
        payload = json.loads(kwargs["messages"][-1]["content"])
        if "candidates" in payload:
            result = {"selected": next(iter(payload["candidates"]), None)}
        elif "plan" in payload or "plan_facts" in payload:
            result = {"verdict": "not_applicable"}
        else:
            result = {"intent": "not_requested", "requirements": []}
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(result)))
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=lambda: None,
    )
    monkeypatch.setattr(
        search.GroundingModelSettings,
        "from_environment",
        classmethod(
            lambda cls: GroundingModelSettings(base_url="unused", model="fake")
        ),
    )
    monkeypatch.setattr(
        search.ChatCompletionsGroundingClient, "_create_client", lambda self: client
    )
    output = tmp_path / "run.json"
    assert search.run(output, live=True) is (not failure)
    report = json.loads(output.read_text())
    assert len(report["calls"]) == len(requested) == (3 if failure else 432)
    assert "PRIVATE" not in output.read_text()
    assert report["source_unchanged"]
    assert {r["max_tokens"] for r in requested} == {4096}
    if failure:
        assert report["stop_reason"] == "three_transport_errors"
    else:
        assert len(report["analysis"]["strategies"]["best_off3"]["pairs"]) == 51
        assert report["analysis"]["strategies"]["off0"]["intent_total"] == 30
    before = output.read_bytes()
    with pytest.raises(ValueError, match="fresh_outputs"):
        search.run(output, live=True)
    assert output.read_bytes() == before


def test_offline_dry_run_never_scores_nonexistent_model_answers(tmp_path):
    output = tmp_path / "dry.json"
    assert search.run(output)
    report = json.loads(output.read_text())
    assert report["calls"] == [] and report["analysis"] is None
