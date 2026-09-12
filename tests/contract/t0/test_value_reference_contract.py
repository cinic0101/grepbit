"""A5: request-scoped, column-bound literal references; no new data exposure."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.litellm import plan_wire
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    _InvalidOutput,
)
from grepbit.domain.overlay import SemanticOverlay
from grepbit.ports.grounding import GroundingModelError


def overlay():
    return SemanticOverlay.model_validate(
        {
            "datasource_id": "iot_test",
            "revision": "a5-test",
            "column_policies": [
                {
                    "column": {"table": "devices", "column": "model"},
                    "sensitivity": "public",
                    "ground": True,
                }
            ],
        }
    )


HINTS = [{"column": "devices.model", "value": "北區／測試設備 (AP-300)"}]


@pytest.mark.parametrize(
    "form", ["flat", "nested", "nested_numerator", "nested_denominator"]
)
@pytest.mark.parametrize("references", [False, True])
def test_ratio_operands_survive_reference_resolution_and_wire_normalisation(
    form, references
):
    items = catalog()
    condition = {"column": "devices.model", "op": "eq"}
    condition["value_refs" if references else "values"] = [
        items[0]["id"] if references else items[0]["value"]
    ]
    numerator = {
        "aggregate": "sum",
        "column": "alerts.downtime_minutes",
        "filters": [condition],
    }
    denominator = {"aggregate": "count"}
    measure = {"alias": "rate"}
    for side, operand in [("numerator", numerator), ("denominator", denominator)]:
        if form == "nested" or form == f"nested_{side}":
            measure.setdefault("ratio", {})[side] = operand
        else:
            measure[side] = operand
    payload = {
        "decision": "plan",
        "plan": {"base_table": "alerts", "measures": [measure]},
    }
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="unused")
    )
    proposal = client._validate(json.dumps(payload), iot_schema(), candidates=items)
    ratio = proposal.plan.measures[0].ratio
    assert ratio.numerator.aggregate.value == "sum"
    assert ratio.numerator.column.id == "alerts.downtime_minutes"
    assert ratio.numerator.filters[0].column.id == "devices.model"
    assert ratio.numerator.filters[0].values == [items[0]["value"]]
    assert ratio.denominator.aggregate.value == "count"
    assert ratio.denominator.column is None and not ratio.denominator.filters
    assert client.last_value_refs == int(references)


@pytest.mark.parametrize("missing", ["numerator", "denominator"])
@pytest.mark.parametrize("form", ["flat", "nested"])
def test_incomplete_ratio_is_rejected_without_guessing_an_operand(missing, form):
    present = "denominator" if missing == "numerator" else "numerator"
    measure = {present: {"aggregate": "count"}}
    if form == "nested":
        measure = {"ratio": measure}
    payload = {
        "decision": "plan",
        "plan": {"base_table": "alerts", "measures": [measure]},
    }
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="unused")
    )
    with pytest.raises(_InvalidOutput, match=missing):
        client._validate(json.dumps(payload), iot_schema(), candidates=catalog())


def catalog():
    # getattr makes a missing implementation a ruler assertion, not import failure.
    function = getattr(plan_wire, "value_candidates", None)
    assert callable(function), "A5 candidate catalog is not implemented"
    return function(HINTS, iot_schema(), overlay())


def test_catalog_is_exact_stable_and_does_not_expand_authorised_columns():
    items = catalog()
    assert items[0]["value"] == HINTS[0]["value"]
    assert items[0]["column"] == "devices.model"
    assert items[0]["id"].startswith("v_")
    hints = [*HINTS, {"column": "devices.status", "value": "PRIVATE_SENTINEL"}]
    assert plan_wire.value_candidates(hints, iot_schema(), overlay()) == items
    assert (
        plan_wire.value_candidates(list(reversed(hints)), iot_schema(), overlay())
        == items
    )
    assert plan_wire.value_candidates(HINTS, iot_schema(), None) == []


@pytest.mark.parametrize(
    "where", ["plan", "measure", "numerator", "denominator", "without"]
)
def test_reference_resolution_reaches_every_filter_position(where):
    items = catalog()
    condition = {"column": "devices.model", "op": "eq", "value_refs": [items[0]["id"]]}
    holder = {"filters": [condition]}
    plan = {"measures": []}
    if where == "plan":
        plan.update(holder)
    elif where == "measure":
        plan["measures"] = [holder]
    elif where in {"numerator", "denominator"}:
        plan["measures"] = [{where: holder}]
    else:
        plan["without"] = holder
    assert plan_wire.resolve_value_refs(plan, items) == 1
    assert condition == {
        "column": "devices.model",
        "op": "eq",
        "values": [HINTS[0]["value"]],
    }


@pytest.mark.parametrize(
    "problem",
    ["unknown", "wrong_column", "both", "empty", "scalar", "op", "no_catalog"],
)
def test_invalid_references_fail_closed_without_literal_fallback(problem):
    items = catalog()
    condition = {"column": "devices.model", "op": "eq", "value_refs": [items[0]["id"]]}
    if problem == "unknown":
        condition["value_refs"] = ["v_unknown"]
    if problem == "wrong_column":
        condition["column"] = "devices.status"
    if problem == "both":
        condition["values"] = ["do not fallback"]
    if problem == "empty":
        condition["value_refs"] = []
    if problem == "scalar":
        condition["value_refs"] = items[0]["id"]
    if problem == "op":
        condition["op"] = "gt"
    if problem == "no_catalog":
        items = []
    with pytest.raises(ValueError, match="candidate_reference_"):
        plan_wire.resolve_value_refs({"filters": [condition]}, items)


def test_literal_that_looks_like_an_id_is_not_a_reference():
    items = catalog()
    plan = {
        "filters": [{"column": "devices.model", "op": "eq", "values": [items[0]["id"]]}]
    }
    original = deepcopy(plan)
    assert plan_wire.resolve_value_refs(plan, items) == 0
    assert plan == original


def test_candidate_schema_is_only_shown_when_candidates_are_available():
    catalog()
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="unused")
    )
    args = {"as_of": "2026-09-12T12:00:00+08:00"}
    messages = client.build_messages(
        "設備數", iot_schema(), question_values=HINTS, overlay=overlay(), **args
    )
    assert "value_refs" in messages[0]["content"]
    assert "value_refs" in messages[1]["content"]
    assert "id" in json.loads(messages[2]["content"])["question_values"][0]
    without = client.build_messages("設備數", iot_schema(), **args)
    assert "value_refs" not in without[1]["content"]


def test_structured_decoding_uses_the_reference_wire_not_the_literal_domain():
    catalog()
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(
            base_url="http://unused",
            model="unused",
            structured_output_mode="json_schema",
        )
    )
    schema = client.response_format(has_candidates=True)["json_schema"]["schema"]
    assert "value_refs" in json.dumps(schema)


def test_propose_resolves_before_domain_validation_and_rejects_stale_catalog():
    items = catalog()
    payload = {
        "decision": "plan",
        "plan": {
            "base_table": "devices",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {"column": "devices.model", "op": "eq", "value_refs": [items[0]["id"]]}
            ],
        },
    }
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))
            ]
        )

    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete))
    )
    client = ChatCompletionsPlanClient(
        GroundingModelSettings(
            base_url="http://unused", model="unused", repair_turns=0
        ),
        client=fake,
    )
    kwargs = {"as_of": "2026-09-12T12:00:00+08:00", "overlay": overlay()}
    proposal = client.propose("設備數", iot_schema(), question_values=HINTS, **kwargs)
    assert proposal.plan.filters[0].values == [HINTS[0]["value"]]
    assert "value_refs" not in proposal.model_dump_json()
    assert client.last_value_refs == 1
    # A later request cannot reuse a catalog retained by the client.
    with pytest.raises(GroundingModelError):
        client.propose("設備數", iot_schema(), **kwargs)
    assert client.last_value_refs == 0 and client.last_value_ref_errors == 1
    assert len(calls) == 2


def test_in_references_preserve_order_and_exact_spelling():
    hints = HINTS + [{"column": "devices.model", "value": "北區 測試設備 AP-300"}]
    items = plan_wire.value_candidates(hints, iot_schema(), overlay())
    plan = {
        "filters": [
            {
                "column": {"table": "devices", "column": "model"},
                "op": "in",
                "value_refs": [item["id"] for item in items],
            }
        ]
    }
    assert plan_wire.resolve_value_refs(plan, items) == 2
    assert plan["filters"][0]["values"] == [item["value"] for item in items]


def test_personal_and_hidden_columns_never_enter_candidate_messages():
    public = overlay()
    for policy in (
        {"sensitivity": "personal", "ground": None},
        {"visible": False},
        {"ground": False},
    ):
        private = public.model_copy(deep=True)
        private.column_policies[0] = private.column_policies[0].model_copy(
            update=policy
        )
        assert plan_wire.value_candidates(HINTS, iot_schema(), private) == []
