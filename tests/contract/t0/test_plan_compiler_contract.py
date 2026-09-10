"""Tier-0 plan compiler: structural validation, joins, time windows, lineage."""

from __future__ import annotations

import pytest
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_compiler import COMPILER_REVISION, PlanCompiler
from grepbit.adapters.sqlglot.policy import (
    PLAN_AGGREGATE_FUNCTIONS,
    REVIEWED_FUNCTIONS,
    PostgresSqlPolicy,
)
from grepbit.domain.assumptions import AssumptionSource
from grepbit.domain.models import ParameterMode, SemanticRefSource
from grepbit.domain.plan import PlanError, QueryPlan
from grepbit.domain.schema_model import ForeignKey
from grepbit.ports.plan_compiler import PlanCompilerPort


def compile_plan(payload: dict, *, schema=None):
    compiler: PlanCompilerPort = PlanCompiler(schema or iot_schema())
    return compiler.compile(QueryPlan.model_validate(payload), as_of=AS_OF)


def policy_for(schema) -> PostgresSqlPolicy:
    return PostgresSqlPolicy(
        tables=frozenset(t.name for t in schema.tables),
        functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
    )


def test_count_with_month_window_binds_boundaries_in_business_timezone() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "severity"},
                    "op": "eq",
                    "values": ["critical"],
                }
            ],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "month", "month": "2026-07"},
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert sql == (
        "SELECT COUNT(*) AS row_count FROM public.alerts WHERE alerts.severity = "
        "%(f_0)s AND (alerts.raised_at >= %(p1_start_1)s "
        "AND alerts.raised_at < %(p1_end_2)s)"
    )
    parameters = {
        p.name: (p.type_name, p.value) for p in compiled.compiled.execution_parameters
    }
    assert parameters == {
        "f_0": ("text", "critical"),
        "p1_start_1": ("timestamptz", "2026-07-01T00:00:00+08:00"),
        "p1_end_2": ("timestamptz", "2026-08-01T00:00:00+08:00"),
    }
    assert compiled.compiled.parameter_mode is ParameterMode.PRESERVED_BINDING
    assert compiled.compiled.semantic_ref_source is SemanticRefSource.COMPILER_RESOLVED
    assert compiled.compiled.compiler_revision == COMPILER_REVISION
    assert compiled.output_columns == ("row_count",)
    assert compiled.interpretation == (
        "count(*) over alerts; for 2026-07; where alerts.severity eq critical"
    )
    assert compiled.lineage.as_dict() == {
        "base_table": "alerts",
        "tables": ["alerts"],
        "joins": [],
        "measures": ["row_count = count(*)"],
        "dimensions": [],
        "filters": ["alerts.severity eq critical"],
        "time_window": [
            "alerts.raised_at in [2026-07-01T00:00:00+08:00, 2026-08-01T00:00:00+08:00)"
        ],
        "having": [],
    }
    policy_for(iot_schema()).assert_safe_select_statement(sql)


def test_every_compiled_plan_carries_the_unreviewed_semantics_assumption() -> None:
    compiled = compile_plan(
        {"base_table": "devices", "measures": [{"aggregate": "count"}]}
    )
    sources = {a.source for a in compiled.assumptions}
    assert AssumptionSource.CANDIDATE in sources
    texts = [a.text for a in compiled.assumptions]
    assert any("No time window was applied" in t for t in texts)
    assert any("No row filter was applied" in t for t in texts)


def test_parent_dimension_joins_one_hop_and_states_the_join_assumption() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                }
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
            "order": [{"field": "sum_downtime_minutes", "direction": "desc"}],
            "limit": 2,
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "FROM public.alerts LEFT JOIN public.devices "
        "ON alerts.device_id = devices.device_id"
    ) in sql
    assert sql.endswith(
        "GROUP BY devices.model ORDER BY sum_downtime_minutes DESC NULLS LAST "
        "LIMIT %(limit_0)s"
    )
    assert compiled.lineage.joins == ("alerts.device_id -> devices.device_id",)
    assert compiled.lineage.tables == ("alerts", "devices")
    assert any(
        "rows without a matching devices row keep NULL" in a.text
        for a in compiled.assumptions
    )
    limit = [p for p in compiled.compiled.execution_parameters if p.name == "limit_0"]
    assert limit and limit[0].value == 2 and limit[0].type_name == "integer"
    policy_for(iot_schema()).assert_safe_select_statement(sql)


