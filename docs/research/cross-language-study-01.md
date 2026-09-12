# Cross-language disagreement: one useful signal, one persistent error

2026-09-12. The approved 48-call development experiment is complete. It provides
a provisional reason to continue researching a disagreement detector, not to
adopt English planning or certify an answer. No production behavior changed.

The decisive observation: Chinese `回傳交易筆數。` again selects return-only
count, including on an identical repeat; its model-generated English translation
selects all-transaction count. Conversely, the explicit request to count work-log
records still becomes distinct work-order count in both languages. Agreement
therefore remains compatible with a wrong answer.

## Protocol and identity

The owner explicitly approved the ruler in
`../plan/cross-language-disagreement.md`, implementation and at most 48 serial
Gemma attempts. Baseline: `8288c06bc96ceb40d2f7eb7bbed18d6ae7dc4744`.
The root owns implementation/analysis; a read-only specialist reviewed transport,
bounded comparison and replay risks. No external DB, package or production work.

Reuse the 12 Chinese authored development questions in
`evals/cases/concepts/metric_selection_ruler.yaml`, six families, not a blind
holdout. Each has Z1 original, Z2 identical repeat, T translation and E planning
of T. The frozen rotated schedule preserves T before E. No candidate sees
another plan; T sees no schema, gold or definitions, and planners see no rows or
gold. Output-label text must remain in its original language.

Model: `gemma-4-31b`, temperature 0, thinking off, 4,096-token/60-second ceilings,
SDK retries 0, repair turns 0. P0 uses `plan-classify-json-v15`; actual ask replay
uses `ask-orchestration-v3`. All 48 requests succeeded; no parse/transport errors,
skipped slots or source drift. The budget is closed, with no extra model calls.

Focused/static/offline/live share source
`sha256:10d704296b0f17daeec68a8d9e4a31a7e6fd5a36319567409c1a00bb511111be`.
Source identity is taken again after analysis. Exact input/context, request,
question/translation and plan hashes are retained under
`.artifacts/cross-language-study-20260912/live.json[l]`; reviewed counts,
witnesses and artifact hashes are in `evidence/cross-language-study-01.json`.

## Translation judgment is separate from a passed screen

The automatic fidelity ledger, written after each T and before its E request,
contains 2 reference-exact and 10 unreviewed translations. Different wording
alone is not an error, but the frozen rule does not credit an unreviewed output.
Accordingly, the unchanged formal report has **0 credited incremental catches**
and `eligible_for_confirmation=false`.

The translation-only sheet was prepared before inspecting planner outcomes.
The owner subsequently asked the root, "你可以幫我檢查嗎". The root's judgment
is that **all 12 preserve meaning**: population, count unit, negation, label,
ratio direction and the unresolved return-rate definition. See
`cross-language-translation-review.md` for the per-family reasoning. This final
agent review follows outcome analysis, so it is neither independent/blinded
review nor human confirmation. No translation, live ledger, gold or acceptance
threshold was rewritten.

The conditional interpretation below assumes that agent judgment is correct.
It is a separately labeled sensitivity reading, not a retrospective formal pass
or a production translation verifier. Adopting an agent-based fidelity rule in a
future study would require its own explicit evaluation contract and measurement.

## Results by question, not by repeated fixture execution

| Outcome | Z1 original | Z2 repeat | E translated |
|---|---:|---:|---:|
| Correct clear question | 9 | 9 | 10 |
| Wrong clear question | 2 | 2 | 1 |
| Unresolved definition, formula nevertheless proposed | 1 | 1 | 1 |

Z1/Z2 computations are equivalent in the supported fragment on **12/12**
questions. Z1/E has 10 equivalent pairs and 2 witnessed differences. All nine
originally correct controls are comparable, with **0/9 observed false alarms**.
This small, authored sample does not establish a low population false-alarm rate.

