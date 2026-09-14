"""Research-only query-kind experiment, never imported by production.

Full typed references stay outside the model. Every arm uses shared ask().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from contextlib import closing, nullcontext
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Literal

import psycopg
import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from evals.query_extension_study import execute, matches
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.adapters.mcp_server import bind_datasource
from grepbit.application.ask import AskSettings, ask
from grepbit.application.request_lifecycle import RequestControl
from grepbit.domain.datasource import DatasourceRegistration
from grepbit.domain.plan import PlanProposal
from grepbit.ports.grounding import GroundingModelError

ROOT = Path(__file__).resolve().parents[1]
POLICY = """Before constructing a plan, distinguish the requested result shape
from whether the supplied data can support the entire request.
An individual-record projection preserves each record and NULL/duplicate values;
use rows for visible columns and filters of one base table, not a fabricated
count/grouping. Totals, counts, averages, distinct entity counts and grouped
metrics use legacy aggregates. The command to list/show/return something alone
does not determine the calculation. Existing latest-per-group and without
entity selection use the legacy constructs, not rows+without. Joined record
projections and independent sibling-fact combinations are outside this pilot.
Support requires supplied bindings for the requested population, condition and
quantity: a related numeric field is not automatically the requested business
quantity, and an available amount does not establish a requested business
subpopulation. If a required definition cannot be established, decline with
semantic_gap; do not silently drop the qualifier, substitute another quantity,
or return broader records. Do not demand extra definitions for ordinary explicit
column projections, ordinary SQL aggregates or conditions the supplied schema
already supports. Unresolved interpretation is ambiguous; a defined but
unrepresentable computation is unsupported. These are proposals, not proofs.
Never output SQL, formulas or computed values. Use only supplied identifiers."""


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: Literal["rows", "legacy", "decline"]
    reason: Literal["semantic_gap", "ambiguous", "unsupported"] | None = None

    @model_validator(mode="after")
    def reason_matches_route(self):
        if (self.route == "decline") != (self.reason is not None):
            raise ValueError("decline_requires_reason_only")
        return self


class StudyPlanner(ChatCompletionsPlanClient):
    def __init__(self, settings, *, arm, **kwargs):
        if arm not in {"direct", "joint", "split"}:
            raise ValueError("unknown_study_arm")
        super().__init__(settings, allow_rows=True, **kwargs)
        self.arm = arm
        self.route = None
        self.stage = "construct"
        self.router_seconds = 0.0
        self.study_error = None

    def build_messages(self, *args, **kwargs):
        messages = super().build_messages(*args, **kwargs)
        if self.arm == "joint":
            messages[0]["content"] += "\n" + POLICY
            context = json.loads(messages[2]["content"])
            context["prompt_revision"] = "query-kind-joint-v1"
            messages[2]["content"] = json.dumps(context, ensure_ascii=False)
        return messages

    def propose(
        self,
        question,
        model,
        *,
        as_of,
        overlay=None,
        previous=None,
        question_values=None,
    ):
        self.route = None
        if self._control:
            self._control.check()
        client = self._transport._client or self._transport._create_client()
        manager = (
            nullcontext(client)
            if self._transport._client is not None
            else closing(client)
        )
        kwargs = dict(
            as_of=as_of,
            overlay=overlay,
            previous=previous,
            question_values=question_values,
        )
        with manager:
            if self.arm == "split":
                self.stage = "route"
                context = json.loads(
                    super().build_messages(question, model, **kwargs)[2]["content"]
                )
                context["prompt_revision"] = "query-kind-router-v1"
                messages = [
                    {
                        "role": "system",
                        "content": POLICY
                        + "\nChoose route rows, legacy, or decline. Return only "
                        "a JSON object matching this schema: "
                        + json.dumps(RouteDecision.model_json_schema()),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(context, ensure_ascii=False),
                    },
                ]
                start = time.monotonic()
                try:
                    raw = self._complete(client, messages)
                    self.route = RouteDecision.model_validate_json(raw)
                except (ValueError, TypeError):
                    self.study_error = "invalid_route_output"
                    raise GroundingModelError("invalid_structured_output", 1) from None
                finally:
                    self.router_seconds = time.monotonic() - start
                if self._control:
                    self._control.check()
                if self.route.route == "decline":
                    return PlanProposal(decision="none", reason=self.route.reason)
                self._allow_rows = self.route.route == "rows"
            self.stage = "construct"
            # Deliberately bypass only the experimental unsupported-only wrapper,
            # not any shared ask gate, validation, repair, compiler or execution.
            proposal = self._propose(client, question, model, **kwargs)
            if self.route and proposal.plan is not None:
                if (proposal.plan.rows is not None) != (self.route.route == "rows"):
                    self.study_error = "route_kind_mismatch"
                    raise GroundingModelError("invalid_structured_output", 1)
            return proposal


def assess(result, case, gold):
    if result.status not in {"answered", "clarify", "semantic_gap", "unsupported"}:
        return {"outcome": "operational_failure"}
    negative = case["expected_route"] == "decline"
    if result.status != "answered":
        return {"outcome": "necessary_refusal" if negative else "unnecessary_refusal"}
    if negative:
        return {"outcome": "wrong_answer"}
    if result.rows_truncated:
        return {"outcome": "unjudged_truncated"}
    names, rows = gold
    if not result.rows and case["expected_route"] == "rows":
        projection = (result.lineage or {}).get("projection", [])
        if not projection:
            return {"outcome": "unjudged_empty_projection"}
        actual_names = [name.split(".")[-1] for name in projection]
    else:
        actual_names = list(result.rows[0]) if result.rows else names
    actual = [tuple(row.values()) for row in result.rows]
    columns_ok = case["expected_route"] != "rows" or actual_names == names
    values_ok = matches(actual, rows, ordered=case.get("ordered", False))
    return {
        "outcome": "correct_answer" if columns_ok and values_ok else "wrong_answer",
        "columns_match": columns_ok,
        "values_match": values_ok,
    }


def load_cases(panel):
    config = yaml.safe_load(panel.read_text())
    cases = []
    for selection in config["selections"]:
        bank = yaml.safe_load((ROOT / selection["file"]).read_text())
        selected = selection.get("ids")
        for original in bank["cases"]:
            if selected is not None and original["case_id"] not in selected:
                continue
            route = selection["route"]
            if original["expected"]["status"] != "answered":
                route = "decline"
            cases.append(
                {
                    **original,
                    "expected_route": route,
                    "ordered": selection.get("ordered", False),
                    "datasource_id": bank["datasource_id"],
                    "as_of": bank["as_of"],
                    "stratum": "existing",
                }
            )
    cases.extend(config["new_cases"])
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate_study_case")
    return cases


def source_hashes():
    paths = list((ROOT / "src").rglob("*.py")) + [Path(__file__)]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=160)
    args = parser.parse_args(argv)
    if not 1 <= args.max_calls <= 160:
        parser.error("max-calls must be between 1 and 160")
    args.output.mkdir(parents=True, exist_ok=False)
    cases = load_cases(args.panel)
    frozen = source_hashes()
    settings = replace(
        GroundingModelSettings.from_environment(), temperature=0, thinking="off"
    )
    if settings.structured_output_mode != "json_object":
        raise ValueError("study_requires_json_object")
    registry = ROOT / "evals/fixtures/dev_web_datasources.json"
    bound = {}
    for raw in json.loads(registry.read_text())["datasources"]:
        raw["allow_rows"] = True
        bound[raw["id"]] = bind_datasource(
            DatasourceRegistration.model_validate(raw), registry
        )
    gold = {}
    for case in cases:
        if case["expected_route"] == "decline":
            continue
        env = bound[case["datasource_id"]].registration.dsn_env

        def connect(env=env):
            return psycopg.connect(os.environ[env], connect_timeout=5)

        gold[case["case_id"]] = execute(connect, case["reference_sql"])
    manifest = {
        "source_hashes": frozen,
        "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "case_sha256": hashlib.sha256(
            json.dumps(cases, sort_keys=True).encode()
        ).hexdigest(),
        "model": settings.model,
        "cases": len(cases),
        "references_prepared": len(gold),
        "max_calls": args.max_calls,
        "research_only": True,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    budget = {"actual_calls": 0, "max_calls": args.max_calls}
    records = []
    # Rotate arm order across cases; this reduces gross order bias but cannot
    # make a shared endpoint deterministic or establish a latency mechanism.
    arms = ["direct", "joint", "split"]
    for index, case in enumerate(cases):
        for arm in arms[index % 3 :] + arms[: index % 3]:
            assert source_hashes() == frozen, "live_source_changed"
            control = RequestControl(30)
            planner = StudyPlanner(settings, arm=arm, control=control)
            calls = []
            native = planner._complete

            def complete(client, messages, **kwargs):
                if budget["actual_calls"] >= args.max_calls:
                    planner.study_error = "study_budget_exhausted"
                    raise GroundingModelError("invalid_structured_output", 0)
                budget["actual_calls"] += 1
                (args.output / "budget.json").write_text(json.dumps(budget))
                calls.append(
                    {
                        "stage": planner.stage,
                        "messages_sha256": hashlib.sha256(
                            json.dumps(messages, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )
                start = time.monotonic()
                try:
                    raw = native(client, messages, **kwargs)
                    calls[-1]["raw"] = raw
                    return raw
                finally:
                    calls[-1]["seconds"] = time.monotonic() - start
                    (args.output / "calls.json").write_text(
                        json.dumps(
                            {
                                "budget": budget,
                                "case_id": case["case_id"],
                                "arm": arm,
                                "calls": calls,
                            },
                            ensure_ascii=False,
                        )
                    )

            planner._complete = complete
            ds = bound[case["datasource_id"]]
            services = replace(ds.request_factory(control), planner=planner)
            result = ask(
                case["question"],
                services,
                AskSettings(as_of=datetime.fromisoformat(case["as_of"])),
                control=control,
            )
            record = {
                "case_id": case["case_id"],
                "arm": arm,
                "stratum": case.get("stratum", "new_authored"),
                "expected_route": case["expected_route"],
                "route": planner.route.model_dump() if planner.route else None,
                "status": result.status,
                "reason": result.reason,
                "study_error": planner.study_error,
                **assess(result, case, gold.get(case["case_id"])),
                "elapsed_seconds": result.elapsed_seconds,
                "model_calls": len(calls),
                "call_trace": calls,
                "plan": result.plan.model_dump(mode="json") if result.plan else None,
                "row_count": result.row_count,
                "rows_truncated": result.rows_truncated,
            }
            records.append(record)
            (args.output / "results.json").write_text(
                json.dumps(records, indent=2, ensure_ascii=False)
            )
            print(case["case_id"], arm, record["outcome"], len(calls), flush=True)
            if budget["actual_calls"] >= args.max_calls:
                raise RuntimeError("study_budget_exhausted")
    summary = {
        arm: dict(Counter(r["outcome"] for r in records if r["arm"] == arm))
        for arm in arms
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "outcomes": summary,
                "budget": budget,
                "source_unchanged": source_hashes() == frozen,
            },
            indent=2,
        )
    )
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
