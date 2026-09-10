"""Provider-neutral boundary for compiling tier-0 plans into executable SQL."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from grepbit.domain.overlay import Segment
from grepbit.domain.plan import CompiledPlan, PlanError, QueryPlan

__all__ = ["CompiledPlan", "PlanCompilerPort", "PlanError"]


class PlanCompilerPort(Protocol):
    def compile(
        self,
        plan: QueryPlan,
        *,
        as_of: datetime,
        exclude_segments: Sequence[Segment] = (),
        named_segments: Sequence[Segment] = (),
    ) -> CompiledPlan:
        """Validate ``plan`` against the schema and render parameterized SQL.

        ``exclude_segments`` are overlay segments the caller wants removed from
        the result (default exclusions the question did not lift); each one
        applied is stated as a reviewed assumption. Raises ``PlanError`` with a
        stable code when the plan is structurally invalid (unknown identifier,
        fan-out join, kind mismatch, missing grain, a past window that reaches
        the future).
        """
        ...
