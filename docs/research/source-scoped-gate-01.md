# Source-scoped concept gate: offline screen rejects both variants

2026-09-14, baseline `4d0152a`. Protocol:
[source-scoped gate screen](../plan/source-scoped-gate-study.md).
Production, prompt v15, ask v5, overlays and historical scores are unchanged.

## Decision

**Do not promote datasource applicability as the gate replacement. No new Gemma
calls or live follow-up.** B rescues three false refusals but releases two wrong
answers that A blocked. C is conservative and exactly preserves A's behavior,
including false refusals; it has no improvement to validate live. D confirms why
global concept removal is not an acceptable substitute. These results meet the
predeclared stop condition; no extra absence entries or wording exceptions were
added to make the candidate pass.

## What was actually measured

**24 question/plan pairs, not 24 new model answers.** They cover 14 distinct
question strings in 15 question/datasource contexts. Some questions are tested
with both correct and deliberately wrong plans, and two with historical captured
plans. This is an intentionally adversarial safety screen, not a frequency or
product-accuracy estimate.

Three inputs are model-derived: two complete historical plan hashes recovered
exactly (English output count, Chinese wrong return-count selection), and the
prior IoT i01 canonical plan with its public month recovered only after matching
the retained hash. The other 21 are authored injections/controls. In particular,
the missing-cancellation unrestricted total is **not** described as a captured
model answer: that prior live case had refused without a plan.

The semantic-bottleneck fixtures provide four instances per synthetic pair,
including empty data; IoT uses the existing fictional PostgreSQL fixture once
per pair. Across four arms: **96 pair/arm results, 360 ask executions**, zero
model calls. Repeated instances are value checks, not independent questions.

| Arm, 24 pairs each | Correct answer | False refusal | Wrong answer | Correct block of wrong plan |
|---|---:|---:|---:|---:|
| A current global concepts | 7 | 7 | 3 | 7 |
| B disable explicitly confirmed-absent concepts | 10 | 4 | 5 | 5 |
| C retain supported and confirmed-absent concepts | 7 | 7 | 3 | 7 |
| D no concepts, diagnostic only | 14 | 0 | 10 | 0 |

The catalog is root-reviewed **research data**, bound to exact datasource/schema/
overlay fingerprints, not an owner-signed production catalog. Supported facts
come from the existing returned-record definition and cancellation flag; absent
means no reviewed definition in the supplied reservation/IoT contract, not a
claim that the event can never occur. Unknown or invalid catalog entries retain
current behavior. No concept words or matching algorithms change.

## Paired gains and harms

B rescues:

- Missing-cancellation datasource, unrestricted total explicitly saying **not**
  to restrict to cancelled reservations.
- Same datasource, unrestricted total quoting "cancelled reservations" only as
  a report title.
- Existing IoT i01, whose **return** is an output verb and whose plan is correct.

B newly releases:

- Missing-cancellation datasource, genuinely asking for cancelled-reservation
  fees but receiving an unrestricted total.
- IoT, genuinely asking for alerts caused by product returns, without a reviewed
  way to identify that population, receiving the same unrestricted July counts.

It still falsely refuses output/negated/quoted mentions where the datasource
does support the returns concept. Source applicability does not remove the
within-datasource role ambiguity. C retains all seven false refusals. D rescues
them but additionally releases all seven originally blocked wrong inputs.

## Why applicability alone is insufficient

Three fixture pairs have an identical feature signature: datasource catalog,
canonical plan and triggered-but-unmapped concept IDs. Their required decisions
are opposite:

1. All reservation fees, **do not restrict to cancelled** / only cancelled fees.
2. All reservation fees, **cancelled as title text** / only cancelled fees.
3. **Return** July alert counts / July counts restricted to **product returns**.

Tests confirm these signatures and opposite authored intent requirements. This
is not a claim that the full questions are indistinguishable: their wording is
different. It establishes the limitation of a policy that adds only datasource
support facts to the current presence-based concept check. It still has not
established whether this question requires the business restriction.

The captured Chinese wrong return-count proposal survives all four arms; the
concept is already represented in that plan. This preserves the other half of
the problem: gate false positives and planner intent errors are separate, and
fixing one does not certify the other.

## Is the gate a bottleneck?

**The lexical concept gate is a confirmed correctness/coverage bottleneck on
these cases**, with causal same-plan counterfactual evidence. This does not
implicate read-only permissions, SQL policy, identifier validation or parameter
binding; those checks remain unchanged and necessary.

It is not yet established as the dominant bottleneck in the user population.
The latest explicit authored baseline had one gate false refusal among 20
answerable cases. The retained 95-owner-question audit had no recorded concept-
gate refusal, while it had other limitations and unanswered intent questions.
Neither the enriched 24-pair safety screen nor that missing exposure observation
is an unbiased estimate of global impact. See `gate-exposure-01.md` and
`db-aware-baseline-01.md` for their denominators.

## Next boundary

Stop this source-only candidate; keep the current gate pending a demonstrated
replacement. Preserve the counterexamples as requirements for future work,
without creating more runtime machinery. Do not rebrand the failed same-model
intent certificate or broad metadata placement experiments.

If reducing these refusals remains the priority, the next proposal must identify
**what new request-role/scope evidence it adds**, where that evidence comes from,
and what it does when the evidence is uncertain. Catalog availability is useful
context but not that evidence. A request-role model would remain a probabilistic
candidate, not an independent certificate; trusted explicit scope input would
be a different interface/product decision, not something to assume silently.
No correction cards or human-in-the-loop UI were introduced. New genuine user
questions can separately measure the frequency/cost of the known failures.

## Validation and artifacts

Research ruler: **2 intended failures, 13 passes** on unchanged selection; root
reviewed that checkpoint under the owner's explicit autonomy authorization.
The private implementation passes all 15 selection/identity/fallback tests.
Final focused gate: **25 passed**, including 10 post-run integrity/collision
checks. Static passes. The exact-source/hash-matched **1,841 offline tests** are
reused, not rerun or claimed as live model evidence.

All frozen valid plans match independent PostgreSQL SQL; wrong numeric plans
have a distinguishing fixture. Missing definitions use refusal requirements,
not invented numerical subset answers. Synthetic ask executions use DuckDB;
every answered synthetic execution is separately cross-checked in PostgreSQL
with inline VALUES. IoT ask executions use the actual PostgreSQL adapter.
Correct answers must retain the same allowed interpretation across instances.

Only existing `grepbit_ro`, sampling 0, readonly SELECTs; no DB writes, provider
calls, raw rows/completions/credentials in artifacts, dependency or runtime edits.
Input, selected oracle and runtime hashes match before and after. Private files:
`.artifacts/source-scoped-gate-20260914/`; durable counts/hashes:
`../../evidence/source-scoped-gate-01.json`. Historical studies remain immutable.
Tracked delta is protocol, report, manifest and roadmap. No public format,
security boundary, identity contract or production evaluation rule changed.
Local commit only; no push.
