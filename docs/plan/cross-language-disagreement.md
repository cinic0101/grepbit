# Cross-language disagreement: bounded feasibility ruler

2026-09-12. Root owns the coupled research contract. Initial baseline is the
clean local closeout at `a2e080b`; production and historical studies stay frozen.
Owner authorized organizing the test and, after Git cleanup, "直接開始". This
slice establishes the required critical evaluation ruler, not its implementation
or new live calls. Explicit follow-up after the ruler is required by AGENTS.md.

## Question and non-claims

Does independently planning a Gemma-generated English translation expose an
original Chinese metric error that repeating the Chinese request misses, at an
acceptable false-alarm cost? This tests a disagreement detector, not an English
answer selector, majority vote, self-verifier or intent certificate.

The earlier authored English/Japanese controls are not model translations.
Their success motivates this experiment but cannot answer it. Same-model
errors can remain correlated across languages. A disagreement proves neither
which interpretation the user wanted nor that either answer is correct.

## Frozen cases and proposed schedule

Reuse only the 12 Chinese development cases from
`evals/cases/concepts/metric_selection_ruler.yaml`: two cases in each of output
count, output amount, label/filter, negation scope, service row/entity and rate
basis. These are known authored controls, not a blind holdout. Do not send golds,
the authored English counterparts, spans, fixed plans or fictional rows to the
model. No challenge expansion or case-dependent prompt repair.

For each question, independently request:

| Arm | Input | Purpose |
|---|---|---|
| Z1 | Original Chinese | Fresh baseline |
| Z2 | Identical original Chinese/context | Same-language repeat control |
| T | Chinese question and generic translation instructions only | English view |
| E | T's text with the same P0 schema/overlay/planner settings as Z1 | Cross-language plan |

Maximum 48 attempts, serial, one request per slot, no retries/repair. Rotate
Z1/Z2/T/E order across cases while preserving T before E; the schedule is frozen
before requests. E cannot run on a missing/malformed translation: record its
slot as skipped and retain the question in the denominator. Z1/Z2 are not shown
T, E or each other. Comparisons are Z1/Z2 and Z1/E, not a vote across three.
Report actual calls and incremental latency: repeat costs one extra planner;
translation route costs a translation plus one extra planner. Budgets are not
cost-matched and no causal claim about language alone follows from this screen.

Translation instruction: preserve the request's operation, population, negation,
numerator/denominator direction, unresolved ambiguity and verbatim quoted output
labels. Translate rather than answer, explain, add business definitions or remove
uncertainty. No glossary of case-specific exceptions.

## Two separate evidence boundaries

### Translation fidelity

The model's assertion that its translation is faithful is not evidence. Before
looking at E's plan or correctness, record a fidelity ledger with exact input
and output hashes and changes in operation/population/negation/ratio/label or
ambiguity. A different string alone is not semantic drift.

- `reference_exact`: matches the frozen authored English reference (keeping
  original quoted labels). This is an authored control, not user-intent proof.
- `human_confirmed`: the owner reviewed the translation as preserving intent.
- `changed`: a recorded fidelity counterexample changes one of the above axes.
- `unreviewed`: no established fidelity verdict, including a plausible paraphrase.
- `unavailable`: no valid translation.

Root may draft the review table, but its LLM opinion must not be relabeled human
confirmation. Nonexact/unreviewed outputs stay unknown unless the owner reviews
them. Report both strict reference-exact and owner-confirmed results; do not
quietly drop unknown translations or claim translation drift is intent detection.

### Plan comparison

Keep `plan-core-v2` as the unchanged structural diagnostic. It does not expand
reviewed metrics or prove semantic equivalence. A new research comparator is
restricted to one scalar count/sum/count-distinct aggregate or two such ratio
operands on a single table, with explicit NULL/not-NULL predicates. Require the
same frozen schema, overlay, source/time identity; reject unsupported constructs
as `outside_fragment`. No time, grouping, order/LIMIT, having, share, growth,
latest, without, default segments or silently ignored fields.

Comparison states:

1. `equivalent_in_fragment`: full supported expression signatures agree after
   expanding reviewed definitions and justified NULL/PK laws. Cosmetic aliases
   are separate; equality does not prove the selected intent or output label.
2. `witnessed_difference`: a schema-valid fictional instance produces different
   outputs, confirmed independently by compiled SQL and the reference evaluator.
   Persist the two plan hashes, instance identity and engine results. It proves
   different computations, not correctness of either one.
