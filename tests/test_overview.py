"""Public deterministic Overview regressions on disposable offline fixtures."""
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import grepbit
from grepbit import (
    ExecutionLimits, FactRequest, KernelError, OverviewAnalysisPack, OverviewCenterBinding,
    OverviewRequest, OverviewSlotResult, execute_facts, execute_overview,
)
from grepbit import composition, grouped, kernel, overview
from grepbit.catalog import LEARNINGOPS
from tools import fixture


METRICS = ("confirmed_booked_amount", "confirmed_booking_count", "booked_seats")
SLOTS = (("amount", "required"), ("bookings", "required"), ("seats", "required"),
         ("daily_amount", "optional"), ("category_amounts", "optional"))


def request(**changes):
    data = dict(center_code="CTR-A01", start="2026-03-01T00:00:00+08:00",
                end="2026-04-01T00:00:00+08:00", timezone="Asia/Taipei")
    data.update(changes)
    return OverviewRequest.from_mapping(data)


class OverviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "overview.sqlite"
        fixture.build(self.db)

    def mutate(self, sql, parameters=()):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(sql, parameters)

    def execute(self, req=None, **kwargs):
        return execute_overview(self.db, request() if req is None else req, **kwargs)

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
        with closing(connect(self.db, timeout=0)) as writer:
            writer.execute("BEGIN EXCLUSIVE")
            writer.execute("UPDATE centers SET name=name")
            writer.rollback()

    def failure(self, code, **kwargs):
        before = self.db.read_bytes()
        with self.readers(), patch.object(overview, "OverviewAnalysisPack") as pack:
            error = self.error(code, self.execute, **kwargs)
        pack.assert_not_called()
        self.assertEqual(self.db.read_bytes(), before)
        return error

    def assert_pack(self, pack, core=(68000, 4, 6), gap=None):
        self.assertIsInstance(pack, OverviewAnalysisPack)
        self.assertIsInstance(pack.binding, OverviewCenterBinding)
        self.assertEqual(tuple(f.value for f in pack.facts), core)
        self.assertEqual(tuple(f.metric_id for f in pack.facts), METRICS)
        self.assertEqual(pack.status, "partial" if gap else "complete")
        self.assertEqual(tuple((s.slot_id, s.role) for s in pack.slots), SLOTS)
        for slot in pack.slots:
            self.assertIs(type(slot), OverviewSlotResult)
            unavailable = gap is not None and slot.slot_id == "category_amounts"
            self.assertEqual(slot.state, "unavailable" if unavailable else "checked")
            self.assertEqual(slot.reason, gap if unavailable else None)
            if unavailable:
                self.assertIsNone(slot.fact_id)
        ids = [f.fact_id for f in (*pack.facts, *pack.grouped_facts)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertCountEqual([s.fact_id for s in pack.slots if s.state == "checked"], ids)

    def test_e01_complete_evidence_serialization_and_original_fact_identity(self):
        req, finalized = request(), []
        finalize = composition._finalize_composition

        def capture(*args):
            result = finalize(*args)
            finalized.append(result)
            return result

        with patch.object(composition, "_finalize_composition", side_effect=capture):
            pack = self.execute(req)
        self.assert_pack(pack)
        internal, = finalized
        self.assertIs(pack.request, req)
        self.assertIs(pack.facts, internal.facts)
        self.assertIs(pack.grouped_facts, internal.grouped_facts)
        self.assertEqual(pack.status, internal.status)
        self.assertEqual([asdict(s) for s in pack.slots], [asdict(s) for s in internal.slots])
        self.assertTrue(all(public is not private for public, private in zip(pack.slots, internal.slots)))
        self.assertEqual((pack.recipe_id, pack.recipe_version), ("overview", "0.1"))
        self.assertEqual(pack.scope, FactRequest(METRICS, req.start, req.end, req.timezone, "CA"))
        self.assertEqual(pack.binding, OverviewCenterBinding("CTR-A01", "CA", pack.snapshot["id"]))
        self.assertEqual(pack.binding.method, "exact_unique_code")
        self.assertEqual({f.snapshot_id for f in (*pack.facts, *pack.grouped_facts)}, {pack.snapshot["id"]})
        self.assertGreaterEqual(pack.snapshot["completed_at_utc"], pack.snapshot["started_at_utc"])
        self.assertEqual([(r.key, r.value) for r in pack.grouped_facts[1].rows],
                         [("arts", 30000), ("technology", 38000)])
        self.assertEqual([sum(r.value for r in f.rows) for f in pack.grouped_facts], [68000, 68000])
        self.assertTrue(all(f.coverage == "all_observed_groups" and f.snapshot == pack.snapshot
                            for f in pack.grouped_facts))
        self.assertTrue(set(internal.checks) <= set(pack.checks))
        self.assertIn("exact_unique_center_code_binding", pack.checks)
        self.assertTrue(pack.limitations)
        payload = json.loads(json.dumps(pack.to_dict()))
        self.assertEqual(set(payload), {"request", "binding", "scope", "facts", "grouped_facts", "slots",
                                        "status", "snapshot", "runtime", "execution", "limitations", "checks",
                                        "recipe_id", "recipe_version"})
        self.assertEqual(payload["request"], req.to_dict())
        self.assertEqual(payload["scope"], pack.scope.to_dict())
        self.assertEqual(payload["binding"], asdict(pack.binding))
        self.assertEqual(payload["facts"], json.loads(json.dumps([asdict(f) for f in internal.facts])))
        self.assertEqual(payload["grouped_facts"], json.loads(json.dumps([f.to_dict() for f in internal.grouped_facts])))
        self.assertTrue(all(set(s) == {"slot_id", "role", "state", "fact_id", "reason"} for s in payload["slots"]))

    def test_single_reader_budget_and_binding_visit_finalize_only_after_close(self):
        def after_close(*args):
            with self.assertRaises(sqlite3.ProgrammingError):
                connections[0].execute("SELECT 1")
            self.assertIn("completed_at_utc", args[7])
            return OverviewAnalysisPack(*args)

        with (self.readers() as (connections, traces),
              patch.object(kernel, "_Budget", wraps=kernel._Budget) as budgets,
              patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as base,
              patch.object(overview, "_bind_center_code", wraps=overview._bind_center_code) as binding,
              patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as core,
              patch.object(grouped, "_execute_grouped_query", wraps=grouped._execute_grouped_query) as views,
              patch.object(overview, "OverviewAnalysisPack", side_effect=after_close)):
            pack = self.execute()
        self.assertEqual(len(connections), 1)
        self.assertEqual(sum(sql == "BEGIN" for sql, _ in traces), 1)
        self.assertTrue(all(active for sql, active in traces if sql.startswith("SELECT")))
        budgets.assert_called_once_with(ExecutionLimits())
        base.assert_called_once()
        binding.assert_called_once()
        core.assert_called_once()
        self.assertEqual(core.call_args.args[1].metrics, METRICS)
        self.assertEqual(views.call_count, 2)
        budget = base.call_args.args[1]
        for call, position in [(binding.call_args, 3), (core.call_args, 5),
                               *((call, 4) for call in views.call_args_list)]:
            self.assertIs(call.args[0], connections[0])
            self.assertIs(call.args[position], budget)
        self.assertEqual([f.execution["source_rows_validated"] for f in pack.grouped_facts], [32, 49])
        self.assertEqual((pack.execution["source_rows_validated"], budget.rows), (49, 49))
        self.assertEqual(pack.execution["progress_callbacks"], budget.callbacks)
        self.assertEqual(pack.runtime, kernel._runtime_evidence())

    def test_public_typed_contract_and_equivalent_explicit_offsets(self):
        names = {"OverviewRequest", "OverviewCenterBinding", "OverviewSlotResult",
                 "OverviewAnalysisPack", "execute_overview"}
        self.assertTrue(names <= set(grepbit.__all__))
        self.assertFalse(any(name.startswith("_Composition") for name in grepbit.__all__))
        signature = inspect.signature(execute_overview)
        self.assertEqual(tuple(signature.parameters), ("database", "request", "limits"))
        self.assertEqual(signature.parameters["limits"].kind, inspect.Parameter.KEYWORD_ONLY)
        req = request()
        self.assertEqual(OverviewRequest(req.center_code, req.start, req.end, req.timezone), req)
        equivalent = request(start="2026-02-28T16:00:00Z", end="2026-03-31T16:00:00Z")
        self.assertEqual(equivalent, req)
        self.assertEqual(equivalent.to_dict()["start"], "2026-02-28T16:00:00+00:00")
        self.assertEqual(OverviewRequest.from_mapping(equivalent.to_dict()), equivalent)
        self.assert_pack(self.execute(equivalent))
        with patch.object(sqlite3, "connect") as connect:
            for value in (None, {}, req.to_dict(), "SELECT 1"):
                self.error("invalid_request", execute_overview, self.db, value)
            self.error("invalid_request", execute_overview, self.db, req, limits={})
            connect.assert_not_called()

    def test_mapping_accepts_exact_fields_without_plans_or_defaults(self):
        valid = request().to_dict()
        invalid = [None, [], "", {}, *({k: v for k, v in valid.items() if k != missing} for missing in valid)]
        invalid += [dict(valid, **{key: value}) for key, value in (
            ("metrics", list(METRICS)), ("center_id", "CA"), ("roles", {}), ("optionals", []),
            ("sql", "SELECT 1"), ("formula", "1+1"), ("callback", None), ("version", "0.1"),
            ("year", 2026), ("month", 3), ("component_timeout", 1),
        )]
        for index, data in enumerate(invalid):
            with self.subTest(case=index):
                self.error("invalid_request", OverviewRequest.from_mapping, data)
        with self.assertRaises(TypeError):
            OverviewRequest()

    def test_period_rejects_unbound_partial_and_non_taipei_months(self):
        changes = [{"start": value} for value in (
            "03-01", "2026-03", "2026-03-01T00:00:00", "2026-02-30T00:00:00+08:00",
            "2026-03-02T00:00:00+08:00", "2026-04-02T00:00:00+08:00", request().start,
        )]
        changes += [{"end": value} for value in ("2026-03-31T00:00:00+08:00", "2026-05-01T00:00:00+08:00")]
        changes += [{"timezone": zone} for zone in ("UTC", "Asia/Shanghai", None)]
        for change in changes:
            with self.subTest(change=change):
                self.error("invalid_request", request, **change)
        req = request()
        for change in ({"start": req.start.isoformat()}, {"start": req.start.replace(tzinfo=None)},
                       {"end": req.start}, {"timezone": "UTC"}):
            with self.subTest(typed=change):
                self.error("invalid_request", replace, req, **change)

    def test_code_validation_exact_utf8_boundary_and_no_normalization(self):
        class NoEncoding(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("Oversized character input must be rejected before encoding")

        for code in (None, "", b"CTR-A01", True, [], "\ud800", "x" * 65,
                     "\u00e9" * 32 + "x", NoEncoding("x" * 65)):
            with self.subTest(code=repr(code)):
                self.error("invalid_request", request, center_code=code)
                self.error("invalid_request", replace, request(), center_code=code)
        for code in ("\u00e9" * 32, " custom-code "):
            with self.subTest(exact_code=code):
                self.mutate("UPDATE centers SET code=? WHERE center_id='CA'", (code,))
                pack = self.execute(request(center_code=code))
                self.assert_pack(pack)
                self.assertEqual((pack.request.center_code, pack.binding.center_code), (code, code))
                self.assertEqual(pack.scope.center_id, "CA")

    def test_unknown_name_id_case_and_whitespace_variants_fail_before_facts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            name, = conn.execute("SELECT name FROM centers WHERE center_id='CA'").fetchone()
        for code in ("missing", "CA", name, "ctr-a01", " CTR-A01", "CTR-A01 "):
            with self.subTest(code=code), patch.object(kernel, "_execute_scope") as core:
                self.failure("unknown_entity", req=request(center_code=code))
                core.assert_not_called()

    def test_duplicate_matching_codes_are_ambiguous_not_a_global_scalar_rejection(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            ddl, = conn.execute("SELECT sql FROM sqlite_schema WHERE name='centers'").fetchone()
            changed = ddl.replace("code TEXT NOT NULL UNIQUE", "code TEXT NOT NULL")
            self.assertNotEqual(changed, ddl)
            conn.execute("CREATE TEMP TABLE saved_centers AS SELECT * FROM centers")
            conn.execute("DROP TABLE centers")
            conn.execute(changed)
            conn.execute("INSERT INTO centers SELECT * FROM saved_centers")
            conn.execute("UPDATE centers SET code='CTR-A01' WHERE center_id='CB'")
        req = request()
        scalar = execute_facts(self.db, FactRequest(METRICS, req.start, req.end, req.timezone, "CA"))
        self.assertEqual([f.value for f in scalar.facts], [68000, 4, 6])
        with (patch.object(kernel, "_execute_scope") as core,
              patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as base):
            self.failure("ambiguous_entity")
        core.assert_not_called()
        self.assertEqual(base.call_args.args[1].rows, 33)
        self.mutate("UPDATE centers SET code='other-duplicate' WHERE center_id IN ('CB','CC')")
        self.assert_pack(self.execute())

    def test_sql_looking_codes_are_bound_as_literals(self):
        code = "x' OR 1=1 --"
        self.mutate("UPDATE centers SET code=? WHERE center_id='CA'", (code,))
        pack = self.execute(request(center_code=code))
        self.assert_pack(pack)
        self.assertEqual((pack.binding.center_code, pack.binding.center_id), (code, "CA"))
        with patch.object(kernel, "_execute_scope") as core:
            self.failure("unknown_entity", req=request(center_code="absent' OR 1=1 --"))
            core.assert_not_called()

    def test_real_missing_category_is_a_named_partial_view(self):
        self.mutate("ALTER TABLE courses RENAME COLUMN category TO unavailable_category")
        pack = self.execute()
        self.assert_pack(pack, gap="unsupported_source")
        self.assertEqual([(f.dimension, sum(r.value for r in f.rows)) for f in pack.grouped_facts],
                         [("booking_day", 68000)])

    def test_e10_trusted_category_timeout_keeps_exact_public_partial_slots(self):
        execute = grouped._execute_grouped_query

        def inject(conn, req, *args):
            if req.dimension == "category":
                raise composition._ComponentTimeout()
            return execute(conn, req, *args)

        with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
            pack = self.execute()
        self.assert_pack(pack, gap="component_timeout")
        self.assertEqual([(f.dimension, sum(r.value for r in f.rows)) for f in pack.grouped_facts],
                         [("booking_day", 68000)])

    def test_empty_and_zero_retain_checked_null_versus_measured_zero(self):
        with closing(sqlite3.connect(self.db)) as conn:
            code, = conn.execute("SELECT code FROM centers WHERE center_id='CZ'").fetchone()
        empty = self.execute(request(center_code=code))
        self.assert_pack(empty, core=(None, 0, None))
        self.assertTrue(all(f.empty_population and f.population_rows == 0 for f in empty.facts))
        self.assertTrue(all(f.empty_population and f.rows == () for f in empty.grouped_facts))
        self.mutate("UPDATE booking_items SET unit_price_minor=0,discount_minor=0")
        zero = self.execute()
        self.assert_pack(zero, core=(0, 4, 6))
        self.assertTrue(all(not f.empty_population and f.population_rows > 0 for f in zero.facts))
        self.assertTrue(all(not f.empty_population and f.rows for f in zero.grouped_facts))
        self.assertTrue(all(r.value == 0 for f in zero.grouped_facts for r in f.rows))

    def test_required_overflow_returns_no_public_pack_or_optional_attempt(self):
        self.mutate("UPDATE booking_items SET seats=1,unit_price_minor=?,discount_minor=0 "
                    "WHERE item_id IN ('I01','I02')", (2**62,))
        with patch.object(composition, "_execute_optional") as optional:
            error = self.failure("execution_failure")
        optional.assert_not_called()
        self.assertIn("integer overflow", str(error.__cause__))

    def test_binding_visit_shares_global_source_budget_at_31_48_and_49(self):
        for cap, calls in ((31, []), (48, ["booking_day"]), (49, ["booking_day", "category"])):
            with (self.subTest(cap=cap),
                  patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as core,
                  patch.object(grouped, "_execute_grouped_query", wraps=grouped._execute_grouped_query) as views):
                limits = ExecutionLimits(max_source_rows=cap)
                if cap == 49:
                    pack = self.execute(limits=limits)
                    self.assert_pack(pack)
                    self.assertEqual(pack.execution["source_rows_validated"], 49)
                else:
                    self.failure("budget_exceeded", limits=limits)
                self.assertEqual(core.call_count, 0 if cap == 31 else 1)
                self.assertEqual([call.args[1].dimension for call in views.call_args_list], calls)

    def test_real_wal_mapping_and_amount_commit_does_not_rebind_inflight_reader(self):
        bind, connect, writes = overview._bind_center_code, sqlite3.connect, []
        with closing(connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
            cb = writer.execute(
                "SELECT i.item_id,i.seats,i.unit_price_minor FROM booking_items i JOIN bookings b "
                "ON i.booking_id=b.booking_id WHERE b.center_id='CB' AND b.status='confirmed' "
                "AND b.created_at_utc>=? AND b.created_at_utc<?",
                ("2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z")).fetchall()
            self.assertEqual(cb, [("I05", 3, 10000)])

            def commit_after_binding(*args):
                binding = bind(*args)
                self.assertEqual(binding.center_id, "CA")
                self.assertFalse(writes)
                with writer:
                    writer.execute("UPDATE centers SET code='unused' WHERE center_id='CA'")
                    writer.execute("UPDATE centers SET code='CTR-A01' WHERE center_id='CB'")
                    writer.execute("UPDATE booking_items SET unit_price_minor=unit_price_minor+1000 "
                                   "WHERE item_id IN ('I01',?)", (cb[0][0],))
                writes.append(writer.total_changes)
                self.assertFalse(writer.in_transaction)
                # Saved connect is only for the independent observer, not a runtime replacement.
                with closing(connect(self.db, timeout=0)) as observer:
                    self.assertEqual(observer.execute("SELECT center_id FROM centers WHERE code='CTR-A01'").fetchall(),
                                     [("CB",)])
                    req = request()
                    for center, expected in (("CA", 70000), ("CB", 33000)):
                        scope = FactRequest((METRICS[0],), req.start, req.end, req.timezone, center)
                        sql, parameters = kernel._compile(LEARNINGOPS.metrics[METRICS[0]], scope)
                        self.assertEqual(observer.execute(sql, parameters).fetchone()[0], expected)
                return binding

            with (self.readers() as (connections, traces),
                  patch.object(overview, "_bind_center_code", side_effect=commit_after_binding)):
                inflight = self.execute()
        self.assertEqual((writes, len(connections), sum(sql == "BEGIN" for sql, _ in traces)), ([4], 1, 1))
        self.assert_pack(inflight)
        self.assertEqual((inflight.binding.center_id, inflight.scope.center_id), ("CA", "CA"))
        self.assertEqual([sum(r.value for r in f.rows) for f in inflight.grouped_facts], [68000, 68000])
        self.assertEqual([(r.key, r.value) for r in inflight.grouped_facts[1].rows],
                         [("arts", 30000), ("technology", 38000)])
        self.assertEqual({inflight.binding.snapshot_id, *(f.snapshot_id for f in
                         (*inflight.facts, *inflight.grouped_facts))}, {inflight.snapshot["id"]})
        fresh = self.execute()
        self.assert_pack(fresh, core=(33000, 1, 3))
        self.assertEqual((fresh.binding.center_id, fresh.scope.center_id), ("CB", "CB"))
        self.assertEqual([sum(r.value for r in f.rows) for f in fresh.grouped_facts], [33000, 33000])
        self.assertNotEqual(fresh.snapshot["id"], inflight.snapshot["id"])

    def test_original_snapshot_id_is_captured_before_binding(self):
        bind = overview._bind_center_code

        def corrupt(conn, code, snapshot, *args):
            binding = bind(conn, code, snapshot, *args)
            snapshot["id"] = "trusted-metadata-corruption"
            return binding

        with (patch.object(overview, "_bind_center_code", side_effect=corrupt),
              patch.object(kernel, "_execute_scope") as core):
            self.failure("snapshot_lost")
        core.assert_not_called()

    def test_transaction_exit_sqlite_failure_or_identity_corruption_has_no_public_pack(self):
        transaction = kernel._read_transaction
        for fault, code in (("sqlite", "execution_failure"), ("identity", "snapshot_lost")):
            with self.subTest(fault=fault):
                @contextmanager
                def failed_exit(*args):
                    with transaction(*args) as opened:
                        yield opened
                    if fault == "sqlite":
                        raise sqlite3.OperationalError("trusted exit fault")
                    opened[1]["id"] = "trusted-metadata-corruption"

                with patch.object(kernel, "_read_transaction", side_effect=failed_exit) as wrapped:
                    self.failure(code)
                wrapped.assert_called_once()


if __name__ == "__main__":
    unittest.main()
