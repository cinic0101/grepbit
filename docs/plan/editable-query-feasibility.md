# Editable query definitions: feasibility experiment

2026-09-12 update: the owner authorized beginning the Stage-0 rulers, explicitly
naming that phase. `editable-query-stage0-rulers.md` specifies the current
test-only boundary, hand facts, whole-candidate edit and review identity.
Baseline clean dev `8c9e7c5`; no editor, model/DB calls or human pilot yet.
Standing local-commit permission supersedes the historical no-Git planning
restriction below; explicit post-ruler implementation approval is still required.
Ruler results are now in `../research/editable-query-ruler-01.md`: focused
272 pass / 3 fail, static pass, offline 1,858 pass / the same 3 reference
named-segment failures. This is a completed specification checkpoint, not a
completed Stage-0 implementation or a green technical readiness gate.

2026-09-12. Status: protocol drafted, not implemented or measured.
Owner request: "好 我們先做個實驗來驗證可行性？你來組織" after comparing
self-certification, answer-and-correct, explicit confirmation and approved templates.
This slice organizes the experiment; it does not approve a production behavior
change or claim that human correction works. Root sole owner, baseline dev
746f168 with existing uncommitted implementation and evidence preserved.

## Decision to test

Can people use a faithful, editable calculation definition to reach the intended
answer despite an imperfect Gemma proposal, without excessive effort or damaging
correct answers? Do not require Gemma to certify its own understanding.

Separate three hypotheses:

1. Fidelity: the displayed definition describes what actually executes, including
   effective metric filters and defaults, not just the unexpanded model proposal.
2. Repairability: an explicit supported edit produces exactly the selected change,
   preserves unrelated semantics, and goes through existing validation.
3. Human usefulness: people notice the relevant mismatch and make that edit.

Scripted gold edits test (2), never (3). A confirm click alone proves neither
understanding nor correctness. Better completion after interaction is not higher
first-turn Gemma accuracy. No automatic-promotion or generalization claim.

## Scope and permission record

- Current work: this protocol and a pointer in `active-work.md`; read-only review
  of existing contracts, synthetic fixture helpers and aggregate research results.
- No edits to src, evals, tests, old golds, scores, prompt or served status labels
  in this planning slice. No stage, commit, push, packages or deployment.
- The previous five-arm 180-call experiment is complete; its budget is not reused.
  The proposed technical and human pilot below both need ZERO new model calls,
  network services, real databases or credentials. Use local fictional fixtures.
- No participants are contacted or recruited now. The owner must identify willing
  participants before the human pilot. Participation and optional research logs
  require their agreement; never record names, audio, video or business data.
- The future edit/confirmation identity and evaluation artifacts are a new
  compatibility-sensitive research contract. First add specification rulers only,
  establish intended behavior, and obtain explicit post-ruler follow-up before
  implementing the editor, confirmation path or measurement harness. Approval of
  this plan is not a substitute for that later checkpoint.
- Production gate removals, provisional-answer statuses, template persistence,
  automatic downstream actions and user-preference memory are OUT OF SCOPE.

## Stage 0: technical prerequisite, zero model calls

Reuse `evals/fixtures/metric_selection.json`, its three fictional instances,
the reviewed fixture overlay, captured synthetic P-arm proposals from
`metric-factor-study-01`, and the existing compiler/reference/ask replay patterns.
Source helpers: `evals/metric_selection_study.py`,
`evals/metric_wire_study.py`, `evals/metric_factor_study.py`.
Verify input hashes and synthetic provenance before opening any captured payload.
Do not read real holdout artifacts to populate the experiment.

Keep the first fragment deliberately small: one ungrouped aggregate or ratio,
count / count-distinct / sum, named calculation candidates with their complete
populations, and an output label. No new basis/population Cartesian products.
Candidates are source-bound existing definitions, not gold-selected alternatives.
Missing definition and unsupported requests remain explicit non-answer options.
Time, joins, grouping, share, growth and without are NOT silently dropped: plans
outside this fragment are reported as unsupported by this prototype. They need
their own fidelity coverage before the editor may claim to support them.

Research card contents:

- counted entity/row unit or summed column, including DISTINCT and NULL handling;
- full effective population, including reviewed exclusions and extra predicates;
- numerator and denominator separately for ratios, including zero-denominator NULL;
- output label separated from business predicates;
- definition source and the existing verification status with its limited meaning;
- explicit "no time restriction / no grouping" for this fragment, not omitted
  fields that could conceal unsupported semantics;
- correction options, "none of these", "definition missing" and "cannot decide".

Generate text deterministically from the bound plan, overlay, applied segments
and compiled interpretation. Authored business labels belong in fixture data.
Do not ask an LLM to explain, translate, certify or repair the calculation card.
No synthetic rows or SQL are sent to any model; people may see fictional aggregates.
Do not reuse the old partial intent checker as a complete meaning oracle.

