"""Research rulers, not a replacement gate or a newly approved refusal policy.

Green characterization tests deliberately expose incorrect heuristic decisions.
Hand answers establish the mutations' meaning without a new semantic checker.
"""

from copy import deepcopy

import pytest
import yaml
from t0_helpers import AS_OF, ROOT, col

from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.shapes import unmapped_concepts
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

PILOT = yaml.safe_load((ROOT / "evals/cases/concepts/pilot.yaml").read_text())
PACK = load_shape_pack()
OVERLAY = load_semantic_overlay(ROOT / "evals/fixtures/pos_overlay.json")
OVERLAY = OVERLAY.model_copy(
    update={
        "metrics": [OVERLAY.metric("return_amount")],
        "column_aliases": [],
        "absent_concepts": [],
    }
)


def ref(name):
    return {"table": "pos_sale", "column": name}


def predicate(name, op):
    return {"column": ref(name), "op": op}


RETURN = predicate("origin_transaction_no", "not_null")
MEMBER = predicate("member_id", "not_null")
SUM = {"aggregate": "sum", "column": ref("total_amount")}
COUNT = {"aggregate": "count"}


def plan(measure, **extra):
    return {"base_table": "pos_sale", "measures": [measure], **extra}


PLANS = {
    "return_metric": plan({"metric": "return_amount"}),
    "return_raw": plan(SUM, filters=[RETURN]),
    "return_operand": plan({**SUM, "filters": [RETURN]}),
    "return_missing": plan(SUM),
    "return_inverted": plan(
        SUM, filters=[predicate("origin_transaction_no", "is_null")]
    ),
    "member_count": plan(COUNT, filters=[MEMBER]),
    "nonmember_count": plan(COUNT, filters=[predicate("member_id", "is_null")]),
    "count_all": plan(COUNT),
    "member_ratio": plan(
        {"ratio": {"numerator": {**COUNT, "filters": [MEMBER]}, "denominator": COUNT}}
    ),
    "member_ratio_reversed": plan(
        {"ratio": {"numerator": COUNT, "denominator": {**COUNT, "filters": [MEMBER]}}}
    ),
    "member_whole_share": plan({**COUNT, "filters": [MEMBER], "share_of_total": True}),
    "return_dimension_only": plan(SUM, dimensions=[ref("origin_transaction_no")]),
    "member_dimension_only": plan(COUNT, dimensions=[ref("member_id")]),
}

# Fictional identifiers only. No existing DB data is used or sampled.
# columns: transaction_no, total_amount, origin_transaction_no, member_id
INSTANCES = {
    "unequal": [
        (1, 100, None, None),
        (2, 40, "fictional_origin_1", "fictional_member_1"),
        (3, 20, "fictional_origin_2", None),
        (4, 80, None, "fictional_member_2"),
        (5, 60, None, "fictional_member_3"),
    ],
    "no_returns": [
        (1, 100, None, None),
        (2, 20, None, "fictional_member_1"),
        (3, 30, None, "fictional_member_2"),
    ],
    "coincidence": [
        (1, 10, None, None),
        (2, 10, "fictional_origin_1", "fictional_member_1"),
        (3, 10, None, None),
        (4, 10, "fictional_origin_2", "fictional_member_2"),
    ],
}
# Hand-computed, not produced by SQL, evaluate(), or the future checker.
# Each entry follows unequal / no_returns / coincidence.
EXPECTED = {
    "return_metric": (60, None, 20),
    "return_raw": (60, None, 20),
    "return_operand": (60, None, 20),
    "return_missing": (300, 150, 40),
    "return_inverted": (240, 150, 20),
    "member_count": (3, 2, 2),
    "nonmember_count": (2, 1, 2),
    "count_all": (5, 3, 4),
    "member_ratio": (0.6, 2 / 3, 0.5),
    "member_ratio_reversed": (5 / 3, 1.5, 2),
    "member_whole_share": (0.6, 2 / 3, 0.5),
}


def schema():
    return SchemaModel(
        datasource_id="pos_test",
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
                    col("sale_date", ColumnKind.TIMESTAMP),
                ],
            )
        ],
    )


def data(instance):
    columns = ["transaction_no", "total_amount", "origin_transaction_no", "member_id"]
    return {
        "pos_sale": [dict(zip(columns, r, strict=True)) for r in INSTANCES[instance]]
    }


