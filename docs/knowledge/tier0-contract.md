# Tier-0 contract

## Exact PostgreSQL identifier binding (2026-09-15 correction)

The shared compiler preserves the catalog spelling of schema, relation, column
and output identifiers. Before serialization it quotes every AST Identifier
containing an ASCII capital, including nested latest/without/aggregate scopes.
Already-safe lowercase SQL is unchanged; this is not a SQL-text replacement and
does not modify literal values or bound parameters. The independent SQL reader
rejects unquoted ASCII-capital identifiers (`identifier_case_unquoted`) before
trusting SQLGlot's spelling-based comparisons. Quoting is identity preservation,
not permission to query another namespace; SQL policy remains unchanged.

This corrects a demonstrated ParentId/parentid JOIN collision, not planner intent.
Compiler revisions: `plan-compiler-sqlglot-v3-exact-identifiers` and
`plan-compiler-rows-v5-exact-identifiers`. See
`../research/identifier-row-wire-closeout-01.md` for PostgreSQL witnesses and
independent raw-response replay. Historical lowercase results are not regraded.

## Temporal repair preservation (integrated 2026-09-15)

After a model validation failure, the existing one repair turn must not silently
alter recognizable explicit timestamp range anchors in plan/without scopes.
`domain/temporal_repair.py` compares source-typed anchors, effective bounds,
inclusion, column and population scope using the approved binding policy below.
Naive instant/clock and equivalent midnight repairs remain legal; missing
identity, unresolved DST or unbound clock offsets are unverifiable, not guessed.
Effective-bound comparison includes recognizable existing same-column filters
in the original draft as well as the repair. Preserving an original stronger
restriction is legal; dropping it is changed. Unresolved original restrictions
or a missing/unknown without.table are unverifiable, not confirmed changes.
Changed and unverifiable repairs retain the existing public operational failure
`failed / invalid_structured_output`, not a successful semantic refusal.
Preserved/not_applicable do not certify user intent; initial valid plans,
unreadable drafts and other semantic changes are outside this narrow check.
Safe declines and unrelated repairs remain available. No extra model call,
prompt change or public field; internal `last_temporal_repair_audit` distinguishes
all four outcomes and resets per request. The historical research wrapper reuses
the production check. Evidence: `../research/production-time-closeout-01.md`.

## Typed time binding (owner approved 2026-09-15)

`SchemaColumn.data_type`, retained from PostgreSQL information_schema, determines
storage semantics even though both timestamps share ColumnKind.TIMESTAMP.
No new schema field or inferred source timezone is introduced.

- `timestamptz`: offset-bearing literals denote instants. Naive timestamp/date
  boundaries use the configured datasource business timezone, with an assumption.
  Ambiguous/nonexistent local instants refuse (`timestamp_local_ambiguous`,
  `timestamp_local_nonexistent`); request an explicit offset, do not choose a fold.
- `timestamp without time zone`: compare naive clock values with timestamp
  parameters, not timestamptz. An offset-bearing input refuses
  `timestamp_zone_binding_required`: a type does not establish stored UTC or a
  local source zone. There is no reviewed column-zone binding feature yet.
- DATE literals retain dates; timestamps against DATE refuse
  `date_literal_precision_loss`. Raw filter operators remain unchanged; EQ is
  not broadened into a whole-day predicate by this binding layer. Existing
  planner date-literal normalization remains separate.
- More than six fractional digits refuse `timestamp_precision_unsupported`;
  unknown timestamp storage and invalid configured zones have typed failures.
  Plan, operand/ratio, reviewed filters, without and row-filter paths share the
  same binding. Calendar windows, grain and latest use source-appropriate types.

Changing session timezone must not change the selected population. The server
does not implement this by fixing the session timezone. SQL selfcheck verifies
the canonical bound literals using schema context; it does not skip timestamps.
Compiler revisions: `plan-compiler-sqlglot-v2-typed-time` and
`plan-compiler-rows-v3-typed-time`. The saved plan and prompt v15 remain unchanged;
execution parameters/assumptions and new typed refusal reasons reflect this
approved semantic correction. Tests and evidence: `../plan/typed-time-boundary.md`,
`../research/typed-time-boundary-01.md`.

## Explicit details request (2026-09-15)

MCP/Web `ask` accepts optional `query_kind: "default" | "rows"`, defaulting to
the existing per-datasource strategy. The response echoes the invocation's kind,
including failures after mode validation; errors before validation do not echo
untrusted modes. It is request metadata, not a semantic verification level.
`allow_rows` remains a separate operator permission. A disabled source returns
unsupported/row_queries_disabled before binding or planning. Invalid kinds are
input errors. The original Web registry and default planner messages are unchanged;
the separate `dev_web_rows_datasources.json` enables only synthetic sources.

Explicit rows uses the measured caller-kind instruction and narrowed displayed
schema `details-schema-only-v21-study` (historical identifier retained on adoption).
Only base_table/rows/filters/order/limit are displayed with complete refusal
branches; canonical wire/normalization and Default/fallback remain unchanged.
Direction is still optional and OrderSpec still defaults to desc. This is not
the SQL grammar's direction default. There is no router or legacy-first fallback.
v20 was the full-schema parent delivery; v19 was base-only. See
`../plan/details-schema-adoption.md` for the bounded adoption and order adjudication.
Every invocation gets its own planner. Shared ask checks the planner's final
proposal, after its wire normalization and any repair turn, but before
application normalization/compilation: an aggregate/latest proposal fails with
request_query_kind_mismatch, not a necessary refusal. Permission and kind checks
are not delegated to the model. Direct application callers configure the planner
for the same requested kind; the serving factory does this per request.
This is not draft-intent protection: an invalid aggregate draft may be repaired
into rows; only the final proposal is subject to this kind guard.

The question still determines population, columns and conditions. Explicit rows
does not authorize dropping a count/sum request, a lease scope, or a without
condition. Mode conflict is an ambiguous proposal; unrepresentable rows combos
are unsupported; missing definitions are semantic_gap. These language decisions
remain fallible; the existing concept gate is unchanged. Reuse all row visibility,
scope, grounding, ordering, NULL/duplicate, limit and lifecycle rules below.
References: `../plan/explicit-rows-entry.md`. No automatic routing promotion.

### Unique-parent attributes (owner approved 2026-09-15)

