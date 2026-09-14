# Retained-question gate exposure: narrow evidence, no blanket replacement

2026-09-14, complete from `cad9dd3`. Protocol:
`../plan/gate-exposure-audit.md`. No production changes, new Gemma calls or DB
access. This is a retrospective corpus audit, not a new live accuracy run.

## Decision

Do not expand absent-concept vocabulary or disable the concept gate globally.
The 95 retained owner questions show three historically accepted absence
refusals, but no recorded concept-gate refusal. The separate authored baseline
contains a confirmed English false refusal as well as historically accepted
concept refusals. It does not justify replacing a gate based only on one side
of that tradeoff, nor establish a product-wide error rate.

Stop repeated prompt/lexical experiments on these known cases. Keep the proved
wrong-answer and false-refusal sentinels. Next useful evidence is unseen owner
questions outside the mainly POS/Chinese population, especially unit selection,
components/populations, and concept words used as instructions or exclusions.
Synthetic adversarial tests remain useful but cannot substitute for that sample.
No new semantic certifier, public input format or human correction card is added.

## Primary population and actual observations

Exactly the same selected sources as name-prevalence-01, with current file hashes,
case/question identity joins and verdict/report/status binding:

| Owner set | Cases | Historical artifact | Prompt |
|---|---:|---|---|
| Batch1 | 50 | product-baseline-20260913/live/batch1.json | v15 |
| Holdout2 | 30 | holdout2/run-26.json, verdicts-26.yaml | v14 |
| Holdout3 | 15 | holdout3/run-13.json, verdicts-13.yaml | v14 |

Paths are relative to `.artifacts/`. All 95 question/datasource identities are
distinct under exact hashing. Historical evidence remains: 47 reference-matched
answers, 33 judged-correct answers, one judged-wrong answer and 14 accepted
refusals. These are seen owner tests, not a representative traffic sample or
fresh independent value judgments. Historical ratio-oracle limitations remain.

- **Observed absence refusals: three**, Batch1 q04–q06. All were accepted by the
  old evaluation. Current overlay predicate also matches these same three and
  no other retained question. There is no saved proposal on these cases, so
  bypassing the gate's counterfactual answer cannot be assessed.
- **Recorded concept-gate refusals: zero.** This is absence of the recorded reason,
  not proof that old instrumentation exposed every internal path.
- **Current concept triggers: eight questions.** Seven available projections
  contain sufficient mapping evidence and would not be rejected by this predicate.
  The eighth is q04, already refused by the pre-planner absence gate; its missing
  plan makes the later concept check unknown, not a potential answered failure.
- **No current-predicate rejection of the retained available plans.** The other
  87 questions do not trigger a concept check. No trigger and a mapped keyword
  are neither correct-intent evidence nor proof that the query's values are right.
- The one historically judged-wrong answer is not flagged by either predicate.
  This records their coverage limit; not every error is in either gate's remit.

No new independently confirmed true/false refusal labels are assigned to the
95 owner cases. In particular, do not turn the three accepted historical refusals
into three newly proven wrong-answer rescues.

## What sanitized plans can actually establish

39 records retain raw plan structures, 47 retain partial sanitized traces, and
nine have no usable plan. The trace retains known columns, metrics, dimensions
and scoped filter columns but omits ratio-operand/latest/without details.
Literal values and aliases are not recovered or printed.

The audit invokes the current predicate using only its relevant references.
For raw plans this is a complete **gate projection**, not a compiler/value replay.
For partial traces it is a conservative lower bound: a known matching reference
proves that this positive-existence predicate is satisfied, because additional
references cannot remove that evidence. A missing match in incomplete evidence
would remain `unknown_partial_trace`, never become a refusal. No such unresolved
partial match occurs in this primary corpus. The one triggered/no-plan case
remains `unknown_no_plan`.

The nine unavailable plans must not be confused with the previous name audit's
filter-availability counters. An empty retained filter list is not a retained
plan. No raw customer question, filter binding or free-text rationale is emitted.

## Separate supplement: 292 historical product-baseline executions

The original manifest and completed-artifact hashes bind all 15 primary sets;
six scheduled repeats are excluded. This is **292 executions**, not 292 distinct
new user questions. Fifty are the same owner Batch1 cases above. Keep the other
242 authored executions separate; do not pool the two panels or double-count.

| Cohort | Executions | Recorded absent_concept | Recorded concept_not_mapped |
|---|---:|---:|---:|
| Owner Batch1 overlap | 50 | 3 | 0 |
| Authored sets | 242 | 4 | 4 |

The four authored absence refusals are overlay inventory/installment/overtime/
online controls, all historically accepted. The four concept refusals are:

| Case | Historical evidence | Current conclusion |
|---|---|---|
| returns_dec_gap | Refusal accepted | Not a fresh value-verified rescue |
| ja_returns_dec_gap | Refusal accepted | Same limitation; not a separate proof of generalization |
| cov_discounted_sales | Refusal accepted | Not a fresh proof of missing-scope understanding |
| svc_units_en | Baseline not accepted | Independently bound historical false refusal |

For `svc_units_en`, the original full plan hash is
`9737cdd17fe1373e66b0c299a7c37397d77016cb1c26daa05a46d6a5441cfd4c`.
It matches the earlier retained raw plan and the hash-bound
failure-roots-01 artifact's PostgreSQL reference check. That plan counts work
log records and distinct ticket IDs correctly. Replaying the current predicate
on exactly that plan flags `returns`; removing only the output instruction
`Return both totals.` clears it. This confirms the same previously established
false refusal, not a new live result or another independent occurrence.

The old value evidence is reused by identity and file hash, not rerun against a
current DB. No other historical accepted refusal is promoted to a confirmed
useful catch. A ratio/count/component error may retain every required concept
keyword, as controlled-refusal-01 demonstrated; this audit does not change that.

## Validation and boundaries

- Nineteen private driver tests pass: full gate projection across plan/measure/
  ratio/dimension/latest/without scopes, partial-evidence asymmetry, unavailable
  plans, named segments, identity mismatches, unknown-versus-rejection and privacy.
- Eight integrity tests pass: frozen source/input hashes, exact population and
  overlap, complete schedule, historical evidence joins and no raw payload output.
- Fresh static passes. The unchanged source/hash-matched 1,841-test offline gate
  is reused, not rerun. No production/evaluation-code changes or dependencies.
- Zero new model or DB calls; no credential files accessed. Historical data stay
  in memory; new artifacts contain safe IDs, fixed labels, counts and hashes.
- No population confidence interval, causal model-improvement claim or new
  acceptance grade. Current overlay/pack replay and historical observations are
  explicitly distinct. Historical artifacts and scores remain unchanged.

Evidence: `../../evidence/gate-exposure-01.json`,
`.artifacts/gate-exposure-20260914/` and
`.artifacts/gate-exposure-analysis-20260914/`. Tracked changes are only protocol,
report, manifest and roadmap. Production, evaluation contract, external formats,
safety boundaries and identity bindings are unchanged. Local commit; no push.
