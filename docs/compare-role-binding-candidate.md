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
