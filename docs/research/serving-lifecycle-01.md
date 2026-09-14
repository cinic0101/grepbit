# Serving lifecycle: implemented boundaries and attribution

2026-09-14, baseline `6f95a32`; root completed owner-authorized steps 1–4.
Protocol/decisions: [`serving-lifecycle.md`](../plan/serving-lifecycle.md).
This slice changes the harness, not Gemma's prompt, query algebra or gate policy.

## What changed

- **MCP v2 public projection:** explicit allowlist, excludes raw model output,
  failed repair output and offered `question_values`; retains the existing answer,
  plan, SQL/bindings, grounding, assumptions, verification, warnings and diagnostic
  counts. Adds opaque `request_id`; future internal fields do not become public.
  A second response row cap also sets `rows_truncated`. Internal AskResult/runner
  diagnostic storage is unchanged. This is not complete PII redaction.
- **Ownership:** unique invocation ID, request-owned planner (including mutable
  `last_*` traces), executor and cancellation resources; shared schema/overlay/
  compiler. Cold bind is serialized and published only after success. Duplicate
  active registry registration rejects without overwriting/revoking the owner.
- **Deadline:** `GREPBIT_REQUEST_TIMEOUT_SECONDS`, finite positive, default 30;
  queue/bind, model retry/repair, checks, DB and result preparation share it.
  Native per-call caps remain upper bounds. Checkpoints suppress later stages and
  discard late results. Owned HTTP clients close in finally; injected clients
  remain their caller's responsibility.
- **Cancellation/failures:** async MCP boundary responds to protocol cancellation,
  stopping only its current DB connection. Whole timeout is `failed/request_timeout`,
  unexpected backend exception is `failed/request_failed`; no exception text is
  exposed by this path. Relay rules distinguish operational failure from refusal.
  Cleanup is awaited for at most two additional seconds. No new cancel tool,
  identity authorization surface, persistent job store or agent framework.

## Ruler and offline evidence

Five initial tests failed at intended behavior boundaries: debug exposure,
duplicate request identity, active-handle overwrite, operational error handling,
and truthful projection truncation. The owner had explicitly delegated checkpoint
decisions; root reviewed these before implementation. The backend exception test
shows the previous direct SDK tool call raised, rather than returning the intended
typed failure; it does not establish that a real secret leaked to an end user.

23 new contract tests cover those behaviors plus independent planner/runtime
ownership, single cold bind, finite/decreasing budget, cancel-before-start,
idempotent cancellation, completion/late-cancel, deadline/late-completion,
suppressed retry/DB/repair after expiry, reduced repair timeout, native client
cleanup and overlapping-request cancellation isolation. Focused iteration reached
55 tests including existing ask controls. Final full offline verification passes
**1,864 tests, zero skipped**, and static verification passes; this is fresh
validation, not reuse of the old 1,841-test artifact.

## Real MCP/PostgreSQL fault tests (zero model calls)

A stdio SDK client calls the actual MCP composition with a controlled fake
planner and real SELECT-only PostgreSQL executor. Delay SQL is injected BELOW
policy after compilation solely to control the fault: model-authored `pg_sleep`
remains prohibited. Fictional IoT database only, no database writes, no raw rows
or credentials in evidence.

1. Observe request A physically waiting in PostgreSQL `PgSleep`, identify it by
   its unique application name; request B answers while A waits. Cancel A through
   the SDK/protocol. A's worker finishes and no matching active delay remains;
   B remains successful with a distinct request ID.
2. With a 0.7-second total budget, a controlled planner returns after one second.
   The tool returns `failed/request_timeout`; the late worker never starts DB
   execution. This is a local blocking-planner test, not a Gemma GPU cancellation
   experiment.
3. A physical five-second delay under the 0.7-second request budget fails with
   `request_timeout`; its worker exits and no active delay remains.

Development fault runs are retained under `fault-live/` and `fault-final/`.
Final evidence under `fault-verified/` additionally requires A to remain physically
active immediately before cancellation and records its worker stop reason as
`request_cancelled`, excluding a coincident timeout as the explanation. Its
before/after source digests match the final model/offline source. These are three
controlled fault runs, not independent accuracy samples; zero model calls each.

