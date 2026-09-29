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

Note (2026-09-29): this paragraph was written before v12 had a probe run.
Four more authorized runs followed the confirmation run; see "Noise
measurement" below. In both of v12's probe runs, `dev-MN1.en`, `dev-MN3.en`
and `dev-MN2` in all three languages are wrong, so these failures are not
specific to v8, v9 or v11.

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
  cause is unknown. It may be drift, such as a serving change between runs,
  or nondeterminism in the model or serving; this data cannot tell them apart.
  The gateway policy is operator-attested only.
- Raw output length also changed on three other inputs, with the same outcome
  and parsed action. Completion tokens, v7 → v12:

  | Input | v7 | v12 |
  | --- | --- | --- |
  | `dev-BM4.en` | 430 | 428 |
  | `dev-BM4.ja` | 404 | 430 |
  | `dev-BM7.ja` | 252 | 250 |

  So the output varied on 4 of 24 identical inputs, and the parsed result
  changed on 1.

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

Other v9 changes:
- Step 1, on the mechanism probe with the v8 probe as baseline, shows the same
  `dev-BM6.zh-TW` flip in reverse, from an answer to the four-choice
  clarification.
- Step 3's regressions are on inputs not on this panel, so this run gives no
  evidence about them. They are `dev-A4` zh-TW/en and `dev-C1` in all three
  languages.

v11's step 1 (#124) ran on `p3-dev-mechanism-probe-v1`, with v9 as baseline.
There, `dev-BM6.zh-TW` changed from the four-choice clarification to an answer
(`missed_clarification`). That is the same flip seen here on v7's identical
bytes, so this one change cannot be attributed to v11 from a single
observation. The typed reading v11 returned for that input, a bound
`booked_seats` count ([count-cue-policy.md](count-cue-policy.md)), is what the
model output under v11; whether v11 caused the answer is not established.

This run bears on v11's other step-1 correctness changes as follows:
- `dev-BM6.en` and `dev-BM6.ja` were not correct on the v7, v8, v9 or v12 runs
  of this panel. `E02_compare.en` was a `false_clarification` on all four. So
  v11's fixes of these three inputs are outside the variation seen here.
- These inputs are not on this panel, so this run gives no evidence about their
  changes:
  - the `dev-MN*` inputs: v11's `dev-MN1`/`dev-MN3` regressions and its
    `dev-MN2` fixes;
  - `dev-MC4.en`, which v11 fixed;
  - `dev-A3.en`, a v11 regression.

  Because the cause may be drift, a change between runs cannot be ruled out
  for them.

Failure-mode comparisons on `dev-BM6` are not reliable from single
observations. The correct/incorrect totals on this panel did reproduce once.
This is one observation on exposed development data, not generalization.


## Noise measurement (2026-09-29)

**Decision and authorization.** The owner chose noise measurement plus
offline replay tooling
([#79 #issuecomment-5892696354](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5892696354));
the tooling is evaluation v2 ([replayable observations](replayable-observations.md), #129).
The four runs were proposed at
[#79 #issuecomment-5894206747](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5894206747)
and authorized, with the route, provider and profile confirmed unchanged, at
[#79 #issuecomment-5899868983](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5899868983).

**Runs.**
- Source is `af3a92d`. All four are evaluation v2 runs of v12's bytes
  (`6d707b8d…`), tier `dev`, claim `development_observation`.
- They ran in this order, each with its own packet, envelope and slot:

  | Run | Panel | Result | Report |
  | --- | --- | --- | --- |
  | control `--r1` | `p3-dev-bound-meaning-v1` | 20/24 | `a78d2c68…` |
  | probe `--r1` | `p3-dev-mechanism-probe-v1` | 11/22 | `e40babc9…` |
  | control `--r2` | `p3-dev-bound-meaning-v1` | 20/24 | `51283dbf…` |
  | probe `--r2` | `p3-dev-mechanism-probe-v1` | 11/22 | `432b797b…` |

- There were 92 of 92 client attempts. No run stopped, and nothing was retried
  or rerun. The requested and returned model was `gemma-4-31b` on every input.
- Upstream inference attempts are unknown.

**Result: no input varied among the observations from the confirmation run
onward.**
- Control: the confirmation run (about 14:23Z, source `71d0354`) and both
  control runs (about 22:00Z, source `af3a92d`) are identical on every one of
  the 24 inputs, about 8 hours apart. That covers the outcome, the parsed
  signature and the completion-token count. For `--r1` and `--r2`, the
  persisted validated action is identical too.
- Raw completions are not kept, so identical raw text is not established.
- Probe: the two runs are identical on every one of the 22 inputs in the same
  way. Both come from one window of about 13 minutes.
- `--aggregate` reports:

  | Panel | Runs | stable_correct | stable_wrong | flaky | insufficient |
  | --- | --- | --- | --- | --- | --- |
  | control | 4 (v7, v12, `--r1`, `--r2`) | 20 | 4 | 0 | 0 |
  | probe | 2 | 11 | 11 | 0 | 0 |

- The only difference across the four control observations is still v7's
  `dev-BM6.zh-TW` clarification: one failure against another, with
  completion-token changes on three other inputs. v7 ran at about 03:30Z,
  about 11 hours before the confirmation run.
- `--replay` of each v2 report at `af3a92d` made 0 model calls. It gave
  `replayed_same` on all 92 rows and 0 comparison changes.
- These are counts over 2–4 observations at temperature 0 on exposed
  development data. They are not probabilities.

**Reading.**
- From the confirmation run onward, the same control bytes gave the same
  graded results, parsed signatures and completion-token counts.
- The one observed change, v7 against the later runs of identical bytes, came
  between sessions. It is consistent with drift between sessions, such as a
  serving change, rather than per-call sampling. The cause remains unknown.
- Between-session variation was not measured on the probe.
- Against v12's measured result as the baseline, the per-input changes of
  earlier candidates are as follows (a fix is wrong → correct, a regression is
  correct → wrong). The count cue policy reports v11 against v9 instead
  (7 fixed, 7 new regressions), which is a different baseline.

  | Candidate and panel | Fixed | Broke |
  | --- | --- | --- |
  | v8, control | none | `dev-BM2.en` |
  | v8, probe | none | `dev-MC3.en`, `dev-A3.en`, `dev-BM2.en` |
  | v9, probe | `dev-MN1.en`, `dev-MN3.en` | `dev-MC3.en` |
  | v11, probe | `E02_compare.en`, `dev-MC4.en`, `dev-BM6.en`/`.ja`, `dev-MN2` ×3 | `dev-MC3.en`, `dev-A3.en`, `dev-MN1.zh-TW`/`.ja`, `dev-MN3.zh-TW`/`.ja` |

  v9 made no correctness change on the control.
- These changes are far larger than the one between-session change seen on
  identical control bytes. They are therefore consistent with each
  candidate's byte change.
- Between-session drift still cannot be excluded for any single input: those
  candidates ran in earlier sessions, and probe drift between sessions was not
  measured.

This supersedes the "Confirmation run" section's statement that the run
gives no evidence about the `dev-MN*`, `dev-MC4.en` and `dev-A3.en` changes.
It remains a development observation, not generalization.
