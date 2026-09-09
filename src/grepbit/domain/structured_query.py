"""Typed structured query contract and deterministic time resolution (spec §6)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from grepbit.domain.catalog import QueryShape
from grepbit.domain.models import DomainModel

_ISO_MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
_QUALIFIED_IDENTIFIER = r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$"
_IDENTIFIER = r"^[a-z_][a-z0-9_]*$"
MAX_RELATIVE_SPAN = 36
MAX_COMPARED_PERIODS = 6


class TimeGrain(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class RelativeUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class SortOrder(StrEnum):
    DESC = "desc"
    ASC = "asc"


class MonthScope(DomainModel):
    kind: Literal["month"] = "month"
    month: str = Field(pattern=_ISO_MONTH)


class RangeScope(DomainModel):
    kind: Literal["range"] = "range"
    start: date
    end_exclusive: date

    @model_validator(mode="after")
    def range_is_forward(self) -> RangeScope:
        if self.end_exclusive <= self.start:
            raise ValueError("time_range_must_be_forward")
        return self


class RelativeScope(DomainModel):
    """A period relative to ``as_of``; the server performs the date arithmetic."""

    kind: Literal["relative"] = "relative"
    unit: RelativeUnit
    offset: int = Field(le=0, ge=-MAX_RELATIVE_SPAN)
    length: int = Field(default=1, ge=1, le=MAX_RELATIVE_SPAN)


class PeriodsScope(DomainModel):
    kind: Literal["periods"] = "periods"
    periods: list[MonthScope] = Field(min_length=2, max_length=MAX_COMPARED_PERIODS)

    @model_validator(mode="after")
    def periods_are_unique(self) -> PeriodsScope:
        months = [period.month for period in self.periods]
        if len(months) != len(set(months)):
            raise ValueError("compared_periods_must_be_unique")
        return self


TimeScope = Annotated[
    MonthScope | RangeScope | RelativeScope | PeriodsScope,
    Field(discriminator="kind"),
]


class EnumFilter(DomainModel):
    dimension_id: str = Field(pattern=_QUALIFIED_IDENTIFIER)
    value_id: str = Field(pattern=_IDENTIFIER)


class StructuredQuery(DomainModel):
    """Identifier-constrained, value-bearing query the renderer turns into SQL."""

    shape: QueryShape
    metric_id: str = Field(pattern=_IDENTIFIER)
    dimension_ids: list[str] = Field(default_factory=list)
    time_field_id: str | None = Field(default=None, pattern=_QUALIFIED_IDENTIFIER)
    time_scope: TimeScope | None = None
    grain: TimeGrain | None = None
    filters: list[EnumFilter] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1)
    order: SortOrder = SortOrder.DESC

    @model_validator(mode="after")
    def shape_requirements(self) -> StructuredQuery:
        dimension_count = len(self.dimension_ids)
        if len(set(self.dimension_ids)) != dimension_count:
            raise ValueError("structured_query_dimension_duplicate")
        filter_ids = [item.dimension_id for item in self.filters]
        if len(set(filter_ids)) != len(filter_ids):
            raise ValueError("structured_query_filter_duplicate")
        is_periods = isinstance(self.time_scope, PeriodsScope)
        if self.shape is QueryShape.COMPARE_PERIODS:
            if not is_periods or dimension_count or self.grain or self.limit:
                raise ValueError("structured_query_compare_periods_invalid")
            return self
        if is_periods:
            raise ValueError("structured_query_periods_scope_requires_compare")
        if self.shape is QueryShape.METRIC_SCALAR:
            if dimension_count or self.limit or self.grain:
                raise ValueError("structured_query_scalar_invalid")
        elif self.shape is QueryShape.METRIC_BY_DIMENSION:
            if dimension_count != 1 or self.limit or self.grain:
                raise ValueError("structured_query_by_dimension_invalid")
        elif self.shape is QueryShape.TOP_N:
            if dimension_count != 1 or self.limit is None or self.grain:
                raise ValueError("structured_query_top_n_invalid")
        elif self.shape is QueryShape.METRIC_OVER_TIME:
            if dimension_count or self.limit or self.grain is None:
                raise ValueError("structured_query_over_time_invalid")
            if self.time_scope is None:
                raise ValueError("structured_query_over_time_requires_scope")
        return self


class ResolvedPeriod(DomainModel):
    label: str = Field(min_length=1)
    start: datetime
    end_exclusive: datetime

    @model_validator(mode="after")
    def bounds_are_aware_and_forward(self) -> ResolvedPeriod:
        if self.start.tzinfo is None or self.end_exclusive.tzinfo is None:
            raise ValueError("resolved_period_requires_timezone")
        if self.end_exclusive <= self.start:
            raise ValueError("resolved_period_must_be_forward")
        return self


def resolve_time_scope(
    scope: MonthScope | RangeScope | RelativeScope | PeriodsScope,
    *,
    as_of: datetime,
    business_timezone: str,
) -> list[ResolvedPeriod]:
    """Return half-open business-timezone periods; the model never does this."""

    zone = ZoneInfo(business_timezone)
    if isinstance(scope, MonthScope):
        return [_month_period(scope.month, zone)]
    if isinstance(scope, PeriodsScope):
        return [_month_period(period.month, zone) for period in scope.periods]
    if isinstance(scope, RangeScope):
        return [
            ResolvedPeriod(
                label=f"{scope.start.isoformat()}..{scope.end_exclusive.isoformat()}",
                start=datetime.combine(scope.start, time(), tzinfo=zone),
                end_exclusive=datetime.combine(
                    scope.end_exclusive, time(), tzinfo=zone
                ),
            )
        ]
    anchor = as_of.astimezone(zone)
    if scope.unit in {RelativeUnit.MONTH, RelativeUnit.QUARTER, RelativeUnit.YEAR}:
        months_per_unit = {
            RelativeUnit.MONTH: 1,
            RelativeUnit.QUARTER: 3,
            RelativeUnit.YEAR: 12,
        }[scope.unit]
        # Snap the anchor to the start of its own unit before stepping.
        anchor_month = ((anchor.month - 1) // months_per_unit) * months_per_unit + 1
        first_year, first_month = _add_months(
            anchor.year, anchor_month, scope.offset * months_per_unit
        )
        last_year, last_month = _add_months(
            first_year, first_month, scope.length * months_per_unit
        )
        start = datetime(first_year, first_month, 1, tzinfo=zone)
        end = datetime(last_year, last_month, 1, tzinfo=zone)
        if scope.unit is RelativeUnit.MONTH:
            first_label = f"{first_year:04d}-{first_month:02d}"
            last_label = f"{last_year:04d}-{last_month:02d}"
        elif scope.unit is RelativeUnit.QUARTER:
            first_label = f"{first_year:04d}-Q{(first_month - 1) // 3 + 1}"
            last_label = f"{last_year:04d}-Q{(last_month - 1) // 3 + 1}"
        else:
            first_label, last_label = f"{first_year:04d}", f"{last_year:04d}"
        label = first_label if scope.length == 1 else f"{first_label}..{last_label}"
        return [ResolvedPeriod(label=label, start=start, end_exclusive=end)]
    if scope.unit is RelativeUnit.WEEK:
        week_start = anchor.date() - timedelta(days=anchor.weekday())  # Monday
        first_day = week_start + timedelta(weeks=scope.offset)
        end_day = first_day + timedelta(weeks=scope.length)
    else:
        first_day = anchor.date() + timedelta(days=scope.offset)
        end_day = first_day + timedelta(days=scope.length)
    label = (
        first_day.isoformat()
        if scope.length == 1
        else f"{first_day.isoformat()}..{end_day.isoformat()}"
    )
    return [
        ResolvedPeriod(
            label=label,
            start=datetime.combine(first_day, time(), tzinfo=zone),
            end_exclusive=datetime.combine(end_day, time(), tzinfo=zone),
        )
    ]


def _month_period(month: str, zone: ZoneInfo) -> ResolvedPeriod:
    year, month_number = (int(part) for part in month.split("-"))
    next_year, next_month = _add_months(year, month_number, 1)
    return ResolvedPeriod(
        label=month,
        start=datetime(year, month_number, 1, tzinfo=zone),
        end_exclusive=datetime(next_year, next_month, 1, tzinfo=zone),
    )


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1
