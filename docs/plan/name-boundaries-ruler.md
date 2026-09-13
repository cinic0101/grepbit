# Nested positive names and normalization collisions: approved ruler

2026-09-13, baseline `658f1f6`. Owner explicitly approved the two decisions:
"同意，依此補齊測試並實作". Root owns the coupled implementation. Independent
example/restatement research freezes only after this runtime slice stabilizes.

## Approved contract

1. Extend existing positive EQ/IN existence/binding checks to measure filters,
   ratio numerator/denominator filters and `without.filters`, only for visible
   TEXT columns explicitly opted into grounding by the reviewed overlay.
   Keep operator and scope unchanged; bind only unique candidates, recheck the
   database, recompile and rerun policy. Missing, ambiguous, unavailable or stale
   candidates clarify before execution, as existing negative binding does.
   Exact stored values remain authoritative. Other columns retain their current
   behavior; no privacy opt-in or operator expansion is implied.
2. Distinct stored strings remain distinct even if normalization produces the
   same key. An exact stored string can bind itself. A normalized-only match to
   multiple strings is ambiguous, independent of insertion order. Candidate
   hints must not silently discard a colliding alternative or turn it into a
   unique identity. Candidate ids remain bound to the actual stored string.
   This includes both pre-plan mentions and post-plan resolution; it is not
   enough to repair only one path.

## Initial evidence

Explicit private ruler:
`.artifacts/examples-restatement-20260913/test_name_boundaries.py`, JUnit
`name-ruler.xml`: 19 cases, 10 intended assertion failures, 9 passes, no setup
errors or skips. Four nested unique EQ bindings fail; four nested missing IN
refusals fail; both insertion orders of the normalization collision fail.
Exact-name, policy-boundary and 100-name prefix controls pass. The fixture is
fictional. Existing runtime tests were not changed or weakened.

Example collision: stored `Harbor-East` and `Harbor East`; requested
`harbor east`. The baseline index retained only the first normalized entry, so its
reported exact match depended on insertion order. The approved result is
ambiguity, not an arbitrary choice. A literal already matching a stored value
exactly remains usable.

Expanded tracked ruler `tests/contract/t0/test_name_boundaries_contract.py`:
38 cases, 29 intended assertion failures and 9 passes before implementation,
including hint-path, stale-index, scope-preservation and mixed-IN controls.
JUnit `name-ruler-expanded.xml` preserves that red evidence. The older private
ruler remains unchanged. A prior sibling-scope test explicitly pinning unchecked
nested EQ is superseded: both opted-in operands now bind, without moving either
predicate into the common population.

Candidate hints remain untrusted model input, not evidence that the model chose
the intended entity. Keeping colliding alternatives prevents index-level loss;
it does not certify a model choice between those alternatives. Resolution may
display only the existing candidate cap, but ambiguity is decided before the
cap and never becomes unique merely through truncation.
