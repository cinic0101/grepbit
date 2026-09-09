#!/usr/bin/env python3
"""Experiment: does a parent agent preserve the tool's caveats when it replies?

Takes tier-0 spike reports, rebuilds the structured tool result a caller would
receive (status, verification, interpretation, assumptions, lineage, rows or
the refusal reason), and asks the model to write the user-facing reply in two
framings: "guided" (rules about numbers, assumptions, refusals) and "bare"
(no rules). Deterministic checks then look at whether numbers survived, whether
a caveat was voiced, whether refusals stayed refusals, and whether an empty
result was reported as no data. Replies are written to the output file only.

  .venv/bin/python evals/spike_parent_agent.py \
      --report .artifacts/spike-tier0/pos-03.json --report ... \
      --case sales_dec_2025_total --case returns_dec_gap ... \
      --output <dir>/parent-agent.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_FILES = sorted((ROOT / "evals" / "cases" / "tier0").glob("*.yaml"))

GUIDED = (
    "You are the assistant a business user is talking to. You called a data "
    "tool and its JSON result follows. Reply to the user in the user's language, "
    "in at most five sentences. Rules: state only numbers the tool returned; "
    "when verification is unverified_semantics, say the answer relies on column "
    "names and schema structure only and restate the assumptions that could "
    "change the number; when the status is not answered, say what the tool could "
    "not do and what the user could ask instead; when the result is empty, say "
    "there is no data rather than giving zero; never guess."
)
BARE = (
    "You are a helpful assistant. The user asked a question and a data tool "
    "returned the JSON below. Write the reply to the user."
)


def summary_sentence(result: dict[str, Any]) -> str:
    """What the tool itself would say; tests whether an unguided parent copies it."""

    if result["status"] == "answered":
        assumptions = " ".join(result.get("assumptions") or [])
        return (
            f"Computed as {result.get('interpretation')}. Verification: "
            "unverified_semantics, meaning column names and schema structure only, "
            f"no reviewed business definition. Assumptions: {assumptions}"
        )
    return (
        f"Not answered: {result.get('reason')}. "
        f"{result.get('clarification') or ''}".strip()
    )


CAVEAT_MARKERS = (
    "假設",
    "未經",
    "未驗證",
    "未套用",
    "僅依",
    "僅根據",
    "依據欄位",
    "欄位名稱",
    "結構",
    "定義",
    "包含",
    "不含",
    "unverified",
    "assum",
    "based on column",
    "schema",
    "not verified",
    "not reviewed",
    "includes",
    "definition",
)
EMPTY_MARKERS = (
    "沒有",
    "無",
    "查無",
    "no data",
    "no sales",
    "no record",
    "not find",
    "empty",
)
REFUSAL_MARKERS = (
    "無法",
    "不能",
    "沒有",
    "無此",
    "不存在",
    "缺少",
    "cannot",
    "can't",
    "unable",
    "not ",
    "no ",
    "does not",
)


def load_questions() -> dict[str, str]:
    questions: dict[str, str] = {}
    for path in CASE_FILES:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for case in document.get("cases", []):
            questions[case["case_id"]] = case["question"]
    return questions


def tool_result(row: dict[str, Any]) -> dict[str, Any]:
    status = row["status"]
    result: dict[str, Any] = {"status": status}
    if status == "answered":
        result.update(
            {
                "verification": row.get("verification", "unverified_semantics"),
                "interpretation": row.get("interpretation"),
                "assumptions": row.get("assumptions", []),
                "lineage": row.get("lineage"),
                "rows": row.get("rows", []),
                "row_count": len(row.get("rows", [])),
            }
        )
    else:
        result.update(
            {
                "reason": row.get("reason"),
                "clarification": row.get("clarification"),
                "detail": row.get("detail"),
            }
        )
    return result


def number_candidates(value: Any) -> list[str]:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return []
    candidates = {format(number.normalize(), "f")}
    for places in (0, 1, 2):
        candidates.add(format(number.quantize(Decimal(1).scaleb(-places)), "f"))
    return [c for c in candidates if c not in {"0", "0.0", "0.00"} or number == 0]


def numbers_preserved(rows: list[dict[str, Any]], reply: str) -> tuple[int, int]:
    text = reply.replace(",", "")
    total = preserved = 0
    for row in rows:
        for value in row.values():
            if value is None or isinstance(value, bool):
                continue
            candidates = number_candidates(value)
            if not candidates:
                continue
            total += 1
            if any(c in text for c in candidates):
                preserved += 1
    return preserved, total


def invented_numbers(reply: str) -> list[str]:
    text = reply.replace(",", "")
    found = re.findall(r"(?<![\d.])\d{3,}(?:\.\d+)?(?![\d.])", text)
    return [n for n in found if not re.fullmatch(r"20\d\d", n)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    questions = load_questions()
    rows_by_case: dict[str, dict[str, Any]] = {}
    for path in arguments.report:
        for row in json.loads(path.read_text(encoding="utf-8"))["results"]:
            rows_by_case.setdefault(row["case_id"], row)
    missing = [c for c in arguments.case if c not in rows_by_case]
    if missing:
        print("PARENT_BLOCKED code=case_missing", *missing)
        return 2

    settings = GroundingModelSettings.from_environment()
    client = ChatCompletionsGroundingClient(settings)._create_client()
    results: list[dict[str, Any]] = []
    for case_id in arguments.case:
        row = rows_by_case[case_id]
        question = questions.get(case_id, case_id)
        result = tool_result(row)
        entry: dict[str, Any] = {
            "case_id": case_id,
            "question": question,
            "tool_status": result["status"],
            "variants": {},
        }
        with_summary = {**result, "summary": summary_sentence(result)}
        for variant, system, payload in (
            ("guided", GUIDED, result),
            ("bare", BARE, result),
            ("bare_with_summary", BARE, with_summary),
        ):
            started = time.monotonic()
            response = client.chat.completions.create(
                model=settings.model,
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"user_question": question, "tool_result": payload},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    },
                ],
                temperature=0,
                max_tokens=400,
            )
            reply = (response.choices[0].message.content or "").strip()
            checks: dict[str, Any] = {}
            rows = result.get("rows") or []
            if result["status"] == "answered":
                all_null = rows and all(
                    v is None or v == "None" for r in rows for v in r.values()
                )
                if all_null:
                    checks["empty_reported"] = any(
                        m in reply.lower() for m in EMPTY_MARKERS
                    )
                else:
                    preserved, total = numbers_preserved(rows, reply)
                    checks["numbers_preserved"] = f"{preserved}/{total}"
                    checks["all_numbers_preserved"] = preserved == total
                checks["caveat_present"] = any(
                    m in reply.lower() for m in CAVEAT_MARKERS
                )
            else:
                checks["stayed_refusal"] = not invented_numbers(reply)
                checks["invented_numbers"] = invented_numbers(reply)
                checks["refusal_explained"] = any(
                    m in reply.lower() for m in REFUSAL_MARKERS
                )
            entry["variants"][variant] = {
                "reply": reply,
                "seconds": round(time.monotonic() - started, 3),
                "checks": checks,
            }
        results.append(entry)
        print(f"== {case_id} [{result['status']}] {question}")
        for variant, data in entry["variants"].items():
            checks_text = json.dumps(data["checks"], ensure_ascii=False)
            print(f"  -- {variant} {data['seconds']:.1f}s {checks_text}")
            print("     " + data["reply"].replace("\n", "\n     "))

    def rate(variant: str, key: str) -> str:
        values = [
            e["variants"][variant]["checks"].get(key)
            for e in results
            if key in e["variants"][variant]["checks"]
        ]
        return f"{sum(1 for v in values if v is True)}/{len(values)}"

    summary = {
        variant: {
            key: rate(variant, key)
            for key in (
                "all_numbers_preserved",
                "caveat_present",
                "empty_reported",
                "stayed_refusal",
                "refusal_explained",
            )
        }
        for variant in ("guided", "bare", "bare_with_summary")
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(
            {"summary": summary, "results": results}, indent=2, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
