"""Test-only wire/selection specifications, not new inference adapters.

Existing final annotations stay canonical. No live harness imports these types.
"""

import json
from copy import deepcopy
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from t0_helpers import ROOT

from evals.metric_selection import Interpretation, Span, authored_annotation
from evals.metric_selection_study import load_inputs

RULERS = json.loads((ROOT / "tests/fixtures/metric_wire_rulers.json").read_text())
GOLD, FIXTURE = load_inputs()


class OccurrenceSpan(BaseModel):
    """Proposed input shape only; resolution is not implemented here."""

    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1)
    occurrence: int = Field(ge=0)
    role: Literal[
        "output_action",
        "business_predicate",
        "mention_only",
        "grouping_constraint",
        "unresolved",
    ]
    scope: Literal[
        "output", "output_label", "population", "numerator", "denominator", "grouping"
    ]
    concept: str | None = None

    @model_validator(mode="after")
    def existing_role_rules(self):
        # Only reuse existing role rules on a local placeholder span. This
        # neither locates its occurrence nor proves what the text means.
        Span.model_validate(
            {
                **self.model_dump(exclude={"occurrence"}),
                "start": 0,
                "end": len(self.text),
            }
        )
        return self


class Selection(BaseModel):
    """Proposed research selection envelope; never a QueryPlan certificate."""

    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["pick", "clarify", "no_candidate"]
    slots: dict[Literal["value", "numerator", "denominator"], str]
    output_label: str | None
    reason: Literal["ambiguous", "missing_definition", "outside_catalog"] | None

    @model_validator(mode="after")
    def closed_forms(self):
        if self.decision == "pick":
            if set(self.slots) not in ({"value"}, {"numerator", "denominator"}):
                raise ValueError("incomplete_selection")
            if self.reason is not None:
                raise ValueError("pick_with_refusal_reason")
            if any(not identifier for identifier in self.slots.values()):
                raise ValueError("empty_candidate_id")
            if len(self.slots.values()) != len(set(self.slots.values())):
                raise ValueError("identical_ratio_candidate")
        else:
            if self.slots or self.output_label is not None:
                raise ValueError("refusal_with_selection")
            allowed = (
                {"ambiguous", "missing_definition"}
                if self.decision == "clarify"
                else {"outside_catalog"}
            )
            if self.reason not in allowed:
                raise ValueError("wrong_refusal_kind")
        return self


