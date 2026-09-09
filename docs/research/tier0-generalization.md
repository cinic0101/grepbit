# Tier-0 generalization spike (2026-09-08)

Question: can `gemma-4-31b` answer aggregate questions over a PostgreSQL
schema it has never seen, with zero hand-written definitions, when the server
owns the algebra, the SQL, and the execution? The reinvention plan (ADR 0008)
assumed a reviewed catalog per datasource; this spike tests the tier below it.

Branch `spike/tier0` (from `dev`). Two days were budgeted; the live runs here
took one.

## What was built

| Piece | Module | Role |
|---|---|---|
| SchemaModel | `grepbit/domain/schema_model.py` | Tables, columns with kinds, primary and foreign keys, sampled enum values, content digest. No business meaning. |
| Introspection | `grepbit/adapters/postgres/introspect.py` | Reads `information_schema` plus `pg_catalog` constraints with the read-only role; samples distinct values only for text columns with at most 20 values and never for key columns. |
| QueryPlan | `grepbit/domain/plan.py` | Closed algebra: one base table, 1 to 4 measures (sum, count, count_distinct, avg, min, max), up to 3 dimensions, up to 6 typed filters, one time spec (month, range, relative, periods; optional day or month grain), order, limit. |
| Plan client | `grepbit/adapters/litellm/plan_client.py` | One JSON-mode call: rules, the plan JSON Schema, the schema payload, the question, `as_of`. Prompt revision `plan-classify-json-v2`. |
| Plan compiler | `grepbit/adapters/sqlglot/plan_compiler.py` (port `grepbit/ports/plan_compiler.py`) | Validates identifiers and kinds, walks foreign keys away from the base table only (no fan-out, up to 3 hops), resolves time windows server-side in the business timezone, builds the SQL as a sqlglot AST with bound placeholders, emits lineage, assumptions, and a one-line interpretation. |
| Policy | `grepbit/adapters/sqlglot/policy.py` | `PostgresSqlPolicy(tables=..., functions=...)`: the allowlist now takes the introspected tables and the plan aggregates. Defaults are unchanged for retail_v1. |
| Runner | `evals/spike_tier0.py` | Introspect, plan, compile, gate, execute read-only, compare rows with each case's reference SQL, honor accepted statuses, write a JSON report without credentials, bindings, or model text beyond the plan. |

The model never sees rows. It sees identifiers, kinds, comments, and the
sampled enum spellings, and it returns identifiers plus typed literals taken
from the question. Every answer carries the candidate assumption "column
meanings come from the schema only; no reviewed business definition was
applied", which is what the agent contract will surface as
`unverified_semantics`.

## Method

Two spike databases on the owner's PostgreSQL, owned by a `SELECT`-only role:

- `grepbit_spike_retail`: the retail_v1 fixture schema (5 tables, 4 FKs). The
  model was given no catalog, no templates, no synonyms.
- `grepbit_spike_iot`: a synthetic schema written for this spike
  (`evals/fixtures/iot_v1`): sites, devices, alerts, readings (4 tables,
  3 FKs, a two-hop path alerts -> devices -> sites).

Cases: `evals/cases/tier0/iot.yaml` (20) and `evals/cases/tier0/retail.yaml`
(12). Each answerable case has a reference SQL; the runner compares the
normalized result rows, not the SQL text. Refusal cases list the statuses that
count as correct. Chinese and English questions are mixed. The cases were
written by the agent before the first run, not by the owner, so this is a
smoke-level signal and not a holdout measurement.

