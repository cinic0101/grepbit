"""Overlay validation against the schema and deterministic absent-concept match."""

from __future__ import annotations

from grepbit.application.text import phrase_in
from grepbit.domain.grounding import normalize_question
from grepbit.domain.overlay import AbsentConcept, SemanticOverlay
from grepbit.domain.schema_model import SchemaModel


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
    return problems


def match_absent_concept(
    question: str, overlay: SemanticOverlay
) -> AbsentConcept | None:
    normalized = normalize_question(question)
    for concept in overlay.absent_concepts:
        if any(
            phrase_in(normalized, normalize_question(name)) for name in concept.names
        ):
            return concept
    return None
