# Holdout 3: the capabilities not yet built, measured blind (2026-09-10)

## Setting

After batch 1 and holdout 2 were settled, the owner wrote 15 questions on
the real POS database aimed at what the algebra does not have yet: growth
comparisons, latest row per entity, day-of-week and time-of-day
breakdowns, anti-joins (entities with no activity) and rolling averages.
The build side did not read them before the run; `questions_to_cases.py`
printed the count only. Prompt v11, overlay v12, shape pack v4, `as_of`
2026-02-04 18:00 Asia/Taipei, sampling off, rows redacted. Question text,
report, review sheet and verdicts stay in `.artifacts/holdout3/` (one
question names three salespeople); `evidence/README.md` records their
SHA-256.

## Run 1 (blind)

| Status | Cases | What they were |
|---|---|---|
| answered | 5 | two growth questions, one "latest business day", two anti-joins |
| unsupported | 8 | two latest-row-per-entity, two time-part breakdowns, three rolling averages, one anti-join refused as `plan_grain_conflict` |
| semantic_gap | 1 | weekday versus weekend |
| failed | 1 | month-to-date growth: the model omitted `unit` in the relative scope (reproduced twice) |

P50 5.9 s, P95 7.1 s. The owner judges run 1; the build side's reading of
the five answers, written into the verdict skeleton as notes:

- Growth over last week per store: the window was last week alone, so
  `LAG` had no previous week and every growth value is NULL. The numbers
  shown (transactions per store) are right; the asked number is missing.
- Growth of two 7-day spans per salesperson: computed as daily growth
  inside the last 7 days. A comparison of two custom-length spans is not
  in the algebra (growth compares calendar buckets); the honest outcome is
  a refusal, the given one is a misread with the misread exposed in the
  interpretation ("per day").
- Latest business day of one store: read as as_of's day. Right because
  2026-02-04 has sales; "the last day with data" is a latest-row question.
- Two anti-joins (products never sold, stores without sales this month):
  the plan groups the child table and asks `HAVING COUNT(...) = 0`, which
  no group can satisfy, so both return 0 rows with only the empty-result
  warning. Wrong by construction; the warning does not say why.

Nine refusals are honest: the constructs do not exist. One is the
malformed-output failure, a shape slip (missing `unit` beside a `grain`).

## What this run asks for, in order of cheapness

1. Deterministic guards, no new algebra: a growth plan widens its window by
   one grain unit so the previous bucket exists (assumption stated); growth
   on a to-date window is refused (the previous bucket would be a whole
   period against a partial one); a missing relative `unit` is taken from
   the grain; `HAVING count = 0` over the base table's own rows is refused
   as an anti-join the algebra cannot express, instead of 0 rows.
2. Constructs, each a real addition: latest row per entity (also "last day
   with data"), anti-join (`NOT EXISTS` from a parent to a child table,
   with the child's filters and window), derived time parts (day of week,
   hour bucket) as dimensions, rolling windows (moving average over a
   dense calendar), and comparison of two same-length spans (growth
   against the previous window, the deferred 期間對期間 item).

Which of the constructs to build first is the roadmap question; this run
gives each of them two or three real questions to be measured on.

## Run 2: the guards, no new algebra

Built the same evening, all deterministic (`../knowledge/tier0-contract.md`,
"Deterministic repairs and rules"): a growth plan whose window is one unit of
its grain is widened one unit backwards; growth on a to-date window is
refused (`growth_to_date_unsupported`); a relative window without `unit`
takes the grain; `HAVING count = 0` over the base table's own rows is
refused (`anti_join_required`) with the reason. Same prompt, overlay and
`as_of`.

| Status | Run 1 | Run 2 |
|---|---|---|
| answered | 5 | 3 |
| unsupported | 8 | 11 |
| semantic_gap | 1 | 1 |
| failed | 1 | 0 |

What moved: the month-to-date growth question went from a malformed model
answer to a typed refusal (unit repaired, then refused as to-date growth);
the two anti-joins went from 0 rows to a refusal that says why; the
last-week growth per store now covers two weeks and, checked directly
against the database at the owner's suggestion (transactions per store in
the week of 2026-01-19 and the week of 2026-01-26), every growth value
matches: 106 to 97 (-8.5%), 56 to 39 (-30.4%), 77 to 83 (+7.8%), 63 to 70
(+11.1%), 78 to 85 (+9.0%). The first week's rows carry NULL growth, which
the assumption announces.