Three live passes ran. After the first pass the prompt gained one rule
(prefer an entity's label column over its foreign-key id when grouping) and
the retail top-2 reference was changed to group by `display_name`; nothing
else was tuned between passes.

## Results (final pass, prompt v2)

| | IoT (unseen schema) | Retail |
|---|---|---|
| Cases correct | 20 / 20 | 12 / 12 |
| Answerable cases with rows equal to the reference | 15 / 15 | 10 / 10 |
| Refusal cases handled correctly | 5 / 5 | 2 / 2 |
| Answered when a refusal was expected | 1 (accepted, see below) | 0 |
| Model call failures or invalid JSON | 0 | 0 |
| P50 / P95 end to end | 2.7 s / 3.8 s | 2.7 s / 4.3 s |
| Introspection | 0.05 s | 0.03 s |

First pass (prompt v1): IoT 19/20, retail 12/12. The miss grouped downtime by
`devices.site_id` instead of `sites.site_name`; the totals were right, the
label was a key. Second pass (prompt v2): IoT 20/20, retail 11/12 for the
mirror-image reason (the model now grouped customers by `display_name`, the
reference still by id). The reference was corrected and the third pass is the
table above.

What the model got right without any definition: Chinese and English
questions on both schemas; enum spellings from samples (`critical`,
`offline`, `completed`); one-hop and two-hop parent joins; `count_distinct`;
`IS NULL` for "unresolved"; month, range, relative ("上個月"), daily and
monthly grains; top-N with order and limit; declining SLA compliance rate,
customer satisfaction, and profit margin as `semantic_gap`.

Accepted but worth noting:

- "What was the temperature last month?" was answered as `avg` with the
  assumption stated, rather than clarified. The case accepts either; the
  product rule for this (clarify versus answer-with-assumption) is undecided.
- "Forecast the number of alerts" came back `semantic_gap` rather than
  `unsupported`. Both refuse; the reason code differs.
- The two unsafe cases were stopped by the runner's language-pack check
  before the model, at zero cost.

## Decision: go

The spike passed its thresholds (at least 80% acceptable plans on an unseen
schema with zero definitions, every answer marked unverified, refusals for
out-of-scope asks, P95 under 5 s). Tier-0 becomes the default path of the
agent; the reviewed catalog becomes an overlay that upgrades verification for
the metrics a reviewer has signed, instead of a prerequisite for answering.

Known limits of tier-0, to be stated to callers rather than hidden:

- One aggregate query per question: no ratios or derived metrics (SLA rate,
  margin), no window functions, no HAVING, no sub-queries. These are
  `semantic_gap` until a reviewed metric defines them.
- Dimensions and filters only from the base table or its parents; a
  child-table dimension is a `grain_conflict`.
- Enum spellings are known only for text columns with at most 20 distinct
  values; other literal filters depend on the question's spelling.
- Correctness here is "rows equal the author's reference", not business
  correctness. Business correctness is exactly what the overlay is for.

## Next slices

1. Wire tier-0 into `StructuredAskService` and the served API behind the
   existing contract: template and catalog hits keep their path; everything
   else goes to the plan client, compiles, and answers as
   `unverified_semantics` with lineage, assumptions, and the interpretation.
2. Datasource registration (`grepbit datasource add`) that introspects,
   stores the schema digest with the run evidence, and refreshes on demand.
3. Decide and test the ambiguity rule for measure-less questions.
4. Replace the author-written cases with the owner's 30 to 50 real questions
   split into dev and holdout before any further prompt change.
5. MCP tool exposing `ask` and `capabilities` per datasource.

Artifacts: `.artifacts/spike-tier0/{iot,retail}-0[123].json` (local only, not
release authority). Verification: `tools/verify.py offline` 693 passed and
`static` passed on the committed tree.

## Addendum: a schema the agent did not design (text2sql_test, same day)

The owner pointed at `text2sql_test`, a fixture POS plus HR database on the
same server: 13 tables, 58 columns, 11 foreign keys, Chinese column comments
on the HR tables only, about 9.6k characters of schema payload. Traps it
carries: two employee tables (`employee` for store staff, `hr_employee` for
HR), `employee.store_id` with no foreign key to `store`, exchanges marked only
by `origin_transaction_no`, split payments that make `pos_payment` a child of
`pos_sale`, `paid_at` versus `period_start` on payroll, and `hr_assignment`
reaching `hr_dept` through two different paths. Cases:
`evals/cases/tier0/pos.yaml` (26, written by the agent after profiling the
data; answerable cases may list alternative reference readings).

| | Pass 1 (prompt v2) | Pass 2 (prompt v3) |
|---|---|---|
| Cases correct | 24 / 26 | 26 / 26 |
| Answerable rows equal to a reference | 19 / 20 | 20 / 20 |
| Refusal cases correct | 5 / 6 | 6 / 6 |
| Answered when a refusal was expected | 1 | 0 |
| P50 / P95 | 4.6 s / 6.1 s | 4.7 s / 6.3 s |

The two pass-1 misses:

- "2025年12月的退貨金額" was answered as the December sales total. The model
  dropped the concept 退貨, which nothing in the schema expresses, and
  answered a broader question. The interpretation line exposed it
  ("sum(pos_sale.total_amount) ... for 2025-12", no filter), but a caller
  would have received a number labelled as returns. This is the failure class
  that matters most. Prompt v3 adds one rule: every business concept in the
  question must map to a column, sample value, or null check, otherwise
  decline with `semantic_gap` naming the concept. With it the case declines;
  IoT (20/20) and retail (12/12) re-ran on v3 with no over-refusal.
- Bonus by month compared unequal only because `DATE_TRUNC` on a `date`
  column returns `timestamptz` in PostgreSQL; the compiler now casts date
  grains back to `DATE`. Not a model error.

Other things the run showed:

- Two same-depth join paths (an assignment's employee's department versus its
  project's department) are now detected by the compiler as
  `ambiguous_join_path`; the earlier search returned whichever it found first.
- Joins with no path (店 x 薪資, `employee` to `store` without a foreign key)
  were attempted by the model and stopped by the compiler, not declined by the
  model. The server-side check is the guarantee; the model is not.
- "各付款方式各有幾筆交易" counted payment rows, not distinct transactions. The
  numbers matched here only because every split payment used two different
  methods. Reviewed metrics exist for exactly this kind of subtlety.
- Latency grew with schema size (P95 3.8 s on 4 tables, 6.3 s on 13). Fifty
  or more tables will need schema retrieval before the plan call.

## Follow-up experiments (same day): no foreign keys, concept drops, parent agent

### 1. A database with no declared foreign keys

`grepbit_spike_pos_nofk` is a clone of text2sql_test with every foreign key
dropped (primary keys kept). Same 26 cases.

| | Declared FKs | No FKs, no inference | No FKs, inferred joins |
|---|---|---|---|
| Cases correct | 26 / 26 | 17 / 26 | 26 / 26 |
| Wrong answers | 0 | 0 | 0 |

Without keys every join question (9) was refused as `grain_conflict`; nothing
was answered wrongly. Join inference (`infer_foreign_keys`) then recovered all
11 declared keys with zero false positives: a child column must be named like
a single-column parent key (`store_id`, `<parent>_<key>`, or `*_<key>` for
keys more specific than `id`), have the same kind, and every sampled distinct
value must exist in the parent. `employee.store_id` was checked and rejected
by the data (its values are not store ids), which is the trap the schema set.
Inferred keys are marked, the compiler adds a candidate assumption ("the join
is inferred, not a declared foreign key") and lineage shows "(inferred)".
Limits: self-references and one-to-one key pairs are not inferred; a column
named `id` in the parent is matched only through `<parent>_id`.

### 2. Concept drops and a coverage audit

24 probes (`evals/cases/tier0/coverage_*.yaml`) each name a concept the
schema cannot express (誤報, 保固, 新客戶, 加班費, 分期付款, ...). The
dangerous outcome is an answer to a broader question.

| | Planner alone (prompt v3) | Audit v1 | Audit v2 |
|---|---|---|---|
| Probes refused by the planner | 22 / 24 | | |
| Planner drops (answered anyway) | 2 | | |
| Drops caught by the audit | | 1 / 2 | 0 / 2 |
| False flags on the 58 base cases | | 1 | 0 |
| Added latency per answered question | | 2 to 6 s | 2 to 6 s |

The two drops: "租賃裝置的月費總額" became the fee of all devices; "折扣後
營業額" became the plain sales total (defensible if `total_amount` is already
net of discount, but the assumption was never stated). The audit is a second
model call that maps each concept in the question to a plan element. Version
1 caught 租賃裝置 but flagged "overall" as uncovered in a base case; version 2
told it that words meaning no restriction map to "no filter", the false flag
disappeared, and it then mapped 租賃裝置 to "no filter" too. One wording
change flipped the outcome both ways. Conclusion: at this model size a
free-form LLM audit is not a reliable gate; the planner's own rule carries the
result (22/24). It stays in the runner as an experiment flag, not in the
product path. The interpretation line remains the most dependable exposure of
a drop, which is why it must be shown to the caller. Next thing to try: make
the planner emit the concept mapping inside its one call so the server can
reject a plan with an unmapped concept deterministically.

### 3. Does a parent agent keep the caveats?

14 tool results (8 answered, 6 refusals, across the three schemas) were given
to the same model acting as the user-facing agent, in three framings: guided
(rules: only returned numbers, restate assumptions, say no data), bare (no
rules), and bare with a tool-written summary sentence in the payload.

| | Guided | Bare | Bare + summary |
|---|---|---|---|
| Returned numbers preserved | 7 / 7 | 7 / 7 | 7 / 7 |
| Refusals stayed refusals, no invented numbers | 6 / 6 | 6 / 6 | 6 / 6 |
| Empty result reported as no data | 1 / 1 | 1 / 1 | 1 / 1 |
| Any caveat or assumption voiced | 8 / 8 | 0 / 8 | 0 / 8 |

Numbers and refusals survive regardless. Caveats survive only when the parent
is instructed: "各付款方式各有幾筆交易" was relayed as transaction counts
with no mention that payment rows were counted, and the temperature answer
lost "average was assumed". A summary sentence inside the payload did not
help; the parent ignored it. Implication for the MCP tool: the relay rules
belong in the tool description and integration contract, not only in the
response body, and the response should keep assumptions as first-class
fields for parents that do follow them.

Artifacts: `.artifacts/spike-tier0/pos-nofk-0[12].json`,
`coverage-{iot,retail,pos}-0[12].json`, `iot-0[56].json`, `retail-05.json`,
`pos-03.json`, `parent-agent-0[12].json`.

### 4. Several languages against one datasource

32 English and Japanese variants of the POS questions
(`evals/cases/tier0/pos_multilingual.yaml`), same reference SQL as the Chinese
set. Comments and enum values in the database are Chinese; there is no
translation layer anywhere.

| | Result |
|---|---|
| Cases correct | 31 / 32 |
| Plan identical to the plan chosen for the Chinese question | 27 / 28 |
| Refusals correct | 4 / 4 |

The one difference: "Average base salary of engineers" filtered
`job_title IN (工程師, 資深工程師)` while the Chinese question got
`eq 工程師`; a wider and defensible reading, counted as wrong against the
reference. "Xindian Far Eastern store" resolved to the sampled value
特約新店遠東, and エンジニア to 工程師. The Japanese delete request was
declined as `unsupported` by the model because the runner's unsafe list has
no Japanese words: language packs matter for the zero-call fast paths (unsafe
words, absent concepts), not for the planner.

### 5. What a semantic overlay fixes, measured before and after

The overlay (`evals/fixtures/pos_overlay.json`) is data a reviewer would
sign: five reviewed metrics expressed as plan fragments (aggregate, defining
filters, prescribed time column), six absent concepts, and business names for
ten columns. Metrics compile through the same sqlglot compiler as tier-0; the
planner selects `{"metric": id}` as a measure and still supplies dimensions,
time, order and limit. No Wren manifest was involved.

| | Tier-0 only | With overlay |
|---|---|---|
| Cases correct (14) | 10 / 14 | 14 / 14 |
| Verified answers | 0 | 8 |
| Unverified answers | 8 | 2 (the two controls) |
| Refusals at zero model calls | 0 | 4 |

What changed per class of question:

- 退貨金額 (zh and en) went from `semantic_gap` to a verified answer whose
  assumption states the definition (`origin_transaction_no` set).
- 薪資總額 by department and by month went from wrong to right: tier-0 chose
  `paid_at` and, for the department question, added bonus; the metric
  prescribes `period_start` and excludes bonus, and the answer says so.
- 各付款方式各有幾筆交易 went from counting payment rows (numerically equal
  here by luck) to `count_distinct(transaction_no)` by definition.
- 折扣後營業額 went from an unverified sum to a verified one with the
  reviewed statement that `total_amount` is already net of discount.
- 庫存, 分期, 加班費, online sales were refused deterministically with the
  reviewer's note, zero model calls.
- The two controls stayed tier-0 `unverified_semantics`, unchanged.

So: what was wrong or refused becomes right once its meaning is defined, and
the answer's verification level says which is which. What the overlay does
not fix is the first occurrence of an undefined concept; that remains a
tier-0 answer with its interpretation exposed, or a clarify once the
vocabulary gate exists. Definitions outside the algebra (base plus bonus as
one number) still need an expression metric, not yet supported.

### 6. Headline query features of comparable products, probed

Products surveyed (vendor documentation and announcements, September 2026):
Snowflake Cortex Analyst, Databricks AI/BI Genie, ThoughtSpot Spotter, Amazon
Q in QuickSight, Google Looker Conversational Analytics, Power BI Copilot,
Wren AI. Their advertised query features were turned into 32 probes on
text2sql_test with the overlay (`evals/cases/tier0/pos_features.yaml`) plus a
suggested-questions loop (`evals/spike_suggest.py`). Additions made for the
probes: week, quarter and year time units and grains; follow-up context (the
previous question and plan offered to the planner); repair of column
references the model writes as bare strings (shape only, never meaning).

| Feature | Advertised by | Ours | Probe result |
|---|---|---|---|
| Natural-language question over a governed semantic model | all seven | tier-0 plus overlay | 78 base cases earlier; 14/14 overlay set |
| Multi-turn follow-ups (change period, add filter, breakdown, limit, new topic) | Cortex Analyst, Genie, ThoughtSpot, Looker CA API, Power BI Copilot | previous-turn context | 6/6 follow-ups, 1/1 new topic ignored context, 7/7 anchors |
| Suggested questions the system can then answer | Genie, Cortex Analyst, QuickSight | schema-driven suggestions | 10 proposed, 9 answered, 1 refused because the suggestion itself was impossible (returns per product) |
| Verified queries / trusted assets / question-SQL pairs | Cortex Analyst, Genie, Looker, Wren AI | reviewed metrics as plan fragments | 14/14, 8 verified |
| Show SQL and explain how the answer was derived | Genie, Looker, ThoughtSpot | SQL, lineage, interpretation, assumptions | every answer |
| Time intelligence: last two months, last 7 days, this and last quarter, YTD, weekly and quarterly trend, same month last year | QuickSight Q, ThoughtSpot, all | month, range, relative (day, week, month, quarter, year), periods, grains | 8/8 |
| Top-N, bottom-N, comparing named entities | all | order, limit, IN filters | 3/3 |
| Several measures in one answer | all | up to 4 on one base table | same base 1/1; cross-base refused as `metric_base_table_mismatch` |
| Numeric, enum, and null filters, including time on a parent table | all | typed filters | 3/3 |
| Ratios, share of total, growth rate | QuickSight Q, ThoughtSpot, Cortex Analyst metrics, Looker measures | not in the algebra | growth rate refused; share of total by payment method was answered as plain sums (a concept drop); share of top 3 refused |
| Forecast, "why did it change" | QuickSight Q, ThoughtSpot | not in scope, same as Genie, Looker and Cortex Analyst which decline these | refused |
| Charts and narrative summaries | Genie, Looker, Power BI, QuickSight, Wren AI | the parent agent's job; not a sub-agent concern | n/a; caveat relay measured in section 3 |
| Feedback and review loop (rate, request review, promote to trusted) | Genie, Wren AI, Cortex Analyst | ask log and overlay exist; no review UI | not tested |
| Row-level security and access control | all | read-only role only | not tested |

Totals for the probe set: 31/32 correct, 29/29 answerable cases with rows
equal to the reference, P95 6.6 s with the overlay. Two model outputs in the
first pass put a column name where the schema wants an object; the shape
repair resolved both and the second pass reports one repair per run.

Gaps that matter against the field: derived metrics (share, growth, rate),
because the closed algebra has no division or window; and the share question
shows that a missing shape is answered as a narrower question rather than
refused, so ratio words belong in the unsupported-shape language pack until
the algebra grows. Everything else the products advertise as a query feature
is present or deliberately out of the sub-agent's scope.

One quirk: the suggested questions were prefixed with "截至 2026-02-10" and
the planner expressed that as a range from 1900-01-01, which is harmless but
ugly; an "up to as_of" scope would be cleaner.
