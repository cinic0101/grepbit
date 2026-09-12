"""Value grounding: normalization, mentions, candidates, resolution, plan substitution,
value loading, and the planner hint."""

from __future__ import annotations

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    GroundingModelSettings,
)
from grepbit.adapters.postgres.value_index import load_column_values
from grepbit.application.grounding import (
    ValueIndex,
    edit_distance,
    normalize_value,
    resolve_plan_literals,
)
from grepbit.domain.plan import ColumnRef, QueryPlan

STORES = [
    "特約台南崇德",
    "特約新店遠東",
    "特約板橋華江",
    "特約永和中正",
    "特約竹東長春二",
]
CATEGORIES = ["資訊商品類", "通訊商品類", "家電商品類", "保健‧保養", "二手回收類"]
INDEX = ValueIndex({"store.store_name": STORES, "category.category_name": CATEGORIES})


def test_normalization_drops_space_case_and_punctuation() -> None:
    assert normalize_value("特約 新店遠東") == "特約新店遠東"
    assert normalize_value(" Credit-Card ") == "creditcard"
    assert normalize_value("保健‧保養") == "保健保養"
    assert edit_distance("永和中正", "永和中") == 1


def test_mentions_find_verbatim_values_across_a_segmentation_boundary() -> None:
    hits = INDEX.mentions("特約永和中正在這禮拜的銷售總額是多少？")
    assert [(m.column, m.value) for m in hits] == [("store.store_name", "特約永和中正")]
    assert INDEX.mentions("各門市營業額") == []
    # a value contained in a longer matched value of the same column is dropped
    nested = ValueIndex({"c": ["永和", "特約永和中正"]})
    assert [m.value for m in nested.mentions("特約永和中正的營業額")] == [
        "特約永和中正"
    ]


@pytest.mark.parametrize(
    ("literal", "kind", "value"),
    [
        ("特約永和中", "unique", "特約永和中正"),  # cut at a segmentation boundary
        ("特約 新店遠東", "exact", "特約新店遠東"),  # space inside the name
        ("特約板橋華汪", "unique", "特約板橋華江"),  # one wrong character
        ("台南", "unique", "特約台南崇德"),  # abbreviation contained in the value
        ("永和中正", "unique", "特約永和中正"),
        ("信義", "none", None),  # nothing similar
    ],
)
def test_resolution_classes_on_store_names(literal, kind, value) -> None:
    resolution = INDEX.resolve("store.store_name", literal)
    assert resolution.kind == kind
    assert resolution.value == value


def test_ambiguous_when_two_values_score_alike() -> None:
    index = ValueIndex({"c": ["通訊商品類", "資訊商品類"]})
    resolution = index.resolve("c", "訊商品類")
    assert resolution.kind == "ambiguous"
    assert {c.value for c in resolution.candidates} == {"通訊商品類", "資訊商品類"}
    assert INDEX.resolve("nowhere.col", "x").kind == "none"  # not a groundable column


def test_plan_substitution_replaces_only_uniquely_resolved_literals() -> None:
    plan = QueryPlan.model_validate(
        {
            "base_table": "pos_sale",
            "measures": [{"aggregate": "count"}],
            "filters": [
                {
                    "column": {"table": "store", "column": "store_name"},
                    "op": "in",
                    "values": ["特約永和中", "特約板橋華江"],
                },
                {
                    "column": {"table": "category", "column": "category_name"},
                    "op": "eq",
                    "values": ["訊商品類"],
                },
            ],
        }
    )
    index = ValueIndex(
        {
            "store.store_name": STORES,
            "category.category_name": ["通訊商品類", "資訊商品類"],
        }
    )
    resolved, resolutions = resolve_plan_literals(
        plan,
        [("store.store_name", "特約永和中"), ("category.category_name", "訊商品類")],
        index,
    )
    assert resolved.filters[0].values == ["特約永和中正", "特約板橋華江"]
    assert resolved.filters[1].values == ["訊商品類"]  # ambiguous: untouched
    assert [r.kind for r in resolutions] == ["unique", "ambiguous"]
    untouched, _ = resolve_plan_literals(plan, [("store.store_name", "信義")], index)
    assert untouched is plan


class _Connection:
    def __init__(self, rows_by_column: dict[str, list[str]]) -> None:
        self.rows_by_column = rows_by_column
        self.queries: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        text = query if isinstance(query, str) else query.as_string(None)
        self.queries.append(text)
        column = next((c for c in self.rows_by_column if f'"{c}"' in text), None)

        class _Result:
            def fetchall(inner):
                return [(v,) for v in self.rows_by_column.get(column, [])]

        return _Result()

    def rollback(self):
        pass


def test_loader_caps_cardinality_reads_enums_as_text_and_skips_unknown_columns():
    connection = _Connection(
        {"model": ["AP-300", "GW-10"], "status": [f"s{i}" for i in range(7)]}
    )
    values, skipped = load_column_values(
        lambda: connection,
        iot_schema(),
        [
            ColumnRef(table="devices", column="model"),
            ColumnRef(table="devices", column="status"),
            ColumnRef(table="devices", column="nothing"),
        ],
        cap=5,
    )
    assert values == {"devices.model": ["AP-300", "GW-10"]}
    assert skipped == ["devices.status", "devices.nothing"]
    assert connection.queries[0] == "BEGIN READ ONLY"
    assert any("LIMIT 6" in q for q in connection.queries)


def test_planner_receives_question_values_and_the_rule_only_when_present() -> None:
    from grepbit.domain.overlay import SemanticOverlay

    client = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://model.local/v1", model="m")
    )
    with_hint = client.build_messages(
        "特約永和中正在這禮拜的銷售總額",
        iot_schema(),
        as_of="2026-02-04T18:00:00+08:00",
        question_values=[{"column": "devices.model", "value": "特約永和中正"}],
        overlay=SemanticOverlay.model_validate(
            {
                "datasource_id": "iot_test",
                "revision": "test",
                "column_policies": [
                    {"column": {"table": "devices", "column": "model"}}
                ],
            }
        ),
    )
    assert "question_values" in with_hint[0]["content"]
    assert '"question_values": [{"column": "devices.model"' in with_hint[2]["content"]
    without = client.build_messages(
        "各門市營業額", iot_schema(), as_of="2026-02-04T18:00:00+08:00"
    )
    assert "question_values" not in without[0]["content"]
    assert "question_values" not in without[2]["content"]
