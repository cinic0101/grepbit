"""Fixed arithmetic and relational traps in the fictional non-POS fixture."""

import json

import duckdb
import yaml
from t0_helpers import ROOT

from grepbit.domain.overlay import SemanticOverlay


def test_service_fixture_is_consistent_and_golden_sql_executes():
    folder = ROOT / "evals/fixtures/service_v1"
    with duckdb.connect() as connection:
        connection.execute("SET TimeZone='Asia/Taipei'")
        connection.execute((folder / "schema.sql").read_text())
        connection.execute((folder / "seed.sql").read_text())
        assert connection.execute("SELECT sum(minutes) FROM work_logs").fetchone() == (
            499,
        )
        assert connection.execute(
            "SELECT sum(estimate_minutes) FROM tickets"
        ).fetchone() == (469,)
        for table, count in {
            "teams": 3,
            "projects": 4,
            "tickets": 8,
            "work_logs": 10,
            "ticket_events": 9,
            "team_links": 2,
        }.items():
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                count,
            )
        cases = yaml.safe_load((ROOT / "evals/cases/tier0/service.yaml").read_text())[
            "cases"
        ]
        assert len(cases) == 24
        rows = {
            case["case_id"]: connection.execute(case["reference_sql"]).fetchall()
            for case in cases
            if "reference_sql" in case
        }
        assert rows["svc_ticket_count"] == [(8,)]
        assert rows["svc_log_count"] == [(10,)]
        assert rows["svc_long_zh_label"] == [(349,)]
        assert rows["svc_long_en_label"] == [(2,)]
        assert rows["svc_prefix_label"] == [(2,)]
        assert rows["svc_long_ja_label"] == [(1,)]
        assert sorted(row[1] for row in rows["svc_month_minutes"]) == [50, 100, 250]
        assert len(rows["svc_north_growth_gap"]) == 2
        assert all(row[2] is None for row in rows["svc_north_growth_gap"])
        assert rows["svc_null_minutes"] == rows["svc_null_work_date"] == [(1,)]
        assert rows["svc_open_tickets"] == [(4,)]
        assert rows["svc_closed_feb"] == [(2,)]
        assert rows["svc_tickets_without_logs"] == [(8, 1)]
        assert sorted(rows["svc_tickets_without_events"]) == [(4, 1), (7, 1), (8, 1)]


def test_service_overlay_has_no_agent_approved_business_metrics():
    overlay = SemanticOverlay.model_validate(
        json.loads((ROOT / "evals/fixtures/service_v1/overlay.json").read_text())
    )
    assert not overlay.metrics and not overlay.segments and not overlay.absent_concepts
    assert {ref.id for ref in overlay.groundable_columns()} == {
        "teams.team_name",
        "projects.project_name",
    }
