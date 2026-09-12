# Reuse existing evidence without inventing a product success rate

2026-09-12. Baseline clean dev `d1aee71`. Owner approved the existing-evidence
measurement after retiring calculation cards and human correction. No change
to production, prompts, historical scores, acceptance thresholds or dependencies.
Evidence: `evidence/evidence-reuse-measurement-01.json`. Private scripts/results:
`.artifacts/reuse-measurement-20260912/`. No raw questions, plans, SQL, result
rows, bindings or verdict notes are copied into this report or public evidence.

## Outcome

Existing assets are useful for regression and known failure-family measurement;
they do not establish a current product accuracy or certify intent. We recovered
manifest bindings, separated recorded answer/refusal/unknown outcomes, audited
verdict reuse, and replayed captured fictional proposals on current code.
The current live panel is prepared but was blocked before execution by automatic
review's requirement for specific real POS payload/destination permission.

The first inventory's 33 complete matching verdict files meant coverage/status
consistency, not verified judgment lineage. This audit identifies a material
limitation: identical parameterized SQL and scalar row count can hide changed
bound filters. Neither file completeness nor a copied `correct` label proves
the current interpretation is right.

## Historical strata and one frozen batch

Reused the hash-bound inventory, not a new scan that could accidentally include
this task's outputs. The 166 non-dry runner reports contain 2,027 observations,
including repeats and ablations. All original files/labels remain unchanged.

| Original recorded outcome | Observations, including repeats |
|---|---:|
| Answer accepted with reference match | 446 |
| Answer rejected with reference mismatch | 22 |
| Answer not accepted for another recorded reason | 5 |
| Answer accepted on status only, without reference result | 2 |
| Answer without recorded correctness | 1,048 |
| Refusal accepted | 73 |
| Refusal not accepted | 20 |
| Refusal without recorded correctness | 371 |
| Operational failure | 40 |

These categories use the runner's original status/correct/reference fields.
Separate human-verdict lineage is a second dimension, not automatically merged
into the buckets. A mismatch is reference disagreement, not automatically an
independently proven wrong number. An unjudged row is not a pass or a failure.

Recovered SHA membership for 103 runner reports in four existing manifests:
`a5-service-01`, `grain-retirement-01`, `a5-ratio-followup-01`, and
`a5-forms-service-01`. This binds old artifacts to their study records; it does
not establish equivalence to today's source, model service or data snapshot.
The other reports remain usable at their weaker recorded provenance level.

As a complete, pre-existing batch rather than selected best runs, the 16 initial
`.artifacts/a5-20260912/v15-*.json` reports contain 313 case executions. They are
all bound to `evidence/a5-service-01.json`, whose initial frozen runtime is
`2c4da6d3d9481d30aa9fdc66ba7eea27b6505e1ef9be931e9c5b151d36dd0aa9`.
Do not attribute these to that study's later repaired source or current code.

| Original initial-v15 result | Count |
|---|---:|
| Answer/reference match | 196 |
| Accepted refusal | 52 |
| Status-only accepted answer | 1 |
| Answer/reference mismatch | 4 |
| Other unaccepted answer | 1 |
| Unaccepted refusal | 2 |
| Unjudged answer | 43 |
| Unjudged refusal | 12 |
| Operational failure | 2 |

Thus the old recorded pass count 249 combines 196 reference matches, 52 accepted
refusals and one status-only pass. Seven rows have a recorded negative verdict;
57 lack correctness labels, including the two operational failures. Reporting
249 as successful answers, or dividing it by a convenient subset to claim
product accuracy, would be misleading. The panel contains repeated controls;
used holdouts are now development data. Settled batch-1 references originate
from previously accepted system output, not a new independent intent oracle.

## Verdict carry: a demonstrated identity gap, not a historical rescore

`evals/carry_verdicts.py` fingerprints only `(status, sql, row_count)` and can
erase aliases for a fallback match. It does not compare the plan, bound values,
question, as_of, schema/overlay/source or data identity. The evaluation-method
prose had stated a stronger plan-identity requirement than the implementation.

A minimal fictional counterexample uses two valid count plans with different
bound text filters over three rows. Hand counts and actual compiled SQL on
DuckDB are **2 versus 1**, while parameterized SQL, status and scalar row count
are identical. The existing tool carries `correct` to the changed plan. This
proves the fingerprint is insufficient, without accessing real databases.

Historical audit scope: 827 filled label entries whose target reports are in
the inventory; 575 recognizable carry edges and 252 entries without that carry
marker. No marker is not proof of fresh independent human review.

