"""Predeclared interpretations, independent hand values and negative controls."""

from copy import deepcopy
from datetime import date

import pytest
from t0_helpers import AS_OF, col, iot_schema

from evals.answer_acceptance import CaseRule, context_digest, grade, prepare
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.application.ask import AskResult, _describe
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable


def schema():
    return SchemaModel(
        datasource_id="fixture",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(
                name="sales",
                primary_key=["id"],
                columns=[
                    col("id", ColumnKind.NUMERIC),
                    col("amount", ColumnKind.NUMERIC),
                    col("day", ColumnKind.DATE),
                    col("role", ColumnKind.TEXT),
                ],
            )
        ],
    )


def plan(*, growth=True, alias="sales"):
    return QueryPlan.model_validate(
        {
            "base_table": "sales",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "sales", "column": "amount"},
                    "alias": alias,
                }
            ],
            "time": {"column": {"table": "sales", "column": "day"}, "grain": "month"},
            "growth": [{"measure": alias}] if growth else [],
        }
    )


ROWS = [(date(2026, 1, 1), 100, None), (date(2026, 2, 1), 200, 1)]
QUESTION = "Compare monthly sales"


def setup(*, expected=None, ordered=False, closed=True, rows=None):
    s = schema()
    compiler = PlanCompiler(s)
    expected = expected or plan()
    rule = CaseRule.model_validate(
        {
            "context_sha256": context_digest(QUESTION, s, None, AS_OF),
            "evidence_id": "fixture-policy-01",
            "closed": closed,
            "interpretations": [
                {
                    "id": "monthly-with-growth",
                    "evidence_id": "hand-values-01",
                    "plan": expected.model_dump(mode="json"),
                    "reference_sql": "SELECT independent_hand_values",
                    "supplementary": ["sales_growth"] if expected.growth else [],
                    "ordered": ordered,
                }
            ],
        }
    )
    prepared = prepare(
        rule,
        question=QUESTION,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=compiler,
        reference=lambda _: rows if rows is not None else ROWS,
    )
    return s, compiler, prepared


def answer(compiler, proposed=None, rows=None, *, question=QUESTION):
    proposed = proposed or plan()
    compiled = compiler.compile(proposed, as_of=AS_OF)
    result = AskResult(
        question=question,
        status="answered",
        plan=proposed,
        rows=[
            dict(zip(compiled.output_columns, r, strict=True))
            for r in (ROWS if rows is None else rows)
        ],
    )
    _describe(result, compiled, question, None, proposed)
    return result


def test_correct_related_growth_passes_without_changing_legacy_matcher():
    from evals.spike_tier0 import match_reference, normalize_rows

    _, c, prepared = setup()
    result = answer(c)
    before = deepcopy(result)
    assert (
        match_reference(
            result.rows, result.plan, [normalize_rows([r[:2] for r in ROWS])]
        )[0]
        is None
    )
    verdict = grade(result, prepared)
    assert verdict["outcome"] == "accepted"
    assert verdict["supplementary_output_positions"] == [2]
    assert verdict["value_evidence_id"] == "hand-values-01"
    assert result == before


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("missing_disclosure", "disclosure_mismatch"),
        ("false_disclosure", "disclosure_mismatch"),
        ("false_assumption", "disclosure_mismatch"),
        ("false_lineage", "disclosure_mismatch"),
        ("sql", "execution_recipe_mismatch"),
        ("bindings", "execution_recipe_mismatch"),
        ("wrong_growth", "value_mismatch"),
        ("wrong_core", "value_mismatch"),
        ("missing_row", "value_mismatch"),
        ("duplicate_row", "value_mismatch"),
        ("extra_column", "output_columns_mismatch"),
    ],
)
def test_disclosure_never_excuses_a_wrong_answer(mutation, reason):
    _, c, prepared = setup()
    result = answer(c)
    if mutation == "missing_disclosure":
        result.interpretation = None
    elif mutation == "false_disclosure":
        result.interpretation = "Only senior engineers, by payment date"
    elif mutation == "false_assumption":
        result.assumptions.append("All rows were excluded")
    elif mutation == "false_lineage":
        result.lineage["filters"] = ["untrue"]
    elif mutation == "sql":
        result.sql = "SELECT 1"
    elif mutation == "bindings":
        result.parameters.append({"name": "invented", "value": 1})
    elif mutation == "wrong_growth":
        result.rows[1]["sales_growth"] = 7
    elif mutation == "wrong_core":
        result.rows[1]["sales"] = 999
    elif mutation == "missing_row":
        result.rows.pop()
    elif mutation == "duplicate_row":
        result.rows.append(dict(result.rows[-1]))
    elif mutation == "extra_column":
        result.rows[0]["unrelated"] = 1
    assert grade(result, prepared)["reason"] == reason
    assert grade(result, prepared)["outcome"] == "rejected"


