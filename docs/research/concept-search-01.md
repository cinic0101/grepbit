# Concept search: more candidates did not solve intent verification

2026-09-12. The owner requested a complete comparison and conclusions. Protocol:
`../plan/concept-search-experiment.md`. Completed 430/432 maximum main-study
Gemma calls; two selectors were skipped because all three offered candidates
were invalid. A separately announced eight-call post-hoc ranking probe brings
the total to 438. Repo source remained unchanged. No promotion or DB access.

## Executive conclusion

Single temperature-0 reasoning was the strongest tested extractor on the frozen
pilot: 28/30 exact intents, versus 22/30 without reasoning. Off-sample voting
added nothing; the tested Best-of-3 selector reduced exact labels to 16/30.
Reasoning sampling produced a gold-correct candidate for 29/30 questions, but
majority selected only 27/30. This is a selection gap, not proof that all future
Best-of-N methods fail. A full 30-question selector-on-reasoning-pool strategy
was not measured; a separately announced post-hoc ranking probe is below.

**None is ready to become a semantic certificate.** Single reasoning's 51/51
fixed-pair verdict match hides two wrong ambiguity interpretations. Post-run
counterexamples using the EXACT recorded intents produce five unjustified
acceptances, with no additional model call. The ruler/representation gap must
be addressed before treating benchmark scores as product reliability.

## What was measured

Gemma4 31B, 4,096 completion-token cap, 60-second per-call timeout, zero retries.
The 30 authored questions are 10 families x zh/en/ja, with 51 fixed pairs:
18 known-wrong plans, 24 correct controls (including 6 no-qualifier controls),
9 unresolved pairs. Same definitions, inputs, original prompt and existing
grader as the earlier pilot. Sampling temperature is 0.6; baselines/views/audits
are temperature 0. Prompts/configuration are versioned as concept-search-v1.

The pre-registered views emphasize population/subset or contrast/prohibition;
both preserve the original output schema. They were designed after seeing
the earlier failures, so their results are tuning evidence, NOT generalization.
The selector sees only the original question, definitions and shuffled unique
validated candidates, not frequencies, expected labels, plan or explanations.
Whole intent cores are voted on; validated span differences are ignored.
Errors remain in the N denominator; ties/all-invalid pools abstain.

The fixed seeded schedule interleaves arms within questions. This is one
experiment, not replicated sessions or a controlled backend-load study. The
configured model ID is the same; backend batching/configuration was not audited.
No SQL, rows, customer data, raw reasoning or provider error bodies were sent
or saved. Model input contains only synthetic questions, schema, definitions
and, for audits, synthetic plans or their bounded facts.

## Extraction and candidate choice

| Strategy | Exact intent / 30 | Correct controls allowed / 24 | Wrong allowed / 18 | Unresolved allowed / 9 | Added latency p50 / p95, seconds |
|---|---:|---:|---:|---:|---:|
| Single off/0 | 22 | 19 | 1 | 2 | 1.13 / 2.25 |
| Single on/0 | 28 | 24 | 0 | 0 | 15.31 / 51.93 |
| Off/0.6 x3 majority | 22 | 19 | 1 | 2 | 3.48 / 6.65 |
| On/0.6 x3 majority | 27 | 22 | 0 | 0 | 46.04 / 126.68 |
| Off/0.6 x3 + on/0 selector | 16 | 12 | 0 | 2 | 13.42 / 30.19 |
| Population-view off/0 | 22 | 18 | 0 | 1 | 1.20 / 2.35 |
| Contrast-view off/0 | 21 | 22 | 4 | 3 | 0.67 / 2.07 |
| Three-view majority | 22 | 19 | 1 | 2 | 3.17 / 6.53 |

Latency includes all calls, errors included. Multi-call rows sum the required
measured sequential calls per question; they are not deployed ask latency,
parallel-race latency, or a measured combined planner/validator pipeline.
Best-of-3 includes the selector when actually invoked. No-request allows passage
but is not verification. Unknown/error/abstention block hypothetical passage;
they are not all successful semantic refusals.

Unanimity did not provide an attractive tradeoff either: off 22/30 exact and
19/24 controls allowed, on 25/30 and 21/24, views 19/30 and 17/24. View unanimity
still allows one unresolved pair. Full per-case results remain in the artifact.

### Diversity versus selection

| Pool | Oracle availability N=1 / 2 / 3 | Questions with >1 valid core | Majority exact |
|---|---|---:|---:|
| Off/0.6 | 22 / 22 / 22 | 0 | 22 |
| On/0.6 | 26 / 29 / 29 | 4 | 27 |
| Three views | 22 / 23 / 24 | 5 | 22 |

These oracle numbers use gold AFTER generation and are upper bounds, not
deliverable answers. N order is the predeclared candidate index, not an online
early-stop sequence; execution order was shuffled.

- Off: the 28 questions with valid candidates have identical cores across all
  three calls; the other two have three schema-invalid responses. Six questions
  share the same valid WRONG core: return_amount_zh, all three member_share
  translations, service_refunds_zh/en. Raising temperature to 0.6 did not supply
  useful diversity here. This does not prove higher N/other settings never help.
