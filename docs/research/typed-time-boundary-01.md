# Typed time correction: source storage and input interpretation are separate

2026-09-15, baseline `e6c5ecf`. The owner explicitly approved the proposed
instant/clock/DST policy before implementation. Prompt stacking remains paused.
[Contract/work record](../plan/typed-time-boundary.md),
[durable evidence](../../evidence/typed-time-boundary-01.json).

## Binding authority: database type plus configured business timezone

`introspect_schema()` queries `information_schema.columns.data_type` with the
readonly role and retains it in `SchemaColumn.data_type`. Both timestamp types
share ColumnKind.TIMESTAMP, but the exact type was **not lost at introspection**.
The compiler and synthetic builder previously failed to use that distinction.
Business timezone comes from datasource registration, not from the SQL type or
a model guess. No public schema field or database migration is necessary.

- Timestamptz literals with offsets identify instants; naive literals use the
  approved business timezone with a disclosure. DST gaps/folds require an offset.
- Timestamp without time zone stores clock labels. Naive values retain those
  labels. Offsets cannot be silently discarded or translated using a guessed
  storage zone, so they refuse until a reviewed source-zone binding is available.
- Raw date boundaries mean midnight, not an automatically expanded whole day.
  DATE columns do not silently truncate timestamps; sub-microsecond literals
  refuse rather than being rounded/truncated by different engines.

PostgreSQL documents both session-dependent timestamp conversion and its own
default handling of invalid/ambiguous local times. The product now applies its
approved policy before execution instead of inheriting those defaults.
[Timestamp types](https://www.postgresql.org/docs/18/datatype-datetime.html),
[DST behavior](https://www.postgresql.org/docs/18/datetime-invalid-input.html).
DuckDB also distinguishes wall timestamps from instants; keeping every synthetic
column TIMESTAMPTZ was therefore an evaluation fidelity bug, not an engine
limitation. [DuckDB timestamp documentation](https://duckdb.org/docs/current/sql/data_types/timestamp.html).

## Implementation and compatibility boundaries

Pure `domain/time_literals.py` implements the shared production policy. It uses
roundtrips through UTC for both folds to distinguish one valid instant, a gap,
and two ambiguous instants. There is no language matching or LLM adjudication.
Compiler filters preserve operator/location and bind explicit, source-typed
values. Calendar ranges, grain and latest use clock columns without accidental
instant conversion. The row path reuses the same population compiler. Compiler
revisions are v2-typed-time and rows-v3-typed-time; the planner revision is unchanged.

The SQL selfcheck still verifies bound values, using schema context to obtain the
approved canonical literal. A tampered midnight parameter fails its regression;
no timestamp exemption was added. This shares a normalization helper with the
compiler, so it is not an independent oracle for localization correctness.
Manual boundary expectations and PostgreSQL cross-session execution cover that
claim separately. The reference evaluator localizes with independent pytz logic
and respects the physical type; its older calendar-window helper sharing remains.

Synthetic generation and DuckDB construction preserve naive columns as naive
datetimes/TIMESTAMP. Type spelling is case-insensitive; unknown production types
are not automatically treated as instants. There is no reviewed column-zone
binding feature, metadata service or ontology added here.

Externally visible changes are intentional: canonical execution parameter types/
values, business-zone assumptions, and new typed PlanError reasons. The stored
QueryPlan shape, prompt, lexical gates, authorization, credential handling, DB
settings and row opt-in defaults are unchanged. No deployment or push is implied.

## Ruler and value evidence

The first complete ruler run had **35 expected assertion failures and 55 passes**,
no setup/import failures. The matrix crosses actual source type, offset/naive/date
input, plan/operand/without scope, and UTC/Taipei/New York sessions. Additional
tests cover microsecond endpoints, DST offset-distinguished occurrences, calendar
grain/windows, disclosure, selfcheck tampering, row projection with an unprojected
sort column and LIMIT, and source-type casing.

Hand data includes never-active entities, only-outside activity, exact start,
one microsecond inside/before-end, exact end, NULL activity time and NULL amount.
Selected COUNT=3, DISTINCT entity count=2, SUM=30, absent entities=5. Created time
is deliberately outside the activity interval. Thus multiple wrong calculations
cannot all match one scalar coincidence. These are synthetic instances, not
independent user questions or a semantic-equivalence proof.

Compiler rulers construct explicit physical types independently of DuckInstance;
fixture fidelity is tested separately. PostgreSQL arms use inline VALUES and
SET LOCAL within READ ONLY transactions, verifying role grepbit_ro. No persistent
relations are created, and no customer data is read or mutated.

Validation artifacts under `.artifacts/typed-time-20260915/`:

- Focused `green-04`: 146 passes, including the affected Service value tests.
- PostgreSQL matrix `postgres`: 181 passes (103 offline plus 78 added PostgreSQL
  arms), before the final two case-spelling controls. Three distinct session zones.
- First broad run: four failures, all existing Service fixtures using uppercase
  `TIMESTAMP WITH TIME ZONE`; 2,163 passes. Case-insensitive storage recognition
  and two controls fix this compatibility issue without changing expected values.
- Final offline: **2,169 passes, zero skips**. Final static passes. Early static
  failures were import/format/line-length issues, not semantic evidence.

## Stored-plan replay: fixes four cases, does not hide the remaining errors

39 actual answered temporal plans from the prior combination study are recompiled
and executed against synthetic PostgreSQL references and isolated boundary data.
Twenty-five previous matches remain matches. Four time/combined Chinese/Japanese
noon plans with naive filter strings change from wrong to reference-matched.
Ten previously wrong plans remain wrong: date/repair meaning errors are not
certified or guessed away by this binding repair. No typed refusals occurred in
this stored-plan subset. The aggregate result is 29 matches / ten mismatches.

This is compiler/value replay, not a new model or full ask() success. Original
reports are unchanged. In particular it does not claim to rescue invalid first
proposals or prevent a model repair from replacing noon with midnight.

## Bounded differential regression

| Source / engine | Valid generated plans | Typed refusals | Value agreements |
|---|---:|---:|---:|
| IoT / PostgreSQL | 192 | 47 | 145 |
| IoT / DuckDB, three instances | 192 | 47 | 435 |
| Service / PostgreSQL | 187 | 36 | 151 |
| Service / DuckDB, three instances | 187 | 36 | 453 |

250 requested examples per run, seeds 91/92, sampling zero and redaction. Total
**1,184 agreements, zero disagreements or DB errors**. Refusals are not agreements;
repeated instances are not new plans. These existing schemas do not substitute
for the explicit two-storage-type ruler matrix. Generator gaps and shared window
helpers still limit the claim. There were **zero Gemma calls** in this slice.

## Next

Keep prompts frozen. Run a bounded live temporal check through shared ask() with
the existing prompts, then separately evaluate the previously researched repair-
preservation guard for serving acceptance. Wrong valid initial plans and repair
truncation are distinct from source-aware binding. Cross-shape definition
availability, refusal-reason scoring and fresh user holdout remain future work;
do not silently revise old necessary-refusal scores or reactivate prompt stacking.
