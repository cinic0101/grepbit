# Concept search and selection: bounded comparison

2026-09-12. Owner: root, sole writer. Status: completed, no promotion.

430 calls completed with unchanged source; focused 66/offline 509/static pass.
Single on is strongest on the frozen pilot (28/30 intent, 51/51 pair verdicts),
but five post-run offline counterexamples expose unjustified acceptance using
its exact captured outputs. No new model call or change to frozen scores.
See ../research/concept-search-01.md and evidence/concept-search-01.json.

## Outcome and original authority

The user asked: "你剛提的那些方案，幫我組織一整個測試計劃，測試完告訴我結論".
Earlier explicit permission covers necessary Gemma4 calls. This is permission
for a research experiment, not runtime promotion, a new business default, or
Git writes. Preserve the existing dirty tree at 746f168. No worker delegation.

Compare whether additional inference improves (a) candidate availability,
(b) actual selection, and (c) safe useful qualifier decisions. Separate these
from full question/SQL correctness and production failure probability.

## Frozen ruler and checkpoint boundary

Reuse concept-pilot-ruler-v1, concept-fixed-plans-v1, Intent, label_core,
check_bindings, and summarize without changing labels or historical reports.
30 authored questions = 10 families x 3 languages; 51 fixed pairs. These are
diagnostic/tuning cases, not a new holdout, independent translations, or live
planner answers. No new family labels are introduced by this experiment.

An implementation instrument and optional experimental prompts do not change
the existing critical grading contract. Characterize representation blind spots
with current-contract tests; do NOT add unrestricted/denominator requirements,
change not_applicable into a pass/fail, or revise the grader. Any proposed
meaning/identity contract expansion ends at a separate ruler checkpoint for
owner follow-up. Production gates, planner prompts and release thresholds stay
unchanged. No claim that the representation proposal has been implemented.

## Pre-registered arms

All calls: Gemma4 31B, same supplied schema/definitions, JSON object output,
4,096 completion-token cap, 60-second timeout, no transport retries. Reasoning
text is never saved. Temperature and prompt are recorded per call.

| Arm | Calls per question | Variation |
|---|---:|---|
| off0 | 1 | Original independent extractor, thinking off, temperature 0 |
| on0 | 1 | Same, thinking on, temperature 0 |
| off_samples | 3 | Same, off, temperature 0.6 |
| on_samples | 3 | Same, on, temperature 0.6 |
| population_view | 1 | Off/0, distinguish universe from selected subset |
| contrast_view | 1 | Off/0, test whether a restriction is demanded or prohibited |

These 300 calls are interleaved by question with a fixed seeded arm schedule.
This reduces block-order confounding, not a load-controlled inference study.
No fixed generation seed is sent: that would defeat sampling diversity.

For each sample pool, measure N=1/2/3 oracle availability, unique semantic
cores, exact agreement, and joint errors. Ignore supporting-span differences
only AFTER validating verbatim spans. Vote over the WHOLE core, never fields.
Strict majority needs >N/2 votes; errors remain in N and cannot win. A tie or
no majority is abstention, not a schema error. Unanimity requires all N valid
and equal. Also test a three-view pool (off0 + both views).

Best-of-3: another on/0 LLM request selects a whole candidate from the three
off_samples or abstains. It sees original question, definitions and unique
validated candidates in seeded shuffled order; no gold, plan, frequencies,
arm labels or generator explanations. A chosen ID must be offered. At most
30 selector calls. Invalid candidates cannot be selected. Selector quality is
reported conditional on a gold-correct candidate being available.

Direct audit: compare the existing off/0 raw-plan rubric to the same rubric
with lossless bounded plan predicate/operand facts (metric filters expanded
from supplied reviewed definitions). 51 calls each, 102 total. This is a
representation ablation, not a new deterministic natural-language verifier.
Facts cover only current fixture shapes; unsupported shapes fail locally.

