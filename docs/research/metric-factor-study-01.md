# Faithful display constraints and factored candidate selection

2026-09-12. Completed: 180/180 Gemma attempts, no transport errors, no candidate
promoted. Plan: `../plan/metric-factor-selection.md`. Owner approved the new
ruler with "ok" after the explicit 13-red/92-pass, five-arm/180-attempt request.
Root sole writer; no production, database, previous gold/score changes or Git
stage/commit/push.

## Decision

Faithful presentation improves valid output and semantic-core accuracy, but does
not reach the entry threshold or resolve the two stable misreadings. Factoring
operation and population does not improve selection and adds an unnecessary
outside-catalog refusal. Stop this factored-selection candidate under the
predeclared conditions; do not consume confirmation/challenge work or increase N.
The corrected research renderer is useful infrastructure, not a semantic gate.

This experiment does not prove the product infeasible. It does show that changing
these interfaces alone has not supplied the missing question-to-meaning evidence.

## Experiment and controls

Same 36 authored development questions, six paired families and three languages;
33 clear questions plus three deliberately ambiguous rates. No new golds or
challenge inference. B/W/P/S/F each get one independent request per question:

| Arm | Intervention |
|---|---|
| B | Existing exact-text plus occurrence interpretation wire |
| W | Same wire/runtime, with existing conditional rules explicitly displayed |
| P | Fresh original P0 planner |
| S | Fresh original flat operand selector |
| F | S candidate universe, basis ID plus population ID in the same response |

Five arms are serially interleaved (schedule seed 20260914), gemma-4-31b,
temperature0, thinking off, <=4096 output tokens, timeout60s, SDK retries0.
All observed reasoning lengths are zero. No combined W+F inference, extra repair,
order-reversal, confirmation or challenge calls. Calls go only to the authorized
existing gateway with opaque credentials and authored/value-free payloads.

The original catalogs have 39 POS and 17 service operands. Their factorizations
have 6 bases/19 populations/39 allowed pairs and 6/4/17 respectively. Exact pair
lookup restores the original operand and reviewed provenance; the full Cartesian
product is forbidden. Explicit empty-predicate populations are choices, never
defaults for an omitted field. All 28 offline gold/ambiguity-plan coverage pairs
remain expressible; this includes uncalled authored challenge controls.

Factors use the existing canonical predicates, including COUNT/DISTINCT's
implicit NULL exclusion where relevant, not a newly inferred business scope.
Both S/F preserve the original catalog, including degenerate NULL combinations.
These are not catalog-quality or real-user generalization measurements.

## 1. Display correction helps, but does not qualify

| Measurement | B | W |
|---|---:|---:|
| Valid full interpretations | 12/36 | 23/36 |
| Exact semantic core, all requests | 7/36 | 19/36 |
| Exact full span annotations | 2/36 | 2/36 |
| Format failures | 24/36 | 13/36 |
| Ambiguous questions called clear | 0 valid; all three malformed | 3/3 |

The 13 previously red conditional-schema rulers now pass, without changing the
old B renderer or runtime validators. W's remaining failures are 11 responses
with `predicate_requires_concept`, one `occurrence_out_of_range`, one
`extra_forbidden`. Exposing JSON Schema as prompt text is not constrained
decoding, and neither mechanism alone would prove the chosen meaning correct.

Separate non-accepting diagnostics: B has 20 parseable semantic cores / 14 exact;
W has 35 / 25 exact, each out of 36 total requests. They are never used as accepted
annotations. Among W's 23 accepted interpretations, 19 match every semantic field;
three ambiguous cases are incorrectly clear, and another has an output-label
mismatch. Per-field counts and available/total denominators are in the evidence.

Crucially, both mandatory Chinese controls remain wrong in W's diagnostic cores:

- `output_count_all`: 回傳交易筆數 is still a returns-only count.
- `service_rows`: work-log row count becomes DISTINCT ticket_id. B's diagnostic
  core is correct on this question in this run; W's is not.

Both W full responses are rejected for missing predicate concepts. Therefore the
official zero wrong affirmative passes reflects unavailable interpretations on
these controls, not successful semantic recognition. W retains 27/28 correct
fixed plans that it can evaluate, rejects 40 wrong plans, and rejects all six
ambiguous-rate plans. There are 13 unavailable full interpretations; fixed-plan
counts and question counts must not be mixed. Only 74 fixed pairs are evaluated
by W, versus 42 by B (116 total). Correct-control retention is evaluated
against all original controls, not just the available subset.

### Post-hoc safety probe: zero passes was also label-dependent

All three valid ambiguous-rate annotations assert a count ratio and invent an
output label taken from the question. Their rejection of the count-ratio control
is `output_label`, not ambiguity recognition. A zero-model-call probe changes
only that control plan's alias to the model annotation's label: all three become
`pass`, while their authored gold remains `unknown`. Amount-ratio controls still
fail measure basis. All six probes preserve operand definitions exactly.

These are explicitly synthetic post-hoc controls, not observed new model plans
and not recomputed official scores. They demonstrate that a cosmetic mismatch
was hiding an unjustified interpretation. Neither a format refusal nor an alias
mismatch can establish a reliable semantic gate. Artifact:
`.artifacts/metric-factor-study-20260912/label-sensitivity.json` and its driver.

## 2. Factoring the selector did not improve meaning

