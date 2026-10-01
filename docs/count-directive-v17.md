# Candidate v17: the count action directive (#146)

Candidate `p3-count-directive-v17`, whose ancestor is `p3-count-reading-v16`.
It is the next step the owner approved on #146
([#issuecomment-5920552185](https://github.com/cinic0101/grepbit/issues/146#issuecomment-5920552185):
「2個都可以，調用沒問題，幫我研究並測試」).

## Why

- **v16** (`docs/count-reading-v16.md`, gate `passed`, #148) left eight count
  rows wrong: `dev-MN1` zh-TW/ja, `dev-MN2` ×3 and `dev-MN3` ×3. Each is the
  model's own `count_basis` clarification offering all four meanings.
- **v13's text** (#140) had answered all eight. It told the model what action to
  take: a generic people count "is answered with the request plus assumption".
- **v16's text** says how to *read* the count (`unresolved`) and what the
  server does, but it never tells the model to return a request instead of
  clarifying. The research note is on #146.

## The change (`grepbit/recipe_model.py`, text only)

`SYSTEM_INSTRUCTION` gains one sentence after the `count_basis` limit:

> With a complete explicit Overview scope, a generic people count (headcount,
> how many people, people who booked) that names no seats, accounts, attendance
> or distinct individuals is answered with the Overview request and
> count_request "unresolved", not a count_basis clarification.

This is v13's sentence (#140), with the same scope guard and the same exclusion
list, adapted to v16's typed reading. v13 said "answered with the request plus
assumption"; v17 says "count_request unresolved", because the assumption is
code-decided since v16.
- The scope guard keeps a count noun from turning a Compare, Breakdown or
  multi-month question into a narrowed Overview, as v13's contract explained.
- The exclusion list keeps a question that names a meaning out of the rule.

- **`INSTRUCTION_VERSION`** becomes `recipe-selection-instruction-v10`, so the
  candidate identity changes.
- **Unchanged:**
  - the context, the output contract and the structured-output schema;
  - the frozen clarification test;
  - v16's code-decided assumption and decline;
  - v15's Compare orientation.
- **The assumption stays code-decided.** A question read as `booked_seats`
  (`dev-BM5`) still states none. That is v16's protection against v13's
  spurious assumption.

## Evaluation

The grant is #146 #issuecomment-5922742690, with 254 calls. It was amended at
#issuecomment-5923049914 to 260 calls, with one operational repeat, after the
operational stop at #issuecomment-5923032940.
- **v2 dev panels:** one v16 sentinel per panel while v16 is current (46), then
  one v17 run per panel (46).
- **Wider validation on `p3-dev-matrix-compare-first-v3`** (#149, empty annex):
  two v16 runs while v16 is current (108; one is the sentinel), then one v17
  run (54).
- **Gate.** `tools/evaluate.py --gate --candidate p3-count-directive-v17
  --baseline-candidate p3-count-reading-v16`, on each panel set, with the
  pre-registered rules: `regression` is a stop and a revert, with no rerun.

## Claims and limits

- **What v17 targets.** v16's eight remaining count rows, `dev-MN1` zh-TW/ja,
  `dev-MN2` ×3 and `dev-MN3` ×3, name no count meaning.
- **What v17 does not target: `dev-C1`** on the v3 panel.
  - The owner ruled it rule 1 (#149), so it expects an answer with the stated
    assumption.
  - But it names seats and booking accounts, so the new sentence's own
    exclusion leaves it out. The existing `count_basis` limit ("undecided
    between named meanings") also reads on it literally.
  - The text does not encode the owner's distinction, that doubt about the
    system's basis is not the user's own undecided choice. So `dev-C1` most
    plausibly stays a clarification, unchanged and wrong. An answer there would
    be a fix.
- **Risks the gate measures:**
  - **`dev-BM5`** (named seats) is protected only while it reads
    `booked_seats`. Under v13's prose, this input gained a spurious assumption.
  - **`dev-BM8` and `dev-D8`.** Their zh-TW/ja forms contain the people noun
    (人數 / 人数 / 人次 / 延べ人数). Read as `unresolved`, a required decline
    would become a booked-seats answer.
  - **`dev-BM7`** names the user's own undecided meanings, so it should stay a
    clarification.
  - **Compare inputs.** `E02_compare.zh-TW`, `dev-MC3.en` and `dev-A3.en`
    moved under earlier byte changes. Under v15, a flip to `unresolved` gives a
    roles clarification.
- **Unmeasured.** No dev case puts a people count on an incomplete scope, a
  Compare, a Breakdown, or with another unsupported output. The scope guard
  addresses those cases, but the gate cannot see them.
- **Scope.** One route, one run per panel; a development observation.
