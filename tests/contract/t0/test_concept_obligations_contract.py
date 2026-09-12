"""Approved v2: oracle-input correctness, scope limits and experiment hygiene."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from hypothesis import find, settings
from hypothesis import strategies as st
from t0_helpers import AS_OF, col
from test_concept_obligations_v2_ruler import DraftObligations, schema

from evals import concept_obligations_pilot as pilot
from evals.concept_obligations import (
    Obligations,
    check_obligations,
    core,
    validate_obligations,
)
from evals.plan_generator import SchemaShape, draw_operand
from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import Filter, QueryPlan
from grepbit.domain.schema_model import ColumnKind

RULER, FIXTURE = pilot.load_study()


@pytest.mark.parametrize("row", pilot.oracle_records(RULER, FIXTURE))
def test_every_fixed_pair_with_gold_obligations(row):
    assert row["verdict"] == row["expected"], row


def test_schema_matches_independently_written_checkpoint_ruler():
    for family in RULER["families"]:
        context, _ = pilot.study_context(family["id"], RULER, FIXTURE)
        for question in family["questions"].values():
            payload = pilot.gold_payload(family, question)
            assert (
                validate_obligations(
                    payload, question, context["concepts"]
                ).model_dump()
                == DraftObligations.model_validate(payload).model_dump()
            )


@pytest.mark.parametrize("mutation", ["id", "span", "role", "duplicate", "extra"])
def test_invalid_claims_are_not_normalized_into_valid_ones(mutation):
    family = RULER["families"][0]
    question = family["questions"]["en"]
    payload = pilot.gold_payload(family, question)
    requirement = payload["requirements"][0]
    if mutation == "id":
        requirement["concept"] = "not_offered"
    elif mutation == "span":
        requirement["span"] = "not in question"
    elif mutation == "role":
        requirement["role"] = "global"
    elif mutation == "duplicate":
        payload["requirements"].append(deepcopy(requirement))
    else:
        payload["confidence"] = 1
    with pytest.raises(ValueError):
        validate_obligations(payload, question, RULER["concepts"])


@pytest.mark.parametrize(
    "mutation",
    ["time", "limit", "share", "metric", "conflict", "join", "unknown_filter", "role"],
)
def test_unsupported_or_conflicting_shapes_cannot_become_passes(mutation):
    family = RULER["families"][0]
    question = family["questions"]["en"]
    claims = pilot.gold_payload(family, question)
    query = deepcopy(FIXTURE["plans"]["count_all"])
    if mutation == "time":
        query["time"] = {"grain": "month"}
    elif mutation == "limit":
        query["limit"] = 1
    elif mutation == "share":
        query = deepcopy(FIXTURE["plans"]["member_count"])
        query["measures"][0]["share_of_total"] = True
    elif mutation == "metric":
        query["measures"] = [{"metric": "unknown"}]
    elif mutation == "conflict":
        query["filters"] = [
            {"column": {"table": "pos_sale", "column": "member_id"}, "op": op}
            for op in ("is_null", "not_null")
        ]
    elif mutation == "join":
        query["dimensions"] = [{"table": "parent", "column": "id"}]
    elif mutation == "unknown_filter":
        query["filters"] = [
            {"column": {"table": "pos_sale", "column": "other"}, "op": "not_null"}
        ]
    else:
        claims["requirements"][0]["role"] = "denominator"
    assert (
        check_obligations(
            Obligations.model_validate(claims),
            QueryPlan.model_validate(query),
            RULER["concepts"],
            None,
        )[0]
        == "unknown"
    )


def test_unresolved_and_missing_bindings_never_erase_known_constraints():
    family = next(f for f in RULER["families"] if f["unresolved"] and f["requirements"])
    payload = pilot.gold_payload(family, family["questions"]["en"])
    claims = Obligations.model_validate(payload)
    assert len(claims.requirements) == 2
    query = QueryPlan.model_validate(FIXTURE["plans"]["member_return_over_members"])
    assert check_obligations(claims, query, RULER["concepts"], None)[0] == "unknown"
    payload["unresolved"] = []
    definitions = deepcopy(RULER["concepts"])
    definitions["member"]["binding"] = None
    assert check_obligations(
        Obligations.model_validate(payload), query, definitions, None
    ) == ("unknown", "binding_unavailable")


def test_reviewed_metric_filters_and_implicit_count_are_both_expanded():
    family = RULER["families"][0]
    payload = pilot.gold_payload(family, family["questions"]["en"])
    query = QueryPlan.model_validate(
        {"base_table": "pos_sale", "measures": [{"metric": "members"}]}
    )
    for metric_form in (
        {"column": {"table": "pos_sale", "column": "member_id"}},
        {"filters": FIXTURE["plans"]["member_count"]["filters"]},
    ):
        overlay = SemanticOverlay.model_validate(
            {
                "datasource_id": "test",
                "revision": "test",
                "metrics": [
                    {
                        "id": "members",
                        "names": ["members"],
                        "description": "test",
                        "base_table": "pos_sale",
                        "aggregate": "count",
                        **metric_form,
                    }
                ],
            }
        )
        assert (
            check_obligations(
                Obligations.model_validate(payload), query, RULER["concepts"], overlay
            )[0]
            == "fail"
        )
        include = deepcopy(payload)
        include["requirements"][0]["polarity"] = "include"
        assert (
            check_obligations(
                Obligations.model_validate(include), query, RULER["concepts"], overlay
            )[0]
            == "pass"
        )


def test_plan_filters_restrict_both_ratio_operands_and_bindings_can_use_is_null():
    family = next(
        f
        for f in RULER["families"]
        if f["id"] == "member_numerator_unrestricted_denominator"
    )
    payload = pilot.gold_payload(family, family["questions"]["en"])
    query = deepcopy(FIXTURE["plans"]["member_ratio"])
    query["filters"] = deepcopy(FIXTURE["plans"]["member_count"]["filters"])
    assert (
        check_obligations(
            Obligations.model_validate(payload),
            QueryPlan.model_validate(query),
            RULER["concepts"],
            None,
        )[0]
        == "fail"
    )
    inverted = deepcopy(RULER["concepts"])
    inverted["member"]["binding"]["op"] = "is_null"
    payload["requirements"] = [
        {
            "concept": "member",
            "polarity": "exclude",
            "role": "population",
            "span": "test",
        }
    ]
    assert (
        check_obligations(
            Obligations.model_validate(payload),
            QueryPlan.model_validate(FIXTURE["plans"]["member_count"]),
            inverted,
            None,
        )[0]
        == "pass"
    )


def test_count_generator_reaches_nullable_columns_without_data_sampling():
    shape = SchemaShape(schema())

    @st.composite
    def operand(draw):
        return draw_operand(SimpleNamespace(draw=draw), shape, "pos_sale")

    result = find(
        operand(),
        lambda p: (
            p.get("aggregate") == "count"
            and p.get("column", {}).get("column") == "member_id"
        ),
        settings=settings(max_examples=2000, database=None, derandomize=True),
    )
    assert result["column"] == {"table": "pos_sale", "column": "member_id"}


def test_ratio_wrapper_filters_are_unknown_not_silently_ignored():
    family = next(
        f
        for f in RULER["families"]
        if f["id"] == "member_numerator_unrestricted_denominator"
    )
    payload = pilot.gold_payload(family, family["questions"]["en"])
    query = deepcopy(FIXTURE["plans"]["member_ratio"])
    plan = QueryPlan.model_validate(query)
    # The domain now rejects this payload. Retain the research safety-net
    # assertion for unchecked in-memory models, without weakening the ruler.
    plan.measures[0] = plan.measures[0].model_copy(
        update={
            "filters": [
                Filter.model_validate(
                    {
                        "column": {
                            "table": "pos_sale",
                            "column": "origin_transaction_no",
                        },
                        "op": "not_null",
                    }
                )
            ]
        }
    )
    assert check_obligations(
        Obligations.model_validate(payload),
        plan,
        RULER["concepts"],
        None,
    ) == ("unknown", "shape_outside_v2")


@pytest.mark.parametrize("values", [[], [None, None], [None, "m", "m"]])
@pytest.mark.parametrize("form", ["plain", "ratio", "metric"])
def test_count_nulls_star_and_reviewed_forms_have_separate_hand_values(values, form):
    model = schema()
    model.tables[0].columns.append(col("other", ColumnKind.NUMERIC))
    column = {"table": "pos_sale", "column": "member_id"}
    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": model.datasource_id,
            "revision": "count-ruler",
            "metrics": [
                {
                    "id": "present",
                    "names": ["present IDs"],
                    "description": "test",
                    "base_table": "pos_sale",
                    "aggregate": "count",
                    "column": column,
                    "review_state": "verified",
                }
            ],
        }
    )
    measure = {"aggregate": "count", "column": column}
    if form == "ratio":
        measure = {
            "ratio": {"numerator": measure, "denominator": {"aggregate": "count"}}
        }
    elif form == "metric":
        measure = {"metric": "present"}
    query = QueryPlan.model_validate({"base_table": "pos_sale", "measures": [measure]})
    tables = {
        "pos_sale": [
            {"transaction_no": i + 1, "member_id": value}
            for i, value in enumerate(values)
        ]
    }
    compiled = PlanCompiler(model, overlay=overlay).compile(query, as_of=AS_OF)
    expected = sum(v is not None for v in values)
    if form == "ratio":
        expected = expected / len(values) if values else None
    duck = DuckInstance(model, tables)
    try:
        _, sql_rows = duck.execute(compiled.compiled)
    finally:
        duck.con.close()
    reference = evaluate(query, model, overlay, AS_OF, tables)
    for actual in (sql_rows[0][0], reference[0][compiled.output_columns[0]]):
        assert (
            actual == pytest.approx(expected)
            if expected is not None
            else actual is None
        )


def test_model_projection_never_contains_expected_claims_or_plans():
    ruler, fixture = deepcopy(RULER), deepcopy(FIXTURE)
    family = ruler["families"][0]
    context, _ = pilot.study_context(family["id"], ruler, fixture)
    request = pilot.messages(family["questions"]["en"], context)
    family["requirements"] = [{"SENTINEL_GOLD": "private"}]
    fixture["plans"] = {"SENTINEL_PLAN": "private"}
    poisoned, _ = pilot.study_context(family["id"], ruler, fixture)
    assert request == pilot.messages(family["questions"]["en"], poisoned)
    payload = json.loads(request[-1]["content"])
    assert set(payload) == {
        "question",
        "schema",
        "concepts",
        "metrics",
        "default_segments",
    }


@pytest.mark.parametrize("failure", [False, True])
def test_fake_live_instrument_budget_privacy_and_freshness(
    tmp_path, monkeypatch, failure
):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        if failure:
            raise RuntimeError("SECRET_SENTINEL")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps({k: [] for k in pilot.FIELDS}),
                        reasoning_content="SECRET_SENTINEL",
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=lambda: None,
    )
    monkeypatch.setattr(
        pilot.GroundingModelSettings,
        "from_environment",
        classmethod(
            lambda cls: GroundingModelSettings(base_url="unused", model="fake")
        ),
    )
    monkeypatch.setattr(
        pilot.ChatCompletionsGroundingClient, "_create_client", lambda self: client
    )
    output = tmp_path / "run.json"
    assert pilot.run(output, live=True) is (not failure)
    report = json.loads(output.read_text())
    assert len(requests) == len(report["calls"]) == (3 if failure else 144)
    assert report["source_unchanged"]
    assert "SECRET_SENTINEL" not in output.read_text()
    assert "SECRET_SENTINEL" not in output.with_suffix(".jsonl").read_text()
    assert {r["temperature"] for r in requests} == {0}
    assert {r["max_tokens"] for r in requests} == {4096}
    if not failure:
        assert len({c["request_sha256"] for c in report["calls"]}) == 36
        summary = report["analysis"]["summaries"]["on:round_all"]
        assert summary["wrong_allowed"] == summary["wrong_plans"] > 0
        assert summary["unresolved_allowed"] == summary["unresolved_pairs"] > 0
    before = output.read_bytes()
    with pytest.raises(ValueError, match="fresh_outputs"):
        pilot.run(output, live=True)
    assert output.read_bytes() == before


def test_dry_run_is_oracle_readiness_not_fabricated_model_performance(tmp_path):
    output = tmp_path / "dry.json"
    assert pilot.run(output)
    report = json.loads(output.read_text())
    assert report["calls"] == [] and report["analysis"] is None
    assert len(report["oracle"]) == 99
    assert core({k: [] for k in pilot.FIELDS}) == {k: [] for k in pilot.FIELDS}
