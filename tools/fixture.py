#!/usr/bin/env python3
"""Offline LearningOps fixture checks; NOT the Grepbit runtime or an LLM eval.

Python 3.11+, SQLite 3.37+. Standard library only. No network or credentials.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/fixtures/learningops"
CASES = ROOT / "evals/cases/learningops.json"
ORACLES = ROOT / "evals/oracles/learningops.json"
START = "2026-02-28T16:00:00Z"
END = "2026-03-31T16:00:00Z"
TABLES = (
    "centers", "learners", "courses", "sessions", "bookings",
    "booking_items", "payments", "refunds", "attendance", "monthly_targets",
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def populate(conn: sqlite3.Connection) -> None:
    """Load trusted, reviewed fixture sources, never model-authored SQL."""
    rows_by_table = load(FIXTURE / "seed.json")
    if set(rows_by_table) != set(TABLES):
        raise ValueError("Unexpected seed table set")
    conn.executescript((FIXTURE / "schema.sql").read_text(encoding="utf-8"))
    for table in TABLES:
        rows = rows_by_table[table]
        if rows:
            marks = ",".join("?" for _ in rows[0])
            conn.executemany(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    conn.commit()


def build(path: Path) -> None:
    if sqlite3.sqlite_version_info < (3, 37):
        raise RuntimeError("SQLite 3.37+ is required for STRICT tables")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.open("xb").close()  # Refuse overwrite, including existing symlinks.
    try:
        with closing(sqlite3.connect(path)) as conn:
            populate(conn)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def equal(actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def reject_write(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("UPDATE centers SET name='tampered' WHERE center_id='CA'")
    except sqlite3.OperationalError:
        return
    raise AssertionError("Read-only connection accepted a write")


def python_ledger(conn: sqlite3.Connection) -> None:
    bookings = {r[0]: r for r in conn.execute("SELECT * FROM bookings")}
    cohort = {k for k, b in bookings.items() if b[4] == "confirmed" and START <= b[3] < END}
    items = list(conn.execute("SELECT * FROM booking_items"))
    equal((
        sum(i[4] * i[5] - i[6] for i in items if i[1] in cohort),
        sum(i[4] for i in items if i[1] in cohort),
        len(cohort),
        len({bookings[k][2] for k in cohort if bookings[k][2] is not None}),
    ), (158000, 12, 7, 5))


def variant(name: str, refs: dict[str, dict[str, Any]]) -> None:
    # Separate throwaway instance; never mutate the inspected database.
    with closing(sqlite3.connect(":memory:")) as conn:
        populate(conn)

        def scalar(sql: str) -> Any:
            return conn.execute(sql, {"start": START, "end": END}).fetchone()[0]

        amount_sql = refs["Q01_booked_amount"]["sql"]
        if name == "split_payment":
            cash_sql = refs["Q06_cash_received"]["sql"]
            before = scalar(cash_sql)
            conn.execute("UPDATE payments SET amount_minor=4000 WHERE payment_id='P01'")
            conn.execute("INSERT INTO payments VALUES ('PX','B01','2026-03-01T03:00:00Z','succeeded',6000)")
            equal(scalar(cash_sql), before)
            equal(scalar(amount_sql), 158000)
        elif name == "fanout":
            bad = """SELECT SUM(i.seats*i.unit_price_minor-i.discount_minor)
              FROM bookings b JOIN booking_items i ON b.booking_id=i.booking_id
              JOIN payments p ON b.booking_id=p.booking_id
              WHERE b.status='confirmed' AND p.status='succeeded'
              AND b.created_at_utc>=:start AND b.created_at_utc<:end"""
            if scalar(bad) == 158000:
                raise AssertionError("Fixture did not distinguish fan-out")
        elif name == "refund_period":
            conn.execute("UPDATE refunds SET posted_at_utc='2026-04-03T06:00:00Z' WHERE refund_id='R1'")
            equal(scalar(refs["Q07_posted_refunds"]["sql"]), 15000)
        elif name == "sum_distinct":
            bad = """SELECT SUM(DISTINCT i.seats*i.unit_price_minor-i.discount_minor)
              FROM bookings b JOIN booking_items i ON b.booking_id=i.booking_id
              WHERE b.status='confirmed' AND b.created_at_utc>=:start
              AND b.created_at_utc<:end"""
            if scalar(bad) == 158000:
                raise AssertionError("Fixture did not distinguish SUM(DISTINCT)")
        else:
            raise ValueError(f"Unknown variant: {name}")


def catalog_check() -> None:
    cases = load(CASES)["cases"]
    refs = load(ORACLES)
    case_ids, ref_ids = [c["id"] for c in cases], [r["id"] for r in refs]
    equal(len(set(case_ids)), len(case_ids))
    equal(len(set(ref_ids)), len(ref_ids))
    equal({c["reference_id"] for c in cases if "reference_id" in c}, set(ref_ids))
    for case in cases:
        if "reference_id" not in case and not case.get("expected_behavior"):
            raise ValueError("Behavioral case lacks an expectation")


def provenance() -> dict[str, Any]:
    paths = [FIXTURE / n for n in ("schema.sql", "seed.json", "README.md")]
    paths += [CASES, ORACLES, Path(__file__).resolve()]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    commit, dirty = None, None
    try:
        # Do not attribute an enclosing, unrelated repository to this fixture.
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                             capture_output=True, text=True, check=True, timeout=5)
        if Path(top.stdout.strip()).resolve() == ROOT:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                    capture_output=True, text=True, check=True, timeout=5).stdout.strip()
            dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                        capture_output=True, text=True, check=True, timeout=5).stdout)
    except (OSError, subprocess.SubprocessError):
        pass
    return {"git_commit": commit, "worktree_dirty": dirty,
            "source_sha256": identity, "files_sha256": hashes}


def check(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    results: list[dict[str, str]] = []

    def record(name: str, family: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            results.append({"id": name, "family": family, "status": "passed"})
        except (AssertionError, ValueError, KeyError, sqlite3.Error) as exc:
            # Synthetic fixture diagnostics only. Never reuse as a live log policy.
            results.append({"id": name, "family": family, "status": "failed", "detail": str(exc)})

    record("case_catalog", "fixture", catalog_check)
    references = load(ORACLES)
    with closing(readonly(path)) as conn:
        record("integrity", "fixture", lambda: equal(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)]))
        record("foreign_keys", "fixture", lambda: equal(conn.execute("PRAGMA foreign_key_check").fetchall(), []))
        for ref in references:
            def run(ref: dict[str, Any] = ref) -> None:
                actual = [list(r) for r in conn.execute(ref["sql"], ref.get("params", {}))]
                equal(actual, ref["expected"])
            record(ref["id"], "reference_sql", run)
        record("python_ledger", "fixture", lambda: python_ledger(conn))
        record("readonly_write_rejected", "fixture", lambda: reject_write(conn))
    refs = {r["id"]: r for r in references}
    for name in ("split_payment", "fanout", "refund_period", "sum_distinct"):
        record(name, "fixture", lambda name=name: variant(name, refs))
    cases = load(CASES)
    pending = [c["id"] for c in cases["cases"] if "reference_id" not in c]
    return {
        "report_version": "fixture-check-v1", "fixture": cases["fixture"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(r["status"] == "passed" for r in results) else "failed",
        "provenance": provenance(),
        "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "python_version": sys.version.split()[0], "sqlite_version": sqlite3.sqlite_version,
        "as_of_utc": cases["as_of_utc"], "business_timezone": cases["timezone"],
        "counts": dict(Counter(r["status"] for r in results)),
        "reference_sql_checks": len(references), "fixture_mechanism_checks": len(results) - len(references),
        "behavioral_cases_not_implemented": pending,
        "live_model_attempts": 0, "results": results,
        "duration_seconds": round(time.perf_counter() - started, 6),
        "scope": "Fixture/reference mechanics only; no Grepbit runtime, LLM, PostgreSQL, or product acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Exclusive-create JSON output; check only")
    args = parser.parse_args()
    if args.report and args.command != "check":
        parser.error("--report is only valid for check")
    try:
        if args.command == "build":
            build(args.db)
            print("Built synthetic LearningOps fixture")
            return 0
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            # Reserve output before testing; interrupted runs cannot overwrite prior evidence.
            with args.report.open("x", encoding="utf-8") as out:
                out.write('{"status":"incomplete"}\n')
                out.flush()
                report = check(args.db)
                out.seek(0)
                out.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                out.truncate()
        else:
            report = check(args.db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "passed" else 1
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
