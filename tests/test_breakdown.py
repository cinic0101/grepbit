"""Bounded offline Breakdown controls, not model or backend-parity acceptance."""
from contextlib import closing, contextmanager, ExitStack
from dataclasses import asdict, replace
from fractions import Fraction
import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

import grepbit
from grepbit import (
    BreakdownAnalysisPack, BreakdownDerivedFact, BreakdownRequest, BreakdownSlotResult,
    ExecutionLimits, GroupedAmountRow, KernelError, execute_breakdown,
)
from grepbit import breakdown, composition, grouped, kernel
from grepbit.catalog import LEARNINGOPS

from tools import fixture


TOP = (("K1", 68000), ("K3", 60000), ("K2", 30000))


def request(**changes):
    data = dict(start="2026-03-01T00:00:00+08:00", end="2026-04-01T00:00:00+08:00",
                timezone="Asia/Taipei", top_k=2)
    data.update(changes)
    return BreakdownRequest.from_mapping(data)


class BreakdownTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "breakdown.sqlite"
        fixture.build(self.db)

    def mutate(self, sql, parameters=()):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(sql, parameters)

    def execute(self, req=None, **kwargs):
        return execute_breakdown(self.db, request() if req is None else req, **kwargs)

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(KernelError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    @contextmanager
    def readers(self):
        connect, connections, traces = sqlite3.connect, [], []

        def capture(*args, **kwargs):
            self.assertIn("?mode=ro", args[0])
            conn = connect(*args, **kwargs)
            connections.append(conn)
            conn.set_trace_callback(lambda sql: traces.append((sql, conn.in_transaction)))
            return conn

        with patch.object(sqlite3, "connect", side_effect=capture):
            yield connections, traces
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
        self.assertLessEqual(len(connections), 1)
        self.assertLessEqual(sum(sql == "BEGIN" for sql, _ in traces), 1)
        with closing(connect(self.db, timeout=0)) as writer:
            writer.execute("BEGIN EXCLUSIVE")
            writer.execute("UPDATE centers SET name=name")
            writer.rollback()

    def failure(self, code, *, exception=KernelError, **kwargs):
        before = self.db.read_bytes()
        with (self.readers(), patch.object(breakdown, "BreakdownAnalysisPack") as pack,
              self.assertRaises(exception) as raised):
            self.execute(**kwargs)
        pack.assert_not_called()
        self.assertEqual(self.db.read_bytes(), before)
        if code is not None:
            self.assertEqual(raised.exception.code, code)
        return raised.exception

    def assert_pack(self, pack, total=158000, rows=TOP[:2], subtotal=128000, share=Fraction(64, 79)):
        self.assertIs(type(pack), BreakdownAnalysisPack)
        whole, = pack.facts
        top, = pack.grouped_facts
        sub, ratio = pack.derived_facts
        self.assertTrue(all(type(f) is BreakdownDerivedFact for f in (sub, ratio)))
        self.assertEqual((whole.value, sub.value, ratio.value), (total, subtotal, share))
        self.assertEqual(tuple((r.key, r.value) for r in top.rows), rows)
        self.assertEqual((top.dimension, top.coverage, top.top_k), ("course", "top_k", pack.request.top_k))
        self.assertEqual((pack.scope.center_id, whole.filters, top.filters), (None, {}, {}))
        self.assertEqual((sub.derivation, sub.input_fact_ids), ("selected_subtotal", (top.fact_id,)))
        self.assertEqual((ratio.derivation, ratio.input_fact_ids), ("share_of_scope", (sub.fact_id, whole.fact_id)))
        self.assertEqual((sub.unit, ratio.unit), ("TWD_minor", "dimensionless"))
        self.assertEqual(tuple(s.slot_id for s in pack.slots), ("top_courses", "all_amount", "top_subtotal", "share"))
        self.assertEqual(tuple(s.fact_id for s in pack.slots), (top.fact_id, whole.fact_id, sub.fact_id, ratio.fact_id))
        self.assertTrue(all(type(s) is BreakdownSlotResult and s.role == "required" for s in pack.slots))
        self.assertEqual(len({f.fact_id for f in (whole, top, sub, ratio)}), 4)
        self.assertEqual({f.snapshot_id for f in (whole, top, sub, ratio)}, {pack.snapshot["id"]})
        self.assertEqual(pack.status, "failed" if subtotal is None else "complete")
        expected = (("checked", None), ("checked", None),
                    ("unavailable", "empty_input") if subtotal is None else ("checked", None),
                    ("unavailable", "unavailable_subtotal") if subtotal is None else
                    ("undefined", "zero_total") if total == 0 else ("checked", None))
        self.assertEqual(tuple((s.state, s.reason) for s in pack.slots), expected)
        self.assertEqual(((sub.state, sub.reason), (ratio.state, ratio.reason)), expected[2:])
        if share is not None:
            self.assertIs(type(ratio.value), Fraction)

    def test_e03_original_sources_exact_derivations_provenance_and_json(self):
        scalar, selection, seen = kernel._execute_scope, grouped._execute_grouped, {}

        def capture_scalar(*args):
            facts = scalar(*args)
            seen["total"], seen["total_id"] = facts[0], facts[0].fact_id
            return facts

        def capture_top(*args):
            fact = selection(*args)
            seen["top"], seen["top_id"] = fact, fact.fact_id
            return fact

        with (patch.object(kernel, "_execute_scope", side_effect=capture_scalar),
              patch.object(grouped, "_execute_grouped", side_effect=capture_top)):
            pack = self.execute()
        self.assert_pack(pack)
        self.assertIs(pack.facts[0], seen["total"])
        self.assertIs(pack.grouped_facts[0], seen["top"])
        self.assertEqual((pack.facts[0].fact_id, pack.grouped_facts[0].fact_id),
                         (seen["total_id"], seen["top_id"]))
        for fact in (*pack.facts, *pack.grouped_facts, *pack.derived_facts):
            self.assertEqual(str(UUID(fact.fact_id)), fact.fact_id)
        self.assertEqual((pack.recipe_id, pack.recipe_version), ("breakdown", "0.1"))
        self.assertEqual(pack.scope, pack.request._scope())
        self.assertEqual(pack.scope.metrics, ("confirmed_booked_amount",))
        self.assertEqual(pack.grouped_facts[0].snapshot, pack.snapshot)
        self.assertGreaterEqual(pack.snapshot["completed_at_utc"], pack.snapshot["started_at_utc"])
        for fragment in ("LIMIT", "GROUP BY", "ORDER BY", "COURSE", "RANK"):
            self.assertNotIn(fragment, pack.facts[0].sql.upper())
        self.assertEqual(set(pack.facts[0].parameters), {"status", "start", "end"})
        self.assertIn("independently_executed_whole_scope_denominator", pack.checks)
        self.assertTrue(pack.limitations)
        payload = json.loads(json.dumps(pack.to_dict()))
        self.assertEqual(set(payload), {"request", "scope", "facts", "grouped_facts", "derived_facts", "slots",
                                        "snapshot", "runtime", "execution", "limitations", "checks",
                                        "recipe_id", "recipe_version", "status"})
        self.assertEqual(payload["request"], pack.request.to_dict())
        self.assertEqual(payload["scope"], pack.scope.to_dict())
        self.assertEqual(payload["facts"], json.loads(json.dumps([asdict(seen["total"])])))
        self.assertEqual(payload["grouped_facts"], json.loads(json.dumps([seen["top"].to_dict()])))
        self.assertEqual([f["value"] for f in payload["derived_facts"]],
                         [128000, {"numerator": 64, "denominator": 79}])
        self.assertEqual(payload["status"], "complete")

    def test_one_scalar_first_reader_and_budget_without_public_or_optional_wrappers(self):
        def after_close(*args):
            with self.assertRaises(sqlite3.ProgrammingError):
                connections[0].execute("SELECT 1")
            self.assertIn("completed_at_utc", args[6])
            return BreakdownAnalysisPack(*args)

        with (self.readers() as (connections, traces), ExitStack() as forbidden,
              patch.object(kernel, "_Budget", wraps=kernel._Budget) as budgets,
              patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as base,
              patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as scalar,
              patch.object(grouped, "_execute_grouped", wraps=grouped._execute_grouped) as top,
              patch.object(grouped, "_validate_dimension_source", wraps=grouped._validate_dimension_source) as admission,
              patch.object(breakdown, "BreakdownAnalysisPack", side_effect=after_close)):
            for module, name in ((kernel, "execute_facts"), (grouped, "execute_grouped_amount"),
                                 (grepbit, "execute_facts"), (grepbit, "execute_grouped_amount"),
                                 (composition, "_execute_in_transaction"), (composition, "_execute_optional")):
                forbidden.enter_context(patch.object(module, name, side_effect=AssertionError(name)))
            pack = self.execute()
        self.assertEqual((len(connections), sum(sql == "BEGIN" for sql, _ in traces)), (1, 1))
        self.assertTrue(all(active for sql, active in traces if sql.startswith("SELECT")))
        self.assertEqual(["GROUP BY" in sql for sql, _ in traces if "SUM(" in sql], [False, True])
        budgets.assert_called_once_with(ExecutionLimits())
        for spy in (base, scalar, top, admission):
            spy.assert_called_once()
        budget = base.call_args.args[1]
        for call, position in ((scalar.call_args, 5), (top.call_args, 4), (admission.call_args, 2)):
            self.assertIs(call.args[0], connections[0])
            self.assertIs(call.args[position], budget)
        self.assertEqual(admission.call_args.args[1], "course")
        self.assertEqual(top.call_args.args[1].scope, scalar.call_args.args[1])
        self.assertEqual((budget.rows, pack.execution["source_rows_validated"],
                          pack.grouped_facts[0].execution["source_rows_validated"]), (48, 48, 48))
        self.assertEqual(pack.execution["progress_callbacks"], budget.callbacks)
        self.assertEqual(pack.runtime, kernel._runtime_evidence())

    def test_each_k_keeps_independent_whole_and_fewer_observed_courses_are_valid(self):
        for k, subtotal, share in ((1, 68000, Fraction(34, 79)), (2, 128000, Fraction(64, 79)),
                                   (3, 158000, Fraction(1))):
            with self.subTest(k=k):
                self.assert_pack(self.execute(request(top_k=k)), rows=TOP[:k], subtotal=subtotal, share=share)
        february = request(start="2026-02-01T00:00:00+08:00", end="2026-03-01T00:00:00+08:00", top_k=3)
        self.assert_pack(self.execute(february), total=50000, rows=(("K2", 30000), ("K1", 20000)),
                         subtotal=50000, share=Fraction(1))

    def test_unselected_course_changes_only_denominator_and_share(self):
        with closing(sqlite3.connect(self.db)) as conn:
            actual = conn.execute(
                "SELECT i.item_id,s.course_id,i.seats,i.unit_price_minor FROM booking_items i "
                "JOIN sessions s ON i.session_id=s.session_id WHERE i.item_id IN ('I02','I05') ORDER BY i.item_id"
            ).fetchall()
        self.assertEqual(actual, [("I02", "K2", 1, 15000), ("I05", "K1", 3, 10000)])
        self.mutate("UPDATE booking_items SET unit_price_minor=unit_price_minor+3000 WHERE item_id='I02'")
        self.assert_pack(self.execute(), total=161000, share=Fraction(128, 161))

    def test_cutoff_ties_and_late_multirow_course_use_full_population_before_limit(self):
        self.mutate("UPDATE booking_items SET seats=1,unit_price_minor=0,discount_minor=0")
        self.mutate("UPDATE booking_items SET unit_price_minor=30000 WHERE item_id IN ('I01','I02','I06')")
        self.assert_pack(self.execute(), total=90000, rows=(("K1", 30000), ("K2", 30000)),
                         subtotal=60000, share=Fraction(2, 3))
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO courses VALUES ('KZ','LATE','Late','late')")
            conn.execute("INSERT INTO sessions VALUES ('SZ','KZ','CA','2026-03-01T00:00:00Z',60,10)")
            conn.execute("INSERT INTO bookings VALUES ('BZ','CA',NULL,'2026-03-25T00:00:00Z','confirmed','TWD')")
            conn.executemany("INSERT INTO booking_items VALUES (?,'BZ','SZ','CA',1,25000,0)",
                             [(f"IZ{i}",) for i in range(3)])
        self.assert_pack(self.execute(), total=165000, rows=(("KZ", 75000), ("K1", 30000)),
                         subtotal=105000, share=Fraction(7, 11))

    def test_strict_mapping_has_no_inferred_k_scope_or_plan_fields(self):
        valid = request().to_dict()
        invalid = [None, [], "", {}, *({k: v for k, v in valid.items() if k != missing} for missing in valid)]
        invalid += [dict(valid, top_k=k) for k in (True, False, 1.0, "2", 0, 4, None)]
        invalid += [dict(valid, **{key: value}) for key, value in (
            ("center_id", "CA"), ("center_code", "CTR-A01"), ("metrics", []), ("dimension", "category"),
            ("filter", {}), ("order", "value"), ("formula", "1+1"), ("sql", "SELECT 1"),
            ("callback", None), ("roles", {}), ("version", "0.1"), ("year", 2026), ("month", 3),
        )]
        for index, data in enumerate(invalid):
            with self.subTest(case=index):
                self.error("invalid_request", BreakdownRequest.from_mapping, data)
        with self.assertRaises(TypeError):
            BreakdownRequest()

    def test_typed_public_contract_explicit_month_and_equivalent_offsets(self):
        names = {"BreakdownRequest", "BreakdownDerivedFact", "BreakdownSlotResult",
                 "BreakdownAnalysisPack", "execute_breakdown"}
        self.assertTrue(names <= set(grepbit.__all__))
        signature = inspect.signature(execute_breakdown)
        self.assertEqual(tuple(signature.parameters), ("database", "request", "limits"))
        self.assertEqual(signature.parameters["limits"].kind, inspect.Parameter.KEYWORD_ONLY)
        for dto, fields in ((BreakdownDerivedFact, ("fact_id",)), (BreakdownSlotResult, ("role",)),
                            (BreakdownAnalysisPack, ("recipe_id", "recipe_version"))):
            self.assertTrue(set(fields).isdisjoint(inspect.signature(dto).parameters))
        req = request()
        equivalent = request(start="2026-02-28T16:00:00Z", end="2026-03-31T16:00:00Z")
        self.assertEqual(equivalent, req)
        self.assertEqual(BreakdownRequest.from_mapping(equivalent.to_dict()), equivalent)
        self.assert_pack(self.execute(equivalent))
        for change in ([{"start": value} for value in ("03-01", "2026-03", "2026-03-01T00:00:00",
                        "2026-02-30T00:00:00+08:00", "2026-03-02T00:00:00+08:00",
                        "2026-04-02T00:00:00+08:00", req.start)] +
                       [{"end": value} for value in ("2026-03-31T00:00:00+08:00", "2026-05-01T00:00:00+08:00")] +
                       [{"timezone": zone} for zone in ("UTC", "Asia/Shanghai")]):
            with self.subTest(mapping=change):
                self.error("invalid_request", request, **change)
        for change in ([{"top_k": k} for k in (True, 1.0, "2", 0, 4, None)] +
                       [{"start": req.start.replace(tzinfo=None)}, {"start": req.start.isoformat()}, {"end": req.start}]):
            with self.subTest(typed=change):
                self.error("invalid_request", replace, req, **change)
        output = self.execute()
        with patch.object(sqlite3, "connect") as connect:
            for value in (None, req.to_dict(), output, output.derived_facts[0], output.slots[0]):
                self.error("invalid_request", execute_breakdown, self.db, value)
            self.error("invalid_request", execute_breakdown, self.db, req, limits={})
            connect.assert_not_called()

    def test_common_wrong_axes_are_rejected_against_request_not_just_each_other(self):
        pack = self.execute()
        total, top = pack.facts[0], pack.grouped_facts[0]
        changes = ({"unit": "wrong"}, {"catalog_id": "wrong"}, {"catalog_sha256": "0" * 64},
                   {"metric_id": "booked_seats"}, {"grain": "booking"}, {"population": "wrong"},
                   {"time_basis": "sessions.starts_at_utc"}, {"start_utc": "2026-02-01T00:00:00Z"},
                   {"end_utc": "2026-05-01T00:00:00Z"}, {"business_timezone": "UTC"},
                   {"snapshot_id": "other"}, {"filters": {"center_id": "CA"}}, {"checks": ()})
        for change in changes:
            for role in (("total", "top", "both") if "unit" in change else ("both",)):
                with self.subTest(change=change, role=role):
                    self.error("incompatible_facts", breakdown._check_inputs, pack.request,
                               replace(total, **change) if role != "top" else total,
                               replace(top, **change) if role != "total" else top,
                               pack.snapshot, pack.snapshot["id"])
        self.error("incompatible_facts", breakdown._check_inputs, replace(pack.request, top_k=1),
                   total, top, pack.snapshot, pack.snapshot["id"])

    def test_scalar_checked_shape_identity_and_disclosures_are_required(self):
        pack = self.execute()
        for change in ({"value": True}, {"value": None}, {"value": -1}, {"value": 2**63},
                       {"population_rows": True}, {"population_rows": 1}, {"empty_population": True},
                       {"completeness": "partial"}, {"disclosures": ()}, {"excluded_anonymous_rows": 0},
                       {"fact_id": pack.grouped_facts[0].fact_id}):
            with self.subTest(change=change):
                self.error("incompatible_facts", breakdown._check_inputs, pack.request,
                           replace(pack.facts[0], **change), pack.grouped_facts[0], pack.snapshot, pack.snapshot["id"])

    def test_course_coverage_keys_order_and_empty_evidence_are_checked(self):
        pack = self.execute()
        top = pack.grouped_facts[0]
        changes = [{"coverage": "all_observed_groups"}, {"dimension": "category"}, {"top_k": True},
                   {"top_k": 3}, {"ordering": ("key_asc",)}, {"snapshot": {}}, {"checks": ()}]
        changes += [{"dimension_source_sha256": value} for value in (None, "0" * 63, "g" * 64)]
        changes += [{"rows": rows} for rows in (
            list(top.rows), top.rows + (GroupedAmountRow("K2", 30000),), tuple(reversed(top.rows)),
            (GroupedAmountRow("K3", 60000), GroupedAmountRow("K1", 60000)),
            (top.rows[0], top.rows[0]),
            *((GroupedAmountRow(key, 1),) for key in (None, "", "\ud800", "\u00e9" * 33)),
            *((GroupedAmountRow("K1", value),) for value in (True, 1.0, -1, 2**63)),
        )]
        changes += [{"empty_population": True}, {"rows": (), "empty_population": True}]
        for change in changes:
            with self.subTest(change=repr(change)):
                self.error("incompatible_facts", breakdown._check_inputs, pack.request, pack.facts[0],
                           replace(top, **change), pack.snapshot, pack.snapshot["id"])

    def test_public_fact_corruption_and_shared_sql_parameter_aliases_return_no_pack(self):
        for stage in ("scalar", "group"):
            for fault in ("unit", "sql", "parameters"):
                with self.subTest(stage=stage, fault=fault):
                    module, name = (kernel, "_execute_scope") if stage == "scalar" else (grouped, "_execute_grouped")
                    execute = getattr(module, name)

                    def corrupt(*args):
                        result = execute(*args)
                        fact = result[0] if stage == "scalar" else result
                        if fault == "parameters":
                            expected = args[2][0][3] if stage == "scalar" else args[2][1]
                            self.assertIs(fact.parameters, expected)
                            fact.parameters["start"] = "2026-02-01T00:00:00Z"
                        else:
                            fact = replace(fact, **({"unit": "wrong"} if fault == "unit" else
                                                    {"sql": fact.sql + " LIMIT 1"}))
                        return (fact,) if stage == "scalar" else fact

                    with patch.object(module, name, side_effect=corrupt):
                        self.failure("incompatible_facts")

    def test_subtotal_provenance_operation_state_and_role_identity_are_not_substitutable(self):
        pack = self.execute()
        total, top, subtotal = pack.facts[0], pack.grouped_facts[0], pack.derived_facts[0]
        changes = ({"input_fact_ids": ("stale",)}, {"input_fact_ids": (total.fact_id,)},
                   {"input_fact_ids": (top.fact_id, total.fact_id)}, {"derivation": "share_of_scope"},
                   {"value": True}, {"value": 0}, {"state": "undefined"}, {"reason": "empty_input"},
                   {"unit": "dimensionless"}, {"snapshot_id": "other"})
        for change in changes:
            with self.subTest(change=change):
                self.error("incompatible_facts", breakdown._share_of_scope, replace(subtotal, **change),
                           top, total, all_amount_id=total.fact_id)
        collision = replace(subtotal)
        object.__setattr__(collision, "fact_id", top.fact_id)
        self.error("incompatible_facts", breakdown._share_of_scope, collision, top, total, all_amount_id=total.fact_id)

    def test_denominator_role_substitution_and_impossible_shares_are_errors_not_clamps(self):
        pack = self.execute()
        total, top, subtotal = pack.facts[0], pack.grouped_facts[0], pack.derived_facts[0]
        for candidate in (replace(total, fact_id="different-whole-same-value"), top, subtotal):
            with self.subTest(denominator=type(candidate).__name__):
                self.error("incompatible_facts", breakdown._share_of_scope, subtotal, top, candidate,
                           all_amount_id=total.fact_id)
        for value in (0, subtotal.value - 1):
            with self.subTest(whole=value):
                smaller = replace(total, value=value)
                breakdown._check_inputs(pack.request, smaller, top, pack.snapshot, pack.snapshot["id"])
                self.error("incompatible_facts", breakdown._share_of_scope, subtotal, top, smaller,
                           all_amount_id=total.fact_id)
        empty = replace(total, value=None, population_rows=0, empty_population=True)
        self.error("incompatible_facts", breakdown._check_inputs, pack.request, empty, top, pack.snapshot, pack.snapshot["id"])
        self.error("incompatible_facts", breakdown._share_of_scope, subtotal, top, empty, all_amount_id=total.fact_id)

    def test_pure_subtotal_exact_int64_boundary_and_overflow(self):
        self.assertIsNone(breakdown._subtotal_value(()))
        self.assertEqual(breakdown._subtotal_value((GroupedAmountRow("K1", 2**63 - 1),)), 2**63 - 1)
        self.error("arithmetic_overflow", breakdown._subtotal_value,
                   (GroupedAmountRow("K1", 2**63 - 1), GroupedAmountRow("K2", 1)))
        for value in (True, 1.0, -1, 2**63):
            with self.subTest(value=value):
                self.error("incompatible_facts", breakdown._subtotal_value, (GroupedAmountRow("K1", value),))

    def test_nonempty_zero_is_undefined_complete_but_empty_is_failed_data_coverage(self):
        empty_request = request(start="2026-01-01T00:00:00+08:00", end="2026-02-01T00:00:00+08:00")
        with patch.object(breakdown, "_check_inputs", wraps=breakdown._check_inputs) as inputs:
            empty = self.execute(empty_request)
        self.assert_pack(empty, total=None, rows=(), subtotal=None, share=None)
        self.assertIs(empty.facts[0], inputs.call_args.args[1])
        self.assertIs(empty.grouped_facts[0], inputs.call_args.args[2])
        self.assertTrue(empty.facts[0].empty_population and empty.grouped_facts[0].empty_population)
        self.assertEqual(empty.to_dict()["status"], "failed")
        self.mutate("UPDATE booking_items SET unit_price_minor=0,discount_minor=0")
        zero = self.execute()
        self.assert_pack(zero, total=0, rows=(("K1", 0), ("K2", 0)), subtotal=0, share=None)
        self.assertFalse(zero.facts[0].empty_population or zero.grouped_facts[0].empty_population)
        self.assertEqual(zero.derived_facts[1].to_dict()["value"], None)

    def test_genuine_scalar_sum_overflow_precedes_grouping_and_derivation(self):
        self.mutate("UPDATE booking_items SET seats=1,unit_price_minor=?,discount_minor=0 "
                    "WHERE item_id IN ('I01','I02')", (2**62,))
        with (patch.object(grouped, "_execute_grouped") as top,
              patch.object(breakdown, "_selected_subtotal") as subtotal):
            error = self.failure("execution_failure")
        top.assert_not_called()
        subtotal.assert_not_called()
        self.assertIn("integer overflow", str(error.__cause__))

    def test_category_is_not_consumed_but_courses_and_inherited_sessions_are_required(self):
        self.mutate("ALTER TABLE courses DROP COLUMN category")
        self.assert_pack(self.execute())
        for table in ("courses", "sessions"):
            with self.subTest(missing=table):
                broken = self.db.with_name(f"missing-{table}.sqlite")
                with closing(sqlite3.connect(self.db)) as source, closing(sqlite3.connect(broken)) as target:
                    source.backup(target)
                    target.execute(f"DROP TABLE {table}")
                    target.commit()
                with patch.object(self, "db", broken):
                    self.failure("unsupported_source")

    def test_group_query_errors_including_private_timeout_are_never_partial(self):
        for error in (KernelError("unsupported_source", "trusted query fault"),
                      KernelError("output_limit_exceeded", "trusted query fault"),
                      composition._ComponentTimeout(), sqlite3.OperationalError("trusted query fault")):
            with self.subTest(error=type(error).__name__, code=getattr(error, "code", None)):
                with patch.object(grouped, "_execute_grouped_query", side_effect=error):
                    self.failure(error.code if isinstance(error, KernelError) else "execution_failure")

    def test_cumulative_source_cap_47_fails_course_admission_and_48_succeeds(self):
        with (patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as scalar,
              patch.object(grouped, "_execute_grouped_query") as query):
            self.failure("budget_exceeded", limits=ExecutionLimits(max_source_rows=47))
        scalar.assert_called_once()
        query.assert_not_called()
        pack = self.execute(limits=ExecutionLimits(max_source_rows=48))
        self.assert_pack(pack)
        self.assertEqual(pack.execution["source_rows_validated"], 48)

    def test_injected_global_deadline_after_grouping_prevents_derivations_and_pack(self):
        execute, clock = grouped._execute_grouped, [100.0]

        def delayed(*args):
            top = execute(*args)
            clock[0] = 103.0
            return top

        with (patch.object(kernel.time, "monotonic", side_effect=lambda: clock[0]),
              patch.object(grouped, "_execute_grouped", side_effect=delayed),
              patch.object(breakdown, "_selected_subtotal") as subtotal):
            error = self.failure("budget_exceeded")
        subtotal.assert_not_called()
        self.assertIn("deadline", str(error))

    def test_real_vm_callback_enforces_injected_near_exhaustion_not_full_workload(self):
        execute, progress = grouped._execute_grouped_query, kernel._Budget.progress
        observed, callbacks = [], []

        def near_limit(conn, req, compiled, snapshot, budget, extension):
            self.assertGreater(budget.callbacks, 0)
            observed.append(budget)
            budget.callbacks = budget.limits.max_vm_steps // 100 - 1
            return execute(conn, req, compiled, snapshot, budget, extension)

        def tracked(budget):
            result = progress(budget)
            callbacks.append((budget, budget.callbacks, result))
            return result

        with (patch.object(grouped, "_execute_grouped_query", side_effect=near_limit),
              patch.object(kernel._Budget, "progress", new=tracked)):
            error = self.failure("budget_exceeded")
        self.assertIn("VM step budget", str(error))
        self.assertEqual(callbacks[-1][1:], (10000, 1))
        self.assertIs(callbacks[-1][0], observed[0])

    def test_required_sql_failure_and_actual_transaction_connection_or_interrupt_loss(self):
        def invalid_sql(conn, *args):
            conn.execute("SELECT * FROM absent_source")

        with (patch.object(kernel, "_execute_scope", side_effect=invalid_sql),
              patch.object(grouped, "_execute_grouped") as top):
            self.failure("execution_failure")
        top.assert_not_called()
        execute = grouped._execute_grouped_query
        for fault, code in (("rollback", "snapshot_lost"), ("close", "execution_failure"),
                            ("sqlite_interrupt", "execution_failure"), ("keyboard", None)):
            with self.subTest(fault=fault):
                def lose(conn, *args):
                    if fault == "keyboard":
                        raise KeyboardInterrupt("trusted interruption")
                    if fault == "close":
                        conn.close()
                    elif fault == "rollback":
                        conn.set_authorizer(None)
                        conn.execute("ROLLBACK")
                    else:
                        conn.set_trace_callback(lambda sql: conn.interrupt() if "GROUP BY" in sql else None)
                    return execute(conn, *args)

                with patch.object(grouped, "_execute_grouped_query", side_effect=lose):
                    self.failure(code, exception=KeyboardInterrupt if fault == "keyboard" else KernelError)

    def test_trusted_snapshot_id_corruption_and_sqlite_exit_failure_never_materialize(self):
        transaction, scalar, selection = kernel._read_transaction, kernel._execute_scope, grouped._execute_grouped
        for stage in ("scalar", "group", "exit", "sqlite_exit"):
            with self.subTest(stage=stage):
                snapshots = []

                @contextmanager
                def lifecycle(*args):
                    with transaction(*args) as opened:
                        snapshots.append(opened[1])
                        yield opened
                    if stage == "sqlite_exit":
                        raise sqlite3.OperationalError("trusted exit fault")
                    if stage == "exit":
                        snapshots[0]["id"] = "trusted-metadata-corruption"

                def core(*args):
                    result = scalar(*args)
                    if stage == "scalar":
                        snapshots[0]["id"] = "trusted-metadata-corruption"
                    return result

                def top(*args):
                    result = selection(*args)
                    if stage == "group":
                        snapshots[0]["id"] = "trusted-metadata-corruption"
                    return result

                with (patch.object(kernel, "_read_transaction", side_effect=lifecycle),
                      patch.object(kernel, "_execute_scope", side_effect=core),
                      patch.object(grouped, "_execute_grouped", side_effect=top)):
                    self.failure("execution_failure" if stage == "sqlite_exit" else "snapshot_lost")

    def test_real_wal_promotion_changes_fresh_selection_and_whole_not_inflight_snapshot(self):
        scalar, connect, writes = kernel._execute_scope, sqlite3.connect, []
        with closing(connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
            self.assertEqual(writer.execute(
                "SELECT s.course_id,i.seats,i.unit_price_minor FROM booking_items i JOIN sessions s "
                "ON i.session_id=s.session_id WHERE i.item_id='I02'").fetchone(), ("K2", 1, 15000))

            def commit_after_scalar(*args):
                facts = scalar(*args)
                self.assertEqual(facts[0].value, 158000)
                self.assertFalse(writes)
                with writer:
                    writer.execute("UPDATE booking_items SET unit_price_minor=55000 WHERE item_id='I02'")
                writes.append(writer.total_changes)
                self.assertFalse(writer.in_transaction)
                # Writer and observer use the saved connection factory, not a second runtime reader.
                with closing(connect(self.db, timeout=0)) as observer:
                    sql, params = kernel._compile(LEARNINGOPS.metrics["confirmed_booked_amount"], request()._scope())
                    self.assertEqual(observer.execute(sql, params).fetchone()[0], 198000)
                    need = grouped.GroupedAmountRequest(request()._scope(), "course", 2)
                    sql, params = grouped._compile_grouped(need)
                    self.assertEqual([row[:2] for row in observer.execute(sql, params)], [("K2", 70000), ("K1", 68000)])
                return facts

            with (self.readers() as (connections, traces),
                  patch.object(kernel, "_execute_scope", side_effect=commit_after_scalar)):
                inflight = self.execute()
        self.assertEqual((writes, len(connections), sum(sql == "BEGIN" for sql, _ in traces)), ([1], 1, 1))
        self.assert_pack(inflight)
        fresh = self.execute()
        self.assert_pack(fresh, total=198000, rows=(("K2", 70000), ("K1", 68000)),
                         subtotal=138000, share=Fraction(23, 33))
        self.assertNotEqual(fresh.snapshot["id"], inflight.snapshot["id"])


if __name__ == "__main__":
    unittest.main()
