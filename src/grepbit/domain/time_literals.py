"""Source-aware temporal literals; never delegate interpretation to a session."""

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from grepbit.domain.plan import PlanError
from grepbit.domain.schema_model import ColumnKind, SchemaColumn


def timestamp_storage(column: SchemaColumn) -> str:
    data_type = column.data_type.strip().lower()
    if data_type in {"timestamp with time zone", "timestamptz"}:
        return "timestamptz"
    if data_type in {"timestamp without time zone", "timestamp"}:
        return "timestamp"
    raise PlanError("timestamp_type_unknown", column.name)


def local_instant(value: datetime, timezone: str) -> datetime:
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise PlanError("timestamp_timezone_invalid") from None
    candidates = {
        candidate.astimezone(UTC)
        for fold in (0, 1)
        if (candidate := value.replace(tzinfo=zone, fold=fold))
        .astimezone(UTC)
        .astimezone(zone)
        .replace(tzinfo=None)
        == value
    }
    if not candidates:
        raise PlanError("timestamp_local_nonexistent")
    if len(candidates) != 1:
        raise PlanError("timestamp_local_ambiguous")
    return next(iter(candidates)).astimezone(zone)


def bind_time_literal(
    column: SchemaColumn, value: str, timezone: str
) -> tuple[str, str, bool]:
    """Return canonical value, physical parameter type, and default-zone use."""
    if column.kind is ColumnKind.DATE:
        try:
            return date.fromisoformat(value).isoformat(), "date", False
        except ValueError:
            raise PlanError("date_literal_precision_loss", column.name) from None
    if re.search(r"[.,]\d{7,}", value):
        raise PlanError("timestamp_precision_unsupported", column.name)
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise PlanError("filter_kind_mismatch", column.name) from None
    storage = timestamp_storage(column)
    if storage == "timestamp":
        if moment.tzinfo is not None:
            raise PlanError("timestamp_zone_binding_required", column.name)
        return moment.isoformat(), storage, False
    assumed = moment.tzinfo is None
    if assumed:
        moment = local_instant(moment, timezone)
    return moment.isoformat(), storage, assumed


def calendar_boundary(
    column: SchemaColumn, value: datetime, timezone: str
) -> tuple[str, str]:
    """Resolved calendar labels retain source storage semantics."""
    wall = value.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
    if column.kind is ColumnKind.DATE:
        return wall.date().isoformat(), "date"
    if timestamp_storage(column) == "timestamp":
        return wall.isoformat(), "timestamp"
    return local_instant(wall, timezone).isoformat(), "timestamptz"
