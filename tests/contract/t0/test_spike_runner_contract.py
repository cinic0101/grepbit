"""Tier-0 spike runner helpers: row normalization and the unsafe language pack."""

from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from t0_helpers import ROOT

spec = importlib.util.spec_from_file_location(
    "spike_tier0", ROOT / "evals" / "spike_tier0.py"
)
spike = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(spike)


def test_normalize_rows_compares_values_not_names_or_order() -> None:
    actual = spike.normalize_rows(
        [{"model": "GW-10", "s": Decimal("360.0000")}, {"model": "AP-500", "s": 270}]
    )
    reference = spike.normalize_rows([("AP-500", Decimal("270")), ("GW-10", 360.0)])
    assert actual == reference
    assert spike.normalize_rows([(None, 1.23456)]) == [("NULL", "1.2346")]
    assert spike.normalize_rows([(date(2026, 7, 1), datetime(2026, 7, 1, 8))]) == [
        ("2026-07-01", "2026-07-01T08:00:00")
    ]


@pytest.mark.parametrize(
    ("question", "flagged"),
    [
        ("Delete all resolved alerts", True),
        ("Drop the orders table", True),
        ("刪除2026年7月的所有訂單", True),
        ("How many devices were updated last month?", False),
        ("Show alerts by severity", False),
    ],
)
def test_unsafe_language_pack_uses_word_boundaries_for_latin_only(
    question, flagged
) -> None:
    assert spike.unsafe(question) is flagged


