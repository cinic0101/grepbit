"""Private P2.3 offline composition regressions, not recipe or model acceptance."""
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import grepbit
from grepbit import ExecutionLimits, FactRequest, GroupedAmountRequest, GroupedAmountRow, KernelError
from grepbit import composition, grouped, kernel
from grepbit.catalog import LEARNINGOPS
from tools import fixture


METRICS = ("confirmed_booked_amount", "confirmed_booking_count", "booked_seats")
SLOTS = (("amount", "required"), ("bookings", "required"), ("seats", "required"),
         ("daily_amount", "optional"), ("category_amounts", "optional"))
DETAIL = "untrusted-component-detail"


def scope(**changes):
    data = dict(metrics=list(METRICS), center_id="CA", timezone="Asia/Taipei",
                start="2026-03-01T00:00:00+08:00", end="2026-04-01T00:00:00+08:00")
    data.update(changes)
    return FactRequest.from_mapping(data)


class CompositionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "composition.sqlite"
        fixture.build(self.db)

    def mutate(self, sql, parameters=()):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(sql, parameters)

    def execute(self, request=None, **kwargs):
        return composition._execute_required_optional(
            self.db, scope() if request is None else request, **kwargs)

    @contextmanager
    def connections(self):
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

    def failure(self, code, *, exception=KernelError, **kwargs):
        before = self.db.read_bytes()
        with (self.connections() as (_, traces),
              patch.object(composition, "_CompositionResult") as result,
              self.assertRaises(exception) as raised):
            self.execute(**kwargs)
        result.assert_not_called()
        self.assertEqual(self.db.read_bytes(), before)
        self.assertLessEqual(sum(sql == "BEGIN" for sql, _ in traces), 1)
        if code is not None:
            self.assertEqual(raised.exception.code, code)
        return raised.exception

    def assert_result(self, result, gaps=None, core=(68000, 4, 6)):
        gaps = gaps or {}
        self.assertEqual(result.status, "partial" if gaps else "complete")
        self.assertEqual(tuple(fact.value for fact in result.facts), core)
        self.assertEqual(tuple(fact.metric_id for fact in result.facts), METRICS)
        self.assertEqual(tuple((slot.slot_id, slot.role) for slot in result.slots), SLOTS)
        identities = [fact.fact_id for fact in (*result.facts, *result.grouped_facts)]
        self.assertEqual(len(identities), len(set(identities)))
        linked = []
        for slot in result.slots:
            self.assertEqual(slot.state, "unavailable" if slot.slot_id in gaps else "checked")
            self.assertEqual(slot.reason, gaps.get(slot.slot_id))
            if slot.slot_id in gaps:
                self.assertIsNone(slot.fact_id)
            else:
                linked.append(slot.fact_id)
        self.assertCountEqual(linked, identities)
        self.assertNotIn(DETAIL, json.dumps(result.to_dict()))

    def test_complete_core_slots_evidence_and_json_shape(self):
        result = self.execute()
        self.assert_result(result)
        self.assertEqual([fact.dimension for fact in result.grouped_facts], ["booking_day", "category"])
        self.assertEqual([sum(row.value for row in fact.rows) for fact in result.grouped_facts], [68000] * 2)
        self.assertEqual(result.snapshot["scope"], "single_read_transaction")
        self.assertGreaterEqual(result.snapshot["completed_at_utc"], result.snapshot["started_at_utc"])
        self.assertEqual(result.runtime, kernel._runtime_evidence())
        self.assertTrue(result.limitations)
        self.assertIn("fixed_required_coverage", result.checks)
        for fact in (*result.facts, *result.grouped_facts):
            self.assertEqual(fact.snapshot_id, result.snapshot["id"])
            self.assertEqual(fact.filters, {"center_id": "CA"})
            self.assertEqual((fact.start_utc, fact.end_utc, fact.business_timezone),
                             ("2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z", "Asia/Taipei"))
            self.assertTrue(fact.sql and fact.checks)
        self.assertTrue(all(fact.completeness == "complete" for fact in result.facts))
        for fact in result.grouped_facts:
            self.assertEqual(fact.snapshot, result.snapshot)
            self.assertEqual(fact.coverage, "all_observed_groups")
            self.assertTrue(set(grouped._GROUP_CHECKS) <= set(fact.checks))
        self.assertEqual(result.execution["source_rows_validated"], 48)
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(set(payload), {"facts", "grouped_facts", "slots", "snapshot", "runtime",
                                        "execution", "limitations", "checks", "status"})
        self.assertEqual(payload["facts"], json.loads(json.dumps([asdict(f) for f in result.facts])))
        self.assertEqual(payload["grouped_facts"],
                         json.loads(json.dumps([f.to_dict() for f in result.grouped_facts])))
        for slot in payload["slots"]:
            self.assertEqual(set(slot), {"slot_id", "role", "state", "fact_id", "reason"})
        self.assertFalse(set(grepbit.__all__) & {
            "composition", "_execute_required_optional", "_CompositionResult", "_CompositionSlot",
            "_ComponentTimeout",
        })

    def test_scope_requires_canonical_center_fixed_metrics_and_full_taipei_month(self):
        with closing(sqlite3.connect(self.db)) as conn:
            code, name = conn.execute("SELECT code,name FROM centers WHERE center_id='CA'").fetchone()
        cases = [({"center_id": None}, "invalid_request")]
        cases += [({"center_id": value}, "unknown_entity") for value in (code, name, "missing")]
        cases += [(change, "invalid_request") for change in (
            {"metrics": list(reversed(METRICS))}, {"metrics": [METRICS[0]]},
            {"timezone": "UTC"}, {"start": "2026-03-02T00:00:00+08:00"},
            {"end": "2026-05-01T00:00:00+08:00"},
        )]
        for change, error in cases:
            with self.subTest(change=change):
                self.failure(error, request=scope(**change))
        for field in ("center_code", "center_name"):
            with self.subTest(field=field), self.assertRaises(KernelError) as raised:
                scope(**{field: code})
            self.assertEqual(raised.exception.code, "invalid_request")

    def test_empty_and_measured_zero_are_checked_not_optional_gaps(self):
        empty = self.execute(scope(center_id="CZ"))
        self.assert_result(empty, core=(None, 0, None))
        self.assertTrue(all(f.empty_population and f.population_rows == 0 for f in empty.facts))
        self.assertTrue(all(f.empty_population and f.rows == () for f in empty.grouped_facts))
        self.mutate("UPDATE booking_items SET unit_price_minor=0,discount_minor=0")
        zero = self.execute()
        self.assert_result(zero, core=(0, 4, 6))
        self.assertTrue(all(not f.empty_population and f.population_rows > 0 for f in zero.facts))
        self.assertTrue(all(not f.empty_population and f.rows for f in zero.grouped_facts))
        self.assertTrue(all(row.value == 0 for f in zero.grouped_facts for row in f.rows))

    def test_missing_category_is_partial_but_inherited_base_admission_is_required(self):
        self.mutate("ALTER TABLE courses RENAME COLUMN category TO unavailable_category")
        result = self.execute()
        self.assert_result(result, {"category_amounts": "unsupported_source"})
        self.assertEqual([f.dimension for f in result.grouped_facts], ["booking_day"])
        self.assertEqual(sum(row.value for row in result.grouped_facts[0].rows), 68000)
        for mutation, code in (("DROP TABLE sessions", "unsupported_source"),
                               ("ALTER TABLE bookings RENAME COLUMN status TO bad_status", "unsupported_source")):
            with self.subTest(mutation=mutation):
                broken = self.db.with_name("broken.sqlite")
                with closing(sqlite3.connect(self.db)) as conn, closing(sqlite3.connect(broken)) as target:
                    conn.backup(target)
                    target.execute(mutation)
                    target.commit()
                with (patch.object(self, "db", broken),
                      patch.object(composition, "_execute_optional") as optional):
                    self.failure(code)
                    optional.assert_not_called()
                broken.unlink()

    def test_failed_category_admission_restores_scalar_authorizer_in_same_transaction(self):
        self.mutate("ALTER TABLE courses RENAME COLUMN category TO unavailable_category")
        request, budget = scope(), kernel._Budget(ExecutionLimits())
        compiled = kernel._compile_scope(request, LEARNINGOPS)
        category = GroupedAmountRequest(replace(request, metrics=(METRICS[0],)), "category")
        with (self.connections() as (_, traces),
              patch.object(grouped, "_execute_grouped_query", wraps=grouped._execute_grouped_query) as query):
            with kernel._read_transaction(self.db, budget) as (conn, snapshot):
                before = kernel._execute_scope(conn, request, compiled, LEARNINGOPS, snapshot["id"], budget)
                rows, callbacks = budget.rows, budget.callbacks
                with self.assertRaises(KernelError) as raised:
                    grouped._execute_grouped(conn, category, grouped._compile_grouped(category), snapshot, budget)
                self.assertEqual(raised.exception.code, "unsupported_source")
                query.assert_not_called()
                for sql in ("SELECT course_id FROM courses", "SELECT course_id FROM sessions",
                            "SELECT date(created_at_utc) FROM bookings"):
                    with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(sql).fetchall()
                after = kernel._execute_scope(conn, request, compiled, LEARNINGOPS, snapshot["id"], budget)
                self.assertTrue(conn.in_transaction)
                self.assertEqual([f.value for f in before], [68000, 4, 6])
                self.assertEqual([f.value for f in after], [68000, 4, 6])
                self.assertEqual({f.snapshot_id for f in (*before, *after)}, {snapshot["id"]})
                self.assertEqual((rows, budget.rows), (31, 31))
                self.assertGreater(budget.callbacks, callbacks)
        self.assertEqual(sum(sql == "BEGIN" for sql, _ in traces), 1)
        self.assertFalse(any("GROUP BY" in sql for sql, _ in traces))

    def test_real_65_category_cap_keeps_core_and_day_without_truncated_fact(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            for table, columns, ddl in (
                ("sessions", "session_id,course_id,center_id",
                 "session_id TEXT PRIMARY KEY NOT NULL,course_id TEXT NOT NULL REFERENCES courses(course_id),"
                 "center_id TEXT NOT NULL REFERENCES centers(center_id),UNIQUE(session_id,center_id)"),
                ("courses", "course_id,category", "course_id TEXT PRIMARY KEY NOT NULL,category TEXT"),
            ):
                conn.execute(f"CREATE TEMP TABLE saved_{table} AS SELECT {columns} FROM {table}")
                conn.execute(f"DROP TABLE {table}")
                conn.execute(f"CREATE TABLE {table}({ddl}) STRICT")
                conn.execute(f"INSERT INTO {table} SELECT * FROM saved_{table}")
            conn.execute("UPDATE bookings SET status='cancelled'")
            conn.execute("INSERT INTO bookings VALUES ('BG','CA',NULL,'2026-03-02T00:00:00Z','confirmed','TWD')")
            conn.executemany("INSERT INTO courses VALUES (?,?)", [(f"KG{i}", f"g{i:02}") for i in range(65)])
            conn.executemany("INSERT INTO sessions VALUES (?,?,'CA')", [(f"SG{i}", f"KG{i}") for i in range(65)])
            conn.executemany("INSERT INTO booking_items VALUES (?,'BG',?,'CA',1,1,0)",
                             [(f"IG{i}", f"SG{i}") for i in range(65)])
        result = self.execute()
        self.assert_result(result, {"category_amounts": "output_limit_exceeded"}, core=(65, 1, 65))
        self.assertEqual([(f.dimension, sum(r.value for r in f.rows)) for f in result.grouped_facts],
                         [("booking_day", 65)])

    def test_trusted_e10_timeout_and_finite_query_recoveries_keep_independent_slots(self):
        cases = [
            {"category": composition._ComponentTimeout()},
            {"booking_day": composition._ComponentTimeout()},
            {"booking_day": composition._ComponentTimeout(),
             "category": KernelError("output_limit_exceeded", DETAIL)},
            {"category": KernelError("output_limit_exceeded", DETAIL)},
            {"booking_day": KernelError("output_limit_exceeded", DETAIL)},
        ]
        execute = grouped._execute_grouped_query
        for failures in cases:
            with self.subTest(failures={key: value.code for key, value in failures.items()}):
                attempted = []

                def inject(conn, request, *args):
                    attempted.append(request.dimension)
                    if request.dimension in failures:
                        raise failures[request.dimension]
                    return execute(conn, request, *args)

                with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
                    result = self.execute()
                self.assert_result(result, {("daily_amount" if key == "booking_day" else "category_amounts"): exc.code
                                            for key, exc in failures.items()})
                self.assertEqual(attempted, ["booking_day", "category"])

    def test_generic_errors_and_wrong_recovery_origins_are_whole_failures(self):
        cases = [("query", "category", KernelError(code, DETAIL), code) for code in (
            "component_timeout", "execution_failure", "budget_exceeded", "unknown", "unsupported_source")]
        cases += [
            ("query", "booking_day", KernelError("unsupported_source", DETAIL), "unsupported_source"),
            ("query", "category", sqlite3.OperationalError(DETAIL), "execution_failure"),
            ("admission", "booking_day", KernelError("unsupported_source", DETAIL), "unsupported_source"),
            ("admission", "category", KernelError("output_limit_exceeded", DETAIL), "output_limit_exceeded"),
            ("admission", "category", composition._ComponentTimeout(), "component_timeout"),
        ]
        for stage, dimension, error, code in cases:
            with self.subTest(stage=stage, dimension=dimension, code=code):
                name = "_execute_grouped_query" if stage == "query" else "_validate_dimension_source"
                execute = getattr(grouped, name)

                def inject(conn, request, *args):
                    if (request.dimension if stage == "query" else request) == dimension:
                        raise error
                    return execute(conn, request, *args)

                with patch.object(grouped, name, side_effect=inject):
                    self.failure(code)

    def test_true_required_aggregate_overflow_never_attempts_optional_work(self):
        self.mutate("UPDATE booking_items SET seats=1,unit_price_minor=?,discount_minor=0 "
                    "WHERE item_id IN ('I01','I02')", (2**62,))
        with patch.object(composition, "_execute_optional") as optional:
            error = self.failure("execution_failure")
        optional.assert_not_called()
        self.assertIsInstance(error.__cause__, sqlite3.OperationalError)
        self.assertIn("integer overflow", str(error.__cause__))

    def test_required_missing_or_corrupted_checked_evidence_is_fatal(self):
        corruptions = [lambda facts: facts[:2],
                       lambda facts: (facts[0], replace(facts[1], fact_id=facts[0].fact_id), facts[2]),
                       lambda facts: (*facts[:2], replace(facts[2], population_rows=facts[2].population_rows + 1))]
        corruptions += [lambda facts, change=change: (replace(facts[0], **change), *facts[1:])
                        for change in ({"unit": "wrong"}, {"snapshot_id": "wrong"}, {"checks": ()},
                                       {"disclosures": ()}, {"value": True}, {"empty_population": True})]
        execute = kernel._execute_scope
        for index, corrupt in enumerate(corruptions):
            with (self.subTest(injected_copy=index),
                  patch.object(kernel, "_execute_scope", side_effect=lambda *args: corrupt(execute(*args))),
                  patch.object(composition, "_execute_optional") as optional):
                self.failure("incompatible_facts")
                optional.assert_not_called()

    def test_optional_semantic_snapshot_coverage_identity_and_integer_corruption_is_fatal(self):
        execute = grouped._execute_grouped_query
        changes = [{"unit": "wrong"}, {"snapshot_id": "wrong"}, {"snapshot": {}},
                   {"coverage": "top_k"}, {"checks": ()}, {"fact_id": ""},
                   {"rows": (GroupedAmountRow("technology", True),)},
                   {"rows": (GroupedAmountRow("technology", 2**63),)}, {"duplicate": True}]
        for change in changes:
            with self.subTest(injected_copy=change):
                seen = []

                def inject(*args):
                    fact = execute(*args)
                    seen.append(fact)
                    if fact.dimension == "category":
                        return replace(fact, **({"fact_id": seen[0].fact_id} if "duplicate" in change else change))
                    return fact

                with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
                    self.failure("incompatible_facts")
                self.assertEqual([f.dimension for f in seen], ["booking_day", "category"])

    def test_compatible_corrupted_rows_or_absence_are_gaps_not_repaired_facts(self):
        execute = grouped._execute_grouped_query
        for dimension, corruption, center in (
            ("booking_day", "sum", "CA"), ("category", "sum", "CA"),
            ("booking_day", "absent", "CA"), ("category", "fabricated", "CZ"),
        ):
            with self.subTest(dimension=dimension, injected_copy=corruption):
                attempted = []

                def inject(*args):
                    fact = execute(*args)
                    attempted.append(fact.dimension)
                    if fact.dimension != dimension:
                        return fact
                    rows = (() if corruption == "absent" else (GroupedAmountRow("technology", 0),)
                            if corruption == "fabricated" else
                            (replace(fact.rows[0], value=fact.rows[0].value + 1), *fact.rows[1:]))
                    return replace(fact, rows=rows, empty_population=not rows)

                with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
                    result = self.execute(scope(center_id=center))
                slot = "daily_amount" if dimension == "booking_day" else "category_amounts"
                self.assert_result(result, {slot: "reconciliation_failed"},
                                   core=(None, 0, None) if center == "CZ" else (68000, 4, 6))
                self.assertNotIn(dimension, [f.dimension for f in result.grouped_facts])
                self.assertEqual(attempted, ["booking_day", "category"])

    def test_one_transaction_admission_budget_and_core_with_final_cumulative_evidence(self):
        construct = composition._CompositionResult

        def after_close(*args):
            self.assertIn("completed_at_utc", args[3])
            with self.assertRaises(sqlite3.ProgrammingError):
                connections[0].execute("SELECT 1")
            return construct(*args)

        with (self.connections() as (connections, traces),
              patch.object(kernel, "_Budget", wraps=kernel._Budget) as budgets,
              patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as base,
              patch.object(kernel, "_execute_scope", wraps=kernel._execute_scope) as core,
              patch.object(grouped, "_execute_grouped_query", wraps=grouped._execute_grouped_query) as queries,
              patch.object(kernel, "execute_facts", side_effect=AssertionError("public scalar wrapper")),
              patch.object(grouped, "execute_grouped_amount", side_effect=AssertionError("public grouped wrapper")),
              patch.object(grepbit, "execute_facts", side_effect=AssertionError("public scalar alias")),
              patch.object(grepbit, "execute_grouped_amount", side_effect=AssertionError("public grouped alias")),
              patch.object(composition, "_CompositionResult", side_effect=after_close)):
            result = self.execute()
        self.assertEqual(len(connections), 1)
        self.assertEqual(sum(sql == "BEGIN" for sql, _ in traces), 1)
        self.assertTrue(all(active for sql, active in traces if sql.startswith("SELECT")))
        budgets.assert_called_once_with(ExecutionLimits())
        base.assert_called_once()
        core.assert_called_once()
        self.assertEqual(core.call_args.args[1].metrics, METRICS)
        budget = base.call_args.args[1]
        self.assertIs(core.call_args.args[0], connections[0])
        self.assertIs(core.call_args.args[-1], budget)
        self.assertEqual(queries.call_count, 2)
        for call in queries.call_args_list:
            self.assertIs(call.args[0], connections[0])
            self.assertIs(call.args[4], budget)
        self.assertEqual([f.execution["source_rows_validated"] for f in result.grouped_facts], [31, 48])
        self.assertEqual(result.execution["source_rows_validated"], budget.rows)
        self.assertEqual(result.execution["progress_callbacks"], budget.callbacks)

    def test_global_category_source_cap_47_aborts_after_successful_daily(self):
        with patch.object(grouped, "_execute_grouped_query", wraps=grouped._execute_grouped_query) as query:
            error = self.failure("budget_exceeded", limits=ExecutionLimits(max_source_rows=47))
        self.assertIn("Source-validation row budget", str(error))
        self.assertEqual([call.args[1].dimension for call in query.call_args_list], ["booking_day"])

    def test_global_deadline_wins_including_when_masked_by_local_timeout(self):
        execute = grouped._execute_grouped_query
        for local_timeout in (False, True):
            with self.subTest(local_timeout=local_timeout):
                clock, attempted = [100.0], []

                def inject(conn, request, *args):
                    attempted.append(request.dimension)
                    if request.dimension == "category":
                        clock[0] = 103.0
                        if local_timeout:
                            raise composition._ComponentTimeout()
                    return execute(conn, request, *args)

                with (patch.object(kernel.time, "monotonic", side_effect=lambda: clock[0]),
                      patch.object(grouped, "_execute_grouped_query", side_effect=inject)):
                    error = self.failure("budget_exceeded")
                self.assertIn("deadline", str(error))
                self.assertEqual(attempted, ["booking_day", "category"])

    def test_real_vm_callback_exhausts_injected_near_exhaustion_global_budget(self):
        execute, progress = grouped._execute_grouped_query, kernel._Budget.progress
        callbacks, observed = [], []

        def inject(conn, request, compiled, snapshot, budget, extension):
            if request.dimension == "category":
                self.assertGreater(budget.callbacks, 0)
                observed.append(budget)
                budget.callbacks = budget.limits.max_vm_steps // 100 - 1
            return execute(conn, request, compiled, snapshot, budget, extension)

        def tracked(budget):
            result = progress(budget)
            callbacks.append((budget, budget.callbacks, result))
            return result

        with (patch.object(grouped, "_execute_grouped_query", side_effect=inject),
              patch.object(kernel._Budget, "progress", new=tracked)):
            error = self.failure("budget_exceeded")
        self.assertIn("VM step budget", str(error))
        self.assertEqual(callbacks[-1][1:], (10000, 1))
        self.assertIs(callbacks[-1][0], observed[0])

    def test_shared_snapshot_id_corruption_after_category_or_exit_is_fatal(self):
        """Trusted metadata corruption, not actual SQLite transaction loss."""
        execute, transaction = grouped._execute_grouped_query, kernel._read_transaction
        for stage in ("return", "timeout", "exit"):
            with self.subTest(stage=stage):
                checked = []

                def inject(conn, request, compiled, snapshot, budget, extension):
                    fact = execute(conn, request, compiled, snapshot, budget, extension)
                    checked.append(fact)
                    self.assertIs(fact.snapshot, snapshot)
                    self.assertEqual(fact.snapshot_id, snapshot["id"])
                    if request.dimension == "category" and stage != "exit":
                        self.assertTrue(conn.in_transaction)
                        snapshot["id"] = "corrupted-shared-id"
                        if stage == "timeout":
                            raise composition._ComponentTimeout()
                    return fact

                @contextmanager
                def corrupt_exit(*args):
                    with transaction(*args) as opened:
                        yield opened
                    if stage == "exit":
                        opened[1]["id"] = "corrupted-shared-id"

                with (patch.object(grouped, "_execute_grouped_query", side_effect=inject),
                      patch.object(kernel, "_read_transaction", side_effect=corrupt_exit)):
                    self.failure("snapshot_lost")
                self.assertEqual([fact.dimension for fact in checked], ["booking_day", "category"])
                self.assertIs(checked[0].snapshot, checked[1].snapshot)
                self.assertNotEqual(checked[1].snapshot_id, checked[1].snapshot["id"])

    def test_actual_close_rollback_and_sqlite_interrupt_never_return_partial(self):
        execute = grouped._execute_grouped_query
        for loss, code in (("close", "execution_failure"), ("rollback", "snapshot_lost"),
                           ("interrupt", "execution_failure")):
            with self.subTest(loss=loss):
                def inject(conn, request, *args):
                    if request.dimension == "category":
                        if loss == "interrupt":
                            conn.set_trace_callback(lambda sql: conn.interrupt() if "GROUP BY" in sql else None)
                        else:
                            if loss == "close":
                                conn.close()
                            else:
                                conn.set_authorizer(None)
                                conn.execute("ROLLBACK")
                            raise composition._ComponentTimeout()
                    return execute(conn, request, *args)

                with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
                    self.failure(code)

    def test_python_interruptions_propagate_and_release_connection_and_locks(self):
        execute = grouped._execute_grouped_query
        for exception in (KeyboardInterrupt, SystemExit):
            with self.subTest(exception=exception.__name__):
                def inject(conn, request, *args):
                    if request.dimension == "category":
                        raise exception(DETAIL)
                    return execute(conn, request, *args)

                with patch.object(grouped, "_execute_grouped_query", side_effect=inject):
                    self.failure(None, exception=exception)

    def test_sqlite_failure_escaping_transaction_exit_never_constructs_result(self):
        transaction = kernel._read_transaction

        @contextmanager
        def failed_exit(*args):
            with transaction(*args) as opened:
                yield opened
            raise sqlite3.OperationalError(DETAIL)

        with patch.object(kernel, "_read_transaction", side_effect=failed_exit):
            self.failure("execution_failure")

    def test_real_wal_commit_changes_fresh_amount_and_category_not_inflight_snapshot(self):
        execute, writes = kernel._execute_scope, []
        with closing(sqlite3.connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))

            def commit_after_core(*args):
                facts = execute(*args)
                self.assertFalse(writes)
                with writer:
                    writer.execute("UPDATE booking_items SET unit_price_minor=unit_price_minor+1000 WHERE item_id='I01'")
                    writer.execute("UPDATE courses SET category='changed' WHERE course_id='K1'")
                writes.append(writer.total_changes)
                self.assertFalse(writer.in_transaction)
                with closing(sqlite3.connect(self.db, timeout=0)) as observer:
                    sql, parameters = kernel._compile(LEARNINGOPS.metrics[METRICS[0]], scope())
                    self.assertEqual(observer.execute(sql, parameters).fetchone()[0], 70000)
                    self.assertEqual(observer.execute("SELECT category FROM courses WHERE course_id='K1'").fetchone(),
                                     ("changed",))
                return facts

            with patch.object(kernel, "_execute_scope", side_effect=commit_after_core):
                inflight = self.execute()
        self.assertEqual(writes, [2])
        self.assert_result(inflight)
        self.assertEqual([sum(r.value for r in f.rows) for f in inflight.grouped_facts], [68000, 68000])
        self.assertEqual([(r.key, r.value) for r in inflight.grouped_facts[1].rows],
                         [("arts", 30000), ("technology", 38000)])
        self.assertEqual({f.snapshot_id for f in (*inflight.facts, *inflight.grouped_facts)}, {inflight.snapshot["id"]})
        fresh = self.execute()
        self.assert_result(fresh, core=(70000, 4, 6))
        self.assertEqual([sum(r.value for r in f.rows) for f in fresh.grouped_facts], [70000, 70000])
        self.assertEqual([(r.key, r.value) for r in fresh.grouped_facts[1].rows],
                         [("arts", 30000), ("changed", 40000)])
        self.assertNotEqual(fresh.snapshot["id"], inflight.snapshot["id"])


if __name__ == "__main__":
    unittest.main()
