"""Boundary for auditing whether a compiled plan covers the question asked."""

from __future__ import annotations

from typing import Protocol

from grepbit.domain.plan import CompiledPlan, CoverageReport
from grepbit.domain.schema_model import SchemaModel

__all__ = ["CoverageReport", "CoverageVerifierPort"]


class CoverageVerifierPort(Protocol):
    def verify(
        self, question: str, compiled: CompiledPlan, schema: SchemaModel
    ) -> CoverageReport:
        """Map every business concept in ``question`` to a plan element or None."""
        ...
