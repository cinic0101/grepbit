# Wider joint-planning regression and row-order repair

2026-09-15, baseline `e5c2c2c`. **Keep joint planning as a research candidate;
do not enable it or rows in Web defaults. Retain the independently validated
row-order repair.** No router, gate exception, or new business dictionary.

Scope/authority: [work record](../plan/joint-regression-and-row-order.md).
Durable manifest: [evidence](../../evidence/joint-regression-and-row-order-01.json).
Detailed fresh artifacts: `.artifacts/joint-regression-20260915/`.

## Paired regression: not a single success percentage

Unchanged v15 versus `query-kind-joint-v1`, before the row repair. All 64 existing
IoT (20), Service (24), coverage IoT (8) and Service adversarial (12) cases.
Group arm order alternates; calls remain serial on Gemma 4 31B, T=0, thinking off.
Synthetic readonly PostgreSQL, enum sampling zero, Service reviewed overlay,
original as_of per case set. No SQL, result rows or reference answers enter the
model. These are previously seen authored controls, not unseen user holdout.

| Historical grading | v15 | Joint v1 |
|---|---:|---:|
| IoT | 20/20 | 19/20 |
| Service | 24/24 | 24/24 |
| Missing-definition IoT | 8/8 | 8/8 |
| Service adversarial | 10/12 | 9/12 |
| Reference-matched answers | 47 | 45 |
| Answer/reference mismatch | 0 | 1 |
| Necessary refusals | 14 | 14 |
| Unnecessary refusals | 2 | 3 |
| Accepted status-only answer, not value-judged | 1 | 1 |

Thus historical totals are 62/64 and 60/64, **not** answer accuracy. The status-
only item is `ambiguous_temperature`. The runner's `false_answers_on_refusal_cases`
counter also includes that accepted answer: it is not evidence of a proven wrong
answer. We retain the raw report and explicitly separate these categories.

Paired phase consumed 125 actual calls, including repairs. This established spike
runner uses shared ask but no total RequestControl deadline; the subsequent
follow-up does use a 30-second total deadline. Do not pool latency or claim that
this run revalidates transport, cancellation or Web E2E behavior.

### Two differences have different explanations

1. **Real regression, reproduced:** `svc_absent_sum_zh`, total estimated minutes
   of tickets with no event records. Joint refuses `unsupported` in the paired
   run and fresh follow-up; v15 returns the correct SUM + without in both.
   The algebra and database can answer it. This is a planner capability-selection
   false refusal, not a missing definition or a compiler inability. The exact
   instruction interaction is not established; do not attribute it to batching.
2. **Historical oracle conflicts with the accepted date policy:**
   `alerts_trend_daily_july_first_week` actually asks "between 2026-07-01 and
   2026-07-08", not "first week". The historical SQL excludes July 8; joint
   includes July 8 and discloses the half-open interval ending July 9. Existing
   [accepted policy](../plan/answer-acceptance-and-cause-studies.md) requires both
   date-only endpoints. Independent typed PostgreSQL replay confirms joint's four
   rows match that policy; v15's three do not. Both model interpretations recur
   in follow-up. Neither old fixture nor old scores were overwritten. This is
   an acceptance-oracle reconciliation task, not evidence of a joint date bug.

Common residuals also recur: Japanese no-February-worklogs is unnecessarily
refused by both arms; English dual row/entity counts produce correct plans but
are blocked by the `Return` concept gate. These do not disappear by selecting
the joint strategy.

## Independent repair: unprojected row sort key

Six intended red rulers and four passing controls preceded implementation.
The opt-in row contract now accepts explicit ordering by any **visible column
of the same base table**, even if it is not projected. SQL qualifies the order
reference; the output stays unchanged, duplicates/NULL remain, NULLs sort last,
PK ties and parameterized LIMIT remain. Semantic refs and existing actual-order
disclosure include the key. Unknown/hidden/foreign references refuse. Aggregate
ordering is still output-only; authorization and default opt-in are unchanged.

