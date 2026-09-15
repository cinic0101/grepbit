"""Historical guidance/control wrapper; production owns temporal repair checks."""

import json

from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.domain.temporal_repair import (
    temporal_repair_audit as temporal_repair_audit,
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


class TemporalPlanner(ChatCompletionsPlanClient):
    """Keep historical guard-off arms explicit; never duplicate the runtime check."""

    def __init__(self, settings, *, guidance=False, guard=False, **kwargs):
        super().__init__(settings, **kwargs)
        self.guidance = guidance
        self.guard = guard

    @property
    def temporal_audit(self):
        return self.last_temporal_repair_audit

    def _audit_repair(self, content, proposal, model):
        if not self.guard:
            return "not_applicable"
        return super()._audit_repair(content, proposal, model)

    def build_messages(self, *args, **kwargs):
        messages = super().build_messages(*args, **kwargs)
        if self.guidance:
            messages[0]["content"] += "\n" + GUIDANCE
            context = json.loads(messages[2]["content"])
            context["prompt_revision"] = REVISION
            messages[2]["content"] = json.dumps(context, ensure_ascii=False)
        return messages
