# Temporal references: checkpoint and independent calendar witnesses

2026-09-13, baseline `099d851`. Protocol and pending contract:
`../plan/temporal-reference-study.md`. This is phase 0, not a completed live
reference-selection experiment. New model calls: **zero**. Production v15,
QueryPlan, normalizers, compiler, overlays and gates are unchanged.

## Findings

1. Existing year/month literal conversion passes hand-written start/end and SQL
   inclusion witnesses for eight calendar/timezone vectors, each for DATE and
   TIMESTAMP. Includes leap/non-leap February, year transitions, and March/November
   in America/New_York. Timestamp witnesses include the last microsecond before
   the lower bound and the last microsecond inside the upper bound. The start
   must be included, end excluded and NULL excluded. Powers-of-two amounts make
   each membership error observable; expected sum is six, never derived by the
   production time resolver. DuckDB and PostgreSQL agree with that independent
   expectation. This is bounded evidence, not coverage of all time expressions.
2. PostgreSQL executes the same vectors in UTC and America/Los_Angeles sessions,
   preserving the datasource's business-timezone meaning. All tests use inline
   synthetic VALUES, read-only transactions and grepbit_ro, no table mutations
   or real row access. Existing missing-bucket and threshold rulers also pass.
3. Year conversion retains month/quarter/year grain. The candidate representation
   need not replace working arithmetic or derive grouping from a lexical list.
4. An authentic source span can still be the wrong year: in a model-number plus
   query-year question, both years bind and compile, but their intervals differ.
   Thus reference validity cannot certify semantic selection. Exact occurrence
   vectors cover repeated text, multiple years, Chinese/English/Japanese and an
   emoji before a span; they are NOT extractor recall measurements.

## Specification boundary

The new test-only ReferenceTimeSpec prohibits a second scope/start/end/as_of/
timezone authority beside scope_ref. It preserves independent column and grain.
The production domain continues rejecting the proposed field. These are static
contract assertions, not red behavior tests for a nonexistent adapter. Request
lookup, stale-ID rejection, source/canonical consistency, scoped lowering and
end-to-end fallback checks still require implementation AFTER checkpoint review.

No automatic candidate extractor was built. The next experiment's authored
catalog is intentionally an upper-bound/representation experiment; informational
and reference arms receive the same candidate facts. This controls for supplied
date information, although prompt length and schema complexity still differ.
A gain cannot establish automatic extraction, universal intent verification or
production readiness. Native relative/latest/growth controls stay separate.

## Validation

Artifacts: `.artifacts/temporal-reference-ruler-20260913/`.

- Initial focused: 111 passed. Timestamp boundary witnesses were then tightened
  to microsecond boundaries; the final runs below supersede that evidence.
- Final focused PostgreSQL run: 145 passed, 0 skipped. Of these, 66 are actual
  PostgreSQL cases: 32 new boundary cases and 34 existing period-semantic cases.
  The other 79 are local/static/DuckDB/reference checks; do not label all 145 as
  PostgreSQL executions. PostgreSQL is opted in using the existing
  GREPBIT_PERIOD_RULER_DSN_ENV convention in the focused profile.
- Static: pass. Full offline: 1,841 passed, 0 skipped, including the 45 new
  offline rulers. Counts overlap with focused; they are not additive.
- Source digest at final validation:
  `sha256:e082cb9bfcaffb40f96f2f533d635cf085c9222731eb8330a76d89a9b16880ad`.
  Evidence manifest: `../../evidence/temporal-reference-ruler-01.json`.

## Decision and next step

No new arithmetic defect found in this panel. Existing conversion is a viable
lowering target, but whether the new representation helps Gemma is unanswered.
The contract checkpoint was presented to the owner; do not infer approval from
this report. After approval, implement a private research adapter, freeze all 24
questions/allowed readings and three-arm messages, validate lookup/lowering and
independent SQL oracles, then run 90 initial calls (at most 180 with repairs).
If reference selection beats the same-information control without new errors,
measure automatic extraction on fresh multilingual questions. Otherwise retain
production unchanged and report whether selection, coverage or representation
caused the failure. No new word exceptions, broad rollout or historical regrade.
