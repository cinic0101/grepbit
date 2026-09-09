#!/usr/bin/env python3
"""Turn a judge's filled verdict file into the stage-2 numbers.

  .venv/bin/python evals/tally_verdicts.py --report <run.json> \
      --verdicts <filled.yaml> --output <tally.json>

The report is a ``spike_tier0.py`` artifact; the verdict file is the skeleton
``--verdicts`` wrote, with every ``verdict`` filled from ``verdict_values``.
Answered cases take ``correct``, ``wrong_exposed`` (the number is wrong but an
assumption states the choice that made it wrong) or ``wrong_silent`` (wrong,
nothing exposed it); refusals take ``refusal_ok`` or ``refusal_bad`` (should
have answered); ``unsure`` is allowed anywhere and counted separately. The
output holds counts and rates only, no rows, so it can live under evidence/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ANSWERED_VERDICTS = {"correct", "wrong_exposed", "wrong_silent"}
REFUSAL_VERDICTS = {"refusal_ok", "refusal_bad"}


def tally(report: dict[str, Any], verdicts: dict[str, Any]) -> dict[str, Any]:
    """Counts and rates; raises ValueError on a missing or inconsistent verdict."""

    allowed = set(verdicts["verdict_values"])
    by_case = {r["case_id"]: r for r in report["results"]}
    problems: list[str] = []
    counts = {name: 0 for name in verdicts["verdict_values"]}
    for entry in verdicts["verdicts"]:
        case_id, verdict = entry["case_id"], entry.get("verdict")
        result = by_case.get(case_id)
        if result is None:
            problems.append(f"{case_id}: not in report")
            continue
        if verdict is None:
            problems.append(f"{case_id}: verdict missing")
            continue
        if verdict not in allowed:
            problems.append(f"{case_id}: verdict {verdict!r} not in verdict_values")
            continue
        answered = result["status"] == "answered"
        if answered and verdict in REFUSAL_VERDICTS:
            problems.append(f"{case_id}: answered case cannot take {verdict}")
        elif not answered and verdict in ANSWERED_VERDICTS:
            problems.append(f"{case_id}: {result['status']} case cannot take {verdict}")
        counts[verdict] += 1
    missing = sorted(set(by_case) - {e["case_id"] for e in verdicts["verdicts"]})
    if missing:
        problems.append("report cases without a verdict: " + ", ".join(missing))
    if problems:
        raise ValueError("\n".join(problems))

    total = len(report["results"])
    judged = total - counts.get("unsure", 0)
    correct = counts["correct"] + counts["refusal_ok"]
    statuses = report["summary"]["status_counts"]
    refused = sum(n for status, n in statuses.items() if status != "answered")
    return {
        "report": report["summary"].get("cases_file"),
        "datasource_id": report["summary"]["datasource_id"],
        "prompt_revision": report["summary"].get("prompt_revision"),
        "cases": total,
        "judged": judged,
        "unsure": counts.get("unsure", 0),
        "correct": correct,
        "correctness": round(correct / judged, 4) if judged else None,
        "wrong_numbers_without_exposed_assumption": counts["wrong_silent"],
        "wrong_numbers_with_exposed_assumption": counts["wrong_exposed"],
        "refusals_that_should_have_answered": counts["refusal_bad"],
        "clarify_count": statuses.get("clarify", 0),
        "clarify_rate": round(statuses.get("clarify", 0) / total, 4) if total else None,
        "refusal_rate": round(refused / total, 4) if total else None,
        "status_counts": statuses,
        "verdict_counts": counts,
        "p50_seconds": report["summary"]["p50_seconds"],
        "p95_seconds": report["summary"]["p95_seconds"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verdicts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    report = json.loads(arguments.report.read_text(encoding="utf-8"))
    verdicts = yaml.safe_load(arguments.verdicts.read_text(encoding="utf-8"))
    try:
        result = tally(report, verdicts)
    except ValueError as error:
        print(f"TALLY_BLOCKED code=verdicts_incomplete\n{error}")
        return 2
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
