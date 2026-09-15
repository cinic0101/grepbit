"""Base-row pilot rulers; no bypass of shared ask() safeguards."""

import pytest
from pydantic import ValidationError
from t0_helpers import AS_OF, iot_schema

from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import PlanError, QueryPlan


def ref(table, column):
    return {"table": table, "column": column}


def row_plan(**extra):
    return QueryPlan.model_validate(
        {"base_table": "devices", "rows": {"all_columns": True}, **extra}
    )


def test_rows_are_a_distinct_plan_without_fake_measures():
    plan = row_plan()
    assert plan.rows.all_columns
    assert plan.measures == []


def test_explicit_rows_preserve_projection_and_order():
    plan = row_plan(
        rows={"columns": [ref("devices", "model")]}, order=[{"field": "model"}]
    )
    assert plan.rows.columns[0].id == "devices.model"
    compiled = PlanCompiler(iot_schema(), allow_rows=True).compile(plan, as_of=AS_OF)
    assert compiled.output_columns == ("model",)
    assert compiled.lineage.projection == ("devices.model",)
    assert compiled.lineage.measures == ()
    assert "COUNT(" not in compiled.compiled.physical_sql
    assert compiled.verification == "unverified_semantics"


def test_compiler_default_refuses_even_a_valid_row_plan():
    plan = row_plan()
    with pytest.raises(PlanError, match="row_queries_disabled"):
        PlanCompiler(iot_schema()).compile(plan, as_of=AS_OF)


@pytest.mark.parametrize(
    "extra",
    [
        {"measures": [{"aggregate": "count"}]},
        {"dimensions": [ref("devices", "model")]},
        {"time": {"grain": "day"}},
        {"without": {"table": "alerts"}},
        {
            "latest": {
                "order_by": [{"column": ref("devices", "device_id")}],
                "take": [ref("devices", "model")],
            }
        },
        {"having": [{"field": "n", "op": "gt", "value": 1}]},
        {"growth": [{"measure": "n"}]},
    ],
)
def test_row_combinations_fail_closed(extra):
    with pytest.raises(ValidationError, match="plan_rows_excludes_other_constructs"):
        row_plan(**extra)


def test_all_columns_and_explicit_projection_are_not_combined():
    with pytest.raises(ValidationError):
        row_plan(rows={"all_columns": True, "columns": [ref("devices", "model")]})


def test_old_aggregate_still_compiles():
    plan = QueryPlan(base_table="devices", measures=[{"aggregate": "count"}])
    assert PlanCompiler(iot_schema()).compile(plan, as_of=AS_OF).output_columns


@pytest.mark.parametrize("reason", ["semantic_gap", "ambiguous"])
def test_row_fallback_keeps_original_refusals(reason):
    import json
    from types import SimpleNamespace

    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
    from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient

    messages = []

    def create(**kwargs):
        messages.append(kwargs["messages"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps({"decision": "none", "reason": reason})
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fixture"),
        client=client,
        allow_rows=True,
    )
    proposal = planner.propose("q", iot_schema(), as_of=AS_OF.isoformat())
    assert proposal.reason == reason and len(messages) == 1
    assert (
        json.loads(messages[0][2]["content"])["prompt_revision"]
        == "plan-classify-json-v15"
    )


@pytest.mark.parametrize("fallback_kind", ["rows", "aggregate"])
def test_only_unsupported_can_fall_back_and_only_rows_can_be_promoted(fallback_kind):
    import json
    from types import SimpleNamespace

    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
    from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient

    records = []
    plan = (
        row_plan()
        if fallback_kind == "rows"
        else QueryPlan(base_table="devices", measures=[{"aggregate": "count"}])
    )
    replies = [
        {"decision": "none", "reason": "unsupported"},
        {"decision": "plan", "plan": plan.model_dump()},
    ]

    def create(**kwargs):
        records.append(kwargs["messages"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(replies[len(records) - 1])
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fixture"),
        client=client,
        allow_rows=True,
    )
    proposal = planner.propose("List devices", iot_schema(), as_of=AS_OF.isoformat())
    assert len(records) == 2
    assert planner.last_row_fallbacks == 1
    assert (proposal.decision == "plan") == (fallback_kind == "rows")
    assert (
        json.loads(records[0][2]["content"])["prompt_revision"]
        == "plan-classify-json-v15"
    )


@pytest.mark.parametrize("cancel", [False, True])
def test_fallback_preserves_plan_and_stops_between_stages(monkeypatch, cancel):
    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
    from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
    from grepbit.application.request_lifecycle import RequestControl, RequestStopped
    from grepbit.domain.plan import PlanProposal

    control = RequestControl(30)
    plan = QueryPlan(base_table="devices", measures=[{"aggregate": "count"}])
    calls = []

    def propose(self, *args, **kwargs):
        calls.append(self._allow_rows)
        if cancel:
            control.stop("request_cancelled")
            return PlanProposal(decision="none", reason="unsupported")
        return PlanProposal(decision="plan", plan=plan)

    monkeypatch.setattr(ChatCompletionsPlanClient, "_propose", propose)
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fixture"),
        client=object(),
        allow_rows=True,
        control=control,
    )
    if cancel:
        with pytest.raises(RequestStopped, match="request_cancelled"):
            planner.propose("q", iot_schema(), as_of=AS_OF.isoformat())
    else:
        assert planner.propose("q", iot_schema(), as_of=AS_OF.isoformat()).plan == plan
        assert planner.last_row_fallbacks == 0
    assert calls == [False]


@pytest.mark.parametrize("projection", ["devices", ["devices.model"], 1, True])
def test_malformed_row_projection_is_typed_invalid_output(projection):
    import json

    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
    from grepbit.adapters.litellm.plan_client import (
        ChatCompletionsPlanClient,
        _InvalidOutput,
    )

    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fixture"),
        allow_rows=True,
    )
    with pytest.raises(_InvalidOutput):
        planner._validate(
            json.dumps(
                {
                    "decision": "plan",
                    "plan": {"base_table": "devices", "rows": projection},
                }
            ),
            iot_schema(),
        )


