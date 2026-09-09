"""Tier-0 spike runner helpers: row normalization and the unsafe language pack."""

from __future__ import annotations

import importlib.util
from datetime import date, datetime
from decimal import Decimal

import pytest
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
