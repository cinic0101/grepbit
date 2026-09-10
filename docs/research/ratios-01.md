# Ratio and share questions: the owner's review and what it found (2026-09-10)

## Setting

Prompt v10 and v11 made ratio, share and growth answerable. Twelve ratio and
share questions from batch 1 and holdout 2 were rerun as a judged set
(`.artifacts/ratios-01/`, text kept out of git because holdout-2 questions
are in it) and the owner read the review sheet of run 2. Their notes, in
order, and what each turned out to be.

## Findings

| Case | Owner's note | Verified against the database | Cause | Fix |
|---|---|---|---|---|
| h2_q21 store share, h2_q23 product quantity share | "1.0 does not look right" | store share 0.185, product share 0.0196 (107 of 5,452 units) | the plan filtered on the grouped column (`store_name = X`) before the window total, so the population was the one store | compiler: with a `share_of_total` measure a filter on a grouped column selects rows after the share (outer `WHERE` over the grouped subquery); lineage `[after share]`, assumption states it |
| b1_q34 return ratio, last 30 days | "SQL looks right but 0 is wrong" | the window was 2026-02-04 to 2026-03-06: the model wrote `offset 0, length 30`, a window starting today and running forward; the data ends on as_of. The past 30 days give -0.044 (282 returns, -986,100 over 22,881,942) | the `relative_window_reaches_future` gate only checked `offset < 0`; a current-anchored window longer than one unit passed and the answer was marked `verified` | planner adapter repair `offset 0, length L > 1` (not to-date) -> `offset -L`, stated as an assumption; the gate now fires for any offset as the safety net |
| b1_q21 salesperson share, 同期 | "where is 同期 defined?" | 25 salespeople, one share each over all data; run 2 had split it by month (61 rows) with no period word in the question | model variance at a fixed revision: a grain without a window that nobody asked for | `unrequested_grain`: such a grain is dropped unless the question carries a per-period or trend word (shape pack v4, 69 words); the share assumption now says what 同期 means: the same window and filters as the group values, or each period's own total when a grain is asked for |
| b1_q10, b1_q17, b1_q50 | same 同期 question | shares sum to 1 by construction; q50 is one whole-data ratio | none | the assumption wording above |
| b1_q41 category share | "negative shares need discussion" | three categories are net negative over all non-return lines: 二手回收類 (120 lines, all negative, -438,555), 收入調整 (139, all negative, -280,240), 佣金 (39 of 43 negative, net -17,643); 其他 also carries 289 negative lines (-262,445) among 3,293 | trade-ins, revenue adjustments and commissions are booked as negative line amounts; the share divides by the net total, so those categories show negative shares and the positive ones are inflated by about 2.6% (net total 38,803,955 against 39,808,834 of positive lines) | a business decision, not code: see below |
| b1_q49 return rate by product | "no problem seen" | denominator excludes returns (the operand-level segment rule) | | verdict `correct` recorded |
| h2_q25 category product share | "do the shares add to 100%?" | 720 products, every one has a category, 保健‧保養 has 43 (0.0597); the window total is over all groups so the 14 shares sum to 1 | | none |

The return ratio comes out negative (-0.044) because return transactions
carry negative `total_amount`. That is the stored sign, not an error, but a
reader expects 退貨率 4.4%. The algebra has no negation; a metric-level
`negate` (or an `abs` aggregate) would be the smallest addition. Owner's call.

## Negative categories: the options

1. Leave it. Shares sum to 1, negative rows are visible, the assumption says
   the total is the net of every line. Cheapest, but a reader asking for
   "category share of sales" gets 通訊 at 38.4% when it is 37.4% of positive
   sales.
2. Define the reviewed metric `line_sales` over positive lines only
   (`amount > 0` as a metric filter). Then 二手回收類, 收入調整 and the
   negative 佣金 lines vanish from every category question, but so do the 289
   negative lines in 其他 (discount or correction lines inside ordinary
   categories), and `line_sales` stops reconciling with `gross_sales`.
3. A default-excluded segment on the three categories (a value-based
   segment on `category.category_name`). Keeps discount lines, drops the
   non-merchandise categories from every line-level question unless the
   question names them. Puts three category names into the overlay, which
   the owner has so far kept out of it.

The owner chose option 1 (2026-09-10). Two things carry it: the reviewed
definition of `line_sales` in overlay v11 now says the sum is the net of
every line and names the negative bookings, so every answer over it states
that; and the ask core adds a warning whenever a share comes out negative
for some group (`negative_share_warning`), so any datasource with the same
pattern says so without an overlay edit. Verified on the ratio set
(`run-04`) and batch 1 (`pos-real-batch1-14.json`).

## After the fixes

Ratio set run 3 (same prompt v11, overlay v10, `as_of`): h2_q23 0.0196 with
the filter applied after the share; b1_q34 window 2026-01-05 to 2026-02-04,
ratio -0.044 with the repair stated as an assumption; b1_q21 25 rows (the
model wrote no grain this time, so the drop rule did not fire); h2_q21 came
back without the store filter at all (all five stores' shares, the asked one
among them at 0.185), another sample of plan variance. h2_q24 (a salesperson
name, refused by policy) now shows the after-share form too. Ten cases wait
for the owner's verdict in `.artifacts/ratios-01/verdicts-03.yaml`
(review-03.md).

Three cases pin the rules on the fixture database (`pos_features.yaml`:
`ft_share_one_store`, `ft_last_30_days`, `ft_share_same_period_no_grain`);
all three pass (`pos-features-18.json`, 35/35). The full suite rerun with the
fixes (artifacts in `evidence/README.md`, "ratio review fixes" row): author
sets 156/160, features 35/35, having 6/6, overlay fixture 14/14, real smoke
7/7, batch 1 43/50 with the same seven ratio cases awaiting judgment,
holdout 2 24 answered / 4 clarify / 1 failed / 1 unsupported as before. The
grain drop fired once on the real database (batch 1 q17, the model added a
monthly grain this run and the answer stayed the whole-window share); the
window repair fired on q34 and on the new fixture case. Nine cases changed
only their output alias between runs, the usual variance at a fixed
revision. One new shape slip surfaced twice in the no-sample POS set
(`pos-nosample-13`, `-14`): the model wrote `"aggregate": "count"` beside a
`ratio` for 會員交易佔比, which the validator rejects; a repair drops the
bare aggregate and the case answers again (`pos-nosample-15`, 25/26 with the
standing partial-name miss). 170 tests.
