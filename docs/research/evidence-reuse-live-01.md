# Fixed current-source panel: answers, refusals and remaining uncertainty

Started 2026-09-12, completed 2026-09-13 (Taipei). All 15 sets / 292 case
executions finished, using 283 model attempts, all completed, zero transport
errors/retries. Source and inputs remained unchanged. Evidence:
`evidence/evidence-reuse-live-01.json`; detailed metrics and ledgers remain in
`.artifacts/reuse-measurement-20260912/current/`.

## Results and interpretation

**283/292 cases meet the existing regression expectation, not 283 correct
answers.** The pass count is 228 reference-matched answers, 54 accepted refusals
and one status-only accepted answer. The nine failures are four reference-
mismatched answers, four unaccepted refusals on expected-answer cases, and one
answer on a case requiring `semantic_gap`. No case is unjudged by the existing
status oracle, but the status-only answer has no value proof. None has `failed`
status or a truncated answer.

| Cohort | Cases | Meets existing expectation | Reference-matched answers | Accepted refusals | Failures |
|---|---:|---:|---:|---:|---:|
| Authors | 160 | 155 | 106 | 48 | 5 |
| Features | 39 | 37 | 37 | 0 | 2 |
| Settled real POS batch 1 | 50 | 50 | 47 | 3 | 0 |
| Real POS smoke | 7 | 7 | 6 | 1 | 0 |
| Fictional service | 24 | 24 | 22 | 2 | 0 |
| Service multilingual adversarial | 12 | 10 | 10 | 0 | 2 |

Authors additionally contain the one status-only accepted answer. Across the
234 answered cases, 228 match references, four mismatch, one has only a status
pass, and one violates the expected refusal without a reference-value oracle.
Do not quietly discard those last two cases from a claimed answer-accuracy rate.
The 292 executions contain 250 exact question/datasource hashes: this is not
250 independently sampled intents, since contexts, controls and languages recur.

The four reference mismatches concern average base salary, the first week of
a month, a two-month comparison, and quarterly payroll. Refusals occur on a
member ratio, a partial-name no-sampling case, a Japanese no-activity question,
and an English records-versus-distinct-entities question. The unexpected answer
concerns a fee concept the fixture marks as absent. Failure IDs/statuses/hashes
are retained privately in `current-analysis.json`; no new manual verdicts were
invented. We cannot establish each failure's exact causal plan transformation
from this metrics-only capture. Only the partial-name case records a literal miss.

Two further observations matter:

- Both POS sampling conditions score 25/26, but on different failures. The
  sampled condition answers the partial-name case and refuses the member ratio;
  no-sampling does the reverse. The paired question hashes match. Equal totals
  do not demonstrate stable per-question behavior, and a single sequential
  comparison does not isolate sampling from endpoint/session variability.
- Every set has shape variants below 5% (one each on POS and no-sampling,
  1/26; all other sets zero), while the four mismatched answers and the
  unexpected answer still occur. All five are `unverified_semantics`; that
  generic label does not detect or identify their specific intent error.
  No stronger intent-certification claim follows from well-formed plans.

Four validation-repair turns occurred (one POS, three features), with zero
transport retries. Eight cases had candidate hints and eight references were
used, with zero candidate-reference errors and zero hinted literal misses.
One unhinted literal miss occurred. This small slice shows working candidate
binding, not independent entity selection or acceptance of provisional A5.

Per-question p50/p95 are 3.865/5.135 seconds under the runner convention below;
model-attempt p50/p95 are 3.846/5.063 seconds. All 283 attempts succeeded, so
transport failure does not explain the nine failed expectations in this run.

My judgment: the existing assets are sufficient to establish a useful current
regression baseline, and the governed query path performs well on the settled
POS and basic service cases. They do **not** demonstrate automatic intent
reliability or product readiness: successful answers coexist with both needless
refusals and a missing-definition answer. The current model remains useful as
a bounded planner; these results do not justify making it its own intent
certifier. This is neither a replacement for fresh real-user holdout evidence
nor a controlled comparison attributing changes to one historical repair.

## Scope and authority

The owner explicitly approved sending the existing test questions (including
real POS), schema/overlay and policy-eligible candidates to the named private
Gemma4 31B gateway, capped at 900 attempts including retries, and requested
the results plus their interpretation. See `../plan/evidence-reuse-measurement.md`
and `../plan/active-work.md`. The previous automatic-review rejection occurred
before any process/call; this follow-up was approved and executes that same
fixed panel, not a workaround or a new experiment.