@pytest.mark.parametrize("case", GOLD["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_occurrence_wire_preserves_all_authored_semantic_fields(case, language):
    canonical = authored_annotation(GOLD, case, language).model_dump()
    proposal = deepcopy(canonical)
    proposal["spans"] = [
        OccurrenceSpan.model_validate(
            {**locator, "occurrence": locator.get("occurrence", 0)}
        ).model_dump()
        for locator in case["spans"][language]
    ]
    assert {k: v for k, v in proposal.items() if k != "spans"} == {
        k: v for k, v in canonical.items() if k != "spans"
    }
    for draft, final in zip(proposal["spans"], canonical["spans"], strict=True):
        assert {k: v for k, v in draft.items() if k != "occurrence"} == {
            k: v for k, v in final.items() if k not in {"start", "end"}
        }
    # Current parser must KEEP rejecting the new envelope. A future separate
    # adapter must produce the unchanged canonical annotation before grading.
    if proposal["spans"]:
        with pytest.raises(ValidationError):
            Interpretation.model_validate(proposal)


@pytest.mark.parametrize("case", RULERS["locations"], ids=lambda c: c["id"])
def test_hand_location_vectors_define_exact_unicode_contract(case):
    q, text = case["question"], case["text"]
    # Specification assertion over all possible starts, not a shipped resolver.
    locations = [i for i in range(len(q)) if q.startswith(text, i)]
    if "expected" in case:
        start, end = case["expected"]
        assert q[start:end] == text
        assert locations.index(start) == case["occurrence"]
        assert type(case["occurrence"]) is int
    elif case["error"] == "span_not_in_question":
        assert not locations
    elif case["error"] == "occurrence_out_of_range":
        assert case["occurrence"] >= len(locations)
    else:
        payload = {
            "text": text,
            "occurrence": case["occurrence"],
            "role": "output_action",
            "scope": "output",
        }
        with pytest.raises(ValidationError):
            OccurrenceSpan.model_validate(payload)


@pytest.mark.parametrize(
    "patch",
    [
        {"role": "output_action", "scope": "population"},
        {"role": "output_action", "concept": "returns"},
        {"role": "business_predicate", "scope": "population", "concept": None},
        {"start": 0},
        {"end": 2},
        {"text": ""},
    ],
)
def test_lower_friction_wire_does_not_relax_role_or_shape_rules(patch):
    with pytest.raises(ValidationError):
        OccurrenceSpan.model_validate(
            {
                "text": "Return",
                "occurrence": 0,
                "role": "output_action",
                "scope": "output",
                **patch,
            }
        )


@pytest.mark.parametrize(
    "slots", [{"value": "c_a"}, {"numerator": "c_a", "denominator": "c_b"}]
)
def test_selection_has_one_value_or_two_distinct_operand_ids(slots):
    parsed = Selection.model_validate(
        {"decision": "pick", "slots": slots, "output_label": None, "reason": None}
    )
    assert parsed.slots == slots
    manifest = {"c_a": {"kind": "count_rows"}, "c_b": {"kind": "sum_amount"}}
    reverse = dict(reversed(list(manifest.items())))
    assert [manifest[i] for i in parsed.slots.values()] == [
        reverse[i] for i in parsed.slots.values()
    ]


@pytest.mark.parametrize(
    "patch",
    [
        {"slots": {}},
        {"slots": {"numerator": "c_a"}},
        {"slots": {"numerator": "c_a", "denominator": "c_a"}},
        {"slots": {"value": ""}},
        {"slots": {"value": "c_a", "denominator": "c_b"}},
        {"reason": "ambiguous"},
        {"plan": {"base_table": "pos_sale"}},
    ],
)
def test_selector_cannot_add_plan_fields_or_mix_decisions(patch):
    with pytest.raises(ValidationError):
        Selection.model_validate(
            {
                "decision": "pick",
                "slots": {"value": "c_a"},
                "reason": None,
                "output_label": None,
                **patch,
            }
        )


@pytest.mark.parametrize(
    "decision,reason",
    [
        ("clarify", "ambiguous"),
        ("clarify", "missing_definition"),
        ("no_candidate", "outside_catalog"),
    ],
)
def test_missing_candidate_and_semantic_uncertainty_remain_distinct(decision, reason):
    value = Selection.model_validate(
        {"decision": decision, "reason": reason, "slots": {}, "output_label": None}
    )
    assert value.decision == decision
    with pytest.raises(ValidationError):
        Selection.model_validate({**value.model_dump(), "slots": {"value": "c_a"}})


def test_form_validity_does_not_prove_membership_or_intent():
    selection = Selection.model_validate(
        {
            "decision": "pick",
            "slots": {"value": "unoffered"},
            "reason": None,
            "output_label": None,
        }
    )
    assert selection.slots["value"] not in {"c_a", "c_b"}
    # A future binder must reject this; never infer that a schema-valid choice
    # refers to a catalog member or to the user's intended measure.


@pytest.mark.parametrize(
    "profile", ["returns_count", "return_ratio", "ambiguous_rate", "missing_refund"]
)
def test_existing_cross_field_guards_still_reject_inconsistent_claims(profile):
    case = next(c for c in GOLD["cases"] if c["profile"] == profile)
    payload = authored_annotation(GOLD, case, "en").model_dump()
    if profile == "returns_count":
        payload["populations"]["population"] = "all_rows"
    elif profile == "return_ratio":
        payload["basis"] = payload["basis"][:1]
    else:
        payload["state"] = "clear"
    with pytest.raises(ValidationError) as error:
        Interpretation.model_validate(payload)
    # These known literal reason codes can be allowlisted by the future
    # diagnostic adapter. Do not serialize errors(), input, ctx or provider text.
    codes = {str(e.get("ctx", {}).get("error", "")) for e in error.value.errors()}
    assert codes & {
        "population_constraint_mismatch",
        "incomplete_measure_roles",
        "state_requires_matching_uncertainty",
    }


def test_budget_and_unknown_policy_are_frozen_before_live_work():
    assert sum(RULERS["allocation"].values()) == 180
    assert set(RULERS["allocation"].values()) == {36}
    assert RULERS["comparison"]["challenge_model_calls"] == 0
    assert RULERS["comparison"]["allowed_wrong_or_unresolved_affirmative_passes"] == 0
    assert RULERS["catalog_language"]["max_candidates_per_source"] == 64