- On: additional candidates fix member_share_zh, member_share_en and Japanese
  ambiguous return rate relative to sample index 0. The English member-share
  gain recovers a transport failure; the other two recover valid wrong labels.
  English return amount has no gold-correct candidate in the three-sample pool.
- Japanese ambiguous return rate has one correct ambiguous candidate and two
  incorrect required/numerator candidates. Majority chooses the wrong reading.
- The off selector never sees more than ONE distinct valid alternative: this
  arm measures acceptance/abstention, not actual reranking quality. It chooses
  a correct candidate in only 16 of the 22 questions
  where one is available. The other six are all no-qualifier controls (output
  verb and explicit unrestricted membership); it abstains. Its prompt does not
  explicitly explain the not_requested label, a plausible rubric-design issue,
  not a proven inherent inability of LLM selectors. Do not silently fix that
  prompt and present the same corpus as independent confirmation. Even an ideal
  selector on this OFF pool is capped at 22/30, below single on's 28/30.

### Post-hoc actual ranking and candidate-order probe

The original study was closed before this methodological follow-up was announced.
Off sampling provided no distinct alternatives, so an additional bounded probe
uses the four existing ON pools with >1 valid core, selected without looking at
gold. Each is offered in forward/reverse order to the UNCHANGED selector prompt:
8 extra calls, no generation, new questions, prompt retuning or new labels.

| Existing question | Forward order | Reverse order |
|---|---|---|
| Japanese ambiguous return rate | Wrong required/numerator | Correct ambiguous |
| Chinese ambiguous return rate | Correct ambiguous | Wrong required/numerator |
| Chinese member share | Correct member numerator | Correct member numerator |
| English member share | Correct member numerator | Correct member numerator |

Six of eight selections match gold. Both ambiguous-rate translations switch
answers when order is reversed and select c0 in BOTH orders. This is consistent
with a position preference, but one sequential forward/reverse pair does not
isolate order from endpoint/time variation. There are only TWO semantic families,
not eight independent examples. All four pools happen to contain a correct
candidate; this probe does not measure rejection of an all-wrong diverse pool.
It is not a full 30-question on-pool selection strategy or a new holdout.

All eight return valid outputs, with reasoning observed and no cap/transport
failure. Selector-only p50/p95 is 22.43/36.03 seconds; 12,998 reported tokens.
Repo source and original scores remain unchanged. The separate driver's hash,
input-report hash and results are recorded in evidence/concept-search-01.json;
raw artifact: .artifacts/concept-search-20260912/selector-probe.json.

## Direct plan audit: easier presentation was not safer

| Off/0 audit input | Wrong allowed / 18 | Unresolved allowed / 9 | Correct controls allowed / 24 | Exact verdict / 51 | p50 / p95, seconds |
|---|---:|---:|---:|---:|---:|
| Raw typed plan | 0 | 1 | 24 | 39 | 0.405 / 0.530 |
| Expanded predicate/operand facts | 0 | 3 | 24 | 40 | 0.410 / 0.615 |

The facts projection preserves the tested predicates, aggregate kinds,
groupings and ratio scopes, expands reviewed metric filters, and rejects
unsupported shapes locally. It does not interpret the question.

Raw audit allows the Chinese ambiguous return-rate question paired with a raw
return SUM. Facts audit allows this same unjustified interpretation in ALL
three languages. Its slightly higher exact-verdict count is therefore not a
safety improvement. On the nine unresolved pairs, raw gives 8 fail + 1 pass;
facts gives 6 fail + 3 pass. Neither gives the expected Unknown on any of them.
This cannot be reported as successful clarification.

## Selective reasoning: predeclared replay, not deployment

| Policy on the same 51 pair scenarios | On calls triggered | Total calls (replay) | Wrong / unresolved allowed | Correct controls allowed | p50 / p95, seconds | Reported tokens (replay) |
|---|---:|---:|---:|---:|---:|---:|
| Always single on | 51 | 51 | 0 / 0 | 24 | 15.57 / 51.93 | 86,659 |
| Off -> on on checker fail/unknown/error | 29 | 80 | 1 / 2 | 24 | 11.65 / 52.44 | 107,825 |
| Off + population view -> on on disagreement or checker failure | 32 | 134 | 0 / 1 | 24 | 17.07 / 53.04 | 169,998 |

All branches were actually collected, but the conditional sequence was not
executed as a deployed policy. Latencies sum the needed branch measurements;
the baseline is weighted to the SAME 51 scenarios, not the 30-question table.
Gold never determines triggering. These replay calls/tokens are NOT extra
requests to add to the actual experiment's 430 calls.

Checker-only routing misses a wrongly accepted inverted return plan in Chinese
and the unresolved Chinese/English service-refund questions. Disagreement routing
still misses English service refunds: both fast views erase the concept, so
neither triggers escalation. Fewer reasoning calls did not imply lower total
tokens or better p95 here. No replay policy overrides production gates.