def test_cases_document_requires_a_case_list(tmp_path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text("as_of: '2026-08-15T12:00:00+08:00'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tier0_cases_invalid"):
        spike.load_cases(path)
    for name in ("iot", "retail"):
        document = spike.load_cases(ROOT / "evals" / "cases" / "tier0" / f"{name}.yaml")
        for case in document["cases"]:
            if case["expected"]["status"] == "answered":
                assert "reference_sql" in case, case["case_id"]


def _answered_result(**extra):
    return {
        "case_id": "q01",
        "question": "各門市營業額",
        "expected_status": None,
        "status": "answered",
        "correct": None,
        "elapsed_seconds": 3.2,
        "verification": "unverified_semantics",
        "interpretation": "sum of total_amount by store_name",
        "assumptions": ["Column meanings come from the schema only."],
        "sql": "SELECT store.store_name, SUM(pos_sale.total_amount) ...",
        "row_count": 2,
        "rows": [
            {"store_name": "門市甲", "s": "10"},
            {"store_name": "門市乙", "s": "20"},
        ],
        "reference_rows": [("門市甲", "10")],
        **extra,
    }


def test_redact_rows_drops_cell_values_but_keeps_counts_and_sql() -> None:
    redacted = spike.redact_rows(_answered_result())
    assert "rows" not in redacted and "reference_rows" not in redacted
    assert redacted["row_count"] == 2 and redacted["sql"].startswith("SELECT")
    dumped = json.dumps(redacted, ensure_ascii=False)
    assert "門市甲" not in dumped and "門市乙" not in dumped  # no cell value survives


def test_review_sheet_shows_rows_and_verdict_skeleton_is_blank() -> None:
    summary = {
        "datasource_id": "pos_real",
        "cases_file": "q.yaml",
        "as_of": "2026-09-01T00:00:00+08:00",
        "prompt_revision": "plan-classify-json-v5",
        "cases": 2,
        "status_counts": {"answered": 1, "clarify": 1},
        "p50_seconds": 3.2,
        "p95_seconds": 4.0,
    }
    refused = {
        "case_id": "q02",
        "question": "退貨率",
        "expected_status": None,
        "status": "clarify",
        "correct": None,
        "elapsed_seconds": 4.0,
        "reason": "ambiguous",
        "clarification": "Which column means return?",
    }
    sheet = spike.review_sheet(summary, [_answered_result(), refused])
    assert "## 1. q01" in sheet and "| 門市甲 | 10 |" in sheet and "```sql" in sheet
    assert "## 2. q02" in sheet and "Which column means return?" in sheet
    skeleton = yaml.safe_load(spike.verdict_skeleton(Path("run.json"), [refused]))
    assert skeleton["verdicts"] == [
        {
            "case_id": "q02",
            "question": "退貨率",
            "status": "clarify",
            "verdict": None,
            "note": "",
        }
    ]
    assert set(skeleton["verdict_values"]) == set(spike.VERDICTS)


def test_tally_counts_the_four_stage_two_numbers_and_rejects_gaps() -> None:
    tally_spec = importlib.util.spec_from_file_location(
        "tally_verdicts", ROOT / "evals" / "tally_verdicts.py"
    )
    tally = importlib.util.module_from_spec(tally_spec)
    assert tally_spec.loader is not None
    tally_spec.loader.exec_module(tally)
    report = {
        "summary": {
            "datasource_id": "pos_real",
            "cases_file": "q.yaml",
            "prompt_revision": "v5",
            "status_counts": {"answered": 3, "clarify": 1, "semantic_gap": 1},
            "p50_seconds": 3.0,
            "p95_seconds": 5.0,
        },
        "results": [
            {"case_id": "a", "status": "answered"},
            {"case_id": "b", "status": "answered"},
            {"case_id": "c", "status": "answered"},
            {"case_id": "d", "status": "clarify"},
            {"case_id": "e", "status": "semantic_gap"},
        ],
    }
    verdicts = {
        "verdict_values": list(spike.VERDICTS),
        "verdicts": [
            {"case_id": "a", "verdict": "correct"},
            {"case_id": "b", "verdict": "wrong_silent"},
            {"case_id": "c", "verdict": "unsure"},
            {"case_id": "d", "verdict": "refusal_ok"},
            {"case_id": "e", "verdict": "refusal_bad"},
        ],
    }
    numbers = tally.tally(report, verdicts)
    assert numbers["judged"] == 4 and numbers["correct"] == 2
    assert numbers["correctness"] == 0.5
    assert numbers["wrong_numbers_without_exposed_assumption"] == 1
    assert numbers["refusals_that_should_have_answered"] == 1
    assert numbers["clarify_rate"] == 0.2 and numbers["refusal_rate"] == 0.4
    assert numbers["p95_seconds"] == 5.0

    verdicts["verdicts"][1]["verdict"] = None
    verdicts["verdicts"][3]["verdict"] = "correct"  # a refusal cannot be "correct"
    with pytest.raises(ValueError) as error:
        tally.tally(report, verdicts)
    assert "b: verdict missing" in str(error.value)
    assert "d: clarify case cannot take correct" in str(error.value)


def test_cases_without_expected_status_are_left_to_the_judge(tmp_path) -> None:
    path = tmp_path / "real.yaml"
    path.write_text(
        "datasource_id: pos_real\nas_of: '2026-09-01T00:00:00+08:00'\n"
        "cases:\n  - case_id: q01\n    question: 各門市營業額\n",
        encoding="utf-8",
    )
    document = spike.load_cases(path)
    case = document["cases"][0]
    assert "expected" not in case  # the runner reads it as None and marks correct null


def test_settle_inlines_bound_values_as_sql_literals() -> None:
    settle_spec = importlib.util.spec_from_file_location(
        "settle_batch", ROOT / "evals" / "settle_batch.py"
    )
    settle = importlib.util.module_from_spec(settle_spec)
    assert settle_spec.loader is not None
    settle_spec.loader.exec_module(settle)
    from grepbit.domain.models import QueryParameter

    sql = (
        "WHERE s.name = %(f_0)s AND d >= %(p1_start_1)s AND n > %(f_2)s "
        "LIMIT %(limit_3)s"
    )
    parameters = [
        QueryParameter(name="f_0", type_name="text", value="O'Reilly"),
        QueryParameter(
            name="p1_start_1",
            type_name="timestamptz",
            value="2026-01-01T00:00:00+08:00",
        ),
        QueryParameter(name="f_2", type_name="numeric", value=1000),
        QueryParameter(name="limit_3", type_name="integer", value=3),
    ]
    assert settle.inline_parameters(sql, parameters) == (
        "WHERE s.name = 'O''Reilly' AND d >= '2026-01-01T00:00:00+08:00'::timestamptz "
        "AND n > 1000 LIMIT 3"
    )
    with pytest.raises(ValueError, match="settle_unbound_placeholder"):
        settle.inline_parameters("x = %(f_9)s", [])


def test_questions_to_cases_strips_numbering_and_blank_lines() -> None:
    spec_q = importlib.util.spec_from_file_location(
        "questions_to_cases", ROOT / "evals" / "questions_to_cases.py"
    )
    module = importlib.util.module_from_spec(spec_q)
    assert spec_q.loader is not None
    spec_q.loader.exec_module(module)
    text = "1. 各門市營業額\n\n  2) 上週每天的交易筆數\n3、退貨率\n退貨金額佔比\n"
    questions = module.parse_questions(text)
    assert questions == ["各門市營業額", "上週每天的交易筆數", "退貨率", "退貨金額佔比"]
    cases = module.build_cases(questions)
    assert cases[0] == {"case_id": "q01", "question": "各門市營業額"}
    assert cases[-1]["case_id"] == "q04"
    assert all("expected" not in c for c in cases)


def test_carry_copies_a_verdict_only_onto_byte_identical_output() -> None:
    carry_spec = importlib.util.spec_from_file_location(
        "carry_verdicts", ROOT / "evals" / "carry_verdicts.py"
    )
    carry = importlib.util.module_from_spec(carry_spec)
    assert carry_spec.loader is not None
    carry_spec.loader.exec_module(carry)

    def row(case_id, sql, status="answered", rows=1):
        return {
            "case_id": case_id,
            "status": status,
            "plan": {"measures": [{"aggregate": "count"}]},
            "sql": sql,
            "row_count": rows,
        }

    judged_report = {
        "results": [
            row("q1", "SELECT 1 AS n"),
            row("q2", "SELECT 2"),
            row("q3", "SELECT 3"),
        ]
    }
    judged = {
        "verdicts": [
            {"case_id": "q1", "verdict": "correct"},
            {"case_id": "q2", "verdict": "correct"},
            {"case_id": "q3", "verdict": "unsure"},
        ]
    }
    new_report = {
        "results": [
            row("q1", "SELECT 1 AS renamed"),
            row("q2", "SELECT 2 WHERE x"),
            row("q3", "SELECT 3"),
        ]
    }
    skeleton = {
        "verdicts": [
            {"case_id": "q1", "verdict": None, "note": ""},
            {"case_id": "q2", "verdict": None, "note": ""},
            {"case_id": "q3", "verdict": None, "note": ""},
        ]
    }
    filled, counts = carry.carry(
        new_report, skeleton, [("run-1.json", judged_report, judged)]
    )
    by_id = {v["case_id"]: v for v in filled["verdicts"]}
    assert by_id["q1"]["verdict"] == "correct"
    assert by_id["q1"]["note"].startswith("carried from run-1.json")
    assert "up to output column names" in by_id["q1"]["note"]
    assert by_id["q2"]["verdict"] is None  # the SQL changed: judge again
    assert by_id["q3"]["verdict"] is None  # unsure is never carried
    assert counts == {"carried": 1, "open": 2}


def test_reference_match_allows_an_extra_related_dimension_but_not_a_measure() -> None:
    from grepbit.domain.plan import QueryPlan

    # owner's decision, 2026-09-11: an extra column that leaves the result
    # unchanged passes; an unrelated one (a measure) or one that changes the
    # rows does not
    plan = QueryPlan.model_validate(
        {
            "base_table": "devices",
            "dimensions": [
                {"table": "devices", "column": "device_id"},
                {"table": "devices", "column": "model"},
            ],
            "measures": [{"aggregate": "count", "alias": "n"}],
        }
    )
    reference = spike.normalize_rows([("AP-300", 2), ("GW-10", 1)])
    rows = [
        {"device_id": "d1", "model": "AP-300", "n": 2},
        {"device_id": "d2", "model": "GW-10", "n": 1},
    ]
    assert spike.match_reference(rows, plan, [reference]) == (0, ["device_id"])
    exact = [{"model": "AP-300", "n": 2}, {"model": "GW-10", "n": 1}]
    assert spike.match_reference(exact, plan, [reference]) == (0, [])
    finer = [
        {"device_id": "d1", "model": "AP-300", "n": 1},
        {"device_id": "d3", "model": "AP-300", "n": 1},
        {"device_id": "d2", "model": "GW-10", "n": 1},
    ]
    assert spike.match_reference(finer, plan, [reference]) == (None, [])
    with_measure = QueryPlan.model_validate(
        {
            "base_table": "devices",
            "dimensions": [{"table": "devices", "column": "model"}],
            "measures": [
                {"aggregate": "count", "alias": "n"},
                {
                    "aggregate": "sum",
                    "column": {"table": "devices", "column": "monthly_fee"},
                    "alias": "fee",
                },
            ],
        }
    )
    rows = [
        {"model": "AP-300", "n": 2, "fee": 10},
        {"model": "GW-10", "n": 1, "fee": 5},
    ]
    assert spike.match_reference(rows, with_measure, [reference]) == (None, [])


def test_stability_compares_plan_cores_across_runs_ignoring_aliases() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "stability", ROOT / "evals" / "stability.py"
    )
    stab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stab)

    def report(rows):
        return {
            "summary": {"cases_file": "x.yaml", "prompt_revision": "v", "model": "m"},
            "results": rows,
        }

    a = report(
        [
            {
                "case_id": "q1",
                "status": "answered",
                "plan": {
                    "base_table": "t",
                    "measures": [{"aggregate": "count", "alias": "n"}],
                    "filters": [],
                },
            },
            {
                "case_id": "q2",
                "status": "answered",
                "plan": {
                    "base_table": "t",
                    "measures": [
                        {"aggregate": "sum", "column": {"table": "t", "column": "x"}}
                    ],
                },
                "correct": True,
            },
        ]
    )
    b = report(
        [
            {
                "case_id": "q1",
                "status": "answered",
                "plan": {
                    "base_table": "t",
                    "measures": [{"aggregate": "count", "alias": "total"}],
                },
            },
            {
                "case_id": "q2",
                "status": "answered",
                "plan": {
                    "base_table": "t",
                    "measures": [
                        {"aggregate": "sum", "column": {"table": "t", "column": "x"}}
                    ],
                    "dimensions": [{"table": "t", "column": "d"}],
                },
                "correct": False,
            },
        ]
    )
    result = stab.stability([a, b])
    assert (
        result["cases"] == 2
        and result["stable_plan"] == 1
        and result["plan_stability"] == 0.5
    )
    [unstable] = result["unstable"]
    assert unstable["case_id"] == "q2" and unstable["differing_keys"] == ["dimensions"]
    assert unstable["correct"] == [True, False]


