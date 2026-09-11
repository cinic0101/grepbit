# Tier-0 contract

## QueryPlan (domain/plan.py)

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
  within each period when the plan has a grain, via a window function). When
  operands carry different reviewed filters each aggregate gets its own
  `FILTER (WHERE ...)`; a single metric keeps its filters in `WHERE`. An
  operand may also carry up to 2 `filters` of its own (會員交易佔比 as
  `count where member_id not_null / count`), compiled as `FILTER (WHERE ...)`
  on that aggregate alone and shown in the lineage as `count(*) where ...`.
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
  aggregate expression as SQL HAVING with the value bound. Added after
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
| `aggregate_kind_mismatch`, `filter_kind_mismatch`, `time_column_kind_mismatch` | `unsupported`; the planner payload already states kinds, a recurrence is a prompt matter |
| `time_scope_requires_grain` | `unsupported`; recurrence would argue for deriving grain from a multi-period scope |
| `relative_window_reaches_future` | `unsupported` with the window in the detail. Since 2026-09-10 it also fires for a window anchored on the current unit (offset 0) that is longer than one unit; the planner adapter re-anchors that shape first (`relative window` repair below), so the gate is the safety net behind it |
| `unknown_metric`, `metric_base_table_mismatch`, `metric_conflict` | `unsupported`; overlay definitions are the fix, not code |
| `growth_to_date_unsupported` | `unsupported`: growth on a period-to-date window would compare a whole previous period with a partial one (holdout 3 q01) |
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
| `repair_column_refs` | a relative window `offset 0, length L > 1` (not "to date") becomes `offset -L`: 最近 30 天 written as today plus the next 29 days has no data, the last 30 complete days is the only reading with data | `shape_repairs` (`relative window ...`) and an assumption |
| `repair_column_refs` | a relative window without `unit` takes the `grain` written beside it (本月截至今天 came back unit-less with grain month) | `shape_repairs` (`relative window without unit ...`) |
| compiler | a growth plan whose window is one unit of its grain (上週 with grain week; a calendar month with grain month) is widened one unit backwards so the previous bucket exists; the first bucket's growth is NULL | assumption (`widened by one ...`) |
| `repair_column_refs` | a bare `aggregate` written beside a `ratio` on the same measure is dropped (the operands carry their own aggregates; the validator would reject the pair); an aggregate with a column or a metric beside a ratio is left to fail | `shape_repairs` (`dropped aggregate ...`) |
| `repair_column_refs` | a `ratio` written on the plan instead of inside a measure moves into `measures`; a measure that is exactly one of its operands (alias aside) is dropped as the same thing spelled twice. Nothing moves when a measure already carries a ratio | `shape_repairs` (`lifted plan-level ratio ...`, `dropped measure ... spelled inside the ratio`) |
| `repair_base_table` (application) | the base moves to the child table holding every measure column, or to a metric's base | assumption |
| `single_period_misread` (application) | a per-period word (`period_words` of the shape pack) answered with the single current unit is a `clarify`, never a rewrite | `per_period_single_window` |
| `unrequested_grain` (application) | a grain without a window when the question has no per-period or trend word is dropped: 同期 with no period word means one whole-window value per group | `shape_repairs` (`dropped grain ...`) and an assumption naming the words that ask for a breakdown |
| after-share selection (compiler) | with a `share_of_total` measure, a filter on a grouped column selects rows after the share (outer `WHERE` over the grouped subquery), so 特約永和中正 佔全部門市 divides by every store; filters on other columns still shape the population | lineage `[after share] ...` and an assumption |

The share assumption states the 同期 reading explicitly: the total is taken
over the same window and filters as the group values; with a grain, each
period's own total. A datasource that needs a different default has no
overlay construct for it yet (`../plan/next-phase.md`).

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

`PLAN_PROMPT_REVISION` in `adapters/litellm/plan_client.py` is `plan-classify-json-v13`.
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
