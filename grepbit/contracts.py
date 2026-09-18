"""Bounded scalar fact requests and execution evidence, not natural-language plans."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_FACTS = 4
MAX_REQUEST_BYTES = 16384


class KernelError(Exception):
    """An explicit whole-batch failure; no successful Fact Pack accompanies it."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class FactRequest:
    metrics: tuple[str, ...]
    start: datetime
    end: datetime
    timezone: str
    center_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metrics, tuple) or not 1 <= len(self.metrics) <= MAX_FACTS:
            raise KernelError("invalid_request", "Request one to four metric IDs.")
        if any(not isinstance(m, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", m)
               for m in self.metrics):
            raise KernelError("invalid_request", "Metric IDs must be bounded canonical identifiers.")
        if len(set(self.metrics)) != len(self.metrics):
            raise KernelError("invalid_request", "Duplicate metric IDs are not allowed.")
        for value in (self.start, self.end):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise KernelError("invalid_request", "Start and end must be offset-aware instants.")
        try:
            ordered = self.start.astimezone(timezone.utc) < self.end.astimezone(timezone.utc)
        except (ValueError, OverflowError) as exc:
            raise KernelError("invalid_request", "Period cannot be represented in UTC.") from exc
        if not ordered:
            raise KernelError("invalid_request", "The half-open period must have start before end.")
        if not isinstance(self.timezone, str) or not 1 <= len(self.timezone) <= 128:
            raise KernelError("invalid_request", "An explicit IANA business timezone is required.")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise KernelError("invalid_request", "Unknown IANA business timezone.") from exc
        if self.center_id is not None and (
            not isinstance(self.center_id, str) or not 1 <= len(self.center_id) <= 64
        ):
            raise KernelError("invalid_request", "Center must be a nonempty canonical ID, not a name.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> FactRequest:
        if not isinstance(data, Mapping):
            raise KernelError("invalid_request", "A request must be an object.")
        required = {"metrics", "start", "end", "timezone"}
        if not required <= data.keys() or not data.keys() <= required | {"center_id"}:
            raise KernelError("invalid_request", "Missing required or unknown request fields.")
        metrics = data["metrics"]
        if not isinstance(metrics, list):
            raise KernelError("invalid_request", "Metrics must be a JSON array of metric IDs.")
        instants: list[datetime] = []
        for key in ("start", "end"):
            text = data[key]
            if not isinstance(text, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
                text,
            ):
                raise KernelError("invalid_request", "Use ISO instants with seconds and explicit offsets.")
            try:
                instants.append(datetime.fromisoformat(text))
            except ValueError as exc:
                raise KernelError("invalid_request", "Invalid calendar instant.") from exc
        zone, center = data["timezone"], data.get("center_id")
        if not isinstance(zone, str) or (center is not None and not isinstance(center, str)):
            raise KernelError("invalid_request", "Timezone and center ID must be strings.")
        metric_ids: list[str] = []
        for metric in metrics:
            if not isinstance(metric, str):
                raise KernelError("invalid_request", "Each metric ID must be a string.")
            metric_ids.append(metric)
        return cls(tuple(metric_ids), instants[0], instants[1], zone, center)

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": list(self.metrics), "start": self.start.isoformat(),
            "end": self.end.isoformat(), "timezone": self.timezone, "center_id": self.center_id,
        }


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: float = 2.0
    max_vm_steps: int = 1_000_000
    max_source_rows: int = 100_000

    def __post_init__(self) -> None:
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 30):
            raise KernelError("invalid_limits", "Timeout must be finite, positive and at most 30 seconds.")
        if type(self.max_vm_steps) is not int or not 100 <= self.max_vm_steps <= 1_000_000:
            raise KernelError("invalid_limits", "VM step budget must be between 100 and 1000000.")
        if type(self.max_source_rows) is not int or not 1 <= self.max_source_rows <= 100_000:
            raise KernelError("invalid_limits", "Source row budget must be between 1 and 100000.")


@dataclass(frozen=True)
class Fact:
    metric_id: str
    catalog_id: str
    catalog_sha256: str
    value: int | None
    unit: str
    grain: str
    population: str
    time_basis: str
    start_utc: str
    end_utc: str
    business_timezone: str
    filters: dict[str, str]
    population_rows: int
    empty_population: bool
    excluded_anonymous_rows: int | None
    disclosures: tuple[str, ...]
    sql: str
    parameters: dict[str, str]
    snapshot_id: str
    checks: tuple[str, ...]
    completeness: str = "complete"


@dataclass(frozen=True)
class FactPack:
    request: FactRequest
    facts: tuple[Fact, ...]
    snapshot: dict[str, str]
    runtime: dict[str, str]
    execution: dict[str, int | float]
    limitations: tuple[str, ...]
    status: str = "complete"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["request"] = self.request.to_dict()
        return result
