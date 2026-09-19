"""Offline scalar Compare regressions on disposable data, not model evaluations."""
from contextlib import closing, contextmanager
from dataclasses import replace
from fractions import Fraction
import inspect
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from typing import get_type_hints
import unittest
from unittest.mock import patch
from uuid import UUID

import grepbit
from grepbit import (
    AnalysisPack, CompareRequest, DerivedFact, ExecutionLimits, Fact, FactRequest,
    KernelError, SlotResult, execute_compare, execute_facts,
)
from grepbit import compare, kernel
from grepbit.catalog import LEARNINGOPS
from grepbit.contracts import utc_text
from tools import fixture


INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def scope_mapping(start, end, **changes):
    result = {
        "metrics": ["confirmed_booked_amount"],
        "start": start,
        "end": end,
        "timezone": "Asia/Taipei",
    }
    result.update(changes)
    return result


def compare_mapping():
    return {
        "current": scope_mapping("2026-03-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00"),
        "baseline": scope_mapping("2026-02-01T00:00:00+08:00", "2026-03-01T00:00:00+08:00"),
    }


class CompareAssertions(unittest.TestCase):
    def assert_kernel_error(self, code, function, *args, **kwargs):
        with self.assertRaises(KernelError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        self.assertTrue(str(raised.exception))
        return raised.exception


class CompareRequestTests(CompareAssertions):
    def test_explicit_scope_round_trip(self):
        request = CompareRequest.from_mapping(compare_mapping())
        self.assertIsInstance(request.current, FactRequest)
        self.assertIsInstance(request.baseline, FactRequest)
        self.assertEqual(request.current.metrics, ("confirmed_booked_amount",))
        self.assertIsNone(request.current.center_id)
        self.assertIsNone(request.baseline.center_id)
        self.assertEqual(
            CompareRequest.from_mapping(json.loads(json.dumps(request.to_dict()))), request,
        )
        self.assertEqual(set(request.to_dict()), {"current", "baseline"})

    def test_constructor_and_execution_signatures_are_typed_and_bounded(self):
        self.assertEqual(tuple(inspect.signature(CompareRequest).parameters), ("current", "baseline"))
        self.assertEqual(get_type_hints(CompareRequest), {
            "current": FactRequest, "baseline": FactRequest,
        })
        signature = inspect.signature(execute_compare)
        self.assertEqual(tuple(signature.parameters), ("database", "request", "limits"))
        self.assertEqual(signature.parameters["limits"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(signature.parameters["limits"].default, ExecutionLimits())
        self.assertEqual(get_type_hints(execute_compare), {
            "database": Path, "request": CompareRequest,
            "limits": ExecutionLimits, "return": AnalysisPack,
        })
        for name in ("CompareRequest", "AnalysisPack", "DerivedFact", "SlotResult", "execute_compare"):
            self.assertIn(name, grepbit.__all__)
        for name in ("_check_compatibility", "_difference", "_relative_change", "_execute_scope"):
            self.assertNotIn(name, grepbit.__all__)
            self.assertFalse(hasattr(grepbit, name))

    def test_direct_constructor_rejects_untyped_scopes(self):
        request = CompareRequest.from_mapping(compare_mapping())
        for field in ("current", "baseline"):
            for value in (None, {}, [], compare_mapping()[field], 1, True):
                with self.subTest(field=field, value=value):
                    self.assert_kernel_error("invalid_request", replace, request, **{field: value})

    def test_current_and_baseline_are_both_required(self):
        for field in ("current", "baseline"):
            with self.subTest(field=field):
                data = compare_mapping()
                del data[field]
                self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_nonobject_requests_and_scopes_are_rejected(self):
        for value in (None, [], "", "compare", 0, True):
            with self.subTest(root=value):
                self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, value)
            for field in ("current", "baseline"):
                with self.subTest(field=field, value=value):
                    data = compare_mapping()
                    data[field] = value
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_third_scope_recipe_formula_and_execution_extras_are_rejected(self):
        extras = {
            "third": compare_mapping()["current"],
            "scopes": [],
            "recipe": "compare",
            "recipe_id": "compare",
            "recipe_version": "0.1",
            "formula": "current - baseline",
            "filters": {"status": "draft"},
            "sql": "SELECT 1",
            "catalog": {"version": "caller"},
            "facts": [],
            "callback": None,
        }
        for field, value in extras.items():
            with self.subTest(field=field):
                data = compare_mapping()
                data[field] = value
                self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_scopes_reject_recipe_formula_filters_and_caller_fact_ids(self):
        extras = {
            "recipe": "compare", "formula": "SUM(amount)", "filters": {"center_id": "CA"},
            "fact_id": "caller-supplied", "sql": "SELECT 1", "catalog": LEARNINGOPS.version,
            "year": 2026, "month": 3,
        }
        for scope in ("current", "baseline"):
            for field, value in extras.items():
                with self.subTest(scope=scope, field=field):
                    data = compare_mapping()
                    data[scope][field] = value
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_each_scope_requires_all_standard_fact_request_fields(self):
        for scope in ("current", "baseline"):
            for field in ("metrics", "start", "end", "timezone"):
                with self.subTest(scope=scope, field=field):
                    data = compare_mapping()
                    del data[scope][field]
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_malformed_or_missing_year_month_and_offset_are_not_inferred(self):
        invalid = (
            "03-01T00:00:00+08:00", "2026-01T00:00:00+08:00",
            "2026-00-01T00:00:00+08:00", "2026-13-01T00:00:00+08:00",
            "2026-02-29T00:00:00+08:00", "March", "last month",
            "2026-03", "2026-03-01", "2026-03-01T00:00:00",
            "2026-03-01T00:00:00+00:60", None, 202603,
        )
        for scope in ("current", "baseline"):
            for field in ("start", "end"):
                for value in invalid:
                    with self.subTest(scope=scope, field=field, value=value):
                        data = compare_mapping()
                        data[scope][field] = value
                        self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_partial_month_boundaries_are_rejected(self):
        periods = (
            ("2026-03-02T00:00:00+08:00", "2026-04-01T00:00:00+08:00"),
            ("2026-03-01T00:00:01+08:00", "2026-04-01T00:00:00+08:00"),
            ("2026-03-01T00:00:00.000001+08:00", "2026-04-01T00:00:00+08:00"),
            ("2026-03-01T00:00:00+08:00", "2026-03-31T23:59:59+08:00"),
            ("2026-03-01T00:00:00+08:00", "2026-04-01T00:00:00.000001+08:00"),
            ("2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z"),
        )
        for scope in ("current", "baseline"):
            for start, end in periods:
                with self.subTest(scope=scope, start=start, end=end):
                    data = compare_mapping()
                    data[scope] = scope_mapping(start, end)
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_multimonth_empty_and_reversed_periods_are_rejected(self):
        for start, end in (
            ("2026-03-01T00:00:00+08:00", "2026-05-01T00:00:00+08:00"),
            ("2025-03-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00"),
            ("2026-03-01T00:00:00+08:00", "2026-03-01T00:00:00+08:00"),
            ("2026-04-01T00:00:00+08:00", "2026-03-01T00:00:00+08:00"),
        ):
            for scope in ("current", "baseline"):
                with self.subTest(scope=scope, start=start, end=end):
                    data = compare_mapping()
                    data[scope] = scope_mapping(start, end)
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_identical_months_are_rejected_even_with_equivalent_offsets(self):
        for baseline in (
            compare_mapping()["current"],
            scope_mapping("2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z"),
        ):
            with self.subTest(baseline=baseline):
                data = compare_mapping()
                data["baseline"] = baseline
                self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_wrong_metric_and_multiple_metrics_are_rejected(self):
        for scope in ("current", "baseline"):
            for metrics in (
                ["confirmed_booking_count"], ["booked_seats"], ["known_booking_accounts"],
                ["unknown_metric"], ["confirmed_booked_amount", "booked_seats"], [],
            ):
                with self.subTest(scope=scope, metrics=metrics):
                    data = compare_mapping()
                    data[scope]["metrics"] = metrics
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_wrong_timezone_is_rejected_even_when_its_offset_matches(self):
        for scope in ("current", "baseline"):
            for zone in ("UTC", "Asia/Shanghai", "Etc/GMT-8", None):
                with self.subTest(scope=scope, zone=zone):
                    data = compare_mapping()
                    data[scope]["timezone"] = zone
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)

    def test_center_filter_is_not_admitted_but_explicit_null_is(self):
        for scope in ("current", "baseline"):
            for center in ("CA", "CTR-A01", ""):
                with self.subTest(scope=scope, center=center):
                    data = compare_mapping()
                    data[scope]["center_id"] = center
                    self.assert_kernel_error("invalid_request", CompareRequest.from_mapping, data)
        data = compare_mapping()
        for scope in data.values():
            scope["center_id"] = None
        self.assertEqual(CompareRequest.from_mapping(data), CompareRequest.from_mapping(compare_mapping()))


class CompareFixture(CompareAssertions):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "learning.sqlite"
        fixture.build(self.db)
        self.request = CompareRequest.from_mapping(compare_mapping())

    def execute(self, request=None, **kwargs):
        pack = execute_compare(self.db, self.request if request is None else request, **kwargs)
        self.assertIsInstance(pack, AnalysisPack)
        return pack

    def mutate(self, *statements):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                for sql, parameters in statements:
                    conn.execute(sql, parameters)

    def zero_scope(self, scope):
        self.mutate((
            "UPDATE booking_items SET unit_price_minor=0, discount_minor=0 WHERE booking_id IN "
            "(SELECT booking_id FROM bookings WHERE status='confirmed' "
            "AND created_at_utc>=? AND created_at_utc<?)",
            (utc_text(scope.start), utc_text(scope.end)),
        ))

    def empty_scope(self, scope):
        self.mutate((
            "UPDATE bookings SET status='cancelled' "
            "WHERE created_at_utc>=? AND created_at_utc<?",
            (utc_text(scope.start), utc_text(scope.end)),
        ))

    def add_amount(self, booking_id, instant, amount):
        self.mutate(
            ("INSERT INTO bookings VALUES (?, 'CA', NULL, ?, 'confirmed', 'TWD')",
             (booking_id, instant)),
            ("INSERT INTO booking_items VALUES (?, ?, 'S01', 'CA', 1, ?, 0)",
             ("I_" + booking_id, booking_id, amount)),
        )

    def assert_writer_available(self):
        with closing(sqlite3.connect(self.db, timeout=0)) as conn:
            conn.execute("BEGIN EXCLUSIVE")
            conn.execute("UPDATE centers SET name=name WHERE center_id='CA'")
            conn.rollback()

    @contextmanager
    def capture_connections(self):
        connect = sqlite3.connect
        connections, traces = [], []

        def traced_connect(*args, **kwargs):
            conn = connect(*args, **kwargs)
            connections.append(conn)
            conn.set_trace_callback(
                lambda sql: traces.append((sql.strip().upper(), conn.in_transaction))
            )
            return conn

        with patch.object(sqlite3, "connect", side_effect=traced_connect):
            yield connections, traces

    def assert_closed(self, connections):
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def assert_failure_closed(self, code, *, database=None, **kwargs):
        database = self.db if database is None else database
        before = database.read_bytes() if database.exists() else None
        with (
            self.capture_connections() as (connections, _),
            patch.object(compare, "AnalysisPack", wraps=AnalysisPack) as pack_constructor,
        ):
            error = self.assert_kernel_error(
                code, execute_compare, database, self.request, **kwargs,
            )
        pack_constructor.assert_not_called()
        self.assert_closed(connections)
        if before is None:
            self.assertFalse(database.exists())
        else:
            self.assertEqual(database.read_bytes(), before)
        self.assert_writer_available()
        return error

    def assert_values(self, pack, current, baseline, delta, growth):
        self.assertEqual(tuple(fact.value for fact in pack.facts), (current, baseline))
        self.assertEqual(tuple(fact.value for fact in pack.derived_facts), (delta, growth))
        for fact in pack.facts:
            if fact.value is not None:
                self.assertIs(type(fact.value), int)
        if delta is not None:
            self.assertIs(type(pack.derived_facts[0].value), int)
        if growth is not None:
            self.assertIs(type(pack.derived_facts[1].value), Fraction)

    def assert_empty_result(self, pack, current, baseline):
        self.assert_values(pack, current, baseline, None, None)
        self.assertEqual(pack.status, "failed")
        self.assertEqual(tuple(slot.slot_id for slot in pack.slots),
                         ("current", "baseline", "delta", "growth"))
        self.assertEqual(tuple(slot.state for slot in pack.slots),
                         ("checked", "checked", "unavailable", "unavailable"))
        self.assertEqual(tuple(slot.reason for slot in pack.slots),
                         (None, None, "empty_input", "unavailable_difference"))
        for fact in pack.facts:
            self.assertEqual(fact.completeness, "complete")
            self.assertTrue(fact.checks)
            self.assertEqual(fact.empty_population, fact.value is None)
            self.assertEqual(fact.population_rows == 0, fact.value is None)
        self.assertEqual(tuple(f.reason for f in pack.derived_facts),
                         ("empty_input", "unavailable_difference"))
        self.assertEqual(tuple(f.state for f in pack.derived_facts),
                         ("unavailable", "unavailable"))
        document = json.loads(json.dumps(pack.to_dict(), allow_nan=False))
        self.assertEqual(document["status"], "failed")
        self.assertTrue(all(fact["value"] is None for fact in document["derived_facts"]))


class CompareValueTests(CompareFixture):
    def test_e02_exact_amounts_difference_growth_and_required_coverage(self):
        pack = self.execute()
        self.assert_values(pack, 158000, 50000, 108000, Fraction(54, 25))
        self.assertEqual(pack.request, self.request)
        self.assertEqual((pack.recipe_id, pack.recipe_version, pack.status), ("compare", "0.1", "complete"))
        self.assertEqual(tuple(slot.slot_id for slot in pack.slots),
                         ("current", "baseline", "delta", "growth"))
        self.assertTrue(all(isinstance(slot, SlotResult) for slot in pack.slots))
        self.assertTrue(all(slot.state == "checked" and slot.reason is None for slot in pack.slots))
        self.assertEqual(tuple(f.population_rows for f in pack.facts), (8, 3))
        self.assertTrue(all(not fact.empty_population for fact in pack.facts))
        self.assertEqual(tuple(f.unit for f in pack.derived_facts), ("TWD_minor", "dimensionless"))

    def test_derived_provenance_reaches_exact_inputs_and_shared_snapshot(self):
        pack = self.execute()
        current, baseline = pack.facts
        delta, growth = pack.derived_facts
        self.assertEqual((delta.derivation, growth.derivation), ("difference", "relative_change"))
        self.assertEqual(delta.input_fact_ids, (current.fact_id, baseline.fact_id))
        self.assertEqual(growth.input_fact_ids, (delta.fact_id, baseline.fact_id))
        self.assertEqual(tuple(slot.fact_id for slot in pack.slots),
                         tuple(fact.fact_id for fact in (*pack.facts, *pack.derived_facts)))
        self.assertEqual({fact.snapshot_id for fact in (*pack.facts, *pack.derived_facts)},
                         {pack.snapshot["id"]})
        self.assertEqual(pack.snapshot["scope"], "single_read_transaction")
        self.assertEqual(pack.snapshot["identity_kind"],
                         "ephemeral_batch_not_persistent_database_version")
        for fact, scope in zip(pack.facts, (self.request.current, self.request.baseline)):
            self.assertEqual((fact.start_utc, fact.end_utc), (utc_text(scope.start), utc_text(scope.end)))
            self.assertEqual(fact.filters, {})
            self.assertEqual((fact.catalog_id, fact.catalog_sha256),
                             (LEARNINGOPS.version, LEARNINGOPS.digest()))
            self.assertEqual(fact.completeness, "complete")

    def test_fact_ids_are_opaque_unique_uuids_including_repeated_analyses(self):
        first, second = self.execute(), self.execute()
        identifiers = []
        for pack in (first, second):
            identifiers.extend(fact.fact_id for fact in (*pack.facts, *pack.derived_facts))
            identifiers.append(pack.snapshot["id"])
        self.assertEqual(len(set(identifiers)), 10)
        for identifier in identifiers:
            self.assertEqual(str(UUID(identifier)), identifier)
            self.assertEqual(UUID(identifier).version, 4)
        self.assert_values(second, 158000, 50000, 108000, Fraction(54, 25))

    def test_p1_fact_ids_remain_additive_keyword_only_evidence(self):
        request = replace(self.request.current, metrics=(
            "confirmed_booked_amount", "confirmed_booking_count",
            "booked_seats", "known_booking_accounts",
        ))
        pack = execute_facts(self.db, request)
        self.assertEqual(tuple(fact.value for fact in pack.facts), (158000, 7, 12, 5))
        self.assertEqual(inspect.signature(Fact).parameters["fact_id"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(set(pack.to_dict()), {
            "request", "facts", "snapshot", "runtime", "execution", "limitations", "status",
        })
        identifiers = [fact["fact_id"] for fact in pack.to_dict()["facts"]]
        self.assertEqual(len(set(identifiers)), 4)
        for identifier in identifiers:
            self.assertEqual(str(UUID(identifier)), identifier)
            self.assertEqual(UUID(identifier).version, 4)

    def test_json_shape_preserves_exact_rational_not_a_float_or_percent(self):
        pack = self.execute()
        document = json.loads(json.dumps(pack.to_dict(), allow_nan=False))
        self.assertEqual(set(document), {
            "request", "facts", "derived_facts", "slots", "snapshot",
            "runtime", "execution", "limitations", "recipe_id", "recipe_version", "status",
        })
        self.assertEqual(document["request"], self.request.to_dict())
        self.assertEqual(document["status"], "complete")
        self.assertEqual(document["recipe_id"], "compare")
        self.assertEqual(document["recipe_version"], "0.1")
        self.assertEqual(document["derived_facts"][0]["value"], 108000)
        self.assertEqual(document["derived_facts"][1]["value"], {"numerator": 54, "denominator": 25})
        for value in document["derived_facts"][1]["value"].values():
            self.assertIs(type(value), int)
        for fact in document["derived_facts"]:
            self.assertEqual(set(fact), {
                "derivation", "input_fact_ids", "value", "unit",
                "snapshot_id", "state", "reason", "fact_id",
            })
        self.assertEqual(document["derived_facts"][1]["input_fact_ids"],
                         [pack.derived_facts[0].fact_id, pack.facts[1].fact_id])
        self.assertEqual(len(document["slots"]), 4)
        self.assertEqual(set(document["runtime"]), {"python", "sqlite", "sqlglot"})
        self.assertTrue(document["execution"])
        self.assertIn("without per-day normalization", " ".join(document["limitations"]))
        self.assertIn("not user intent or source truth", " ".join(document["limitations"]))

    def test_changed_source_changes_both_facts_and_derivations(self):
        self.mutate(
            ("UPDATE booking_items SET unit_price_minor=unit_price_minor+123 WHERE item_id='I01'", ()),
            ("UPDATE booking_items SET unit_price_minor=unit_price_minor+17 WHERE item_id='I12'", ()),
        )
        self.assert_values(self.execute(), 158246, 50034, 108212, Fraction(54106, 25017))

    def test_nonempty_zero_baseline_is_undefined_but_complete(self):
        self.zero_scope(self.request.baseline)
        pack = self.execute()
        self.assert_values(pack, 158000, 0, 158000, None)
        self.assertEqual(pack.status, "complete")
        self.assertEqual((pack.facts[1].population_rows, pack.facts[1].empty_population), (3, False))
        self.assertEqual(tuple(slot.state for slot in pack.slots),
                         ("checked", "checked", "checked", "undefined"))
        growth = pack.derived_facts[1]
        self.assertEqual((growth.state, growth.reason), ("undefined", "zero_baseline"))
        self.assertEqual(pack.slots[3].reason, "zero_baseline")
        self.assertIsNone(pack.to_dict()["derived_facts"][1]["value"])

    def test_both_nonempty_zero_amounts_do_not_invent_zero_growth(self):
        self.zero_scope(self.request.current)
        self.zero_scope(self.request.baseline)
        pack = self.execute()
        self.assert_values(pack, 0, 0, 0, None)
        self.assertEqual(pack.status, "complete")
        self.assertTrue(all(fact.population_rows > 0 and not fact.empty_population for fact in pack.facts))
        self.assertEqual(pack.derived_facts[0].state, "checked")
        self.assertEqual((pack.derived_facts[1].state, pack.derived_facts[1].reason),
                         ("undefined", "zero_baseline"))

    def test_current_zero_against_positive_baseline_is_exact_negative_one(self):
        self.zero_scope(self.request.current)
        pack = self.execute()
        self.assert_values(pack, 0, 50000, -50000, Fraction(-1, 1))
        self.assertEqual(pack.status, "complete")
        self.assertEqual(pack.to_dict()["derived_facts"][1]["value"],
                         {"numerator": -1, "denominator": 1})

    def test_negative_relative_change_is_reduced_and_unclamped(self):
        self.zero_scope(self.request.current)
        self.mutate(("UPDATE booking_items SET unit_price_minor=10000 WHERE item_id='I01'", ()))
        pack = self.execute()
        self.assert_values(pack, 20000, 50000, -30000, Fraction(-3, 5))
        self.assertEqual(pack.to_dict()["derived_facts"][1]["value"],
                         {"numerator": -3, "denominator": 5})

    def test_equal_positive_amounts_have_exact_zero_growth(self):
        self.zero_scope(self.request.current)
        self.mutate(("UPDATE booking_items SET unit_price_minor=25000 WHERE item_id='I01'", ()))
        pack = self.execute()
        self.assert_values(pack, 50000, 50000, 0, Fraction(0, 1))
        self.assertEqual(pack.status, "complete")
        self.assertEqual(pack.derived_facts[1].state, "checked")

    def test_values_above_binary_float_precision_remain_exact(self):
        self.zero_scope(self.request.current)
        self.zero_scope(self.request.baseline)
        self.mutate(
            ("UPDATE booking_items SET seats=1, unit_price_minor=? WHERE item_id='I01'", (2**53 + 1,)),
            ("UPDATE booking_items SET unit_price_minor=? WHERE item_id='I10'", (2**53,)),
        )
        pack = self.execute()
        self.assert_values(pack, 2**53 + 1, 2**53, 1, Fraction(1, 2**53))
        self.assertEqual(pack.to_dict()["derived_facts"][1]["value"],
                         {"numerator": 1, "denominator": 2**53})

    def test_empty_baseline_is_checked_null_and_required_derivations_fail(self):
        self.empty_scope(self.request.baseline)
        self.assert_empty_result(self.execute(), 158000, None)

    def test_confirmed_baseline_booking_without_lines_is_not_numeric_zero(self):
        data = compare_mapping()
        data["baseline"] = scope_mapping("2026-01-01T00:00:00+08:00", "2026-02-01T00:00:00+08:00")
        request = CompareRequest.from_mapping(data)
        self.mutate((
            "INSERT INTO bookings VALUES ('B_NO_LINES', 'CA', NULL, "
            "'2026-01-10T00:00:00Z', 'confirmed', 'TWD')", (),
        ))
        count = execute_facts(self.db, replace(request.baseline, metrics=("confirmed_booking_count",)))
        self.assertEqual(count.facts[0].value, 1)
        self.assert_empty_result(self.execute(request), 158000, None)

    def test_empty_current_does_not_become_a_negative_baseline_difference(self):
        self.empty_scope(self.request.current)
        self.assert_empty_result(self.execute(), None, 50000)

    def test_both_empty_scopes_are_failed_not_zero_over_zero(self):
        self.empty_scope(self.request.current)
        self.empty_scope(self.request.baseline)
        self.assert_empty_result(self.execute(), None, None)

    def test_cross_year_january_and_december_are_explicit_half_open_months(self):
        for identifier, instant, amount in (
            ("B_DEC_START", "2025-11-30T16:00:00Z", 20),
            ("B_DEC_END", "2025-12-31T15:59:59Z", 10),
            ("B_JAN_START", "2025-12-31T16:00:00Z", 40),
            ("B_JAN_END", "2026-01-31T15:59:59Z", 20),
            ("B_FEB_START", "2026-01-31T16:00:00Z", 999),
        ):
            self.add_amount(identifier, instant, amount)
        request = CompareRequest.from_mapping({
            "current": scope_mapping("2026-01-01T00:00:00+08:00", "2026-02-01T00:00:00+08:00"),
            "baseline": scope_mapping("2025-12-01T00:00:00+08:00", "2026-01-01T00:00:00+08:00"),
        })
        pack = self.execute(request)
        self.assert_values(pack, 60, 30, 30, Fraction(1, 1))
        self.assertEqual(tuple(fact.population_rows for fact in pack.facts), (2, 2))

    def test_leap_february_includes_last_second_and_excludes_march_boundary(self):
        for identifier, instant, amount in (
            ("B_JAN_LEAP", "2024-01-31T15:59:59Z", 30),
            ("B_FEB_LEAP", "2024-01-31T16:00:00Z", 40),
            ("B_LEAP_DAY", "2024-02-29T15:59:59Z", 20),
            ("B_MAR_LEAP", "2024-02-29T16:00:00Z", 999),
        ):
            self.add_amount(identifier, instant, amount)
        request = CompareRequest.from_mapping({
            "current": scope_mapping("2024-02-01T00:00:00+08:00", "2024-03-01T00:00:00+08:00"),
            "baseline": scope_mapping("2024-01-01T00:00:00+08:00", "2024-02-01T00:00:00+08:00"),
        })
        pack = self.execute(request)
        self.assert_values(pack, 60, 30, 30, Fraction(1, 1))
        self.assertEqual(pack.facts[0].end_utc, "2024-02-29T16:00:00Z")

    def test_equivalent_explicit_offsets_preserve_taipei_months_and_values(self):
        request = CompareRequest.from_mapping({
            "current": scope_mapping("2026-02-28T11:00:00-05:00", "2026-03-31T11:00:00-05:00"),
            "baseline": scope_mapping("2026-01-31T16:00:00Z", "2026-02-28T16:00:00Z"),
        })
        pack = self.execute(request)
        self.assert_values(pack, 158000, 50000, 108000, Fraction(54, 25))
        self.assertEqual(tuple((fact.start_utc, fact.end_utc) for fact in pack.facts), (
            ("2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z"),
            ("2026-01-31T16:00:00Z", "2026-02-28T16:00:00Z"),
        ))


class CompareCompatibilityTests(CompareFixture):
    def setUp(self):
        super().setUp()
        self.checked = self.execute()
        self.current, self.baseline = self.checked.facts

    def assert_incompatible(self, field, value):
        changed = replace(self.baseline, **{field: value})
        self.assert_kernel_error(
            "incompatible_facts", compare._check_compatibility,
            self.request, self.current, changed, self.checked.snapshot["id"],
        )
        execute_scope = kernel._execute_scope

        def altered_scope(conn, request, compiled, catalog, snapshot_id, budget):
            facts = execute_scope(conn, request, compiled, catalog, snapshot_id, budget)
            if request == self.request.baseline:
                return (replace(facts[0], **{field: value}),)
            return facts

        with (
            patch.object(kernel, "_execute_scope", side_effect=altered_scope) as scopes,
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            self.assert_failure_closed("incompatible_facts")
        self.assertEqual(scopes.call_count, 2)
        difference.assert_not_called()

    def test_compatible_checked_facts_are_admitted(self):
        self.assertIsNone(compare._check_compatibility(
            self.request, self.current, self.baseline, self.checked.snapshot["id"],
        ))

    def test_mismatched_unit_is_rejected_before_difference(self):
        self.assert_incompatible("unit", "USD_minor")

    def test_mismatched_catalog_id_is_rejected_before_difference(self):
        self.assert_incompatible("catalog_id", "other-catalog")

    def test_mismatched_catalog_digest_is_rejected_before_difference(self):
        self.assert_incompatible("catalog_sha256", "0" * 64)

    def test_mismatched_metric_is_rejected_before_difference(self):
        self.assert_incompatible("metric_id", "confirmed_booking_count")

    def test_mismatched_population_is_rejected_before_difference(self):
        self.assert_incompatible("population", "All bookings including cancelled bookings.")

    def test_mismatched_grain_is_rejected_before_difference(self):
        self.assert_incompatible("grain", "booking")

    def test_mismatched_filters_are_rejected_before_difference(self):
        self.assert_incompatible("filters", {"center_id": "CA"})

    def test_mismatched_time_basis_is_rejected_before_difference(self):
        self.assert_incompatible("time_basis", "sessions.starts_at_utc")

    def test_mismatched_timezone_is_rejected_before_difference(self):
        self.assert_incompatible("business_timezone", "UTC")

    def test_mismatched_snapshot_is_rejected_before_difference(self):
        self.assert_incompatible("snapshot_id", "another-snapshot")

    def test_wrong_batch_snapshot_is_rejected_even_if_fact_snapshots_agree(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._check_compatibility,
            self.request, self.current, self.baseline, "another-batch",
        )

    def test_incomplete_input_is_rejected_before_difference(self):
        self.assert_incompatible("completeness", "partial")

    def test_missing_required_check_is_rejected_before_difference(self):
        for check in self.baseline.checks:
            with self.subTest(check=check):
                self.assert_incompatible("checks", tuple(item for item in self.baseline.checks if item != check))

    def test_changed_exclusion_evidence_is_rejected_before_difference(self):
        self.assert_incompatible("excluded_anonymous_rows", 0)

    def test_changed_disclosures_are_rejected_before_difference(self):
        self.assert_incompatible("disclosures", ())

    def test_wrong_bound_start_is_rejected_before_difference(self):
        self.assert_incompatible("start_utc", "2026-01-31T16:00:01Z")

    def test_wrong_bound_end_is_rejected_before_difference(self):
        self.assert_incompatible("end_utc", "2026-02-28T15:59:59Z")

    def test_swapped_fact_roles_are_rejected_before_difference(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._check_compatibility,
            self.request, self.baseline, self.current, self.checked.snapshot["id"],
        )
        check = compare._check_compatibility
        with (
            patch.object(compare, "_check_compatibility",
                         side_effect=lambda request, current, baseline, snapshot:
                         check(request, baseline, current, snapshot)),
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            self.assert_failure_closed("incompatible_facts")
        difference.assert_not_called()

    def test_duplicate_fact_identity_is_rejected_before_difference(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._check_compatibility, self.request, self.current,
            replace(self.baseline, fact_id=self.current.fact_id), self.checked.snapshot["id"],
        )
        execute_scope = kernel._execute_scope
        observed = []

        def duplicate_identity(*args):
            fact, = execute_scope(*args)
            if observed:
                fact = replace(fact, fact_id=observed[0].fact_id)
            observed.append(fact)
            return (fact,)

        with (
            patch.object(kernel, "_execute_scope", side_effect=duplicate_identity),
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            self.assert_failure_closed("incompatible_facts")
        self.assertEqual(len(observed), 2)
        difference.assert_not_called()

    def test_missing_fact_identity_is_rejected_before_difference(self):
        self.assert_incompatible("fact_id", "")

    def test_noninteger_amounts_are_rejected_before_difference(self):
        for value in (True, 50000.0, "50000", Fraction(50000, 1)):
            with self.subTest(value=value):
                self.assert_incompatible("value", value)

    def test_out_of_int64_amounts_are_rejected_before_difference(self):
        for value in (INT64_MIN - 1, INT64_MAX + 1):
            with self.subTest(value=value):
                self.assert_incompatible("value", value)

    def test_invalid_population_row_type_or_sign_is_rejected_before_difference(self):
        for rows in (True, 3.0, "3", -1):
            with self.subTest(rows=rows):
                self.assert_incompatible("population_rows", rows)

    def test_null_with_nonempty_evidence_is_rejected_before_difference(self):
        self.assert_incompatible("value", None)

    def test_empty_flag_with_nonempty_rows_is_rejected_before_difference(self):
        self.assert_incompatible("empty_population", True)

    def test_nonboolean_empty_flag_is_rejected_before_difference(self):
        self.assert_incompatible("empty_population", 0)

    def test_zero_population_rows_with_numeric_amount_is_rejected_before_difference(self):
        self.assert_incompatible("population_rows", 0)

    def test_difference_accepts_exact_signed_int64_boundaries(self):
        # Signed copies exercise the arithmetic guard; negative source amounts are not admitted.
        for current, baseline, expected in (
            (INT64_MAX, 0, INT64_MAX), (INT64_MIN, 0, INT64_MIN),
            (0, INT64_MIN + 1, INT64_MAX), (-1, INT64_MAX, INT64_MIN),
            (INT64_MAX, INT64_MAX, 0), (INT64_MIN, INT64_MIN, 0),
        ):
            with self.subTest(current=current, baseline=baseline):
                difference = compare._difference(
                    replace(self.current, value=current), replace(self.baseline, value=baseline),
                )
                self.assertIs(type(difference.value), int)
                self.assertEqual(difference.value, expected)
                self.assertEqual((difference.state, difference.reason), ("checked", None))
                self.assertEqual(difference.input_fact_ids, (self.current.fact_id, self.baseline.fact_id))

    def test_difference_overflow_on_signed_copies_is_explicit(self):
        for current, baseline in (
            (INT64_MAX, -1), (INT64_MIN, 1),
            (INT64_MAX, INT64_MIN), (INT64_MIN, INT64_MAX),
        ):
            with self.subTest(current=current, baseline=baseline):
                self.assert_kernel_error(
                    "arithmetic_overflow", compare._difference,
                    replace(self.current, value=current), replace(self.baseline, value=baseline),
                )

    def test_relative_change_rejects_a_different_baseline_id(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._relative_change, self.checked.derived_facts[0],
            replace(self.baseline, fact_id=self.current.fact_id),
        )

    def test_relative_change_rejects_a_different_snapshot(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._relative_change, self.checked.derived_facts[0],
            replace(self.baseline, snapshot_id="another-snapshot"),
        )

    def test_relative_change_rejects_a_different_unit(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._relative_change, self.checked.derived_facts[0],
            replace(self.baseline, unit="USD_minor"),
        )

    def test_relative_change_rejects_a_non_difference_derivation(self):
        self.assert_kernel_error(
            "incompatible_facts", compare._relative_change,
            replace(self.checked.derived_facts[0], derivation="relative_change"), self.baseline,
        )

    def test_relative_change_rejects_noninteger_checked_difference(self):
        for value in (True, 108000.0, Fraction(108000, 1), None):
            with self.subTest(value=value):
                self.assert_kernel_error(
                    "incompatible_facts", compare._relative_change,
                    replace(self.checked.derived_facts[0], value=value), self.baseline,
                )


class CompareExecutionTests(CompareFixture):
    def test_public_execution_rejects_mappings_fact_inputs_and_untyped_limits(self):
        pack = self.execute()
        for request in (compare_mapping(), self.request.current, pack.facts, pack.facts[0], None):
            with self.subTest(request_type=type(request).__name__):
                self.assert_kernel_error("invalid_request", execute_compare, self.db, request)
        for limits in (None, {}, 1):
            with self.subTest(limits=limits):
                self.assert_kernel_error(
                    "invalid_request", execute_compare, self.db, self.request, limits=limits,
                )

    def test_public_execution_exposes_no_trusted_facts_sql_callback_or_catalog_argument(self):
        extras = {
            "facts": (), "current_fact": None, "baseline_fact": None,
            "sql": "SELECT 1", "callback": lambda: None,
            "catalog": LEARNINGOPS, "connection": None,
        }
        with patch.object(kernel, "_read_transaction",
                          side_effect=AssertionError("Untrusted input reached execution")) as transaction:
            for field, value in extras.items():
                with self.subTest(field=field):
                    with self.assertRaises(TypeError):
                        execute_compare(self.db, self.request, **{field: value})
        transaction.assert_not_called()

    def test_database_argument_cannot_be_a_connection_or_sql(self):
        with closing(sqlite3.connect(self.db)) as conn:
            for value in (conn, "SELECT 1", str(self.db)):
                with self.subTest(value_type=type(value).__name__):
                    self.assert_kernel_error("invalid_request", execute_compare, value, self.request)
            self.assertEqual(conn.execute("SELECT 1").fetchone(), (1,))

    def test_one_connection_transaction_validation_and_budget_serve_both_scopes(self):
        events, observations = [], []
        compile_scope, execute_scope = kernel._compile_scope, kernel._execute_scope
        validate_source = kernel._validate_source

        def compiled(request, catalog):
            events.append(("compile", request))
            return compile_scope(request, catalog)

        def validated(conn, budget):
            events.append(("validate", None))
            return validate_source(conn, budget)

        def scoped(conn, request, compiled, catalog, snapshot_id, budget):
            before = (budget.callbacks, budget.rows)
            facts = execute_scope(conn, request, compiled, catalog, snapshot_id, budget)
            observations.append((conn, budget, before, (budget.callbacks, budget.rows)))
            return facts

        with (
            self.capture_connections() as (connections, traces),
            patch.object(kernel, "_Budget", wraps=kernel._Budget) as budgets,
            patch.object(kernel, "_compile_scope", side_effect=compiled) as compilation,
            patch.object(kernel, "_validate_source", side_effect=validated) as validation,
            patch.object(kernel, "_execute_scope", side_effect=scoped) as scopes,
            patch.object(kernel, "execute_facts", side_effect=AssertionError("No separate P1 batches")),
            patch.object(grepbit, "execute_facts", side_effect=AssertionError("No exported P1 batches")),
        ):
            pack = self.execute()
        self.assert_values(pack, 158000, 50000, 108000, Fraction(54, 25))
        self.assertEqual(len(connections), 1)
        self.assertEqual([sql for sql, _ in traces if sql.startswith("BEGIN")], ["BEGIN"])
        self.assertTrue(all(active for sql, active in traces if sql.startswith("SELECT")))
        self.assertEqual(events, [
            ("compile", self.request.current), ("compile", self.request.baseline), ("validate", None),
        ])
        self.assertEqual(compilation.call_count, 2)
        validation.assert_called_once()
        budgets.assert_called_once_with(ExecutionLimits())
        self.assertEqual(scopes.call_count, 2)
        self.assertEqual(len(observations), 2)
        self.assertIs(observations[0][0], connections[0])
        self.assertIs(observations[1][0], connections[0])
        self.assertIs(observations[0][1], observations[1][1])
        self.assertIs(validation.call_args.args[1], observations[0][1])
        self.assertEqual(observations[0][3], observations[1][2])
        self.assertGreater(observations[0][2][0], 0)
        self.assertGreater(observations[0][3][0], observations[0][2][0])
        self.assertGreaterEqual(observations[1][3][0], observations[1][2][0])
        self.assertEqual(pack.execution["progress_callbacks"], observations[1][3][0])
        self.assertEqual(pack.execution["source_rows_validated"], 31)
        self.assertEqual({item[2][1] for item in observations} | {item[3][1] for item in observations}, {31})
        self.assertEqual(pack.execution["vm_step_check_interval"], 100)
        self.assert_closed(connections)
        self.assert_writer_available()

    def test_real_wal_writer_commit_between_scopes_cannot_mix_snapshots(self):
        execute_scope = kernel._execute_scope
        observed, outside_values = [], []
        committed = False
        with closing(sqlite3.connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")

            def race(conn, request, compiled, catalog, snapshot_id, budget):
                nonlocal committed
                facts = execute_scope(conn, request, compiled, catalog, snapshot_id, budget)
                observed.append(facts[0])
                if len(observed) == 1:
                    self.assertEqual(facts[0].value, 158000)
                    with writer:
                        writer.execute(
                            "UPDATE booking_items SET unit_price_minor=unit_price_minor+1000 "
                            "WHERE item_id='I01'"
                        )
                        writer.execute(
                            "UPDATE booking_items SET unit_price_minor=unit_price_minor+7000 "
                            "WHERE item_id='I11'"
                        )
                    committed = not writer.in_transaction
                    self.assertEqual(writer.total_changes, 2)
                    with closing(sqlite3.connect(self.db, timeout=0)) as observer:
                        for scope in (self.request.current, self.request.baseline):
                            outside_values.append(observer.execute(
                                "SELECT SUM(i.seats*i.unit_price_minor-i.discount_minor) "
                                "FROM booking_items i JOIN bookings b "
                                "ON b.booking_id=i.booking_id AND b.center_id=i.center_id "
                                "WHERE b.status='confirmed' AND b.created_at_utc>=? AND b.created_at_utc<?",
                                (utc_text(scope.start), utc_text(scope.end)),
                            ).fetchone()[0])
                    self.assertEqual(outside_values, [160000, 57000])
                return facts

            with (
                patch.object(kernel, "_execute_scope", side_effect=race) as scopes,
                patch.object(kernel, "execute_facts", side_effect=AssertionError("No separate P1 batches")),
                patch.object(grepbit, "execute_facts", side_effect=AssertionError("No exported P1 batches")),
            ):
                pack = self.execute()
            self.assertTrue(committed)
            self.assertEqual(scopes.call_count, 2)
            self.assertEqual(tuple(f.value for f in observed), (158000, 50000))
            self.assert_values(pack, 158000, 50000, 108000, Fraction(54, 25))
            self.assertEqual({fact.snapshot_id for fact in (*pack.facts, *pack.derived_facts)},
                             {pack.snapshot["id"]})
        for scope, expected in ((self.request.current, 160000), (self.request.baseline, 57000)):
            standalone = execute_facts(self.db, scope)
            self.assertEqual(standalone.facts[0].value, expected)
            self.assertNotEqual(standalone.snapshot["id"], pack.snapshot["id"])
        self.assert_writer_available()

    def test_source_row_budget_exact_boundary_is_counted_once_not_per_scope(self):
        with closing(sqlite3.connect(self.db)) as conn:
            rows = sum(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                       for table in ("centers", "bookings", "booking_items"))
        self.assertEqual(rows, 31)
        with patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as validation:
            pack = self.execute(limits=ExecutionLimits(max_source_rows=rows))
        validation.assert_called_once()
        self.assertEqual(pack.execution["source_rows_validated"], rows)
        self.assertEqual(pack.execution["max_source_rows"], rows)
        self.assert_values(pack, 158000, 50000, 108000, Fraction(54, 25))
        error = self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(max_source_rows=rows - 1))
        self.assertIn("row budget", str(error))

    def test_low_vm_budget_fails_explicitly_and_closes_connection(self):
        error = self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(max_vm_steps=100))
        self.assertIn("VM step budget", str(error))

    def test_low_row_budget_fails_explicitly_and_closes_connection(self):
        error = self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(max_source_rows=1))
        self.assertIn("row budget", str(error))

    def test_low_time_budget_fails_without_real_time_sleep(self):
        with patch.object(kernel.time, "monotonic", side_effect=[100.0, 101.0]):
            error = self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(timeout_seconds=0.5))
        self.assertIn("deadline", str(error))

    def test_timeout_deadline_is_not_restarted_for_second_scope(self):
        clock = [100.0]
        execute_scope = kernel._execute_scope
        observations = []
        completed = []

        def tick_between_scopes(conn, request, compiled, catalog, snapshot_id, budget):
            observations.append(budget)
            if len(observations) == 2:
                clock[0] = 101.25
            facts = execute_scope(conn, request, compiled, catalog, snapshot_id, budget)
            completed.extend(facts)
            clock[0] = 100.75
            return facts

        with (
            patch.object(kernel.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(kernel, "_execute_scope", side_effect=tick_between_scopes),
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            error = self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(timeout_seconds=1.0))
        self.assertEqual(tuple(f.value for f in completed), (158000,))
        self.assertEqual(len(observations), 2)
        self.assertIs(observations[0], observations[1])
        self.assertEqual(observations[1].started, 100.0)
        self.assertIn("deadline", str(error))
        difference.assert_not_called()

    def test_second_query_real_progress_callback_consumes_remaining_shared_vm_budget(self):
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.executemany(
                    "INSERT INTO booking_items VALUES (?, 'B10', 'S06', 'CA', 1, 1, 0)",
                    [(f"I_VM_{index}",) for index in range(64)],
                )
        execute_scope, progress = kernel._execute_scope, kernel._Budget.progress
        phase = [0]
        callbacks, completed, budgets = [], [], []

        def tracked_progress(budget):
            before = budget.callbacks
            result = progress(budget)
            callbacks.append((phase[0], before, budget.callbacks, result))
            return result

        def nearly_exhausted(conn, request, compiled, catalog, snapshot_id, budget):
            phase[0] += 1
            budgets.append(budget)
            facts = execute_scope(conn, request, compiled, catalog, snapshot_id, budget)
            completed.extend(facts)
            if phase[0] == 1:
                # Leave one real SQLite callback; do not replace callbacks or loosen limits.
                budget.callbacks = budget.limits.max_vm_steps // 100 - 1
            return facts

        with (
            patch.object(kernel._Budget, "progress", new=tracked_progress),
            patch.object(kernel, "_execute_scope", side_effect=nearly_exhausted),
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            error = self.assert_failure_closed("budget_exceeded")
        self.assertEqual(tuple(fact.value for fact in completed), (158000,))
        self.assertEqual(len(budgets), 2)
        self.assertIs(budgets[0], budgets[1])
        self.assertEqual(budgets[1].limits, ExecutionLimits())
        final = callbacks[-1]
        self.assertEqual(final, (2, 9999, 10000, 1))
        self.assertIn("VM step budget", str(error))
        difference.assert_not_called()

    def test_timeout_after_both_reads_still_returns_no_partial_pack(self):
        clock = [100.0]
        execute_scope = kernel._execute_scope
        completed = []

        def late_deadline(*args):
            facts = execute_scope(*args)
            completed.extend(facts)
            if len(completed) == 2:
                clock[0] = 102.0
            return facts

        with (
            patch.object(kernel.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(kernel, "_execute_scope", side_effect=late_deadline),
        ):
            self.assert_failure_closed("budget_exceeded", limits=ExecutionLimits(timeout_seconds=1.0))
        self.assertEqual(tuple(fact.value for fact in completed), (158000, 50000))

    def test_missing_database_is_not_created(self):
        self.assert_failure_closed("execution_failure", database=self.root / "missing.sqlite")

    def test_invalid_source_fails_before_scalar_reads_and_releases_lock(self):
        self.mutate((
            "UPDATE bookings SET created_at_utc='2026-03-01 00:00:00' WHERE booking_id='B01'", (),
        ))
        with patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as scopes:
            self.assert_failure_closed("unsupported_source")
        scopes.assert_not_called()

    def test_late_baseline_sum_overflow_fails_without_deriving_or_returning_a_pack(self):
        self.mutate((
            "UPDATE booking_items SET seats=1, unit_price_minor=?, discount_minor=0 "
            "WHERE item_id IN ('I10','I11')", (2**62,),
        ))
        execute_scope = kernel._execute_scope
        completed = []

        def observed_scope(*args):
            facts = execute_scope(*args)
            completed.extend(facts)
            return facts

        with (
            patch.object(kernel, "_execute_scope", side_effect=observed_scope) as scopes,
            patch.object(compare, "_difference", wraps=compare._difference) as difference,
        ):
            error = self.assert_failure_closed("execution_failure")
        self.assertEqual(scopes.call_count, 2)
        self.assertEqual(tuple(fact.value for fact in completed), (158000,))
        self.assertIsInstance(error.__cause__, sqlite3.OperationalError)
        self.assertIn("integer overflow", str(error.__cause__).lower())
        difference.assert_not_called()

    def test_valid_maximum_int64_source_amount_is_not_treated_as_overflow(self):
        self.zero_scope(self.request.current)
        self.mutate((
            "UPDATE booking_items SET seats=1, unit_price_minor=? WHERE item_id='I01'", (INT64_MAX,),
        ))
        self.assert_values(
            self.execute(), INT64_MAX, 50000, INT64_MAX - 50000, Fraction(INT64_MAX - 50000, 50000),
        )

    def test_connection_is_read_only_before_validation_and_closed_after_success(self):
        validate_source = kernel._validate_source
        before = self.db.read_bytes()

        def readonly_probe(conn, budget):
            self.assertTrue(conn.in_transaction)
            self.assertEqual(conn.execute("PRAGMA query_only").fetchone(), (1,))
            with self.assertRaises(sqlite3.OperationalError) as raised:
                conn.execute("UPDATE centers SET name='untrusted' WHERE center_id='CA'")
            self.assertEqual(raised.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
            return validate_source(conn, budget)

        with (
            self.capture_connections() as (connections, _),
            patch.object(kernel, "_validate_source", side_effect=readonly_probe) as validation,
        ):
            self.assert_values(self.execute(), 158000, 50000, 108000, Fraction(54, 25))
        validation.assert_called_once()
        self.assertEqual(len(connections), 1)
        self.assert_closed(connections)
        self.assertEqual(self.db.read_bytes(), before)
        self.assert_writer_available()

    def test_compare_execution_makes_no_network_calls(self):
        forbidden = AssertionError("Network forbidden in offline Compare")
        with (
            patch.object(socket.socket, "connect", side_effect=forbidden),
            patch.object(socket.socket, "connect_ex", side_effect=forbidden),
            patch.object(socket.socket, "sendto", side_effect=forbidden),
            patch.object(socket, "create_connection", side_effect=forbidden),
            patch.object(socket, "getaddrinfo", side_effect=forbidden),
        ):
            self.assert_values(self.execute(), 158000, 50000, 108000, Fraction(54, 25))

    def test_fresh_import_and_execution_are_separate_from_evaluators_and_model_transport(self):
        script = textwrap.dedent("""
            import json
            import os
            from pathlib import Path
            import socket
            import sys

            evaluator_root = Path(sys.argv[1]).resolve() / "evals"
            forbidden = {"tools", "tests", "evals", "grepbit.model", "grepbit.gateway"}
            violations = []

            class IsolationViolation(RuntimeError):
                pass

            def forbidden_module(name):
                return any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)

            class ImportGuard:
                def find_spec(self, fullname, path=None, target=None):
                    if forbidden_module(fullname):
                        violations.append("import:" + fullname)
                        raise IsolationViolation("Evaluator/model import forbidden")
                    return None

            def audit(event, arguments):
                if event.startswith("socket."):
                    violations.append("network:" + event)
                    raise IsolationViolation("Network forbidden")
                if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(arguments[0])).resolve()
                    if path.is_relative_to(evaluator_root):
                        violations.append("open:" + str(path))
                        raise IsolationViolation("Evaluator read forbidden")

            sys.meta_path.insert(0, ImportGuard())
            sys.addaudithook(audit)
            assert not any(forbidden_module(name) for name in sys.modules)
            for module in ("tools", "tests", "evals"):
                try:
                    __import__(module)
                except IsolationViolation:
                    pass
                else:
                    raise AssertionError("Import negative control was not blocked")
            try:
                (evaluator_root / "oracles" / "learningops.json").read_bytes()
            except IsolationViolation:
                pass
            else:
                raise AssertionError("File negative control was not blocked")
            try:
                socket.socket()
            except IsolationViolation:
                pass
            else:
                raise AssertionError("Network negative control was not blocked")
            violations.clear()

            from grepbit import CompareRequest, execute_compare

            pack = execute_compare(Path(sys.argv[2]), CompareRequest.from_mapping(json.loads(sys.argv[3])))
            assert not violations, violations
            assert not any(forbidden_module(name) for name in sys.modules)
            print(json.dumps({
                "status": pack.status,
                "values": [fact.value for fact in pack.facts],
                "growth": pack.to_dict()["derived_facts"][1]["value"],
                "violations": violations,
            }))
        """)
        before = self.db.read_bytes()
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(fixture.ROOT), str(self.db),
             json.dumps(compare_mapping())],
            cwd=fixture.ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {
            "status": "complete", "values": [158000, 50000],
            "growth": {"numerator": 54, "denominator": 25}, "violations": [],
        })
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
