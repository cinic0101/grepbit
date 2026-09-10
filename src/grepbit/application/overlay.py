"""Overlay validation against the schema and deterministic absent-concept match."""

from __future__ import annotations

from grepbit.application.text import phrase_in
from grepbit.domain.grounding import normalize_question
from grepbit.domain.overlay import AbsentConcept, Segment, SemanticOverlay
from grepbit.domain.schema_model import ColumnKind, SchemaModel


def overlay_problems(overlay: SemanticOverlay, schema: SchemaModel) -> list[str]:
    """Every identifier an overlay names must exist in the introspected schema."""

    problems: list[str] = []

    def check(ref_table: str, ref_column: str | None, where: str) -> None:
        table = schema.table(ref_table)
        if table is None:
            problems.append(f"{where}: unknown table {ref_table}")
        elif ref_column is not None and table.column(ref_column) is None:
            problems.append(f"{where}: unknown column {ref_table}.{ref_column}")

    for metric in overlay.metrics:
        where = f"metrics.{metric.id}"
        check(metric.base_table, None, where)
        if metric.column is not None:
            check(metric.column.table, metric.column.column, where)
        for item in metric.filters:
            check(item.column.table, item.column.column, where)
        if metric.time_column is not None:
            check(metric.time_column.table, metric.time_column.column, where)
    for alias in overlay.column_aliases:
        check(alias.column.table, alias.column.column, "column_aliases")
    for table_alias in overlay.table_aliases:
        check(table_alias.table, None, "table_aliases")
    for value_alias in overlay.value_aliases:
        check(value_alias.column.table, value_alias.column.column, "value_aliases")
    for default in overlay.time_defaults:
        check(default.table, None, "time_defaults")
        check(default.column.table, default.column.column, "time_defaults")
        table = schema.table(default.column.table)
        column = table.column(default.column.column) if table is not None else None
        if column is not None and column.kind not in {
            ColumnKind.TIMESTAMP,
            ColumnKind.DATE,
        }:
            problems.append(
                f"time_defaults: {default.column.id} is not a timestamp or date column"
            )
    for segment in overlay.segments:
        where = f"segments.{segment.id}"
        check(segment.table, None, where)
        check(segment.filter.column.table, segment.filter.column.column, where)
    for policy in overlay.column_policies:
        check(policy.column.table, policy.column.column, "column_policies")
    for table_policy in overlay.table_policies:
        check(table_policy.table, None, "table_policies")
    for table in schema.tables:
        if not overlay.table_visible(table.name):
            continue
        visible = [
            c for c in table.columns if overlay.visible_column(table.name, c.name)
        ]
        if not visible:
            problems.append(f"table_policies: {table.name} has no visible column left")
    return problems


def excluded_segments(question: str, overlay: SemanticOverlay) -> list[Segment]:
    """Default-excluded segments the question does not name (script-aware match)."""

    normalized = normalize_question(question)
    return [
        segment
        for segment in overlay.segments
        if segment.default_exclude
        and not any(
            phrase_in(normalized, normalize_question(name)) for name in segment.names
        )
    ]


def match_absent_concept(
    question: str, overlay: SemanticOverlay
) -> AbsentConcept | None:
    normalized = normalize_question(question)
    for concept in overlay.absent_concepts:
        if any(
            phrase_in(normalized, normalize_question(name)) for name in concept.names
        ):
            return concept
        for group in concept.all_of:
            if group and all(
                phrase_in(normalized, normalize_question(word)) for word in group
            ):
                return concept
    return None
