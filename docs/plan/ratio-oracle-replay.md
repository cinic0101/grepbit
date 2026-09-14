# Independent ratio oracle replay

2026-09-14, root-owned research from clean dev `8d54710`.

Authority: the owner's latest “好 開始下一步”, following explicit permission to
continue research, decide in-scope checkpoints, call psql/Gemma when needed and
commit locally. No push. No worker, production change, prompt change, historical
score rewrite, new gate or human-correction feature.

## Frozen scope and ruler decision

Restore independently checkable value evidence for holdout2 q21 (one store's
gross-sales share), q23 (one product's unit-sales share), and q25 (one category's
catalog-product share). The owner-approved readings and target identities are
anchored in `../research/ratios-01.md` and its reviewed ratio run 07, not inferred
from the current compiler or the later run 26's correctness flags. Match question
identity and reviewed target before replay. q22's two-store ratio has a different
review history and is out of this slice; q24 involves personal names and is out.

Research contract: numerator and denominator use the same all-time population;
q21 gross sales and q23 unit sales exclude return transactions under the reviewed
default, keep stored negative values and SQL NULL aggregate behavior. q25 counts
catalog products, including unsold products, not transaction lines or units.
Grouped target selection occurs after the whole-population share. A scalar
part/whole representation is also admissible for q23. Test complete output shape
and values, not arbitrary row subsets. Empty grouped output and scalar NULL have
separate declared shape rules; never turn missing/zero denominators into zero.

Root approves this bounded research ruler under the user's delegated checkpoint
authority. It adds no public evaluation contract. Freeze direct SQL, hand
arithmetic, data instances and known wrong alternatives before execution; current
and reviewed captured plans are subjects, never generators of the oracle SQL.

## Execution and privacy

- Five synthetic instances: unequal contributions/duplicate lines, a different
  mix with unsold products, zero denominator, empty population, and NULL amounts.
  Check handwritten arithmetic, independent PostgreSQL SELECTs and compiled
  captured plans. DuckDB provides an additional engine, not an intent oracle.
- Wrong alternatives: selected-only denominator, include-return population, and
  row/count versus quantity or catalog confusion. Each must differ on at least
  one predeclared instance; a coincidental match is not a successful witness.
- Read-only real PostgreSQL replay on one repeatable-read snapshot: compare
  current compilation of both captured revisions with independently written
  aggregate SQL. Role `grepbit_ro`, opaque `GREPBIT_POS_REAL_DSN`, no data writes.
  Limit executed SQL to the five required tables/approved columns; no personal
  names or member values. Bind public target names in memory, never persist them.
- Persist only case IDs, hashes, counts, match/shape indicators and safe errors.
  No raw questions, plans, SQL parameters, customer rows, names or DSNs in new
  artifacts. Schema introspection samples zero values. Synthetic SQL/data are
  fictional and remain in the private helper.
- Zero planned Gemma calls: first locate a fresh numerical discrepancy. Passing
  captured plans is not a fresh planner result. A discrepancy is recorded before
  deciding a narrowly bounded follow-up; do not launch another prompt search.

Evidence lives under `.artifacts/ratio-oracle-20260914/`, with a counts/hashes-only
manifest under `evidence/`. Focused rulers and fresh static closeout; reuse the
source-matched 1,841-test offline gate only while production/evaluation sources
remain identical. Stop on identity mismatch, unsafe capture, source drift or
unresolved oracle meaning rather than inventing a denominator.

## Closeout

Completed with fourteen focused tests, 90 synthetic queries per engine and all
nine wrong alternatives distinguished. Three real oracle queries and six
captured-plan replays agree; these are historical v11/v14 proposals, not new v15
model calls. No fresh numerical defect: no compiler/prompt repair or model call
is justified by this slice. q22/q24 and full holdout2 readiness remain outside it.
Fresh static passes; source/hash-matched offline 1,841 reused. Runtime, public
formats, evaluation policy, authorization and identity contracts are unchanged.
Details: `../research/ratio-oracle-replay-01.md`.
