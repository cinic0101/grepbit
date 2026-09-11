"""Chat Completions client that turns a question into a tier-0 QueryPlan."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from grepbit.adapters.litellm.plan_wire import normalize_variants, shown_schema_text
from grepbit.application.text import phrase_in
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import Filter, Measure, PlanProposal, PreviousTurn, QueryPlan
from grepbit.domain.schema_model import SchemaModel
from grepbit.ports.ask import RELATIVE_WINDOW_REPAIR
from grepbit.ports.grounding import GroundingModelError

PLAN_PROMPT_REVISION = "plan-classify-json-v14"

_RULES_ALL = (
    "You translate one analytics question into ONE aggregate query plan over the "
    "given PostgreSQL schema, or decline. Output only JSON matching the schema. "
    "Rules: "
    "(1) Use only table and column names that appear in the schema; never invent "
    'names. Write every column reference as the string "table.column". '
    "base_table is the table whose rows are being counted or summed. "
    "(2) measures: aggregate is one of sum, count, count_distinct, avg, min, max; "
    "count without a column counts rows. sum and avg need numeric columns. A "
    "share or percentage of the total (佔比, 比例, share of) is the same measure "
    'with "share_of_total": true; the server divides each group by the total over '
    "all groups (within each period when there is a grain). Use it only when the "
    "question groups by something (each store's share); the share of a subset "
    "in the whole (member transactions among all transactions) is a ratio whose "
    "numerator is a metric or an aggregate the question restricts and whose "
    "denominator is the same aggregate unrestricted. A rate or ratio of "
    "two aggregates (退貨率, 客單價 as amount per transaction, conversion rate) is "
    'one measure with "numerator": {aggregate/column or metric, optional filters} '
    'and "denominator": {...} over the same base table; an operand\'s own filters '
    "restrict that aggregate alone. base_table may be omitted when the measure columns "
    "or metrics determine it. "
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
    "trend or compares periods. Only when the question asks for growth, a rate of "
    'change or 成長率 add "growth": [{"measure": <output name>}] with a grain; the '
    "server computes (current - previous) / previous. A question that merely "
    "compares periods wants the per-period values, no growth. time.column "
    "may be omitted when the table lists a default_time_column. A question that "
    "asks for a value per period "
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
    "(8) Entities with no activity (哪些商品從未出現在銷售明細, 沒有任何交易的門市, "
    "沒有銷售紀錄的店員, products never sold, stores without orders): base_table "
    "is the entity table, dimensions its name column, measures "
    '[{"aggregate": "count", "alias": "<entity>_count"}], and "without": '
    '{"table": <the child table whose rows must be absent>, "filters": [...], '
    '"time": {"column": ..., "scope": ...}} carrying the window and filters that '
    "describe the missing activity (time has a scope, no grain). Never express "
    "this as having count = 0; a group that exists always has rows. "
    "(9) The latest row per entity (每位店員最新一筆交易的金額與日期, each product's "
    "last sale date and quantity, 最近一筆): base_table is the table holding the "
    "rows, dimensions the entity's name column, measures [], and "
    '"latest": {"order_by": [{"column": <time column>, "direction": "desc"}, '
    "<the tie-breaker the question names, such as the transaction number>], "
    '"take": [<columns to return from that row>]}; filters and time still say '
    "which rows qualify. Do not aggregate for such a question. "
    "(10) The most recent period that has data (最新營業日, the last month with "
    'sales) is the time scope {"kind": "latest", "unit": "day"|"week"|"month"|'
    '"quarter"|"year"}; the server finds the latest unit with rows after the '
    "filters, so never guess a date for it. "
    "(11) Return only one JSON object."
)
_PACK_MARKERS = {
    "without": "(8) Entities with no activity",
    "latest": "(9) The latest row per entity",
    "latest_period": "(10) The most recent period that has data",
}
_CLOSING_RULE = "(11) Return only one JSON object."


def _split_rules() -> tuple[str, dict[str, str], str]:
    starts = {key: _RULES_ALL.index(marker) for key, marker in _PACK_MARKERS.items()}
    closing = _RULES_ALL.index(_CLOSING_RULE)
    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    ends = [start for _, start in ordered[1:]] + [closing]
    packs = {key: _RULES_ALL[start:end] for (key, start), end in zip(ordered, ends)}
    return _RULES_ALL[: ordered[0][1]], packs, _RULES_ALL[closing:]


_RULES_CORE, _RULE_PACKS, _RULES_CLOSING = _split_rules()
_RULE_TRIGGERS: dict[str, list[str]] | None = None


def _triggers() -> dict[str, list[str]]:
    global _RULE_TRIGGERS
    if _RULE_TRIGGERS is None:
        _RULE_TRIGGERS = dict(load_shape_pack().rule_triggers)
    return _RULE_TRIGGERS


def rules_for(question: str) -> str:
    """The core rules plus the packs the question's words switch on.

    Rules 8 to 10 (entities with no activity, the latest row per entity, the
    latest period with data) enter the prompt only when the question carries
    one of their trigger words (``unsupported_shapes.json``, ``rule_triggers``);
    a rule the question does not need is prompt length and shape risk.
    """

    packs = "".join(
        text
        for key, text in _RULE_PACKS.items()
        if any(phrase_in(question, word) for word in _triggers().get(key, []))
    )
    return _RULES_CORE + packs + _RULES_CLOSING


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


def _anchor_relative_window(plan: dict[str, Any], repairs: list[str]) -> None:
    """Read "offset 0, length L > 1" as the last L complete units before as_of.

    Anchored on the current unit and longer than it, such a window reaches
    into the future, where no data can be (最近 30 天 written as offset 0
    length 30 covered today and the next 29 days). The only reading with data
    is the past one, offset -L, the encoding the prompt gives for "last L
    units"; "to date" windows are left alone.
    """

    time = plan.get("time")
    scope = time.get("scope") if isinstance(time, dict) else None
    if not isinstance(scope, dict) or scope.get("kind") != "relative":
        return
    offset, length = scope.get("offset"), scope.get("length")
    if offset != 0 or not isinstance(length, int) or length <= 1:
        return
    if scope.get("to_date"):
        return
    scope["offset"] = -length
    repairs.append(
        f"{RELATIVE_WINDOW_REPAIR} offset 0 length {length} -> offset {-length}"
    )


def _unit_from_grain(plan: dict[str, Any], repairs: list[str]) -> None:
    """A relative window that names no unit takes the grain written beside it.

    本月截至今天 came back as {"grain": "month", "scope": {"kind": "relative",
    "offset": 0, "length": 1, "to_date": true}}: the unit is the grain.
    Without a grain nothing is guessed and validation fails as before.
    """

    time = plan.get("time")
    if not isinstance(time, dict):
        return
    scope, grain = time.get("scope"), time.get("grain")
    if not isinstance(scope, dict) or scope.get("kind") != "relative":
        return
    if "unit" in scope or not isinstance(grain, str):
        return
    scope["unit"] = grain
    repairs.append(f"relative window without unit -> unit {grain} (from grain)")


def _drop_aggregate_beside_ratio(plan: dict[str, Any], repairs: list[str]) -> None:
    """A ratio measure that also names a bare aggregate keeps only the ratio.

    The model writes {"aggregate": "count", "ratio": {...}} for 會員交易佔比:
    the operands inside the ratio carry their own aggregates, the sibling is
    a duplicate the validator rejects (``plan_measure_ratio_excludes_aggregate``).
    Only a bare aggregate (no column, no metric) is dropped; anything else
    stays ambiguous and fails validation as before.
    """

    for item in plan.get("measures") or []:
        if not isinstance(item, dict) or not isinstance(item.get("ratio"), dict):
            continue
        if "aggregate" in item and "column" not in item and "metric" not in item:
            dropped = item.pop("aggregate")
            repairs.append(f"dropped aggregate {dropped} beside ratio")


def _lift_plan_level_ratio(plan: dict[str, Any], repairs: list[str]) -> None:
    """A ``ratio`` written on the plan instead of inside a measure becomes one.

    For 會員交易佔比 the model sometimes spells the two operands out as
    measures and then writes the ratio beside ``measures`` at the plan level,
    a key the plan does not have. The ratio is the measure the question asks
    for: it moves into ``measures`` and any measure that is exactly one of its
    operands (same aggregate, column, metric and filters; the alias aside)
    is dropped as the same thing spelled twice. Nothing moves when a measure
    already carries a ratio; that plan fails validation as before.
    """

    ratio = plan.get("ratio")
    if not isinstance(ratio, dict) or not (
        isinstance(ratio.get("numerator"), dict)
        and isinstance(ratio.get("denominator"), dict)
    ):
        return
    measures = plan.get("measures")
    if measures is None:
        measures = plan["measures"] = []
    if not isinstance(measures, list) or any(
        isinstance(m, dict) and "ratio" in m for m in measures
    ):
        return

    def core(node: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in node.items() if k != "alias"}

    operands = [core(ratio["numerator"]), core(ratio["denominator"])]
    kept: list[Any] = []
    for item in measures:
        if isinstance(item, dict) and core(item) in operands:
            name = item.get("alias") or core(item)
            repairs.append(f"dropped measure {name} spelled inside the ratio")
            continue
        kept.append(item)
    kept.append({"ratio": plan.pop("ratio")})
    plan["measures"] = kept
    repairs.append("lifted plan-level ratio into a measure")


def _is_column_ref(node: dict[str, Any]) -> bool:
    return set(node) == {"table", "column"} and all(
        isinstance(node[k], str) for k in ("table", "column")
    )


def _strip_qualifier(ref: dict[str, Any], repairs: list[str]) -> None:
    """{"table": "t", "column": "t.c"} -> {"table": "t", "column": "c"}: the model
    qualified the column name inside a reference that already names the table."""

    if ref["column"].startswith(ref["table"] + "."):
        repairs.append(f"{ref['column']} -> {ref['column'].split('.', 1)[1]}")
        ref["column"] = ref["column"].split(".", 1)[1]


def _repair_refs(node: Any, model: SchemaModel, base_table, repairs, coerce, key=None):
    """Walk the whole plan and mend column references wherever they sit.

    A reference dict that qualifies its own column loses the prefix; an item
    that names a column as a string beside a sibling ``table`` key (measures,
    filters, latest.order_by) is folded into a reference when that table owns
    the column; any other string column (measures, filters, dimensions, time,
    ratio operands, without, latest.take) is coerced when the name resolves to
    exactly one table. Meaning is never guessed: anything still ambiguous fails
    validation as before.
    """

    if isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, str) and key in ("dimensions", "take"):
                node[index] = coerce(item)
            elif (
                key in ("dimensions", "take")
                and isinstance(item, dict)
                and isinstance(item.get("column"), dict)
                and _is_column_ref(item["column"])
                and set(item) <= {"column", "table"}
            ):
                # {"column": {"table": t, "column": c}, "table": t}: a reference
                # wrapped the way order_by items are written; the inner reference
                # is the whole meaning
                node[index] = item["column"]
                repairs.append(f"{key}: unwrapped column reference")
                _strip_qualifier(node[index], repairs)
            else:
                _repair_refs(item, model, base_table, repairs, coerce, key)
        return
    if not isinstance(node, dict):
        return
    if _is_column_ref(node):
        _strip_qualifier(node, repairs)
        return
    if "column" in node:
        column = node["column"]
        if isinstance(column, dict) and _is_column_ref(column):
            _strip_qualifier(column, repairs)
        elif isinstance(column, str):
            table = node.get("table")
            if isinstance(table, str) and "." not in column:
                owner = model.table(table)
                if owner is not None and owner.column(column) is not None:
                    del node["table"]
                    repairs.append(f"{column} + table {table} -> {table}.{column}")
                    node["column"] = {"table": table, "column": column}
                # a sibling table that does not own the column is left alone:
                # the extra key fails validation instead of being guessed away
            else:
                node["column"] = coerce(column)
    for child_key, value in list(node.items()):
        if child_key == "column":
            continue
        _repair_refs(value, model, base_table, repairs, coerce, child_key)


def _output_names(plan: dict[str, Any]) -> set[str]:
    """Output names a plan can be ordered or filtered by, read from the dict."""

    names: set[str] = set()
    for item in plan.get("dimensions") or []:
        if isinstance(item, dict) and isinstance(item.get("column"), str):
            names.add(item["column"])
    for item in plan.get("measures") or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("alias"), str):
            names.add(item["alias"])
        elif isinstance(item.get("metric"), str):
            names.add(item["metric"])
    latest = plan.get("latest")
    if isinstance(latest, dict):
        for ref in latest.get("take") or []:
            if isinstance(ref, dict) and isinstance(ref.get("column"), str):
                names.add(ref["column"])
    time = plan.get("time")
    if isinstance(time, dict) and time.get("grain"):
        names.add("period_start")
    return names


def _strip_qualified_fields(plan: dict[str, Any], repairs: list[str]) -> None:
    """order.field "store.store_name" -> "store_name" when that is an output name.

    Order, having and growth refer to outputs by name; the model sometimes
    qualifies them like columns. The prefix is dropped only when the bare
    name is an output the plan produces, so nothing is guessed.
    """

    names = _output_names(plan)
    for section, key in (
        ("order", "field"),
        ("having", "field"),
        ("growth", "measure"),
    ):
        for item in plan.get(section) or []:
            value = item.get(key) if isinstance(item, dict) else None
            if isinstance(value, str) and "." in value:
                bare = value.rsplit(".", 1)[1]
                if bare in names:
                    item[key] = bare
                    repairs.append(f"{section}.{key} {value} -> {bare}")


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
    normalize_variants(plan, repairs)
    time = plan.get("time")
    if (
        isinstance(time, dict)
        and time.get("scope") is None
        and time.get("grain") is None
    ):
        # a time column named without a window or a grain constrains nothing
        del plan["time"]
        repairs.append("dropped time without scope or grain")
    _unit_from_grain(plan, repairs)
    _anchor_relative_window(plan, repairs)
    _drop_aggregate_beside_ratio(plan, repairs)
    _lift_plan_level_ratio(plan, repairs)
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
        if "." not in value:
            # a bare name resolved to one table is a variant of the shown form
            repairs.append(f"{value} -> {candidates[0]}.{column}")
        return {"table": candidates[0], "column": column}

    without = plan.get("without")
    if isinstance(without, dict):
        w_time = without.get("time")
        if (
            isinstance(w_time, dict)
            and w_time.get("scope") is None
            and w_time.get("grain") is None
        ):
            del without["time"]
            repairs.append("dropped without.time without scope")
    _repair_refs(plan, model, base_table, repairs, coerce)
    _strip_qualified_fields(plan, repairs)
    return payload, repairs


_REPAIR_INSTRUCTION = (
    "The JSON object you returned did not validate against the schema. "
    "Errors: {errors}. Return the complete corrected JSON object and nothing "
    "else: keep the same tables, columns, filters and values, fix only the "
    "structure."
)


class _InvalidOutput(Exception):
    def __init__(self, errors: str) -> None:
        super().__init__(errors)
        self.errors = errors


def _validation_summary(error: ValidationError) -> str:
    parts = [
        ".".join(str(x) for x in item["loc"]) + ": " + item["msg"]
        for item in error.errors()[:8]
    ]
    return "; ".join(parts)[:1200]


def _content(response: Any) -> str | None:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError):
        return None
    return content if isinstance(content, str) else None


class ChatCompletionsPlanClient:
    """One strict call per question, plus one repair turn when the plan fails
    validation; the server validates every identifier."""

    last_repairs: list[str] = []
    # the model's text the first time it failed validation, kept even when the
    # repair turn then succeeded, so the slip can be classified
    last_raw_output: str | None = None
    # the repair turn's text when it failed too
    last_repair_output: str | None = None
    # 1 when the plan came from the repair turn or the repair turn also failed
    last_model_repair_turns: int = 0

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
        schema = shown_schema_text()
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
        rules = rules_for(question) + (_OVERLAY_RULE if overlay is not None else "")
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
        self.last_raw_output = None
        self.last_repair_output = None
        self.last_model_repair_turns = 0
        messages = self.build_messages(
            question,
            model,
            as_of=as_of,
            overlay=overlay,
            previous=previous,
            question_values=question_values,
        )
        content = self._complete(client, messages)
        try:
            return self._validate(content, model)
        except _InvalidOutput as first:
            self.last_raw_output = content
            if self._settings.repair_turns < 1 or content is None:
                raise GroundingModelError("invalid_structured_output", 1) from None
            errors = first.errors
        # the repair turn: the model sees its own text and the validation
        # errors, and returns the corrected object; meaning must not change
        repair_messages = [
            *messages,
            {"role": "assistant", "content": content},
            {"role": "user", "content": _REPAIR_INSTRUCTION.format(errors=errors)},
        ]
        self.last_model_repair_turns = 1
        repaired = self._complete(client, repair_messages)
        try:
            return self._validate(repaired, model)
        except _InvalidOutput:
            self.last_repair_output = repaired
            raise GroundingModelError("invalid_structured_output", 2) from None

    def _complete(self, client: Any, messages: list[dict[str, str]]) -> str | None:
        try:
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=messages,
                temperature=self._settings.temperature,
                max_tokens=max(self._settings.max_tokens, 768),
                response_format=self.response_format(),
            )
        except Exception:
            raise GroundingModelError("model_call_failed", 1) from None
        return _content(response)

    def _validate(self, content: str | None, model: SchemaModel) -> PlanProposal:
        if content is None:
            raise _InvalidOutput("empty response")
        try:
            payload = json.loads(content)
        except ValueError as error:
            raise _InvalidOutput(f"not valid JSON: {error}") from None
        try:
            payload, repairs = repair_column_refs(payload, model)
            self.last_repairs = repairs
            return PlanProposal.model_validate(payload)
        except ValidationError as error:
            raise _InvalidOutput(_validation_summary(error)) from None
        except (AttributeError, TypeError, ValueError) as error:
            raise _InvalidOutput(f"{type(error).__name__}: {error}") from None