An explicit rows projection may add columns from one direct parent with one
declared single-column FK targeting that parent's sole PK column. It does not
allow inferred projection links, self/reverse/multi-hop joins, two projected
parents, or FK-to-non-PK-UNIQUE projections. Such UNIQUE links remain in the
common graph for existing aggregate/segment use; this is a rows eligibility rule.

LEFT JOIN preserves one row per base record AFTER existing filters/reviewed
segments/exclusions and BEFORE LIMIT/truncation. Parent-only projection still
preserves duplicate parent values. Missing parents yield NULL unless existing
population restrictions already exclude the base record. The one-parent limit
does not cap existing population JOINs. Self-check receives population edges
and the pre-projection predicate from the separately compiled population carrier,
not an allowlist inferred from the final SQL. Existing inferred population links
to a proven single PK retain their candidate disclosure; they do not authorize
new parent projection. All used relations must avoid inheritance expansion.

Parent outputs use a quoted, **flat** `table.column` key; base names are unchanged.
Aliases over 63 bytes refuse, never truncate. all_columns stays visible base-only;
base filters/order, row caps, NULLs and duplicate semantics are unchanged. Hidden
tables/projections/join keys refuse. Parent filtering/order, rows+without and child
expansion remain unsupported. No new per-datasource permission or default router.

Introspector v3 retains original FK columns separately from representable edges,
so omitting composite/cross-schema relations does not permit sampling, grounding
proposals or reinference of those keys. It records inheritance descendants;
rows on an expanded base/used parent refuse rather than introducing ONLY.
Metadata/digests change; affected default schema contexts require revalidation.
The 110 existing Default/fallback contexts on IoT/service stayed byte-identical.
Fresh schema metadata is assumed; concurrent DDL/stale snapshots are not covered.

Compiler: `plan-compiler-rows-v4-parent-projection`. Evidence and cost limitations:
`../research/parent-row-projection-01.md`. The earlier base-only pilot below is
historical where it conflicts with this approved extension.

## Opt-in base-row listing pilot (2026-09-14)

Scope/rulers: `../plan/base-row-pilot.md`. `DatasourceRegistration.allow_rows`
defaults false; disabled planners retain prompt v15 and compilers refuse
`row_queries_disabled`. Enabled profiles use `plan-v15-rows-fallback-v1`: run
unchanged v15 first, retain its plan/semantic_gap/ambiguous result, and only on
explicit unsupported try `plan-classify-json-v17-row-order` once. Only a rows
plan can be promoted; an aggregate fallback retains the original refusal.
`model_row_fallbacks` reports that extra stage; repairs are reported separately.
This preserves old proposals, not their correctness: a mistaken aggregate plan
for a listing bypasses the fallback. The pilot is not enabled in Web defaults.
No separate query tool or execution bypass is introduced. The public plan gains
optional `rows` and row lineage adds `projection`; capabilities disclose
`row_queries` per source. Runtime column policies are unchanged, not a PII
whitelist. Do not enable an unreviewed real datasource merely because rows work.

`rows: {columns: [ColumnRef, ...]}` or `rows: {all_columns: true}` lists individual
base-table records. It requires base_table, excludes measures/dimensions/time/
latest/without/having/growth, and allows existing plan filters/order/limit only.
Projection and question filters must belong to the base table. Resolve all
columns against current visibility; maximum 32, no SQL wildcard, duplicate
projection or silent hidden-column inclusion. A visible whole primary key is
required for deterministic ordering/tie breaking. As of 2026-09-15, explicit
order may name an unprojected visible base-table column. A qualified row order
must name that same base table. The sort key is disclosed and included in
semantic references, but is not added to output projection. NULLs sort last;
remaining primary-key columns break ties. Aggregate ordering stays output-only.
Unknown/hidden columns refuse; unsupported projection/unchecked combinations
give `row_projection_unsupported`. Parent-label row projection is not in this
pilot; reviewed segment predicates retain existing parent-join semantics.

Rows preserve multiplicity and NULL, never GROUP BY or DISTINCT. They always
carry `unverified_semantics`, explicit projection lineage and actual row-scope/
ordering assumptions, even with reviewed segments. Literal checks, opted-in
name binding/recompile, SQL policy and per-request lifecycle are the same ask()
path as aggregates. Projection does not certify an intended business scope.

Without a requested limit, no SQL LIMIT is added: executor/public caps detect
and expose `rows_truncated`. `row_count` is returned row count, not a second
query for total matches. Requested LIMIT is bound and separately described as
a subset; it does not promise all matching records. A NULL-only projected
record is not described as an aggregate over an empty population. No paging,
total-count query, input/output unit conversion or independent aggregate join
is added by this feature.

Named row tests cover filters/default segments/named-exclusion lifting,
visibility, qualified ordering, NULL/duplicates, LIMIT, shared grounding,
truncation and stop-before-execute. Ten generated row instances are compared
against independent Python ordering/projection oracles. The general differential
generator/reference evaluator does not yet generate this new row kind; do not
claim full algebra differential closure. All older construct scores are retained.
The research rows wrapper now follows the shared limit of two explicit sort
keys (formerly three in that research-only format); old study evidence is not
regraded or claimed compatible with that narrowed experimental wire.
The row compiler was `plan-compiler-rows-v2` before the typed-time correction above.
Historical query-kind study arms
pin their measured v16 prompt; `query-kind-joint-v1` is still research-only and
does not replace the runtime fallback strategy.

## MCP serving boundary v2 (2026-09-14)

The owner authorized public/debug separation and request-lifecycle work. MCP
v2 removes `raw_output`, `raw_output_repair`, `question_values` from its public
response; existing required answer/disclosure fields remain. A new opaque
`request_id` identifies each invocation but grants no cancellation authority.
Future internal AskResult fields are not automatically public. The internal
AskResult and runner's diagnostic access remain unchanged. Public SQL parameters,
grounding and rows can still contain authorized data: this is NOT a universal
PII-redaction guarantee. A second row cap also sets `rows_truncated` truthfully.

Operational failures are `failed`, never necessary semantic refusals. Whole
request expiry yields `request_timeout`; unexpected backend exceptions become
`request_failed` without raw exception details. Native DB errors retain their
typed codes when they occur before the whole deadline. Protocol cancellation
does not fabricate a result. Relay rules distinguish failed from refused.

