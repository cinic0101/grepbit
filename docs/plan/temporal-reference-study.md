# Temporal references: bounded research ruler

2026-09-13. Ruler baseline `099d851`, implementation baseline `bee008d`.
Status: owner explicitly replied "同意" to the quoted checkpoint request,
authorizing the research-only adapter and 90 initial calls / 180 total attempts.
Production remains unchanged. Authority is that user reply, not this document.

## Outcome, ownership and authority

Root owns this slice. The owner's latest instruction, "我們先用小型研究來試試看，
最好告訴我研究成果，以及研究完下一步該怎麼進行", authorizes the bounded study
proposed in the preceding research response. Earlier user messages authorize
read-only psql/Gemma use and local commits without another Git question; no push.
AGENTS' two-phase rule still requires review of a new reference/identity contract
before implementing its adapter. Complete independent existing-contract checks
while that checkpoint is pending. This record does not grant permissions.

Initial ruler slice: specification fixtures/tests, existing calendar conversion and
SQL boundary checks. No src/evals change, schema mutation, parser installation,
lexical gate, production prompt change or replacement of historical grades.

## Hypothesis and attribution

Giving a planner question-bound calendar literals and prohibiting independently
generated bounds may remove invented endpoints without losing grain or date-role
selection. This is not a claim that a valid reference proves the intended scope.
The preceding year-EQ instruction failed; copying its successes is not evidence.

First separate representation feasibility from extraction quality. The initial
catalog is authored, with spans and all declared distractors frozen before calls.
It is an oracle-catalog experiment, NOT an automatic extraction benchmark. It
must not use the correct selected column, slot, grain or answer to build the
catalog. A later extractor must reproduce the catalog coverage on unseen questions
before end-to-end adoption can be considered. Do not call an oracle-catalog gain
a production fix or generalization.

## Proposed research-only contract

Initially support explicit Gregorian calendar-year and calendar-month literals.
An entry has a request-local ID, exact question text plus zero-based occurrence,
and a canonical year/month literal. The frozen request also binds question,
schema/overlay, as_of, timezone, catalog and research revision by digest.
No generated code, external lookup, global ID cache or gold selected column.

Within the selected research arm, a time position uses
`{"column":"table.column","scope_ref":"t0","grain":"quarter"}`.
The reference replaces scope, not column or grain. Its year/month literal lowers
to the same calendar interval as the existing date-literal conversion; year
boundaries are server-owned. Candidate lookup must validate the request, exact
occurrence, canonical literal and ID before lowering. Validity is not intent.

- One authority per position: no `scope` beside `scope_ref`, no additional date
  filters supplying that position's bounds, no native-range fallback on bad IDs.
- Missing, stale, ambiguous or malformed references cannot silently pick a value.
  Canonical year must be a valid year with a representable following year;
  canonical month must be valid. Source text validation is not regex truth about
  whether the text denotes a query date (a model number may contain a year).
- A catalog may contain distractors. Picking the wrong valid ID remains a
  semantic error, not a successful binding. Selecting no window is also graded.
- Different positions can have different references: `time` and `without.time`
  do not overwrite one another. `without` still cannot have a grain/latest scope.
- All non-time plan fields, visibility, gate, metric/filter and SQL constraints
  remain unchanged. No new query algebra, multi-year union or comparison feature.
- Relative/latest, inclusive-date ranges, growth widening and grain-only controls
  retain native semantics. They are outside initial reference routing, declared
  before calls, not a fallback chosen after observing an invalid reference.
- Future clamp, missing-period NULL growth and approved date-basis disclosure
  remain unchanged. No fixed payroll-month lag. Fiscal years without a definition
  are not silently mapped to calendar years. Preserve ambiguity in annotations.

The initial ruler used static shape assertions, exact span vectors and existing-engine
controls. A red test calling a nonexistent adapter would be an import/setup
failure, not behavioral evidence. Production must continue rejecting the proposed
field at that checkpoint. Reference lookup/lowering was not yet implemented.

## Experiment after checkpoint approval

