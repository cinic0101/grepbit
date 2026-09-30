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
| Route | `litellm-gemma-4-31b`; retry, fallback and cache disabled |
| `p3-dev-bound-meaning-v2` | run `…p3-count-assumption-v13--201d4711ee20--r1`, 24/24 calls, complete, report `7c615645` |
| `p3-dev-mechanism-probe-v2` | run `…p3-count-assumption-v13--9a48a6804639--r1`, 22/22 calls, complete, report `c64fd90d` |
| Possible in-flight attempts | 0 |
| Grant use | 138 of 160 calls: 92 in step 2, 46 here; no repeat |

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
- **Compare moved.** v13 changed only count text, yet three Compare inputs that
  v12 answered correctly in both baseline runs of their panel became
  `comparison_roles` clarifications.
  The v12 instruction's Compare orientation text is unchanged, so this is
  consistent with the byte change perturbing a decision already known to be
  unstable (`E02_compare.en`, `dev-MC2`, `dev-MC4`). One v13 run cannot
  separate that from between-session drift. The gate counts them by design.

## Claims and limits

- This is a development observation on exposed inputs: one run per panel, on
  one route. It is not promotion evidence, and it is not a claim about holdout
  or formal panels.
- The gate is pre-registered, and its verdict is not reinterpreted. No
  expectation is changed to match the candidate.
  - Whether a redundant, true assumption on a question that names booked seats
    should count as wrong is a semantic question. It would need an explicit
    rationale, independent acceptance and a new annex identity.
  - It cannot change this verdict.
- The unmeasured near-misses and limits recorded in
  `docs/count-assumption-v13.md` stay unmeasured:
  - `dev-C1` and `dev-D8` on `p3-dev-matrix-compare-first-v2`;
  - the precedence with another unsupported requirement.
- Raw reports stay local in `.artifacts/v13-candidate-20260930/`. The index
  keeps their digests.

## Next

The grant's pre-registered consequence is a revert of v13 to v12 by a further
PR, with no rerun. The owner decides what follows the stop.
