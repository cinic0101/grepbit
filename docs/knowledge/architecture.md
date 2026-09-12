# Architecture

## Layers

```text
application -> domain
      |
      v
    ports <- adapters
```

| Layer | Modules | May import |
|---|---|---|
| domain | `models`, `plan`, `schema_model`, `overlay`, `language_pack`, `assumptions`, `structured_query`, `grounding`, `agent_response`, `catalog` | stdlib, pydantic, domain |
| ports | `plan_compiler`, `coverage`, `grounding`, `embedding`, `query_executor`, `active_query_lifecycle` | stdlib, domain |
| application | `overlay` (schema check, absent concepts, segment activation), `shapes` (unsupported-shape and per-period gates), `literals` (which filter literals to check), `grounding` (value index: mentions, candidates, resolution), `policies` (column-policy proposer), `text` (script-aware phrase match), `active_queries` (cancellation registry) | stdlib, domain, ports, application |
| adapters | `postgres/introspect`, `postgres/value_check`, `postgres/value_index`, `postgres/executor`, `sqlglot/plan_compiler`, `sqlglot/policy`, `litellm/plan_client`, `litellm/coverage_client`, `litellm/grounding_client` (transport and settings), `litellm/embeddings_client`, `overlay_store`, `language_pack_store` | anything |

`resources/unsupported_shapes.json` is the packaged language data for shape
gates, prompt triggers and concept checks, loaded by `language_pack_store`.
Shares and growth are supported constructs, not blanket refusals. The owner
rejected using absent rate words to delete growth; that mechanism and its
unused trigger lists are removed in pack v9. The owner also approved retiring
lexical grain deletion on 2026-09-12; orchestration v3 preserves a valid grain
without testing whether the question contains a recognised period word.
Business vocabulary belongs in reviewed data,
but moving a heuristic into JSON does not prove it safe across languages.

`tests/contract/test_module_boundaries.py` enforces the table and adds one
more rule: sqlglot is imported only inside `adapters/sqlglot/`.

## Flow of one question (as implemented by `evals/spike_tier0.py`)

1. Introspect: `introspect_schema` reads tables, columns, kinds, primary and
   foreign keys from `pg_catalog` with the read-only role, and samples
   distinct values of text columns that have at most 20 of them (key columns
   excluded). Optional `infer_foreign_keys` adds joins that a name rule and
   zero-orphan containment both support, marked `inferred` with evidence.
   Columns of a PostgreSQL enum type are text columns whose sample values
   are the labels from `pg_enum` (type metadata, shown at any sampling
   limit); the compiler compares them as text so an unknown literal matches
   no row instead of raising.
2. Deterministic gates before any model call, all zero cost: unsafe words
   (language pack), overlay absent concepts (`match_absent_concept`), and
   unsupported shapes (`match_unsupported_shape`, using the loaded pack;
   the default pack no longer refuses shares, ratios or growth).
