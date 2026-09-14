# Base-row integration: computation ready, automatic selection not ready

2026-09-14. **No Web/default promotion.** Default datasource registrations remain
unchanged. The shared compiler and opt-in planner experiment are retained for
bounded follow-up; this is not a released listing capability.

Scope/authority: [base-row-pilot](../plan/base-row-pilot.md).
Durable outcomes and hashes: [base-row-pilot-01.json](../../evidence/base-row-pilot-01.json).
Private/synthetic details: `.artifacts/base-row-pilot-20260914/`.

## What was integrated

`QueryPlan.rows` supports visible base-table projection, typed base filters,
stable primary-key ordering, explicit LIMIT and honest truncation. The normal
ask path retains grounding/recompile, segments, SQL policy, verification and
per-request cancellation. No model SQL, row exposure to the model, arbitrary
formula, joins of independent aggregates or separate execution service.
Research rows delegate to this compiler, removing the duplicate SQL builder.
The experimental wrapper now permits two explicit sort keys instead of three;
production's existing sort limit is unchanged. Old study evidence stays historical.

Default `allow_rows=false` is enforced by planner and compiler. The opt-in
strategy is `plan-v15-rows-fallback-v1`: unchanged v15 first; only explicit
unsupported can invoke v16 once. Existing plans, semantic_gap and ambiguous
responses are retained. Only a row plan can be promoted from the second stage;
an aggregate proposal retains the old refusal. Additional stages are disclosed
through `model_row_fallbacks`; repair turns remain separate.

## Controlled live observations

Gemma 4 31B, temperature 0, thinking off, serial shared endpoint. Synthetic
IoT/Service only, read-only grepbit_ro, enum sampling 0, no DB mutation. First
phase: **171/180 actual calls**, including 11 interrupted calls with no scored
report. Separate fallback phase: **80/96 actual calls**. No live MCP/Web calls:
promotion condition failed, so the reserved serving smoke was not run.

### New listing panel

11 answerable base-row cases plus one joined-detail negative outside this pilot.
Complete typed ordered SQL replay checks actual model plans, not injected gold.

| Strategy | Full matching answers / 11 | Joined-detail negative |
|---|---:|---|
| Direct v16 row prompt | 11/11 | Correct unsupported |
| v15 then unsupported-only row fallback | 6/11 | Incorrect aggregate answer |

Fallback submits five genuine row plans: the original device-detail request
and all four Service listings. The sixth match is the existing aggregate plan
for top device fees. Five other IoT listings bypass fallback with aggregate
plans and fail full columns/values comparison. The joined-detail negative also
bypasses fallback. Retaining v15 behavior does not make those proposals correct.
These are new diagnostic observations, not newly introduced fallback regressions.

The first trial found qualified row order fields were not normalized against
row outputs. A failing ruler pinned the omission; the existing unambiguous
output-name normalization now covers explicit and all-column row projections.
No word-list repair or question-specific instruction was added.

### Old paired controls (legacy pass, including accepted refusals)

| Set | v15 baseline | Direct v16 | Fallback |
|---|---:|---:|---:|
| IoT (20) | 19 | 20 | 19 |
| Service (24) | 24 | 23 | 24 |
| IoT coverage (8) | 8 | 6 | 8 |
| Service adversarial (12) | 10 | 9 | 10 |

All 64 fallback case statuses/reasons/pass outcomes match the baseline in this
run; this is not a guarantee about future endpoint responses. Direct v16 turns
`cov_mttr` and `cov_leased_fee` from correct semantic_gap into unjustified
answers. It also breaks the old successful `svc_tickets_without_logs` query
by proposing excluded rows+without, and loses `svc_absent_sum_ja`.
The IoT improvement cannot offset these failures.

The proposed rows+without expansion was stopped before implementation after
the broader semantic regressions appeared. Its initial red artifact is retained;
the exclusion remains in the current contract. Extending the algebra would not
fix the two missing-definition answers.

## Evaluation and validation boundaries

The legacy artifact serializer turns NULL/Decimal/datetime into strings. Extra
`strict_ordered_values` flags in the first fixed reports were therefore invalid
as a typed oracle; those artifacts are preserved, not rewritten. Separate
read-only replay confirms the direct arm's 11 exact ordered results and public
NULL preservation; fallback replay compares every answer, including failures.
Historical scoring rules were not changed to make this pilot pass.

Initial ruler: 10 intended failures, two controls passed. Final broad static
gate passed; offline gate **1,998 tests passed**, zero skips. Four additional
malformed-projection adversarial cases subsequently passed in a **49-test
focused run**; no production source changed after the broad gate/live freeze.
The tests cover visibility, hidden PK, NULL/duplicates, ten generated instances,
segments, grounding, bound LIMIT, output lineage, stop-before-execute and
between-planner-stage cancellation. This is not full row-algebra differential
closure or live Web lifecycle validation.

All panels are synthetic/authored/seen. No generalization rate, latency causal
claim, intent certification or new PII authorization follows from these results.

## Decision and next discriminating experiment

Keep the feature opt-in and the Web registry unchanged. SQL projection and
shared serving safeguards are usable building blocks, but neither tested
selection policy meets both coverage and semantic-risk requirements.

Next isolate **query-kind selection** from **construction**, without treating
either as an intent certificate. Reuse these existing row and v15 outputs to
audit the ceiling of researcher-selected dispatch; this is a diagnostic, not
a product score, and needs no more model calls. The earlier query-extension
study already tested researcher-supplied operator restriction and got 2/8;
do not rebrand or repeat that prompt experiment. The distinct untested proposal
is dispatch BEFORE planning: preserve v15 construction for aggregate requests
and use the row branch only for requests selected as listings. Any automatic
selector must then be tested on held-out neighboring families, including the
missing-definition negatives; measure wrong-kind rate, final values and extra
call cost jointly. A correct routing label does not prove downstream scope.
No lexical routing or new framework is justified yet. Do not combine this
experiment with conversion or independent aggregate integration; those research
implementations remain separate.
