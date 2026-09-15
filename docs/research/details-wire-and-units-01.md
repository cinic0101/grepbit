# Details-only shown schema: wire gain, adoption held on ordering

2026-09-15. Baseline `6b38aa0`; fixed protocol:
[`details-wire-and-units`](../plan/details-wire-and-units.md).
Decision: do not promote this candidate under the frozen acceptance criteria.
Do not start another prompt arm. Existing runtime and construct freeze remain
unchanged. This is NOT evidence that the narrower schema causes wrong numbers:
the only new result mismatch is an unspecified sort direction. Its product/oracle
policy needs resolution before an adoption claim, not another prompt tweak.

## What was tested

One private candidate, `details-schema-only-v21-study`, changes only explicit
`query_kind=rows` shown schema: plan keeps base_table, rows, filters, order, limit;
plan requires base_table/rows and the top-level decision branches require plan or
reason respectively. Existing complete refusal options and field shapes remain.
Rules, examples, canonical wire, normalizer, `extra=forbid`, JSON mode and gate
are unchanged. Default/fallback is not keyed off allow_rows and is untouched.

45 known diagnostic cases, two predeclared paired rounds, serial baseline45 /
candidate45 / baseline45 / candidate45. Actual `gemma-4-31b`, T=0, thinking off;
180 initial requests and **180 native completion calls**, within the 240 cap.
SDK retries zero; repairs, application retries and fallback were counted at the
native boundary and all were zero. No extra selective repeat or adoption smoke.

Execution used the production registry/request factory, shared ask, grounding,
compiler, SQL policy and readonly PostgreSQL fixture databases. This is **not a
new HTTP/MCP/Web transport run**. Source, tests, probe and protocol fingerprints
were constant across all 180 requests. Only synthetic schema, questions and
reviewed metadata reached the existing LAN model. Sampling zero, grepbit_ro,
opaque credentials; no database data/schema/grant mutation or new provider.

The exact questions, reference SQL/results, candidate source hashes, raw requests,
raw completions and original grades are retained in
`.artifacts/details-wire-20260915/live/`. The fixed panel includes 32 historical
Details, four recent Details, and nine Default controls. Repeats and familiar
questions are not independent holdout/generalization observations.

## Wire result: real improvement, without hiding refusals

Both rounds have exactly these counts; do not pool their denominators:

| Stratum per round | Baseline variants | Candidate variants | Plans produced in either arm |
|---|---:|---:|---:|
| Historical Details (32 requests) | 8/32 (25%) | 1/32 (3.125%) | 21 |
| Recent Details (4 requests) | 2/4 (50%) | 0/4 | 3 |
| Default (9 requests; not in Details gate) | 0/9 | 0/9 | 6 |

Plan-produced denominators separately: historical 8/21 -> 1/21; recent 2/3 ->
0/3. Datasource Details strata: IoT 6/21 -> 1/21 (14 plans), Service 4/15 ->
0/15 (10 plans). Raw shown-schema departures are exactly the same cases, all
extra duplicate `plan.columns`; normalization entries equal variant case counts.
Candidate's remaining case is `parent_top_fees`. This is still a shape variant,
not meaning normalization. Production continues to use the baseline prompt.

All 18 paired Default native request bodies are exactly equal. Each round has
the same statuses/reason codes in both arms; necessary refusals remain 16 and
false refusal remains S8 alone. S7/S8 still produce the same correct rows plan,
preserving repeated minutes, NULL and ascending id. S8 is still blocked by
`concept_not_mapped`, not newly refused by the planner. Non-PK parent projection
still reaches the compiler's typed refusal despite losing its redundant columns.

Native completion p50: baseline 2.404/2.467s, candidate 2.182/2.211s by round.
Shared ask p50: 2.464/2.527s vs 2.271/2.295s. No repair-call savings: baseline
already normalizes without a second call. These sequential small-panel timings
are descriptive, not controlled latency or general reliability guarantees.

## Value/oracle review, with original grades preserved

| Outcome per round | Baseline | Candidate |
|---|---:|---:|
| Correct answers after existing-contract label correction | 27 | 26 |
| Appropriate refusal status/reason within frozen allowances | 16 | 16 |
| False refusal (S8) | 1 | 1 |
| Confirmed wrong business population | 1 | 1 |
| Frozen ascending-order mismatch, direction unspecified in question | 0 | 1 |
| Operational failures | 0 | 0 |

