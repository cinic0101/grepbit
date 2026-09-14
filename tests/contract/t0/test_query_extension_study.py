"""Research contracts; no production QueryPlan compatibility changes."""

import pytest
from pydantic import ValidationError
from t0_helpers import AS_OF, iot_schema

from evals.query_extension_study import (
    matches,
    parse_proposal,
    study_schema,
    visible_units,
)
from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.query_extension_study import StudyCompiler, StudyRefusal
from grepbit.domain.overlay import SemanticOverlay
from grepbit.domain.plan import QueryPlan
from grepbit.domain.query_extension_study import StudyProposal


def ref(table, column):
    return {"table": table, "column": column}


def rows(**extra):
    return {"kind": "rows", "base_table": "devices", "all_columns": True, **extra}


def parse(query):
    return StudyProposal.model_validate({"decision": "plan", "query": query}).query


def test_research_rows_does_not_relax_production_queryplan():
    assert parse(rows()).all_columns
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(rows())


@pytest.mark.parametrize(
    "query",
    [
        rows(all_columns=False),
        rows(columns=[ref("devices", "model")]),
        rows(limit=0),
        rows(limit=201),
        rows(sql="SELECT * FROM devices"),
        rows(base_table="devices; DROP TABLE alerts"),
        rows(all_columns=False, columns=[ref("devices", "model")] * 2),
    ],
)
def test_invalid_projection_contract(query):
    with pytest.raises(ValidationError):
        parse(query)


@pytest.mark.parametrize(
    "bad",
    [
        {"limit": 2},
        {"order": [{"field": "n"}]},
        {"dimensions": [ref("devices", "device_id")]},
    ],
)
def test_combine_cannot_silently_drop_component_clauses(bad):
    with pytest.raises(ValidationError):
        parse(
            {
                "kind": "combine",
                "entity_table": "devices",
                "components": [
                    {
                        "base_table": "alerts",
                        "measures": [{"aggregate": "count", "alias": "n"}],
                        **bad,
                    }
                ],
            }
        )


def test_conversion_never_accepts_model_formula_or_source_unit():
    for extra in ({"formula": "x*1.8+32"}, {"source_unit": "celsius"}):
        with pytest.raises(ValidationError):
            parse(
                {
                    "kind": "aggregate",
                    "plan": {
                        "base_table": "readings",
                        "measures": [{"aggregate": "count"}],
                    },
                    "conversion": {
                        "field": "row_count",
                        "target_unit": "fahrenheit",
                        **extra,
                    },
                }
            )


def sample_tables():
    return {
        "sites": [
            {"site_id": "s1", "site_name": "same"},
            {"site_id": "s2", "site_name": "same"},
            {"site_id": "s3", "site_name": "empty"},
        ],
        "devices": [
            {"device_id": f"d{i}", "site_id": s, "model": "AP"}
            for i, s in enumerate(["s1", "s1", "s2", "s3"], 1)
        ],
        "readings": [
            {"reading_id": i, "device_id": device, "temperature_c": temp}
            for i, (device, temp) in enumerate([("d1", 10), ("d1", 30), ("d2", 100)], 1)
        ],
        "alerts": [
            {"alert_id": i, "device_id": device}
            for i, device in enumerate(["d1"] * 3 + ["d3"] * 5, 1)
        ],
    }


def compile_query(query, **kwargs):
    return StudyCompiler(iot_schema(), **kwargs).compile(parse(query), as_of=AS_OF)


def execute(query, tables=None, **kwargs):
    compiled = compile_query(query, **kwargs)
    db = DuckInstance(iot_schema(), tables or sample_tables())
    try:
        _, result = db.execute(compiled.compiled)
        return result
    finally:
        db.con.close()


def component(table, aggregate, alias, name=None):
    measure = {"aggregate": aggregate, "alias": alias}
    if name:
        measure["column"] = ref(table, name)
    return {"base_table": table, "measures": [measure]}


def bundle(entity="devices", **kwargs):
    return {
        "kind": "combine",
        "entity_table": entity,
        "components": [
            component("readings", "count", "readings_n"),
            component("alerts", "count", "alerts_n"),
        ],
        **kwargs,
    }


def test_independent_counts_preserve_all_four_activity_populations():
    assert execute(bundle()) == [("d1", 2, 3), ("d2", 1, 0), ("d3", 0, 5), ("d4", 0, 0)]


