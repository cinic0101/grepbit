# Combining prompt improvements does not make their benefits additive

2026-09-15, baseline `bbf4ef9`. **Do not promote the combined prompt.** It ties
the time-only arm in correct-answer count but loses different cases, including
a repeated exact-time failure. The experiment also exposes a separate,
deterministic timestamp/session-timezone dependency in the execution harness.

[Protocol and authority](../plan/planner-combination-study.md);
[durable evidence](../../evidence/planner-combination-study-01.json).
Raw replies, request hashes, plans and results remain under
`.artifacts/planner-combination-20260915/`. No production changes.

## The experiment isolates two frozen factors

All four arms share **research joint-v1** (not production v15), the same v16
research row wire, schema, overlay, gates, compiler and request lifecycle.
The factors are the unmodified timestamp-filter guidance from the preceding
study and unmodified without-population composition paragraph. No router, new
examples, phrase exceptions, extra definitions or repair guard are introduced.
The new revisions are `joint-factor-time-v1`, `joint-factor-composition-v1`
and `joint-factor-combined-v1`; baseline messages equal joint-v1 byte-for-byte.
Thus this does not repeat the prior time-v15 experiment on an identical prompt.

The ID-deduplicated union of three existing panels has 55 authored/seen cases:
30 aggregate, 13 row and 12 necessary-decline controls. Duplicate contracts
must agree, rather than being silently overwritten. Arm order rotates per case;
calls are serial, Gemma 4 31B, T=0, thinking off, 30-second request control.
Actual shared `ask()` results are checked against independently executed readonly
PostgreSQL SQL. Temporal answers must also match isolated boundary witnesses,
including both previously repaired Service endpoint instances. Expected values
and SQL never reach the model. No real-user blind holdout or all-product-suite
claim is made. Historical scores and evaluation acceptance policy are unchanged.

## Main panel: do not collapse refusals into answer success

| Outcome / 55 | Joint baseline | Time only | Composition only | Combined |
|---|---:|---:|---:|---:|
| Correct answer | 32 | 36 | 33 | 36 |
| Wrong answer | 4 | 3 | 6 | 3 |
| Necessary refusal | 12 | 12 | 11 | 12 |
| Unnecessary refusal | 4 | 3 | 2 | 3 |
| Invalid output | 3 | 1 | 3 | 1 |
| Actual model calls | 63 | 56 | 63 | 58 |
| Repair calls | 8 | 1 | 8 | 3 |

Every arm answers 12/13 row cases correctly. The remaining row case and an
aggregate count control use English `Return`; both hit `concept_not_mapped` in
all arms. Prompt composition does not solve that existing gate false-positive.
Time-only and combined each answer 24/30 aggregate cases correctly; composition
answers 21 and baseline 20. Composition also answers a missing-lease-definition
question with SUM(monthly_fee) over **all** devices, an unsupported business scope.

Answer coverage is 36/55 for baseline and 39/55 for each other arm. Effective
correct-answer rate is respectively 32/55, 36/55, 33/55, 36/55. Known wrong-answer
fractions among answered are 4/36, 3/39, 6/39, 3/39; no unjudged/truncated answers
in this panel. These are sample proportions, not product confidence bounds.
Observed end-to-end p50 is approximately 2.24–2.26 seconds across arms; p95 ranges
6.21–7.44 seconds. An offline gate overlapped the early run, and endpoint workload
is uncontrolled, so these are descriptive costs, not latency guarantees.

### Equal totals hide incompatible case-level effects

- Combined rescues precise-time without where time-only is invalid, and retains
  inclusive date BETWEEN where time-only selects the wrong endpoint.
- Time-only answers the exact-noon English case, but combined repairs it into
  the wrong interval. Combined also newly refuses supported Chinese three-hop
  team absence while time-only answers it.
- Composition-only adds the missing-lease wrong answer and a wrong Service
  time interval; its prior local success is not sufficient promotion evidence.
- Japanese multi-hop absence is unsuccessful in every arm, with different
  refusal versus malformed-plan paths. Do not relabel those as necessary refusals.

These are empirical prompt-context interactions, not proof of an attention,
batching, ordering or token-length mechanism. No further tuning occurred.

