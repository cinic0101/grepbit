# Candidate v22: gate results (#169)

Steps (2), (4) and (5) of the grant
[#169 #issuecomment-5944677551](https://github.com/cinic0101/grepbit/issues/169#issuecomment-5944677551).
- **The candidate.** `p3-overview-basis-v22` (`docs/overview-basis-v22.md`,
  #175) is v21 with the owner's count assumption stated on every executed
  Overview (policy A).
- **The baseline.** v21 (`p3-count-basis-answer-v21`), with three runs on each
  policy A panel version (#172).

**Verdict of the pre-registered gate (`evaluation-gate-v3`): `passed`.**
- **17 fixed:**
  - **15 come from the server's statement:** `dev-BM5`, `dev-CF06`,
    `dev-CF07`, `dev-CF18` and `dev-A2`, three languages each. These are the
    rows the policy A annexes made wrong under v21, as projected.
  - **2 are variance on the same model input, not v22:** `dev-BM2.en`, on
  two panels. The variance may be sampling or a serving-side change. See
    Reading.
- **0 broke, 0 excluded.**
- **The `dev-A1` class** (`dev-A1`, `dev-CF16`, `dev-CF17`, ×3) is
  `unchanged_correct`, as projected. **The policy resolved it, by changing the
  expectation; v22 did not.**

This is a development observation on exposed inputs, not promotion. Most of
the gain is an expectation change (#172) that the runtime now meets. Improving
the grader does not establish product improvement.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v21 baselines (step 2) | From `dev@6bc8209`, the #173 merge, while v21 was current and before #175 merged. Three runs on each new panel version, plus r2 and r3 on `p3-dev-mechanism-probe-v2`. Its r1 is #167's. |
| v22 runs (step 4) | From `dev@95e3e15`, the #175 merge, made after the no-blocker review records on #175. The merged tree equals the reviewed head `a1c6bef`. |
| Where | A clean HTTPS clone of `dev` at those commits. The artifact folders were copied back byte for byte (`diff -rq` identical) for `--record` and the gate. |
| Possible in-flight attempts | 0 in all fifteen runs |
| Grant use | **594 of 594** calls, with no repeat |
| Identities | v22: candidate `375482d4…` (the same model input as v21, v20 and v18), behaviour `6b054075…`. v21: candidate `375482d4…`, behaviour `b6145662…`. |

| Run | Candidate | Calls | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- | --- | --- |
| bound-meaning-v4 r1 | v21 | 24 | `1314985da2c95675954d78eaa4308a67921f037ef247e4c0fcd93b0d0f7b34e4` | `0b2a3009a41ad4274033187d297f8f208cde26c8eb2dec5815ca21acff221ac2` |
| bound-meaning-v4 r2 | v21 | 24 | `d104bc7fd783d4abba1eeb17047bac12cc2d227efa823ab4984a384dd504f3f6` | `fcc5b0d5bfc53ca2c0c19548c5e3366c31f82d20646c4737658f09ee12527ba2` |
| bound-meaning-v4 r3 | v21 | 24 | `14e430baefb801da2a9d4158f2a844827102a707317f645b9de7023cfde98ef4` | `29bf23c87a53351009ba5490e8428f0f9af88428c47b352bab0ae26f48794093` |
| count-fresh-v3 r1 | v21 | 54 | `e72b189ed2674e11ca0d8d136ffae440ba490eee384cbf474160453fbc0fbb61` | `bd502fdd1c96af3541e21230c73f9dac05cc4245cf9eb90aa96f6d9bbd554253` |
| count-fresh-v3 r2 | v21 | 54 | `673d619017c6d673d4b44d747eafea3e9b25f257b2c6f11015cf428c258d8aef` | `b2beeaca06522946c1adc42c29e41445817bbba98fd48c338541e8ed2f0e6e24` |
| count-fresh-v3 r3 | v21 | 54 | `2d462c1e9704524659289768b783e337714f161e78039cbcfd722f9236325ebb` | `1342d7c679487af11c485f21e65318cf3baf47a4cc01b6e399407a35565fee8c` |
| compare-first-v4 r1 | v21 | 54 | `d33c5ff6dbb05b9701719edd71a1d36d9cb40f1473ace35a1dda6c40fcd9661d` | `b1e0fb3893bff4f6994b50a3cb584c541588cebf8a30991bfec619fe214795af` |
| compare-first-v4 r2 | v21 | 54 | `751e522a5efdcb0b65e80d99cb66835e0547111da44982fabc121ab9f09999cd` | `09cdb251499f52afca7dd58bd02ff51387a29c916ce38e7a2de75e9b3405a65a` |
| compare-first-v4 r3 | v21 | 54 | `58471f3343951afc3eedf8ee0db2bd434cf5004838817d424fae1aaaab7ecaf4` | `2ef4c45176b35cbbfca90fd8417f6a95b47f913703ede9209473d7350608dce3` |
| mechanism-probe-v2 r2 | v21 | 22 | `6dd3abd762a72cf6815d9558d0912bee6b22e4f534792bd1cf3168d6b317c21b` | `1d6877af7373158bcfc8845a67568ef19fffbf5ecf5cb4b44dd929215828c3b3` |
| mechanism-probe-v2 r3 | v21 | 22 | `647e4fbfec1f1a90ec50259af0c016fe34bffb2cc6619fc833c7f0d2dedca2f5` | `cf208d7f5124f9815561a967623c96864f4669014d6389faf670c3eafeb57d95` |
| bound-meaning-v4 r1 | v22 | 24 | `8ca15766c8e46ab8caee7e5ff3416c02d2b230a4fd79512cbe28680ae23728d3` | `e7b1e888a18df144d56da19e61234d91909681a616fd27c3ba371e494e10d095` |
| count-fresh-v3 r1 | v22 | 54 | `c742e5c4ae6f51cf12ff16403c029cb61ada8e1763b52861e679a012657880b3` | `28b20d9b890342e61663427b824a06bfb4d5ce0fc19e3d00cd629ebf2ec29a14` |
| compare-first-v4 r1 | v22 | 54 | `ffcf678765807727695ee4545d0dd5e15570236e4fba8a3d1bbb51193f38b0fd` | `04ef4a32fd63da86075b9c65ce4d436b68e93a89ba3452d670b0b98bc5201d82` |
| mechanism-probe-v2 r1 | v22 | 22 | `619df51d45dda083114fbc074a2b1717ba26c9c9eeb985416754a957c92593e2` | `0a1d729b863dd10496a6934f1058159f6ff7b56dff579f56b9e482e2605cf3ac` |

### Order (UTC, 2026-10-02; local file times and GitHub)

| Time | Event |
| --- | --- |
| 02:48:44 | grant recorded (the owner: 「ok」 to at most 594 calls) |
| 03:09:33 to 03:09:37 | v21 baseline packets written at `6bc8209` |
| 03:09:43 to 03:42:55 | the eleven v21 baseline runs |
| 04:27:32 | #175 merged (`95e3e15`), so v22 became current |
| 04:27:52 to 04:27:54 | v22 packets written |
| 04:28:05 to 04:39:54 | the four v22 runs |
| 04:28:25 to 04:28:26 | the eleven v21 baseline rows recorded |
| 04:40:09 | the four v22 rows recorded |

The gate ran after all fifteen rows were recorded.

## Gate

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-overview-basis-v22 \
  --baseline-candidate p3-count-basis-answer-v21 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/169#issuecomment-5944677551 \
  --panels p3-dev-bound-meaning-v4 p3-dev-count-fresh-v3 p3-dev-matrix-compare-first-v4 p3-dev-mechanism-probe-v2
```

**The gate used `evaluation-gate-v3`** with run index `09d5361e`.
- **Baseline.** Each panel's baseline is three v21 runs. On
  `p3-dev-mechanism-probe-v2`, these are #167's r1 and this grant's r2 and r3.
- **Sentinels.** Every input was sentinel-assessed.

| Panel | Fixed | Broke | Excluded | Unchanged correct | Unchanged wrong | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v4` | 4 | 0 | 0 | 20 | 0 | passed |
| `p3-dev-count-fresh-v3` | 9 | 0 | 0 | 45 | 0 | passed |
| `p3-dev-matrix-compare-first-v4` | 3 | 0 | 0 | 51 | 0 | passed |
| `p3-dev-mechanism-probe-v2` | 1 | 0 | 0 | 21 | 0 | passed |
| **Overall** | 17 | 0 | 0 | 137 | 0 | **passed** |

- **Fixed:**
  - `p3-dev-bound-meaning-v4`: `dev-BM2.en` and `dev-BM5` ×3.
  - `p3-dev-count-fresh-v3`: `dev-CF06`, `dev-CF07` and `dev-CF18` ×3.
  - `p3-dev-matrix-compare-first-v4`: `dev-A2` ×3.
  - `p3-dev-mechanism-probe-v2`: `dev-BM2.en`.
- **The `dev-BM2.en` baseline class.** It is `stable_wrong` on both panels:
  v21 declined it in all three runs of each.

Annex-aware index counts:

| Panel | v21 r1 | v21 r2 | v21 r3 | v22 |
| --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v4` | 20/24 | 20/24 | 20/24 | 24/24 |
| `p3-dev-count-fresh-v3` | 45/54 | 45/54 | 45/54 | 54/54 |
| `p3-dev-matrix-compare-first-v4` | 51/54 | 51/54 | 51/54 | 54/54 |
| `p3-dev-mechanism-probe-v2` | 21/22 (#167) | 21/22 | 21/22 | 22/22 |
| **Total** | 137/154 | 137/154 | 137/154 | 154/154 |

## Reading

- **The statement alone made the 15 policy fixes.**
  - **The actions did not change.** On each of the 15 rows, v22's validated
    action is byte-identical to all three v21 runs. The readings are
    `booked_seats` (BM5, CF06, CF07) and `none` (CF18, A2).
  - **Only the statement changed.** v22's server stated the basis, and v21's
    stated none.
- **The live statements match the contract.** Over the 154 v22 rows, a row
  carries `count_assumption` exactly when it is one of these (75 rows):
  - an answered Overview without an error: `booked_seats` 9, `none` 6,
    `unresolved` 39;
  - the server answer to a model `count_basis` clarification: 21.

  No Compare, Breakdown, decline or other clarification row states it. A named
  unavailable count did not occur in these runs, so the server-decline path
  (v16) still never ran live.
- **150 of 154 v22 actions equal all of v21's baseline actions.** The four
  that differ:
  - **`dev-BM7.ja` and `dev-CF15.ja`:** a model `count_basis` clarification
    with the same choices under different local choice ids. v22 used
    `basis_seats`/`basis_accounts`; v21 used `c1`/`c2` in all three runs. The
    server answers both the same way, and both stay `unchanged_correct`.
  - **`dev-BM2.en` on two panels:** v21 declined it in every run; v22
    answered it, with a request that carries no count reading. See the next
    item.
- **`dev-BM2.en` is a variance fix, not v22's.**
  - **v22 cannot have caused it.** v22's change acts only after the model's
    action, and only on an executed Overview. The model input is
    byte-identical to v21's.
  - **The question** is "Against February 2026 as the reference, how did the
    overall confirmed booking amount in March change?".
  - **Its observations on model input `375482d4…`** (run end times, UTC, one
    route), continuing #167's table:

    | Date | Time (UTC) | Candidate (behaviour) | Outcome |
    | --- | --- | --- | --- |
    | 2026-10-01 | 03:42 to 13:15 | v18 | answered ×5 |
    | 2026-10-01 | 15:55, 16:04 | v20 (v18's behaviour) | declined ×2 |
    | 2026-10-01 | 16:27, 16:36 | v21 | declined ×2 |
    | 2026-10-02 | 03:11 to 03:16 | v21 (bound-meaning-v4 r1 to r3) | declined ×3 |
    | 2026-10-02 | 03:41, 03:42 | v21 (mechanism-probe-v2 r2, r3) | declined ×2 |
    | 2026-10-02 | 04:30, 04:39 | v22 | answered ×2 |

  - **The counts.** It was answered 7 times and declined 9 times. The
    declines run unbroken from 15:55 on 2026-10-01 to 03:42 on 2026-10-02,
    with answers on either side.
    - **What this cannot tell apart:** a serving-side change from sampling.
  - **A limit of the gate.** Within v21's behaviour identity, all three
    baseline runs on each panel declined it, and all of them fell inside the
    decline stretch:
    - `p3-dev-bound-meaning-v4`: 03:11 to 03:16;
    - `p3-dev-mechanism-probe-v2`: #167's 16:36, then 03:41 and 03:42.

    So the three-run rule (#168) classed it `stable_wrong`. The gate pools by
    behaviour, so it cannot see v18's earlier answers on the same model input.
    A time-clustered flaky input can still pass as stable. The owner's
    decision on this is tracked in #177.
- **The `dev-A1` class stayed `unchanged_correct`.** v21 already stated the
  basis for its `unresolved` readings. The policy A expectation (#172), not v22,
  resolved it.

## Claims and limits

- **What this shows.** On 31B, v22's server statement made every answered
  Overview on these four panels carry the basis. The policy A panel versions
  expect exactly that, and the 15 rows that v21 failed under them now pass.
  Nothing broke under the gate.
- **What carries most of the change.**
  - **Expectation:** the policy A panel versions (#172). Under the
    predecessors, these 15 rows were already correct for v21.
  - **What v22 adds:** consistency between the server's statement and that
    expectation. It changes no model reading.
  - **What this does not establish:** the gain is not evidence of a better
    model or of better product answers.
- **Observations.** One v22 run and three v21 runs per panel, on one route,
  with exposed, mostly agent-authored inputs. This is not generalization
  evidence. It makes no claim about holdout or formal panels, Bedrock or
  promotion. Formal and holdout panels predate policy A, so a promotion claim
  needs a new formal panel (#169).
- **Status.** v22 stays the registered current candidate.
- **Untested live.**
  - **The server-decline path (v16) and the count ablation under v22.** The
    ablation does not record the statement (#174).
- **Budget.** The grant is spent at 594 of 594 calls.
- **Raw reports** stay local under `.artifacts/v22-baseline-20261002/` and
  `.artifacts/v22-runs-20261002/`. The index keeps their digests.
