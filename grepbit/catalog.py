"""Reviewed runtime bindings derived from LearningOps definitions, not evaluator SQL."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

from sqlglot import exp

from .contracts import KernelError

PROFILE_ID = "learningops-sqlite-utc-text-v1"


def _column(name: str, table: str) -> exp.Column:
    return exp.column(name, table=table, quoted=True)


def _distinct_count(name: str) -> exp.Count:
    return exp.Count(this=exp.Distinct(expressions=[_column(name, "b")]))


@dataclass(frozen=True)
class MetricBinding:
    source: str
    expression: exp.Expression
    unit: str
    description: str
    disclosures: tuple[str, ...] = ()
    excluded_null_column: str | None = None


@dataclass(frozen=True)
class Catalog:
    """Trusted Python configuration; never accepted as a request field."""

    version: str
    metrics: Mapping[str, MetricBinding]

    def __post_init__(self) -> None:
        if (not isinstance(self.version, str) or not 1 <= len(self.version) <= 128
                or not isinstance(self.metrics, Mapping) or not 1 <= len(self.metrics) <= 32):
            raise KernelError("invalid_catalog", "Catalog needs a version and one to 32 bindings.")
        for key, binding in self.metrics.items():
            if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)
                    or not isinstance(binding, MetricBinding)
                    or not isinstance(binding.expression, exp.Expression)
                    or not isinstance(binding.unit, str) or not binding.unit
                    or not isinstance(binding.description, str) or not binding.description
                    or not isinstance(binding.disclosures, tuple)
                    or any(not isinstance(text, str) for text in binding.disclosures)):
                raise KernelError("invalid_catalog", "Malformed metric binding.")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def digest(self) -> str:
        definitions = {
            key: {
                "source": binding.source, "expression": binding.expression.sql(dialect="sqlite"),
                "unit": binding.unit, "description": binding.description,
                "disclosures": binding.disclosures, "excluded_null_column": binding.excluded_null_column,
            }
            for key, binding in self.metrics.items()
        }
        payload = {"profile": PROFILE_ID, "version": self.version, "metrics": definitions}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


LEARNINGOPS = Catalog("learningops-metrics-v1", {
    "confirmed_booked_amount": MetricBinding(
        "booking_items",
        exp.Sum(this=exp.Sub(
            this=exp.Mul(this=_column("seats", "i"), expression=_column("unit_price_minor", "i")),
            expression=_column("discount_minor", "i"),
        )),
        "TWD_minor", "Confirmed line amount after discounts and before refunds.",
        ("Refunds are not subtracted; this is not profit or recognized revenue.",),
    ),
    "confirmed_booking_count": MetricBinding(
        "bookings", _distinct_count("booking_id"), "bookings", "Distinct confirmed booking IDs.",
    ),
    "booked_seats": MetricBinding(
        "booking_items", exp.Sum(this=_column("seats", "i")), "seats", "Seats on confirmed booking lines.",
        ("Seats are not unique people or attendance visits.",),
    ),
    "known_booking_accounts": MetricBinding(
        "bookings", _distinct_count("learner_id"), "booking_accounts",
        "Distinct non-null booking-account IDs on confirmed bookings.",
        ("Anonymous bookings are excluded; booking accounts are not unique people.",),
        excluded_null_column="learner_id",
    ),
})
