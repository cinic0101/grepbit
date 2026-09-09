# Next phase (proposed 2026-09-09): four to six weeks, three stages

Each stage has an exit that is a measurement or a working call, not a
document.

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
