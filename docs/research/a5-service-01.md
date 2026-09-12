# Candidate references and a non-POS service source

Subsequent owner decision: lexical grain deletion is now retired in
orchestration v3; see `../plan/grain-retirement.md` for new evidence. The
results below remain the original measurements, not relabelled post-fix runs.

2026-09-12. Baseline dev 746f168, uncommitted takeover work. A5 is implemented
but **not accepted for promotion**: exact binding works, but a repeated
structured-output failure prevents a no-regression claim. A4 is not started.
Artifacts are under `.artifacts/a5-20260912/`; the durable manifest records
counts and hashes without questions, customer literals or credential values.

## Experiment boundary

Gemma4 31B, json_object, thinking off, serial calls to the authorised gateway.
Real-source as_of is 2026-02-04 18:00 Taipei; sampling is 0. The driver drops
questions, SQL, plans, raw outputs and value-bearing fields before persistence,
retaining metrics and plan hashes. `--redact-rows` alone does not do this.
The new service database is entirely fictional and its diagnostic reports may
retain fictional plans. No old database was modified. Existing grepbit_ro is
SELECT-only; container-local setup authentication avoided the supplied admin
password entirely. The label overlay contains no reviewed business metrics.

The v14 control restores the old wire and value rule but keeps the accepted
compiler semantics and the same candidate eligibility/order as v15. It is
not a historic deployment replay. Candidate references change neither domain
plans nor the compiler. No missing ratio operand is guessed or filled in.

The initial synthetic format probe was 9/9 in each arm (18 calls), with p50
2.047 s literal / 1.908 s reference and slightly shorter reference outputs.
This establishes usability, not an accuracy or reliable speed improvement.

## Live results

The complete existing 313-case v15 run preceded the service-discovered grain
dependency repair. Its source stayed frozen throughout (hash in the manifest).
After that repair, both service runs and the targeted counterfactuals completed.

| Set | Result | Important limit |
|---|---|---|
| Author 160 | 155/160 | smoke, not generalisation |
| Features 39 | 37/39 | comparison-extra-growth and quarterly-payroll failures |
| Batch 1 | v14 50/50; v15 50/50 | two candidate cases; v15 uses two IDs |
| Holdout 2 | 30 unjudged; one structured-output failure | 28 validated references, zero reference errors |
| Ratio set | 12 unjudged; one structured-output failure | three validated references, zero reference errors |
| Holdout 3 | 15 unjudged, no model failure | not a fresh correctness score |
| Real smoke | 7/7 | seven authored cases, not a blind holdout |
| Service raw | 21/24 | two literal misses, one incorrect grain rewrite |
| Service public-label index | 23/24 | five ID references, zero literal misses; grain rewrite still wrong |
| Service same-index v14 control | 23/24 | zero literal misses without IDs; no demonstrated A5 accuracy gain |

Across the existing v15 sets, reference errors and hinted literal misses are
zero. The latter is a case-level co-occurrence metric, not measured candidate
recall or proof that every required literal had an eligible candidate. IDs
assure exact binding, not correct entity selection or question interpretation.
The service raw/index difference does not isolate A5 from existing indexing.
The completed same-index v14 control is also 23/24 (p50 2.366 s versus v15
2.387 s). Here the gain comes from indexing, not a measured A5 improvement.

### Failure counterfactuals

Each initial failed model case was repeated twice per wire, serially:

- Holdout 2 q25: v15 answered once and failed once; the failure omitted
  `plan.measures[0].ratio.denominator` both before and after repair. Combined
  with the initial run, that is two failures in three v15 observations. The
  three v14 observations succeeded. This is a regression warning, not proof
  of an endpoint cause, and blocks A5 acceptance.
- Ratio h2_q23: all four targeted repeats answered; the original failure is
  retained. None of these unjudged results becomes an accuracy claim.
- Failed author questions were also repeated twice per arm (36 executions,
  including shared POS/no-sampling case IDs). Most failures reproduce under
  both wires. The comparison question answers correctly under v14 but adds
  growth under v15 in both repeats. It has no candidate: the model-visible
  revision label alone differs there. Incidental prompt metadata can affect
  output; do not attribute that case to reference resolution.

The error diagnostic records only pydantic error types and allowlisted field
locations, not messages/inputs containing literal values. Do not tune a
prompt to q25 and call the now-seen holdout an independent measurement.

## What the second datasource exposed

1. **Impossible parent fan-out in random data.** Natural FK targets were not
   unique unless they were primary keys. PostgreSQL had 160 agreements; the
   initial three-instance DuckDB run had 360 agreements and 120 disagreements.
   Preserving FK-target uniqueness fixes the same 216-plan replay: 480
   agreements, 56 typed refusals, no disagreement/error. Non-PK numeric keys
   also differ from numeric IDs so a first-PK join bug cannot hide again.
   IoT/POS replay guards add 546/510 agreements. Combined final comparisons
   across these four reports: 1,696; refusals are not comparisons. NULL and
   dangling-child stress remains deliberate; this is not a general SQL
   constraint-satisfying data generator.
2. **A normalisation invalidated a valid plan.** The grain word list did not
   recognise the service question's period wording and removed the grain
   needed by growth. The compiler then asserted. Two offline rulers reproduce
   it; the repair preserves the structural dependency regardless of language.
   It neither deletes growth nor adds a case-specific phrase. Both initial
   service attempts aborted and are not counted as complete runs.
3. **A remaining wrong-valid rewrite.** Without growth, the same word-list
   rule removes the correct month grain in `svc_month_minutes`, returning one
   total rather than three periods in both service arms. The assumption even
   says no period was asked for. Retirement of this lexical deletion is
   recommended and has been put to the owner; it has not been silently removed.

The six-table source also exercises non-ID joins, a three-hop parent dimension,
multiple clocks, NULL/zero measures, empty parents and two sibling fact tables.
It correctly refuses unsupported cross-child aggregation. It is a small
authored fixture, not evidence that large-schema linking is solved or needed.

## Validation and next step

329 offline tests pass. Focused natural-key tests cover text/numeric keys over
20 seeds; 26 gate/ask/generator tests pass after the assertion repair. Final
static checks pass after a formatting-only line wrap; two focused generator
tests revalidate that wrap. Earlier failed checks remain historical artifacts.
No commit, stage or push was performed.

Do not add A4 or a new algebra construct on top of this unresolved result.
First separate incomplete ratio output from reference syntax in a bounded
counterfactual using the existing domain contract (never invent a denominator),
and decide the lexical grain rewrite. Removing incidental revision text from
model input is an experiment candidate, not an already-measured improvement.
Any resulting prompt revision needs its own affected-set regression; a broader
independent holdout remains necessary for a generalisation claim.
