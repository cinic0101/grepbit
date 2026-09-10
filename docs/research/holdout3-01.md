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
