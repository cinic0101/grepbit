# Evaluation and improvement loop

## Asset boundaries

`evals/fixtures/learningops/` holds a new fictional development fixture.
`evals/cases/` and `evals/oracles/` are evaluator-only assets. Never include gold
answers, case expectations or reference SQL in evaluated-model context or in
runtime discovery. Coding agents may read them to develop tests.

Unify the fixture family, not one mutable database file: core seed; isolated
issue scenarios; later deterministic stress variants. Extend data before schema,
and schema before inventing execution primitives. A genuinely different domain
may need an extension fixture rather than a distorted LearningOps table.

Expected values are authored independently of candidate runtime results. The
current SQL references and separate Python ledger have different algorithms but
were authored together: this is NOT independent human oracle review. Freeze and
review expectations; an oracle correction is a separately explained revision,
not a retrospective upgrade of historical results.

## What P0 actually checks

The current command builds/checks a synthetic SQLite instance. It runs 18 SQL
references, integrity/foreign-key/catalog checks, a Python ledger, read-only write
rejection and four isolated variant controls. Reports enumerate every executed
check and list 12 behavioral descriptions as `not_implemented`. There is no model
adapter or product evaluator. Do not report 30/30 product passes.

Reports include source-file hashes, aggregate source identity, DB digest,
Git commit/dirty state when a checkout is available, Python/SQLite versions,
as_of/timezone, outcomes, elapsed time and zero live attempts. Outside a checkout,
Git identity is null rather than invented. Hashes identify content, not authority.
A failed reference yields a failed report and nonzero exit; unrelated checks
continue. Missing/malformed assets abort with nonzero exit; a reserved report stays
incomplete (or unparsable if interrupted), never successful. Output is exclusive-create.

The checker trusts the committed fixture SQL and is not an arbitrary-SQL sandbox.
Its detailed diagnostics are for synthetic data only, not a live logging policy.

## Product evaluation contract to implement in P1-P3

Evaluate four dimensions separately: interpretation/binding; fact correctness;
request coverage/response faithfulness; operational/maintenance cost. Compare
results, not SQL strings. Preserve duplicates, required order/ties, NULL and
units; use declared numerical tolerance, not universal float coercion.

Use explicit product outcomes: complete_correct, partial_correct, wrong,
necessary_clarification, unnecessary_clarification, necessary_refusal,
false_refusal, unassessed, operational_failure, and not_implemented. Keep the
reason and promised-scope denominator. Report coverage and operational failures
separately from assessed semantic accuracy. Unassessed is neither pass nor wrong.

Track failed required facts separately from optional gaps. Synthesis claims must
reference input facts; any new arithmetic is a server-derived fact. Do not use
an LLM judge as the sole numeric/semantic oracle. Reconciliation is conditional
on compatible population/time/unit/coverage/snapshot, and may share an omission.

For live runs add model/deployment identity, prompt/config/recipe/semantic
versions, data-scope approval, attempt/retry counts, tokens (unknown if missing),
latency, fixed budget, stop reason and execution-origin classification. Include
all attempts, not only the eventual successful one. No hidden provider fallback.
Formal tests use the same future runtime path as serving, not a second planner.

## Issue workflow

Use GitHub Issues as the single active-work tracker. Start with one roadmap
issue and three P0 issues. Use the templates in `.github/ISSUE_TEMPLATE/`.
No labels, Projects automation or milestones are prerequisites for starting.

Observed -> triaged -> reproduced -> expected semantics reviewed -> fix/scope
choice -> targeted/protected regression -> original-source replay -> closed.
Use issue body checkboxes/comments for these states; no large duplicate work log.

Triage: missing definition, ambiguity, model selection, recipe coverage,
compiler/executor, verification, synthesis, oracle defect, operational issue, or
unpromised enhancement. Do not automatically add a verifier for every failure.
A normal bug requires an issue, minimal regression and PR/commit. Add a decision
note only when semantics, scope, security or architecture changes.

Each issue records original evidence privately where necessary, public synthetic
reproduction, expected behavior, phase/promise, code/data identities, candidate
budget, affected tests and closure evidence. If reproduction is missing, keep
that status. An authored case is not a successful reproduction.

## Real-data feedback and RSI foundations

Owner observation -> public-safe synthetic scenario -> demonstrate old failure
-> minimal semantics/recipe/code fix -> targeted + neighboring/protected tests
-> owner replay on the original source -> regression asset. A merely similar
synthetic failure is a hypothesis until confirmed. Never publish real schema
comments, credentials, names, literals, screenshots or row dumps by default.

Once feedback informs development it is no longer unseen. Keep fresh real-data
questions for generalization and report first-run and post-fix outcomes separately.
Do not tune on a "holdout" then retain its holdout label.

Measure both product improvement and improvement of the repair process: unseen
repair success, time/attempts, human intervention, regressions, production code
changed, new operators/repairs and semantic/recipe complexity. Persist learning
in reviewed repo artifacts, not an assumption that chat memory or weights update.

A repair agent may propose new tests or an oracle/grader correction, but cannot
unilaterally rewrite the gold and promotion criteria and certify its own gain.
Keep acceptance review separate. These are prerequisites for recursive improvement,
not evidence that RSI has already occurred.
