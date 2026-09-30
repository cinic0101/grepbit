# Reading diagnostic and routing upper bound: evidence (#79)

These are steps 2 and 3 of the owner-delegated sequence
([#79 #issuecomment-5903014322](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903014322)).
They ran under the standing grant
[#issuecomment-5903164765](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903164765).
All results are development observations on exposed dev-panel inputs; none is
promotion or gate evidence. Archives live under `.artifacts/` and are not in
git. The digests below pin them.

## Step 2: reading diagnostic (`docs/reading-diagnostic.md`)

Six runs from `dev@5ddb2eb3ad6e` (#134), all complete, with no stop, retry or repeat:

| Run | Route | Source run | Calls | Packet | Report |
| --- | --- | --- | --- | --- | --- |
| `c31-replayed` | 31B | v12 control r2 | 24 | `22c59d31c303` | `bd8337b8e530` |
| `c31-fresh` | 31B | v12 control r2 | 24 | `f9fe0bffb26b` | `a1c79f1dfd4d` |
| `p31-replayed` | 31B | v12 probe r2 | 22 | `a39de80d95e4` | `13cef1c68f89` |
| `p31-fresh` | 31B | v12 probe r2 | 22 | `4ea6708712c9` | `59a0afc1e36c` |
| `ps-replayed` | Sonnet | Sonnet v12 probe r1 | 22 | `e8411f20a33b` | `d186b945b491` |
| `ps-fresh` | Sonnet | Sonnet v12 probe r1 | 22 | `2f65d6af2536` | `74103cc79d50` |

Slots are `.artifacts/reading-20260930/<run>-run`. Only three readings follow
mechanically from an existing oracle; everything else was reported, not graded:

| Check | 31B fresh | 31B replayed | Sonnet fresh | Sonnet replayed |
| --- | --- | --- | --- | --- |
| Count read as unresolved (`count_basis` clarify inputs) | 18/18 | 18/18 | 2/12 | 0/12 |
| Orientation read as unresolved (`comparison_roles`) | 3/3 | 3/3 | n/a | n/a |
| Orientation read as stated (Compare answers) | 19/19 | 15/19 | 10/10 | 10/10 |
| Self-reported decision equals the recorded action | 20/46 | 25/46 | 21/22 | 22/22 |

**Findings:**
- **31B reads correctly and decides wrongly.** Its fresh count and
  orientation readings agree with the oracle-implied reading on all 40
  checkable inputs, including its own production failures.
  - Its self-reported decisions are unreliable.
  - Its replayed orientation readings rationalize the recorded false
    clarifications.
- **31B reads `dev-MN3.en`'s "headcount" as an attendance event,** which the
  instruction says to decline.
- **31B reads `dev-MN2` as booking-framed** in both variants, yet production
  offered attendance visits. Its event reading on unframed questions is
  unreliable, which is v11's failure mode.
- **Sonnet reads generic people counts as `distinct_people`** and declines, as
  the instruction directs for that meaning. Its self-report is faithful.

## Step 3: routing upper bound (`docs/routing-upper-bound.md`)

Four runs from `dev@3cf549cd6a65` (#135), all complete, with no stop, retry or repeat.
- The two v12 sentinels are indexed runs.
- The routing reports are observational. Their comparison with v12's classes
  is recomputed at readback.

| Run | Calls | Packet | Report |
| --- | --- | --- | --- |
| v12 sentinel, control: `p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--7aeddc49b5a8--r1` | 24 | `6db87d7dd743` | `9006cc9ba167` |
| v12 sentinel, probe: `p3-dev-mechanism-probe-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--0b5f7b1f52f3--r1` | 22 | `4f226a22e659` | `46d2b31c5db7` |
| routing, control (`.artifacts/step3-20260930/routing-bound-meaning-run`) | 24 | `ce2d69a32a37` | `cc6af0a05170` |
| routing, probe (`.artifacts/step3-20260930/routing-mechanism-probe-run`) | 22 | `b052059cd560` | `ef4dccfa244c` |

**Sentinels.** They scored 20/24 and 11/22, as before. The aggregate over
every v12-bytes run shows control 20 stable correct and 4 stable wrong over 5
runs, and probe 11 and 11 over 3 runs, with no flaky input.
`dev-BM6.zh-TW` alternated again between two wrong outcomes across sessions
(`missed_clarification` and `wrong_action`).

**Routing against v12, by the candidate gate's rules:**

| Panel | Routed | Sentinel | Fixed | Broke | Verdict |
| --- | --- | --- | --- | --- | --- |
| control | 19/24 | 20/24 | none | `E02_compare.zh-TW` | regression |
| probe | 8/22 | 11/22 | `dev-MN3.en` | `dev-MC1.en`, `dev-MC3.en`, `dev-A3.en`, `dev-MN1.ja` | regression |

**Findings:**
- **Narrowing each input to its analysis type made Compare worse.** Four
  directed Compare inputs that v12 answers became false `comparison_roles`
  clarifications, and none of v12's three false clarifications was fixed.
- **On the count inputs it fixed only `dev-MN3.en`** (headcount: decline
  became the expected clarification) and broke `dev-MN1.ja`. `dev-BM6` ×3,
  `dev-MN1.en` and `dev-MN2` ×3 stayed wrong.
- **A perfect router by analysis type does not help on these inputs, so a
  real router would not either.** Routing as context narrowing is not
  supported.

## Combined reading

- **Separating reading from deciding has support.** 31B's typed readings are
  accurate where its decisions fail (step 2).
- **Narrowing what it sees does not help** (step 3). The Compare decision
  moves with any context change, as v8, v9 and v11 also showed.
- This favors a design where the model emits typed readings and reviewed
  rules decide. It is the direction of ADR #136 for counts.
- An analogous typed orientation reading would be the Compare counterpart. It
  is not yet designed or tested.

## Limits

- One run per variant or panel. The inputs are exposed, mostly
  agent-authored development material, so this is not fresh generalization
  evidence.
- Readings are self-reports under a diagnostic framing. The replayed variant
  is post hoc.
- Between 31B and Sonnet, the model and the route are confounded.
- Routing results measure the old count rule, before ADR #136.

**Budget used under the grant:**
- 31B: 184 of 240 calls. Step 2 used 92 (383,834 prompt tokens); step 3 used 92. The routing runs took 117,538 prompt tokens.
- Sonnet: 44 of 120 calls (227,326 prompt tokens).
