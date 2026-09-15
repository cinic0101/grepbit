# Parent-row checkpoint and known-entry diagnostic

2026-09-15; baseline 8cc6189, root sole writer. No model, PostgreSQL or external
service calls. No owner Web restart, source permission change or push.

## Delivered independently: HTTP failure context

The documented mode echo omitted HTTP-generated errors. Eight intended failures
and 24 controls reproduced it, then the HTTP/explicit-entry focused check passed
55 tests. Subsequent coverage exercises all three backend failure paths in both
Default and Details. Only validated mode values are echoed; arbitrary fields,
invalid modes and backend exception text are not. JSON error codes and SSE event
kinds remain unchanged. This repairs the existing mode contract, not SQL meaning.
Final static gate and **2,244 current-runtime offline tests pass**, zero skips.
The pending parent ruler result below is separate and is intentionally red.

The page freezes a local submission snapshot (question, datasource, mode, reporting
time). It remains visible through rejection/timeout/network failure and after
editing the next question, without being represented as a tool answer. It uses
textContent, no persistence. A Node DOM simulation passed HTTP, SSE and network
failure paths (3/3). This is not a real browser/socket or new MCP/model acceptance.

Documentation clarification for explicit-rows-entry-01: the kind guard checks
the planner's **final proposal after wire normalization/repair**, before application
normalization/compilation. It does not protect the original draft's query kind.
The historical model/result counts remain unchanged; HTTP mode echo was incomplete
there and is repaired in this slice.

## Pending contract: unique-parent projection

Specification: `../plan/parent-row-projection.md`. Explicitly invoked ruler
`tests/contract/t0/parent_rows_pending.py`: **11 intended failures, 13 passes,
zero setup errors/skips**. No production parent compiler/planner change.

Five failures exercise currently rejected legal parent projections; one checks
quoted parent aliases; four expose missing join-invariant checks in the rows
self-check; one is a static catalog contract assertion (single-column/local FK
selection). The latter is not an executed PostgreSQL catalog test.

The separate reference witness actually executes LEFT JOIN, INNER JOIN and
DISTINCT in DuckDB. Repeated base values/shared parent and a NULL FK make the
incorrect operations observably different. Negative parent controls currently
pass because the old parser rejects all parents; do not call that future safe
parent-join validation.

The pending file deliberately does not have a `test_` discovery name. It is
explicitly run and red; the ordinary current-runtime gate excludes this proposed
contract, not through xfail/skip or a changed scoring rule. Rename into ordinary
discovery as part of the approved implementation. Checkpoint remains open under
the newest owner-supplied AGENTS two-phase rule.

## Saved-results diagnostic: routing is useful but insufficient

No new classifier and no best-outcome selection. Choose Details for the original
13 expected rows cases plus three explicitly record-shaped decline controls:
rows_joined_details_gap, kind_rented_rows, kind_vip_rows. Choose Default for the
other 39, including without and aggregate questions. This distinguishes query
kind from the original panel's `decline` answerability label. Shared question,
source, reporting time, ordering, reference SQL and expected-route identities
were checked before reusing each Details grade. Decline reason checks all pass.

| Historical known cases, 55 | Default/fallback run | Known-entry diagnostic |
|---|---:|---:|
| Correct answer | 27 | 32 |
| Wrong answer | 7 | 1 |
| Necessary refusal | 11 | 12 |
| Unnecessary refusal | 4 | 4 |
| Operational failure | 6 | 6 |

This combines two different historical runs. It is neither a randomized paired
comparison nor new runtime replay, routing accuracy, measured router latency,
an accuracy upper bound or unseen-user generalization. It preserves original
grades and oracles; it does not re-score historical time-policy cases.

Residual wrong answer: date_between_inclusive_v1. False refusals: the two
concept_not_mapped minutes cases, svc_absent_feb_ja and offline_devices_count.
Six historical temporal invalid_structured_output outcomes remain. Therefore
correct entry selection alone cannot remove these other bottlenecks. Parent
projection remains a separate compiler capability gap; gate and temporal failures
must not be attributed to the new row compiler or solved by router prompt tuning.

## Evidence and next step

Private artifact root `.artifacts/parent-rows-20260915/`: http-red, http-green,
parent-ruler-final, routing-diagnostic.json, routing_diagnostic.py,
web_failure_dom.cjs, static and offline. Routing diagnostic records source file
SHA256 identities, all per-case selections, outcomes and limitations. Original
artifacts remain untouched. Durable summary: `evidence/parent-row-checkpoint-01.json`.

Confirm the pending unique-parent contract, then implement and validate values,
catalog/visibility/join mutation boundaries and existing reviewed segments. Only
afterward version the explicit row presentation and run bounded shared-service
acceptance. Default prompts stay unchanged; no new router call is yet justified
as a required dependency. Existing UI may collect new owner questions now.
