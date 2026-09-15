"""Reviewed direction alternatives reuse existing recipe and value verification."""

from copy import deepcopy

import pytest
from t0_helpers import AS_OF
from test_answer_acceptance import answer, schema

from evals.answer_acceptance import CaseRule, context_digest, grade, prepare
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan

QUESTION = "List every amount, ordered by amount."
# Independent oracle includes NULL last and id ASC inside equal amounts.
ASC = [(2, 10), (4, 10), (1, 20), (3, None)]
DESC = [(1, 20), (2, 10), (4, 10), (3, None)]


def row_plan(direction="desc", field="amount"):
    return QueryPlan.model_validate(
        {
            "base_table": "sales",
            "rows": {
                "columns": [{"table": "sales", "column": c} for c in ["id", "amount"]]
            },
            "order": [{"field": field, "direction": direction}],
        }
    )


def setup(directions=("asc", "desc"), question=QUESTION):
    s = schema()
    c = PlanCompiler(s, allow_rows=True)
    specs = [
        {
            "id": d,
            "evidence_id": "rows-direction-adjudication-v1",
            "plan": row_plan(d),
            "ordered": True,
            "reference_sql": (
                f"SELECT id, amount FROM sales ORDER BY amount {d} NULLS LAST, id ASC"
            ),
        }
        for d in directions
    ]
    rule = CaseRule(
        context_sha256=context_digest(question, s, None, AS_OF),
        evidence_id="rows-direction-adjudication-v1",
        closed=True,
        interpretations=specs,
    )
    prepared = prepare(
        rule,
        question=question,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=c,
        reference=lambda sql: ASC if "amount asc" in sql else DESC,
    )
    return c, prepared


@pytest.mark.parametrize("direction,rows", [("asc", ASC), ("desc", DESC)])
def test_full_disclosed_order_accepts_both_independent_oracles(direction, rows):
    c, prepared = setup()
    r = answer(c, row_plan(direction), rows, question=QUESTION)
    assert grade(r, prepared)["outcome"] == "accepted"


@pytest.mark.parametrize(
    "mutation",
    [
        "reverse",
        "tie_reverse",
        "null_first",
        "missing",
        "deduplicate",
        "shuffle",
        "wrong_key",
        "disclosure",
        "truncated",
        "limit",
        "offset_sql",
    ],
)
def test_relaxed_direction_is_not_relaxed_values_or_scope(mutation):
    c, prepared = setup()
    r = answer(c, row_plan(), deepcopy(DESC), question=QUESTION)
    if mutation == "reverse":
        r.rows = list(reversed(answer(c, row_plan("asc"), ASC, question=QUESTION).rows))
    elif mutation == "tie_reverse":
        r.rows[1], r.rows[2] = r.rows[2], r.rows[1]
    elif mutation == "null_first":
        r.rows.insert(0, r.rows.pop())
    elif mutation in {"missing", "deduplicate"}:
        r.rows.pop(2)
    elif mutation == "shuffle":
        r.rows[0], r.rows[1] = r.rows[1], r.rows[0]
    elif mutation == "wrong_key":
        r = answer(c, row_plan(field="id"), DESC, question=QUESTION)
    elif mutation == "disclosure":
        r.interpretation = "Ordered ascending"
    elif mutation == "truncated":
        r.rows_truncated = True
    elif mutation == "limit":
        r.plan = r.plan.model_copy(update={"limit": 3})
    elif mutation == "offset_sql":
        r.sql += " OFFSET 1"
    assert grade(r, prepared)["outcome"] != "accepted"


@pytest.mark.parametrize(
    "question,allowed,other",
    [
        ("List amounts in ascending order", "asc", "desc"),
        ("List amounts descending", "desc", "asc"),
        ("List amounts from lowest to highest", "asc", "desc"),
        ("List amounts from highest to lowest", "desc", "asc"),
    ],
)
def test_reviewed_explicit_or_implicit_direction_has_only_one_interpretation(
    question, allowed, other
):
    c, prepared = setup((allowed,), question)
    assert (
        grade(
            answer(
                c, row_plan(other), DESC if other == "desc" else ASC, question=question
            ),
            prepared,
        )["reason"]
        == "unlisted_interpretation"
    )


def test_top_n_reference_not_admitted_by_direction_adjudication():
    s = schema()
    c, prepared = setup()
    rule = prepared.rule.model_copy(deep=True)
    rule.interpretations[0].plan = row_plan().model_copy(update={"limit": 2})
    with pytest.raises(ValueError, match="acceptance_limit_oracle_not_supported"):
        prepare(
            rule,
            question=QUESTION,
            schema=s,
            overlay=None,
            as_of=AS_OF,
            compiler=c,
            reference=lambda _: DESC[:2],
        )
