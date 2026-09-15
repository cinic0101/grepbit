"""Research-only preservation of explicit range instants across model repair."""

import json
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    _InvalidOutput,
)

GUIDANCE = (
    "Calendar range scopes accept dates only, not timestamps. For a requested "
    "precise timestamp interval, use existing gte/gt/lt/lte filters on the "
    "timestamp column in the correct population scope; day grain can remain "
    "without a range scope. Preserve exact instants, timezone offsets and "
    "inclusive/exclusive operators. If a draft puts timestamps in a date-only "
    "range, repair their representation into filters at the same scope; never "
    "truncate the time, round the endpoint, change column or move the restriction "
    "between the base population and without. Decline if not representable."
)
REVISION = "time-precision-guidance-v1"


def _instant(value):
    if not isinstance(value, str) or not re.search(r"\d[Tt ]\d", value):
        return None
    # Python would silently truncate sub-microsecond precision.
    if re.search(r"[.,]\d{7,}", value):
        return None
    try:
        instant = datetime.fromisoformat(value)
        return instant if instant.tzinfo is not None else None
    except ValueError:
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
            instant = _instant(literal)
            column = _column(spec.get("column"))
            if instant is None or column is None or not draft.get("base_table"):
                return "unverifiable"
            table, field = column.split(".")
            known = model.table(table)
            if not known or not known.column(field):
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
                    value = _instant(f.values[0]) if len(f.values) == 1 else None
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
                boundary = datetime.combine(
                    getattr(window.scope, key),
                    time.min,
                    tzinfo=ZoneInfo(model.business_timezone),
                )
                bounds.append((boundary, 0))
            effective = (
                (max(bounds) if key == "start" else min(bounds)) if bounds else None
            )
            if effective != (instant, 0):
                return "changed"
    return "preserved" if found else "not_applicable"


class TemporalPlanner(ChatCompletionsPlanClient):
    def __init__(self, settings, *, guidance=False, guard=False, **kwargs):
        super().__init__(settings, **kwargs)
        self.guidance = guidance
        self.guard = guard
        self.first_invalid = None
        self.temporal_audit = "not_applicable"

    def propose(self, *args, **kwargs):
        self.first_invalid = None
        self.temporal_audit = "not_applicable"
        return super().propose(*args, **kwargs)

    def build_messages(self, *args, **kwargs):
        messages = super().build_messages(*args, **kwargs)
        if self.guidance:
            messages[0]["content"] += "\n" + GUIDANCE
            context = json.loads(messages[2]["content"])
            context["prompt_revision"] = REVISION
            messages[2]["content"] = json.dumps(context, ensure_ascii=False)
        return messages

    def _validate(self, content, model, **kwargs):
        try:
            proposal = super()._validate(content, model, **kwargs)
        except _InvalidOutput:
            if self.first_invalid is None:
                self.first_invalid = content
            raise
        if self.guard and self.first_invalid and proposal.plan is not None:
            self.temporal_audit = temporal_repair_audit(
                self.first_invalid, proposal.plan, model
            )
            if self.temporal_audit in {"changed", "unverifiable"}:
                raise _InvalidOutput("repair_temporal_anchor_not_preserved")
        return proposal
