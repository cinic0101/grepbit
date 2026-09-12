"""Schema-driven plan generation for the differential and property tests.

Given any ``SchemaModel`` (and optionally an overlay), ``draw_plan`` builds a
QueryPlan payload from Hypothesis draws: a base table, raw or reviewed
measures with their own filters, ratios and shares, dimensions on the base or
on a parent reached through foreign keys, filters typed by column kind, a
time window or grain, having, growth, order and limit, and the two row
shapes (the latest row per group, entities with no activity). The generator
knows the plan's own rules only loosely; a payload the plan rejects is skipped
by the caller, a payload the compiler refuses with a typed error is a
legitimate outcome, and anything else is a finding.
"""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.schema_model import ColumnKind, SchemaModel

UNITS = ["day", "week", "month", "quarter", "year"]
NUMBERS = [0, 1, 5, 100]
FALLBACK_TEXT = ["x", "critical", "offline", "A"]


class SchemaShape:
    """What the generator may draw for one base table."""

    def __init__(self, schema: SchemaModel, overlay: SemanticOverlay | None = None):
        self.schema = schema
        self.overlay = overlay
        self.parents: dict[str, list[str]] = {}
        self.ambiguous: set[str] = set()
        for table in schema.tables:
            links = [fk for fk in schema.foreign_keys if fk.table == table.name]
            targets = [fk.referenced_table for fk in links]
            self.parents[table.name] = sorted(set(targets))
            if len(targets) != len(set(targets)):
                self.ambiguous.add(table.name)

    def reachable(self, base: str, hops: int = 3) -> list[str]:
        """The base and the tables a chain of foreign keys reaches from it."""

        seen, frontier = [base], [base]
        for _ in range(hops):
            step = []
            for table in frontier:
                if table in self.ambiguous and table != base:
                    continue
                for parent in self.parents.get(table, []):
                    if parent not in seen:
                        seen.append(parent)
                        step.append(parent)
            frontier = step
        return seen

    def columns(
        self, base: str, kinds: set[ColumnKind], *, keys: bool = False
    ) -> list[str]:
        out = []
        for name in self.reachable(base):
            table = self.schema.table(name)
            if table is None:
                continue
            for column in table.columns:
                if column.kind not in kinds:
                    continue
                if not keys and (
                    column.name in table.primary_key or column.name.endswith("_id")
                ):
                    continue
                out.append(f"{name}.{column.name}")
        return out

    def time_columns(self, base: str) -> list[str]:
        table = self.schema.table(base)
        return [
            f"{base}.{c.name}"
            for c in (table.columns if table else [])
            if c.kind in (ColumnKind.TIMESTAMP, ColumnKind.DATE)
        ]

    def text_values(self, column: str) -> list[str]:
        table_name, name = column.split(".")
        table = self.schema.table(table_name)
        col = table.column(name) if table else None
        return list(col.sample_values or FALLBACK_TEXT) if col else FALLBACK_TEXT

    def metrics(self, base: str) -> list[str]:
        if self.overlay is None:
            return []
        return [m.id for m in self.overlay.metrics if m.base_table == base]

    def children(self, base: str) -> list[str]:
        """Activity tables reaching the base, including multi-hop FK paths."""
        return sorted(
            table.name
            for table in self.schema.tables
            if table.name != base and base in self.reachable(table.name)
        )


def ref(column: str) -> dict[str, str]:
    table, name = column.split(".")
    return {"table": table, "column": name}


def draw_filters(data, shape: SchemaShape, base: str, at_most: int) -> list[dict]:
    text = shape.columns(base, {ColumnKind.TEXT})
    numeric = shape.columns(base, {ColumnKind.NUMERIC})
    nullable = shape.columns(
        base,
        {ColumnKind.TEXT, ColumnKind.NUMERIC, ColumnKind.TIMESTAMP, ColumnKind.DATE},
    )
    filters = []
    for _ in range(data.draw(st.integers(0, at_most))):
        options = (
            (["eq", "in"] if text else [])
            + (["cmp"] if numeric else [])
            + (["null"] if nullable else [])
        )
        if not options:
            break
        kind = data.draw(st.sampled_from(options))
        if kind == "eq":
            column = data.draw(st.sampled_from(text))
            filters.append(
                {
                    "column": ref(column),
                    "op": "eq",
                    "values": [data.draw(st.sampled_from(shape.text_values(column)))],
                }
            )
        elif kind == "in":
            column = data.draw(st.sampled_from(text))
            values = data.draw(
                st.lists(
                    st.sampled_from(shape.text_values(column)),
                    min_size=1,
                    max_size=3,
                    unique=True,
                )
            )
            filters.append({"column": ref(column), "op": "in", "values": values})
        elif kind == "cmp":
            column = data.draw(st.sampled_from(numeric))
            filters.append(
                {
                    "column": ref(column),
                    "op": data.draw(st.sampled_from(["gt", "gte", "lt", "lte", "ne"])),
                    "values": [data.draw(st.sampled_from(NUMBERS))],
                }
            )
        else:
            column = data.draw(st.sampled_from(nullable))
            filters.append(
                {
                    "column": ref(column),
                    "op": data.draw(st.sampled_from(["is_null", "not_null"])),
                }
            )
    return filters


