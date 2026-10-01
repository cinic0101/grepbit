# Candidate v19: gate results (#158)

Steps (2), (2b), (4) and (5) of the grant
[#158 #issuecomment-5927141003](https://github.com/cinic0101/grepbit/issues/158#issuecomment-5927141003)
and its amendment
[#issuecomment-5932057637](https://github.com/cinic0101/grepbit/issues/158#issuecomment-5932057637).
The candidate is `p3-count-basis-answer-v19` (`docs/count-basis-answer-v19.md`,
#160), and the baseline is v18 (`docs/count-scope-v18.md`).

**Verdict of the pre-registered gate: `regression`** (overall, and on
`p3-dev-bound-meaning-v3` and `p3-dev-mechanism-probe-v2`).
- **21 fixed:** `dev-C1` ×3, `dev-BM7` ×3, and the fresh panel's `dev-CF11` to
  `dev-CF15` ×15.
- **2 broke:** `dev-BM2.en` on each of the two panels that contain it.

A regression is a stop. No run is repeated, and v19 is to be reverted by a
further PR (the grant's verdict term). The revert needs an owner decision
first, because it restores a frozen source. This is a development observation
on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v18 sentinels (step 2) | From `dev@ba7e556` (the #159 merge), while v18 was current |
| v18 baseline runs (step 2b) | From `dev@ba7e556`, in a second clean HTTPS clone, under the amendment. Repetition 2 on the two panel versions that had only the sentinel. |
| v19 runs (step 4) | From `dev@250fc89`, the #160 merge. That merge came after the round-2 no-blocker review record (#160 #issuecomment-5931964878) and the owner's confirmation of the frozen-test diff (#issuecomment-5931564694). The reviewed head `8807876` is the merged head. |
| Where | Clean HTTPS clones of `dev` at those commits. The artifact folders were copied back byte for byte (`diff -rq` identical) for `--record` and the gate. |
| Possible in-flight attempts | 0 in all ten runs |
| Grant use | **386 of 386** calls (308 in the grant and 78 in the amendment), with no repeat |
| Candidate SHA256 | v19 `510dbdad9749f77fdf542056889cf178c9d7c22945e4368c7c8419b125ed0230`; baseline v18 `375482d4ca8f9f9714c913fa5cbc3d968c16e1e9a2bc1dcf383c7bcde0b90a16` |

| Run | Candidate | Calls | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- | --- | --- |
| bound-meaning-v3 r1 (sentinel) | v18 | 24 | `33e5588cf7864a2e8b1c46d8fab962908d2d8821957e2178b23e83a7496fd145` | `d02465ec839646ab66af85816ef9df69a81cfab7a53ed67a0b0b6cfa7ed9b42f` |
| count-fresh-v2 r1 (sentinel) | v18 | 54 | `270eb953b67c5879a36b0645b2a3b1c04c120157e572df6e7fe46d6f5220481a` | `84b77efdd16ed83a11413f1f8d254c55a77b533d2a709a51cf7e5dbc4a19ef7b` |
| compare-first-v3 r2 (sentinel) | v18 | 54 | `3bdb1d2ee5ea313df3d30fe5d6e2657313a69621e23c8c706b6c4c35da1c4210` | `821d1466e9fd2d65cc0418964037e6d4035b54cc4c88a660c7e59e6256080628` |
| mechanism-probe-v2 r2 (sentinel) | v18 | 22 | `bfe5f8cc56ad06704e62df98248970ca0908f585425799e27812fde000c63136` | `f1eec804a58250926b5295f42079d05c07aff0179758749ff76475490e421598` |
| bound-meaning-v3 r1 | v19 | 24 | `41a51aeb3955b17b96a2a3662d28a3df51e829e91ac115f8fe6998b69f584638` | `4f970ebba3c5abaadf4fe6c45e736a24d3d85194d61d9cca71a92c21f2d2608c` |
| count-fresh-v2 r1 | v19 | 54 | `a62eb57af1f2735edcea09ebc0d7ad4a14f99302168201425f999b42981fefc0` | `78f5b015db82b2f7df5996280afbff7869098f4aa3b8f93c8c939e0b50585327` |
| compare-first-v3 r1 | v19 | 54 | `04caa5fdbfae77232bc9ad967545154e927bc271c8219ed4388a1fab15f9d5dd` | `e73b0954dce269131f912b303d0188be062173e42d19578989ec3beab2a73b36` |
| mechanism-probe-v2 r1 | v19 | 22 | `704996b44792c649eecf66840b99f3613013a8ff7223c469672fa9e1a06c5aa5` | `24afb8d85aed01e34b9cfd2b7adba3d117712725edaa4b95c4bb571ff0d6a926` |
| bound-meaning-v3 r2 (step 2b) | v18 | 24 | `207d3eb8e736a166907e4a08ea48e62e2f2b96d97e0c3626bbf78c3c25ed9985` | `554e7cb6fbf98f8ab287833bb5112b0dac06e1ea99d00b6a54b2ef44a8cb35a5` |
| count-fresh-v2 r2 (step 2b) | v18 | 54 | `fded5fbeeb587ef36c3d2df72e9ec70b0ecbe068acedee4f9a4d86fb7d1d87c9` | `72605aa2f09e7ee491e129f81c3c35b84bddd27e2148d61dcdf6c199910ab4b3` |

The index rows carry the grant reference: the original grant for the
sentinels and the v19 runs, and the amendment for the step-(2b) runs.

### Order (UTC; local file times and GitHub)

| Time | Event |
| --- | --- |
| 07:49:00 | grant recorded (the owner: 「ok 同意 with 308 次」) |
| 08:28:29 | #159 merged (`ba7e556`) |
| 08:28:53 to 08:40:28 | v18 sentinel packets written and the four runs finished |
| 12:33:51 | the owner's confirmation of the frozen-test diff recorded on #160 |
| 12:58:34 | #160 round-2 review record (no blocker) posted, verified on GitHub |
| 12:59:35 | #160 merged (`250fc89`), so v19 became current |
| 13:00:32 | the step-5 gap (#160 review L-C) and options A/B posted on #158, before any v19 call |
| 13:01:07 | v19 packets written and bound |
| 13:01:14 to 13:03:20 | v19 `bound-meaning-v3` run (its report holds the `dev-BM2.en` break and the `dev-BM7` fixes) |
| 13:03:20 to 13:07:37 | v19 `count-fresh-v2` run |
| 13:04:25 | the owner's choice and the amendment recorded (78 calls) |
| 13:05:27 | step-(2b) packets written and bound to the amendment |
| 13:07:37 to 13:10:48 | v19 `compare-first-v3` run |
| 13:10:48 to 13:12:36 | v19 `mechanism-probe-v2` run; step (4) complete |
| 13:12:54 to 13:19:14 | the two step-(2b) runs |
| 13:13:30 to 13:13:39 | the sentinel and v19 rows recorded |
| 13:14:24 | **an early gate on the two panels that were already measurable** (see below) |
| 13:19:34 | the step-(2b) rows recorded and the four-panel gate run |

**Order deviation, disclosed.** The amendment put step (2b) before step (5).
The agent ran the gate on `p3-dev-matrix-compare-first-v3` and
`p3-dev-mechanism-probe-v2` at 13:14:24, while step (2b) was still running. It
already showed `regression`.
- **Why it changes nothing.** Step (2b) adds baseline runs only to the other
  two panels, so it cannot change those two panels' classes.
- **Which verdict counts.** The four-panel gate below is the pre-registered
  verdict. Its rows for these two panels equal the early gate's.

**Option B was chosen after one v19 result existed, disclosed.** The first v19
run (`bound-meaning-v3`) finished at 13:03:20, before the amendment (13:04:25)
and the step-(2b) binding (13:05:27).
- **What the agent saw.** By the agent's own account, which no artifact can
  confirm, it had then seen only folder listings and the run sequence's start
  line, not any v19 report or score.
  - The first v19 content it read was the run sequence's completion lines
    after 13:12:36, which hold call counts and status only.
  - The first scores it saw were in the `--record` output at 13:13:38, after
    the step-(2b) runs had started (13:12:54).
- **The verdict does not depend on B.** The `p3-dev-mechanism-probe-v2` break
  alone gives `regression`, and option B only made the gate measure two more
  panels.
- **The amendment's order held for the runs.** Step (2b) started after step
  (4) completed.

## Gate

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-basis-answer-v19 \
  --baseline-candidate p3-count-scope-v18 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/158#issuecomment-5927141003 \
  --panels p3-dev-bound-meaning-v3 p3-dev-count-fresh-v2 p3-dev-matrix-compare-first-v3 p3-dev-mechanism-probe-v2
```

The gate used `evaluation-gate-v1` with run index `f8b87cef`.
- **Baseline.** Each panel's baseline is two v18 runs:
  - on `p3-dev-bound-meaning-v3` and `p3-dev-count-fresh-v2`, the sentinel (r1) and the step-(2b) run (r2);
  - on the other two, #152's r1 and the sentinel (r2).
- **Coverage.** Every input was sentinel-assessed. No input was excluded.

| Panel | Fixed | Broke | Excluded | Unchanged correct | Unchanged wrong | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v3` | 3 | 1 | 0 | 20 | 0 | **regression** |
| `p3-dev-count-fresh-v2` | 15 | 0 | 0 | 33 | 6 | passed |
| `p3-dev-matrix-compare-first-v3` | 3 | 0 | 0 | 48 | 3 | passed |
| `p3-dev-mechanism-probe-v2` | 0 | 1 | 0 | 21 | 0 | **regression** |
| **Overall** | 21 | 2 | 0 | 122 | 9 | **regression** |

- **Fixed:**
  - `dev-BM7` ×3;
  - `dev-CF11`, `dev-CF12` (the user's own undecided choice, revised by ADR #158) and `dev-CF13` to `dev-CF15` (doubt about the system's basis), ×3 each;
  - `dev-C1` ×3.
- **Broke:** `dev-BM2.en`, on both panels.
- **Unchanged wrong:** `dev-CF16` and `dev-CF17` ×3 (no-count overviews), and `dev-A1` ×3. They are the `dev-A1` class, out of scope (#158).

Annex-aware index counts:

| Panel | v18 first run | v18 second run | v19 r1 |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v3` | 21/24 | 21/24 | 23/24 |
| `p3-dev-count-fresh-v2` | 33/54 | 33/54 | 48/54 |
| `p3-dev-matrix-compare-first-v3` | 48/54 | 48/54 | 51/54 |
| `p3-dev-mechanism-probe-v2` | 22/22 | 22/22 | 21/22 |
| **Total** | 124/154 | 124/154 | 143/154 |

## Reading

- **The fixes come from the runtime rule.**
  - **On every fixed row,** v19's model action is its own `count_basis`
    clarification, as on v18, and the server answered it with booked seats
    and the stated assumption. The offline prediction in the contract
    (`dev-C1` ×3 and the fresh panel's B ×9 become correct, the D rows stay
    correct, `dev-A1` and the O rows stay wrong) held on every row.
  - **The revised oracles count too.** The D and `dev-BM7` rows were already
    v18 clarifications; under the revised oracles, the server's answer is
    what makes them correct.
- **The model's actions barely moved.**
  - **Byte-identical: 142 of 154** v19 validated actions equal v18's
    sentinel action.
  - **Same kind of action: 10 more** keep the same kind of action.
    - **Nine on `p3-dev-count-fresh-v2`.** They differ only in local choice
      ids, except `dev-CF13.ja`, which went from two to four choices. It is
      still a `count_basis` clarification and is still answered.
    - **`dev-C3.en`** (a `center` clarification) differs in ids only.
    - **The graded outcome** of the nine count-fresh rows changed, because
      the server answered them.
  - **One decision changed:** `dev-BM2.en`, on the 2 rows of the two panels
    that contain it (below). So 142 + 10 + 2 = 154.
- **`dev-BM2.en` broke.**
  - **The question:** "Against February 2026 as the reference, how did the
    overall confirmed booking amount in March change?" It is a Compare of an
    amount, with no count.
  - **The change:** v18 answered it in all five v18 observations (#152's
    `p3-dev-bound-meaning-v2` and `p3-dev-mechanism-probe-v2` r1, the two
    sentinels and the step-(2b) run). v19 returned the model's own decline
    (`{"outcome":"declined"}`) on both panels, a `false_refusal`.
  - **The cause is not established;** the raw model reasoning is not retained.
- **Close to deterministic.**
  - **v18 repeated itself:** between its two runs on the two new panel
    versions, 76 of 78 validated actions are byte-identical, and 78 of 78
    outcomes.
  - **v19 too:** its five inputs shared by `p3-dev-bound-meaning-v3` and
    `p3-dev-mechanism-probe-v2` gave identical actions, including the decline.
  - **v18 still answered it after v19 declined it.** The step-(2b) v18 run
    (13:12:54 to 13:15:04) answered `dev-BM2.en` after v19 had declined it,
    which argues against a route-side change during the session.
  - **What follows.** The flip is most likely an effect of the changed
    model-facing context, not sampling noise. v19 added one sentence to be
    registrable, and the context version string changed with it (v6 to v7).
    The gate doc records the same kind of effect for v11 (7 fixed, 6 broke).
  - **Not tested.** Which part of the change moved it.
  - **How independent v19's two declines are.** They are two observations of
    the same question bytes in one session. If serving is close to
    deterministic, they are not independent, so the decline is shown to
    repeat, not to be stable.
- **Still wrong:** the `dev-A1` class (`dev-A1` ×3, `dev-CF16`, `dev-CF17`),
  which reads a spurious assumption on a no-count overview.

## Claims and limits

- **What this shows.** On 31B, the server answering a model `count_basis`
  clarification turned all 21 such rows into correct answers. On these four
  panels, under the revised oracles and with one v19 run, it moved no
  other count reading. The context change made for registrability (the added
  sentence and the version string) coincided with one unrelated decline. That
  decline repeated on both v19 observations, and the input was stable on v18
  (5 of 5).
- **Observations.** One v19 run and two v18 runs per panel, on one route, with
  exposed, mostly agent-authored inputs. The fresh panel is regression data
  after #157. This is not generalization evidence. It makes no claim about
  holdout or formal panels, Bedrock or promotion.
- **v19 is not accepted.** It stays the registered current candidate only until
  the revert PR. The revert needs an owner decision, because it restores the
  frozen `tests/test_recipe_clarification.py` and its pin (a mandatory stop),
  as v12 did (`docs/v10-restoration-v12.md`). The options are on #158.
- **Untested live.** The server-decline path (v16) still never ran.
- **Budget.** The grant is spent at 386 of 386 calls.
  - **How the 78-call cap was confirmed.** The owner's words delegated the
    A/B choice to the agent. The 78 more calls and the 386 total were stated
    in the options message the owner answered, not in the owner's own words.
    The amendment records this, and the owner is asked to confirm it.
- **Raw reports** stay local under `.artifacts/v19-sentinel-20261001/`,
  `.artifacts/v19-candidate-20261001/` and `.artifacts/v19-baseline-20261001/`.
  The index keeps their digests.
