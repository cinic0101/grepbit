# Grammatical comparison-role binding candidate (#79)

The owner explicitly delegated selection and continuation of this third
candidate fix in chat on2026-09-27:
"涉及同一 failure family 的第三次候選修正，可以由你來挑出最適合的方案並繼續執行/研究/測試"
("For the third candidate fix involving the same failure family, you may choose
the most suitable approach and continue implementation/research/testing.")
The agent recorded this in [#79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857290417).
This approves this specific stop exception and delegates the in-scope checkpoint;
other authority, data, case/oracle and execution boundaries remain unchanged.

## Evidence and selection

The [serving retest](compare-serving-retest.md#observed-result-2026-09-27) returned
validJSON/typed requests for all3 inputs, but A3.en falsely clarified comparison
roles. C2.zh-TW and C2.en correctly clarified. Prior exposed A3.en observations
were mostly timeouts, not assessed semantic results. All three recent outputs
were clarifications; successful Compare answer execution remains unverified.
No raw completion/reasoning was retained, so the cause is unknown.

Hypothesis: the instruction's requirement for explicit roles is insufficiently
operational about grammatical target/reference, despite its existing general
reminder. Choose one instruction-only clarification of that mapping and the
contrast with symmetric comparison. An unchanged rerun is not a repair;
schema/postprocessing/serving changes add coupled risk without supporting
failure evidence. No new routing, language parser, literal case match, question
example, date/value answer, or second planner is introduced.

## Exact scope and checkpoint

Register `p3-31b-instruction-v5`, ancestor `p3-31b-instruction-v4`, and advance
only the recipe instruction version to `recipe-selection-instruction-v5`.
Replace the contiguous comparison-direction sentences beginning
"Both distinct named months and their comparison roles must be explicit"
and ending "Ask comparison_roles only when both assignments remain possible."
with the following text (single spaces between sentences):

> Both distinct named months must be supplied. Bind comparison roles from the question's grammatical target and reference: the period being assessed is current, and the period it is assessed against is baseline. A stated reference binds the roles without requiring the literal labels current or baseline. Keep those roles even when current is earlier than baseline. A symmetric comparison that merely names two months supplies no direction: use comparison_roles only when both reversed assignments remain compatible with the wording. Never use chronological order or first mention alone to assign the roles.

Preserve every other instruction character, including unsupported-output
priority, choice-set restrictions, year handling and compact serialization.
Keep runtime context, structured schema, native execution, P1 context/wire,
limits, serving profile, original cases/oracles and old candidate files unchanged.
This implements existing coverage-matrix A3/C2 and P3 A03/C02 meanings; it does
not redefine ambiguity or add a product capability. The new instruction is
model-visible policy, not an oracle or proof of semantic compliance.

Commit this document and the archived identity ruler before implementation.
The expected initial failure is absent v5 registration. The ruler pins exact
instruction identity and unchanged surfaces; no offline mock can prove model
obedience. Root approves this specification checkpoint under the owner's
explicit delegation above. Compatibility: only the new candidate's instruction
and wire identity change; historical evidence stays interpretable. Recovery is
to stop live evaluation and preserve the failed candidate/evidence, not rewrite
history or silently truncate the registry.

## Verification and bounds

Full offline suite once after implementation, local risk review, fresh-context
actual GitHub diff review and squash merge to dev before live execution.
Same synthetic LearningOps data, local31B route and serving witness; opaque
existing credentials; no raw completion/reasoning. Existing #87dev grant and
renewed #79 route attestation (5857155780) apply; route/provider/profile do not
change. One run in flight; no retry/fallback/cache/repair/resume.

Run `p3-dev-compare-retest-v1` once in an exclusive slot: max3calls,60seconds and
2,048outputtokens/call,300seconds/panel. Only3/3 complete, valid and correct
permits one separately prepared54-input `p3-dev-matrix-compare-first-v1` run,
max54calls, same per-call bounds,3,360seconds/panel. Max57calls for this attempt,
within the standing1,000/day ceiling. Keep all scoring thresholds and stop rules.
A failed three-input gate stops this candidate's live sequence. Do not silently
start a fourth candidate. Any full-panel result remains exposed development
observation; it does not establish fresh quality, stability or promotion.

## Observed results (2026-09-27)

PR #104 merged as `2141d819bd95f17eac54e4723b76f44dc9dbdd32` after
1,240 offline tests passed, focused16/16, fixture27/27 and two reviews without
actionable findings. Both live runs used that commit, unchanged serving witness,
the recorded decision/grant chain above, separate exclusive slots and normal
limits. The three-input run finished and passed offline readback before the
54-input packet was prepared. Exactly57 client calls total; no retries/reruns,
raw completion/reasoning retention, or further candidate change.

| Run | Inputs correct | Selected/full families correct | Client calls | Run seconds |
| --- | ---: | ---: | ---: | ---: |
| Three-input gate | 3/3 | 2/2 selected only | 3 | 34.597905 |
| Full dev panel | 48/54 | 15/18 | 54 | 229.262421 |

The gate produced A3.en `complete_correct` in8.065192seconds, C2.zh-TW
`correct_clarification` in12.765445seconds and C2.en `correct_clarification`
in12.798998seconds. Compared through the runner to the completed same-panel
v4report, this is1`FIXED_KNOWN_FAILURE`,2`UNCHANGED_CORRECT`,0`NEW_REGRESSION`
**within these three exposed inputs only**.

The full run completed all54 inputs with validJSON and no timeout/operational
failure. Client latency median3.380122seconds, range0.382409-14.414391seconds.
All9 A3/A4/C2 inputs passed across zh-TW/en/ja, including earlier-current A4
and intentionally ambiguous C2. This supports the targeted A3 repair under the
observed dev conditions; it is not stability, fresh generalization or promotion.

Six semantic failures remain:

| Inputs | Recorded outcome | Observation |
| --- | --- | --- |
| C1.zh-TW, C1.en | wrong_action | count_basis clarification with4choices; semantic_choices failed |
| C4.zh-TW | wrong_action | metric_meaning clarification with4choices; semantic_choices failed |
| C4.en, C4.ja | missed_clarification | answered where clarification was required |
| D8.zh-TW | false_clarification | count_basis clarification with2choices where decline was required |

These same six IDs failed semantically in the earlier v3 boundaries-first
observation (C4.zh-TW had a different wrong outcome there). That historical
run was incomplete and used a different order/serving configuration, so this
is a case-ID observation, not a formal complete no-regression or causal claim.
No gold, threshold, historical result or prompt was adjusted after these runs.
The targeted sequence is complete; remaining clarification boundaries need a
separate bounded follow-up, not an automatic fourth candidate or holdout run.

Evidence is appended in the run index. Local slots under
`.artifacts/compare-role-binding-v5-20260927/`:

- `three/run`, report SHA256 `bb92c8aa6a4ada722ee22474d75d0c9d0c9c7ef6d84fdfd26b9eab55acdaa6ee`.
- `full/run`, report SHA256 `dee80abb63c011ea0123e434d1db915b4c434968b4fa1fc2ee4d1cb615ab1b92`.

Both reports remain `development_observation`, promotion-ineligible. Upstream
inference attempt counts remain unknown;57 is the observed client-call total.
