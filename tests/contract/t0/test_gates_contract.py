"""Deterministic gates: unsupported shapes (language pack) and literal existence."""

from __future__ import annotations

import glob

import yaml
from t0_helpers import ROOT, col, iot_schema

from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.postgres.value_check import missing_literals
from grepbit.application.literals import LiteralCheck, text_literal_checks
from grepbit.application.shapes import match_unsupported_shape
from grepbit.domain.plan import QueryPlan
from grepbit.domain.schema_model import ColumnKind

PACK = load_shape_pack()


def test_shape_pack_no_longer_refuses_share_or_growth_questions() -> None:
    # v3: shares, ratios and growth are algebra now; the pack keeps only the
    # per-period words for the single-window gate.
    for question in (
        "各付款方式的收款佔比",
        "Revenue growth year over year",
        "前年比の売上",
    ):
        assert match_unsupported_shape(question, PACK) is None
    assert PACK.shapes == [] and PACK.period_words


def test_default_pack_is_valid_and_covers_the_case_sets_refusal_probes() -> None:
    assert PACK.revision.startswith("unsupported-shapes-")
    # Every case that the pack refuses must accept `unsupported`: a hit on an
    # answerable case would be an over-refusal and must show up here.
    hits = []
    for path in sorted(glob.glob(str(ROOT / "evals" / "cases" / "tier0" / "*.yaml"))):
        document = yaml.safe_load(open(path, encoding="utf-8"))
        for case in document["cases"]:
            if "expected" not in case:
                continue  # judged cases (real questions) carry no expectation
            if match_unsupported_shape(case["question"], PACK) is not None:
                accepted = case.get("accept_statuses") or [case["expected"]["status"]]
                assert "unsupported" in accepted, (path, case["case_id"])
                hits.append(case["case_id"])
    assert hits == []  # nothing is refused by shape any more


def _schema_with_enum():
    schema = iot_schema()
    devices = schema.table("devices")
    channel = col(
        "channel",
        ColumnKind.TEXT,
        data_type="channel_t",
        sample_values=["email", "sms"],
        is_enum=True,
    )
    devices = devices.model_copy(update={"columns": [*devices.columns, channel]})
    return schema.model_copy(
        update={
            "tables": [devices if t.name == "devices" else t for t in schema.tables]
        }
    )


def test_literal_checks_take_eq_and_in_text_literals_only() -> None:
    plan = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "in",
                    "values": ["critical", "warning"],
                },
                {
                    "column": {"table": "devices", "column": "channel"},
                    "op": "eq",
                    "values": ["fax"],
                },
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "ne",
                    "values": ["offline"],
                },
                {
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                    "op": "gt",
                    "values": [10],
                },
                {
                    "column": {"table": "devices", "column": "is_managed"},
                    "op": "eq",
                    "values": [True],
                },
                {
                    "column": {"table": "alerts", "column": "resolved_at"},
                    "op": "is_null",
                },
            ],
        }
    )
    assert text_literal_checks(plan, _schema_with_enum()) == [
        LiteralCheck(table="alerts", column="severity", value="critical"),
        LiteralCheck(table="alerts", column="severity", value="warning"),
        LiteralCheck(table="devices", column="channel", value="fax", is_enum=True),
    ]


class _Connection:
    """Answers EXISTS queries from a set of present values; records the SQL."""

    def __init__(self, present: set[str]) -> None:
        self.present = present
        self.queries: list[tuple[str, tuple]] = []
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        text = query if isinstance(query, str) else query.as_string(None)
        self.queries.append((text, params))

        class _Result:
            def fetchone(inner):
                return (params[0] in self.present,)

        return _Result()

    def rollback(self):
        self.rolled_back = True


def test_missing_literals_binds_each_value_and_casts_enums_to_text() -> None:
    connection = _Connection(present={"critical"})
    checks = [
        LiteralCheck(table="alerts", column="severity", value="critical"),
        LiteralCheck(table="alerts", column="severity", value="crit"),
        LiteralCheck(table="devices", column="channel", value="fax", is_enum=True),
    ]
    misses = missing_literals(lambda: connection, "public", checks)
    assert [m.value for m in misses] == ["crit", "fax"]
    exists_queries = [q for q in connection.queries if q[0].startswith("SELECT EXISTS")]
    assert [q[1] for q in exists_queries] == [("critical",), ("crit",), ("fax",)]
    assert (
        exists_queries[0][0] == 'SELECT EXISTS (SELECT 1 FROM "public"."alerts" '
        'WHERE "alerts"."severity" = %s)'
    )
    assert '"devices"."channel"::text = %s' in exists_queries[2][0]
    assert connection.queries[0][0] == "BEGIN READ ONLY"
    assert "statement_timeout" in connection.queries[1][0]
    assert connection.rolled_back
    # no literal, no connection at all
    assert missing_literals(lambda: 1 / 0, "public", []) == []


def test_per_period_word_with_a_single_current_window_is_a_misread() -> None:
    from grepbit.application.shapes import single_period_misread

    today_only = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "relative", "unit": "day", "offset": 0, "length": 1},
                "grain": "day",
            },
        }
    )
    assert single_period_misread("每天的告警數是多少？", today_only, PACK) == "每天"
    assert single_period_misread("Daily alert count", today_only, PACK) == "daily"
    # the same plan is right for a question about today
    assert single_period_misread("今天的告警數是多少？", today_only, PACK) is None
    # a per-period question with a real range or no window is fine
    last_month_by_day = today_only.model_copy(
        update={
            "time": today_only.time.model_copy(
                update={
                    "scope": {"kind": "relative", "unit": "month", "offset": -1},
                }
            )
        }
    )
    assert single_period_misread("上個月每天的告警數", last_month_by_day, PACK) is None
    no_window = today_only.model_copy(update={"time": None})
    assert single_period_misread("每天的告警數", no_window, PACK) is None
    assert PACK.period_words and PACK.period_clarification


def test_a_grain_nobody_asked_for_is_dropped_but_period_words_keep_it() -> None:
    from grepbit.adapters.language_pack_store import load_shape_pack
    from grepbit.application.shapes import drop_grain, unrequested_grain

    pack = load_shape_pack()
    bucketed = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count", "share_of_total": True}],
            "dimensions": [{"table": "devices", "column": "model"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
            },
        }
    )
    assert (
        unrequested_grain("各機型的告警數占同期全部告警的比例", bucketed, pack)
        == "month"
    )
    assert unrequested_grain("各機型每月的告警數占比", bucketed, pack) is None
    assert unrequested_grain("各機型告警數的趨勢", bucketed, pack) is None
    assert (
        unrequested_grain("alert share by model, month by month", bucketed, pack)
        is None
    )
    windowed = QueryPlan.model_validate(
        {
            **bucketed.model_dump(mode="json", exclude_none=True),
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "grain": "month",
                "scope": {
                    "kind": "relative",
                    "unit": "month",
                    "offset": -3,
                    "length": 3,
                },
            },
        }
    )
    assert unrequested_grain("各機型的告警數占比", windowed, pack) is None
    dropped = drop_grain(bucketed)
    assert dropped.time is None  # a column-only time spec constrains nothing
    kept = drop_grain(windowed)
    assert (
        kept.time is not None
        and kept.time.grain is None
        and kept.time.scope is not None
    )
