"""Closed formal allocation policies over the unchanged historical accounting engine.

No questions, oracle payloads, native execution or configurable allocations.
Policy admission is separate from semantic review, freeze and live authorization.
"""
from collections import Counter
from copy import deepcopy

from tools import p3_assets as assets, p3_scoring as scoring

V1 = "p3-formal-allocation-v1"
V2 = "p3-formal-allocation-v2"
# Holdout A (#79): independently authored fresh families only, one observation per
# candidate; never promotion eligible.
HOLDOUT_A = "p3-holdout-a-allocation-v1"
VERSIONS = (V1, V2, HOLDOUT_A)
HOLDOUT_VERSIONS = (HOLDOUT_A,)
_POLICIES = {
    V1: {
        "families": 24, "inputs": 44,
        "family_cohorts": {"answer": 12, "clarify": 4, "decline": 5, "anchor": 3},
        "input_cohorts": {"answer": 18, "clarify": 8, "decline": 9, "anchor": 9},
        "family_exposures": {"frozen_fresh": 12, "exposed_regression": 12},
        "input_exposures": {"frozen_fresh": 26, "exposed_regression": 18},
        "cohort_exposure": {"answer": (8, 4), "clarify": (2, 2), "decline": (2, 3), "anchor": (0, 3)},
        "languages": {"zh-TW": 14, "en": 15, "ja": 15},
    },
    V2: {
        "families": 14, "inputs": 28,
        "family_cohorts": {"answer": 3, "clarify": 3, "decline": 5, "anchor": 3},
        "input_cohorts": {"answer": 5, "clarify": 5, "decline": 9, "anchor": 9},
        "family_exposures": {"frozen_fresh": 5, "exposed_regression": 9},
        "input_exposures": {"frozen_fresh": 13, "exposed_regression": 15},
        "cohort_exposure": {"answer": (2, 1), "clarify": (1, 2), "decline": (2, 3), "anchor": (0, 3)},
        "languages": {"zh-TW": 8, "en": 10, "ja": 10},
    },
    HOLDOUT_A: {
        "families": 7, "inputs": 21,
        "family_cohorts": {"answer": 2, "clarify": 3, "decline": 2},
        "input_cohorts": {"answer": 6, "clarify": 9, "decline": 6},
        "family_exposures": {"frozen_fresh": 7},
        "input_exposures": {"frozen_fresh": 21},
        "cohort_exposure": {"answer": (2, 0), "clarify": (3, 0), "decline": (2, 0)},
        "languages": {"zh-TW": 7, "en": 7, "ja": 7},
    },
}


def identity(version: str) -> dict:
    if not isinstance(version, str) or version not in VERSIONS:
        raise assets.P3Error("invalid_panel")
    definition = {"version": version, **_POLICIES[version],
                  "mandatory_only": True, "excluded_slot": "P21",
                  "accounting_baseline": "20abb5592262c77c98f9cabeaf7cf4854edb6fbe"}
    return {"version": version, "sha256": assets.digest(definition)}


def validate_identity(pin: dict) -> str:
    if not isinstance(pin, dict) or set(pin) != {"version", "sha256"} or pin != identity(pin["version"]):
        raise assets.P3Error("invalid_panel")
    return pin["version"]


def validate_allocation(inputs: list[dict], version: str) -> None:
    identity(version)
    if version == V1:
        scoring.validate_formal_allocation(inputs)
        return
    # Reuse the frozen family-consistency/ordering/type rules, not a second scorer.
    families = scoring._inputs_by_family(inputs, "invalid_panel")
    representatives = [rows[0] for rows in families.values()]
    expected = _POLICIES[version]
    if (len(families) != expected["families"] or len(inputs) != expected["inputs"]
            or any(row["observational"] or not row["must_pass"] or row["exposure"] == "design_seen"
                   or any(row.get(key) == "P21" for key in ("case_id", "family_id", "slot")) for row in inputs)):
        raise assets.P3Error("invalid_panel")
    for field, rows, key in (
        ("cohort", representatives, "family_cohorts"), ("cohort", inputs, "input_cohorts"),
        ("exposure", representatives, "family_exposures"), ("exposure", inputs, "input_exposures"),
        ("language", inputs, "languages"),
    ):
        if Counter(row[field] for row in rows) != expected[key]:
            raise assets.P3Error("invalid_panel")
    cross = {(cohort, exposure): count for cohort, counts in expected["cohort_exposure"].items()
             for exposure, count in zip(("frozen_fresh", "exposed_regression"), counts) if count}
    if Counter((row["cohort"], row["exposure"]) for row in representatives) != cross:
        raise assets.P3Error("invalid_panel")


def summarize(inputs: list[dict], results: list[dict], *, panel_kind: str, run_status: str,
              allocation_policy: dict | None = None) -> dict:
    if allocation_policy is None:
        return scoring.summarize(inputs, results, panel_kind=panel_kind, run_status=run_status)
    version = validate_identity(allocation_policy)
    # A holdout panel is frozen in the formal asset format; its live report labels
    # itself "holdout". Either label is accepted only for holdout versions.
    if panel_kind not in (("formal", "holdout") if version in HOLDOUT_VERSIONS else ("formal",)):
        raise assets.P3Error("invalid_panel")
    validate_allocation(inputs, version)
    summary = scoring.summarize(inputs, results, panel_kind="formal" if version == V1 else "development",
                                run_status=run_status)
    if version in HOLDOUT_VERSIONS:
        # Fresh observation: family-weighted outcomes from the frozen engine, no
        # promotion routing at all. Passing a holdout is evidence, not a gate.
        summary["panel_kind"] = "holdout"
        summary["promotion"]["eligible"] = False
        summary["promotion"]["passed"] = False
    if version == V2:
        # Only eligibility is routed. Outcomes, fractions, denominators and every
        # success/veto gate are exactly those produced by the frozen engine.
        summary["panel_kind"] = "formal"
        summary["promotion"]["eligible"] = True
        summary["promotion"]["passed"] = all(summary["promotion"]["gates"].values())
    summary["allocation_policy"] = identity(version)
    return summary


def stability_preselection() -> dict:
    """Owner-selected slot/language identities, not a runnable stability manifest."""
    rows = (
        ("P02", "FA01", "zh-TW", None), ("P04", "FA04", "en", None),
        ("R03", "E03_share_denominator", "ja", "E03_share_denominator.ja"),
        ("P14", "FA09 r2", "zh-TW", None), ("P17", "FA10", "ja", None),
        ("P18", "FA11", "en", None),
    )
    selection = {"version": "p3-stability-preselection-v2", "trials_per_input": 3,
                 "inputs": [dict(zip(("slot", "reviewed_family", "language", "case_id"), row)) for row in rows]}
    return {**deepcopy(selection), "sha256": assets.digest(selection)}