3. Plan: `ChatCompletionsPlanClient.propose` sends the rules, the JSON Schema
   of `PlanProposal`, the value-free schema payload (plus overlay metrics,
   aliases, value names, default time columns and segments, plus the previous
   turn for follow-ups) and gets one JSON object: a `QueryPlan` or a decline
   with a reason. Before the call, the value index (distinct values of the
   overlay's groundable columns, loaded once per run and capped per column)
   lists stored values that occur verbatim in the question as
   `question_values`, so a name is not cut at a segmentation boundary. In the
   provisional A5 implementation (acceptance warning: `../research/a5-service-01.md`),
   eligible entries receive column-bound IDs; `value_refs` resolves to exact
   literals before the domain plan is validated, using only this request's
   catalog. No-candidate calls keep the original filter form. Hidden
   tables and columns and withheld samples follow the overlay's policies.
   String-shaped column references are repaired only when they resolve to
   exactly one table; a base table that is merely the parent of the table
   holding every measure column is moved there (`repair_base_table`, stated
   as an assumption). Valid grains are preserved, with their interpretation
   and normal compiler assumptions; absence of a period word does not prove
   that the model added an unwanted grain. Before compilation, a
   per-period question (每天, monthly; language pack
   `period_words`) answered with a single current-period window is a
   `clarify` (`single_period_misread`), never a rewritten plan.
4. Compile: `PlanCompiler.compile` validates every identifier and kind, walks
   foreign keys away from the base table only (up to three hops, ambiguous
   paths rejected), expands reviewed metrics, applies the overlay segments the
   question did not lift (`excluded_segments`) as reviewed default filters
   and keeps a segment the question named out of the operands that do not
   select it (`named_segments`; the ids that shaped the SQL come back as
   `CompiledPlan.applied_segments`),
   resolves time windows in the business time zone from `as_of` (rejecting a
   relative window that reaches the future), takes a share over all groups
   even when the question filters on the grouped column (the filter selects
   rows after the share), widens a growth window by one unit when it covers
   a single bucket and refuses growth on a to-date window. Growth is NULL
   across absent calendar buckets instead of jumping to the last observed
   period; no synthetic rows are inserted. It refuses a
   `HAVING count = 0` over the base rows as an anti-join it cannot express,
   adds a correlated `NOT EXISTS` for a `without` (entities with no
   activity, the child's filters, window and segments inside), ranks rows
   with `ROW_NUMBER()` for a `latest` (the most recent row per group) and
   resolves a `latest` time scope against the data (the unit of the maximum
   time value after the filters), places `having` conditions on aggregate
   expressions for plain aggregates (or on output after share/growth,
   preserving their comparison population), builds the SQL as a sqlglot AST with bound
   placeholders, and emits lineage, assumptions, interpretation and the
   verification level.
5. Gate: `PostgresSqlPolicy(tables=..., functions=...)` re-parses the SQL and
   allows one SELECT over the introspected tables with reviewed functions.
6. Check literals: every `eq` or `in` text literal the plan filters on is
   checked against its column (`text_literal_checks` chooses, `missing_literals`
   runs one bounded `SELECT EXISTS` per literal with the literal bound). A
   literal that matches no row is resolved against the value index when its
   column is groundable (`resolve_plan_literals`: character-bigram similarity
   with an edit-distance tie break): one clear candidate is substituted into
   the plan, which is recompiled, and stated as a candidate assumption;
   several candidates become a `clarify` that lists them; none, or a column
   that is not groundable, leaves the `clarify` naming the literal, instead of
   an empty aggregate that reads like a number.
7. Execute: `PsycopgQueryExecutor` runs inside `BEGIN READ ONLY` with
   statement and idle timeouts, a named cursor, bounded rows, and the
   cancellation registry.
8. Answer: status, verification, interpretation, assumptions, lineage, SQL,
   rows, a warning when the result is empty; or a typed refusal with the
   reason and, when available, a clarification.

## Invariants

- The model emits identifiers from the offered schema and typed literals from
  the question. Never SQL, never rows, never computed dates.
- Every literal is bound as a parameter by the server.
- Joins follow declared or inferred foreign keys away from the base table;
  fan-out is a compile error, never a silent row multiplication.
- Assumptions state every default the server chose; an inferred join and an
  unreviewed column meaning are `candidate` assumptions; a reviewed metric is
  a `reviewed` assumption.
- A concept the schema cannot express is a refusal, not a broader answer.
  The planner rule enforces it; the interpretation line exposes it; the
  overlay's absent concepts make it deterministic once seen.

## The callable surface

`application/ask.py` is the per-question pipeline as one function over
ports (`ports/ask.py`): gates, planner with one transport retry, shape and
base repairs, compile and policy, literal check with grounding, segment
exclusion, execution, and an `AskResult` carrying the served contract.
`adapters/mcp_server.py` composes the adapters for each datasource listed in
`datasources.json` (the DSN comes only from the environment variable the
registry names) and exposes two MCP tools over stdio: `capabilities`
(datasources, visible tables, reviewed metrics, segments, absent concepts,
supported shapes, relay rules; no values; a datasource whose environment
variable is missing or whose bind fails is listed under `unavailable` by
reason, never by connection detail) and `ask` (status or typed refusal,
SQL with bound parameters, lineage, assumptions, verification, up to 200
rows, warnings, hints and resolutions). Run it with
`.venv/bin/python -m grepbit.adapters.mcp_server` or the `grepbit-mcp`
script after `uv sync`. The runner `evals/spike_tier0.py` calls the same
`ask()` per case and maps the `AskResult` onto its report, so measurements
and the served path cannot drift (`../research/runner-on-ask-01.md`).

## What is not here yet

MCP and datasource registration exist as described above. Open work includes
live acceptance of candidate references (A5), measured large-schema needs
(A4), PII-safe sampling and review tooling. See the current
status in `../plan/root-cause-program.md`; earlier planning prose is history.
