"""Test-only interpretation schema, hand answers and legacy characterizations.

No new semantic grader, language extractor or production gate. The old v2
checker is intentionally not required to certify a larger contract.
"""

from collections import Counter
from copy import deepcopy
from functools import lru_cache
from typing import Literal

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from t0_helpers import AS_OF, ROOT, col

from evals.concept_obligations import check_obligations, validate_obligations
from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.shapes import unmapped_concepts
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

DRAFT = yaml.safe_load(
    (ROOT / "evals/cases/concepts/metric_selection_ruler.yaml").read_text()
)
OVERLAY = load_semantic_overlay(ROOT / "evals/fixtures/pos_overlay.json")
OVERLAY = OVERLAY.model_copy(
    update={
        "metrics": [OVERLAY.metric("return_count"), OVERLAY.metric("return_amount")],
        "segments": [],
        "column_aliases": [],
        "absent_concepts": [],
    }
)


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Span(ClosedModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)
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
    def role_scope(self):
        allowed = {
            "output_action": {"output"},
            "mention_only": {"output_label"},
            "grouping_constraint": {"grouping"},
            "business_predicate": {"population", "numerator", "denominator"},
            "unresolved": {"population", "numerator", "denominator"},
        }
        if self.end <= self.start or self.scope not in allowed[self.role]:
            raise ValueError("invalid_span_scope")
        if self.role == "business_predicate" and self.concept is None:
            raise ValueError("predicate_requires_concept")
        if (
            self.role in {"output_action", "mention_only", "grouping_constraint"}
            and self.concept
        ):
            raise ValueError("nonpredicate_cannot_activate_concept")
        return self


class Basis(ClosedModel):
    role: Literal["value", "numerator", "denominator"]
    aggregate: Literal["count", "sum", "count_distinct"]
    entity: str
    column: str | None

    @model_validator(mode="after")
    def column_required(self):
        if self.aggregate != "count" and self.column is None:
            raise ValueError("basis_column_required")
        return self


class Requirement(ClosedModel):
    concept: str
    polarity: Literal["include", "exclude", "unrestricted"]
    role: Literal["population", "numerator", "denominator"]


