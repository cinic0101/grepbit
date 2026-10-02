# Candidate v22: every executed Overview states its count basis (#169, step A3)

Candidate `p3-overview-basis-v22`, whose ancestor is `p3-count-basis-answer-v21`.
It is step A3 of the plan for the owner's policy A
([#169](https://github.com/cinic0101/grepbit/issues/169), plan at
#issuecomment-5944003912, revised at #issuecomment-5944521151):

> every executed Overview states its people-count basis.

It is registrable as a runtime-only candidate under the behaviour identity
(#165).

## The change

**Runtime** (`grepbit/recipe_model.py`). It is v21's file with one change:
- **v21:** `RecipeProposal.assumption` returns the owner's count assumption
  only for an Overview whose count reading is `unresolved`.
- **v22:** it returns it for every Overview proposal whose count reading is not
  a named unavailable count. That covers `none`, `booked_seats` and
  `unresolved`; an Overview action always carries a reading (v16).
  - **Named unavailable counts** are still declined by the server before
    execution (v16), so no statement is made for them.
  - **The evidence.** Every executed Overview without an error carries the
    statement `count_assumption`, which reports booked seats and names the
    unavailable meanings.
- **Compare and Breakdown** never carry it.

**Model input: unchanged.**
- **The bytes.** The instruction, context, structured output, P1 context,
  limits and wire witnesses all equal v21's. So `candidate_sha256` equals v21's
  (and v20's and v18's), and the behaviour identity differs through
  `grepbit/recipe_model.py` only.
- **One sentence is now out of date.** The instruction still tells the model
  that the stated assumption follows an unresolved reading. That sentence stays,
  on purpose, so the model input does not move. The change is the server's
  alone.

**Evaluator.**
- **What it relies on.** v22 relies on #169 step A1 (PR #173,
  `docs/recorded-count-assumption.md`): the annex verdict reads the statement
  the server recorded.
- **Without A1.** The derivation from the action would miss the statement on
  `none` and `booked_seats` readings.
- **Order.** v22 merges only after A1.

## Tests

- **The v22 ruler** (`tests/test_v22_overview_basis.py`), committed failing
  before the implementation:
  - **The runtime file** equals v21's registered `grepbit/recipe_model.py`
    once the one property is set back.
  - **Model input and behaviour.** The model input equals v21's, and the
    behaviour identity differs.
  - **Every executed Overview states the basis:** `none`, `booked_seats` and
    `unresolved`.
  - **A named unavailable count** is declined with no statement. The rule
    itself excludes it, not only the server's decline before execution.
  - **Executed Compare and Breakdown** state none.
  - **Which checks stay after v22 is superseded.** These statement checks are
    policy A's behaviour, so they keep running after v22 is superseded. Only
    the identity checks (the runtime file and the current registration) stop.
  - **v22 is the registered current candidate:** ancestor v21; the same
    `candidate_sha256`, a different behaviour identity; `check` reports no
    changed runtime file.
- **Earlier rulers** asserted v21's narrower rule against the live runtime.
  Each one now checks either the annex mechanics under a pinned rule, or the
  owner's rule as the registry gives it (`tests/narrow_assumption.py`):
  - **Where the rule comes from.** The rule is the narrow one until v22 is
    registered, and policy A from then on. It never comes from the runtime
    under test.
  - **What that protects.** A later candidate that silently drops policy A
    fails these rulers. This was checked with a scratch successor that
    restores v21's property.
  - **Before the merge,** each changed file also passes on v21's runtime, where
    v22 is not registered.
  - **The annex mechanics** (`test_count_assumption`, and
    `test_compare_first_v3`, which reuses its synthetic runs). These pin the
    narrow rule in `setUp`. They test how the annex is computed, not which
    rule the current candidate uses.
  - **v16's ruler** (`test_v16_count_reading`). It checks v16's rule until v22
    is registered. Under policy A:
    - the reading table and the legacy proposal expect the statement;
    - the named-seats rows (`dev-BM5.en` with `booked_seats` and `none`, and
      `dev-BM6.en` with `booked_seats`) run on `p3-dev-bound-meaning-v4`. Each
      must carry the statement, have no error, and grade `complete_correct`
      and annex-`correct` on the recorded statement.
  - **A1's ruler** (`test_recorded_count_assumption`). See the amendment in
    `docs/recorded-count-assumption.md`.

## Evaluation (grant #169 #issuecomment-5944677551)

**The grant is 594 calls,** which the owner confirmed. The steps run in this
order:
- **First, v21 baselines,** made while v21 is current, so before this PR
  merges. They are recorded with the v22 runs:
  - three v21 runs on each of `p3-dev-bound-meaning-v4`,
    `p3-dev-count-fresh-v3` and `p3-dev-matrix-compare-first-v4`: 396 calls;
  - two more on `p3-dev-mechanism-probe-v2`: 44 calls.
- **Then the v22 run,** one on each of the four panels, after this PR merges:
  154 calls.
- **Then the gate,** `evaluation-gate-v3` against v21. `regression` is a stop
  and a revert.

**The projection** (`docs/policy-a-panels.md`; not evidence):
- **The policy-attributable fixes** are the 15 rows that the policy A annexes
  made wrong under v21: `dev-BM5`, `dev-CF06`, `dev-CF07`, `dev-CF18` and
  `dev-A2`, three languages each.
- **The `dev-A1` class** (`dev-A1`, `dev-CF16`, `dev-CF17`) is already
  annex-correct under v21, so it shows as `unchanged_correct`. It is resolved
  by the policy, not by v22.
- **Any `broke` row** keeps the `regression` verdict and is investigated.

## Claims and limits

- **What v22 changes.** It makes the server's statement consistent across
  Overview answers. It does not change the model's readings or its input.
- **What it does not establish.** No promotion and no generalization claim.
  Formal and holdout panels predate policy A, so a promotion claim needs a new
  formal panel (#169).
- **The count ablation is not v22-ready.** `tools/count_ablation.py` archives
  no statement per row, so its annex verdict keeps the derivation from the
  action (`docs/recorded-count-assumption.md`, "Not covered").
  - **Under v22,** its verdicts on `none` and `booked_seats` Overview readings
    would be wrong.
  - **Before any use under v22,** it must record the statement. That is #174,
    and the ablation is not part of this grant's steps.