def test_grandparent_dimension_walks_two_foreign_keys_without_fan_out() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "dimensions": [{"table": "sites", "column": "site_name"}],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "FROM public.alerts LEFT JOIN public.devices "
        "ON alerts.device_id = devices.device_id "
        "LEFT JOIN public.sites ON devices.site_id = sites.site_id"
    ) in sql
    assert compiled.lineage.joins == (
        "alerts.device_id -> devices.device_id",
        "devices.site_id -> sites.site_id",
    )


def test_child_table_dimension_is_a_grain_conflict() -> None:
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "dimensions": [{"table": "alerts", "column": "severity"}],
            }
        )
    assert info.value.code == "grain_conflict"
    assert info.value.detail == "alerts"


def test_two_foreign_keys_to_the_same_parent_are_ambiguous() -> None:
    schema = iot_schema(
        extra_foreign_keys=[
            ForeignKey(
                table="alerts",
                column="related_device_id",
                referenced_table="devices",
                referenced_column="device_id",
            )
        ]
    )
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "dimensions": [{"table": "devices", "column": "model"}],
            },
            schema=schema,
        )
    assert info.value.code == "ambiguous_join_path"


@pytest.mark.parametrize(
    ("payload", "code", "detail"),
    [
        (
            {"base_table": "nowhere", "measures": [{"aggregate": "count"}]},
            "unknown_table",
            "nowhere",
        ),
        (
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "dimensions": [{"table": "alerts", "column": "colour"}],
            },
            "unknown_column",
            "alerts.colour",
        ),
        (
            {
                "base_table": "alerts",
                "measures": [
                    {
                        "aggregate": "sum",
                        "column": {"table": "alerts", "column": "severity"},
                    }
                ],
            },
            "aggregate_kind_mismatch",
            "alerts.severity",
        ),
        (
            {
                "base_table": "devices",
                "measures": [
                    {
                        "aggregate": "max",
                        "column": {"table": "devices", "column": "metadata"},
                    }
                ],
            },
            "aggregate_kind_mismatch",
            "devices.metadata",
        ),
        (
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "filters": [
                    {
                        "column": {"table": "devices", "column": "monthly_fee"},
                        "op": "gt",
                        "values": ["cheap"],
                    }
                ],
            },
            "filter_kind_mismatch",
            "monthly_fee",
        ),
        (
            {
                "base_table": "devices",
                "measures": [{"aggregate": "count"}],
                "filters": [
                    {
                        "column": {"table": "devices", "column": "is_managed"},
                        "op": "eq",
                        "values": ["yes"],
                    }
                ],
            },
            "filter_kind_mismatch",
            "is_managed",
        ),
        (
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {
                    "column": {"table": "alerts", "column": "severity"},
                    "scope": {"kind": "month", "month": "2026-07"},
                },
            },
            "time_column_kind_mismatch",
            "alerts.severity",
        ),
        (
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count"}],
                "time": {
                    "column": {"table": "alerts", "column": "raised_at"},
                    "scope": {
                        "kind": "periods",
                        "periods": [
                            {"kind": "month", "month": "2026-07"},
                            {"kind": "month", "month": "2026-08"},
                        ],
                    },
                },
            },
            "time_scope_requires_grain",
            None,
        ),
    ],
)
def test_structural_errors_carry_stable_codes(payload, code, detail) -> None:
    with pytest.raises(PlanError) as info:
        compile_plan(payload)
    assert info.value.code == code
    assert info.value.detail == detail


def test_plan_error_rejects_unknown_codes() -> None:
    with pytest.raises(ValueError, match="plan_error_code_invalid"):
        PlanError("made_up")


