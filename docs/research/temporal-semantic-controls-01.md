# Temporal generation and semantic metadata: bounded controls

2026-09-13, baseline `69f6b57`. Protocol:
`../plan/temporal-and-semantic-controls.md`. Runtime ask v5 / grounding v2 /
`plan-classify-json-v15` unchanged. Research arms have separate revisions in
the frozen manifest; no production prompt, overlay, gate or scoring change.
Private artifacts: `.artifacts/temporal-semantic-controls-20260913/`;
durable manifest: `../../evidence/temporal-semantic-controls-01.json`.

## Result and decision

132 scheduled executions completed in 133 actual Gemma4 31B calls, serial,
T=0/thinking off. One validation repair, zero transport errors/retries. All
contexts, independent oracles and source identities match at end. Both research
screens fail; neither intervention is promoted. A narrow missing-definition
metadata benefit is retained as evidence, not a generalized improvement.

| Study / arm | Primary accepted | Fixed later accepted |
|---|---:|---:|
| A, unchanged planner | 7/8 | 1/2 |
| A, neutral instruction | 8/8 | 2/2 |
| A, year-literal instruction | 6/8 | 1/2 |
| B, unchanged metadata | 24/30 | 2/4 |
| B, neutral metadata | 24/30 | 2/4 |
| B, semantic metadata | 25/30 | 3/4 |

Accepted means the predeclared full-recipe/value/disclosure rule passes, or
the case's predeclared refusal is returned. In B each primary arm has **22
accepted answers**; the change from 24 to 25 is one additional correct refusal,
not one more answered question. Unknown recipes are not automatically wrong.
These are authored/reused questions, not independent user holdouts. Repetitions
in one run are not independent session samples or population confidence bounds.

## A: error origin is known; the proposed instruction is not a repair

The existing adapter already converts a date-column EQ filter containing a
four-digit year into its calendar-year range. The targeted research instruction
asked the model to use that existing form, retaining grain and omitting scope;
other windows were explicitly left on their ordinary forms. There was no new
wire format, arithmetic function or rejection rule.

- Both original Chinese baseline executions contain **2060-01-01 in the raw
  model response**, with the same scope hash before/after adapter and in the
  final plan. This localizes the bad boundary to generation, not a date computed
  by the normalizer/compiler. It does not explain why decoding chose those
  tokens or establish endpoint batching as the cause.
- Neutral text rescues both original executions without teaching year handling.
  Do not adopt neutral text as a fix: this small control only shows that added
  context can change the result, not that its contents improve understanding.
- The targeted arm initially rescues the Chinese original **using an ordinary
  range, not the requested year-EQ mechanism**. On the scheduled later repeat
  it emits both a year filter and a current-year scope, and is refused.
- Of ten targeted executions, three emit a year EQ: one uses it with no scope
  and passes; two also emit a scope and fail `plan_filter_kind_mismatch`.
  Another explicit-2025 question uses the current-year relative scope and
  remains unassessed by the frozen grader. Finite offline hash reconstruction
  identifies `unit=year, offset=0, length=1`, meaning 2026 at the frozen as_of.
- Month, relative-period and cross-year range controls otherwise pass. The
  targeted arm still loses two previously accepted primary cases and has no
  gain over neutral, so it fails the predetermined screen.

Post-observation mechanism tests confirm current behavior: a raw 2060 range
survives adapter normalization and is clamped by the compiler; a year EQ does
not override an already supplied scope. That refusal protects against ambiguous
representations. Do not repair these experiment failures by silently choosing
one of two time authorities.

Next temporal work should start with a **proposed ruler**, not another prompt
variant: one authoritative, question-bound calendar reference, with server-owned
boundaries, limited initially to unambiguous explicit years. Multiple years,
relative windows, growth widening, date roles and missing evidence need controls.
Whether to introduce that research format and its fallback remains a separate
compatibility decision; nothing here implements or approves it for production.

## B: schema support information helps one missing-definition question

