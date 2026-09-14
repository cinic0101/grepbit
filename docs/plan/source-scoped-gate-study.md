# Source-scoped concept gate: bounded offline screen

2026-09-14, baseline `4d0152a`. The owner approved the proposed next round and
asked whether the gate is a bottleneck. Existing authorization covers autonomous
research checkpoints, needed psql/Gemma calls and local commits; no push.

## Question and boundaries

Can reviewed datasource applicability remove false concept refusals without
releasing wrong plans? This is not another metadata-text/prompt experiment.
Only the in-memory concept list supplied to existing `ask()` varies. Production,
language words, overlay, planner, compiler, grounding and graders stay unchanged.
No new public configuration or model-based intent certificate.

The experimental catalog is authored and root-reviewed from existing fictional
fixture definitions. It binds datasource, schema and overlay fingerprints; it
is not an owner-certified production catalog. States concern available reviewed
query definitions, not whether a business event can occur in the real world:

- supported: an existing reviewed fixture definition expresses the concept;
- confirmed_absent: the supplied fixture contract has no reviewed definition;
- unreviewed: no claim. Missing, incomplete, stale or mismatched configuration
  retains the existing concept gate, never silently disables it.

## Arms

| Arm | Concept list |
|---|---|
| A current | Existing global concepts |
| B supported-only | Disable only concepts explicitly confirmed absent in a valid catalog; supported/unreviewed keep existing checks |
| C supported-or-absent | Retain both supported and confirmed-absent concepts, unreviewed falls back to current behavior |
| D none | Empty concept list, diagnostic control only |

C deliberately tests the conservative alternative; with this fallback it is
behaviorally identical to A. B/C cannot distinguish grammatical roles within a
datasource. No new lexical exceptions or newly authored absence-trigger words.
Existing overlay absence checks remain in place; no absent-concept entries are
added to conceal errors revealed by this screen.

## Panel and acceptance

Freeze before execution: six existing Chinese/English output/business/both-role
questions with correct and wrong plans, defined/missing cancellation controls,
neutral/negated/quoted mentions, the captured IoT i01 plan and a real-business-
scope counterexample on the same schema. Include exact-hash-recovered historical
correct and wrong model proposals separately from authored injections. Missing
plan traces are never described as actual model proposals.

Use the existing fictional multi-instance fixtures and independent reference SQL;
reuse the actual IoT DB with `grepbit_ro`, sampling 0. PostgreSQL access is only
SELECT/metadata or inline VALUES through the existing role and opaque DSN env.
Retain hashes, codes and counts, not raw rows, credentials or completions. No
Gemma calls in the offline phase. The unchanged 24-question baseline is existing
live evidence, not rerun accuracy or 24 new independent user requests.

Report correct answers, correct blocks of known wrong plans, false refusals and
wrong answers separately, including paired rescued/harmed case IDs. Evaluate
the same allowed interpretation across all instances; fixed wrong injections
are safety controls, not estimates of model failure frequency.

A candidate proceeds only if it rescues at least one existing false refusal,
introduces no false refusal and no wrong-answer release relative to A, and
preserves all previously blocked omission negatives. If B fails, do not repair
it with ad-hoc entries or run a live wording search. If C has no gain, do not call
unchanged behavior a successful replacement. Stop this candidate and report why.
Any later live slice requires a separately frozen budget/panel after this screen
passes; the authorized conditional next step is not an obligation to spend calls.

## Work record

Private code/specs/results: `.artifacts/source-scoped-gate-20260914/`. First run
catalog-selection rulers against the unchanged selection stub, inspect intended
failures, then implement the research-only selection function under the owner's
delegated checkpoint authority. Final report, manifest and roadmap enter Git;
no runtime or historical evidence edits. Focused tests, static and exact-source
offline evidence reuse form the closeout. Completion may be a decisive rejection
of source-only applicability, not deployment of a replacement.
