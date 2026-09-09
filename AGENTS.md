# Coding-Agent Guide

## Mission

One question, one governed aggregate query, an honest answer. The model
chooses identifiers and typed literals inside a closed algebra; the server owns
the schema, the SQL, the execution, and the evidence. Every answer carries a
verification level and its assumptions, or a typed refusal (`clarify`,
`semantic_gap`, `unsupported`, `unsafe`). The north star is a sub-agent other
agents call.

Read before editing: `docs/knowledge/README.md` (map), then
`docs/knowledge/architecture.md` and `docs/knowledge/tier0-contract.md`.
Decisions and their evidence live in `docs/research/`. History that must not
be repeated lives in `docs/history/lessons-from-v1.md`.

## Rules that the previous attempt taught

1. Experiment before feature. A capability enters the code base only after a
   live measurement says it helps; the measurement goes in `docs/research/`
   or the evaluation log with its artifact under `evidence/`.
2. No hardcoded datasource knowledge in code. Business meaning lives in the
   overlay (`docs/knowledge/overlay-format.md`), drafted by tooling and signed
   by a reviewer. Cross-datasource language packs are data too.
3. The model never writes SQL and never sees rows. If a change needs either,
   stop and record the product decision first.
4. Prompt changes are versioned (`PLAN_PROMPT_REVISION`) and re-measured on
   every case set they could affect; a prompt tuned to one failing case is
   reported as such.
5. Author-written cases are smoke signals. Only a holdout of real user
   questions, unseen before a run, counts as a generalization measurement.
6. Refusing is cheaper than a wrong number. Never trade a deterministic check
   for a model judgment to make a case pass.

## Architecture boundaries

```text
application -> domain
      |
      v
    ports <- adapters
```

- `domain/`: pydantic contracts and pure functions; imports stdlib, pydantic,
  domain only.
- `ports/`: protocols; imports stdlib and domain only.
- `application/`: orchestration; never imports adapters or providers.
- `adapters/`: sqlglot, psycopg, OpenAI-compatible clients. SQL is built only
  in `adapters/sqlglot/`.

`tests/contract/test_module_boundaries.py` enforces this; keep it green.

## Validation

```sh
.venv/bin/python tools/verify.py static  --output .artifacts/<run>/static
.venv/bin/python tools/verify.py offline --output .artifacts/<run>/offline
.venv/bin/python tools/verify.py focused --tests <paths> --output .artifacts/<run>/focused
```

Live runs use `evals/spike_tier0.py` against a read-only role. Report the
exact case file, the prompt revision, and the artifact path. Numbers without
an artifact are not results.

## Secrets and external state

- `.env` may hold `LITELLM_API_KEY`; source it opaquely, never print or commit
  it. Database DSNs are passed through environment variables named on the
  command line, never written into files under version control.
- The runtime role is `SELECT` only. Setup credentials are never given to
  application code or model calls.
- Introspection samples low-cardinality text values for the model. Until the
  PII exclusion exists (see `docs/plan/next-phase.md`), run only against
  fixture or consented databases.

## Delivery style

Conventional Commits, imperative subject under 72 characters, body for why.
Commit when authorized; never push unless separately authorized. Keep diffs
narrow; rewrite tests that pin a superseded contract in the same commit and
say so. Each slice ends with scope, changed files, validation counts, known
gaps, and Git state.
