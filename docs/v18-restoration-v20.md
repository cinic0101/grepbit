# v18 restoration v20 (#158)

The owner decided this in chat on 2026-10-01, and the agent recorded it on
#158 ([#issuecomment-5932833755](https://github.com/cinic0101/grepbit/issues/158#issuecomment-5932833755)):
「選 2，照你的建議開始」 ("Option 2; start as you recommended"). Option 2 is
step 1, this restoration, followed by step 2, a decision issue on letting the
candidate identity cover the runtime's decision rule. No model call is
authorized by that decision, and v20 needs none.

## Why

v19 (`docs/count-basis-answer-v19.md`, #160) failed its pre-registered gate:
`regression`, with 21 fixed and `dev-BM2.en` broken on both panels that
contain it (`docs/count-basis-answer-v19-result.md`, #162). The grant's verdict
term is that v19 is reverted by a further PR. v19 is not an accepted
improvement, and it was the registered current candidate until v20.

v20 returns the runtime to v18's exact bytes. It is a restoration, not a new
fix: it makes no count, Compare or other repair. The v21 proposal (v18's
model-facing bytes plus v19's server answer) is a separate decision.

## Exact identity specification

Candidate `p3-v18-restoration-v20` is registered after v19, so its registry
ancestor is v19, because the registry is one linear append-only chain.

Its runtime is byte-identical to `p3-count-scope-v18`:
- `grepbit/recipe_model.py` is restored to its bytes at `ba7e556` (#159), with
  SHA256 `6c7e59cef313ec0e96a745429f86a7ffdbc0c630be3bad6095e4107233c75fc5`.
  This takes context v7 back to v6, and it removes the server answer
  (`_server_answers`) and `RecipeInterpretation.source_clarification`.
- No other runtime file changed in #160, so the runtime file digests equal
  v18's registered `runtime_files_sha256`.
- These fields equal v18's:
  - the recipe context, the structured output, the P1 context and the limits;
  - `semantic_identity_sha256`
    `73eb8f8379e44e242e765277d04bfec409cacb5dc539fbe941ad28d03470ee7a`;
  - `candidate_sha256`
    `375482d4ca8f9f9714c913fa5cbc3d968c16e1e9a2bc1dcf383c7bcde0b90a16`;
  - the wire witnesses and `runtime_files_sha256`.
- Only the registration fields differ: candidate ID, ancestor, ancestor
  SHA256, registered commit and time, and note.

v20 and v18 have the same `candidate_sha256`, so v18's runs are v20's
same-bytes runs for `--aggregate` and `--gate`, as v7's are v12's.

## Owner-approved reversal: the frozen source

The approval at #issuecomment-5932833755 names it.
- **`tests/test_recipe_clarification.py`** returns to its accepted frozen bytes
  at `ba7e556`, with SHA256
  `36c3a189bfd3499c086eee83683c715490fb1d3fb10e44523029007e9923cc24`.
- **`tests/test_p3_exposed.py`** returns to its bytes at `ba7e556`. It pins that
  hash again, and its ancestry entry again cites #146.
- **What stays in history:** the v19 amendment (`7eb96419…`) and its record on
  #160. The frozen evaluator files and P3 assets are untouched.

This is the inverse of #160's frozen hunks, whose concrete diff the owner
confirmed (#160 #issuecomment-5931564694).

## The evaluator keeps reading v19

v19's archives are in the run index (#162), so the readback rule stays:
- `tools/evaluate.py` (`_check_action`, `annexed`), `tools/routing_upper_bound.py`,
  `tools/reading_diagnostic.py` and `tools/count_ablation.py` keep the
  row-based rule. A model `count_basis` clarification on a row whose recorded
  `actual_action` is `answer` is a v19 server answer that states the
  assumption. On a `clarify` row it is the clarification it was.
- **One change:** `_stated_assumption` now states the assumption for a
  `count_basis` clarification only when the recorded `actual_action` is
  `answer`. So an action with no recorded row states none. Readback already
  rejects any other recorded action for that action.
  - **Why.** Under v19, "no row" meant the current runtime's answer. Under v20
    the current runtime clarifies.
  - **The rule now.** Only a recorded server answer states the assumption, and
    no current runtime is consulted. This is v18's behaviour on every v18-shaped
    input.
- `_validated_action` keeps reading `source_clarification` with `getattr`, so
  it works with both runtimes.

## Superseded v19 assets and tests

- **Tests #160 changed to follow its runtime,** and the frozen pair, return to
  their bytes at `ba7e556`. No later commit changed them. They are:
  - `test_recipe_clarification` and `test_p3_exposed` (the approval above);
  - the history tools' tests `test_p3_candidate_regression`,
    `test_p3_dev_regression`, `test_p3_formal_run` and `test_p3_stability_run`
    (the `_server_answers` seam is gone with the runtime);
  - `test_evaluate`, `test_evaluate_replay`, `test_evaluate_gate`,
    `test_count_assumption`, `test_compare_first_v3`, `test_count_ablation`,
    `test_reading_diagnostic`, `test_p3_eval`, `test_p3_admission`,
    `test_dev_panel`, `test_mechanism_probe_controls`,
    `test_bound_meaning_controls`, `test_count_fresh_panel`,
    `test_invalid_request_reason` and `test_v17_count_directive`.
- **Kept, because they pass unchanged against v20:**
  - `tests/test_v18_count_scope.py` keeps #160's `superseded()` guard. v18 is
    registered but not current, so its registration check skips.
- **The v19 ruler,** `tests/test_v19_count_basis_answer.py`, keeps its
  runtime-free checks, as v11's ruler did under v12:
  - the request cap;
  - the row-based mappings in routing, the reading diagnostic and the annex,
    with a recorded row.

  The no-row case of `_stated_assumption` is asserted in the v20 ruler.

  Its runtime, context, v18-archive and registration checks skip once v19 is
  superseded.
- **v19's archives stay covered end to end** by the v20 ruler, through a frozen
  copy of v19's runtime:
  - `tests/fixtures/v19_recipe_model.py` holds v19's `grepbit/recipe_model.py`
    bytes, whose SHA256 equals v19's registered runtime digest
    (`80120e98ce34945bd192a44381a808a59cce8b79e6f5a605ff87b19929f83915`).
  - The ruler loads it inside the `grepbit` package, under a private module
    name, and has it produce v19-shaped archives on the synthetic dev panel.
  - Those archives then read back, record, aggregate and gate against v20 with
    the current code.
  - It is never a runtime path: only the ruler imports it.
- `docs/count-basis-answer-v19.md` is marked superseded.

## Ruler (`tests/test_v20_restoration.py`)

Committed failing before the restoration and passing after it, in the same PR:
- `grepbit/recipe_model.py` has v18's registered digest, the context is v6, and
  there is no server answer;
- v20 is the registered current candidate, with ancestor v19. Every identity
  field above equals v18's, and `check` reports no changed runtime file;
- the frozen pair equals its `ba7e556` bytes. The 19 other restored tests
  are verified on the PR and are not pinned, so later edits to them stay
  possible;
- `_stated_assumption` states the assumption only on a recorded `answer` row,
  and `_check_action` reads both kinds of `count_basis` row;
- the v19 fixture has v19's registered digest, and its archives read back,
  aggregate (the answered C01 input `stable_wrong` against the historical
  clarify oracle) and gate. The gate is v20 against v19: C01 `fixed`, every
  other input `unchanged_correct`, verdict `passed`. This end-to-end check
  skips with a named reason if any other runtime file differs from v19's
  registration, because the fixture is v19 only together with them.

Once v20 is superseded, its runtime, frozen-pair, registration and
end-to-end checks skip, as the earlier restorations' rulers do. The
evaluator checks and the fixture's digest stay.

## Evaluation

None. v20 makes no live claim. Its identity equals v18's, whose recorded runs
stand. The next live step belongs to the v21 decision and its own grant.

## Claims and limits

- **v20 restores v18's behaviour.** `dev-C1`, `dev-BM7`, the fresh panel's
  system-basis-doubt rows and the user-undecided rows (D) are wrong again
  under the revised oracles, as v18 was (#162's v18 runs).
- **The two-fix default.** v20 is not a count fix. The v21 proposal needs the
  owner's decision on its ADR, its frozen-test amendment, an exception to the
  two-fix default and a grant.
