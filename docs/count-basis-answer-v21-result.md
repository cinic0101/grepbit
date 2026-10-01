# Candidate v21: gate results (#164)

Steps (2), (4) and (5) of the grant
[#164 #issuecomment-5934502364](https://github.com/cinic0101/grepbit/issues/164#issuecomment-5934502364).
- **The candidate.** `p3-count-basis-answer-v21` (`docs/count-basis-answer-v21.md`,
  #166) is v19's server answer to a model `count_basis` clarification, on v20's
  model-facing bytes.
- **The baseline.** v20 (`p3-v18-restoration-v20`), whose behaviour identity
  equals v18's (`docs/behavior-identity.md`, #165).

**Verdict of the pre-registered gate (`evaluation-gate-v2`): `passed`.**
- **21 fixed:** `dev-C1` ×3, `dev-BM7` ×3, `dev-CF11` to `dev-CF15` ×15.
- **0 broke.**
- **2 excluded:** `dev-BM2.en`, flaky in the baseline.

**The verdict depends on that baseline's flakiness.**
- **The prediction failed.** The contract predicted that `dev-BM2.en` would
  stay answered, and it did not: v21 declined it on both panels.
- **What saved the verdict.** It is excluded only because the v20 sentinel
  declined it too. Had the sentinel answered, the baseline would be
  `stable_correct`, v21's decline a `broke`, and the verdict `regression`.

This is a development observation on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v20 sentinels (step 2) | From `dev@229c115`, the #165 merge (15:53:05 UTC), while v20 was current. Recorded at #164 #issuecomment-5935707196 before #166 merged. |
| v21 runs (step 4) | From `dev@2641299`, the #166 merge (16:24:59 UTC), made after the no-blocker review record (#166 #issuecomment-5935717060). The merged head `4a49fb3` is the reviewed head. |
| Where | A clean HTTPS clone of `dev` at those commits. The artifact folders were copied back byte for byte (`diff -rq` identical) for `--record` and the gate. |
| Possible in-flight attempts | 0 in all eight runs |
| Grant use | **308 of 308** calls, with no repeat |
| Identities | v21: candidate `375482d4…` (the same model input as v20 and v18), behaviour `b6145662…`. v20: candidate `375482d4…`, behaviour `7cc96145…`. |

| Run | Candidate | Calls | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- | --- | --- |
| bound-meaning-v3 r1 (sentinel) | v20 | 24 | `87d0aa5497f762381bab1613e6d8596c048854677073de67869dbdb556ff2e6f` | `8fb38755639371dfbf2c8310185e38032d2a1d59711d2e1d4b8def626f2fc494` |
| count-fresh-v2 r1 (sentinel) | v20 | 54 | `bbfe80d5a0f35ce02f6c61686d395f084aeb6e30c802f14895d5e8844a3d1f68` | `07a554028bfedd314fb7e1e7a625c919a85972066211236ec5265f3f43e9f923` |
| compare-first-v3 r1 (sentinel) | v20 | 54 | `619f89ac8dd95ce52931ca549a454cd6c20f137fb34fb9f97997436e7c473c11` | `cf8972c8e50d817dc6b8a73a64ff0a91b365d7b6da1a7fcf3ad56a2604d17819` |
| mechanism-probe-v2 r1 (sentinel) | v20 | 22 | `f647000bb0b04d0393cd8b97cb036420801c7cdbed52fe31a918cfc8c07bde9c` | `c6f3730b6ada278dc9c3c69a0a5cc74f7253f7eac25af076dce45ba2503b9193` |
| bound-meaning-v3 r1 | v21 | 24 | `9a53745c43876f208e7b19fe59ae9ed0b816c775bae7a353cb3880a30f92ea11` | `7bf452e28f35d0c8038e8af81f4264e76179a9feac0840fb39c50a23c00d02be` |
| count-fresh-v2 r1 | v21 | 54 | `599e375b9bdf76427263a69595ad5e6230a390a33dec51e655bfae2054d7ca67` | `a7ca534d3bc11c42bd37a4593c4e77269f24e63d903565ba869bba8736176a1c` |
| compare-first-v3 r1 | v21 | 54 | `d0e308a270ce1416ebee6f850565052f0815bc4062f0b3f9196c0c42f43a8a38` | `965fdbb7934fae7c69e7ba475b13236ed8468b499a5017193f8aa54a098c9a37` |
| mechanism-probe-v2 r1 | v21 | 22 | `ead10101813a6f5eee33c60a09fc0d7d0a5476b9fad56dca5df9b7b24209a940` | `6eae7764eb403d0242dbfce6cffd65268d67de9e44a96a220828e0ee86f233b9` |

### Order (UTC; local file times and GitHub)

| Time | Event |
| --- | --- |
| 15:20:56 | grant recorded (the owner: 「ok，繼續, 308 沒問題」) |
| 15:53:05 | #165 merged (`229c115`) |
| 15:53:24 to 16:04:46 | v20 sentinel packets written and the four runs finished |
| 16:24:53 | #166 review record (no blocker) posted |
| 16:24:59 | #166 merged (`2641299`), so v21 became current |
| 16:25:19 to 16:36:37 | v21 packets written and the four runs finished |
| 16:36:55 to 16:36:56 | all eight rows recorded |

The gate ran after all eight rows were recorded.

## Gate

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-basis-answer-v21 \
  --baseline-candidate p3-v18-restoration-v20 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/164#issuecomment-5934502364 \
  --panels p3-dev-bound-meaning-v3 p3-dev-count-fresh-v2 p3-dev-matrix-compare-first-v3 p3-dev-mechanism-probe-v2
```

**The gate used `evaluation-gate-v2`** with run index `bbf39d2f`.
- **Baseline.** Each panel's baseline is three runs of v18's behaviour identity:
  - on `p3-dev-bound-meaning-v3` and `p3-dev-count-fresh-v2`, #158's sentinel and step-(2b) runs plus the v20 sentinel;
  - on the other two, #152's r1 and #158's sentinel plus the v20 sentinel.
- **Sentinels.** Every input was sentinel-assessed.

| Panel | Fixed | Broke | Excluded | Unchanged correct | Unchanged wrong | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v3` | 3 | 0 | 1 | 20 | 0 | passed |
| `p3-dev-count-fresh-v2` | 15 | 0 | 0 | 33 | 6 | passed |
| `p3-dev-matrix-compare-first-v3` | 3 | 0 | 0 | 48 | 3 | passed |
| `p3-dev-mechanism-probe-v2` | 0 | 0 | 1 | 21 | 0 | no_fix |
| **Overall** | 21 | 0 | 2 | 122 | 9 | **passed** |

- **Fixed:** `dev-BM7` ×3, `dev-CF11` to `dev-CF15` ×15, and `dev-C1` ×3. Nine of them (`dev-BM7`, `dev-CF11`, `dev-CF12`) count as fixes under the ADR #158 oracle revisions.
- **Excluded:** `dev-BM2.en` on both panels. Its baseline is `flaky`: correct, correct, then a decline in the v20 sentinel. v21 declined it too, against the contract's prediction; see the note under the verdict.
- **Unchanged wrong:** the `dev-A1` class, which is out of scope (#158): `dev-A1` ×3, and `dev-CF16` and `dev-CF17` ×3.

Annex-aware index counts:

| Panel | v18 first | v18 second | v20 sentinel | v21 |
| --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v3` | 21/24 | 21/24 | 20/24 | 23/24 |
| `p3-dev-count-fresh-v2` | 33/54 | 33/54 | 33/54 | 48/54 |
| `p3-dev-matrix-compare-first-v3` | 48/54 | 48/54 | 48/54 | 51/54 |
| `p3-dev-mechanism-probe-v2` | 22/22 | 22/22 | 21/22 | 21/22 |
| **Total** | 124/154 | 124/154 | 122/154 | 143/154 |

## Reading

- **The rule alone made the change.**
  - **Byte-identical: 153 of 154** v21 validated actions equal the v20
    sentinel's; the remaining one differs only in local choice ids.
  - **Every fixed row is the model's own `count_basis` clarification** (the
    same in v20), which v21's server answered with booked seats and the stated
    assumption.
  - **No other count reading moved.** The G, S, U and K rows of the fresh
    panel, the Compare rows and the decline rows all kept their outcomes.
- **`dev-BM2.en` is flaky on v18's model-facing bytes.** Its decline is not
  specific to v19's or v21's change, because v20's run of the same model
  input declined it too. Whether either change also affected it cannot be
  told from these runs. The question is "Against February 2026 as the
  reference, how did the overall confirmed booking amount in March change?"
  Its observations on 2026-10-01 (UTC, run end times), all on the same route:

  | Time (UTC) | Candidate (model input) | Outcome |
  | --- | --- | --- |
  | 03:42, 03:44 | v18 | answered ×2 |
  | 08:31, 08:40 | v18 | answered ×2 |
  | 13:03, 13:12 | v19 (changed context) | declined ×2 |
  | 13:15 | v18 | answered |
  | 15:55, 16:04 | v20 (v18's bytes) | declined ×2 |
  | 16:27, 16:36 | v21 (v18's bytes) | declined ×2 |

  - **What this shows.**
    - **The counts.** By behaviour identity (v18 and v20), it was answered 5
      times and declined twice. By model input, which adds v21, it was
      answered 5 times and declined 4 times.
    - **The declines cluster from 13:00 on,** so a serving-side change during
      the day cannot be told apart from sampling.
  - **What it corrects.** The v19 record's reading that its decline was "most
    likely an effect of the changed model-facing context" does not hold. That
    record carries a dated correction.
- **Determinism is high but not complete.** Between the v20 sentinel and the
  six earlier v18 runs in the gate's baselines, 304 of 308 outcomes repeat,
  and the four differences are all `dev-BM2.en`.
- **Re-running v19's gate now gives a different verdict.**
  - **What changed.** v19's documented gate command, run on today's index
    (`bbf39d2f`, which now holds v20's runs of v18's behaviour), gives
    `passed` with `dev-BM2.en` excluded.
  - **Which verdict counts.** v19's recorded `regression` was computed at
    index `f8b87cef` and is the pre-registered verdict.
  - **What the re-run is.** A counterfactual, not a re-gate.

## Claims and limits

- **What this shows.** On 31B, the server answering a model `count_basis`
  clarification, with no model-facing change, turned all 21 such rows into
  correct answers on these four panels. Nothing else broke under the gate.
- **Observations.** One v21 run and three baseline runs per panel, on one
  route, with exposed, mostly agent-authored inputs. The fresh panel is
  regression data after #157. This is not generalization evidence. It makes no
  claim about holdout or formal panels, Bedrock or promotion.
- **Status.** v21 stays the registered current candidate.
  - **The gate does not establish:** product readiness, the `dev-A1` class, or
    behaviour on frozen formal and holdout panels. Those may expect
    `count_basis` clarifications, so a promotion claim needs a new formal panel
    (#158 item 6).
- **Untested live.** The server-decline path (v16) still never ran.
- **Budget.** The grant is spent at 308 of 308 calls.
- **Raw reports** stay local under `.artifacts/v21-sentinel-20261001/` and
  `.artifacts/v21-candidate-20261001/`. The index keeps their digests.
