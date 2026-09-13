"""Proposed negative-binding checkpoint; current runtime intentionally fails.

Black-box ask rulers use fictional data and real SQL compilation/execution.
No remote model, production DB, private artifact imports or new runtime API.
"""

from datetime import datetime

import pytest
from t0_helpers import col

from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.application.ask import AskServices, AskSettings, ask
from grepbit.application.grounding import ValueIndex
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import Filter, FilterOp, PlanProposal, QueryPlan
from grepbit.domain.schema_model import (
    ColumnKind,
    ForeignKey,
    SchemaModel,
    SchemaTable,
)
from grepbit.ports.query_executor import ExecutionResult

AS_OF = datetime.fromisoformat("2026-02-10T18:00:00+08:00")
FULL = "Harbor East Terminal"
NAMES = [FULL, "North Hub Alpha", "North Hub Beta"]
SCHEMA = SchemaModel(
    datasource_id="negative_ruler",
    schema_name="public",
    business_timezone="Asia/Taipei",
    tables=[
        SchemaTable(
            name="facts",
            primary_key=["id"],
            columns=[
                col("id", ColumnKind.NUMERIC),
                col("label", ColumnKind.TEXT),
                col("amount", ColumnKind.NUMERIC),
            ],
        ),
        SchemaTable(
            name="events",
            primary_key=["id"],
            columns=[
                col("id", ColumnKind.NUMERIC),
                col("fact_id", ColumnKind.NUMERIC),
                col("label", ColumnKind.TEXT),
            ],
        ),
    ],
    foreign_keys=[
        ForeignKey(
            table="events",
            column="fact_id",
            referenced_table="facts",
            referenced_column="id",
        )
    ],
)
DATA = {
    "facts": [
        {"id": i + 1, "label": name, "amount": (i + 1) * 100}
        for i, name in enumerate([*NAMES, None])
    ],
    "events": [
        {"id": 1, "fact_id": 1, "label": FULL},
        {"id": 2, "fact_id": 2, "label": "North Hub Alpha"},
        {"id": 3, "fact_id": 3, "label": None},
    ],
}
PATHS = ["plan", "measure", "numerator", "denominator", "without"]
EXPECTED = {"plan": 500, "measure": 2, "numerator": 0.5, "denominator": 2, "without": 3}


def predicate(value, *, table="facts", column="label", op="ne"):
    return {"column": {"table": table, "column": column}, "op": op, "values": [value]}


def proposal(path="plan", value="Harbor East"):
    condition = predicate(value, table="events" if path == "without" else "facts")
    count = {"aggregate": "count"}
    payload = {"base_table": "facts", "measures": [count]}
    if path == "plan":
        payload.update(
            measures=[
                {"aggregate": "sum", "column": {"table": "facts", "column": "amount"}}
            ],
            filters=[condition],
        )
    elif path == "measure":
        payload["measures"] = [{**count, "filters": [condition]}]
    elif path in {"numerator", "denominator"}:
        ratio = {"numerator": dict(count), "denominator": dict(count)}
        ratio[path]["filters"] = [condition]
        payload["measures"] = [{"ratio": ratio}]
    else:
        payload["without"] = {"table": "events", "filters": [condition]}
    return QueryPlan.model_validate(payload)


def occurrence(plan, path):
    if path == "plan":
        return plan.filters[0]
    if path == "measure":
        return plan.measures[0].filters[0]
    if path == "without":
        return plan.without.filters[0]
    return getattr(plan.measures[0].ratio, path).filters[0]


