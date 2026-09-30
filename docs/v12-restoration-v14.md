# v12 restoration v14 (#136, #79)

The owner decided this in chat on 2026-09-30, and the agent recorded it on #79
([#issuecomment-5907491660](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5907491660)):
「我沒有問題，可以開始 (a)」 ("No problem from me; you can start (a)"). The
agent read "no problem" as confirming the revert that the v13 grant had
pre-registered, including the restoration of the frozen test. No model call is
authorized by this decision.

## Why

Candidate v13 (`docs/count-assumption-v13.md`, #140) got the pre-registered
gate verdict `regression` (`docs/count-assumption-v13-result.md`, #141). Under
the grant
([#79 #issuecomment-5904208402](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5904208402))
that is a stop, and v13 is reverted by a further PR. v14 is that revert.

- v14 returns the runtime to v12's exact bytes, which are v10's and v7's. It is
  a restoration, not a new fix.
- The next change, ADR #142, starts from these bytes. v14 is also the
  candidate whose sentinel runs that ADR's grant needs.

## Exact identity specification

Candidate `p3-v12-restoration-v14` is registered after v13, so its registry
ancestor is v13, because the registry is one linear append-only chain.

Its runtime is byte-identical to `p3-v10-restoration-v12`:

- `grepbit/recipe_model.py` is restored to its bytes at `607c673`, the parent of
  the #140 merge, with SHA256
  `90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457`.
- No other runtime file changed in v13. The runtime file digests equal v12's
  registered `runtime_files_sha256`.
- These fields are equal to v12's:
  - the recipe context, structured output, P1 context and limits (request
    32,768);
  - `semantic_identity_sha256`
    `95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb`;
  - `candidate_sha256` `6d707b8dc2d58915f2a794d97404faf85be72ab5ac7e27545bd2d9d0c428e536`,
    the wire witnesses and `runtime_files_sha256`.
- Only the registration fields differ: candidate ID, ancestor, ancestor
  SHA256, registered commit and time, and note.
- The v7, v10 and v12 runs therefore count as the same bytes in the aggregate
  and in the gate's baseline.

## Reversals

**Frozen source restored.** `tests/test_recipe_clarification.py` returns to
its accepted frozen bytes at `20abb55`, which are also its bytes at
`607c673`: SHA256
`42b0ce5ca722422540deb8ef46517da78c8ff558098fc6d81b6948602b3f0c11`.
- `tests/test_p3_exposed.py` returns to its bytes at `607c673` and pins that
  hash again. Its v13 superseded-ancestry entry goes with it, because the file
  again holds the frozen bytes.
- The v13 amendment (`0ab94719…`) and its record (#136
  #issuecomment-5905969011, `docs/count-assumption-v13.md`,
  `docs/p3-evaluator.md`) stay in history.
- The frozen evaluator files and the P3 assets are untouched.

**Bedrock route reopened.** `grepbit/bedrock.py` pins the v10/v12 recipe
schema hash, which is again the live schema. So the `bedrock_converse` route
no longer fails closed before transport. v14 makes no Bedrock claim, and a
Bedrock run needs its own authorization.

## Tests

- **Restored to their bytes at `607c673`.** These are the modules that v13
  changed only to follow its runtime:
  - `tests/test_recipe_clarification.py` and `tests/test_p3_exposed.py` (above);
  - `tests/test_evaluate.py`: the Bedrock route test sends again;
  - `tests/test_invalid_request_reason.py`: the wire test uses the live schema
    again;
  - `tests/test_v10_restoration_v12.py`: its frozen-source check reads the
    working tree again.
- **Kept from v13:**
  - `tests/registry_twin.py` and its use in `tests/test_evaluate_gate.py` and
    `tests/test_evaluate_replay.py`. They do not depend on which candidate is
    current.
  - `tests/frozen_recipe_schema.py`, whose docstring records that v11 and v13
    fail closed.
- **The v13 ruler** `tests/test_v13_count_assumption.py` skips its runtime
  checks once v13 is superseded, as the v11 and v12 rulers do. Its registered
  identity stays pinned.
- **Registry pins.** `tests/test_candidate_registry.py` names v14 as current,
  with 13 entries.
- **New ruler** `tests/test_v12_restoration_v14.py`: the live runtime equals
  v12's registered identity field by field, and the frozen test holds its
  accepted bytes.

## Claims and limits

- v14 is v12's behaviour. Its recorded results are v12's, including the v2
  panel baseline (#139), with no new evidence.
- The v13 archives stay readable: the run index keeps both v13 rows, and the
  annex shape still admits the persisted assumption.
- The count rule of ADR #136 is not implemented by v14. Its evaluation half
  (the annex and the v2 panels, #138) stays in force.