def draw_operand(data, shape: SchemaShape, base: str) -> dict:
    numeric = shape.columns(base, {ColumnKind.NUMERIC})
    text = shape.columns(base, {ColumnKind.TEXT}, keys=True)
    times = shape.time_columns(base)
    metrics = shape.metrics(base)
    options = (
        ["count", "distinct"]
        + (["sum", "avg", "minmax"] if numeric else [])
        + (["metric"] if metrics else [])
    )
    kind = data.draw(st.sampled_from(options))
    if kind == "metric":
        operand: dict = {"metric": data.draw(st.sampled_from(metrics))}
    elif kind == "count":
        operand = {"aggregate": "count"}
        countable = shape.columns(base, set(ColumnKind) - {ColumnKind.OTHER}, keys=True)
        if countable and data.draw(st.booleans()):
            operand["column"] = ref(data.draw(st.sampled_from(countable)))
    elif kind == "distinct":
        operand = {
            "aggregate": "count_distinct",
            "column": ref(data.draw(st.sampled_from(text))),
        }
    elif kind == "minmax":
        operand = {
            "aggregate": data.draw(st.sampled_from(["min", "max"])),
            "column": ref(data.draw(st.sampled_from(numeric + times))),
        }
    else:
        operand = {
            "aggregate": kind,
            "column": ref(data.draw(st.sampled_from(numeric))),
        }
    if data.draw(st.integers(0, 2)) == 0:
        own = draw_filters(data, shape, base, 1)
        if own:
            operand["filters"] = own
    return operand


def draw_measure(data, shape: SchemaShape, base: str, index: int) -> dict:
    if data.draw(st.integers(0, 3)) == 0:
        measure = {
            "alias": f"m{index}",
            "ratio": {
                "numerator": draw_operand(data, shape, base),
                "denominator": draw_operand(data, shape, base),
            },
        }
    else:
        measure = {**draw_operand(data, shape, base), "alias": f"m{index}"}
    if data.draw(st.integers(0, 3)) == 0:
        measure["share_of_total"] = True
    return measure


def draw_scope(data) -> dict | None:
    kind = data.draw(
        st.sampled_from(["month", "range", "relative", "to_date", "latest", "periods"])
    )
    if kind == "month":
        return {
            "kind": "month",
            "month": data.draw(st.sampled_from(["2026-06", "2026-07", "2025-12"])),
        }
    if kind == "range":
        return {
            "kind": "range",
            "start": "2026-06-01",
            "end_exclusive": data.draw(st.sampled_from(["2026-07-01", "2026-08-01"])),
        }
    if kind == "relative":
        return {
            "kind": "relative",
            "unit": data.draw(st.sampled_from(UNITS)),
            "offset": data.draw(st.integers(-6, 0)),
            "length": data.draw(st.integers(1, 3)),
        }
    if kind == "to_date":
        return {
            "kind": "relative",
            "unit": data.draw(st.sampled_from(UNITS)),
            "offset": 0,
            "length": 1,
            "to_date": True,
        }
    if kind == "latest":
        return {"kind": "latest", "unit": data.draw(st.sampled_from(UNITS))}
    return {
        "kind": "periods",
        "periods": [
            {"kind": "month", "month": "2026-06"},
            {"kind": "month", "month": "2026-07"},
        ],
    }


