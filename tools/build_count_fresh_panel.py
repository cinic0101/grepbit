#!/usr/bin/env python3
"""Build the fresh count panel (docs/count-fresh-panel.md, #152): kernel-derived Overview answer oracles, typed
count_basis clarify and decline oracles, the count-assumption annex and scripted correct actions, from the verbatim
authored questions in evals/dev/count-fresh-authored-v1.json. Offline: fixture only, no model.

Usage: .venv/bin/python tools/build_count_fresh_panel.py <output-dir> <fixture-db>
The committed count-fresh-* files under evals/dev/ are the output of this script; re-running it must reproduce the
same bytes.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grepbit.catalog import LEARNINGOPS  # noqa: E402
from grepbit.overview import OverviewRequest, execute_overview  # noqa: E402
from tools import p3_assets, p3_grading, recipe_smoke  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AUTHORED = ROOT / "evals/dev/count-fresh-authored-v1.json"
PANEL_ID = "p3-dev-count-fresh-v1"
LANGUAGES = ("zh-TW", "en", "ja")
TZ = "Asia/Taipei"
ASSUMPTION = {"count_basis": "booked_seats"}
PROV = ["Count fresh panel (#152): kernel-derived from the synthetic LearningOps fixture; development gold.",
        "Questions written by an independent fresh-context sub-agent from the owner's count rules; never a "
        "candidate output."]
# Type -> (branch, Overview count reading of the scripted correct action, stated assumption expected).
TYPES = {"G": ("answer", "unresolved", True), "S": ("answer", "booked_seats", False), "U": ("decline", None, False),
         "D": ("clarify", None, False), "B": ("answer", "unresolved", True), "O": ("answer", "none", False),
         "K": ("answer", "none", False)}
# Decline categories: the contract's D08 (an explicit account or people count) is recorded as D06 because the oracle
# parser admits D01-D06 only (as docs/coverage-matrix.md's D7 and D9 rows); an Overview plus a required unavailable
# count is D04 (its D8 row, and dev-BM8).
DECLINE_CATEGORY = {"F08": "D06", "F09": "D04", "F10": "D06"}
# The named meanings each clarify slot offers, in the question's order.
CLARIFY_MEANINGS = {"F11": ("booked_seats", "known_booking_accounts"), "F12": ("booked_seats", "distinct_people")}


def month(value):
    year, number = (int(part) for part in value.split("-"))
    following = (year + 1, 1) if number == 12 else (year, number + 1)
    return {"start": f"{year}-{number:02d}-01T00:00:00+08:00",
            "end": f"{following[0]}-{following[1]:02d}-01T00:00:00+08:00", "timezone": TZ}


def overview_request(slot):
    return {"center_code": slot["center_code"], **month(slot["month"])}


def answer_oracle(database, oracle_id, request):
    """An Overview answer oracle, built exactly as tools/build_dev_panel.py builds one."""
    pack = execute_overview(database, OverviewRequest.from_mapping(request))
    assert pack.status == "complete", (oracle_id, pack.status)
    facts = p3_grading._facts(pack)
    roles = list(facts)
    required = [r for r in roles if r not in ("daily_amount", "category_amounts")]
    auxiliary = [r for r in roles if r in ("daily_amount", "category_amounts")]
    coverage = {"status": "complete", "slots": {s.slot_id: s.role for s in pack.slots}, "states": ["checked"],
                "binding_center_id": pack.binding.center_id}
    aux_values = {r: [{"key": row.key, "value": row.value} for row in facts[r].rows] for r in auxiliary}
    return {
        "oracle_id": oracle_id, "revision": 1, "branch": "answer", "provenance": PROV,
        "recipe_id": "overview", "recipe_version": "0.1", "request": request, "coverage": coverage,
        "values": recipe_smoke._values(pack), "required_slots": required, "auxiliary_slots": auxiliary,
        "auxiliary_values": aux_values, "slot_states": {s.slot_id: s.state for s in pack.slots},
        "units": {r: f.unit for r, f in facts.items()}, "catalog_sha256": LEARNINGOPS.digest(),
    }


def clarification(slot):
    scope = overview_request(slot)
    return {"kind": "count_basis", "choices": [
        {"id": f"c{index}", "semantic_value": {"type": "count_basis", "scope": scope, "value": value}}
        for index, value in enumerate(CLARIFY_MEANINGS[slot["slot"]], 1)]}


def build(output: Path, database: Path) -> dict:
    authored = json.loads(AUTHORED.read_text(encoding="utf-8"))
    assert authored["version"] == "count-fresh-authored-v1"
    cases, oracles, order, responses, annex = [], [], [], [], {}
    for slot in authored["slots"]:
        name, kind = slot["slot"], slot["type"]
        branch, reading, assumed = TYPES[kind]
        family, oracle_id = f"dev-C{name}", f"dev-C{name}.v1"
        request = overview_request(slot)
        if branch == "answer":
            oracles.append(answer_oracle(database, oracle_id, request))
            action = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": request,
                      "count_request": reading}
        elif branch == "clarify":
            oracles.append({"oracle_id": oracle_id, "revision": 1, "branch": "clarify", "provenance": PROV,
                            "clarification": clarification(slot)})
            action = {"outcome": "clarify", "clarification": clarification(slot)}
        else:
            oracles.append({"oracle_id": oracle_id, "revision": 1, "branch": "decline", "provenance": PROV,
                            "designated_control": True, "capability_category": DECLINE_CATEGORY[name]})
            action = {"outcome": "declined"}
        if assumed:
            annex[oracle_id] = dict(ASSUMPTION)
        for language in LANGUAGES:
            case_id = f"{family}.{language}"
            cases.append({
                "case_id": case_id, "family_id": family, "question": slot["questions"][language],
                "language": language, "expected_branch": branch, "cohort": branch, "exposure": "design_seen",
                "provenance": {"origin": "development",
                               "references": [f"docs/count-fresh-panel.md#{name}",
                                              f"evals/dev/count-fresh-authored-v1.json#{name}"],
                               "seen_by_implementer": True, "exposure_history": ["design_seen"]},
                "semantic_signature": f"dev|C{name}|{kind}|{slot['center_code']}|{slot['month']}",
                "must_pass": True, "observational": False, "oracle_id": oracle_id})
            order.append(case_id)
            responses.append({"case_id": case_id, "action": action})
    output.mkdir(parents=True, exist_ok=True)
    documents = {
        "count-fresh-cases-v1.json": {"version": p3_assets.CASE_VERSION, "cases": cases},
        "count-fresh-oracles-v1.json": {"version": p3_assets.ORACLE_VERSION, "oracles": oracles},
        "count-fresh-panel-v1.json": {"version": p3_assets.PANEL_VERSION, "panel_id": PANEL_ID,
                                      "kind": "development", "cases": "count-fresh-cases-v1.json",
                                      "oracles": "count-fresh-oracles-v1.json", "order": order},
        "count-fresh-annex-v1.json": {"version": "count-assumption-annex-v1", "expectations": annex},
        "count-fresh-read-responses-v1.json": {"version": "p3-fake-responses-v1", "responses": responses},
    }
    for filename, document in documents.items():
        (output / filename).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    panel = p3_assets.load_panel(output / "count-fresh-panel-v1.json")
    return {"panel_id": panel.panel_id, "cases": len(panel.cases), "oracles": len(panel.oracles),
            "annex": sorted(annex)}


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2]))))