The 30-second default total deadline is server-configurable and includes the
worker queue, cold binding, model retries/repair, checks, DB and result preparation.
Native per-call caps use remaining time; late results and later stages are
suppressed after stop. Cancellation cleanup may use two additional seconds.
Remote inference termination, transport write latency, arbitrary hostile worker
termination and high-load capacity guarantees are not claimed. Request ownership
and exact tests are in `../plan/serving-lifecycle.md`; query algebra, prompt v15,
gate policy, verification meanings and historical acceptance scores are unchanged.

Owner-approved scoped name binding (2026-09-13, `ask-orchestration-v5`):
`../plan/name-boundaries-ruler.md` extends opted-in visible TEXT EQ/IN binding
to measure, ratio-operand and `without` filters. Exact stored strings win;
normalized-only collisions remain ambiguous, preserving distinct candidates
in hints and resolution. Candidate hints are not intent certification.

Earlier negative name binding (2026-09-13, `ask-orchestration-v4`):
`../plan/negative-name-grounding.md` defines binding assurance for model-authored
text NE on visible, explicitly groundable overlay columns: plan, measure extra
filters, either ratio operand and `without.filters`. Missing literals resolve
in place through the existing index, followed by compilation, policy and
existence rechecks; ambiguous, absent, unavailable or stale bindings clarify
before execution. An injected index does not authorize a column. Reviewed
metric/segment definitions, ordinary non-grounded exclusions, SQL NULL behavior
and existing EQ/IN coverage are unchanged. An intentional exclusion of an absent
name on an opted-in column can also clarify; the owner accepted that tradeoff.
Grounding is disclosed, not promoted to proof of intent. Existing research
bypasses remain bypasses, not safety claims. The original red checkpoint is
retained separately; its 53 behavior rulers now pass without changed expectations.

## Owner-approved period semantics (takeover after 746f168)

The owner explicitly accepted the four defaults below and requested fewer
hardcoded language triggers for multilingual generalisation. The new value
rulers are `tests/contract/t0/test_period_semantics_ruler.py`; their answers
are hand-computed, with compiled SQL (in-memory DuckDB) and the Python
reference checked separately. The same hand-computed cases can also run as
read-only PostgreSQL SELECTs over inline synthetic data; see
`../plan/active-work.md` for executed validation and artifact locations.

- **No lexical growth deletion.** Neither a missing rate word nor a matched
  comparison word is sufficient evidence to delete a growth entry. Retire
  the deletion mechanism, not just its default switch. The legacy-pack
  assertion in `test_ask_contract.py` now passes: the functions, result field,
  repair label and unused trigger lists have been removed (shape pack v9;
  `ask-orchestration-v2` no longer emits `growth_dropped`).
  This does not approve arbitrary extra measures or change historic scores.
- **Adjacent calendar periods only.** Growth compares the same group's
  current bucket with the immediately preceding calendar bucket of its
  grain, in the datasource business timezone. A missing previous bucket,
  NULL current/previous value, or zero previous value yields NULL, not zero.
  Do not manufacture missing rows or jump to the last observed period.
  A one-unit scope may still widen as documented below to fetch the prior
  bucket. SQL checks the lagged bucket against one calendar unit earlier;
  the reference uses its own calendar arithmetic. Both pass the gap rulers.
- **NULL times are not periods.** A grain excludes rows whose effective time
  column is NULL, with an assumption. Unperiodized totals retain them unless
  another explicit filter/window excludes them; totals need not reconcile
  across those two populations. Already implemented, now explicitly approved.
- **Thresholds select after share/growth.** Compute over the pre-threshold
  population, then apply `having` as output selection. A below-threshold
  period still exists for growth; it is different from an absent period.
  A=80, B=20 with threshold >50 returns A at 80%, not 100%. January=100,
  February=20, March=120 with threshold >50 leaves March at 500%, not 20%.
  Already implemented, now explicitly approved. Requests to change the
  denominator population require a separately expressible plan, not a silent
  reinterpretation of this default.

The initial checkpoint had 23 intended failures; the owner then explicitly
authorised implementation. No new algebra, prompt revision, zero-fill policy
or extra-measure scoring rule is introduced. Historical evidence is unchanged.

## QueryPlan (domain/plan.py)

Owner-approved boundary, 2026-09-12: a ratio measure cannot carry nonempty
wrapper-level `filters`. Their scope was undefined and silently ignored by
the compiler. Domain validation rejects `plan_ratio_wrapper_filters_unsupported`;
unchecked in-memory plans are refused by the compiler with
`ratio_wrapper_filters_unsupported`, and SQL self-check flags the same shape.
Filters remain legal at plan scope (both operands) and independently on either
operand. Empty wrapper filters remain accepted. Neither share-filter movement
nor duplicate-aggregate normalization may erase a nonempty ratio-wrapper
filter to bypass validation. See `../plan/semantic-contrast-program.md` for
the red ruler and explicit follow-up approval. The compact shown schema remains
an overapproximation checked by domain validation; its text and v15 prompt are
unchanged. Previously accepted filtered duplicate-aggregate variants now refuse;
ordinary duplicate-aggregate forms without wrapper filters remain accepted.

Follow-up owner decision, 2026-09-12: **no lexical grain deletion**. An absent
or unrecognised period word is not evidence that a valid grain is unwanted.
Orchestration v3 removes `unrequested_grain`, `drop_grain`, `grain_dropped`,
the repair label and its misleading assumption. The ordinary compiler
interpretation/assumptions still describe the grouping. This does not approve
arbitrary extra grouping as correct or change golden scores. The separate
single-period clarification gate and its language data remain in force.
See `../plan/grain-retirement.md`; prompt v15 is unchanged.

```json
{
  "base_table": "pos_sale",
  "measures": [{"aggregate": "sum", "column": {"table": "pos_sale", "column": "total_amount"}},
               {"metric": "transaction_count"}],
  "dimensions": [{"table": "store", "column": "store_name"}],
  "filters": [{"column": {"table": "pos_sale", "column": "member_id"}, "op": "not_null"}],
  "time": {"column": {"table": "pos_sale", "column": "sale_date"},
           "scope": {"kind": "relative", "unit": "quarter", "offset": -1, "length": 1},
           "grain": "month"},
  "order": [{"field": "sum_total_amount", "direction": "desc"}],
  "having": [{"field": "sum_total_amount", "op": "gt", "value": 100000}],
  "limit": 5
}
```

