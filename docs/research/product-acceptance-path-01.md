# Fixed acceptance assets and actual MCP path

2026-09-14, baseline `9e86ca8`. Protocol:
[`product-acceptance-path.md`](../plan/product-acceptance-path.md).
Root executed the owner-approved combined slice with existing psql/Gemma and
local-commit authority. No production, prompt, gate or public response change.

## Acceptance data, not retrospective score repair

Reused the 24 authored fictional Service/IoT questions (20 answerable, four
refusal controls). Four reviewed COUNT/AVG equivalences from the previous
baseline are now explicit prospective alternatives in new private rule files,
still using the unchanged `disclosed-answer-v1` grader. Four missing-alternative
rulers initially failed at their intended assertions; two controls passed.
Original interpretations, reference SQL, context and legacy status expectations
remain intact. PostgreSQL independently checked all 24 compiled interpretation
recipes against their reference results before the six scheduled model calls.
This is one fixture per datasource, not a new multi-instance equivalence proof.

The data map also retains source-scoped fixed-plan safety controls, name/time
contracts and historical owner panels as distinct layers. This slice did not
rerun the entire 24-question model bank or historical owner panels. Blank intake
metadata reuses the existing natural-question collection workflow; no holdout
questions have been supplied or invented. See
[`product-acceptance.md`](../knowledge/product-acceptance.md).

## Actual stdio MCP measurement

Existing SDK client and actual `build_server`/`bind_datasource`/`ask` composition,
with metrics-only instrumentation: Service/IoT fictional databases, SELECT-only
role, sampling zero, isolated registry. The production registry is unchanged.
All contexts/oracles and script identities were frozen before calls and verified
afterward. No gold plans, SQL or rows went to Gemma. Tool rows stayed in client
memory; safe evidence contains hashes, counts and codes rather than raw payloads.

Model: gemma-4-31b, v15 prompt / ask v5 / MCP v1, temperature 0, thinking off,
20-second per-call timeout, one possible validation repair. Six scheduled initial
requests, at most 12 actual calls, serial; instrumented transport retries disabled.
Observed six calls, zero repair turns, zero transport errors. These retry/budget
controls belong to this probe, not a new production retry/deadline guarantee.

| Case | Actual status | Prospective judgment |
|---|---|---|
| s01 | answered | Correct; reviewed equivalent COUNT recipe |
| s11 | answered | Correct; reviewed equivalent ratio numerator COUNT recipe |
| s14 | semantic_gap | Necessary refusal action; legacy preferred status still differs |
| i01 | clarify / concept_not_mapped | Known unnecessary clarification on an answerable control |
| i02 | answered | Correct; original interpretation |
| i10 | unsupported | Necessary refusal |

Three correct answers, zero observed wrong answers, two necessary refusals, one
false refusal, zero operational failures. The generic grader labels i01
`unassessed/not_answered`; the answerable control and prior controlled replay
establish the false-refusal diagnosis. Its present plan was not regraded with the
gate disabled. Do not silently change the generic grader label or call five
accepted actions five correct answers. This purposively selected six-case smoke
provides no population error estimate. Historical full-bank scores remain as
reported in `db-aware-baseline-01.md`.

All six serialized payload fingerprints matched between server and SDK client.
The three answers retained `unverified_semantics`, assumptions, interpretation,
lineage and relay rules; oracle acceptance did not upgrade verification. Live
capabilities listed both available databases and safely identified the missing
environment variable for a deliberate unavailable registration. Unknown datasource
and invalid `as_of` produced tool errors without additional model calls.

Server ask p50 2.6025 seconds; client ask roundtrip p50 2.6910 seconds, maximum
3.2272 seconds. Client timings exclude initialization/capabilities and evidence
preparation. Six samples do not establish a latency SLA.

## Product gaps exposed by mechanism checks

Ten controlled-port/serialization checks cover answer, decline, model failure,
injected SQL timeout code, injected truncation, safe binding errors and the
following current-behavior characterizations. These are not live DB timeout,
concurrent load or cancellation experiments.

1. **Request identity is reused.** `mcp_server.py` supplies
   `run_id=f"mcp-{datasource_id}"`. Two tool calls demonstrate the same ID;
   registering two active handles under that ID replaces the first. This creates
   a lifecycle/cancellation collision risk. It is not evidence of cross-request
   result mixing or a reproduced multi-client database failure.
2. **Cancellation/deadline completeness is unproven.** The public tools are only
   capabilities/ask; the current adapter does not explicitly connect protocol
   cancellation to the active-query registry. Absence of a cancel tool alone
   would not establish this: protocol cancellation can exist independently.
   Model/DB timeouts and the probe client's timeout are not one server-owned
   whole-request deadline. Require an end-to-end lifecycle test before claiming
   cancellation stops physical work or concurrent requests are isolated.
3. **The public response is not a safe debug projection.** `result_payload`
   starts with `asdict(AskResult)`; a synthetic failed result retains arbitrary
   `raw_output`. No real secret leak was observed. This proves that wholesale
   persistence is not a guaranteed redaction boundary, not that rows reached the
   planner. Specify the intended public fields before changing compatibility.
4. **Relay instructions are not verified relay behavior.** The SDK received the
   same payload, but no parent LLM consumed it. Correct upstream rendering remains
   unmeasured. The owner has not requested reintroducing human correction cards.

## Decision and next order

Keep the prospective annotations and acceptance map. Serial research integration
passes its narrow transport checks; general concurrent/untrusted-client production
readiness is **not established**. Do not use another prompt/gate experiment to
repair these independently testable serving gaps.

Next: a bounded product-path ruler for (a) safe public/debug projection and
(b) unique per-invocation lifecycle plus deadline/cancellation isolation. Separate
compatibility and security decisions explicitly; reuse the current executor and
registry rather than add an agent framework. Measure timeout/cancel races with
controlled blocking work before any live test. In parallel collect natural user
questions using the existing intake; until those arrive, no new generalization
claim is available. Gate research resumes only with new discriminating evidence,
not another source-only applicability variant.

## Validation and scope

25 focused tests pass: six acceptance-data tests, ten controlled MCP checks,
five probe-safety tests and four post-run evidence checks. Static validation
passes. Existing 1,841-test offline evidence is reused only after checking its
artifact hash and both source digests against the unchanged runtime. It is not a
new full-suite run. Manifest: `evidence/product-acceptance-path-01.json`; private
scripts, rulers, rules, preparation and metrics:
`.artifacts/product-acceptance-path-20260914/`.

Changed evaluation data: four evidence-linked prospective alternatives only.
Changed external formats, security boundaries, identity bindings: none; the
current gaps above are recorded, not repaired. No DB writes, customer DB access,
new datasource provisioning or push. Committed files are documentation and a
safe count/hash manifest; private research code remains ignored.