## Fresh-process repeat, specified before the main results

Four cases, all four arms: Chinese absence SUM, Japanese multi-hop absence,
precise noon, and missing MTTR. All main outcomes recur: every arm answers SUM
and refuses MTTR; no arm succeeds on the Japanese case; only time-only answers
precise noon correctly. Baseline/composition/combined again produce wrong time
answers. Initial request message hashes are retained for identity verification.
These 21 additional calls are repeats, not new independent questions.

### Post-hoc recurrence diagnostics, kept separate

Four cases were selected after their main-run outcomes were known, before the
follow-up calls: lease amount, leased-row negative control, English absence SUM,
and Chinese three-hop absence. Sixteen calls, no new prompt or fixture changes.
Composition again answers the lease-amount question without a lease binding;
all arms still correctly refuse leased-row listing. Baseline's English SUM
refusal disappears. Combined's Chinese multi-hop refusal also disappears, while
baseline now refuses that question. The relevant initial messages are identical
between main and follow-up. This supports recurrence of the lease failure and
variation in the absence cases, not causal attribution to endpoint batching.
The original wrong answers/refusals remain recorded even when they do not recur.

Total **277/320 actual model calls**: main 240 (220 initial + 20 repairs),
predeclared repeat 21 (16 + five), post-hoc follow-up 16 (no repairs). No transport
failures or unjudged answers were reported. No budget increase or extra model
family was needed. All 32 initial repeat/follow-up requests match their own
main-run message hashes.

## Separate root cause: naive timestamp filters inherit session timezone

Time-only's Chinese/Japanese noon cases produce a valid first plan with
`gte "2026-07-01 00:00:00"`, `lt "2026-07-08 12:00:00"`: clock time survives,
but no offset is supplied. PostgreSQL values fail while the DuckDB witness
(configured in Asia/Taipei) passes. The original assessment correctly requires
both, so it never credits this as a correct answer.

Code inspection: `_bind_type` accepts `datetime.fromisoformat` without requiring
tzinfo, then gives timestamp filters a `timestamptz` cast. An independent readonly
replay of the **same actual plan** establishes the consequence:

| PostgreSQL transaction timezone | Actual naive plan | Manual +08:00 contrast |
|---|---|---|
| UTC | Wrong: includes an extra July 8 alert | Reference match |
| Asia/Taipei | Reference match | Reference match |

The manual contrast is diagnostic, not a model success or an automatic rewrite.
Only SET LOCAL inside isolated read-only connections was used; no stored DB
configuration changed. No new model call was required. This is evidence of
session-dependent interpretation, not a transport or random model failure.
The previous temporal guard covers invalid range repairs, so a first-pass-valid
naive filter is outside its explicit scope. Do not quietly broaden its guarantee.

## Validation and next order

36 focused tests, static pass, **2,064 offline tests with zero skips**. Six new
rulers verify exact passage/revision isolation, byte-identical baseline, panel
deduplication and counts, and invalid-arm rejection. These are meaningful static
research assertions, not claimed red production-behavior tests. No source edits
during live phases; source fingerprints accompany every run. Runtime, API,
identity bindings, security, persistent data and Web defaults remain unchanged.
Pilot-validation discipline matters: typed PostgreSQL plus separate boundary
witnesses prevented session-dependent timestamps from being credited as success.

Recommended next order:

1. Address **timestamp interpretation at the compiler/typed-value boundary** with
   rulers first: offset-aware versus naive inputs, actual timestamp column types,
   business timezone, DST ambiguity/nonexistent times, and plan/operand/without
   scopes. Decide a documented naive-input policy (business-zone default with
   disclosure, or explicit refusal); never let DB session timezone choose it.
   Keep that work separate from prompt tuning and from date-only BETWEEN policy.
2. Retain time guidance as a candidate and the narrow repair-preservation guard
   as a separately measurable safety mechanism. Do not concatenate composition
   globally or add a question-keyword router on the basis of these small results.
3. After deterministic boundary repair, replay stored plans, then rerun paired
   temporal and missing-definition controls before wider acceptance. Keep Return
   gate and Japanese unsupported-shape selection separate. Unseen user questions
   are still needed before any generalization or default-promotion claim.