- measures: 1 to 4; each is `aggregate` (sum, count, count_distinct, avg,
  min, max) over a column, `count` without a column, or `metric` (an overlay
  id). sum and avg need numeric columns; min and max need ordered kinds. A
  measure may instead be a `ratio` of two such operands over the same base
  (`{"ratio": {"numerator": {...}, "denominator": {...}}}`, compiled as
  `CAST(a AS DOUBLE PRECISION) / NULLIF(b, 0)`), and any measure may carry
  `share_of_total: true` (divided by the same measure summed over all groups,
  within each period when the plan has a grain, via a window function; with
  no groups and no grain the share is the part over the whole, see the rule
  table below). When
  operands carry different reviewed filters each aggregate gets its own
  `FILTER (WHERE ...)`; a single metric keeps its filters in `WHERE`. An
  operand may also carry up to 2 `filters` of its own (會員交易佔比 as
  `count where member_id not_null / count`), compiled as `FILTER (WHERE ...)`
  on that aggregate alone and shown in the lineage as `count(*) where ...`;
  a reviewed-metric operand keeps them too (店A的銷售額 / 店B的銷售額 as
  `gross_sales where store eq A / gross_sales where store eq B`), and a plan
  with such filters is at most `partially_verified`.
- latest: `{"order_by": [{"column", "direction"}...], "take": [<columns>]}`
  returns, per group of the dimensions, the single most recent base row
  ranked by `order_by` (the compiler appends the base table's primary key
  descending as the tie-breaker when only one column is given, and says so);
  `take` are the columns returned from that row. `measures` must be empty,
  `base_table` is required, no grain, no having or growth; filters, window
  and default segments apply before the choice. Compiled as `ROW_NUMBER()
  OVER (PARTITION BY dims ORDER BY ...)` in a subquery filtered to rank 1.
  The first shape whose result is a row's values, not an aggregate; its
  verification level is `unverified_semantics`.
- time scope `{"kind": "latest", "unit": day|week|month|quarter|year}` is the
  most recent unit that has base rows after the plan's other filters: the
  compiler emits `DATE_TRUNC(unit, (SELECT MAX(col) ... same filters))` as the
  window start and one unit later as the end, in the business time zone; it
  never consults `as_of`, and growth over it is refused.
