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
