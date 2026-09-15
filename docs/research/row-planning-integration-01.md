# Joint row planning: integration acceptance rejected

2026-09-15. Fixed runtime `6942416` includes the temporal-guard reviewer fixes.
Decision: **do not promote this candidate**. Keep the useful details capability
open, the existing opt-in fallback unchanged and Web defaults off. No new public
strategy flag, router, vocabulary exception or production prompt was introduced.
Time binding and the guard correction are separate completed deliveries.

## Fixed test and evidence

Specification: `../plan/row-planning-integration.md`. Reuse 55 known synthetic
Service/IoT cases from `evals.planner_combination_study.load_panel()`: rows,
aggregates, without, missing definitions and temporal precision controls.
This is regression/integration acceptance, **not unseen-user generalization**.

Both arms call the shared `ask()` and readonly PostgreSQL execution pipeline.
The baseline enables the existing unsupported-only row fallback. The candidate
plans jointly using the current v17 row/order wire plus the previously measured
`query_kind_study.POLICY`, revision `plan-classify-json-v18-joint-row-order`.
No new policy wording, time hints or composition hints. Literal Unicode is
already present. This comparison measures the whole strategy change, not an
isolated attribution to a single sentence or model-inference mechanism.

Independent reference SQL and complete row/projection/order assessment precede
model calls. Temporal cases additionally use independently discriminating
boundary fixtures, so a coincidental match on the ordinary fixture is insufficient.
Freeze contexts, source/tests and probe inputs; rotate arm order per case and
call Gemma 4 31B serially, T=0, thinking off. Model inputs exclude DB rows,
reference SQL and credentials. All databases are synthetic, with readonly role
and no schema-value sampling. No customer DB, new provider or deployment.

Private artifacts: `.artifacts/row-integration-20260915/main/` and
`repeat/main/` contain manifests, immutable actual-call records and results.
Counts and content hashes: `../../evidence/row-planning-integration-01.json`.

## Primary results: 55 requests per arm

| Outcome | Existing fallback | Joint candidate |
|---|---:|---:|
| Correct answer | 27 | 34 |
| Wrong answer | 7 | 2 |
| Necessary refusal | 11 | 10 |
| Unnecessary refusal | 4 | 4 |
| Operational failure | 6 | 5 |
| Actual model calls | 68 | 62 |

The 13 expected-row cases improve from 7 to 12 correct answers. The remaining
row failure is the existing concept gate false refusal on `kind_minutes_records`.
Median request elapsed time is 2.435 versus 2.248 seconds; small known panel,
not a latency service-level claim. Baseline has seven fallback calls and six
repair turns; candidate has no fallback and seven repair turns.

Total answers are 34 versus 36: correct/all is 27/55 versus 34/55; observed
wrong/answered is 7/34 versus 2/36. Necessary refusals are not correct answers,
and failed requests are not successful safety refusals. Improved totals do not
override the predeclared no-new-unsupported-answer requirement.

## The three disqualifying regressions repeat

| Case | Existing fallback, both runs | Joint candidate, both runs |
|---|---|---|
| `cov_mttr` | Missing-definition semantic gap | AVG(alerts.downtime_minutes) labelled repair time, without a reviewed equivalence |
| `cov_leased_fee` | Missing-definition semantic gap | SUM(devices.monthly_fee) across all devices, no lease population |
| `svc_absent_feb_zh` | Correct teams without February work logs | Unnecessary semantic-gap refusal |

The repeat also retains three controls: original device details answer, leased
device details refusal, and the English supported without answer. All twelve
case/arm plan payloads match their first-run counterparts (including absent
plans for refusals); contexts and gold results match the frozen first run.
This establishes recurrence, not a batching explanation or an independence claim.
Repeat outcomes: baseline three correct/three necessary refusals; candidate two
correct/two wrong/one necessary refusal/one unnecessary refusal.

The first two failures select a valid computation with unsupported business
meaning; the compiler faithfully executes it. Listing assumptions does not
create the missing MTTR or lease definition. The third is a planning refusal on
a population the existing aggregate/without path can express. The comparison
does not prove which prompt token caused it. Leasing rows still refuse while
leasing SUM answers: definition handling is not reliable across query shapes.

130 primary + 13 repeat = **143/180 actual model attempts**, zero transport
failures, no frozen-input drift. The finite rejection condition was reached;
no additional prompt variations or deployment follow-up were run.

## Disposition and next product slice

Do not enable the joint candidate or claim natural-question serving acceptance.
This round exercised shared application/DB behavior, not a newly deployed Web
or a new HTTP/MCP natural-language run. The prior time-service acceptance stands.

Next review should separate two bounded decisions, rather than build a general
semantic certification system:

1. Can a caller-specified **details-only entry** deliver the existing safe row
   execution capability without changing aggregate planning? This is a proposed
   smaller product scope, not an implemented API or proof that row scope is safe.
   Specify its compatibility/visibility/refusal contract before any implementation;
   retain both leased-details and ordinary-details controls. It would not solve
   automatic natural-language routing by itself.
2. For automatic planning, use the repeated MTTR/lease counterexamples to test
   reviewed executable support definitions versus absent/withdrawn definitions
   across rows/COUNT/SUM. First inventory existing metadata experiments and reuse
   their evidence; do not repeat a renamed prompt study or add a word gate.

Independent conversion/component compiler integration may continue under the
board's own semantic and consumer acceptance; this candidate's rejection must
not block all other capabilities. There is no new production abstraction to clean
up: private acceptance adapters remain ignored, durable output is the decision
and its evidence. The corrected runtime retains its source-matched static gate
and **2,210 offline tests**; no duplicate full suite for documentation-only closeout.