def compile_rows(plan=None, overlay=None, schema=None):
    return PlanCompiler(
        schema or iot_schema(), overlay=overlay, allow_rows=True
    ).compile(plan or row_plan(), as_of=AS_OF)


def test_all_columns_visibility_and_hidden_pk_fail_closed():
    from grepbit.domain.overlay import SemanticOverlay

    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="rows",
        column_policies=[{"column": ref("devices", "model"), "visible": False}],
    )
    compiled = compile_rows(overlay=overlay)
    assert "model" not in compiled.output_columns
    assert "devices.model" not in compiled.compiled.semantic_refs
    with pytest.raises(PlanError, match="unknown_column"):
        compile_rows(row_plan(rows={"columns": [ref("devices", "model")]}), overlay)
    overlay.column_policies[0].column = type(overlay.column_policies[0].column)(
        table="devices", column="device_id"
    )
    with pytest.raises(PlanError, match="row_projection_unsupported"):
        compile_rows(overlay=overlay)


@pytest.mark.parametrize(
    "extra",
    [
        {
            "filters": [
                {"column": ref("sites", "site_name"), "op": "eq", "values": ["site"]}
            ]
        },
        {"rows": {"columns": [ref("devices", "model")] * 2}},
        {"base_table": None},
        {"rows": {}},
        {"limit": 201},
    ],
)
def test_invalid_scope_projection_and_limits(extra):
    with pytest.raises(ValidationError):
        row_plan(**extra)


def test_unchecked_combination_cannot_drop_aggregate():
    from grepbit.domain.plan import Measure

    plan = row_plan().model_copy(update={"measures": [Measure(aggregate="count")]})
    with pytest.raises(PlanError, match="row_projection_unsupported"):
        compile_rows(plan)


@pytest.mark.parametrize("seed", range(10))
def test_generated_row_values_preserve_null_duplicates_order_and_limit(seed):
    import random

    from evals.synthetic import DuckInstance

    rng = random.Random(seed)
    data = [
        {"device_id": f"d{i:02d}", "model": rng.choice([None, "AP", "AP", "Z"])}
        for i in range(12)
    ]
    rng.shuffle(data)
    instance = DuckInstance(iot_schema(), {"devices": data})
    try:
        plan = row_plan(rows={"columns": [ref("devices", "model")]})
        expected = [(r["model"],) for r in sorted(data, key=lambda r: r["device_id"])]
        assert instance.execute(compile_rows(plan).compiled)[1] == expected
        plan = row_plan(
            rows={"columns": [ref("devices", "model")]},
            order=[{"field": "model", "direction": "desc"}],
            limit=5,
        )
        # Independent Python oracle: DESC NULLS LAST, then PK ascending.
        ordered = sorted(data, key=lambda r: r["device_id"])
        nonnull = sorted(
            [r for r in ordered if r["model"] is not None],
            key=lambda r: r["model"],
            reverse=True,
        )
        expected = [
            (r["model"],) for r in nonnull + [r for r in ordered if r["model"] is None]
        ][:5]
        compiled = compile_rows(plan)
        assert instance.execute(compiled.compiled)[1] == expected
        assert any(p.value == 5 for p in compiled.compiled.execution_parameters)
        assert "not all matching rows" in compiled.interpretation
    finally:
        instance.con.close()