- without: `{"table": <child>, "filters": [...], "time": {"column"?, "scope"}}`
  keeps only base rows with no matching row in a child table that references
  the base through foreign keys (up to 3 hops): entities with no activity
  (從未出現在銷售明細的商品, 沒有任何交易的門市). Compiled as a correlated
  `NOT EXISTS` whose inner query carries the child's own filters, its window
  (a scope, never a grain; the child's default time column when none is
  named) and the default-excluded segments on the child or on a table the
  child reaches through foreign keys (a return line is not sales activity;
  the segment's table is joined inside), each stated in the
  lineage (`[no rows in <child>]`) and as assumptions. `base_table` is
  required with it; filters or time columns outside the child are
  `without_filter_outside_child`; a table that does not reach the base is
  `without_table_not_a_child`.
- growth: up to 2 `{"measure": <output name>}` entries, each adding
  `<name>_growth` = (current minus previous period) / previous period per group
  with `LAG` over `period_start`; requires a grain. The first period is NULL.
  The previous bucket must be the adjacent calendar period;
  missing buckets are NULL growth, not skipped or zero-filled.
- base_table may be omitted when the operand columns or metrics determine it
  (the table among them that reaches the others through foreign keys);
  otherwise `base_table_undetermined`. It is required for a bare `count`.
- dimensions: up to 3 columns of the base table or a table reachable by
  foreign keys away from the base (parent, grandparent, up to 3 hops).
- filters: up to 6; ops eq, ne, in, gt, gte, lt, lte, is_null, not_null;
  values typed against the column kind (numeric, boolean, text, timestamptz,
  date).
- time: one timestamp or date column, or none when the overlay names a
  `time_defaults` column for the base table (`time_column_required`
  otherwise); scope `month` (YYYY-MM), `range`
  (start, end_exclusive), `relative` (unit day, week, month, quarter, year;
  offset 0 is the current unit; length counts units; `to_date` true ends the
  window after `as_of`'s day, for month-to-date and year-to-date), or
  `periods` (2 to N months). Grain day, week, month, quarter, year is required
  when the scope has several periods. Scope may be omitted when a grain is
  set: "every day" over all the data buckets without a window (before v7 the
  scope was required, which forced the planner to invent a window for 每天
  questions and it chose today). A past relative window (offset below 0)
  must not end beyond the current unit; unit week with length 7 is rejected as
  `relative_window_reaches_future`.
- order fields are output names (dimension column, measure alias, or
  `period_start`); limit is 1 to 200.
- having: up to 2 conditions on measures of each group (`field` is a measure
  output name; ops gt, gte, lt, lte, eq, ne; numeric value), compiled onto the
  aggregate expression as SQL HAVING with the value bound for plain aggregates;
  beside share or growth it selects output rows after those calculations.
  Added after
  holdout 2, where four "groups whose total exceeds N" questions were
  answered without the threshold. A row condition stays in `filters`; the
  planner rule says which is which.

## PlanProposal

`{"decision": "plan", "plan": {...}}` or `{"decision": "none", "reason":
"semantic_gap" | "unsupported" | "ambiguous", "clarification": "..."}`.

## PlanError codes (compile time, structural)

`unknown_table`, `unknown_column`, `grain_conflict` (a table not reachable by
foreign keys away from the base, including child tables and unrelated tables),
`ambiguous_join_path` (two foreign keys to the same parent, or two chains of
the same length), `aggregate_kind_mismatch`, `filter_kind_mismatch`,
`time_column_kind_mismatch`, `time_scope_requires_grain`,
`relative_window_reaches_future`, `base_table_undetermined`,
`time_column_required`, `unknown_metric`, `metric_base_table_mismatch`,
`metric_conflict`.

Every code has a remedy, decided 2026-09-10 so that a recurring code is a
work item, not a surprise (the regression summary counts them as
`plan_error_counts`):

| Code | Remedy |
|---|---|
| `unknown_table`, `unknown_column` | shape repair when the name resolves to one table (`repair_column_refs`); hidden identifiers stay unknown by design; otherwise `unsupported` |
| `grain_conflict` | base repair when every raw measure column sits on one child table that reaches the base (`repair_base_table`); otherwise `unsupported`, the plan would fan out |
| `ambiguous_join_path` | `unsupported` today; the candidate remedy is a typed `clarify` naming the two paths |
| `aggregate_kind_mismatch`, `filter_kind_mismatch`, `time_column_kind_mismatch` | `unsupported`; the planner payload already states kinds, a recurrence is a prompt matter. Since 2026-09-11 `aggregate_kind_mismatch` also refuses a ratio, share, growth or having whose operand is not numeric (a min or max of a date or text: PostgreSQL 42846 and 42883, found by the differential), and growth on a share is rejected at validation as `plan_growth_on_share` (LAG over a window: 42P20). Since 2026-09-11 `filter_kind_mismatch` also fires for a literal on a date or timestamp column that does not parse as one, with the literal in the detail, instead of PostgreSQL 22007 at execution |
| `time_scope_requires_grain` | `unsupported`; recurrence would argue for deriving grain from a multi-period scope |
| `relative_window_reaches_future` | `unsupported` with the window in the detail. Since 2026-09-10 it also fires for a window anchored on the current unit (offset 0) that is longer than one unit; the planner adapter re-anchors that shape first (`relative window` repair below), so the gate is the safety net behind it |
| `unknown_metric`, `metric_base_table_mismatch`, `metric_conflict` | `unsupported`; overlay definitions are the fix, not code |
| `growth_to_date_unsupported` | `unsupported`: growth on a period-to-date window would compare a whole previous period with a partial one (holdout 3 q01) |
| `ratio_operands_identical` | `unsupported`: the numerator and denominator resolve to the same aggregate once a reviewed metric is expanded (`count(*)` over `all_alerts`), so the ratio is 1 for every row; the plan-level twin (two literally identical operands) is refused at validation as `plan_ratio_operands_identical`, and a `latest` scope inside `without` as `plan_without_takes_no_latest_scope`. All three were found by the generated-plan properties on 2026-09-11 |
| `share_requires_groups` | `unsupported` with the remedy in the detail: a `share_of_total` with no groups and no periods, whose operand carries no filter of its own, would be 1 for every row (the window total is the value itself); name the groups or ask for the part over the whole |
| `self_check_failed` | `unsupported` with the broken invariants in the detail: after compiling, the SQL is parsed back and checked against the plan (`adapters/sqlglot/plan_check.py`): every plan, operand and `without` filter is a predicate of its kind on its column; every filter literal is bound; no ratio divides an expression by itself; no window function without groups, a grain or growth; GROUP BY lists exactly the dimensions; a plan `having` is a SQL HAVING; `verified` only without question filters. Replays of the two 2026-09-11 wrong numbers are the tests |
| `without_table_not_a_child`, `without_filter_outside_child` | `unsupported`; the plan named a `without` table that does not reference the base, or a filter outside the child |
| `anti_join_required` | `unsupported` with the reason: `HAVING count = 0` over the base table's own rows can never match, the question wants entities with no rows at all (holdout 3 q10, q11); the anti-join construct is on the roadmap |

`PlanCompiler.compile(plan, as_of=..., exclude_segments=[...],
named_segments=[...])` also takes the overlay segments the caller wants
excluded by default and the ones the question named; each segment that
shaped the SQL, query-wide or per operand, is a `reviewed` assumption and is
listed in `CompiledPlan.applied_segments` (see `overlay-format.md`). The ask
result's `excluded_segments` is that list, never the set of defaults the
question merely failed to lift.

## Deterministic repairs and rules between the plan and the SQL

Each one is data-driven or structural, never a guess at meaning, and each
one leaves a trace: a `shape_repairs` entry, an assumption, or both.

| Where | Rule | Trace |
|---|---|---|
| `repair_column_refs` (planner adapter) | string column references resolved to one table; a sibling `table` key folded in; `null` extra keys dropped; `t.c` inside a column stripped; an empty `time` object dropped | `shape_repairs` |
| `repair_column_refs` | a relative window `offset 0, length L > 1` becomes `offset -L`: 最近 30 天 written as today plus the next 29 days has no data, the last 30 complete days is the only reading with data. Since 2026-09-11 the same when the window also carries `to_date` (the flag is dropped; a one-unit "to date" window, 本月截至今天, is left alone): with the flag the window had collapsed to as_of's day | `meaning_normalisations` (`relative window ...`) and an assumption |
| `repair_column_refs` | a relative window without `unit` takes the `grain` written beside it (本月截至今天 came back unit-less with grain month) | `shape_repairs` (`relative window without unit ...`) |
| compiler | a growth plan whose window is one unit of its grain (上週 with grain week; a calendar month with grain month) is widened one unit backwards so the previous bucket exists; the first bucket's growth is NULL | assumption (`widened by one ...`) |
| `repair_column_refs` | a bare `aggregate` written beside a `ratio` on the same measure is dropped (the operands carry their own aggregates; the validator would reject the pair); an aggregate with a column or a metric beside a ratio is left to fail | `shape_repairs` (`dropped aggregate ...`) |
| `repair_column_refs` | a `ratio` written on the plan instead of inside a measure moves into `measures`; a measure that is exactly one of its operands (alias aside) is dropped as the same thing spelled twice. Nothing moves when a measure already carries a ratio | `shape_repairs` (`lifted plan-level ratio ...`, `dropped measure ... spelled inside the ratio`) |
| `repair_base_table` (application) | the base moves to the child table holding every measure column, or to a metric's base | assumption |
| `constant_dimensions` (application) | a dimension the plan's own equality filter fixes to one value (`by store_name` beside `store_name = X`) is not returned: it would repeat on every row; the filter still applies. Owner's decision 2026-09-11; latest-row plans and plans with a `share_of_total` measure are left alone (there the after-share selection is the reading) | `shape_repairs` (`dropped constant dimensions ...`) and an assumption |
| `single_period_misread` (application) | a per-period word (`period_words` of the shape pack) answered with the single current unit is a `clarify`, never a rewrite | `per_period_single_window` |
| `unmapped_concepts` (application) | a business concept the question names (`concepts` of the shape pack, v6: returns, member, discount, cancellation, cost and margin, with their words in zh, ja and en) must leave a trace in the plan: a referenced column whose name carries one of the concept's keywords, a reviewed metric whose id or names carry it, or a default-excluded segment the question named. Otherwise `clarify` naming the word: 2025年12月退貨金額 answered as the month's total sales twice on 2026-09-11 | `concept_not_mapped`, `unmapped_concepts` |
| range clamp (compiler) | a `range` whose end lies after as_of's day (2025 asked, 2060-01-01 written) ends at as_of's day instead; a `to_date` window longer than one unit is refused (`relative_window_reaches_future`), the planner having re-anchored it first | assumption (`clamped to the end of as_of's day`) |
| after-share selection (compiler) | with a `share_of_total` measure, a filter on a grouped column selects rows after the share (outer `WHERE` over the grouped subquery), so 特約永和中正 佔全部門市 divides by every store; filters on other columns still shape the population. A plain `having` stays on the inner grouped query (the outer has no `GROUP BY`: 42803, found by the differential); a `having` beside a share or a growth measure is applied after them, as the outer `WHERE`, because SQL would run it before the window functions and shrink the share's total or make growth compare with the previous surviving period (found by the differential on random data) | lineage `[after share] ...`, `[after share and growth] ...` and an assumption |
| whole share (compiler) | a `share_of_total` with no groups and no grain whose operand carries a filter of its own is the part over the whole: the filter shapes the numerator only and the total is the same aggregate over every row of the window (會員交易佔比 came back as a filtered count with `share_of_total`, which the window form made 1.0). A reviewed metric's defining filters do not make a part (gross_sales excludes returns; over net sales holdout 2 q21 came out 1.232 on 2026-09-11), so a metric share with no groups and no operand filter is refused (`share_requires_groups`) | lineage `... / count(*) [the whole]` and an assumption |

The share assumption states the 同期 reading explicitly: the total is taken
over the same window and filters as the group values; with a grain, each
period's own total. A datasource that needs a different default has no
overlay construct for it yet (`../plan/next-phase.md`).

## Construct matrix (2026-09-11)

Every measure kind against every row construct it can meet. A cell names the
contract test that compiles that pair, or the validation error that excludes
it, or says **gap**. The two wrong numbers of 2026-09-11 were both gap cells
(operand filter with share; operand filter with a metric). A new construct
adds a row or a column and fills every cell before it merges; gap cells are
covered generically by the generated-plan properties (`test_plan_properties.py`,
every valid plan compiles or raises a typed error and the self-check
invariants hold) and closed one by one with a value test.

| measure \ rows | plan filter | operand filter | default segment | named segment | time window | grain | latest | without |
|---|---|---|---|---|---|---|---|---|
| raw aggregate | `test_enum_filters_compare_as_text...`, `test_null_checks_and_count_distinct...` | `test_an_operand_may_carry_its_own_filters...` | `test_default_exclusion_adds_the_inverse_filter...` | `test_excluded_segments_are_lifted_when_the_question_names_them` | `test_count_with_month_window_binds_boundaries...` | `test_monthly_grain_buckets_in_business_timezone...` | excluded: `plan_latest_excludes_aggregates` | `test_without_compiles_an_anti_join...` |
| reviewed metric | `test_extra_question_filters_or_candidate_metrics_are_only_partially_verified` | `test_a_metric_operand_keeps_its_own_filters` | `test_default_segment_becomes_operand_level_when_one_operand_selects_it` | **gap** | `test_time_column_defaults_to_the_overlay_time_default_of_the_base` | **gap** | excluded: `plan_latest_excludes_aggregates` | **gap** (a metric on the entity table) |
| ratio | **gap** | `test_an_operand_may_carry_its_own_filters...`, `test_a_metric_operand_keeps_its_own_filters` | `test_default_segment_becomes_operand_level...` (return ratio keeps gross sales) | **gap** | **gap** (b1_q34 is an eval case only) | **gap** | excluded | `test_service_hand_counted_values[without_ratio-*]` |
| share_of_total | `test_share_filtered_on_its_own_dimension_is_the_subset_share_of_the_whole` (after-share selection) | `test_a_share_with_no_groups_is_the_filtered_part_over_the_whole`, `test_grouped_share_and_growth_keep_their_windows`, `test_share_filter_on_a_grouped_column_becomes_the_after_share_selection` | **gap** (batch 1 q17 is an eval case only) | **gap** | `test_share_of_total_divides_by_the_window_total_over_all_groups` | `test_share_within_each_period_when_the_plan_has_a_grain` | excluded | `test_service_hand_counted_values[without_share-*]` |
| growth | **gap** | **gap** | **gap** | **gap** | `test_growth_on_a_single_period_window_widens...`, `test_growth_on_a_to_date_window_is_refused` | `test_growth_compares_each_period_with_the_previous_one_per_group`; adjacency value rulers in `test_period_semantics_ruler.py` (required: `plan_growth_requires_grain`) | excluded | `test_service_hand_counted_values[without_growth-*]` |
| having | `test_having_compares_the_aggregate_expression_with_a_bound_value` | **gap** | **gap** | **gap** | **gap** | `test_growth_threshold_hides_a_period_without_removing_its_comparison_value` (hand-computed SQL and reference values) | excluded | `count = 0` excluded: `anti_join_required`; `test_service_hand_counted_values[without_having-*]` |

The application-level normalisations are rows of their own: the
constant-dimension drop is skipped for plans with a share measure (holdout 2
q21, `test_a_share_asked_for_one_group_keeps_its_dimension`) and for
latest-row plans. Lexical grain deletion is retired; its removal and preserved
grain/ordering/share/growth invariants have gates/ask contract tests. Base
repair tests remain in `test_plan_compiler_contract.py`.

Having on a ratio or share is excluded (`plan_having_on_derived_measure`,
`test_having_cannot_target_a_derived_measure`); a ratio of identical operands
is excluded at validation (`plan_ratio_operands_identical`, found by the
generated-plan properties on their first run). Twenty-two gap cells on
2026-09-11; generated-plan properties provide structural coverage, not value
proof. At the takeover ruler checkpoint, the having/grain value cell above
is filled. Service hand-counted rulers subsequently fill ratio/share/growth/
having with `without`; 17 named-test gaps remain. The missing-period rulers pass.
Generated coverage is limited to what the strategies actually draw; named
segments are not covered by the current differential generator. Multi-hop
`without` and its combinations with ordinary measures/output selection are
now generated; value coverage is still bounded by the recorded plans.
The service rulers exposed and repaired a count-only shortcut in the
reference evaluator, not the compiler. `without` restricts the base rows,
then normal aggregation and output selection apply; reference rows remain
unlimited for the differential comparator's tie-aware LIMIT check.
Do not infer every matrix cell's value coverage from a clean run.

## Time closure (2026-09-11)

Every time shape a plan can carry and what the compiler does with it
(`tests/contract/t0/test_time_closure_contract.py`, one test per row;
as_of 2026-08-15 12:00 Asia/Taipei in the fixture).

| Shape | Outcome |
|---|---|
| `month` | that calendar month |
| `range` | as written; an end after as_of's day is clamped to it, with an assumption |
| `relative`, offset < 0 | the L complete units before the current one |
| `relative`, offset 0, length 1 | the current unit (whole) |
| `relative`, offset 0, length > 1 | refused `relative_window_reaches_future`; the planner re-anchors it to offset -L first, so the refusal is the safety net |
| `relative`, offset 0, length 1, `to_date` | the current unit up to the end of as_of's day |
| `relative`, `to_date`, length > 1 | refused `relative_window_reaches_future`; the planner drops the flag and re-anchors first |
| `relative`, offset -1, length 7, unit week (last week written as seven weeks) | refused `relative_window_reaches_future` |
| `periods` | one period each; needs a grain (`time_scope_requires_grain`) |
| `latest` | the most recent unit with rows, resolved in SQL |
| grain without scope | every row bucketed, no window; rows whose time value is NULL are left out (they are in no period), with an assumption |
| growth over a one-unit window | window widened by one unit backwards, with an assumption |
| growth with a missing period (no rows in February) | March growth is NULL, not a comparison with January. No February row is fabricated. Day/week/month/quarter/year, date/timestamp and per-group value rulers verify the accepted default |
| growth on `to_date` or `latest` | refused `growth_to_date_unsupported` |
| growth without grain | rejected at validation `plan_growth_requires_grain` |
| `without.time` with a grain, or a `latest` scope | rejected at validation |
| `latest` plan with a grain | rejected at validation |

## Verification levels (CompiledPlan.verification)

| Level | When |
|---|---|
| `verified` | every measure is a verified reviewed metric and the plan adds no filters of its own |
| `partially_verified` | every measure is a reviewed metric but some are candidates, or the plan adds question filters that are checked for structure only |
| `unverified_semantics` | at least one raw aggregate: column meanings come from the schema alone |

## Response statuses (as the runner reports them; the served contract is in `../history/spec-v0.2-catalog-first.md` Section 8)

`answered`, `clarify`, `semantic_gap`, `unsupported`, `unsafe`, `failed`.

Deterministic reasons (no model call, or before execution): `absent_concept`
(overlay, `semantic_gap`), `unsupported_shape:<id>` (language pack,
`unsupported`), `per_period_single_window` (a per-period question answered
for the current period only, `clarify`), `filter_value_not_found` (a text
literal matched no row and could not be resolved, `clarify`, with the literal
named in the clarification), `filter_value_ambiguous` (several stored values
resemble the literal, `clarify` listing them; only for groundable columns),
`plan_<PlanError code>` (compile-time structure, `unsupported`). A uniquely
resolved literal is not a refusal: the plan is answered with the stored value
and a `candidate` assumption that names the substitution and its similarity.

## Assumption sources

`reviewed` (from the overlay: metric definitions, default segment
exclusions), `candidate` (inferred join, schema-only meaning, question filters
on a metric), `default` (server defaults: LEFT JOIN keeps unmatched rows,
NULLs ignored by aggregates, time window boundaries, no filter applied).

After execution the runner adds a `warnings` entry when the answer has no
rows or a single all-NULL row (an aggregate over zero rows), so the caller
does not read NULL as a number.

## Prompt revisions

`PLAN_PROMPT_REVISION` in `adapters/litellm/plan_client.py` is `plan-classify-json-v15`.

**Wire v3 / A5 (2026-09-12, provisional implementation; not accepted).**
See `../research/a5-service-01.md`: binding works, but a repeated model-output
regression blocks promotion. Only when the request has eligible value
candidates, its filter schema additionally accepts `value_refs: [id, ...]`
instead of `values`. The `question_values` entries carry an opaque,
deterministic ID derived from the column and exact stored spelling. These
are references, not authorization tokens or global lookup keys; only the
catalog supplied in this request may resolve them. No additional database
lookup, fuzzy retrieval or persistent candidate cache is introduced.

Candidates are restricted to existing text columns explicitly groundable
and visible under the overlay. No overlay means no advertised candidate
catalog. The existing personal-column defaults and hidden-column policies
apply. This is not the deferred PII display/whitelist product feature.

`eq`, `ne` and `in` filters may use references at the plan, measure/ratio
operand or `without` level. Resolution verifies the exact column and ID,
then substitutes the exact stored string before normalisation and domain
validation. Mixed `values`/`value_refs`, empty/malformed references, unsupported
operators, wrong-column IDs and IDs absent from this request fail validation
with `candidate_reference_*`; the existing bounded repair turn may correct
the output, otherwise it is `invalid_structured_output`. Invalid references
never silently fall back to literal guessing. Ordinary `values` strings are
never interpreted as IDs. References themselves are not shape repairs.

The compiler, domain QueryPlan and saved follow-up plans still contain typed
literals, not IDs. No-candidate messages retain the original compact filter
schema. Reference usage and validation failures are recorded separately as
`value_references` and `value_reference_errors`; candidate availability is
not evidence of correct entity selection. `hinted_literal_misses` is only
the count of cases with both a hint and an unresolved literal; it does not
prove that the missing literal had a matching candidate on that column.
Live rollout evidence is recorded in `../plan/a5-and-service-fixture.md`.

**Wire contract v2 (2026-09-11, `adapters/litellm/plan_wire.py`).** The
schema the planner is shown is no longer the pydantic schema of the domain
models (11,838 characters with titles and docstrings) but a hand-built,
flat form of 6,671 characters built around what the model writes: every
column is the string `table.column`; a ratio is `numerator` and
`denominator` directly on the measure; `latest.order_by[].column`,
`latest.take[]`, `without.filters[].column` and `time.column` are strings
too; no titles, descriptions or defaults. The normaliser
(`normalize_variants`, then the reference walk) accepts a documented
superset and rewrites it to the domain models without guessing meaning:

| Accepted variant | Rewritten to | Recorded as |
|---|---|---|
| `numerator` / `denominator` beside a missing or partial `ratio` (batch 1 q49, five runs) | `ratio: {numerator, denominator}` | nothing: it is the shown form |
| `{"table": t, "column": c}` objects (the v1 form) | kept | nothing |
| `plan.columns` exactly duplicates the nonempty ordered `rows.columns` list of qualified strings or strict reference objects, with all_columns absent/false | drop only `plan.columns`; full validation still applies | `shape_variants` (`dropped exact duplicate plan.columns matching rows.columns`); **not** a meaning normalization |
| an alias in the question's language (銷售總額), or any quotable text up to 63 bytes; the `order`, `having`, `growth` fields that name it | kept; the compiler quotes it, so the column comes back under that name (owner's decision 2026-09-11) | nothing |
| a qualified output name in `order`, `having` or `growth` (`product.product_name`), or a qualified column inside its own reference | the bare name | nothing (unambiguous, owner's decision 2026-09-11) |
| a bare column name that resolves to one table (or the base table) | `table.column` | `shape_repairs` (`c -> t.c`) |
| `{"column": "c", "table": t}` | `t.c` when `t` owns `c` | `shape_repairs` |
| `{"column": {"table": t, "column": c}, "table": t}` on a measure, filter or operand (fu_base_payment) | the reference alone | `shape_repairs` (`dropped table beside the column reference`); a sibling naming another table is left to fail |
| a dimension wrapped like an `order_by` item, or carrying `alias`, `description`, `label`, `name` | the reference alone | `shape_repairs` |
| `grain` on the plan (the 12B control model) | `time.grain` | `shape_repairs` |
| `ratio` on the plan beside its operands as measures | one ratio measure | `shape_repairs` |
| `numerator` and `denominator` on the plan beside the operands spelled out as measures (holdout 2 q23) | one ratio measure, the spelled-out operands dropped | `shape_repairs` |
| an `aggregate` and `column` beside `numerator`/`denominator` that restate one operand (the repair turn on q23) | the ratio alone | `shape_repairs` |
| an alias that cannot be quoted at all (a quote or control character inside, more than 63 bytes) | its ASCII part, or `measure_N`; the `order`, `having`, `growth` items that named it follow | `shape_variants` |
| a non-ratio share measure whose own filter names a grouped column (holdout 2 q25: 1.0 for that group, 0 elsewhere) | the filter moves to the plan's filters, so the after-share selection applies; ratio-wrapper filters remain for rejection | `shape_repairs` |
| a month (`YYYY-MM`), day or year written as a filter literal on a date or timestamp column when the plan has no window (the 12B control: `sale_date IN ('2025-12')`, PostgreSQL 22007) | the time window it can only mean; the time column taken from the filter when the plan names none | `shape_repairs` (`date literal ...`) and an assumption |

Exact row-column deduplication does not accept reordered/different lists, a
top-level-only projection, empty/malformed lists, unqualified references or
all_columns=true. It does not canonicalize two different lists before comparing,
take a union, ignore unrelated extras or bypass permissions, kind, visibility,
compiler or SQL policy. The canonical shown schema/prompt are unchanged and
extra=forbid remains in force. Ordinary validation may still reject an identical
list (e.g. duplicate or unknown projections). Original noncanonical-output rate,
deterministic normalization count and model repair calls are distinct metrics;
the construct freeze is not relaxed by reducing model calls.

The repair list is read two ways (`ports/ask.py`, `is_meaning_repair`):
`shape_variants` are departures from the shown form that were rewritten
(the wire contract's health metric; the freeze on new constructs lifts when
they stay under 5% of cases on every set), and `meaning_normalisations` are
the rules that change what the plan means and say so in an assumption
(relative window re-anchored, unit from grain, date literal as a window,
share filter to the after-share selection,
constant dimension dropped). `shape_repairs` stays as their union in the
reports. Rules 8 to 10 (entities with no activity,
the latest row per entity, the latest period with data) enter the prompt
only when the question carries one of their trigger words
(`resources/unsupported_shapes.json`, `rule_triggers`, pack v5); the other
rules are always present. Prompt size on the POS fixture fell from 27,304
to 20,993 characters (21,461 with a rule pack) and on the real database
from 31,048 to 24,733.

**Repair turn (2026-09-11).** When the model's text fails to parse or to
validate, the planner adapter sends one follow-up in the same conversation:
its own text as the assistant turn, then the validation errors (path and
message, at most eight) with the instruction to return the corrected object
without changing tables, columns, filters or values. A plan that arrives this
way is served like any other and the row records `model_repair_turns: 1` and
the first text as `raw_output`, so every slip stays classifiable; a second
failure is `invalid_structured_output` with both texts kept.
`GREPBIT_MODEL_REPAIR_TURNS=0` disables it for ablations. Each call has a 20 s
budget (`GREPBIT_MODEL_TIMEOUT_SECONDS`), one transport retry, so a question
costs at most three calls.
History: v1 baseline; v2 prefer an entity's label column over its key; v3 a
business concept with no column, sample value or null check must decline;
v4 reviewed metrics rule (only when an overlay is present); v5 follow-up rule
(only when a previous turn is present) and week, quarter, year units; v6
(2026-09-09, after the owner's 50 questions) per-period questions set grain
without inventing a window, relative length counts units, `to_date` for
month-to-date, and the overlay rule names table aliases, value aliases,
default time columns and segments; v7 (same day) makes the time scope
optional when a grain is set, because v6's rule could not be followed while
the schema required a scope; v8 (same day, after holdout 2) adds the
`having` rule: a condition on a group's aggregate goes in `having`, never
dropped and never written as a row filter; v9 (same day) adds the
`question_values` rule, present only when the value index found a stored
value verbatim in the question: filter with exactly that value; v10
(2026-09-10) teaches `share_of_total`, `ratio`, `growth`, an omitted
`base_table` and an omitted `time.column`, and the language pack stops
refusing share and growth words; v11 (same day) restricts `growth` to
questions that ask for change and distinguishes a per-group share from the
share of a subset in the whole (a ratio with a restricted numerator).

v12 (2026-09-10 evening) adds rule (8): entities with no activity are a
`without` on the entity table, never `having count = 0`; measured in
`../research/holdout3-01.md`.

v13 (2026-09-11) adds rules (9) and (10): the latest row per entity is a
`latest` with `order_by` and `take` and no measures; the most recent period
with data is the time scope `{"kind": "latest", "unit": ...}`; measured in
`../research/holdout3-01.md`.

v14 (2026-09-11 afternoon) is the wire contract v2 above: the shown schema
is the flat compact form, column references are `table.column` strings, a
ratio is `numerator` and `denominator` on the measure, and rules 8 to 10 are
attached only on their trigger words; no rule changed meaning.

v15 (2026-09-12) adds request-scoped candidate references to rule 11 and the
conditional wire schema. Schema linking (A4) is deliberately not included.
