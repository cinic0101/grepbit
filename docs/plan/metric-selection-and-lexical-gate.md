# Metric selection and lexical-gate research

Current state: owner approved the annotation checkpoint and Gemma calls with
"同意，gemma 呼叫也 ok". Research grader and exposure guards are implemented;
initial 180-call development screen is complete with no qualifying candidate.
See [results and next minimal experiments](../research/metric-selection-development-01.md).
P0/P1 30 clear matches, P2/P3 31; both stable wrong answers remain. L1 only
1/36 valid response; no gate replacement. Production and v2 stay unchanged.
The original proposal below is retained. See the
[annotation checkpoint](metric-selection-annotation-contract.md) and
[validation](../research/metric-selection-ruler-01.md).

Implementation note: the served metric payload contains names/descriptions,
not typed aggregate/filter definitions. P3 preserves that text and additionally
structures its effective operation/population and the algebra's NULL/DISTINCT
rules. This makes implicit information explicit; do not attribute a gain to
layout alone or claim the payloads contain identical literal information.
P0-P3 all use the same fictional time-free table projection. P1's all-row metric
is fixture-only, not a redefinition of payment-based transaction_count.

Status: PROPOSED, 2026-09-12. Literature and repository-grounded plan only.
Owner request: "幫我搜尋網路資源/論文，組織planner 選錯 metric 與 詞表誤擋研究計劃",
then "也找些新一點的論文來參考？". No production change, model/DB run,
new evaluation contract implementation, stage, commit or push in this slice.
This plan is not an authorization record for future external actions.

Literature follow-up: [deeper review and ruler refinements](../research/metric-selection-literature-02.md).
The owner requested continued research; no live study has started. These
refinements preserve call ceilings, existing contracts and checkpoint boundaries.

## 1. Starting evidence and the actual questions

Read [the completed contrast study](../research/semantic-contrast-01.md),
`evidence/semantic-contrast-01.json`, and
`evidence/semantic-contrast-ask-replay-01.json` first. Its 108 calls found no
winning extraction prompt. Its actual-ask replay reused six captured plans
across three fictional instances, not eighteen independent model samples:

- Chinese output-action wording selected reviewed `return_count`, producing
  wrong counts 2/3/1 instead of 4/5/3. Both research verifiers passed it.
- English output-action wording had a correct raw COUNT plan, but the existing
  lexical gate returned `concept_not_mapped` before execution.
- Japanese had a correct raw COUNT plan and answered correctly.

These are different failure paths. Fixing English refusal does not fix Chinese
metric selection; removing a mistaken obligation does not certify the answer.
Current `verified` denotes reviewed metric provenance, not intent correctness.
Keep that status contract and v2's limited certification claims unchanged.

In `application/shapes.py::unmapped_concepts`, lexical occurrence activates a
concept; column/metric/segment name traces count as mapping. Deterministic
execution of this heuristic is not deterministic proof of word sense, predicate
polarity, or operand scope. Conversely, its false positives do not establish
that its genuine omission protection can safely be removed.

One additional hypothesis needs measurement: catalog imbalance. The small
research context projects metrics by base table (`evals/concept_pilot.py`).
The POS overlay's reviewed `transaction_count` uses `pos_payment`, while
`return_count` uses `pos_sale`. A sale-only context therefore retains the
specialized reviewed count but not that reviewed total count; raw COUNT remains
expressible. This is not yet evidence of causality or of a production-wide
schema-linking failure. Do not relabel payment DISTINCT-count as sale-row count:
they can differ when transactions lack payments or payment keys repeat.

Research questions:

1. Was the intended metric/aggregation available, and did its presentation or
   competition with reviewed alternatives change selection?
2. Does a contextual concept detector reduce false blocks without missing
   actual omitted constraints? How often does it share planner errors?
3. Can bounded, semantically distinct choices improve selection, rather than
   repeatedly sampling the same mistaken interpretation?
4. Is a failure genuine ambiguity, missing business knowledge, stable
   misinterpretation, or instability? Each requires a different response.

## 2. Recent literature and what transfers

Sources checked on 2026-09-12. This is a targeted review, not a systematic
survey or a reproduction. Abstracts/publication metadata were checked; HTML
methods/results/limitations were inspected for ErrorLLM, EntSQL and CLUES.
The proposed adaptations below are our hypotheses, not findings on Grepbit.

