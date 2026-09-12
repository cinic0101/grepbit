"""Offline instrument checks: no model calls and no runtime gate changes."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from evals.concept_check import Intent, check_bindings, lexical_intent, validate_intent
from evals.concept_pilot import call, context_for, load_inputs, messages, run, summarize
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.domain.plan import QueryPlan

PILOT, FIXTURE = load_inputs()
PAIR_CASES = [
    (family, plan_id, expected)
    for family in PILOT["families"]
    for plan_id, expected in FIXTURE["pairs"][family["family_id"]]
]


def gold(family):
    return Intent.model_validate(
        {
            "intent": family["intent"],
            "requirements": [
                {**r, "span": family["questions"]["en"]} for r in family["requirements"]
            ],
        }
    )


@pytest.mark.parametrize(
    "family,plan_id,expected",
    PAIR_CASES,
    ids=[f[0]["family_id"] + ":" + f[1] for f in PAIR_CASES],
)
def test_oracle_input_checker_matches_frozen_pair_labels(family, plan_id, expected):
    context, overlay = context_for(family["datasource"], PILOT, FIXTURE)
    actual, _ = check_bindings(
        gold(family),
        QueryPlan.model_validate(FIXTURE["plans"][plan_id]),
        context["concepts"],
        overlay,
    )
    assert actual == expected


@pytest.mark.parametrize("plan_id", ["return_metric", "return_raw", "return_operand"])
def test_equivalent_return_bindings_are_accepted(plan_id):
    context, overlay = context_for("pos", PILOT, FIXTURE)
    assert (
        check_bindings(
            gold(PILOT["families"][0]),
            QueryPlan.model_validate(FIXTURE["plans"][plan_id]),
            context["concepts"],
            overlay,
        )[0]
        == "pass"
    )


def test_whole_share_matches_ratio_without_conflating_metric_filters():
    context, overlay = context_for("pos", PILOT, FIXTURE)
    family = next(f for f in PILOT["families"] if f["family_id"] == "member_share")
    assert (
        check_bindings(
            gold(family),
            QueryPlan.model_validate(FIXTURE["plans"]["member_whole_share"]),
            context["concepts"],
            overlay,
        )[0]
        == "pass"
    )
    # The metric's defining predicate applies to denominator too, unlike an
    # operand-level part. Cannot certify a part/whole from this metric alone.
    intent = Intent.model_validate(
        {
            "intent": "required",
            "requirements": [
                {
                    "concept": "returns",
                    "polarity": "include",
                    "role": "numerator",
                    "span": "returns",
                }
            ],
        }
    )
    query = QueryPlan.model_validate(
        {
            "base_table": "pos_sale",
            "measures": [{"metric": "return_amount", "share_of_total": True}],
        }
    )
    assert check_bindings(intent, query, context["concepts"], overlay)[0] != "pass"


@pytest.mark.parametrize(
    "mutation", ["conflict", "extra_filter", "time", "unknown_metric", "grouping"]
)
def test_unsupported_or_conflicting_forms_cannot_be_certified(mutation):
    context, overlay = context_for("pos", PILOT, FIXTURE)
    payload = deepcopy(FIXTURE["plans"]["return_raw"])
    if mutation == "conflict":
        payload["filters"].append(
            {
                "column": {"table": "pos_sale", "column": "origin_transaction_no"},
                "op": "is_null",
            }
        )
    elif mutation == "extra_filter":
        payload["filters"].append(
            {
                "column": {"table": "pos_sale", "column": "total_amount"},
                "op": "gt",
                "values": [10],
            }
        )
    elif mutation == "time":
        payload["time"] = {
            "column": {"table": "pos_sale", "column": "sale_date"},
            "grain": "month",
        }
    elif mutation == "unknown_metric":
        payload["measures"] = [{"metric": "not_defined"}]
    else:
        payload["dimensions"] = [{"table": "pos_sale", "column": "member_id"}]
    assert (
        check_bindings(
            gold(PILOT["families"][0]),
            QueryPlan.model_validate(payload),
            context["concepts"],
            overlay,
        )[0]
        == "unknown"
    )


def test_lexical_arm_does_not_receive_gold_polarity_or_operand():
    intent = lexical_intent(
        "Count non-member transactions", load_shape_pack(), PILOT["concepts"]
    )
    assert intent.requirements
    assert {(r.polarity, r.role) for r in intent.requirements} == {
        ("unknown", "unknown")
    }
    context, overlay = context_for("pos", PILOT, FIXTURE)
    assert (
        check_bindings(
            intent,
            QueryPlan.model_validate(FIXTURE["plans"]["nonmember_count"]),
            context["concepts"],
            overlay,
        )[0]
        == "unknown"
    )


def test_model_payload_has_no_answer_or_case_label_leakage():
    context, _ = context_for("pos", PILOT, FIXTURE)
    request = messages("SYNTHETIC QUESTION", context)
    payload = json.loads(request[-1]["content"])
    assert set(payload) == {
        "question",
        "schema",
        "concepts",
        "metrics",
        "default_segments",
    }
    assert not (
        {
            "plan",
            "expected",
            "family_id",
            "rationale",
            "requirements",
            "rows",
            "interpretation",
        }
        & set(payload)
    )
    altered = deepcopy(PILOT)
    for family in altered["families"]:
        family["intent"] = "POISONED GOLD"
        family["requirements"] = [{"concept": "POISONED GOLD"}]
    changed, _ = context_for("pos", altered, FIXTURE)
    assert messages("SYNTHETIC QUESTION", changed) == request
    service, _ = context_for("service", PILOT, FIXTURE)
    assert all(c["binding"] is None for c in service["concepts"].values())
    assert service["metrics"] == []


@pytest.mark.parametrize("bad", ["span", "concept", "extra", "duplicate", "empty"])
def test_model_output_is_closed_and_grounded_to_the_question(bad):
    payload = {
        "intent": "required",
        "requirements": [
            {
                "concept": "member",
                "polarity": "include",
                "role": "population",
                "span": "members",
            }
        ],
    }
    if bad == "span":
        payload["requirements"][0]["span"] = "not in the question"
    elif bad == "concept":
        payload["requirements"][0]["concept"] = "invented"
    elif bad == "extra":
        payload["sql"] = "must not persist"
    elif bad == "duplicate":
        payload["requirements"] *= 2
    else:
        payload["requirements"] = []
    with pytest.raises(ValueError):
        validate_intent(payload, "Count members", PILOT["concepts"])


def test_transport_failure_never_persists_provider_error_or_retries():
    attempts = []

    def broken(**kwargs):
        attempts.append(kwargs)
        raise RuntimeError("SENSITIVE provider error sentinel")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=broken))
    )
    result = call(
        client, GroundingModelSettings(base_url="unused", model="fake"), [], lambda p: p
    )
    assert result["status"] == "transport_error"
    assert "SENSITIVE" not in json.dumps(result) and len(attempts) == 1
    assert attempts[0]["max_tokens"] == 768 and attempts[0]["temperature"] == 0
    assert attempts[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


@pytest.mark.parametrize("thinking", [False, True])
def test_reasoning_switch_is_transmitted_without_persisting_the_trace(thinking):
    from evals.concept_check import Audit

    attempts = []
    trace = "PRIVATE reasoning sentinel"

    def create(**kwargs):
        attempts.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content='{"verdict":"unknown"}',
                        reasoning_content=trace if thinking else None,
                    ),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                completion_tokens_details=SimpleNamespace(
                    reasoning_tokens=15 if thinking else 0
                ),
            ),
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    result = call(
        client,
        GroundingModelSettings(base_url="unused", model="fake"),
        [],
        Audit.model_validate,
        thinking=thinking,
        max_tokens=4096,
    )
    assert (
        attempts[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is thinking
    )
    assert attempts[0]["max_tokens"] == 4096
    assert result["status"] == "ok" and result["finish_reason"] == "stop"
    assert result["reasoning_characters"] == (len(trace) if thinking else 0)
    assert result["tokens"]["reasoning_tokens"] == (15 if thinking else 0)
    assert "PRIVATE" not in json.dumps(result)


def test_truncation_is_observable_without_reasoning_or_invalid_content():
    from evals.concept_check import Audit

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(
                    content="", reasoning_content="PRIVATE reasoning sentinel"
                ),
            )
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    result = call(
        client,
        GroundingModelSettings(base_url="unused", model="fake"),
        [],
        Audit.model_validate,
        thinking=True,
    )
    assert result["status"] == "format_error" and result["finish_reason"] == "length"
    assert result["reasoning_characters"] > 0
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize(
    "content,expected",
    [
        ("not JSON SENSITIVE sentinel", "invalid_json"),
        ('{"intent":"SENSITIVE sentinel","requirements":[]}', "schema_validation"),
        (
            '{"intent":"required","requirements":[{"concept":"SENSITIVE sentinel",'
            '"polarity":"include","role":"population","span":"members"}]}',
            "unknown_concept",
        ),
    ],
)
def test_format_diagnostics_persist_codes_not_raw_model_text(content, expected):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    result = call(
        client,
        GroundingModelSettings(base_url="unused", model="fake"),
        [],
        lambda p: validate_intent(p, "Count members", PILOT["concepts"]),
    )
    assert result["status"] == "format_error" and result["format_kind"] == expected
    assert "SENSITIVE" not in json.dumps(result)


def test_metrics_count_unknown_and_no_requirement_without_all_refusal_winning():
    rows = [
        {"expected": expected, "verdicts": {"C": actual}}
        for expected, actual in [
            ("fail", "not_applicable"),
            ("fail", "unknown"),
            ("pass", "unknown"),
            ("unknown", "pass"),
            ("not_applicable", "not_applicable"),
        ]
    ]
    measured = summarize(rows, [])["C"]
    assert measured["wrong_pairs"] == 2 and measured["wrong_allowed"] == 1
    assert (
        measured["correct_pairs"] == 2 and measured["correct_blocked_or_unknown"] == 1
    )
    assert measured["unresolved_allowed"] == 1
    assert measured["accepted_pairs"] == 3


def test_offline_run_has_no_calls_and_preserves_fresh_output(tmp_path):
    output = tmp_path / "offline.json"
    assert run(output)
    result = json.loads(output.read_text())
    assert result["completed"] and result["source_unchanged"]
    assert result["calls"] == []
    assert len(result["records"]) == 51
    assert all(r["verdicts"]["oracle"] == r["expected"] for r in result["records"])
    before = output.read_bytes()
    with pytest.raises(ValueError, match="fresh_outputs_required"):
        run(output)
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    "unavailable,thinking", [(False, False), (False, True), (True, False)]
)
def test_live_driver_with_fake_transport_preserves_budget_and_failure_evidence(
    tmp_path, monkeypatch, unavailable, thinking
):
    from evals import concept_pilot

    requested = []

    def create(**kwargs):
        requested.append(kwargs)
        if unavailable:
            raise RuntimeError("SENSITIVE sentinel")
        payload = json.loads(kwargs["messages"][-1]["content"])
        result = (
            {"verdict": "not_applicable"}
            if "plan" in payload
            else {"intent": "not_requested", "requirements": []}
        )
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
        concept_pilot.GroundingModelSettings,
        "from_environment",
        classmethod(
            lambda cls: GroundingModelSettings(base_url="unused", model="fake")
        ),
    )
    monkeypatch.setattr(
        concept_pilot.ChatCompletionsGroundingClient,
        "_create_client",
        lambda self: client,
    )
    output = tmp_path / "mock-live.json"
    assert run(
        output, live=True, thinking=thinking, max_tokens=4096, timeout_seconds=60
    ) is (not unavailable)
    report = json.loads(output.read_text())
    assert report["settings"]["thinking"] is thinking
    assert report["settings"]["max_tokens"] == 4096
    assert report["settings"]["timeout_seconds"] == 60
    assert all(
        r["max_tokens"] == 4096
        and r["extra_body"]["chat_template_kwargs"]["enable_thinking"] is thinking
        for r in requested
    )
    assert len(requested) == len(report["calls"]) == (3 if unavailable else 81)
    assert "SENSITIVE" not in output.read_text()
    if unavailable:
        assert report["stop_reason"] == "three_transport_errors"
    else:
        assert len(report["records"]) == 51 and len(report["intents"]) == 30
        assert all(
            r["actual"] != r["expected"]
            for r in report["intents"]
            if r["expected"]["intent"] == "required"
        )
