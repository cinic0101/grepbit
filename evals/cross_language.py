"""Bounded research plan comparison; agreement is never intent certification."""

import math
from datetime import datetime
from decimal import Decimal

from evals.concept_pilot import digest
from evals.metric_selection import OutsideFragment, _operand
from evals.reference_eval import evaluate
from evals.synthetic import DuckInstance
from grepbit.adapters.sqlglot.plan_compiler import PlanCompiler
from grepbit.domain.plan import QueryPlan

REVISION = "cross-language-comparison-v1"


def expression(plan, schema, overlay):
    """Only explicit supported scalar expressions; never discard extra shapes."""
    plan = QueryPlan.model_validate(plan.model_dump())
    if (
        not plan.base_table
        or schema.table(plan.base_table) is None
        or len(plan.measures) != 1
        or any(
            (
                plan.dimensions,
                plan.time,
                plan.order,
                plan.having,
                plan.growth,
                plan.without,
                plan.latest,
            )
        )
        or plan.limit is not None
        or plan.measures[0].share_of_total
        or (overlay and overlay.segments)
    ):
        raise OutsideFragment("outside_fragment")
    measure = plan.measures[0]
    operands = (
        (measure.ratio.numerator, measure.ratio.denominator)
        if measure.ratio
        else (measure,)
    )
    parts = []
    for operand in operands:
        basis, predicates = _operand(operand, plan, overlay, schema)
        parts.append((basis, tuple(sorted(predicates))))
    return ("ratio" if measure.ratio else "aggregate", tuple(parts))


def fixture_data(schema, instance):
    """Fixed fictional instances must respect column arity, nullability and PKs."""
    data = {}
    for table in schema.tables:
        rows = [
            dict(zip([c.name for c in table.columns], row, strict=True))
            for row in instance[table.name]
        ]
        if any(
            r[c.name] is None for r in rows for c in table.columns if not c.nullable
        ):
            raise ValueError("fixture_nullability")
        keys = [tuple(r[k] for k in table.primary_key) for r in rows]
        if table.primary_key and (
            len(keys) != len(set(keys)) or any(None in k for k in keys)
        ):
            raise ValueError("fixture_primary_key")
        data[table.name] = rows
    return data


def same_scalar(left, right):
    if left is None or right is None:
        return left is right
    numeric = (int, float, Decimal)
    if not isinstance(left, numeric) or not isinstance(right, numeric):
        return left == right
    return (
        math.isfinite(float(left))
        and math.isfinite(float(right))
        and math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    )


def scalar(rows):
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError("non_scalar_result")
    value = rows[0][0]
    if value is not None and not math.isfinite(float(value)):
        raise ValueError("nonfinite_result")
    return value


def compare(
    left, right, schema, overlay, instances, *, as_of, left_context, right_context
):
    """One shared, identity-bound context; witnesses use two local engines."""
    result = {"status": "unavailable", "certified": False, "checks": []}
    if not left_context or left_context != right_context:
        return {**result, "reason": "context_mismatch"}
    if left is None or right is None:
        return {**result, "reason": "missing_plan"}
    result.update(
        left_sha256=digest(left.model_dump(mode="json")),
        right_sha256=digest(right.model_dump(mode="json")),
        context_sha256=left_context,
    )
    try:
        signatures = [expression(p, schema, overlay) for p in (left, right)]
    except (ValueError, TypeError):
        return {**result, "status": "outside_fragment"}
    try:
        compiled = [
            PlanCompiler(schema, overlay=overlay).compile(p, as_of=as_of)
            for p in (left, right)
        ]
    except Exception:
        return {**result, "reason": "compile_refused"}
    if signatures[0] == signatures[1]:
        return {**result, "status": "equivalent_in_fragment"}
    for name, instance in instances.items():
        database = None
        try:
            data = fixture_data(schema, instance)
            database = DuckInstance(schema, data)
            values = []
            for plan, query in zip((left, right), compiled, strict=True):
                _, sql_rows = database.execute(query.compiled)
                ref = evaluate(
                    plan, schema, overlay, datetime.fromisoformat(as_of), data
                )
                ref_rows = [tuple(r[c] for c in query.output_columns) for r in ref]
                values.append((scalar(sql_rows), scalar(ref_rows)))
            if any(not same_scalar(sql, ref) for sql, ref in values):
                return {**result, "reason": "engine_disagreement"}
            different = not same_scalar(values[0][0], values[1][0])
            result["checks"].append(
                {
                    "instance": name,
                    "instance_sha256": digest(instance),
                    "sql": [None if v[0] is None else float(v[0]) for v in values],
                    "reference": [
                        None if v[1] is None else float(v[1]) for v in values
                    ],
                    "different": different,
                }
            )
        except Exception:
            return {**result, "reason": "local_execution_error"}
        finally:
            if database is not None:
                database.con.close()
    # All recorded engine checks must agree before any witness is credited.
    return {
        **result,
        "status": "witnessed_difference"
        if any(c["different"] for c in result["checks"])
        else "not_distinguished",
    }


def accounting(original, fidelity, pair, repeat):
    different = pair == "witnessed_difference"
    credit = (
        original == "wrong"
        and fidelity in {"reference_exact", "human_confirmed"}
        and different
    )
    return {
        "credit": credit,
        "incremental": credit and repeat == "equivalent_in_fragment",
        "false_alarm": original == "correct" and different,
        "persistent_wrong": original == "wrong" and pair == "equivalent_in_fragment",
        "translation_noise": different and fidelity in {"changed", "unreviewed"},
        "certified": False,
    }


def may_advance(
    *,
    incremental,
    correct_controls,
    comparable_correct,
    false_alarms,
    accounted_slots,
    fidelity_unreviewed,
):
    return (
        incremental >= 1
        and correct_controls > 0
        and comparable_correct == correct_controls
        and false_alarms == 0
        and accounted_slots == 12
        and fidelity_unreviewed == 0
    )
