# Candidate v17: gate results (#146)

Steps (1), (3) and (4) of the grant
[#146 #issuecomment-5922742690](https://github.com/cinic0101/grepbit/issues/146#issuecomment-5922742690),
amended to 260 calls at #issuecomment-5923049914, for candidate
`p3-count-directive-v17` (`docs/count-directive-v17.md`, #150). The baseline is
v16 (`docs/count-reading-v16.md`).

**Verdicts of the pre-registered gates:**
- `passed` on the two v2 dev panels;
- `no_fix`, with no break, on `p3-dev-matrix-compare-first-v3` (#149).

These are development observations on exposed inputs, not promotion.

## Runs

| Item | Value |
| --- | --- |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| v16 runs (step 1) | From `dev@78475bf` (the #149 merge), while v16 was current |
| v17 runs (step 3) | From `dev@4f1181a` (the #150 merge, after its round-2 no-blocker record) |
| Possible in-flight attempts | 0 in all eight runs |
| Grant use | **260 of 260** calls: 160 in step 1, including 6 in the stopped run, and 100 in step 3 |
| Candidate SHA256 | v17 `c69e474bec8e894ccb94c07f775bfe8c03c15e4043266d155082fedf1affeb6c`; baseline v16 `f6e48dd4b237e0fbdf9003d966db74922748d5f2f8404e850c390a414dafd0f5` |

| Run | Candidate | Calls | Status | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- | --- | --- | --- |
| bound-meaning r2 | v16 | 24 | complete | `c040e0e35440e82da92d1873d5406c0fbaa4d2606638c71403427dcc0f7c65d8` | `8c121ce6de243a8c8c2ba0e65a63a605ed067dbe6bf0efabc3fb3de418aa07cb` |
| mechanism-probe r2 | v16 | 6 | **incomplete** (`accepted_commit_required`) | `c867a9930c73978f95f3a169a5689a84d4d93c70a1df23b412de29d50b090d2e` | `88d59c501770a4d0e1d073b590c4da3913a52b899b86d831271665947f9ae4c9` |
| mechanism-probe r3 | v16 | 22 | complete | `025d85b59f7b2828e4193280a5e018ce1c3113b04e659398e119604451164324` | `af5bb235f18812af9f42a57855b93a54228fdd015d2a9dde6d7d5cfac294793b` |
| compare-first-v3 r1 | v16 | 54 | complete | `7964978c442bd765af9871c4dda49a3d9e3dd8b2dad64a5a6e1bcc901484dc1a` | `8b33d511fb166b000f6c900210ce0a028d357e944b77f3ff502aa08e300ada78` |
| compare-first-v3 r2 | v16 | 54 | complete | `abe55bdf44867b2c9b6cdd8b71cde510b03da29f36e4027e9e171c7135e9e587` | `33783b2940892e4f63f9a02b9656309c4a78e2a9aa33b32f197b550a84a307d5` |
| bound-meaning r1 | v17 | 24 | complete | `6100b0a6fb48b6867cc7104dd80fc2a7b03d58d16afffd29e6643ec6c13fb818` | `23b88093a2d4e02d300d536cc26b067c43b304d35e3626c87343a22867715c52` |
| mechanism-probe r1 | v17 | 22 | complete | `a1fa60f21aa59013ab4e4b67b2770a25cf74322943d7764bde804735ed72494b` | `84cf192c30b2e8bb2bc4f7cad1233726469366356ba1ed57927f58532e2d5603` |
| compare-first-v3 r1 | v17 | 54 | complete | `f38d0ef77f4c9e267fe5313de14954e6d269c60eb1fca291e5e5132a90bcdc10` | `c5a51ae0b2a3aefeecac837bcb3fe4667e49cb9444202750e5c27c02ebc6bd4b` |

**The stopped run.** `mechanism-probe-r2` stopped after 6 calls. The run checks
the source identity while it runs, and the main checkout had become dirty: another
agent edited `AGENTS.md` and `docs/collaboration-model.md`, and the owner had
the edits reverted. No row ran on a changed source.
- The stop is #146 #issuecomment-5923032940.
- The owner approved one operational repeat and the 260 cap at
  #issuecomment-5923049914.
- The run is recorded as incomplete. Its six rows count as baseline
  observations.

**Where the runs executed.**
- **Main checkout.** Step 1 prepared four bound envelopes in
  `.artifacts/v17-baseline-20261001/`. The first two ran there. The two
  `compare-first-v3` envelopes were never run, because the sequence stops at the
  first incomplete run. Their packets hold only the 0-attempt preparation report.
  Their run slots were never created, and nothing was recorded for them.
- **Clean HTTPS clone.** After the stop, the remaining runs were prepared and run
  from a clean HTTPS clone of `dev`, at the same merged commits: `78475bf` for
  v16 and `4f1181a` for v17. They used fresh envelopes and slots. The tools
  refuse a run unless `dev` is the checked-out branch and the tree is clean.
- **Copy back.** The run directories were copied back to the main checkout byte
  for byte (`diff -rq` identical) for `--record` and the gate.

**Order** (UTC; local file times and GitHub):

| Time | Event |
| --- | --- |
| 01:15:58 | grant recorded (254 calls) |
| 01:33:26 | #149 merged, with v16 current |
| 01:33 to 01:35 | step-1 packets written; `bound-meaning-r2` finished |
| 01:36 | `mechanism-probe-r2` stopped |
| 01:43:19 | the operational stop recorded on #146 |
| 01:44:56 | the owner's amendment recorded (260 calls, one repeat) |
| 01:45 to 01:55 | `mechanism-probe-r3` and `compare-first-v3` r1 and r2 prepared and run from the clone |
| 02:12:55 | #150's round-2 no-blocker record posted, verified on GitHub before step 3 |
| 02:13:09 | #150 merged, so v17 became current |
| 02:13 to 02:20 | the v17 packets were written and the three runs finished |

All eight index rows were recorded together afterwards, under the grant
reference. The gate does not limit the recording order.

## Gates

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-directive-v17 \
  --baseline-candidate p3-count-reading-v16 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/146#issuecomment-5922742690 \
  --panels p3-dev-bound-meaning-v2 p3-dev-mechanism-probe-v2
# and the same with --panels p3-dev-matrix-compare-first-v3
```

Both used `evaluation-gate-v1` with run index `b431c071`. Every input was
sentinel-assessed.

| Panel | Baseline runs | Fixed | Broke | Excluded | Unchanged correct | Unchanged wrong | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 2 | 0 | 0 | 0 | 24 | 0 | no_fix (already 24/24) |
| `p3-dev-mechanism-probe-v2` | 3 (r1, incomplete r2, r3) | 8 | 0 | 1 | 13 | 0 | passed |
| **v2 pair** | | 8 | 0 | 1 | 37 | 0 | **passed** |
| `p3-dev-matrix-compare-first-v3` | 2 | 0 | 0 | 0 | 48 | 6 | **no_fix** |

- **Fixed:** `dev-MN1` zh-TW and ja, `dev-MN2` ×3 and `dev-MN3` ×3. All were
  stable-wrong four-meaning `count_basis` clarifications on v16, and all now
  read `unresolved` with the stated assumption.
- **Excluded:** `dev-MN1.en` was flaky on v16 (correct on #148's r1, a
  clarification on r3). v17 answers it correctly, but a flaky baseline cannot
  gate as fixed.
- **Unchanged wrong on v3:** `dev-A1` ×3 and `dev-C1` ×3. v17's contract
  expected both and did not target them.
- **Broke:** none, on any panel.

Annex-aware index counts:

| Panel | v16 | v17 |
| --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 24/24 | 24/24 |
| `p3-dev-mechanism-probe-v2` | 14/22 (#148), 13/22 (r3) | **22/22** |
| `p3-dev-matrix-compare-first-v3` | 48/54, 48/54 | 48/54 |

## Reading

- **Only the targeted inputs moved.** Against the v16 baseline of the same
  panel, the only outcome changes are the nine `dev-MN` rows: from
  clarification to the correct answer. Every other input on the three panels
  kept its outcome:
  - `dev-BM5` read `booked_seats`, with no assumption;
  - `dev-BM7` kept its clarification;
  - `dev-BM8` and `dev-D8` were declined by the model itself;
  - `dev-A2` read `none`;
  - Compare and Breakdown inputs were unchanged. The contract's named Compare
    risks, `E02_compare.zh-TW`, `dev-MC3.en` and `dev-A3.en`, read `stated`
    and were answered correctly.

  None of the risks the contract named
  (`docs/count-directive-v17.md`) occurred.
- **The two v2 panels are now 46/46** on one v17 run.
- **Two known v3 failures remain, both readings:**
  - `dev-A1` ("Give me the March 2026 booking picture for CTR-A01") asks for no
    count, yet v16 and v17 read `count_request: "unresolved"`, which is a
    spurious assumption.
  - `dev-C1` ("How many people booked at CTR-B01 in March 2026? I am not sure
    whether you count seats or booking accounts.") is still the model's
    two-meaning `count_basis` clarification, against the owner's rule-1 ruling
    (#149). The v17 sentence excludes questions that name a meaning, and it does
    not encode the owner's distinction.

## Claims and limits

- **Scope.** One v17 run per panel, on one route, with exposed and mostly
  agent-authored inputs. It makes no claim about holdout or formal panels,
  Bedrock (which fails closed) or promotion.
- **Untested live.** The server-decline path still never ran: 31B declined
  `dev-BM8` and `dev-D8` itself.
- **Next candidates** need their own decision and authorization:
  - the `dev-A1` reading, where a no-count overview reads `unresolved`;
  - the `dev-C1` distinction between the system's basis and the user's own
    choice.
- **Budget.** The grant is spent at 260 of 260 calls.
- **Raw reports** stay local under `.artifacts/v17-baseline-20261001/`,
  `.artifacts/v17-baseline-20261001b/` and `.artifacts/v17-candidate-20261001/`.
  The index keeps their digests.
