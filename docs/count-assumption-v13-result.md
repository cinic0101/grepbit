# Candidate v13: gate result (#136)

Steps (4) and (5) of the owner's grant
[#79 #issuecomment-5904208402](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5904208402)
for candidate `p3-count-assumption-v13` (`docs/count-assumption-v13.md`, #140).
The baseline is v12 on the same panels (`docs/count-assumption-evaluation.md`, #139).

**Pre-registered verdict: `regression`.** Under the grant this is a stop: there
is no rerun, and v13 is reverted by a further PR.

## Runs

| Item | Value |
| --- | --- |
| Tool and runtime commit | `dev@6c34efd` (the #140 merge), clean checkout |
| Route | `litellm-gemma-4-31b`; retry, fallback and cache attested disabled (#79 #issuecomment-5857155780; the reports record `operator_cli_attestation_not_independently_verified`) |
| Candidate | `p3-count-assumption-v13`, candidate SHA256 `23e3de1ae955aa4638f206026d79b1079a681000f75e6ab7a06162c5824122d0` |
| `p3-dev-bound-meaning-v2` | run `…p3-count-assumption-v13--201d4711ee20--r1`, 24/24 calls, complete |
| `p3-dev-mechanism-probe-v2` | run `…p3-count-assumption-v13--9a48a6804639--r1`, 22/22 calls, complete |
| Possible in-flight attempts | 0 |
| Grant use | 138 of 160 calls: 92 in step 2, 46 here; no repeat |

| Run | Packet manifest SHA256 | Report SHA256 |
| --- | --- | --- |
| bound-meaning | `ba59a3d1a1ecf8038f0157d031a7cbe53725e6dbb82e694130b1e88a15840ee0` | `7c615645257018aeb4e7fb8c58137ff8838b86776549dd5ef79ff6ff5bbac782` |
| mechanism-probe | `2263b72cd9003b20c9aa70fc5d1705ee980a0281804cb51bd4dfec8eea59d362` | `c64fd90db3496b89663b70118da414109d5ea56f93d4f87402ac971ec551a707` |

Annex-aware index counts:

| Panel | v12 (2 runs, each) | v13 (1 run) |
| --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 20/24 | 19/24 |
| `p3-dev-mechanism-probe-v2` | 7/22 | 17/22 |

## Gate

The command:

```bash
.venv/bin/python tools/evaluate.py --gate --candidate p3-count-assumption-v13 \
  --baseline-candidate p3-v10-restoration-v12 --route litellm-gemma-4-31b \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/79#issuecomment-5904208402 \
  --panels p3-dev-bound-meaning-v2 p3-dev-mechanism-probe-v2
```

It gave `evaluation-gate-v1`, verdict `regression`, run index `6ae62d19`.
Each panel's baseline is the two v12 runs of step 2, which are also the
sentinels. They were recorded under the same grant, and every input was
sentinel-assessed.

| Panel | Fixed | Broke | Unchanged correct | Unchanged wrong | Excluded or unassessed | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 3 | 4 | 16 | 1 | 0 | regression |
| `p3-dev-mechanism-probe-v2` | 12 | 2 | 5 | 3 | 0 | regression |

`dev-BM6` is on both panels, so the 15 fixed rows are 12 distinct inputs.

**Fixed.** These were all stable wrong on v12, and v13 answers each with the
stated assumption:
- `dev-BM6` in all three languages (on both panels);
- `dev-MN1`, `dev-MN2` and `dev-MN3` in all three languages.

**Broke.** These were all stable correct on v12:

| Input | v12 | v13 |
| --- | --- | --- |
| `dev-BM5` zh-TW, en, ja ("including the number of confirmed booked seats") | Overview, no assumption | The same Overview **plus** `assumption: booked_seats`: frozen-correct, annex-wrong (a spurious assumption) |
| `E02_compare.zh-TW` | Compare | `comparison_roles` clarification (false clarification) |
| `dev-MC3.en` | Compare | `comparison_roles` clarification (false clarification) |
| `dev-A3.en` | Compare | `comparison_roles` clarification (false clarification) |

**Unchanged wrong.** `E02_compare.en` (both panels), `dev-MC2.en` and
`dev-MC4.en`, all false clarifications, as on v12.

## Reading

- **The count rule worked where it was aimed.** Every generic people-count
  input moved from clarify, decline or a silent answer to the answer with the
  stated assumption, in all three languages.
- **The exclusion did not hold.** "Names no seats …; otherwise omit
  assumption" did not stop 31B stating the assumption on `dev-BM5`, whose
  question names booked seats. The round-2 review had flagged this risk
  (#140, F2). The stated assumption there is redundant and true, but the
  accepted annex expects none on an unlisted oracle.
- **Compare moved.** Three Compare inputs became `comparison_roles`
  clarifications. v12's bytes had answered them correctly in every recorded
  run, across several authorizations: `E02_compare.zh-TW` in 7 of 7 (bound
  meaning v1 and v2), and `dev-MC3.en` and `dev-A3.en` in 5 of 5 (mechanism
  probe v1 and v2).
  - **What v13 changed.** It left the Compare orientation text unchanged. But
    besides the count text it changed two things every question sees:
    - the shared structured-output schema: the Overview branch gained the
      optional `assumption`, and the output-contract and structured-output
      versions moved to v3;
    - the generic request-shape sentence, which now ends "Overview may add
      assumption".

    On this constrained-decoding route, either could move the decision.
  - **Earlier byte changes broke the same inputs:**
    - `dev-MC3.en` under v8, v9 and v11, and `dev-A3.en` under v8 and v11
      (`docs/v10-restoration-v12.md`);
    - all three in the routing upper-bound run
      (`docs/reading-and-routing-evidence.md`).

    So these are the inputs whose decision moves when the bytes move.
  - **What one run cannot rule out:** a route change in the roughly two hours
    between the sentinel runs (recorded 06:28Z) and the v13 runs (recorded
    08:24Z), or variation of v13's own
    output between sessions. The gate counts the rows by design.

## Claims and limits

- This is a development observation on exposed inputs: one run per panel, on
  one route. It is not promotion evidence, and it is not a claim about holdout
  or formal panels.
- The gate is pre-registered, and its verdict is not reinterpreted. No
  expectation is changed to match the candidate.
  - Whether a redundant, true assumption on a question that names booked seats
    should count as wrong is a semantic question. It would need an explicit
    rationale, independent acceptance and a new annex identity.
  - It cannot change this verdict, for two reasons:
    - even with `dev-BM5` counted correct, each panel keeps a break
      (`E02_compare.zh-TW`; `dev-MC3.en` and `dev-A3.en`), so the gate's
      rule 1 still gives `regression`;
    - a new annex identity changes `panel.annex_sha256`, so these runs could
      not be re-gated under it.
- The unmeasured near-misses and limits recorded in
  `docs/count-assumption-v13.md` stay unmeasured:
  - `dev-C1` and `dev-D8` on `p3-dev-matrix-compare-first-v2`;
  - the precedence with another unsupported requirement.
- Raw reports stay local in `.artifacts/v13-candidate-20260930/`. The index
  keeps their digests.

## Next

The grant's pre-registered consequence is a revert of v13 to v12 by a further
PR, with no rerun. By owner decision (#79 #issuecomment-5907491660) that revert
is candidate `p3-v12-restoration-v14` (`docs/v12-restoration-v14.md`), and the
next step is ADR #142.
