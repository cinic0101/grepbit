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
  "limit": 5
}
```

- measures: 1 to 4; each is `aggregate` (sum, count, count_distinct, avg,
  min, max) over a column, `count` without a column, or `metric` (an overlay
  id). sum and avg need numeric columns; min and max need ordered kinds.
- dimensions: up to 3 columns of the base table or a table reachable by
  foreign keys away from the base (parent, grandparent, up to 3 hops).
- filters: up to 6; ops eq, ne, in, gt, gte, lt, lte, is_null, not_null;
  values typed against the column kind (numeric, boolean, text, timestamptz,
  date).
- time: one timestamp or date column; scope `month` (YYYY-MM), `range`
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

## PlanProposal

`{"decision": "plan", "plan": {...}}` or `{"decision": "none", "reason":
"semantic_gap" | "unsupported" | "ambiguous", "clarification": "..."}`.

## PlanError codes (compile time, structural)

`unknown_table`, `unknown_column`, `grain_conflict` (a table not reachable by
foreign keys away from the base, including child tables and unrelated tables),
`ambiguous_join_path` (two foreign keys to the same parent, or two chains of
the same length), `aggregate_kind_mismatch`, `filter_kind_mismatch`,
`time_column_kind_mismatch`, `time_scope_requires_grain`,
`relative_window_reaches_future`, `unknown_metric`,
`metric_base_table_mismatch`, `metric_conflict`.

`PlanCompiler.compile(plan, as_of=..., exclude_segments=[...])` also takes
the overlay segments the caller wants excluded by default; each applied one is
a `reviewed` assumption (see `overlay-format.md`).

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
literal matched no row, `clarify`, with the literal named in the
clarification), `plan_<PlanError code>` (compile-time structure,
`unsupported`).

## Assumption sources

`reviewed` (from the overlay: metric definitions, default segment
exclusions), `candidate` (inferred join, schema-only meaning, question filters
on a metric), `default` (server defaults: LEFT JOIN keeps unmatched rows,
NULLs ignored by aggregates, time window boundaries, no filter applied).

After execution the runner adds a `warnings` entry when the answer has no
rows or a single all-NULL row (an aggregate over zero rows), so the caller
does not read NULL as a number.

## Prompt revisions

`PLAN_PROMPT_REVISION` in `adapters/litellm/plan_client.py` is `plan-classify-json-v7`.
History: v1 baseline; v2 prefer an entity's label column over its key; v3 a
business concept with no column, sample value or null check must decline;
v4 reviewed metrics rule (only when an overlay is present); v5 follow-up rule
(only when a previous turn is present) and week, quarter, year units; v6
(2026-09-09, after the owner's 50 questions) per-period questions set grain
without inventing a window, relative length counts units, `to_date` for
month-to-date, and the overlay rule names table aliases, value aliases,
default time columns and segments; v7 (same day) makes the time scope
optional when a grain is set, because v6's rule could not be followed while
the schema required a scope.
