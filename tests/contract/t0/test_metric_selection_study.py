"""Approved research grader, unchanged rulers and inference-exposure guards."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
import test_metric_selection_ruler as ruler_test

from evals import metric_selection_study as study
from evals.metric_selection import (
    Interpretation,
    annotation_core,
    authored_annotation,
    check_plan,
    validate_interpretation,
)
from grepbit.domain.plan import QueryPlan

RULER, FIXTURE = study.load_inputs()


def test_promoted_schema_and_fixture_preserve_approved_ruler():
    actual = Interpretation.model_json_schema()
    expected = ruler_test.Interpretation.model_json_schema()
    actual.pop("description")
    expected.pop("description")
    assert actual == expected
    assert FIXTURE["schema"] == ruler_test.SCHEMA.model_dump(mode="json")
    assert FIXTURE["plans"] == ruler_test.PLANS
    assert FIXTURE["instances"] == json.loads(json.dumps(ruler_test.INSTANCES))
    for case in RULER["cases"]:
        for language in case["questions"]:
            assert authored_annotation(RULER, case, language).model_dump() == (
                ruler_test.Interpretation.model_validate(
                    ruler_test.draft_payload(case, language)
                ).model_dump()
            )


@pytest.mark.parametrize("pair", study.fixed_checks(RULER, FIXTURE))
def test_fixed_grader_agrees_with_frozen_hand_rulers(pair):
    assert pair["verdict"] == pair["expected"], pair


@pytest.mark.parametrize(
    "extra",
    [
        {"order": [{"field": "row_count", "direction": "desc"}]},
        {"limit": 1},
        {"having": [{"field": "row_count", "op": "gt", "value": 1}]},
        {
            "filters": [
                {
                    "column": {"table": "pos_sale", "column": "total_amount"},
                    "op": "gt",
                    "values": [1],
                }
            ]
        },
    ],
)
def test_unknown_fragment_is_never_silently_ignored(extra):
    case = RULER["cases"][0]
    gold = authored_annotation(RULER, case, "en")
    schema, overlay, _, _, concepts = study.context("pos", "P0", FIXTURE)
    plan = QueryPlan.model_validate({**FIXTURE["plans"]["all_count"], **extra})
    assert check_plan(gold, plan, schema, concepts, overlay)["verdict"] == "unknown"


def test_null_count_law_not_same_as_distinct_or_row_sum():
    case = next(c for c in RULER["cases"] if c["profile"] == "member_count")
    gold = authored_annotation(RULER, case, "en")
    schema, overlay, _, _, concepts = study.context("pos", "P0", FIXTURE)
    for key, expected in (
        ("member_column_count", "pass"),
        ("member_count", "pass"),
        ("member_distinct", "fail"),
        ("all_count", "fail"),
    ):
        assert (
            check_plan(
                gold,
                QueryPlan.model_validate(FIXTURE["plans"][key]),
                schema,
                concepts,
                overlay,
            )["verdict"]
            == expected
        )


def test_well_formed_claim_is_not_language_truth():
    case = RULER["cases"][0]
    schema, _, _, _, concepts = study.context("pos", "L1", FIXTURE)
    gold = authored_annotation(RULER, case, "en")
    wrong = gold.model_dump()
    wrong["basis"][0].update(aggregate="sum", column="pos_sale.total_amount")
    parsed = validate_interpretation(wrong, case["questions"]["en"], schema, concepts)
    assert annotation_core(parsed) != annotation_core(gold)


@pytest.mark.parametrize("source", ["pos", "service"])
def test_catalog_transformations_keep_effective_definitions(source):
    schema, baseline, _, _, _ = study.context(source, "P0", FIXTURE)
    _, added, _, _, _ = study.context(source, "P1", FIXTURE)
    assert added.metrics[: len(baseline.metrics)] == baseline.metrics
    assert len(added.metrics) == len(baseline.metrics) + (source == "pos")
    if source == "pos":
        assert added.metrics[-1].aggregate == "count" and not added.metrics[-1].filters
        assert added.metrics[-1].column is None
    _, canonical, shown, reverse, _ = study.context(source, "P2", FIXTURE)
    assert canonical == added
    for renamed, original in zip(shown.metrics, added.metrics, strict=True):
        assert renamed.model_copy(update={"id": reverse[renamed.id]}) == original
    for arm, overlay in (("P1", added), ("P3", added)):
        request = study.planner_messages(
            "Return the transaction count.", schema, overlay, arm
        )
        entries = json.loads(request[-1]["content"])["schema"].get(
            "reviewed_metrics", []
        )
        for entry, metric in zip(entries, added.metrics, strict=True):
            card = entry.pop("operation_card", None)
            if arm == "P3":
                assert card["population"] == [
                    f.model_dump(mode="json") for f in metric.filters
                ]
                assert card["operation"] == metric.aggregate
            assert entry["description"] == metric.description
            assert entry["names"] == metric.names


def test_only_question_schema_definitions_reach_requests():
    fixture = deepcopy(FIXTURE)
    fixture["plans"] = {"gold": "DO_NOT_SEND_GOLD"}
    fixture["instances"] = {"row": "DO_NOT_SEND_ROWS"}
    fixture["expected"] = "DO_NOT_SEND_EXPECTED"
    for source in ("pos", "service"):
        for arm in study.ARMS:
            schema, _, shown, _, concepts = study.context(source, arm, fixture)
            request = (
                study.interpretation_messages("question", schema, concepts)
                if arm == "L1"
                else study.planner_messages("question", schema, shown, arm)
            )
            text = json.dumps(request)
            assert "DO_NOT_SEND" not in text and "fake_origin" not in text
            payload = json.loads(request[-1]["content"])
            assert set(payload) == (
                {"question", "schema", "concepts", "default_segments"}
                if arm == "L1"
                else {"question", "schema", "as_of", "prompt_revision"}
            )
            assert "plan" not in payload and "spans" not in payload


def test_p2_maps_nested_metric_ids_back_before_gate():
    schema, _, _, reverse, _ = study.context("pos", "P2", FIXTURE)
    key = next(k for k, v in reverse.items() if v == "return_count")
    parsed = study.parse_plan(
        {
            "decision": "plan",
            "plan": {
                "base_table": "pos_sale",
                "measures": [
                    {
                        "numerator": {"metric": key},
                        "denominator": {"aggregate": "count"},
                    }
                ],
            },
        },
        schema,
        reverse,
    )
    assert parsed.plan.measures[0].ratio.numerator.metric == "return_count"
    with pytest.raises(ValueError, match="unoffered_metric_id"):
        study.parse_plan(
            {"decision": "plan", "plan": FIXTURE["plans"]["returns_count_metric"]},
            schema,
            reverse,
        )


def test_schedule_has_only_development_and_exact_budget():
    scheduled = study.schedule(RULER)
    assert (
        len(scheduled)
        == len({(r["case_id"], r["language"], r["arm"]) for r in scheduled})
        == 180
    )
    assert {r["case_id"] for r in scheduled} == {
        c["id"] for c in RULER["cases"] if c["split"] == "development"
    }
    assert study.schedule(RULER) == scheduled


def test_unique_primary_key_distinct_count_is_row_count_not_member_distinct():
    schema, overlay, _, _, concepts = study.context("pos", "P0", FIXTURE)
    gold = authored_annotation(RULER, RULER["cases"][0], "en")
    plan = QueryPlan.model_validate(
        {
            "base_table": "pos_sale",
            "measures": [
                {
                    "aggregate": "count_distinct",
                    "column": {"table": "pos_sale", "column": "transaction_no"},
                }
            ],
        }
    )
    assert check_plan(gold, plan, schema, concepts, overlay)["verdict"] == "pass"


def test_sample_values_cannot_enter_the_projection():
    fixture = deepcopy(FIXTURE)
    fixture["schema"]["tables"][0]["columns"][0]["sample_values"] = ["DO_NOT_SEND"]
    with pytest.raises(ValueError, match="sample_values_forbidden"):
        study.context("pos", "P0", fixture)


def test_captured_plan_replay_checks_compiler_values_and_gate_separately():
    records = []
    for case in RULER["cases"]:
        for key in ("correct", "wrong", "unresolved_candidates"):
            for name in case.get(key, []):
                plan = deepcopy(FIXTURE["plans"][name])
                if case.get("labels"):
                    plan["measures"][0]["alias"] = case["labels"]["en"]
                records.append(
                    {
                        "case_id": case["id"],
                        "language": "en",
                        "arm": "P0",
                        "source": "service"
                        if case["id"] in study.SERVICE_CASES
                        else "pos",
                        "status": "ok",
                        "result": {"decision": "plan", "plan": plan},
                    }
                )
    analysis = study.analyze(records, RULER, FIXTURE)
    assert all(r["compiled"] for r in analysis["plans"])
    for row in analysis["plans"]:
        checks = row["value_checks"]
        assert len(checks) == 3
        assert all(
            c["status"] == "ok" and c["compiler_reference_match"] for c in checks
        )
        if row["pre_gate"] == "pass":
            assert all(c["gold_values_match"] for c in checks)
        elif row["pre_gate"] == "fail":
            assert not all(c["gold_values_match"] for c in checks)
    assert analysis["summaries"]["P0"]["correct_false_blocks"] > 0
    assert analysis["summaries"]["P0"]["wrong_unblocked"] > 0


@pytest.mark.parametrize("transport_error, expected", [(False, 180), (True, 3)])
def test_fake_live_is_bounded_serial_and_fresh(
    monkeypatch, tmp_path, transport_error, expected
):
    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings

    monkeypatch.setattr(
        GroundingModelSettings,
        "from_environment",
        lambda: GroundingModelSettings(base_url="http://unused.invalid", model="fake"),
    )
    closed = []
    monkeypatch.setattr(
        study.ChatCompletionsGroundingClient,
        "_create_client",
        lambda self: SimpleNamespace(close=lambda: closed.append(True)),
    )
    invocations = []

    def fake_call(client, settings, request, parser, **kwargs):
        assert settings.timeout_seconds == 60
        assert kwargs == {"thinking": False, "max_tokens": 4096}
        invocations.append(request)
        return {"status": "transport_error" if transport_error else "format_error"}

    monkeypatch.setattr(study, "call", fake_call)
    output = tmp_path / "result.json"
    report = study.run(output, live=True)
    assert len(invocations) == len(report["calls"]) == expected
    assert report["completed"] is (not transport_error)
    assert report["source_unchanged"] and closed == [True]
    with pytest.raises(ValueError, match="fresh_output_required"):
        study.run(output, live=True)