def test_cosmetic_output_alias_is_not_a_different_interpretation():
    _, c, prepared = setup()
    assert grade(answer(c, plan(alias="營業額")), prepared)["outcome"] == "accepted"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("duplicate", "acceptance_duplicate_recipe"),
        ("all_supplementary", "acceptance_invalid_supplementary_columns"),
        ("limit", "acceptance_limit_oracle_not_supported"),
        ("order", "acceptance_explicit_order_requires_ordered_oracle"),
        ("oracle_width", "acceptance_reference_column_count"),
    ],
)
def test_invalid_or_unsupported_oracles_fail_before_grading(mutation, reason):
    s, c, prepared = setup()
    rule = prepared.rule.model_copy(deep=True)
    alternative = rule.interpretations[0]
    if mutation == "duplicate":
        rule.interpretations.append(alternative.model_copy(update={"id": "duplicate"}))
    elif mutation == "all_supplementary":
        alternative.supplementary = ["period_start", "sales", "sales_growth"]
    elif mutation in {"limit", "order"}:
        data = alternative.plan.model_dump(mode="json")
        data[mutation] = (
            1 if mutation == "limit" else [{"field": "sales", "direction": "desc"}]
        )
        alternative.plan = QueryPlan.model_validate(data)
    with pytest.raises(ValueError, match=reason):
        prepare(
            rule,
            question=QUESTION,
            schema=s,
            overlay=None,
            as_of=AS_OF,
            compiler=c,
            reference=lambda _: [(1,)] if mutation == "oracle_width" else ROWS,
        )


@pytest.mark.parametrize("closed,outcome", [(True, "rejected"), (False, "unassessed")])
def test_coincidental_values_do_not_approve_an_unlisted_population(closed, outcome):
    _, c, prepared = setup(closed=closed)
    data = plan().model_dump(mode="json")
    data["filters"] = [
        {
            "column": {"table": "sales", "column": "role"},
            "op": "eq",
            "values": ["unapproved"],
        }
    ]
    result = answer(c, QueryPlan.model_validate(data))
    assert grade(result, prepared)["outcome"] == outcome
    assert grade(result, prepared)["reason"] == "unlisted_interpretation"


@pytest.mark.parametrize("ordered", [True, False])
def test_row_order_only_relaxed_when_annotation_allows_it(ordered):
    _, c, prepared = setup(ordered=ordered)
    assert grade(answer(c, rows=list(reversed(ROWS))), prepared)["outcome"] == (
        "rejected" if ordered else "accepted"
    )


def test_changed_context_and_truncation_are_unassessed():
    s, c, prepared = setup()
    result = answer(c)
    result.rows_truncated = True
    assert grade(result, prepared)["reason"] == "bounded_result_not_supported"
    s.business_timezone = "UTC"
    assert grade(result, prepared)["reason"] == "context_mismatch"


def test_refusal_only_does_not_allow_a_broader_answer():
    s, c, _ = setup()
    rule = CaseRule(
        context_sha256=context_digest(QUESTION, s, None, AS_OF),
        evidence_id="missing-lease-binding",
        refusal_only=True,
    )
    prepared = prepare(
        rule,
        question=QUESTION,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=c,
        reference=lambda _: pytest.fail("no value oracle for absent meaning"),
    )
    assert grade(answer(c), prepared)["reason"] == "answer_on_refusal_case"
    assert (
        grade(AskResult(question=QUESTION, status="semantic_gap"), prepared)["outcome"]
        == "accepted"
    )
    assert (
        grade(AskResult(question=QUESTION, status="failed"), prepared)["outcome"]
        == "unassessed"
    )


@pytest.mark.parametrize("broad", [False, True])
def test_predeclared_engineer_categories_accept_both_disclosed_readings(broad):
    question = "What is the average amount for engineers?"
    s = schema()
    compiler = PlanCompiler(s)
    variants = []
    for roles in (["engineer"], ["engineer", "senior engineer"]):
        variants.append(
            QueryPlan.model_validate(
                {
                    "base_table": "sales",
                    "measures": [
                        {
                            "aggregate": "avg",
                            "column": {"table": "sales", "column": "amount"},
                        }
                    ],
                    "filters": [
                        {
                            "column": {"table": "sales", "column": "role"},
                            "op": "in",
                            "values": roles,
                        }
                    ],
                }
            )
        )
    rule = CaseRule.model_validate(
        {
            "context_sha256": context_digest(question, s, None, AS_OF),
            "evidence_id": "approved-two-categories",
            "closed": True,
            "interpretations": [
                {
                    "id": str(i),
                    "evidence_id": "hand-averages",
                    "plan": p.model_dump(mode="json"),
                    "reference_sql": str(i),
                }
                for i, p in enumerate(variants)
            ],
        }
    )
    prepared = prepare(
        rule,
        question=question,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=compiler,
        reference=lambda sql: [(100 if sql == "0" else 150,)],
    )
    result = answer(
        compiler, variants[int(broad)], [(150 if broad else 100,)], question=question
    )
    assert grade(result, prepared)["outcome"] == "accepted"
    assert ("senior engineer" in result.interpretation) == broad


