# Ratio oracle replay: three historical questions, independent values

2026-09-14. Complete from `8d54710`; no production, prompt, overlay, historical
grading or model changes. Plan: `../plan/ratio-oracle-replay.md`.

## What this closes

Three owner-reviewed readings now have a reproducible, independent arithmetic
check against the current compiler. These are **captured plans**, not fresh model
answers. `reviewed` denotes ratio run 07 / prompt v11; the helper's `current`
denotes holdout2 run 26 / prompt v14, **not a new v15 proposal**. Both are compiled
by today's unchanged source, with current overlay v12.

Question strings must match across the case file and both reports. The run-07
verdict's question, answered status and correct label must match; its report
reference was separately checked. Each target comes from that reviewed proposal,
and run 26 must select exactly the same column/value. Names stay in memory.
This reuses the owner's reviewed target, not an independent new annotation of
the original language, and does not certify new name choices.

| Case | Fixed reading | Real DB: v11 / v14 captured plans |
|---|---|---|
| h2 q21 | Selected store's gross sales / all stores' gross sales; reviewed non-return population | match / match |
| h2 q23 | Selected product's sold units / all sold units; reviewed non-return population | match / match |
| h2 q25 | Products in selected category / all catalog products, including unsold products | match / match |

The independent SQL uses separate numerator/denominator aggregates, not the
compiler's window-share implementation. It does not import the Python reference
evaluator or production time-boundary functions. No time parser claim follows:
these questions use all-time populations, fixed as_of retained for compilation.
Negative stored values remain negative; NULL and zero denominators stay NULL.

## Results and what the counts mean

Five predeclared synthetic instances include unequal contributions, duplicate
lines, return lines, negative values, unsold products, NULL and zero/empty
populations. They are deliberately reduced POS-shaped fixtures, not copies of
the full customer's data or a new datasource-generalization test.

Each engine executes **90 SELECTs**:

- 15 independently authored oracle queries, checked against hand arithmetic.
- 30 captured-plan queries: 3 cases × 2 captured revisions × 5 instances.
- 45 wrong-alternative queries: 3 alternatives per case × 5 instances.

DuckDB and read-only PostgreSQL agree on all 90 paired results. All 30 compiled
plan results per engine agree with the expected arithmetic and complete declared
row shape. All **9 wrong alternatives** differ on at least one nonempty instance.
The 45 deliberately wrong queries are not 45 correct answers or compiler tests.

The alternatives test selected-only denominators; including return transactions;
transaction/line counts instead of amounts or units; and sold-product/line
populations instead of the product catalog. A useful finding: the sold-product
alternative coincides with the catalog oracle on the first populated instance,
but the second instance's unsold products distinguish them. One real/fixture
number alone would have missed this difference.

Real PostgreSQL: **3 independent aggregate queries + 6 current-compiler replays**
on one repeatable-read, read-only snapshot. All six match, with one output row
each. No actual names, numeric customer answers, SQL parameters, raw questions
or personal-column values are persisted. Introspection samples zero values;
execution uses `grepbit_ro`, the five required tables, and no personal columns.
The driver records only allowlisted identifiers, counts, booleans and hashes.

Complete outputs are compared, not arbitrary subsets or whichever alternative
fits each instance. The captured plan fixes grouped versus scalar shape for all
five instances. A grouped query can yield no row on an empty population; a scalar
part/whole query yields one NULL cell. These declared shapes are not collapsed
into zero, and an unrelated extra row/column is not projected away.

## Validation and disposition

Fourteen focused tests pass, including all synthetic checks, historical identity,
target scope preservation, output shape, NULL/empty distinctions and counterexample
sensitivity. Fresh static passes. Input/helper hashes and the output allowlist
pass the closeout integrity check. The exact source-matched **1,841-test offline
gate is reused**, not rerun; its report hash is retained in the evidence manifest.
The initial inline PostgreSQL schema read is metadata preflight, not a numerical
test. Zero model calls, DB writes, new dependencies or runtime code changes.

**Decision:** no new numerical compiler defect was observed for these three
captured computations. Keep these independent controls; do not invent a compiler
repair or run a ratio prompt search merely because old labels were insufficient.
Historical answers/scores remain untouched. Neither full holdout2 oracle readiness
nor A5 acceptance is closed: q22 has separate two-store/operand-filter semantics,
q24 involves personal names, and later malformed proposals still need their own
trace. This is not an end-to-end serving or fresh planner evaluation.

Next priorities:

1. Use these controls whenever a future captured ratio differs; then distinguish
   selection/binding, malformed representation and numerical compilation rather
   than assigning the failure from a final status alone.
2. Return to reproducible intent errors: missing business-scope definitions and
   wrong metric selection. The lease-metadata gain remains one family only;
   any confirmation must include defined/absent/unknown configurations plus
   answerable neighbors in another context, without a simultaneous gate change.
3. Keep imperative-versus-business-role gate false refusals separate. Correct-plan
   replay has already located them; neither another same-model certificate nor
   a broad gate bypass is an evidenced fix. No lexical exception is added here.

Evidence: `evidence/ratio-oracle-replay-01.json` and
`.artifacts/ratio-oracle-20260914/`. Helpers are private research assets; only the
plan, report, counts/hashes manifest and roadmap update enter Git. Local commit
only; no push.
