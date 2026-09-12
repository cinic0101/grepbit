"""Offline checks of the approved research boundary; no external calls."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from t0_helpers import ROOT

from evals import cross_language as comparison
from evals import cross_language_study as study
from evals import metric_selection_study as prior
from evals.concept_pilot import digest
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.domain.plan import PlanProposal, QueryPlan

RULER = json.loads((ROOT / "tests/fixtures/cross_language_rulers.json").read_text())
GOLD, FIXTURE = prior.load_inputs()
CONTEXTS = {s: prior.context(s, "P0", FIXTURE) for s in ("pos", "service")}
CASES = {c["id"]: c for c in GOLD["cases"] if c["split"] == "development"}


def query(name):
    return QueryPlan.model_validate(FIXTURE["plans"][name])


def compare(left, right, *, source="pos", instances=None, schema=None, overlay=None):
    context = CONTEXTS[source]
    return comparison.compare(
        left,
        right,
        schema or context[0],
        overlay or context[1],
        FIXTURE["instances"] if instances is None else instances,
        as_of=prior.AS_OF,
        left_context="bound",
        right_context="bound",
    )


@pytest.mark.parametrize("row", RULER["accounting"], ids=lambda r: r["id"])
def test_runtime_accounting_matches_frozen_ruler(row):
    result = comparison.accounting(
        row["original"], row["fidelity"], row["pair"], row["repeat"]
    )
    assert {
        k: result[k] for k in ("credit", "incremental", "false_alarm", "certified")
    } == {k: row[k] for k in ("credit", "incremental", "false_alarm", "certified")}


@pytest.mark.parametrize("row", RULER["advancement"], ids=lambda r: r["id"])
def test_runtime_advancement_matches_frozen_ruler(row):
    assert (
        comparison.may_advance(
            **{k: v for k, v in row.items() if k not in {"id", "may_advance"}}
        )
        is row["may_advance"]
    )


@pytest.mark.parametrize("row", RULER["equivalence_laws"], ids=lambda r: r["law"])
def test_equivalence_requires_named_algebra_law_not_fixture_match(row):
    result = compare(query(row["left"]), query(row["right"]))
    assert result["status"] == "equivalent_in_fragment"
    assert not result["certified"]


@pytest.mark.parametrize("row", RULER["witnesses"], ids=lambda r: r["left"])
def test_witness_outputs_match_independent_hand_ruler(row):
    source = "service" if row["left"] == "log_count" else "pos"
    result = compare(query(row["left"]), query(row["right"]), source=source)
    assert result["status"] == "witnessed_difference"
    witness = next(c for c in result["checks"] if c["instance"] == row["instance"])
    assert witness["different"]
    assert (
        witness["sql"]
        == witness["reference"]
        == [row["left_value"], row["right_value"]]
    )
    assert witness["instance_sha256"] == digest(FIXTURE["instances"][row["instance"]])


def test_coincidence_and_empty_witness_search_are_not_equivalence():
    row = RULER["coincidence"]
    for instances in ({row["instance"]: FIXTURE["instances"][row["instance"]]}, {}):
        result = compare(query(row["left"]), query(row["right"]), instances=instances)
        assert result["status"] == "not_distinguished"


def test_primary_key_law_does_not_infer_a_key_from_data():
    all_rows = query("all_count")
    pk = all_rows.model_copy(deep=True)
    pk.measures[0] = type(pk.measures[0]).model_validate(
        {
            "aggregate": "count_distinct",
            "column": {"table": "pos_sale", "column": "transaction_no"},
        }
    )
    assert compare(all_rows, pk)["status"] == "equivalent_in_fragment"
    schema = CONTEXTS["pos"][0].model_copy(deep=True)
    schema.tables[0].primary_key = []
    assert compare(all_rows, pk, schema=schema)["status"] == "not_distinguished"
    assert (
        compare(query("member_column_count"), query("member_distinct"))["status"]
        == "witnessed_difference"
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"dimensions": [{"table": "pos_sale", "column": "member_id"}]},
        {"limit": 1},
        {"order": [{"field": "row_count", "direction": "desc"}]},
        {"having": [{"field": "row_count", "op": "gt", "value": 1}]},
        {
            "filters": [
                {
                    "column": {"table": "pos_sale", "column": "member_id"},
                    "op": "eq",
                    "values": ["fake_m1"],
                }
            ]
        },
    ],
)
def test_unsupported_fields_cannot_be_silently_ignored(extra):
    plan = QueryPlan.model_validate({**FIXTURE["plans"]["all_count"], **extra})
    assert compare(plan, plan)["status"] == "outside_fragment"


def test_context_mismatch_cannot_certify_identical_plans():
    schema, overlay = CONTEXTS["pos"][:2]
    result = comparison.compare(
        query("all_count"),
        query("all_count"),
        schema,
        overlay,
        FIXTURE["instances"],
        as_of=prior.AS_OF,
        left_context="old",
        right_context="new",
    )
    assert result["status"] == "unavailable" and result["reason"] == "context_mismatch"


def test_invalid_witness_instance_is_not_a_difference():
    instances = deepcopy(FIXTURE["instances"])
    first = next(iter(instances.values()))["pos_sale"]
    first[1][0] = first[0][0]
    result = compare(
        query("all_count"), query("returns_count_metric"), instances=instances
    )
    assert result["status"] == "unavailable"


def test_engine_disagreement_prevents_a_witness(monkeypatch):
    monkeypatch.setattr(
        comparison, "evaluate", lambda *args: [{"return_count": 999, "row_count": 999}]
    )
    result = compare(query("all_count"), query("returns_count_metric"))
    assert result["status"] == "unavailable"


def test_translation_payload_has_no_context_answers_or_reference():
    case = CASES["output_count_all"]
    request = study.translation_messages(case["questions"]["zh"])
    assert json.loads(request[-1]["content"]) == {"question": case["questions"]["zh"]}
    assert "return_count" not in json.dumps(request)
    assert case["questions"]["en"] not in json.dumps(request)
    assert all(m["role"] != "assistant" for m in request)


@pytest.mark.parametrize("text", ["", "   ", 3, None])
def test_invalid_translation_is_not_sent_to_english_planner(text):
    with pytest.raises(ValueError):
        study.Translation.model_validate({"text": text})


def test_fidelity_never_promotes_a_plausible_nonexact_translation():
    case = CASES["output_count_all"]
    assert study.fidelity(case, case["questions"]["en"])["state"] == "reference_exact"
    result = study.fidelity(case, "Please provide the number of transactions.")
    assert result["state"] == "unreviewed" and not result["human_confirmed"]
    assert study.fidelity(case, None)["state"] == "unavailable"
    label = CASES["label_only"]
    assert label["labels"]["zh"] in study.reference_translation(label)
    assert study.fidelity(label, label["questions"]["en"])["state"] == "changed"


def test_schedule_is_frozen_and_has_twelve_independent_four_slot_bundles():
    ordered = study.schedule(GOLD)
    assert ordered == study.schedule(GOLD) and len(ordered) == 48
    for case in CASES:
        arms = [c["arm"] for c in ordered if c["case_id"] == case]
        assert set(arms) == {"Z1", "Z2", "T", "E"} and arms.index("T") < arms.index("E")
    changed = deepcopy(GOLD)
    changed["cases"] = changed["cases"][1:]
    with pytest.raises(ValueError, match="unexpected_case_universe"):
        study.schedule(changed)


def fake_live(monkeypatch, response):
    settings = study.GroundingModelSettings(
        base_url="http://unused.invalid", model="fake"
    )
    monkeypatch.setattr(
        study.GroundingModelSettings, "from_environment", lambda: settings
    )
    monkeypatch.setattr(
        study.ChatCompletionsGroundingClient,
        "_create_client",
        lambda self: SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(study, "call", response)


def test_transport_stop_retains_all_question_denominators(tmp_path, monkeypatch):
    fake_live(monkeypatch, lambda *args, **kwargs: {"status": "transport_error"})
    report = study.run(tmp_path / "run.json", live=True)
    assert (
        len(report["calls"]) == 3 and report["stop_reason"] == "three_transport_errors"
    )
    assert len(report["analysis"]["rows"]) == 12
    assert not report["completed"] and not report["eligible_for_confirmation"]


def test_source_drift_stops_before_any_external_attempt(tmp_path, monkeypatch):
    calls = []
    fake_live(monkeypatch, lambda *args, **kwargs: calls.append(1))
    sequence = iter(("before", "after", "after"))
    monkeypatch.setattr(
        study,
        "_source_snapshot",
        lambda: {"available": True, "tracked_source_digest": next(sequence)},
    )
    report = study.run(tmp_path / "run.json", live=True)
    assert not calls and report["stop_reason"] == "source_drift"
    assert not report["source_unchanged"]


def test_fresh_output_is_required_before_loading_credentials(tmp_path, monkeypatch):
    def forbidden():
        pytest.fail("credential settings were loaded")

    monkeypatch.setattr(study.GroundingModelSettings, "from_environment", forbidden)
    output = tmp_path / "run.json"
    output.with_suffix(".jsonl").write_text("existing")
    with pytest.raises(ValueError, match="fresh_output_required"):
        study.run(output, live=True)


def test_full_fake_schedule_never_exceeds_48_and_persists_fidelity_before_e(
    tmp_path, monkeypatch
):
    sent = []

    def response(client, settings, request, parser, **kwargs):
        assert settings.timeout_seconds == 60 and settings.repair_turns == 0
        assert kwargs == {"thinking": False, "max_tokens": 4096}
        sent.append(request)
        if request[0]["content"] == study.TRANSLATION_RULES:
            question = json.loads(request[-1]["content"])["question"]
            case = next(c for c in CASES.values() if c["questions"]["zh"] == question)
            payload = {"text": study.reference_translation(case)}
        else:
            payload = {
                "decision": "none",
                "reason": "ambiguous",
                "clarification": "unspecified",
            }
        return {
            "status": "ok",
            "result": parser(payload).model_dump(mode="json"),
            "request_sha256": digest(request),
        }

    fake_live(monkeypatch, response)
    output = tmp_path / "run.json"
    report = study.run(output, live=True)
    assert len(sent) == len(report["calls"]) == len(report["slots"]) == 48
    assert report["completed"] and not report["eligible_for_confirmation"]
    journal = [
        json.loads(line)
        for line in output.with_suffix(".jsonl").read_text().splitlines()
    ]
    for case in CASES:
        fid = next(
            i
            for i, row in enumerate(journal)
            if row.get("case_id") == case and "fidelity" in row
        )
        english = next(
            i
            for i, row in enumerate(journal)
            if row.get("call", {}).get("case_id") == case and row["call"]["arm"] == "E"
        )
        assert fid < english
        requests = [
            c["request_sha256"]
            for c in report["calls"]
            if c["case_id"] == case and c["arm"] in {"Z1", "Z2"}
        ]
        assert len(set(requests)) == 1


def test_bad_translations_skip_twelve_e_calls_without_losing_slots(
    tmp_path, monkeypatch
):
    fake_live(monkeypatch, lambda *args, **kwargs: {"status": "format_error"})
    report = study.run(tmp_path / "run.json", live=True)
    assert len(report["calls"]) == 36 and len(report["slots"]) == 48
    assert (
        sum(s["status"] == "skipped_translation_unavailable" for s in report["slots"])
        == 12
    )
    assert report["analysis"]["criteria"]["accounted_slots"] == 12
    assert not report["eligible_for_confirmation"]


def test_actual_ask_replay_keeps_wrong_verified_and_isolates_only_concept_gate():
    schema, overlay = CONTEXTS["pos"][:2]
    pack = load_shape_pack()
    instance = FIXTURE["instances"]["coincidental"]
    wrong = PlanProposal(decision="plan", plan=query("returns_count_metric"))
    result = study.replay(
        wrong,
        CASES["output_count_all"]["questions"]["zh"],
        schema,
        overlay,
        pack,
        instance,
        query("all_count"),
    )
    assert result["status"] == "answered" and result["verification"] == "verified"
    assert result["rows_match_gold"] is False and result["sql_executions"] == 1
    right = PlanProposal(decision="plan", plan=query("all_count"))
    question = CASES["output_count_all"]["questions"]["en"]
    current = study.replay(
        right, question, schema, overlay, pack, instance, query("all_count")
    )
    shadow = study.replay(
        right,
        question,
        schema,
        overlay,
        pack.model_copy(update={"concepts": []}, deep=True),
        instance,
        query("all_count"),
    )
    assert current["status"] == "clarify" and current["sql_executions"] == 0
    assert shadow["status"] == "answered" and shadow["rows_match_gold"] is True
    assert pack.concepts and result["model_calls"] == shadow["model_calls"] == 0


def positive_report():
    ordered = study.schedule(GOLD)
    report = {
        "contexts": {s: "bound" for s in CONTEXTS},
        "calls": [],
        "slots": ordered,
        "fidelity": {},
    }
    for item in ordered:
        case, arm = CASES[item["case_id"]], item["arm"]
        text = study.reference_translation(case)
        report["fidelity"][case["id"]] = study.fidelity(case, text)
        if arm == "T":
            continue
        if case["correct"]:
            name = (
                "returns_count_metric"
                if case["id"] == "output_count_all" and arm != "E"
                else case["correct"][0]
            )
            plan = query(name)
            if case.get("labels"):
                plan.measures[0].alias = case["labels"]["zh"]
            proposal = PlanProposal(decision="plan", plan=plan)
        else:
            proposal = PlanProposal(
                decision="none", reason="ambiguous", clarification="unspecified"
            )
        report["calls"].append(
            {
                **item,
                "status": "ok",
                "context_sha256": "bound",
                "question": text if arm == "E" else case["questions"]["zh"],
                "result": proposal.model_dump(mode="json"),
            }
        )
    return report


def test_end_to_end_analysis_credits_detection_not_intent_certification():
    result = study.analyze(
        positive_report(), GOLD, FIXTURE, CONTEXTS, load_shape_pack()
    )
    assert result["criteria"] == {
        "incremental": 1,
        "correct_controls": 10,
        "comparable_correct": 10,
        "false_alarms": 0,
        "accounted_slots": 12,
        "fidelity_unreviewed": 0,
    }
    assert result["screen_eligible"] and not result["certified"]
    assert len(result["replays"]) == 216
    assert all(r["model_calls"] == 0 for r in result["replays"])
    assert sum(r["status"] == "replay_unavailable" for r in result["replays"]) == 0


def test_source_identity_is_checked_after_analysis(tmp_path, monkeypatch):
    state = {"digest": "before"}
    monkeypatch.setattr(
        study,
        "_source_snapshot",
        lambda: {"available": True, "tracked_source_digest": state["digest"]},
    )
    original = study.analyze

    def changed(*args):
        result = original(*args)
        state["digest"] = "after"
        return result

    monkeypatch.setattr(study, "analyze", changed)
    report = study.run(tmp_path / "dry.json")
    assert not report["source_unchanged"] and not report["eligible_for_confirmation"]


def test_live_call_budget_uses_runtime_guard_even_if_schedule_is_corrupt(
    tmp_path, monkeypatch
):
    original = study.schedule(GOLD)
    # Do not send anything when a frozen schedule no longer has 48 slots.
    monkeypatch.setattr(study, "schedule", lambda ruler: original + original[:1])
    invoked = []
    fake_live(monkeypatch, lambda *args, **kwargs: invoked.append(1))
    with pytest.raises(ValueError, match="unexpected_call_budget"):
        study.run(tmp_path / "run.json", live=True)
    assert not invoked
