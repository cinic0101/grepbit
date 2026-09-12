"""Generated plans (root-cause program, B3).

Every plan the generator builds over the IoT fixture either compiles to SQL
that passes the policy and the serve-time self-check, or raises a typed
``PlanError`` other than ``self_check_failed``; never a Python exception, never
an invariant violation. The generator draws measure kinds, row constructs and
time shapes independently, so the construct matrix of the contract
(`docs/knowledge/tier0-contract.md`) is exercised pairwise and beyond.
``GREPBIT_PROPERTY_EXAMPLES`` raises the example count for a long run.
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import PlanError, QueryPlan

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, assume, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

SCHEMA = iot_schema()
OVERLAY = SemanticOverlay.model_validate(
    {
        "datasource_id": "iot_test",
        "revision": "property-1",
        "metrics": [
            {
                "id": "critical_alerts",
                "names": ["嚴重告警"],
                "description": "count of critical alerts",
                "base_table": "alerts",
                "aggregate": "count",
                "review_state": "verified",
                "filters": [
                    {
                        "column": {"table": "alerts", "column": "severity"},
                        "op": "eq",
                        "values": ["critical"],
                    }
                ],
            },
            {
                "id": "all_alerts",
                "names": ["告警數"],
                "description": "count of alerts",
                "base_table": "alerts",
                "aggregate": "count",
            },
            {
                "id": "downtime",
                "names": ["停機分鐘"],
                "description": "sum of downtime minutes",
                "base_table": "alerts",
                "aggregate": "sum",
                "column": {"table": "alerts", "column": "downtime_minutes"},
                "review_state": "verified",
            },
        ],
        "time_defaults": [
            {"table": "alerts", "column": {"table": "alerts", "column": "raised_at"}}
        ],
        "segments": [
            {
                "id": "retired",
                "names": ["retired", "已汰換"],
                "table": "devices",
                "filter": {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["retired"],
                },
                "default_exclude": True,
                "note": "retired devices are left out unless asked for",
            }
        ],
    }
)
POLICY = PostgresSqlPolicy(
    tables=frozenset(t.name for t in SCHEMA.tables),
    functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
)
COMPILER = PlanCompiler(SCHEMA, overlay=OVERLAY)

BASES = ["alerts", "readings", "devices"]
NUMERIC = {
    "alerts": ["alerts.downtime_minutes"],
    "readings": ["readings.temperature_c"],
    "devices": ["devices.monthly_fee"],
}
TEXT = {
    "alerts": ["alerts.severity", "devices.model", "devices.status", "sites.site_name"],
    "readings": ["devices.model", "devices.status", "sites.site_name"],
    "devices": ["devices.model", "devices.status", "sites.site_name"],
}
NULLABLE = {
    "alerts": ["alerts.resolved_at", "alerts.related_device_id", "devices.site_id"],
    "readings": ["readings.temperature_c", "devices.site_id"],
    "devices": ["devices.site_id", "devices.installed_on"],
}
TIME_COLUMNS = {
    "alerts": ["alerts.raised_at", "alerts.resolved_at"],
    "readings": ["readings.measured_at"],
    "devices": ["devices.installed_on"],
}
DIMENSIONS = {
    "alerts": ["devices.model", "devices.status", "sites.site_name", "alerts.severity"],
    "readings": ["devices.model", "sites.site_name"],
    "devices": ["devices.model", "devices.status", "sites.site_name"],
}
UNITS = ["day", "week", "month", "quarter", "year"]
VALUES = {
    "text": ["critical", "warning", "AP-300", "offline", "x y"],
    "number": [0, 5, 100],
}


def ref(column: str) -> dict:
    table, name = column.split(".")
    return {"table": table, "column": name}


def draw_filters(data, base: str, at_most: int) -> list[dict]:
    filters = []
    for _ in range(data.draw(st.integers(0, at_most))):
        kind = data.draw(st.sampled_from(["eq", "in", "gt", "null"]))
        if kind == "eq":
            column = data.draw(st.sampled_from(TEXT[base]))
            filters.append(
                {
                    "column": ref(column),
                    "op": "eq",
                    "values": [data.draw(st.sampled_from(VALUES["text"]))],
                }
            )
        elif kind == "in":
            column = data.draw(st.sampled_from(TEXT[base]))
            values = data.draw(
                st.lists(st.sampled_from(VALUES["text"]), min_size=1, max_size=3)
            )
            filters.append({"column": ref(column), "op": "in", "values": values})
        elif kind == "gt":
            column = data.draw(st.sampled_from(NUMERIC[base]))
            op = data.draw(st.sampled_from(["gt", "gte", "lt", "lte", "ne"]))
            filters.append(
                {
                    "column": ref(column),
                    "op": op,
                    "values": [data.draw(st.sampled_from(VALUES["number"]))],
                }
            )
        else:
            column = data.draw(st.sampled_from(NULLABLE[base]))
            filters.append(
                {
                    "column": ref(column),
                    "op": data.draw(st.sampled_from(["is_null", "not_null"])),
                }
            )
    return filters


def draw_operand(data, base: str) -> dict:
    kind = data.draw(
        st.sampled_from(["count", "sum", "avg", "minmax", "distinct", "metric"])
    )
    operand: dict
    if kind == "metric" and base == "alerts":
        operand = {
            "metric": data.draw(
                st.sampled_from(["critical_alerts", "all_alerts", "downtime"])
            )
        }
    elif kind == "count" or kind == "metric":
        operand = {"aggregate": "count"}
        if data.draw(st.booleans()):
            operand["column"] = ref(
                data.draw(
                    st.sampled_from(NUMERIC[base] + TEXT[base] + TIME_COLUMNS[base])
                )
            )
    elif kind in ("sum", "avg"):
        operand = {
            "aggregate": kind,
            "column": ref(data.draw(st.sampled_from(NUMERIC[base]))),
        }
    elif kind == "minmax":
        operand = {
            "aggregate": data.draw(st.sampled_from(["min", "max"])),
            "column": ref(
                data.draw(st.sampled_from(NUMERIC[base] + TIME_COLUMNS[base]))
            ),
        }
    else:
        operand = {
            "aggregate": "count_distinct",
            "column": ref(data.draw(st.sampled_from(TEXT[base]))),
        }
    if data.draw(st.booleans()):
        operand["filters"] = draw_filters(data, base, 1)
    return operand


def draw_measure(data, base: str, index: int) -> dict:
    if data.draw(st.integers(0, 3)) == 0:
        measure = {
            "alias": f"m{index}",
            "ratio": {
                "numerator": draw_operand(data, base),
                "denominator": draw_operand(data, base),
            },
        }
    else:
        measure = {**draw_operand(data, base), "alias": f"m{index}"}
    if data.draw(st.integers(0, 3)) == 0:
        measure["share_of_total"] = True
    return measure


def draw_time(data, base: str) -> dict | None:
    if data.draw(st.integers(0, 3)) == 0:
        return None
    time: dict = {}
    if base != "alerts" or data.draw(st.booleans()):
        time["column"] = ref(data.draw(st.sampled_from(TIME_COLUMNS[base])))
    scope_kind = data.draw(
        st.sampled_from(
            ["none", "month", "range", "relative", "to_date", "latest", "periods"]
        )
    )
    if scope_kind == "month":
        time["scope"] = {"kind": "month", "month": "2026-07"}
    elif scope_kind == "range":
        time["scope"] = {
            "kind": "range",
            "start": "2026-06-01",
            "end_exclusive": "2026-08-01",
        }
    elif scope_kind == "relative":
        time["scope"] = {
            "kind": "relative",
            "unit": data.draw(st.sampled_from(UNITS)),
            "offset": data.draw(st.integers(-6, 0)),
            "length": data.draw(st.integers(1, 3)),
        }
    elif scope_kind == "to_date":
        time["scope"] = {
            "kind": "relative",
            "unit": data.draw(st.sampled_from(UNITS)),
            "offset": 0,
            "length": 1,
            "to_date": True,
        }
    elif scope_kind == "latest":
        time["scope"] = {"kind": "latest", "unit": data.draw(st.sampled_from(UNITS))}
    elif scope_kind == "periods":
        time["scope"] = {
            "kind": "periods",
            "periods": [
                {"kind": "month", "month": "2026-06"},
                {"kind": "month", "month": "2026-07"},
            ],
        }
    if scope_kind == "none" or data.draw(st.booleans()):
        time["grain"] = data.draw(st.sampled_from(UNITS))
    return time


def draw_plan(data) -> tuple[dict, list]:
    base = data.draw(st.sampled_from(BASES))
    shape = data.draw(st.sampled_from(["aggregate"] * 6 + ["latest", "without"]))
    plan: dict = {"base_table": base}
    if shape == "latest":
        base = plan["base_table"] = data.draw(st.sampled_from(["alerts", "readings"]))
        plan["dimensions"] = [ref(data.draw(st.sampled_from(DIMENSIONS[base])))]
        plan["latest"] = {
            "order_by": [{"column": ref(TIME_COLUMNS[base][0]), "direction": "desc"}],
            "take": [
                ref(c)
                for c in data.draw(
                    st.lists(
                        st.sampled_from(NUMERIC[base] + TIME_COLUMNS[base]),
                        min_size=1,
                        max_size=2,
                        unique=True,
                    )
                )
            ],
        }
        plan["filters"] = draw_filters(data, base, 1)
        window = draw_time(data, base)
        if window is not None and "grain" in window:
            del window["grain"]
        if window and window.get("scope"):
            plan["time"] = window
    else:
        if shape == "without":
            base = plan["base_table"] = "devices"
            plan["dimensions"] = [ref("devices.model")]
            plan["measures"] = [{"aggregate": "count", "alias": "device_count"}]
            child_time = draw_time(data, "alerts")
            without: dict = {
                "table": data.draw(st.sampled_from(["alerts", "readings"]))
            }
            if without["table"] == "alerts":
                without["filters"] = draw_filters(data, "alerts", 1)
                if child_time and child_time.get("scope"):
                    without["time"] = {
                        "column": ref("alerts.raised_at"),
                        "scope": child_time["scope"],
                    }
            plan["without"] = without
        else:
            plan["measures"] = [
                draw_measure(data, base, i) for i in range(data.draw(st.integers(1, 2)))
            ]
            plan["dimensions"] = [
                ref(c)
                for c in data.draw(
                    st.lists(st.sampled_from(DIMENSIONS[base]), max_size=2, unique=True)
                )
            ]
            time = draw_time(data, base)
            if time is not None:
                plan["time"] = time
            plan["filters"] = draw_filters(data, base, 2)
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
                            "value": data.draw(st.sampled_from(VALUES["number"])),
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
    exclude = [OVERLAY.segments[0]] if data.draw(st.booleans()) else []
    return plan, exclude


EXAMPLES = int(os.environ.get("GREPBIT_PROPERTY_EXAMPLES", "200"))


@settings(
    max_examples=EXAMPLES,
    deadline=None,
    suppress_health_check=[
        HealthCheck.filter_too_much,
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
    ],
)
@given(data=st.data())
def test_every_generated_plan_compiles_cleanly_or_refuses_with_a_typed_error(
    data,
) -> None:
    payload, exclude = draw_plan(data)
    try:
        plan = QueryPlan.model_validate(payload)
    except ValidationError:
        assume(
            False
        )  # the generator overshot the plan's own rules; not a compiler case
        return
    try:
        compiled = COMPILER.compile(
            plan, as_of=AS_OF, exclude_segments=exclude, named_segments=[]
        )
    except PlanError as error:
        # a typed refusal is a legitimate outcome; the self-check firing is not:
        # it means the compiler produced SQL that contradicts the plan
        assert error.code != "self_check_failed", (payload, error.detail)
        return
    except Exception as error:  # noqa: BLE001
        # anything but a typed refusal is a compiler defect; show the plan
        raise AssertionError((payload, exclude, repr(error))) from error
    POLICY.assert_safe_select_statement(compiled.compiled.physical_sql)
    outputs = compiled.output_columns
    assert outputs and len(set(outputs)) == len(outputs), payload
    assert compiled.interpretation and compiled.lineage.base_table, payload
    for name in (m.output_name for m in plan.measures):
        assert name in outputs, (payload, outputs)
