# Exact-occurrence wire and bounded candidate selection

2026-09-12. Completed; no candidate advances or enters production.
Plan and authorization: `../plan/metric-wire-and-selector.md`. The owner explicitly
approved the ruler checkpoint with "同意通過，繼續實作與測試". Root sole writer;
180/180 authorized Gemma attempts consumed, zero transport errors and retries.
No additional challenge, confirmation, reasoning or repair calls were made.

## Conclusion

Moving offset calculation to the server improves interface acceptance, but does
not establish semantic reliability. Selecting valid candidate IDs solves the
output-format problem in this run, but worsens meaning selection. Neither is a
safe replacement for the current lexical gate or an affirmative semantic gate.
This is evidence against these particular candidates on the frozen development
set, not proof that the product or every alternative approach is infeasible.

## Frozen setup and attribution

- Same 36 authored development questions: 12 cases, six paired families, Chinese,
  English and Japanese. There are 33 clear questions and three deliberately
  ambiguous rate questions. This is not a blind real-user holdout.
- A: original independent interpretation interface. B: identical final semantics,
  exact text plus zero-based occurrence, with server-computed Unicode offsets.
- P: fresh P0 planner control. S1/S2: atomic aggregate/filter candidate selection,
  with identical IDs/definitions and reversed display order. The selector changes
  both the available action space and presentation relative to P.
- Candidate catalogs are generated without questions, gold or rows: POS 39,
  service 17. All 28 offline gold/ambiguity-plan coverage pairs are expressible;
  this includes uncalled challenge cases, not challenge inference evidence.
- Serial interleaving, schedule seed 20260913, gemma-4-31b, temperature 0,
  thinking off, 4096 output-token ceiling, 60-second timeout, SDK retries zero.
  All recorded reasoning lengths are zero. Only authored questions, value-free
  schema, definitions, candidate cards and output schemas leave the process.

## 1. The occurrence adapter fixes some friction, not the semantic failure

| Measurement | A: original offsets | B: text + occurrence |
|---|---:|---:|
| Valid final interpretations | 1/36 | 12/36 |
| Exact semantic core, among all requests | 1/36 | 6/36 |
| Exact full span annotations | 0/36 | 2/36 |
| Format failures | 35/36 | 24/36 |
| Ambiguous questions with valid interpretations | 0/3 | 0/3 |

B fails the predeclared 35/36 format threshold. Among its 12 valid responses,
measure basis matches 12, population and requirements each match 11, output label
matches seven; only six match every semantic field. Exact evidence localization
cannot establish the role of a phrase or the requested population.

Most importantly, B interprets `output_count_all/zh` (回傳交易筆數) as a returns
subset and affirmatively accepts the known-wrong `returns_count_metric` plan.
Across the fixed controls available to its 12 valid interpretations, B retains
9/18 correct plan controls, rejects 23/24 wrong controls and passes one wrong
control. Missing interpretations are unknown, never passes. A evaluates only
four pairs (two correct/two wrong), which is insufficient gate coverage.

Separate, non-accepting diagnostics remove spans and inspect the remaining
fields: A has 18/36 parseable cores, 16 exact; B has 20/36 parseable cores, 13
exact. These are diagnostics only, never downstream annotations or rescued calls.
They do not show a semantic improvement from B. Detailed per-field counts and
their distinct available/total denominators are in the evidence JSON.

### New instrument finding: the displayed schema under-specifies the parser

Safe diagnostics expose role/scope and predicate/concept constraints, not just
offset arithmetic. In A, 13 responses report `span_not_in_question`, ten report
`invalid_span_scope`, and 12 report `predicate_requires_concept`. In B, eight
report invalid scope, seven missing predicate concept, six unknown basis
identifier. One response can contribute multiple codes; early rejection can
hide later failures. B's zero reported location errors is not proof every
rejected response had valid locations.

An independent JSON Schema validator accepts six synthetic counterexamples
that the actual runtime rejects: A/B each with (1) output_action scoped to
population, (2) business_predicate without a concept, and (3) a returns include
requirement paired with all_rows population. The Python cross-field validators
are stricter than the schema shown to the model. This establishes a real
presentation gap, not that all observed model failures are caused by it.
Rejected raw model responses were intentionally not retained.

Any next wire experiment should expose the existing conditional invariants in
the model-visible form and test equivalence to the unchanged final validator.
Do not loosen the validator, silently invent a concept, change gold, or count a
diagnostic-only core as accepted. Fixing presentation still cannot, by itself,
solve the observed semantically wrong but fully valid return-count reading.

## 2. Finite choices make valid output, not correct choices

| Measurement | P | S1 | S2 reversed |
|---|---:|---:|---:|
| Valid interface | 35/36 | 36/36 | 36/36 |
| Correct clear interpretations | 31/33 | 27/33 | 27/33 |
| Wrong clear interpretations | 2 | 6 | 5 |
| False outside-catalog decision on a clear question | 0 | 0 | 1 |
| Unjustified answers to ambiguous questions | 2/3 | 3/3 | 3/3 |
| Format failures | 1 | 0 | 0 |

P's one format failure is the remaining ambiguous question, not a proper
clarification. No arm produces a correct semantic refusal on these ambiguities.
S2's outside-catalog declaration is a selection failure despite independently
established catalog coverage, not an actual missing candidate or correct refusal.

