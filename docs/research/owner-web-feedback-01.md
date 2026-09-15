# Owner Web feedback: IoT transcript and Service live bank

2026-09-15, runtime baseline `0e44a28`. Owner first supplied 13 IoT observations
and asked that unspecified modes mean Default, then asked the agent to execute
the exact Service S1–S10 bank and report conclusions. Earlier local DB/model and
commit authorization applies; no push. The owner separately authorized automatic
local test-Web restart when needed. No restart was needed during this run.

Only synthetic IoT/Service databases and the existing private Gemma gateway were
used. Runtime, prompt, overlay, gate, schemas and UI were not modified. No new
sampling, dependency, response format, identity rule or evaluation threshold.
These are assistant-authored diagnostic questions executed through a real
consumer, not a blind holdout or a product reliability estimate.

## Evidence boundaries

IoT is an owner transcription: 13 opaque request IDs, original question strings,
reported labels/explanations and eight displayed tables are preserved privately.
Only the two explicitly marked Details requests are recorded as rows; the rest
are Default, even when the question asks for listing. Reporting time, plans,
SQL/bindings, assumptions and truncation flags were not supplied. The suggested
UI date is recorded separately, not asserted as the invocation's actual as_of.
The transcript's `ambiguous` is a reported label, not an invented public status.

Service is ten fresh serial HTTP requests to the existing local Web, using real
MCP, the authorized Gemma4 31B gateway and the rows-enabled fixture registry.
Reporting time is exactly `2026-04-15T12:00:00+08:00`; S7–S9 are Details, all other
requests Default. Independent readonly PostgreSQL references, original questions,
expected behavior/focus, source/probe hashes and schedule were saved **before**
the first model request. Existing runtime retry/repair remained enabled; no
manual retry, rewritten question or prompt intervention followed a failure.
HTTP request count is ten, not independently instrumented provider completions.

Private intake/results: `.artifacts/owner-web-intake-20260915/`:

- `iot-01.json`: original 13 observations, including exact request IDs and
  the U+2801 character in the Details alert question.
- `iot-01-oracle.json`: independent SQL and current values for all eight tables.
- `service-01-cases.json`, `service-live/manifest.json`: frozen questions/oracles.
- `service-live/S1.json` … `S10.json`: complete public SSE/MCP responses,
  request IDs, plans, SQL, bound parameters, assumptions and diagnostics.
- `service-01-review.json`: value and case-specific semantic review; no model
  calls to judge the model. Durable summary/hashes are in
  `../../evidence/owner-web-feedback-01.json`.

## Service: eight correct answers, one necessary refusal, one false refusal

| Case | Result | Review |
|---|---|---|
| S1 rows / non-NULL minutes / distinct tickets | 10 / 9 / 7 | Correct; the non-NULL count is COUNT(*) with an operand-level NOT NULL filter, equivalent to COUNT(minutes), without filtering the other measures |
| S2 monthly actual logged minutes | Jan 100, Feb 50, Mar 250 | Correct logged_at month/window; unknown-date rows excluded and disclosed |
| S3 February closures, independent of creation date | 2 | Correct closed_at filter, no created_at restriction |
| S4 teams with no February work | 北區／維運中心（第二期）, 東京・検証専用チーム | Correct scoped NOT EXISTS, including the never-active team; related per-team count=1 is accurate |
| S5 exact 北區設備巡檢 | 349 minutes | Correct exact project scope, including unknown-date work |
| S6 exact 北區設備巡檢／延伸計畫 | 0 minutes | Correct independent project; zero retained, no prefix-name union |
| S7 List minutes | Ten rows, including repeated values, zero and NULL | Correct base-row listing ordered by unprojected id |
| S8 Return minutes | clarify / concept_not_mapped | False refusal: same final plan as S7, blocked by returns vocabulary |
| S9 work-log attributes plus ticket status | Ten rows | Correct direct-parent LEFT JOIN, flat tickets.status key, duplicates/NULL retained |
| S10 project SLA achievement | semantic_gap | Necessary missing-definition refusal; no substituted closure rate |

All eight answered results match the independently frozen SQL references. Review
also checked actual plan population, measures/operand filters, date columns,
windows, name filters and assumptions. Cosmetic aliases are not semantic errors;
S4's correct supplementary count is allowed by the existing acceptance policy.
This is a bounded current-fixture judgment, not multi-instance equivalence proof.

### S7/S8 localize a real gate failure, not a planner-selection failure

