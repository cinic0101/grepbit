# LearningOps language review

This is an evaluator-only review sheet, not a runtime prompt or a live-evaluation result.
The original `question` in `learningops.json` is Traditional Chinese (`zh-TW`).
The paired English/Japanese variants are in `learningops-languages.json`, keyed
by `case_id` and pinned to the base catalog hash. Every triplet shares the same
case ID, fixture, context and existing reference/behavior expectation.
Wording revision v0.2 follows the owner-relayed local-agent review of `80109e5`.
Q06/Q07 Japanese now names posting plus successful status, not processing completion.
Q13 explicitly uses ascending course ID for ties in all three languages, matching
the existing reference SQL. E09 consistently names a session, not a course.
Only Q13/E09 source wording and Q13 oracle question metadata changed. Seed,
schema, reference SQL/parameters, numeric results and behavioral expectations
are unchanged; historical wording/evidence remains at `80109e5`.

**Status: local-agent review received; revisions pending focused local recheck and owner approval; no evaluation-model run.**

## Review provenance

The owner supplied the local coding-agent report on `80109e5`: 21 tests and
18 reference/9 fixture checks passed on Python 3.11.13 / SQLite 3.50.4; numerical
recalculation matched all 18 references after viewing expectations. This is
reported local-agent evidence, not a blinded or human-native language sign-off.
The review identified Q06/Q07 posting wording as the sign-off concern; E09,
ranking witnesses and surface guards were optional improvements. Revision v0.2
addresses those findings without changing product scope or starting P1.

## Review rules

- Preserve count unit, population, time basis, boundaries, negation, denominator and uncertainty.
- Keep stable codes and stored proper names unchanged; localized aliases are a separate future test.
- Do not insert a year into E06, choose a center for E04, or choose a counting unit for E05.
- Q14 remains a reference-only ID-boundary check, not an MVP details promise.
- E10 is an injected timeout scenario description, not a user question or a live language trial.
- E12 retains its conditional capability boundary; translation does not admit the capability.
- Q13 explicitly requires course ID ascending at equal amount; an isolated fourth-course/tied-cutoff witness is in `tests/test_review_witnesses.py`. This is reference coverage, not runtime support.
- E09 keeps S01 and names a session in all three languages; the expected 120 minutes / 2 hours is unchanged.
- A shared expectation is a proposed equivalence, not proof of translation fidelity. Record mismatches in issue #3 before any live comparison.

There are 30 semantic families: 29 question families (87 authored question
variants) and one operational scenario (three translated descriptions). This
is not 90 independent questions, 87 selected model calls, or a 90-case product pass.

## Paired inputs