def test_differential_limit_comparison_respects_order_and_ties() -> None:
    """The reviewer's counterexample: top-1 of {100, 1} returning 1 must not pass."""

    import importlib.util
    from zoneinfo import ZoneInfo

    from grepbit.domain.plan import QueryPlan

    spec = importlib.util.spec_from_file_location(
        "differential", ROOT / "evals" / "differential.py"
    )
    diff = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diff)
    zone = ZoneInfo("Asia/Taipei")
    plan = QueryPlan.model_validate(
        {
            "base_table": "devices",
            "dimensions": [{"table": "devices", "column": "model"}],
            "measures": [{"aggregate": "count", "alias": "n"}],
            "order": [{"field": "n", "direction": "desc"}],
            "limit": 1,
        }
    )
    columns = ["model", "n"]
    reference = [("AP", 100), ("GW", 1)]
    assert diff.compare(plan, columns, [("AP", 100)], reference, zone)
    assert not diff.compare(plan, columns, [("GW", 1)], reference, zone)
    # a duplicated row in place of a missing one fails too
    plan2 = plan.model_copy(update={"limit": 2})
    assert not diff.compare(plan2, columns, [("AP", 100), ("AP", 100)], reference, zone)
    # ties at the boundary may stand in for one another
    tied = [("AP", 5), ("GW", 5), ("SW", 1)]
    assert diff.compare(plan, columns, [("GW", 5)], tied, zone)
    assert diff.compare(plan, columns, [("AP", 5)], tied, zone)
    assert not diff.compare(plan, columns, [("SW", 1)], tied, zone)
    # NULLS LAST when descending: a NULL never wins a top-1
    with_null = [("AP", None), ("GW", 3)]
    assert diff.compare(plan, columns, [("GW", 3)], with_null, zone)
    assert not diff.compare(plan, columns, [("AP", None)], with_null, zone)