def test_monthly_grain_buckets_in_business_timezone_and_orders_by_period() -> None:
    compiled = compile_plan(
        {
            "base_table": "readings",
            "measures": [
                {
                    "aggregate": "avg",
                    "column": {"table": "readings", "column": "temperature_c"},
                }
            ],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "in",
                    "values": ["offline", "online"],
                }
            ],
            "time": {
                "column": {"table": "readings", "column": "measured_at"},
                "scope": {
                    "kind": "range",
                    "start": "2026-07-01",
                    "end_exclusive": "2026-09-01",
                },
                "grain": "month",
            },
        }
    )
    sql = compiled.compiled.physical_sql
    assert sql.startswith(
        "SELECT DATE_TRUNC('MONTH', readings.measured_at AT TIME ZONE 'Asia/Taipei') "
        "AS period_start, AVG(readings.temperature_c) AS avg_temperature_c"
    )
    assert "devices.status IN (%(f_0)s, %(f_1)s)" in sql
    assert sql.endswith(
        "GROUP BY DATE_TRUNC('MONTH', readings.measured_at AT TIME ZONE 'Asia/Taipei') "
        "ORDER BY period_start NULLS FIRST"
    )
    assert compiled.output_columns == ("period_start", "avg_temperature_c")
    assert compiled.interpretation.startswith(
        "avg(readings.temperature_c) over readings; per month; for "
    )
    policy_for(iot_schema()).assert_safe_select_statement(sql)


def test_relative_window_is_resolved_server_side_from_as_of() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "alerts", "column": "raised_at"},
                "scope": {"kind": "relative", "unit": "month", "offset": -1},
            },
        }
    )
    [period] = compiled.periods
    assert (period.start.isoformat(), period.end_exclusive.isoformat()) == (
        "2026-07-01T00:00:00+08:00",
        "2026-08-01T00:00:00+08:00",
    )
    assert any(
        a.text.startswith(
            "Relative period resolved from as_of 2026-08-15T12:00:00+08:00"
        )
        for a in compiled.assumptions
    )


def test_null_checks_and_count_distinct_render_without_bindings() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "count_distinct",
                    "column": {"table": "alerts", "column": "device_id"},
                    "alias": "devices_with_alerts",
                }
            ],
            "filters": [
                {
                    "column": {"table": "alerts", "column": "resolved_at"},
                    "op": "is_null",
                }
            ],
        }
    )
    assert compiled.compiled.physical_sql == (
        "SELECT COUNT(DISTINCT alerts.device_id) AS devices_with_alerts "
        "FROM public.alerts WHERE alerts.resolved_at IS NULL"
    )
    assert compiled.compiled.execution_parameters == []
    assert compiled.compiled.semantic_refs == ["alerts.device_id", "alerts.resolved_at"]


def test_policy_rejects_tables_outside_the_introspected_allowlist() -> None:
    compiled = compile_plan(
        {"base_table": "sites", "measures": [{"aggregate": "count"}]}
    )
    narrowed = PostgresSqlPolicy(
        tables=frozenset({"alerts"}),
        functions=REVIEWED_FUNCTIONS | PLAN_AGGREGATE_FUNCTIONS,
    )
    with pytest.raises(ValueError):
        narrowed.assert_safe_select_statement(compiled.compiled.physical_sql)


def test_two_distinct_paths_to_the_same_grandparent_are_ambiguous() -> None:
    from t0_helpers import col

    from grepbit.domain.schema_model import ColumnKind, SchemaModel, SchemaTable

    schema = SchemaModel(
        datasource_id="hr",
        schema_name="public",
        business_timezone="Asia/Taipei",
        tables=[
            SchemaTable(name="dept", columns=[col("dept_id", ColumnKind.TEXT)]),
            SchemaTable(
                name="employee",
                columns=[
                    col("emp_id", ColumnKind.TEXT),
                    col("dept_id", ColumnKind.TEXT),
                ],
            ),
            SchemaTable(
                name="project",
                columns=[
                    col("project_id", ColumnKind.TEXT),
                    col("dept_id", ColumnKind.TEXT),
                ],
            ),
            SchemaTable(
                name="assignment",
                columns=[
                    col("emp_id", ColumnKind.TEXT),
                    col("project_id", ColumnKind.TEXT),
                    col("hours", ColumnKind.NUMERIC),
                ],
            ),
        ],
        foreign_keys=[
            ForeignKey(
                table="employee",
                column="dept_id",
                referenced_table="dept",
                referenced_column="dept_id",
            ),
            ForeignKey(
                table="project",
                column="dept_id",
                referenced_table="dept",
                referenced_column="dept_id",
            ),
            ForeignKey(
                table="assignment",
                column="emp_id",
                referenced_table="employee",
                referenced_column="emp_id",
            ),
            ForeignKey(
                table="assignment",
                column="project_id",
                referenced_table="project",
                referenced_column="project_id",
            ),
        ],
    )
    with pytest.raises(PlanError) as info:
        compile_plan(
            {
                "base_table": "assignment",
                "measures": [
                    {
                        "aggregate": "sum",
                        "column": {"table": "assignment", "column": "hours"},
                    }
                ],
                "dimensions": [{"table": "dept", "column": "dept_id"}],
            },
            schema=schema,
        )
    assert info.value.code == "ambiguous_join_path"
    # Naming the intermediate table removes the ambiguity.
    compiled = compile_plan(
        {
            "base_table": "assignment",
            "measures": [
                {
                    "aggregate": "sum",
                    "column": {"table": "assignment", "column": "hours"},
                }
            ],
            "dimensions": [{"table": "employee", "column": "dept_id"}],
        },
        schema=schema,
    )
    assert compiled.lineage.joins == ("assignment.emp_id -> employee.emp_id",)


