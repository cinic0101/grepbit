# Plan stability: three passes at an idle endpoint, three concurrent ones under load (2026-09-11)

## Setting

Phase 1 of the root-cause program. Three flapping cases had accumulated
during the day (`ft_compare_last_two_months` right and wrong on alternate
runs, `returns_dec_gap` answering the wrong concept twice, holdout 3 q03
read three ways in three runs), and the program's Best-of-N item depended
on knowing how often the same question gives a different plan.
`evals/stability.py` compares repeated runs of a case set by plan core (the
plan without aliases, lists in canonical order), so a renamed column is not
instability but a changed filter, dimension or window is.

## Three sequential passes, 20:01 to 21:04

Every set ran three times in a row under `5508af0` (prompt v14, overlay
v12, gemma-4-31b, concept check on), one process at a time on an otherwise
idle endpoint.

| Set | Cases | Plan stability | Result on each pass |
|---|---|---|---|
| 13 fixture and real sets | 268 | 1.0 on every set | identical: pos 26/26, nosample 25/26, multilingual 31/32, overlay 14/14, having 6/6, coverage 8/8, 7/8, 8/8, features 38/39, iot 19/20, retail 12/12, batch 1 50/50, smoke 7/7 |
| holdout 2 | 30 | 1.0 | 30/30 |
| ratio set | 12 | 1.0 | 12/12 |
| holdout 3 | 15 | 1.0 | 13/15 (q03 the daily misread, q12 refused: the absence window written offset 0 length 30, fixed after) |

313 cases, 939 calls, three identical plan cores each, 0 transport
failures. p50 stayed at 4 to 5 s.

## Three concurrent passes, 21:05 to 21:08

The features set (39) ran three times at once on the same endpoint.

| | Result |
|---|---|
| the three concurrent runs against each other | plan stability 1.0, all 38/39 |
| the three against the idle pass an hour earlier | 0.974: one case (`ft_non_member`) changed base table and measure between the idle pass and the concurrent ones, both times answering the same reference correctly |
| latency | p50 4.6 s, p95 6.5 s: no inflation from three concurrent requests |

## Reading

The variance is not per call. Identical requests sent together, or one after
another in a quiet minute, produce the same plan; the plan changes between
sessions, when the endpoint's load and batch composition differ. That
matches the batch-invariance account of temperature-0 nondeterminism
(Thinking Machines, 2025) and explains the day: `ft_compare_last_two_months`
flips between morning and afternoon runs but not within either;
`alerts_trend_daily_july_first_week` was right in the afternoon and wrong,
stably, all evening (range end 07-09 instead of 07-08).

Two consequences for the program:

1. **Best-of-N by repeating the call is useless here.** Three calls made at
   the same moment agree with each other and with nothing else. Diversity
   would need temperature above zero, which trades a known variance for a
   larger unknown one. Item A6 is closed as "measure, do not build";
   `plan_stability` stays a standing metric, measured as three sequential
   passes.
2. **Flapping cases are pinned, not voted on.** A question whose plan changes
   between sessions is a question the prompt and the overlay leave
   under-determined; the fix is a pinned reading (an overlay metric or
   absent concept, a rule with a test) or an accepted variance stated in
   the case. The three known ones: `ft_compare_last_two_months` (two months
   compared: growth over a widened window against per-period values),
   `alerts_trend_daily_july_first_week` (the first week's end), holdout 3
   q03 (two 7-day spans: a construct the algebra lacks, so a refusal is the
   pinned outcome).

The concept check of phase 0 fired four times in 939 calls, all intended
(`returns_dec_gap` in Chinese and Japanese, `cov_discounted_sales`) and
never on a real question; `returns_dec_gap` no longer answers the wrong
concept.