def test_differential_redaction_and_replay_rules() -> None:
    """A review found --redact left plan literals in the records and the replay
    had no way to tell a redacted plan from a real one. With sampling off no
    literal comes from the database, so plans stay as they are; a report whose
    plans were scrubbed says so, and its plans are not replayed (the seed is)."""

    spec = importlib.util.spec_from_file_location(
        "differential", ROOT / "evals" / "differential.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.plans_carry_data(0) is False
    assert module.plans_carry_data(20) is True
    plan = {
        "base_table": "t",
        "measures": [{"aggregate": "count", "alias": "n"}],
        "filters": [
            {"column": {"table": "t", "column": "c"}, "op": "in", "values": ["a", "b"]},
            {"column": {"table": "t", "column": "d"}, "op": "is_null", "values": []},
        ],
    }
    scrubbed = module.scrub(plan)
    assert scrubbed["filters"][0]["values"] == ["<redacted>", "<redacted>"]
    assert scrubbed["filters"][1]["values"] == []
    kept, redacted = module.replayable([plan, scrubbed, plan])
    assert kept == [plan, plan] and redacted == 1


def test_generator_literals_are_constants_when_sampling_is_off() -> None:
    """The redaction rule above rests on this: without sample_values every text
    literal the generator draws is one of its own constants."""

    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
    from t0_helpers import iot_schema

    spec = importlib.util.spec_from_file_location(
        "plan_generator", ROOT / "evals" / "plan_generator.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    schema = iot_schema()
    for table in schema.tables:
        for column in table.columns:
            column.sample_values = []
    shape = module.SchemaShape(schema, None)
    seen: list[str] = []

    @settings(max_examples=200, suppress_health_check=list(HealthCheck), deadline=None)
    @given(st.data())
    def draw(data):
        payload = module.draw_plan(data, shape)

        def walk(o):
            if isinstance(o, dict):
                if "values" in o and isinstance(o["values"], list):
                    seen.extend(v for v in o["values"] if isinstance(v, str))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(payload)

    draw()
    assert seen, "the generator drew no text literal at all"
    assert set(seen) <= set(module.FALLBACK_TEXT)
