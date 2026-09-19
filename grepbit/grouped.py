"""One observed grouped-amount primitive with reviewed dimension bindings."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Callable, Literal, Mapping
from uuid import uuid4

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from . import kernel
from .catalog import LEARNINGOPS, _column
from .contracts import ExecutionLimits, FactRequest, KernelError, utc_text

_MAX_GROUP_ROWS = 64
_MAX_CATEGORY_BYTES = 256
_MAX_COURSE_BYTES = 64
_TAIPEI_OFFSET = timezone(timedelta(hours=8))
_DIMENSION_PROFILE = "learningops-grouped-amount-v1"
_SESSION_COLUMNS = (
    ("session_id", "TEXT", 1, 1), ("course_id", "TEXT", 1, 0), ("center_id", "TEXT", 1, 0),
)
_COURSE_COLUMNS = (("course_id", "TEXT", 1, 1), ("category", "TEXT", 0, 0))
_SESSION_FKS = {
    ("courses", (("course_id", "course_id"),)),
    ("centers", (("center_id", "center_id"),)),
}
_ORDERING = {
    "category": ("key_asc_nulls_first",),
    "booking_day": ("key_asc",),
    "course": ("value_desc", "key_asc"),
}


@dataclass(frozen=True)
class GroupedAmountRequest:
    scope: FactRequest
    dimension: str
    top_k: int | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.scope, FactRequest)
                or self.scope.metrics != ("confirmed_booked_amount",)
                or self.scope.timezone != "Asia/Taipei"):
            raise KernelError("invalid_request", "Grouped amount requires booked amount in Asia/Taipei.")
        if not isinstance(self.dimension, str) or self.dimension not in _ORDERING:
            raise KernelError("invalid_request", "Choose one reviewed grouped-amount dimension.")
        if self.dimension == "course":
            if type(self.top_k) is not int or not 1 <= self.top_k <= 3:
                raise KernelError("invalid_request", "Course grouping requires integer top_k from 1 to 3.")
        elif self.top_k is not None:
            raise KernelError("invalid_request", "Category and booking day require all observed groups.")
        try:
            start = self.scope.start.astimezone(_TAIPEI_OFFSET)
            end = self.scope.end.astimezone(_TAIPEI_OFFSET)
            complete_month = (
                (start.day, start.hour, start.minute, start.second, start.microsecond) == (1, 0, 0, 0, 0)
                and end == start + timedelta(days=monthrange(start.year, start.month)[1])
            )
        except (ValueError, OverflowError) as exc:
            raise KernelError("invalid_request", "Grouped month is outside the supported calendar.") from exc
        if not complete_month:
            raise KernelError("invalid_request", "Supply one explicit full month in the reviewed UTC+08:00 profile.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> GroupedAmountRequest:
        if (not isinstance(data, Mapping) or not {"scope", "dimension"} <= data.keys()
                or not data.keys() <= {"scope", "dimension", "top_k"}):
            raise KernelError("invalid_request", "Supply scope, dimension and only the admitted course top_k.")
        scope, dimension, top_k = data["scope"], data["dimension"], data.get("top_k")
        if (not isinstance(scope, Mapping) or not isinstance(dimension, str)
                or dimension not in ("category", "booking_day", "course")):
            raise KernelError("invalid_request", "Use an explicit scope and one reviewed dimension.")
        if top_k is not None and type(top_k) is not int:
            raise KernelError("invalid_request", "top_k must be an integer, not a formula or expression.")
        return cls(FactRequest.from_mapping(scope), dimension, top_k)


@dataclass(frozen=True)
class GroupedAmountRow:
    key: str | None
    value: int


@dataclass(frozen=True)
class GroupedAmountFact:
    metric_id: str
    catalog_id: str
    catalog_sha256: str
    dimension: str
    rows: tuple[GroupedAmountRow, ...]
    unit: str
    grain: str
    population: str
    time_basis: str
    start_utc: str
    end_utc: str
    business_timezone: str
    filters: dict[str, str]
    snapshot_id: str
    checks: tuple[str, ...]
    coverage: Literal["all_observed_groups", "top_k"]
    top_k: int | None
    ordering: tuple[str, ...]
    empty_population: bool
    sql: str
    parameters: dict[str, str | int]
    dimension_source_sha256: str | None
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    dimension_profile_id: str = field(default=_DIMENSION_PROFILE, init=False)
    fact_id: str = field(default_factory=lambda: str(uuid4()), kw_only=True)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _compile_grouped(request: GroupedAmountRequest) -> tuple[str, dict[str, str | int]]:
    query, scalar_parameters = kernel._scalar_query(
        LEARNINGOPS.metrics["confirmed_booked_amount"], request.scope,
    )
    key: exp.Expression
    if request.dimension == "booking_day":
        key = exp.Anonymous(this="date", expressions=[
            _column("created_at_utc", "b"), exp.Literal.string("+8 hours"),
        ])
    else:
        query = query.join(kernel._table("sessions", "s"), on=exp.and_(
            _column("session_id", "i").eq(_column("session_id", "s")),
            _column("center_id", "i").eq(_column("center_id", "s")),
        )).join(kernel._table("courses", "c"),
                on=_column("course_id", "s").eq(_column("course_id", "c")))
        key = _column("category" if request.dimension == "category" else "course_id", "c")
    query = query.select(key.copy().as_("group_key", quoted=True), *query.expressions,
                         append=False).group_by(key.copy())
    ordering = [exp.Ordered(this=key.copy(), desc=False, nulls_first=True)]
    if request.dimension == "course":
        ordering.insert(0, exp.Ordered(this=exp.column("value", quoted=True),
                                       desc=True, nulls_first=False))
    parameters: dict[str, str | int] = dict(scalar_parameters)
    parameters["row_limit"] = request.top_k if request.top_k is not None else _MAX_GROUP_ROWS + 1
    query = query.order_by(*ordering).limit(exp.Placeholder(this="row_limit"))
    return query.sql(dialect="sqlite"), parameters


def _check_key(key: object, dimension: str) -> None:
    if key is None and dimension == "category":
        return
    if not isinstance(key, str) or (dimension == "course" and not key):
        raise KernelError("unsupported_source", "Grouped key has an unreviewed type or nullability.")
    limit = _MAX_CATEGORY_BYTES if dimension == "category" else _MAX_COURSE_BYTES
    if dimension == "booking_day":
        limit = 10
    try:
        size = len(key.encode("utf-8"))
    except UnicodeError as exc:
        raise KernelError("unsupported_source", "Grouped keys must be valid UTF-8 text.") from exc
    if size > limit:
        raise KernelError("unsupported_source", "Grouped key exceeds the reviewed UTF-8 byte bound.")
    if dimension == "booking_day":
        try:
            if date.fromisoformat(key).isoformat() != key:
                raise ValueError
        except ValueError as exc:
            raise KernelError("execution_failure", "Expected a canonical booking date.") from exc


def _validate_dimension_source(conn: sqlite3.Connection, dimension: str,
                               budget: kernel._Budget) -> str | None:
    if dimension == "booking_day":
        return None
    conn.set_authorizer(None)
    try:
        tables = {row[1]: row for row in conn.execute("PRAGMA main.table_list")}
        identity = {}
        for table, required in (
            ("courses", _COURSE_COLUMNS if dimension == "category" else _COURSE_COLUMNS[:1]),
            ("sessions", _SESSION_COLUMNS),
        ):
            budget.check()
            if table not in tables or tables[table][2] != "table" or tables[table][5] != 1:
                raise KernelError("unsupported_source", "Dimension sources must be real STRICT tables.")
            columns = conn.execute(f'PRAGMA main.table_xinfo("{table}")').fetchall()
            by_name = {row[1]: row for row in columns}
            for name, kind, not_null, primary in required:
                row = by_name.get(name)
                if row is None or (row[2], row[3], row[5], row[6]) != (kind, not_null, primary, 0):
                    raise KernelError("unsupported_source", "Consumed dimension columns differ from the reviewed profile.")
            if [(row[1], row[5]) for row in columns if row[5]] != [(required[0][0], 1)]:
                raise KernelError("unsupported_source", "Dimension keys must uniquely identify one member.")
            ddl = conn.execute(
                "SELECT sql FROM main.sqlite_schema WHERE type='table' AND name=?", (table,),
            ).fetchone()[0]
            if len(ddl.encode("utf-8")) > 16384:
                raise KernelError("unsupported_source", "Dimension source DDL exceeds the admitted size.")
            try:
                definition = sqlglot.parse_one(ddl, read="sqlite")
            except ParseError as exc:
                raise KernelError("unsupported_source", "Unreviewed dimension source DDL.") from exc
            names = {column[0] for column in required}
            if (not isinstance(definition, exp.Create)
                    or any(column.name in names and column.find(exp.CollateColumnConstraint)
                           for column in definition.find_all(exp.ColumnDef))):
                raise KernelError("unsupported_source", "Consumed dimension columns require default binary collation.")
            identity[table] = ddl
        if kernel._declared_foreign_keys(conn, "sessions") != _SESSION_FKS:
            raise KernelError("unsupported_source", "Session relationship declarations differ from the reviewed profile.")
        if conn.execute('PRAGMA main.foreign_key_check("sessions")').fetchone() is not None:
            raise KernelError("unsupported_source", "Dimension sources violate reviewed relationship constraints.")
        course_columns = "course_id,category" if dimension == "category" else "course_id"
        for row in conn.execute(f"SELECT {course_columns} FROM main.courses"):
            budget.source_row()
            _check_key(row[0], "course")
            if dimension == "category":
                _check_key(row[1], "category")
        for row in conn.execute("SELECT session_id,course_id,center_id FROM main.sessions"):
            budget.source_row()
            if any(not isinstance(value, str) for value in row):
                raise KernelError("unsupported_source", "Dimension relationship keys must be text.")
            _check_key(row[1], "course")
        budget.check()
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    finally:
        conn.set_authorizer(kernel._authorize)


def _group_authorizer(dimension: str) -> Callable[
    [int, str | None, str | None, str | None, str | None], int
]:
    def authorize(action: int, table: str | None, column: str | None,
                  database: str | None, trigger: str | None) -> int:
        if kernel._authorize(action, table, column, database, trigger) == sqlite3.SQLITE_OK:
            return sqlite3.SQLITE_OK
        if trigger is not None:
            return sqlite3.SQLITE_DENY
        if dimension == "booking_day":
            if action == sqlite3.SQLITE_FUNCTION and column == "date":
                return sqlite3.SQLITE_OK
        elif dimension in ("category", "course") and action == sqlite3.SQLITE_READ and database == "main":
            columns = {"sessions": {"session_id", "course_id", "center_id"},
                       "courses": {"course_id", "category"} if dimension == "category" else {"course_id"}}
            if table is not None and table in columns and (column == "" or column in columns[table]):
                return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    return authorize


def _execute_grouped(conn: sqlite3.Connection, request: GroupedAmountRequest,
                     compiled: tuple[str, dict[str, str | int]], snapshot: dict[str, str],
                     budget: kernel._Budget) -> GroupedAmountFact:
    kernel._check_center(conn, request.scope)
    extension_hash = _validate_dimension_source(conn, request.dimension, budget)
    sql, parameters = compiled
    conn.set_authorizer(_group_authorizer(request.dimension))
    try:
        budget.check()
        raw_rows = conn.execute(sql, parameters).fetchmany(_MAX_GROUP_ROWS + 1)
        cap = request.top_k if request.top_k is not None else _MAX_GROUP_ROWS
        if len(raw_rows) > cap:
            raise KernelError("output_limit_exceeded", "Grouped output exceeds its declared row bound.")
        rows = []
        for row in raw_rows:
            budget.check()
            if (len(row) != 3 or type(row[1]) is not int or not 0 <= row[1] < 2**63
                    or type(row[2]) is not int or row[2] <= 0):
                raise KernelError("execution_failure", "Expected exact grouped integer amounts and nonempty populations.")
            _check_key(row[0], request.dimension)
            rows.append(GroupedAmountRow(row[0], row[1]))
    finally:
        conn.set_authorizer(kernel._authorize)
    budget.check()
    scope = request.scope
    checks = tuple(check for check in kernel._CHECKS if check != "scalar_result_shape_and_type") + (
        "reviewed_dimension_binding", "grouped_integer_shape_and_key_bounds",
        "declared_group_coverage_and_row_bound",
    )
    if extension_hash is not None:
        checks += ("dimension_source_keys_and_relationships",)
    return GroupedAmountFact(
        "confirmed_booked_amount", LEARNINGOPS.version, LEARNINGOPS.digest(), request.dimension,
        tuple(rows), "TWD_minor", "booking_line",
        "Current confirmed bookings within the explicit creation-time scope.",
        "bookings.created_at_utc", utc_text(scope.start), utc_text(scope.end), scope.timezone,
        {"center_id": scope.center_id} if scope.center_id is not None else {},
        snapshot["id"], checks, "top_k" if request.dimension == "course" else "all_observed_groups",
        request.top_k, _ORDERING[request.dimension], not rows, sql, parameters, extension_hash,
        snapshot, kernel._runtime_evidence(), kernel._execution_evidence(budget),
        kernel._LIMITATIONS + (
            "Observed groups only; absent members are not zero-filled.",
            "Grouped calendar scopes and booking-day keys use fixed UTC+08:00, not historical IANA/DST rules.",
            "Course top-k is subset coverage, not a whole-population denominator.",
        ),
    )


def execute_grouped_amount(database: Path, request: GroupedAmountRequest, *,
                           limits: ExecutionLimits = ExecutionLimits()) -> GroupedAmountFact:
    """Execute one checked grouped amount fact; any failure raises KernelError."""
    if not isinstance(request, GroupedAmountRequest) or not isinstance(limits, ExecutionLimits):
        raise KernelError("invalid_request", "Use a typed GroupedAmountRequest and trusted ExecutionLimits.")
    budget = kernel._Budget(limits)
    compiled = _compile_grouped(request)
    with kernel._read_transaction(database, budget) as (conn, snapshot):
        fact = _execute_grouped(conn, request, compiled, snapshot, budget)
    return replace(fact, execution=kernel._execution_evidence(budget))