@pytest.mark.parametrize("name", EXPECTED)
@pytest.mark.parametrize("instance", INSTANCES)
def test_compiler_and_reference_match_independent_hand_answers(name, instance):
    model = schema()
    query = QueryPlan.model_validate(deepcopy(PLANS[name]))
    compiled = PlanCompiler(model, overlay=OVERLAY).compile(query, as_of=AS_OF)
    duck = DuckInstance(model, data(instance))
    try:
        _, sql_rows = duck.execute(compiled.compiled)
    finally:
        duck.con.close()
    reference = evaluate(query, model, OVERLAY, AS_OF, data(instance))
    ref_rows = [
        tuple(row[column] for column in compiled.output_columns) for row in reference
    ]
    expected = EXPECTED[name][list(INSTANCES).index(instance)]
    for rows in (sql_rows, ref_rows):
        assert len(rows) == 1 and len(rows[0]) == 1
        actual = rows[0][0]
        if expected is None:
            assert actual is None
        else:
            assert float(actual) == pytest.approx(expected)


@pytest.mark.parametrize("name", ["return_dimension_only", "member_dimension_only"])
def test_dimension_mention_changes_shape_and_does_not_filter_population(name):
    model = schema()
    query = QueryPlan.model_validate(PLANS[name])
    compiled = PlanCompiler(model, overlay=OVERLAY).compile(query, as_of=AS_OF)
    duck = DuckInstance(model, data("unequal"))
    try:
        _, rows = duck.execute(compiled.compiled)
    finally:
        duck.con.close()
    assert len(rows) > 1
    assert sum(float(row[1]) for row in rows) == (
        300 if name.startswith("return") else 5
    )


@pytest.mark.parametrize(
    "name,question,concept",
    [
        ("return_missing", "退貨金額是多少？", "returns"),
        ("return_inverted", "退貨金額是多少？", None),
        ("return_dimension_only", "退貨金額是多少？", None),
        ("nonmember_count", "會員交易筆數是多少？", None),
        ("member_ratio_reversed", "會員交易佔全部交易的比例是多少？", None),
        ("member_dimension_only", "會員交易筆數是多少？", None),
        (
            "return_missing",
            "Sum total_amount where origin_transaction_no is not NULL.",
            None,
        ),
        (
            "count_all",
            "Do not filter by membership; count all transaction rows.",
            "member",
        ),
    ],
)
def test_legacy_gate_characterization_not_a_correctness_expectation(
    name, question, concept
):
    """None means the old gate misses the issue, NOT a correct semantic answer."""
    query = QueryPlan.model_validate(PLANS[name])
    unmapped = unmapped_concepts(question, query, PACK, OVERLAY, set())
    assert [item[0] for item in unmapped] == ([] if concept is None else [concept])


def test_return_imperative_false_positive_is_isolated_with_the_same_plan():
    family = next(
        f for f in PILOT["families"] if f["family_id"] == "service_return_verb"
    )
    query = QueryPlan.model_validate(
        {
            "base_table": "work_logs",
            "measures": [
                COUNT,
                {
                    "aggregate": "count_distinct",
                    "column": {"table": "work_logs", "column": "ticket_id"},
                },
            ],
        }
    )
    for language, question in family["questions"].items():
        missing = unmapped_concepts(question, query, PACK, None, set())
        assert [item[0] for item in missing] == (
            ["returns"] if language == "en" else []
        )
    without_imperative = family["questions"]["en"].removesuffix(" Return both totals.")
    assert unmapped_concepts(without_imperative, query, PACK, None, set()) == []


def test_single_instance_agreement_can_hide_inverted_predicates():
    assert EXPECTED["return_raw"][2] == EXPECTED["return_inverted"][2]
    assert EXPECTED["return_raw"][0] != EXPECTED["return_inverted"][0]
    assert EXPECTED["member_count"][2] == EXPECTED["nonmember_count"][2]
    assert EXPECTED["member_count"][0] != EXPECTED["nonmember_count"][0]


def test_pilot_is_a_balanced_authored_development_ruler_not_a_holdout():
    assert PILOT["scope"] == "development_only"
    families = PILOT["families"]
    assert len(families) == len({f["family_id"] for f in families}) == 10
    assert {f["datasource"] for f in families} == {"pos", "service"}
    assert {f["intent"] for f in families} == {"required", "not_requested", "ambiguous"}
    for family in families:
        assert set(family["questions"]) == {"zh", "en", "ja"}
        assert family["rationale"]
        assert bool(family["requirements"]) == (family["intent"] == "required")
        for requirement in family["requirements"]:
            assert requirement["concept"] in PILOT["concepts"]
            assert requirement["polarity"] in {"include", "exclude"}
            assert requirement["role"] in {"population", "numerator"}
        if family["intent"] == "ambiguous":
            assert family["binding_status"] == "unresolved"
    # Definition unavailable is still a real request, not an irrelevant word.
    missing = next(f for f in families if f["family_id"] == "service_refunds")
    assert (
        missing["intent"] == "required" and missing["binding_status"] == "unavailable"
    )


def test_return_binding_has_existing_definition_provenance():
    metric = OVERLAY.metric("return_amount")
    binding = PILOT["concepts"]["returns"]["binding"]
    assert metric.filters[0].column.id == binding["column"]
    assert metric.filters[0].op.value == binding["op"]
