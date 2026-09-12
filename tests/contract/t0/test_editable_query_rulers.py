"""Stage-0 specification vectors, not a renderer/editor/confirmation runtime.

Hand-authored card facts have independent hand values and two-engine checks.
The transition predicates below are test-only rulers; never import them into
a future editor. Green specification vectors do not prove UI fidelity/usefulness.
"""

import hashlib
import json
from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import ValidationError
from t0_helpers import ROOT

from evals.concept_pilot import digest
from evals.cross_language import fixture_data
from evals.cross_language_study import replay
from evals.metric_selection_study import AS_OF, context
from evals.metric_wire_selection import bind_selection, catalog
from evals.reference_eval import evaluate
from evals.stability import plan_core
from evals.synthetic import DuckInstance
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.overlay import Segment
from grepbit.domain.plan import PlanProposal, QueryPlan

RULER = json.loads((ROOT / "tests/fixtures/editable_query_rulers.json").read_text())
FIXTURE_BYTES = (ROOT / RULER["fixture_file"]).read_bytes()
FIXTURE = json.loads(FIXTURE_BYTES)
PLANS = FIXTURE["plans"] | RULER["extra_plans"]
CARDS = {c["id"]: c for c in RULER["cards"]}
INSTANCES = list(FIXTURE["instances"])
SEGMENT = Segment.model_validate(RULER["segment"])


def case_context(card):
    source = "pos" if card["base_table"] == "pos_sale" else "service"
    schema, overlay, *_ = context(source, "P0", FIXTURE)
    segments = [SEGMENT] if card["segment_mode"] != "none" else []
    overlay = overlay.model_copy(update={"segments": segments})
    kwargs = {
        "exclude_segments": segments if card["segment_mode"] == "default" else [],
        "named_segments": segments if card["segment_mode"] == "named" else [],
    }
    return schema, overlay, kwargs


def original_plan(card):
    raw = deepcopy(PLANS[card["plan_id"]])
    raw["measures"][0]["alias"] = card["output_label"]
    return QueryPlan.model_validate(raw)


def card_fact_plan(card):
    """Literal test-fixture projection, NOT an implementation of a renderer.

    Expand already hand-written facts into a raw plan for value checking. It
    does not discover metric/segment meaning, bind edits or implement an API.
    """

    def predicate(item):
        table, column = item["column"].split(".")
        return {
            "column": {"table": table, "column": column},
            "op": item["op"],
            "values": item["values"],
        }

    operands = {}
    for role, facts in card["slots"].items():
        operand = {
            "aggregate": facts["aggregate"],
            "filters": [predicate(p) for p in facts["predicates"]],
        }
        if facts["column"]:
            table, column = facts["column"].split(".")
            operand["column"] = {"table": table, "column": column}
        operands[role] = operand
    measure = operands["value"] if "value" in operands else {"ratio": operands}
    measure["alias"] = card["output_label"]
    return QueryPlan.model_validate(
        {
            "base_table": card["base_table"],
            "measures": [measure],
            "filters": [predicate(p) for p in card["common_predicates"]],
        }
    )


def value(plan, card, instance, engine, *, expanded=False):
    schema, overlay, kwargs = case_context(card)
    # Fully expanded fact plans must not apply metric/segment defaults twice.
    if expanded:
        overlay, kwargs = None, {}
    compiled = PlanCompiler(schema, overlay=overlay).compile(
        plan, as_of=AS_OF, **kwargs
    )
    data = fixture_data(schema, FIXTURE["instances"][instance])
    if engine == "reference":
        rows = evaluate(
            plan, schema, overlay, datetime.fromisoformat(AS_OF), data, **kwargs
        )
        rows = [tuple(r[c] for c in compiled.output_columns) for r in rows]
    else:
        database = DuckInstance(schema, data)
        try:
            _, rows = database.execute(compiled.compiled)
        finally:
            database.con.close()
    assert len(rows) == len(rows[0]) == 1
    return rows[0][0]


def assert_value(actual, expected):
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected)