- 36 carry edges differ under raw canonical plan comparison.
- 15 become identical after validating both plans and materializing domain
  defaults; these are not retained as changed-plan flags.
- 21 still differ: measures on 12, time on seven, filters on two and having on
  one (field counts overlap). Differences can still be semantically equivalent;
  this audit does not decide those cases.
- Propagating unresolved lineage through later copies affects **165 repeated
  label entries**, not 165 unique questions and not 165 proven wrong answers.

For illustration, the latest inventoried holdout2/holdout3/ratio reports contain
12/2/2 labels with unresolved lineage respectively. Remaining labels have no
detected issue under this limited audit; they are not independently certified.
Missing source/data identity, unrecognized note formats, unavailable plans and
other unobserved changes are outside the assurance this audit can provide.

The tool and historical verdict files were not modified. A future repair needs
an explicit, fail-closed reuse identity specification and counterexample tests;
do not silently refresh old labels or use the current carry tool for this panel.

## Current-source local replay

Reused `.artifacts/cross-language-study-20260912/live.json`, checking the frozen
fixture/ruler digest and schema/overlay/as_of bindings before replay. Today's
source is `e01de711`; the captured study source was `10d70429`. Source identity
is recorded separately, not faked to satisfy the old binding.

Executed **216 actual ask workflows**, with **195 SQL executions within those
workflows**, zero provider calls and zero external DB calls. The study analyzer
also performs local grading/witness checks; 195 is not a task-wide SQL total.
Status, reason, verification, gold-result comparison and workflow SQL counts
all match the recorded replay. This is deterministic replay of old proposals,
not evidence that a fresh model call today would produce the same proposals.

The following reports one 12-question instance to avoid tripling the apparent
sample size. All three fictional instances were replayed. Z1/Z2 are the old
Chinese proposal calls; E is the captured translated-English planning call.

| Gate mode / captured arm | Answered | Clarify | Answer matches gold | Answer mismatches gold | Answer has no gold |
|---|---:|---:|---:|---:|---:|
| Current / Z1 | 11 | 1 | 8 | 2 | 1 |
| Current / Z2 | 11 | 1 | 8 | 2 | 1 |
| Current / E | 7 | 5 | 6 | 0 | 1 |
| No-lexical shadow / Z1 | 12 | 0 | 9 | 2 | 1 |
| No-lexical shadow / Z2 | 12 | 0 | 9 | 2 | 1 |
| No-lexical shadow / E | 12 | 0 | 10 | 1 | 1 |

The current gate still permits the two known wrong Chinese proposals; removing
the lexical gate alone does not fix them. The English current-gate arm has zero
answered mismatches by also blocking four correct proposals and the wrong one.
It is not a free correctness improvement or a replacement planner. The old
translation-fidelity ledger and detector adoption decision remain unchanged.

## Current panel, validation and next action

Prepared a fixed 15-set / 292-case panel using existing expected outcomes:
author 160, features 39, settled batch 1 50, real smoke seven, fictional service
24 and service adversarial 12. Keep no-sampling repeats separate. Unjudged
holdout2/holdout3/ratio are excluded from fresh calls: another answer would not
create a missing oracle. No prompt tuning, Best-of-N or new case-generation
framework was added. The panel is bounded to 900 transport attempts including
repair/retry, serial shared-endpoint calls and fresh metrics-only outputs.

Automatic review rejected the invocation **before process creation** because
generic Gemma/psql permission did not explicitly authorize sending real POS
questions and database-derived schema/overlay information to that gateway.
No credentials were read, no model/PostgreSQL calls occurred, and the current-run
directory does not exist. The command was not retried or routed around the
denial. Specific payload/destination approval is needed to continue this panel;
its results must not be presented as measured yet.

Twenty private tests passed for accounting, lineage propagation/cycles, the
compiler counterexample, value-dropping output, fresh-only writes, fixed panel,
call limits and transport stop behavior. Tracked source is unchanged at
`sha256:e01de711a9ebb6e0da5b67fe9b6b2773184f64bc5f6abf307b6ee71c53943361`;
reuse the previous final static/offline gate: 1,646 pass, zero failures/errors/
skips. These are separate counts; the private tests are not part of that gate.

Next obtain the required external permission, run the fixed panel and use the
per-family wrong-answer/false-refusal counts to prioritize work. Separately
repair verdict identity before any new automatic judgment reuse. Do not resume
cards, add lexical exceptions, or promote bilingual agreement to intent proof.
