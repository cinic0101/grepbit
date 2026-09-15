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
[`details-schema-adoption-01.md`](../research/details-schema-adoption-01.md):
explicit Details now displays only its measured rows/refusal schema. Versioned
owner ordering adjudication resolves the prior oracle mismatch; six actual
Web/MCP calls pass bounded acceptance with the known Return false refusal intact.
Default/fallback and OrderSpec defaults stay unchanged. Conversion is next, not
yet implemented; per-set construct thresholds and lease omission controls remain.

[`status-and-web-closeout-01.md`](../research/status-and-web-closeout-01.md):
synthetic IoT status value aliases accepted in the local Web profile after paired
HTTP/MCP checks (two false refusals recovered); mode guidance preserves original
results, isolated time witnesses distinguish boundary/month mistakes. Return
gate and refusal-type selection remain open; no parser or router introduced.

[`identifier-row-wire-closeout-01.md`](../research/identifier-row-wire-closeout-01.md):
shared exact-identifier serialization fixes a PostgreSQL case-folding JOIN error;
saved-response replay supports narrow traced duplicate-row-column normalization,
without changing the prompt, gate, answer/refusal counts or construct freeze.

[`parent-row-projection-01.md`](../research/parent-row-projection-01.md): explicit
Details can attach one eligible direct parent's attributes; segment population,
visibility, catalog/inheritance and flat output boundaries validated. Existing
Default contexts unchanged on measured sources; extra repair cost remains named.

[`explicit-rows-entry-01.md`](../research/explicit-rows-entry-01.md): explicit
caller-selected Details accepted through shared ask/MCP/Web; separate opt-in
synthetic profile, unchanged default planning. Automatic routing remains open;
one known concept-gate false refusal persists. Earlier records below are history.

[`base-row-pilot-01.md`](../research/base-row-pilot-01.md): shared row compiler
available only by opt-in; automatic planner selection is not ready for Web
promotion. Conversion and independent aggregates remain research-only.

Follow-up: [`query-kind-study-01.md`](../research/query-kind-study-01.md) compares
one-call planning policy with an independent router. The one-call candidate
matches the router's outcomes at lower cost. The
[`wider regression`](../research/joint-regression-and-row-order-01.md) reproduces
one new supported-without false refusal, so no default promotion. The independent
opt-in row-order repair passes typed PostgreSQL checks and offline validation.

[`Without composition follow-up`](../research/without-capability-study-01.md):
generic scope-then-aggregation guidance improves the small panel, but its SUM
advantage does not recur over the unchanged baseline on repeat. A new boundary
witness catches timestamp-to-date precision loss during model repair. No runtime
promotion; prospective date controls retain old scores separately.

[`Temporal repair follow-up`](../research/temporal-repair-study-01.md): generic
timestamp-filter guidance passes the small 13-case panel and three-case repeat;
guarded raw-output replay stops five wrong repairs, not first-pass mistakes.
Separate endpoint witnesses correct one scalar false pass without overwriting
history. Research only; wider combination regression remains next.

[`Four-arm combination regression`](../research/planner-combination-study-01.md):
55 cases plus separate recurrence checks, 277 calls. Time-only and combined tie
on total correct answers but fail different cases; composition loses a required
lease refusal twice. No promotion. Same-plan PostgreSQL replay establishes naive
timestamp dependence on session timezone; typed-time boundary rulers are next.

[`Typed-time correction`](../research/typed-time-boundary-01.md): owner-approved
source-type/default-zone/DST policy implemented without prompt changes. Session
matrix and stored-plan replay pass within recorded scope; 2,169 offline tests,
1,184 differential agreements. Remaining repair truncation is not fixed by typed
binding; default promotion and missing-definition studies remain separate.

[`Production time closeout`](../research/production-time-closeout-01.md): binding
accepted through actual Web/MCP replay; narrow source-aware repair protection
integrated into the shared planner. Thirty live calls, exact-reply runtime
replay, 2,191 offline passes. Four known wrong repairs become failures, not new
correct answers. [Integration board](../plan/production-integration-board.md)
tracks independent deliveries and per-capability semantic/consumer acceptance.