class Harness:
    def __init__(self, plan, *, policy="public", index=True, stale=False):
        self.plan = plan
        self.before = plan.model_dump(mode="json")
        self.calls = 0
        self.checked = []
        self.executions = 0
        self.compilations = []
        self.policies = []
        self.stale = stale
        self.database = DuckInstance(SCHEMA, DATA)
        policies = []
        if policy != "unlisted":
            for table in ["facts", "events"]:
                item = {"column": {"table": table, "column": "label"}, "sample": False}
                if policy == "personal":
                    item["sensitivity"] = "personal"
                elif policy == "off":
                    item["ground"] = False
                elif policy == "hidden":
                    item["visible"] = False
                policies.append(item)
        self.overlay = SemanticOverlay.model_validate(
            {
                "datasource_id": SCHEMA.datasource_id,
                "revision": "ruler",
                "column_policies": policies,
            }
        )
        self.compiler = PlanCompiler(SCHEMA, overlay=self.overlay)
        self.policy = PostgresSqlPolicy(
            tables=frozenset(t.name for t in SCHEMA.tables),
            functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
        )
        self.index = (
            ValueIndex({"facts.label": NAMES, "events.label": NAMES}) if index else None
        )

    def propose(self, *args, **kwargs):
        self.calls += 1
        return PlanProposal(decision="plan", plan=self.plan.model_copy(deep=True))

    def compile(self, plan, **kwargs):
        self.compilations.append(plan.model_dump(mode="json"))
        return self.compiler.compile(plan, **kwargs)

    def assert_safe_select_statement(self, sql):
        self.policies.append(sql)
        return self.policy.assert_safe_select_statement(sql)

    def check(self, checks):
        self.checked.extend((c.table, c.column, c.value) for c in checks)
        return [
            c
            for c in checks
            if (self.stale and c.value == FULL)
            or not any(row[c.column] == c.value for row in DATA[c.table])
        ]

    def execute(self, query, **kwargs):
        self.executions += 1
        columns, rows = self.database.execute(query)
        return ExecutionResult(
            rows=tuple(dict(zip(columns, r, strict=True)) for r in rows),
            columns=tuple(columns),
            row_count=len(rows),
        )

    def run(self, question="Exclude Harbor East from the total.", **settings):
        try:
            return ask(
                question,
                AskServices(
                    schema=SCHEMA,
                    planner=self,
                    compiler=self,
                    policy=self,
                    executor=self,
                    literal_checker=self.check,
                    unsafe=lambda q: False,
                    overlay=self.overlay,
                    value_index=self.index,
                ),
                AskSettings(as_of=AS_OF, **settings),
            )
        finally:
            self.database.con.close()
            assert self.plan.model_dump(mode="json") == self.before


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "question", ["Exclude Harbor East.", "排除 Harbor East。", "Harbor East を除外。"]
)
def test_unique_negative_binding_preserves_scope_and_values(path, question):
    h = Harness(proposal(path))
    result = h.run(question)
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL]
    assert occurrence(result.plan, path).op == "ne"
    assert float(next(iter(result.rows[0].values()))) == EXPECTED[path]
    assert h.calls == 1 and h.executions == 1
    assert len(h.compilations) >= 2 and len(h.policies) >= 2
    assert any(value == FULL for _, _, value in h.checked)
    assert any(
        "Harbor East" in a and FULL in a and "stored value" in a
        for a in result.assumptions
    )
    assert result.verification != "verified"


@pytest.mark.parametrize("path", PATHS)
def test_exact_negative_literal_and_null_semantics_remain(path):
    h = Harness(proposal(path, FULL))
    result = h.run()
    assert result.status == "answered"
    assert occurrence(result.plan, path).values == [FULL]
    assert float(next(iter(result.rows[0].values()))) == EXPECTED[path]
    assert result.grounding == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "value,reason",
    [("North Hub", "filter_value_ambiguous"), ("ZZZZ9999", "filter_value_not_found")],
)
def test_unresolved_eligible_negative_name_refuses_before_execution(
    path, value, reason
):
    h = Harness(proposal(path, value))
    result = h.run()
    assert (result.status, result.reason) == ("clarify", reason)
    assert h.executions == 0 and result.rows == []
    assert occurrence(result.plan, path).values == [value]


@pytest.mark.parametrize("path", PATHS)
def test_missing_index_is_not_evidence_of_an_empty_candidate_universe(path):
    h = Harness(proposal(path), index=False)
    result = h.run()
    assert (result.status, result.reason) == ("clarify", "filter_value_not_found")
    assert h.executions == 0


def test_stale_unique_candidate_must_be_rechecked():
    h = Harness(proposal(), stale=True)
    result = h.run()
    assert result.status == "clarify"
    assert any(value == FULL for _, _, value in h.checked)
    assert h.executions == 0


@pytest.mark.parametrize("policy", ["unlisted", "off", "personal"])
def test_unapproved_index_does_not_enable_negative_matching(policy):
    h = Harness(proposal(value="Harbor East"), policy=policy)
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == ["Harbor East"]
    assert h.checked == [] and result.grounding == []
    assert float(next(iter(result.rows[0].values()))) == 600


def test_ordinary_absent_category_exclusion_remains_a_valid_literal():
    h = Harness(proposal(value="ZZZZ9999"), policy="off")
    result = h.run()
    assert result.status == "answered" and h.checked == []
    assert float(next(iter(result.rows[0].values()))) == 600  # NULL still excluded


@pytest.mark.parametrize("flag", ["grounding", "literal_check"])
def test_existing_research_bypass_is_not_silently_redefined(flag):
    h = Harness(proposal())
    result = h.run(**{flag: False})
    assert result.status == "answered"
    assert result.plan.filters[0].values == ["Harbor East"]


def test_numeric_negative_filter_is_not_name_grounding():
    plan = proposal(value=FULL)
    plan.filters[0].column.column = "amount"
    plan.filters[0].values = [100]
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered" and h.checked == []
    assert float(next(iter(result.rows[0].values()))) == 900