### Rulers required before implementation

1. Wrong-valid controls display their actual wrong population/unit, not the gold
   meaning or a reassuring copy of the question. Independently hand-authored facts
   check fidelity; renderer round-trip equality alone is insufficient.
2. Every result-affecting supported predicate/default is visible in the correct
   scope. Hidden metric filters, COUNT versus DISTINCT, implicit NULL exclusion,
   denominator restrictions and labels have positive and negative controls.
3. A source-bound whole-candidate replacement retains that candidate's provenance;
   no reviewed metric is relabeled after arbitrarily editing its internal filters.
   The allowed catalog does not depend on gold or the current error.
4. Label-only edits cannot change filters, measure or population. Operand edits
   cannot change the other operand or unrelated fields. Incompatible combinations
   refuse atomically; never silently repair an edit to a different meaning.
5. Research confirmation references the exact effective plan/context revision:
   schema, overlay, segment state, as_of and display revision. A stale confirmation
   fails; a changed calculation needs fresh review. This is an in-memory research
   identity, not a new persistent API or a security credential.
6. Recompiled effective semantics must match the reviewed definition. Any subsequent
   normalization that changes meaning requires redisplay, not reuse of confirmation.
7. No-choice, timeout, "none" and missing definition are not confirmation. An agent's
   inferred agreement is not human confirmation. Existing verified status is never
   promoted merely because a button was pressed.
8. Known forbidden/unsupported plans remain refusals. All arms preserve actual ask
   gates, policy, literal checks and compiler/self-check behavior. A production
   refusal cannot be rendered as an answered result in the experimental arm.
9. Check each supported starting and edited plan on all three fictional instances
   against independent hand expectations and the reference. Include witnesses where
   wrong and correct meanings differ; value coincidence never establishes intent.
10. Preserve a no-op exactly. Invalid edits leave the previous state intact; a
    superseded result is visibly stale and cannot be submitted as the new answer.

Stage-0 entry gate: all specified fidelity/identity/safety rulers pass, all planned
value checks execute and agree, with no silent omission or gate bypass. Report
unavailable cards and refusals instead of dropping them from denominators. A
failure here stops the human pilot; it is not evidence about user ability.

## Stage 1: controlled human feasibility pilot

Proposed size: six willing business-data users, twelve tasks each, seventy-two
task exposures. This is a small usability pilot, not a power calculation or
proof of population-level improvement. If only the owner participates, run a
walkthrough and label it as such; repeated owner/agent trials are not six users.
Start in Traditional Chinese; no multilingual usability claim from translations.

### Arms

| Arm | Initial presentation | Editing and completion |
|---|---|---|
| A | Existing answer, interpretation and assumptions | Common explicit editor accessible through an Edit action |
| B | Same answer plus faithful calculation card, with fields directly editable | Same allowed edits; final submission records the chosen definition |
| C | Same card and editor before any numeric result is visible | Explicit confirmation reveals the result; later edits invalidate confirmation |

A is a display control augmented with the SAME deterministic editor, not a claim
to reproduce the current natural-language follow-up product. This isolates card
visibility/edit access and the timing of numeric results without confounding them
with Gemma's ability to parse correction text. All arms have the same candidate
universe, glossary, final submission action and maximum task time. A user has to
submit or abstain; clicking Continue is not scored as correct understanding.

No live natural-language repair in this pilot. Free-text comments can describe an
unavailable edit but do not magically become corrected executable plans. Such
tasks remain unresolved. A later end-to-end conversational comparison needs a
separate measured model-call scope; no benefit is attributed to it here.

### Task and assignment design

Freeze twelve distinct task families before recruitment:

- Four correct initial answers: include genuinely requested returns, all-row
  count with a return-themed output label, distinct entities and a scoped ratio.
- Four wrong-valid initial answers: extra returns subset, rows versus entities,
  unintended NULL exclusion and a wrong ratio denominator.
- Two underspecified initial questions with a clear private business brief:
  count versus amount rate and denominator scope. The brief is available to the
  participant, not to the original proposal. These measure evidence acquisition,
  not resolution of an unknowable intention.
- Two missing-definition/unsupported tasks: abstention is appropriate; ensure
  the interface does not pressure the participant into choosing a false answer.

The examples above specify categories, not final frozen case IDs. Match to actual
captured proposals when available; mark manually seeded faults separately. Never
label seeded prevalence as Gemma's natural error rate. Do not force a blocked
proposal into the answered stratum: replace it before freezing or retain it as a
declared refusal control. Initial plans/results are identical across arms per task.

