# v10 restoration v12 (#79)

The owner decided this in chat on 2026-09-29, and the agent recorded it on #79
([fallback direction](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5890972084),
[full-fallback approval](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5891175175)).
The owner selected `full_v10`, labelled
「1. 完整回退 v10：核准 (a)(b)(c)，先做證據詞彙 PR，再做 v12 候選 PR」
("1. Full fallback to v10: approve (a), (b) and (c); do the
evidence-vocabulary PR first, then the v12 candidate PR"). No model call is
authorized by that decision.

## Why

v11 ([count-cue policy](count-cue-policy.md)) failed step 1 of grant #79:
5/12 in the count group, where 12/12 was required. Its bounded sequence
stopped (#124). v11 is not an accepted improvement, but it remained the
registered current candidate.

The grant named v10 as the fallback. v12 returns the runtime to v10's exact
bytes, which are v7's. It is a restoration, not a new fix: it makes no count,
Compare or other repair. The event-cue analysis is a separate proposal, ADR
#125, and v12 implements none of it.

The evidence-vocabulary step (#126, `907e111`) came first. The report reader
now pins v11's evidence vocabulary, so v11 archives stay readable without
`grepbit/count_policy.py`.

## Exact identity specification

Candidate `p3-v10-restoration-v12` is registered after v11, so its registry
ancestor is v11, because the registry is one linear append-only chain.

Its runtime is byte-identical to `p3-v7-context-restoration-v10`:

- `grepbit/recipe_model.py` is restored to its bytes at `43116a7` (#119), with
  SHA256
  `90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457`.
- `grepbit/gateway.py` is restored to its bytes at `43116a7`, with SHA256
  `5739e79d9e3c1eaf828eb347e4c5930dfdeb41fd157e9e3c68cc5b61da8e526f`, so the
  cap is again `MAX_REQUEST_BYTES = 32768`.
- `grepbit/count_policy.py` is removed.
- No other runtime file has changed since v10. The runtime file digests equal
  v10's registered `runtime_files_sha256`.
- These fields are equal to v10's:
  - the recipe context, structured output, P1 context and limits (request
    32,768);
  - `semantic_identity_sha256`
    `95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb`;
  - `candidate_sha256`, the wire witnesses and `runtime_files_sha256`.
- Only the registration fields differ: candidate ID, ancestor, ancestor
  SHA256, registered commit and time, and note.

## Owner-approved reversals

The owner approved three items by name. Each reverses part of #120.

**(a) Frozen source restored.** `tests/test_recipe_clarification.py` returns
to its accepted frozen bytes at `20abb55`, which are also its bytes at
`43116a7`: SHA256
`42b0ce5ca722422540deb8ef46517da78c8ff558098fc6d81b6948602b3f0c11`.
`tests/test_p3_exposed.py` returns to its bytes at `43116a7` and pins that
hash again. The v11 amendment (`821bc7d5…`) and its record in
[count-cue-policy.md](count-cue-policy.md#frozen-source-change-owner-decision-120)
stay in history. The frozen evaluator files and P3 assets are untouched.

**(b) Request cap reversed.** The gateway cap returns to 32,768 bytes, for
every path.
- The #122 mechanism stays: known caps are exactly 32,768 and 40,960.
  Packets are prepared at the candidate's registered `limits.request`, and
  archive read-back accepts an exact match at a known cap. v11 archives, at
  40,960, stay readable.
- `tools/p3_eval.MAX_REQUEST_BYTES`, the default for new manifests, now
  follows `grepbit.gateway.MAX_REQUEST_BYTES`, instead of a literal 40,960
  that would disagree with the gateway.

**(c) Bedrock route reopened.** `grepbit/bedrock.py` pins the v10 recipe
schema hash, which is again the live schema. So the `bedrock_converse` route
no longer fails closed before transport. v12 makes no Bedrock claim, and a
Bedrock run needs its own authorization.

## Superseded v11 assets and tests

- `tools/p3_eval.DEFAULT_RESPONSES` returns to
  `evals/p3/development-responses-v1.json`.
- The four `*-cued-responses-v1.json` files, the readings fixture and the
  frozen v10 schema fixture stay as immutable v11 assets. Tests that ran them
  through the v11 runtime return to the v1 files, whose bytes never changed.
- Ten test modules that v11 changed to follow its runtime, and that fail
  against v12, return to their bytes at `43116a7`. No later commit changed
  them. They are:
  - `test_recipe_clarification` and `test_p3_exposed` (approval (a));
  - `test_structured_output`, `test_smoke`, `test_p3_admission` and
    `test_mechanism_probe_controls`;
  - `test_gateway`, `test_dev_panel`, `test_bound_meaning_controls` and
    `test_invalid_request_reason`.
- `tests/test_evaluate.py`, which #122 also changed, reverses only v11's hunks.
  That restores the Bedrock success-path test on the live schema. Its two #122
  request-cap tests now:
  - take v12 at 32,768 as the current cap;
  - use v11 at 40,960 as the other registered cap;
  - read back archives at both known caps.
- Ten other modules keep v11's test-only adaptations, because they pass
  unchanged against v12:
  - `tests/test_recipe_smoke.py` and `tests/history/test_p3_candidate_probe.py`
    use a `metric_meaning` clarification instead of `count_basis`.
  - Eight modules patch `recipe_model.output_schema` with the frozen v10 schema
    fixture:
    - `test_bedrock_adapter`, `test_bedrock_complex_const_contract`,
      `test_bedrock_grammar_budget_contract` and
      `test_bedrock_wire_coupling_contract`;
    - the history modules `test_p3_bedrock_candidate_contract`,
      `test_p3_bedrock_candidate_probe`, `test_p3_bedrock_observed_regression`
      and `test_p3_reason_diagnostic`.
  - Under v12 that fixture equals the live schema. `grepbit/bedrock.py` pins
    the same hash, so the patch is a no-op. Their comments that "v11 fails
    closed on Bedrock" describe v11, not v12.
  - `tools/p3_completion_diagnostic.py` keeps v11's import of the gateway cap,
    which is again 32,768.
- `tests/test_archive_request_cap.py` (#122) checks that the manifest default
  follows the gateway; the known caps are unchanged.
- The dated notes that v11 added to `docs/clarification-action.md`,
  `docs/p3-evaluator.md` and `docs/recipe-model-integration.md` stay, each
  followed by a dated v12 note. `docs/count-cue-policy.md` is marked superseded.
- The v11 ruler `tests/test_count_cue_policy.py` keeps its runtime-free checks
  and skips its runtime checks once v11 is superseded, as v9's and v10's
  rulers do. The runtime-free checks are:
  - the readings fixture against the accepted oracles, through the ruler's own
    reference table;
  - the cued files differing only in the 22 listed actions;
  - the v11 registration.

No instruction, schema, validator, execution path, catalog, case, oracle,
panel or gold changes beyond restoring v10's bytes. Old candidates and reports
stay immutable.

## Ruler

`tests/test_v10_restoration_v12.py` is committed failing before the
production edit. It asserts:

- that the live runtime is byte-identical to v10:
  - no `count_policy.py`;
  - the `recipe_model.py` and `gateway.py` digests;
  - every runtime file digest;
  - the semantic identity;
  - the 32,768 cap.

  This check skips once v12 is superseded.
- that the evaluation defaults follow the gateway, with known caps
  `(32768, 40960)` and v1 default responses;
- that the frozen `tests/test_recipe_clarification.py` has its accepted bytes;
- that the v12 registration equals v10 on every identity field, is ordered
  after v11 with v11 as its ancestor, and differs from v11's semantic identity;
- that the v7 through v11 registry files are byte-stable.

`tests/test_archived_evidence_vocabulary.py` (#126) keeps proving that
v11-shaped evidence reads back without the v11 runtime. v11's step-1 report is
re-read after the change.

## Claims and limits

At registration v12 had no observation of its own; v7's recorded runs used
the same wire bytes, and v10 has no run. One confirmation run followed. See
"Confirmation run" below. Any further live observation of v12 needs separate
owner authorization.

The limitations recorded on v7's bytes carry over unchanged:
- `E02_compare.en`: a false clarification on `p33-formal-v2` and
  `p3-dev-bound-meaning-v1`.
- `HA02_C01_headcount_ctr_b01.en`: a wrong action on `p3-holdout-a-v2`.
- `dev-BM6`: fails in all three languages on `p3-dev-bound-meaning-v1`.

v12 makes no claim about the mechanism-probe failures seen only on v8, v9 or
v11. Those are:
- the `dev-MN1.en` and `dev-MN3.en` declines;
- the `dev-MN2` wrong actions;
- v11's step-1 regressions.

## Confirmation run (2026-09-29)

**Decision and authorization.** The owner adopted ADR #125 Option A, so the
count family stops ([#125 #issuecomment-5892107834](https://github.com/cinic0101/grepbit/issues/125#issuecomment-5892107834)).
The owner then authorized one confirmation run on the 24-input control, as
proposed at [#79 #issuecomment-5892145439](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5892145439).
The owner confirmed that the route and serving profile were unchanged. The
agent recorded both at
[#79 #issuecomment-5892176486](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5892176486).

**Run.**
- Run ID:
  `p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--a0316317df34`.
- Source `71d0354`; packet `11be0e6a…`; report `b94d628f…`.
- Tier `dev`, claim `development_observation`.
- The baseline was v7's report on the same panel and route (`d9216e88…`, 20/24).
- The run completed with 24 of 24 client attempts. The requested and returned
  model was `gemma-4-31b` on all 24 inputs.
- Tokens: 93,054 prompt and 4,806 completion. Total call time was 148 s.

**Result: 20/24, the same total as v7, but not an exact per-input
reproduction.**
- 23 of 24 per-input outcomes, actions and clarification shapes equal v7's.
  The non-correct inputs are `E02_compare.en` (`false_clarification`) and
  `dev-BM6` in all three languages.
- `dev-BM6.zh-TW` differs:
  - v7 clarified `count_basis` with four choices (`wrong_action`);
  - v12 answered (`missed_clarification`), using 109 completion tokens where
    v7 used 478.
- The input was the same:
  - all 24 question hashes and prompt-token counts equal v7's;
  - the runtime bytes are the same.
- So on identical input and temperature 0, this input's output changed. The
  cause, model or serving nondeterminism, cannot be told apart from this data.

Pre-registered reading: **not reproduced**, one input. Per the proposal, this
is drift or nondeterminism of unknown cause. It is not a v12 defect, and no
repair follows.

**Comparability.** On this panel, `dev-BM6.zh-TW` has alternated between the
same two failures:

| Candidate | `dev-BM6.zh-TW` outcome |
| --- | --- |
| v7 | four-choice clarification |
| v8 | answered |
| v9 | four-choice clarification |
| v12 | answered |

v8's `dev-BM6.zh-TW` change against v7 is therefore within the variation seen
on identical bytes. v8's counted regression, `dev-BM2.en` (correct to
`false_refusal`), is not contradicted: v12 answered it correctly, as v7 did.
v9's `dev-BM6.en`/`dev-BM6.ja` changes were likewise one failure to another.
Failure-mode comparisons on `dev-BM6` are not reliable from single
observations. The correct/incorrect totals on this panel did reproduce once.
This is one observation on exposed development data, not generalization.

