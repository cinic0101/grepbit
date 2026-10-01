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

> **Amended 2026-09-30 (v16, #146).** An action states the assumption through
> v13's explicit `assumption` key or through v16's typed Overview
> `count_request: "unresolved"`, from which the server states it
> (`docs/count-reading-v16.md`). A v16 `count_request` other than `unresolved`
> states none. The expectations and the annexes are unchanged.

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

## The empty annex and the compare-first v3 panel (2026-10-01, ADR #146)

- **An empty annex.** An annex may list no oracle:
  `{"version": "count-assumption-annex-v1", "expectations": {}}`. It means that
  no oracle of the panel expects an assumption. So a frozen-correct answer is
  annex-correct only if its action states none, and a stated assumption is
  annex-wrong. The reader still refuses a missing `expectations`, a non-object
  one, another version, an extra key or another assumption value.
- **`p3-dev-matrix-compare-first-v3`.** It is `p3-dev-matrix-compare-first-v2`
  under a new panel id, in the same order, with one family revised by the owner's
  ruling:
  - **`dev-C1` is ruled rule 1**, by owner decision on #149
    (#issuecomment-5922552274, 「a 沒問題」). "How many people booked … I am not
    sure whether you count seats or booking accounts" is a generic people count
    whose meaning is unresolved. The user doubts the *system's* basis; the
    question is not undecided between the user's own named meanings, as
    `dev-BM7` is.
  - **The new oracle `dev-C1.v2`** is an Overview answer for CTR-B01, 2026-03-01
    to 2026-04-01 `+08:00`, `Asia/Taipei`. It equals `dev-A2.v1` except for its
    id, revision and provenance. The three `dev-C1` cases point to it, with
    `expected_branch` and `cohort` set to `answer` and a new
    `semantic_signature`. The question text is unchanged.
  - **New files:** `dev-cases-v3.json` and `dev-oracles-v3.json`. They differ
    from v2 only there.
  - **The annex** `evals/dev/compare-first-annex-v3.json` lists exactly
    `dev-C1.v2`.
- **Why no other oracle changes.** Under the owner's rule table, none of the
  other 17 families expects an assumption:
  - `dev-A1` and `dev-A2` are Overview answers that name no generic people
    count. `dev-A2` asks for bookings and seats.
  - `dev-D8` requires attendance visits, so it is a decline.
- **The v2 panel, its identity and its archives are unchanged.**
- **Why v3.** It widens the evaluation of the count reading (#146) to inputs
  the v2 bound-meaning and mechanism-probe panels lack:
  - a bookings count (`dev-A2`);
  - a named unavailable count, where the server may decline (`dev-D8`);
  - a people-booked question that also names the system's possible bases
    (`dev-C1`).
- **Acceptance.** The annex and `dev-C1.v2` are expectation data. They need
  independent semantic acceptance on their PR, as #138's had. The empty-annex
  reader rule stays for any panel that expects no assumption.

## Clarify only when every choice is answerable (2026-10-01, ADR #158)

The owner decided on #158 that a clarification is offered only when every
offered choice can be answered (「反問的確要在我們都有能力回答時再反問」). The
owner approved the scope and the revisions at #issuecomment-5926866518 and
#issuecomment-5927141003. Booked seats is the only executable count, so a
`count_basis` clarification is never answerable.
- A user's own undecided choice between named count meanings (the old rule
  table's row 3, `dev-BM7`) is now answered with booked seats and the stated
  assumption, exactly as rule 1.
- The doubt about the system's basis (`dev-C1`, the #149 ruling) was already
  answered this way.

**New panels; the old ones stay as history.**
- **`p3-dev-bound-meaning-v3`** is `p3-dev-bound-meaning-v2` under a new id
  and files, with one family revised:
  - **`dev-BM7.v2`** is an Overview answer for CTR-A01 March 2026. It equals
    `dev-BM6.v2` except for its id, revision and provenance. The three
    `dev-BM7` cases point to it, as `answer` with a new signature.
  - **The annex** `bound-meaning-annex-v3.json` lists `dev-BM6.v2` and
    `dev-BM7.v2`.
- **`p3-dev-count-fresh-v2`** is `p3-dev-count-fresh-v1` with two families
  revised:
  - **`dev-CF11.v2`** equals `dev-CF05.v1`'s CTR-B01 March 2026 Overview, and
    **`dev-CF12.v2`** equals `dev-CF04.v1`'s CTR-A01 February 2026 Overview,
    each apart from its id, revision and provenance.
  - **Exposure.** The panel counts as exposed after its v18 run, so every case
    is `exposed_regression`, with history `design_seen` then
    `exposed_regression`.
  - **The annex** `count-fresh-annex-v2.json` adds the two revised oracles.
- **Scripted correct actions.** `bound-meaning-read-responses-v2.json` and
  `count-fresh-read-responses-v2.json` read the revised families as a generic
  count (`count_request: "unresolved"`). Every other action is unchanged.
- **Unchanged as history.** The older oracles that expect a `count_basis`
  clarification predate #158: `p3-development-v1`'s C01, the dev-matrix
  v1/v2 `dev-C1.v1`, and bound-meaning v1 and mechanism-probe v1. So do
  `p3-dev-bound-meaning-v2` and `p3-dev-count-fresh-v1`, and their results.
- **The ruler** is `tests/test_count_basis_revisions.py`. It checks that each
  new panel equals its predecessor byte for byte apart from the stated fields,
  that each revised oracle equals its named source answer, the annex
  additions, the scripted actions, and that a mock loop grades every case
  correct with exactly its annexed assumption.
- **Not covered here.** The runtime half is candidate v19, which answers a
  model `count_basis` clarification on the server. It is a separate PR.
  Frozen formal and holdout panels may still expect `count_basis`
  clarifications: a promotion claim needs a new formal panel (#158).

## Acceptance

- **Semantics.** The owner-designated independent reviewer accepted the v2
  expectations on #138. The acceptance covers the expected results, which are
  the same under route A: an Overview answer with the stated assumption.
- **Code.** The implementation of route A has its own independent code review
  on #138.
- **The v3 panel (#149).**
  - The owner-designated independent reviewer accepted the v3 expectations,
    `dev-C1.v2` and an annex listing it, after the owner's `dev-C1` ruling.
  - A first round had not accepted the data while `dev-C1` still expected a
    clarification.
  - The reviewer did not re-check `dev-A2.v1`'s values, which `dev-C1.v2`
    copies, against the fixture; they rest on `dev-A2.v1`'s accepted status.

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