def test_winner_without_readings_stays_winner_with_null_temperature():
    query = bundle(
        "sites",
        components=[
            component("alerts", "count", "alerts_n"),
            component("readings", "avg", "temperature", "temperature_c"),
        ],
        selection={"field": "alerts_n", "direction": "max"},
    )
    assert execute(query) == [("s2", 5, None)]
    tables = sample_tables()
    tables["alerts"] += [
        {"alert_id": 9, "device_id": "d2"},
        {"alert_id": 10, "device_id": "d2"},
    ]
    answer = execute(query, tables)
    assert answer[0][0:2] == ("s1", 5)
    assert answer[0][2] == pytest.approx(140 / 3)
    assert answer[1] == ("s2", 5, None)


@pytest.mark.parametrize("seed", range(10))
def test_independent_count_values_across_random_instances(seed):
    import random

    randomizer = random.Random(seed)
    tables = sample_tables()
    counts = []
    tables["readings"], tables["alerts"] = [], []
    for device in tables["devices"]:
        nr, na = randomizer.randrange(8), randomizer.randrange(8)
        counts.append((device["device_id"], nr, na))
        for table, n, key in (
            ("readings", nr, "reading_id"),
            ("alerts", na, "alert_id"),
        ):
            for _ in range(n):
                tables[table].append(
                    {key: len(tables[table]) + 1, "device_id": device["device_id"]}
                )
    assert execute(bundle(), tables) == counts


def conversion(target="fahrenheit", aggregate="avg"):
    return {
        "kind": "aggregate",
        "plan": component("readings", aggregate, "temperature", "temperature_c"),
        "conversion": {"field": "temperature", "target_unit": target},
    }


def binding(unit="celsius"):
    return [
        {
            "column": ref("readings", "temperature_c"),
            "unit": unit,
            "evidence": "hand-authored synthetic unit ruler",
        }
    ]


@pytest.mark.parametrize(
    "value,expected", [(0, 32), (100, 212), (-40, -40), (None, None)]
)
def test_fahrenheit_golden_points_and_null(value, expected):
    tables = sample_tables()
    tables["readings"] = [{"reading_id": 1, "temperature_c": value, "device_id": "d1"}]
    assert execute(conversion(), tables, units=binding()) == [(expected,)]


def test_conversion_of_mean_and_inverse():
    assert execute(conversion(), units=binding())[0][0] == pytest.approx(116)
    assert execute(conversion("celsius"), units=binding("fahrenheit"))[0][
        0
    ] == pytest.approx((140 / 3 - 32) * 5 / 9)


@pytest.mark.parametrize("aggregate", ["sum", "count", "count_distinct"])
def test_temperature_sum_or_counts_cannot_be_converted(aggregate):
    with pytest.raises(StudyRefusal, match="unit_aggregate_incompatible"):
        compile_query(conversion(aggregate=aggregate), units=binding())


def test_missing_and_incompatible_source_units_refuse():
    with pytest.raises(StudyRefusal, match="source_unit_not_bound"):
        compile_query(conversion())
    with pytest.raises(StudyRefusal, match="unit_dimensions_incompatible"):
        compile_query(conversion("hours"), units=binding())


def test_duration_conversion_preserves_null_and_zero():
    assert execute(conversion("hours", "sum"), units=binding("minutes"))[0][
        0
    ] == pytest.approx(140 / 60)


def test_rows_projection_is_not_an_aggregate_and_has_stable_limit():
    query = rows(
        all_columns=False,
        columns=[ref("devices", "device_id"), ref("devices", "model")],
        limit=2,
    )
    assert execute(query) == [("d1", "AP"), ("d2", "AP")]
    compiled = compile_query(query)
    assert "COUNT" not in compiled.compiled.physical_sql
    assert "devices.model" in compiled.compiled.semantic_refs
    assert any("not all matching rows" in a for a in compiled.assumptions)


def test_hidden_columns_cannot_be_named_or_included_by_all():
    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="hidden-ruler",
        column_policies=[{"column": ref("devices", "model"), "visible": False}],
    )
    query = rows(all_columns=False, columns=[ref("devices", "model")])
    with pytest.raises(StudyRefusal, match="visible_base_columns"):
        compile_query(query, overlay=overlay)
    compiled = compile_query(rows(), overlay=overlay)
    assert "model" not in compiled.columns
    assert "devices.model" not in compiled.compiled.semantic_refs


