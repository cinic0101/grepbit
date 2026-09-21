"""Pure P3 accounting over frozen metadata; no questions, oracles or execution.

Scores count explicit, non-observational families. Every inventoried variant
must pass, including variants whose family is not a mandatory control.
Per-language scores instead count inputs and are diagnostics, not promotion
scores. Fractions are reduced exact rationals, or None for empty denominators.
Agreement is unassessed (None) unless every variant has a completed signature.
"""

from collections import Counter
from fractions import Fraction
import re

from tools.p3_assets import EXPOSURES, LANGUAGES, OUTCOMES, P3Error


_SUCCESS = {
    "answer": "complete_correct",
    "clarify": "correct_clarification",
    "decline": "correct_decline",
}
_COHORT_BRANCH = {
    "answer": "answer", "clarify": "clarify", "decline": "decline", "anchor": "answer",
}
_FAMILY_FIELDS = (
    "expected_branch", "cohort", "exposure", "must_pass", "observational", "semantic_signature",
)
_STATUSES = ("pending", "in_progress", "completed", "not_run")
_RUN_STATUSES = ("pending", "prepared", "in_progress", "incomplete", "complete")
_FIRST_SLICE_OUTCOMES = tuple(outcome for outcome in OUTCOMES if outcome != "synthesis_error")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not any(char.isspace() for char in value)


def _inputs_by_family(inputs: list[dict], code: str) -> dict[str, list[dict]]:
    if not isinstance(inputs, list):
        raise P3Error(code)
    families: dict[str, list[dict]] = {}
    case_ids: set[str] = set()
    for order, item in enumerate(inputs, 1):
        if not isinstance(item, dict):
            raise P3Error(code)
        if (not _identifier(item.get("case_id")) or not _identifier(item.get("family_id"))
                or item["case_id"] in case_ids
                or type(item.get("order")) is not int or item["order"] != order
                or not isinstance(item.get("language"), str) or item["language"] not in LANGUAGES
                or not isinstance(item.get("cohort"), str) or item["cohort"] not in _COHORT_BRANCH
                or item.get("expected_branch") != _COHORT_BRANCH[item["cohort"]]
                or not isinstance(item.get("exposure"), str) or item["exposure"] not in EXPOSURES
                or type(item.get("must_pass")) is not bool
                or type(item.get("observational")) is not bool
                or not isinstance(item.get("semantic_signature"), str)
                or not item["semantic_signature"].strip()):
            raise P3Error(code)
        case_ids.add(item["case_id"])
        variants = families.setdefault(item["family_id"], [])
        if variants and any(item[field] != variants[0][field] for field in _FAMILY_FIELDS):
            raise P3Error(code)
        variants.append(item)
    return families


def validate_formal_allocation(inputs: list[dict]) -> None:
    """Validate the admitted 24/44 allocation, not novelty or oracle correctness."""
    families = _inputs_by_family(inputs, "invalid_panel")
    if len(families) != 24 or len(inputs) != 44:
        raise P3Error("invalid_panel")
    if any(item["observational"] or not item["must_pass"] or item["exposure"] == "design_seen"
           or item["case_id"] == "P21" or item["family_id"] == "P21" or item.get("slot") == "P21"
           for item in inputs):
        raise P3Error("invalid_panel")
    representatives = [variants[0] for variants in families.values()]
    family_cohorts = Counter(item["cohort"] for item in representatives)
    input_cohorts = Counter(item["cohort"] for item in inputs)
    family_exposures = Counter(item["exposure"] for item in representatives)
    input_exposures = Counter(item["exposure"] for item in inputs)
    allocation = Counter((item["cohort"], item["exposure"]) for item in representatives)
    if (family_cohorts != {"answer": 12, "clarify": 4, "decline": 5, "anchor": 3}
            or input_cohorts != {"answer": 18, "clarify": 8, "decline": 9, "anchor": 9}
            or family_exposures != {"frozen_fresh": 12, "exposed_regression": 12}
            or input_exposures != {"frozen_fresh": 26, "exposed_regression": 18}
            or allocation != {
                ("answer", "frozen_fresh"): 8, ("answer", "exposed_regression"): 4,
                ("clarify", "frozen_fresh"): 2, ("clarify", "exposed_regression"): 2,
                ("decline", "frozen_fresh"): 2, ("decline", "exposed_regression"): 3,
                ("anchor", "exposed_regression"): 3,
            }
            or Counter(item["language"] for item in inputs) != {"zh-TW": 14, "en": 15, "ja": 15}):
        raise P3Error("invalid_panel")


