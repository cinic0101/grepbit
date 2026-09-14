# Knowledge for coding agents

Read in this order before changing code.

| Document | Answers |
|---|---|
| `architecture.md` | What the layers are, how a question flows, where SQL is allowed to exist. |
| `tier0-contract.md` | The `QueryPlan` algebra, error codes, verification levels, response statuses. |
| `overlay-format.md` | How reviewed knowledge is expressed as data, with the POS example. |
| `evaluation-method.md` | Case file format, runner flags, how to read an artifact, what counts as evidence. |
| `product-acceptance.md` | Fixed acceptance assets, actual MCP evidence and remaining product boundaries. |
| `local-web.md` | Loopback streaming E2E launcher, fixture scope, usage and validation limitations. |
| `environment-and-secrets.md` | Model gateway, embeddings, PostgreSQL roles, credential hygiene. |
| `legacy-map.md` | What the v1 repository contained, what was carried over, what must not come back as-is. |
| `verification-workflow.md` | The verify profiles (carried from v1; the postgres profile references a fixture that this seed does not ship yet). |
| `glossary.md` | Terms used across code, cases and documents. |

Companion reading: `../research/tier0-generalization.md` (every experiment,
with numbers) and `../history/lessons-from-v1.md`.

Current query-extension integration result:
[`base-row-pilot-01.md`](../research/base-row-pilot-01.md): shared row compiler
available only by opt-in; automatic planner selection is not ready for Web
promotion. Conversion and independent aggregates remain research-only.