def test_positive_grounding_control_remains_unchanged():
    plan = proposal()
    plan.filters[0].op = FilterOp.EQ
    h = Harness(plan)
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == [FULL]
    assert float(next(iter(result.rows[0].values()))) == 100


def test_hidden_column_does_not_leak_index_candidates():
    h = Harness(proposal(), policy="hidden")
    result = h.run()
    assert result.status == "unsupported"
    assert h.checked == [] and h.executions == 0
    assert result.grounding == [] and FULL not in (result.clarification or "")


def test_exact_name_wins_over_similar_longer_names():
    h = Harness(proposal(value="North Hub Alpha"))
    h.index = ValueIndex({"facts.label": ["North Hub Alpha", "North Hub Alpha Annex"]})
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == ["North Hub Alpha"]
    assert result.grounding == []
    assert float(next(iter(result.rows[0].values()))) == 400


def test_same_literal_in_opposite_operand_is_not_a_global_restriction():
    plan = proposal("numerator")
    plan.measures[0].ratio.denominator.filters = [
        Filter.model_validate(predicate(FULL, op="eq"))
    ]
    h = Harness(plan)
    result = h.run()
    assert occurrence(result.plan, "numerator").values == [FULL]
    assert occurrence(result.plan, "denominator").op == "eq"
    assert occurrence(result.plan, "denominator").values == [FULL]
    assert result.plan.filters == []
    assert float(next(iter(result.rows[0].values()))) == 2


def test_multiple_negative_occurrences_keep_both_predicates():
    plan = proposal()
    plan.filters.append(Filter.model_validate(predicate("North Hub Alpha")))
    h = Harness(plan)
    result = h.run()
    assert [f.values for f in result.plan.filters] == [[FULL], ["North Hub Alpha"]]
    assert all(f.op == "ne" for f in result.plan.filters)
    assert float(next(iter(result.rows[0].values()))) == 300


def test_reviewed_definition_is_not_fuzzy_rewritten():
    h = Harness(
        QueryPlan.model_validate(
            {"base_table": "facts", "measures": [{"metric": "reviewed_total"}]}
        )
    )
    h.overlay = SemanticOverlay.model_validate(
        {
            **h.overlay.model_dump(mode="json"),
            "metrics": [
                {
                    "id": "reviewed_total",
                    "names": ["Reviewed total"],
                    "description": "Reviewed literal, not a proposed name.",
                    "base_table": "facts",
                    "aggregate": "sum",
                    "column": {"table": "facts", "column": "amount"},
                    "filters": [predicate("Harbor East")],
                }
            ],
        }
    )
    before = h.overlay.model_dump(mode="json")
    h.compiler = PlanCompiler(SCHEMA, overlay=h.overlay)
    result = h.run()
    assert result.status == "answered"
    assert h.overlay.model_dump(mode="json") == before
    assert h.checked == [] and result.grounding == []
    assert float(next(iter(result.rows[0].values()))) == 600


def test_normalized_exact_replacement_is_also_disclosed():
    h = Harness(proposal(value="harbor east terminal"))
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == [FULL]
    assert any(
        "harbor east terminal" in a and FULL in a and "stored value" in a
        for a in result.assumptions
    )


def test_question_filter_on_reviewed_metric_is_still_an_unreviewed_binding():
    plan = proposal("measure")
    data = plan.model_dump(mode="json")
    data["measures"] = [
        {"metric": "row_count", "filters": data["measures"][0]["filters"]}
    ]
    h = Harness(QueryPlan.model_validate(data))
    h.overlay = SemanticOverlay.model_validate(
        {
            **h.overlay.model_dump(mode="json"),
            "metrics": [
                {
                    "id": "row_count",
                    "names": ["Rows"],
                    "description": "All rows.",
                    "base_table": "facts",
                    "aggregate": "count",
                }
            ],
        }
    )
    h.compiler = PlanCompiler(SCHEMA, overlay=h.overlay)
    result = h.run()
    assert result.status == "answered"
    assert result.plan.measures[0].filters[0].values == [FULL]
    assert float(next(iter(result.rows[0].values()))) == 2
    assert result.verification == "partially_verified"


def test_exact_existing_negative_name_needs_no_fuzzy_index():
    h = Harness(proposal(value=FULL), index=False)
    result = h.run()
    assert result.status == "answered"
    assert result.plan.filters[0].values == [FULL]
    assert float(next(iter(result.rows[0].values()))) == 500


def test_skipped_index_column_does_not_authorize_a_missing_negative_name():
    h = Harness(proposal())
    h.index = ValueIndex({})
    result = h.run()
    assert (result.status, result.reason) == ("clarify", "filter_value_not_found")
    assert h.executions == 0