class Interpretation(ClosedModel):
    """Proposed research annotation ONLY; not imported by src/ or evals/."""

    state: Literal["clear", "ambiguous", "missing_definition"]
    populations: dict[
        Literal["population", "numerator", "denominator"],
        Literal["all_rows", "constrained", "unresolved"],
    ]
    basis: list[Basis]
    requirements: list[Requirement]
    grouping: Literal["none", "unspecified"]
    unresolved: list[
        Literal["measure_basis", "denominator_population", "business_binding"]
    ]
    spans: list[Span]
    output_label: str | None

    @model_validator(mode="after")
    def structural_contract(self):
        if (self.state == "clear") != (not self.unresolved):
            raise ValueError("state_requires_matching_uncertainty")
        if self.state == "clear" and not self.basis:
            raise ValueError("clear_requires_measure_basis")
        if (
            self.state == "missing_definition"
            and "business_binding" not in self.unresolved
        ):
            raise ValueError("missing_definition_requires_binding_gap")
        for keys in (
            [b.role for b in self.basis],
            [(r.concept, r.role) for r in self.requirements],
            [(s.start, s.end) for s in self.spans],
            self.unresolved,
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate_annotation")
        roles = {b.role for b in self.basis}
        if roles and roles not in ({"value"}, {"numerator", "denominator"}):
            raise ValueError("incomplete_measure_roles")
        if self.state == "clear":
            scopes = {"population"} if roles == {"value"} else roles
            if any(r.role not in scopes for r in self.requirements):
                raise ValueError("requirement_outside_measure_scope")
            if set(self.populations) != scopes:
                raise ValueError("missing_population_scope")
            for scope, policy in self.populations.items():
                restrictions = [
                    r
                    for r in self.requirements
                    if r.role == scope and r.polarity != "unrestricted"
                ]
                if policy == "unresolved":
                    raise ValueError("clear_with_unknown_population")
                if (policy == "constrained") != bool(restrictions):
                    raise ValueError("population_constraint_mismatch")
        return self


def draft_payload(case, language):
    """Turn authored span locators into code-point offsets, not NL inference."""
    question = case["questions"][language]
    spans = []
    for locator in case["spans"][language]:
        entry = dict(locator)
        occurrence = entry.pop("occurrence", 0)
        start = -1
        for _ in range(occurrence + 1):
            start = question.index(entry["text"], start + 1)
        spans.append({**entry, "start": start, "end": start + len(entry["text"])})
    return {
        **deepcopy(DRAFT["profiles"][case["profile"]]),
        "spans": spans,
        "output_label": case.get("labels", {}).get(language),
    }


def validate_draft(payload, question):
    """Shape, identifiers and span integrity only; no semantic grading."""
    parsed = Interpretation.model_validate(payload)
    for span in parsed.spans:
        if span.end > len(question) or question[span.start : span.end] != span.text:
            raise ValueError("span_not_in_question")
        if span.concept is not None and span.concept not in DRAFT["concepts"]:
            raise ValueError("unknown_concept")
    for requirement in parsed.requirements:
        if requirement.concept not in DRAFT["concepts"]:
            raise ValueError("unknown_concept")
        if parsed.state == "clear" and DRAFT["concepts"][requirement.concept] is None:
            raise ValueError("clear_with_missing_binding")
    for basis in parsed.basis:
        table = SCHEMA.table(basis.entity)
        if table is None or (
            basis.column
            and basis.column not in {f"{table.name}.{c.name}" for c in table.columns}
        ):
            raise ValueError("unknown_basis_identifier")
    if parsed.output_label is not None and parsed.output_label not in question:
        raise ValueError("label_not_in_question")
    return parsed


def ref(column, table="pos_sale"):
    return {"table": table, "column": column}


COUNT = {"aggregate": "count"}
SUM = {"aggregate": "sum", "column": ref("total_amount")}
RETURN = {"column": ref("origin_transaction_no"), "op": "not_null"}
MEMBER = {"column": ref("member_id"), "op": "not_null"}


def plan(measure, *, table="pos_sale", **extra):
    return {"base_table": table, "measures": [deepcopy(measure)], **extra}


PLANS = {
    "all_count": plan(COUNT),
    "all_sum": plan(SUM),
    "returns_count_raw": plan(COUNT, filters=[RETURN]),
    "returns_count_metric": plan({"metric": "return_count"}),
    "returns_sum_raw": plan(SUM, filters=[RETURN]),
    "returns_sum_metric": plan({"metric": "return_amount"}),
    "nonreturns_count": plan(COUNT, filters=[{**RETURN, "op": "is_null"}]),
    "member_count": plan(COUNT, filters=[MEMBER]),
    "member_column_count": plan({**COUNT, "column": ref("member_id")}),
    "nonmember_count": plan(COUNT, filters=[{**MEMBER, "op": "is_null"}]),
    "member_distinct": plan(
        {"aggregate": "count_distinct", "column": ref("member_id")}
    ),
    "member_group": plan(COUNT, filters=[MEMBER], dimensions=[ref("member_id")]),
    "return_ratio": plan(
        {"ratio": {"numerator": {**COUNT, "filters": [RETURN]}, "denominator": COUNT}}
    ),
    "return_amount_ratio": plan(
        {"ratio": {"numerator": {**SUM, "filters": [RETURN]}, "denominator": SUM}}
    ),
    "inverse_ratio": plan(
        {"ratio": {"numerator": COUNT, "denominator": {**COUNT, "filters": [RETURN]}}}
    ),
    "log_count": plan(COUNT, table="work_logs"),
    "logged_ticket_count": plan(
        {"aggregate": "count_distinct", "column": ref("ticket_id", "work_logs")},
        table="work_logs",
    ),
    "minutes_sum": plan(
        {"aggregate": "sum", "column": ref("minutes", "work_logs")}, table="work_logs"
    ),
}

SCHEMA = SchemaModel(
    datasource_id="metric_selection_ruler",
    schema_name="public",
    business_timezone="Asia/Taipei",
    tables=[
        SchemaTable(
            name="pos_sale",
            primary_key=["transaction_no"],
            columns=[
                col("transaction_no", ColumnKind.NUMERIC, nullable=False),
                col("total_amount", ColumnKind.NUMERIC),
                col("origin_transaction_no", ColumnKind.TEXT),
                col("member_id", ColumnKind.TEXT),
            ],
        ),
        SchemaTable(
            name="work_logs",
            primary_key=["id"],
            columns=[
                col("id", ColumnKind.NUMERIC, nullable=False),
                col("ticket_id", ColumnKind.NUMERIC, nullable=False),
                col("minutes", ColumnKind.NUMERIC),
            ],
        ),
    ],
)

# Fictional values; no sampled DB content. PKs are unique; repeated member/ticket
# IDs are deliberate and not primary keys. No FK is declared in this projection.
INSTANCES = {
    "coincidental": {
        "pos_sale": [
            (1, 100, None, None),
            (2, 40, "fake_origin", "fake_m1"),
            (3, 10, "fake_origin", "fake_m1"),
            (4, 50, None, "fake_m2"),
        ],
        "work_logs": [(1, 10, 30), (2, 10, 20), (3, 20, 10)],
    },
    "asymmetric": {
        "pos_sale": [
            (1, 90, None, None),
            (2, 40, None, "fake_m1"),
            (3, 30, "fake_origin", None),
            (4, 10, "fake_origin", "fake_m1"),
            (5, 20, "fake_origin", None),
        ],
        "work_logs": [(1, 30, 0), (2, 30, 15)],
    },
    "null_zero": {
        "pos_sale": [
            (1, 0, None, None),
            (2, 5, "fake_origin", "fake_m1"),
            (3, None, None, None),
        ],
        "work_logs": [(1, 40, None), (2, 50, 0), (3, 50, 0)],
    },
}
# Hand answers, never generated from the plan, compiler or reference evaluator.
EXPECTED = {
    "all_count": [4, 5, 3],
    "all_sum": [200, 190, 5],
    "returns_count_raw": [2, 3, 1],
    "returns_count_metric": [2, 3, 1],
    "returns_sum_raw": [50, 60, 5],
    "returns_sum_metric": [50, 60, 5],
    "nonreturns_count": [2, 2, 2],
    "member_count": [3, 2, 1],
    "member_column_count": [3, 2, 1],
    "nonmember_count": [1, 3, 2],
    "member_distinct": [2, 1, 1],
    "return_ratio": [1 / 2, 3 / 5, 1 / 3],
    "return_amount_ratio": [1 / 4, 60 / 190, 1],
    "inverse_ratio": [2, 5 / 3, 3],
    "log_count": [3, 2, 3],
    "logged_ticket_count": [2, 1, 2],
    "minutes_sum": [60, 15, 0],
    "member_group": [
        [("fake_m1", 2), ("fake_m2", 1)],
        [("fake_m1", 2)],
        [("fake_m1", 1)],
    ],
}


def data(instance):
    return {
        table.name: [
            dict(zip([c.name for c in table.columns], row, strict=True))
            for row in INSTANCES[instance][table.name]
        ]
        for table in SCHEMA.tables
    }


@lru_cache
def results(name, instance):
    query = QueryPlan.model_validate(deepcopy(PLANS[name]))
    compiled = PlanCompiler(SCHEMA, overlay=OVERLAY).compile(query, as_of=AS_OF)
    database = DuckInstance(SCHEMA, data(instance))
    try:
        _, sql_rows = database.execute(compiled.compiled)
    finally:
        database.con.close()
    reference = evaluate(query, SCHEMA, OVERLAY, AS_OF, data(instance))
    ref_rows = [tuple(r[c] for c in compiled.output_columns) for r in reference]
    return tuple(sorted(sql_rows, key=repr)), tuple(sorted(ref_rows, key=repr))


@pytest.mark.parametrize("case", DRAFT["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_authored_annotation_integrity_not_model_accuracy(case, language):
    payload = draft_payload(case, language)
    parsed = validate_draft(payload, case["questions"][language])
    assert (parsed.state == "clear") == bool(case["correct"])
    if parsed.state == "clear":
        assert len(case["wrong"]) >= 2
    else:
        assert not case["wrong"] and len(case["unresolved_candidates"]) >= 2
    for name in case["correct"] + case["wrong"] + case.get("unresolved_candidates", []):
        raw = deepcopy(PLANS[name])
        if parsed.output_label:
            raw["measures"][0]["alias"] = parsed.output_label
        compiled = PlanCompiler(SCHEMA, overlay=OVERLAY).compile(
            QueryPlan.model_validate(raw), as_of=AS_OF
        )
        if parsed.output_label:
            assert parsed.output_label in compiled.output_columns


def test_split_families_and_fictional_keys():
    cases = DRAFT["cases"]
    assert len({c["id"] for c in cases}) == len(cases) == 20
    families = {}
    for split, expected in (("development", 6), ("challenge", 4)):
        selected = [c for c in cases if c["split"] == split]
        counts = Counter(c["family"] for c in selected)
        assert len(counts) == expected and set(counts.values()) == {2}
        assert all(
            set(c["questions"]) == set(c["spans"]) == {"zh", "en", "ja"}
            for c in selected
        )
        families[split] = set(counts)
    assert families["development"].isdisjoint(families["challenge"])
    for instance in INSTANCES:
        for rows in data(instance).values():
            keys = [next(iter(row.values())) for row in rows]
            assert None not in keys and len(keys) == len(set(keys))


@pytest.mark.parametrize("name", PLANS)
@pytest.mark.parametrize("instance", INSTANCES)
def test_two_local_evaluations_match_hand_answers(name, instance):
    expected = EXPECTED[name][list(INSTANCES).index(instance)]
    for rows in results(name, instance):
        if name == "member_group":
            assert rows == tuple(sorted(expected, key=repr))
        else:
            assert len(rows) == 1 and len(rows[0]) == 1
            assert float(rows[0][0]) == pytest.approx(expected, rel=1e-9, abs=1e-9)


@pytest.mark.parametrize(
    "case", [c for c in DRAFT["cases"] if c["correct"]], ids=lambda c: c["id"]
)
def test_each_wrong_candidate_has_a_distinguishing_witness(case):
    for wrong in case["wrong"]:
        for right in case["correct"]:
            for engine in (0, 1):
                witnesses = [
                    i
                    for i in INSTANCES
                    if results(right, i)[engine] != results(wrong, i)[engine]
                ]
                assert witnesses, (case["id"], right, wrong, "not_distinguished")
    for right in case["correct"][1:]:
        for instance in INSTANCES:
            assert results(right, instance) == results(case["correct"][0], instance)


def test_coincidental_matches_are_not_equivalence():
    assert results("returns_count_raw", "coincidental") == results(
        "nonreturns_count", "coincidental"
    )
    assert results("returns_count_raw", "asymmetric") != results(
        "nonreturns_count", "asymmetric"
    )
    assert results("all_sum", "null_zero") == results("returns_sum_raw", "null_zero")
    assert results("all_sum", "asymmetric") != results("returns_sum_raw", "asymmetric")


@pytest.mark.parametrize(
    "mutation",
    [
        "span",
        "scope",
        "duplicate",
        "concept",
        "basis",
        "role",
        "unresolved",
        "unbound",
        "extra",
        "bool_offset",
        "population_missing",
        "population_unknown",
        "population_conflict",
    ],
)
def test_annotation_rejects_structural_errors_without_claiming_nl_understanding(
    mutation,
):
    case = DRAFT["cases"][1]
    payload = draft_payload(case, "en")
    if mutation == "span":
        payload["spans"][0]["start"] += 1
    elif mutation == "scope":
        payload["spans"][0]["scope"] = "population"
    elif mutation == "duplicate":
        payload["spans"].append(deepcopy(payload["spans"][0]))
    elif mutation == "concept":
        payload["requirements"][0]["concept"] = "unknown"
    elif mutation == "basis":
        payload["basis"][0]["entity"] = "missing_table"
    elif mutation == "role":
        payload["basis"][0]["role"] = "numerator"
    elif mutation == "unresolved":
        payload["unresolved"] = ["measure_basis"]
    elif mutation == "unbound":
        payload["requirements"][0]["concept"] = "refund"
    elif mutation == "extra":
        payload["certified"] = True
    elif mutation == "population_missing":
        payload.pop("populations")
    elif mutation == "population_unknown":
        payload["populations"]["population"] = "unresolved"
    elif mutation == "population_conflict":
        payload["populations"]["population"] = "all_rows"
    else:
        payload["spans"][0]["start"] = True
    with pytest.raises((ValueError, ValidationError)):
        validate_draft(payload, case["questions"]["en"])


@pytest.mark.parametrize(
    "name, question, expected",
    [
        ("all_count", "Return the transaction count.", ["returns"]),
        (
            "all_count",
            "Count all transactions and label the column returns statistics.",
            ["returns"],
        ),
        ("all_count", "Count returned transactions.", ["returns"]),
        ("nonreturns_count", "Count returned transactions.", []),
    ],
)
def test_current_gate_characterization_not_requested_production_changes(
    name, question, expected
):
    actual = unmapped_concepts(
        question,
        QueryPlan.model_validate(PLANS[name]),
        load_shape_pack(),
        OVERLAY,
        set(),
    )
    assert [concept for concept, _ in actual] == expected


@pytest.mark.parametrize(
    "wrong,right",
    [
        ("returns_sum_metric", "returns_count_metric"),
        ("returns_count_metric", "returns_sum_metric"),
        ("member_distinct", "member_count"),
    ],
)
def test_v2_pass_does_not_certify_measure_basis(wrong, right):
    concept = "member" if wrong == "member_distinct" else "returns"
    question = (
        "Count member transactions."
        if concept == "member"
        else "Count returned transactions."
    )
    if right == "returns_sum_metric":
        question = "Sum the amount of returned transactions."
    payload = {
        "requirements": [
            {
                "concept": concept,
                "polarity": "include",
                "role": "population",
                "span": question,
            }
        ],
        "forbidden_groupings": [],
        "unresolved": [],
    }
    concepts = {k: {"binding": v} for k, v in DRAFT["concepts"].items()}
    obligations = validate_obligations(payload, question, concepts)
    verdict, _ = check_obligations(
        obligations, QueryPlan.model_validate(PLANS[wrong]), concepts, OVERLAY
    )
    assert verdict == "pass"  # Correct for its existing, partial contract.
    assert results(wrong, "asymmetric") != results(right, "asymmetric")


def test_repeated_occurrences_use_distinct_offsets_and_bad_meaning_can_be_well_formed():
    question = "Return all counts; Return all counts."
    case = {
        "profile": "all_count",
        "questions": {"en": question},
        "spans": {
            "en": [
                {
                    "text": "Return",
                    "occurrence": 0,
                    "role": "output_action",
                    "scope": "output",
                },
                {
                    "text": "Return",
                    "occurrence": 1,
                    "role": "output_action",
                    "scope": "output",
                },
            ]
        },
    }
    payload = draft_payload(case, "en")
    parsed = validate_draft(payload, question)
    assert parsed.spans[0].start != parsed.spans[1].start
    payload["spans"][0].update(
        role="business_predicate", scope="population", concept="returns"
    )
    # Schema validation must not be advertised as semantic validation.
    assert validate_draft(payload, question).spans[0].role == "business_predicate"
