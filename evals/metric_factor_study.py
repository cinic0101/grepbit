"""Five-arm, one-response research study; no production or gold changes."""

import argparse
import json
import random
from collections import Counter
from dataclasses import replace
from pathlib import Path

from evals import metric_wire_study as previous
from evals.concept_pilot import call, digest
from evals.metric_factor_selection import (
    FactoredSelection,
    bind_factors,
    factor_cards,
    factor_catalog,
    shown_interpretation,
)
from evals.metric_wire_selection import diagnostics
from grepbit.adapters.litellm.grounding_client import (
    ChatCompletionsGroundingClient,
    GroundingModelSettings,
)
from tools.verify import _source_snapshot

REVISION = "metric-factor-study-v1"
ARMS = ("B", "W", "P", "S", "F")
OLD = {"B": "A", "W": "B", "P": "P", "S": "S1", "F": "S2"}
NEW = {v: k for k, v in OLD.items()}


def messages(question, source, arm, contexts, catalogs):
    if arm in {"B", "W"}:
        result = previous.messages(question, source, "B", contexts, catalogs)
        if arm == "W":
            schema, _, _, _, concepts = contexts[source]
            result[1]["content"] = json.dumps(
                shown_interpretation(schema, concepts), sort_keys=True
            )
        return result
    result = previous.messages(
        question, source, "P" if arm == "P" else "S1", contexts, catalogs
    )
    if arm != "F":
        if arm not in {"P", "S"}:
            raise ValueError("unknown_arm")
        return result
    original = (
        "Each candidate is one aggregate with its own population. "
        "Select slots {value: id} for a single aggregate or {numerator: id, "
        "denominator: id} for a ratio over the same table. Candidate order and IDs "
        "have no business meaning."
    )
    replacement = (
        "Each allowed pair is one aggregate with its own population. "
        "Select slots {value: {basis_id, population_id}} for a single aggregate "
        "or {numerator: {basis_id, population_id}, denominator: {basis_id, "
        "population_id}} for a ratio over the same table. Both IDs must be "
        "explicit, and their pair must be listed in allowed_pairs. Candidate "
        "order and IDs have no business meaning."
    )
    assert original in result[0]["content"]
    result[0]["content"] = result[0]["content"].replace(original, replacement)
    result[1]["content"] = json.dumps(
        FactoredSelection.model_json_schema(), sort_keys=True
    )
    payload = json.loads(result[-1]["content"])
    payload.pop("candidates")
    payload["candidate_factors"] = factor_cards(catalogs[source])
    result[-1]["content"] = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return result


def parse_record(payload, item, question, contexts, catalogs, observation):
    if item["arm"] != "F":
        old = "B" if item["arm"] in {"B", "W"} else OLD[item["arm"]]
        return previous.parse_record(
            payload, {**item, "arm": old}, question, contexts, catalogs, observation
        )
    try:
        result = bind_factors(payload, catalogs[item["source"]], question)
        observation["factor_selection"] = FactoredSelection.model_validate(
            payload
        ).model_dump()
        return result
    except (ValueError, TypeError) as error:
        observation["diagnostics"] = diagnostics(error)
        if error.args == ("pair_not_offered",):
            observation["diagnostics"] = [
                {
                    "stage": "validation",
                    "code": "pair_not_offered",
                    "schema_path": ["slots"],
                    "count": 1,
                }
            ]
        raise


def analyze(calls, ruler, fixture, contexts):
    normalized = [{**c, "arm": OLD[c["arm"]]} for c in calls]
    result = previous.analyze(normalized, ruler, fixture, contexts)
    result.pop("order")  # S/F is NOT an order-reversal experiment.
    result["summaries"] = {NEW[a]: s for a, s in result["summaries"].items()}
    for key in ("annotations", "fixed_pairs", "plans"):
        for row in result[key]:
            row["arm"] = NEW[row["arm"]]
            if "contextual" in row:
                row["contextual"] = {NEW[a]: v for a, v in row["contextual"].items()}
    return result


def screen(analysis, ruler):
    pairs = [r for r in analysis["fixed_pairs"] if r["arm"] == "W"]
    wanted = sum(
        len(c["correct"]) * 3 for c in ruler["cases"] if c["split"] == "development"
    )
    w = analysis["summaries"]["W"]
    wire = {
        "format_ready": w["status"].get("ok", 0) >= 35,
        "correct_controls_retained": sum(
            r["expected"] == r["verdict"] == "pass" for r in pairs
        )
        == wanted,
        "wrong_or_unresolved_passes": sum(
            r["expected"] != "pass" and r["verdict"] == "pass" for r in pairs
        ),
    }
    wire["eligible"] = (
        wire["format_ready"]
        and wire["correct_controls_retained"]
        and not wire["wrong_or_unresolved_passes"]
    )

    def correct(row):
        values = row.get("values", [])
        return (
            row["verdict"] == "pass"
            and row["compiled"]
            and len(values) == 3
            and all(
                v.get("gold_values_match") and v.get("compiler_reference_match")
                for v in values
            )
        )

    lookup = {(r["arm"], r["case_id"], r["language"]): r for r in analysis["plans"]}
    f = [r for r in analysis["plans"] if r["arm"] == "F"]
    improved, lost = [], []
    for row in f:
        baseline = lookup.get(("P", row["case_id"], row["language"]))
        if baseline is None:
            continue  # Interrupted schedules may not have reached paired P yet.
        if correct(row) and not correct(baseline):
            improved.append(row)
        if correct(baseline) and not correct(row):
            lost.append(row)
    stable = (
        all(
            correct(lookup["F", case, "zh"])
            for case in ("output_count_all", "service_rows")
        )
        if len(f) == 36
        else False
    )
    selector = {
        "improved": [(r["case_id"], r["language"]) for r in improved],
        "improved_families": sorted({r["family"] for r in improved}),
        "lost_correct": [(r["case_id"], r["language"]) for r in lost],
        "unresolved_answered": sum(
            r["gold_state"] != "clear" and r["compiled"] for r in f
        ),
        "stable_errors_fixed": stable,
        "F_correct": sum(correct(r) for r in f),
        "S_correct": sum(correct(r) for r in analysis["plans"] if r["arm"] == "S"),
        "order_confirmation": "not_measured",
    }
    selector["eligible_for_confirmation"] = (
        len(f) == 36
        and len(selector["improved_families"]) >= 2
        and not lost
        and not selector["unresolved_answered"]
        and stable
        and selector["F_correct"] > selector["S_correct"]
    )
    return {"W": wire, "F": selector}


