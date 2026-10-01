# Candidate v18: gate results (#152)

Steps (1), (3) and (4) of the grant
[#152 #issuecomment-5923864223](https://github.com/cinic0101/grepbit/issues/152#issuecomment-5923864223)
for candidate `p3-count-scope-v18` (`docs/count-scope-v18.md`, #153). The
baseline is v17 (`docs/count-directive-v17.md`).

**Verdicts of the pre-registered gates:** `no_fix` on the v2 pair and `no_fix`
on `p3-dev-matrix-compare-first-v3`. Nothing was fixed and nothing broke. On
all 100 inputs, v18 behaves exactly like v17. This is a development
observation on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v17 sentinels (step 1) | From `dev@a937ed8` (the #151 merge), while v17 was current, repetition 2 |
| v18 runs (step 3) | From `dev@d84e30a`, the #153 merge, made after its no-blocker review record |
| Where | A clean HTTPS clone of `dev` at those commits, as in #151. The artifact folders were copied back byte for byte (`diff -rq` identical) for `--record` and the gate. |
| Possible in-flight attempts | 0 in all six runs |
| Grant use | **200 of 200** calls, with no repeat |
| Candidate SHA256 | v18 `375482d4ca8f9f9714c913fa5cbc3d968c16e1e9a2bc1dcf383c7bcde0b90a16`; baseline v17 `c69e474bec8e894ccb94c07f775bfe8c03c15e4043266d155082fedf1affeb6c` |

| Run | Candidate | Calls | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- | --- | --- |
| bound-meaning r2 | v17 | 24 | `7f721909a033579da9e00f6b02f9bee584f3d531a4a30510532a2ba7acd85138` | `30a90953d95f3f8a6dadc96bc0933540a17a6b2346901af60c4038d58bd92a4c` |
| mechanism-probe r2 | v17 | 22 | `1cb0de9305509fa7a5f28c5a81612552e3089036272201f556754e8fd33b2758` | `5396e27a153fda230b8afb13c57304fe9bd024cf09cdfcaecd6c0b7f8ec51330` |
| compare-first-v3 r2 | v17 | 54 | `fce3a862f33245926459df0fbee23865c5f8392240d086ea5695d701bc1e6f64` | `11c75f09b3ed7728fe5943409757a22a7f9abb5d7ebb37a86a5730ba15aa44f1` |
| bound-meaning r1 | v18 | 24 | `d1c6b74b9197d73bc9c65ad90536bdea548c532f321c36769f67b37d37f2373f` | `e965b964f4c06aaa5d60a3f1f451de834b63e406e63a71e2dcd2efd8f0021dae` |
| mechanism-probe r1 | v18 | 22 | `92724a94bd1479d58caa85929c1383c2ff7e17f2cf56db01c9e430f8cbf253a0` | `066acefba1b8a7e1f1ee44b5a673a22c797562a4bf2872d59e6179502f80c34a` |
| compare-first-v3 r1 | v18 | 54 | `bf5fb64ad042b32097d2bb6a24c97dcfe07ba2b44205a917c27399aae53e2a31` | `44bf45e3896314c33c351dfd91f01e2075b9f20d38c37970297f4527984d55e7` |

**Order** (UTC; local file times and GitHub):

| Time | Event |
| --- | --- |
| 03:01:44 | grant recorded (the owner: 「方案 T + 200 沒問題」) |
| 03:02:21 to 03:09:41 | v17 sentinel packets written and the three runs finished, from `a937ed8` |
| 03:40:13 | #153's no-blocker review record posted, verified on GitHub before step 3 |
| 03:40:21 | #153 merged, so v18 became current |
| 03:40:32 to 03:47:52 | v18 packets written and the three runs finished, from `d84e30a` |
| 03:48:46 to 03:48:47 | all six index rows recorded under the grant reference |

## Gates

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-scope-v18 \
  --baseline-candidate p3-count-directive-v17 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/152#issuecomment-5923864223 \
  --panels p3-dev-bound-meaning-v2 p3-dev-mechanism-probe-v2
# and the same with --panels p3-dev-matrix-compare-first-v3
```

Both used `evaluation-gate-v1` with run index `c4c0d11a`. Each panel's baseline
is two v17 runs, #151's r1 and this grant's sentinel. Every input was
sentinel-assessed.

| Panel | Fixed | Broke | Excluded | Unchanged correct | Unchanged wrong | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 0 | 0 | 0 | 24 | 0 | no_fix |
| `p3-dev-mechanism-probe-v2` | 0 | 0 | 0 | 22 | 0 | no_fix |
| **v2 pair** | 0 | 0 | 0 | 46 | 0 | **no_fix** |
| `p3-dev-matrix-compare-first-v3` | 0 | 0 | 0 | 48 | 6 | **no_fix** |

The unchanged wrong rows are `dev-A1` ×3 and `dev-C1` ×3, the two targets.

Annex-aware index counts:

| Panel | v17 r1 (#151) | v17 r2 (sentinel) | v18 r1 |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 24/24 | 24/24 | 24/24 |
| `p3-dev-mechanism-probe-v2` | 22/22 | 22/22 | 22/22 |
| `p3-dev-matrix-compare-first-v3` | 48/54 | 48/54 | 48/54 |

## Reading

- **v18 moved nothing.** Across v17 r1, v17 r2 and v18 r1, no input changes
  outcome. The validated actions are byte-identical except for local choice ids
  in two clarifications:
  - `dev-BM7.ja`: `c1` and `c2` in both v17 runs, `basis_seats` and
    `basis_accounts` on v18;
  - `dev-C3.en`: `CTR-A01` on v17 r2, `ctr_a01` on v17 r1 and v18.

  The semantic values are the same in every run.
- **`dev-A1`** still reads `count_request: "unresolved"` in all three
  languages. Edit 1 ("including a general overview of bookings that asks for no
  number of people") did not change the reading.
- **`dev-C1`** is still the model's own `count_basis` clarification with
  `booked_seats` and `known_booking_accounts`, in all three languages. Edits 2
  and 3 did not change it. Two texts that pull toward this clarification were
  left unchanged, as the contract named: the context's `count_basis` entry and
  the either/or rule.
- **v17 is stable on these panels.** Its second run reproduces its first,
  input for input in outcome: 46/46 on the v2 pair and 48/54 on v3.
- **None of the risks the contract named occurred.** `dev-BM6`, the `dev-MN`
  inputs, `dev-BM7`, `dev-C3`, `dev-C4-v2`, `dev-BM8`, `dev-D8`, `dev-BM5`,
  `dev-A2` and the Compare and Breakdown inputs all kept their outcomes.

## Claims and limits

- **What this shows.** On 31B, these instruction edits do not move the two
  readings. It does not show why. The model's raw reasoning is not retained.
- **Two observations each.** One v18 run per panel, and two v17 runs per panel,
  on one route with exposed, mostly agent-authored inputs. This is not
  generalization evidence. It makes no claim about holdout or formal panels,
  Bedrock (which fails closed) or promotion.
- **v18 stays current.** The gate rules require a revert only on `regression`.
  v18's text matches the owner's rulings, and it adds 312 bytes to each
  request, with no measured effect. Restoring v17's text would be a new candidate and needs an
  owner decision.
- **Next steps need their own owner decision**, as recorded at #152
  #issuecomment-5924018925. A further count-family candidate needs one; the
  options are in ADR #152, including option B for `dev-C1`.
- **Untested live.** The server-decline path still never ran.
- **Budget.** The grant is spent at 200 of 200 calls.
- **Raw reports** stay local under `.artifacts/v18-sentinel-20261001/` and
  `.artifacts/v18-candidate-20261001/`. The index keeps their digests.
