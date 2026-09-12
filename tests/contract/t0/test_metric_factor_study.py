"""Research implementation against the approved factor/presentation rulers."""

import json
from copy import deepcopy

import pytest
import test_metric_factor_rulers as rulers
from jsonschema import Draft202012Validator

from evals import metric_factor_selection as factor
from evals import metric_factor_study as study
from evals.metric_selection import authored_annotation
from evals.metric_wire_selection import bind_selection


@pytest.mark.parametrize("name", ["FactorPair", "FactoredSelection"])
def test_runtime_factor_shapes_match_checkpoint(name):
    assert (
        getattr(factor, name).model_json_schema()
        == getattr(rulers, name).model_json_schema()
    )


@pytest.mark.parametrize("case", rulers.GOLD["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_new_display_retains_all_positive_canonical_controls(case, language):
    source = "service" if case["id"] in study.previous.prior.SERVICE_CASES else "pos"
    request = study.messages(
        case["questions"][language], source, "W", rulers.CONTEXTS, rulers.CATALOGS
    )
    shown = json.loads(request[1]["content"])
    Draft202012Validator.check_schema(shown)
    payload = rulers.wire_payload(case, language)
    Draft202012Validator(shown).validate(payload)
    assert study.parse_record(
        payload,
        {"arm": "W", "source": source},
        case["questions"][language],
        rulers.CONTEXTS,
        rulers.CATALOGS,
        {},
    ) == authored_annotation(rulers.GOLD, case, language)


@pytest.mark.parametrize(
    "vector", rulers.RULERS["shown_schema_counterexamples"], ids=lambda v: v["id"]
)
def test_old_display_is_frozen_while_new_display_exposes_gap(vector):
    case, payload = rulers.counterexample(vector["id"])
    request = study.messages(
        case["questions"]["en"], "pos", "B", rulers.CONTEXTS, rulers.CATALOGS
    )
    assert Draft202012Validator(json.loads(request[1]["content"])).is_valid(payload)


@pytest.mark.parametrize("source", ["pos", "service"])
def test_factor_runtime_exactly_reverses_test_only_relation(source):
    candidates = rulers.CATALOGS[source]
    assert factor.factor_catalog(candidates) == rulers.factor_spec(candidates)
    bases, populations, pairs = factor.factor_catalog(candidates)
    assert factor.factor_cards(candidates) == factor.factor_cards(
        list(reversed(candidates))
    )
    for (bid, pid), candidate in pairs.items():
        payload = {
            "decision": "pick",
            "slots": {"value": {"basis_id": bid, "population_id": pid}},
            "reason": None,
            "output_label": None,
        }
        expected = {**payload, "slots": {"value": candidate["id"]}}
        assert factor.bind_factors(payload, candidates, "question") == bind_selection(
            expected, candidates, "question"
        )
    assert len(pairs) == len(candidates)
    assert bases and populations


def test_unoffered_pair_rejects_and_preserves_safe_diagnostics():
    observation = {}
    with pytest.raises(ValueError, match="pair_not_offered"):
        study.parse_record(
            {
                "decision": "pick",
                "slots": {
                    "value": {"basis_id": "DO_NOT_EMIT", "population_id": "DO_NOT_EMIT"}
                },
                "reason": None,
                "output_label": None,
            },
            {"arm": "F", "source": "pos"},
            "question",
            rulers.CONTEXTS,
            rulers.CATALOGS,
            observation,
        )
    assert "DO_NOT_EMIT" not in json.dumps(observation)
    assert observation["diagnostics"][0]["code"] == "pair_not_offered"
    assert "factor_selection" not in observation


@pytest.mark.parametrize("source", ["pos", "service"])
def test_factor_payload_retains_all_metadata_without_gold_or_materialized_operands(
    source,
):
    request = study.messages("question", source, "F", rulers.CONTEXTS, rulers.CATALOGS)
    flat = study.messages("question", source, "S", rulers.CONTEXTS, rulers.CATALOGS)
    payload, old = json.loads(request[-1]["content"]), json.loads(flat[-1]["content"])
    cards = payload.pop("candidate_factors")
    old_cards = old.pop("candidates")
    assert payload == old
    assert sorted(
        [m for p in cards["allowed_pairs"] for m in p["reviewed_metrics"]],
        key=lambda m: m["id"],
    ) == sorted(
        [m for c in old_cards for m in c["reviewed_metrics"]], key=lambda m: m["id"]
    )
    assert "operand" not in json.dumps(cards)
    assert all(
        k not in cards for k in ("gold", "questions", "rows", "expected", "plans")
    )
    assert (
        request[0]["content"].split("Decide what rows/entities")[1]
        == flat[0]["content"].split("Decide what rows/entities")[1]
    )


def test_partial_run_never_qualifies_or_claims_order_measurement():
    analysis = study.analyze([], rulers.GOLD, rulers.FIXTURE, rulers.CONTEXTS)
    result = study.screen(analysis, rulers.GOLD)
    assert not result["W"]["eligible"]
    assert not result["F"]["eligible_for_confirmation"]
    assert "order" not in analysis
    assert result["F"]["order_confirmation"] == "not_measured"


def test_missing_value_checks_never_count_as_correct():
    analysis = study.analyze([], rulers.GOLD, rulers.FIXTURE, rulers.CONTEXTS)
    row = {
        "arm": "P",
        "case_id": "output_count_all",
        "language": "zh",
        "verdict": "pass",
        "compiled": True,
        "values": [],
        "gold_state": "clear",
        "family": "output_count",
    }
    analysis["plans"] = [row, {**deepcopy(row), "arm": "F"}]
    assert study.screen(analysis, rulers.GOLD)["F"]["F_correct"] == 0


def test_interrupted_schedule_can_include_selector_before_its_planner_control():
    analysis = study.analyze(
        [
            {
                "arm": "F",
                "case_id": "service_entities",
                "language": "en",
                "source": "service",
                "status": "transport_error",
            },
        ],
        rulers.GOLD,
        rulers.FIXTURE,
        rulers.CONTEXTS,
    )
    result = study.screen(analysis, rulers.GOLD)
    assert result["F"]["improved"] == result["F"]["lost_correct"] == []
    assert not result["F"]["eligible_for_confirmation"]


def test_dry_schedule_has_five_frozen_arms_and_zero_calls(tmp_path):
    report = study.run(tmp_path / "dry.json")
    assert len(report["schedule"]) == 180 and not report["calls"]
    assert {c["arm"] for c in report["schedule"]} == set(study.ARMS)
    assert report["source_unchanged"] and not report["completed"]
    assert report["settings"]["max_retries"] == 0
    assert all(c["covered"] for c in report["coverage"])
