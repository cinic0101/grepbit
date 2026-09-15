# Reviewed IoT status values accepted; Web guidance and time witnesses

2026-09-15, starting at b22b04e. Protocol:
[`status-and-web-closeout`](../plan/status-and-web-closeout.md).

## Decisions

- Adopt the existing value_aliases path for this synthetic IoT datasource.
  It recovers the two targeted false refusals without observed control regressions.
  The rows-enabled local Web registry now loads `iot_v1/status_overlay.json`.
- Deliver local, mode-specific failure guidance without changing status, reason,
  question, mode or original evidence. No router, message-keyword parser or retry.
- Keep the Return gate defect open. No gate candidate adds sufficient new evidence
  in this slice; no production gate relaxation, parser dependency or verifier.
- Add durable distinguishing time tests. These validate compiled plans, not new
  natural-language success or universal semantic equivalence.

## Fixed paired live measurement

Actual loopback HTTP -> development Web -> production stdio MCP -> shared ask ->
existing LAN gemma-4-31b / readonly PostgreSQL. Both arms used the same frozen
source/tests/probe and synthetic DBs, sampling zero, temperature zero, thinking
off, ordinary retry/repair settings. Requests were serial: baseline 16, candidate
16, then four preselected candidate repeats. Original Web on 8765 was not
interrupted; the same production Web implementation ran on temporary 8766 and
was stopped after each arm. No database data/schema/grants were modified.

The 12 IoT requests test offline/maintenance/online counts, NOT online, explicit
offline, July absence, all-status counts/fees, unknown sleeping, missing lease
identity, offline details, count-in-Details conflict and direct-parent alert
details. Service controls are original S1 COUNT/NULL/DISTINCT, S7 List minutes,
S8 Return minutes, S10 missing SLA. Reporting times remain August 15 for IoT and
April 15 for Service. Exact questions, references and schedule preceded calls.

| Outcome (16 main requests per arm) | No IoT overlay | Status overlay |
|---|---:|---:|
| Correct answers | 9 | 11 |
| Necessary missing-definition refusals (lease/SLA) | 2 | 2 |
| Necessary unknown-value clarification | 1 | 1 |
| Necessary mode clarification | 1 | 1 |
| False refusals | 3 | 1 |
| Observed wrong answers | 0 | 0 |
| Operational failures | 0 | 0 |

Preselected candidate repeats: offline=2, maintenance=1, NOT online=3, lease
semantic_gap; all four retain the intended outcome. They are repetitions, not
four new independent questions. Cases are known diagnostics, not a blind holdout
or an estimate of population accuracy.

Specific checks:

- Offline and maintenance become COUNT over exactly the corresponding status,
  not all devices. Online remains 5. Explicit offline remains 2.
- NOT online remains `status <> 'online'` and returns 3, including maintenance.
- No July alerts remains scoped NOT EXISTS and returns d008 (online), without
  introducing an offline predicate. Supplementary count=1 is accurate and allowed.
- All-status grouping remains maintenance 1/800, offline 2/500, online 5/1800.
- `sleeping` is not changed into a known status: both arms reach the existing
  filter_value_not_found clarification. Prepared SQL may be present even though
  no answer rows are executed/returned; SQL presence is not answer success.
- Lease/SLA refusals explicitly name the missing definition. No absent-concept
  entries were added to force these outcomes.
- Details preserves two offline IDs and all 15 alert records/parent fields/NULLs.
  The original parent question is used without the owner's earlier U+2801 variant.
- S1 remains 10/9/7; S7 preserves all ten ordered values including duplicates/NULL.
  S8 still has exactly S7's final plan and is blocked by concept_not_mapped.

Values were compared with independent PostgreSQL reference queries frozen before
the calls. Case-specific scope assertions additionally inspect actual plans,
operators, measures, absence window, projection and ordering. No model judge,
reworded failure or retrospective relaxed threshold was used.

All 36 responses report zero model retries, repair turns and row fallbacks.
Each main arm has one exact duplicate-columns shape normalization on I12 (1/16).
Original raw-wire variation is NOT fixed; the construct freeze is not relaxed.
HTTP p50 was 3.06s baseline, 3.19s candidate, including necessary/false refusals;
this small sequential panel is not a latency improvement claim. HTTP invocation
and diagnostic counters are not independent provider-completion telemetry.

## What changed in the planner information

The fixture's TEXT CHECK already constrains status to online/offline/maintenance;
the current introspector does not expose CHECK labels as enum samples. The new
overlay provides reviewed Chinese names plus stored spellings. Sampling remains
zero, no column is newly groundable, and no row values are sampled for the model.
No metrics, default segments, time defaults, absent concepts or policies change.
Fixture mapping review: root under the owner's explicit approval to implement
this mapping; provenance is the fixture CHECK, connectivity comment and seed.

