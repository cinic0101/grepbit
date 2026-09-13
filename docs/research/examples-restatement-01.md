# Examples and deterministic restatement: bounded development screen

2026-09-13. Baseline `658f1f6` plus the approved name-boundary repair,
`ask-orchestration-v5` / `grounding-bigram-v2`. Production prompt remains
`plan-classify-json-v15`. Protocol: `../plan/examples-and-restatement-study.md`.
Private evidence: `.artifacts/examples-restatement-20260913/`; durable counts
and hashes: `../../evidence/examples-restatement-01.json`.

## Decision

Neither research candidate advances to production or a larger confirmation
run. Keep the separately approved deterministic name repairs
(`name-boundaries-01.md`). Do not add retrieval infrastructure, more keyword
exceptions, a model intent gate or calculation cards from this result.

Ordinary examples rescue one English payroll question; the targeted contrastive
examples do not. This is a useful observation, not evidence of a generalized
negation/scope solution. Restatement catches no additional wrong pair, loses
one previous catch and introduces one new false flag. Fewer total false flags
do not offset these paired regressions under the frozen acceptance screen.

## A: four planner presentations

36 authored questions: payroll, goods and services; four component/population
intents; Chinese, English and Japanese. Existing questions, QueryPlans and
independent reference SQL reused; Japanese cases are authored development
controls, not independent translation judgments or a new-user holdout.
Two examples use a separate fictional subscriptions schema, never test tables
or questions. Ordinary and contrastive arms have equal example counts, not
equal token counts; the neutral arm supplies true generic catalog prose.

| Arm | Accepted answers / 36 | Confirmed component-as-row errors | p50 seconds |
|---|---:|---:|---:|
| Unchanged planner | 35 | 1 | 3.504 |
| Neutral context | 35 | 1 | 3.571 |
| Ordinary question/plan examples | 36 | 0 | 3.585 |
| Contrastive question/plan examples | 35 | 1 | 3.534 |

All 144 executions answered; no score improvement comes from refusing.
The three wrong outputs share the same plan hash on
`b_payroll_exclude_component_en`: the intended sum of base salary excluding
the separate bonus component is turned into a population restricted by
`bonus = 0`. Actual payment date and quarterly grouping are correct. Three
fictional instances distinguish this filter error from the intended sum.
The ordinary-example plan omits the erroneous restriction.

The unchanged `disclosed-answer-v1` grader records those answers as
`unassessed`, not accepted. A separate, explicit post-run cause adjudication
uses the frozen component intent, the exact extra filter and all three value
mismatches. Historical scores/golds are not rewritten. Shadow replay without
the concept veto yields the same 35/35/36/35 accepted counts: this panel's
gain is not a lexical-gate masking effect. That shadow still uses the remaining
deterministic pipeline; it is not unconstrained raw-model certification.

The contrastive arm rescues zero baseline errors. The ordinary arm's one rescue
is below the two-question/two-domain screen. Importantly, this run's baseline
has only one error: there is a ceiling/power limitation, so the experiment
cannot establish cross-domain rescue and does **not** establish that examples
in general are useless. No in-run tuning or replacement of that threshold.

## B: untrusted coverage audit, structured versus restated computation

12 authored utterances (six question families, two languages), each paired with
one correct and one wrong plan; two presentations = 48 calls. Component scope,
population selection and rows-versus-entities are covered. Three fictional
instances per utterance distinguish each paired computation. Known labels come
from the existing authored contract/fixtures, never the model audit.

| Audit presentation | Wrong pairs flagged / 12 | Correct pairs falsely flagged / 12 | Unavailable / 24 | p50 seconds |
|---|---:|---:|---:|---:|
| Structured plan + effective lineage | 6 | 4 | 1 | 3.565 |
| Deterministic effective-computation text | 5 | 3 | 0 | 3.661 |

No incremental wrong-pair catch. Restatement loses
`b_goods_exclude_component_zh` and newly flags the correct
`output_count_returns_en`. Both presentations miss the two wrong payroll
component-exclusion plans and the wrong all-transaction-count plans when they
produce valid reports. The structured English all-count audit is unavailable,
not a successful detection. Both miss Chinese `service_rows`, while both catch
its English counterpart in this run. Same-model agreement remains no proof.

The audit more reliably flags the missing explicit `bonus = 0` restriction
than the erroneous addition of that restriction in these pairs. This supports
a scoped observation about the existing coverage-style task, not a universal
claim about all verifiers or back-translation. Empty/malformed reports are
unavailable; unflagged means only that this audit raised no issue.

The two arms share question, column metadata, audit rules and CoverageReport
wire. Structured input retains the proposed plan, effective lineage and count
NULL/duplicate semantics; restatement uses the compiler's existing disclosure.
This is a representation-package comparison, not token matching. The renderer
shares the compiler's semantic machinery and is not an independent SQL oracle.
No SQL or rows are sent to Gemma; no generated paraphrase is treated as gold.

## Accounting and safeguards

192 scheduled jobs completed; **193 actual attempts**, comprising 192 completed
transport responses and one deliberately interrupted in-flight A attempt. No
transport failure. One B response fails the structured-output contract; no
retry/repair is allowed for that audit. Gemma4 31B, temperature zero, thinking
off (explicit at B transport), serial/interleaved arms, unchanged 480-attempt cap.

Before any B calls, input review found that the first structured projection
had dropped the quarterly grain. The run was paused after 99 completed A jobs.
Original `frozen.json`/`live/` are immutable; v2 files retain the plan/grain and
resume only unfinished jobs. All 144 A payload/oracle hashes, case order, source
and schema hashes match the first freeze. No B output informed this correction.
The interrupted call is counted, not hidden. The pause can still confound
session comparisons; English payroll's four arms all ran before it.

Source/schema/oracle identity is checked at completion. 216 frozen compiler/
independent-SQL comparisons and 36 paired value witnesses pass; these repeat
orders, instances and language-equivalent plans, not 252 independent questions.
Private preflight: 11 original and 12 corrected-driver tests, 5 analysis tests
on each version. Name repair: 115 focused, 2 additional cap controls, 15
PostgreSQL VALUES checks, one 1,796-test offline gate and static pass. Private
scripts/results remain in `.artifacts`; only sanitized counts/hashes are published.
Read-only role only, opaque existing credentials, no persistent DB write or push.

## Next order

1. Keep the scoped binding/collision repair. Next name-quality measurement
   should use independently supplied names/questions, not relabel these rulers
   as model generalization evidence.
2. Preserve the ordinary-example rescue as a candidate observation. Revisit
   only with additional independently labeled errors across domains and a
   frozen confirmation scope; do not keep varying the same prompt on one case.
3. Do not turn this restatement audit into a gate. Keep deterministic effective
   computation disclosure for its existing transparency purpose, not validation.
4. Resume product coverage/evidence work with existing artifacts and explicit
   supported semantics. No automatic expansion, new model budget or production
   example mechanism follows from this failed development screen.
