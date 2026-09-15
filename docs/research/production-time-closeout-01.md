# Production time delivery: binding accepted, repair guard integrated

2026-09-15, baseline `8701dfd`. Root sole writer. Owner approved the revised
integration roadmap, independent delivery and autonomous checkpoint decisions.
Scope/permission sources: `../plan/production-time-closeout.md`.
Evidence: `../../evidence/production-time-closeout-01.json`.

## Product decisions

1. **Close typed-time binding service acceptance independently.** Actual HTTP/SSE
   -> stdio MCP -> shared ask -> readonly PostgreSQL retains parameters,
   assumptions, request identity and public payload. Separate saved actual-plan
   replays prove approved naive-to-business-zone binding and correct values.
2. **Adopt the narrow temporal repair guard in the shared planner.** No prompt,
   router, row-default, public field, permission or compiler change. The same
   runtime module now owns the candidate check; the research wrapper delegates
   to it and retains only explicit historical guard-off/guidance controls.
3. **Do not claim improved answer coverage.** Four wrong repairs become failed
   requests, not correct answers or necessary refusals. The remaining first-
   generation / unsupported repair / semantic selection gaps stay open.

## Contract before implementation

The old guard accepted offset timestamps only and did not use physical source
type. Compatibility rulers first produced **11 intended failures / 26 passes**.
After applying approved binding semantics, 36 focused tests passed (one obsolete
"missing offset is always unknown" case was replaced, not silently kept as gold).
Two additional legal date-filter-at-midnight controls failed before correction;
the updated focused set passed 38. Runtime rulers then produced **4 failures /
2 passes**: changed/unknown repairs were served and no request-local audit existed.
One final year-0001 UTC conversion ruler caught an OverflowError, now classified
unverifiable rather than escaping as a raw exception.

`domain/temporal_repair.py` compares recognized invalid plan/without timestamp
range anchors with the repaired plan. It uses the approved source-type binding
policy: naive instants use business timezone; clock labels stay clock labels;
offsets on unbound clock columns, DST gaps/folds, unknown source types and lossy
precision are unverifiable. Equivalent offsets compare in UTC; date-only filter
midnight and calendar representations are allowed when genuinely equivalent.
Column, population scope, effective bound and inclusion changes are protected;
keeping the original literal beside a stronger rounded window does not pass.

Four diagnostic outcomes remain distinct: preserved, changed, unverifiable,
not_applicable. Runtime blocks changed and unverifiable with existing
`failed / invalid_structured_output`, retains original/repaired diagnostic text
internally and adds no model call. Safe declines and ordinary repairs are not
blocked. `last_temporal_repair_audit` resets per request and is copied through
the existing opt-in baseline stage; it is not a new public response field.

This is NOT an intent verifier, all-filter equivalence checker or blanket claim
of preservation. It does not prove an initial draft correct, cover unreadable
drafts, guard every measure/filter location, or fix valid first-pass mistakes.
Blocking unknown can reduce coverage; unknown blocks must not be credited as
confirmed catches. More general checking is not required to ship this bounded
safety improvement.

## Frozen service measurement

Ten existing cases from `evals/cases/temporal_repair_study.yaml`: Chinese/Japanese
noon, equivalent UTC, Service logs, without alerts, fractional bounds, calendar
control, offline device count, missing MTTR and missing rental definition.
No new paraphrase tuning or oracle relaxation. The preparation fingerprints
messages and independent SQL results before model calls. Same Gemma 4 31B, T=0,
thinking off, sample limit zero, readonly synthetic Service/IoT. No gold SQL,
rows or credentials go to the model. Loopback port 18765 does not replace the
owner's existing Web. Actual browser visual interaction is not claimed.

| Outcome / 10 | Baseline live | Candidate live, combined segments | Integrated runtime exact-reply replay |
|---|---:|---:|---:|
| Correct answer | 2 | 2 | 2 |
| Wrong answer | 4 | 0 | 0 |
| Necessary refusal | 2 | 2 | 2 |
| False refusal | 1 | 1 | 1 |
| Operational / failed repair | 1 | 5 | 5 |

**30 actual Gemma calls total**, 15 per logical arm; zero transport failures.
All ten raw response sequences (including repairs) are byte-identical across
the two live arms. The guard confirms changed anchors for four cases; this
panel has zero unverifiable blocks and no naturally occurring successful
temporal repair. Legal repair retention is therefore covered by controlled
runtime/compatibility tests, not a fabricated live denominator.

All four baseline wrong answers matched the ordinary fixture scalar/rows, but
failed the predeclared boundary instances. They remain wrong in reporting.
Japanese noon retained correct naive filters but also added a stronger rounded
calendar range: the new binding and disclosure worked while the intersection
was still wrong. The guard catches this as changed. Offline device count is a
model ambiguous decline on an answerable case; without remains invalid after
repair. Neither is credited as a safety success.

One harness interruption is separate: while candidate calls were running, new
runtime test files changed the verification runner's broader source digest,
despite src/evals being frozen. The ninth request stopped in probe startup
before any model call. Eight completed requests remain intact; the two untouched
refusal controls were prepared and run in `candidate-tail/`. No source changes
to production or candidate logic occurred between those two live segments.
Do not call this one uninterrupted frozen run. Future phases freeze all Python
inputs (including tests) because the source pin includes them.

## Actual served binding, separately from natural generation

`binding-replay/` supplies two previously saved **actual** time-arm model plans
from the combination study to the normal planner validation stage, not hand
corrected plans. They pass actual Web/MCP/ask/PG and independent boundary data.
Both produce explicit +08:00 timestamptz parameters and business-timezone
assumptions, identical at MCP and HTTP. This establishes binding service
integration; it is **zero-model-call replay, not two new natural-query successes**.

`runtime-replay/` uses all ten baseline raw reply sequences through the newly
integrated runtime, with the actual transport/DB path and zero model calls.
Four harmful repairs stop, controls remain identical. All 32 successful HTTP
deliveries across live and replay phases preserve complete public payload
fingerprints and request identity; debug raw replies/question_values stay out.
Boundary fixtures stay isolated in memory; no persistent DB writes/admin use.

## Validation, cleanup and next delivery

Final static passes; **2,191 offline tests, zero skips**. The focused runtime
set passed 44 before the final overflow control; the final broad gate includes
all 45 temporal guard tests. Source hashes and phase timing are in evidence.
No prompt revision change: original and repair messages stay unchanged.

Removed duplicate audit implementation and validation interception from
`evals/temporal_repair_study.py`; a small historical control wrapper reuses
production. No customer artifacts, historical reports or unrelated code deleted.
No deployment/restart of the owner's Web and no push.

Time binding and this bounded guard are now delivered shared-path changes,
not reasons to keep all capabilities waiting. Next: the details/aggregate
integration slice, including rows-versus-entities, missing-definition controls,
visibility/limits and actual consumer acceptance. Reuse the successful Unicode
research representation for later conversion/independent-aggregate integration.
See `../plan/production-integration-board.md`; collect genuinely new questions
alongside implementation without treating old cases as fresh holdout.
