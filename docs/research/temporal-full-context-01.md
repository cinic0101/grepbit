# Full-context temporal reproduction: baseline ceiling again

2026-09-13, clean baseline `771284a`. The owner approved the preceding next
step with "ok 可以開始下一步": reproduce the original full-schema baseline
first; compare information/reference arms only if temporal errors recur.
Production remains ask v5 / `plan-classify-json-v15`. No runtime change.

## Result and decision

Three frozen questions, two serial passes: **6 executions / 6 actual Gemma4 31B
calls**, all six accepted under the **unchanged historical rules and oracles**.
Zero validation repairs, refusals, unassessed outputs or transport failures.
Call-time p50 **3.94 seconds**. The conditional comparison was **not started**.

| Case | First pass | Second pass | Observed interpretation |
|---|---|---|---|
| `year_zh`: original quarterly payroll question | accepted | accepted | paid_at, base salary, four quarters of 2025 |
| `year_en`: English quarterly payroll question | accepted | accepted | same permitted interpretation |
| `paid_year`: explicit payment-date/base-only control | accepted | accepted | same required interpretation |

All six model responses initially supply a native range ending `2026-01-01`;
none supply `2060-01-01`. Raw-scope hashes equal the validated scope hashes.
Initial and final plans are identical per call. Effective bounds are
`2025-01-01T00:00:00+08:00` through `2026-01-01T00:00:00+08:00`, exclusive.
All return four rows and pass independent PostgreSQL values plus existing
interpretation/disclosure checks. This is not a clamp, repair or refusal rescue.
Each question's raw-response hash is identical across its two calls.

The original broad payroll wording retains its historical permitted date-basis
and component alternatives. Acceptance does not establish a unique payroll
definition; the explicit control requires paid_at and base_salary only.

## Was the original context actually restored?

Yes, at the recorded application-request level. This is the complete consented
POS/HR fixture: **13 tables, 58 columns**, datasource `pos_test`, sampling limit
20, no overlay, no value index, `as_of=2026-02-10T12:00:00+08:00`.
All three context, rule, message and oracle records match the frozen baseline
entries in `.artifacts/temporal-semantic-controls-20260913/frozen.json` exactly.
Prompt lengths are 20,967 / 20,993 / 20,992 characters respectively. No synthetic
replacement schema, new column description, candidate hint or prompt edit.

Gemma4 31B, existing gateway, temperature 0, thinking off, one permitted
validation repair, 20-second timeout; configured max_tokens 512 (production
planner raises the request to at least 768). Six initial calls were frozen with
a twelve-actual-call cap. Calls were serial, clients closed, transport retries
suppressed. These are two passes in **one run**, not independent sessions.

The historical record did not freeze the backend model weights, gateway routing,
server version, batch composition, cache state or every transport-level setting.
Equal application messages do **not** prove an identical inference environment.
This study cannot identify which unobserved factor changed the output.

## What this changes, and what it does not

- The previous synthetic-schema ceiling is no longer the only observation:
  the original full request can also answer correctly without intervention.
- The historical 2060 failure remains valid evidence. No fix was made, and six
  closely spaced correct calls do not establish a low production failure rate.
- A fixed question/prompt/schema is not sufficient to predict that error on
  every invocation. Backend batch effects remain a hypothesis, not a diagnosis.
- Neither this run nor the preceding reference study demonstrates incremental
  benefit from scope_ref. No reference calls occurred here; v1.1 remains offline
  tested only. Automatic extraction and production integration stay deferred.

## Validation and evidence

Private root: `.artifacts/temporal-full-context-20260913/`, with the bounded
permission/work record, reproducibility runner, tests, frozen preparation,
six records, summary and end-check. Durable counts and SHA-256s are in
`../../evidence/temporal-full-context-01.json`.

- **10 focused tests**: schedule bounds, exact start/end checks (including 2060
  and future-clamped foils), missing windows, fatal payload drift, attempt caps,
  suppressed transport retry and raw-response temporal evidence.
- **18 compiled-vs-independent PostgreSQL oracle checks per preparation**;
  preparation, pre-call and post-call snapshots match. Repeated checks are not
  additional cases. All six served answers also match the frozen reference.
- Tracked source digest unchanged from the preceding study. Its **1,841-test
  offline result is reused**, not reported as a new full-suite run. Static gate
  is run for this documentation/evidence closeout.
- grepbit_ro and read-only transactions only; no data/schema writes, administrator
  credentials, SQL/result rows sent to the model, raw response persistence or
  real POS data. Original consented fixture samples are sent only in memory;
  published evidence contains counts and hashes, not sampled values.

## Next order

Stop this intervention experiment at its predefined ceiling. Keep production
unchanged and retain the original case as a sentinel in future already-planned
regressions; do not start an unbounded polling campaign just to reproduce it.
If it recurs, preserve the application/source/request identity and, where safely
available, provider revision/request metadata before retrying. Then freeze the
same-context information/reference v1.1 comparison **before** further calls.

Meanwhile, prioritize the existing product regression and unresolved reproducible
semantic errors over an automatic time-parser feature. A future reference study
needs repeated rescue beyond the information-only control, not just valid IDs.
No deployment, release, push or promotion claim.
