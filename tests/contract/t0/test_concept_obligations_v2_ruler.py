"""Executable draft and legacy counterexamples, NOT a v2 checker or live score.

Only the proposed payload schema is implemented here, as a test-only ruler.
Green characterization tests expose the frozen checker's misses. PostgreSQL
is opt-in through an opaque DSN variable name and reads fictional VALUES only.
"""

import json
import os
from copy import deepcopy
from typing import Literal

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from t0_helpers import AS_OF, ROOT, col

from evals.concept_check import Intent, check_bindings
from evals.concept_pilot import context_for, digest, load_inputs
from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

DRAFT = yaml.safe_load(
    (ROOT / "evals/cases/concepts/obligations_v2_ruler.yaml").read_text()
)
PILOT, FIXTURE = load_inputs()
CONTEXT, OVERLAY = context_for("pos", PILOT, FIXTURE)


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    span: str = Field(min_length=1)


class DraftRequirement(EvidenceSpan):
    concept: str
    polarity: Literal["include", "exclude", "unrestricted"]
    role: Literal["population", "numerator", "denominator"]


class DraftForbiddenGrouping(EvidenceSpan):
    concept: str


class DraftUnresolved(EvidenceSpan):
    aspect: Literal["measure_basis", "denominator_population", "qualifier"]


class DraftObligations(BaseModel):
    """Schema assertion only; production/evals must not import this test class."""

    model_config = ConfigDict(extra="forbid")
    requirements: list[DraftRequirement]
    forbidden_groupings: list[DraftForbiddenGrouping]
    unresolved: list[DraftUnresolved]

    @model_validator(mode="after")
    def unique_scopes(self):
        for keys in (
            [(r.concept, r.role) for r in self.requirements],
            [r.concept for r in self.forbidden_groupings],
            [r.aspect for r in self.unresolved],
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate_obligation")
        return self


def proposed_payload(family, question):
    return {
        key: [{**entry, "span": question} for entry in family[key]]
        for key in ("requirements", "forbidden_groupings", "unresolved")
    }


def validate_draft(payload, question):
    result = DraftObligations.model_validate(payload)
    for entry in [*result.requirements, *result.forbidden_groupings]:
        if entry.concept not in DRAFT["concepts"]:
            raise ValueError("unknown_concept")
    for entry in [
        *result.requirements,
        *result.forbidden_groupings,
        *result.unresolved,
    ]:
        if entry.span not in question:
            raise ValueError("span_not_in_question")
    return result


def ref(column):
    return {"table": "pos_sale", "column": column}


MEMBER = {"column": ref("member_id"), "op": "not_null"}
RETURN = {"column": ref("origin_transaction_no"), "op": "not_null"}
COUNT = {"aggregate": "count"}
SUM = {"aggregate": "sum", "column": ref("total_amount")}


def ratio(numerator, denominator):
    return {
        "base_table": "pos_sale",
        "measures": [{"ratio": {"numerator": numerator, "denominator": denominator}}],
    }


PLANS = deepcopy(FIXTURE["plans"])
PLANS.update(
    count_member_column={
        "base_table": "pos_sale",
        "measures": [{**COUNT, "column": ref("member_id")}],
    },
    count_member_distinct={
        "base_table": "pos_sale",
        "measures": [{"aggregate": "count_distinct", "column": ref("member_id")}],
    },
    return_count_ratio=ratio({**COUNT, "filters": [RETURN]}, COUNT),
    return_amount_ratio=ratio({**SUM, "filters": [RETURN]}, SUM),
    member_return_over_members=ratio(
        {**COUNT, "filters": [MEMBER, RETURN]}, {**COUNT, "filters": [MEMBER]}
    ),
    member_return_over_all=ratio({**COUNT, "filters": [MEMBER, RETURN]}, COUNT),
    member_return_over_returns=ratio(
        {**COUNT, "filters": [MEMBER, RETURN]}, {**COUNT, "filters": [RETURN]}
    ),
    member_ratio_implicit_denominator=ratio(
        {**COUNT, "filters": [MEMBER]}, {**COUNT, "column": ref("member_id")}
    ),
    service_count={"base_table": "tickets", "measures": [COUNT]},
)

# Hand-designed, fictional, no rows from any database. Repeated member IDs
# deliberately distinguish transaction counts from counts of distinct members.
# transaction_no, amount, return reference, member ID
INSTANCES = {
    "coincidental": [
        (1, 100, None, "fictional_m"),
        (2, 100, None, None),
        (3, 10, "fictional_r", "fictional_m"),
        (4, 20, "fictional_r", None),
    ],
    "asymmetric": [
        (1, 90, None, None),
        (2, 40, None, "fictional_m"),
        (3, 30, "fictional_r", None),
        (4, 10, "fictional_r", "fictional_m"),
        (5, 20, "fictional_r", None),
    ],
}
# Independent hand answers, NOT generated by compiler/reference/LLM.
EXPECTED = {
    "count_all": (4, 5),
    "member_count": (2, 2),
    "nonmember_count": (2, 3),
    "count_member_column": (2, 2),
    "count_member_distinct": (1, 1),
    "member_ratio": (1 / 2, 2 / 5),
    "return_count_ratio": (1 / 2, 3 / 5),
    "return_amount_ratio": (30 / 230, 60 / 190),
    "member_return_over_members": (1 / 2, 1 / 2),
    "member_return_over_all": (1 / 4, 1 / 5),
    "member_return_over_returns": (1 / 2, 1 / 3),
    "member_ratio_implicit_denominator": (1, 1),
}


def schema():
    return SchemaModel(
        datasource_id="concept_v2_ruler",
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
            )
        ],
    )


