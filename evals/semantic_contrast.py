"""Bounded research ablations using the unchanged v2 obligation contract.

No production integration, DB access, SQL/rows/gold in model requests or retries.
"""

import argparse
import json
import random
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import yaml

from evals import concept_obligations_pilot as pilot
from evals.concept_obligations import validate_obligations
from evals.concept_pilot import call, digest
from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from tools.verify import _source_snapshot

ROOT = Path(__file__).resolve().parents[1]
REVISION = "semantic-contrast-v1"
ARMS = ("baseline", "definitions", "task")
TASK = (
    "First distinguish the requested output action from the business population "
    "to be measured. A verb asking you to deliver an answer does not itself "
    "select rows. Concept definitions describe how a requested population maps "
    "to data, not a requirement to select that population in every question. "
    "Determine whether the question already specifies the measure basis: an "
    "explicit count of entities or sum of their amounts is specified, even "
    "without a reviewed metric ID. Do not mark a specified basis unresolved. "
    "For a rate with genuinely unspecified basis or denominator, preserve "
    "unresolved entries. Preserve actual inclusion, exclusion, unrestricted "
    "scopes and grouping prohibitions. Do not infer unrestricted from silence. "
    "Use the same output schema; do not output intermediate reasoning."
)


def load_study(phase="development"):
    original, fixture = pilot.load_study()
    data = yaml.safe_load((ROOT / "evals/cases/concepts/contrast_v1.yaml").read_text())
    if phase == "legacy":
        return original, fixture, data
    split = "challenge" if phase == "challenge" else "development"
    ruler = {
        **original,
        "families": [f for f in data["families"] if f["split"] == split],
    }
    fixture["plans"].update(data["plans"])
    fixture["family_sources"].update({f["id"]: f["source"] for f in ruler["families"]})
    return ruler, fixture, data


def messages(question, context, arm, definitions):
    context = deepcopy(context)
    if arm == "definitions":
        for key, concept in context["concepts"].items():
            concept["definition"] = definitions[key]
    request = pilot.messages(question, context)
    if arm == "task":
        request.insert(1, {"role": "system", "content": TASK})
    if arm not in ARMS:
        raise ValueError("unknown_arm")
    return request


def analyze(calls, ruler, fixture):
    summaries, pairs, intents = {}, [], []
    families = {f["id"]: f for f in ruler["families"]}
    for arm in ARMS:
        selected = [{**c, "arm": "off"} for c in calls if c["arm"] == arm]
        if not selected:
            continue
        result = pilot.analyze(selected, ruler, fixture)
        summary = result["summaries"]["off:round_all"]
        summary["failed_extractions"] = sum(c["status"] != "ok" for c in selected)
        for name in ("correct", "wrong"):
            rows = [
                p
                for p in result["pairs"]
                if p["plan_id"] in families[p["family_id"]].get(f"{name}_answers", [])
            ]
            summary[f"{name}_full_answer_controls"] = len(rows)
            summary[f"{name}_full_answer_no_block"] = sum(
                p["verdict"] in {"pass", "not_applicable"} for p in rows
            )
            summary[f"{name}_full_answer_pass"] = sum(
                p["verdict"] == "pass" for p in rows
            )
        summaries[arm] = summary
        pairs.extend({**p, "arm": arm} for p in result["pairs"])
        intents.extend({**p, "arm": arm} for p in result["intents"])
    return {"summaries": summaries, "pairs": pairs, "intents": intents}


def select_candidate(summaries):
    baseline = summaries["baseline"]
    eligible = []
    for arm in ARMS[1:]:
        if arm not in summaries:
            continue
        candidate = summaries[arm]
        if (
            candidate["intent_exact"] >= baseline["intent_exact"] + 2
            and candidate["correct_controls_allowed"]
            >= baseline["correct_controls_allowed"]
            and candidate["wrong_allowed"] <= baseline["wrong_allowed"]
            and candidate["unresolved_allowed"] <= baseline["unresolved_allowed"]
            and candidate["wrong_full_answer_no_block"]
            <= baseline["wrong_full_answer_no_block"]
            and candidate["failed_extractions"] <= baseline["failed_extractions"]
        ):
            eligible.append(arm)
    return (
        min(
            eligible,
            key=lambda a: (
                -summaries[a]["intent_exact"],
                -summaries[a]["correct_controls_allowed"],
                summaries[a]["failed_extractions"],
                a,
            ),
        )
        if eligible
        else None
    )