def test_row_segments_keep_values_and_lineage():
    from evals.synthetic import DuckInstance
    from grepbit.domain.overlay import SemanticOverlay

    overlay = SemanticOverlay(
        datasource_id="iot_test",
        revision="rows",
        segments=[
            {
                "id": "offline",
                "names": ["offline"],
                "table": "devices",
                "filter": {
                    "column": ref("devices", "status"),
                    "op": "eq",
                    "values": ["offline"],
                },
                "default_exclude": True,
                "note": "fictional test",
            }
        ],
    )
    instance = DuckInstance(
        iot_schema(),
        {
            "devices": [
                {"device_id": "d1", "status": "offline"},
                {"device_id": "d2", "status": "online"},
            ]
        },
    )
    compiler = PlanCompiler(iot_schema(), overlay=overlay, allow_rows=True)
    plan = row_plan(rows={"columns": [ref("devices", "device_id")]})
    try:
        excluded = compiler.compile(
            plan, as_of=AS_OF, exclude_segments=overlay.segments
        )
        assert instance.execute(excluded.compiled)[1] == [("d2",)]
        assert excluded.applied_segments == ("offline",)
        named = compiler.compile(plan, as_of=AS_OF, named_segments=overlay.segments)
        # Naming lifts the default exclusion; it does not invent a raw row filter.
        assert instance.execute(named.compiled)[1] == [("d1",), ("d2",)]
        assert named.verification == "unverified_semantics"
    finally:
        instance.con.close()


def test_row_selfcheck_detects_projection_and_cardinality_changes():
    from grepbit.adapters.sqlglot.plan_check import check_compiled

    plan = row_plan(rows={"columns": [ref("devices", "model")]})
    assert "row_projection_mismatch" in check_compiled(
        plan,
        "SELECT device_id FROM devices ORDER BY device_id",
        [],
        "unverified_semantics",
    )
    assert "row_cardinality_changed" in check_compiled(
        plan,
        "SELECT DISTINCT devices.model FROM devices ORDER BY device_id",
        [],
        "unverified_semantics",
    )
    assert "row_limit_mismatch" in check_compiled(
        plan,
        "SELECT devices.model FROM devices ORDER BY device_id LIMIT 1",
        [],
        "unverified_semantics",
    )


def row_services(plan, executor, **kwargs):
    import test_ask_contract as h

    services = h.services(
        h._Planner({"decision": "plan", "plan": plan.model_dump()}), executor, **kwargs
    )
    services.compiler = PlanCompiler(
        services.schema, overlay=services.overlay, allow_rows=True
    )
    return services


def test_rows_use_shared_grounding_recompile_and_bound_parameters():
    import test_ask_contract as h

    from grepbit.application.ask import AskSettings, ask

    plan = row_plan(
        rows={"columns": [ref("devices", "device_id")]},
        filters=[
            {"column": ref("devices", "status"), "op": "eq", "values": ["offlin"]}
        ],
    )
    executor = h._Executor([{"device_id": "d1"}])
    services = row_services(plan, executor)
    result = ask("List offlin devices", services, AskSettings(as_of=AS_OF))
    assert result.status == "answered"
    assert result.grounding and result.plan.filters[0].values == ["offline"]
    assert result.parameters[0]["value"] == "offline"
    assert "offline" not in result.sql
    assert result.lineage["projection"] == ["devices.device_id"]


