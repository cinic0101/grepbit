# First run of the owner's 50 real questions (2026-09-09)

## Setup

- Database: the owner's real POS schema copied with test data
  (`t2s_8c2b8bbc_6d072f83`, 9 tables). Questions:
  `evals/cases/tier0/pos_real_holdout.yaml`, written by the owner without
  looking at the system. The owner pasted them into the build conversation,
  so the build side saw them before the run; no code, prompt or language
  pack changed between receipt and the run (commits `c695b6d` to `fa1082f`).
- Runner: judged mode, `--enum-distinct-limit 0` (no row value reaches the
  model), `--redact-rows`, both gates on, no overlay, prompt
  `plan-classify-json-v5`, `gemma-4-31b`, sequential. `as_of`
  2026-02-04 18:00 Asia/Taipei, the last day with data.
- Judge: the owner, verdicts given in chat; the build side mapped them onto
  the verdict vocabulary and split wrong answers into exposed and silent from
  the interpretation lines. Files: `evidence/spike-tier0/pos-real-holdout-01.json`
  (report, no rows), `-verdicts.yaml`, `-tally.json`.

## The four numbers

| Number | Value |
|---|---|
| Correctness over 50 judged | 39/50 = 78% (24 answered correctly, 15 refusals the owner accepted) |
| Wrong numbers without an exposed assumption | 4 (q07, q14, q16, q20; q16 and q20 disputed, see below) |
| Wrong numbers with the reading exposed in the interpretation | 7 (q06, q22, q23, q24, q27, q31, q32) |
| Clarify rate / refusal rate | 0% / 30% (9 `semantic_gap`, 6 shape gate) |
| P50 / P95 | 3.6 s / 4.7 s |

Zero model failures, zero literal checks fired (no question carried a value).

## Failure classes

| Class | Cases | What happened | Deterministic fix available |
|---|---|---|---|
| Planner invents a time window | q22, q23, q24 ("每天" read as today), q27 ("各月份" read as one month a year ago, 0 rows) | the algebra allows a window the question did not ask for | an empty result on an invented window can be flagged; the reading itself is a prompt matter (a grain without a window is legal) |
| `length` written in days for unit week | q31, q32 (7 weeks instead of 1) | the window runs 6 weeks past `as_of` | compile-time check: a past relative window must not reach beyond the current unit |
| Whole unit for "to date" | q33 (right only because no future rows) | the algebra has no month-to-date | add a to-date variant of relative scopes |
| Wrong table for a concept | q06 (訂單狀態 from `transfer_status`), while q05 refused the same concept | the model was inconsistent on an absent concept | overlay absent concept (zero-call refusal) or the vocabulary gate |
| Returns not excluded | q14 (min picks a return); q37 to q39 accepted with the same caveat | no business definition of a sale versus a return | overlay: a return is `pos_sale.origin_transaction_no` not null; default scope or metric filters |
| Ratios | q10, q17, q21, q34, q41, q50 (shape gate), q49 (退貨率, refused by the model), q13 and q24 (客單價, right only because the base table has one row per transaction) | not in the algebra | derived-metric shapes: share of total and ratio of two aggregates |
| Templates without values | q29, q44 | refused; the owner will rewrite them with a store and a product name | none needed |
| Ordering | q16, q20 marked wrong by the owner | both plans order by the measure desc then by name asc; `LIMIT %(limit_0)s` is a bound parameter (1 and 3) | to recheck with the owner |

## What this run does not show

- Value grounding: none of the 50 questions names a store, product or
  salesperson, so the effect of sampling off and the literal check is not
  measured here. The owner's rewritten q29 and q44 are the first such cases.
- Generalization: the questions were seen by the build side before the run.
  The 50 become the first regression batch on the real schema; the next
  batch (with values) is the holdout.