What did not move, by design: the two 7-day spans compared per salesperson
still compile as daily growth inside the last 7 days (the fix is the
previous-window growth construct, not a guard), and "latest business day"
still means as_of's day. The nine structural refusals stand.

Run 2 tallied (`evidence/pos-real-holdout3-02-tally.json`): 14 of 15, the
one miss being the two-span comparison computed as daily growth (exposed in
the interpretation), 0 silent wrong numbers, refusal rate 80%. The verdicts
were filled by the build side under the owner's delegation: the two answers
were checked in the database (per-store weekly counts; the store's last day
with sales and its gross that day), the refusals are of constructs the
algebra does not have.

## Run 3: the `without` construct (prompt v12)

Entities with no activity became a plan field: `without` names the child
table whose rows must be absent, with its own filters and window, compiled
as a correlated `NOT EXISTS` (`../knowledge/tier0-contract.md`). Prompt v12
teaches the shape and forbids `having count = 0` for it. Rerun the same
evening, same overlay and `as_of`.

| Status | Run 2 | Run 3 |
|---|---|---|
| answered | 3 | 6 |
| unsupported | 11 | 8 |
| semantic_gap | 1 | 1 |

The three anti-join questions answer. Checked directly in the database:
stores with no non-return sale this month to date, 0 (the plan said 0);
salespeople with no non-return sale in the 30 days before as_of, 3 of 25
(the plan listed 3). Products never sold came back as 0 rows: the plan
tested for any `pos_saleitem` row, and the returns default did not apply
inside the test because the returns segment sits on `pos_sale`, the child's
parent; the database has 129 products whose only line items are on returns.
The absence test now joins the segment's table and applies the default
inside, as a plan over the child would (`73e98f8`); run 4 measures it.
Tally 13 of 15 (`evidence/pos-real-holdout3-03-tally.json`): the two
exposed misses are the two-span growth computed as daily growth and the
never-sold products before the fix; 0 silent wrong numbers; refusal rate
60%, down from 80%.

## Run 4: the default inside the test

With the returns default applied inside the absence test, products never
sold come back as 129, the number the database gives for products whose
line items are all on returns or absent; the assumption names the rule and
the word that lifts it. Stores and salespeople unchanged (0, 3). Tally 14 of
15 (`evidence/pos-real-holdout3-04-tally.json`): the one exposed miss is the
two-span growth, which waits for the previous-window growth construct.
Refusal rate 60%, all nine refusals structural (latest row, time parts,
rolling averages, to-date growth).

## Runs 5 and 6: the latest row per entity and the latest period with data

Prompt v13 adds two shapes (`../knowledge/tier0-contract.md`): `latest`
(the most recent base row per group, `ROW_NUMBER` over the dimensions, the
primary key as the default tie-breaker) and the time scope `latest` (the
most recent unit that has rows after the filters, resolved in SQL against
the data instead of `as_of`).

Run 5 exposed a cost of the new prompt before its benefit: the model wrote
the `latest` fields in three shapes the per-section repairs did not reach
(a sibling `table` beside a string column inside `order_by`, a qualified
column inside a `take` reference, a qualified column inside
`without.time.column`), and both latest-row questions plus one anti-join
failed as malformed output. Worse, on the fixture sets the model started
writing ordinary dimensions the way `order_by` items are written
(`{"column": <ref>, "table": t}`), and grouped questions failed across
the board. Both are shape, not meaning: the reference repairs now walk the
whole plan (`e3eafbf`) and unwrap such a dimension (`fef2698`); the fixture
sets were rerun.

Run 6, same prompt, with the repairs:

| Status | Run 4 | Run 6 |
|---|---|---|
| answered | 6 | 8 |
| unsupported | 8 | 6 |
| semantic_gap | 1 | 1 |

The two latest-row questions answer and were checked by running their SQL
directly against the database next to a `DISTINCT ON` reference with the
same ordering: 25 of 25 salespeople and 591 of 591 products identical.
The latest business day is now the day of the store's maximum `sale_date`
(190,852, unchanged) rather than as_of's day. The anti-joins are unchanged
(129, 0, 3). Tally 14 of 15 (`evidence/pos-real-holdout3-06-tally.json`):
the one exposed miss is still the two-span growth, which this run read as
calendar weeks; 0 silent wrong numbers; refusal rate 47% (from 80% on run
2), every remaining refusal structural: time parts, rolling averages,
to-date growth.