def test_date_column_grain_stays_a_date() -> None:
    compiled = compile_plan(
        {
            "base_table": "devices",
            "measures": [{"aggregate": "count"}],
            "time": {
                "column": {"table": "devices", "column": "installed_on"},
                "scope": {
                    "kind": "range",
                    "start": "2026-01-01",
                    "end_exclusive": "2026-07-01",
                },
                "grain": "month",
            },
        }
    )
    assert compiled.compiled.physical_sql.startswith(
        "SELECT CAST(DATE_TRUNC('MONTH', devices.installed_on) AS DATE) AS period_start"
    )


def test_inferred_join_is_stated_as_a_candidate_assumption() -> None:
    base = iot_schema()
    schema = base.model_copy(
        update={
            "foreign_keys": [
                fk.model_copy(
                    update={"inferred": True, "evidence": "names match; 0 orphans"}
                )
                if fk.table == "alerts"
                else fk
                for fk in base.foreign_keys
            ]
        }
    )
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [{"aggregate": "count"}],
            "dimensions": [{"table": "devices", "column": "model"}],
        },
        schema=schema,
    )
    assert compiled.lineage.joins == (
        "alerts.device_id -> devices.device_id (inferred)",
    )
    candidate = [
        a for a in compiled.assumptions if a.source is AssumptionSource.CANDIDATE
    ]
    assert any(
        "is inferred, not a declared foreign key: names match" in a.text
        for a in candidate
    )


def test_enum_filters_compare_as_text_so_unknown_labels_miss_instead_of_raising():
    from t0_helpers import col

    from grepbit.domain.schema_model import ColumnKind

    schema = iot_schema()
    devices = schema.table("devices")
    assert devices is not None
    channel = col(
        "channel",
        ColumnKind.TEXT,
        data_type="channel_t",
        sample_values=["email", "sms"],
        is_enum=True,
    )
    devices = devices.model_copy(update={"columns": [*devices.columns, channel]})
    schema = schema.model_copy(
        update={
            "tables": [devices if t.name == "devices" else t for t in schema.tables]
        }
    )
    compiled = compile_plan(
        {
            "base_table": "devices",
            "measures": [{"aggregate": "count"}],
            "dimensions": [{"table": "devices", "column": "channel"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "channel"},
                    "op": "in",
                    "values": ["email", "fax"],
                }
            ],
        },
        schema=schema,
    )
    sql = compiled.compiled.physical_sql
    assert "CAST(devices.channel AS TEXT) IN (%(f_0)s, %(f_1)s)" in sql
    assert (
        "SELECT devices.channel AS channel" in sql
    )  # the dimension itself is not cast
    assert [p.type_name for p in compiled.compiled.execution_parameters] == [
        "text",
        "text",
    ]