Both selectors repair `service_rows/zh`, but lose five previously correct
questions each. Only one family improves, below the required two, and losses
violate the zero-regression condition. New mistakes include treating a quoted
output label as a returns predicate and adding `minutes IS NOT NULL` to a
distinct-ticket count. The Chinese output-action/return-count error survives.

S1/S2 select the same complete envelope on 30/36 questions; envelope differences
include labels, so this is not the semantic stability score. Among 35 pairs
where both produce plans, 31 have the same meaning and four differ: the three
ambiguous rates switch count-based versus amount-based ratios, and Japanese
label_only switches wrong versus correct population. A fifth question changes
from a correct plan to outside_catalog. One pair differs only in its envelope
without changing the plan meaning. Correctness/refusal outcomes agree 34/36,
which conceals the three ambiguous-rate semantic flips.

These order-associated differences fail the declared stability screen. One
request per order is not sufficient to isolate an order effect from endpoint
nondeterminism. No causal claim or cross-session confirmation is made.

Descriptive median latency (seconds): P 1.32, S1 1.64, S2 1.62; A 6.13, B 5.24.
Median prompt tokens: P 3844.5, S1/S2 4575.5, A 1356.5, B 1353.5. Candidate
selection is not a demonstrated latency or prompt-size win in this experiment.

## 3. Actual ask replay separates false blocks from wrong answers

Captured proposals were replayed through the actual application, compiler,
policy and SQL execution path on three fictional DuckDB instances. No new model
or PostgreSQL calls. Counts below are question-language observations, not the
threefold instance count. Malformed P output is excluded from ask replay.

| Arm / local policy | Correct answered | Wrong answered | Ambiguous answered | Correct questions blocked |
|---|---:|---:|---:|---:|
| P / current | 24 | 2 | 2 | 7 |
| P / no lexical shadow | 31 | 2 | 2 | 0 |
| S1 / current | 23 | 6 | 3 | 4 |
| S1 / no lexical shadow | 27 | 6 | 3 | 0 |
| S2 / current | 22 | 5 | 3 | 5 |
| S2 / no lexical shadow | 27 | 5 | 3 | 0 |

S2 also refuses one clear question as outside_catalog under either policy.
The smaller false-block count of S1 is not a net improvement: several previously
correct label-only plans became wrong plans that contain the lexical concept
and therefore bypass the gate. Removing that gate recovers correct answers but
does not eliminate any wrong or ambiguous answers. Production policy is unchanged.

B cross-checks affirmatively pass the same wrong Chinese return-count reading
in all three planner/selector arms. Separate inference contexts did not remove
this shared error. For P with no-lexical shadow, B passes six correct questions
and one wrong question, fails five correct questions, and leaves 20 correct,
one wrong and two ambiguous questions unknown. It is neither adequate coverage
nor a reliable semantic certificate.

The current verification levels are preserved, not redefined: in P one wrong
answer is `verified` (reviewed return metric) and one `unverified_semantics`.
In S1/S2 respectively four/three wrong answers use reviewed metrics and are
`verified`. Metric provenance does not prove question-to-metric alignment.

## Validation, evidence and limits

- Approved rulers: focused 306, static pass, offline 1,221.
- Implemented research: iteration focused 182 at source c7620a43; final static
  pass and offline 1,306 at frozen b48a2bcd (includes those focused tests).
  No repeated full gate after an unchanged-source live run.
- All 106 compiled proposals have exactly three value checks: 318/318
  compiler/reference agreements, no errors. This proves neither gold agreement
  nor natural-language correctness; a wrong plan can execute faithfully.
- 642 actual ask workflows, 588 SQL executions, zero new model calls. These
  reuse captured proposals and must not be counted as independent model samples.
- Zero-call re-analysis exactly reproduces analysis and entry screens. Runtime,
  final gates and replay share source
  `sha256:b48a2bcd907ba88891c5ad2ec1e56a5c1584c4fa5bd9dd7373e163212440d6b0`.
- Durable evidence: `evidence/metric-wire-selector-01.json`. Full local artifacts:
  `.artifacts/metric-wire-study-20260912/{live,ask-replay,schema-gap,closeout}.json`;
  replay/closeout drivers and SHA-256 bindings are recorded in the evidence.
- Five new research/ruler files only in source snapshot; every source/input
  file present at the preceding study baseline remains byte-identical. Preserve
  the pre-existing dirty worktree. HEAD dev remains 746f168; no stage/commit/push.

## Next order, not additional work silently consumed

1. Keep both interfaces research-only. Neither passes the frozen entry screen,
   so do not consume confirmation/challenge work as if one did.
2. Correct the model-visible schema/runtime presentation gap as a separately
   specified experiment, with exact adapter equivalence and rejection tests.
   Separate binding, population, basis and label errors from location failures.
3. For semantic selection, test whether separating operation/basis from optional
   population selection reduces distractor-induced filters; include explicit
   no-extra-filter, output-label and ambiguous-rate controls. This is a new
   hypothesis, not an established improvement or permission for another run.
4. Retain the two stable misreadings as mandatory negative controls. Only after
   a candidate improves multiple families without losses or wrong affirmative
   passes should a separately budgeted cross-session run and untouched authored
   challenge proceed. Real-user blind evaluation remains a later requirement.

Do not add language-specific exceptions, increase N, replace deterministic checks
with a model, or change verification semantics to make these results look better.