Each participant sees each family only once, with four tasks per arm. Use a frozen
counterbalanced assignment so each task occurs twice in each arm across six people;
balance order and fault strata as closely as possible and record the schedule.
Candidate ordering is balanced independently of gold. Do not reveal a task's
correctness or expected answer between trials. Give two separate practice tasks
and the same neutral instructions; no warning that a particular task is wrong.
Participants know that some proposals may be wrong, not the planted error rate.

Gold is an independently reviewed business task brief plus accepted final plan
semantics and hand-computed values, frozen before the session. The task brief
states the intended business outcome without instructing which editor button to
press. It is never used to prune or sort options. No gold leakage through filenames,
browser payloads, visible IDs or facilitator hints. Feedback transcripts and task
briefs are controlled research inputs, not real-user blind holdout questions.

### Measurements

Record pseudonymous participant/task/arm, initial and final semantic identities,
explicit edits, confirmation invalidations, submission/abstention, task duration
and outcome. Collect no keystroke streams or unrelated personal information.
Proposed per-task cap: three minutes; a timeout/abandonment remains in the total.
Use correctness-blind facilitation; adjudicate final semantics against frozen gold.

Report separately, per arm and fault stratum:

- wrong submitted answers / all tasks, and / submitted answers;
- initial wrong answers corrected, detected-but-unresolved and accepted unchanged;
- initial correct answers retained, corrupted or unnecessarily abandoned;
- evidence supplied on ambiguous questions; unjustified answers on missing definitions;
- editing coverage, timeouts, task completion time, edits and confirmations;
- confirmation of a wrong definition (rubber-stamping), not just click counts;
- end-to-end task success, with correct abstention separate from correct answers.

Arithmetic agreement, semantic correctness and human recognition are different
columns. A visible assumption is not proof the participant noticed it. Use explicit
edits/flags to identify observed detection; otherwise label detection unknown.
Show participant/task breakdowns and raw denominators; trials share participants
and families and are not seventy-two independent users or new model predictions.
The deliberately enriched error mix is not a production error-rate estimate.

### Pilot decision rules (proposed, freeze before sessions)

Hard stop: misleading card, changed-but-still-confirmed plan, invalid edit executed,
gate bypass, leaked data or unintended mutation. Correct these before further use;
do not average them away with a better usability score.

A candidate may justify a larger independent study only if it has fewer wrong
submissions than A, preserves at least as many initially correct tasks, does not
increase unjustified answers on missing-definition tasks, and has median completion
time no more than 1.5 times A among comparable completed tasks. Also report timeout
rates and time including capped trials so selective completion cannot hide cost.
Require improvement across at least two fault families and more than one person;
if A has no wrong submissions, or results depend on one participant, call the
comparison inconclusive instead of inventing a win. These are resource-allocation
screens for this small pilot, not statistical significance or release thresholds.

Prefer B if its safety outcomes match C with less burden; prefer testing C further
if it prevents errors B misses at acceptable cost. If neither helps, stop polishing
the card: investigate comprehension or narrow the supported task space. Do not
respond by adding another same-model judge or automatically increasing sample size.

## Stage 2: only after a positive pilot

Separate follow-up proposals: actual Gemma natural-language corrections; fresh
user-authored questions; other languages; time/grouping constructs; and predefined
task invocation by another agent. None is included in this initial measurement.
Template persistence, production answer/confirmation statuses and autonomous
consumption require separate contracts and owner decisions. No automatic rollout.

## Evidence, validation and handoff

Future local artifacts: fresh `.artifacts/editable-query-<run>/` with source/input
hashes, catalog/display versions, arm schedule and pseudonymous events. Consent
and participant coordination stay outside Git. Commit-eligible evidence, only
if later authorized: aggregate counts, fictional rulers and a research report;
do not commit raw participant comments. Old study scores stay unchanged.

During future implementation, use focused ruler tests; run one static/offline
closeout on the final source. Reuse existing fixture/compiler/replay helpers where
their assumptions match; no generic UI framework or production service is needed
for a local study prototype. Freeze code and material before human sessions.

Current deliverable: protocol only. No new tests, model attempts, DB comparisons
or human trials have been run. Next technical step is the Stage-0 ruler checkpoint;
participants are needed only after that contract is implemented and verified.

## Research basis and limits

- [STEPS, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.1004/): editable
  explanations and a 24-participant study motivate the interaction hypothesis.
  It is not evidence that our card, users or Gemma corrections work.
- [Clarify When Necessary, NAACL 2025](https://aclanthology.org/2025.findings-naacl.306/):
  clarification has a cost and benefit; its non-SQL tasks do not determine our
  thresholds or imply that frequent confirmation solves confident misreadings.
- Local negative baseline: `../research/metric-factor-study-01.md`. A faithful
  format, a valid candidate choice and reviewed provenance did not establish intent.