| Measurement | P | S flat | F factored |
|---|---:|---:|---:|
| Valid interface | 35/36 | 36/36 | 36/36 |
| Correct clear questions | 31/33 | 27/33 | 26/33 |
| Wrong clear questions | 2 | 6 | 6 |
| False outside-catalog refusal | 0 | 0 | 1 |
| Unjustified ambiguous answers | 2/3 | 3/3 | 3/3 |
| Format failures | 1 | 0 | 0 |

P's format failure is the third ambiguous question, not a proper clarification.
All selector output IDs/pairs bind successfully except F deliberately declaring
outside_catalog on Japanese output_count_all, despite proven candidate coverage.
That is a false declaration, not an unavailable member or an actual catalog gap.

F repairs service_rows/zh relative to P, but this is also repaired by S. It loses
six P-correct questions: all three label_only translations, service_entities/zh
and /ja, and output_count_all/ja. Its six wrong plans comprise the label-only
returns subset (three), unrequested minutes-not-null on DISTINCT tickets (two),
and the persistent Chinese return-count misreading (one). The factored interface
has not eliminated the accidental population predicates it was meant to address.

F improves only one family, retains a mandatory stable error, loses six controls,
answers every ambiguous rate without clarification and scores below fresh S.
It does not meet the advancement conditions. Identical candidate universes
make this a meaningful contemporaneous control, but layout/order/token changes
remain part of the factorization intervention. No model-order causality or
cross-session robustness is claimed.

## 3. Actual application replay

Captured plans run through the actual ask/compiler/policy/executor path on three
fictional DuckDB instances. These counts are distinct question-language cases;
threefold instance replays are not independent model observations.

| Arm / policy | Correct answered | Wrong answered | Ambiguous answered | Correct cases blocked |
|---|---:|---:|---:|---:|
| P / current | 24 | 2 | 2 | 7 |
| P / no-lexical shadow | 31 | 2 | 2 | 0 |
| S / current | 23 | 6 | 3 | 4 |
| S / no-lexical shadow | 27 | 6 | 3 | 0 |
| F / current | 22 | 6 | 3 | 4 |
| F / no-lexical shadow | 26 | 6 | 3 | 0 |

P has one malformed proposal excluded from replay; F also has one outside-catalog
refusal in both policies. Gate ablation does not solve wrong answers. Selector
false blocks appear smaller partly because wrong plans contain the triggering
concept and bypass the gate. Production policy is unchanged.

As an isolated cross-check on no-lexical P, W passes 19 of 31 correct answers,
fails one and leaves 11 unknown. Both wrong answers are unknown because W's full
interpretations are unavailable. The two answered ambiguities fail, but the
alias probe above shows why this is not an ambiguity guarantee. Do not combine
these experiments into an unmeasured production promotion.

Existing verification labels are preserved: P has one wrong reviewed-metric
answer marked verified; S/F each have four. Reviewed metric provenance is not
question-to-metric alignment. No verification-status contract is changed here.

## Cost and evidence

| Arm | Median prompt tokens | Median seconds |
|---|---:|---:|
| B | 1353.5 | 5.37 |
| W | 3319.5 | 5.40 |
| P | 3844.5 | 1.31 |
| S | 4575.5 | 1.59 |
| F | 5023.5 | 2.57 |

W raises prompt size without an observed median-latency penalty in this run;
F is larger and slower than S. These are descriptive endpoint observations.

- Ruler: focused 92 passed/13 intended failed, static passed, offline
  1,398 passed/13 intended failed; no other errors or skips. Owner then approved.
- Implementation iteration: focused 188 passed. A zero-network interruption
  probe exposed an unmatched-control KeyError in the new runner; corrected with
  a focused regression, then final static/offline **1,495 passed**. Final full
  suite includes the focused tests; the earlier source is recorded separately.
- Budget probes verify180 maximum, three transport errors stop, source drift
  stop and exclusive fresh outputs. No actual model calls in these probes.
- 106 compiled proposals x3 instances = **318/318 compiler/reference agreements**,
  every compiled proposal has all three checks; zero local execution errors.
- **642 actual ask workflows, 591 SQL executions**, zero new model or PostgreSQL
  calls. Exact re-analysis reproduces official analyses and entry screens.
- Frozen final gate/live/replay source:
  `sha256:592397dd10ff1e3478b225ab5e85e92186153a50c07f6a68837e97f69de83ee8`.
  Five new source/ruler files relative to b48a2bcd; all pre-existing source and
  frozen inputs are byte-identical. No src changes. Dev HEAD remains 746f168;
  preserve pre-existing dirty work, no stage/commit/push.
- Durable evidence: `evidence/metric-factor-study-01.json`; local artifacts and
  reproducible replay/diagnostic drivers under
  `.artifacts/metric-factor-study-20260912/`, with SHA-256 bindings.

## Stop and next discussion

Stop this factored-selection candidate. Keep the corrected renderer research-only
and do not promote the contextual gate, add language exceptions or start larger-N
confirmation. The two intended mechanisms were tested separately; one improved
interface quality, neither supplied sufficient semantic reliability.

The next product/research discussion should identify what genuinely different
evidence can disambiguate intent (for example explicit clarification or an
independent information source), and how to retain useful coverage while failing
closed. That is a new decision/experiment, not additional work or model budget
silently authorized by this run. Untouched authored challenge and real-user blind
validation remain unconsumed.