The compiler revision is `plan-compiler-rows-v2`; optional row-stage prompt is
`plan-classify-json-v17-row-order`. Runtime v15-first/unsupported-only fallback
strategy is unchanged. The historical study explicitly pins v16 messages, and
reconstructing baseline e5c2c2c confirms exact complete-message equality on both
source contexts. Compiler fingerprints distinguish the new execution semantics.

Evidence separates three claims:

- Thirteen row-order tests cover asc/desc, tied/NULL sort keys, projection,
  visibility, qualifier identity, aggregate restrictions, prompt versions and
  mutated SQL order-column/direction/NULL-placement/table detection. SQL self-
  check validates the requested order prefix; it does not independently prove
  the entire PK tie list (schema-based compiler/oracle tests cover that).
- The original captured `kind_minutes_records` first model response now validates
  and executes **without deleting its explicit id order**. Independent PostgreSQL
  reference matches all ten typed ordered rows and projection.
- Live original Return phrasing now gets past shape validation but still reaches
  `concept_not_mapped`. Two separate v17 direct-builder controls using "List"
  match PostgreSQL: minutes-only ordered by id, and minutes descending/id ascending
  with LIMIT 4. This verifies computation, not a general fix for Return intent.

## Conservative fallback is still not a solution to planning classification

Re-measured v17 fallback on all 11 existing row-positive cases and 12 refusal
controls: **7 correct row answers, 4 wrong aggregate answers; 11 necessary
refusals, 1 wrong aggregate answer**, 31 model calls. The wrong cases retain v15
COUNT plans rather than reaching the new row prompt: offline devices, Japanese
firmware listing, all sites, zero-minute logs, and joined detail projection.
The last is the refusal control. No post-hoc gate or output projection rescues
these results. Differences from older counts are observations, not a controlled
claim that changing only the v17 sentence improved model accuracy.

This reinforces the original architectural diagnosis: unsupported-only fallback
misses listings misclassified as valid aggregates. Single-call joint selection
is still promising from the earlier 32-question comparison, but its reproduced
without false refusal prevents default adoption. A separate router has not earned
its extra call in the earlier matched comparison; this run did not remeasure it.

## Gate evidence: keep the known collision, do not repeat a rejected relaxation

Two deterministic sentinels retain the collision between output-command Return
and genuine product-returns scope, including a sentence containing both. Same
plan/source and triggered concept ID are not enough to distinguish those roles.
These are fixed-pair harness tests, not model-accuracy evidence.

[Source-scoped gate research](source-scoped-gate-01.md) already showed that
relaxing absent-concept gating restores false refusals but also releases genuine
scope omissions. No new language exception, source allowlist, gate disablement,
or same-model semantic certification was added here.

## Validation, decision and next step

Static passes; full offline **2,028 tests, zero skips**. No production source
changed while a live regression ran. Paired phase 125 calls + follow-up 42 =
**167/180 actual calls**. All SQL was readonly against synthetic IoT/Service;
no customer data, DB mutation, new datasource or deployment. Web defaults,
MCP response format, security/identity boundaries and historical evaluation
definitions are unchanged. Public row-plan sort capability widens only behind
the existing opt-in flag; actual-order disclosure uses existing fields.

Next proposed bounded slice:

1. Reconcile the prospective date oracle with the already-approved inclusive
   date-only policy, retaining the historical result alongside it.
2. Diagnose the joint `without` false refusal using a small cross-language,
   SUM/COUNT and ordinary-row-selection contrast panel. Change at most one
   generic capability instruction per arm; retain missing-definition and wrong-
   aggregate controls. No source-specific phrase exception or second router yet.
3. Require the candidate to retain row value matches **and** stop regressing
   supported aggregate/without requests before an explicit fixture-only Web
   promotion decision. Keep the Return gate problem separate; a better planner
   does not resolve an independent gate false positive.

The pilot-validation discipline keeps SQL feasibility, model selection, necessary
refusal and actual product readiness as separate claims. No human correction
card or new routing framework was introduced.
