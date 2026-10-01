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

> A generic people count (headcount, how many people, people who booked) that
> names no count meaning is answered with the Overview request and
> count_request "unresolved", not a count_basis clarification.

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

The grant needs the owner's numeric confirmation before any call; proposed
254 calls (#146).
- **v2 dev panels:** one v16 sentinel per panel while v16 is current (46), then
  one v17 run per panel (46).
- **Wider validation on `p3-dev-matrix-compare-first-v3`** (#149, empty annex):
  two v16 runs while v16 is current (108; one is the sentinel), then one v17
  run (54).
- **Gate.** `tools/evaluate.py --gate --candidate p3-count-directive-v17
  --baseline-candidate p3-count-reading-v16`, on each panel set, with the
  pre-registered rules: `regression` is a stop and a revert, with no rerun.

## Claims and limits

- **Risk of moving other decisions.** The sentence steers the model away from
  `count_basis`. `dev-BM7` names the user's own undecided meanings and should
  stay a clarification. On the v3 panel, `dev-C1` is ruled rule 1 by the
  owner (#149), so it expects an answer with the stated assumption. The gate
  measures both.
- **Scope.** One route, one run per panel; a development observation.