Baseline `6ddd8eb`; frozen tracked source
`sha256:e01de711a9ebb6e0da5b67fe9b6b2773184f64bc5f6abf307b6ee71c53943361`.
No runtime, prompt, fixture, scoring, threshold, dependency or historical-label
change. No cards, human correction, Best-of-N, prompt tuning or second run to
pick a better answer. Research drivers stay ignored under
`.artifacts/reuse-measurement-20260912/`; only documentation and counts/hash
evidence enter Git. No push.

The panel contains 292 case executions across 15 sets: author 160, features
39, settled batch 1 50, real smoke seven, service 24 and service adversarial
12. The 26-case no-sampling POS control repeats the original POS questions;
languages and paraphrases are not independent draws from real users. The
previously used holdout2/holdout3/ratio sets lack a trustworthy new oracle and
are not called again just to generate another unjudged answer.

## What the measurement means

The existing runner computes correctness from accepted response statuses, then
reference SQL when the answer has one. This report separately counts:

- answered/reference-matched cases;
- answered/reference-mismatched cases;
- status-only accepted answers, which have no value proof;
- accepted refusals;
- unaccepted refusals on expected-answer cases and mismatched refusal types;
- unaccepted answers on expected-refusal cases;
- operational failures and unjudged cases.

The original reference comparator sorts rows, normalizes numeric values to
four decimal places, accepts fixed reference alternatives, and can project
away extra dimensions when the remaining result agrees. Thus a match is
agreement under that comparator on this data, not proof of output ordering,
full precision, exact selected concept or generalization. Settled batch-1
references are previously accepted system outputs, not a new independent
human oracle. No verdicts are automatically carried into this run.

Latency uses the runner's index convention, excluding `unsafe`/`not_run` and
including other zero-call refusals. It is per-question ask time, not total
introspection/reference-comparison overhead. Provider-attempt latency is
reported separately from the metered transport ledger.

## Execution controls and evidence limits

Five existing PostgreSQL databases are accessed only through `grepbit_ro`;
the driver verifies `current_user` before the panel and the query paths are
read-only. Original credentials are loaded opaquely in the executing shell;
no second copy is made. Real POS uses sampling zero and `--redact-rows`.
Questions/schema/overlay/eligible hints are authorized model inputs; SQL,
result rows and credentials are not model inputs.

The model is configured as `gemma-4-31b`, temperature 0, thinking off,
`json_object`, prompt `plan-classify-json-v15`, one validation repair turn and
a 20-second call timeout. The shell token setting is 512; the existing planner
applies its non-thinking minimum of 768. This records configuration, not an
immutable provider weight/build fingerprint. Calls are serial and all attempts
are metered; the driver stops at 900 attempts, two consecutive transport errors,
source drift or an incomplete set. No unrecorded candidate-selection calls.

Source identity is checked between sets and at completion. Case/overlay hashes
and effective as_of are bound into the manifest and checked again by analysis.
Real POS as_of stays 2026-02-04 18:00 Taipei; other sets use their case-file
as_of, including service 2026-04-15. The DBs are not frozen against external
writers, so no cross-run data-snapshot equivalence is claimed.

The metrics writer strips question, raw plan, SQL, result rows, assumptions,
literal values and raw model output before writing anything. Private artifacts
retain fixed case IDs and hashes; public evidence contains counts and hashes.
The privacy trade-off is that a new failure's exact plan and refusal reason
are not retained. Do not infer its root cause merely from its case name or an
older failure. A targeted diagnostic would need separately scoped, safe
structural evidence; this run does not introduce that logging contract.

This measurement cannot establish an absence of unexposed wrong numbers or
certify intent. Structural verification levels and generic assumptions are
not an independent adjudication of what the question requested. The separate
local cross-language replay in `evidence-reuse-measurement-01.md` still shows
shared wrong proposals and false lexical refusals; this panel does not promote
bilingual agreement, same-model verification or another selector as a gate.

## Validation and next priority

The post-run analyzer checks all 292 case IDs, question hashes, expected and
accepted statuses, original correctness arithmetic, per-set report hashes,
case/overlay/effective-context hashes and frozen model/prompt settings. It
checks exactly one start and one completion for each of the 283 attempts and
the unchanged source hash. Five new analysis tests pass; the unchanged panel
driver/history analysis retain their prior 20 passing private tests. The
runtime/test source is unchanged, so the previous passing static/offline gate
(1,646 tests, zero failures/errors/skips) is reused, not rerun or misreported
as new live evidence. No query-result data is published.

Next prioritize the one missing-definition answer and the four reference-
mismatch families before reducing refusals just to lift the total score.
Organize a bounded diagnostic with safe structural evidence and unchanged
gold, then test a cause-specific candidate against both that family and the
correct controls. Do not add a lexical exception or assume an old cause from
the case name. Repair the separately demonstrated verdict-identity gap before
using automatic carry again. A fresh non-POS user holdout is still needed to
measure generalization. No additional calls or product change were made here.
