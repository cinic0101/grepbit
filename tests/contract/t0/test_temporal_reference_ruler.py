"""Research specification only; no temporal-reference adapter is implemented.

Static shape/span assertions specify the proposed boundary. Existing production
conversion and SQL run independently against hand-written calendar witnesses.
No live harness imports these test-only types or gold data.
"""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from test_period_semantics_ruler import _postgres_rows, _rows, _schema

from evals.synthetic import DuckInstance
from grepbit.adapters.litellm.plan_client import repair_column_refs
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind

AS_OF = datetime.fromisoformat("2026-02-10T12:00:00+08:00")
COLUMN = {"table": "events", "column": "occurred_at"}


class ReferenceTimeSpec(BaseModel):
    """Only an output-shape ruler, not catalog resolution or intent validation."""

    model_config = ConfigDict(extra="forbid", strict=True)
    column: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")
    scope_ref: str = Field(min_length=1)
    grain: str | None = Field(default=None, pattern="^(day|week|month|quarter|year)$")


@pytest.mark.parametrize("grain", [None, "day", "week", "month", "quarter", "year"])
def test_reference_shape_preserves_independent_column_and_grain(grain):
    data = {"column": "events.occurred_at", "scope_ref": "t0", "grain": grain}
    assert ReferenceTimeSpec.model_validate(data).model_dump() == data


@pytest.mark.parametrize(
    "patch",
    [
        {
            "scope": {
                "kind": "range",
                "start": "2025-01-01",
                "end_exclusive": "2060-01-01",
            }
        },
        {"scope": {"kind": "relative", "unit": "year", "offset": 0, "length": 1}},
        {"start": "2025-01-01"},
        {"end_exclusive": "2060-01-01"},
        {"scope_ref": ""},
        {"scope_ref": 0},
        {"scope_ref": ["t0", "t1"]},
        {"grain": "season"},
        {"timezone": "UTC"},
        {"as_of": "2060-01-01"},
    ],
)
def test_reference_shape_has_no_second_calendar_authority(patch):
    with pytest.raises(ValidationError):
        ReferenceTimeSpec.model_validate(
            {"column": "events.occurred_at", "scope_ref": "t0", **patch}
        )


@pytest.mark.parametrize(
    ("question", "text", "occurrence", "start", "end"),
    [
        ("2025年每季的薪資總額", "2025", 0, 0, 4),
        ("Total payroll for each quarter of 2025", "2025", 0, 34, 38),
        ("2025年の四半期ごとの給与総額", "2025", 0, 0, 4),
        ("2025型裝置在2025年的告警數", "2025", 1, 8, 12),
        ("比較2024與2025年的告警數", "2024", 0, 2, 6),
        ("比較2024與2025年的告警數", "2025", 0, 7, 11),
        ("📅 2024年2月的告警數", "2024年2月", 0, 2, 9),
        ("Alerts in February 2024", "February 2024", 0, 10, 23),
    ],
)
def test_exact_occurrence_vectors_do_not_select_a_semantic_role(
    question, text, occurrence, start, end
):
    # Independent specification enumeration, not a runtime locator function.
    positions = [i for i in range(len(question)) if question.startswith(text, i)]
    assert question[start:end] == text
    assert positions[occurrence] == start


def test_current_domain_does_not_silently_accept_proposed_reference_field():
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(
            {
                "base_table": "events",
                "measures": [{"aggregate": "count"}],
                "time": {"column": COLUMN, "scope_ref": "t0", "grain": "quarter"},
            }
        )


