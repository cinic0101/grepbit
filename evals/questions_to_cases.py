#!/usr/bin/env python3
"""Turn a plain-text list of questions into a judged-mode case file, unread.

  .venv/bin/python evals/questions_to_cases.py --questions <file.txt> \
      --datasource-id pos_real --as-of 2026-02-04T18:00:00+08:00 \
      --output evals/cases/tier0/<name>.yaml [--prefix q]

One question per line, UTF-8. Blank lines are skipped; a leading number such
as "12." or "12)" or "12、" is stripped. Cases get ids <prefix>01, <prefix>02,
... and no expected status, so the runner marks them for a human judge. The
tool prints only the count, so the build side can convert a holdout without
seeing a single question.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

_NUMBERING = re.compile(r"^\s*\(?\d{1,3}[.)、:：]\s*")


def parse_questions(text: str) -> list[str]:
    questions: list[str] = []
    for line in text.splitlines():
        stripped = _NUMBERING.sub("", line, count=1).strip()
        if stripped:
            questions.append(stripped)
    return questions


def build_cases(questions: list[str], *, prefix: str = "q") -> list[dict[str, str]]:
    width = max(2, len(str(len(questions))))
    return [
        {"case_id": f"{prefix}{index:0{width}d}", "question": question}
        for index, question in enumerate(questions, start=1)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--as-of", required=True, help="ISO datetime with offset")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", default="q")
    arguments = parser.parse_args(argv)
    questions = parse_questions(arguments.questions.read_text(encoding="utf-8"))
    if not questions:
        print("QUESTIONS_BLOCKED code=empty_file")
        return 2
    document = {
        "datasource_id": arguments.datasource_id,
        "as_of": arguments.as_of,
        "cases": build_cases(questions, prefix=arguments.prefix),
    }
    header = (
        f"# Converted from {arguments.questions.name} by evals/questions_to_cases.py; "
        "judged mode (no expected status). The build side did not read the questions.\n"
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        header
        + yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    print(f"{len(questions)} questions -> {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
