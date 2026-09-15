"""Known lexical limitation; these tests do not authorize disabling a gate."""

from grepbit.adapters.language_pack_store import load_shape_pack
from grepbit.application.shapes import unmapped_concepts
from grepbit.domain.plan import QueryPlan


def test_output_verb_and_business_scope_have_same_current_gate_features():
    plan = QueryPlan(
        base_table="work_logs",
        measures=[{"aggregate": "count"}],
        filters=[
            {"column": {"table": "work_logs", "column": "minutes"}, "op": "not_null"}
        ],
    )
    pack = load_shape_pack()
    instruction = (
        "Return the count of work_logs records whose minutes field is not NULL."
    )
    business_scope = (
        "Count work_logs records for product returns whose minutes field is not NULL."
    )
    first = unmapped_concepts(instruction, plan, pack, None, set())
    second = unmapped_concepts(business_scope, plan, pack, None, set())
    # Different request meanings, same plan and triggered concept ID. Dropping
    # the first hit solely on source applicability also drops the second one.
    assert [c for c, word in first] == [c for c, word in second] == ["returns"]


def test_command_and_real_concept_can_coexist():
    plan = QueryPlan(base_table="work_logs", measures=[{"aggregate": "count"}])
    hits = unmapped_concepts(
        "Return the count of work logs for product returns.",
        plan,
        load_shape_pack(),
        None,
        set(),
    )
    assert [concept for concept, word in hits] == ["returns"]