def test_fixture_is_frozen_fictional_and_cards_are_closed_specification_vectors():
    assert hashlib.sha256(FIXTURE_BYTES).hexdigest() == RULER["fixture_sha256"]
    assert len(CARDS) == len(RULER["cards"]) == 19
    assert INSTANCES == ["coincidental", "asymmetric", "null_zero"]
    assert not FIXTURE["schema"]["foreign_keys"]
    fields = {
        "id",
        "plan_id",
        "base_table",
        "segment_mode",
        "output_label",
        "time",
        "grouping",
        "common_predicates",
        "applied_segments",
        "verification",
        "ratio_zero_denominator",
        "slots",
        "expected",
    }
    for card in CARDS.values():
        assert set(card) == fields
        assert len(card["expected"]) == 3
        assert card["time"] == "unrestricted" and card["grouping"] == "none"
        assert set(card["slots"]) in ({"value"}, {"numerator", "denominator"})
        assert card["ratio_zero_denominator"] == (
            "null" if "numerator" in card["slots"] else None
        )
        for operand in card["slots"].values():
            assert set(operand) == {
                "aggregate",
                "column",
                "unit_label",
                "null_policy",
                "empty_result",
                "definition",
                "predicates",
            }
            assert operand["null_policy"] == (
                "ignore_null_values" if operand["column"] else "count_every_row"
            )
            assert operand["empty_result"] == (
                None if operand["aggregate"] == "sum" else 0
            )
            assert operand["unit_label"]


@pytest.mark.parametrize("card", RULER["cards"], ids=lambda c: c["id"])
@pytest.mark.parametrize("instance", INSTANCES)
@pytest.mark.parametrize("engine", ["sql", "reference"])
def test_original_plan_agrees_with_hand_card_values(card, instance, engine):
    # Three reference/named_ratio failures are meaningful current-contract
    # violations, not a missing future renderer import or a setup failure.
    assert_value(
        value(original_plan(card), card, instance, engine),
        card["expected"][INSTANCES.index(instance)],
    )


@pytest.mark.parametrize("card", RULER["cards"], ids=lambda c: c["id"])
@pytest.mark.parametrize("instance", INSTANCES)
def test_independent_expanded_card_facts_have_the_hand_values(card, instance):
    plan = card_fact_plan(card)
    for engine in ("sql", "reference"):
        assert_value(
            value(plan, card, instance, engine, expanded=True),
            card["expected"][INSTANCES.index(instance)],
        )


@pytest.mark.parametrize("card", RULER["cards"], ids=lambda c: c["id"])
def test_labels_verification_and_actual_segment_application_are_not_inferred(card):
    schema, overlay, kwargs = case_context(card)
    compiled = PlanCompiler(schema, overlay=overlay).compile(
        original_plan(card), as_of=AS_OF, **kwargs
    )
    assert compiled.output_columns == (card["output_label"],)
    assert compiled.verification == card["verification"]
    assert list(compiled.applied_segments) == card["applied_segments"]
    for slot in card["slots"].values():
        if slot["definition"] != "raw":
            metric = overlay.metric(slot["definition"].removeprefix("overlay.metrics."))
            assert metric is not None
            assert metric.aggregate.value == slot["aggregate"]
            assert (metric.column.id if metric.column else None) == slot["column"]
            assert {
                p["column"] for p in slot["predicates"] if p["source"] == "metric"
            } == {p.column.id for p in metric.filters}


@pytest.mark.parametrize("pair", RULER["witnesses"], ids=lambda p: p["left"])
def test_known_different_meanings_have_hand_and_compiled_witnesses(pair):
    left, right = (CARDS[pair[s]] for s in ("left", "right"))
    index = INSTANCES.index(pair["instance"])
    assert left["expected"][index] != right["expected"][index]
    assert value(original_plan(left), left, pair["instance"], "sql") != value(
        original_plan(right), right, pair["instance"], "sql"
    )


@pytest.mark.parametrize("omission", ["plan", "metric", "operand"])
def test_omitting_any_scope_from_the_card_has_a_value_counterexample(omission):
    card = deepcopy(CARDS["scoped_ratio"])
    if omission == "plan":
        card["common_predicates"] = []
    else:
        facts = card["slots"]["numerator"]
        facts["predicates"] = [
            p for p in facts["predicates"] if p["source"] != omission
        ]
    assert any(
        value(card_fact_plan(card), card, name, "sql", expanded=True)
        != pytest.approx(card["expected"][i])
        for i, name in enumerate(INSTANCES)
    )


