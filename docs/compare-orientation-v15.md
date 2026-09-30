# Candidate v15: typed Compare orientation (#142)

Candidate `p3-compare-orientation-v15`, whose ancestor is
`p3-v12-restoration-v14` (v12's exact bytes). It implements ADR #142,
option A, as approved at
[#142 #issuecomment-5907589299](https://github.com/cinic0101/grepbit/issues/142#issuecomment-5907589299).
It is step (2) of the grant
[#142 #issuecomment-5907593990](https://github.com/cinic0101/grepbit/issues/142#issuecomment-5907593990).

**The model reads, and code decides.** For a two-month comparison, the model
always returns a Compare request with a typed `orientation`. The code, not the
model, then decides between executing it and offering the `comparison_roles`
clarification. Count behaviour is v12's, unchanged.

Only `grepbit/recipe_model.py` changes at runtime. The kernel,
`compare.py`, `clarification.py`, `presentation.py` and the frozen P3.3
evaluator stay byte-identical.

## Model-facing changes

1. **Output.** A Compare proposal carries exactly one extra top-level key:

   ```json
   {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1",
    "orientation": "stated",
    "request": {"current": {"...": "..."}, "baseline": {"...": "..."}}}
   ```

   - `orientation` is required on Compare and absent on Overview and Breakdown.
   - Its values are `stated` and `unresolved`, as defined by the reading
     diagnostic (`docs/reading-diagnostic.md`): whether the question states
     which period is evaluated and which is the reference.
2. **Schema.**
   - The Compare request branch gains the required property `orientation`,
     `{"enum": ["stated", "unresolved"]}`.
   - The `comparison_roles` kind is removed from the model's clarification
     branch, so the model cannot emit it.
   - The other kinds, and the other request branches, are unchanged.
3. **Instruction.**
   - The `comparison_roles` sentence is replaced by the orientation rule: set
     `stated` when the question states which period is evaluated and which is
     the reference, and `unresolved` otherwise.
   - With `stated`, the existing role-binding text applies unchanged: the
     assessed period is current, even when it is earlier.
   - With `unresolved`, either role order is accepted, because the server
     offers both.
   - "Never use chronological order or first mention alone" now reads as a
     rule for `stated`.
4. **Context.** The `comparison_roles` clarification note says that it is
   server-built and not a model action.
5. **Versions.** The instruction, context, output-contract and
   structured-output versions all change, so the candidate identity changes.

## Runtime changes (`grepbit/recipe_model.py`)

- **Parsing.** `_proposal` requires `orientation` on a Compare request, with
  one of the two values, and refuses it on any other recipe. Anything else is
  `invalid_request`, with reason `root_shape`.
- **A model-emitted `comparison_roles` clarification** is `invalid_request`.
  A well-formed one has reason `clarification_shape`. A malformed one keeps
  the reason native parsing gives it, for example `choice_consistency` or
  `choice_values`.
- **The proposal object.** `RecipeProposal` keeps `orientation`, and
  `to_dict()` includes it only when present.
  - A proposal constructed directly without `orientation` stays valid. The
    frozen `tests/test_p3_grading.py` constructs Compare proposals that way.
  - A value other than the two, or `orientation` on another recipe, raises.
- **`stated`** executes the Compare request exactly as v12 does.
- **`unresolved`** executes nothing:
  - The code builds
    `Clarification("comparison_roles", (as_proposed, reversed))` from the
    request and its role reversal, with the fixed choice ids `as_proposed` and
    `reversed`.
  - It renders the clarification with the unchanged presentation module and
    runs the same export check as a model-built clarification.
  - The result has `proposal = None` and the clarification set, so the frozen
    grader grades it as a clarification. The grader compares alternatives by
    semantic value, sorted, without ids (`tools/p3_assets.py`
    `semantic_choices`), so it grades exactly like a model-built one.
  - `RecipeInterpretation.source_proposal` keeps the model's proposal. The
    evidence records `compare_orientation` and `source_proposal`, which the
    archived evidence projection does not select, and keeps
    `model_outcome: "clarify"`, the action taken.

## Evaluation side (`tools/evaluate.py`)

- **Persisted action.** The persisted validated action is the model's action
  that passed the runtime validators. For a server-built clarification that is
  `source_proposal`: the Compare request with `orientation: "unresolved"`, not
  the derived clarification.
- **Replay.** Replay at the recording source therefore feeds the model's own
  action, and the runtime rebuilds the same clarification.
- **Closed shape.** `_action_shape` admits `orientation` on a Compare request,
  with exactly one of the two values. The v13 Overview assumption stays
  admitted, for v13 archives.
- **Structural readback.** `_check_action` reads a Compare request with
  `unresolved` as the action `clarify`, of kind `comparison_roles` with two
  choices. Any other request reads as `answer`, as before.
- **Other rows** and the frozen grade are unchanged.

## Frozen source change (owner decision #142 #issuecomment-5911691344, "A")

`tests/test_recipe_clarification.py` changes in the three places the owner
approved:
1. The P2 schema pin is checked after removing the Compare `orientation`
   property and its `required` entry. The test asserts the property's exact
   form.
2. The `comparison_roles` kind is exercised through the server-built path, and
   a model-emitted `comparison_roles` clarification is asserted refused.
3. The P2 Compare meanings carry `orientation: "stated"`. They come from the
   shared helper `proposal("compare")` in `tests/test_recipe_model.py`, which
   is not frozen, so this item needs no edit in the frozen file.

`tests/test_p3_exposed.py` pins the new hash and keeps `42b0ce5c…` as
superseded ancestry, verified against Git. If v15 is reverted, both are
restored.

## Test and tool changes

- **Offline scripts.** The four v1 fake-response scripts stay immutable, and the
  P3 development one is pinned by `tests/test_p3_exposed.py`. Each gets a
  derived sibling, `*-oriented-responses-v1.json`:
  - The derivation is `tests/oriented_actions.py` `orient()`. A Compare request
    gains `orientation: "stated"`, and a `comparison_roles` clarification
    becomes the Compare request of its first choice with `"unresolved"`, from
    which the server rebuilds the same two choices. Every other action is
    unchanged.
  - The ruler checks that each sibling equals the derivation of its v1 script,
    byte for byte.
  - `tools/p3_eval.DEFAULT_RESPONSES` and the dev-panel, bound-meaning,
    mechanism-probe and admission tests use the siblings, as v11 used its cued
    siblings.
- **Shared helpers.** `proposal("compare")` in `tests/test_recipe_model.py` and
  in `tests/test_json_diagnostics.py`, and the oracle-derived action in
  `tests/test_recipe_smoke.py`, carry the orientation. The asset test parses
  the immutable v1 script through `orient()`.
- **Tools.** `tools/reading_diagnostic.py` and `tools/routing_upper_bound.py`
  read a persisted Compare request with `"unresolved"` as a `comparison_roles`
  clarification, as `tools/evaluate.py` does. The routing narrowed-context
  test expects only the kinds the model may emit.
- **Assertions adapted to the new shape:**
  - The replay rulers: the persisted-action shape, and the kernel-change rows,
    which are only the executed Compare requests.
  - The history reason-diagnostic and Bedrock wire-coupling tests: their
    Compare values gain the orientation, so they still reach the native
    validator they test.
- **Bedrock** (the v11 and v13 pattern): the runner's Bedrock route test asserts
  the fail-closed stop, and the wire test of
  `tests/test_invalid_request_reason.py` uses the frozen v12 schema.
- **Earlier rulers:**
  - The v12 ruler again checks its frozen-source restoration through Git at
    #127 and the recorded ancestry, the v13 pattern. Its offline-script default
    applies only while v12 is current.
  - The v13 and v14 rulers skip their runtime checks once superseded.
- **Registry pins.** `tests/test_candidate_registry.py` names v15 as current,
  with 14 entries.

## Routes and limits

- **LiteLLM 31B** is the route under evaluation.
- **Bedrock fails closed for v15.** `grepbit/bedrock.py` pins the v12 recipe
  schema digest, so the changed schema is refused before any send, as with v11
  and v13.
- **Request size.** Removing the model's `comparison_roles` branch shrinks the
  schema.
  - On the 31B route, a full 4,096-byte input gives a 28,762-byte request (v12:
    31,826), under the unchanged 32,768-byte cap.
  - The ruler checks every dev-tier question and that input.

## Evaluation (the grant's steps 3 and 4)

- **Runs.** One v15 run on each of `p3-dev-bound-meaning-v2` and
  `p3-dev-mechanism-probe-v2`, 46 calls, after the v14 sentinels of step 1.
- **Gate.** `tools/evaluate.py --gate --candidate p3-compare-orientation-v15
  --baseline-candidate p3-v12-restoration-v14 --route litellm-gemma-4-31b
  --owner-authorization-reference <grant> --panels p3-dev-bound-meaning-v2
  p3-dev-mechanism-probe-v2`.
- **Verdict.** It is pre-registered. `regression` is a stop and a revert,
  with no rerun.

## Claims and limits

- **The hypothesis under test** is that 31B's accurate diagnostic orientation
  reading (22/22 on these inputs) carries over to the production action call.
  The diagnostic was a separate call, and the production call may keep the
  bias. For `stated`, the roles must still be bound correctly.
- **Scope.** A single model-facing change on one route, one run per panel. It
  may move unrelated decisions. The gate measures that only on the two run
  panels.
- **The count family is not changed** (v12's count text). Applying the same
  pattern to counts is a later, separate decision.
- **Reading diagnostic on v15 runs.** The `replayed` variant of
  `tools/reading_diagnostic.py` would show the model its persisted
  `orientation`, which is the reading under test. Any future diagnostic on a
  v15 source should use the `fresh` variant, or account for this.