def test_having_compares_the_aggregate_expression_with_a_bound_value() -> None:
    compiled = compile_plan(
        {
            "base_table": "alerts",
            "measures": [
                {"aggregate": "count", "alias": "alert_count"},
                {
                    "aggregate": "sum",
                    "column": {"table": "alerts", "column": "downtime_minutes"},
                },
            ],
            "dimensions": [{"table": "devices", "column": "model"}],
            "having": [
                {"field": "alert_count", "op": "gt", "value": 100},
                {"field": "sum_downtime_minutes", "op": "lte", "value": 5000},
            ],
        }
    )
    sql = compiled.compiled.physical_sql
    assert (
        "GROUP BY devices.model HAVING COUNT(*) > %(h_0)s "
        "AND SUM(alerts.downtime_minutes) <= %(h_1)s"
    ) in sql
    assert [
        (p.name, p.type_name, p.value) for p in compiled.compiled.execution_parameters
    ] == [
        ("h_0", "numeric", 100),
        ("h_1", "numeric", 5000),
    ]
    assert compiled.lineage.having == (
        "alert_count gt 100",
        "sum_downtime_minutes lte 5000",
    )
    assert (
        "having alert_count gt 100 and sum_downtime_minutes lte 5000"
        in compiled.interpretation
    )
    assert compiled.lineage.as_dict()["having"] == [
        "alert_count gt 100",
        "sum_downtime_minutes lte 5000",
    ]


def test_having_field_must_name_a_measure() -> None:
    with pytest.raises(ValueError, match="plan_having_field_not_a_measure"):
        QueryPlan.model_validate(
            {
                "base_table": "alerts",
                "measures": [{"aggregate": "count", "alias": "n"}],
                "dimensions": [{"table": "devices", "column": "model"}],
                "having": [{"field": "model", "op": "gt", "value": 1}],
            }
        )


def test_base_repair_moves_the_base_to_the_child_holding_the_measures() -> None:
    from grepbit.application.plan_repair import repair_base_table

    # the q29 shape: grouped by the parent (sites), measures on the child (devices)
    plan = QueryPlan.model_validate(
        {
            "base_table": "sites",
            "measures": [
                {
                    "aggregate": "max",
                    "column": {"table": "devices", "column": "monthly_fee"},
                }
            ],
            "dimensions": [{"table": "sites", "column": "site_name"}],
            "having": [{"field": "max_monthly_fee", "op": "gt", "value": 100}],
        }
    )
    repaired, note = repair_base_table(plan, iot_schema())
    assert repaired.base_table == "devices" and "sites -> devices" in note
    compiled = compile_plan(repaired.model_dump(mode="json", exclude_none=True))
    assert (
        "FROM public.devices LEFT JOIN public.sites" in compiled.compiled.physical_sql
    )
    assert "HAVING MAX(devices.monthly_fee) > %(h_0)s" in compiled.compiled.physical_sql
    # unchanged when the measure sits on the base, on several tables, is count(*),
    # or when the base is not a parent of the measure table
    same = QueryPlan.model_validate(
        {"base_table": "devices", "measures": [{"aggregate": "count"}]}
    )
    assert repair_base_table(same, iot_schema()) == (same, None)
    unrelated = QueryPlan.model_validate(
        {
            "base_table": "alerts",
            "measures": [
                {
                    "aggregate": "avg",
                    "column": {"table": "readings", "column": "temperature_c"},
                }
            ],
        }
    )
    assert repair_base_table(unrelated, iot_schema())[1] is None


def test_base_repair_also_follows_a_metric_whose_base_is_a_child_of_the_plan_base():
    from grepbit.application.plan_repair import repair_base_table
    from grepbit.domain.overlay import SemanticOverlay

    overlay = SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "t",
            "metrics": [
                {
                    "id": "alert_count",
                    "names": ["告警數"],
                    "description": "count of alerts",
                    "base_table": "alerts",
                    "aggregate": "count",
                }
            ],
        }
    )
    plan = QueryPlan.model_validate(
        {
            "base_table": "devices",
            "measures": [{"metric": "alert_count"}],
            "filters": [
                {
                    "column": {"table": "devices", "column": "status"},
                    "op": "eq",
                    "values": ["offline"],
                }
            ],
        }
    )
    repaired, note = repair_base_table(plan, iot_schema(), overlay)
    assert repaired.base_table == "alerts" and "devices -> alerts" in note
    # without the overlay the metric cannot be resolved: no repair
    assert repair_base_table(plan, iot_schema())[1] is None