@pytest.mark.parametrize("explicit_payment", [False, True])
@pytest.mark.parametrize("period_basis", [False, True])
def test_payroll_alternatives_respect_explicit_time_requirements(
    explicit_payment, period_basis
):
    from test_answer_acceptance_ruler import payroll_plan, payroll_schema

    question = "2025 年每季底薪總額" + ("，按實際付款日期" if explicit_payment else "")
    s = payroll_schema()
    compiler = PlanCompiler(s)
    payment = payroll_plan(False)
    data = payment.model_dump(mode="json")
    data["time"]["column"]["column"] = "period_start"
    period = QueryPlan.model_validate(data)
    approved = [payment] if explicit_payment else [payment, period]
    rule = CaseRule.model_validate(
        {
            "context_sha256": context_digest(question, s, None, AS_OF),
            "evidence_id": "explicit-payment"
            if explicit_payment
            else "either-payroll-basis",
            "closed": True,
            "interpretations": [
                {
                    "id": str(i),
                    "evidence_id": "hand-payroll",
                    "plan": p.model_dump(mode="json"),
                    "reference_sql": "payment" if i == 0 else "period",
                }
                for i, p in enumerate(approved)
            ],
        }
    )
    prepared = prepare(
        rule,
        question=question,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=compiler,
        reference=lambda sql: [(date(2025, 1, 1), 100 if sql == "payment" else 150)],
    )
    result = answer(
        compiler,
        period if period_basis else payment,
        [(date(2025, 1, 1), 150 if period_basis else 100)],
        question=question,
    )
    assert grade(result, prepared)["outcome"] == (
        "rejected" if explicit_payment and period_basis else "accepted"
    )


def test_date_endpoint_binding_matters_even_if_values_coincide():
    question = "Count sales between July 1 and July 8, 2026, including both dates"
    s = schema()
    compiler = PlanCompiler(s)
    payload = {
        "base_table": "sales",
        "measures": [{"aggregate": "count"}],
        "time": {
            "column": {"table": "sales", "column": "day"},
            "scope": {
                "kind": "range",
                "start": "2026-07-01",
                "end_exclusive": "2026-07-09",
            },
        },
    }
    p = QueryPlan.model_validate(payload)
    rule = CaseRule.model_validate(
        {
            "context_sha256": context_digest(question, s, None, AS_OF),
            "evidence_id": "inclusive-dates",
            "closed": True,
            "interpretations": [
                {
                    "id": "inclusive",
                    "evidence_id": "hand-window",
                    "plan": payload,
                    "reference_sql": "SELECT 2",
                }
            ],
        }
    )
    prepared = prepare(
        rule,
        question=question,
        schema=s,
        overlay=None,
        as_of=AS_OF,
        compiler=compiler,
        reference=lambda _: [(2,)],
    )
    assert (
        grade(answer(compiler, p, [(2,)], question=question), prepared)["outcome"]
        == "accepted"
    )
    payload["time"]["scope"]["end_exclusive"] = "2026-07-08"
    assert (
        grade(
            answer(
                compiler, QueryPlan.model_validate(payload), [(2,)], question=question
            ),
            prepared,
        )["outcome"]
        == "rejected"
    )


def test_unknown_extra_measure_is_not_silently_projected_away():
    _, c, prepared = setup(closed=False)
    data = plan().model_dump(mode="json")
    data["measures"].append({"aggregate": "count", "alias": "unrelated"})
    p = QueryPlan.model_validate(data)
    compiled = c.compile(p, as_of=AS_OF)
    rows = [tuple(1 for _ in compiled.output_columns)]
    assert grade(answer(c, p, rows), prepared)["reason"] == "unlisted_interpretation"


def test_metric_filters_do_not_claim_every_row_counts():
    from grepbit.domain.overlay import SemanticOverlay

    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "test",
            "metrics": [
                {
                    "id": "only_critical",
                    "names": ["critical"],
                    "description": "Critical alerts only",
                    "base_table": "alerts",
                    "aggregate": "count",
                    "filters": [
                        {
                            "column": {"table": "alerts", "column": "severity"},
                            "op": "eq",
                            "values": ["critical"],
                        }
                    ],
                }
            ],
        }
    )
    compiled = PlanCompiler(iot_schema(), overlay=overlay).compile(
        QueryPlan.model_validate(
            {"base_table": "alerts", "measures": [{"metric": "only_critical"}]}
        ),
        as_of=AS_OF,
    )
    disclosure = " ".join(a.text for a in compiled.assumptions)
    assert "alerts.severity eq critical" in disclosure
    assert not any("every alerts row counts" in a.text for a in compiled.assumptions)
    assert "NULL-bearing rows" in disclosure