The 24 frozen challenge-v2 questions were combined with four existing
component-exclusion questions, missing-lease-population and English record/entity
count regressions. Baseline was not at the ceiling, so the planned neutral and
targeted arms and four fixed later repetitions ran. Comments changed only in
memory; column identities, policies, questions, data and value oracles stayed
paired. Neutral text is a perturbation control, not token/length-matched proof.

The sole incremental success is `cov_leased_fee`, twice. The targeted column
description explicitly says monthly fee does not encode lease membership and
that this datasource has no recorded lease membership/reviewed definition.
The model returns `semantic_gap`; baseline and neutral still sum all devices.
This supports supplying **what the schema does not establish**, not inferring
that a monthly charge proves leasing. It does not demonstrate the effect across
multiple absent concepts or datasets, and the case was already known.

The component controls pass baseline here, leaving no incremental benefit to
attribute to component comments. The four reused questions run over small
synthetic payroll/goods/service schemas; particularly payroll is not an identical
context rerun of the earlier full-POS study. No claim that the historical
component-scope failure has been permanently fixed follows.

English imperative `Return` remains blocked by `concept_not_mapped` in every
arm for both the new row-count case and the existing row/unique-ticket case.
Two separate offline tests show the frozen correct count plans themselves hit
the lexical gate. Column comments cannot change this gate: it checks language
triggers against selected identifiers/metrics/segments, not their comments.
No bypass, keyword exception or same-model verifier was introduced.

The screen requires incremental benefit beyond neutral across more than one
semantic family, with refusal controls retained. Only missing population gains,
and one expected name clarification remains answered. Therefore B is not
promoted as a general semantic fix. The localized support-description result is
worth a future multi-concept/multi-datasource check, not a broad prompt rollout.

## Names expose an evidence boundary, not a new binder regression

All arms preserve ordinary ambiguous-prefix and nonexistent-negative-name
clarifications. For normalized collisions, the model instead emits IN over
both exact stored spellings and the runtime accepts their union. This fails
the frozen authored clarification oracle. Exact binding of both literals is
nevertheless consistent with the current binder's contract; the binder does
not certify that the question asked for their union. Preserving candidate
ambiguity through model selection is a distinct product-policy question.
Do not call this an arbitrary first-candidate bug or an approved new gate.

Two exact-name questions remain unassessed because they count depot entities,
where the frozen oracle counts service records. Their wording did not name the
counted table clearly enough, and the three original instances happen to give
the same count for these two interpretations. They are **not established model
errors**. Three post-observation extra-child witness tests distinguish the two
counts, without changing any live fixture, oracle or score. A later panel must
make counting units explicit and independently review ambiguous readings.
The earlier 63 checks only distinguished the specific foils they included;
they were never evidence against every alternative plan.

## Evidence and scope

- Frozen 114 case/arm contexts; 366 interpretation-instance SQL comparisons
  before calls and again in end checks (105 PostgreSQL, 261 synthetic DuckDB
  per preparation). Three instances for synthetic answers. These are bounded
  oracle checks, not a transactionally shared snapshot of all DB rows.
- 143 focused tests pass, including new measurement/analysis controls and seven
  post-observation mechanism checks. Static passes. Previous offline 1,796 is
  reused only after source digest and stored artifact SHA-256 verification.
- Original owned clients close per invocation, including repair. Raw response
  content remains in memory; only allowlisted temporal facts and hashes are
  persisted. No real POS rows/values, credentials, SQL or DSNs go to the model.
- No failed research helper or temporary abstraction enters runtime. Documentation
  and value-free manifests are committed locally; scripts and detailed artifacts
  remain private. No production fix, legacy regrade, new release claim or push.

Next order: temporal reference ruler proposal; separately broaden reviewed
schema-support metadata beyond the known leasing example; resolve name-union
versus-clarification policy before any related runtime change. The lexical
gate remains a documented false-positive source, not something this metadata
experiment solved. A5 broad acceptance and A4 measured need remain open.
