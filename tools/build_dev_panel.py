#!/usr/bin/env python3
"""Build the dev-tier coverage panel (#87 step 3): kernel-derived answer oracles, typed clarify/decline oracles,
54 questions (18 matrix rows x 3 languages; D5 and D10 deferred: the contract scores neither a missing-period
decline nor a name-only decline as success). Offline: fixture only, no model.

Usage: .venv/bin/python tools/build_dev_panel.py <output-dir> <fixture-db>
The committed cases, oracles and panel under evals/dev/ are the output of this script and re-running it must
reproduce the same bytes; dev-responses-v1.json (scripted correct actions) is authored separately.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grepbit.catalog import LEARNINGOPS  # noqa: E402
from grepbit.breakdown import BreakdownRequest, execute_breakdown  # noqa: E402
from grepbit.compare import CompareRequest, execute_compare  # noqa: E402
from grepbit.overview import OverviewRequest, execute_overview  # noqa: E402
from tools import p3_assets, p3_grading, recipe_smoke  # noqa: E402

OUT = Path(sys.argv[1])
DB = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
TZ = "Asia/Taipei"
CATALOG = LEARNINGOPS.digest()


def month(y, m):
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return {"start": f"{y}-{m:02d}-01T00:00:00+08:00", "end": f"{ny}-{nm:02d}-01T00:00:00+08:00", "timezone": TZ}


def scope(y, m):
    return {"metrics": ["confirmed_booked_amount"], **month(y, m), "center_id": None}


PROV = ["Dev tier (#87 step 3): kernel-derived from the synthetic LearningOps fixture; development gold, not fresh semantics.",
        "Coverage matrix row; questions authored by the implementing agent; never a candidate output."]


def answer_oracle(oracle_id, recipe, request):
    if recipe == "overview":
        pack = execute_overview(DB, OverviewRequest.from_mapping(request))
    elif recipe == "compare":
        pack = execute_compare(DB, CompareRequest.from_mapping(request))
    else:
        pack = execute_breakdown(DB, BreakdownRequest.from_mapping(request))
    assert pack.status == "complete", (oracle_id, pack.status)
    facts = p3_grading._facts(pack)
    roles = list(facts)
    required = [r for r in roles if r not in ("daily_amount", "category_amounts")]
    auxiliary = [r for r in roles if r in ("daily_amount", "category_amounts")]
    coverage = {"status": "complete",
                "slots": {s.slot_id: ("required" if recipe == "compare" else s.role) for s in pack.slots},
                "states": ["checked"] if recipe == "overview" else ["checked", "undefined"]}
    if recipe == "overview":
        coverage["binding_center_id"] = pack.binding.center_id
    if recipe == "breakdown":
        coverage["group"] = {"dimension": "course", "coverage": "top_k", "top_k": request["top_k"]}
    aux_values = {r: [{"key": row.key, "value": row.value} for row in facts[r].rows] for r in auxiliary}
    return {
        "oracle_id": oracle_id, "revision": 1, "branch": "answer", "provenance": PROV,
        "recipe_id": recipe, "recipe_version": "0.1", "request": request, "coverage": coverage,
        "values": recipe_smoke._values(pack), "required_slots": required, "auxiliary_slots": auxiliary,
        "auxiliary_values": aux_values, "slot_states": {s.slot_id: s.state for s in pack.slots},
        "units": {r: f.unit for r, f in facts.items()}, "catalog_sha256": CATALOG,
    }


def clarify_oracle(oracle_id, kind, choices):
    return {"oracle_id": oracle_id, "revision": 1, "branch": "clarify", "provenance": PROV,
            "clarification": {"kind": kind, "choices": [{"id": f"c{i}", "semantic_value": v}
                                                        for i, v in enumerate(choices, 1)]}}


def decline_oracle(oracle_id, category):
    return {"oracle_id": oracle_id, "revision": 1, "branch": "decline", "provenance": PROV,
            "designated_control": True, "capability_category": category}


ov = lambda code: {"center_code": code, **month(2026, 3)}
oracles = [
    answer_oracle("dev-A1.v1", "overview", ov("CTR-A01")),
    answer_oracle("dev-A2.v1", "overview", ov("CTR-B01")),
    answer_oracle("dev-A3.v1", "compare", {"current": scope(2026, 3), "baseline": scope(2026, 2)}),
    answer_oracle("dev-A4.v1", "compare", {"current": scope(2026, 4), "baseline": scope(2026, 2)}),
    answer_oracle("dev-A5.v1", "breakdown", {**month(2026, 3), "top_k": 3}),
    answer_oracle("dev-A6.v1", "breakdown", {**month(2026, 3), "top_k": 2}),
    clarify_oracle("dev-C1.v1", "count_basis", [
        {"type": "count_basis", "scope": ov("CTR-B01"), "value": "booked_seats"},
        {"type": "count_basis", "scope": ov("CTR-B01"), "value": "known_booking_accounts"}]),
    clarify_oracle("dev-C2.v1", "comparison_roles", [
        {"type": "comparison_roles", "request": {"current": scope(2026, 3), "baseline": scope(2026, 2)}},
        {"type": "comparison_roles", "request": {"current": scope(2026, 2), "baseline": scope(2026, 3)}}]),
    clarify_oracle("dev-C3.v1", "center", [
        {"type": "center", "request": ov("CTR-A01")}, {"type": "center", "request": ov("CTR-A02")}]),
    clarify_oracle("dev-C4.v1", "metric_meaning", [
        {"type": "metric_meaning", "scope": ov("CTR-A02"), "value": "confirmed_booked_amount"},
        {"type": "metric_meaning", "scope": ov("CTR-A02"), "value": "cash_received"}]),
    decline_oracle("dev-D1.v1", "D01"), decline_oracle("dev-D2.v1", "D02"), decline_oracle("dev-D3.v1", "D03"),
    decline_oracle("dev-D4.v1", "D04"), decline_oracle("dev-D6.v1", "D06"), decline_oracle("dev-D7.v1", "D06"),
    decline_oracle("dev-D8.v1", "D04"), decline_oracle("dev-D9.v1", "D06"),
]

# Paraphrase or translation descendants of exposed development families keep the
# exposed_regression label and name their historical parent (contract section 5).
EXPOSED_PARENT = {"A1": "evals/p3/development-cases-v1.json#E01_overview", "A3": "evals/p3/development-cases-v1.json#E02_compare",
                  "A5": "evals/p3/development-cases-v1.json#E03_share_denominator",
                  "A6": "evals/p3/development-cases-v1.json#E03_share_denominator",
                  "C1": "evals/p3/development-cases-v1.json#C01_count_basis",
                  "C2": "evals/p3/development-cases-v1.json#C02_comparison_roles",
                  "C3": "evals/p3/development-cases-v1.json#C03_center", "C4": "evals/p3/development-cases-v1.json#C04_metric_meaning",
                  "D1": "evals/p3/development-cases-v1.json#D01_profit", "D2": "evals/p3/development-cases-v1.json#D02_cash_received"}
# (row, branch, cohort, oracle, signature, {lang: question})
ROWS = [
    ("A1", "answer", "dev-A1.v1", "overview|core|CTR-A01|2026-03", {
        "zh-TW": "CTR-A01 在 2026 年 3 月的報名狀況如何？",
        "en": "Give me the March 2026 booking picture for CTR-A01.",
        "ja": "CTR-A01 の 2026 年 3 月の申込状況を教えてください。"}),
    ("A2", "answer", "dev-A2.v1", "overview|explicit_definitions|CTR-B01|2026-03", {
        "zh-TW": "想看 CTR-B01 2026 年 3 月的已確認報名：折扣後、未扣退款的金額、報名筆數和席次。",
        "en": "For CTR-B01 in March 2026, show confirmed bookings: amount after discounts and before refunds, number of bookings, and seats.",
        "ja": "CTR-B01 の 2026 年 3 月の確定済み申込について、割引後・返金差引前の金額、申込件数、席数を見たいです。"}),
    ("A3", "answer", "dev-A3.v1", "compare|current=2026-03|baseline=2026-02|bound_orientation", {
        "zh-TW": "2026 年 3 月全部中心的已確認報名金額，跟 2 月比起來怎麼樣？",
        "en": "How does the confirmed booking amount across all centers for March 2026 compare against February?",
        "ja": "2026 年 3 月の全センターの確定済み申込金額は、2 月と比べてどうでしたか。"}),
    ("A4", "answer", "dev-A4.v1", "compare|current=2026-04|baseline=2026-02|shared_year_nonadjacent", {
        "zh-TW": "2026 年 4 月的整體已確認報名金額相較於同年 2 月變化多少？",
        "en": "In 2026, how much did the overall confirmed booking amount change in April compared with February?",
        "ja": "2026 年の 4 月の全体の確定済み申込金額は、同年 2 月に対してどれだけ変わりましたか。"}),
    ("A5", "answer", "dev-A5.v1", "breakdown|top_k=3|2026-03", {
        "zh-TW": "2026 年 3 月報名金額最高的三個課程是哪些？各多少，合計占整體多少？",
        "en": "Which three courses had the highest booking amounts in March 2026, and what share of the total do they make up together?",
        "ja": "2026 年 3 月に申込金額が最も多かった講座トップ 3 とその金額、合計が全体に占める割合を教えてください。"}),
    ("A6", "answer", "dev-A6.v1", "breakdown|top_k=2|share|2026-03", {
        "zh-TW": "3 月（2026）前兩名課程的報名金額合計占全體幾成？",
        "en": "In March 2026, what portion of all booking amount came from the top 2 courses?",
        "ja": "2026 年 3 月、上位 2 講座の申込金額は全体の何割でしたか。"}),
    ("C1", "clarify", "dev-C1.v1", "clarify|count_basis|CTR-B01|2026-03", {
        "zh-TW": "CTR-B01 在 2026 年 3 月報名的人數有多少？我不確定你們是算席次還是算報名帳戶。",
        "en": "How many people booked at CTR-B01 in March 2026? I am not sure whether you count seats or booking accounts.",
        "ja": "CTR-B01 で 2026 年 3 月に申し込んだ人数はどれくらいですか。席数で数えるのか申込アカウントで数えるのか分かりません。"}),
    ("C2", "clarify", "dev-C2.v1", "clarify|comparison_roles|2026-02,2026-03", {
        "zh-TW": "幫我比一下 2026 年 2 月和 3 月的整體已確認報名金額。",
        "en": "Compare the overall confirmed booking amounts of February and March 2026.",
        "ja": "2026 年 2 月と 3 月の全体の確定済み申込金額を比較してください。"}),
    ("C3", "clarify", "dev-C3.v1", "clarify|center|CTR-A01,CTR-A02|2026-03", {
        "zh-TW": "CTR-A01 或 CTR-A02，2026 年 3 月的報名狀況如何？",
        "en": "What did March 2026 bookings look like at CTR-A01 or CTR-A02?",
        "ja": "CTR-A01 か CTR-A02 の 2026 年 3 月の申込状況はどうでしたか。"}),
    ("C4", "clarify", "dev-C4.v1", "clarify|metric_meaning|CTR-A02|2026-03", {
        "zh-TW": "CTR-A02 在 2026 年 3 月的收入是多少？",
        "en": "What was the revenue at CTR-A02 in March 2026?",
        "ja": "CTR-A02 の 2026 年 3 月の売上はいくらでしたか。"}),
    ("D1", "decline", "dev-D1.v1", "decline|D01|profit", {
        "zh-TW": "CTR-A01 在 2026 年 3 月賺了多少利潤？",
        "en": "How much profit did CTR-A01 make in March 2026?",
        "ja": "CTR-A01 は 2026 年 3 月にいくら利益を出しましたか。"}),
    ("D2", "decline", "dev-D2.v1", "decline|D02|cash_received", {
        "zh-TW": "2026 年 3 月實際入帳的收款金額是多少？",
        "en": "What was the total cash actually received in March 2026?",
        "ja": "2026 年 3 月に実際に入金された金額はいくらですか。"}),
    ("D3", "decline", "dev-D3.v1", "decline|D03|annual", {
        "zh-TW": "2026 年全年到目前為止的已確認報名金額總計是多少？",
        "en": "What is the year-to-date confirmed booking amount for 2026?",
        "ja": "2026 年の年初から今までの確定済み申込金額の合計はいくらですか。"}),
    ("D4", "decline", "dev-D4.v1", "decline|D04|overview_plus_instructor_ranking", {
        "zh-TW": "給我 CTR-A01 2026 年 3 月的報名概況，並且列出哪位講師的評價最高。",
        "en": "Show CTR-A01's March 2026 booking overview and also tell me which instructor got the best ratings.",
        "ja": "CTR-A01 の 2026 年 3 月の申込概況と、あわせて評価が一番高い講師を教えてください。"}),
    ("D6", "decline", "dev-D6.v1", "decline|D06|weekly_by_region", {
        "zh-TW": "2026 年 3 月各地區每週的已確認報名金額是多少？",
        "en": "What were the confirmed booking amounts per region per week in March 2026?",
        "ja": "2026 年 3 月の地域別・週別の確定済み申込金額を教えてください。"}),
    ("D7", "decline", "dev-D7.v1", "decline|D06|currency_conversion", {
        "zh-TW": "把 2026 年 3 月全部中心的已確認報名金額換算成美元給我。",
        "en": "Convert the March 2026 confirmed booking amount across all centers into US dollars.",
        "ja": "2026 年 3 月の全センターの確定済み申込金額を米ドルに換算してください。"}),
    ("D8", "decline", "dev-D8.v1", "decline|D04|overview_plus_attendance_count", {
        "zh-TW": "CTR-B01 2026 年 3 月的報名概況，另外也要實際到場的人次。",
        "en": "I need CTR-B01's March 2026 booking overview plus the number of attendance visits that actually took place.",
        "ja": "CTR-B01 の 2026 年 3 月の申込概況に加えて、実際に出席した延べ人数も必要です。"}),
    ("D9", "decline", "dev-D9.v1", "decline|D06|row_enumeration", {
        "zh-TW": "列出 2026 年 3 月 CTR-A01 每一筆報名的學員姓名和電話。",
        "en": "List every March 2026 booking at CTR-A01 with the learner's name and phone number.",
        "ja": "2026 年 3 月の CTR-A01 の申込を一件ずつ、受講者の氏名と電話番号付きで一覧にしてください。"}),
]

cases, order = [], []
for row, branch, oracle_id, signature, questions in ROWS:
    for lang in ("zh-TW", "en", "ja"):
        case_id = f"dev-{row}.{lang}"
        exposure = "exposed_regression" if row in EXPOSED_PARENT else "design_seen"
        references = [f"docs/coverage-matrix.md#{row}"] + ([EXPOSED_PARENT[row]] if row in EXPOSED_PARENT else [])
        cases.append({
            "case_id": case_id, "family_id": f"dev-{row}", "question": questions[lang], "language": lang,
            "expected_branch": branch, "cohort": branch, "exposure": exposure,
            "provenance": {"origin": "development", "references": references,
                           "seen_by_implementer": True, "exposure_history": [exposure]},
            "semantic_signature": f"dev|{row}|{signature}", "must_pass": True, "observational": False,
            "oracle_id": oracle_id})
        order.append(case_id)

(OUT / "dev-cases-v1.json").write_text(json.dumps({"version": p3_assets.CASE_VERSION, "cases": cases},
                                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "dev-oracles-v1.json").write_text(json.dumps({"version": p3_assets.ORACLE_VERSION, "oracles": oracles},
                                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "dev-panel-v1.json").write_text(json.dumps({
    "version": p3_assets.PANEL_VERSION, "panel_id": "p3-dev-matrix-v1", "kind": "development",
    "cases": "dev-cases-v1.json", "oracles": "dev-oracles-v1.json", "order": order}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8")
panel = p3_assets.load_panel(OUT / "dev-panel-v1.json")
print("panel loads:", panel.panel_id, len(panel.cases), "cases", len(panel.oracles), "oracles")
for o in oracles:
    if o["branch"] == "answer":
        print(o["oracle_id"], o["values"])
