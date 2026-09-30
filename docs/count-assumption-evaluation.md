# Count assumption: v13 evaluation record (#136)

This record tracks the owner-authorized evaluation of candidate v13 under
ADR #136, in the order of the grant
[#79 #issuecomment-5904208402](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5904208402).
The rule is `docs/count-assumption.md`, and the verdict is the candidate gate's
(`docs/candidate-gate.md`). All results are development observations on
exposed dev inputs. The archives are local under `.artifacts/`, pinned by
the run index and by the full SHA256 values below.

## Step 1: evaluation side (#138)

#138 merged as `dev@8330f4b`. It added the annex, the v2 dev panels and the
annex verdict, with no protected file changed. Semantic acceptance and code
review are recorded on #138.

## Step 2: v12 baseline on the v2 panels

These are four runs of the current candidate, `p3-v10-restoration-v12`, on
`litellm-gemma-4-31b`, all from `dev@8330f4bec2b4`.
- **Run conditions.** Each run was prepared before any record and bound to the
  grant and one slot. All four completed with 92 of 92 calls and no stop,
  retry or repeat.
- **Environment.** The 31B runs used the provider override
  `GREPBIT_LLM_PROVIDER=litellm` with `.env`, which was not edited.
- **Sentinel.** All four carry the grant reference, so either run of each
  panel serves as the gate's same-authorization sentinel for v13.

| Run | Packet SHA256 | Report SHA256 | Correct (annex verdict) |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2--litellm-gemma-4-31b--p3-v10-restoration-v12--5bf939f186ba--r1` | `24053f2e865b7aeb4c1329328e6f1bf48ff2f9279ca8ef0351435f0201bcdb94` | `00965f1ddf5521a19585264fb77fceb06874ec9136c476a2d87fa8aabe0baa05` | 20/24 |
| `…--5bf939f186ba--r2` | `7bd41a86e5202b559ec1571e69e143083209ac336b154441fb5ed99b9b471ee3` | `9b7bab2f9351b576ce403fb1653cbb8572c35e119fb2effe77fdd528118bdefb` | 20/24 |
| `p3-dev-mechanism-probe-v2--litellm-gemma-4-31b--p3-v10-restoration-v12--1d68d124de87--r1` | `4bbdfe655bf096f5d6a6f858dabbd0fafcb50acd83988436101dab3e6170f161` | `581d840b9eef4981980dedb1d7328f9da6dbfad5ca340f616d7aed5db275ec32` | 7/22 |
| `…--1d68d124de87--r2` | `e4dad646081cec8cd5e059ee30d498fb850c8cf7cddace98979a66ad9d23ea01` | `c50e93630b6b59f91721e69dbf62b29ea1f8ce993e4c65e22e03563907ebe25f` | 7/22 |

**Aggregate classes.** These are annex verdicts over the two runs per panel,
with the run index SHA256 at
`7d8f3241aa8174d8b0cc8c70042d6c714e52d19224509388bcc9d7f9b956c97f` after these
records.

| Panel | Stable correct | Stable wrong | Flaky | Stable-wrong inputs |
| --- | --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | 20 | 4 | 0 | `E02_compare.en`; `dev-BM6` ×3 |
| `p3-dev-mechanism-probe-v2` | 7 | 15 | 0 | `E02_compare.en`, `dev-MC2.en`, `dev-MC4.en`; `dev-BM6` ×3, `dev-MN1` ×3, `dev-MN2` ×3, `dev-MN3` ×3 |

**Reading:**
- v12 cannot state an assumption, so every changed count input is wrong under
  the new rule. Its silent `dev-BM6` answers are frozen-correct:
  `complete_correct` counts 13 on control and 10 on the probe. They are
  annex-wrong, and it clarifies or declines the others.
- The Compare failures are the three known false `comparison_roles`
  clarifications.
- This is the baseline v13 must improve on without breaking any stable-correct
  input.

## Next

The next steps are step (3), PR B with the v13 runtime and candidate, and
step (4), one v13 run on each v2 panel, followed by the gate. **Budget under
the grant:** 92 of 160 calls used; step 4 needs 46.
