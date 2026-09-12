"""Test-only presentation and pair-identity rulers, not inference adapters."""

import hashlib
import json
from copy import deepcopy
from typing import Literal

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from t0_helpers import ROOT

from evals import metric_wire_study as study
from evals.metric_factor_selection import shown_interpretation
from evals.metric_selection import authored_annotation, check_plan
from evals.metric_wire_selection import Selection, bind_selection, diagnostics
from grepbit.domain.plan import QueryPlan

RULERS = json.loads((ROOT / "tests/fixtures/metric_factor_rulers.json").read_text())
GOLD, FIXTURE, CONTEXTS, CATALOGS, COVERAGE = study.prepare()


class FactorPair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    basis_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)


class FactoredSelection(BaseModel):
    """Proposed pair envelope with the old decision/role/decline semantics."""

    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["pick", "clarify", "no_candidate"]
    slots: dict[Literal["value", "numerator", "denominator"], FactorPair]
    output_label: str | None
    reason: Literal["ambiguous", "missing_definition", "outside_catalog"] | None

    @model_validator(mode="after")
    def original_envelope_rules(self):
        Selection.model_validate(
            {
                **self.model_dump(),
                "slots": {
                    role: json.dumps(pair.model_dump(), sort_keys=True)
                    for role, pair in self.slots.items()
                },
            }
        )
        return self


def identity(prefix, definition):
    """Test specification only; IDs depend on definitions, not display order."""
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(encoded.encode()).hexdigest()[:16]


def factor_spec(candidates):
    """A relational projection/join oracle over the existing candidate list."""
    bases, populations, pairs = {}, {}, {}
    for candidate in candidates:
        basis = {k: candidate[k] for k in ("base_table", "operation", "column")}
        population = {
            "base_table": candidate["base_table"],
            "predicates": candidate["population"],
        }
        bid, pid = identity("b_", basis), identity("p_", population)
        assert bid not in bases or bases[bid] == basis, "basis_id_collision"
        assert pid not in populations or populations[pid] == population
        assert (bid, pid) not in pairs, "duplicate_pair_identity"
        bases[bid], populations[pid] = basis, population
        pairs[bid, pid] = deepcopy(candidate)
    return bases, populations, pairs


def original_selection_spec(payload, pairs):
    """Expected pair lookup only; actual materialization uses the old binder."""
    parsed = FactoredSelection.model_validate(payload)
    slots = {}
    for role, pair in parsed.slots.items():
        key = (pair.basis_id, pair.population_id)
        if key not in pairs:
            raise ValueError("pair_not_offered")
        slots[role] = pairs[key]["id"]
    return {**parsed.model_dump(), "slots": slots}


def wire_payload(case, language):
    payload = authored_annotation(GOLD, case, language).model_dump()
    payload["spans"] = [
        {**s, "occurrence": s.get("occurrence", 0)} for s in case["spans"][language]
    ]
    return payload


def counterexample(name):
    case = next(c for c in GOLD["cases"] if c["profile"] == "returns_count")
    payload = wire_payload(case, "en")
    # Use a valid exact occurrence so location is not the cause of rejection.
    payload["spans"] = [
        {
            "text": case["questions"]["en"],
            "occurrence": 0,
            "role": "output_action",
            "scope": "output",
            "concept": None,
        }
    ]
    if name == "span_scope":
        payload["spans"][0]["scope"] = "population"
    elif name == "predicate_concept":
        payload["spans"][0].update(role="business_predicate", scope="population")
    elif name == "nonpredicate_concept":
        payload["spans"][0]["concept"] = "returns"
    elif name == "basis_column":
        payload["basis"][0]["aggregate"] = "sum"
    elif name == "state_uncertainty":
        payload["unresolved"] = ["measure_basis"]
    elif name == "empty_clear_basis":
        payload["basis"] = []
    elif name == "missing_binding_gap":
        payload.update(state="missing_definition", unresolved=["measure_basis"])
    elif name == "duplicate_basis":
        payload["basis"] *= 2
    elif name == "partial_ratio":
        payload["basis"][0]["role"] = "numerator"
    elif name == "requirement_scope":
        payload["requirements"][0]["role"] = "denominator"
    elif name == "missing_population":
        payload["populations"] = {}
    elif name == "unresolved_population":
        payload["populations"]["population"] = "unresolved"
    elif name == "population_mismatch":
        payload["populations"]["population"] = "all_rows"
    else:
        raise AssertionError("unknown_counterexample")
    return case, payload