| Primary source and status | Relevant finding/method | Proposed use and limit |
|---|---|---|
| [ErrorLLM](https://arxiv.org/html/2603.03742v2), KDD 2026; March initial / June revision | Explicit error categories and separate detection/refinement; measures corruption of previously correct queries. | Label metric/population errors and measure correct-to-wrong transitions before trying repair. Its trained SQL detector is not an off-the-shelf Gemma prompt result. |
| [EntSQL](https://arxiv.org/html/2606.03363v3), June 2026, July revision; arXiv preprint, venue not verified | Enterprise business knowledge benchmark with aligned Chinese/English examples; localized evidence helps but does not eliminate grounding failures. | Separate absent knowledge, missing candidates, and failure to use offered definitions. Do not assume a larger schema retriever fixes the small-context case. |
| [CLUES](https://arxiv.org/html/2602.12015v2), Clinical NLP workshop at LREC 2026; February / May revision | Separates interpretation ambiguity from answer instability. Limitations include nine calls/query in its setup and dependence on interpretation quality. | Annotate those causes separately; test known interpretations before model-generated alternatives. Do not immediately implement its graph estimator or treat stability as correctness. |
| [SQLens](https://proceedings.neurips.cc/paper_files/paper/2025/hash/c57812dee8acade8c5e385260b2cde28-Abstract-Conference.html), NeurIPS 2025 | Combines database and model signals for fine-grained semantic error detection. | Combine local plan mutation/value oracles with separately measured language judgments. No model access to rows or SQL; no wholesale port of its pipeline. |
| [Calibrating LLMs for Text-to-SQL Parsing](https://aclanthology.org/2025.emnlp-main.859/), EMNLP 2025 | Post-hoc calibration using structured sub-clause sample frequencies. | Measure selective risk and coverage; calibration is a later option with held-out labels, not a confidence threshold invented from this tiny study. |
| [Correlated Errors in Large Language Models](https://arxiv.org/abs/2506.07962), ICML 2025 per author record | Errors can correlate across providers and architectures. | Measure joint wrong acceptance, including across model families if an endpoint is available and authorized. Separate contexts or different model names do not establish independence. |
| [HEROSQL](https://arxiv.org/abs/2512.22744), December 2025 preprint; venue not verified | Hierarchical logical-plan/AST validation and structured negative-sample augmentation. | Borrow single-component plan mutations for diagnostic tests. A new trained graph verifier is not justified by current evidence. |

Older foundations remain useful: [CheckList, ACL 2020](https://aclanthology.org/2020.acl-main.442/)
motivates capability-specific behavioral tests;
[Dr.Spider, ICLR 2023](https://arxiv.org/abs/2301.08881) motivates paired question
and schema perturbations; [schema-linking re-appraisal, Findings ACL 2023](https://aclanthology.org/2023.findings-acl.53/)
shows limitations of exact matching in the studied parsers;
[AmbiQT, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.436/) motivates
logical rather than merely token-level candidate diversity. None establishes
that a lexical gate can be removed safely in this product.

## 3. Phase 0: freeze attribution rulers, without new model calls

Reuse existing fixtures and evaluators; do not introduce a semantic framework.
Draft a small new research annotation contract without changing v2 scores:

- Question meaning: clear / genuinely ambiguous / business definition missing.
- Required measure basis: operation, counted entity, DISTINCT and NULL behavior,
  and unit where relevant. Accept equivalent plans, not one metric identifier.
- Required population and polarity, including numerator/denominator roles.
- For concept-bearing spans: output action / business predicate / mention-only
  / unresolved. No span match alone proves the role.
- Candidate availability and the effective predicates of each reviewed metric.
- Gold labels must come from question plus reviewed definitions, not from the
  planner output, its verifier, or a coincidental fixture result.

Explicitly keep closed-world claims bounded: silence is not an automatic
`unrestricted` claim; incomplete interpretation stays unknown. A whole-answer
certificate would be a separate product/evaluation contract.

Roles are per occurrence, not one label per question: "Return the count of
returned transactions" has both an output action and a business predicate.
Include explicit all-population controls, negation targeting grouping rather
than population, and business predicates expressed without a vocabulary hit.

Prepare 36 development questions: six semantic families, a minimal pair in
each, and Chinese/English/Japanese equivalents. Include the known failure as
diagnostic material, plus genuine returns, non-return/exclusion, count versus
amount, quoted names versus selection, and non-POS service/cancellation cases.
Freeze 24 authored challenge questions from four different families before
calls. Separate families, not random translations, across splits. Reviewed
translations must preserve meaning; an author-frozen challenge is not a blind
real-user holdout. Do not reuse the unrun prior challenge for tuning.

Each clear question gets a correct plan and at least two one-change mutants:
wrong measure basis, extra/missing population restriction, reversed polarity,
or wrong operand scope as applicable. A mere dimension/alias trace must not
count as a correct population predicate. Ambiguous questions get multiple
plausible readings and an explicit unresolved oracle, not an invented winner.

Check values over three non-coincidental fictional instances: include NULLs,
repeated keys, zero/sparse populations and differing total/subset amounts.
Use hand expectations and the independent evaluator; local SQL execution
checks arithmetic, not natural-language correctness. Existing replay isolates
the current gate and a shadow no-gate counterfactual with all other checks
unchanged. Report wrong answers newly exposed as well as false blocks avoided.

Require a recorded distinguishing witness for each known inequivalent mutant;
three instances alone are not a coverage criterion. If none distinguishes it,
mark it not_distinguished, not equivalent. Respect schema/business constraints
and the existing strict comparator; do not use rounded soft matching as the
oracle. Check catalog transforms preserve effective metric signatures and map
opaque IDs back before existing gate replay.

Exit: meaningful rulers establish intended labels and existing failures.
Because this introduces a critical research grading contract, stop at the
ruler checkpoint for explicit follow-up before implementing that new grader.
Do not reinterpret the approved ratio-wrapper repair as authority for it.

## 4. Phase 1: controlled diagnosis, maximum 180 new calls

### P1: planner selection (36 questions x four arms = 144)

Keep question, supported algebra, model and decoding fixed. Freeze separate
research prompt/payload identities; leave production v15 untouched.

| Arm | Intervention | What it isolates |
|---|---|---|
| P0 | Current offered catalog and planner | Fresh matched baseline, not an old run's score |
| P1 | Add a reviewed **fixture-only** all-sale-row count equivalent to available raw COUNT; specialized metrics remain | Choice-set imbalance; this changes available reviewed knowledge and must be reported as such |
| P2 | P1 with opaque metric IDs, all definitions/names/bindings otherwise identical and IDs mapped back locally | Identifier-name priming, not full removal of lexical cues |
| P3 | P1 definitions rendered as uniform operation/entity/population/NULL/distinct cards with the same information | Representation, not more semantic facts or a new vocabulary exception |

Pair candidate order across arms where possible; log it. Do not attribute P1
gains solely to "reviewed preference": adding a candidate also adds useful
semantic description. P2/P3 help narrow, not completely identify, that cause.
If successful only on the known phrase, report targeted repair evidence only.
Evaluate selected-plan meaning before the lexical gate and final ask outcomes
after it; a refusal hiding a wrong metric is not a planner success.

### L1: contextual activation (36 questions x one arm = 36)

Use one research-only, question-first classifier with reviewed concept
definitions but no proposed plan or gold. Output the Phase-0 span roles and
unknown states. This changes the task/interface, not merely the prose in the
already-failed v2 extraction prompt. Obtain one result per question and replay
it against all fixed plans; those replays are not additional model observations.

Compare current lexical gate, shadow no-gate, and contextual activation plus
the separately tested predicate/scope checker. Measure activation errors and
plan-checker errors separately. Unknown cannot bypass an established check or
become an affirmative certificate. Do not automatically deploy a learned
classifier as an override for the current gate.

Use captured P0-P3 plans to cross planner variants with gate policies offline.
This isolates interaction without multiplying model calls by every gate arm.
No automatic correction: first determine whether detection is reliable enough.

## 5. Conditional experiments, not automatic expansion

P4: if correct candidates are available but selection still fails, compare a
fresh joint planner with a bounded typed-candidate selector on the same 36
questions (72 calls). The server offers distinct count/sum/population plans,
plus none/ambiguous choices; the model selects IDs, never writes SQL. Freeze a
schema-driven selection rule, cap candidates, and report gold candidate recall
separately from selection accuracy. Do not hide distractors or use gold to
construct a candidate list at inference. Hand-curated oracle candidates may
be a diagnostic ceiling only. Counterbalance order; prior v1 ranking already
showed order sensitivity, so this is not a claim that ranking is new or solved.

Separately report selection on an identical frozen pool, reusing captured pools
and offline baselines where possible. The end-to-end comparison above does not
isolate selector quality. Another model-based selector must replace a budgeted
arm or receive a revised budget. Include all-wrong pools and abstention cases.

Only a surviving candidate proceeds to confirmation: baseline versus one
frozen winner, two separated sessions on 36 development questions (144 calls),
then once on the 24 frozen challenge questions (48 calls). Total maximum is
180 + 72 + 192 = 444 new calls, with conditional portions unspent on failure.
If both independent tracks qualify, confirm one first; budget a second
confirmation explicitly instead of quietly multiplying this allocation.

Reasoning, larger N, model-family comparisons, calibration training and
fine-tuning are not extra arms hidden in this budget. A new model family is
worth testing only against a frozen task and with measured error overlap;
availability, destination and authorization must be checked first. Full
legacy/live acceptance is a later separately costed step, not part of these
444 calls. Session/load effects are hypotheses; two sessions cannot prove
the endpoint batching mechanism caused a change.

## 6. Metrics and decisions

Report every numerator/denominator, by language, family and catalog arm:

- Candidate recall on clear expressible requests; selected semantic correctness
  conditional on availability, and unconditional end-to-end correctness.
- False-block rate = correct fixed plans refused / correct fixed plans tested.
- Omission escape = plans missing required predicates allowed / such mutants.
- Joint wrong acceptance = wrong planner outputs allowed / wrong outputs;
  separately count affirmative certification and merely not-blocked/unknown.
- Served risk = wrong answered requests / answered requests; correct coverage =
  correct answered requests / clear answerable requests. Count request-level
  outcomes, not three synthetic database instances as three independent users.
- Unnecessary clarification on clear requests; appropriate clarification on
  genuine ambiguity or missing definitions; transport/format failures separate.
- If repair is later tested: wrong-to-right and correct-to-wrong transitions,
  with both conditional and all-request denominators. An assumption is not a fix.
- Calls/request, tokens, p50/p95 latency, paired changes and semantic-core
  stability. Identical wrong answers remain errors.

Development screening (not a release guarantee): improvement on at least two
semantic families for the targeted metric, no lost correct controls and no new
known wrong acceptance or missed-ambiguity controls. Pre-register before calls;
retain negative results and do not keep tuning until the challenge passes.
Confirmation must retain the direction of improvement across both sessions
and the frozen challenge. Small authored samples and zero observed failures
cannot establish a production error bound. Show uncertainty clustered by
semantic family; do not treat translations or replays as independent samples.
With only six development families, prioritize raw paired transitions and family
counts; bootstrap intervals cannot support a precise release-risk conclusion.

Decision branches:

- Catalog-only gain: improve reviewed catalog coverage/presentation first;
  do not build a second model or a broad schema-linking subsystem from it.
- Contextual gate improves false blocks but adds escapes: no promotion.
- Both models misread the same clear request: no majority-vote certificate;
  investigate representation or a genuinely different detector.
- Genuine ambiguity/missing definition: clarify the disputed business choice;
  do not ask users to resolve a clear imperative merely because Gemma misread it.
- No survivor: publish the limit and stop this experiment; consider a separately
  scoped model comparison or reviewed metric-choice interaction.

Changing a production gate, verification status, or semantic certificate needs
its own ruler/approval and affected-case validation. Preserve type checking,
SQL policy, authorization, PII controls and all existing deterministic scope
checks. Do not install a keyword exception list or an ontology framework.

## 7. Execution and evidence handoff

Future execution must reference the owner's actual model/DB authorization, not
this document. Proposed destination is the existing configured Gemma gateway;
outbound data is fictional questions, value-free schemas and reviewed synthetic
definitions/typed candidates only. No customer rows, SQL, secrets or gold labels
go to the model. Opaque credential reuse, serial shared-endpoint calls,
temperature 0, reasoning off, max_tokens 4096, timeout 60 s, no automatic retries;
all attempted calls count against the budget. Abort on unexpected exposure.

Prefer local fictional data; no new database or administrative action is needed
for initial diagnosis. If later doing PostgreSQL confirmation, use read-only
SELECT over synthetic data and opaque DSN environment names. No credential
copying or plaintext inspection. No real-DB sampling in this study.

Reuse the existing research harness where practical; add only bounded helpers
and new rulers, never mutate historical scores. Record source and input digests,
prompt identities, offered candidates/order, model configuration, per-stage
decisions, seeds, attempted calls and redacted artifacts. Keep challenge sealed
until its gate. Produce one research note and durable aggregate evidence,
explicitly separating recorded replay, fresh model calls and DB validation.

Current completion: literature search and this plan only; existing dirty work
preserved. Next executable slice is Phase-0 rulers, not production gate removal.