def test_current_interpretation_sentence_alone_is_not_a_complete_card():
    card = CARDS["returns_metric"]
    schema, overlay, kwargs = case_context(card)
    compiled = PlanCompiler(schema, overlay=overlay).compile(
        original_plan(card), as_of=AS_OF, **kwargs
    )
    assert "metric return_count" in compiled.interpretation
    assert "origin_transaction_no" not in compiled.interpretation
    assert "origin_transaction_no" in " ".join(compiled.lineage.filters)
    assert compiled.verification == "verified"
    # The complete existing response has lineage; this is not an allegation
    # that every served surface omits the filter, or a request to change it.
    assert CARDS["returns_metric"]["expected"] != CARDS["all_rows"]["expected"]


def test_bounded_catalog_is_not_an_implicit_normalizer_or_provenance_certificate():
    card = CARDS["returns_metric"]
    schema, overlay, _ = case_context(card)
    offered = catalog(schema, overlay)
    chosen = next(c for c in offered if c["operand"].get("metric") == "return_count")
    assert chosen["population"] == [
        {"column": "pos_sale.origin_transaction_no", "op": "not_null"}
    ]
    modified = overlay.model_copy(deep=True)
    modified.metric("return_count").description += " Updated reviewed description."
    updated = catalog(schema, modified)
    assert {c["id"] for c in offered} == {c["id"] for c in updated}
    assert digest(offered) != digest(updated)
    assert digest(overlay.model_dump(mode="json")) != digest(
        modified.model_dump(mode="json")
    )
    # Stable semantic candidate IDs alone cannot bind review provenance/context.


def test_whole_operand_replacement_preserves_the_other_operand_and_common_filters():
    before = original_plan(CARDS["scoped_ratio"]).model_dump(mode="json")
    schema, overlay, _ = case_context(CARDS["scoped_ratio"])
    offered = catalog(schema, overlay)
    selected = next(c for c in offered if c["operand"].get("metric") == "return_amount")
    after = deepcopy(before)
    after["measures"][0]["ratio"]["numerator"] = deepcopy(selected["operand"])
    validated = QueryPlan.model_validate(after)
    assert validated.measures[0].ratio.numerator.metric == "return_amount"
    assert after["filters"] == before["filters"]
    assert (
        after["measures"][0]["ratio"]["denominator"]
        == before["measures"][0]["ratio"]["denominator"]
    )
    assert after["measures"][0]["alias"] == before["measures"][0]["alias"]
    # The old operand's extra filter is explicitly replaced with the WHOLE
    # candidate, not silently attached to a new reviewed definition.
    assert not validated.measures[0].ratio.numerator.filters
    for instance, expected in zip(INSTANCES, [12.5, 12, 2.5], strict=True):
        for engine in ("sql", "reference"):
            assert_value(
                value(validated, CARDS["scoped_ratio"], instance, engine), expected
            )


def test_identical_plan_and_interpretation_do_not_bind_default_segment_meaning():
    plain, excluded = CARDS["all_rows"], CARDS["default_exclusion"]
    assert original_plan(plain) == original_plan(excluded)
    outputs = []
    for card in (plain, excluded):
        schema, overlay, kwargs = case_context(card)
        compiled = PlanCompiler(schema, overlay=overlay).compile(
            original_plan(card), as_of=AS_OF, **kwargs
        )
        outputs.append(compiled.interpretation)
    assert outputs[0] == outputs[1]
    assert plain["expected"] != excluded["expected"]
    assert plain["slots"] != excluded["slots"]
    assert plain["applied_segments"] != excluded["applied_segments"]


def test_reverting_a_calculation_cannot_resurrect_an_old_confirmation():
    facts = digest(CARDS["all_rows"])
    old_review = {"effective_facts_sha256": facts, "review_revision": 0}
    changed = {
        "effective_facts_sha256": digest(CARDS["returns_metric"]),
        "review_revision": 1,
    }
    reverted = {"effective_facts_sha256": facts, "review_revision": 2}
    assert old_review["effective_facts_sha256"] == reverted["effective_facts_sha256"]
    assert len({digest(v) for v in (old_review, changed, reverted)}) == 3


