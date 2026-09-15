# Typed time boundary — approved and implemented

2026-09-15, baseline `e6c5ecf`, root sole writer, initially clean dev.
User explicitly requests time contracts/tests before implementation and pauses
prompt stacking. Existing grants authorize readonly psql checks and local Git
closeout; no push. The input-policy question was explicitly approved by the
owner's follow-up "同意這組政策". The initial 90 rulers yielded 35 expected
failures and 55 passes before implementation. This records the contract-first
phase and follow-up authority; the work record itself grants no permission.

## Findings and scope

Introspection groups both timestamp types into ColumnKind.TIMESTAMP but retains
their full information_schema data_type. No public kind/schema migration is
needed merely to distinguish them. Compiler `_bind_type` ignores that distinction,
accepts naive ISO timestamps and returns timestamptz. Synthetic DuckDB maps both
source types to TIMESTAMPTZ. Reference `_as_datetime` independently attaches UTC
to naive values. Agreement between any two paths is not a truth oracle.

Core invariant: for a defined interpretation, changing DB session timezone must
not change the selected records, aggregation population or calendar grouping.
Check stored source types as well as parameter types; do not fix this by setting
every engine/session to Taipei. Use explicit independent typed relations for
compiler rulers, and test production synthetic fixture type fidelity separately.

## Owner-approved policy

| Source type | Literal | Meaning |
|---|---|---|
| timestamptz | explicit offset | exact instant, preserve offset/instant and microseconds |
| timestamptz | naive timestamp | interpret in datasource business timezone, disclose the default |
| timestamptz | date only | business-zone midnight boundary, not an implicit whole-day predicate |
| timestamp without time zone | naive timestamp / date only | stored clock label / midnight label, use timestamp comparison; do not infer an instant |
| timestamp without time zone | explicit offset | typed refusal `timestamp_zone_binding_required` until a reviewed source-zone binding exists; do not discard the offset or guess stored UTC/Taipei |
| date | date only | calendar date; no timezone conversion |
| date | timestamp | typed refusal `date_literal_precision_loss`, not truncation |

For conversion to an instant, ambiguous fall-back times refuse
`timestamp_local_ambiguous`, nonexistent spring-forward times refuse
`timestamp_local_nonexistent`. Require an explicit offset; do not choose fold=0/1,
shift forward, or rely on PostgreSQL's standard-time preference. Explicit offsets
distinguish the two repeated occurrences. Raw wall-clock columns do not represent
instants, so their naive comparisons do not require DST resolution. Timestamp
precision beyond six fractional digits refuses `timestamp_precision_unsupported`
rather than Python truncation or DB rounding. All failures must be typed before
execution, not model judgments or ordinary empty answers.

The operator and location stay unchanged: EQ is a point comparison, not a day
range; existing date-literal-to-window normalization is separately documented and
must not be silently broadened by this repair. Plan, operand, ratio operands,
without, row filters and reviewed definition filters must use the same binding
policy without moving conditions. Existing calendar scopes/grain on naive source
columns must operate on wall-clock values without session-dependent casts.
Do not invent per-column zone metadata in this slice; unsupported conversions
stay explicit pending reviewed metadata. No prompt, gate or default promotion.

## Evidence design and implementation order

1. Rulers cross actual source types, explicit/naive/date input, plan/operand/
   without positions, UTC/Taipei/New York sessions, microsecond endpoints and
   DST gaps/folds. Manual expected populations, not reference-generated answers.
2. Hand data separates never-active entities, only-outside activity, exact start,
   just-before end, exact end, NULL times, repeated entity IDs and NULL amounts.
   Creation time deliberately differs from activity time. Count, distinct count
   and SUM must not collapse onto the same truth. Reuse the same interpretation
   across all instances/sessions.
3. PostgreSQL evidence uses inline typed VALUES in READ ONLY transactions under
   grepbit_ro, with SET LOCAL timezones. No tables/customer data read or written,
   no admin, no Gemma calls, opaque existing password file/env DSN. Synthetic
   DuckDB is in-memory and preserves physical source types in the ruler helper.
4. At the ruler checkpoint report expected assertion failures separately from
   setup failures. After explicit policy/implementation follow-up, repair
   shared typed binding, time scope/grain paths, synthetic type fidelity and
   reference evaluation; run focused, PostgreSQL cross-session and broad gates.
5. Replay stored plans from the previous study after repair. Do not count a
   manually corrected plan as a model success or rewrite old scores. Cross-shape
   definition availability and refusal-reason evaluation remain later studies.

## Closeout

Implemented shared typed-value and calendar-boundary binding, source-aware grain/
latest handling, canonical-value selfcheck, and independent reference-filter
interpretation. Synthetic data and DuckDB preserve wall-clock source types.
No introspector/schema migration, model call, prompt/gate change or DB write.
Final focused 146, PostgreSQL cross-session 181, offline 2,169, static pass;
the final broad rerun follows an uppercase type-name compatibility repair.
39 stored plans replayed: four previously wrong unzoned plans now match, 25 prior
matches retained, ten other wrong plans remain wrong. Four differential runs:
1,184 agreements, zero disagreements/DB errors. See
`../research/typed-time-boundary-01.md` for evidence limits and fingerprints.

## Primary references

- PostgreSQL timestamp input/type semantics:
  https://www.postgresql.org/docs/18/datatype-datetime.html
- PostgreSQL invalid/ambiguous local-time policy:
  https://www.postgresql.org/docs/18/datetime-invalid-input.html
- DuckDB distinguishes TIMESTAMP clock values from TIMESTAMPTZ instants:
  https://duckdb.org/docs/current/sql/data_types/timestamp.html
