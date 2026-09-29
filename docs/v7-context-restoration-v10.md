# v7 context restoration v10 (#79)

The owner decided this in chat on 2026-09-29, and the agent recorded it on #79
([decision and analysis](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5885606457)).
The owner selected `direction=restore_v7_and_adr`, labelled
「建議：執行環境回到 v7，並離線起草結構化 decision issue、契約與 ruler」
("Recommended: return the runtime to v7, and draft the structural decision
issue, contract and ruler offline"). No model call is authorized by that
decision.

## Why

v9 ([generic-count checkpoint](generic-count-context-v9.md)) failed its 54/54
development gate at 49/54, and its bounded sequence stopped. v9 is not an
accepted improvement, but it remained the registered current candidate.

v7 is the last registered runtime that passed its development gate; v8 and v9
both stopped at their thresholds. v7's recorded 31B observations are:

- 54/54 on `p3-dev-matrix-compare-first-v2`, its development gate;
- 27/28 on `p33-formal-v2`, a regression-tier observation;
- 17/18 on `p3-holdout-a-v2`, an observed regression against the frozen
  candidate's 18/18;
- 20/24 on `p3-dev-bound-meaning-v1`, the same count as v9.

v7 has no run on `p3-dev-mechanism-probe-v1`.

v10 returns the runtime to v7's exact bytes. It is a restoration, not a new
fix, and makes no count, Compare or other repair.

## Exact identity specification

Candidate `p3-v7-context-restoration-v10` is registered after v9, so its
registry ancestor is v9, because the registry is one linear append-only chain.

Its runtime is byte-identical to `p3-31b-count-context-v7`:

- `grepbit/recipe_model.py` is restored to its bytes at `b332881` (#108), with
  SHA256
  `90f7fd578361e17fcdf9fc1ebf6acbd963095b1394be73b11c7147fef55ab457`. That
  is the file digest v7 registered. No other runtime file has changed since
  v7.
- `CONTEXT_VERSION` returns to `learningops-recipe-context-v3`. Keeping the v7
  version string is deliberate: the recorded repeatability observation (below)
  shows that small context edits can move near-boundary decisions, so the
  restoration keeps every wire byte.
- These fields are equal to v7's:
  - the recipe context, structured output, P1 context and limits;
  - `semantic_identity_sha256`
    `95a9833c186cd26937c3a7382a5c459ae02fda620dd70866f95f830b8e0442bb`;
  - `candidate_sha256`, the wire witnesses and `runtime_files_sha256`.
- Only the registration fields differ: candidate ID, ancestor, ancestor
  SHA256, registered commit and time, and note.

No instruction, schema, validator, execution path, catalog, case, oracle,
panel or gold changes. Old candidates and reports stay immutable. v9's
registered identity stays pinned by its own ruler, whose live-context check
skips once v9 is superseded.

The ruler `tests/test_v7_restoration_candidate.py` is committed failing before
the production edit. It asserts:

- that the live runtime's semantic identity and `recipe_model.py` digest equal
  v7's;
- that the v10 registration equals v7 on every identity field, is ordered after
  v9, and differs from v9's semantic identity;
- that the v7, v8 and v9 registry files are byte-stable.

## Claims and limits

v10 has **no observation of its own**. v7's recorded runs were made with the
same wire bytes. The #79 analysis found that temperature-0 serving on the
`litellm-gemma-4-31b` route gave identical semantic signatures in 65 of 65
repeated observations. So v10 is expected to reproduce v7's outputs while that
route and serving profile are unchanged. That is an inference, not evidence:
no run is recorded under v10, and STATE shows none.

Any live observation of v10 needs separate owner authorization. Limitations
recorded on v7's bytes carry over unchanged:

- `E02_compare.en`, a false clarification on `p33-formal-v2` and
  `p3-dev-bound-meaning-v1`;
- `HA02_C01_headcount_ctr_b01.en`, a wrong action on `p3-holdout-a-v2`;
- `dev-BM6` in all three languages on `p3-dev-bound-meaning-v1`.

Some failures on `p3-dev-mechanism-probe-v1` were observed only on v8 or v9,
whose wire bytes differ from v7's, and are unobserved on v7's bytes. These are
the `dev-MN1.en` and `dev-MN3.en` declines (v8) and the `dev-MN2` wrong actions
(v8 and v9). v10 makes no claim about them.

The structural proposal for count choice sets and comparison roles is a
separate `decision` issue. v10 does not implement it.