## Actual Gemma regression

Before model calls, all 24 authored acceptance contexts, prompt-message hashes,
rules and independent PostgreSQL oracle hashes exactly match the previous frozen
preparation. Rechecked 24 compiled interpretation recipes. New scripts/source
identity are frozen separately; old evidence remains unchanged.

Six serial actual stdio calls, gemma-4-31b / prompt v15 / ask v5 / MCP v2,
temperature 0, thinking off, per-model cap 20 seconds, request cap 30 seconds;
six actual model calls, zero repair turns/transport errors. Bounded protocol
allowed at most 18 actual calls and stopped after two transport errors; no reruns
to seek a better score. Only fictional questions/schema/reviewed context reach
Gemma, never gold plans, reference SQL or rows.

| Cases | Outcome |
|---|---|
| s01, s11, i02 | Three reference-matched answers, with assumptions and `unverified_semantics` retained |
| s14, i10 | Two necessary refusal actions; s14 still differs from legacy preferred exact status |
| i01 | Same unnecessary clarification, `concept_not_mapped`; not a new accepted exception |

Six complete response fingerprints match server/client; six distinct public
request IDs; removed debug fields absent. Client ask roundtrip p50 2.5123 seconds,
maximum 2.7122 seconds, excluding setup/capabilities/oracle preparation. These six
samples establish neither a latency improvement nor an SLA. Judgment parity is a
small regression signal, not a new generalization result. The generic grader's
i01 label remains `unassessed/not_answered`; the prior answerable-control diagnosis
is reported separately as false refusal.

## Is the principal cause Gemma or the harness?

There is no supported population percentage or single winner. Evidence separates
three layers:

| Failure family | Attribution supported by current evidence |
|---|---|
| Wrong count unit/metric; same-model planner and extractor jointly misread | Model semantic selection limitation under that supplied context; a legal plan is not proof of intent (`concept-obligations-v2-02.md`) |
| Correct offered plan blocked by lexical concept gate | Harness false refusal, confirmed by fixed-plan gate ablation; this i01 failure remains (`db-aware-baseline-01.md`) |
| SQL interactions or wrong reference expectations | Compiler/evaluator/contract defects; not evidence against the model (`differential-01.md`, post-hoc COUNT/AVG review) |
| Shared IDs/traces, cancellation, budget reset, raw debug projection | Harness engineering defects or missing guarantees addressed by this slice |
| Missing business definition or genuinely ambiguous scope | Information/product-contract gap; neither a different model nor an extra deterministic rule supplies the missing fact |

Prompt/context/task design can influence model errors, so a wrong model output
does not prove an immutable model capability limit. Conversely, improving request
lifecycle does not improve semantic selection. Current authored/selected panels
cannot say whether model errors or harness errors dominate natural user traffic.
Next measurement needs new natural questions and the same separated outcome
categories, not a combined pass rate padded by necessary refusals.

## Limits and next step

No claim of unrestricted production readiness. Cancellation stops waiting and
cooperatively prevents later work; Python threads are not forcibly killed and
remote gateway GPU work may continue until its own completion/timeout. DB connect
timeouts have native granularity; native limits remain fallbacks when cancellation
delivery fails. Network response delivery/upstream-agent processing are outside
the ask-handler budget. Sustained load, adversarial slow providers, PII whitelist,
multi-tenant authorization and faithful upstream relay remain separate work.

Next: bounded synthetic upstream relay testing and intake of genuinely new owner
questions. Do not reintroduce human correction cards, relax safety gates, or add
source-only applicability heuristics merely to eliminate i01. Resume semantic
interventions only with new discriminating evidence and matching leakage controls.

Evidence: `.artifacts/serving-lifecycle-20260914/`; committed safe hash/count
manifest `evidence/serving-lifecycle-01.json`. Private payloads stay in memory;
only safe codes/counts/opaque IDs/hashes are persisted by live probes. Local commit
authorized, no push. No customer database, admin role, fixture write or prompt
change in this slice.
