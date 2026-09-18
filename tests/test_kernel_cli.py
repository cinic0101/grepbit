"""Offline subprocess contracts for exclusive-create kernel JSON input/output."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tools import fixture


class KernelCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "learning.sqlite"
        fixture.build(self.db)
        self.request_path = self.root / "request.json"
        self.data = {
            "metrics": [
                "confirmed_booked_amount", "confirmed_booking_count",
                "booked_seats", "known_booking_accounts",
            ],
            "start": "2026-03-01T00:00:00+08:00",
            "end": "2026-04-01T00:00:00+08:00",
            "timezone": "Asia/Taipei",
        }
        self.request_path.write_text(json.dumps(self.data), encoding="utf-8")
        self.attempt = 0

    def cli(self, *, raw=None, database=None, output=None):
        if raw is not None:
            self.request_path.write_bytes(raw if isinstance(raw, bytes) else raw.encode("utf-8"))
        if output is None:
            output = self.root / f"result-{self.attempt}.json"
        self.attempt += 1
        result = subprocess.run(
            [
                sys.executable, "-m", "grepbit", "--db", str(database or self.db),
                "--request", str(self.request_path), "--output", str(output),
            ],
            cwd=fixture.ROOT, capture_output=True, text=True, timeout=15,
        )
        return result, output

    def assert_failure(self, result, output, code):
        self.assertNotEqual(result.returncode, 0)
        evidence = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["error"]["code"], code)
        self.assertIsInstance(evidence["error"]["message"], str)
        self.assertTrue(evidence["error"]["message"])
        self.assertNotIn("facts", evidence)
        self.assertEqual(json.loads(result.stderr), evidence)
        return evidence

    def test_success_writes_complete_json_pack_without_changing_inputs(self):
        database_before = self.db.read_bytes()
        request_before = self.request_path.read_bytes()
        result, output = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        pack = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(pack["status"], "complete")
        self.assertEqual({fact["metric_id"]: fact["value"] for fact in pack["facts"]}, {
            "confirmed_booked_amount": 158000,
            "confirmed_booking_count": 7,
            "booked_seats": 12,
            "known_booking_accounts": 5,
        })
        self.assertTrue(all(fact["completeness"] == "complete" for fact in pack["facts"]))
        self.assertEqual(pack["request"]["metrics"], self.data["metrics"])
        self.assertEqual(pack["request"]["timezone"], "Asia/Taipei")
        self.assertEqual(self.db.read_bytes(), database_before)
        self.assertEqual(self.request_path.read_bytes(), request_before)

    def test_existing_outputs_database_and_request_are_never_overwritten(self):
        existing = self.root / "existing.json"
        existing.write_bytes(b'{"previous":"evidence"}\n')
        for output in (existing, self.db, self.request_path):
            with self.subTest(output=output.name):
                before = output.read_bytes()
                result, _ = self.cli(output=output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_bytes(), before)
                failure = json.loads(result.stderr)
                self.assertEqual(failure["status"], "failed")
                self.assertEqual(failure["error"]["code"], "file_error")
                self.assertNotIn("facts", failure)

    def test_output_symlinks_cannot_overwrite_or_create_their_targets(self):
        existing = self.root / "target.json"
        existing.write_bytes(b"preserve me")
        missing = self.root / "missing-target.json"
        for index, target in enumerate((existing, missing)):
            with self.subTest(target=target.name):
                link = self.root / f"output-link-{index}.json"
                link.symlink_to(target)
                result, _ = self.cli(output=link)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "file_error")
                self.assertTrue(link.is_symlink())
        self.assertEqual(existing.read_bytes(), b"preserve me")
        self.assertFalse(missing.exists())

    def test_duplicate_json_keys_are_rejected_even_with_identical_values(self):
        original = json.dumps(self.data)
        for duplicate in ('"timezone":"Asia/Taipei"', '"metrics":["booked_seats"]'):
            with self.subTest(duplicate=duplicate):
                raw = original[:-1] + "," + duplicate + "}"
                result, output = self.cli(raw=raw)
                self.assert_failure(result, output, "invalid_request")

    def test_malformed_json_and_non_object_json_are_structured_failures(self):
        for raw in ("{", "", "[]", "null", "1", '"request"', '{"metrics":NaN}'):
            with self.subTest(raw=raw):
                result, output = self.cli(raw=raw)
                self.assert_failure(result, output, "invalid_request")

    def test_invalid_utf8_and_utf16_or_utf32_auto_detection_are_rejected(self):
        text = json.dumps(self.data)
        encodings = (
            b"\xff", text.encode("utf-16"), text.encode("utf-16-le"),
            text.encode("utf-32"), text.encode("utf-32-le"),
        )
        for index, raw in enumerate(encodings):
            with self.subTest(encoding=index):
                result, output = self.cli(raw=raw)
                self.assert_failure(result, output, "invalid_request")

    def test_valid_json_at_exact_16384_byte_limit_is_accepted(self):
        raw = json.dumps(self.data).encode("utf-8")
        raw += b" " * (16384 - len(raw))
        self.assertEqual(len(raw), 16384)
        result, output = self.cli(raw=raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "complete")

    def test_valid_json_one_byte_over_limit_is_rejected(self):
        raw = json.dumps(self.data).encode("utf-8")
        raw += b" " * (16385 - len(raw))
        self.assertEqual(len(raw), 16385)
        result, output = self.cli(raw=raw)
        self.assert_failure(result, output, "invalid_request")

    def test_invalid_scope_or_untrusted_fields_never_produce_success_shaped_output(self):
        cases = (
            ({"metrics": ["confirmed_booking_count", "unknown_metric"]}, "unknown_metric"),
            ({"center_id": "CTR-A01"}, "unknown_entity"),
            ({"sql": "SELECT 1"}, "invalid_request"),
            ({"start": "2026-03-01T00:00:00+00:60"}, "invalid_request"),
        )
        for changes, code in cases:
            with self.subTest(changes=changes):
                data = dict(self.data)
                data.update(changes)
                result, output = self.cli(raw=json.dumps(data))
                self.assert_failure(result, output, code)

    def test_missing_database_is_not_created_or_replaced_by_success(self):
        database = self.root / "missing.sqlite"
        result, output = self.cli(database=database)
        self.assertNotEqual(result.returncode, 0)
        evidence = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn(evidence["error"]["code"], {"unsupported_source", "execution_failure"})
        self.assert_failure(result, output, evidence["error"]["code"])
        self.assertFalse(database.exists())

    def test_missing_request_is_a_structured_file_error(self):
        self.request_path.unlink()
        result, output = self.cli()
        self.assert_failure(result, output, "file_error")
        self.assertFalse(self.request_path.exists())

    def test_late_required_sum_failure_writes_error_not_a_partial_pack(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "UPDATE booking_items SET seats=1, unit_price_minor=?, discount_minor=0 "
                "WHERE item_id IN ('I01','I02')", (2 ** 62,),
            )
            conn.commit()
        self.data["metrics"] = ["confirmed_booking_count", "confirmed_booked_amount"]
        before = self.db.read_bytes()
        result, output = self.cli(raw=json.dumps(self.data))
        self.assert_failure(result, output, "execution_failure")
        self.assertEqual(self.db.read_bytes(), before)
        with closing(sqlite3.connect(self.db, timeout=0)) as conn:
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("UPDATE centers SET name=name WHERE center_id='CA'")
            conn.rollback()

    def test_import_and_execution_cannot_access_evaluator_assets_or_modules(self):
        script = textwrap.dedent("""
            import json
            import os
            from pathlib import Path
            import sys

            evaluator_root = Path(sys.argv[1]).resolve() / "evals"
            forbidden = {"tools", "tests", "evals"}
            violations = []

            class IsolationViolation(RuntimeError):
                pass

            class EvaluatorImportGuard:
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split(".")[0] in forbidden:
                        violations.append("import:" + fullname)
                        raise IsolationViolation("Evaluator import forbidden")
                    return None

            def audit(event, arguments):
                if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(arguments[0])).resolve()
                    if path.is_relative_to(evaluator_root):
                        violations.append("open:" + str(path))
                        raise IsolationViolation("Evaluator file read forbidden")

            sys.meta_path.insert(0, EvaluatorImportGuard())
            sys.addaudithook(audit)
            assert not any(name.split(".")[0] in forbidden for name in sys.modules)

            for module in forbidden:
                try:
                    __import__(module)
                except IsolationViolation:
                    pass
                else:
                    raise AssertionError("Import guard did not reject its negative control")
            try:
                (evaluator_root / "oracles" / "learningops.json").read_bytes()
            except IsolationViolation:
                pass
            else:
                raise AssertionError("Audit hook did not reject its negative control")
            violations.clear()

            from grepbit import FactRequest, execute_facts

            pack = execute_facts(Path(sys.argv[2]), FactRequest.from_mapping(json.loads(sys.argv[3])))
            assert not violations, violations
            assert not any(name.split(".")[0] in forbidden for name in sys.modules)
            print(json.dumps({
                "status": pack.status,
                "values": {fact.metric_id: fact.value for fact in pack.facts},
                "violations": violations,
            }))
        """)
        before = self.db.read_bytes()
        result = subprocess.run(
            [
                sys.executable, "-B", "-c", script, str(fixture.ROOT),
                str(self.db), json.dumps(self.data),
            ],
            cwd=fixture.ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence, {
            "status": "complete",
            "values": {
                "confirmed_booked_amount": 158000,
                "confirmed_booking_count": 7,
                "booked_seats": 12,
                "known_booking_accounts": 5,
            },
            "violations": [],
        })
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
