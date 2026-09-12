# Reasoning helps the concept pilot, with substantial latency and remaining errors

2026-09-12. Owner request: "試試開啟 reasoning". Authority and bounded setup:
`../plan/concept-reasoning-ablation.md`. No production policy change or promotion.

## Matched experiment

Reuse `concept-shadow-v1`, the 30 authored questions, 51 fixed question/plan
pairs, definitions, labels, C independent-extractor prompt, D direct-audit prompt
and structural checker. Run one off block, then one on block on Gemma4 31B.
Both use temperature 0, 4,096 maximum completion tokens, 60-second timeout and
no retries: 81 calls each, 162 in this slice. No DB access or rows/SQL sent.

The earlier 768-token/20-second baseline is historical, not the primary control:
reasoning must have room to finish. Both contemporaneous blocks have the same
source digest, input hashes and all 81 corresponding **message** hashes. Only
`chat_template_kwargs.enable_thinking` differs in the requests. Internal chat
template tokens may differ: provider prompt-token totals differ by 162 (2/call).
Both runs confirm unchanged source during execution. This is a sequential block
comparison, not a randomized or load-controlled study; no stability claim.

Activation is observed: all 81 on responses contain nonempty reasoning_content,
versus none of the off responses. Only character counts are retained, not the
reasoning text. Neither mode has transport failures or length/cap stops. The
provider does not return separate reasoning-token counts; absence is not zero.

## Results

C is independent intent extraction plus the unchanged deterministic checker.
D is direct LLM qualifier-only auditing. Counts are paired-plan observations,
not independent user questions. An error/Unknown blocks hypothetical passage;
not_applicable allows passage but is not a certificate of correctness.

| Measure | Off | On |
|---|---:|---:|
| C exact intent/polarity/role labels | 22/30 | 26/30 |
| C known wrong pairs allowed | 1/18 | 0/18 |
| C unresolved pairs allowed | 2/9 | 0/9 |
| C correct controls blocked/error/Unknown | 5/24 | 3/24 |
| D known wrong pairs allowed | 0/18 | 0/18 |
| D unresolved pairs allowed | 1/9 | 0/9 |
| D correct controls blocked/error/Unknown | 0/24 | 0/24 |
| C output-validation errors | 2/30 | 1/30 |
| D output-validation errors | 0/51 | 0/51 |

A/B/oracle controls remain unchanged. Oracle-input checks still match all fixed
expectations; this says nothing about the correctness of a model's premise.

### What improved and what did not

Five question-level C labels improve: Chinese/Japanese return amount, Chinese
member share, and Chinese/English service refund amount. One regresses: Japanese
ambiguous return rate. These translations do not represent five independent
business intents.

- Both service refund misses are repaired: unavailable bindings no longer mean
  no requested refund concept. The checker correctly returns binding_unavailable.
- English and Japanese member-share questions still acquire an extra return-only
  population requirement from "including returns". Their correct ratio is Unknown
  to the checker. Chinese is now correct; do not generalize that to all languages.
- English return amount changes from not_requested to a schema-validation error.
  That removes its wrong-plan escape, **not** by correctly understanding the
  question. This failure cannot be counted as a successful semantic refusal.
- Japanese return rate changes from ambiguous to a chosen return numerator, even
  though the count/amount interpretation is unspecified. The checker still
  returns Unknown on the supplied plans; a safe outcome masks an extraction error.
- D no longer passes the Chinese ambiguous rate with a raw return SUM. It returns
  fail, not the expected Unknown. Across the nine unresolved pairs, on gives two
  Unknown and seven fail; off gives eight fail and one pass. Zero escapes is not
  the same as correct ambiguity classification or a good clarification question.

## Cost

Latency below includes all calls, including output-validation errors. Reports'
existing successful_call_latency excludes those errors; these are deliberately
distinguished rather than mixed. There are no transport errors in this study.

| Added call latency | Off p50 / p95 | On p50 / p95 |
|---|---:|---:|
| C independent intent | 1.114 / 2.156 s | 15.148 / 40.429 s |
| D direct audit | 0.403 / 0.497 s | 8.189 / 24.829 s |

Median C is about 13.6x slower; D about 20.3x. Some reasoning calls exceed the
previous 20-second per-call cap. These are extra validation calls, not complete
ask latency or a measured combined planner-plus-auditor path.

Provider-reported completion tokens rise from 1,317 to 37,364 (about 28.4x).
Total tokens rise from 78,444 to 114,329 (about 1.46x); prompt tokens dominate
the off baseline. Do not invent a separate reasoning-token count from these
totals. Off starts at 02:48:05 UTC and on at 02:48:54 UTC; on's last call starts
at 03:07:00 UTC. The endpoint's batching/cache/load state was not controlled.

## Decision

Reasoning **does help this concept-validation task**, unlike the earlier planner
experiment's measured lack of answer gains. That earlier result must not be
generalized to every use of this model. It is also not a cure for semantic
ambiguity: errors remain and one intent interpretation regresses.

Retain reasoning-on as an offline/shadow research option, default off. Do not
enable an additional reasoning call for every production question, replace the
existing deterministic gates, or call this a generalization pass. This one
authored, sequential on/off pair does not establish reliability on unseen data.
A later study could measure D-on on independently adjudicated questions or a
bounded escalation policy, but neither is implemented or validated here. In
particular, a trigger based only on existing lexical checks may miss exactly
the concepts being dropped; selective reasoning needs its own measured trigger.

## Validation and evidence

Only `evals/concept_pilot.py` and its instrument tests change in executable
source. Optional thinking/token/timeout flags keep old defaults. Tests cover
switch transmission, bounded driver settings, reasoning-text non-persistence,
finish-reason observation and the existing error/circuit-breaker paths.
No prompt, label, fixture, checker or runtime src change.

- Focused instrument: 45 passed.
- Full offline: 488 passed; no errors/failures/skips.
- Static: ruff check, format check and diff whitespace check pass.
- Artifacts: `.artifacts/concept-reasoning-20260912/{off,on}.json` with incremental
  `.jsonl` call journals; focused/static/offline verify directories beside them.
- Durable manifest: `evidence/concept-reasoning-01.json` with source/report hashes,
  counts, token totals and both all-call and successful-call latency evidence.

All own runs ended. Existing dirty work is preserved at HEAD 746f168, no staging,
commit, push, packages, persistent DB writes or credential copies. Credentials
were sourced opaquely from the existing ignored environment. Reported results
do not include reasoning text, provider error bodies, secrets or endpoint URLs.