def run(output: Path, *, live=False, phase="development", previous=None):
    ruler, fixture, data = load_study(phase)
    source = _source_snapshot()
    if not source["available"]:
        raise ValueError("source_snapshot_unavailable")
    candidate = None
    if phase != "development":
        if previous is None:
            raise ValueError("prior_screen_required")
        prior = json.loads(previous.read_text())
        required = "development" if phase == "replicate" else "replicate"
        if (
            prior["revision"] != REVISION
            or prior["phase"] != required
            or not prior["completed"]
            or not prior["source_unchanged"]
            or prior["source_start"]["tracked_source_digest"]
            != source["tracked_source_digest"]
            or (live and not prior["live"])
        ):
            raise ValueError("invalid_prior_screen")
        candidate = select_candidate(prior["analysis"]["summaries"])
        if candidate is None or candidate != prior["selected_candidate"]:
            raise ValueError("no_eligible_candidate")
    arms = ARMS if phase == "development" else ("baseline", candidate)
    oracle = pilot.oracle_records(ruler, fixture)
    if any(p["verdict"] != p["expected"] for p in oracle):
        raise ValueError("oracle_mismatch")
    contexts = {
        f["id"]: pilot.study_context(f["id"], ruler, fixture)[0]
        for f in ruler["families"]
    }
    schedule = [
        {
            "family_id": f["id"],
            "case_id": f["id"] + "_" + language,
            "language": language,
            "arm": arm,
            "question": question,
            "round": 2 if phase == "replicate" else 1,
        }
        for f in ruler["families"]
        for language, question in f["questions"].items()
        for arm in arms
    ]
    random.Random(91203).shuffle(schedule)
    budgets = {"development": 108, "replicate": 72, "challenge": 24, "legacy": 72}
    if len(schedule) != budgets[phase]:
        raise ValueError("fixed_budget_mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.with_suffix(".jsonl").exists():
        raise ValueError("fresh_outputs_required")
    report = {
        "revision": REVISION,
        "phase": phase,
        "live": live,
        "completed": False,
        "source_start": source,
        "inputs_sha256": digest([ruler, fixture, data, contexts]),
        "previous_sha256": digest(prior) if previous is not None else None,
        "settings": {
            "max_calls": budgets[phase],
            "temperature": 0,
            "thinking": "off",
            "max_tokens": 4096,
            "timeout_seconds": 60,
            "retries": 0,
        },
        "prompt_revisions": {
            a: pilot.REVISION if a == "baseline" else f"{REVISION}-{a}" for a in arms
        },
        "oracle": oracle,
        "calls": [],
        "schedule": [],
    }
    for item in schedule:
        request = messages(
            item["question"],
            contexts[item["family_id"]],
            item["arm"],
            data["definitions"],
        )
        report["schedule"].append(
            {
                **{k: v for k, v in item.items() if k != "question"},
                "request_sha256": digest(request),
            }
        )
    settings = (
        replace(GroundingModelSettings.from_environment(), timeout_seconds=60)
        if live
        else None
    )
    report["settings"]["model"] = settings.model if settings else None
    with output.open("x") as target, output.with_suffix(".jsonl").open("x") as journal:
        journal.write(json.dumps({"manifest": report}) + "\n")
        journal.flush()
        client = (
            ChatCompletionsGroundingClient(settings)._create_client() if live else None
        )
        try:
            for item in schedule if live else []:
                question, context = item["question"], contexts[item["family_id"]]
                result = call(
                    client,
                    settings,
                    messages(question, context, item["arm"], data["definitions"]),
                    lambda p: validate_obligations(p, question, context["concepts"]),
                    thinking=False,
                    max_tokens=4096,
                )
                record = {
                    **{k: v for k, v in item.items() if k != "question"},
                    **result,
                }
                report["calls"].append(record)
                journal.write(json.dumps(record, ensure_ascii=False) + "\n")
                journal.flush()
                print(
                    f"{phase} calls={len(report['calls'])}/{len(schedule)} "
                    f"arm={item['arm']} status={result['status']}",
                    flush=True,
                )
                if len(report["calls"]) >= 3 and all(
                    c["status"] == "transport_error" for c in report["calls"][-3:]
                ):
                    report["stop_reason"] = "three_transport_errors"
                    break
            else:
                report["completed"] = True
        finally:
            if client:
                client.close()
            report["source_end"] = _source_snapshot()
            report["source_unchanged"] = (
                source["tracked_source_digest"]
                == report["source_end"]["tracked_source_digest"]
            )
            report["analysis"] = (
                analyze(report["calls"], ruler, fixture) if live else None
            )
            report["selected_candidate"] = (
                select_candidate(report["analysis"]["summaries"])
                if live and report["completed"]
                else None
            )
            json.dump(report, target, ensure_ascii=False, indent=2)
    return report["completed"] and report["source_unchanged"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("development", "replicate", "challenge", "legacy"),
        default="development",
    )
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    raise SystemExit(
        0
        if run(args.output, live=args.live, phase=args.phase, previous=args.previous)
        else 1
    )
