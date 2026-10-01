# Candidate v21: v19's server answer on v20's model-facing bytes (#164)

Candidate `p3-count-basis-answer-v21`, whose ancestor is `p3-v18-restoration-v20`.
- **The decision.** The owner approved it, with its frozen-test amendment, an
  exception to the two-fix default and a 308-call grant, in chat on
  2026-10-01, recorded at
  [#164 #issuecomment-5934502364](https://github.com/cinic0101/grepbit/issues/164#issuecomment-5934502364):
  「ok，繼續, 308 沒問題」.
- **Why it can be registered.** Option C of ADR #164 (`docs/behavior-identity.md`,
  #165) makes a runtime-only candidate registrable.

## Why

v19 (`docs/count-basis-answer-v19.md`) had the server answer a model
`count_basis` clarification with booked seats and the stated assumption.
- **What it fixed.** All 21 of its fixes came from that rule: on every fixed
  row the model made the same kind of `count_basis` clarification as on v18
  (some choice ids differ), and the server answered.
- **What broke it.** To be registrable, v19 also changed the model-facing
  context: one sentence, and the version string v6 to v7. The outputs are
  close to deterministic (v18 repeated 76 of 78 actions), and that change most
  likely flipped `dev-BM2.en` to a decline (corrected after v21's run: the
  input is flaky on v18's own bytes; see `count-basis-answer-v21-result.md`). The gate gave `regression` (#162),
  and v20 restored v18 (#163).

v21 keeps v19's rule and drops v19's context change. The model sees exactly
v20's (that is, v18's) bytes.

## The change

**Runtime** (`grepbit/recipe_model.py`):
- **The bytes.** It is v19's file (`tests/fixtures/v19_recipe_model.py`,
  v19's registered digest) with exactly two lines reverted to v18's:
  - `CONTEXT_VERSION` stays `learningops-recipe-context-v6`;
  - the `count_basis` context entry ends, as in v18, at "booked_seats is
    executable through this recipe."
- **The rule.** Everything else is v19's: `_server_answers`, the answer of a
  validated model `count_basis` clarification with its own Overview scope and
  `count_request: "unresolved"`, `RecipeInterpretation.source_clarification`,
  the `source_clarification` evidence key, and keeping it through kernel
  failures and timeouts. The contract is v19's, "The change: Runtime".
- **Identity.**
  - **Model input unchanged:** the recipe context, instruction, structured
    output, P1 context, limits and wire witnesses all equal v20's. So
    `candidate_sha256` and `semantic_identity_sha256` equal v20's (and v18's).
  - **Behaviour changed:** `runtime_files_sha256` differs from v20's in
    `grepbit/recipe_model.py` only, so the behaviour identity differs.

**Evaluator:** unchanged since v20.
- **The row-based rule.** A model `count_basis` clarification on a row
  recorded `answer` is a server answer that states the assumption. On a
  `clarify` row it is the clarification it was.
- **No recorded row** states none.
- **Archives.** v18, v19 and v20 archives keep reading back.

**Frozen-test amendment** (approved at #164 #issuecomment-5934502364):
- `tests/test_recipe_clarification.py` returns to the amended bytes from #160,
  `7eb964192be7b584e972e2db7f4036c15e773bec0b37b27051fd3dbdd1d3eb06`:
  - the generic default clarification is `center`;
  - `count_basis` leaves the non-executing kinds.
- `tests/test_p3_exposed.py` pins that digest. Its ancestry keeps the accepted
  baseline `42b0ce5c…` and cites the v21 decision. That citation is the only
  difference from the diff confirmed on #160.

## Tests

- **Restored to their v19 bytes.** The tests that #160 changed to follow
  v19's runtime, and that #163 restored, return to their bytes at `250fc89`
  (v19), where they pass against v21. This includes the history tools' tests
  with their `_server_answers` seam. Any that need a change for v21 are listed
  on the PR.
- **The v21 ruler** (`tests/test_v21_count_basis_answer.py`), committed
  failing before the implementation:
  - **The runtime file** is the v19 fixture with exactly the two context lines
    reverted, and the model-facing identity equals v20's;
  - **v19's runtime behaviour holds:**
    - the answer and its assumption;
    - other kinds still clarify;
    - an invalid clarification fails before any answer;
    - failure paths keep the model's clarification;
  - **The evaluator's row rule and its no-row default;**
  - **A v20-shaped archive** (a real `count_basis` clarification row) reads
    back, aggregates and gates against v21 under `evaluation-gate-v2`. Against
    the synthetic panel's historical clarify oracle, C01 is a `broke`;
  - **v21 is the registered current candidate:**
    - ancestor v20;
    - the same `candidate_sha256` as v20, and a different behaviour identity;
    - `check` reports no changed runtime file.
- **Superseded rulers.** The v19 and v20 rulers skip their runtime checks once
  superseded. Their runtime-free checks stay.

## Evaluation (grant #164 #issuecomment-5934502364)

**Result: `passed`.** 21 fixed, 0 broke, and `dev-BM2.en` excluded as flaky
in the baseline.
- **The prediction failed.** The offline prediction below that it "stays
  answered" failed: v21 declined it.
- **What saved the verdict.** The pass on it rests on the v20 sentinel also
  declining it.

See the [gate results](count-basis-answer-v21-result.md).

**The steps.**
- **(2)** One v20 sentinel on each of `p3-dev-bound-meaning-v3`,
  `p3-dev-count-fresh-v2`, `p3-dev-matrix-compare-first-v3` and
  `p3-dev-mechanism-probe-v2` (154 calls), while v20 is current.
- **(4)** One v21 run on each (154).
- **(5)** The gate against v20 under `evaluation-gate-v2`.
- **Baseline.** v18's and v20's runs share one behaviour identity, so each
  panel's baseline is v18's two runs (#162) plus the v20 sentinel.
- **Stop.** `regression` is a stop and a revert.

**Offline prediction** (not evidence). v21's model input is v18's, so v18's
recorded actions predict v21's model actions up to sampling: 76 of 78 repeated
between v18's runs. Under v21's rule:
- the 21 `count_basis` clarifications that v19 fixed become answers;
- `dev-BM2.en` stays answered (failed: v21 declined it, as did the v20
  sentinel);
- `dev-A1` and the fresh panel's O rows stay wrong (out of scope).

`--replay` of v18's or v20's archives under v21 is allowed, because the model
input matches. It can show this offline, and it is never a gate input.

## Claims and limits

- **Not fixed:** the `dev-A1` class (out of scope, #158).
- **Risks the gate measures:**
  - The model's actions vary slightly between runs even with identical bytes.
  - A `count_basis` clarification given for a Compare or Breakdown question
    would run its one-month Overview scope (the #160 review's L4).
- **Scope.** Formal and holdout panels are frozen and may expect
  `count_basis` clarifications, so a promotion claim needs a new formal panel
  (#158 item 6). This covers one route and one run per panel, on exposed
  development inputs.
