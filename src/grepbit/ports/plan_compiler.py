"""Provider-neutral boundary for compiling tier-0 plans into executable SQL."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from grepbit.domain.plan import CompiledPlan, PlanError, QueryPlan

__all__ = ["CompiledPlan", "PlanCompilerPort", "PlanError"]


class PlanCompilerPort(Protocol):
    def compile(self, plan: QueryPlan, *, as_of: datetime) -> CompiledPlan:
        """Validate ``plan`` against the schema and render parameterized SQL.

        Raises ``PlanError`` with a stable code when the plan is structurally
        invalid (unknown identifier, fan-out join, kind mismatch, missing grain).
        """
        ...
