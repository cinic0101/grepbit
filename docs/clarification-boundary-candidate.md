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

## Observed result (2026-09-28 Asia/Taipei)

[PR #106](https://github.com/cinic0101/grepbit/pull/106) merged as
`5b2c697803f4a5ec05b3bbe328b4e576cde028ac` after focused 17/17, the complete
1,242-test offline gate, fixture 27/27, local risk review and independent
GitHub diff review without actionable findings. The owner-designated semantic
reviewer separately accepted the exact registered C4 v2 objects at a72efc8
([record](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857662824)).
Read-only preflight confirmed the registered serving image/configuration and
healthy service before execution; no serving change was made.

Exactly one run of `p3-dev-matrix-compare-first-v2` completed from the merged
commit, using the recorded grant chain and unchanged route attestation above.
All 54 inputs completed, with 54 observed client calls, valid JSON and no
operational failure or timeout. Upstream inference attempts remain unknown.
No retry, rerun, raw completion/reasoning retention or subsequent candidate
change occurred. Run duration was 217.376754 seconds; per-call latency median
3.351699 seconds, range 0.365872–12.448763 seconds.

| Evidence slice | Result | Interpretation |
| --- | ---: | --- |
| Revised 54-input dev panel | 53/54; 17/18 families | Development observation under the new panel identity |
| 51 unchanged cases | v5 48/51 → v6 50/51 | C1.zh-TW and C1.en improved; no newly failing case in this observation |
| C1, all three languages | 3/3 | Correct two-choice count-basis clarification |
| Revised C4 v2, all three languages | 3/3 | Correct two-choice metric-meaning clarification on explicitly contrasted new questions |
| D8, all three languages | 2/3 | zh-TW remains false clarification; en/ja correctly decline |
| A3/A4/C2 Compare controls | 9/9 | All previously passing Compare cases passed this observation |

The unchanged-case comparison is an offline intersection, not the runner's
same-panel baseline comparison. All 51 input question hashes, oracle IDs,
expected branches and semantic signatures match the v5 report. The asset
ruler also proves the corresponding case and oracle objects are unchanged.
The old C4 questions are absent from the new panel: their earlier results are
preserved, and this run establishes neither a fix nor a new score for them.
The revised C4 trio is evidence of the accepted explicit-contrast behavior,
not an additional three repaired historical failures.

The sole failure is `dev-D8.zh-TW`: HTTP/JSON and typed request validation
passed, but the model produced `clarify/count_basis` with two choices where
`decline` is required. The grader records `false_clarification`; native kernel
execution did not run. Its call took 7.596632 seconds and returned 252 completion
tokens. This is a semantic action failure, not a timeout or malformed JSON.
English and Japanese D8 still correctly decline. No raw output or reasoning is
available to establish the model's internal cause.

Outcomes: 18 `complete_correct`, 12 `correct_clarification`, 23 `correct_decline`,
1 `false_clarification`; no checked-wrong answer. The targeted observation is
complete. D8 remains open after this second targeted C1/D8 instruction attempt;
a third targeted candidate needs the applicable owner checkpoint. Do not rerun
or start holdout/golden consumption automatically. These exposed observations
do not establish stability, fresh quality, promotion or general absence of
regressions.

Evidence is appended to `evals/runs/index.jsonl` and reflected in `STATE.md`:

- Run ID: `p3-dev-matrix-compare-first-v2--litellm-gemma-4-31b--p3-31b-instruction-v6--9bcaaccd1c99`.
- Local slot: `.artifacts/clarification-boundaries-v6-20260928/run`.
- Report SHA256: `f9dae48e0d54026a60c93a311df48b5097aa7b5029362ca5e3c8b0a8deb39237`.
- v5 comparison report SHA256: `dee80abb63c011ea0123e434d1db915b4c434968b4fa1fc2ee4d1cb615ab1b92`.
- Local offline readback and `comparison.json` preserve the counts and case-ID
  comparison; claim remains `development_observation`, promotion-ineligible.
