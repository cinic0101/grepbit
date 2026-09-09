# Semantic overlay format

An overlay is a JSON document per datasource, loaded by
`adapters/overlay_store.py`, validated against the introspected schema by
`application/overlay.py::overlay_problems`. Example: `evals/fixtures/pos_overlay.json`.

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

## Rules

- Names in any language; the planner matches them itself (measured on
  Chinese, English and Japanese).
- Every identifier must exist in the schema; `overlay_problems` lists the
  ones that do not, and the runner refuses to start with an invalid overlay.
- Overlays are data with provenance, not code. Drafting tooling and a review
  step are planned (`../plan/next-phase.md`); until then they are edited by
  hand and the revision string is bumped on every change.

## What the overlay cannot express yet

Expressions across columns (base salary plus bonus as one metric), ratios,
window functions, metrics whose base table differs from the question's
dimension table. These need algebra changes, not overlay changes.