@pytest.mark.parametrize(
    "card_id", ["all_rows", "nullable_count", "distinct_member", "returns_amount"]
)
@pytest.mark.parametrize("empty", [False, True], ids=["null_values", "empty_rows"])
@pytest.mark.parametrize("engine", ["sql", "reference"])
def test_empty_and_null_values_have_explicit_count_versus_sum_outcomes(
    card_id, empty, engine
):
    card = CARDS[card_id]
    schema, _, _ = case_context(card)
    plan = card_fact_plan(card)
    # Same frozen schema, one new all-NULL-value control or zero rows. PK is
    # still non-NULL/unique; these are hand-created synthetic data, not samples.
    data = {
        "pos_sale": []
        if empty
        else [
            {
                "transaction_no": 1,
                "total_amount": None,
                "origin_transaction_no": "fake_origin",
                "member_id": None,
            }
        ]
    }
    compiled = PlanCompiler(schema).compile(plan, as_of=AS_OF)
    if engine == "reference":
        rows = evaluate(plan, schema, None, datetime.fromisoformat(AS_OF), data)
        result = rows[0][card["output_label"]]
    else:
        database = DuckInstance(schema, data)
        try:
            _, rows = database.execute(compiled.compiled)
            result = rows[0][0]
        finally:
            database.con.close()
    expected = (
        None
        if card_id == "returns_amount"
        else int(card_id == "all_rows" and not empty)
    )
    assert_value(result, expected)


@pytest.mark.parametrize("shape", ["share", "growth", "latest"])
def test_additional_valid_runtime_shapes_need_their_own_cards(shape):
    raw = original_plan(CARDS["all_rows"]).model_dump(mode="json")
    if shape == "share":
        raw["measures"][0]["share_of_total"] = True
        raw["measures"][0]["filters"] = [RULER["segment"]["filter"]]
    elif shape == "growth":
        raw["time"] = {"grain": "month"}
        raw["growth"] = [{"measure": "結果"}]
    else:
        raw["measures"] = []
        ref = {"table": "pos_sale", "column": "transaction_no"}
        raw["latest"] = {
            "order_by": [{"column": ref, "direction": "desc"}],
            "take": [ref],
        }
    parsed = QueryPlan.model_validate(raw)
    assert parsed != original_plan(CARDS["all_rows"])
    if shape == "share":
        assert parsed.measures[0].share_of_total
    else:
        assert getattr(parsed, shape)


def test_unknown_and_cross_table_candidates_remain_rejected():
    sources = [context(s, "P0", FIXTURE)[:2] for s in ("pos", "service")]
    catalogs = [catalog(s, o) for s, o in sources]
    payload = {
        "decision": "pick",
        "slots": {"value": "missing"},
        "output_label": None,
        "reason": None,
    }
    with pytest.raises(ValueError, match="candidate_not_offered"):
        bind_selection(payload, catalogs[0], "synthetic")
    payload["slots"] = {
        "numerator": catalogs[0][0]["id"],
        "denominator": catalogs[1][0]["id"],
    }
    with pytest.raises(ValueError, match="candidate_cross_table"):
        bind_selection(payload, catalogs[0] + catalogs[1], "synthetic")


@pytest.mark.parametrize("row", RULER["edit_vectors"], ids=lambda r: r["id"])
def test_edit_transition_vectors_preserve_noop_and_invalidate_changed_review(row):
    before, after = (
        original_plan(CARDS[row["before"]]),
        original_plan(CARDS[row["after"]]),
    )
    changed = before.model_dump(mode="json") != after.model_dump(mode="json")
    assert changed is row["changed"]
    assert row["preserve_confirmation"] is (not changed)
    assert row["old_result"] == ("stale" if changed else "current")
    if row["kind"] == "label":
        assert plan_core(before.model_dump()) == plan_core(after.model_dump())
        assert digest(before.model_dump(mode="json")) != digest(
            after.model_dump(mode="json")
        )
    if row["kind"] == "invalid":
        invalid = deepcopy(before.model_dump(mode="json"))
        invalid["measures"][0]["aggregate"] = "unsupported_operation"
        with pytest.raises(ValidationError):
            QueryPlan.model_validate(invalid)
        assert original_plan(CARDS[row["before"]]) == before


@pytest.mark.parametrize("field", RULER["required_identity_fields"])
def test_each_declared_binding_dimension_invalidates_the_old_identity(field):
    # Static identity contract vectors, not persistent tokens or an authorizer.
    identity = {name: "fixture-v1" for name in RULER["required_identity_fields"]}
    changed = {**identity, field: "fixture-v2"}
    assert digest(changed) != digest(identity)
    absent = {k: v for k, v in identity.items() if k != field}
    assert set(absent) != set(RULER["required_identity_fields"])


