# Knowledge for coding agents

Read in this order before changing code.

| Document | Answers |
|---|---|
| `architecture.md` | What the layers are, how a question flows, where SQL is allowed to exist. |
| `tier0-contract.md` | The `QueryPlan` algebra, error codes, verification levels, response statuses. |
| `overlay-format.md` | How reviewed knowledge is expressed as data, with the POS example. |
| `evaluation-method.md` | Case file format, runner flags, how to read an artifact, what counts as evidence. |
| `environment-and-secrets.md` | Model gateway, embeddings, PostgreSQL roles, credential hygiene. |
| `legacy-map.md` | What the v1 repository contained, what was carried over, what must not come back as-is. |
| `verification-workflow.md` | The verify profiles (carried from v1; the postgres profile references a fixture that this seed does not ship yet). |
| `glossary.md` | Terms used across code, cases and documents. |

Companion reading: `../research/tier0-generalization.md` (every experiment,
with numbers) and `../history/lessons-from-v1.md`.
