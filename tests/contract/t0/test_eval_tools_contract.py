"""Offline regressions for the evaluation tools, using synthetic data only."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from t0_helpers import ROOT, iot_schema

from grepbit.domain.plan import PlanError


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "evals" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _report(*plans):
    return {
        "summary": {"cases_file": "synthetic.yaml", "prompt_revision": "v-test"},
        "results": [
            {"case_id": f"q{i}", "status": "answered", "plan": p}
            for i, p in enumerate(plans)
        ],
    }


PLAN = {
    "base_table": "t",
    "measures": [
        {"aggregate": "sum", "column": {"table": "t", "column": "x"}, "alias": "s"}
    ],
    "dimensions": [{"table": "t", "column": "group"}],
    "order": [
        {"field": "s", "direction": "desc"},
        {"field": "group", "direction": "asc"},
    ],
    "limit": 1,
}


def test_stability_preserves_order_priority():
    module = _load("stability")
    other = deepcopy(PLAN)
    other["order"].reverse()
    assert module.stability([_report(PLAN), _report(other)])["plan_stability"] == 0


def test_stability_preserves_latest_tie_break_priority():
    module = _load("stability")
    plan = {
        "latest": {
            "order_by": [
                {"column": {"table": "t", "column": "at"}, "direction": "desc"},
                {"column": {"table": "t", "column": "id"}, "direction": "desc"},
            ]
        }
    }
    other = deepcopy(plan)
    other["latest"]["order_by"].reverse()
    assert module.plan_core(plan) != module.plan_core(other)


def test_stability_preserves_dimension_order_used_by_implicit_sort():
    module = _load("stability")
    plan = deepcopy(PLAN)
    plan.pop("order")
    plan["dimensions"].append({"table": "t", "column": "other"})
    other = deepcopy(plan)
    other["dimensions"].reverse()
    assert module.plan_core(plan) != module.plan_core(other)


def test_stability_renames_alias_references_but_not_literals_or_source_columns():
    module = _load("stability")
    plan = deepcopy(PLAN)
    plan.update(
        having=[{"field": "s", "op": "gt", "value": 1}], growth=[{"measure": "s"}]
    )
    plan["filters"] = [
        {"column": {"table": "t", "column": "s"}, "op": "eq", "values": ["s"]}
    ]
    other = deepcopy(plan)
    other["measures"][0]["alias"] = "銷售額"
    other["order"][0]["field"] = "銷售額"
    other["having"][0]["field"] = "銷售額"
    other["growth"][0]["measure"] = "銷售額"
    assert module.plan_core(plan) == module.plan_core(other)
    other["filters"][0]["values"] = ["銷售額"]
    assert module.plan_core(plan) != module.plan_core(other)


def test_stability_follows_default_output_names_and_measure_reordering():
    module = _load("stability")
    plan = {
        "measures": [
            {"aggregate": "count"},
            {"aggregate": "sum", "column": {"table": "t", "column": "x"}},
        ],
        "order": [{"field": "row_count", "direction": "desc"}],
    }
    other = deepcopy(plan)
    other["measures"][0]["alias"] = "n"
    other["order"][0]["field"] = "n"
    other["measures"].reverse()
    assert module.plan_core(plan) == module.plan_core(other)


def test_stability_normalises_conjunction_and_in_membership_order():
    module = _load("stability")
    plan = deepcopy(PLAN)
    plan["filters"] = [
        {"column": {"table": "t", "column": "group"}, "op": "in", "values": ["a", "b"]},
        {"column": {"table": "t", "column": "x"}, "op": "gt", "values": [0]},
    ]
    other = deepcopy(plan)
    other["filters"][0]["values"].reverse()
    other["filters"].reverse()
    assert module.plan_core(plan) == module.plan_core(other)


def test_stability_does_not_erase_a_changed_measure_reference():
    module = _load("stability")
    plan = deepcopy(PLAN)
    plan["measures"].append(
        {"aggregate": "sum", "column": {"table": "t", "column": "y"}, "alias": "other"}
    )
    other = deepcopy(plan)
    other["order"][0]["field"] = "other"
    assert module.plan_core(plan) != module.plan_core(other)


@pytest.mark.parametrize(
    "problem", ["missing", "duplicate", "empty", "single", "count"]
)
def test_stability_rejects_incomplete_or_nonrepeated_runs(problem):
    module = _load("stability")
    reports = [_report(PLAN), _report(PLAN)]
    if problem == "missing":
        reports[1]["results"] = []
    elif problem == "duplicate":
        reports[1]["results"] *= 2
    elif problem == "empty":
        reports = [_report(), _report()]
    elif problem == "single":
        reports.pop()
    else:
        reports[0]["summary"]["cases"] = 2
    with pytest.raises(ValueError, match="stability_"):
        module.stability(reports)


@pytest.mark.parametrize(
    "field", ["cases_file", "prompt_revision", "model", "datasource_id", "as_of"]
)
def test_stability_rejects_mixed_experiment_metadata(field):
    module = _load("stability")
    a, b = _report(PLAN), _report(PLAN)
    a["summary"][field], b["summary"][field] = "a", "b"
    with pytest.raises(ValueError, match="stability_"):
        module.stability([a, b])


def test_stability_cli_does_not_write_a_score_for_incomplete_runs(tmp_path, capsys):
    module = _load("stability")
    a, b, output = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "score.json"
    a.write_text(json.dumps(_report(PLAN)))
    b.write_text(json.dumps(_report()))
    assert module.main(["--reports", str(a), str(b), "--output", str(output)]) == 2
    assert not output.exists()
    assert "stability_" in capsys.readouterr().out


@pytest.mark.parametrize("source_limit", [20, None, 0])
def test_redacted_replay_keeps_source_sensitivity_across_generations(
    tmp_path, monkeypatch, source_limit
):
    module = _load("differential")
    schema = iot_schema()
    sentinel = "SYNTHETIC_PRIVATE_VALUE"
    plan = {
        "base_table": "devices",
        "measures": [{"aggregate": "count"}],
        "filters": [
            {
                "column": {"table": "devices", "column": "status"},
                "op": "eq",
                "values": [sentinel],
            }
        ],
    }
    source = {
        "schema_digest": schema.digest(),
        "plans": [{"plan": plan, "exclude_segments": []}],
    }
    if source_limit is not None:
        source["enum_distinct_limit"] = source_limit
    path = tmp_path / "source.json"
    path.write_text(json.dumps(source))
    monkeypatch.setenv("GREPBIT_TOOL_TEST_DSN", "unused-by-offline-test")
    monkeypatch.setattr(module, "introspect_schema", lambda *a, **k: schema)
    monkeypatch.setattr(module, "load_tables", lambda *a: {})

    def no_connection(*args, **kwargs):
        pytest.fail("offline replay test must not open a database connection")

    monkeypatch.setattr(module.psycopg, "connect", no_connection)

    def refuse(*args, **kwargs):
        raise PlanError("share_requires_groups", "synthetic refusal before execution")

    monkeypatch.setattr(module.PlanCompiler, "compile", refuse)
    # An unredacted replay must not relabel sampled/unknown values as safe,
    # even though current introspection defaults to zero.
    args = ["--dsn-env", "GREPBIT_TOOL_TEST_DSN", "--datasource-id", "iot_test"]
    intermediate, output = tmp_path / "intermediate.json", tmp_path / "redacted.json"
    assert (
        module.main([*args, "--replay", str(path), "--output", str(intermediate)]) == 0
    )
    assert (
        module.main(
            [*args, "--redact", "--replay", str(intermediate), "--output", str(output)]
        )
        == 0
    )
    report = json.loads(output.read_text())
    sensitive = source_limit != 0
    assert report["plans_redacted"] is sensitive
    assert (sentinel in output.read_text()) is not sensitive
    assert report["plans_carry_data"] is sensitive


@pytest.mark.parametrize("stage", ["compiler", "database", "evaluator"])
def test_redacted_errors_do_not_leak_row_or_literal_values(
    tmp_path, monkeypatch, stage
):
    module = _load("differential")
    schema = iot_schema()
    sentinel = "SYNTHETIC_PRIVATE_ERROR_VALUE"
    monkeypatch.setenv("GREPBIT_TOOL_TEST_DSN", "unused-by-offline-test")
    monkeypatch.setattr(module, "introspect_schema", lambda *a, **k: schema)
    monkeypatch.setattr(module, "load_tables", lambda *a: {})
    monkeypatch.setattr(
        module,
        "generate_plans",
        lambda *a: [{"base_table": "devices", "measures": [{"aggregate": "count"}]}],
    )

    def no_connection(*args, **kwargs):
        pytest.fail("offline error test must not open a database connection")

    monkeypatch.setattr(module.psycopg, "connect", no_connection)

    def fail(*args, **kwargs):
        raise ValueError(sentinel)

    if stage == "compiler":
        monkeypatch.setattr(module.PlanCompiler, "compile", fail)
    monkeypatch.setattr(
        module.PsycopgQueryExecutor,
        "execute",
        lambda *a, **k: SimpleNamespace(
            columns=("row_count",),
            rows=({"row_count": 1},),
            error_code=sentinel if stage == "database" else None,
            truncated=False,
        ),
    )
    monkeypatch.setattr(module, "evaluate", fail)
    output = tmp_path / "report.json"
    assert (
        module.main(
            [
                "--dsn-env",
                "GREPBIT_TOOL_TEST_DSN",
                "--datasource-id",
                "iot_test",
                "--redact",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert len(report["errors"]) == 1
    assert (
        report["errors"][0]["kind"]
        == {
            "compiler": "compiler_exception",
            "database": "database_error",
            "evaluator": "evaluator_exception",
        }[stage]
    )
    assert sentinel not in output.read_text()
