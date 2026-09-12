# Metric selection: Phase-0 ruler checkpoint

2026-09-12. Rulers complete; new grader/live study await follow-up approval.
Contract: [annotation ruler v1](../plan/metric-selection-annotation-contract.md).
Original authority: "沒問題...按照你的想法/順序組織測試驗證".

## What was established

36 authored development questions (six paired families x three languages),
24 author-visible frozen challenge questions (four paired families x three
languages). Local validation checks their annotations and plans, not model
performance. No blind-user generalization claim. Existing unrun contrast
challenge was not used for tuning or relabelled.

The test-only annotation explicitly separates measure basis, populations,
constraints, grouping, requested output label, uncertainty and per-occurrence
span roles. `all_rows` is explicit: empty requirements never imply it. It is
still an interpretation claim, not a certificate. Ambiguous return rates and
missing service refund definitions remain unresolved. The schema checks shape,
identifiers and code-point offsets, not whether the language interpretation
is correct. A well-formed but wrong span interpretation is an explicit control.

18 fixed plans over three fictional instances produce 54 plan-instance pairs.
Compiled SQL executes in local in-memory DuckDB; the existing Python reference
evaluates the same plans separately. Both match independent hand answers:
108 engine/plan/instance checks. These are not PostgreSQL checks or model calls.
Numeric checks use relative/absolute tolerance 1e-9; grouping checks retain
column positions and multiplicity. No DPC soft rounding or date truncation.

48 case-level correct/wrong candidate comparisons represent 37 distinct directed
plan pairs, all with distinguishing witnesses in both engines. The asymmetric
instance distinguishes all 37. Correct alternatives include raw/reviewed
returns metrics and nullable-column COUNT versus explicitly filtered COUNT.
No equivalence theorem is inferred from their finite-instance agreement.

Intentional coincidence controls are preserved:

- Returns versus non-returns count: both 2 on `coincidental`, 3 versus 2 on
  `asymmetric`.
- All versus return-only amounts: both 5 on `null_zero`, 190 versus 60 on
  `asymmetric`.

The current lexical gate still falsely blocks an output-action request and a
label-only request when given the correct COUNT plan. It still catches a
genuine dropped returns condition and misses a reversed returns predicate.
These four characterizations record current behavior, not an approved gate
replacement or a new model observation.

Three old-v2 characterizations pass their specified concept constraints while
answering the wrong measure basis:

| Requested answer on asymmetric data | Wrong candidate | Hand values: correct / wrong |
|---|---|---|
| Returns transaction count | Reviewed returns sum | 3 / 60 |
| Returns amount | Reviewed returns count | 60 / 3 |
| Member transaction count | Distinct member count | 2 / 1 |

This is a scope limitation, not a regression against v2's partial contract.
Requiring red rejection tests on the old checker would silently change that
contract. The checkpoint uses executable static annotations, hand witnesses
and green legacy characterizations instead; no new grader is implemented.

## Validation and state

- Focused final: 155 passed, zero failures/errors/skips.
- Full offline: 915 passed, zero failures/errors/skips.
- Static: passed. No separate redundant broad suite.
- All final gates share source digest
  `sha256:d9630e4926826e84b40388becba03bf035a319eb2c61445d697d6fdea1105743`.
- Initial YAML flow-scalar punctuation caused a collection error; fixed by
  block question mappings. Formatting was applied only to the new test file.
  Neither setup failure nor formatting is semantic checkpoint evidence.
- No Gemma, PostgreSQL, external data, new packages, production source edits,
  old-grader edits, stage, commit or push. dev remains at 746f168 with previous
  dirty work preserved. Process preflight read names only, not arguments/env.
- Files: new ruler YAML/test, annotation contract, this note and evidence;
  plan/active-work status updated. Final snapshots differ from the initial
  ruler snapshot only in the two new source/fixture files, not existing code.

Artifacts: `.artifacts/metric-selection-ruler-20260912/{focused-first,
focused-second,focused-final,static,offline}/`; durable summary in
`evidence/metric-selection-ruler-01.json`.

## Next checkpoint decision

Approve or revise the explicit population/basis/per-occurrence annotation
contract for a bounded research grader, while leaving production/v2 contracts
unchanged. Then implement grader/input guards and fake-client tests before
the proposed 144 planner + 36 activation calls. The initial 180 and conditional
444 call ceilings are unconsumed. Presentation transforms, actual-ask model
replay, inference candidate selection, and live performance are not established
by these rulers. No automatic production promotion follows research success.