3. `not_distinguished`: signatures differ but bounded instances give no witness.
   This is not equivalence; coincidental fixture answers cannot certify it.
4. `outside_fragment` / `unavailable`: retain as unknown, not detection or pass.

Count(column) means count non-NULL rows, not count distinct entities. Only a
declared single-column non-NULL primary key permits count-distinct -> row count.
Never infer a key, an all-rows population or a business definition from data.
Output-label fidelity is scored independently even for equivalent computations.
Initially reuse the three existing fictional instances; no DB provisioning or
general-purpose SQL equivalence framework is needed. No witness does not imply
the bounded search was complete.

## Endpoints, data and stops after ruler approval

Destination: existing `http://10.12.0.187:4000/v1`, `gemma-4-31b`. Use the existing
ignored .env key opaquely; never print/copy credentials or persist reasoning.
Outbound: authored question/translation, value-free projected schema, reviewed
metric definitions and closed output schema only. No SQL, rows, golds, customer
questions/data, credentials in payloads, second endpoint/model or package work.
Temperature 0, thinking off, max4096 output tokens, timeout60s, SDK retries0.
All attempts consume the 48 ceiling; stop on three consecutive transport errors,
source/input drift or exposure risk. No automatic restart with a fresh budget.
Freeze/hash packaged resources too, and take final identity after analysis.
Fresh .artifacts outputs only; commit reviewed synthetic/count/hash evidence.
Offline DuckDB/reference and captured-plan ask replays need no external DB/model.

## Measures and decision rule

Always retain all 12 question slots, available pairs and reasons for missing
ones. Separate proposal correctness from actual ask/gate availability. Replay
captured proposals through current ask and isolated no-lexical shadow with zero
additional model calls; neither replay changes production behavior.

- Credited catch: Z1 is wrong by the frozen authored gold, fidelity is established,
  and Z1/E has a witness. E may still be wrong; record whether it is correct.
- False alarm: Z1 is correct but Z1/E has a witness, even if T caused the change.
- Persistent wrong: Z1 wrong with an equivalent E, never an affirmative pass.
- Translation-noise flag: witnessed difference with changed/unreviewed T; it
  consumes attention but receives no intent-detection credit.
- Unknown/invalid/ambiguous outcomes and label-only errors remain separate.
- Incremental catches require a credited catch and a supported, positively
  equivalent Z1/Z2 pair. Merely lacking a repeat witness (including unknown,
  outside-fragment or unavailable repeats) is insufficient.

Advance only to a separately scoped confirmation study if there is at least one
incremental catch (including `output_count_all` when its original error recurs),
no false alarms among observed Z1-correct clear-question controls, a nonempty
comparable correct-control denominator, and all 12 slots have complete
transport/parse/comparison/fidelity accounting. Every observed correct control
must have a supported equivalent/witnessed-different Z1/E comparison; missing or
outside-fragment pairs cannot shrink the denominator to make the screen pass.
No comparable correct controls means "catch demonstrated, false-alarm screen
inconclusive", even if one wrong answer was detected. Unreviewed fidelity means the
claim remains provisional, not a passed screen. If no Z1 error recurs, report
inconclusive sensitivity; do not claim zero errors proves detection works. One
catch supports a cheap further experiment, not adoption. Neither remaining
consistent errors nor unknowns are hidden by the screen. Confirm later with
fresh sessions and broader untouched questions before a product decision.

## Executable ruler, not a missing-implementation failure

`tests/fixtures/cross_language_rulers.json` fixes the accounting examples and
semantic witnesses. `tests/contract/t0/test_cross_language_rulers.py` checks
these against frozen golds, hand values, the two local engines and existing
structural comparison. It demonstrates both structural false alarms and
consistent wrong answers without redefining the old stability contract.

The new live comparator does not exist yet. A missing import failure would not
establish the intended behavior, so use explicit test-only decision/accounting
rules and existing-behavior counterexamples at this checkpoint. Do not import
test helpers into a future driver. No new src/evals implementation or live call
before the explicit post-ruler follow-up.

Checkpoint validation: 33 focused checks (32 new plus the existing single-PK
law), static pass; `evidence/cross-language-ruler-01.json`. Read-only adversarial
review added explicit repeat-equivalence and nonempty/full correct-control
comparison requirements to prevent vacuous advancement. No new model/DB calls.
The prior combined 1,501-test closeout gate preceded this test-only slice.