def test_missing_row_filter_does_not_execute():
    import test_ask_contract as h

    from grepbit.application.ask import AskSettings, ask

    plan = row_plan(
        filters=[
            {"column": ref("devices", "status"), "op": "eq", "values": ["unfindable"]}
        ]
    )
    executor = h._Executor([])
    result = ask(
        "List devices",
        row_services(plan, executor, index=False),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "clarify" and executor.executed == []


def test_null_row_warning_does_not_claim_empty_aggregate():
    import test_ask_contract as h

    from grepbit.application.ask import AskSettings, ask

    plan = row_plan(rows={"columns": [ref("devices", "model")]})
    result = ask(
        "List models",
        row_services(plan, h._Executor([{"model": None}])),
        AskSettings(as_of=AS_OF),
    )
    assert result.status == "answered"
    assert "aggregate ran over zero rows" not in " ".join(result.warnings)


def test_row_stop_after_planner_prevents_execution():
    import test_ask_contract as h

    from grepbit.application.ask import AskSettings, ask
    from grepbit.application.request_lifecycle import RequestControl

    control = RequestControl(30)
    executor = h._Executor([])
    services = row_services(row_plan(), executor)
    original = services.planner.propose

    def propose(*a, **kw):
        result = original(*a, **kw)
        control.stop("request_cancelled")
        return result

    services.planner.propose = propose
    result = ask("List devices", services, AskSettings(as_of=AS_OF), control=control)
    assert result.status == "failed" and executor.executed == []


def test_rows_prompt_opt_in_and_reference_normalization():
    import json

    from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
    from grepbit.adapters.litellm.plan_client import (
        ChatCompletionsPlanClient,
        _InvalidOutput,
    )

    settings = GroundingModelSettings(base_url="http://unused", model="fixture")
    old = ChatCompletionsPlanClient(settings)
    pilot = ChatCompletionsPlanClient(settings, allow_rows=True)
    kwargs = {"as_of": AS_OF.isoformat()}
    a = old.build_messages("列出裝置", iot_schema(), **kwargs)
    b = pilot.build_messages("列出裝置", iot_schema(), **kwargs)
    assert (
        "rows"
        not in json.loads(a[1]["content"].split(": ", 1)[1])["properties"]["plan"][
            "properties"
        ]
    )
    assert json.loads(a[2]["content"])["prompt_revision"] == "plan-classify-json-v15"
    assert "列出裝置" in b[2]["content"]
    proposal = pilot._validate(
        json.dumps(
            {
                "decision": "plan",
                "plan": {
                    "base_table": "devices",
                    "rows": {"columns": ["devices.model"]},
                },
            }
        ),
        iot_schema(),
    )
    assert proposal.plan.rows.columns[0].id == "devices.model"
    for projection in ({"columns": ["devices.device_id"]}, {"all_columns": True}):
        ordered = pilot._validate(
            json.dumps(
                {
                    "decision": "plan",
                    "plan": {
                        "base_table": "devices",
                        "rows": projection,
                        "order": [{"field": "devices.device_id", "direction": "asc"}],
                    },
                }
            ),
            iot_schema(),
        )
        assert ordered.plan.order[0].field == "device_id"
        assert not pilot.last_repairs
    with pytest.raises(_InvalidOutput, match="row_queries_disabled"):
        old._validate(
            json.dumps({"decision": "plan", "plan": row_plan().model_dump()}),
            iot_schema(),
        )


def test_row_truncation_public_projection_and_previous_turn():
    import test_ask_contract as h

    from grepbit.adapters.mcp_server import result_payload
    from grepbit.application.ask import AskSettings, ask
    from grepbit.domain.plan import PreviousTurn
    from grepbit.ports.query_executor import ExecutionResult

    class Executor(h._Executor):
        def execute(self, query, **kwargs):
            assert kwargs["max_rows"] == 2
            assert "LIMIT" not in query.physical_sql
            return ExecutionResult(
                rows=({"device_id": "d1"}, {"device_id": "d2"}),
                row_count=2,
                columns=("device_id",),
                truncated=True,
            )

    plan = row_plan(rows={"columns": [ref("devices", "device_id")]})
    previous = PreviousTurn(question="List devices", plan=plan)
    result = ask(
        "List them again",
        row_services(plan, Executor([])),
        AskSettings(as_of=AS_OF, max_rows=2),
        previous=previous,
    )
    payload = result_payload(result, max_rows=2)
    assert payload["rows_truncated"] and payload["row_count"] == 2
    assert payload["lineage"]["projection"] == ["devices.device_id"]
    assert "raw_output" not in payload
    assert previous.plan.rows is not None


def test_datasource_opt_in_reaches_request_owned_planner(monkeypatch, tmp_path):
    from grepbit.adapters import mcp_server as server
    from grepbit.application.request_lifecycle import RequestControl
    from grepbit.domain.datasource import DatasourceRegistration

    monkeypatch.setattr(server, "introspect_schema", lambda *a, **kw: iot_schema())
    registration = DatasourceRegistration(
        id="iot_test", dsn_env="OPAQUE_TEST_DSN", allow_rows=True
    )
    bound = server.bind_datasource(
        registration,
        tmp_path / "registry.json",
        {
            "OPAQUE_TEST_DSN": "unused-fixture",
            "GREPBIT_MODEL_BASE_URL": "http://unused",
            "GREPBIT_MODEL_NAME": "fixture",
        },
    )
    assert bound.services.planner._allow_rows
    assert bound.services.compiler._allow_rows
    owned = bound.request_factory(RequestControl(30))
    assert owned.planner._allow_rows and owned.planner is not bound.services.planner
    assert server.capabilities_payload({"iot_test": bound})["datasources"][0][
        "row_queries"
    ]
    assert not DatasourceRegistration(id="old", dsn_env="OPAQUE_TEST_DSN").allow_rows
