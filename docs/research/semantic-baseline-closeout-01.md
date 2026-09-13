# Semantic baseline closeout: allowed readings versus wrong windows

2026-09-13. Baseline `5639af1`, unchanged ask v5 / grounding v2 /
`plan-classify-json-v15`. Protocol: `../plan/semantic-baseline-closeout.md`.
Fresh private artifacts: `.artifacts/semantic-baseline-closeout-20260913/`;
durable counts/hashes: `../../evidence/semantic-baseline-closeout-01.json`.
No production, prompt, overlay, acceptance-contract or persistent DB change.

## Measurement

Nine scheduled executions completed in nine Gemma4 31B attempts, serial,
T=0/thinking off; no model transport errors, retries or validation repair.
The seven primary executions are existing POS engineer, no-sampling engineer,
English/Japanese engineer, IoT daily alerts and two feature cases. Two further
payroll executions were scheduled before any response. This is not a new
holdout, independent session sample or product-wide success rate.

All independent SQL and allowed interpretations were frozen before proposals,
using unchanged `disclosed-answer-v1`. English/Japanese annotations inherit the
same two approved engineer populations through the existing `base_case`.
Legacy grades and previous panel outputs remain unchanged.

| Evidence | Result |
|---|---|
| Seven primary, disclosed-answer policy | Six accepted; payroll unassessed |
| Two later payroll repetitions | Both unassessed, same final plan/scope hashes |
| Nine executions, legacy references | Four pass, five mismatch |
| Allowed engineer readings | English includes senior engineers; Chinese/Japanese use exact engineers; all match their frozen full-value oracle and disclosure |
| Inclusive daily date range | Accepted, despite legacy mismatch |
| Monthly comparison | Accepted descending period values without growth |

There is no planner-improvement claim from accepting an already permitted
reading. The remaining payroll problem is **not** explained by choosing
payment versus attribution date.

## Payroll: an unresolved hash became a concrete scope error

1. Offline enumeration of 601,156 forward date-only ranges in the fictional
   2024–2027 calendar did not recover the prior scope. That result is retained.
2. All three new payroll executions match the previous unknown scope hash
   `61c2518dab9189798075bb67ef679de7e9b36b790b9befa1d553cfdf15a8fb13`
   and the previous final-plan hash. Safe in-memory diagnostics establish a
   start at the requested year boundary and an end after that year.
3. A separately labeled post-observation enumeration of 27,757 fixed-start
   dates through 2100 recovers an exact scope hash: 2025-01-01 to **2060-01-01**.
4. The compiler's existing future-range rule clamps this to the end of the
   as_of day, February 10, 2026. It does not recover the requested year.
   A minimal same-scope paid-at/base-salary replay agrees with independent
   PostgreSQL SQL using that effective boundary: five quarterly rows, versus
   four for either permitted calendar-2025 date basis; both value comparisons
   differ. The actual three captured results also contain five untruncated rows.

The minimal replay does not match the entire recorded plan hash; do not call
it bitwise full-plan recovery. Scope identity, the three recorded five-row
results and the independent mechanism replay are separate evidence. We have
localized the wrong window and shown why clamping is insufficient, **not**
identified the precise generation/normalization step or proved an endpoint
batching cause. Automatic grades remain `unassessed/unlisted_interpretation`;
the separate diagnosis identifies a violation of the explicit calendar year.
Disclosure cannot make an extra quarter satisfy that question.

Next investigate time-window construction with this exact historical control,
not another payroll date-role metadata trial. Any proposed server-owned
calendar reference or new rejection rule must first get its own experiment
and compatibility ruler; no silent replacement of the current clamp contract.

## Actual product registry audit

Used the real `bind_datasource` path with original opaque DSNs and `grepbit_ro`,
not a manually assembled approximation. No model requests were made by this
audit, and no indexed values were persisted.

| Registration | Sampling | Groundable/indexed columns | Index values |
|---|---:|---:|---:|
| pos_real | 0 | 5 / 5 | 755 |
| pos_test | 20, fictional fixture | 0 / 0 | 0 |
| iot_spike | 20, fictional fixture | 0 / 0 | 0 |
| retail_spike | 20, fictional fixture | 0 / 0 | 0 |

Real POS indexes reviewed public category, payment method, product, store and
transfer-status columns; none skipped. The two specifically prohibited PII
columns are not groundable. This checks policy/configuration, not a general
audit of every potential PII value or live MCP deployment readiness.

POS-test has an overlay but **no groundable column policies**. The no-sampling
regression has neither overlay nor index. These intentional configurations
cannot be counted as failure of a loaded real-POS name index. The service
research datasource is not yet among these four product registrations.
No registration/policy was changed. Existing no-policy/missing/ambiguous/
negative binding contracts remain green; policy expansion needs explicit review.

## Next authored panel: prepared, not yet measured live

`challenge-panel-v2.json`: 24 new authored questions, four families of six:
required population, component-versus-row exclusion, imperative/business return
and name boundaries. Eighteen semantic cases include Chinese/English/Japanese
variants; six name cases cover exact names, negation, absence and collisions.
Twenty-one are answerable and three require clarification under the existing
name policy. There are no real private values or persistent DB setup.

Independent SQL versus compiled plans agrees in 63 case-instance checks over
three fictional instances. Every answerable case differs from its specified
wrong alternative. Eighteen additional return-family comparisons distinguish
row count from distinct-entity count; six resolver controls have the expected
kind. Initial fixtures accidentally let returned rows equal distinct entities;
v2 fixes that witness **before any challenge model call**, retaining v1 outputs.
This is oracle readiness, not 24 successful ask executions.

The new questions intentionally state their scopes explicitly; several expose
field/value spellings. They are sensitivity controls, not a realistic estimate
of ambiguous-user performance, and translations lack independent blind review.
Future experiments must pair them with existing implicit/absent-definition
regressions and obtain actual unseen user questions separately. Do not tune on
this panel and later call it a holdout.

## Validation, limitations and next order

- 147 focused tests pass, including private measurement controls and existing
  acceptance/name contracts. Static gate passes. Reuse prior 1,796 offline
  tests only after checking its artifact hash and exact tracked-source digest;
  no duplicate full-suite run for this docs/evidence-only change.
- All 38 interpretation alternatives are PostgreSQL-checked before calls and
  their reference values checked afterward. Four registry schema/settings
  contexts and tracked runtime source match at end. These are endpoint checks,
  not one shared DB snapshot or proof that every row remained unchanged.
- Owned model clients close per invocation, including repair; sanitized metrics
  are persisted before any raw response can reach a report. Local helpers stay
  private; counts/hashes and conclusions are durable. No push.

Next: (1) add the recovered payroll window to temporal construction research;
(2) freeze a bounded baseline/neutral/targeted semantic-metadata experiment,
using these explicit controls plus the existing implicit/regression families;
first check for a baseline ceiling, stop without promotion if neutral ties or
wrong-valid/necessary-refusal controls regress; (3) independently qualify A5
coverage, then A4 only when full-schema measurements justify it. Product
registration/PII hardening remains separate from language-model accuracy.