def run(output, *, live=False):
    ruler, fixture, contexts, catalogs, coverage = previous.prepare()
    for candidates in catalogs.values():
        _, _, pairs = factor_catalog(candidates)
        assert sorted(pairs.values(), key=lambda c: c["id"]) == candidates
    cases = {c["id"]: c for c in ruler["cases"]}
    schedule = [
        {
            "case_id": c["id"],
            "language": language,
            "arm": arm,
            "source": "service" if c["id"] in previous.prior.SERVICE_CASES else "pos",
        }
        for c in ruler["cases"]
        if c["split"] == "development"
        for language in ("zh", "en", "ja")
        for arm in ARMS
    ]
    random.Random(20260914).shuffle(schedule)
    assert len(schedule) == 180
    requests = [
        messages(
            cases[i["case_id"]]["questions"][i["language"]],
            i["source"],
            i["arm"],
            contexts,
            catalogs,
        )
        for i in schedule
    ]
    start = _source_snapshot()
    if not start["available"]:
        raise ValueError("source_snapshot_unavailable")
    settings = (
        replace(GroundingModelSettings.from_environment(), timeout_seconds=60)
        if live
        else None
    )
    report = {
        "revision": REVISION,
        "live": live,
        "completed": False,
        "source_start": start,
        "inputs_sha256": digest({"ruler": ruler, "fixture": fixture}),
        "catalogs": catalogs,
        "coverage": coverage,
        "factor_cards": {s: factor_cards(c) for s, c in catalogs.items()},
        "settings": {
            "model": settings.model if settings else None,
            "temperature": 0,
            "thinking": False,
            "max_tokens": 4096,
            "timeout_seconds": 60,
            "max_retries": 0,
            "max_calls": 180,
        },
        "schedule": [
            {**i, "request_sha256": digest(r)}
            for i, r in zip(schedule, requests, strict=True)
        ],
        "requests": requests,
        "calls": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.with_suffix(".jsonl").exists():
        raise ValueError("fresh_output_required")
    with output.open("x") as out, output.with_suffix(".jsonl").open("x") as journal:
        journal.write(json.dumps({"manifest": report}, ensure_ascii=False) + "\n")
        journal.flush()
        client = None
        try:
            client = (
                ChatCompletionsGroundingClient(settings)._create_client()
                if live
                else None
            )
            for item, request in zip(schedule, requests, strict=True) if live else []:
                # Never send another request after source/input drift.
                if (
                    _source_snapshot()["tracked_source_digest"]
                    != start["tracked_source_digest"]
                ):
                    report["stop_reason"] = "source_drift"
                    break
                observation = {}
                question = cases[item["case_id"]]["questions"][item["language"]]
                result = call(
                    client,
                    settings,
                    request,
                    lambda p: parse_record(
                        p, item, question, contexts, catalogs, observation
                    ),
                    thinking=False,
                    max_tokens=4096,
                )
                record = {**item, **result, **observation}
                report["calls"].append(record)
                journal.write(json.dumps(record, ensure_ascii=False) + "\n")
                journal.flush()
                print(
                    f"calls={len(report['calls'])}/180 arm={item['arm']} "
                    f"status={result['status']}",
                    flush=True,
                )
                if len(report["calls"]) >= 3 and all(
                    c["status"] == "transport_error" for c in report["calls"][-3:]
                ):
                    report["stop_reason"] = "three_transport_errors"
                    break
            else:
                report["completed"] = bool(live)
        finally:
            if client:
                client.close()
            report["analysis"] = analyze(report["calls"], ruler, fixture, contexts)
            report["screen"] = screen(report["analysis"], ruler)
            report["source_end"] = _source_snapshot()
            report["source_unchanged"] = (
                start["tracked_source_digest"]
                == report["source_end"]["tracked_source_digest"]
            )
            report["call_status"] = dict(Counter(c["status"] for c in report["calls"]))
            json.dump(report, out, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    result = run(args.output, live=args.live)
    raise SystemExit(
        0
        if result["source_unchanged"] and (not args.live or result["completed"])
        else 1
    )
