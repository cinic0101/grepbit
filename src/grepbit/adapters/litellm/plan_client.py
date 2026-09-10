"""Chat Completions client that turns a question into a tier-0 QueryPlan."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import Filter, Measure, PlanProposal, PreviousTurn, QueryPlan
from grepbit.domain.schema_model import SchemaModel
from grepbit.ports.grounding import GroundingModelError

PLAN_PROMPT_REVISION = "plan-classify-json-v9"

_RULES = (
    "You translate one analytics question into ONE aggregate query plan over the "
    "given PostgreSQL schema, or decline. Output only JSON matching the schema. "
    "Rules: "
    "(1) Use only table and column names that appear in the schema; never invent "
    "names. base_table is the table whose rows are being counted or summed. "
    "(2) measures: aggregate is one of sum, count, count_distinct, avg, min, max; "
    "count without a column counts rows. sum and avg need numeric columns. "
    "(3) dimensions and filters may use columns of base_table or of a table that "
    "base_table references through a foreign key (its parent, or the parent's "
    "parent). Never group by a child table's column. When a question groups by "
    "an entity that has its own table, group by that table's descriptive text "
    "column (a name or label), not by the foreign-key id. "
    "(4) filters: op in eq, ne, in, gt, gte, lt, lte, is_null, not_null; values "
    "are typed literals taken from the question (use sample_values spelling for "
    "text columns). Do not add filters the question does not ask for. "
    "(5) time: pick the timestamp or date column that matches the question and "
    'express the window as {"kind":"month","month":"YYYY-MM"}, '
    '{"kind":"range","start":"YYYY-MM-DD","end_exclusive":"YYYY-MM-DD"}, '
    '{"kind":"relative","unit":"day"|"week"|"month"|"quarter"|"year",'
    '"offset":-N,"length":L} (offset 0 is the current unit, so this quarter is '
    "unit quarter offset 0; last 7 days is unit day offset -7 length 7), or "
    '{"kind":"periods","periods":[{"kind":"month","month":"YYYY-MM"},...]}. '
    "Set grain (day, week, month, quarter, or year) when the question wants a "
    "trend or compares periods. A question that asks for a value per period "
    "(每天, 每日, daily, 各月份, monthly, per week) sets grain; give it a scope "
    "only if the question states a window, otherwise omit scope and the server "
    "buckets all the data. Never add a window the question does not ask for. "
    "In a relative window, length counts units: last week is unit week "
    "offset -1 length 1, not length 7. A period so far (本月截至今天, month to "
    'date, year to date) is {"kind":"relative","unit":...,"offset":0,"length":1,'
    '"to_date":true}. '
    "Never compute dates yourself; the server resolves relative windows from as_of. "
    "(6) Use order and limit for top-N questions; order fields must be output "
    "names (dimension column name, measure alias, or period_start). A condition "
    "on a group's aggregate (stores whose total sales exceed 100000, salespeople "
    "with more than 100 transactions: 超過, 以上, 至少, 大於, 少於, 低於 applied to a "
    'sum, count or average) goes in having as {"field": <measure output name>, '
    '"op": gt|gte|lt|lte|eq|ne, "value": number}; filters compare a row '
    "column, having compares a group measure. Never drop such a condition. "
    "(7) If the question asks for something the schema cannot express with one "
    "aggregate query (a metric with no column, a forecast, free text, a data "
    "change, several unrelated questions), return decision none with reason "
    "semantic_gap or unsupported. Every business concept in the question "
    "(return, refund, discount, margin, churn, and the like) must map to a "
    "column, a sample value, or a null check that expresses it; if one does "
    "not, never drop it and answer a broader question instead: return none with "
    "reason semantic_gap and name the concept in clarification. If two readings "
    "are equally plausible, return none with reason ambiguous and a one-sentence "
    "clarification naming the candidate columns. "
    "(8) Return only one JSON object."
)
_VALUES_RULE = (
    " (11) question_values lists stored values that occur verbatim in the question, "
    "each with its column. When the question refers to one of them, filter that "
    "column with exactly that value; do not shorten or re-segment it."
)
_FOLLOW_UP_RULE = (
    " (10) previous_turn holds the last answered question and its plan. If the new "
    "message is a follow-up that adjusts it (another period, an added or changed "
    "filter, a different breakdown, a different limit, a different measure), start "
    "from that plan and change only what the message asks; keep everything else. "
    "If the message is a new question, ignore previous_turn."
)
_OVERLAY_RULE = (
    " (9) reviewed_metrics are business definitions a reviewer signed. When the "
    "question asks for one of them (match on its names), the measure must be "
    '{"metric": "<id>"} with no aggregate or column; the metric carries its own '
    "definition and filters, so do not add filters that restate it. Still take "
    "dimensions, time, order, and limit from the question; base_table must be the "
    "metric's base_table. Tables and columns may list aliases (their business "
    "names) and a table may name its default_time_column: prefer it for that "
    "table. A column's value_aliases map business names to stored values: use "
    "the stored value as the literal. segments describe row subsets the server "
    "already excludes by default; do not add filters for them."
)


def schema_payload(
    model: SchemaModel, overlay: SemanticOverlay | None = None
) -> dict[str, Any]:
    """Value-free schema description: names, kinds, comments, sampled enum values."""

    def column_entry(table_name: str, column) -> dict[str, Any]:
        samples = column.sample_values or None
        if (
            overlay is not None
            and not overlay.column_switches(f"{table_name}.{column.name}")[0]
        ):
            samples = None  # policy: this column's values never reach the planner
        entry = {
            "name": column.name,
            "kind": column.kind.value,
            "type": f"enum {column.data_type}" if column.is_enum else column.data_type,
            "nullable": column.nullable,
            "comment": column.comment,
            "sample_values": samples,
        }
        if overlay is not None:
            column_id = f"{table_name}.{column.name}"
            aliases = overlay.aliases_for(column_id)
            if aliases:
                entry["aliases"] = aliases
            values = overlay.values_for(column_id)
            if values:
                # Reviewed stored values with their business names; the planner
                # uses the stored spelling as the literal.
                entry["value_aliases"] = [
                    {"value": v.value, "names": v.names} for v in values
                ]
        return entry

    def table_entry(table) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "name": table.name,
            "comment": table.comment,
            "primary_key": table.primary_key,
        }
        if overlay is not None:
            names = overlay.table_names(table.name)
            if names:
                entry["aliases"] = names
            default = overlay.time_default(table.name)
            if default is not None:
                entry["default_time_column"] = default.id
        entry["columns"] = [
            column_entry(table.name, c)
            for c in table.columns
            if overlay is None or overlay.visible_column(table.name, c.name)
        ]
        return entry

    def visible_table(table) -> bool:
        return overlay is None or overlay.table_visible(table.name)

    payload: dict[str, Any] = {
        "datasource_id": model.datasource_id,
        "business_timezone": model.business_timezone,
        "tables": [
            table_entry(table) for table in model.tables if visible_table(table)
        ],
        "foreign_keys": [
            f"{fk.table}.{fk.column} -> {fk.referenced_table}.{fk.referenced_column}"
            for fk in model.foreign_keys
            if overlay is None
            or (
                overlay.table_visible(fk.table)
                and overlay.table_visible(fk.referenced_table)
            )
        ],
    }
    if overlay is not None and overlay.metrics:
        payload["reviewed_metrics"] = [
            {
                "id": metric.id,
                "names": metric.names,
                "description": metric.description,
                "base_table": metric.base_table,
                "review_state": metric.review_state.value,
            }
            for metric in overlay.metrics
        ]
    if overlay is not None and overlay.segments:
        payload["segments"] = [
            {
                "id": segment.id,
                "names": segment.names,
                "table": segment.table,
                "excluded_by_default": segment.default_exclude,
                "note": segment.note,
            }
            for segment in overlay.segments
        ]
    return payload


_PLAN_KEYS = set(QueryPlan.model_fields)
_MEASURE_KEYS = set(Measure.model_fields)
_FILTER_KEYS = set(Filter.model_fields)


def _drop_null_extras(plan: dict[str, Any], repairs: list[str]) -> None:
    """Remove null-valued keys the model added that are not plan fields.

    The model sometimes copies a decline field ("reason": null) into a plan or
    writes "column": null on a count measure; the strict schema rejects the
    whole answer. A null carries no meaning, so dropping such a key changes
    nothing but the shape. Nulls on real fields are left for validation.
    """

    dropped: list[str] = []
    for key in [k for k, v in plan.items() if v is None and k not in _PLAN_KEYS]:
        del plan[key]
        dropped.append(f"plan.{key}")
    for section, allowed in (("measures", _MEASURE_KEYS), ("filters", _FILTER_KEYS)):
        for item in plan.get(section) or []:
            if not isinstance(item, dict):
                continue
            for key in [k for k, v in item.items() if v is None and k not in allowed]:
                del item[key]
                dropped.append(f"{section}.{key}")
            if section == "measures" and item.get("column", "x") is None:
                del item["column"]  # count(*) written with an explicit null column
                dropped.append("measures.column")
    if dropped:
        repairs.append("dropped null keys: " + ", ".join(dropped))


def repair_column_refs(payload: Any, model: SchemaModel) -> tuple[Any, list[str]]:
    """Coerce column references the model wrote as strings into ColumnRef dicts.

    Only the shape is repaired ("store_name" or "store.store_name" becomes
    {"table": ..., "column": ...}) and only when the name resolves to exactly
    one table (or to the base table). A measure or filter that carries the
    table as a sibling key ({"column": "store_name", "table": "store", ...})
    is folded the same way when that table has that column. Meaning is never
    guessed; anything that stays ambiguous fails validation as before. Repairs
    are reported so the caller can count how often the model slips.
    """

    repairs: list[str] = []
    if not isinstance(payload, dict) or not isinstance(payload.get("plan"), dict):
        return payload, repairs
    plan = payload["plan"]
    _drop_null_extras(plan, repairs)
    base_table = plan.get("base_table")

    def coerce(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if "." in value:
            table, column = value.split(".", 1)
            candidates = [table] if model.table(table) else []
        else:
            column = value
            candidates = [t.name for t in model.tables if t.column(column)]
            if len(candidates) > 1 and base_table in candidates:
                candidates = [base_table]
        if len(candidates) != 1:
            return value
        repairs.append(f"{value} -> {candidates[0]}.{column}")
        return {"table": candidates[0], "column": column}

    for key in ("measures", "filters"):
        for item in plan.get(key) or []:
            if not isinstance(item, dict) or "column" not in item:
                continue
            table, column = item.get("table"), item["column"]
            if isinstance(table, str) and isinstance(column, str) and "." not in column:
                owner = model.table(table)
                if owner is not None and owner.column(column) is not None:
                    del item["table"]
                    repairs.append(f"{column} + table {table} -> {table}.{column}")
                    item["column"] = {"table": table, "column": column}
                # A sibling table that does not own the column is left alone:
                # the extra key fails validation instead of being guessed away.
                continue
            item["column"] = coerce(column)
    if isinstance(plan.get("dimensions"), list):
        plan["dimensions"] = [coerce(d) for d in plan["dimensions"]]
    time = plan.get("time")
    if isinstance(time, dict) and "column" in time:
        time["column"] = coerce(time["column"])
    return payload, repairs


class ChatCompletionsPlanClient:
    """One strict call per question; the server validates every identifier."""

    last_repairs: list[str] = []

    def __init__(
        self,
        settings: GroundingModelSettings,
        *,
        client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._transport = ChatCompletionsGroundingClient(settings, client=client)

    @property
    def settings(self) -> GroundingModelSettings:
        return self._settings

    def response_format(self) -> dict[str, Any]:
        """``json_object`` (valid JSON) or ``json_schema`` (constrained decoding).

        In ``json_schema`` mode the gateway (vLLM guided decoding) can only
        emit tokens that keep the output inside ``PlanProposal``'s schema, so
        shape slips cannot happen; the shape repairs stay as the fallback for
        the other mode.
        """

        if self._settings.structured_output_mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "plan_proposal",
                    "schema": PlanProposal.model_json_schema(),
                    "strict": True,
                },
            }
        return {"type": "json_object"}

    def build_messages(
        self,
        question: str,
        model: SchemaModel,
        *,
        as_of: str,
        overlay: SemanticOverlay | None = None,
        previous: PreviousTurn | None = None,
        question_values: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        schema = json.dumps(PlanProposal.model_json_schema(), sort_keys=True)
        payload: dict[str, Any] = {
            "question": question.strip(),
            "as_of": as_of,
            "prompt_revision": PLAN_PROMPT_REVISION,
            "schema": schema_payload(model, overlay),
        }
        if previous is not None:
            payload["previous_turn"] = previous.model_dump(
                mode="json", exclude_none=True
            )
        if question_values:
            payload["question_values"] = question_values
        rules = _RULES + (_OVERLAY_RULE if overlay is not None else "")
        rules += _FOLLOW_UP_RULE if previous is not None else ""
        rules += _VALUES_RULE if question_values else ""
        return [
            {"role": "system", "content": rules},
            {
                "role": "system",
                "content": "Conform exactly to this JSON Schema: " + schema,
            },
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True, ensure_ascii=False),
            },
        ]

    def propose(
        self,
        question: str,
        model: SchemaModel,
        *,
        as_of: str,
        overlay: SemanticOverlay | None = None,
        previous: PreviousTurn | None = None,
        question_values: list[dict[str, str]] | None = None,
    ) -> PlanProposal:
        client = self._transport._client or self._transport._create_client()
        try:
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=self.build_messages(
                    question,
                    model,
                    as_of=as_of,
                    overlay=overlay,
                    previous=previous,
                    question_values=question_values,
                ),
                temperature=self._settings.temperature,
                max_tokens=max(self._settings.max_tokens, 768),
                response_format=self.response_format(),
            )
        except Exception:
            raise GroundingModelError("model_call_failed", 1) from None
        try:
            content = response.choices[0].message.content
            payload, repairs = repair_column_refs(json.loads(content), model)
            self.last_repairs = repairs
            return PlanProposal.model_validate(payload)
        except (AttributeError, IndexError, TypeError, ValueError, ValidationError):
            raise GroundingModelError("invalid_structured_output", 1) from None
