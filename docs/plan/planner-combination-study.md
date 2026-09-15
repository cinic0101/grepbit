# Planner guidance combination: bounded 2 x 2 study

2026-09-15. Baseline `bbf4ef9`, clean dev, root sole writer. User "ok" accepts
the preceding next step (baseline / timestamp / composition / combination).
Original session grants authorize autonomous checkpoint decisions, psql/Gemma,
and local commits without asking again; no push. No runtime promotion, router,
gate change, DB writes, persistent contract or public format changes.

## Identification and acceptance

All four arms use the **same research joint-v1 planner** (rows enabled), not v15
for one arm and joint for another. The factors are the exact frozen generic
timestamp guidance from temporal-repair-study and exact without-composition
replacement from without-capability-study. Distinct revisions; unchanged question,
schema/overlay/candidates, wire, validation, compiler, policy and execution.
No repair guard in live arms: separate guard effects were measured previously.
One planning stage, existing bounded repair only; no independent router/fallback.

Panel = ID-deduplicated union of query_kind_study, without_capability_study and
temporal_repair_study. Assert duplicate question/source/as_of/reference/route/
order identity rather than silently picking one. 55 authored/seen controls:
30 aggregates, 13 rows, 12 required declines. Freeze before any model call.
All expected answers use independent PostgreSQL SQL; precision cases additionally
require typed execution on boundary witnesses, including independently separated
Service start/end instances. Historical oracles and scores remain unchanged.
These are not fresh user holdouts or full product regression coverage.

Rotate arm order per question. Report per-case transitions and per-stratum
correct answers, wrong answers, necessary/unnecessary refusals, operational
failures and unjudged results. A combination that rescues cases but introduces
new errors is not unconditionally better. Do not pick winners by total pass
or pool necessary refusals with answered coverage. Repeat four predeclared
sentinels (precise noon, Chinese without SUM, Japanese multi-hop absence,
missing MTTR) in a fresh process for all arms. No tuning during or after results.

## Work and external scope

1. Rulers: exact factor isolation, invalid arms, joint no-change control,
   panel deduplication and counts. Meaningful static assertions verify a
   research prompt contract, not a changed production behavior.
2. Implement a thin study planner, no new runtime API/framework. Focused/static.
3. Serial Gemma 4 31B via existing internal LiteLLM gateway; T=0, thinking off,
   30-second request budget. Up to **320 actual model calls** including repairs
   and transport retries, counted before calls. Main 220 initial requests,
   repeat 16, remainder repair/retry allowance. Stop at cap, do not erase failures.
   Outbound only synthetic questions and schema/reviewed metadata/candidates;
   never SQL, rows, gold plans or credentials. Opaque existing .env and password
   file, DSN environment variables; no credential copies or printing.
4. Readonly grepbit_ro on existing localhost synthetic IoT/Service databases;
   sampling zero. Isolated DuckDB witness data, no customer data or DB writes.
5. Freeze source/fixtures during runs. Fresh artifacts under
   `.artifacts/planner-combination-20260915/`. Focused then one offline gate;
   source/hash evidence, document limits, root review, authorized local commit.

No authority is granted by this work record itself; it references the user's
existing grants. Any discovered oracle ambiguity must be recorded separately,
not silently changed to make an arm win. A material unresolved product decision
stops that affected path, not independent research analysis.

## Post-hoc recurrence check, specified while the main run is frozen

The main run observed a composition-only answer without a lease definition,
a combined-only false refusal on Chinese three-hop absence, and a baseline-only
false refusal on English absence SUM. After the predeclared repeat, run one
separate four-arm follow-up on `cov_leased_fee`, `svc_absent_feb_zh`,
`svc_absent_sum_en`, plus adjacent refusal control `kind_rented_rows`.
These 16 initial requests stay inside the original 320-call total cap. They are
post-hoc recurrence diagnostics, not extra holdout evidence or a reason to tune
the frozen interventions. Keep the initial findings regardless of recurrence.

## Closeout

277/320 calls completed; main, predeclared repeat and post-hoc checks remain
separate. Zero-model-call same-plan PostgreSQL replay additionally verifies
session-dependent naive timestamp interpretation. SET LOCAL was transaction-only,
no persistent DB changes. Six new factor rulers pass; focused 36, offline 2,064,
static pass. No runtime promotion; see the research report and durable evidence.
