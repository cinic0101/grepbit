"""The wire contract: what the planner is shown, and the shapes it may write.

Contract v2 (2026-09-11). The model kept flattening the nesting the domain
models describe: a ratio's ``numerator`` beside ``ratio`` instead of inside
it, a ``ColumnRef`` with a redundant sibling ``table``, dimensions written
like ``order_by`` items, aliases on dimensions. Each was a repair, each
repair a guess about the next one. The contract now runs the other way:
the schema shown to the model is a compact, flat form built around what it
writes (columns as ``table.column`` strings, ``numerator`` and
``denominator`` directly on the measure, no titles or docstrings), and the
normaliser accepts a documented superset of that form and rewrites it to
the domain models. Deviations from the shown form are still counted
(``shape_repairs``) so the alignment of contract and model stays measured.
"""

from __future__ import annotations

import json
import re
from typing import Any

from grepbit.domain.plan import is_output_name

WIRE_REVISION = "wire-v2"

_IDENT = "[A-Za-z_][A-Za-z0-9_$]*"
_COLUMN = {"type": "string", "pattern": f"^{_IDENT}\\.{_IDENT}$"}
_UNIT = {"enum": ["day", "week", "month", "quarter", "year"]}
_FILTER = {
    "type": "object",
    "required": ["column", "op"],
    "additionalProperties": False,
    "properties": {
        "column": _COLUMN,
        "op": {
            "enum": ["eq", "ne", "in", "gt", "gte", "lt", "lte", "is_null", "not_null"]
        },
        "values": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
    },
}
_OPERAND_PROPERTIES = {
    "aggregate": {"enum": ["sum", "count", "count_distinct", "avg", "min", "max"]},
    "column": _COLUMN,
    "metric": {"type": "string"},
    "filters": {"type": "array", "items": _FILTER, "maxItems": 2},
}
_OPERAND = {
    "type": "object",
    "additionalProperties": False,
    "properties": _OPERAND_PROPERTIES,
}
_MEASURE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **_OPERAND_PROPERTIES,
        "alias": {"type": "string", "maxLength": 63},
        "share_of_total": {"type": "boolean"},
        "numerator": _OPERAND,
        "denominator": _OPERAND,
    },
}
_MONTH = {
    "type": "object",
    "required": ["kind", "month"],
    "properties": {"kind": {"const": "month"}, "month": {"type": "string"}},
}
_SCOPE = {
    "oneOf": [
        _MONTH,
        {
            "type": "object",
            "required": ["kind", "start", "end_exclusive"],
            "properties": {
                "kind": {"const": "range"},
                "start": {"type": "string"},
                "end_exclusive": {"type": "string"},
            },
        },
        {
            "type": "object",
            "required": ["kind", "unit", "offset", "length"],
            "properties": {
                "kind": {"const": "relative"},
                "unit": _UNIT,
                "offset": {"type": "integer"},
                "length": {"type": "integer", "minimum": 1},
                "to_date": {"type": "boolean"},
            },
        },
        {
            "type": "object",
            "required": ["kind", "unit"],
            "properties": {"kind": {"const": "latest"}, "unit": _UNIT},
        },
        {
            "type": "object",
            "required": ["kind", "periods"],
            "properties": {
                "kind": {"const": "periods"},
                "periods": {"type": "array", "items": _MONTH},
            },
        },
    ]
}
_TIME = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"column": _COLUMN, "scope": _SCOPE, "grain": _UNIT},
}
_PLAN = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "base_table": {"type": "string"},
        "measures": {"type": "array", "items": _MEASURE, "maxItems": 4},
        "dimensions": {"type": "array", "items": _COLUMN, "maxItems": 3},
        "filters": {"type": "array", "items": _FILTER, "maxItems": 6},
        "time": _TIME,
        "order": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["field"],
                "properties": {
                    "field": {"type": "string"},
                    "direction": {"enum": ["asc", "desc"]},
                },
            },
        },
        "having": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["field", "op", "value"],
                "properties": {
                    "field": {"type": "string"},
                    "op": {"enum": ["gt", "gte", "lt", "lte", "eq", "ne"]},
                    "value": {"type": "number"},
                },
            },
        },
        "growth": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["measure"],
                "properties": {"measure": {"type": "string"}},
            },
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        "without": {
            "type": "object",
            "required": ["table"],
            "properties": {
                "table": {"type": "string"},
                "filters": {"type": "array", "items": _FILTER, "maxItems": 4},
                "time": _TIME,
            },
        },
        "latest": {
            "type": "object",
            "required": ["order_by", "take"],
            "properties": {
                "order_by": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": ["column"],
                        "properties": {
                            "column": _COLUMN,
                            "direction": {"enum": ["asc", "desc"]},
                        },
                    },
                },
                "take": {"type": "array", "items": _COLUMN, "maxItems": 4},
            },
        },
    },
}
_PROPOSAL = {
    "type": "object",
    "required": ["decision"],
    "additionalProperties": False,
    "properties": {
        "decision": {"enum": ["plan", "none"]},
        "plan": _PLAN,
        "reason": {"enum": ["semantic_gap", "unsupported", "ambiguous"]},
        "clarification": {"type": "string"},
    },
}


