#!/usr/bin/env python3
"""Plan stability across repeated runs of one case set.

  .venv/bin/python evals/stability.py --reports run1.json run2.json run3.json \
      --output evidence/<name>-stability.json

The same question at temperature 0 does not always give the same plan; this
tool measures variation, not its cause. For every case the runs' statuses
and plan cores are compared. Measure aliases and their output references are
canonicalised, but ordering priority (including implicit dimension order)
is retained. Only known commutative lists are sorted.
The output holds counts and, per unstable case, which keys differed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from grepbit.domain.plan import Measure

_COSMETIC = {"alias"}
_UNORDERED = {"measures", "filters", "values", "having", "growth"}
STABILITY_REVISION = "plan-core-v2"


def _core(plan: Any, key: str = "") -> Any:
    if isinstance(plan, dict):
        core = {
            k: _core(v, k)
            for k, v in plan.items()
            if k not in _COSMETIC and v not in (None, [], {})
        }
        return {k: v for k, v in core.items() if v not in (None, [], {})}
    if isinstance(plan, list):
        items = [_core(v) for v in plan]
        if key in _UNORDERED:
            items.sort(key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
        return items
    return plan


def plan_core(plan: Any) -> Any:
    core = _core(plan)
    if not isinstance(plan, dict):
        return core
    names = {}
    for measure in plan.get("measures", []):
        try:
            name = Measure.model_validate(measure).output_name
        except (ValidationError, ValueError):
            # Malformed historical payloads are compared as written, not guessed.
            continue
        names[name] = {"measure_core": _core(measure)}
    # Rename output references only. Literals and source column names that
    # happen to equal an alias keep their original meaning.
    for key, field in (("order", "field"), ("having", "field"), ("growth", "measure")):
        for item in core.get(key, []):
            if item.get(field) in names:
                item[field] = names[item[field]]
    return _core(core)


def _validate_reports(reports: list[dict[str, Any]]) -> None:
    if len(reports) < 2:
        raise ValueError("stability_requires_repeated_runs")
    case_ids = None
    for report in reports:
        rows = report["results"]
        ids = [row["case_id"] for row in rows]
        if not ids:
            raise ValueError("stability_empty_run")
        if len(ids) != len(set(ids)):
            raise ValueError("stability_duplicate_case")
        if case_ids is not None and set(ids) != case_ids:
            raise ValueError("stability_incomplete_runs")
        case_ids = set(ids)
        declared = report["summary"].get("cases")
        if declared is not None and declared != len(ids):
            raise ValueError("stability_case_count_mismatch")
        for field in (
            "cases_file",
            "prompt_revision",
            "model",
            "datasource_id",
            "as_of",
        ):
            if report["summary"].get(field) != reports[0]["summary"].get(field):
                raise ValueError(f"stability_incompatible_reports:{field}")


def _differing_keys(cores: list[dict]) -> list[str]:
    keys = set().union(*(c.keys() for c in cores if isinstance(c, dict)))
    return sorted(
        k
        for k in keys
        if len(
            {json.dumps(c.get(k), sort_keys=True, ensure_ascii=False) for c in cores}
        )
        > 1
    )


def stability(reports: list[dict[str, Any]]) -> dict[str, Any]:
    _validate_reports(reports)
    by_case: dict[str, list[dict]] = {}
    for report in reports:
        for row in report["results"]:
            by_case.setdefault(row["case_id"], []).append(row)
    cases = []
    for case_id, rows in by_case.items():
        statuses = [r["status"] for r in rows]
        cores = [plan_core(r.get("plan")) for r in rows]
        core_texts = {json.dumps(c, sort_keys=True, ensure_ascii=False) for c in cores}
        stable_status = len(set(statuses)) == 1
        stable_plan = stable_status and len(core_texts) == 1
        entry: dict[str, Any] = {
            "case_id": case_id,
            "runs": len(rows),
            "statuses": statuses,
            "distinct_plans": len(core_texts),
            "stable_status": stable_status,
            "stable_plan": stable_plan,
        }
        if not stable_plan:
            dict_cores = [c for c in cores if isinstance(c, dict)]
            entry["differing_keys"] = (
                _differing_keys(dict_cores) if len(dict_cores) > 1 else []
            )
            entry["correct"] = [r.get("correct") for r in rows]
        cases.append(entry)
    n = len(cases)
    return {
        "stability_revision": STABILITY_REVISION,
        "reports": [r["summary"].get("cases_file") for r in reports],
        "prompt_revision": reports[0]["summary"].get("prompt_revision"),
        "model": reports[0]["summary"].get("model"),
        "runs": len(reports),
        "cases": n,
        "stable_status": sum(c["stable_status"] for c in cases),
        "stable_plan": sum(c["stable_plan"] for c in cases),
        "plan_stability": round(sum(c["stable_plan"] for c in cases) / n, 4)
        if n
        else None,
        "status_stability": round(sum(c["stable_status"] for c in cases) / n, 4)
        if n
        else None,
        "unstable": [c for c in cases if not c["stable_plan"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in arguments.reports]
    try:
        result = stability(reports)
    except ValueError as error:
        print(str(error))
        return 2
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"cases {result['cases']} runs {result['runs']} plan stability "
        f"{result['plan_stability']} status stability {result['status_stability']} "
        f"unstable {len(result['unstable'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
