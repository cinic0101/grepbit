"""Research interface implementation against the approved, unchanged rulers."""

import json
from types import SimpleNamespace

import pytest
import test_metric_wire_selection_rulers as rulers
from pydantic import ValidationError

from evals import metric_wire_selection as wire
from evals import metric_wire_study as study
from evals.metric_selection import authored_annotation
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings

RULER, FIXTURE, CONTEXTS, CATALOGS, COVERAGE = study.prepare()


@pytest.mark.parametrize("name", ["OccurrenceSpan", "Selection"])
def test_runtime_shapes_preserve_checkpoint(name):
    assert (
        getattr(wire, name).model_json_schema()
        == getattr(rulers, name).model_json_schema()
    )


@pytest.mark.parametrize("case", RULER["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_exact_wire_conversion_never_changes_semantic_fields(case, language):
    source = "service" if case["id"] in study.prior.SERVICE_CASES else "pos"
    schema, _, _, _, concepts = CONTEXTS[source]
    gold = authored_annotation(RULER, case, language)
    payload = gold.model_dump()
    payload["spans"] = [
        {**s, "occurrence": s.get("occurrence", 0)} for s in case["spans"][language]
    ]
    assert (
        wire.parse_occurrences(payload, case["questions"][language], schema, concepts)
        == gold
    )
    payload["state"] = "clear" if gold.state != "clear" else "ambiguous"
    with pytest.raises(ValidationError):
        wire.parse_occurrences(payload, case["questions"][language], schema, concepts)


@pytest.mark.parametrize("case", rulers.RULERS["locations"], ids=lambda c: c["id"])
def test_resolver_against_hand_vectors(case):
    if "expected" in case:
        assert wire.locate(case["text"], case["occurrence"], case["question"]) == tuple(
            case["expected"]
        )
    else:
        with pytest.raises(ValueError):
            wire.locate(case["text"], case["occurrence"], case["question"])


def test_safe_diagnostics_never_emit_unknown_keys_or_exception_text():
    marker = "DO_NOT_EMIT_SECRET"
    try:
        wire.Selection.model_validate({marker: marker})
    except ValidationError as error:
        safe = wire.diagnostics(error)
    assert marker not in json.dumps(safe)
    assert all(set(e) == {"stage", "code", "schema_path", "count"} for e in safe)
    assert len(safe) <= 8
    assert wire.diagnostics(ValueError(marker))[0]["code"] == "unclassified_validation"
    assert (
        wire.diagnostics(ValueError("candidate_not_offered"))[0]["code"]
        == "candidate_not_offered"
    )


def test_semantic_diagnostics_do_not_convert_failed_response_to_success():
    case = RULER["cases"][0]
    schema, _, _, _, concepts = CONTEXTS["pos"]
    payload = authored_annotation(RULER, case, "en").model_dump()
    payload["spans"][0]["start"] = 999
    observation = {}
    with pytest.raises(ValueError):
        study.parse_record(
            payload,
            {"arm": "A", "source": "pos"},
            case["questions"]["en"],
            CONTEXTS,
            CATALOGS,
            observation,
        )
    assert observation["diagnostic_core"] is not None
    assert observation["diagnostics"]
    assert "result" not in observation
    assert "spans" not in observation["diagnostic_core"]


def test_catalog_is_bounded_deduplicated_and_independent_of_gold():
    assert all(c["covered"] for c in COVERAGE)
    assert {s: len(v) for s, v in CATALOGS.items()} == {"pos": 39, "service": 17}
    for source, values in CATALOGS.items():
        schema, overlay, _, _, _ = CONTEXTS[source]
        assert values == wire.catalog(schema, overlay)
        keys = [
            wire.digest(wire.signature(c["operand"], c["base_table"], schema, overlay))
            for c in values
        ]
        assert len(keys) == len(set(keys)) == len({c["id"] for c in values})
        assert any(c["reviewed_metrics"] for c in values) is (source == "pos")


@pytest.mark.parametrize("source", ["pos", "service"])
def test_reversing_order_preserves_candidate_bindings_and_payload(source):
    one = study.messages("Return the count.", source, "S1", CONTEXTS, CATALOGS)
    two = study.messages("Return the count.", source, "S2", CONTEXTS, CATALOGS)
    assert one[:2] == two[:2]
    p1, p2 = json.loads(one[-1]["content"]), json.loads(two[-1]["content"])
    p2["candidates"].reverse()
    assert p1 == p2
    assert all("operand" not in c for c in p1["candidates"])
    for candidate in CATALOGS[source]:
        payload = {
            "decision": "pick",
            "slots": {"value": candidate["id"]},
            "reason": None,
            "output_label": None,
        }
        assert wire.bind_selection(
            payload, CATALOGS[source], "q"
        ) == wire.bind_selection(payload, list(reversed(CATALOGS[source])), "q")


def test_unoffered_ids_cross_table_and_label_invention_are_rejected():
    candidate = CATALOGS["pos"][0]
    payload = {
        "decision": "pick",
        "slots": {"value": "unknown"},
        "reason": None,
        "output_label": None,
    }
    with pytest.raises(ValueError, match="candidate_not_offered"):
        wire.bind_selection(payload, CATALOGS["pos"], "q")
    payload["slots"] = {
        "numerator": candidate["id"],
        "denominator": CATALOGS["service"][0]["id"],
    }
    with pytest.raises(ValueError, match="candidate_cross_table"):
        wire.bind_selection(payload, CATALOGS["pos"] + CATALOGS["service"], "q")
    payload.update(slots={"value": candidate["id"]}, output_label="invented")
    with pytest.raises(ValueError, match="candidate_label_not_in_question"):
        wire.bind_selection(payload, CATALOGS["pos"], "q")


def test_catalog_missing_is_not_a_correct_semantic_refusal():
    case = next(c for c in RULER["cases"] if c["id"] == "rate_unspecified")
    chosen = wire.bind_selection(
        {
            "decision": "no_candidate",
            "reason": "outside_catalog",
            "slots": {},
            "output_label": None,
        },
        CATALOGS["pos"],
        case["questions"]["en"],
    )
    report = study.analyze(
        [
            {
                "case_id": case["id"],
                "language": "en",
                "arm": "S1",
                "source": "pos",
                "status": "ok",
                "result": chosen.model_dump(mode="json"),
            }
        ],
        RULER,
        FIXTURE,
        CONTEXTS,
    )
    assert report["plans"][0]["verdict"] == "candidate_missing"
    assert not report["plans"][0]["refusal_correct"]


def test_b_changes_only_span_schema_and_localization_instruction():
    a = study.messages("question", "pos", "A", CONTEXTS, CATALOGS)
    b = study.messages("question", "pos", "B", CONTEXTS, CATALOGS)
    assert a[-1] == b[-1]
    sa = json.loads(a[1]["content"])
    sb = json.loads(b[1]["content"])
    assert {k: v for k, v in sa["properties"].items() if k != "spans"} == {
        k: v for k, v in sb["properties"].items() if k != "spans"
    }
    assert sa["required"] == sb["required"]
    for arm in study.ARMS:
        payload = json.loads(
            study.messages("question", "pos", arm, CONTEXTS, CATALOGS)[-1]["content"]
        )
        assert not set(payload) & {
            "gold",
            "profiles",
            "rows",
            "instances",
            "plans",
            "correct",
            "wrong",
        }
        assert "fake_origin" not in json.dumps(payload)


@pytest.mark.parametrize("fail,expected", [(False, 180), (True, 3)])
def test_runner_no_hidden_calls_and_fresh_outputs(
    monkeypatch, tmp_path, fail, expected
):
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
    calls = []

    def fake_call(client, settings, request, parser, **kwargs):
        assert kwargs == {"thinking": False, "max_tokens": 4096}
        assert settings.timeout_seconds == 60
        calls.append(request)
        return {"status": "transport_error" if fail else "format_error"}

    monkeypatch.setattr(study, "call", fake_call)
    output = tmp_path / "report.json"
    result = study.run(output, live=True)
    assert len(calls) == expected and closed == [True]
    assert result["completed"] is (not fail)
    assert result["source_unchanged"]
    assert {r["case_id"] for r in result["schedule"]} == {
        c["id"] for c in RULER["cases"] if c["split"] == "development"
    }
    with pytest.raises(ValueError, match="fresh_output_required"):
        study.run(output, live=True)
