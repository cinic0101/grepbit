# Disclosed-answer acceptance: bounded implementation

2026-09-13. Baseline `89060ae`. Owner approved the acceptance ruler and
implementation. Evidence: `../../evidence/answer-acceptance-01.json`.

## What changed

The compiler uses its effective expanded lineage to describe the actual
population, measures, grouping, time column/comment, business timezone and
windows in the existing assumptions field. Metric time overrides are visible.
COUNT/DISTINCT and fractional growth conventions are explicit. Misleading
"every row counts" assumptions no longer accompany metric/operand/default
restrictions. No SQL semantics, prompt, gate, verification level or API field
was changed; this is not the retired calculation-card product.

The optional `--acceptance-rules` grader is separate from legacy `correct`.
Trusted annotations predeclare acceptable complete plans, relevant supplementary
outputs and independently authored full-output value queries. It prepares all
references before planning, checks semantic context and actual disclosure,
then matches the compiled recipe and every value. Cosmetic measure aliases are
ignored, not predicates or time bindings. Unknown interpretations are unassessed
unless a reviewed closed set explicitly excludes them. No model judges itself.

## Evidence and interpretation

- 36 focused acceptance tests pass. They include runner-level default/legacy
  separation, freezing references before planning, context mismatch and row
  redaction, plus positive and adversarial controls.
- Predeclared narrow/broad engineer interpretations can pass with truthful
  scope; unspecified payroll can use either approved time role. Explicit
  payment-time requirements reject attribution-time plans even if disclosed.
- Correct related growth can pass without dropping it; wrong growth, missing
  or duplicate rows, unrelated columns, false disclosure and coincidentally
  equal values under a different binding fail. These are authored fixture
  tests, not measured user acceptance or model improvement.
- A seeded 500-input comparison against the baseline compiler produced 67
  invalid plans, 313 compiled pairs and 120 typed-refusal pairs. Zero differences
  in executable query/bindings, output columns, verification, periods, applied
  segments, coverage-model plan payload or refusal codes. Assumptions
  intentionally differ; interpretation does not. This is
  bounded regression evidence, not an exhaustive equivalence proof.
- The first broad gate found one stale interpretation assertion, revealing that
  the coverage model also consumes this field. Detailed disclosure was moved
  to assumptions, leaving interpretation and coverage-model input unchanged.
  The failed run remains recorded; the final gate was rerun after this repair.
- Final static PASS; offline **1,693 passed**, zero failures/errors/skips.
  Evidence and source identity are under
  `.artifacts/answer-acceptance-20260913-implementation/{static-final,offline-final}`.

## Boundaries and next work

This solves an evaluation/disclosure gap, **not** the planner's wrong choice of
meaning. Researchers still approve the interpretation sets before inspecting
candidates. Units unknown to metadata are not invented. v1 conservatively
declines LIMIT/truncated results and follow-up annotations, and exact compiled
recipe matching is not universal semantic equivalence. Use static fixtures:
reference and candidate execution are not snapshot-coordinated.

No live Gemma or database call was made in this implementation slice. The old
292-case results remain unchanged. The independent public-name grounding and
payroll-metadata studies in `../plan/answer-acceptance-and-cause-studies.md` are
next; neither has been run or declared successful by these offline tests.