def postgres_values(compiled, rows):
    import psycopg

    assert compiled.physical_sql.count("public.pos_sale") == 1
    parameters = {p.name: p.value for p in compiled.execution_parameters}
    tuples = []
    for i, row in enumerate(rows):
        cells = []
        for j, (value, kind) in enumerate(
            zip(row, ("numeric", "numeric", "text", "text"), strict=True)
        ):
            key = f"fictional_{i}_{j}"
            parameters[key] = value
            cells.append(f"%({key})s::{kind}")
        tuples.append(f"({', '.join(cells)})")
    relation = (
        f"(VALUES {', '.join(tuples)}) AS pos_sale "
        "(transaction_no, total_amount, origin_transaction_no, member_id)"
    )
    sql = compiled.physical_sql.replace("public.pos_sale", relation, 1)
    try:
        with psycopg.connect(
            os.environ[os.environ["GREPBIT_CONCEPT_RULER_DSN_ENV"]], connect_timeout=5
        ) as connection:
            connection.execute("BEGIN READ ONLY")
            assert (
                connection.execute("SELECT current_user").fetchone()[0] == "grepbit_ro"
            )
            connection.execute("SELECT set_config('statement_timeout', '5000', true)")
            return connection.execute(sql, parameters).fetchall()
    except psycopg.Error as error:
        pytest.fail(
            f"postgres_ruler_error:{error.sqlstate or type(error).__name__}",
            pytrace=False,
        )


ENGINES = ["duckdb", "reference"]
if os.environ.get("GREPBIT_CONCEPT_RULER_DSN_ENV"):
    ENGINES.append("postgres")


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("instance", INSTANCES)
@pytest.mark.parametrize("name", EXPECTED)
def test_hand_answers_distinguish_implicit_restriction_and_scope(
    name, instance, engine
):
    query = QueryPlan.model_validate(PLANS[name])
    model = schema()
    compiled = PlanCompiler(model, overlay=OVERLAY).compile(query, as_of=AS_OF)
    columns = ["transaction_no", "total_amount", "origin_transaction_no", "member_id"]
    data = {
        "pos_sale": [
            dict(zip(columns, row, strict=True)) for row in INSTANCES[instance]
        ]
    }
    if engine == "reference":
        rows = evaluate(query, model, OVERLAY, AS_OF, data)
        rows = [tuple(row[c] for c in compiled.output_columns) for row in rows]
    elif engine == "duckdb":
        duck = DuckInstance(model, data)
        try:
            _, rows = duck.execute(compiled.compiled)
        finally:
            duck.con.close()
    else:
        rows = postgres_values(compiled.compiled, INSTANCES[instance])
    expected = EXPECTED[name][list(INSTANCES).index(instance)]
    assert len(rows) == 1 and len(rows[0]) == 1
    assert float(rows[0][0]) == pytest.approx(expected)


