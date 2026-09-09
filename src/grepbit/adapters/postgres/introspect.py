"""Deterministic PostgreSQL introspection into a tier-0 SchemaModel."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from grepbit.domain.schema_model import (
    ColumnKind,
    ForeignKey,
    SchemaColumn,
    SchemaModel,
    SchemaTable,
)

INTROSPECTOR_REVISION = "postgres-introspect-v1"
INFERENCE_REVISION = "fk-infer-name-containment-v1"
_NUMERIC_TYPES = {
    "smallint",
    "integer",
    "bigint",
    "numeric",
    "real",
    "double precision",
    "money",
}
_TEXT_TYPES = {"text", "character varying", "character", "uuid"}
_TIMESTAMP_TYPES = {"timestamp with time zone", "timestamp without time zone"}


def column_kind(data_type: str) -> ColumnKind:
    if data_type in _NUMERIC_TYPES:
        return ColumnKind.NUMERIC
    if data_type in _TEXT_TYPES:
        return ColumnKind.TEXT
    if data_type in _TIMESTAMP_TYPES:
        return ColumnKind.TIMESTAMP
    if data_type == "date":
        return ColumnKind.DATE
    if data_type == "boolean":
        return ColumnKind.BOOLEAN
    return ColumnKind.OTHER


def introspect_schema(
    connection_factory: Callable[[], AbstractContextManager[Any]],
    *,
    datasource_id: str,
    schema_name: str = "public",
    business_timezone: str = "Asia/Taipei",
    enum_distinct_limit: int = 20,
) -> SchemaModel:
    """Read structure and low-cardinality text values with the runtime role."""

    with connection_factory() as connection:
        rows = connection.execute(
            """
            SELECT c.table_name, c.column_name, c.data_type,
                   c.is_nullable = 'YES', c.ordinal_position,
                   col_description(
                       format('%%I.%%I', c.table_schema, c.table_name)::regclass,
                       c.ordinal_position
                   )
            FROM information_schema.columns AS c
            JOIN information_schema.tables AS t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = %s AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
            """,
            (schema_name,),
        ).fetchall()
        table_comments = dict(
            connection.execute(
                """
                SELECT cl.relname, obj_description(cl.oid, 'pg_class')
                FROM pg_catalog.pg_class AS cl
                JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cl.relnamespace
                WHERE ns.nspname = %s AND cl.relkind = 'r'
                """,
                (schema_name,),
            ).fetchall()
        )
        row_estimates = dict(
            connection.execute(
                """
                SELECT cl.relname, GREATEST(cl.reltuples, 0)::bigint
                FROM pg_catalog.pg_class AS cl
                JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cl.relnamespace
                WHERE ns.nspname = %s AND cl.relkind = 'r'
                """,
                (schema_name,),
            ).fetchall()
        )
        # information_schema constraint views hide constraints from roles that
        # only hold SELECT; pg_catalog is visible to the read-only runtime role.
        primary_keys: dict[str, list[str]] = {}
        for table_name, column_name in connection.execute(
            """
            SELECT cl.relname, att.attname
            FROM pg_catalog.pg_constraint AS con
            JOIN pg_catalog.pg_class AS cl ON cl.oid = con.conrelid
            JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cl.relnamespace
            JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
            JOIN pg_catalog.pg_attribute AS att
              ON att.attrelid = cl.oid AND att.attnum = k.attnum
            WHERE ns.nspname = %s AND con.contype = 'p'
            ORDER BY cl.relname, k.ord
            """,
            (schema_name,),
        ).fetchall():
            primary_keys.setdefault(table_name, []).append(column_name)
        foreign_keys = [
            ForeignKey(
                table=table_name,
                column=column_name,
                referenced_table=referenced_table,
                referenced_column=referenced_column,
            )
            for table_name, column_name, referenced_table, referenced_column in (
                connection.execute(
                    """
                    SELECT cl.relname, att.attname, rcl.relname, ratt.attname
                    FROM pg_catalog.pg_constraint AS con
                    JOIN pg_catalog.pg_class AS cl ON cl.oid = con.conrelid
                    JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cl.relnamespace
                    JOIN pg_catalog.pg_class AS rcl ON rcl.oid = con.confrelid
                    JOIN LATERAL unnest(con.conkey, con.confkey)
                         WITH ORDINALITY AS k(attnum, rattnum, ord) ON TRUE
                    JOIN pg_catalog.pg_attribute AS att
                      ON att.attrelid = cl.oid AND att.attnum = k.attnum
                    JOIN pg_catalog.pg_attribute AS ratt
                      ON ratt.attrelid = rcl.oid AND ratt.attnum = k.rattnum
                    WHERE ns.nspname = %s AND con.contype = 'f'
                    ORDER BY cl.relname, att.attname
                    """,
                    (schema_name,),
                ).fetchall()
            )
        ]
        key_columns = {
            (table_name, column)
            for table_name, columns in primary_keys.items()
            for column in columns
        } | {(fk.table, fk.column) for fk in foreign_keys}
        columns_by_table: dict[str, list[SchemaColumn]] = {}
        for table_name, column_name, data_type, nullable, _, comment in rows:
            kind = column_kind(data_type)
            samples: list[str] = []
            distinct: int | None = None
            if kind is ColumnKind.TEXT and (table_name, column_name) not in key_columns:
                samples, distinct = _sample_text_values(
                    connection,
                    schema_name,
                    table_name,
                    column_name,
                    enum_distinct_limit,
                )
            columns_by_table.setdefault(table_name, []).append(
                SchemaColumn(
                    name=column_name,
                    data_type=data_type,
                    kind=kind,
                    nullable=bool(nullable),
                    comment=comment,
                    sample_values=samples,
                    distinct_estimate=distinct,
                )
            )
    tables = [
        SchemaTable(
            name=name,
            columns=columns,
            primary_key=primary_keys.get(name, []),
            row_estimate=row_estimates.get(name),
            comment=table_comments.get(name),
        )
        for name, columns in columns_by_table.items()
    ]
    return SchemaModel(
        datasource_id=datasource_id,
        schema_name=schema_name,
        business_timezone=business_timezone,
        tables=tables,
        foreign_keys=foreign_keys,
    )


def _sample_text_values(
    connection: Any, schema_name: str, table: str, column: str, limit: int
) -> tuple[list[str], int | None]:
    """Return distinct values only for low-cardinality columns; never long tails."""

    from psycopg import sql

    query = sql.SQL(
        "SELECT {column} FROM (SELECT DISTINCT {column} FROM {table} "
        "WHERE {column} IS NOT NULL LIMIT {limit}) AS s ORDER BY 1"
    ).format(
        column=sql.Identifier(column),
        table=sql.Identifier(schema_name, table),
        limit=sql.Literal(limit + 1),
    )
    values = [str(row[0]) for row in connection.execute(query).fetchall()]
    if len(values) > limit:
        return [], None
    return values, len(values)


Containment = Callable[[Any, str, str, str, str, str, int], tuple[int, int]]


def infer_foreign_keys(
    connection_factory: Callable[[], AbstractContextManager[Any]],
    schema: SchemaModel,
    *,
    sample_limit: int = 2000,
    containment: Containment | None = None,
) -> SchemaModel:
    """Add undeclared joins that both a name rule and the data support.

    A column qualifies as a candidate child of a single-column primary key when
    it is not itself a key, has the same kind, and is named either exactly like
    the parent key, ``<parent>_<key>``, or ``*_<key>`` for a key more specific
    than ``id``. It is confirmed only when every distinct sampled value exists
    in the parent (zero orphans). A column with several confirmed parents is
    left alone. Inferred keys carry ``inferred=True`` and their evidence so the
    compiler can state the join as an assumption rather than a fact.
    """

    check = containment or _containment
    declared = {(fk.table, fk.column) for fk in schema.foreign_keys}
    parents = [t for t in schema.tables if len(t.primary_key) == 1]
    inferred: list[ForeignKey] = []
    with connection_factory() as connection:
        for table in schema.tables:
            for column in table.columns:
                if (table.name, column.name) in declared:
                    continue
                if column.name in table.primary_key or column.kind not in {
                    ColumnKind.TEXT,
                    ColumnKind.NUMERIC,
                }:
                    continue
                confirmed: list[tuple[str, str, int]] = []
                for parent in parents:
                    key = parent.primary_key[0]
                    key_column = parent.column(key)
                    if parent.name == table.name or key_column is None:
                        continue
                    if key_column.kind is not column.kind:
                        continue
                    if not _name_matches(column.name, parent.name, key):
                        continue
                    total, orphans = check(
                        connection,
                        schema.schema_name,
                        table.name,
                        column.name,
                        parent.name,
                        key,
                        sample_limit,
                    )
                    if total > 0 and orphans == 0:
                        confirmed.append((parent.name, key, total))
                if len(confirmed) == 1:
                    parent_name, key, total = confirmed[0]
                    inferred.append(
                        ForeignKey(
                            table=table.name,
                            column=column.name,
                            referenced_table=parent_name,
                            referenced_column=key,
                            inferred=True,
                            evidence=(
                                f"column name matches {parent_name}.{key} and all "
                                f"{total} sampled distinct values exist there"
                            ),
                        )
                    )
    return schema.model_copy(update={"foreign_keys": [*schema.foreign_keys, *inferred]})


def _name_matches(column: str, parent: str, key: str) -> bool:
    if column == key or column == f"{parent}_{key}":
        return True
    return key != "id" and column.endswith(f"_{key}")


def _containment(
    connection: Any,
    schema_name: str,
    table: str,
    column: str,
    parent: str,
    key: str,
    limit: int,
) -> tuple[int, int]:
    from psycopg import sql

    query = sql.SQL(
        "SELECT count(*), count(*) FILTER (WHERE p.{key} IS NULL) "
        "FROM (SELECT DISTINCT {column} AS v FROM {table} "
        "WHERE {column} IS NOT NULL LIMIT {limit}) AS s "
        "LEFT JOIN {parent} AS p ON p.{key} = s.v"
    ).format(
        key=sql.Identifier(key),
        column=sql.Identifier(column),
        table=sql.Identifier(schema_name, table),
        parent=sql.Identifier(schema_name, parent),
        limit=sql.Literal(limit),
    )
    total, orphans = connection.execute(query).fetchone()
    return int(total), int(orphans)
