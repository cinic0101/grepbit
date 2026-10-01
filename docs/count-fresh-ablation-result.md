# Fresh count panel and count ablation: results (#152)

Steps (3) and (4) of the grant
[#152 #issuecomment-5925246940](https://github.com/cinic0101/grepbit/issues/152#issuecomment-5925246940).
The owner confirmed the step-(4) run shape at #issuecomment-5926564128. Both
steps observe the current candidate v18 (`p3-count-scope-v18`, candidate
`375482d4…`) on route `litellm-gemma-4-31b`. Retry, fallback and cache are
attested disabled (#79 #issuecomment-5857155780).

- **Calls.** **96 of 100**: 54 on the fresh panel and 42 for the ablation.
  There were no repeats, and 0 attempts were in flight in all four runs.
- **Where.** Both ran from a clean HTTPS clone of `dev` at the merged commits.
  The artifact folders were copied back byte for byte (`diff -rq` identical).
- **What they are.** The fresh-panel run is a development observation and is in
  the run index. The ablation is a diagnostic observation: never a run-index
  entry, a gate input or promotion evidence.

## Step (3): v18 on the fresh panel

| Item | Value |
| --- | --- |
| Panel | `p3-dev-count-fresh-v1` (#155, `docs/count-fresh-panel.md`): 18 families × 3 languages |
| Commit | `dev@0e5003b` (the #155 merge, after its semantic acceptance and no-blocker records) |
| Packet manifest SHA256 | `e81e729f44274937336f8a259c7aa815badbdf5717b41a87dd9d4abaf54bf9cc` |
| Report SHA256 | `fa205f45250a5895fc2b905afe052bc24af2ad3fd3e2c7158424f461e65e0909` |
| Run | `p3-dev-count-fresh-v1--litellm-gemma-4-31b--p3-count-scope-v18--821041f0ef75--r1`, complete, 54 calls |
| Annex-aware result | **39/54**, 13 of 18 families |

| Type | Families | Rows correct | What v18 did |
| --- | --- | --- | --- |
| G: generic people count | CF01–CF05 | **15/15** | `unresolved`, so the assumption is stated |
| S: booked seats | CF06, CF07 | **6/6** | `booked_seats` |
| U: required unavailable count | CF08–CF10 | **9/9** | the model's own decline |
| D: user's own undecided choice | CF11, CF12 | **6/6** | a two-choice `count_basis` clarification |
| K: bookings count | CF18 | **3/3** | `none` |
| **B: doubt about the system's basis** (like `dev-C1`) | CF13–CF15 | **0/9** | a false `count_basis` clarification on all 9 rows: two choices on 8, four on `dev-CF14.zh-TW` |
| **O: general overview, no count** (like `dev-A1`) | CF16, CF17 | **0/6** | `unresolved`, so a spurious assumption (annex-wrong) on all 6 |

**Reading:**
- **The handling generalized where it already worked.** v18 handles the five
  types it handled on the tuned panels (G, S, U, D, K) on 39 new questions.
- **`dev-A1` and `dev-C1` are not wording accidents.** Their failures are
  systematic for their whole classes: every O row and every B row failed, in
  all three languages.
- **Limits:**
  - one run;
  - questions written within the prompt's own vocabulary (the brief shared its
    wording, `docs/count-fresh-panel.md`, accepted by the owner as a disclosed
    limitation at #issuecomment-5926564128);
  - some near-paraphrases of tuned questions.

## Step (4): the count ablation

| Run (fixed order) | Calls | Packet SHA256 | Report SHA256 |
| --- | --- | --- | --- |
| `p3-dev-matrix-compare-first-v3` | 18 | `80ba56a858c5e19a7c835e14124876eb888b6c173c2d5b69bd5aad86eaea2df4` | `fe155db22fe20ba55cf2cbca23c380640fcd4cf73e34e816f4af10a7870f919c` |
| `p3-dev-bound-meaning-v2` | 18 | `d641a716bcd9d06407d541c9713b542a5032b26bbe3a44d6f480c5dc2ab9437d` | `4b719d550c7cc7c32203c6d576ee72ee6f97e7891d0efc1762fad9a6045ebf75` |
| `p3-dev-mechanism-probe-v2` | 6 | `cdb2af72127fdd4cf9709ab16371e154d8f7dd59138d4ff807a549ef1c637908` | `39bf93871f698155298f44661a007669521f6b794e1199b6c9767902de4446f7` |

- **The runs.** All three are complete, from `dev@d6e7945` (the #156 merge),
  under `count-ablation-v1` (`docs/count-ablation.md`). Every row returned.
- **Readback.** Each report reads back in the main checkout with
  `.venv/bin/python -m tools.count_ablation --report`, against the v18 r1 run
  of each panel, with no comparison refusal.

**Rows, by the pre-registered reading rule:**

| Input | v18 baseline | `labels` | `rules` |
| --- | --- | --- | --- |
| `dev-A1` (target H-A1) | wrong ×3 | **correct 1/3**: ja reads `none`; zh-TW and en stay `unresolved` | wrong 3/3 (`unresolved`) |
| `dev-C1` (target H-C1) | wrong ×3 | wrong 3/3 (two-choice clarification) | **wrong 3/3**: two-choice clarification on en and ja, four-choice on zh-TW |
| `dev-A2`, `dev-BM5`, `dev-BM6`, `dev-BM7`, `dev-MN2` (controls, 15 rows) | correct | correct 15/15 | correct 15/15 |

**Verdicts (pre-registered rule):**
- **H-A1 (labels): No support.** The target's `c = 1` and `u = 0`, so it
  cannot reach 2 of 3.
- **H-C1 (rules): No support.** `c = 0`.
- **Controls.** None broke under either variant. `dev-BM7` stayed a two-choice
  clarification under both, and the generic counts kept `unresolved`.

**Mapping.** Under `labels`, `mapped` is true on 11 of 21 rows: every row whose
reply carried `no_people_count` or `generic_people_count`. The other 10 needed
no mapping:
- four read `booked_seats`: `dev-A2.ja` and `dev-BM5` ×3;
- six are the clarifications of `dev-BM7` and `dev-C1`.

No `rules` row was mapped.

## Reading

- **Neither hypothesis explains the failures on this wording.**
  - **Labels.** Renaming the labels to `no_people_count` and
    `generic_people_count` did not move `dev-A1`'s reading in zh-TW or en.
  - **Rules.** Scoping the context's `count_basis` entry and the either/or
    rule did not move `dev-C1`'s clarification in any language.
  - **What it does not rule out.** These were one-sample probes. The result
    gives no support; it does not refute the hypotheses.
- **The remaining explanation, an untested inference.** The decisions come
  from the model's own reading rather than from these prompt texts:
  - a general booking overview "implies" a count of unresolved meaning (the
    Overview answer does contain counts);
  - a user who voices uncertainty and names two bases is asked to choose.

  The raw model reasoning is not retained, so this remains an inference.
- **One weak signal.** `dev-A1.ja` moved under `labels`: 1 of 3, below the
  pre-registered threshold.

## Claims and limits

- **Evidence class.** These are development and diagnostic observations on
  one route, with one sample per row. They are not generalization or promotion
  evidence.
- **What the fresh panel's 39/54 means.** The shared vocabulary may make it
  easier than real wording.
- **What the ablation tested.** It tested two specific text changes. Other
  wordings, or combinations of them, are untested.
- **Untested live.** The server-decline path was not exercised: every
  required unavailable count was declined by the model itself.
- **Budget.** 96 of 100 calls are used. The remaining 4 are not for repeats.
- **Next steps need owner decisions** (#152).
  - **Policy.** Clarify only between executable meanings. With one executable
    count, that answers the D and B types alike with the stated assumption,
    which also removes the C1 class. It changes accepted oracles (`dev-BM7`,
    CF11, CF12), so it is a mandatory stop. It should be decided on product
    merit.
  - **Capability.** Admit known booking accounts into the Overview.
  - **Accept.** Accept `dev-A1` and `dev-C1` as known limitations.
- **Raw reports** stay local under `.artifacts/count-fresh-20261001/` and
  `.artifacts/count-ablation-20261001/`. The index keeps the fresh run's
  digest, and this record keeps the ablation's.

## Order (UTC)

| Time | Event |
| --- | --- |
| 05:18:36 | grant recorded (100 calls) |
| 05:41:02 | #155 semantic acceptance recorded (18/18) |
| 05:56:33 | #155 code-review record (no blocker) |
| 06:03:36 | #155 merged (`0e5003b`) |
| 06:03:57 to 06:08:54 | fresh-panel packet written and run finished (54 calls) |
| 06:36:37 | fresh run recorded in the index (on this evidence branch) |
| 07:09:55 | #156 delta-review record (no blocker) |
| 07:09:58 | #156 merged (`d6e7945`) |
| 07:13:50 | the owner's confirmation of the three-run shape recorded |
| 07:14:08 to 07:17:50 | ablation packets written and the three runs finished (42 calls) |