def shown_schema() -> dict[str, Any]:
    """The JSON Schema the planner is asked to conform to (the preferred form)."""

    return json.loads(json.dumps(_PROPOSAL))


def shown_schema_text() -> str:
    return json.dumps(_PROPOSAL, sort_keys=True, separators=(",", ":"))


_REFERENCE_KEYS = {"table", "column"}
_DIMENSION_EXTRAS = {"alias", "description", "label", "name"}


def _is_reference(node: Any) -> bool:
    return (
        isinstance(node, dict)
        and set(node) == _REFERENCE_KEYS
        and all(isinstance(node[k], str) for k in _REFERENCE_KEYS)
    )


def normalize_variants(plan: dict[str, Any], repairs: list[str]) -> None:
    """Rewrite the accepted variants of the wire form into the domain form.

    Every rewrite here is a shape the model has written and the contract
    accepts; none guesses meaning. Each one is recorded in ``repairs`` so the
    distance between the shown form and what the model writes stays visible.
    """

    # a grain written on the plan instead of inside time
    grain = plan.pop("grain", None)
    if isinstance(grain, str):
        time = plan.get("time")
        if not isinstance(time, dict):
            time = plan["time"] = {}
        time.setdefault("grain", grain)
        repairs.append("plan.grain moved into time.grain")

    # numerator and denominator written on the plan beside spelled-out measures
    # (holdout 2 q23): the ratio is the measure asked for, the spelled-out
    # operands are the same thing twice
    if isinstance(plan.get("numerator"), dict) and isinstance(
        plan.get("denominator"), dict
    ):
        numerator, denominator = plan.pop("numerator"), plan.pop("denominator")
        measures = plan.get("measures")
        if not isinstance(measures, list):
            measures = plan["measures"] = []
        kept = [
            m
            for m in measures
            if not (
                isinstance(m, dict)
                and _core(m) in (_core(numerator), _core(denominator))
            )
        ]
        if len(kept) != len(measures):
            repairs.append("dropped measures spelled inside the plan-level ratio")
        kept.append({"numerator": numerator, "denominator": denominator})
        plan["measures"] = kept
        repairs.append("lifted plan-level numerator/denominator into a measure")

    for index, item in enumerate(plan.get("measures") or []):
        if not isinstance(item, dict):
            continue
        # an aggregate and column beside numerator/denominator that merely restate
        # one operand (the repair turn on q23) are dropped
        if (
            "numerator" in item
            and "denominator" in item
            and item.get("aggregate") is not None
            and any(
                _core(
                    {
                        k: item.get(k)
                        for k in ("aggregate", "column", "filters")
                        if k in item
                    }
                )
                == _core(item[side])
                for side in ("numerator", "denominator")
                if isinstance(item[side], dict)
            )
        ):
            for key in ("aggregate", "column", "filters"):
                item.pop(key, None)
            repairs.append("dropped aggregate restating a ratio operand")
        # an alias is written in the question's language and quoted by the
        # compiler (owner's decision 2026-09-11); only one that cannot be an
        # identifier at all (quotes, control characters, over 63 bytes) is
        # renamed, and the order, having and growth items that named it follow
        alias = item.get("alias")
        if isinstance(alias, str) and not is_output_name(alias):
            replacement = re.sub(r"[^A-Za-z0-9_$]", "", alias) or f"measure_{index + 1}"
            if not re.match(r"^[A-Za-z_]", replacement):
                replacement = f"m_{replacement}"
            item["alias"] = replacement
            for section, key in (
                ("order", "field"),
                ("having", "field"),
                ("growth", "measure"),
            ):
                for ref in plan.get(section) or []:
                    if isinstance(ref, dict) and ref.get(key) == alias:
                        ref[key] = replacement
            repairs.append(f"alias {alias!r} -> {replacement} (not quotable)")
        # numerator and denominator written on the measure (the shown form)
        # become the domain's ratio; a partial ratio beside them is completed
        operands = {k: item.pop(k) for k in ("numerator", "denominator") if k in item}
        if operands:
            ratio = item.get("ratio")
            if not isinstance(ratio, dict):
                ratio = item["ratio"] = {}
            for key, value in operands.items():
                if key in ratio:
                    repairs.append(
                        f"measure.{key} written twice, kept the one inside ratio"
                    )
                    continue
                ratio[key] = value
        _drop_redundant_sibling_table(item, repairs, "measures")
        ratio = item.get("ratio")
        if isinstance(ratio, dict):
            for key in ("numerator", "denominator"):
                if isinstance(ratio.get(key), dict):
                    _drop_redundant_sibling_table(ratio[key], repairs, f"ratio.{key}")

    dimensions = plan.get("dimensions")
    if isinstance(dimensions, list):
        for index, item in enumerate(dimensions):
            if not isinstance(item, dict):
                continue
            extras = set(item) & _DIMENSION_EXTRAS
            if extras and set(item) - _DIMENSION_EXTRAS <= {"column", "table"}:
                for key in extras:
                    del item[key]
                repairs.append("dimensions: dropped " + ", ".join(sorted(extras)))
            # a sibling table beside a wrapped reference is unwrapped later, in
            # the reference walk, as one variant

    for item in plan.get("filters") or []:
        if isinstance(item, dict):
            _drop_redundant_sibling_table(item, repairs, "filters")
    without = plan.get("without")
    if isinstance(without, dict):
        for item in without.get("filters") or []:
            if isinstance(item, dict):
                _drop_redundant_sibling_table(item, repairs, "without.filters")
    latest = plan.get("latest")
    if isinstance(latest, dict):
        for item in latest.get("order_by") or []:
            if isinstance(item, dict):
                _drop_redundant_sibling_table(item, repairs, "latest.order_by")


def _core(node: dict[str, Any]) -> str:
    """An operand without its alias, as a comparable string."""

    return json.dumps({k: v for k, v in node.items() if k != "alias"}, sort_keys=True)


def _drop_redundant_sibling_table(
    node: dict[str, Any], repairs: list[str], where: str
) -> None:
    """``{"column": {"table": t, "column": c}, "table": t}``: the sibling repeats
    the reference and is dropped; a sibling naming another table is left to fail."""

    column = node.get("column")
    table = node.get("table")
    if isinstance(table, str) and _is_reference(column) and column["table"] == table:
        del node["table"]
        repairs.append(f"{where}: dropped table beside the column reference")
