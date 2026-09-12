# Concept obligations v2: approved implementation and off/on study

Status: COMPLETE, 2026-09-12. Research implementation validated; neither
extractor configuration is promoted. All 144 main + 18 shadow calls ended.
Protocol: `../plan/concept-obligations-v2.md`. The owner explicitly approved
the interface checkpoint with "同意，依此繼續". This is a research-only slice.

## Implemented and validated

- Reference COUNT now counts present values. Bare COUNT supplies a non-NULL
  sentinel per row, so COUNT(*) retains its established behavior. Empty,
  all-NULL and mixed inputs, raw/ratio/reviewed-metric forms have hand-value tests.
- Schema-driven and property generators now include COUNT(column), including
  nullable columns and key columns. Generated plan records contain 63 such
  occurrences in IoT and 70 in service (occurrences, not distinct executed cases).
- `evals/concept_obligations.py` implements the approved separate v2 payload
  and bounded checker. It preserves explicit unrestricted operand scopes,
  prohibited groupings and partial unresolved intent. Metric predicates and
  implicit COUNT null exclusion are checked. Unsupported shapes/bindings are
  unknown. No source under src/ changed in this slice.
- `evals/concept_obligations_pilot.py` keeps generation independent of labels
  and fixed plans. The new plan fixture is data; the old v1 inputs and checker
  are untouched. The independent test-only checkpoint schema is retained.
- 99 fixed question/plan pairs pass with gold obligations. This establishes
  the checker on these supported inputs, not NL understanding. Schema/transport
  failures are not converted into passes or removed from denominators.
- Focused implementation tests: 130 pass. Static and full offline: 735 pass.
  Additional property stress: max_examples=10000, 1 test passed in 37.46 s;
  Hypothesis seed was not explicitly fixed, so this is a stress observation,
  not a seed-replay artifact or 10,000 distinct plans.
- PostgreSQL inline VALUES goldens: 24/24 pass as grepbit_ro, no table reads.
  Random DuckDB differential, 500 requested examples / three instances each:
  IoT 376 valid plans, 88 typed refusals, 864 agreements; service 361 valid
  plans, 98 typed refusals, 789 agreements. Total 1,653 comparisons, zero
  disagreements/errors. DB access was schema-only with sampling disabled.
  An initial IoT invocation stopped at a nonexistent overlay path before
  generating plans; the corrected invocation uses the fixture without overlay.

## Frozen live protocol

Research prompt revision: concept-obligations-extract-v2-01. Twelve authored
families x three languages x off/on x two rounds = 144 calls. Both arms have
temperature 0, 4096 max output tokens, 60-second timeout, no retries. The same
seeded 72-call order repeats in round two, separating each case/configuration
by one whole block of other requests; no deliberate backend-load intervention.
The existing gateway receives synthetic questions, schema and definitions only.
There are no SQL, rows, labels, expected plans or persuasive planner explanations
in the extractor request. Only reasoning character counts, never text, are kept.

Source digest: sha256:aa1a6ce8a46ce7739bebe9dfe375e270c855e4f788160b06e7bfe7ab26017521.
Input hash: 34e6ccd3a0c3c35869abc64726ebfd51218c3e48d3db80eb4b4a8763308578b5.
Journal: `.artifacts/concept-obligations-v2-impl-20260912/live.jsonl`;
final report: the sibling `live.json`. Both source snapshots match. The
following paragraphs preserve the supplementary hypotheses registered during
the run; completed results follow below.

Supplementary diagnostic planned during the run (after observing transport/schema
status only, before reviewing extracted intents): replay captured ambiguous-rate
obligations against plausible raw return-SUM and return-COUNT plans as well as
the fixed ratios. A ratio-only bank could otherwise hide a wrong population-role
extraction behind an incidental unsupported-shape unknown. No extra model call,
no main-score change; report this separately as a targeted cross-plan diagnostic,
not a newly independent holdout or full-answer oracle.

## Interpretation boundaries

After inspecting round one, an additional targeted hypothesis is registered:
both arms interpret the Chinese output verb in 回傳交易筆數 as a return-row
restriction. The main family pairs this question only with count_all, which
exposes false blocking but cannot measure acceptance of a matching wrong return
plan. Reuse those exact outputs with return-SUM/COUNT after the frozen run.

