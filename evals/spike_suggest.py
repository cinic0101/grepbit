#!/usr/bin/env python3
"""Suggested questions: can the system propose questions it can then answer?

Asks the model, from the schema payload alone (plus the overlay if given), for
N questions a business user might ask, writes them as a tier-0 case file with
expected status answered and no reference SQL, so `spike_tier0.py` can report
how many of the system's own suggestions it actually answers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import yaml

from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from grepbit.adapters.litellm.plan_client import schema_payload
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.adapters.postgres.introspect import introspect_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn-env", required=True)
    parser.add_argument("--datasource-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--language", default="Traditional Chinese")
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    import psycopg

    dsn = os.environ.get(arguments.dsn_env)
    if not dsn:
        print(f"SUGGEST_BLOCKED code=dsn_env_missing env={arguments.dsn_env}")
        return 2

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection

    schema = introspect_schema(connect, datasource_id=arguments.datasource_id)
    overlay = load_semantic_overlay(arguments.overlay) if arguments.overlay else None
    settings = GroundingModelSettings.from_environment()
    client = ChatCompletionsGroundingClient(settings)._create_client()
    system = (
        f"Propose {arguments.count} distinct questions a business user would ask "
        f"about this data, in {arguments.language}. Each must be answerable by ONE "
        "aggregate query over the schema (a sum, count, average, min, or max, "
        "optionally by one dimension, with a time window inside the data's range "
        f"given as_of {arguments.as_of}). Vary the tables and the shapes (totals, "
        "breakdowns, top-N, trends, filters). Output only JSON: "
        '{"questions": ["...", ...]}.'
    )
    response = client.chat.completions.create(
        model=settings.model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    schema_payload(schema, overlay), ensure_ascii=False
                ),
            },
        ],
        temperature=0,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    questions = json.loads(response.choices[0].message.content)["questions"]
    document = {
        "datasource_id": arguments.datasource_id,
        "as_of": arguments.as_of,
        "cases": [
            {
                "case_id": f"suggested_{index:02d}",
                "question": question,
                "expected": {"status": "answered"},
            }
            for index, question in enumerate(questions, start=1)
        ],
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    for question in questions:
        print("  -", question)
    return 0


if __name__ == "__main__":
    sys.exit(main())
