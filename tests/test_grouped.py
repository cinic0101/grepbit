"""Offline grouped-amount regressions on disposable fixtures, not model evaluations."""
from contextlib import closing, contextmanager
from dataclasses import replace
import inspect
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from uuid import UUID

from grepbit import (
    CompareRequest, ExecutionLimits, Fact, FactRequest, GroupedAmountFact,
    GroupedAmountRequest, GroupedAmountRow, KernelError, execute_compare,
    execute_facts, execute_grouped_amount,
)
from grepbit import grouped, kernel
from grepbit.catalog import LEARNINGOPS
from tools import fixture


DIMENSIONS = ("category", "booking_day", "course")
CATEGORY = [("arts", 90000), ("technology", 68000)]
DAY = [(f"2026-03-{day}", value) for day, value in (
    ("01", 35000), ("05", 8000), ("07", 10000), ("10", 15000),
    ("12", 30000), ("13", 40000), ("20", 20000),
)]
COURSE = [("K1", 68000), ("K3", 60000), ("K2", 30000)]
COURSES_DDL = "CREATE TABLE courses(course_id TEXT PRIMARY KEY NOT NULL, category TEXT) STRICT"
SESSIONS_DDL = (
    "CREATE TABLE sessions(session_id TEXT PRIMARY KEY NOT NULL, "
    "course_id TEXT NOT NULL REFERENCES courses(course_id), "
    "center_id TEXT NOT NULL REFERENCES centers(center_id), UNIQUE(session_id,center_id)) STRICT"
)


def scope(**changes):
    data = dict(metrics=["confirmed_booked_amount"], start="2026-03-01T00:00:00+08:00",
                end="2026-04-01T00:00:00+08:00", timezone="Asia/Taipei")
    data.update(changes)
    return data


def request(dimension="category", **changes):
    return GroupedAmountRequest(FactRequest.from_mapping(scope(**changes)), dimension,
                                3 if dimension == "course" else None)


class GroupedTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.fresh("learning")

    def fresh(self, name):
        db = self.root / f"{name}.sqlite"
        fixture.build(db)
        return db

    def mutate(self, *statements, db=None):
        with closing(sqlite3.connect(db or self.db)) as conn, conn:
            for sql, parameters in statements:
                conn.execute(sql, parameters)

    def rebuild(self, db, table, ddl):
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(f"CREATE TEMP TABLE saved AS SELECT * FROM {table}")
            old = {row[1] for row in conn.execute("PRAGMA temp.table_info(saved)")}
            conn.execute(f"DROP TABLE {table}")
            conn.execute(ddl)
            columns = ",".join(row[1] for row in conn.execute(f"PRAGMA table_xinfo({table})")
                               if row[1] in old and row[6] == 0)
            conn.execute(f"INSERT INTO {table}({columns}) SELECT {columns} FROM saved")

    def run_group(self, dimension="category", *, db=None, req=None, **kwargs):
        return execute_grouped_amount(db or self.db, req or request(dimension), **kwargs)

    def pairs(self, fact):
        return [(row.key, row.value) for row in fact.rows]

    def error(self, codes, function, *args, **kwargs):
        with self.assertRaises(KernelError) as raised:
            function(*args, **kwargs)
        self.assertIn(raised.exception.code, (codes,) if isinstance(codes, str) else codes)
        self.assertTrue(str(raised.exception))
        self.assertNotIn(str(self.root), str(raised.exception))
        return raised.exception

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

    def failure(self, codes, dimension="category", *, db=None, **kwargs):
        db = db or self.db
        before = db.read_bytes()
        with self.connections(), patch.object(grouped, "GroupedAmountFact") as result:
            error = self.error(codes, self.run_group, dimension, db=db, **kwargs)
        result.assert_not_called()
        self.assertEqual(db.read_bytes(), before)
        with closing(sqlite3.connect(db, timeout=0)) as writer:
            writer.execute("BEGIN EXCLUSIVE")
            writer.execute("UPDATE centers SET name=name")
            writer.rollback()
        return error

    def scalar(self, conn, scope_request, snapshot, budget):
        return kernel._execute_scope(conn, scope_request, kernel._compile_scope(scope_request, LEARNINGOPS),
                                     LEARNINGOPS, snapshot["id"], budget)[0]

    def grouped(self, conn, req, snapshot, budget):
        return grouped._execute_grouped(conn, req, grouped._compile_grouped(req), snapshot, budget)

    def test_public_request_and_execution_are_narrow_and_typed(self):
        self.assertEqual(tuple(inspect.signature(GroupedAmountRequest).parameters),
                         ("scope", "dimension", "top_k"))
        signature = inspect.signature(execute_grouped_amount)
        self.assertEqual(tuple(signature.parameters), ("database", "request", "limits"))
        self.assertEqual(signature.parameters["limits"].kind, inspect.Parameter.KEYWORD_ONLY)
        for dimension in DIMENSIONS:
            data = dict(scope=scope(), dimension=dimension)
            if dimension == "course":
                data["top_k"] = 3
            self.assertEqual(GroupedAmountRequest.from_mapping(data), request(dimension))
        self.assertEqual(request().scope, request(start="2026-02-28T16:00:00Z",
                                                  end="2026-03-31T16:00:00Z").scope)
        for value in (None, {}, [], "SELECT 1", True):
            with self.subTest(value=value):
                self.error("invalid_request", execute_grouped_amount, self.db, value)
                self.error("invalid_request", replace, request(), scope=value)
                self.error("invalid_request", self.run_group, limits=value)
        self.error("invalid_request", execute_grouped_amount, str(self.db), request())
        with self.assertRaises(TypeError):
            execute_grouped_amount(self.db, request(), sql="SELECT 1")

    def test_invalid_mapping_matrix_has_no_implicit_scope_or_generic_language(self):
        invalid = [None, [], "", True, {}, {"scope": scope()}, {"dimension": "category"}]
        invalid += [dict(scope=value, dimension="category") for value in (None, [], True, request().scope)]
        invalid += [dict(scope=scope(), dimension=value) for value in
                    (None, True, [], ["category", "course"], "center", "CATEGORY", "date")]
        invalid += [dict(scope=scope(), dimension="course", top_k=value)
                    for value in (None, True, False, 0, 4, -1, 1.0, "1", "1+1", [])]
        invalid += [dict(scope=scope(), dimension=dimension, top_k=value)
                    for dimension in ("category", "booking_day") for value in (0, 1, False)]
        extras = {"order": "key", "order_by": "value DESC", "filter": {}, "filters": {}, "functions": [], "sql": "SELECT 1",
                  "formula": "sum(amount)", "table": "courses", "callback": None,
                  "catalog": {}, "dimensions": ["category"], "year": 2026, "month": 3}
        for key, value in extras.items():
            invalid += [dict(scope=scope(), dimension="category", **{key: value}),
                        dict(scope=scope(**{key: value}), dimension="category")]
        for key in ("metrics", "start", "end", "timezone"):
            data = scope()
            del data[key]
            invalid.append(dict(scope=data, dimension="category"))
        changes = [{"metrics": value} for value in
                   ([], ["booked_seats"], ["unknown"], ["confirmed_booked_amount", "booked_seats"])]
        changes += [{"timezone": value} for value in ("UTC", "Asia/Shanghai", None)]
        changes += [{"center_id": value} for value in ("", True, [], "C" * 65)]
        changes += [{"start": value} for value in
                    ("03-01", "2026-03", "March", None, "2026-03-01T00:00:00",
                     "2026-03-02T00:00:00+08:00", "2026-03-01T00:00:00.000001+08:00")]
        changes += [{"end": value} for value in
                    ("2026-03-31T23:59:59+08:00", "2026-05-01T00:00:00+08:00",
                     "2026-03-01T00:00:00+08:00")]
        invalid += [dict(scope=scope(**change), dimension="category") for change in changes]
        for index, data in enumerate(invalid):
            with self.subTest(case=index):
                self.error("invalid_request", GroupedAmountRequest.from_mapping, data)
        for dimension, top_k in (("course", True), ("course", None), ("course", 4),
                                 ("category", 1), ("booking_day", 1), (["category"], None)):
            with self.subTest(dimension=dimension, top_k=top_k):
                self.error("invalid_request", GroupedAmountRequest, request().scope, dimension, top_k)

    def test_exact_witnesses_and_fact_evidence(self):
        identities = set()
        for dimension, expected in zip(DIMENSIONS, (CATEGORY, DAY, COURSE)):
            for k in ((1, 2, 3) if dimension == "course" else (None,)):
                with self.subTest(dimension=dimension, k=k):
                    req = replace(request(dimension), top_k=k)
                    fact = self.run_group(req=req)
                    self.assertIs(type(fact), GroupedAmountFact)
                    self.assertNotIsInstance(fact, Fact)
                    self.assertIs(type(fact.rows), tuple)
                    self.assertEqual(self.pairs(fact), expected[:k])
                    self.assertTrue(all(type(row) is GroupedAmountRow and type(row.value) is int
                                        for row in fact.rows))
                    self.assertEqual((fact.unit, fact.grain, fact.time_basis),
                                     ("TWD_minor", "booking_line", "bookings.created_at_utc"))
                    self.assertEqual((fact.metric_id, fact.catalog_id, fact.catalog_sha256),
                                     ("confirmed_booked_amount", LEARNINGOPS.version, LEARNINGOPS.digest()))
                    self.assertEqual((fact.start_utc, fact.end_utc, fact.business_timezone, fact.filters),
                                     ("2026-02-28T16:00:00Z", "2026-03-31T16:00:00Z", "Asia/Taipei", {}))
                    self.assertEqual(fact.coverage, "top_k" if k else "all_observed_groups")
                    self.assertEqual(fact.top_k, k)
                    self.assertEqual(fact.ordering, {"category": ("key_asc_nulls_first",),
                                     "booking_day": ("key_asc",), "course": ("value_desc", "key_asc")}[dimension])
                    self.assertEqual(fact.parameters["row_limit"], k or 65)
                    self.assertIn("LIMIT :row_limit", fact.sql)
                    self.assertNotIn("DISTINCT", fact.sql)
                    self.assertFalse(fact.empty_population)
                    self.assertEqual(fact.snapshot_id, fact.snapshot["id"])
                    self.assertEqual(fact.snapshot["scope"], "single_read_transaction")
                    self.assertIn("completed_at_utc", fact.snapshot)
                    for identity in (fact.fact_id, fact.snapshot_id):
                        self.assertEqual(str(UUID(identity)), identity)
                        self.assertNotIn(identity, identities)
                        identities.add(identity)
                    self.assertEqual(fact.dimension_profile_id, "learningops-grouped-amount-v1")
                    if dimension == "booking_day":
                        self.assertIsNone(fact.dimension_source_sha256)
                    else:
                        self.assertRegex(fact.dimension_source_sha256, r"^[0-9a-f]{64}$")
                    self.assertIn("read_only_single_transaction", fact.checks)
                    self.assertIn("grouped_integer_shape_and_key_bounds", fact.checks)
                    self.assertEqual(set(fact.runtime), {"python", "sqlite", "sqlglot"})
                    self.assertGreater(fact.execution["progress_callbacks"], 0)
                    self.assertTrue(fact.limitations)
                    data = json.loads(json.dumps(fact.to_dict()))
                    self.assertEqual(data["rows"], [dict(key=key, value=value) for key, value in expected[:k]])
                    self.assertFalse({"status", "facts", "recipe_id", "subtotal", "share"} & data.keys())

    def test_canonical_centers_do_not_resolve_codes_names_or_unknown_ids(self):
        with closing(sqlite3.connect(self.db)) as conn:
            name = conn.execute("SELECT name FROM centers WHERE center_id='CA'").fetchone()[0]
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                fact = self.run_group(req=request(dimension, center_id="CA"))
                self.assertEqual(sum(row.value for row in fact.rows), 68000)
                self.assertEqual(fact.filters, {"center_id": "CA"})
                for center in ("CTR-A01", name, "missing"):
                    self.error("unknown_entity", self.run_group, req=request(dimension, center_id=center))

    def test_full_groups_reconcile_with_scalar_only_in_same_transaction(self):
        scopes = ({}, {"center_id": "CA"}, {"center_id": "CZ"},
                  dict(start="2027-01-01T00:00:00+08:00", end="2027-02-01T00:00:00+08:00"))
        for changes, total in zip(scopes, (158000, 68000, None, None)):
            with self.subTest(scope=changes):
                budget = kernel._Budget(ExecutionLimits())
                with kernel._read_transaction(self.db, budget) as (conn, snapshot):
                    scalar = self.scalar(conn, request(**changes).scope, snapshot, budget)
                    self.assertEqual(scalar.value, total)
                    for dimension in ("category", "booking_day"):
                        fact = self.grouped(conn, request(dimension, **changes), snapshot, budget)
                        for field in ("snapshot_id", "metric_id", "catalog_sha256", "unit", "grain",
                                      "population", "time_basis", "start_utc", "end_utc", "filters"):
                            self.assertEqual(getattr(fact, field), getattr(scalar, field))
                        self.assertEqual(fact.empty_population, scalar.empty_population)
                        self.assertEqual(sum(row.value for row in fact.rows) if fact.rows else None, total)
                    for k in (1, 2):
                        fact = self.grouped(conn, replace(request("course", **changes), top_k=k),
                                            snapshot, budget)
                        self.assertEqual(fact.snapshot_id, scalar.snapshot_id)
                        self.assertEqual((fact.coverage, fact.top_k), ("top_k", k))
                        if not changes:
                            self.assertLess(sum(row.value for row in fact.rows), scalar.value)
                        if total is None:
                            self.assertEqual(fact.rows, ())

    def test_null_category_is_distinct_from_literal_unknown_and_binary_sorted(self):
        self.mutate(("UPDATE courses SET category=CASE course_id "
                     "WHEN 'K1' THEN 'Unknown' WHEN 'K2' THEN NULL ELSE 'unknown' END", ()))
        self.assertEqual(self.pairs(self.run_group()),
                         [(None, 30000), ("Unknown", 68000), ("unknown", 60000)])

    def test_zero_population_is_not_empty_and_absent_members_are_not_filled(self):
        self.mutate(("UPDATE booking_items SET unit_price_minor=0,discount_minor=0", ()))
        for dimension, expected in zip(DIMENSIONS, (CATEGORY, DAY, sorted(COURSE))):
            with self.subTest(dimension=dimension):
                fact = self.run_group(dimension)
                self.assertFalse(fact.empty_population)
                self.assertEqual(self.pairs(fact), [(key, 0) for key, _ in expected])
        self.mutate(("UPDATE bookings SET status='cancelled'", ()))
        for dimension in DIMENSIONS:
            fact = self.run_group(dimension)
            self.assertEqual(fact.rows, ())
            self.assertTrue(fact.empty_population)

    def test_day_is_creation_time_with_fixed_utc8_half_open_month_boundaries(self):
        self.mutate(("UPDATE sessions SET starts_at_utc='2040-01-01T00:00:00Z'", ()),
                    ("INSERT INTO bookings VALUES ('BX','CA',NULL,'2026-03-31T15:59:59Z','confirmed','TWD')", ()),
                    ("INSERT INTO booking_items VALUES ('IX','BX','S01','CA',1,7,0)", ()))
        for start, end, expected in (
            ("2026-02-01", "2026-03-01", [("2026-02-04", 10000), ("2026-02-06", 30000), ("2026-02-28", 10000)]),
            ("2026-03-01", "2026-04-01", DAY + [("2026-03-31", 7)]),
            ("2026-04-01", "2026-05-01", [("2026-04-01", 20000)]),
        ):
            with self.subTest(start=start):
                fact = self.run_group(req=request("booking_day", start=start + "T00:00:00+08:00",
                                                   end=end + "T00:00:00+08:00"))
                self.assertEqual(self.pairs(fact), expected)

    def test_course_ranking_aggregates_late_lines_before_top_k(self):
        self.mutate(("INSERT INTO courses VALUES ('KZ','LATE','Late','late')", ()),
                    ("INSERT INTO sessions VALUES ('SZ','KZ','CA','2026-03-01T00:00:00Z',60,10)", ()),
                    ("INSERT INTO bookings VALUES ('BZ','CA',NULL,'2026-03-25T00:00:00Z','confirmed','TWD')", ()),
                    *(("INSERT INTO booking_items VALUES (?, 'BZ','SZ','CA',1,25000,0)", (f"IZ{i}",))
                      for i in range(3)))
        self.assertEqual(self.pairs(self.run_group(req=replace(request("course"), top_k=1))), [("KZ", 75000)])

    def test_course_ties_return_exactly_k_with_binary_course_id_tiebreak(self):
        self.mutate(("UPDATE booking_items SET seats=1,unit_price_minor=0,discount_minor=0", ()),
                    ("UPDATE booking_items SET unit_price_minor=30000 WHERE item_id IN ('I01','I02','I06')", ()))
        for k in (1, 2, 3):
            with self.subTest(k=k):
                self.assertEqual(self.pairs(self.run_group(req=replace(request("course"), top_k=k))),
                                 [(key, 30000) for key in ("K1", "K2", "K3")[:k]])

    def test_keys_only_session_parent_without_courses_preserves_scalar_day_compare(self):
        self.rebuild(self.db, "sessions", "CREATE TABLE sessions(session_id TEXT PRIMARY KEY NOT NULL, "
                     "center_id TEXT NOT NULL, UNIQUE(session_id,center_id)) STRICT")
        self.mutate(("DROP TABLE courses", ()))
        self.assertEqual(execute_facts(self.db, request().scope).facts[0].value, 158000)
        self.assertEqual(self.pairs(self.run_group("booking_day")), DAY)
        baseline = FactRequest.from_mapping(scope(start="2026-02-01T00:00:00+08:00",
                                                  end="2026-03-01T00:00:00+08:00"))
        self.assertEqual([fact.value for fact in execute_compare(
            self.db, CompareRequest(request().scope, baseline)).facts], [158000, 50000])
        for dimension in ("category", "course"):
            self.failure("unsupported_source", dimension)

    def test_missing_session_parent_is_still_rejected_by_scalar_and_day(self):
        self.mutate(("DROP TABLE sessions", ()))
        self.error("unsupported_source", execute_facts, self.db, request().scope)
        self.failure("unsupported_source", "booking_day")

    def test_only_consumed_dimension_columns_are_required(self):
        self.rebuild(self.db, "sessions", SESSIONS_DDL)
        self.rebuild(self.db, "courses", COURSES_DDL.replace("PRIMARY KEY NOT NULL", "PRIMARY KEY"))
        self.assertEqual(self.pairs(self.run_group()), CATEGORY)
        self.assertEqual(self.pairs(self.run_group("course")), COURSE)
        self.rebuild(self.db, "courses", COURSES_DDL.replace(", category TEXT", ""))
        self.assertEqual(self.pairs(self.run_group("course")), COURSE)
        self.failure("unsupported_source", "category")

    def test_malformed_dimension_profiles_fail_before_group_query(self):
        variants = [
            ("courses", COURSES_DDL.replace(" STRICT", "")),
            ("courses", COURSES_DDL.replace("category TEXT", "category ANY")),
            ("courses", COURSES_DDL.replace("category TEXT", "category TEXT NOT NULL")),
            ("courses", COURSES_DDL.replace("PRIMARY KEY NOT NULL", "UNIQUE NOT NULL")),
            ("courses", COURSES_DDL.replace("category TEXT", "category TEXT GENERATED ALWAYS AS ('x') VIRTUAL")),
            ("courses", COURSES_DDL.replace("category TEXT", "category TEXT COLLATE NOCASE")),
            ("courses", COURSES_DDL.replace("course_id TEXT", "course_id ANY")),
            ("courses", COURSES_DDL.replace("course_id TEXT", "course_id TEXT COLLATE NOCASE")),
            ("courses", "CREATE TABLE courses(course_id TEXT NOT NULL,category TEXT, "
             "PRIMARY KEY(course_id,category)) STRICT"),
            ("sessions", SESSIONS_DDL.replace(" STRICT", "")),
            ("sessions", SESSIONS_DDL.replace("course_id TEXT NOT NULL", "course_id TEXT")),
            ("sessions", SESSIONS_DDL.replace("course_id TEXT", "course_id ANY")),
            ("sessions", SESSIONS_DDL.replace("PRIMARY KEY NOT NULL", "UNIQUE NOT NULL")),
            ("sessions", SESSIONS_DDL.replace("course_id TEXT NOT NULL", "course_id TEXT NOT NULL COLLATE NOCASE")),
            ("sessions", SESSIONS_DDL.replace("course_id TEXT NOT NULL",
             "course_id TEXT GENERATED ALWAYS AS ('K1') VIRTUAL NOT NULL")),
            ("sessions", SESSIONS_DDL.replace("REFERENCES courses(course_id)", "")),
            ("sessions", SESSIONS_DDL.replace("REFERENCES centers(center_id)", "")),
            ("sessions", SESSIONS_DDL.replace(", UNIQUE(session_id,center_id)", "")),
        ]
        for index, (table, ddl) in enumerate(variants):
            with self.subTest(table=table, ddl=ddl):
                db = self.fresh(f"profile{index}")
                self.mutate(("UPDATE courses SET category='filled' WHERE category IS NULL", ()), db=db)
                self.rebuild(db, table, ddl)
                with self.connections() as (_, traces):
                    self.error(("unsupported_source", "execution_failure"), self.run_group, db=db)
                self.assertFalse(any("GROUP BY" in sql for sql, _ in traces))
        for table in ("courses", "sessions"):
            with self.subTest(view=table):
                db = self.fresh(f"{table}_view")
                self.mutate((f"CREATE TABLE hidden AS SELECT * FROM {table}", ()),
                            (f"DROP TABLE {table}", ()),
                            (f"CREATE VIEW {table} AS SELECT * FROM hidden", ()), db=db)
                self.failure(("unsupported_source", "execution_failure"), db=db)

    def test_actual_relationships_and_null_course_keys_are_not_repaired(self):
        for index, sql in enumerate((
            "UPDATE sessions SET course_id='absent' WHERE session_id='S01'",
            "UPDATE sessions SET center_id='CB' WHERE session_id='S01'",
            "UPDATE sessions SET center_id='missing' WHERE session_id='S08'",
        )):
            with self.subTest(sql=sql):
                db = self.fresh(f"relationship{index}")
                self.mutate((sql, ()), db=db)
                for dimension in ("category", "course"):
                    self.failure("unsupported_source", dimension, db=db)
        # STRICT primary keys imply NOT NULL; a nullable UNIQUE key is not the admitted PK.
        self.rebuild(self.db, "courses", COURSES_DDL.replace("PRIMARY KEY NOT NULL", "UNIQUE"))
        self.mutate(("UPDATE courses SET course_id=NULL WHERE course_id='K5'", ()))
        self.failure("unsupported_source", "course")

    def test_category_row_cap_has_inclusive_64_and_rejects_65_without_partial_result(self):
        self.rebuild(self.db, "sessions", SESSIONS_DDL)
        self.rebuild(self.db, "courses", COURSES_DDL)
        self.mutate(("UPDATE bookings SET status='cancelled'", ()),
                    ("INSERT INTO bookings VALUES ('BG','CA',NULL,'2026-03-02T00:00:00Z','confirmed','TWD')", ()))
        for index in range(65):
            self.mutate(("INSERT INTO courses VALUES (?,?)", (f"KG{index}", f"g{index:02}")),
                        ("INSERT INTO sessions VALUES (?,?,'CA')", (f"SG{index}", f"KG{index}")),
                        ("INSERT INTO booking_items VALUES (?, 'BG',?,'CA',1,1,0)", (f"IG{index}", f"SG{index}")))
            if index == 63:
                self.assertEqual(self.pairs(self.run_group()), [(f"g{i:02}", 1) for i in range(64)])
        self.failure("output_limit_exceeded")

    def test_utf8_key_byte_limits_are_exact_and_validate_unselected_sources(self):
        for dimension, size in (("category", 256), ("course", 64)):
            with self.subTest(dimension=dimension):
                db = self.fresh(dimension)
                key = "\u00e9" * (size // 2)
                column = "category" if dimension == "category" else "course_id"
                self.mutate((f"UPDATE courses SET {column}=? WHERE course_id='K1'", (key,)), db=db)
                if dimension == "course":
                    self.mutate(("UPDATE sessions SET course_id=? WHERE course_id='K1'", (key,)), db=db)
                self.assertIn(key, [row.key for row in self.run_group(dimension, db=db).rows])
                self.mutate((f"UPDATE courses SET {column}=? WHERE course_id='K5'", (key + "x",)), db=db)
                if dimension == "course":
                    self.mutate(("UPDATE sessions SET course_id=? WHERE course_id='K5'", (key + "x",)), db=db)
                self.failure("unsupported_source", dimension, db=db)

    def test_invalid_utf8_and_empty_course_ids_fail_safely(self):
        for index, (dimension, assignment) in enumerate((
            ("category", "category=CAST(X'80' AS TEXT)"), ("course", "course_id=CAST(X'80' AS TEXT)"),
            ("course", "course_id=''"),
        )):
            with self.subTest(dimension=dimension, assignment=assignment):
                db = self.fresh(f"badkey{index}")
                self.mutate((f"UPDATE courses SET {assignment} WHERE course_id='K5'", ()), db=db)
                if dimension == "course":
                    self.mutate((f"UPDATE sessions SET {assignment} WHERE course_id='K5'", ()), db=db)
                self.failure(("unsupported_source", "execution_failure"), dimension, db=db)

    def test_exact_int64_max_and_sum_overflow_fail_closed_and_release_locks(self):
        self.mutate(("UPDATE booking_items SET seats=1,unit_price_minor=0,discount_minor=0", ()),
                    ("UPDATE booking_items SET unit_price_minor=? WHERE item_id='I01'", (2**63 - 1,)))
        for dimension in DIMENSIONS:
            self.assertIn(2**63 - 1, [row.value for row in self.run_group(dimension).rows])
        self.mutate(("INSERT INTO booking_items VALUES ('IO','B01','S01','CA',1,1,0)", ()))
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.failure("execution_failure", dimension)

    def test_one_connection_base_validation_extension_and_shared_budget(self):
        with (self.connections() as (connections, traces),
              patch.object(kernel, "_Budget", wraps=kernel._Budget) as budgets,
              patch.object(kernel, "_validate_source", wraps=kernel._validate_source) as base,
              patch.object(grouped, "_validate_dimension_source", wraps=grouped._validate_dimension_source) as extension):
            fact = self.run_group()
        self.assertEqual(len(connections), 1)
        self.assertEqual([sql for sql, _ in traces if sql == "BEGIN"], ["BEGIN"])
        self.assertTrue(all(active for sql, active in traces if sql.startswith("SELECT")))
        base.assert_called_once()
        extension.assert_called_once()
        budgets.assert_called_once_with(ExecutionLimits())
        self.assertIs(base.call_args.args[0], connections[0])
        self.assertIs(extension.call_args.args[0], connections[0])
        self.assertIs(base.call_args.args[1], extension.call_args.args[2])
        self.assertEqual(fact.execution["source_rows_validated"], 48)

    def test_source_row_budget_counts_independent_tables_and_exact_boundaries(self):
        with closing(sqlite3.connect(self.db)) as conn:
            counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("centers", "bookings", "booking_items", "courses", "sessions")}
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                count = sum(counts[table] for table in
                            (("centers", "bookings", "booking_items") if dimension == "booking_day" else counts))
                self.assertEqual(count, 31 if dimension == "booking_day" else 48)
                fact = self.run_group(dimension, limits=ExecutionLimits(max_source_rows=count))
                self.assertEqual(fact.execution["source_rows_validated"], count)
                self.failure("budget_exceeded", dimension, limits=ExecutionLimits(max_source_rows=count - 1))
        self.assertEqual(ExecutionLimits(), ExecutionLimits(2.0, 1_000_000, 100_000))

    def test_deadline_is_not_reset_after_extension_or_before_group_query(self):
        clock, observed = [100.0], []
        validate = grouped._validate_dimension_source

        def extension(conn, dimension, budget):
            observed.append(budget)
            clock[0] = 100.75
            result = validate(conn, dimension, budget)
            clock[0] = 101.25
            return result

        with (patch.object(kernel.time, "monotonic", side_effect=lambda: clock[0]),
              patch.object(grouped, "_validate_dimension_source", side_effect=extension)):
            error = self.failure("budget_exceeded", limits=ExecutionLimits(timeout_seconds=1))
        self.assertIn("deadline", str(error))
        self.assertEqual((len(observed), observed[0].started, observed[0].rows), (1, 100.0, 48))

    def test_real_group_query_progress_callback_uses_remaining_shared_vm_budget(self):
        validate, progress = grouped._validate_dimension_source, kernel._Budget.progress
        callbacks, observed = [], []

        def extension(conn, dimension, budget):
            result = validate(conn, dimension, budget)
            self.assertGreater(budget.callbacks, 0)
            observed.append(budget)
            budget.callbacks = budget.limits.max_vm_steps // 100 - 1
            return result

        def tracked(budget):
            before = budget.callbacks
            result = progress(budget)
            callbacks.append((before, budget.callbacks, result, budget))
            return result

        with (patch.object(grouped, "_validate_dimension_source", side_effect=extension),
              patch.object(kernel._Budget, "progress", new=tracked)):
            error = self.failure("budget_exceeded")
        self.assertIn("VM step budget", str(error))
        self.assertEqual(callbacks[-1][:3], (9999, 10000, 1))
        self.assertIs(callbacks[-1][3], observed[0])

    def test_scalar_authorizer_is_restored_after_success_and_failed_group_query(self):
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                budget = kernel._Budget(ExecutionLimits())
                with kernel._read_transaction(self.db, budget) as (conn, snapshot):
                    req = request(dimension)
                    self.grouped(conn, req, snapshot, budget)
                    for sql in ("SELECT course_id FROM sessions", "SELECT category FROM courses",
                                "SELECT date(created_at_utc) FROM bookings"):
                        with self.assertRaises(sqlite3.DatabaseError):
                            conn.execute(sql).fetchall()
                    with self.assertRaises(sqlite3.DatabaseError):
                        grouped._execute_grouped(conn, req, ("SELECT email FROM learners", {}), snapshot, budget)
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute("SELECT category FROM courses").fetchall()
                    self.assertEqual(self.scalar(conn, req.scope, snapshot, budget).value, 158000)

    def test_hostile_compiler_cannot_expand_dimension_authorization(self):
        common = ("SELECT email FROM learners", "SELECT random()", "SELECT total(seats) FROM booking_items",
                  "UPDATE bookings SET status='cancelled'", "ATTACH DATABASE ':memory:' AS extra")
        for dimension in DIMENSIONS:
            denied = ("SELECT category FROM courses", "SELECT course_id FROM sessions") if dimension == "booking_day" else (
                "SELECT date(created_at_utc) FROM bookings", "SELECT title FROM courses",
                "SELECT starts_at_utc FROM sessions")
            if dimension == "course":
                denied += ("SELECT category FROM courses",)
            for sql in common + denied:
                with self.subTest(dimension=dimension, sql=sql), patch.object(
                    grouped, "_compile_grouped", return_value=(sql, {})
                ):
                    self.failure("execution_failure", dimension)

    def test_dimension_admission_is_read_only_even_without_query_authorizer(self):
        declared, observed = kernel._declared_foreign_keys, []

        def probe(conn, table):
            if table == "sessions":
                observed.append(table)
                self.assertEqual(conn.execute("PRAGMA query_only").fetchone(), (1,))
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone(), (1,))
                self.assertEqual(conn.execute("PRAGMA trusted_schema").fetchone(), (0,))
                conn.execute("PRAGMA query_only=OFF")
                try:
                    with self.assertRaises(sqlite3.OperationalError) as raised:
                        conn.execute("UPDATE courses SET category='changed'")
                    self.assertEqual(raised.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
                finally:
                    conn.execute("PRAGMA query_only=ON")
            return declared(conn, table)

        before = self.db.read_bytes()
        with patch.object(kernel, "_declared_foreign_keys", side_effect=probe):
            self.assertEqual(self.pairs(self.run_group()), CATEGORY)
        self.assertEqual(observed, ["sessions"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_wal_writer_cannot_change_category_or_amount_between_same_snapshot_facts(self):
        with closing(sqlite3.connect(self.db, timeout=0)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
            budget = kernel._Budget(ExecutionLimits())
            req = request()
            with kernel._read_transaction(self.db, budget) as (conn, snapshot):
                scalar = self.scalar(conn, req.scope, snapshot, budget)
                with writer:
                    writer.execute("UPDATE booking_items SET unit_price_minor=unit_price_minor+1000 WHERE item_id='I01'")
                    writer.execute("UPDATE courses SET category='changed' WHERE course_id='K1'")
                self.assertFalse(writer.in_transaction)
                self.assertEqual(writer.total_changes, 2)
                with closing(sqlite3.connect(self.db, timeout=0)) as observer:
                    self.assertEqual(observer.execute("SELECT category FROM courses WHERE course_id='K1'").fetchone(),
                                     ("changed",))
                    self.assertEqual(observer.execute("SELECT unit_price_minor FROM booking_items WHERE item_id='I01'").fetchone(),
                                     (11000,))
                fact = self.grouped(conn, req, snapshot, budget)
                self.assertEqual((scalar.value, self.pairs(fact)), (158000, CATEGORY))
                self.assertEqual(sum(row.value for row in fact.rows), scalar.value)
                self.assertEqual(fact.snapshot_id, scalar.snapshot_id)
        fresh = self.run_group()
        self.assertEqual(self.pairs(fresh), [("arts", 90000), ("changed", 70000)])
        self.assertNotEqual(fresh.snapshot_id, fact.snapshot_id)
        self.assertEqual(execute_facts(self.db, req.scope).facts[0].value, 160000)

    def test_fresh_runtime_import_and_execution_cannot_use_evaluators_models_or_network(self):
        script = textwrap.dedent("""
            import json, os, socket, sys
            from pathlib import Path
            root = Path(sys.argv[1]).resolve()
            forbidden = ("tools", "tests", "evals", "grepbit.model", "grepbit.gateway")
            blocked_roots = [root / name for name in ("tools", "tests", "evals")]
            violations = []
            class Forbidden(RuntimeError): pass
            def banned(name):
                return any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
            class Guard:
                def find_spec(self, fullname, path=None, target=None):
                    if banned(fullname):
                        violations.append("import")
                        raise Forbidden("Forbidden runtime import")
            def audit(event, args):
                if event.startswith("socket."):
                    violations.append("network")
                    raise Forbidden("Network forbidden")
                if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(args[0])).resolve()
                    if (any(path.is_relative_to(base) for base in blocked_roots) or path.name == ".env"
                            or (path.is_relative_to(root / "grepbit")
                                and path.name.split(".")[0] in ("model", "gateway"))):
                        violations.append("file")
                        raise Forbidden("Evaluator/config read forbidden")
            sys.meta_path.insert(0, Guard())
            sys.addaudithook(audit)
            for operation in (lambda: __import__("tools"), lambda: (root / "tests" / "missing").read_bytes(),
                              lambda: socket.socket()):
                try: operation()
                except Forbidden: pass
                else: raise AssertionError("Isolation negative control failed")
            violations.clear()
            from grepbit import GroupedAmountRequest, execute_grouped_amount
            rows = []
            for dimension in ("category", "booking_day", "course"):
                data = dict(scope=json.loads(sys.argv[3]), dimension=dimension)
                if dimension == "course": data["top_k"] = 3
                fact = execute_grouped_amount(Path(sys.argv[2]), GroupedAmountRequest.from_mapping(data))
                rows.append([[row.key, row.value] for row in fact.rows])
            assert not violations and not any(banned(name) for name in sys.modules)
            print(json.dumps(rows))
        """)
        before = self.db.read_bytes()
        result = subprocess.run([sys.executable, "-B", "-c", script, str(fixture.ROOT),
                                 str(self.db), json.dumps(scope())],
                                cwd=fixture.ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), json.loads(json.dumps([CATEGORY, DAY, COURSE])))
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