def required_successes(total: int) -> int:
    """The exact integer ceiling of 90 percent, without floating-point rounding."""
    if type(total) is not int or total < 0:
        raise P3Error("invalid_scoring")
    return (9 * total + 9) // 10


def _score(numerator: int, denominator: int) -> dict:
    fraction = Fraction(numerator, denominator) if denominator else None
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": None if fraction is None else {
            "numerator": fraction.numerator, "denominator": fraction.denominator,
        },
    }


def _outcomes(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows if row["outcome"] is not None)
    return {outcome: counts[outcome] for outcome in _FIRST_SLICE_OUTCOMES if counts[outcome]}


def _statuses(rows: list[dict]) -> dict:
    counts = Counter(row["status"] for row in rows)
    return {status: counts[status] for status in _STATUSES}


def _family_group(families: list[dict]) -> dict:
    scored = [family for family in families if not family["observational"]]
    mandatory = [family for family in scored if family["must_pass"]]
    return {
        "family_count": len(families),
        "input_count": sum(family["input_count"] for family in families),
        "observational_family_count": len(families) - len(scored),
        "family_score": _score(sum(family["family_all_variants_correct"] for family in scored), len(scored)),
        "mandatory_score": _score(sum(family["family_all_variants_correct"] for family in mandatory),
                                  len(mandatory)),
    }


def _input_score(rows: list[dict]) -> dict:
    scored = [row for row in rows if not row["observational"]]
    return _score(sum(row["correct"] for row in scored), len(scored))


def _threshold_met(score: dict) -> bool:
    return score["denominator"] > 0 and score["numerator"] >= required_successes(score["denominator"])


def _all_pass(score: dict) -> bool:
    return score["denominator"] > 0 and score["numerator"] == score["denominator"]


