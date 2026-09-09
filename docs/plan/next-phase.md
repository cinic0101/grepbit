# Next phase (proposed 2026-09-09): four to six weeks, three stages

Each stage has an exit that is a measurement or a working call, not a
document.

## Status (2026-09-09, owner's ordering)

The owner chose to run the real questions before building the callable
surface, so stage 1 is reordered: only what stands between the code and a
blind run on the real database comes first.

| Item | State |
|---|---|
| PII sampling approach | decision deferred by the owner to the column-settings work; the first real run uses `--enum-distinct-limit 0` (no row value reaches the model). Enum labels come from the catalog and are shown regardless (`../research/pos-real-enum.md`). |
| Judged runs for questions without reference SQL | done: `--review-sheet`, `--verdicts`, `evals/tally_verdicts.py`, `--redact-rows` (`../knowledge/evaluation-method.md`) |
| Real POS test database | granted to `grepbit_ro`; 9 tables; compatibility smoke 7/7 |
| Unsupported-shape language pack, literal existence check | built as deterministic gates; measured on the 160 author cases in `../research/deterministic-gates.md` |
| Blind run of the owner's 30 to 50 real questions | waiting on the question file and the `as_of` date |
| Ask service, datasource registration, MCP tool, vocabulary gate | after the blind run, in the order its numbers dictate |
| Real-database overlay | v2 in `overlays/pos_real.json`: return metrics and paid-amount metric signed by the owner (verified), absent concepts, table and column aliases, payment-method value names, default time columns, a returns segment excluded by default (confirmed by the owner). Format additions measured on the 160 author cases and the 50 questions with prompt v6 |
| Period-over-period growth | deferred by the owner to the phase after the 50 questions are settled (stage 3 derived metrics) |

### Decisions recorded from the first real-question run (owner, 2026-09-09)

- Ambiguous questions: keep answering the more plausible reading with the
  assumption exposed; refuse only when two readings are equally plausible.
  Recurring misreadings are fixed in the overlay (q03 已付款 became the
  `paid_amount` metric), not in the prompt.
- Rules about rows (which rows are returns, that they are excluded unless
  asked) are overlay data; the mechanism that applies them is code and
  datasource-agnostic.
- Response contract: keep a `parameters` list (name, type, value) next to the
  SQL so a reviewer or the calling agent can reproduce the query; rows are
  bounded at 200 with a `truncated` flag; default ordering stays by the
  grouping columns ascending unless the question or the overlay says otherwise.
- Sign-off of overlay definitions is delegated to the build side once the
  owner has confirmed the business rule in conversation.

### Semantic-layer gaps to take up in the next phase (from the Cube and Wren comparison)

Not expressible in the overlay today, each seen at least once in the 50
questions or in the owner's discussion; see `../knowledge/overlay-format.md`
for what exists.

| Gap | Seen in | Closest prior art |
|---|---|---|
| Ratio and share measures (客單價, 退貨率, 佔比), a ratio of two aggregates or of a group to the total | q10, q13, q17, q21, q24, q34, q41, q49, q50 | Cube calculated measures (`type: number`), Wren calculated fields |
| Derived dimensions: a CASE label as a group-by (各訂單狀態 as 銷售/退貨) | q05 | Cube `case` dimensions, Wren calculated fields |
| Period-over-period growth (LAG windows) | owner's deferral | Cube rolling windows and comparisons |
| Aggregate filters (HAVING): 交易筆數超過 100 的銷售員 | holdout 2: 4 of 30 answered without the threshold, silent wrong numbers; `having` added to the algebra the same day (prompt v8), measured in `../research/holdout2-01.md` | Cube and Looker measure filters, Malloy `having` |
| Declared joins for schemas without foreign keys where inference fails | not yet hit | Cube joins, Wren relationships |
| Hidden tables or columns per datasource (transfer tables for sales questions) | q06 | Cube views and `public: false` |
| Hierarchies and drill paths (category to product) | not needed yet | Cube hierarchies |
| Latest-record lookups, weekday or hour breakdowns, anti-joins (沒有交易的門市), rolling averages | not in the 50; put two or three of each in the next batch so they become measured refusals | |

Deliberately not adopted: free-text instructions or question-to-SQL pairs
shown to the model (Wren AI). The model never writes SQL, and prompt knowledge
carried as data is prompt tuning by another name.

Also for the next phase, raised by the owner on 2026-09-09: a way to let an
LLM propose a datasource onboarding (table and column aliases, candidate
metrics, absent concepts, column policies, default time columns) from the
introspected schema and the ask log, as a draft a reviewer approves; the
deterministic policy proposer is the first piece, and the rule stands that a
model proposes and never decides. And: how an overlay is
organized so that a user can adjust it without an engineer (file layout per
datasource, one document versus several by kind, revision and sign-off
workflow, what the ask log proposes and what a reviewer edits by hand). Input
to that discussion: `overlays/pos_real.json` as it stands after this batch.

## Stage 1 (about two weeks): make it callable

- Ask service on tier-0 plus overlay: template of the v0.2 response contract
  (`docs/history/spec-v0.2-catalog-first.md` Section 8) filled from
  `CompiledPlan`: status, verification, interpretation, assumptions, lineage,
  SQL, rows, clarification with a pending plan.
- Datasource registration command: introspect, infer joins, store the schema
  digest, refresh on demand, and sampling that excludes PII (opt-in column
  list or name and value heuristics; default off for free-text columns).
  Input for that choice: `../research/sampling-ablation.md` (without any
  sampling 54/58 on the base sets, 3 refusals and 1 wrong answer on a name
  column).
- MCP tool `ask` and `capabilities` per datasource; the tool description
  carries the relay rules (only returned numbers, restate assumptions, say
  what was refused and why).
- Unsupported-shape language pack (ratio, share, growth words) as a
  deterministic clarify until the algebra supports them.
- Vocabulary gate: the planner emits its concept mapping in the same call;
  the server turns an unmapped concept into `clarify` with a pending plan;
  unmapped concepts are logged for review.

Exit: an external agent asks questions through MCP end to end against one
registered datasource; the offline suite and a live regression on the
existing case sets are green.

## Stage 2 (one to two weeks): measure on real questions

- The owner's 30 to 50 real questions on the real database, split into dev
  and holdout; the build side does not read the holdout and does not change
  prompts between runs.
- Schema-size test: a 50-plus table schema, measure accuracy and latency,
  decide whether schema retrieval is needed now.

Exit: holdout correctness, count of wrong numbers without an exposed
assumption (target zero), clarify rate, P95. These four numbers decide
stage 3.

## Stage 3 (about two weeks): overlay lifecycle and algebra

- `overlay draft`: from the ask log and the schema, the model drafts aliases,
  absent concepts and candidate metrics; a reviewer approves; revisions are
  recorded.
- Derived metrics in the algebra: share of total and period-over-period
  growth as explicit shapes compiled with window functions, still one
  statement, still bound parameters.
- Port the retail_v1 catalog to overlay metrics as the worked example of
  retiring the Wren path.

Exit: a reviewer can turn a logged gap into a verified answer without an
engineer; the derived-metric probes that failed in `pos_features.yaml` pass.

## Deferred until there is a user

Charts and narrative (parent agent), row-level security, multi-engine
support (sqlglot dialects make transpile feasible; introspection and executor
are per engine), review UI, evidence ledger beyond the ask log.
