# Repair review: compare both effective bounds and preserve uncertainty

2026-09-15, baseline `a6e9c69`; owner requested the two concrete corrections
alongside the details/aggregate integration work. Root sole writer, initially
clean tree. Existing local-commit authority applies; no push. No model or DB
call is needed for these pure counterexamples. Time binding stays independently
accepted; this corrects the already-integrated narrow guard, not its intent claim.

Both P2 findings reproduce. The first guard measured only the repaired effective
bound against the original range endpoint, dropping the original filter context.
The second compared a known repaired child with a missing original child as if
both identities were known. Nineteen new controls cover plan/without scopes,
stronger lower/upper bounds, equal exclusive endpoints, redundant weaker bounds,
dropped original restrictions, unknown predicates/values/list/operator shape,
unresolved child identities and the actual two-turn runtime.

Initial reviewer ruler: 16 intended failures / 2 passes. Implementation then
passed 63 related tests. An additional malformed operator value exposed an
unhashable-list TypeError before its type check; it is now unverifiable. The
final broad gate passes 2,210 tests (zero skips), static passes. Artifacts under
`.artifacts/guard-review-20260915/`, fingerprints in
`../../evidence/temporal-repair-review-01.json`.

The guard now parses recognizable same-column inequalities symmetrically for
both original and repaired scopes, combining each with its own range. Unknown
original filters or unknown base/child identity do not establish a difference;
they remain unverifiable and conservatively blocked. Other-column semantics
are still outside this narrow anchor check; no full query equivalence claim.
The four prior confirmed harmful repairs and historical scores are not erased.

Execution guidance now freezes **all fingerprinted inputs**, including tests and
probe scripts, not just src/evals. Read-only work may overlap; covered writes
must wait. This is a documentation correction to match the existing verifier,
not a new execution framework. No prompt, API, DB, permission or deployment
change. Use this fixed runtime as the next row/aggregate acceptance baseline.
