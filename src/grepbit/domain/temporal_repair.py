"""Narrow preservation of explicit timestamp range anchors across repair.

This compares a recognizable invalid draft with its repair, not the user's
intent. Only plan/without range endpoints are protected; unknown is not a
confirmed change. Time interpretation is owned by the approved binding policy.
"""

import json
import re
from datetime import UTC, datetime, time

from grepbit.domain.plan import PlanError
from grepbit.domain.schema_model import ColumnKind
from grepbit.domain.time_literals import bind_time_literal


def _instant(value, column, timezone):
    if not isinstance(value, str):
        return None
    if column.kind is not ColumnKind.TIMESTAMP:
        return None
    try:
        canonical, _, _ = bind_time_literal(column, value, timezone)
        instant = datetime.fromisoformat(canonical)
        return instant.astimezone(UTC) if instant.tzinfo is not None else instant
    except (ValueError, OverflowError, PlanError):
        return None


def _column(value):
    if isinstance(value, str) and value.count(".") == 1:
        return value
    if isinstance(value, dict) and isinstance(value.get("table"), str):
        if isinstance(value.get("column"), str):
            identity = value["table"] + "." + value["column"]
            return identity if identity.count(".") == 1 else None
    return None


def _filter_bounds(filters, column, source, timezone, key):
    """Read only recognizable same-column comparisons on either side."""
    if not isinstance(filters, list):
        return None
    bounds = []
    operators = {"gte", "gt"} if key == "start" else {"lt", "lte"}
    for item in filters:
        if (
            not isinstance(item, dict)
            or (identity := _column(item.get("column"))) is None
        ):
            return None
        if identity != column:
            continue  # Other-column predicates are outside the protected anchors.
        if set(item) - {"column", "op", "values"}:
            return None
        op, values = item.get("op"), item.get("values")
        if not isinstance(op, str) or op not in {"gte", "gt", "lt", "lte"}:
            return None
        if not isinstance(values, list) or len(values) != 1:
            return None
        value = _instant(values[0], source, timezone)
        if value is None:
            return None
        if op in operators:
            bounds.append((value, int(op in {"gt", "lte"})))
    return bounds


def temporal_repair_audit(raw, plan, model):
    """A narrow monotonic safeguard, not complete semantic equivalence."""
    try:
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        draft = json.loads(raw).get("plan")
    except (ValueError, AttributeError):
        return "not_applicable"
    if not isinstance(draft, dict):
        return "not_applicable"
    found = False
    for location in ("plan", "without"):
        before = draft if location == "plan" else draft.get("without")
        if not isinstance(before, dict) or not isinstance(before.get("time"), dict):
            continue
        spec = before["time"]
        scope = spec.get("scope")
        if not isinstance(scope, dict) or scope.get("kind") != "range":
            continue
        for key, op in (("start", "gte"), ("end_exclusive", "lt")):
            literal = scope.get(key)
            if not isinstance(literal, str) or not re.search(r"\d[Tt ]\d", literal):
                continue
            found = True
            column = _column(spec.get("column"))
            base = draft.get("base_table")
            child = before.get("table") if location == "without" else None
            if (
                column is None
                or not isinstance(base, str)
                or model.table(base) is None
                or (
                    location == "without"
                    and (not isinstance(child, str) or model.table(child) is None)
                )
            ):
                return "unverifiable"
            table, field = column.split(".")
            known = model.table(table)
            if not known or not known.column(field):
                return "unverifiable"
            source = known.column(field)
            instant = _instant(literal, source, model.business_timezone)
            if instant is None:
                return "unverifiable"
            original_bounds = _filter_bounds(
                before.get("filters", []), column, source, model.business_timezone, key
            )
            if original_bounds is None:
                return "unverifiable"
            original_bounds.append((instant, 0))
            if plan.base_table != base:
                return "changed"
            after = plan if location == "plan" else plan.without
            if after is None or (location == "without" and after.table != child):
                return "changed"
            bounds = _filter_bounds(
                [f.model_dump(mode="json") for f in after.filters],
                column,
                source,
                model.business_timezone,
                key,
            )
            if bounds is None:
                return "unverifiable"
            window = after.time
            if window is not None and window.scope is not None:
                if window.scope.kind != "range" or window.column is None:
                    return "unverifiable"
                if window.column.id != column:
                    return "changed"
                boundary = _instant(
                    datetime.combine(getattr(window.scope, key), time.min).isoformat(),
                    source,
                    model.business_timezone,
                )
                if boundary is None:
                    return "unverifiable"
                bounds.append((boundary, 0))
            effective = (
                (max(bounds) if key == "start" else min(bounds)) if bounds else None
            )
            original = max(original_bounds) if key == "start" else min(original_bounds)
            if effective != original:
                return "changed"
    return "preserved" if found else "not_applicable"
