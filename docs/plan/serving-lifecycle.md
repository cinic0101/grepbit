# Serving projection and request lifecycle

2026-09-14; root owner; baseline `6f95a32`. User explicitly requested steps
1–4 (public/debug projection, per-request identity, deadline/cancellation,
integration verification), with prior autonomous checkpoint decisions, psql/Gemma
and local commits authorized. No push. Existing Claude PID 49876 is the same
session the owner explicitly allowed us to ignore; no regression process found.
No other agent is delegated this coupled surface.

## Ruler and compatibility decisions

Establish intended failing behavior tests before implementation, then root reviews
and proceeds under the owner's explicit checkpoint authority. Existing evidence:
`product-acceptance-path-01.md` demonstrates shared IDs, duplicate active-handle
replacement and raw failed model text on the wire. New code must not change query
meaning, gate policy, prompt, accepted interpretations or historical scores.

- MCP v2 uses an explicit public field allowlist. Retain answer/refusal fields,
  SQL/parameters, plan, grounding, assumptions, verification and bounded rows.
  Remove `raw_output`, `raw_output_repair`, and `question_values` (the offered
  candidate pool, not the resolved answer). Internal AskResult/runner diagnostics
  remain available; no new diagnostic persistence is introduced. This is a
  deliberate public compatibility change, not a general PII-redaction guarantee.
  Add opaque per-invocation `request_id`; not an authorization/cancellation token.
- Each ask has a fresh planner and bounded request state. No shared mutable
  planner trace. Cache schema/overlay only after successful binding; serialize
  cold binding to avoid duplicate construction. Requests waiting for binding
  consume their own budget and cannot cancel another request's bind.
- Server-owned default total budget 30 seconds, configured by
  `GREPBIT_REQUEST_TIMEOUT_SECONDS` (finite, positive). Covers queue/bind, model,
  retries/repair, checks, execution and result preparation. Existing per-model
  and per-DB caps remain upper bounds, reduced to remaining budget. No later
  stage starts after expiry/cancellation; late successful results are discarded.
- Deadline is `failed/request_timeout`, never semantic refusal or answer.
  Unexpected runtime/driver errors become a safe failed code, not raw exceptions.
  Protocol cancellation propagates as cancellation, with no fabricated answer;
  it signals only this request's active connection. No new cancel tool or auth
  surface. Cancellation cleanup has at most two seconds of awaited grace.
- Python worker threads cannot be killed safely. Blocking calls retain native
  connect/statement/HTTP limits; the caller can stop waiting, and checkpoints
  prevent subsequent work. Remote gateway GPU cancellation is NOT promised.
  Physical PostgreSQL stop is verified separately using controlled read-only
  work. Duplicate active registry keys must reject, not overwrite another handle.

## Implementation and validation order

1. Public projection, unique IDs and request-owned services rulers.
2. Minimal request lifecycle object; explicit injection into ask and request-owned
   adapters (no global context, agent framework or persistent job store).
3. Async MCP boundary observes protocol cancellation/deadline; sync governed ask
   stays shared with the runner. DB connections and model calls are bounded;
   native model clients owned by a call are closed in finally.
4. Deterministic blocking tests: overlapping calls, cancellation isolation,
   cancel-before-query, completion/cancel race, timeout between model and DB,
   no retry/repair after deadline, truncation and safe operational failure.
   Focused tests while iterating; one broad offline/static closeout gate.
5. Fresh private read-only PostgreSQL timeout/cancel controls over fictional
   Service/IoT or inline synthetic SQL; do not modify fixture/customer data.
   Then six serial MCP/Gemma requests from the existing authored acceptance set,
   at most 18 actual calls (including all repairs/retries), stop after two
   transport failures, no success-seeking reruns. Existing internal gateway /
   gemma-4-31b, T0 thinking off; only questions, value-free schema and reviewed
   overlay/candidates leave for the model. Golds/SQL/rows never reach it.
   Opaque existing read-only DSNs/key, safe counts/hashes only in evidence.

Private evidence/work record: `.artifacts/serving-lifecycle-20260914/`.
Live SQL delay tests deliberately exercise the executor below SQL policy; delay
functions remain unavailable to model-authored queries. Gate false refusal stays
a failure, not a newly approved exception. Report model versus harness attribution
by evidenced failure family, not an unsupported population percentage.

## Closeout

Root reviewed five intended ruler failures and completed implementation under the
owner's explicit steps 1–4/checkpoint authorization. Added 23 contract tests;
fresh full offline suite: 1,864 passed, zero skipped; static passed. Final
`fault-verified/` evidence distinguishes protocol cancellation from incidental
timeout and confirms physical DB stop plus peer isolation. Six Gemma requests
retain prior judgments with distinct IDs and matching public payload hashes.
Full findings/limitations: `../research/serving-lifecycle-01.md`. No further model
experiments or unrelated production work are part of this completed slice.
