#!/usr/bin/env python3
"""Plan stability across repeated runs of one case set.

  .venv/bin/python evals/stability.py --reports run1.json run2.json run3.json \
      --output evidence/<name>-stability.json

The same question at temperature 0 does not always give the same plan (a
shared endpoint batches requests differently call to call). For every case
the runs' statuses and plan cores are compared; a plan core is the plan
without its aliases and with its lists in canonical order, so a change of
output name is not instability but a changed filter, dimension or window is.
The output holds counts and, per unstable case, which keys differed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_COSMETIC = {"alias"}


def plan_core(plan: Any) -> Any:
    if isinstance(plan, dict):
        core = {
            k: plan_core(v)
            for k, v in plan.items()
            if k not in _COSMETIC and v not in (None, [], {})
        }
        return {k: v for k, v in core.items() if v not in (None, [], {})}
    if isinstance(plan, list):
        items = [plan_core(v) for v in plan]
        return sorted(
            items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False)
        )
    return plan


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
    files = {r["summary"].get("cases_file") for r in reports}
    if len(files) != 1:
        print(f"reports come from different case files: {sorted(files)}")
        return 2
    result = stability(reports)
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
