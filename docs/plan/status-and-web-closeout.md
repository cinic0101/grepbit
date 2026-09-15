# Status metadata and Web guidance closeout

Owner: root. Baseline b22b04e. Authorization: owner accepted the preceding
four-part plan with "ok 開始"; earlier authorization permits local commits,
read-only fixture PostgreSQL, serial Gemma calls, and an idle local Web restart.
No push, real-data access, production gate relaxation or customer-data mutation.

## Scope and fixed acceptance

1. Use existing value_aliases for devices.status only: online (在線/線上),
   offline (離線), maintenance (維護中). These describe current status, not
   alert absence or lease identity. Reviewer: root under this accepted fixture
   mapping task; provenance: iot_v1 CHECK, comment and seed. No new defaults,
   policies, sampling, grounding permissions, metrics or absent-concept entries.
2. Compare unchanged no-overlay Web with this overlay through actual HTTP/MCP.
   Fixed 12 IoT cases and four Service controls per arm, then four scheduled
   candidate repeats: at most 36 HTTP requests, up to 108 native completions
   under existing retry/repair limits. No same-endpoint concurrency. Outbound:
   synthetic schema, approved value labels, questions and planner messages only,
   to existing LAN Gemma gateway; credentials opaque, DB role grepbit_ro.
   Freeze source/tests/probe/cases across both arms. No generic prompt edit;
   enabling an overlay also enables the existing conditional overlay instruction,
   so the intervention is the existing overlay path, not alias tokens alone.
3. Adopt only if targeted natural-status answers improve, negative/all-status
   populations are correct, supported controls do not regress, and lease/SLA
   definitions are not fabricated. Unknown status must not become a known one.
   Score answers, necessary/false refusals, wrong answers and failures separately.
   Compare actual plans/scopes as well as independent SQL values. This known
   diagnostic panel is not holdout generalization or a population error rate.
4. Web guidance is local presentation only: immutable original result/status,
   no error-message parsing, auto-resubmit, automatic kind change or promise
   that Details will answer. Counts/sums/without and genuine missing definitions
   remain distinct. Existing Default aggregate-equivalent answers remain valid.
5. New time witnesses use inline synthetic relations in readonly PostgreSQL
   and offline DuckDB; never modify the active Web fixture. Correct and wrong
   plans must disagree on boundary inclusion and asymmetric month averages.
   Do not regrade historical matches as failures or claim new NL accuracy from
   compiled-plan witnesses.

## Gate decision (bounded design review, no implementation)

Current evidence supplies no new independently trustworthy request-role/scope
signal. The already-stopped source-scoped and finite-English candidates remain
stopped. A new gate candidate must name its signal, command/business occurrences,
same-question correct/wrong-plan controls, attainable target coverage and unknown
policy before implementation. S8 recurrence confirms the defect, not a new fix.
No production gate change, new dependency, parser or verifier in this slice.

## Work record

- Preflight: baseline clean; local Web listening on 8765. Root is sole writer.
- Evidence destination: .artifacts/status-web-closeout-20260915/ (fresh outputs).
- Rulers reuse existing overlay/API/time semantics; no new compatibility-sensitive
  contract. Test expectations and measurement criteria precede live runs.
- Finish with focused tests, one broad offline/static gate, independently reviewed
  live values/plans, local adoption only on passing evidence, and final Git state.
- Live completed: 36 requests, baseline 9 correct/3 false refusals -> candidate
  11 correct/1 false refusal; four appropriate non-answer controls unchanged.
  Four preselected repeats pass; all values and scopes independently checked.
- Adopted existing status overlay in rows-enabled Web registry. Active assets
  and production binding verified; no backend restart or extra model call needed.
- Return remains open, no new candidate implementation. Time witnesses: 12
  tests across DuckDB and three PostgreSQL zones, 40 compiled SELECTs.
- Final report: docs/research/status-and-web-closeout-01.md. Static passes;
  2,335 offline tests and 57 focused tests pass, zero skips. PostgreSQL evidence
  reused only after exact witness/production-source hashes were checked unchanged.
  Gate remains no-go; authorized local Git closeout follows final delta review.
