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
| domain | `models`, `plan`, `schema_model`, `overlay`, `assumptions`, `structured_query`, `grounding`, `agent_response`, `catalog` | stdlib, pydantic, domain |
| ports | `plan_compiler`, `coverage`, `grounding`, `embedding`, `query_executor`, `active_query_lifecycle` | stdlib, domain |
| application | `overlay` (schema check, absent concepts), `text` (script-aware phrase match), `active_queries` (cancellation registry) | stdlib, domain, ports, application |
| adapters | `postgres/introspect`, `postgres/executor`, `sqlglot/plan_compiler`, `sqlglot/policy`, `litellm/plan_client`, `litellm/coverage_client`, `litellm/grounding_client` (transport and settings), `litellm/embeddings_client`, `overlay_store` | anything |

`tests/contract/test_module_boundaries.py` enforces the table and adds one
more rule: sqlglot is imported only inside `adapters/sqlglot/`.

## Flow of one question (as implemented by `evals/spike_tier0.py`)

1. Introspect: `introspect_schema` reads tables, columns, kinds, primary and
   foreign keys from `pg_catalog` with the read-only role, and samples
   distinct values of text columns that have at most 20 of them (key columns
   excluded). Optional `infer_foreign_keys` adds joins that a name rule and
   zero-orphan containment both support, marked `inferred` with evidence.
2. Deterministic gates before any model call: unsafe words (language pack),
   overlay absent concepts (`match_absent_concept`), both zero cost.
3. Plan: `ChatCompletionsPlanClient.propose` sends the rules, the JSON Schema
   of `PlanProposal`, the value-free schema payload (plus overlay metrics and
   aliases, plus the previous turn for follow-ups) and gets one JSON object:
   a `QueryPlan` or a decline with a reason. String-shaped column references
   are repaired only when they resolve to exactly one table.
4. Compile: `PlanCompiler.compile` validates every identifier and kind, walks
   foreign keys away from the base table only (up to three hops, ambiguous
   paths rejected), expands reviewed metrics, resolves time windows in the
   business time zone from `as_of`, builds the SQL as a sqlglot AST with
   bound placeholders, and emits lineage, assumptions, interpretation and the
   verification level.
5. Gate: `PostgresSqlPolicy(tables=..., functions=...)` re-parses the SQL and
   allows one SELECT over the introspected tables with reviewed functions.
6. Execute: `PsycopgQueryExecutor` runs inside `BEGIN READ ONLY` with
   statement and idle timeouts, a named cursor, bounded rows, and the
   cancellation registry.
7. Answer: status, verification, interpretation, assumptions, lineage, SQL,
   rows; or a typed refusal with the reason and, when available, a
   clarification.

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

## What is not here yet

Served API and CLI, datasource registration, the vocabulary gate, MCP tool,
derived metrics, schema retrieval for large schemas, PII-safe sampling,
review tooling. See `../plan/next-phase.md`.
