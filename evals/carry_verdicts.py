#!/usr/bin/env python3
"""Pre-fill a verdict skeleton from earlier judged runs of the same questions.

  .venv/bin/python evals/carry_verdicts.py --report <run.json> \
      --verdicts <skeleton.yaml> --from <judged-run.json>:<filled.yaml> \
      [--from ...] [--output <prefilled.yaml>]

A verdict is carried only when the new case has the same status, SQL and
row count as a case with the same id in a judged run, or the same SQL up to
the output column names (aliases change no number); the note names the run
it came from and which of the two matched. Everything else stays ``null`` for
the judge. The tool never invents a verdict: a carried verdict is a human's
earlier verdict on the same executable output, restated. The plan JSON is
not compared because its shape grows with the algebra while the SQL stays.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

FINGERPRINT_KEYS = ("status", "sql", "row_count")
_ALIAS = re.compile(r' AS (?:[A-Za-z_][A-Za-z0-9_$]*|"[^"]+")')  # quoted: AS "銷售總額"


def fingerprint(result: dict[str, Any], *, ignore_aliases: bool = False) -> str:
    values = [result.get(k) for k in FINGERPRINT_KEYS]
    if ignore_aliases and isinstance(values[1], str):
        values[1] = _ALIAS.sub(" AS _", values[1])
    return json.dumps(values, sort_keys=True, ensure_ascii=False)


def carry(
    report: dict[str, Any],
    skeleton: dict[str, Any],
    judged: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the skeleton with carried verdicts and counts (carried, open)."""

    by_case = {r["case_id"]: r for r in report["results"]}
    carried = 0
    for entry in skeleton["verdicts"]:
        if entry.get("verdict") is not None:
            continue
        current = by_case.get(entry["case_id"])
        if current is None:
            continue
        case_id = entry["case_id"]
        for label, old_report, old_verdicts in judged:
            results = old_report["results"]
            old = next((r for r in results if r["case_id"] == case_id), None)
            verdict = next(
                (v for v in old_verdicts["verdicts"] if v["case_id"] == case_id), None
            )
            if old is None or verdict is None:
                continue
            if verdict.get("verdict") in (None, "unsure"):
                continue
            if fingerprint(old) == fingerprint(current):
                how = "same status, SQL and row count"
            elif fingerprint(old, ignore_aliases=True) == fingerprint(
                current, ignore_aliases=True
            ):
                how = "same status, SQL up to output column names, and row count"
            else:
                continue
            entry["verdict"] = verdict["verdict"]
            entry["note"] = f"carried from {label}: {how}"
            carried += 1
            break
    open_count = sum(1 for e in skeleton["verdicts"] if e.get("verdict") is None)
    return skeleton, {"carried": carried, "open": open_count}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--verdicts", required=True, type=Path)
    parser.add_argument(
        "--from",
        dest="sources",
        action="append",
        required=True,
        metavar="RUN.json:VERDICTS.yaml",
    )
    parser.add_argument("--output", type=Path, help="default: overwrite --verdicts")
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text())
    skeleton = yaml.safe_load(args.verdicts.read_text())
    judged = []
    for source in args.sources:
        run_path, verdict_path = source.split(":", 1)
        judged.append(
            (
                Path(run_path).name,
                json.loads(Path(run_path).read_text()),
                yaml.safe_load(Path(verdict_path).read_text()),
            )
        )
    filled, counts = carry(report, skeleton, judged)
    out = args.output or args.verdicts
    out.write_text(yaml.safe_dump(filled, allow_unicode=True, sort_keys=False))
    open_ids = [e["case_id"] for e in filled["verdicts"] if e.get("verdict") is None]
    print(f"carried {counts['carried']}, open {counts['open']}: {' '.join(open_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