@pytest.mark.parametrize(
    "vector", RULERS["shown_schema_counterexamples"], ids=lambda v: v["id"]
)
def test_existing_runtime_rejects_each_presentation_counterexample(vector):
    case, payload = counterexample(vector["id"])
    with pytest.raises(ValueError) as captured:
        study.parse_record(
            payload,
            {"arm": "B", "source": "pos"},
            case["questions"]["en"],
            CONTEXTS,
            CATALOGS,
            {},
        )
    assert vector["runtime_reason"] in {d["code"] for d in diagnostics(captured.value)}


@pytest.mark.parametrize(
    "vector", RULERS["shown_schema_counterexamples"], ids=lambda v: v["id"]
)
def test_shown_schema_must_expose_existing_conditional_constraint(vector):
    # Red at checkpoint. Approved follow-up now points at W; B stays unchanged.
    _, payload = counterexample(vector["id"])
    schema, _, _, _, concepts = CONTEXTS["pos"]
    validator = Draft202012Validator(shown_interpretation(schema, concepts))
    assert not validator.is_valid(payload), "shown_schema_accepts_runtime_invalid"


@pytest.mark.parametrize("case", GOLD["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_positive_wire_controls_keep_final_semantics(case, language):
    source = "service" if case["id"] in study.prior.SERVICE_CASES else "pos"
    question, payload = case["questions"][language], wire_payload(case, language)
    request = study.messages(question, source, "B", CONTEXTS, CATALOGS)
    Draft202012Validator(json.loads(request[1]["content"])).validate(payload)
    parsed = study.parse_record(
        payload, {"arm": "B", "source": source}, question, CONTEXTS, CATALOGS, {}
    )
    assert parsed == authored_annotation(GOLD, case, language)


@pytest.mark.parametrize("source", ["pos", "service"])
def test_factor_relation_is_bijective_preserves_provenance_and_order(source):
    original = deepcopy(CATALOGS[source])
    bases, populations, pairs = factor_spec(original)
    assert len(pairs) == len(original)
    assert sorted(pairs.values(), key=lambda c: c["id"]) == original
    assert (bases, populations, pairs) == factor_spec(list(reversed(original)))
    for (bid, pid), candidate in pairs.items():
        payload = {
            "decision": "pick",
            "slots": {"value": {"basis_id": bid, "population_id": pid}},
            "output_label": None,
            "reason": None,
        }
        rebound = original_selection_spec(payload, pairs)
        expected = {**rebound, "slots": {"value": candidate["id"]}}
        assert bind_selection(rebound, original, "question") == bind_selection(
            expected, original, "question"
        )
        assert pairs[bid, pid]["reviewed_metrics"] == candidate["reviewed_metrics"]
    assert CATALOGS[source] == original


@pytest.mark.parametrize(
    "pair",
    [
        {"basis_id": "b_a"},
        {"basis_id": "b_a", "population_id": None},
        {"basis_id": "b_a", "population_id": ""},
        {"basis_id": "b_a", "population_id": True},
        {"basis_id": "b_a", "population_id": "p_all", "filter": []},
    ],
)
def test_missing_population_is_never_an_all_rows_default(pair):
    with pytest.raises(ValidationError):
        FactorPair.model_validate(pair)


def test_valid_individual_ids_do_not_authorize_an_unoffered_pair():
    # Sparse subset is a specification witness, not a new live catalog.
    candidates = [
        c
        for c in CATALOGS["service"]
        if (c["operation"] == "count" and not c["population"])
        or (c["operation"] == "count_distinct" and c["population"])
    ]
    bases, populations, pairs = factor_spec(candidates)
    missing = next((b, p) for b in bases for p in populations if (b, p) not in pairs)
    payload = {
        "decision": "pick",
        "slots": {"value": {"basis_id": missing[0], "population_id": missing[1]}},
        "output_label": None,
        "reason": None,
    }
    FactoredSelection.model_validate(payload)
    with pytest.raises(ValueError, match="pair_not_offered"):
        original_selection_spec(payload, pairs)


def test_ratio_can_share_basis_but_not_identical_population_pair():
    _, _, pairs = factor_spec(CATALOGS["pos"])
    n, d = next((a, b) for a in pairs for b in pairs if a[0] == b[0] and a != b)
    payload = {
        "decision": "pick",
        "slots": {
            "numerator": {"basis_id": n[0], "population_id": n[1]},
            "denominator": {"basis_id": d[0], "population_id": d[1]},
        },
        "output_label": None,
        "reason": None,
    }
    rebound = original_selection_spec(payload, pairs)
    assert bind_selection(rebound, CATALOGS["pos"], "question").proposal.plan
    payload["slots"]["denominator"] = payload["slots"]["numerator"]
    with pytest.raises(ValidationError, match="identical_ratio_candidate"):
        FactoredSelection.model_validate(payload)


@pytest.mark.parametrize(
    "decision,reason",
    [
        ("clarify", "ambiguous"),
        ("clarify", "missing_definition"),
        ("no_candidate", "outside_catalog"),
    ],
)
def test_factor_refusals_preserve_existing_distinctions(decision, reason):
    payload = {
        "decision": decision,
        "slots": {},
        "reason": reason,
        "output_label": None,
    }
    assert original_selection_spec(payload, {}) == payload


def test_old_single_id_contract_does_not_silently_accept_factor_envelope():
    payload = {
        "decision": "pick",
        "slots": {"value": {"basis_id": "b_x", "population_id": "p_all"}},
        "reason": None,
        "output_label": None,
    }
    FactoredSelection.model_validate(payload)
    with pytest.raises(ValidationError):
        Selection.model_validate(payload)


def test_duplicate_pair_identity_is_rejected_not_last_write_wins():
    card = CATALOGS["pos"][0]
    with pytest.raises(AssertionError, match="duplicate_pair_identity"):
        factor_spec([card, {**card, "id": "another_id"}])


def test_factor_ids_from_another_source_cannot_bind_in_current_catalog():
    _, _, pos = factor_spec(CATALOGS["pos"])
    _, _, service = factor_spec(CATALOGS["service"])
    b, p = next(iter(service))
    payload = {
        "decision": "pick",
        "slots": {"value": {"basis_id": b, "population_id": p}},
        "reason": None,
        "output_label": None,
    }
    with pytest.raises(ValueError, match="pair_not_offered"):
        original_selection_spec(payload, pos)


def test_pair_membership_does_not_authorize_cross_table_ratio():
    cards = CATALOGS["pos"] + CATALOGS["service"]
    _, _, pairs = factor_spec(cards)
    left = next(k for k, c in pairs.items() if c["base_table"] == "pos_sale")
    right = next(k for k, c in pairs.items() if c["base_table"] == "work_logs")
    payload = {
        "decision": "pick",
        "slots": {
            "numerator": {"basis_id": left[0], "population_id": left[1]},
            "denominator": {"basis_id": right[0], "population_id": right[1]},
        },
        "reason": None,
        "output_label": None,
    }
    with pytest.raises(ValueError, match="candidate_cross_table"):
        bind_selection(original_selection_spec(payload, pairs), cards, "question")


def test_explicit_all_rows_is_not_filtered_metric_with_filters_removed():
    cards = CATALOGS["pos"]
    _, _, pairs = factor_spec(cards)
    returns = next(
        k for k, c in pairs.items() if c["operand"].get("metric") == "return_count"
    )
    all_rows = next(
        k for k, c in pairs.items() if k[0] == returns[0] and not c["population"]
    )
    payload = {
        "decision": "pick",
        "slots": {"value": {"basis_id": all_rows[0], "population_id": all_rows[1]}},
        "reason": None,
        "output_label": "returns statistics",
    }
    result = bind_selection(
        original_selection_spec(payload, pairs),
        cards,
        'Name the output "returns statistics".',
    )
    measure = result.proposal.plan.measures[0]
    assert measure.aggregate == "count" and measure.metric is None
    assert not measure.filters and not result.proposal.plan.filters
    assert measure.alias == "returns statistics"
    assert pairs[returns]["operand"] == {"metric": "return_count"}


def test_well_formed_wrong_return_reading_survives_structural_constraints():
    case = next(c for c in GOLD["cases"] if c["id"] == "output_count_all")
    payload = deepcopy(GOLD["profiles"]["returns_count"])
    payload.update(spans=[], output_label=None)
    question = case["questions"]["zh"]
    wrong_claim = study.parse_record(
        payload,
        {"arm": "B", "source": "pos"},
        question,
        CONTEXTS,
        CATALOGS,
        {},
    )
    schema, overlay, _, _, concepts = CONTEXTS["pos"]
    plan = QueryPlan.model_validate(FIXTURE["plans"]["returns_count_metric"])
    gold = authored_annotation(GOLD, case, "zh")
    assert check_plan(wrong_claim, plan, schema, concepts, overlay)["verdict"] == "pass"
    assert check_plan(gold, plan, schema, concepts, overlay)["verdict"] == "fail"


def test_allocation_keeps_new_budget_and_frozen_gold_separate():
    assert sum(RULERS["allocation"].values()) == RULERS["max_model_attempts"] == 180
    assert all(c["covered"] for c in COVERAGE)
    assert sum(c["split"] == "development" for c in GOLD["cases"]) * 3 == 36
