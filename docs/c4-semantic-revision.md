# C4 explicit-contrast development revision

## Decision and independent review

The owner designated an independent fresh-context C4 semantic reviewer in chat,
then delegated approval of the concrete case/gold revision to root:
"審核建議改題目或 gold，具體修訂方案你確認無誤即可繼續".
English: "If the review recommends changing the questions or gold, you may
confirm the concrete revision plan is correct and then continue."
Recorded [owner delegation](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857618573).

The designated reviewer read questions/contracts before the oracle and found
that the original dev-C4 wording dropped the parent's explicit two-meaning
contrast while retaining its exclusive two-choice oracle. Clarification is
defensible, but neither that exclusive pair nor every allowed enum value is
entailed by the bare words revenue/收入/売上. Existing exact-choice acceptance
is not supported across all three languages. Also, the manually authored
clarification oracle incorrectly describes itself as kernel-derived.

Root selects a new explicitly contrasted family rather than a new policy for
bare revenue terms. This preserves the intended admitted clarification boundary
without deciding that generic revenue has exactly two meanings. The replacement
requires the owner-designated reviewer's semantic acceptance before production
asset registration. No revised expectation is derived from candidate output.

## Exact replacement

New family `dev-C4-v2`, input IDs `dev-C4-v2.zh-TW`, `.en`, `.ja`; oracle
`dev-C4.v2`, revision2. Same center CTR-A02, March2026, timezone Asia/Taipei,
full-month half-open scope. Questions:

- zh-TW: 請提供 CTR-A02 在 2026 年 3 月的報名概況與金額；這裡的金額要用已確認報名金額，還是實際收款金額，我尚未決定。
- en: Give me a booking overview for CTR-A02 in March 2026 with the amount; I have not specified whether that means confirmed booked amount or cash received.
- ja: CTR-A02 の 2026 年 3 月の申込概況と金額を知りたいです。金額は確定済み申込金額と実際の入金額のどちらを意味するか、まだ指定していません。

Expected action: `clarify`, kind `metric_meaning`, exactly the two explicitly
named alternatives `confirmed_booked_amount` and `cash_received`. Existing
native Overview scope and typed choice shapes remain. Choice ID spelling and
order do not define correctness. The question leaves one meaning unresolved,
not a demand to calculate both amounts; cash collection remains unavailable
through the recipe entry. No product capability or resume flow is added.

Questions-map canonical SHA256: `c047a34a849a486e8a79cdd64406488ccda67437307a48ec6e12b4444b9327cc`.

Oracle provenance states these are authored semantic expectations for an
explicit two-way ambiguity, not kernel-derived or candidate output, with a
reference to this review/owner decision. Case provenance links each old C4 input
and exposed C04 parent; exposure remains `exposed_regression`, seen by implementer.

## Versioning and claims

Add `evals/dev/dev-cases-v2.json`, `dev-oracles-v2.json` and
`dev-panel-compare-first-v2.json`; register `p3-dev-matrix-compare-first-v2` as dev.
Only the three C4 case objects and C4 oracle change in the new copies; preserve
all51 other case objects and17 other oracle objects exactly, including their
historical provenance text (not a new derivation claim). Order equals the v1
compare-first order with only the three C4 IDs substituted. Prior assets,
registry entries, all recorded reports, and original54 denominators stay intact.
The old C4 scores remain historical grader outputs with this acceptance concern;
they are not silently corrected to passes, excluded, or relabeled.

Commit this specification and an initially failing registration/projection ruler
before asset changes. Independent semantic acceptance and root's delegated
checkpoint must precede registration. The ruler proves identity preservation,
not natural-language semantics. Code QA remains separate from semantic review.

A v6 run on the new panel can report its54-input total but must show the revised
C4 trio separately. Compare model outcomes against v5 only on the51 unchanged
case IDs with unchanged oracles. Do not call revised C4 successes fixes to the
original questions or treat the new panel as fresh/golden evidence. If acceptance
fails or the repair requires a new business meaning, stop that surface while
continuing independent C1/D8 work.

## Accepted specification checkpoint

Before production asset changes, the owner-designated reviewer accepted all
three exact proposed questions, branch, two-choice set, scope and authored
provenance with no actionable semantic findings. Its follow-up retained its
prior independent context and saw the quoted owner delegation/proposal; no
C1/D8 implementation, model outputs, network, services or fresh holdout data.
Root approves the concrete versioning checkpoint under the owner's explicit
delegation. Production registration and history preservation remain code-review
obligations, not conclusions supplied by semantic acceptance.