Freeze 24 authored questions and full permitted interpretations before calls:
12 explicit year/month questions (including original payroll, English/Japanese,
alternate year, repeated/distractor years and explicit date basis), plus 12 native
controls (relative, latest, no window, cross-year inclusive dates, multiple time
positions, growth and unsupported/ambiguous cases). Existing user holdouts stay
private and their scores unchanged. Do not widen gold after seeing outputs.

Three arms, distinct research revisions, same frozen schema and model settings:

1. Unchanged v15 baseline.
2. The same candidate facts as arm 3, informational only; original output shape.
3. Candidate facts plus reference-only output at predeclared eligible positions.

Arm 2 is a stronger information control than unrelated neutral text: it separates
extra date information from constrained representation. It is not an equal-token
or equal-schema-complexity control. Out-of-scope native controls are reported
separately, not counted as reference-mechanism rescues.

24 x 3 initial calls; six fixed cases x 3 later calls: 90 initial calls total.
One validation repair per case, zero automatic transport retries: at most 180
actual attempts. Serial Gemma4 31B, existing gateway 10.12.0.187:4000/v1,
T=0, thinking off, 20-second request budget. Opaque existing .env key only.
Outbound: authored/consented fixture questions, value-free schema/overlay,
question-derived candidate literals. Never SQL, result rows, credentials, real
POS PII or gold interpretations. Use fresh private artifacts and close clients.
Stop on drift, unsafe capture, two transport errors or exhausted attempt budget.

PostgreSQL localhost:5432, existing POS-test DSN env and grepbit_ro only. Initial
boundary checks use inline synthetic VALUES in read-only transactions; no table
creation, real row reads or administrator credentials. This is independent SQL
validation, not a new datasource. Freeze expected endpoints/rows by hand, not by
the production resolver or the reference evaluator that shares time functions.

Report extraction coverage (not measured by oracle catalog), selected reference,
window, grain, date basis, scope placement, raw vs served outcomes, wrong-valid,
refusal type, repair/transport attempts and latency separately. Preserve requested
vs effective widened/clamped windows. Exact boundary equality, not time-overlap
score or coincidentally equal fixture totals. All gold/foil pairs need witnesses.

Screen: repeated mechanism-based rescue beyond arm 2, no newly wrong eligible
answers or lost necessary refusals, native controls retained, declared ambiguity
preserved. A tie, absent baseline errors or increased refusals without corrected
answers is inconclusive/failure, not a win. Authored panels are not user holdouts.

If positive: test automatic candidate extraction on fresh multilingual questions,
then affected-set runtime evaluation and a separate production decision. If only
oracle catalogs help, keep production unchanged and isolate extraction/selection.
If negative: retire the experiment helper, retain evidence; do not add phrase
exceptions or expand the time framework to rescue the original question.

## Primary sources informing the design

- [SCATE executable normalization, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/e722a7be34788c81b53b744e7c7e675c-Paper-Conference.pdf): symbolic representation, not arbitrary code execution here.
- [Intermediate representation and anchoring, CL 2025](https://aclanthology.org/2025.cl-4.7/): separate calendar arithmetic from language interpretation.
- [Discourse-aware normalization, NAACL 2024](https://aclanthology.org/2024.naacl-short.27/): extraction recall is a separate bottleneck.
- [TRAVELER, 2026](https://link.springer.com/article/10.1007/s42979-026-04973-y): explicit/relative/vague strata; synthetic English evidence is not multilingual deployment evidence.

## Work record

Initial tree clean at 099d851. Read AGENTS, architecture, current tier-0 time
contract and prior temporal study. Process preflight found no Python regression;
the previously acknowledged Claude PID 49876 is still present (user previously
said to disregard that session). Preserve other work and stop on file drift.
Evidence directory: `.artifacts/temporal-reference-ruler-20260913/`.
The owner subsequently approved this checkpoint. Implementation and new artifacts
are private under `.artifacts/temporal-reference-study-20260913/`; no production
surface or parser dependency is added. Root owns the coupled adapter/runner work.
Completed 90 calls, zero repair/transport errors. Incremental-benefit screen is
inconclusive: the original baseline failure did not recur in the small synthetic
context. See `../research/temporal-reference-study-01.md`, including frozen grades,
post-hoc representation diagnosis and the separately tested v1.1 guard correction.