Maximum live calls: 432. No automatic extension or retuning after results.
Stop after three consecutive transport errors, source drift, or budget breach.
No DB, packages, second model/endpoint, training, runtime integration or Git
writes. Destination: the already-authorized Gemma gateway configured in the
opaque environment. Outbound: authored synthetic questions, projected schema,
reviewed definitions, synthetic typed plans/facts and validated intent outputs.
Never send rows, customer data, credentials, expected labels, IDs of test
families, gold rationales or SQL. Source .env opaquely in the existing shell;
no copied credentials or endpoint URLs in artifacts. Process-name preflight
found no matching Python/regression process before edits (outside sandbox).

## Adaptive-policy replay (not extra calls)

Using the measured complete branches, predeclare two counterfactual policies:

1. off0 -> on0 when extraction fails, is ambiguous, or its checker returns
   fail/unknown on this plan; otherwise retain off0.
2. off0 + population_view -> on0 when either is invalid or their cores differ,
   or baseline checker returns fail/unknown; otherwise retain off0.

No gold determines triggering. Evaluate all untriggered pairs too, including
shared wrong agreement. Cost is the SUM of the required measured sequential
calls, counting errors, not a fastest-of-N parallel claim or a deployed latency
measurement. Failure/abstention must not be silently replaced by the best gold
candidate. Timing of counterfactual requests is a limitation.

## Representation diagnostic and interpretation

Current Intent cannot express explicit no-restriction, denominator-role, or
two roles/polarities for the same concept. Characterize these limitations
without relabelling current pairs. In particular no-request currently bypasses
the checker even on a restrictive plan; call this a blind spot, not semantic
verification. Prompt-only views cannot repair a missing representational slot.

Report exact intent labels, wrong/unresolved allowed separately, correct-control
acceptance and rejection/error/unknown, all-call p50/p95, completion/total tokens,
calls, cap/format/transport failures, and source/input/message hashes. Compare
risk at observed coverage; an all-abstain method cannot win. Counts are primary;
no calibrated product-level risk estimate from 10 authored families.

Recommended continuation must follow evidence: no oracle gain -> representation
or generation; oracle gain without selection gain -> selector; useful gain at
unacceptable cost -> evaluate adaptive routing. Actual unseen user questions
and family-held-out evaluation remain necessary before a promotion decision.

## Evidence and validation

Fresh outputs: .artifacts/concept-search-20260912/ (live report, append-only
call journal, focused/static/offline verification). Durable summary and hashes:
evidence/concept-search-01.json; conclusions: docs/research/concept-search-01.md.
Focused tests first, then one static and broad offline closeout. Preserve full
existing work; this slice owns only experiment instrument/tests and these docs.

## Post-run methodological addendum: separate eight-call ranking probe

The original 430-call experiment is closed and its cap/results are not changed.
Its off pool contains no distinct valid alternatives, so it did not exercise
actual reranking. To complete the user's requested comparison, a separately
bounded exploratory diagnostic is announced before execution: select only the
four ON pools with >1 distinct valid core (selection criterion uses no gold),
offer each in two reverse orders to the UNCHANGED original selector prompt.
At most 8 additional on/0 calls; same gateway, opaque key, synthetic data,
4,096-token/60-second caps and three-consecutive-transport-error stop. No new
questions, N increase, generation, prompt retuning, grading changes or production
integration. This is post-hoc exploration, not pre-registered confirmation; do
not merge it into the 30-question strategy scores or claim generalization.

Authority remains the user's current request to organize and execute the
comparison plus existing Gemma authorization, not this agent-written record.
The small bounded diagnostic resolves a measurement gap within that scope;
it grants no new endpoint, DB, Git or product authority. Script and reports:
.artifacts/concept-search-20260912/selector-probe.py and selector-probe.json[l].
Record the standalone driver's hash separately from the unchanged repo source.

Completed: all 8 calls returned valid output, 6/8 gold selections. Both ambiguous
rate translations switch selected core after order reversal; both member-share
translations select correctly in either order. Total actual calls across the
two explicitly separated scopes: 438. All own runs ended; no promotion.