The two served final plans are exactly equal: `work_logs`, only `minutes`, no
filter, rows projection, id ascending. S7 executes correctly. S8 has no SQL or
rows because `unmapped_concepts` matches the command `Return` to `returns`.
Offline evaluation of the existing function with these actual plans reproduces
`[]` for List and `[(returns, return)]` for Return. This is stronger than merely
comparing statuses, but it does not validate a replacement gate or justify
disabling checks on genuine return concepts. The stopped finite-parser candidate
is not reopened by another occurrence of its already-known motivating example.

Both exact-name questions use one request-bound value reference and preserve the
correct distinct project. All responses report zero model retries and zero model
repair turns. S9 records one exact redundant-columns shape normalization; this
is still a wire variant, not a repaired business meaning or a freeze exemption.

## IoT: all eight displayed answer tables match; qualifications remain

| Observation(s) | Review |
|---|---|
| I1 Default offline count | Known value-meaning availability refusal recurs; I2 supplies the stored literal and answers 2. Not evidence of the Return concept gate; original planner trace is unavailable |
| I1 Details count | Appropriate mode-conflict clarification: Details does not authorize changing a count request into records |
| I2 explicit status=offline | Displayed 2 matches SQL |
| I3 July 1–7 daily alerts | July 2, 3 and 5 each have one alert; displayed sparse buckets match. Missing days are not zero-filled by the existing algebra |
| I4 July site temperatures | All three averages match exactly, including decimal precision |
| I5 devices with no July alerts | d008 with the related count 1 matches SQL |
| I6 count and monthly fees by status | All counts and totals match SQL |
| I7 top three fees, submitted in Default | IDs/models/fees and tie order match. max_monthly_fee alias suggests aggregation but does not establish actual plan kind; do not fail solely for alias spelling |
| I8 twice in Default | unsupported followed by semantic_gap; exact question repeated but missing plans prevent precise pipeline attribution. The second explanation describes a capability limit, not a missing business definition |
| I8 Details variant | All 15 alerts, parent models, timestamps and NULL resolution match SQL; confirms this served result is available through Details |
| I9 devices and sites in Default | All eight identities/labels and supplementary count=1 match. Do not call it successful automatic rows selection without the plan |
| I10 leased-device fees | Appropriate refusal: no reviewed lease identity definition exists |

Important limits:

1. **July 7 has zero fixture alerts.** The correct-looking I3 rows cannot prove
   that the original plan included that entire final day. A distinguishing
   boundary fixture or actual bounds is needed; do not use this as new evidence
   closing time-boundary coverage.
2. **UTC presentation is not a wrong instant.** The Details timestamps have
   explicit +00:00 and match PostgreSQL instants. That differs from the local
   calendar buckets, whose source interpretation is not recoverable from the
   owner table alone. No automatic +8-hour rewrite was applied.
3. **The Details alert wording changed too.** It contains U+2801 between 型號
   and model, and omits the final full stop. Keep it verbatim; it is not a clean
   mode-only paired experiment, nor proof that the extra character caused success.
4. **Value matches are not full-service certification.** Original SQL/plan and
   disclosure were not supplied; no claims about hidden truncation, repair count,
   original context identity or complete semantics are inferred from pasted rows.

## Conclusions and next decisions

- The real consumer can deliver count/null/distinct, scoped absence, exact names,
  month/closure-time selection and bounded parent details on these cases. No
  answered Service case was observed to have a wrong value; no operational
  failure occurred. This is not an error-rate guarantee beyond this small bank.
- Two different problems remain separate: missing offered value meaning for
  natural-language offline status, and the proven Return gate false refusal.
  The first deserves a bounded assessment of existing reviewed value aliases or
  safe catalog-supported value metadata before any sampling/prompt change; the
  second must not be patched by another familiar-word exception.
- Default giving accurate aggregate-equivalent listing results does not close
  automatic routing. A mode capability limit should not be explained as missing
  business meaning; refusal reason quality is a distinct follow-up item.
- Preserve these questions as known regression/diagnostic material; do not relabel
  them unseen. The existing Return/minutes sentinel already covers that family.
  Mode-specific observations and exact-name contrasts are recorded with provenance;
  no duplicate permanent case set, new grading contract or production change is
  introduced in this intake slice.

Validation: ten actual Web/MCP invocations; eight independently checked Service
answer tables; eight retrospectively checked IoT answer tables; saved-plan gate
control and integrity/source-pin checks. No broad source suite was rerun for
documentation and ignored diagnostic scripts; no maintained runtime/test code
changed. Local commit only; Web remains running and no push was made.
