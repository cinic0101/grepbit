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
            if column is None or not draft.get("base_table"):
                return "unverifiable"
            table, field = column.split(".")
            known = model.table(table)
            if not known or not known.column(field):
                return "unverifiable"
            source = known.column(field)
            instant = _instant(literal, source, model.business_timezone)
            if instant is None:
                return "unverifiable"
            if plan.base_table != draft["base_table"]:
                return "changed"
            after = plan if location == "plan" else plan.without
            if after is None or (
                location == "without" and after.table != before.get("table")
            ):
                return "changed"
            bounds = []
            operators = {"gte", "gt"} if key == "start" else {"lt", "lte"}
            for f in after.filters:
                if f.column.id != column:
                    continue
                if f.op not in {"gte", "gt", "lt", "lte"}:
                    return "unverifiable"
                if f.op in operators:
                    value = (
                        _instant(f.values[0], source, model.business_timezone)
                        if len(f.values) == 1
                        else None
                    )
                    if value is None:
                        return "unverifiable"
                    # At equal instants, exclusive bounds are stronger.
                    bounds.append((value, int(f.op in {"gt", "lte"})))
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
            if effective != (instant, 0):
                return "changed"
    return "preserved" if found else "not_applicable"
