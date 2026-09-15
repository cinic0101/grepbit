# Explicit details request: bounded acceptance and delivery

2026-09-15, root sole owner; baseline fe96f5e, initially clean.
Authority: owner approved the preceding four-step plan with "ok 開始吧";
earlier owner grants allow autonomous checkpoint decisions, readonly psql,
existing on-prem Gemma and local commits. No push or existing Web restart.
Keep one owner for this coupled request contract; no worker delegation needed.

## Contract ruler

Proposed additive `query_kind`: omitted/default retains today's exact planner
and fallback strategy; `rows` explicitly asks for base-record details.
Datasource `allow_rows` remains an independent operator capability permission,
not a per-request override. An explicit rows request on a disabled source stops
before a model/DB call. Unknown modes are input errors, not implicit defaults.

Only `rows` plans may execute in that entry. A model-produced aggregate/latest
is an operational `request_query_kind_mismatch`, never a successful refusal or
an automatic fallback. Enforce in shared ask before repairs/compile/execution,
not just the prompt. Do not modify default messages, gates or aggregate behavior.
Modes and all invocation-local state must not leak between concurrent requests.

The model must still preserve the question's population, filters, columns and
counting unit. A request for COUNT/SUM conflicts with rows mode: decline ambiguous
and ask the caller to use default mode, not return records instead. A supported
but unrepresentable rows+without/join declines unsupported; missing business
definitions decline semantic_gap. These are model proposals, not guaranteed
language judgments. The mode itself is only evidence about output kind.

Reuse current base-row algebra and visibility, primary-key order, duplicates,
NULL, parameter binding, grounding, limits/truncation, lifecycle and public
projection. No new DB capability, row authorization, SQL generation pathway,
unit conversion, ontology, selector or router. Ordinary projections do not need
invented business definitions. Do not change historical correctness scores.

## Finite execution plan

1. Private research adapter/rulers: current v17 wire plus one explicit mode
   instruction, frozen as `plan-classify-json-v19-explicit-rows`; no joint POLICY,
   composition or time guidance. Keep original question unchanged and send mode
   separately. Rulers separate value outcome, returned plan kind, entry acceptance
   and refusal reason; failed kind guard is not necessary refusal.
2. Known 13 row cases, missing-definition and joined/without boundaries, aggregate
   conflicts, plus duplicate/non-PK projection controls. Independent reference SQL
   and multi-instance witness data; serial readonly Service/IoT and existing Gemma
   only. Model receives questions/schema/approved fixture metadata, never rows,
   gold SQL or credentials. Sampling zero. At most 100 actual model attempts
   including repair/retry, targeted repeat and any integrated consumer calls.
   Stop after two transport failures. Freeze all fingerprinted inputs during calls.
3. Adopt only if ordinary rows improve over historical fallback with actual rows
   plans, no new wrong population/projection, and conflict/missing-definition
   controls retain appropriate declines. Known gate false refusals remain named
   separately and do not become planner success. Repeat any new critical failure
   once; recurrence rejects promotion without a new prompt variation.
4. If accepted, add runtime/API rulers first, implement through shared ask and
   existing MCP/Web, parity-check the measured messages, then focused, static and
   one offline gate plus consumer acceptance. Explicit request mode is additive;
   no default routing promotion. Do not enable source flags until acceptance.
   If rejected, preserve the contract/evidence but do not add a dormant public
   API or permanent candidate implementation. Route the blocker to scope binding.

Artifacts: `.artifacts/explicit-rows-20260915/`. Reuse prior guard acceptance
separately. Review complete delta against fe96f5e and report exact Git state.

## Completed

Bounded candidate accepted and integrated through existing ask/MCP/Web. 24 known
cases: 13 correct answers, ten appropriate refusals, one known gate false refusal;
14 proposed plans are rows. Four-case repeat, 24 actual HTTP/MCP saved-response
replays and nine fresh HTTP/MCP requests complete. Total 39/100 Gemma attempts.
114 related tests, static and 2,233 offline pass. Separate opt-in synthetic profile
added; original profile and running owner Web unchanged. No auto-routing promotion.
See `../research/explicit-rows-entry-01.md` for limits and follow-up.