Enabling an overlay also activates the existing conditional overlay instruction.
Thus this is evidence for the existing overlay path, not an ablation proving
alias tokens alone caused the change. No prompt text or revision was edited.
Default remains v15, explicit Details remains v20-parent-rows.

Production binder/schema payload was checked against each registry. The saved
`*-production-messages.json` are separate binder/build_messages diagnostics,
NOT network captures; their default service object has allow_rows enabled, so
its direct builder shows the fallback wire. Additional completion-boundary tests
invoke the real propose dispatch with a stub completion: Default actually uses
v15 first; Details uses v20; both carry these aliases. No fabricated successful
model result is credited from the stub. Live results above use the real endpoint.

## Web delivery and non-claims

Mode descriptions were already present; they are clarified, not replaced by a
new UI. For clarify/semantic_gap/unsupported, local guidance explains the selected
mode and explicitly says it is NOT a diagnosis of the refusal. It does not promise
Details can answer, infer the question's kind, rewrite an erroneous semantic_gap,
or tell the user to drop a business condition. Disabled Details is respected.
Answered/failed results receive no semantic mode suggestion. Original refusal,
evidence and request mode are unchanged and rendered as text.

JavaScript render tests exercise all three refusal statuses plus answered/failed,
both modes and disabled Details, with untrusted text; only initial config reads
occur, never an automatic /query. These are DOM-stub execution tests, not a full
browser visual or end-user usability study. Actual 8765 assets/config were fetched
and match the files. Production binding after adoption exactly matches the
measured candidate schema payload. No restart was required: backend code is
unchanged, assets are read from disk, and each query starts a fresh MCP child with
the current registry. No extra model call was made for this adoption check.
Fixing the model's refusal-type selection remains an open item.

## Distinguishing time evidence

`test_owner_time_witnesses.py` compares hand-computed answers with shared compiler
SQL in DuckDB and readonly PostgreSQL inline VALUES under UTC, Los Angeles and
Taipei sessions. No active Web fixture is mutated.

- July 1 midnight and July 7 23:59:59.999999 count as 2; June 30's final microsecond
  and July 8 midnight do not. Wrong end July 7 yields 1, wrong end July 9 yields 3,
  omitted window yields 4. Each error is distinguishable.
- Two asymmetric month instances have July averages 20/40 and August 90/200.
  Both wrong-month and omitted-month plans differ from the intended result.
- 12 engine/instance tests pass, totaling 40 compiled SELECT executions, including
  30 on PostgreSQL. Additional original typed-time/DST rulers are unchanged.

Original IoT averages matched the live fixture, but its periodic temperature
formula can hide missing month filters. Original July 7 has no alerts and cannot
prove final-day inclusion. Preserve historical value-match scores with these
limitations; new counterexamples are not retroactive natural-language failures.

## Gate follow-up decision

Rechecked source-scoped gate study: recovery came with two new wrong releases.
Rechecked finite-gate v1: rows-only support excluded two of three nominated targets
before implementation, so the beyond-minutes adoption threshold was unattainable
on that fixed target set. Keep v1 stopped; do not call this an empirical discovery
that its excluded aggregate forms were unsupported.

A next candidate needs a genuinely different request-role/scope signal, explicit
occurrence handling for "Return the return rate", correct/wrong plans for the
same question, achievable scope/targets and an unknown policy. No such production-
ready candidate is established here. This is a bounded no-go decision, not a
claim that gate false refusal is solved or that all parsers are impossible.

## Validation and artifacts

Private evidence: `.artifacts/status-web-closeout-20260915/` (frozen live manifest,
36 response records, independent oracles/review, PostgreSQL witnesses, adoption
check, focused/static/offline outputs). Durable summary:
[`evidence/status-and-web-closeout-01.json`](../../evidence/status-and-web-closeout-01.json).
Initial focused: 54; final focused with dispatcher/adoption checks: 57, zero skips.
PostgreSQL-enabled witnesses: 12, zero skips. Static passes; broad offline gate:
2,335 passed, zero skips. Final focused/static/offline source digests match.
PostgreSQL witness and production source hashes remain unchanged at final gate;
later differences are adoption registration and additional presentation/dispatch
tests, not time binding. Early new-test helper failures (DuckInstance return
shape/connection API) were test wiring errors, not compiler findings; fixed before
measurement. Review's initial assumption that a literal refusal has no prepared
SQL was corrected without changing answer/refusal criteria or issuing new calls.

No new query construct, external response field, evaluation classification,
security/authorization policy, identity binding, dependency or DB persistent state.
Only existing local Web configuration gains a status overlay; no remote deployment
or push. Unit conversion/independent aggregates, automatic routing, remaining
intent errors and wire health retain their previous work items.
