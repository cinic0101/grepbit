# Count assumption: evaluation side (#136)

Contract `count-assumption-eval-v1`. It implements the evaluation half of
ADR #136, as amended in
[#136 #issuecomment-5904225044](https://github.com/cinic0101/grepbit/issues/136#issuecomment-5904225044),
for the owner's people-count decision
([#79 #issuecomment-5903677393](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903677393),
rule table approved at
[#issuecomment-5903712127](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903712127)):

> A generic people or count question whose meaning is unresolved is answered
> with booked seats, the only executable count, with the assumption stated and
> the unavailable meanings named.

**No protected file changes, by the owner's choice of route A**
([#79](https://github.com/cinic0101/grepbit/issues/79), "按照你建議的做 = A").
- The frozen P3.3 evaluator is unchanged: `tools/p3_assets.py`,
  `tools/p3_grading.py` and `tools/p3_scoring.py`, and every other file in
  `tests/fixtures/p310_identity_baseline.json`.
- The runtime is unchanged, so the current candidate (v12) stays current and can
  be evaluated on the new panels. The runtime half, where the model emits the
  assumption, is candidate v13 in a later PR.

## The annex

The expected assumption is kept **outside** the oracle, in a closed annex file:

```json
{"version": "count-assumption-annex-v1",
 "expectations": {"dev-BM6.v2": {"count_basis": "booked_seats"}, "...": {"count_basis": "booked_seats"}}}
```

- Every listed oracle expects exactly the assumption
  `{"count_basis": "booked_seats"}`. Every oracle of the panel that is not
  listed expects none.
- A listed oracle must be one of the panel's Overview answer oracles.
- A `dev`-tier panel registry entry may carry an optional `annex`
  `{path, sha256}`, like `intake` and `freeze`. The loader pins the file, and
  `evaluate.build_packet` records its digest as the packet's
  `panel.annex_sha256`.
- So the annex is part of every packet's and report's panel identity. The
  candidate gate's `inputs_differ` check also compares it.
- A panel without an annex is unchanged. Its packets carry no `annex_sha256`
  and read back as before.

## The annex verdict

- **The frozen grade is recorded unchanged.** On an annex panel, the runner
  derives a verdict per row from that grade and the row's persisted
  `validated_action`:
  - a frozen-wrong row is `wrong`;
  - a frozen-correct row is `correct` only if the assumption its validated
    action states equals the oracle's expectation. A clarification or decline
    states none. An unlisted oracle expects none. Otherwise the row is
    `wrong`: a missing assumption is a silent substitution, and a spurious one
    an unwanted assumption;
  - a frozen-correct row without a persisted action is `unassessed`, because
    the assumption cannot be checked.
- **Where the verdict is used:**
  - the counts `tools/evaluate.py --record` writes to the run index, and so
    `STATE.md`;
  - the aggregate classes (`--aggregate`);
  - the candidate gate: the baseline classes, the candidate rows and the
    sentinel's assessment of an input.
  - `--replay`: a row is `replayed_same` only if both its frozen grade and
    its annex verdict are unchanged. Each replay row also reports the annex
    verdict before and after.
  - the aggregate's per-run `correct`.
- **Where the frozen grade is kept:**
  - the report rows written by the live run. The live path records the frozen
    grade, and the annex is applied where the rows are read. This is narrower
    than the route-A proposal's wording, which named the live grading path
    too.
  - the run index's `outcomes` tally, so `outcomes.complete_correct` can
    exceed the index `correct` on an annex panel;
  - the reading diagnostic and the routing upper bound. The routing tool
    refuses the new panels: its router table covers only the v1 panels.
- **Persisted actions.** A persisted validated action may carry the assumption
  on an Overview request, with exactly the value above. The closed shape
  rejects any other value, and an assumption on any other recipe.

## Revised oracles and new panels

The four count families that the rule table changes get new oracle revisions:
`dev-BM6.v2`, `dev-MN1.v2`, `dev-MN2.v2` and `dev-MN3.v2`.
- Each is a plain Overview answer for `CTR-A01`, 2026-03-01 to 2026-04-01
  `+08:00`, `Asia/Taipei`. It equals the accepted `dev-BM5.v1` except for its
  id, revision and provenance. The expected assumption is in the annex.
- Each case of these families is re-pointed to its v2 oracle, with
  `expected_branch` and `cohort` set to `answer` and a new
  `semantic_signature`.
- The question text and every other case are unchanged.

| New panel | Cases file | Oracles file | Changed cases |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | `bound-meaning-cases-v2.json` | `bound-meaning-oracles-v2.json` | `dev-BM6` ×3 |
| `p3-dev-mechanism-probe-v2` | `mechanism-probe-cases-v2.json` | `mechanism-probe-oracles-v2.json` | `dev-BM6` ×3, `dev-MN1` ×3, `dev-MN2` ×3, `dev-MN3` ×3 |

- Each panel pins its own annex, which lists exactly its v2 oracles. Every
  listed oracle must be one of that panel's Overview answers.
  - `bound-meaning-annex-v2.json` lists `dev-BM6.v2`.
  - `mechanism-probe-annex-v2.json` lists `dev-BM6.v2`, `dev-MN1.v2`,
    `dev-MN2.v2` and `dev-MN3.v2`.
- The v1 panels, files and archived results are unchanged.
- Contract row C01 of `docs/p3-evaluation-contract.md` keeps its accepted v1
  text. Its note points here for the v2 panels.
- The families the rule table leaves unchanged keep their oracles:
  `dev-BM5` (answer), `dev-BM7` (clarify with the stated meanings) and
  `dev-BM8` (decline).

## Acceptance

- **Semantics.** The owner-designated independent reviewer accepted the v2
  expectations on #138. The acceptance covers the expected results, which are
  the same under route A: an Overview answer with the stated assumption.
- **Code.** The implementation of route A has its own independent code review
  on #138.

## Claims and limits

- **Only the typed assumption is checked.** Whether a product shows the
  assumption, says "confirmed booked seats" rather than bookings, and names
  the unavailable meanings is not graded here. Candidate v13 must render
  and test that. A pass on these panels shows only the typed part of the
  rule.
- **An annex-unassessed row counts as not correct** in the index count and
  `STATE.md`, and as unassessed in the aggregate and the gate.
- **Readers of raw reports must apply the annex.** A raw report row on an annex
  panel shows the frozen grade. For example, v12's silent answer to `dev-BM6`
  is `complete_correct` there, while its annex verdict is `wrong`. The index,
  `STATE.md`, the aggregate and the gate use the annex verdict.
- **Signatures and distinct-action counts.** `actual_signature` comes from the
  frozen grader and does not include the assumption. The aggregate's
  distinct-action counts come from the validated actions, which do include it.
- **Scope.** The new panels measure the owner's rule on exposed development
  inputs. Holdout and formal oracles are untouched.