def test_payroll_discloses_effective_metric_time_override():
    from t0_helpers import ROOT
    from test_answer_acceptance_ruler import payroll_plan, payroll_schema

    from grepbit.adapters.overlay_store import load_semantic_overlay

    compiled = PlanCompiler(
        payroll_schema(),
        overlay=load_semantic_overlay(ROOT / "evals/fixtures/pos_overlay.json"),
    ).compile(payroll_plan(True), as_of=AS_OF)
    disclosure = " ".join(a.text for a in compiled.assumptions)
    assert "time basis: hr_payroll.period_start (薪資週期起日)" in disclosure
    assert "time basis: hr_payroll.paid_at" not in disclosure
    assert "2026-01-01T00:00:00+08:00)" in disclosure


@pytest.mark.parametrize("invalid_context", [False, True])
def test_runner_keeps_legacy_score_and_freezes_rules_before_planning(
    tmp_path, monkeypatch, invalid_context
):
    import json
    from types import SimpleNamespace

    import psycopg
    from test_ask_contract import _Executor, _Planner

    from evals import spike_tier0 as runner
    from evals.answer_acceptance import POLICY_REVISION

    s = schema()
    events = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            self.sql = sql
            events.append(sql)

        def fetchall(self):
            return ROWS if self.sql == "SELECT full_oracle" else [r[:2] for r in ROWS]

    class Connection(Cursor):
        def cursor(self):
            return Cursor()

    class Planner(_Planner):
        def propose(self, *args, **kwargs):
            events.append("PLAN")
            return super().propose(*args, **kwargs)

    planner = Planner({"decision": "plan", "plan": plan().model_dump(mode="json")})
    planner.settings = SimpleNamespace(
        model="fixture",
        structured_output_mode="json_object",
        repair_turns=0,
        thinking="off",
    )
    monkeypatch.setenv("ACCEPTANCE_TEST_DSN", "not-a-real-connection")
    monkeypatch.setattr(psycopg, "connect", lambda _: Connection())
    monkeypatch.setattr(runner, "introspect_schema", lambda *a, **kw: s)
    monkeypatch.setattr(runner.GroundingModelSettings, "from_environment", lambda: None)
    monkeypatch.setattr(
        runner, "ChatCompletionsPlanClient", lambda _, **kwargs: planner
    )
    monkeypatch.setattr(
        runner,
        "PsycopgQueryExecutor",
        lambda **kw: _Executor(answer(PlanCompiler(s)).rows),
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "as_of": AS_OF.isoformat(),
                "cases": [
                    {
                        "case_id": "comparison",
                        "question": QUESTION,
                        "expected": {"status": "answered"},
                        "reference_sql": "SELECT core_oracle",
                    }
                ],
            }
        )
    )
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "revision": POLICY_REVISION,
                "cases": {
                    "comparison": {
                        "context_sha256": "0" * 64
                        if invalid_context
                        else context_digest(QUESTION, s, None, AS_OF),
                        "evidence_id": "reviewed-policy",
                        "closed": True,
                        "interpretations": [
                            {
                                "id": "with-growth",
                                "evidence_id": "hand-value-oracle",
                                "plan": plan().model_dump(mode="json"),
                                "reference_sql": "SELECT full_oracle",
                                "supplementary": ["sales_growth"],
                            }
                        ],
                    }
                },
            }
        )
    )
    output = tmp_path / "out.json"
    code = runner.main(
        [
            "--dsn-env",
            "ACCEPTANCE_TEST_DSN",
            "--datasource-id",
            "fixture",
            "--cases",
            str(cases),
            "--output",
            str(output),
            "--live",
            "--acceptance-rules",
            str(policy),
            "--redact-rows",
        ]
    )
    if invalid_context:
        assert code == 2 and not planner.calls and not output.exists()
        return
    assert code == 0
    assert events.index("SELECT full_oracle") < events.index("PLAN")
    report = json.loads(output.read_text())
    assert report["results"][0]["correct"] is False
    assert report["results"][0]["answer_acceptance"]["outcome"] == "accepted"
    assert report["summary"]["correct"] == 0
    assert report["summary"]["answer_acceptance"]["outcomes"]["accepted"] == 1
    assert "rows" not in report["results"][0]
