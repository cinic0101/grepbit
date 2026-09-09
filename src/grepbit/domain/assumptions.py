"""Assumption records attached to every rendered answer (spec Section 8)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from grepbit.domain.models import DomainModel


class AssumptionSource(StrEnum):
    REVIEWED = "reviewed"
    CANDIDATE = "candidate"
    DEFAULT = "default"


class Assumption(DomainModel):
    text: str = Field(min_length=1)
    source: AssumptionSource
    definition_ref: str = Field(min_length=1)
