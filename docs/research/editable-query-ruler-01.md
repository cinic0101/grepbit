# Editable-query Stage-0 rulers: contract ready for review, oracle gap exposed

2026-09-12. The ruler phase requested by the owner is complete. It does not
implement a calculation-card renderer, editor or confirmation runtime. It does
not measure human comprehension or approve a production behavior change.

Scope: `../plan/editable-query-stage0-rulers.md`; executable vectors in
`tests/fixtures/editable_query_rulers.json` and
`tests/contract/t0/test_editable_query_rulers.py`. Baseline clean dev `8c9e7c5`.
Root sole writer; no src/evals modifications, model calls, external DB calls,
credentials, packages, participant contact or push. Standing local-commit
permission applies; post-ruler implementation still needs explicit approval.

## What is specified

Nineteen hand-written calculation cards use the three existing fictional POS
and work-log instances. They expose row/non-NULL/distinct count, sum, reviewed
metric predicates, common and operand scope, ratio direction, default/named
segments, labels, verification levels and empty/NULL behavior. Business labels
are fixture data, not question-trigger rules in production code.

Whole-candidate edits preserve common filters and the other operand, but replace
the selected operand's complete definition, including its old extra filters.
This must be presented as a complete-calculation replacement, with removed
restrictions visible, not a deceptive basis-only toggle. No-op and invalid edit
leave state intact. A changed label still invalidates the reviewed display.

Review binds full source/context, effective calculation, display/catalog and
gate state, plus a monotonic revision. A -> B -> A does not revive an old review.
Unknown choice, timeout, missing definition, agent inference, stale identity and
refusal cannot become a human confirm event. Confirmation never upgrades the
verification level or proves that the person understood the definition.

There is deliberately no fake failure caused by importing a nonexistent editor.
Hand cards and transition/identity truth tables establish the new specification;
they are not the future implementation. After approval, actual rendering/editing
functions must be checked against independent facts and these vectors.

## A real reference-evaluator defect, not a failed new UI

The current compiler processes both `exclude_segments` and `named_segments`.
When one operand selects the named segment, its inverse still restricts the
other operand. The reference accepts `named_segments` but never uses it; its
segment loop only consumes `exclude_segments`.

Example plan: numerator is reviewed `return_count`, denominator is raw row
count, with the fictional returns segment explicitly named. The pre-existing
contract excludes return rows from the denominator because only the numerator
references the segment's column. These are computation-contract controls, not
a new definition of the ambiguous business term "return rate".

| Instance | Numerator / intended denominator | Hand + compiled SQL | Current reference |
|---|---|---:|---:|
| coincidental | 2 / 2 | 1.0 | 0.5 (2 / 4) |
| asymmetric | 3 / 2 | 1.5 | 0.6 (3 / 5) |
| null_zero | 1 / 2 | 0.5 | 0.3333… (1 / 3) |

All three failures are actual numeric assertion failures. No setup/import errors,
timeouts, skip or xfail masks them. Named-segment lifting for a plain count and
the default-excluded ratio both pass, locating the gap in the named operand-
level path. The expanded hand-fact plans pass both engines because their
denominator predicate is explicit, not dependent on the omitted named argument.

No implementation is repaired in this ruler-only slice. Stage-0 value readiness
is false until the existing reference contract is repaired and revalidated.
This does not rewrite old differential scores; their generator/coverage limits
must remain attached to their historical claims.

## Existing display and identity counterexamples

The current interpretation sentence says `metric return_count`, without
expanding its defining predicate. The predicate exists in lineage; the existing
complete response is not alleged to omit it everywhere. Nevertheless, copying
only that sentence is insufficient for the proposed full calculation card.

An identical plan and interpretation can produce different values under default
segment state. A semantic candidate ID can remain stable when its reviewed
description changes. A label edit can leave `plan-core` unchanged. Therefore
neither plan-core equality, candidate ID nor interpretation text alone binds
what was reviewed. The proposed identity is local research state, not a secure
authorization credential or a production DB snapshot guarantee.

Actual ask controls remain unchanged: the Chinese output-count and work-log
unit mistakes are served; the correct label-only plan is refused by the current
concept gate. Three local workflows, two SQL executions, zero new model calls.
This preserves the baseline problems instead of bypassing gates for a UI score.

## Validation and evidence

Final source, shared by focused/static/offline:
`sha256:d2588a9c9a33fa7ce7132f9a2e259bdb48cfaf300ad103f7e34ef6b6dca7a106`.
Fresh artifacts: `.artifacts/editable-query-ruler-20260912/`.
Source identities, artifact hashes and exact failed test IDs:
`evidence/editable-query-ruler-01.json`.

| Check | Result |
|---|---|
| Final focused | 272 passed, 3 failed; zero errors/skips |
| Final static | Pass |
| Final offline, including focused | 1,858 passed, the same 3 failed; zero errors/skips |
| Original card-plan values | SQL 57/57 hand agreements; reference 54/57 |
| Expanded hand-card values | 114/114 engine/hand agreements |
| Empty/all-NULL aggregate controls | 16/16 agreements |
| NULL numerator/denominator composition | 12/12 agreements |
| Whole-operand edit values | 6/6 agreements |

Initial focused: 239 pass / 3 fail; next 260 pass / 3 fail. An earlier offline
gate had 1,846 pass / the same 3 fail, then direct NULL-ratio composition coverage
was added and the final gate repeated on the completed rulers. Earlier reports
are retained; do not add overlapping runs to claim independent coverage.

The final offline gate is **failed**, not green. Its only failures are the named
reference gap; no historical test failure was introduced. The checkpoint is a
reviewable specification plus a reproducible existing-contract counterexample,
not an implemented editor, completed Stage-0 or successful usability experiment.

## Requested follow-up

Review the new card/edit/identity contract. If approved, first repair the
reference's existing named-segment behavior and make these three tests pass;
then implement the bounded research renderer/editor/confirmation path against
the hand facts and invalidation rulers. Keep production gates/statuses, model
budgets and human recruitment unchanged. No extra live model calls are needed
for that technical implementation. Only an actual human pilot can establish
whether people notice and correct the displayed mistakes.