@pytest.mark.parametrize("row", RULER["confirmation_vectors"], ids=lambda r: r["id"])
def test_confirmation_truth_table_never_infers_a_human_action_or_overrides_a_gate(row):
    acceptable = (
        row["event"] == "confirm"
        and row["same_identity"]
        and row["actor"] == "human"
        and row["gate"] == "answered"
    )
    assert acceptable is row["accepted"]
    # Even an accepted event means "review action recorded", not correct intent.
    assert "intent_certification" in RULER["nonclaims"]


@pytest.mark.parametrize(
    "card_id,question,gold_id,status,match",
    [
        ("returns_metric", "回傳交易筆數。", "all_count", "answered", False),
        (
            "ticket_entities",
            "回傳所有工時紀錄的總筆數，同一工單有多筆紀錄就各算一筆。",
            "log_count",
            "answered",
            False,
        ),
        (
            "label_not_filter",
            "統計所有交易筆數，欄名用「退貨統計」。",
            "all_count",
            "clarify",
            None,
        ),
    ],
)
def test_actual_ask_wrong_valid_and_refusal_controls_remain_unchanged(
    card_id, question, gold_id, status, match
):
    card = CARDS[card_id]
    schema, overlay, _ = case_context(card)
    proposal = PlanProposal(decision="plan", plan=original_plan(card))
    result = replay(
        proposal,
        question,
        schema,
        overlay,
        load_shape_pack(),
        FIXTURE["instances"]["coincidental"],
        QueryPlan.model_validate(PLANS[gold_id]),
    )
    assert result["model_calls"] == 0
    assert result["status"] == status
    assert result["rows_match_gold"] is match
    assert result["sql_executions"] == (1 if status == "answered" else 0)


@pytest.mark.parametrize(
    "field,change",
    [
        ("dimensions", [{"table": "pos_sale", "column": "member_id"}]),
        (
            "time",
            {
                "column": {"table": "pos_sale", "column": "total_amount"},
                "grain": "month",
            },
        ),
        ("order", [{"field": "結果", "direction": "desc"}]),
        ("limit", 1),
        ("having", [{"field": "結果", "op": "gt", "value": 1}]),
        ("without", {"table": "work_logs"}),
    ],
)
def test_unsupported_fields_cannot_be_dropped_to_make_a_card(field, change):
    original = original_plan(CARDS["all_rows"]).model_dump(mode="json")
    unsupported = QueryPlan.model_validate({**original, field: change})
    assert unsupported.model_dump(mode="json")[field] != original[field]
    # This specification deliberately has no renderer accepting these fields.
    # A future renderer must return outside_fragment, never the original card.
    assert digest(unsupported.model_dump(mode="json")) != digest(original)


def test_ratio_wrapper_filters_still_refuse_before_any_card_or_edit():
    raw = original_plan(CARDS["count_ratio"]).model_dump(mode="json")
    raw["measures"][0]["filters"] = [
        {"column": {"table": "pos_sale", "column": "member_id"}, "op": "not_null"}
    ]
    with pytest.raises(ValidationError, match="ratio_wrapper_filters_unsupported"):
        QueryPlan.model_validate(raw)


@pytest.mark.parametrize("null_role", ["numerator", "denominator"])
@pytest.mark.parametrize("instance", INSTANCES)
@pytest.mark.parametrize("engine", ["sql", "reference"])
def test_null_ratio_operand_remains_null_not_zero(null_role, instance, engine):
    # A SUM restricted to NULL values is NULL even if the base has rows.
    # This checks the composition, not merely SUM-empty and divide-by-zero
    # separately; the other operand counts all base rows and is nonzero.
    column = {"table": "pos_sale", "column": "total_amount"}
    null_sum = {
        "aggregate": "sum",
        "column": column,
        "filters": [{"column": column, "op": "is_null"}],
    }
    ratio = {"numerator": {"aggregate": "count"}, "denominator": {"aggregate": "count"}}
    ratio[null_role] = null_sum
    plan = QueryPlan.model_validate(
        {
            "base_table": "pos_sale",
            "measures": [{"ratio": ratio, "alias": "結果"}],
        }
    )
    assert value(plan, CARDS["count_ratio"], instance, engine) is None
