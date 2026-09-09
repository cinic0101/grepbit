# Enum columns on the real POS database (2026-09-09)

## Question

The owner's real POS test database (`t2s_8c2b8bbc_6d072f83`, a copy of the
production schema with test data, 9 tables, 33 columns, 8 declared foreign
keys) has one column of a PostgreSQL enum type, `pos_payment.payment_method`,
with 13 English snake_case labels (`cash`, `credit_card`, `line_pay`, ...).
Introspection reported it as kind `other`, type `USER-DEFINED`, no sample
values. What does the planner do with a Chinese question about a payment
method, and what does the fix cost?

## Method

- Seven author-written compatibility cases, `evals/cases/tier0/pos_real_smoke.yaml`:
  three filter on a payment method named in Chinese (信用卡, LINE Pay, 現金),
  one groups by payment method, two exercise ordinary joins and time windows
  on this schema, one is a semantic-gap probe (毛利率). Smoke only: written
  after reading the schema.
- Both runs: `gemma-4-31b`, prompt `plan-classify-json-v5`, no overlay,
  `--enum-distinct-limit 0` (no row value reaches the model),
  `--redact-rows` (no row value in the artifact), sequential.
- Change under test (`postgres-introspect-v2`): a column whose type is an
  enum is reported as kind `text`, type `enum <name>`, with the labels read
  from `pg_enum` as its sample values. Labels are type metadata, so they are
  shown whatever the sampling limit and the column is never sampled. The
  compiler compares enum columns as text (`CAST(col AS TEXT) = %(f)s`), because
  PostgreSQL raises on a literal outside the labels instead of matching no
  row.

## Results

| Run | Correct | Statuses | P50 / P95 | Artifact (`evidence/spike-tier0/`) |
|---|---|---|---|---|
| before, enum as `other` | 4/7 | 2 `semantic_gap` (no spelling for 信用卡, 現金), 1 `failed` 22P02 (literal `LINE Pay` against the enum), 4 correct | 3.2 / 4.8 s | `pos-real-smoke-before.json` |
| after, enum as text with labels | 7/7 | filters `credit_card`, `line_pay`, `cash`; the gap probe still refuses | 3.1 / 4.2 s | `pos-real-smoke-after.json` |

The three flipped cases are exactly the ones that needed a label spelling.
The `failed` run is the class the cast removes: the model guessed a literal,
the database raised, and the answer was a driver error rather than a refusal.
With the cast the same guess would match no row; the literal existence check
(next slice) turns that into `clarify`.

## What this says

- Enum labels are the one kind of "sample value" that carries no personal
  data by construction; they belong in the payload independent of the PII
  decision on row sampling.
- On this schema, with row sampling off, the planner is left with column
  names and comments only for `store.store_name`, `salesperson.sales_name`
  (PII), `transfer_status.status`, `category_name`, `product_name`. Every
  Chinese spelling of a stored English or abbreviated value in those columns
  is a refusal until the column whitelist exists.
- Seven cases are a compatibility check, not a measurement of the real
  questions; the numbers above say the schema is usable, nothing more.
