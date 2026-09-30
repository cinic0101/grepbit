# Reading diagnostic and routing upper bound: evidence (#79)

These are steps 2 and 3 of the owner-delegated sequence
([#79 #issuecomment-5903014322](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903014322)).
They ran under the standing grant
[#issuecomment-5903164765](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903164765).
All results are development observations on exposed dev-panel inputs; none is
promotion or gate evidence. The reading and routing reports are local
archives under `.artifacts/`, not in git and not in the run index. This
document is their record, and it pins them by full SHA256.

## Step 2: reading diagnostic (`docs/reading-diagnostic.md`)

Six runs from `dev@5ddb2eb3ad6e` (#134). All completed, with no stop, retry or
repeat. The slot of each run is `.artifacts/reading-20260930/<run>-run`.

| Run | Route | Source run | Calls |
| --- | --- | --- | --- |
| `c31-replayed`, `c31-fresh` | 31B | `p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--a5dab3c260c1--r2` | 24 each |
| `p31-replayed`, `p31-fresh` | 31B | `p3-dev-mechanism-probe-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--907afa5375f9--r2` | 22 each |
| `ps-replayed`, `ps-fresh` | Sonnet | `p3-dev-mechanism-probe-v1--bedrock-jp-sonnet-4-6--p3-v10-restoration-v12--e483c3468cdd--r1` | 22 each |

| Run | Packet SHA256 | Report SHA256 |
| --- | --- | --- |
| `c31-replayed` | `22c59d31c303815c82d6af7246d3c228cf4e81e298d29b4f892cc9a11fbc8ddb` | `bd8337b8e530b6620e28d1e00cfb2b8a5b45a0cee27e3fdb5fdb0fb7c3952306` |
| `c31-fresh` | `f9fe0bffb26b921734781c42f2d0670bd94f67d75fc54943af9318efa22d9f7a` | `a1c79f1dfd4d8007d9df7a2c4722275a33aa6a39cc1ce85cbcd61176ff38376d` |
| `p31-replayed` | `a39de80d95e4f537b5a3ca1fc16cbc0527fa37ae8fff35070fc6332d56576576` | `13cef1c68f892206c7c0814c707ea7ae75b1e5e6401a5c4d7358d256449b5d44` |
| `p31-fresh` | `4ea6708712c9e5a0cd4b73d2891f7a88b3da20f55666cbedcefde65047af0d52` | `59a0afc1e36c751172bf6352f35dfa3fa01ffd55ca232ac0b32280ac63bc13a3` |
| `ps-replayed` | `e8411f20a33be7d717b55d89112f4c9e4ec9791d3d8f60055a7077a87a31bc41` | `d186b945b4916bf5b6ae2b805baed01a725c16b8c3ed96e84efe54a805ab0a43` |
| `ps-fresh` | `2f65d6af2536e1df37f6d6cf6080281b48ac920677e9f1dc6432065bd9533457` | `74103cc79d50d265c1019dbdba804828c9f5978a0a1bf16da27c7fc9a3d331f6` |

**Post hoc checks.** The tool itself compares only the decision and reason
fields with the oracles, as the contract says. The reading checks below were
defined by the implementing agent after the runs. They were computed by an
offline script over the six reports. Each maps an existing oracle to one
reading, and every other reading is reported, not graded:
- a `count_basis` clarification oracle → `count_request` `unresolved`;
- a `comparison_roles` clarification oracle → `orientation` `unresolved`;
- a Compare answer oracle → `orientation` `stated`. This is an
  interpretation: the oracle fixes the orientation of its request, not the
  wording of the question.

| Check | 31B fresh | 31B replayed | Sonnet fresh | Sonnet replayed |
| --- | --- | --- | --- | --- |
| Count read as unresolved (`count_basis` inputs) | 18/18 | 18/18 | 2/12 | 0/12 |
| Orientation read as unresolved (`comparison_roles`) | 3/3 | 3/3 | n/a | n/a |
| Orientation read as stated (Compare answers) | 19/19 | 15/19 | 10/10 | 10/10 |

**Specificity, reported, not graded.** 31B does not read every count as
unresolved. In both variants it read:
- `dev-BM5` (seats named) as `booked_seats`, 3/3;
- `dev-BM8` (deduplicated people named) as `distinct_people`, 3/3;
- every Compare input as `count_request` `none`, 22/22.

**Two different decision measures:**
- *Replayed restatement.* The model was shown its own recorded action and
  asked which decision it took. 31B restated it correctly in 25/46 rows. So
  its replayed readings are weak evidence; the 15/19 orientation row above
  is one symptom. Sonnet restated 22/22, which shows only that it repeated
  an action it was shown.
- *Fresh decision against production.* The decision under the diagnostic
  framing matched the production action in 20/46 rows for 31B and 21/22 for
  Sonnet. The contract expects the fresh action to differ from production,
  so this is not a fidelity measure.

**Findings**, limited to these fields and inputs:
- **31B's count-resolution and orientation readings are accurate where its
  production decisions fail.** Fresh readings agree with the mapping above on
  all 40 checkable inputs. That includes four production failures that the
  readings would have resolved: `dev-BM6` ×3 and `dev-MN1.en` (count read as
  unresolved), and `E02_compare.en`, `dev-MC2.en` and `dev-MC4.en`
  (orientation read as stated). The production action is correct on 31 of
  the 46 inputs.
- **The readings do not explain 4 of v12's 11 failures:**
  - `dev-MN3.en`: 31B reads the "headcount" event as attendance, which the
    instruction says to decline.
  - `dev-MN2` ×3: 31B reads the event as booking in both variants, yet
    production offered attendance visits. That is a choice-construction
    failure, not a reading failure.
- **31B's event readings are unreliable on the unframed questions.**
  `dev-MN1` and `dev-MN3` in zh-TW and ja give `booking`, `not_applicable` or
  `attendance`. That is v11's failure mode.
- **Sonnet reads generic people counts as `distinct_people`** (10/12 fresh)
  and declines, as the instruction directs for that meaning.

## Step 3: routing upper bound (`docs/routing-upper-bound.md`)

Four runs from `dev@3cf549cd6a65` (#135). All completed, with no stop, retry or repeat.
- **Review record.** #135's round-2 re-review reported no blocker before the
  merge. Its record was posted late because of a GitHub API failure
  ([#135 #issuecomment-5904131736](https://github.com/cinic0101/grepbit/pull/135#issuecomment-5904131736)).
- **Drift.** All four packets were prepared before either sentinel was
  recorded, so none drifted.

| Run | Calls | Packet SHA256 | Report SHA256 |
| --- | --- | --- | --- |
| v12 sentinel, control: `p3-dev-bound-meaning-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--7aeddc49b5a8--r1` | 24 | `6db87d7dd7431ecece4f1586a7c0f742511a5ce2d9ecc058d5bac89a12e974ec` | `9006cc9ba1671605d1a9629a794deca313f4725278293ff662e33e9ff26ce754` |
| v12 sentinel, probe: `p3-dev-mechanism-probe-v1--litellm-gemma-4-31b--p3-v10-restoration-v12--0b5f7b1f52f3--r1` | 22 | `4f226a22e6595c21e60a6322c674344984f76e8edbdab5f71d53127d8c9696fc` | `46d2b31c5db7bbc00a9db9d0e2b4f1307be4cd87bbad7c334f6dfac775ace89b` |
| routing, control (`.artifacts/step3-20260930/routing-bound-meaning-run`) | 24 | `ce2d69a32a372e58a68db3ddca1e479ea7dbb0bc97e7ea70fd7cdbd053613424` | `cc6af0a05170d855d7f836b9fdc7642eec0cc51a3af41208e6ec86e7f8fb956a` |
| routing, probe (`.artifacts/step3-20260930/routing-mechanism-probe-run`) | 22 | `b052059cd56034f0c27b929662a17037e7a31f0660d663cd6d72421ed3702852` | `ef4dccfa244c8106cfcf874ff187cbbbef88a51f32e5c8b4145ac344cf1b2b61` |

**Sentinels.** They scored 20/24 and 11/22, as before. The aggregate over
every v12-bytes run shows control 20 stable correct and 4 stable wrong over 5
runs, and probe 11 and 11 over 3 runs, with no flaky input.
`dev-BM6.zh-TW` alternated again between two wrong outcomes across sessions
(`missed_clarification` ×3 and `wrong_action` ×2 on control).

**Routing against v12, by the candidate gate's rules.** The comparison is
recomputed at readback from the run index. The values below used the index as
of this PR, SHA256
`b4ff9d22257651612df9cdd9758455f98c065c2e164273115f8aed1b1107bdc3`; appending
more v12-bytes runs changes them.

| Panel | Routed | Sentinel | Fixed | Broke | Verdict |
| --- | --- | --- | --- | --- | --- |
| control | 19/24 | 20/24 | none | `E02_compare.zh-TW` | regression |
| probe | 8/22 | 11/22 | `dev-MN3.en` | `dev-MC1.en`, `dev-MC3.en`, `dev-A3.en`, `dev-MN1.ja` | regression |

**Findings**, for this run on these inputs:
- **In the routed run, four directed Compare inputs that v12 answers were
  falsely clarified**, and none of v12's three false clarifications was
  fixed.
- **On the count inputs, `dev-MN3.en` was fixed** (the headcount decline
  became the expected clarification) and `dev-MN1.ja` broke. `dev-BM6` ×3,
  `dev-MN1.en` and `dev-MN2` ×3 stayed wrong.
- **Narrowing each input to its analysis type did not help.** A router that
  delivers only these narrowed contexts would not reach more than this
  perfect-router bound here. The result is limited to these contexts, these
  inputs and one run.

## Combined reading

- **Accuracy lies in the readings, not the decisions.** On these inputs,
  31B's count-resolution and orientation readings were accurate where its
  decisions failed (step 2).
- **Narrowing the context did not help** (step 3). The Compare decision moved
  under every context change tested so far: v8, v9, v11 and this routing run.
- **Direction.** Together these favour making the typed readings explicit
  and reducing what the model must decide. ADR #136 is a partial step: the
  model sets a typed `count_assumption` and still chooses the action. A fuller
  split, where the model reads and rules decide, and a typed orientation
  reading for Compare are neither designed nor tested.

## Limits

- One run per variant or panel. The inputs are exposed and mostly
  agent-authored (`E02_compare` is historical). This is not fresh
  generalization evidence.
- The readings are self-reports under a diagnostic framing, and the replayed
  variant is post hoc. The diagnostic's instruction sits in the user message,
  which the production system text calls question data, not authority.
- The routing contexts kept `SYSTEM_INSTRUCTION` unchanged, including its
  count text. So the count-text tension was not tested, and the routing
  results measure the old count rule, before ADR #136.
- Between 31B and Sonnet, the model and the route are confounded.

**Budget used under the grant:**
- 31B: 184 of 240 calls. Step 2 used 92 (383,834 prompt tokens). Step 3 used 92; its routing runs took 117,538 prompt tokens.
- Sonnet: 44 of 120 calls (227,326 prompt tokens).