## Why 51/51 still fails a counterexample check

Single on has all 51 original verdicts matching the frozen expected labels.
Its two intent errors are the English/Japanese ambiguous return-rate questions:
it emits required returns/include/numerator instead of ambiguous. The supplied
member-ratio and raw-SUM plans happen to hit the bounded checker's unknown paths.
That is not recognition of ambiguity.

After completing the frozen experiment, reuse those EXACT captured model outputs
with a plausible existing QueryPlan: count(return rows) / count(all rows).
The unchanged checker returns pass for BOTH languages. The unspecified count
versus amount interpretation was not resolved. No new LLM/DB call or code change
is needed to demonstrate the escape.

Likewise, reuse single on's three unrestricted-membership outputs with the
existing member_count plan, which filters member_id not NULL. All three return
not_applicable and bypass the check despite the explicit prohibition on filtering.

These are five post-run authored counterexamples, not an expansion of the 51
frozen scores or a holdout. Artifact: evidence/concept-search-counterexamples-01.json.
A four-row fictional arithmetic check shows why the differences matter: count
all=4 versus count members=2; return count ratio=0.5 versus return amount
ratio=30/230. No records from a database are involved.

Current-contract characterization tests also establish that the research Intent
cannot encode explicit unrestricted polarity, denominator role, or multiple
roles for one concept. **QueryPlan itself can express filtered/unfiltered queries.**
The missing representation is in the experiment's requirement/verifier interface,
which is not integrated into production. An LLM generating the correct current
label does not repair that blind spot.

## Cost, provenance and validation

- Main: 430 actual calls: 300 extractors, 28 selectors, 102 audits. 416 valid outputs,
  11 schema-validation failures, 3 transport failures at about the 60-second cap.
  Failures are retained; no automatic retries. No observed length stops.
- 148 calls requested reasoning; all 145 returned responses expose nonempty
  reasoning_content. Only character counts are retained. The three failed
  requests have no returned reasoning/usage observation; absence is not zero.
- Provider-reported tokens: 415,300 prompt + 89,834 completion = 505,134 total.
  Failed-request usage is unavailable, so this is not complete billable usage.
- Including the separate ranking probe: 438 actual calls, 424 valid outputs,
  the same 11 schema and 3 transport failures, and 518,132 reported tokens.
- Calls span 03:41:38 to 04:30:10 UTC, about 49 minutes. Their measured durations
  sum to 2,909.54 seconds. No backend-load/cancellation guarantees after timeout.
- Focused: 66 passed. Full offline: 509 passed, no skips/errors/failures. Static
  passed. All match the live repo-source digest; repo code did not change after
  validation. The standalone ignored post-hoc driver has its own recorded hash
  and passed ruff/dry-run preflight; it is not covered by the 509-test suite.
- Source digest: sha256:1a0f0052c4500f368079a3eeb647f00a6e6617bf2db0b869fea2c71ada071ce7.
  Inputs hash is unchanged from the prior reasoning pilot. Source delta from
  that run: concept_pilot.py (optional temperature, default unchanged), new
  concept_search.py and its instrument/characterization test file, nothing in src/.
- Artifacts: .artifacts/concept-search-20260912/live.json and live.jsonl, plus
  focused/static/offline directories. Durable summary: evidence/concept-search-01.json.
  HEAD remains 746f168 with earlier dirty work preserved. No stage/commit/push.

## Next test stages and decision

1. **Complete:** frozen-ruler comparison and post-run counterexamples. Retain
   single reasoning as the strongest measured research baseline; do not promote
   any candidate or increase N automatically.
2. **Next ruler checkpoint:** define minimal explicit no-restriction/scope and
   ambiguity obligations, with counterexamples for plausible alternative plans.
   Preserve requests whose definitions are unavailable. Do not create a universal
   semantic IR or silently rewrite old scores. The owner reviews this material
   evaluation-contract change before implementation. A clarified selector rubric
   is another separately versioned experiment, not a result claimed here.
3. **After the contract decision:** compare the repaired baseline off/on on new
   families with fixed labels; a proposed budget is 40 families x 3 languages,
   split by entire families before outputs (e.g. 24 development, 16 held out).
   Independently adjudicate labels; do not tune on the held-out families. These
   remain synthetic validation, not real-user generalization. Repeat time-separated
   runs before claiming stability. No such expansion was executed in this slice.
4. **Product-level test:** unseen real user questions through planner AND verifier,
   reviewed answer oracles, joint planner/verifier misses, correct clarification,
   wrong accepted answers at agreed answer coverage, and end-to-end p50/p95.
   Real-data privacy/opaque-read-only boundaries still apply. Owner-agreed risk
   and usefulness criteria must precede a release decision; 30 authored questions
   cannot estimate the product's failure probability.

More inference can help, but agreement, a correct candidate somewhere in a pool,
and a narrow checker pass are three different claims. This experiment supplies
concrete failures for each distinction; it does not solve natural-language
intent reliability or justify production integration.