| Case ID / kind | Traditional Chinese | English | Japanese |
|---|---|---|---|
| `Q01_booked_amount` / question | 2026年3月已確認報名的折扣後金額是多少（未扣退款）？ | What is the total amount after discounts for confirmed bookings in March 2026, before deducting refunds? | 2026年3月の確定済み申込について、割引適用後・返金差引前の金額合計はいくらですか？ |
| `Q02_booking_count` / question | 2026年3月有幾筆已確認報名？ | How many confirmed bookings were there in March 2026? | 2026年3月の確定済み申込は何件ですか？ |
| `Q03_booked_seats` / question | 2026年3月已確認報名合計多少席次？ | How many seats were booked in total through confirmed bookings in March 2026? | 2026年3月の確定済み申込で、予約された席数は合計いくつですか？ |
| `Q04_known_learners` / question | 2026年3月已確認報名涉及幾個不同的具名報名帳戶（不含匿名）？ | How many distinct identified booking accounts were associated with confirmed bookings in March 2026, excluding anonymous bookings? | 2026年3月の確定済み申込には、匿名申込を除いて、識別可能な申込アカウントが重複なしでいくつありますか？ |
| `Q05_center_amount` / question | CTR-A01 在2026年3月已確認報名金額是多少？ | What was the confirmed booking amount for CTR-A01 in March 2026? | CTR-A01の2026年3月の確定済み申込金額はいくらですか？ |
| `Q06_cash_received` / question | 2026年3月入帳的成功收款金額，不依報名狀態排除，是多少？ | What was the total amount of successful payments posted in March 2026, without excluding any based on booking status? | 申込の状態による除外をせず、2026年3月に計上された、支払ステータスが「成功」の入金額の合計はいくらですか？ |
| `Q07_posted_refunds` / question | 2026年3月成功入帳的退款金額是多少？ | What was the total amount of successful refunds posted in March 2026? | 2026年3月に計上された、返金ステータスが「成功」の返金額の合計はいくらですか？ |
| `Q08_cohort_refunds` / question | 2026年3月已確認報名截至2026年4月1日零時的累計成功退款是多少？ | For confirmed bookings in March 2026, what was the cumulative amount of successful refunds as of midnight at the start of April 1, 2026? | 2026年3月の確定済み申込について、2026年4月1日午前0時時点での返金完了額の累計はいくらですか？ |
| `Q09_previous_amount` / question | 2026年2月已確認報名金額是多少？ | What was the confirmed booking amount in February 2026? | 2026年2月の確定済み申込金額はいくらですか？ |
| `Q10_center_breakdown` / question | 2026年3月各中心已確認報名金額，包含無報名中心？ | What was the confirmed booking amount for each center in March 2026, including centers with no bookings? | 申込がなかったセンターも含め、2026年3月の各センターの確定済み申込金額を教えてください。 |
| `Q11_category_breakdown` / question | 2026年3月已確認報名按課程分類拆分金額？ | Break down the confirmed booking amount in March 2026 by course category. | 2026年3月の確定済み申込金額を講座カテゴリ別に示してください。 |
| `Q12_daily_trend` / question | 按台北日期列出2026年3月每日已確認報名金額（只列有資料日）？ | List the daily confirmed booking amount for March 2026 by Taipei calendar date, showing only dates with data. | 台北の日付に基づき、2026年3月の日別の確定済み申込金額を、データがある日だけ表示してください。 |
| `Q13_top_courses` / question | 2026年3月已確認報名金額最高的前三個課程（同額按課程ID升冪）？ | Which three courses had the highest confirmed booking amounts in March 2026? Break ties by course ID in ascending order. | 2026年3月の確定済み申込金額が最も高い講座を上位3件示してください。同額の場合は講座IDの昇順にしてください。 |
| `Q14_boundary_membership` / question | 哪些已確認報名落在台北2026年3月（只驗證ID，不代表MVP提供任意明細）？ | Which confirmed bookings fall within March 2026 in Taipei time? This checks IDs only and does not imply arbitrary detail listings are supported in the MVP. | 台北時間の2026年3月に該当する確定済み申込はどれですか？ これはIDのみの検証であり、MVPが任意の明細表示に対応することを意味しません。 |
| `Q15_net_cash` / question | 2026年3月淨現金流入（成功收款減同月成功退款）是多少？ | What was the net cash inflow in March 2026, defined as successful payments received minus successful refunds in the same month? | 2026年3月の純現金流入額はいくらですか？ 同月の入金完了額から返金完了額を差し引いてください。 |
| `Q16_cohort_net_amount` / question | 2026年3月已確認報名金額扣除截至2026年4月1日零時的該群報名退款後是多少？ | What was the confirmed booking amount for March 2026 after deducting refunds belonging to those bookings as of midnight at the start of April 1, 2026? | 2026年3月の確定済み申込金額から、その申込に対する2026年4月1日午前0時時点の返金額を差し引くと、いくらですか？ |
| `Q17_line_count` / question | 2026年3月已確認報名有幾筆課程明細（不是報名筆數或席次）？ | How many course line items were in confirmed bookings in March 2026, rather than the number of bookings or seats? | 2026年3月の確定済み申込には、講座明細が何件ありますか？ 申込件数や席数ではありません。 |
| `Q18_target_missing_zero` / question | 2026年3月各中心的已確認報名金額目標；缺目標保留空值，不當成0？ | Show each center's confirmed booking amount target for March 2026. Keep missing targets null instead of treating them as zero. | 2026年3月の各センターの確定済み申込金額の目標値を示してください。目標値がない場合はNULLのままにし、0として扱わないでください。 |
| `E01_overview` / question | CTR-A01 2026年3月的報名狀況如何？ | How were bookings at CTR-A01 in March 2026? | CTR-A01の2026年3月の申込状況はどうでしたか？ |
| `E02_compare` / question | 2026年3月全體已確認報名金額比2月如何？ | How did the overall confirmed booking amount in March 2026 compare with February? | 2026年3月の全体の確定済み申込金額は、2月と比べてどうでしたか？ |
| `E03_share_denominator` / question | 2026年3月報名金額前兩名課程合占全部金額多少？ | What share of the total booking amount in March 2026 came from the top two courses by booking amount? | 2026年3月の申込金額上位2講座は、全体の申込金額のどれくらいの割合を占めますか？ |
| `E04_ambiguous_entity` / question | 星河中心2026年3月報名多少筆？ | How many bookings did 星河中心 have in March 2026? | 星河中心の2026年3月の申込は何件ですか？ |
| `E05_ambiguous_count` / question | 2026年3月參加人數多少？ | How many people participated in March 2026? | 2026年3月の参加人数は何人ですか？ |
| `E06_ambiguous_year` / question | CTR-A01 3月報名金額多少？ | What was the booking amount for CTR-A01 in March? | CTR-A01の3月の申込金額はいくらですか？ |
| `E07_missing_profit` / question | 2026年3月利潤是多少？ | What was the profit in March 2026? | 2026年3月の利益はいくらですか？ |
| `E08_visibility` / question | 列出所有學員的email。 | List the email addresses of all learners. | すべての受講者のメールアドレスを一覧表示してください。 |
| `E09_unit_conversion` / question | S01場次的時長是幾小時？ | What is the duration of session S01 in hours? | 開催回S01の所要時間は何時間ですか？ |
| `E10_budget_partial` / scenario_description | Overview 的非必要分類事實查詢逾時。 | The query for an optional category fact in an overview times out. | 概要分析で、必須ではないカテゴリ別の事実を取得するクエリがタイムアウトする。 |
| `E11_zero_missing` / question | CTR-B01與CTR-Z01的2026年3月目標達成率？ | What were the target attainment rates for CTR-B01 and CTR-Z01 in March 2026? | CTR-B01とCTR-Z01の2026年3月の目標達成率はいくらですか？ |
| `E12_absence_extension` / question | 2026年3月哪些課程沒有任何已確認報名？ | Which courses had no confirmed bookings at all in March 2026? | 2026年3月に確定済みの申込が一件もなかった講座はどれですか？ |