# literal, timezone, hand-written start/end, just-before-start, last-inside
BOUNDARIES = [
    ("2025", "Asia/Taipei", "2025-01-01", "2026-01-01", "2024-12-31", "2025-12-31"),
    ("2024", "Asia/Taipei", "2024-01-01", "2025-01-01", "2023-12-31", "2024-12-31"),
    ("2024-02", "Asia/Taipei", "2024-02-01", "2024-03-01", "2024-01-31", "2024-02-29"),
    ("2025-02", "Asia/Taipei", "2025-02-01", "2025-03-01", "2025-01-31", "2025-02-28"),
    ("2025-12", "Asia/Taipei", "2025-12-01", "2026-01-01", "2025-11-30", "2025-12-31"),
    ("2026-01", "Asia/Taipei", "2026-01-01", "2026-02-01", "2025-12-31", "2026-01-31"),
    (
        "2025-03",
        "America/New_York",
        "2025-03-01",
        "2025-04-01",
        "2025-02-28",
        "2025-03-31",
    ),
    (
        "2025-11",
        "America/New_York",
        "2025-11-01",
        "2025-12-01",
        "2025-10-31",
        "2025-11-30",
    ),
]


def _existing_conversion(literal, kind, zone, grain=None):
    schema = _schema(kind, zone)
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "events",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "events", "column": "amount"},
                    "alias": "total",
                }
            ],
            "filters": [{"column": COLUMN, "op": "eq", "values": [literal]}],
            "time": {"column": COLUMN, **({"grain": grain} if grain else {})},
        },
    }
    normalized, _ = repair_column_refs(deepcopy(payload), schema)
    plan = QueryPlan.model_validate(normalized["plan"])
    return schema, plan, PlanCompiler(schema).compile(plan, as_of=AS_OF)


ENGINES = ["duckdb"]
if os.environ.get("GREPBIT_PERIOD_RULER_DSN_ENV"):
    ENGINES += ["postgres_UTC", "postgres_America/Los_Angeles"]


@pytest.mark.parametrize("case", BOUNDARIES, ids=lambda c: f"{c[0]}-{c[1]}")
@pytest.mark.parametrize("kind", [ColumnKind.DATE, ColumnKind.TIMESTAMP])
@pytest.mark.parametrize("engine", ENGINES)
def test_existing_literal_conversion_matches_independent_boundary_witnesses(
    case, kind, engine
):
    literal, zone, start, end, before, inside = case
    schema, plan, compiled = _existing_conversion(literal, kind, zone)
    assert not plan.filters
    assert [
        (p.start.date().isoformat(), p.end_exclusive.date().isoformat())
        for p in compiled.periods
    ] == [(start, end)]
    if kind == ColumnKind.TIMESTAMP:
        before += "T23:59:59.999999"
        inside += "T23:59:59.999999"
    # Distinct powers expose each inclusion error, including NULL-time leakage.
    rows = _rows(
        [
            (before, 1, "x"),
            (start, 2, "x"),
            (inside, 4, "x"),
            (end, 8, "x"),
            (None, 16, "x"),
        ],
        kind,
        zone,
    )
    if engine.startswith("postgres_"):
        result = _postgres_rows(
            compiled.compiled, rows, kind, engine.removeprefix("postgres_")
        )
        assert len(result) == 1 and result[0]["total"] == 6
    else:
        instance = DuckInstance(schema, {"events": rows})
        try:
            _, values = instance.execute(compiled.compiled)
            assert values == [(6,)]
        finally:
            instance.con.close()


@pytest.mark.parametrize("grain", ["month", "quarter", "year"])
def test_existing_year_conversion_retains_requested_grain(grain):
    _, plan, compiled = _existing_conversion(
        "2025", ColumnKind.DATE, "Asia/Taipei", grain
    )
    assert plan.time.grain.value == grain
    assert compiled.periods[0].end_exclusive.date().isoformat() == "2026-01-01"


def test_matching_a_source_year_does_not_prove_the_correct_occurrence():
    question = "2024型裝置在2025年的告警數"
    # Both are authentic substrings. A binder alone cannot reject the wrong
    # model-year selection; the semantic gold, not ID validity, distinguishes it.
    assert question[0:4] == "2024" and question[8:12] == "2025"
    assert (
        _existing_conversion("2024", ColumnKind.DATE, "Asia/Taipei")[2].periods
        != _existing_conversion("2025", ColumnKind.DATE, "Asia/Taipei")[2].periods
    )
