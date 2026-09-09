# Legacy map: the v1 repository and what came over

Source: `grepbit` at commit `c382dda` (branch `spike/tier0`). Line counts are
from that commit.

| v1 area | Lines | Status in this seed |
|---|---|---|
| `domain/models.py` (CompiledQuery, QueryParameter, ExecutionResult and the G-series run and evidence contracts) | 931 | carried whole; only the query and parameter types are used. Trim when the served contract is rebuilt. |
| `domain/plan.py`, `schema_model.py`, `overlay.py`, `assumptions.py` | ~460 | core, carried |
| `domain/structured_query.py`, `catalog.py`, `grounding.py`, `agent_response.py` | ~1,100 | carried as contracts: time scopes and resolution are used by the compiler; StructuredQuery, SemanticCatalog, Clarification, AgentResponse are the v0.2 response contracts to port onto tier-0 |
| `adapters/sqlglot/plan_compiler.py`, `policy.py`; `adapters/postgres/introspect.py`, `executor.py`; `adapters/litellm/plan_client.py`, `coverage_client.py`, `grounding_client.py`, `embeddings_client.py`; `adapters/overlay_store.py` | ~1,900 | core, carried |
| `application/trusted_execution.py` (1,785), `fixed_query.py` (900), `g3.py`, `g4.py`, `g5.py` (~3,100), `cross_task_relation.py`, `request_*.py`, `api_service.py` (~2,600) | ~8,400 | not carried: G-series orchestration, budgets, replanning, relation flow. `ActiveQueryRegistry` was extracted to `application/active_queries.py` (50 lines). |
| `application/query_renderer.py`, `grounding.py`, `structured_ask.py`, `validators.py` | ~1,900 | not carried: the catalog-first path (StructuredQuery to Wren SQL, lexical and embedding retrieval, one-call classifier, templates). `phrase_in` extracted to `application/text.py`. Re-implement grounding on top of the overlay when the vocabulary gate is built. |
| `adapters/wren/compiler.py`, `semantic/retail_v1/*.json` (Wren MDL, catalog, templates) | ~400 plus data | not carried: the overlay compiles through sqlglot; Wren's engine repository is archived. |
| `adapters/sqlite/ledger.py` (975), `api_store.py` (601), `ask_store.py` (181) | ~1,750 | not carried: evidence ledger and ask log schemas were built for the G-series contract. Rebuild a small ask log when the API returns. |
| `api/*`, `bootstrap.py`, `cli.py` | ~1,600 | not carried: FastAPI loopback API, `ask` and `capabilities` CLI, composition root. The API shape (`/ask`, `/capabilities`, `/runs/{id}/evidence`) is documented in `../history/spec-v0.2-catalog-first.md` Section 8 and should be rebuilt on tier-0. |
| tests `g2` to `g6b`, `s2` to `s4`, `spike/g1` | | not carried except the SQL policy contract and a rewritten module-boundary ruler. `t0` carried whole. |
| `evals/grounding_eval.py`, `live_ask.py`, `evals/cases/g2`, `g3`, `grounding` | | not carried: they test the catalog-first path. |
| `Dockerfile`, `compose.yaml`, `compose.g1.yaml` | | not carried: they served the v1 API and a fixture with a v1 bootstrap script. Re-add with the new API. |

Rule for bringing anything back: it returns as a re-implementation on the
tier-0 contracts with a measurement, not as a copy.
