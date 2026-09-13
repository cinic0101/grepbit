# Scoped positive names and normalization collisions

2026-09-13, baseline `658f1f6`. Owner approved the two behavior changes after
the initial ruler; exact reply recorded in `../plan/name-boundaries-ruler.md`.
Root owned the coupled implementation, no delegated writer. Local commit
authorized, no push. Only read-only PostgreSQL VALUES over fictional data used.

## Decision and mechanism

Keep both deterministic repairs. Nested model-authored EQ/IN conditions on
overlay-opted-in visible TEXT columns now receive the same binding assurance
as NE. Selection and replacement share the existing filter traversal. Operators,
operand versus common-population scope, SQL NULL semantics and reviewed
definitions remain unchanged. Unique candidates are checked again against the
DB, recompiled and passed through SQL policy; unresolved names clarify before
execution. Exact stored literals remain authoritative. No new keyword rules,
SQL constructs, model calls, dependency, service or abstraction were added.

Normalization previously deduplicated by normalized text, merging distinct
stored names such as `Harbor-East` and `Harbor East`. Both insertion orders now
retain both entries and report a normalized-only `harbor east` lookup as
ambiguous. A raw exact match still selects itself, even outside the candidate
display cap. Hints preserve colliding alternatives; ordering is deterministic.
The cap limits displayed candidates, not the ambiguity decision.

`ask-orchestration-v5`, `grounding-bigram-v2`, production prompt v15 unchanged.
Internal `negative_columns` parameter renamed to `grounded_columns` because
it now authorizes all three operators in nested scopes; callers were updated
together. This is not a new public API or overlay schema.

## Evidence

Private root `.artifacts/examples-restatement-20260913/`:

- Initial ruler: 10 intended assertion failures, 9 controls pass.
- Expanded tracked ruler: 29 intended assertion failures, 9 passes before
  repair; all 38 pass after. No setup errors, skips or xfails disguised as red
  contract evidence. Red JUnit files remain unchanged.
- Combined new/existing name-binding controls: 115 pass. One former assertion
  pinned unchecked nested EQ; it was explicitly superseded to require both
  authorized operands to bind independently, without changing their scopes.
- Additional seven-way normalized collision, both insertion orders: 2 private
  tests pass; all seven hints survive, display stays capped, exact values win.
- PostgreSQL compiled VALUES queries: 15/15 agree with independent hand values
  and DuckDB, covering EQ/IN/NE at plan, measure, numerator, denominator and
  without scopes. Includes mixed IN and NULL-bearing rows; no persistent write.
- One broad offline gate: 1,796 pass, zero errors/failures/skips. Static pass.

## Limits

These are deterministic execution/binding tests, not a live name-understanding
score. The concurrent examples/restatement experiment has no opted-in names
and must not be counted as a live grounding regression. Prior 48-call negative
binding results belong to the prior revision, not this new slice.

Preserving colliding hints prevents index-level data loss. It does not prove
that a model chose the intended entity when it emits one exact candidate.
Bigram matching can still select an unintended unique candidate in an unseen
catalog; assumptions remain candidate evidence, never intent certification.
The accepted no-candidate clarification tradeoff and privacy policy stay in force.