Original automated totals were 26/25 correct and 2/3 wrong respectively; no
original files or historical scores were overwritten. Post-live accounting is
`.artifacts/details-wire-20260915/analysis.json` and `summarize.py`.

1. `recent_I12` was an oracle label wiring mistake in all four arms. Reference
   names used `model`, but the established parent-projection contract requires
   `devices.model`. All 15 ordered rows, NULLs and other columns match exactly;
   the typed plan has the intended four projections and ascending alert_id.
   Only this existing-contract mismatch is corrected to correct_answer. No
   broader alias relaxation or frozen-input edit was made during measurement.
2. `parent_worklog_status`: baseline returns ids 1..10; candidate returns 10..1,
   in both rounds, with otherwise exactly reversed identical complete records.
   The original question says `按 work_logs.id 排序`, not ascending. The frozen
   reference says ASC. Keep this as an acceptance mismatch; it is not a wrong
   number or demonstrated violation of an explicit user direction. Nor is it
   retrospectively counted correct to promote a favorable candidate. Decide
   whether unspecified direction is a product ASC default or an allowed,
   disclosed choice, then define the corresponding prospective controls. A
   narrowly allowed choice would cover complete, untruncated listings only, with
   no ranking/top-N/membership-selecting limit or implied direction; it must not
   excuse reversal that changes the selected records.
3. `default_cov_leased_fee`, `租賃裝置的月費總額`, answers 3100.00 by summing all
   devices without lease identity in **both baseline and candidate, both rounds**.
   This is a genuine necessary-population omission. The fuller recent_I9 question
   still gets semantic_gap. Current baseline is therefore wording-sensitive;
   neither new rows schema nor status aliases alone are established as cause.
   Historical no-overlay refusal and recent overlay-panel successes had different
   contexts/questions; do not infer endpoint shift or overlay causality from them.

Refusal reason codes conform to the frozen allowances, not a new certification
that every explanation is precise. For example Default MTTR still mentions lack
of duration computation; it does not establish a reviewed MTTR definition.
No gateway self-judgment was used to grade plans or the original question.

## Conversion preparation delivered independently

Added 16 controls to the **existing isolated research** contract suite: inverse
temperature goldens, duration bidirectionality, NULL/identity, AVG/MIN/MAX
population and unchanged second output, duration SUM/AVG/MIN/MAX, and exclusion
of delta unit representations. Reviewed source binding wins over a misleading
column name. All 65 focused research tests pass. Delta representation rejection
does not claim natural-language temperature-difference detection.

An additional outer-expression mutant changes Celsius-to-Fahrenheit coefficient
9 to 5. Original fixture result 116 becomes 78.66666666666666 in DuckDB, while
both SQL statements pass the current SQL safety policy. This illustrates the
integration requirement: check final conversion semantics independently, not
only safe SQL or the inner query. It is not a production conversion bug; this
capability is still research-only. Evidence: `unit-outer-mutant.json`, zero model
calls. No Pint/dependency, production unit API or reviewed overlay schema added.

## Exit and next decision

- Stop this candidate's implementation work; private prototype remains replay
  evidence, not a new production module. Existing Web needs no restart for this
  slice: no runtime/config/assets changed. Do not deploy the candidate.
- Resolve the **ordering evaluation/product default**, not another schema/prompt
  hypothesis. Wire rate itself passed this fixed panel's gate. Until disposition,
  maintain the existing freeze and name conversion/independent aggregates as
  deferred; do not conflate policy gating with a technical conversion dependency.
- Keep lease omission open as a distinct baseline semantic finding. Any next
  diagnostic must distinguish information supply from selection and use the exact
  short/full wording pair; no emergency vocabulary exception or overlay rollback.
- Once adoption/freeze is settled, conversion needs the proposed public rulers,
  reviewed source/target/version disclosure, final-expression mutations and shared
  service acceptance. Existing unit research need not be reinvented.

Validation: 18 private candidate-boundary tests, 65 research focused tests,
2,351 offline tests (zero skips) and static pass. Focused and offline counts
overlap; they are not summed. Final source matches the live/focused fingerprint;
only documentation/evidence were added afterward. Validation and local Git closeout are recorded in
[`evidence/details-wire-and-units-01.json`](../../evidence/details-wire-and-units-01.json).
No push, deployment, global freeze clearance or blanket correctness claim.
