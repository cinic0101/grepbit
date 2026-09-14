# Local streaming web: E2E entry, not another answering agent

2026-09-14, baseline `61c38e9`. Owner requested a simple streaming web interface
instead of connecting an external upstream application. This replaces that
integration prerequisite. Root owns this slice. Existing Gemma/readonly DB and
local-commit authority applies; no push or deployment.

**Checkpoint history: specification and rulers approved by the owner.**
Implemented 2026-09-14; see `../research/local-web-01.md`. Browser-control setup
still blocks real-browser/visual validation. Each dev request owns its own MCP
child/session, avoiding a shared-session reconnect supervisor. The following
contract and ruler evidence preserve the approved pre-implementation design.
The newly supplied AGENTS
instructions require a follow-up checkpoint for a new security/public boundary.
An HTTP listener is new; establish the contract here before implementation.
The associated tests validate the static specification and existing MCP result
semantics. They are not failing HTTP behavior tests, because no web server or
renderer exists yet; import errors would not be meaningful ruler evidence.

## Small implementation after approval

One local Python dev launcher (`tools/dev_web.py`) and a static HTML/CSS/JS page,
using installed MCP SDK/HTTP components, no SPA framework, database, new agent
framework, persistent conversation store, user accounts, or external assets.
Declare any directly used dev dependency rather than relying silently on a
transitive install. No package/provider change without need.

Browser -> local HTTP/SSE bridge -> actual stdio MCP `ask` -> existing
planner/grounding/compiler/readonly executor -> structured MCP result -> browser.
The bridge does not reimplement ask(), query generation or business semantics.
This measures actual served transport, not a canned fixture response presented
as a DB answer. Controlled fake adapters are separate fault tests only.

UI: datasource dropdown, explicit reporting date (`as_of`), question box,
submit/stop, progress, result table, visible interpretation/assumptions/verification/
warnings, and expandable plan/SQL diagnostics. Refusal reason and clarification
remain visible; operational failure has a distinct state. No correction card,
click-to-rewrite intent, second model narration or hidden semantic certification.

## Streaming means truthful progress, not invented tokens

POST `/query` returns `text/event-stream`: `progress` (accepted/waiting), exactly
one terminal `result` or `error`, then closes. Heartbeats mean waiting only;
do not fabricate planner/SQL stage events without real instrumentation. No row
or numeric answer is shown until the tool result is complete. JSON event data
handles embedded newlines as escaped string contents. Use fetch streaming for
POST; do not place questions or credentials in query strings.

The original structured result is retained in page memory alongside rendering;
all required disclosure is visible without relying on model paraphrase. A
collapsed raw payload alone does not satisfy disclosure. Display NULL distinctly
from zero, count unit from output column/interpretation, two-of-five truncation
as metadata rather than a new metric, and reviewed definitions without claiming
intent certification. If verification is absent for a refusal, do not invent it.

DOM uses textContent/text nodes, not innerHTML/Markdown execution for any
question, row, column, error or evidence string. No localStorage, analytics,
history files, service worker, autosave or result logging. Page refresh clears
in-memory results. This is not a blanket browser/OS forensic-erasure claim.

## Local security and lifecycle boundary

- Bind **127.0.0.1 only**, default port 8765, configurable numeric port. No
  `--host 0.0.0.0`, LAN/public deployment or tunneling. Loopback is not user auth.
- Exact Host and same-origin Origin checks for the bound loopback origin;
  `/query` additionally requires JSON and a custom local-client header. No CORS
  allowance; missing/foreign/null Origin on POST is rejected. Reject invalid
  requests before contacting MCP. Static GET access does not grant query access.
- Serve only named routes/assets. Security headers: no-store, nosniff, frame
  denial and restrictive CSP; no CDN, remote scripts or arbitrary filesystem
  paths. Error/log output contains safe codes, never raw exceptions/payloads.
- Require an **explicit registry**; never silently use repo `datasources.json`,
  which includes real POS. Initial launcher/demo only enables explicitly selected
  synthetic fixture sources with sampling zero and opaque DSN names. This is
  operator-scoped configuration, not automatic PII classification of arbitrary DBs.
  No admin credentials, browser-entered DSNs, connection editor or browser key.
- Registry/path/DSN env names are server inputs, not accepted in a query request.
  Browser submits only known datasource ID, question and ISO `as_of`. Reject
  unknown keys, malformed dates, unregistered IDs, body >16 KiB, empty or >4,000
  character questions. No full environment or registry dump to the browser.
- One active web query globally for this development endpoint. A second request
  gets 429 without another model call. No queue, retry storm or prior-answer reuse.
- Stop/disconnect cancels that MCP request; retain existing server deadline and
  DB cancellation semantics. Do not close the shared MCP session to cancel one
  request. Cleanup releases admission only when the request task exits.
- Bound the bridge wait (35 seconds default with the standard 30-second MCP
  budget), including failure recovery; late results never replace a stopped or
  subsequent request. Page state is per invocation; retain returned request_id.
  Startup/child death yields safe operational error, not a semantic refusal.
- No claim of forcibly stopping remote GPU work, multi-tenant authorization,
  unrestricted PII support, high-load capacity or production readiness.

## Implementation and validation order after approval

1. Implement the small bridge and page to this contract. Add actual HTTP tests
   for Host/Origin/header/body/ID validation and no downstream call on rejection;
   SSE parse/terminal framing, error sanitization and public debug exclusion.
2. Controlled lifecycle tests: progress arrives before completion, disconnect
   propagates cancellation, overlap is rejected, deadline suppresses late output,
   child failure releases the slot and a later request can complete.
3. Browser interaction tests with synthetic hostile strings, NULL/zero, refusal,
   truncation and verification: visible text, no script execution, no hidden
   required caveats. Inspect rendering and stop/retry behavior in the browser.
4. Run the existing six authored Service/IoT MCP cases through HTTP/browser,
   with their already-reviewed judgments and reporting dates; at most 18 Gemma
   calls including existing bounded retries/repairs, serial, existing private
   gateway only. Planner receives schema/question/approved metadata, not result
   rows. Readonly fixture DB, sampling zero, no customer data/new provider.
   Record model calls, statuses, source identity and transport/disclosure fidelity
   separately. The known gate false refusal remains a known failure, not a UI fix.
5. Focused gates during iteration and one fresh broad static/offline gate for
   implementation closeout. Local smoke is not a user generalization measurement.
   Hand off the localhost URL/start command and exact remaining limitations.

## Relation to mechanism composition

This combines deterministic evidence preservation with an actual E2E path; it
removes the extra prose-relay failure stage from the first test interface. It
does not solve wrong metric selection or establish that a later upstream agent
will relay faithfully. Keep the rejected gate variants rejected. Planner-level
combinations still require same-panel baseline/X/Y/X+Y ablations with paired
rescues and harms; successful attachment copying is not evidence of semantic
synergy. The independent relay-copy probe is documented separately, not promoted.

## Checkpoint evidence

Eleven static contract/current-MCP-payload tests pass. Fresh static and the broad
1,875-test offline gate pass (zero skipped); neither executes a web UI. The
independent private copy probe has 23 passing checks outside that broad suite.
Safe counts/hashes: `../../evidence/local-web-ruler-01.json`. No red HTTP behavior
test is claimed. The next action needs checkpoint follow-up, not credentials or
an external upstream application.
