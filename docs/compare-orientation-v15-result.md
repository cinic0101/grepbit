# Candidate v15: gate result (#142)

Steps (1), (3) and (4) of the owner's grant
[#142 #issuecomment-5907593990](https://github.com/cinic0101/grepbit/issues/142#issuecomment-5907593990)
for candidate `p3-compare-orientation-v15` (`docs/compare-orientation-v15.md`, #144).
The baseline is v12's bytes on the same panels: the two v12 runs of #139 plus
the v14 sentinel below.

**Pre-registered verdict: `passed`, on both panels.** This is a development
observation on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v14 sentinels (step 1) | From `dev@e57b848` (the #143 merge), while v14 was current: 24/24 and 22/22 calls, complete |
| v15 runs (step 3) | From `dev@79a5b74` (the #144 merge, after its no-blocker review): 24/24 and 22/22 calls, complete |
| Possible in-flight attempts | 0 in all four runs |
| Grant use | **92 of 92** calls, no repeat |
| Candidate SHA256 | v15 `5ba892e9c024754d6218cc0fbf05415e56960dc57f557776f1b400575f1c5e95`; baseline v12 bytes `6d707b8dc2d58915f2a794d97404faf85be72ab5ac7e27545bd2d9d0c428e536` |

| Run | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- |
| v14 sentinel, bound-meaning | `5dba22db070c37edc05db3fac905e0f6bd8442ce9a0ec320cd950a5e10c60800` | `9db12ca858968ad64775ebccf0809611804222eeb05e5e88858e9b3ea57acad2` |
| v14 sentinel, mechanism-probe | `72319e3054b277ff8cdbd55086e44e1970dc86d287e2b6533a718c8f720b2e94` | `9fd6e886fa7df1981b7f8d8604dfc3c74b43636d07367d1048c8e0fe5ba6cc28` |
| v15, bound-meaning | `b31d1fcf0c1c060d2eec2cc5b26a28f2e406eb317f7c9f411e5f4d9535d8aadf` | `f5352b7160d61d78f079e6cbd6cb77d777ff6fff02eb85720cef707ad45c9cde` |
| v15, mechanism-probe | `00b63d2da0a26e3db14715e4f3d4929a17a0848e6fa7d001d76f74206d775d56` | `99f4da04a4be570c48419ef165a65f7c3bb9861c03e59ecffd449a0b074c11e0` |

**Recording and order.**
- Grant step (1) reads "recorded under this reference, while v14 is current".
  Its next sentence reads "the v14 sentinels and v15 must both be recorded
  under this reference".
- The sentinels were *run* while v14 was current, and all four index rows
  carry this grant reference. But the rows were *written* together, after the
  v15 runs, at 14:27:33Z. v15 had been current since 14:19:23Z.
  - This differs from the v13 cycle, where #139 recorded the baseline before
    the candidate PR.
  - The gate does not limit the recording order (`docs/candidate-gate.md`).
- **The timeline**, from the local packet and report file times and GitHub:

  | Time (UTC) | Event |
  | --- | --- |
  | 13:05:09 | #143 merged, so v14 became current |
  | 13:05:35 | sentinel packets written |
  | 13:09 and 13:13 | sentinel reports finished |
  | 14:18:57 | #144's no-blocker review record posted, verified on GitHub before step 3 |
  | 14:19:23 | #144 merged, so v15 became current |
  | 14:19:51 | v15 packets written |
  | 14:23 and 14:27 | v15 reports finished |
  | 14:27:33 | all four index rows recorded |

- **What this rests on.** The reports carry no wall-clock time, and the
  committed index times are 0.3 s apart. So "the sentinels ran before v15 was
  registered" rests on the local file times and on the rule that a packet can
  be built only for the current candidate. No digest-pinned field shows it: the
  sentinel packets name `p3-v12-restoration-v14` and `dev@e57b848`, where v15
  did not exist.

**The sentinels match v12.** Each v14 sentinel equals both v12 runs of #139
input for input in outcome, `actual_signature` and action, with zero
differences. So no session drift was observed on these outcomes.
- Validated actions differ only in clarification choice ids, for example
  `march_current` and `March_current`. The two v12 runs differ in the same way.

Annex-aware index counts:

| Panel | v12 bytes (3 runs, each) | v15 (1 run) |
| --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 20/24 | 21/24 |
| `p3-dev-mechanism-probe-v2` | 7/22 | 10/22 |

## Gate

The command:

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-compare-orientation-v15 \
  --baseline-candidate p3-v12-restoration-v14 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/142#issuecomment-5907593990 \
  --panels p3-dev-bound-meaning-v2 p3-dev-mechanism-probe-v2
```

It gave `evaluation-gate-v1`, verdict `passed`, run index `bb9a4500`. Each
panel's baseline is three v12-bytes runs, the v14 sentinel included, and every
input was sentinel-assessed.

| Panel | Fixed | Broke | Unchanged correct | Unchanged wrong | Excluded or unassessed | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 1 | 0 | 20 | 3 | 0 | passed |
| `p3-dev-mechanism-probe-v2` | 3 | 0 | 7 | 12 | 0 | passed |

- **Fixed.** These were v12's three stable-wrong Compare inputs, each a false
  `comparison_roles` clarification on v12 and now answered: `E02_compare.en`
  (on both panels), `dev-MC2.en` and `dev-MC4.en`. That is 4 rows and 3
  distinct inputs.
- **Broke:** none.
- **Unchanged wrong.** The count inputs, which v15 was not designed to change:
  - `dev-BM6` ×3 on both panels: silent answers, annex-wrong.
  - `dev-MN1`–`MN3` ×3: false clarifications, except `dev-MN1.en`, a silent
    answer, and `dev-MN3.en`, a decline, as on v12.

## Reading

- **Every Compare row is correct.** There are 22 Compare rows on the two
  panels, 20 distinct inputs, since `E02_compare.en` and `dev-BM2.en` are on
  both. All 22 are correct on v15. The model returned `stated` on all 19
  directed-comparison rows (17 distinct inputs), and they executed. It returned `unresolved` on
  `dev-BM4` ×3, the symmetric comparison, and the server built the expected
  `comparison_roles` clarification.
  - This checks the typed reading against the orientation each oracle implies,
    the mapping `docs/reading-and-routing-evidence.md` used. It is a post hoc
    tally, not a gate layer.
- **The diagnostic reading carried over.** In the reading diagnostic's fresh
  variant, 31B read the orientation of the same Compare questions correctly
  22/22, in a separate call, on the v1 panels. The replayed variant gave 18/22. With the
  decision moved to code, the production call now reads it correctly 22/22 on
  the same inputs.
- **One count input moved within wrong.** `dev-BM6.zh-TW` went from a false
  clarification on all three v12-bytes runs to a silent Overview answer
  (frozen-correct, annex-wrong) on both panels.
  - Its class stays `unchanged_wrong`.
  - This input is already recorded as switching between two wrong outcomes
    across sessions (`docs/reading-and-routing-evidence.md`). One run cannot
    separate that from an effect of v15's text change.
  - Every other input kept its v12-bytes outcome, the three fixed Compare
    inputs aside.
  - The v13 lesson was that a change to the model-facing text also moved
    Compare. Here no correct input broke.

## Claims and limits

- **Scope.** One run per panel, one route, exposed and mostly agent-authored
  inputs. It is not fresh generalization evidence, and it makes no claim about
  holdout or formal panels, Bedrock (which fails closed on v15) or promotion.
- **Unmeasured.** `p3-dev-matrix-compare-first-v2`, which holds the `dev-C1`
  and `dev-D8` near-misses and 54 inputs, was not run. It needs its own owner
  authorization.
- **The count family was not designed to change.** v12's 12 wrong count inputs
  (15 rows) stay wrong. `dev-BM6.zh-TW` moved between two wrong outcomes (see
  Reading). The count-rule families `dev-BM5`, `BM7` and `BM8` stay correct.
  Applying the same read-then-decide pattern to counts would be a further fix
  on that family and needs its own owner decision.
- **Budget.** Grant #142's 92 calls are spent, so any further run needs new
  owner authorization.
- **Raw reports** stay local under `.artifacts/v15-sentinel-20260930/` and
  `.artifacts/v15-candidate-20260930/`. The index keeps their digests.
