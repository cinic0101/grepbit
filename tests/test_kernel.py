"""Offline kernel regressions on isolated synthetic fixtures, not model evaluations."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import builtins
import inspect
import io
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from grepbit import ExecutionLimits, FactPack, FactRequest, KernelError, execute_facts
from grepbit.catalog import Catalog, LEARNINGOPS
from tools import fixture


METRICS = (
    "confirmed_booked_amount",
    "confirmed_booking_count",
    "booked_seats",
    "known_booking_accounts",
)
MARCH_VALUES = (158000, 7, 12, 5)
MARCH_START = "2026-02-28T16:00:00Z"
MARCH_END = "2026-03-31T16:00:00Z"


def request_mapping(**changes):
    result = {
        "metrics": list(METRICS),
        "start": "2026-03-01T00:00:00+08:00",
        "end": "2026-04-01T00:00:00+08:00",
        "timezone": "Asia/Taipei",
    }
    result.update(changes)
    return result


def request(**changes):
    return FactRequest.from_mapping(request_mapping(**changes))


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class KernelAssertions(unittest.TestCase):
    def assert_kernel_error(self, code, function, *args, **kwargs):
        with self.assertRaises(KernelError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        self.assertTrue(str(raised.exception))
        return raised.exception


class FactRequestTests(KernelAssertions):
    def test_mapping_preserves_explicit_offsets_and_microseconds(self):
        data = request_mapping(
            start="2026-02-28T11:00:00.123456-05:00",
            end="2026-03-31T11:00:00.654321-05:00",
            center_id="CA",
        )
        parsed = FactRequest.from_mapping(data)
        self.assertEqual(parsed.metrics, METRICS)
        self.assertEqual(parsed.start.microsecond, 123456)
        self.assertEqual(parsed.end.microsecond, 654321)
        self.assertEqual(parsed.start.isoformat(), data["start"])
        self.assertEqual(parsed.end.isoformat(), data["end"])
        self.assertEqual(parsed.timezone, "Asia/Taipei")
        self.assertEqual(parsed.center_id, "CA")
        self.assertEqual(parsed.to_dict(), data)
        self.assertEqual(FactRequest.from_mapping(json.loads(json.dumps(parsed.to_dict()))), parsed)

    def test_z_instants_and_null_optional_center_are_accepted(self):
        parsed = request(start=MARCH_START, end=MARCH_END, center_id=None)
        self.assertEqual(parsed.start.utcoffset().total_seconds(), 0)
        self.assertEqual(parsed.end.utcoffset().total_seconds(), 0)
        self.assertIsNone(parsed.center_id)

    def test_missing_required_fields_are_rejected(self):
        for key in ("metrics", "start", "end", "timezone"):
            with self.subTest(field=key):
                data = request_mapping()
                del data[key]
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping, data)

    def test_sql_formula_units_ranking_and_catalog_are_not_request_fields(self):
        extras = {
            "sql": "SELECT 1",
            "query": "SELECT 1",
            "formula": "SUM(seats)",
            "unit": "people",
            "ranking": "top",
            "order_by": "value DESC",
            "limit": 1,
            "catalog": {"version": "untrusted"},
            "filters": {"status": "draft"},
            "table": "payments",
        }
        for key, value in extras.items():
            with self.subTest(field=key):
                self.assert_kernel_error(
                    "invalid_request", FactRequest.from_mapping, request_mapping(**{key: value})
                )

    def test_non_object_requests_are_rejected(self):
        for value in (None, [], "SELECT 1", 1, True):
            with self.subTest(value=value):
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping, value)

    def test_metric_list_shape_identifiers_duplicates_and_bound_are_checked(self):
        invalid = (
            [], "booked_seats", ("booked_seats",), [None], [1], [True],
            ["booked_seats", "booked_seats"], ["a", "b", "c", "d", "e"],
            [""], ["BookED"], ["a" * 65], ["booked_seats; SELECT 1"],
        )
        for metrics in invalid:
            with self.subTest(metrics=metrics):
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping,
                                         request_mapping(metrics=metrics))

    def test_direct_request_requires_a_tuple_of_metric_ids(self):
        valid = request()
        for metrics in ([], ["booked_seats"], "booked_seats", (), (None,)):
            with self.subTest(metrics=metrics):
                self.assert_kernel_error("invalid_request", replace, valid, metrics=metrics)

    def test_bad_iso_instants_and_naive_mapping_times_are_rejected(self):
        invalid = (
            None, 1772294400, True, "2026-03-01", "2026-03-01T00:00:00",
            "2026-03-01 00:00:00Z", "2026-02-30T00:00:00Z",
            "2026-03-01T25:00:00Z", "2026-03-01T00:00:00+25:00",
            "2026-03-01T00:00:00+00:60", "2026-03-01T00:00:00-00:60",
            "2026-03-01T00:00:00.1234567Z", "2026-03-01T00:00Z",
        )
        for field in ("start", "end"):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    self.assert_kernel_error(
                        "invalid_request", FactRequest.from_mapping,
                        request_mapping(**{field: value}),
                    )

    def test_direct_naive_and_non_datetime_instants_are_rejected(self):
        valid = request()
        for field in ("start", "end"):
            for value in (datetime(2026, 3, 1), None, MARCH_START):
                with self.subTest(field=field, value=value):
                    self.assert_kernel_error("invalid_request", replace, valid, **{field: value})

    def test_equal_or_inverted_instants_are_rejected_across_offsets(self):
        for start, end in (
            (MARCH_START, MARCH_START),
            (MARCH_END, MARCH_START),
            ("2026-03-01T00:00:00+08:00", MARCH_START),
            ("2026-03-01T00:00:00+08:00", "2026-02-28T15:59:59Z"),
        ):
            with self.subTest(start=start, end=end):
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping,
                                         request_mapping(start=start, end=end))

    def test_unknown_or_invalid_business_timezone_is_rejected(self):
        for zone in ("Mars/Olympus", "+08:00", "", "../UTC", None, 8, True):
            with self.subTest(zone=zone):
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping,
                                         request_mapping(timezone=zone))

    def test_center_id_shape_is_checked_without_resolving_names(self):
        for center in ("", "C" * 65, 1, True, ["CA"], {"id": "CA"}):
            with self.subTest(center=center):
                self.assert_kernel_error("invalid_request", FactRequest.from_mapping,
                                         request_mapping(center_id=center))
        self.assertEqual(request(center_id="CTR-A01").center_id, "CTR-A01")


class ExecutionLimitTests(KernelAssertions):
    def test_defaults_and_inclusive_upper_bounds(self):
        defaults = ExecutionLimits()
        self.assertEqual(defaults.timeout_seconds, 2.0)
        self.assertEqual(defaults.max_vm_steps, 1_000_000)
        self.assertEqual(defaults.max_source_rows, 100_000)
        self.assertEqual(ExecutionLimits(30, 1_000_000, 100_000).timeout_seconds, 30)
        self.assertEqual(ExecutionLimits(0.001, 100, 1).max_vm_steps, 100)

    def test_invalid_timeout_limits_are_rejected(self):
        for value in (0, -1, 30.1, math.inf, -math.inf, math.nan, True, "2", None):
            with self.subTest(value=value):
                self.assert_kernel_error("invalid_limits", ExecutionLimits, timeout_seconds=value)

    def test_invalid_step_and_row_limits_are_rejected(self):
        for field, values in (
            ("max_vm_steps", (0, 99, 1_000_001, 100.0, True, "100", None)),
            ("max_source_rows", (0, -1, 100_001, 1.0, True, "1", None)),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_kernel_error("invalid_limits", ExecutionLimits, **{field: value})


class KernelTests(KernelAssertions):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.build_database("learning.sqlite")

    def build_database(self, name):
        path = self.root / name
        fixture.build(path)
        return path

    def mutate(self, *statements, database=None):
        with closing(sqlite3.connect(database or self.db)) as conn:
            with conn:
                for sql, parameters in statements:
                    conn.execute(sql, parameters)

    def execute(self, fact_request=None, *, database=None, **kwargs):
        fact_request = request() if fact_request is None else fact_request
        pack = execute_facts(database or self.db, fact_request, **kwargs)
        self.assertIsInstance(pack, FactPack)
        self.assertEqual(pack.status, "complete")
        self.assertEqual(pack.request, fact_request)
        self.assertIsInstance(pack.facts, tuple)
        self.assertEqual(len(pack.facts), len(fact_request.metrics))
        self.assertCountEqual([fact.metric_id for fact in pack.facts], fact_request.metrics)
        self.assertTrue(all(fact.completeness == "complete" for fact in pack.facts))
        return pack

    def assert_values(self, pack, expected):
        if isinstance(expected, tuple):
            expected = dict(zip(METRICS, expected))
        self.assertEqual({fact.metric_id: fact.value for fact in pack.facts}, expected)
        for fact in pack.facts:
            if fact.value is not None:
                self.assertIs(type(fact.value), int)

    def assert_writer_available(self, database=None):
        with closing(sqlite3.connect(database or self.db, timeout=0)) as conn:
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("UPDATE centers SET name=name WHERE center_id='CA'")
            conn.rollback()

    def replace_table_schema(self, database, table, transform):
        # Rebuild only a throwaway fixture table; never edit reviewed DDL assets.
        with closing(sqlite3.connect(database)) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("PRAGMA legacy_alter_table=ON")
            ddl = conn.execute(
                "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            changed = transform(ddl)
            self.assertNotEqual(changed, ddl)
            replacement = "replacement_" + table
            changed = changed.replace("CREATE TABLE " + table, "CREATE TABLE " + replacement, 1)
            with conn:
                conn.execute(changed)
                conn.execute(f'INSERT INTO "{replacement}" SELECT * FROM "{table}"')
                conn.execute(f'DROP TABLE "{table}"')
                conn.execute(f'ALTER TABLE "{replacement}" RENAME TO "{table}"')

    def test_frozen_q01_to_q04_values(self):
        pack = self.execute()
        self.assert_values(pack, MARCH_VALUES)
        references = {row["id"]: row for row in fixture.load(fixture.ORACLES)}
        for fact, reference_id in zip(METRICS, (
            "Q01_booked_amount", "Q02_booking_count", "Q03_booked_seats", "Q04_known_learners",
        )):
            with self.subTest(metric=fact):
                actual = next(item.value for item in pack.facts if item.metric_id == fact)
                self.assertEqual(actual, references[reference_id]["expected"][0][0])

    def test_q05_uses_canonical_center_id(self):
        pack = self.execute(request(center_id="CA"))
        self.assert_values(pack, (68000, 4, 6, 2))
        for fact in pack.facts:
            self.assertEqual(fact.filters, {"center_id": "CA"})
            self.assertIn("CA", fact.parameters.values())
            self.assertNotIn("'CA'", fact.sql)

    def test_q09_february_is_an_explicit_different_window(self):
        pack = self.execute(request(
            start="2026-02-01T00:00:00+08:00", end="2026-03-01T00:00:00+08:00",
        ))
        self.assert_values(pack, (50000, 3, 4, 3))
        for fact in pack.facts:
            self.assertEqual(fact.start_utc, "2026-01-31T16:00:00Z")
            self.assertEqual(fact.end_utc, MARCH_START)

    def test_march_half_open_cohort_contains_exact_boundary_booking_ids(self):
        with closing(fixture.readonly(self.db)) as conn:
            ids = conn.execute(
                "SELECT booking_id FROM bookings WHERE status='confirmed' "
                "AND created_at_utc>=? AND created_at_utc<? ORDER BY booking_id",
                (MARCH_START, MARCH_END),
            ).fetchall()
        self.assertEqual(ids, [(key,) for key in ("B01", "B02", "B03", "B04", "B05", "B06", "B13")])
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_each_boundary_second_is_included_only_in_its_half_open_window(self):
        windows = (
            ("2026-02-28T15:59:59Z", MARCH_START, "B09", (10000, 1, 1, 1)),
            (MARCH_START, "2026-02-28T16:00:01Z", "B01", (35000, 1, 3, 1)),
            (MARCH_END, "2026-03-31T16:00:01Z", "B12", (20000, 1, 1, 1)),
        )
        for start, end, booking_id, expected in windows:
            with self.subTest(booking_id=booking_id):
                with closing(fixture.readonly(self.db)) as conn:
                    ids = conn.execute(
                        "SELECT booking_id FROM bookings WHERE status='confirmed' "
                        "AND created_at_utc>=? AND created_at_utc<?", (start, end),
                    ).fetchall()
                self.assertEqual(ids, [(booking_id,)])
                self.assert_values(self.execute(request(start=start, end=end)), expected)

    def test_equivalent_offsets_produce_the_same_instants_and_sql_parameters(self):
        baseline = self.execute()
        for start, end in (
            (MARCH_START, MARCH_END),
            ("2026-02-28T11:00:00-05:00", "2026-03-31T11:00:00-05:00"),
            ("2026-03-01T01:00:00+09:00", "2026-04-01T01:00:00+09:00"),
        ):
            with self.subTest(start=start):
                pack = self.execute(request(start=start, end=end))
                self.assert_values(pack, MARCH_VALUES)
                for actual in pack.facts:
                    original = next(fact for fact in baseline.facts if fact.metric_id == actual.metric_id)
                    self.assertEqual(actual.start_utc, original.start_utc)
                    self.assertEqual(actual.end_utc, original.end_utc)
                    self.assertEqual(actual.parameters, original.parameters)
                    self.assertEqual(actual.sql, original.sql)
                    self.assertEqual(actual.business_timezone, "Asia/Taipei")

    def test_business_timezone_does_not_infer_or_snap_calendar_ranges(self):
        for zone in ("UTC", "Asia/Taipei", "America/New_York"):
            with self.subTest(zone=zone):
                pack = self.execute(request(
                    start="2026-03-01T00:00:00Z", end="2026-04-01T00:00:00Z", timezone=zone,
                ))
                self.assert_values(pack, (143000, 7, 10, 6))
                for fact in pack.facts:
                    self.assertEqual(fact.business_timezone, zone)
                    self.assertEqual(fact.start_utc, "2026-03-01T00:00:00Z")
                    self.assertEqual(fact.end_utc, "2026-04-01T00:00:00Z")

    def test_fractional_start_and_end_are_ceiled_for_whole_second_storage(self):
        cases = (
            ("2026-02-28T15:59:59.500000Z", "2026-02-28T16:00:00.500000Z",
             MARCH_START, "2026-02-28T16:00:01Z", (35000, 1, 3, 1)),
            ("2026-02-28T16:00:00.000001Z", "2026-02-28T16:00:01Z",
             "2026-02-28T16:00:01Z", "2026-02-28T16:00:01Z", (None, 0, None, 0)),
            ("2026-02-28T15:59:59.500000Z", MARCH_START,
             MARCH_START, MARCH_START, (None, 0, None, 0)),
            ("2026-02-28T15:59:59Z", "2026-02-28T15:59:59.500000Z",
             "2026-02-28T15:59:59Z", MARCH_START, (10000, 1, 1, 1)),
            ("2026-02-28T16:00:00.100000Z", "2026-02-28T16:00:00.900000Z",
             "2026-02-28T16:00:01Z", "2026-02-28T16:00:01Z", (None, 0, None, 0)),
            ("2026-03-31T15:59:59.999999Z", "2026-03-31T16:00:00.000001Z",
             MARCH_END, "2026-03-31T16:00:01Z", (20000, 1, 1, 1)),
        )
        for start, end, bound_start, bound_end, expected in cases:
            with self.subTest(start=start, end=end):
                parsed = request(start=start, end=end)
                pack = self.execute(parsed)
                self.assert_values(pack, expected)
                self.assertEqual(pack.request.start.microsecond, parsed.start.microsecond)
                self.assertEqual(pack.request.end.microsecond, parsed.end.microsecond)
                for fact in pack.facts:
                    self.assertEqual(fact.start_utc, utc_text(parsed.start))
                    self.assertEqual(fact.end_utc, utc_text(parsed.end))
                    self.assertIn(bound_start, fact.parameters.values())
                    self.assertIn(bound_end, fact.parameters.values())

    def test_no_activity_center_has_null_sums_zero_counts_and_empty_population(self):
        pack = self.execute(request(center_id="CZ"))
        self.assert_values(pack, (None, 0, None, 0))
        for fact in pack.facts:
            self.assertIs(fact.empty_population, True)
            self.assertEqual(fact.population_rows, 0)
            self.assertEqual(fact.filters, {"center_id": "CZ"})
        known = next(fact for fact in pack.facts if fact.metric_id == "known_booking_accounts")
        self.assertEqual(known.excluded_anonymous_rows, 0)

    def test_empty_time_window_does_not_coerce_sums_to_zero(self):
        pack = self.execute(request(start="2027-01-01T00:00:00Z", end="2027-02-01T00:00:00Z"))
        self.assert_values(pack, (None, 0, None, 0))
        self.assertTrue(all(fact.empty_population and fact.population_rows == 0 for fact in pack.facts))

    def test_anonymous_only_population_is_not_empty(self):
        pack = self.execute(request(
            start="2026-03-07T04:00:00Z", end="2026-03-07T04:00:01Z",
        ))
        self.assert_values(pack, (10000, 1, 1, 0))
        for fact in pack.facts:
            self.assertEqual(fact.population_rows, 1)
            self.assertIs(fact.empty_population, False)
        known = next(fact for fact in pack.facts if fact.metric_id == "known_booking_accounts")
        self.assertEqual(known.excluded_anonymous_rows, 1)
        self.assertIn("anonymous", " ".join(known.disclosures).lower())

    def test_zero_amount_on_nonempty_lines_is_not_an_empty_sum(self):
        self.mutate(("UPDATE booking_items SET unit_price_minor=0, discount_minor=0", ()))
        pack = self.execute()
        self.assert_values(pack, (0, 7, 12, 5))
        amount = next(fact for fact in pack.facts if fact.metric_id == "confirmed_booked_amount")
        self.assertEqual(amount.population_rows, 8)
        self.assertIs(amount.empty_population, False)

    def test_exact_units_grains_population_sizes_and_catalog_provenance(self):
        pack = self.execute()
        expected = {
            "confirmed_booked_amount": ("TWD_minor", "booking_line", 8),
            "confirmed_booking_count": ("bookings", "booking", 7),
            "booked_seats": ("seats", "booking_line", 8),
            "known_booking_accounts": ("booking_accounts", "booking", 7),
        }
        for fact in pack.facts:
            with self.subTest(metric=fact.metric_id):
                unit, grain, population_rows = expected[fact.metric_id]
                self.assertEqual((fact.unit, fact.grain, fact.population_rows),
                                 (unit, grain, population_rows))
                self.assertIs(fact.empty_population, False)
                self.assertEqual(fact.catalog_id, LEARNINGOPS.version)
                self.assertEqual(fact.catalog_sha256, LEARNINGOPS.digest())
                self.assertEqual(fact.filters, {})
                self.assertEqual(fact.start_utc, MARCH_START)
                self.assertEqual(fact.end_utc, MARCH_END)
                self.assertEqual(fact.business_timezone, "Asia/Taipei")
                self.assertIn("confirmed", fact.population.lower())
                self.assertIn("booking", fact.population.lower())
                self.assertIn("created_at_utc", fact.time_basis)
                self.assertIsInstance(fact.checks, tuple)
                self.assertTrue(fact.checks)
                self.assertTrue(all(isinstance(check, str) and check for check in fact.checks))
                checks = " ".join(fact.checks).lower()
                self.assertIn("schema", checks)
                self.assertTrue("catalog" in checks or "binding" in checks, fact.checks)
                self.assertIsInstance(fact.disclosures, tuple)
                for disclosure in LEARNINGOPS.metrics[fact.metric_id].disclosures:
                    self.assertIn(disclosure, fact.disclosures)
                self.assertEqual(fact.excluded_anonymous_rows,
                                 1 if fact.metric_id == "known_booking_accounts" else None)

    def test_json_pack_contains_the_authoritative_output_fields(self):
        pack = self.execute()
        document = json.loads(json.dumps(pack.to_dict(), allow_nan=False))
        self.assertEqual(set(document), {
            "request", "facts", "snapshot", "runtime", "execution", "limitations", "status",
        })
        self.assertEqual(document["request"], pack.request.to_dict())
        self.assertEqual(document["status"], "complete")
        self.assertEqual(len(document["facts"]), 4)
        required_fact_fields = {
            "metric_id", "catalog_id", "catalog_sha256", "value", "unit", "grain",
            "population", "time_basis", "start_utc", "end_utc", "business_timezone",
            "filters", "population_rows", "empty_population", "excluded_anonymous_rows",
            "disclosures", "sql", "parameters", "snapshot_id", "checks", "completeness", "fact_id",
        }
        for fact in document["facts"]:
            self.assertEqual(set(fact), required_fact_fields)
            self.assertEqual(fact["completeness"], "complete")
        for field in ("snapshot", "runtime", "execution"):
            self.assertIsInstance(document[field], dict)
            self.assertTrue(document[field])
        self.assertIsInstance(document["limitations"], list)
        self.assertTrue(document["limitations"])

    def test_sql_is_bound_read_only_and_uses_only_admitted_fact_sources(self):
        pack = self.execute(request(center_id="CA"))
        with closing(fixture.readonly(self.db)) as conn:
            for fact in pack.facts:
                with self.subTest(metric=fact.metric_id):
                    tree = parse_one(fact.sql, dialect="sqlite")
                    self.assertIsInstance(tree, exp.Select)
                    tables = {table.name for table in tree.find_all(exp.Table)}
                    self.assertIn("bookings", tables)
                    self.assertLessEqual(tables, {"bookings", "booking_items", "centers"})
                    if fact.grain == "booking_line":
                        self.assertIn("booking_items", tables)
                    self.assertTrue(list(tree.find_all(exp.Placeholder)))
                    self.assertIn(MARCH_START, fact.parameters.values())
                    self.assertIn(MARCH_END, fact.parameters.values())
                    for value in fact.parameters.values():
                        self.assertIsInstance(value, str)
                        self.assertNotIn("'" + value.replace("'", "''") + "'", fact.sql)
                    rows = conn.execute(fact.sql, fact.parameters).fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertIn(fact.value, tuple(rows[0]))

    def test_batch_snapshot_is_a_shared_uuid_not_a_persistent_database_identity(self):
        first = self.execute()
        second = self.execute()
        snapshot_ids = {fact.snapshot_id for fact in first.facts}
        self.assertEqual(len(snapshot_ids), 1)
        first_id = snapshot_ids.pop()
        self.assertEqual(str(UUID(first_id)), first_id)
        self.assertIn(first_id, first.snapshot.values())
        self.assertTrue(all(fact.snapshot_id != first_id for fact in second.facts))
        self.assert_values(second, MARCH_VALUES)
        self.assert_writer_available()

    def test_batch_opens_and_finishes_one_read_transaction(self):
        connect = sqlite3.connect
        connections = []
        traces = []

        def traced_connect(*args, **kwargs):
            conn = connect(*args, **kwargs)
            connections.append(conn)
            conn.set_trace_callback(
                lambda sql: traces.append((sql.strip().upper(), conn.in_transaction))
            )
            return conn

        with patch.object(sqlite3, "connect", side_effect=traced_connect):
            self.assert_values(self.execute(), MARCH_VALUES)
        self.assertEqual(len(connections), 1)
        starts = [sql for sql, _ in traces if sql.startswith("BEGIN")]
        reads = [active for sql, active in traces if sql.startswith("SELECT")]
        self.assertEqual(len(starts), 1, traces)
        self.assertNotIn("IMMEDIATE", starts[0])
        self.assertNotIn("EXCLUSIVE", starts[0])
        self.assertTrue(reads)
        self.assertTrue(all(reads), traces)
        try:
            transaction_open = connections[0].in_transaction
        except sqlite3.ProgrammingError:
            transaction_open = False
        self.assertFalse(transaction_open)
        self.assert_writer_available()

    def test_batch_snapshot_survives_a_writer_commit_between_fact_queries(self):
        connect = sqlite3.connect
        with closing(connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            aggregate_queries = 0
            callback_errors = []
            writer_committed = False

            def trace(sql):
                nonlocal aggregate_queries, writer_committed
                if not sql.lstrip().upper().startswith("SELECT"):
                    return
                try:
                    tree = parse_one(sql, dialect="sqlite")
                    if tree.find(exp.AggFunc) is None:
                        return
                    aggregate_queries += 1
                    if aggregate_queries == 2:
                        writer.execute("UPDATE bookings SET status='cancelled' WHERE booking_id='B04'")
                        writer.commit()
                        writer_committed = True
                except (sqlite3.Error, ParseError) as exc:
                    # SQLite trace callbacks do not propagate their exceptions.
                    callback_errors.append(exc)

            def traced_connect(*args, **kwargs):
                conn = connect(*args, **kwargs)
                conn.set_trace_callback(trace)
                return conn

            with patch.object(sqlite3, "connect", side_effect=traced_connect):
                pack = self.execute()
            self.assertEqual(callback_errors, [])
            self.assertTrue(writer_committed)
            self.assertGreaterEqual(aggregate_queries, 4)
            self.assert_values(pack, MARCH_VALUES)
        self.assert_values(self.execute(), (128000, 6, 9, 4))
        self.assert_writer_available()

    def test_center_filters_do_not_leak_between_calls(self):
        expectations = (
            ("CA", (68000, 4, 6, 2)),
            ("CB", (30000, 1, 3, 1)),
            (None, MARCH_VALUES),
            ("CC", (60000, 2, 3, 2)),
            ("CZ", (None, 0, None, 0)),
            ("CA", (68000, 4, 6, 2)),
            (None, MARCH_VALUES),
        )
        for center_id, expected in expectations:
            with self.subTest(center_id=center_id):
                pack = self.execute(request(center_id=center_id))
                self.assert_values(pack, expected)
                for fact in pack.facts:
                    self.assertEqual(fact.filters, {} if center_id is None else {"center_id": center_id})
                known = next(fact for fact in pack.facts if fact.metric_id == "known_booking_accounts")
                self.assertEqual(known.excluded_anonymous_rows, int(center_id in (None, "CA")))

    def test_extra_lines_change_line_metrics_without_multiplying_booking_or_account_counts(self):
        self.mutate((
            "INSERT INTO booking_items VALUES ('I_EXTRA','B01','S01','CA',4,1250,500)", (),
        ))
        pack = self.execute()
        self.assert_values(pack, (162500, 7, 16, 5))
        for fact in pack.facts:
            self.assertEqual(fact.population_rows, 9 if fact.grain == "booking_line" else 7)

    def test_extra_anonymous_line_does_not_multiply_excluded_booking_count(self):
        self.mutate((
            "INSERT INTO booking_items VALUES ('I_ANON','B06','S01','CA',1,10000,0)", (),
        ))
        pack = self.execute()
        self.assert_values(pack, (168000, 7, 13, 5))
        known = next(fact for fact in pack.facts if fact.metric_id == "known_booking_accounts")
        self.assertEqual(known.population_rows, 7)
        self.assertEqual(known.excluded_anonymous_rows, 1)

    def test_booking_without_lines_still_counts_at_booking_grain(self):
        self.mutate((
            "INSERT INTO bookings VALUES ('B_EMPTY','CA','L5',"
            "'2026-03-21T00:00:00Z','confirmed','TWD')", (),
        ))
        pack = self.execute()
        self.assert_values(pack, (158000, 8, 12, 6))
        self.assertTrue(all(fact.population_rows == 8 for fact in pack.facts))

    def test_split_payments_cannot_change_any_admitted_metric(self):
        self.mutate(
            ("UPDATE payments SET amount_minor=4000 WHERE payment_id='P01'", ()),
            ("INSERT INTO payments VALUES "
             "('P_SPLIT','B01','2026-03-01T03:00:00Z','succeeded',6000)", ()),
        )
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_extra_refunds_cannot_change_before_refund_booked_metrics(self):
        self.mutate(
            ("INSERT INTO refunds VALUES "
             "('R_EXTRA','I01','2026-03-22T06:00:00Z','succeeded',1000)", ()),
            ("INSERT INTO refunds VALUES "
             "('R_LATER','I01','2026-04-03T06:00:00Z','succeeded',2000)", ()),
        )
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_repeated_amounts_and_payment_fanout_are_real_negative_controls(self):
        with closing(fixture.readonly(self.db)) as conn:
            common = (
                "FROM bookings b JOIN booking_items i ON b.booking_id=i.booking_id "
                "WHERE b.status='confirmed' AND b.created_at_utc>=:start AND b.created_at_utc<:end"
            )
            parameters = {"start": MARCH_START, "end": MARCH_END}
            distinct_amount = conn.execute(
                "SELECT SUM(DISTINCT i.seats*i.unit_price_minor-i.discount_minor) " + common,
                parameters,
            ).fetchone()[0]
            fanout_amount = conn.execute(
                "SELECT SUM(i.seats*i.unit_price_minor-i.discount_minor) "
                "FROM bookings b JOIN booking_items i ON b.booking_id=i.booking_id "
                "JOIN payments p ON b.booking_id=p.booking_id WHERE b.status='confirmed' "
                "AND p.status='succeeded' AND b.created_at_utc>=:start AND b.created_at_utc<:end",
                parameters,
            ).fetchone()[0]
        self.assertNotEqual(distinct_amount, 158000)
        self.assertNotEqual(fanout_amount, 158000)
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_cancelled_and_draft_line_amounts_do_not_enter_confirmed_population(self):
        self.mutate((
            "UPDATE booking_items SET seats=99, unit_price_minor=999999 "
            "WHERE booking_id IN ('B07','B08')", (),
        ))
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_time_basis_is_booking_creation_not_session_payment_or_refund_time(self):
        self.mutate(
            ("UPDATE sessions SET starts_at_utc='2027-01-01T00:00:00Z'", ()),
            ("UPDATE payments SET posted_at_utc='2027-01-01T00:00:00Z'", ()),
            ("UPDATE refunds SET posted_at_utc='2027-01-01T00:00:00Z'", ()),
        )
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_separate_database_contents_are_used_instead_of_cached_or_gold_values(self):
        changed = self.build_database("different.sqlite")
        self.mutate((
            "UPDATE booking_items SET discount_minor=discount_minor+100 WHERE item_id='I03'", (),
        ), database=changed)
        self.assert_values(self.execute(database=changed), (157900, 7, 12, 5))
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_trusted_metric_aliases_share_the_existing_binding_and_sql_path(self):
        baseline = {fact.metric_id: fact for fact in self.execute().facts}
        for original_id, binding in LEARNINGOPS.metrics.items():
            with self.subTest(metric=original_id):
                alias = "test_" + original_id
                catalog = Catalog("test-alias-v1", {alias: binding})
                pack = self.execute(request(metrics=[alias]), catalog=catalog)
                fact = pack.facts[0]
                original = baseline[original_id]
                self.assert_values(pack, {alias: original.value})
                for field in (
                    "sql", "parameters", "unit", "grain", "population", "time_basis",
                    "population_rows", "excluded_anonymous_rows", "disclosures",
                ):
                    self.assertEqual(getattr(fact, field), getattr(original, field), field)
                self.assertEqual(fact.catalog_id, "test-alias-v1")
                self.assertEqual(fact.catalog_sha256, catalog.digest())
                self.assertNotEqual(fact.catalog_sha256, original.catalog_sha256)

    def test_unknown_metric_fails_the_whole_required_batch(self):
        self.assert_kernel_error(
            "unknown_metric", execute_facts, self.db,
            request(metrics=["confirmed_booked_amount", "not_a_metric"]),
        )
        self.assert_writer_available()

    def test_center_codes_unknown_ids_and_sql_like_ids_do_not_resolve(self):
        for center_id in ("CTR-A01", "UNKNOWN", "ca", "CA' OR 1=1 --"):
            with self.subTest(center_id=center_id):
                self.assert_kernel_error("unknown_entity", execute_facts, self.db,
                                         request(center_id=center_id))
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_execution_accepts_only_the_fact_request_not_sql_or_json(self):
        parameters = inspect.signature(execute_facts).parameters
        self.assertEqual(set(parameters), {"database", "request", "catalog", "limits"})
        self.assertEqual(parameters["catalog"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(parameters["limits"].kind, inspect.Parameter.KEYWORD_ONLY)
        for invalid in ("SELECT * FROM bookings", request_mapping(), None):
            with self.subTest(value=invalid):
                self.assert_kernel_error("invalid_request", execute_facts, self.db, invalid)
        with self.assertRaises(TypeError):
            execute_facts(self.db, request(), sql="SELECT 1")

    def test_unsafe_catalog_nodes_columns_and_sources_are_rejected(self):
        binding = LEARNINGOPS.metrics["confirmed_booked_amount"]
        invalid = (
            replace(binding, source="payments"),
            replace(binding, expression=exp.Sum(this=exp.column("email", table="b"))),
            replace(binding, expression=exp.Sum(this=exp.column("seats", table="other"))),
            replace(binding, expression=exp.Anonymous(
                this="load_extension", expressions=[exp.Literal.string("not-a-library")],
            )),
            replace(binding, expression=parse_one("SELECT learner_id FROM learners")),
            replace(binding, expression=exp.Subquery(this=parse_one("SELECT 1"))),
            replace(binding, excluded_null_column="email"),
        )
        for bad_binding in invalid:
            with self.subTest(source=bad_binding.source, expression=str(bad_binding.expression)):
                catalog = Catalog("test-invalid-v1", {"invalid_binding": bad_binding})
                self.assert_kernel_error(
                    "invalid_catalog", execute_facts, self.db,
                    request(metrics=["invalid_binding"]), catalog=catalog,
                )
        self.assert_writer_available()

    def test_invalid_later_catalog_binding_does_not_return_partial_success(self):
        catalog = Catalog("test-invalid-batch-v1", {
            "valid_amount": LEARNINGOPS.metrics["confirmed_booked_amount"],
            "invalid_amount": replace(
                LEARNINGOPS.metrics["confirmed_booked_amount"],
                expression=exp.Sum(this=exp.column("not_a_column", table="i")),
            ),
        })
        self.assert_kernel_error(
            "invalid_catalog", execute_facts, self.db,
            request(metrics=["valid_amount", "invalid_amount"]), catalog=catalog,
        )

    def test_missing_required_tables_are_unsupported_sources(self):
        for table in ("centers", "bookings", "booking_items"):
            with self.subTest(table=table):
                database = self.build_database("missing-" + table + ".sqlite")
                self.mutate((f'DROP TABLE "{table}"', ()), database=database)
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_views_cannot_impersonate_required_tables(self):
        database = self.build_database("view.sqlite")
        self.mutate(
            ("PRAGMA legacy_alter_table=ON", ()),
            ("ALTER TABLE bookings RENAME TO hidden_bookings", ()),
            ("CREATE VIEW bookings AS SELECT * FROM hidden_bookings", ()),
            database=database,
        )
        self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_changed_strictness_columns_types_nullability_keys_and_fks_are_rejected(self):
        variants = (
            ("bookings", lambda sql: sql.replace(") STRICT", ")")),
            ("booking_items", lambda sql: sql.replace("unit_price_minor", "price_minor")),
            ("booking_items", lambda sql: sql.replace("seats INTEGER NOT NULL", "seats REAL NOT NULL")),
            ("booking_items", lambda sql: sql.replace("seats INTEGER NOT NULL", "seats INTEGER")),
            ("bookings", lambda sql: sql.replace(
                "booking_id TEXT PRIMARY KEY NOT NULL", "booking_id TEXT NOT NULL",
            )),
            ("bookings", lambda sql: sql.replace(" REFERENCES centers(center_id)", "")),
            ("booking_items", lambda sql: sql.replace("CHECK(unit_price_minor >= 0)", "")),
            ("booking_items", lambda sql: sql.replace("CHECK(discount_minor >= 0)", "")),
        )
        for index, (table, transform) in enumerate(variants):
            with self.subTest(variant=index, table=table):
                database = self.build_database(f"schema-{index}.sqlite")
                self.replace_table_schema(database, table, transform)
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_explicit_collations_are_not_an_admitted_schema_profile(self):
        for index, collation in enumerate(("BINARY", "NOCASE")):
            with self.subTest(collation=collation):
                database = self.build_database(f"collation-{index}.sqlite")
                self.replace_table_schema(
                    database, "bookings",
                    lambda sql: sql.replace("status TEXT NOT NULL",
                                            f"status TEXT COLLATE {collation} NOT NULL"),
                )
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_noncanonical_or_invalid_physical_timestamp_encodings_are_rejected(self):
        encodings = (
            "2026-03-01T00:00:00+08:00",
            "2026-02-28T16:00:00+00:00",
            "2026-02-28 16:00:00",
            "2026-02-28T16:00:00.000000Z",
            "2026-02-30T16:00:00Z",
            "2026-02-28T16:00:60Z",
            "1772294400",
            "",
        )
        for index, timestamp in enumerate(encodings):
            with self.subTest(timestamp=timestamp):
                database = self.build_database(f"encoding-{index}.sqlite")
                self.mutate((
                    "UPDATE bookings SET created_at_utc=? WHERE booking_id='B01'", (timestamp,),
                ), database=database)
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_non_text_physical_timestamp_column_is_rejected(self):
        database = self.build_database("integer-time.sqlite")
        self.mutate(("UPDATE bookings SET created_at_utc='1772294400'", ()), database=database)
        self.replace_table_schema(
            database, "bookings", lambda sql: sql.replace("created_at_utc TEXT", "created_at_utc INTEGER"),
        )
        self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_orphan_or_cross_center_rows_are_rejected(self):
        mutations = (
            "UPDATE bookings SET center_id='MISSING' WHERE booking_id='B01'",
            "UPDATE bookings SET learner_id='MISSING' WHERE booking_id='B01'",
            "UPDATE booking_items SET booking_id='MISSING' WHERE item_id='I01'",
            "UPDATE booking_items SET session_id='MISSING' WHERE item_id='I01'",
            "UPDATE booking_items SET center_id='CB' WHERE item_id='I01'",
        )
        for index, sql in enumerate(mutations):
            with self.subTest(mutation=index):
                database = self.build_database(f"orphan-{index}.sqlite")
                self.mutate(("PRAGMA foreign_keys=OFF", ()), (sql, ()), database=database)
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_rows_violating_declared_value_constraints_are_rejected(self):
        mutations = (
            "UPDATE booking_items SET seats=-1 WHERE item_id='I01'",
            "UPDATE booking_items SET seats=0 WHERE item_id='I01'",
            "UPDATE booking_items SET unit_price_minor=-1 WHERE item_id='I01'",
            "UPDATE booking_items SET discount_minor=-1 WHERE item_id='I01'",
            "UPDATE booking_items SET discount_minor=999999 WHERE item_id='I01'",
            "UPDATE bookings SET currency='USD' WHERE booking_id='B01'",
            "UPDATE bookings SET status='unknown' WHERE booking_id='B01'",
        )
        for index, sql in enumerate(mutations):
            with self.subTest(mutation=index):
                database = self.build_database(f"invalid-row-{index}.sqlite")
                self.mutate(("PRAGMA ignore_check_constraints=ON", ()), (sql, ()), database=database)
                self.assert_kernel_error("unsupported_source", execute_facts, database, request())

    def test_success_and_failure_leave_database_bytes_and_directory_unchanged(self):
        before = self.db.read_bytes()
        entries = set(self.root.iterdir())
        self.execute()
        self.assert_kernel_error(
            "unknown_metric", execute_facts, self.db, request(metrics=["unknown_metric"]),
        )
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), entries)

    def test_uri_special_filename_is_opened_without_losing_path_characters(self):
        database = self.build_database("space # question ? percent % mode=rw.sqlite")
        before = database.read_bytes()
        self.assert_values(self.execute(database=database), MARCH_VALUES)
        self.assertEqual(database.read_bytes(), before)

    def test_missing_database_is_not_created(self):
        database = self.root / "missing.sqlite"
        with self.assertRaises(KernelError) as raised:
            execute_facts(database, request())
        self.assertIn(raised.exception.code, {"unsupported_source", "execution_failure"})
        self.assertFalse(database.exists())

    def test_execution_makes_no_socket_connections(self):
        forbidden = AssertionError("Network forbidden in offline kernel")
        with (
            patch.object(socket.socket, "connect", side_effect=forbidden),
            patch.object(socket.socket, "connect_ex", side_effect=forbidden),
            patch.object(socket.socket, "sendto", side_effect=forbidden),
            patch.object(socket, "create_connection", side_effect=forbidden),
        ):
            self.assert_values(self.execute(), MARCH_VALUES)

    def test_runtime_does_not_read_evaluator_assets_or_fixture_helpers(self):
        evaluator_root = fixture.ROOT / "evals"
        builtin_open, io_open = builtins.open, io.open

        def guarded(opener):
            def open_without_evals(file, *args, **kwargs):
                if isinstance(file, (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(file)).resolve()
                    if path.is_relative_to(evaluator_root):
                        raise AssertionError("Runtime read evaluator-only assets")
                return opener(file, *args, **kwargs)
            return open_without_evals

        with (
            patch.object(builtins, "open", side_effect=guarded(builtin_open)),
            patch.object(io, "open", side_effect=guarded(io_open)),
            patch.object(fixture, "load", side_effect=AssertionError("Runtime used fixture.load")),
            patch.object(fixture, "populate", side_effect=AssertionError("Runtime used fixture.populate")),
            patch.object(fixture, "build", side_effect=AssertionError("Runtime used fixture.build")),
        ):
            self.assert_values(self.execute(), MARCH_VALUES)

    def test_small_row_step_and_time_budgets_fail_explicitly_and_release_locks(self):
        for limits in (
            ExecutionLimits(max_source_rows=1),
            ExecutionLimits(max_vm_steps=100),
            ExecutionLimits(timeout_seconds=1e-12),
        ):
            with self.subTest(limits=limits):
                before = self.db.read_bytes()
                self.assert_kernel_error("budget_exceeded", execute_facts, self.db,
                                         request(), limits=limits)
                self.assertEqual(self.db.read_bytes(), before)
                self.assert_writer_available()
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_sqlite_execution_errors_are_structured_failures_not_success_packs(self):
        with patch.object(sqlite3, "connect", side_effect=sqlite3.OperationalError("synthetic failure")):
            self.assert_kernel_error("execution_failure", execute_facts, self.db, request())
        self.assert_writer_available()
        self.assert_values(self.execute(), MARCH_VALUES)

    def test_late_required_sum_overflow_fails_whole_batch_and_releases_transaction(self):
        self.mutate((
            "UPDATE booking_items SET seats=1, unit_price_minor=?, discount_minor=0 "
            "WHERE item_id IN ('I01','I02')", (2 ** 62,),
        ))
        self.assert_values(
            self.execute(request(metrics=["confirmed_booking_count"])),
            {"confirmed_booking_count": 7},
        )
        before = self.db.read_bytes()
        self.assert_kernel_error(
            "execution_failure", execute_facts, self.db,
            request(metrics=["confirmed_booking_count", "confirmed_booked_amount"]),
        )
        self.assertEqual(self.db.read_bytes(), before)
        self.assert_writer_available()

    def test_runtime_connection_rejects_writes_before_fact_authorization(self):
        from grepbit import kernel

        original = kernel._validate_source
        before = self.db.read_bytes()

        def probe(conn, budget):
            self.assertEqual(conn.execute("PRAGMA query_only").fetchone(), (1,))
            self.assertTrue(conn.in_transaction)
            name = conn.execute("SELECT name FROM centers WHERE center_id='CA'").fetchone()
            with self.assertRaises(sqlite3.OperationalError) as rejected:
                conn.execute("UPDATE centers SET name='untrusted write' WHERE center_id='CA'")
            self.assertEqual(rejected.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
            self.assertTrue(conn.in_transaction)
            self.assertEqual(
                conn.execute("SELECT name FROM centers WHERE center_id='CA'").fetchone(), name,
            )
            self.assertEqual(self.db.read_bytes(), before)
            return original(conn, budget)

        with patch.object(kernel, "_validate_source", side_effect=probe) as validation:
            self.assert_values(self.execute(), MARCH_VALUES)
        validation.assert_called_once()
        self.assertEqual(self.db.read_bytes(), before)
        self.assert_writer_available()

    def test_hostile_compiler_output_is_blocked_by_runtime_defenses(self):
        from grepbit import kernel

        attached = self.build_database("hostile-attachment.sqlite")
        before = {path: path.read_bytes() for path in (self.db, attached)}
        entries = set(self.root.iterdir())
        statements = (
            ("write", "UPDATE centers SET name='untrusted write' WHERE center_id='CA'", {}),
            ("attach", "ATTACH DATABASE :path AS hostile", {"path": str(attached)}),
            ("pragma", "PRAGMA query_only=OFF", {}),
            ("restricted_column",
             "SELECT COUNT(email) AS value, COUNT(*) AS population_rows FROM learners", {}),
            ("unreviewed_function", "SELECT length('untrusted') AS value, 1 AS population_rows", {}),
        )
        for name, sql, parameters in statements:
            with self.subTest(statement=name):
                with patch.object(kernel, "_compile", return_value=(sql, parameters)) as compiler:
                    self.assert_kernel_error(
                        "execution_failure", execute_facts, self.db,
                        request(metrics=["confirmed_booking_count"]),
                    )
                compiler.assert_called_once()
                for path, content in before.items():
                    self.assertEqual(path.read_bytes(), content)
                    self.assert_writer_available(path)
                self.assertEqual(set(self.root.iterdir()), entries)


if __name__ == "__main__":
    unittest.main()
