"""One bounded read-only SQLite path for reviewed scalar fact bindings."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Iterator
from uuid import uuid4

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from .catalog import Catalog, LEARNINGOPS, MetricBinding, PROFILE_ID, _column
from .contracts import ExecutionLimits, Fact, FactPack, FactRequest, KernelError, utc_text

# Required physical columns: name, declared type, NOT NULL, primary-key position.
_SCHEMA = {
    "centers": (
        ("center_id", "TEXT", 1, 1), ("code", "TEXT", 1, 0), ("name", "TEXT", 1, 0),
        ("region", "TEXT", 1, 0), ("business_timezone", "TEXT", 1, 0),
    ),
    "bookings": (
        ("booking_id", "TEXT", 1, 1), ("center_id", "TEXT", 1, 0),
        ("learner_id", "TEXT", 0, 0), ("created_at_utc", "TEXT", 1, 0),
        ("status", "TEXT", 1, 0), ("currency", "TEXT", 1, 0),
    ),
    "booking_items": (
        ("item_id", "TEXT", 1, 1), ("booking_id", "TEXT", 1, 0),
        ("session_id", "TEXT", 1, 0), ("center_id", "TEXT", 1, 0),
        ("seats", "INTEGER", 1, 0), ("unit_price_minor", "INTEGER", 1, 0),
        ("discount_minor", "INTEGER", 1, 0),
    ),
}
_FOREIGN_KEYS = {
    "centers": set(),
    "bookings": {
        ("centers", (("center_id", "center_id"),)),
        ("learners", (("learner_id", "learner_id"),)),
    },
    "booking_items": {
        ("bookings", (("booking_id", "booking_id"), ("center_id", "center_id"))),
        ("sessions", (("session_id", "session_id"), ("center_id", "center_id"))),
    },
}
_VALUE_CONSTRAINTS = {
    "centers": (),
    "bookings": (
        exp.In(this=exp.column("status"), expressions=[
            exp.Literal.string(value) for value in ("confirmed", "cancelled", "draft")
        ]),
        exp.column("currency").eq(exp.Literal.string("TWD")),
    ),
    "booking_items": (
        exp.GT(this=exp.column("seats"), expression=exp.Literal.number(0)),
        exp.GTE(this=exp.column("unit_price_minor"), expression=exp.Literal.number(0)),
        exp.GTE(this=exp.column("discount_minor"), expression=exp.Literal.number(0)),
        exp.LTE(this=exp.column("discount_minor"), expression=exp.Mul(
            this=exp.column("seats"), expression=exp.column("unit_price_minor"),
        )),
    ),
}
_GRAINS = {"bookings": "booking", "booking_items": "booking_line"}
_POPULATION = "Current confirmed bookings within the explicit creation-time scope."
_COLUMNS = {
    "b": {"booking_id", "learner_id"},
    "i": {"seats", "unit_price_minor", "discount_minor"},
}
_CHECKS = (
    "strict_request_and_scope", "reviewed_binding_ast", "strict_schema_and_primary_keys",
    "declared_and_actual_foreign_keys", "declared_check_constraints", "canonical_utc_second_encoding",
    "integer_line_amounts", "read_only_single_transaction", "scalar_result_shape_and_type",
    "execution_budget",
)
_LIMITATIONS = (
    "Checks cover this execution, not user intent or source truth.",
    "Current booking status is not historical status at the end of the period.",
    "Only canonical whole-second UTC TEXT and integer minor units are admitted.",
    "Business timezone is preserved context; explicit instants determine the interval.",
    "Snapshot identity is batch-local, not a persistent reproducible database version.",
    "Cooperative SQLite/Python budgets are not hard OS memory or filesystem I/O isolation.",
)


class _Budget:
    def __init__(self, limits: ExecutionLimits):
        self.limits = limits
        self.started = time.monotonic()
        self.callbacks = 0
        self.rows = 0
        self.reason: str | None = None

    def check(self) -> None:
        if time.monotonic() - self.started >= self.limits.timeout_seconds:
            self.reason = "Execution deadline exceeded."
        if self.reason:
            raise KernelError("budget_exceeded", self.reason)

    def progress(self) -> int:
        self.callbacks += 1
        if self.callbacks * 100 >= self.limits.max_vm_steps:
            self.reason = "SQLite VM step budget exhausted."
        if time.monotonic() - self.started >= self.limits.timeout_seconds:
            self.reason = "Execution deadline exceeded."
        return int(self.reason is not None)

    def source_row(self) -> None:
        self.rows += 1
        if self.rows > self.limits.max_source_rows:
            self.reason = "Source-validation row budget exhausted."
        self.check()


def _storage_bound(value: datetime) -> str:
    # With second-resolution source instants, ceil(start) and ceil(end) preserve
    # a half-open interval exactly; truncation or fractional TEXT comparison does not.
    value = value.astimezone(timezone.utc)
    try:
        if value.microsecond:
            value = value.replace(microsecond=0) + timedelta(seconds=1)
    except OverflowError as exc:
        raise KernelError("invalid_request", "Period exceeds the source timestamp range.") from exc
    return utc_text(value)


def _validate_binding(binding: MetricBinding) -> None:
    expression = binding.expression
    if binding.source not in _GRAINS or type(expression) not in (exp.Sum, exp.Count):
        raise KernelError("invalid_catalog", "Unsupported scalar binding.")
    allowed = {exp.Sum, exp.Count, exp.Distinct, exp.Mul, exp.Sub, exp.Column, exp.Identifier}
    nodes = list(expression.walk())
    if len(nodes) > 32 or any(type(node) not in allowed for node in nodes):
        raise KernelError("invalid_catalog", "Binding contains an unapproved expression.")
    if sum(isinstance(node, exp.AggFunc) for node in nodes) != 1:
        raise KernelError("invalid_catalog", "Bindings must contain exactly one scalar aggregate.")
    for column in expression.find_all(exp.Column):
        if column.table not in _COLUMNS or column.name not in _COLUMNS[column.table]:
            raise KernelError("invalid_catalog", "Binding references an unapproved column.")
        expected_alias = "b" if binding.source == "bookings" else "i"
        if column.db or column.catalog or column.table != expected_alias:
            raise KernelError("invalid_catalog", "Binding references an unapproved source.")
    if binding.source == "bookings":
        if (type(expression) is not exp.Count or type(expression.this) is not exp.Distinct
                or len(expression.this.expressions) != 1
                or type(expression.this.expressions[0]) is not exp.Column):
            raise KernelError("invalid_catalog", "Booking-grain bindings require a distinct key count.")
    elif type(expression) is not exp.Sum or expression.find(exp.Distinct):
        raise KernelError("invalid_catalog", "Line sums must preserve duplicates, not SUM(DISTINCT).")
    if binding.excluded_null_column is not None and (
        binding.source != "bookings" or binding.excluded_null_column != "learner_id"
        or expression.this.expressions[0].name != "learner_id"
    ):
        raise KernelError("invalid_catalog", "Unreviewed exclusion disclosure.")


def _table(name: str, alias: str) -> exp.Table:
    return exp.Table(this=exp.to_identifier(name, quoted=True),
                     alias=exp.TableAlias(this=exp.to_identifier(alias, quoted=True)))


def _scalar_query(binding: MetricBinding, request: FactRequest) -> tuple[exp.Select, dict[str, str]]:
    _validate_binding(binding)
    expressions = [
        binding.expression.copy().as_("value", quoted=True),
        exp.Count(this=exp.Star()).as_("population_rows", quoted=True),
    ]
    if binding.excluded_null_column:
        expressions.append(exp.Sub(
            this=exp.Count(this=exp.Star()),
            expression=exp.Count(this=_column(binding.excluded_null_column, "b")),
        ).as_("excluded_anonymous_rows", quoted=True))
    query = exp.select(*expressions)
    if binding.source == "bookings":
        query = query.from_(_table("bookings", "b"))
    else:
        query = query.from_(_table("booking_items", "i")).join(
            _table("bookings", "b"),
            on=exp.and_(
                _column("booking_id", "i").eq(_column("booking_id", "b")),
                _column("center_id", "i").eq(_column("center_id", "b")),
            ),
        )
    predicates = [
        _column("status", "b").eq(exp.Placeholder(this="status")),
        exp.GTE(this=_column("created_at_utc", "b"), expression=exp.Placeholder(this="start")),
        exp.LT(this=_column("created_at_utc", "b"), expression=exp.Placeholder(this="end")),
    ]
    parameters = {"status": "confirmed", "start": _storage_bound(request.start),
                  "end": _storage_bound(request.end)}
    if request.center_id is not None:
        predicates.append(_column("center_id", "b").eq(exp.Placeholder(this="center_id")))
        parameters["center_id"] = request.center_id
    return query.where(*predicates), parameters


def _compile(binding: MetricBinding, request: FactRequest) -> tuple[str, dict[str, str]]:
    query, parameters = _scalar_query(binding, request)
    return query.sql(dialect="sqlite"), parameters


def _declared_foreign_keys(conn: sqlite3.Connection, table: str) -> set[
    tuple[str, tuple[tuple[str, str], ...]]
]:
    grouped: dict[int, list[tuple]] = {}
    for row in conn.execute(f'PRAGMA main.foreign_key_list("{table}")'):
        grouped.setdefault(row[0], []).append(row)
    return {
        (rows[0][2], tuple((r[3], r[4]) for r in sorted(rows, key=lambda r: r[1])))
        for rows in grouped.values()
    }


def _validate_source(conn: sqlite3.Connection, budget: _Budget) -> str:
    tables = {row[1]: row for row in conn.execute("PRAGMA main.table_list")}
    identity = {}
    for table, expected in _SCHEMA.items():
        budget.check()
        if table not in tables or tables[table][2] != "table" or tables[table][5] != 1:
            raise KernelError("unsupported_source", "Required source must be a real STRICT table.")
        columns = conn.execute(f'PRAGMA main.table_xinfo("{table}")').fetchall()
        actual = tuple((row[1], row[2], row[3], row[5]) for row in columns)
        if actual != expected or any(row[4] is not None or row[6] != 0 for row in columns):
            raise KernelError("unsupported_source", "Source columns/types/keys differ from the reviewed profile.")
        ddl = conn.execute(
            "SELECT sql FROM main.sqlite_schema WHERE type='table' AND name=?", (table,),
        ).fetchone()[0]
        if len(ddl.encode("utf-8")) > 16384:
            raise KernelError("unsupported_source", "Source DDL exceeds the admitted size.")
        if re.search(r"\bCOLLATE\b", ddl, re.IGNORECASE):
            raise KernelError("unsupported_source", "Explicit collations are outside the binary-text profile.")
        try:
            definition = sqlglot.parse_one(ddl, read="sqlite")
        except ParseError as exc:
            raise KernelError("unsupported_source", "Source DDL is outside the reviewed profile.") from exc
        actual_checks = {
            node.this.sql(dialect="sqlite", identify=True, normalize=True)
            for node in definition.find_all(exp.CheckColumnConstraint)
        }
        expected_checks = {
            node.sql(dialect="sqlite", identify=True, normalize=True)
            for node in _VALUE_CONSTRAINTS[table]
        }
        if not isinstance(definition, exp.Create) or actual_checks != expected_checks:
            raise KernelError("unsupported_source", "Reviewed CHECK constraint definitions have changed.")
        budget.check()
        if _declared_foreign_keys(conn, table) != _FOREIGN_KEYS[table]:
            raise KernelError("unsupported_source", "Required relationship declarations have changed.")
        if conn.execute(f'PRAGMA main.foreign_key_check("{table}")').fetchone() is not None:
            raise KernelError("unsupported_source", "Source violates reviewed relationship constraints.")
        identity[table] = ddl

    for row in conn.execute("SELECT center_id FROM main.centers"):
        budget.source_row()
        if not 1 <= len(row[0]) <= 64:
            raise KernelError("unsupported_source", "Center IDs exceed the admitted encoding.")
    for value, status, currency in conn.execute(
        "SELECT created_at_utc,status,currency FROM main.bookings"
    ):
        budget.source_row()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise KernelError("unsupported_source", "Noncanonical booking timestamp.") from exc
        if len(value) != 20 or not value.endswith("Z") or utc_text(parsed) != value:
            raise KernelError("unsupported_source", "Source timestamps must be canonical whole-second UTC TEXT.")
        if status not in ("confirmed", "cancelled", "draft") or currency != "TWD":
            raise KernelError("unsupported_source", "Unreviewed booking status or currency.")
    for seats, price, discount in conn.execute(
        "SELECT seats,unit_price_minor,discount_minor FROM main.booking_items"
    ):
        budget.source_row()
        if (seats <= 0 or price < 0 or discount < 0 or discount > seats * price
                or seats * price > 2**63 - 1):
            raise KernelError("unsupported_source", "Line values violate exact integer-money assumptions.")
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _authorize(action: int, table: str | None, column: str | None,
               database: str | None, trigger: str | None) -> int:
    if trigger is not None:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database == "main" and table in _SCHEMA:
        if column == "" or column in {c[0] for c in _SCHEMA[table]}:
            return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and column in ("sum", "count"):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


_CompiledScalar = tuple[str, MetricBinding, str, dict[str, str]]


def _compile_scope(request: FactRequest, catalog: Catalog) -> list[_CompiledScalar]:
    unknown = set(request.metrics) - catalog.metrics.keys()
    if unknown:
        raise KernelError("unknown_metric", "The request contains a metric not admitted by this catalog.")
    return [(metric, catalog.metrics[metric], *_compile(catalog.metrics[metric], request))
            for metric in request.metrics]


@contextmanager
def _read_transaction(database: Path, budget: _Budget) -> Iterator[
    tuple[sqlite3.Connection, dict[str, str]]
]:
    budget.check()
    if sqlite3.sqlite_version_info < (3, 37):
        raise KernelError("unsupported_source", "SQLite 3.37+ is required.")
    if not isinstance(database, Path):
        raise KernelError("invalid_request", "Database must be a local filesystem Path, not a connection or SQL.")
    conn = None
    snapshot = {
        "id": str(uuid4()), "scope": "single_read_transaction", "source_file": database.name,
        "started_at_utc": utc_text(datetime.now(timezone.utc)), "source_profile": PROFILE_ID,
        "identity_kind": "ephemeral_batch_not_persistent_database_version",
    }
    try:
        conn = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True,
                               timeout=0, isolation_level=None)
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_048_576)
        conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 16384)
        conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 16)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.set_progress_handler(budget.progress, 100)
        conn.execute("BEGIN")
        snapshot["schema_sha256"] = _validate_source(conn, budget)
        conn.set_authorizer(_authorize)
        yield conn, snapshot
        budget.check()
    except sqlite3.Error as exc:
        if budget.reason:
            raise KernelError("budget_exceeded", budget.reason) from exc
        raise KernelError("execution_failure", "SQLite could not complete the required fact batch.") from exc
    except OSError as exc:
        raise KernelError("execution_failure", "The local database could not be accessed.") from exc
    finally:
        if conn is not None:
            conn.set_progress_handler(None, 0)
            conn.set_authorizer(None)
            conn.close()
    budget.check()
    snapshot["completed_at_utc"] = utc_text(datetime.now(timezone.utc))


def _check_center(conn: sqlite3.Connection, request: FactRequest) -> None:
    if request.center_id is not None and conn.execute(
        "SELECT 1 FROM main.centers WHERE center_id=?", (request.center_id,),
    ).fetchone() is None:
        raise KernelError("unknown_entity", "Center ID is not present in the reviewed source.")


def _execute_scope(conn: sqlite3.Connection, request: FactRequest,
                   compiled: list[_CompiledScalar], catalog: Catalog,
                   snapshot_id: str, budget: _Budget) -> tuple[Fact, ...]:
    _check_center(conn, request)
    catalog_hash = catalog.digest()
    facts = []
    for metric, binding, sql, parameters in compiled:
        budget.check()
        rows = conn.execute(sql, parameters).fetchmany(2)
        size = 3 if binding.excluded_null_column else 2
        if (len(rows) != 1 or len(rows[0]) != size
                or any(value is not None and type(value) is not int for value in rows[0])):
            raise KernelError("execution_failure", "Expected one exact integer-or-null scalar aggregate row.")
        value, count = rows[0][:2]
        if type(count) is not int or count < 0 or (count > 0 and value is None):
            raise KernelError("execution_failure", "Invalid scalar population evidence.")
        excluded = rows[0][2] if binding.excluded_null_column else None
        facts.append(Fact(
            metric, catalog.version, catalog_hash, value, binding.unit, _GRAINS[binding.source],
            _POPULATION,
            "bookings.created_at_utc", utc_text(request.start), utc_text(request.end),
            request.timezone, {"center_id": request.center_id} if request.center_id is not None else {},
            count, count == 0, excluded, binding.disclosures, sql, parameters, snapshot_id, _CHECKS,
        ))
    budget.check()
    return tuple(facts)


def _runtime_evidence() -> dict[str, str]:
    return {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "sqlglot": sqlglot.__version__}


def _execution_evidence(budget: _Budget) -> dict[str, int | float]:
    return {**asdict(budget.limits), "progress_callbacks": budget.callbacks,
            "vm_step_check_interval": 100, "source_rows_validated": budget.rows,
            "elapsed_seconds": round(time.monotonic() - budget.started, 6)}


def execute_facts(database: Path, request: FactRequest, *, catalog: Catalog = LEARNINGOPS,
                  limits: ExecutionLimits = ExecutionLimits()) -> FactPack:
    """Execute an all-required scalar batch; failures raise KernelError, never partial packs."""
    if not isinstance(request, FactRequest):
        raise KernelError("invalid_request", "Use FactRequest; SQL and unvalidated mappings are not executable.")
    if not isinstance(limits, ExecutionLimits) or not isinstance(catalog, Catalog):
        raise KernelError("invalid_request", "Use typed trusted catalog and execution limits.")
    budget = _Budget(limits)
    compiled = _compile_scope(request, catalog)
    with _read_transaction(database, budget) as (conn, snapshot):
        facts = _execute_scope(conn, request, compiled, catalog, snapshot["id"], budget)
    return FactPack(request, facts, snapshot, _runtime_evidence(), _execution_evidence(budget),
                    _LIMITATIONS)