Then, at most 18 additional serial gateway calls: the three ORIGINAL output-verb
questions x two rounds x (one existing v15 planner call + fresh off/on v2
extractions). Use the same fictional schema/overlay, 4096-token bounds, planner
20-second timeout / verifier 60 seconds, no repair turns or retries. The planner
and extractor never see each other's output; neither sees rows, SQL or gold.
Compile valid plans and compare locally on the two existing hand-counted
instances (all-transaction totals 4 and 5), plus a third hand-counted three-row
instance with NULL amounts so count(amount) cannot accidentally look like
count(*). Keep proposed-plan, compiler/value
and supplied-obligation verdicts separate. This tests the actual planner
adapter with a research verifier in shadow, not the whole ask/grounding stack
or a release gate. Record provider timing/usage but not raw reasoning/errors.
Stop on three consecutive transport failures. Same authorized Gemma destination
and opaque credential; no DB calls, no new provider or persistent data changes.
This post-hoc probe is NOT merged into the 144 calls or 99-pair scores. It is
motivated by an observed error, not an independent generalization measurement.

During the frozen run, a separate authored structural probe found a ratio
wrapper carrying its own filters is accepted by the existing domain, ignored
by compiled SQL, and passed by v2. This shape is absent from the 99 main pairs.
Evidence: `evidence/concept-obligations-v2-wrapper-filter.json`. Do not choose
whether it means numerator-only or both operands. After the live freeze, the
research checker now returns unknown under its ALREADY approved unsupported-shape
rule. Its regression passes; the complete original analysis and all 99 gold-input
oracle pairs replay identically. Production behavior is outside this slice and
remains an explicitly reported gap, not silently repaired or certified here.

Exact-core match is strict agreement with authored obligations, not necessarily
semantic equivalence of every reasonable ambiguity description. Report verdicts
and harmful escapes separately; do not retune labels after seeing model outputs.
Conversely, a matching fixed-pair verdict can conceal a missing obligation.

The pair labels concern qualifier/grouping obligations only. In particular,
count-distinct(member_id) passes the member-population obligation but is a wrong
answer to a transaction-count question. The hand fixtures distinguish it from
COUNT(member_id). Neither pass nor not_applicable is a full-answer certificate.
Their union is the experiment's explicit hypothetical no-block policy, not a
new production authorization rule. This run cannot measure end-to-end product
risk or latency because the planner is not in the loop.

The bank is author-proposed development data; translations and repeat calls
are correlated. This is not a new blind real-user holdout and the results must
not be pooled with the old 438-call v1 experiment. The schema/definition interface
also differs from v1, so historical score changes are not a matched causal test.
No production promotion, commit or push is authorized by a clean diagnostic run.

## Completed main measurement

Each row below is per round; both rounds have identical counts, not 72
independent questions per arm. Main prompt and inputs were not tuned mid-run.

| Metric | Thinking off | Thinking on |
|---|---:|---:|
| Strict obligation-core match | 27/36 | 20/36 |
| Fixed-pair exact verdict | 93/99 | 76/99 |
| Correct qualifier/grouping controls not blocked | 30/33 | 24/33 |
| Known qualifier violations allowed | 0/48 | 0/48 |
| Unresolved or unbound fixed pairs allowed | 0/18 | 0/18 |
| Valid structured responses | 35/36 | 34/36 |
| Schema failures | 1 | 0 |
| Transport failures | 0 | 2 |
| p50 / p95, all 72 attempts across both rounds | 1.93 / 4.14 s | 24.10 / 60.00 s |

Off has 97,496 reported total tokens; on 142,983, with usage unavailable on
four transport failures. Failures occurred at the 60-second boundary; raw
provider errors were not retained, so do not infer their server-side cause.
Off's Japanese unrestricted-and-ungrouped case fails schema validation with
value_error in both rounds; invalid content was not retained or rescored.
Successful on responses have nonempty reasoning character counts; off has none.

All 35 off and 34 on valid repeat pairs have identical cores; all 36 statuses
per arm repeat. This is an observation in one serial shared-endpoint run, not
evidence of a particular backend batching mechanism or statistical independence.
No Best-of-N experiment was added to this v2 study.

Some strict-core mismatches remain conservative partial ambiguity descriptions,
not wrong answers: e.g. retaining measure_basis but omitting the separate
denominator_population entry. Conversely, on invents measure_basis ambiguity
for several explicit transaction-count requests. Exact-core agreement alone
is therefore not the acceptance decision.

