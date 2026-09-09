"""Second-opinion call: does the compiled plan express every concept asked?

The planner can silently drop a qualifier it cannot express (asked for return
amount, answered total sales). This client audits the compiled plan against the
question with a different task framing; the server treats an uncovered concept
as a reason to clarify instead of answering.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from grepbit.domain.plan import CompiledPlan, CoverageReport
from grepbit.domain.schema_model import SchemaModel
from grepbit.ports.grounding import GroundingModelError

COVERAGE_PROMPT_REVISION = "coverage-audit-json-v2"

_RULES = (
    "You audit whether a compiled query plan answers exactly the question asked. "
    "Step 1: list every business concept in the question: the measured quantity, "
    "the entities, every qualifier (a state, category, segment, or adjective such "
    "as new, returned, online, VIP, confirmed), and every time reference. "
    "Step 2: for each concept name the plan element that expresses it, copying "
    "the element text from the plan: a measure, a dimension, a filter, a null "
    "check, a join, or the time window. If nothing in the plan expresses the "
    "concept, set mapped_to to null. A concept is not expressed by a column that "
    "is merely related to it; a qualifier the plan ignores is uncovered. Column "
    "comments and sample values tell you what a column expresses. Words that "
    "mean no restriction (overall, total, all, in general, 全部, 整體, 總共) are "
    "expressed by the absence of a filter: map them to 'no filter'. Do not "
    "invent plan elements. Output only one JSON object matching the schema."
)


def plan_payload(compiled: CompiledPlan, schema: SchemaModel) -> dict[str, Any]:
    columns = []
    for ref in compiled.compiled.semantic_refs:
        table_name, column_name = ref.split(".", 1)
        table = schema.table(table_name)
        column = table.column(column_name) if table else None
        if column is None:
            continue
        columns.append(
            {
                "id": ref,
                "type": column.data_type,
                "comment": column.comment,
                "table_comment": table.comment if table else None,
                "sample_values": column.sample_values or None,
            }
        )
    return {
        "interpretation": compiled.interpretation,
        **compiled.lineage.as_dict(),
        "columns_used": columns,
    }


class ChatCompletionsCoverageClient:
    def __init__(
        self, settings: GroundingModelSettings, *, client: Any | None = None
    ) -> None:
        self._settings = settings
        self._transport = ChatCompletionsGroundingClient(settings, client=client)

    def build_messages(
        self, question: str, compiled: CompiledPlan, schema: SchemaModel
    ) -> list[dict[str, str]]:
        json_schema = json.dumps(CoverageReport.model_json_schema(), sort_keys=True)
        payload = {
            "question": question.strip(),
            "prompt_revision": COVERAGE_PROMPT_REVISION,
            "plan": plan_payload(compiled, schema),
        }
        return [
            {"role": "system", "content": _RULES},
            {
                "role": "system",
                "content": "Conform exactly to this JSON Schema: " + json_schema,
            },
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True, ensure_ascii=False),
            },
        ]

    def verify(
        self, question: str, compiled: CompiledPlan, schema: SchemaModel
    ) -> CoverageReport:
        client = self._transport._client or self._transport._create_client()
        try:
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=self.build_messages(question, compiled, schema),
                temperature=self._settings.temperature,
                max_tokens=max(self._settings.max_tokens, 512),
                response_format={"type": "json_object"},
            )
        except Exception:
            raise GroundingModelError("model_call_failed", 1) from None
        try:
            payload = json.loads(response.choices[0].message.content)
            return CoverageReport.model_validate(payload)
        except (AttributeError, IndexError, TypeError, ValueError, ValidationError):
            raise GroundingModelError("invalid_structured_output", 1) from None
