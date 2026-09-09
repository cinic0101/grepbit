"""Tier-0 schema model: what introspection alone can say about a datasource."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import Field, model_validator

from grepbit.domain.models import DomainModel

_IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_$]*$"


class ColumnKind(StrEnum):
    NUMERIC = "numeric"
    TEXT = "text"
    TIMESTAMP = "timestamp"
    DATE = "date"
    BOOLEAN = "boolean"
    OTHER = "other"


class SchemaColumn(DomainModel):
    name: str = Field(pattern=_IDENTIFIER)
    data_type: str = Field(min_length=1)
    kind: ColumnKind
    nullable: bool
    comment: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    distinct_estimate: int | None = Field(default=None, ge=0)
    # A PostgreSQL enum: kind TEXT, data_type is the type name, sample_values are
    # its labels read from the catalog (type metadata, never a row value).
    is_enum: bool = False


class SchemaTable(DomainModel):
    name: str = Field(pattern=_IDENTIFIER)
    columns: list[SchemaColumn] = Field(min_length=1)
    primary_key: list[str] = Field(default_factory=list)
    row_estimate: int | None = Field(default=None, ge=0)
    comment: str | None = None

    def column(self, name: str) -> SchemaColumn | None:
        return next((item for item in self.columns if item.name == name), None)


class ForeignKey(DomainModel):
    table: str = Field(pattern=_IDENTIFIER)
    column: str = Field(pattern=_IDENTIFIER)
    referenced_table: str = Field(pattern=_IDENTIFIER)
    referenced_column: str = Field(pattern=_IDENTIFIER)
    inferred: bool = False
    evidence: str | None = None

    @property
    def id(self) -> str:
        return (
            f"{self.table}.{self.column} -> "
            f"{self.referenced_table}.{self.referenced_column}"
        )


class SchemaModel(DomainModel):
    """Introspected structure of one datasource schema; no business semantics."""

    datasource_id: str = Field(min_length=1)
    schema_name: str = Field(pattern=_IDENTIFIER)
    business_timezone: str = Field(min_length=1)
    tables: list[SchemaTable] = Field(min_length=1)
    foreign_keys: list[ForeignKey] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_resolve(self) -> SchemaModel:
        names = [table.name for table in self.tables]
        if len(names) != len(set(names)):
            raise ValueError("schema_table_duplicate")
        for foreign_key in self.foreign_keys:
            source = self.table(foreign_key.table)
            target = self.table(foreign_key.referenced_table)
            if source is None or target is None:
                raise ValueError("schema_foreign_key_table_unknown")
            if source.column(foreign_key.column) is None or (
                target.column(foreign_key.referenced_column) is None
            ):
                raise ValueError("schema_foreign_key_column_unknown")
        return self

    def table(self, name: str) -> SchemaTable | None:
        return next((item for item in self.tables if item.name == name), None)

    def parent_links(self, table_name: str) -> list[ForeignKey]:
        """Foreign keys leaving ``table_name``: joining them cannot fan out."""

        return [item for item in self.foreign_keys if item.table == table_name]

    def parent_link(self, table_name: str, parent_name: str) -> ForeignKey | None:
        return next(
            (
                item
                for item in self.parent_links(table_name)
                if item.referenced_table == parent_name
            ),
            None,
        )

    def time_columns(self, table_name: str) -> list[SchemaColumn]:
        table = self.table(table_name)
        if table is None:
            return []
        return [
            column
            for column in table.columns
            if column.kind in {ColumnKind.TIMESTAMP, ColumnKind.DATE}
        ]

    def digest(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