def draw_time(
    data, shape: SchemaShape, base: str, *, window_only: bool = False
) -> dict | None:
    times = shape.time_columns(base)
    if data.draw(st.integers(0, 3)) == 0:
        return None
    time: dict = {}
    default = shape.overlay.time_default(base) if shape.overlay is not None else None
    if times and (default is None or data.draw(st.booleans())):
        time["column"] = ref(data.draw(st.sampled_from(times)))
    elif default is None:
        return None
    if window_only or data.draw(st.integers(0, 4)) > 0:
        time["scope"] = draw_scope(data)
    if not window_only and (("scope" not in time) or data.draw(st.booleans())):
        time["grain"] = data.draw(st.sampled_from(UNITS))
    return time


def draw_plan(data, shape: SchemaShape) -> dict[str, Any]:
    """One plan payload over ``shape``'s schema (may still fail plan validation)."""

    bases = [t.name for t in shape.schema.tables if t.name not in shape.ambiguous]
    base = data.draw(st.sampled_from(bases))
    dimensions = shape.columns(base, {ColumnKind.TEXT})
    kind = data.draw(st.sampled_from(["aggregate"] * 6 + ["latest", "without"]))
    plan: dict[str, Any] = {"base_table": base}
    if kind == "latest" and shape.time_columns(base):
        plan["dimensions"] = (
            [
                ref(c)
                for c in data.draw(
                    st.lists(st.sampled_from(dimensions), min_size=1, max_size=1)
                )
            ]
            if dimensions
            else []
        )
        order_column = data.draw(st.sampled_from(shape.time_columns(base)))
        take = shape.columns(
            base,
            {
                ColumnKind.NUMERIC,
                ColumnKind.TEXT,
                ColumnKind.TIMESTAMP,
                ColumnKind.DATE,
            },
            keys=True,
        )
        take = [c for c in take if c.startswith(base + ".")]
        plan["latest"] = {
            "order_by": [{"column": ref(order_column), "direction": "desc"}],
            "take": [
                ref(c)
                for c in data.draw(
                    st.lists(st.sampled_from(take), min_size=1, max_size=2, unique=True)
                )
            ],
        }
        plan["filters"] = draw_filters(data, shape, base, 1)
        window = draw_time(data, shape, base, window_only=True)
        if window and window.get("scope"):
            plan["time"] = window
        return plan
    if kind == "without" and shape.children(base):
        child = data.draw(st.sampled_from(shape.children(base)))
        without: dict = {"table": child}
        child_filters = draw_filters(data, shape, child, 1)
        child_filters = [f for f in child_filters if f["column"]["table"] == child]
        if child_filters:
            without["filters"] = child_filters
        window = draw_time(data, shape, child, window_only=True)
        if (
            window
            and window.get("scope")
            and window.get("column", {}).get("table", child) == child
        ):
            without["time"] = window
        plan["without"] = without
        # Absence selects base rows; exercise the ordinary measures, periods
        # and output selection below instead of generating only COUNT.
    plan["measures"] = [
        draw_measure(data, shape, base, i) for i in range(data.draw(st.integers(1, 2)))
    ]
    plan["dimensions"] = (
        [
            ref(c)
            for c in data.draw(
                st.lists(st.sampled_from(dimensions), max_size=2, unique=True)
            )
        ]
        if dimensions
        else []
    )
    time = draw_time(data, shape, base)
    if time is not None:
        plan["time"] = time
    plan["filters"] = draw_filters(data, shape, base, 2)
    outputs = [d["column"] for d in plan["dimensions"]] + [
        m["alias"] for m in plan["measures"]
    ]
    if time is not None and time.get("grain"):
        outputs.append("period_start")
        if data.draw(st.booleans()):
            plan["growth"] = [{"measure": plan["measures"][0]["alias"]}]
    if data.draw(st.integers(0, 3)) == 0:
        plain = [
            m
            for m in plan["measures"]
            if "ratio" not in m and not m.get("share_of_total")
        ]
        if plain:
            plan["having"] = [
                {
                    "field": plain[0]["alias"],
                    "op": data.draw(st.sampled_from(["gt", "gte", "lt"])),
                    "value": data.draw(st.sampled_from(NUMBERS)),
                }
            ]
    if data.draw(st.booleans()):
        plan["order"] = [
            {
                "field": data.draw(st.sampled_from(outputs)),
                "direction": data.draw(st.sampled_from(["asc", "desc"])),
            }
        ]
        if data.draw(st.booleans()):
            plan["limit"] = data.draw(st.integers(1, 50))
    return plan
