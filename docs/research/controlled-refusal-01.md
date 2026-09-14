# Controlled refusals: scope facts are not request intent

2026-09-14, complete from `98ccadc`. Protocol:
`../plan/controlled-refusal-validation.md`. Production prompt v15 / ask v5
unchanged. This is **offline fixed-plan diagnosis and historical replay**, not
a new model-success measurement. No new Gemma calls or production changes.

## Decision

Neither tested configuration qualifies for live promotion. Existing reviewed
`absent_concepts` catches missing-scope answers but also blocks questions that
explicitly do not request that scope. Disabling the concept gate restores a
correct answer but releases known-wrong controls. Preserve current production;
do not expand vocabulary, introduce phrase exceptions or call either gate an
intent certificate. Their determinism does not make their language premise true.

## Support facts versus requested scope

36 authored English questions: lease/warranty/insurance × supported/confirmed
absent/unknown mapping × scoped/plain/ignore/quoted. Thirty are answerable;
six genuinely require unavailable support. Facts, questions and expected intent
were frozen separately. Both arms receive identical complete reviewed schema
comments. Only the confirmed-absent state receives the candidate declaration.
Correct plans are injected on answerable requests; an unrestricted-total foil
is injected on unsupported requests. These are controlled inputs, not claims
that a live planner would always make that omission.

| 36 fixed-plan requests per arm | Correct answer | Necessary refusal | Wrong answer | False refusal |
|---|---:|---:|---:|---:|
| No absence declaration | 21 | 0 | 6 | 9 |
| Existing reviewed absence declaration | 18 | 3 | 3 | 12 |

No unassessed cases or operational failures. The candidate catches all three
confirmed-absent scoped omissions. It does not enforce unknown mappings, which
are deliberately **not** relabeled absent. It newly blocks three explicit-ignore
questions, for example: “Do not distinguish leased devices from other records.
Sum monthly fees across all records.”

The candidate's pre-planner absence rule also blocks three quoted-heading
controls, but those were already blocked by a different baseline gate. Thus:
six answerable cases are rejected by the absence rule itself, but only three
are **incremental** false refusals. Do not double-count the overlapping loss.
All six absence-rule false refusals occur before the fixed planner is called;
no better model response can repair that path.

### Additional discovery: an unrelated member-concept collision

All nine original quoted-heading controls already fail in baseline. Their
explicit unrestricted-total instruction ends with “without a membership
restriction”. The current concept gate maps `membership` to business **member**,
even though the word refers to membership of a set, not customer membership.

Separate post-observation diagnosis, 36 fixed-plan requests:

| Same nine contexts | Concept gate on | Concept gate off |
|---|---:|---:|
| Original membership wording | 9 false refusals | 9 correct answers |
| Replace with “without filtering records” | 9 correct answers | 9 correct answers |

The direct detector reports `(member, membership)` only for the original text.
This isolates the collateral match; it is not a proposed input rewrite, a
generalization result, or nine independent linguistic discoveries. Original
panel grades stay unchanged. The common phrase is repeated across nine contexts.

## Metric, component and denominator diagnosis

16 authored questions: two row/entity counts, six output-verb/business-return
contrasts, six component/population contrasts across payroll/goods/services,
and two all-records/known-status denominators. Each has one allowed gold and
one predefined wrong foil. All 16 foils differ from their gold on the three
nonempty instances; the fourth instance is empty. SQL and hand-checked support/
ratio values provide independent numeric evidence. Same interpretation and full
output must hold across all instances; no per-instance reference shopping.

| 16 requests per cell | Gold correctly answered | Gold falsely refused | Wrong foils blocked | Wrong foils answered |
|---|---:|---:|---:|---:|
| Current concept gate | 15 | 1 | 4 | 12 |
| Gate disabled, diagnostic only | 16 | 0 | 0 | 16 |

The false block is `Return the transaction count.`; the four useful blocks
are actual return requests with the return restriction removed. Missed foils
include row/entity confusion, changing population instead of monetary component,
and wrong denominators that still mention the return concept. Presence of a
column or metric keyword does not establish its computational role or scope.
These foil rates are **not** live model error prevalence or product accuracy.

Three actual old proposals were recovered by exact full-plan SHA-256 under a
bounded recipe/alias search; original question/schema/overlay context matched:

- Chinese `output_zh`: selects reviewed `return_count` instead of total records;
  wrong with either gate setting, independently distinguishable as 2 versus 7.
- English `output_en`: correct total count; falsely refused with the gate,
  answered correctly without it.
- Chinese `rows_zh`: this historical proposal is correct, including its original
  count representation. It is a control, **not** a reproduced unit-selection error.

Captured proposals are replayed, not regenerated. All three compiled outputs
also match PostgreSQL; their labels are not inferred from similarity to a foil.

## Evidence and validation

- Final artifact `result-postgres-v2.json`: 72 support injections, 64 metric
  injections, 36 isolated phrase diagnostics, six exact-capture gate replays:
  **178 ask executions**, zero unassessed/operational failures, zero model calls.
- 316 compiled-gold checks, 64 compiled-foil checks and 12 captured-plan checks
  per engine. PostgreSQL additionally executes 316 independent reference SELECTs:
  **708 synthetic SELECTs**, plus one role check. Counts include repeated contexts
  and recipes, not 708 distinct tests or independent semantic questions. No SQL
  disagreement; this proves fixture arithmetic, not question understanding.
- PostgreSQL uses `grepbit_ro`, READ ONLY transactions and inline synthetic VALUES;
  no stored customer rows read, no persistent DB mutation. ask uses the existing
  DuckDB fixture executor; this is not end-to-end MCP/PostgreSQL-driver validation.
- 17 private driver tests and eight post-observation integrity tests pass. Fresh
  static passes; reuse the unchanged source/hash-matched 1,841-test offline gate,
  not a rerun. The standard focused wrapper rejects private paths outside tests/;
  the private tests therefore use direct pytest with JUnit evidence.
- Initial v1 replay labeling mistakenly treated every captured plan as a foil:
  a correct blocked capture was labeled necessary refusal. Corrected with a
  regression test and independent captured-value checks, rerun to fresh v2.
  Earlier artifacts remain but are superseded; all published counts use v2.
- No raw model text, customer values, DSNs or credentials in the new reports.
  Manifest contains hashes/counts, with private helpers and test artifacts retained
  under `.artifacts/controlled-refusal-20260914/` and the separate analysis folder.

## Next steps and limits

Stop absence-vocabulary expansion and blanket gate removal. The offline screen
failed, so no conditional Gemma stage, broad live regression or A5 promotion is
justified by this slice. Preserve these bidirectional controls for any replacement.

Next measurement should use retained owner questions and exact historical plans
to estimate the actual exposure to these two gates. Separate genuinely wrong
plans blocked, correct plans blocked, unresolved judgments and unrecoverable
captures; use existing independent references before crediting a label. Do not
generalize the deliberately adversarial 16/36-case rates to product traffic, or
spend another model round rediscovering the same known failure. This retrospective
exposure audit is a proposed next slice, not completed here.

Do not build another same-model intent certifier or revive correction cards.
If a caller can supply explicit reviewed metric/scope identifiers, the server can
enforce that binding; it still cannot certify that an upstream model chose the
user's intended binding. Changing the tolerated false-refusal/wrong-answer tradeoff
is a product decision, not a compiler fix. The existing component/count/denominator
witnesses remain useful regardless of that decision.

Tracked scope: protocol, this report, evidence manifest and roadmap. Evaluation
contracts, external formats, safety boundaries, identity bindings and production
configuration are unchanged. Local commit only; no push.
