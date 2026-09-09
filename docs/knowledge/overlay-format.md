# Semantic overlay format

An overlay is a JSON document per datasource, loaded by
`adapters/overlay_store.py`, validated against the introspected schema by
`application/overlay.py::overlay_problems`. Examples:
`evals/fixtures/pos_overlay.json` (fixture) and `overlays/pos_real.json` (the
owner's real POS database; overlays for real datasources live under
`overlays/`, one file per datasource).

```json
{
  "datasource_id": "pos_test",
  "revision": "pos-overlay-experiment-v1",
  "metrics": [
    {
      "id": "return_amount",
      "names": ["退貨金額", "return amount", "返品金額"],
      "description": "Sum of pos_sale.total_amount over transactions that reference an origin transaction.",
      "base_table": "pos_sale",
      "aggregate": "sum",
      "column": {"table": "pos_sale", "column": "total_amount"},
      "filters": [{"column": {"table": "pos_sale", "column": "origin_transaction_no"}, "op": "not_null"}],
      "time_column": {"table": "pos_sale", "column": "sale_date"},
      "review_state": "verified"
    }
  ],
  "absent_concepts": [
    {"names": ["庫存", "inventory"], "note": "This datasource has no inventory data."}
  ],
  "column_aliases": [
    {"column": {"table": "pos_sale", "column": "total_amount"}, "names": ["營業額", "sales amount"]}
  ],
  "table_aliases": [
    {"table": "pos_sale", "names": ["訂單", "交易", "sales"]}
  ],
  "value_aliases": [
    {"column": {"table": "pos_payment", "column": "payment_method"},
     "values": [{"value": "credit_card", "names": ["信用卡", "刷卡"]}]}
  ],
  "time_defaults": [
    {"table": "pos_saleitem", "column": {"table": "pos_sale", "column": "sale_date"}}
  ],
  "segments": [
    {"id": "returns", "names": ["退貨", "退款", "returns"],
     "table": "pos_sale",
     "filter": {"column": {"table": "pos_sale", "column": "origin_transaction_no"}, "op": "not_null"},
     "default_exclude": true,
     "note": "transactions that reference an origin transaction are returns"}
  ],
  "column_policies": [
    {"column": {"table": "store", "column": "store_name"}, "sensitivity": "public"},
    {"column": {"table": "salesperson", "column": "sales_name"}, "sensitivity": "personal"},
    {"column": {"table": "pos_sale", "column": "receipt_no"}, "sensitivity": "public", "sample": false, "ground": true}
  ],
  "table_policies": [
    {"table": "transfer_status", "visible": false}
  ]
}
```

## Semantics

- A metric is a plan fragment: one aggregate, its defining filters, and
  optionally the time column the definition prescribes. The planner selects it
  with `{"metric": "<id>"}`; the compiler expands it, adds the definition as a
  `reviewed` assumption, and overrides the plan's time column when the metric
  prescribes one (stated as an assumption). `review_state: candidate` metrics
  answer but never yield `verified`.
- Absent concepts are matched deterministically against the normalized
  question (script-aware phrase match) before any model call and produce
  `semantic_gap` with the reviewer's note at zero cost.
- Column aliases are shown to the planner next to the column and are the
  vocabulary a future coverage gate will match question concepts against.
- Table aliases are the business names of a table (訂單 for `pos_sale`),
  shown on the table entry. They stop the planner reaching for a table whose
  name merely resembles the concept (`transfer_status` for 訂單狀態).
- Value aliases list reviewed stored values of a column with the names people
  use for them. They are the PII-safe substitute for row sampling: only what a
  reviewer listed reaches the planner, which uses the stored spelling as the
  literal. Enum labels come from the catalog anyway; value aliases add their
  business names and cover ordinary text columns.
- Time defaults name the time column questions about a table usually mean
  (`pos_saleitem` rows are dated by their sale's `sale_date`). Shown to the
  planner as `default_time_column`; the compiler does not enforce it.
- Column policies carry one reviewed fact per column, `sensitivity`
  (`public` or `personal`), and three switches derived from it, each
  overridable: `sample` (values may be shown to the planner as samples),
  `ground` (values may be indexed, looked up as candidates and shown in a
  clarification) and `visible` (the column is offered to the planner at all).
  Public defaults to all three on, personal to visible only. Grounding is
  opt-in: an unlisted column is visible and samplable but never grounded. A
  table policy with `visible: false` hides a whole table. Hidden tables and
  columns are absent from the payload and unknown to the compiler, so a plan
  cannot name them; a table left without a visible column fails validation.
  `evals/spike_tier0.py --propose-policies <file>` writes a deterministic
  draft (`application/policies.py`: kinds, keys, cardinality, person words in
  names and comments) to a file the runtime never loads; copying an entry
  into the overlay is the review.
- Segments are named row subsets defined by one invertible filter (`is_null`,
  `not_null`, `eq`, `ne`) on the segment's table. With `default_exclude` the
  server removes the subset from every plan over that table, or over a table
  that reaches it through foreign keys, unless the question names the segment
  (script-aware phrase match, `excluded_segments`) or the plan already filters
  on the segment's column (a return metric keeps its rows). Each applied
  exclusion is a `reviewed` assumption that tells the caller which word lifts
  it, and appears in the lineage as `[default: exclude <id>]`. The planner sees
  segments only as a note not to add filters for them.

## Rules

- Names in any language; the planner matches them itself (measured on
  Chinese, English and Japanese).
- Every identifier must exist in the schema; `overlay_problems` lists the
  ones that do not, and the runner refuses to start with an invalid overlay.
- Overlays are data with provenance, not code. Drafting tooling and a review
  step are planned (`../plan/next-phase.md`); until then they are edited by
  hand and the revision string is bumped on every change.

## What the overlay cannot express yet

Expressions across columns (base salary plus bonus as one metric), ratios and
shares (客單價, 退貨率, 佔比), derived dimensions (a CASE label such as
銷售/退貨 as a group-by), declared joins for schemas without foreign keys,
hidden tables or columns, hierarchies. These need algebra or format changes
and are listed for the next phase in `../plan/next-phase.md`.