| Case | Observation | Interpretation |
|---|---|---|
| `output_count_all` | Z1/Z2 use `return_count`; E uses row count. Three SQL/reference instances give Z1/E values 2/4, 3/5, 1/3. | One potential incremental catch among two observed known-wrong questions, conditional on agent-reviewed fidelity. |
| `service_rows` | All arms count distinct work orders instead of work records. | Persistent wrong agreement; the detector misses it. |
| `rate_unspecified` | Z1/Z2 use return count / net sales; E uses return amount / net sales. | Genuine computational disagreement, but neither establishes the user's intended definition. Not credited as a correct answer or a known-wrong catch. |

The rate example also shows why a disagreement cannot choose the better plan.
The original count/currency ratio is suspicious, but this study neither invents
a business default nor adds a new dimensional-unit policy.

Comparison expands reviewed measures and justified NULL/primary-key count laws;
the old structural diagnostic stays unchanged. A witness requires compiled SQL
and the independent reference evaluator to agree on each plan's value, while
the two plans differ. Signature equality proves only equality in the supported
single-table scalar fragment, not correct intent. No witness is not equivalence.
The fixture validator is scoped to the fixed no-FK schemas, not arbitrary data.

## Actual ask replay: English is not a production replacement

All 36 proposals were replayed on three fictional instances through actual
`application.ask`, with both the current concept gate and a research-only
`concepts=[]` shadow: **216 workflows, 195 SQL executions, zero new model calls**.

| Arm | Current gate: answered / 12 | Correct proposals blocked | Clear wrong proposals answered | No-lexical shadow: clear wrong proposals answered |
|---|---:|---:|---:|---:|
| Z1 | 11 | 1 | 2 | 2 |
| Z2 | 11 | 1 | 2 | 2 |
| E | 7 | 4 | 0 | 1 |

Each answered count includes the unresolved return-rate formula; it is not a
correct-answer count. Each question has the same status on the three instances.
Current English blocks `output_count_all`, `output_amount_all`, `label_only`
and `service_entities` despite correct plans, plus the wrong `service_rows`.
Chinese blocks the correct `label_only`. Thus English's zero served wrong
answers is partly refusal, not successful semantic verification. The shadow
recovers availability but preserves one wrong English answer and both Chinese
errors. Neither production gate nor its verification labels are changed here.

Local value checks: **108/108** proposal-instance compiler/reference agreements,
plus **12/12** plan-instance agreements used for six pair-instance witnesses.
Those six instances represent two question differences, not six independent
catches. No PostgreSQL replication was needed or performed in this slice.

## Cost, validation and recommendation

Per-call p50: Z1 1.315 s, Z2 1.302 s, T 0.711 s, E 1.437 s. Paired incremental
p50 is **1.302 s for the repeat** and **2.123 s for T+E**. Across all 48 requests,
recorded call time totals 56.511 s and provider-reported tokens total 140,661.
These arms are not cost-matched; this is not a throughput benchmark or proof
that language, rather than other prompt effects, caused the change.

Focused 85 tests pass; static passes; the final offline gate is **1,586 passed,
zero failures/skips**, including focused tests. Tests cover frozen accounting,
count laws, hand-value witnesses, unsupported/context-mismatched plans,
translation isolation, 48-call limits, source drift, transport stops, fresh
outputs, ledger-before-E and real ask replay. No full gate is repeated for the
subsequent docs/evidence-only closeout. Production and earlier study sources
remain unchanged from the clean baseline.

Recommendation: keep this as a **provisional shadow-detector candidate**, not a
validator, selector or automatic clarification gate. It produced information
that one identical repeat did not, but missed half of the two observed errors;
this is a descriptive count, not an estimated 50% sensitivity. The strict
screen remains unpassed because nonexact fidelity lacks the specified review.
Do not silently waive that rule or consume another live allocation.

Next discussion should separate a bounded, independently judged confirmation
study from the already planned editable-query technical ruler. The former must
measure translation drift, persistent wrong agreement and human attention cost
on fresh sessions/questions; the latter supplies a route to new intent evidence
when both plans agree wrongly. Neither is a reason to add word exceptions or
to postpone the human correction path. No new study, adoption or push occurs
as part of this completed 48-call slice.
