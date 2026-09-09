# Environment and secrets

## Model gateway

OpenAI-compatible Chat Completions endpoint (LiteLLM in front of vLLM during
the spike). Settings (`adapters/litellm/grounding_client.py`):

| Variable | Meaning |
|---|---|
| `GREPBIT_MODEL_BASE_URL` | e.g. `http://gateway/v1` |
| `GREPBIT_MODEL_NAME` | `gemma-4-31b` was the reference model for every result in `docs/research/` |
| `GREPBIT_MODEL_TIMEOUT_SECONDS`, `GREPBIT_MODEL_TEMPERATURE` (0), `GREPBIT_MODEL_MAX_TOKENS` (plan calls raise this to at least 768) | |
| `GREPBIT_MODEL_CREDENTIAL_ENV` | name of the variable holding the API key, default `LITELLM_API_KEY` |

Calls use `response_format: json_object`, temperature 0, one call per
question (two with the coverage audit, which is an experiment flag).

Embeddings (not used by tier-0 yet; kept for the vocabulary gate):
`GREPBIT_EMBEDDING_*` with `embeddinggemma-300m` (768-d, prompt prefixes
`task: search result | query:` and `title: none | text:`) or
`harrier-oss-v1-0.6b` (1024-d, instruct prefix) measured in v1.

## Credentials

- `LITELLM_API_KEY` lives in an ignored `.env`. Load it opaquely:
  `set -a; . ./.env; set +a`. Never print, grep, copy, or commit it.
- Database DSNs are passed as the name of an environment variable
  (`--dsn-env`), never written into files under version control. Admin DSNs
  are used only in the shell for setup (create database, grant) and never
  reach application code.
- The runtime role has `CONNECT`, `USAGE` on the schema, and `SELECT` on
  tables. Introspection reads `pg_catalog` (visible to such a role;
  `information_schema` constraint views are not).

## Databases used in the spike (owner's Docker PostgreSQL, localhost:5432)

`grepbit_spike_retail` and `grepbit_spike_iot` (from `evals/fixtures/`),
`text2sql_test` (owner's POS plus HR fixture), `grepbit_spike_pos_nofk` (a
clone of the latter with foreign keys dropped). Read by role `grepbit_ro`.

## Known hazard

Introspection samples low-cardinality text values and shows them to the
model. On a real database that can include names. PII exclusion or an
opt-in list is the first item in the next phase; until then, fixtures and
consented databases only.
