# Qualified requirements and bounded alternatives candidate (#79)

Owner follow-up on 2026-09-28: "okay，開始 C1、C4、D8 剩餘六題的澄清邊界"
("Okay, start on the clarification boundaries for the remaining six inputs in
C1, C4 and D8"). Recorded in [#79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857591251).
The owner then designated an independent semantic reviewer for C4 and directed
implementation to continue on C1/D8: "指定獨立 reviewer 審核 C4，繼續 C1／D8",
recorded [here](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857596382).

## Evidence and scope

The complete v5 dev observation scored 48/54. C1.zh-TW/en emitted four count
choices despite an explicit seats/accounts contrast. D8.zh-TW clarified an
explicitly required attendance measure instead of declining the whole request.
The accepted contracts already distinguish alternatives from cumulative
requirements and require preserving bound meanings. This candidate operationalizes
that distinction; it does not add a capability, alter expectations or infer why
the model produced its earlier action. No raw reasoning was retained.

C4 has a separate unresolved semantic-support concern: its historical parent
names two amount interpretations explicitly, while the dev wording omits that
contrast and keeps an exact two-choice oracle. The owner-designated independent
reviewer determines whether existing acceptance is supported. Do not put that
pair into the prompt merely to satisfy gold. The owner subsequently delegated the concrete case/gold revision checkpoint
(#79 comment5857618573). The new C4 identities described in
[c4-semantic-revision.md](c4-semantic-revision.md) require the designated
reviewer's semantic acceptance before registration. Old cases/oracles, grader,
product meanings and historical scores stay unchanged.

This is one instruction-only successor, `p3-31b-instruction-v6`, ancestor v5.
It is the second targeted C1/D8 boundary repair after v3; v4 changed serialization
and v5 changed comparison direction. Keep the successful v5 comparison wording,
compact serialization and every other instruction character unchanged. Schema,
runtime context, native execution, route/serving profile, limits, cases/oracles
and all prior candidate files stay unchanged. C4 asset versioning is a separate
evidence repair and cannot count as candidate improvement. No case IDs, literal questions,
dates, codes, language routing, examples, postprocessing or extra model calls.

## Exact instruction changes and checkpoint

Advance the instruction version to `recipe-selection-instruction-v6`.
Replace the contiguous block beginning "First distinguish required outputs"
and ending "not a list of required outputs." with:

> Read the entire question before selecting an action. Collect its requested outputs and explicit qualifiers. Outputs requested together or in addition are cumulative requirements, not competing interpretations. An explicitly named event or population binds a count to that meaning; a generic count noun does not erase its qualifiers. If any required output, scope or bound meaning is unsupported by the recipe, decline the whole request, even when another part is ambiguous. Do not replace a required unsupported measure with a supported measure, or offer those two measures as alternatives. An unresolved interpretation is a meaning the question leaves open, not an additional output it explicitly requires.

Replace the contiguous block beginning "Choose only the alternatives"
and ending "not a default choice set." with:

> Derive choices from the entire question before mapping them to allowed enum values. An explicit either/or contrast restricts the open interpretations to that contrast, even after an earlier generic noun. Represent each explicitly contrasted meaning once and include no other meanings: two contrasted meanings require exactly two choices. Do not reopen alternatives excluded by the question or expand a contrast to fill the schema choice limit. The reviewed enum lists are a vocabulary for representing grounded choices, never a menu to offer in full.

Expected full instruction SHA256: `fb32abe3adc5018ed637dae4c7a47c3146f1c726b9b8f80f8820a1ec738390d4`.

Commit this specification and archived identity ruler first. The initial ruler
must fail because v6 is not registered; retain the failure log. This is an
identity/scope ruler, not a mock proof of model obedience. Existing accepted
contract restatement follows the standing goal's contract/ruler workflow; no new
product meaning is approved here. Preserve historical evidence and stop on a
failed candidate instead of rewriting the registry or changing gold.

## Verification and bounded live observation

Run focused checks and the complete offline suite once; local risk review and
fresh-context actual GitHub diff review precede merge to dev. Use the revised54-input compare-first panel once after independent acceptance
of its C4 replacement. This covers all C1/D8 languages and the nine previously
passing Compare inputs. Report the three revised C4 cases separately and compare
only the51 unchanged input IDs to v5 offline; the runner's same-panel baseline
is not applicable because the panel/case identities changed.

The standing dev grant (#87 comment5852775731) and unchanged-route attestation
(#79 comment5857155780) apply through the recorded follow-up. Synthetic LearningOps
only; opaque existing local credentials; one exclusive run slot and merged dev
identity; at most54 client calls,60seconds and2,048tokens/call,3,360seconds/panel,
one run in flight, no retries/fallback/cache/repair/resume/raw completion or
reasoning. The1,000/day Asia/Taipei ceiling remains. Record all failures and stop
this candidate after the observation; no further candidate is inferred.

Historical C4 scores remain recorded, with the independent review concern
disclosed. Revised C4 results are exposed development observations under new
identities, not fixes to the original broad-term questions. Separate operational completion, historical scoring and
accepted semantic claims. No fresh quality, stability or promotion claim.