def test_component_filter_parameters_do_not_collide():
    query = bundle()
    query["components"][0]["filters"] = [
        {"column": ref("readings", "device_id"), "op": "eq", "values": ["d1"]}
    ]
    query["components"][1]["filters"] = [
        {"column": ref("alerts", "device_id"), "op": "eq", "values": ["d3"]}
    ]
    assert execute(query) == [("d1", 2, 0), ("d2", 0, 0), ("d3", 0, 5), ("d4", 0, 0)]
    compiled = compile_query(query).compiled
    names = [p.name for p in compiled.execution_parameters]
    assert len(names) == len(set(names))


def test_wire_v2_is_explicit_about_conversion_without_inventing_intent():
    import json

    payload = {
        "decision": "plan",
        "query": {"kind": "aggregate", "plan": component("alerts", "count", "n")},
    }
    parse_proposal(json.dumps(payload), "v1")
    with pytest.raises(ValueError, match="explicit_conversion_or_null_required"):
        parse_proposal(json.dumps(payload), "v2")
    payload["query"]["conversion"] = None
    assert parse_proposal(json.dumps(payload), "v2").query.conversion is None
    schema = study_schema("v2")
    assert "conversion" in schema["$defs"]["AggregateQuery"]["required"]
    assert set(schema["$defs"]["UngroupedComponent"]["properties"]) == {
        "base_table",
        "measures",
        "filters",
        "time",
    }


def test_unit_payload_does_not_reintroduce_hidden_columns():
    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="hidden-units",
        column_policies=[
            {"column": ref("readings", "temperature_c"), "visible": False}
        ],
    )
    assert visible_units(binding(), iot_schema(), overlay) == []
    with pytest.raises(ValueError):
        compile_query(conversion(), overlay=overlay, units=binding())


def test_values_grader_preserves_duplicates_nulls_and_requested_order():
    assert not matches([(1,), (1,)], [(1,)])
    assert not matches([(None,)], [(0,)])
    assert matches([(1,), (2,)], [(2,), (1,)])
    assert not matches([(1,), (2,)], [(2,), (1,)], ordered=True)
    assert not matches([(1, 99)], [(1,)])


def test_default_segment_applies_to_its_component_only():
    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="segment-ruler",
        segments=[
            {
                "id": "critical",
                "names": ["critical"],
                "table": "alerts",
                "filter": {
                    "column": ref("alerts", "severity"),
                    "op": "eq",
                    "values": ["critical"],
                },
                "default_exclude": True,
                "note": "Synthetic exclusion test only",
            }
        ],
    )
    tables = sample_tables()
    for alert in tables["alerts"]:
        alert["severity"] = "warning"
    tables["alerts"][0]["severity"] = "critical"
    assert execute(bundle(), tables, overlay=overlay, excluded=overlay.segments) == [
        ("d1", 2, 2),
        ("d2", 1, 0),
        ("d3", 0, 5),
        ("d4", 0, 0),
    ]


def test_conversion_combinations_refuse_instead_of_dropping_having():
    query = conversion()
    query["plan"]["having"] = [{"field": "temperature", "op": "gt", "value": 100}]
    with pytest.raises(StudyRefusal, match="conversion_combination_unsupported"):
        compile_query(query, units=binding())


def test_independent_component_windows_remain_separate():
    from datetime import datetime

    query = bundle()
    query["components"][0]["time"] = {
        "column": ref("readings", "measured_at"),
        "scope": {"kind": "month", "month": "2026-07"},
    }
    query["components"][1]["time"] = {
        "column": ref("alerts", "raised_at"),
        "scope": {"kind": "month", "month": "2026-08"},
    }
    tables = sample_tables()
    for row in tables["readings"]:
        row["measured_at"] = datetime.fromisoformat("2026-07-02T12:00:00+08:00")
    for row in tables["alerts"]:
        row["raised_at"] = datetime.fromisoformat("2026-07-02T12:00:00+08:00")
    tables["alerts"][-1]["raised_at"] = datetime.fromisoformat(
        "2026-08-02T12:00:00+08:00"
    )
    assert execute(query, tables) == [
        ("d1", 2, 0),
        ("d2", 1, 0),
        ("d3", 0, 1),
        ("d4", 0, 0),
    ]


def test_null_only_duration_total_stays_null_and_zero_stays_zero():
    for value in (None, 0):
        tables = sample_tables()
        tables["readings"] = [
            {"reading_id": 1, "device_id": "d1", "temperature_c": value}
        ]
        assert execute(
            conversion("hours", "sum"), tables, units=binding("minutes")
        ) == [(value,)]
