"""Compatibility rulers for the narrow candidate, not an intent oracle."""

import json

import pytest
from t0_helpers import iot_schema
from test_temporal_repair_study import draft, fixed

from evals.temporal_repair_study import temporal_repair_audit
from grepbit.domain.plan import QueryPlan


def run(before, after, storage="timestamp with time zone", zone="Asia/Taipei"):
    schema = iot_schema()
    schema.business_timezone = zone
    schema.table("alerts").column("raised_at").data_type = storage
    return temporal_repair_audit(
        json.dumps(before), QueryPlan.model_validate(after), schema
    )


@pytest.mark.parametrize(
    "storage", ["timestamp with time zone", "timestamp without time zone"]
)
@pytest.mark.parametrize("location", ["plan", "without"])
def test_naive_anchors_follow_approved_source_policy(storage, location):
    before, after = draft(), fixed()
    for k in ("start", "end_exclusive"):
        before["plan"]["time"]["scope"][k] = before["plan"]["time"]["scope"][k][:-6]
    for f in after["filters"]:
        f["values"][0] = f["values"][0][:-6]
    if location == "without":
        before["plan"]["base_table"] = after["base_table"] = "devices"
        before["plan"]["without"] = {
            "table": "alerts",
            "time": before["plan"].pop("time"),
        }
        after.pop("time")
        after["without"] = {"table": "alerts", "filters": after.pop("filters")}
    assert run(before, after, storage) == "preserved"


def test_naive_business_instant_and_explicit_offset_are_equivalent():
    before = draft()
    before["plan"]["time"]["scope"]["end_exclusive"] = "2026-07-08T12:00:00"
    assert run(before, fixed()) == "preserved"


def test_offset_on_unbound_clock_source_is_unverifiable_not_preserved():
    assert run(draft(), fixed(), "timestamp without time zone") == "unverifiable"


@pytest.mark.parametrize("literal", ["2026-03-08T02:30:00", "2026-11-01T01:30:00"])
def test_dst_unresolved_draft_is_not_a_confirmed_changed_repair(literal):
    before = draft()
    before["plan"]["time"]["scope"]["end_exclusive"] = literal
    assert run(before, fixed(), zone="America/New_York") == "unverifiable"


def test_unresolved_repaired_value_is_not_a_confirmed_change():
    after = fixed()
    after["filters"][1]["values"] = ["2026-11-01T01:30:00"]
    assert run(draft(), after, zone="America/New_York") == "unverifiable"


def test_clock_midnight_calendar_repair_preserves_clock_not_instant():
    before, after = draft(), fixed()
    before["plan"]["time"]["scope"].update(
        start="2026-07-01T00:00:00", end_exclusive="2026-07-09T00:00:00"
    )
    after["filters"] = []
    after["time"]["scope"] = {
        "kind": "range",
        "start": "2026-07-01",
        "end_exclusive": "2026-07-09",
    }
    assert run(before, after, "timestamp without time zone") == "preserved"


@pytest.mark.parametrize(
    "storage", ["timestamp with time zone", "timestamp without time zone"]
)
def test_date_only_filter_midnight_is_a_legal_repair(storage):
    before, after = draft(), fixed()
    before["plan"]["time"]["scope"].update(
        start="2026-07-01T00:00:00", end_exclusive="2026-07-09T00:00:00"
    )
    after["filters"][0]["values"] = ["2026-07-01"]
    after["filters"][1]["values"] = ["2026-07-09"]
    assert run(before, after, storage) == "preserved"


@pytest.mark.parametrize("kind", ["clock", "instant"])
def test_naive_noon_to_midnight_is_confirmed_changed(kind):
    before, after = draft(), fixed()
    for key in ("start", "end_exclusive"):
        before["plan"]["time"]["scope"][key] = before["plan"]["time"]["scope"][key][:-6]
    for f in after["filters"]:
        f["values"][0] = f["values"][0][:-6]
    after["filters"][1]["values"] = ["2026-07-08T00:00:00"]
    typ = (
        "timestamp without time zone" if kind == "clock" else "timestamp with time zone"
    )
    assert run(before, after, typ) == "changed"


def test_unknown_physical_type_does_not_get_an_instant_default():
    assert run(draft(), fixed(), "unknown_timestamp") == "unverifiable"


def test_out_of_representable_utc_range_is_unverifiable_not_an_exception():
    before = draft()
    before["plan"]["time"]["scope"]["start"] = "0001-01-01T00:00:00+14:00"
    assert run(before, fixed()) == "unverifiable"


def test_non_timestamp_column_is_not_certified_by_offset_spelling():
    before, after = draft(), fixed()
    before["plan"]["time"]["column"] = "alerts.severity"
    for f in after["filters"]:
        f["column"]["column"] = "severity"
    after.pop("time")
    assert run(before, after) == "unverifiable"