## Supplemental counterexamples and actual planner shadow

Zero-call replay adds 72 comparisons against raw return COUNT/SUM. For the two
ambiguous families, off stays unknown in 24/24 comparisons; on stays unknown
in 20, with four comparisons inheriting the two failed extractions. No ambiguous
raw plan passes. This addresses the earlier ratio-only-bank blind spot without
claiming new independent model observations.

For output-verb controls, both arms pass the wrong return COUNT/SUM for Chinese
in both rounds (four passes per arm). Off also returns not_applicable for the
Japanese wrong plans, correctly showing that empty obligations cannot certify
a whole answer. These are supplementary full-answer counterexamples, NOT
changes to the main qualifier labels.

The separate 18-call shadow then confirms a real joint failure, rather than
only a hypothetical pairing. Existing plan-classify-json-v15 adapter, no repair
turns, three original questions, two rounds; all calls succeed and source is
stable. Both extractors are fresh independent requests, blind to the plan.

| Question language | Planner, both rounds | Off verifier | On verifier |
|---|---|---|---|
| Chinese: 回傳交易筆數。 | chooses reviewed return_count; wrong | pass | pass |
| English: Return the transaction count. | unfiltered COUNT; correct | unknown | unknown |
| Japanese: 取引件数を返してください。 | unfiltered COUNT; correct | not_applicable | unknown |

Three fictional instances have whole-transaction counts 4, 5 and 3. Chinese
plans return 2, 3 and 1: return-only counts, not the requested whole count.
The third fixture includes NULL amounts to distinguish COUNT(amount) too.
Both arms pass both wrong Chinese planner cases. Of four correct English/
Japanese planner cases, off does not block two, on none. Six planner proposals
are six correlated authored observations, not an estimated product failure rate.
Neither role sees rows, SQL, gold, or the other role's response. Using the same
model in separate contexts did not prevent shared semantic errors. Reviewed
metric provenance proves a metric's definition, not that the question asked
for that metric. This shadow does not execute the complete ask/grounding stack.

## Decision and next bounded work

Do not promote v2 as a production certificate; do not enable reasoning by
default on this evidence. The representation now expresses the missing
distinctions and the bounded checker enforces supplied claims. NL extraction
still both invents a return obligation and invents ambiguity on clear counts.
Neither an affirmative bounded pass nor empty claims establish complete intent.
Increasing N is not the supported next step: the repeated tested cores share
their errors. This does not rule out every different model/sampling strategy.

The proposed 40-family / 480-call expansion is NOT started. First isolate the
remaining extraction failure with minimal-pair development cases (output verbs
versus actual return predicates, explicit counts versus underspecified rates),
and a separately frozen multilingual challenge. Compare one context/prompt
change at a time; any definition/name-priming hypothesis remains unproven until
its ablation. No runtime language-specific deletion rule, new ontology, or
larger voting system is justified by this failure. Report false blocks and
joint planner/verifier escapes, not only oracle-input accuracy.

Separately prioritize the production ratio-wrapper-filter omission: either
explicitly reject the unsupported form or specify its scope before compiling;
do not guess numerator versus both operands. This slice added only the v2
unknown guard, not a production contract or implementation change.

Final focused tests 131; final static pass and offline 736 pass, no skips or
failures. The second broad gate is justified by the post-live guard/test change;
the original 735-count gate remains historical. Post-guard digest:
sha256:e2ec1c886fb6995372496bfbff48da27482cc74352f0d6f27b4148e688d85b00.
This is the shadow/final-validation source; the 144-call main source remains
the aa1a6ce8 digest above. Only seven source/input files differ from the approved
checkpoint baseline: the reference, two generators, v2 checker, v2 driver,
new plan fixture and v2 implementation test. No src/ or v1 file changed.

Durable evidence: `evidence/concept-obligations-v2-02.json` (counts, sanitized
shadow responses, source identities and artifact hashes),
`evidence/concept-obligations-v2-replay-01.json` (unchanged main replay and
counterexamples), plus the wrapper-filter evidence linked above. The standalone
ignored shadow driver had fake/privacy self-tests and ruff validation; it is
not represented as covered by the 736 repository tests. All DB/model processes
owned by this slice ended. Existing dirty work is preserved; dev remains at
746f168, no stage, commit or push.