def summarize(inputs: list[dict], results: list[dict], *, panel_kind: str, run_status: str) -> dict:
    """Account for the complete ordered inventory, including unresolved rows.

    The runner's terminal status is ``complete``; per-result status is
    ``completed``. Formal eligibility means the metadata allocation is admitted,
    not that authorship, independence, or owner acceptance has been established.
    Runtime/grading details remain in the caller's result records; this function
    copies only accounting fields and never derives or repairs an outcome.
    """
    families = _inputs_by_family(inputs, "invalid_scoring")
    if (panel_kind not in ("development", "formal") or run_status not in _RUN_STATUSES
            or not isinstance(results, list) or len(results) != len(inputs)):
        raise P3Error("invalid_scoring")
    if panel_kind == "formal":
        validate_formal_allocation(inputs)
    per_input = []
    for item, result in zip(inputs, results):
        if not isinstance(result, dict):
            raise P3Error("invalid_scoring")
        status = result.get("status")
        outcome = result.get("outcome")
        signature = result.get("actual_signature")
        if (result.get("case_id") != item["case_id"] or status not in _STATUSES
                or "outcome" not in result or "actual_signature" not in result
                or type(result.get("checked_wrong")) is not bool
                or (signature is not None and
                    (not isinstance(signature, str) or _SHA256.fullmatch(signature) is None))
                or ("order" in result and
                    (type(result["order"]) is not int or result["order"] != item["order"]))):
            raise P3Error("invalid_scoring")
        if status in ("pending", "in_progress"):
            if outcome is not None:
                raise P3Error("invalid_scoring")
        elif status == "not_run":
            if outcome != "not_run" or signature is not None or result["checked_wrong"]:
                raise P3Error("invalid_scoring")
        elif (not isinstance(outcome, str) or outcome not in _FIRST_SLICE_OUTCOMES
              or outcome == "not_run"):
            raise P3Error("invalid_scoring")
        per_input.append({
            **{field: item[field] for field in ("order", "case_id", "family_id", "language", *_FAMILY_FIELDS)},
            "status": status, "outcome": outcome, "actual_signature": signature,
            "checked_wrong": result["checked_wrong"],
            "correct": status == "completed" and outcome == _SUCCESS[item["expected_branch"]],
        })
    per_family = {}
    for family_id, variants in families.items():
        rows = [per_input[item["order"] - 1] for item in variants]
        signatures = [row["actual_signature"] for row in rows]
        agreement_assessed = all(row["status"] == "completed" and row["actual_signature"] is not None
                                 for row in rows)
        per_family[family_id] = {
            **{field: variants[0][field] for field in _FAMILY_FIELDS},
            "case_ids": [row["case_id"] for row in rows],
            "languages": [row["language"] for row in rows],
            "input_count": len(rows), "outcomes": _outcomes(rows), "statuses": _statuses(rows),
            "family_all_variants_correct": all(row["correct"] for row in rows),
            "family_all_variants_agree": len(set(signatures)) == 1 if agreement_assessed else None,
            "checked_wrong": any(row["checked_wrong"] for row in rows),
        }
    family_rows = list(per_family.values())
    by_cohort = {}
    for cohort in _COHORT_BRANCH:
        selected = [family for family in family_rows if family["cohort"] == cohort]
        by_cohort[cohort] = {
            **_family_group(selected),
            "by_exposure": {
                exposure: _family_group([family for family in selected if family["exposure"] == exposure])
                for exposure in EXPOSURES
            },
        }
    by_exposure = {
        exposure: _family_group([family for family in family_rows if family["exposure"] == exposure])
        for exposure in EXPOSURES
    }
    per_language = {}
    for language in LANGUAGES:
        rows = [row for row in per_input if row["language"] == language]
        per_language[language] = {
            "case_ids": [row["case_id"] for row in rows], "input_count": len(rows),
            "observational_input_count": sum(row["observational"] for row in rows),
            "outcomes": _outcomes(rows), "statuses": _statuses(rows), "input_score": _input_score(rows),
            "by_cohort": {
                cohort: _input_score([row for row in rows if row["cohort"] == cohort])
                for cohort in _COHORT_BRANCH
            },
            "by_exposure": {
                exposure: _input_score([row for row in rows if row["exposure"] == exposure])
                for exposure in EXPOSURES
            },
        }
    answer = by_cohort["answer"]["family_score"]
    fresh_answer = by_cohort["answer"]["by_exposure"]["frozen_fresh"]["family_score"]
    exposed_answer = by_cohort["answer"]["by_exposure"]["exposed_regression"]["family_score"]
    checked_wrong_ids = [row["case_id"] for row in per_input if row["checked_wrong"]]
    gates = {
        "complete_run": run_status == "complete" and all(row["status"] == "completed" for row in per_input),
        "answer_threshold": _threshold_met(answer),
        "fresh_answer_threshold": _threshold_met(fresh_answer),
        "exposed_answer_controls": _all_pass(exposed_answer),
        "clarification_controls": _all_pass(by_cohort["clarify"]["family_score"]),
        "decline_controls": _all_pass(by_cohort["decline"]["family_score"]),
        "anchors": _all_pass(by_cohort["anchor"]["family_score"]),
        "mandatory_families": _all_pass(_family_group(family_rows)["mandatory_score"]),
        "no_checked_wrong": not checked_wrong_ids,
    }
    return {
        "panel_kind": panel_kind, "run_status": run_status,
        "input_count": len(inputs), "semantic_families": len(families),
        "scored_families": sum(not family["observational"] for family in family_rows),
        "observational_families": sum(family["observational"] for family in family_rows),
        "outcomes": _outcomes(per_input), "statuses": _statuses(per_input),
        "per_input": per_input, "per_family": per_family,
        "by_cohort": by_cohort, "by_exposure": by_exposure, "per_language": per_language,
        "answer_score": answer, "fresh_answer_score": fresh_answer,
        "checked_wrong_veto": bool(checked_wrong_ids),
        "checked_wrong_count": len(checked_wrong_ids), "checked_wrong_case_ids": checked_wrong_ids,
        "promotion": {
            "eligible": panel_kind == "formal",
            "passed": panel_kind == "formal" and all(gates.values()),
            "threshold": {"numerator": 9, "denominator": 10},
            "required_answer_successes": required_successes(answer["denominator"]),
            "required_fresh_answer_successes": required_successes(fresh_answer["denominator"]),
            "gates": gates,
        },
    }
