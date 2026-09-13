# Temporal references: feasible, incremental benefit unproven

2026-09-13, baseline `bee008d`. The owner explicitly approved the checkpoint
in `../plan/temporal-reference-study.md`. Production remains ask v5 / prompt
`plan-classify-json-v15`; no runtime, overlay, gate or historical-grade changes.

## Result

90 scheduled executions / **90 actual Gemma4 31B calls**, serial, T=0, thinking
off, zero validation repairs and zero transport failures/retries. Approximately
302 seconds for the model phase. All reference-eligible invocations used a
reference: **16/16** (12 primary, four scheduled repeats). All selected the
intended calendar literal; the repeated-year question selected its second
occurrence, and the batch-code/year distractor selected the query year twice.
This is not extractor recall or evidence of generalization.

| Frozen acceptance | Baseline | Same-information control | Reference arm |
|---|---:|---:|---:|
| Eligible year/month questions | 11/12 | 12/12 | 11/12 |
| Native time controls | 10/12 | 11/12 | 11/12 |
| Primary total | 21/24 | 23/24 | 22/24 |
| Fixed later panel | 5/6 | 5/6 | 5/6 |
| Primary call-time p50 | 3.09 s | 2.99 s | 3.11 s |

Each primary arm produced 22 answers and two required refusals. Each repeat arm
produced five answers and one required refusal. Nonaccepted outputs above are
**unassessed**, not established wrong numbers. No rejected value comparison or
new unnecessary refusal was recorded. Do not read 23/24 vs 22/24 as a difference
in temporal understanding; see the representation diagnosis below.

The original Chinese payroll question passes all arms, on both invocations.
The predefined incremental-rescue screen is **inconclusive: no demonstrated
benefit**, not a promotion. This establishes bounded interface feasibility, not
that references fixed the earlier 2060 failure. No production adapter is added.

## Experimental limits

The panel has 24 authored questions: 12 explicit Gregorian year/month cases and
12 controls covering relative/latest, no window, inclusive cross-year ranges,
two named months, separate main/without dates, growth, to-date, and explicitly
undefined fiscal/date-locale interpretations. Six IDs were fixed for later
repetition. These are not unseen user questions or independent session samples.

All use one **small synthetic payroll/employee schema**, with distinct paid_at
and period_start definitions, a non-temporal batch_code, and three fictional
datasets. The original question text is retained, but the historical full POS
schema/sampling context is NOT reproduced. The datasets mostly share calendar
and relationship structure and vary amounts; they are not independent schema
samples. The missing baseline failure limits power to demonstrate improvement.

Catalogs are authored occurrence annotations. Canonical year/month literals are
validated against exact numeric/ISO/Chinese numeric date spans; arbitrary language
extraction, English month names and fiscal calendars are not implemented. All
declared distractors are included. Question, schema, as_of/timezone, catalog,
positions and revision bind request-local IDs. Catalogs do not encode selected
column, grain or answer. Routing eligibility is predeclared, not auto-detected.

Both non-baseline arms receive the same candidate facts; only the reference arm
replaces native scope with scope_ref at eligible positions. Column, grain,
ordinary validation, gates and execution remain in the existing pipeline.
Information and reference arms differ in schema/rules/length: not a token-matched
experiment. Native-control fluctuations are outside reference routing.

## Nine unassessed outputs are not nine demonstrated mistakes

They reduce to three unique full plan hashes. A separate post-observation search
over **180 valid synthetic candidate plans** recovered all three hashes exactly,
including all fields. Their initial/final hashes match. Nine offline value checks
(three recovered plans x three datasets) agree with the original independent
reference after explicitly accounting for the extra period-label column:

- `paid_scalar`: baseline/reference add year grain to one calendar-year total.
- `latest`: baseline adds month grain to the latest-month total.
- `two_positions`: all arms, including repeats, encode hire dates as ordinary
  date filters and the absent-payroll window in without.time. The hire-date
  condition was not dropped.

This is post-hoc diagnosis, **not a frozen-score change or new accuracy score**.
Four further tests show the extra-label explanation's limit: with nonempty data
the sums agree; on empty data scalar SUM returns one NULL row and grouping returns
no rows. Do not globally erase grain or declare universal equivalence. Next time,
predeclare permitted related outputs/representations and empty-result behavior,
consistent with the owner's existing evaluation principle.

## Post-run parser review

The measured v1 guard recognizes qualified date columns but misses bare names
such as `paid_at`, which ordinary normalization can later qualify. Two intended
failing tests reproduce this gap in the approved no-competing-boundary rule.
Thus the measured parser is not a complete runtime input boundary, even though
the panel recorded no wrong temporal result attributable to that hole.

Measured helpers and frozen data remain immutable. A separate private
`wire_hardened.py` (v1.1) fixes bare-date recognition; **61 tests pass** (original
59 plus two regressions), with **zero new model calls**. Do not attribute the
90-call result to v1.1. The guard remains conservative about extra date predicates
in reference-routed cases; full mixed temporal-filter support needs more coverage
before a production proposal. No production code was changed.

## Evidence and validation

- `.artifacts/temporal-reference-study-20260913/`: original helpers, 24 frozen
  annotations/contexts, message hashes, schedule, results and end check.
- 59 private tests pass before calls; final static passes. Source/hash-matched
  repository offline **1,841** is reused; tracked source is unchanged.
- Before and after calls: **174 DuckDB and 174 PostgreSQL** compiled-vs-independent
  SQL comparisons per preparation across three fictional datasets. Source,
  contexts, message/oracle hashes match at end. Repeated checks are not extra
  independent questions or generalization samples.
- PostgreSQL uses grepbit_ro, inline VALUES and read-only transactions. No stored
  rows read, tables created or admin credentials used. No SQL/results, secrets or
  real POS PII sent to the model. Response text is not persisted; only hashes,
  validated plan facts, temporal fields and grades are retained.
- `.artifacts/temporal-reference-diagnosis-20260913/`: exact-hash reconstruction,
  nine value checks, four empty/nonempty tests, two red tests and v1.1's 61 green
  tests. They do not modify the frozen live study.
- Counts/hashes: `../../evidence/temporal-reference-study-01.json`.

## Recommended next order

1. Keep production unchanged. No parser integration or new time framework yet.
2. Restore the previously failing **full-schema context** and first run a small
   fixed baseline-only reproducibility check with source/prompt/schema/sampling/
   as_of recorded. If baseline stays correct, stop at the ceiling rather than
   spending another full comparison budget. The 2060 token cause is unresolved.
3. If errors recur, freeze that richer-context panel plus permitted related-output
   alternatives/empty-result behavior, then compare baseline/information/reference
   v1.1. Only repeated incremental gains warrant automatic multilingual extraction.

No further live calls under the completed 90-call schedule. Local evidence and
documentation only; no push, deployment, promotion or release claim.