@pytest.mark.parametrize("family", DRAFT["families"], ids=lambda f: f["id"])
@pytest.mark.parametrize("language", ["zh", "en", "ja"])
def test_proposed_obligations_are_representable_not_a_measured_extraction(
    family, language
):
    question = family["questions"][language]
    validate_draft(proposed_payload(family, question), question)
    for plan_id, intended in family["pairs"]:
        QueryPlan.model_validate(PLANS[plan_id])
        assert intended in {"pass", "fail", "unknown", "not_applicable"}


@pytest.mark.parametrize(
    "mutation",
    ["unknown_id", "invented_span", "duplicate", "conflict", "bad_role", "extra"],
)
def test_draft_rejects_malformed_claims_without_interpreting_language(mutation):
    family = DRAFT["families"][0]
    question = family["questions"]["en"]
    payload = proposed_payload(family, question)
    item = payload["requirements"][0]
    if mutation == "unknown_id":
        item["concept"] = "not_offered"
    elif mutation == "invented_span":
        item["span"] = "invented evidence"
    elif mutation in {"duplicate", "conflict"}:
        payload["requirements"].append(
            {
                **item,
                "polarity": "include" if mutation == "conflict" else item["polarity"],
            }
        )
    elif mutation == "bad_role":
        item["role"] = "everywhere"
    else:
        payload["confidence"] = 1.0
    with pytest.raises((ValidationError, ValueError)):
        validate_draft(payload, question)


def test_v1_inputs_and_recorded_scores_are_not_relabelled():
    assert (
        digest([PILOT, FIXTURE])
        == "47665256c0d3eb8a0f178c569a2e6a471f145be682c270403529523adb360eb8"
    )
    assert len(DRAFT["families"]) == 12
    assert len({f["id"] for f in DRAFT["families"]}) == 12


def test_all_five_recorded_escapes_still_replay_under_frozen_v1():
    evidence = json.loads(
        (ROOT / "evidence/concept-search-counterexamples-01.json").read_text()
    )
    assert len(evidence["probes"]) == 5
    for probe in evidence["probes"]:
        core = deepcopy(probe["observed_intent"])
        for item in core["requirements"]:
            item["span"] = "unused by the frozen binding checker"
        verdict, reason = check_bindings(
            Intent.model_validate(core),
            QueryPlan.model_validate(probe["plan"]),
            CONTEXT["concepts"],
            OVERLAY,
        )
        assert (verdict, reason) == (probe["observed_verdict"], probe["checker_reason"])
        assert verdict != probe["diagnostic_expected"]


@pytest.mark.parametrize("plan_id", ["count_member_column", "count_member_distinct"])
def test_legacy_no_request_bypass_misses_implicit_membership_exclusion(plan_id):
    verdict, _ = check_bindings(
        Intent(intent="not_requested", requirements=[]),
        QueryPlan.model_validate(PLANS[plan_id]),
        CONTEXT["concepts"],
        OVERLAY,
    )
    assert verdict == "not_applicable"  # Characterization, NOT the intended v2 fail.
    assert EXPECTED[plan_id] != EXPECTED["count_all"]


def test_legacy_checker_passes_implicitly_restricted_denominator_with_correct_intent():
    intent = Intent.model_validate(
        {
            "intent": "required",
            "requirements": [
                {
                    "concept": "member",
                    "polarity": "include",
                    "role": "numerator",
                    "span": "member transactions / all transactions",
                }
            ],
        }
    )
    verdict, reason = check_bindings(
        intent,
        QueryPlan.model_validate(PLANS["member_ratio_implicit_denominator"]),
        CONTEXT["concepts"],
        OVERLAY,
    )
    assert (verdict, reason) == ("pass", "predicate_binding_only")
    assert EXPECTED["member_ratio_implicit_denominator"] != EXPECTED["member_ratio"]


def test_one_coincidental_instance_cannot_certify_scope_or_measure_choice():
    assert (
        EXPECTED["member_return_over_members"][0]
        == EXPECTED["member_return_over_returns"][0]
    )
    assert (
        EXPECTED["member_return_over_members"][1]
        != EXPECTED["member_return_over_returns"][1]
    )
    assert EXPECTED["count_member_column"] != EXPECTED["count_member_distinct"]
