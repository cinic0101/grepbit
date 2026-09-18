"""Offline fixture tooling contracts, not product/LLM acceptance."""
from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import fixture


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "learning.sqlite"
        fixture.build(self.db)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(fixture.ROOT / "tools/fixture.py"), *map(str, args)],
            cwd=fixture.ROOT, capture_output=True, text=True, timeout=15,
        )

    def test_fresh_fixture_report(self):
        report = fixture.check(self.db)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["reference_sql_checks"], 18)
        self.assertEqual(len(report["behavioral_cases_not_implemented"]), 12)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertEqual(len(report["provenance"]["source_sha256"]), 64)

    def test_all_tables_and_rows_are_synthetic_seed(self):
        with closing(fixture.readonly(self.db)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall()
            self.assertEqual({r[0] for r in tables}, set(fixture.TABLES))
            self.assertEqual(sum(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                                 for t in fixture.TABLES), 88)
            for table, rows in fixture.load(fixture.FIXTURE / "seed.json").items():
                self.assertCountEqual(conn.execute(f'SELECT * FROM "{table}"').fetchall(),
                                      [tuple(row) for row in rows])

    def test_builder_never_overwrites(self):
        before = self.db.read_bytes()
        with self.assertRaises(FileExistsError):
            fixture.build(self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_builder_cleans_partial_failure(self):
        path = self.root / "failed.sqlite"
        with patch.object(fixture, "populate", side_effect=ValueError("bad seed")):
            with self.assertRaises(ValueError):
                fixture.build(path)
        self.assertFalse(path.exists())

    def test_readonly_and_uri_special_characters(self):
        special = self.root / "space # question ?.sqlite"
        fixture.build(special)
        with closing(fixture.readonly(special)) as conn:
            fixture.reject_write(conn)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DROP TABLE centers")

    def test_missing_database_not_created(self):
        missing = self.root / "missing.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            fixture.readonly(missing)
        self.assertFalse(missing.exists())

    def test_strict_types_and_same_center_constraints(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE booking_items SET seats='unknown' WHERE item_id='I01'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE booking_items SET center_id='CZ' WHERE item_id='I01'")

    def test_failed_reference_is_reported_without_stopping_suite(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("UPDATE payments SET amount_minor=amount_minor+1 WHERE payment_id='P01'")
            conn.commit()
        report = fixture.check(self.db)
        self.assertEqual(report["status"], "failed")
        self.assertGreater(report["counts"].get("failed", 0), 0)
        self.assertIn("sum_distinct", [r["id"] for r in report["results"]])

    def test_checks_make_no_socket_connections(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            self.assertEqual(fixture.check(self.db)["status"], "passed")

    def test_case_catalog_duplicate_ids_rejected(self):
        cases = fixture.load(fixture.CASES)
        cases["cases"].append(dict(cases["cases"][0]))
        copy = self.root / "cases.json"
        copy.write_text(json.dumps(cases), encoding="utf-8")
        with patch.object(fixture, "CASES", copy):
            with self.assertRaises(AssertionError):
                fixture.catalog_check()

    def test_target_codes_do_not_confuse_entity_ids(self):
        with closing(fixture.readonly(self.db)) as conn:
            rows = conn.execute("SELECT c.code,t.target_minor FROM centers c LEFT JOIN monthly_targets t "
                                "ON c.center_id=t.center_id ORDER BY c.code").fetchall()
            self.assertIn(("CTR-B01", 0), rows)
            self.assertIn(("CTR-Z01", None), rows)

    def test_report_is_exclusive_and_failed_cli_is_nonzero(self):
        report = self.root / "run.json"
        self.assertEqual(self.cli("check", "--db", self.db, "--report", report).returncode, 0)
        before = report.read_bytes()
        self.assertNotEqual(self.cli("check", "--db", self.db, "--report", report).returncode, 0)
        self.assertEqual(report.read_bytes(), before)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("UPDATE payments SET amount_minor=1 WHERE payment_id='P01'")
            conn.commit()
        failed = self.root / "failed.json"
        self.assertNotEqual(self.cli("check", "--db", self.db, "--report", failed).returncode, 0)
        self.assertEqual(json.loads(failed.read_text())["status"], "failed")

    def test_incomplete_report_is_not_a_success(self):
        report = self.root / "incomplete.json"
        self.assertNotEqual(self.cli("check", "--db", self.root / "missing.sqlite", "--report", report).returncode, 0)
        self.assertEqual(json.loads(report.read_text())["status"], "incomplete")

    def test_report_on_build_is_rejected(self):
        self.assertNotEqual(self.cli("build", "--db", self.root / "x.sqlite", "--report", self.root / "x.json").returncode, 0)
        self.assertFalse((self.root / "x.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
