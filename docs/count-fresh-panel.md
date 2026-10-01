# Fresh count panel (#152)

Panel `p3-dev-count-fresh-v1`, step (1) of the grant
[#152 #issuecomment-5925246940](https://github.com/cinic0101/grepbit/issues/152#issuecomment-5925246940)
(owner: 「我沒問題了，可以開始」). It tests whether the current candidate's count
handling generalizes beyond the panels used in tuning:
`p3-dev-bound-meaning-v2`, `p3-dev-mechanism-probe-v2` and
`p3-dev-matrix-compare-first-v3`.

It is a dev-tier panel: a development observation, never a gate input against
another candidate, holdout or promotion evidence. It leaves the runtime,
candidates and every existing case, oracle and panel unchanged.

## Why

v16 to v18 were tuned on the same exposed inputs. v17 and v18 score 46/46 on
the two v2 panels and 48/54 on the v3 panel, but those inputs shaped the
prompt. Two questions remain open:
- whether the generic people-count handling holds on questions that were not
  used in tuning. These questions are new, but their brief shares the
  prompt's vocabulary (see Authoring);
- whether `dev-A1`'s and `dev-C1`'s failures are general or tied to their
  wording. The panel has two families shaped like `dev-A1` (O) and three shaped
  like `dev-C1` (B).

## Authoring

- **The slot table** (types, centers, months, one-line details) was designed by
  the implementing agent, who knows the production prompt. That is a disclosed
  limitation.
- **The questions** were written by an independent fresh-context sub-agent.
  - It worked from a brief with three things in it: the product's Overview
    scope, the four count meanings, and the owner's count rules (the rule table
    of #79 #issuecomment-5903712127, the #149 ruling for `dev-C1`, and the
    no-count and bookings readings of `docs/count-assumption.md` and
    `docs/count-reading-v16.md`).
  - It saw no production prompt, candidate output, oracle or tuned-panel
    question, and it used no tools.
  - **The brief's wording is not independent of the prompt.** The implementing
    agent wrote the brief's rule rows and wording guidance. Four of its seven
    rows closely follow the production instruction:
    - **O:** "a general overview or status of bookings that asks for no number
      of people" is almost word for word v18's edit 1 (`docs/count-scope-v18.md`).
    - **G:** the wording guidance mirrors v17's directive, both its trigger words
      ("how many people", headcount) and its exclusion list (no seats,
      accounts, attendance or individual persons).
    - **K and B:** these rows paraphrase the bookings clause and v18's
      system-basis-doubt sentence.

    So the questions were written against the prompt's own boundaries and
    trigger words. The panel tests new questions within that vocabulary, which
    may be easier than real users' wording. "Without the production prompt"
    holds only literally. The owner may judge whether that meets the grant's
    intent.
  - Its disclosure: auto-attached project instructions, the memory index and
    the git status. None of it describes case text or expected answers.
- **Records.** The sub-agent's questions and notes are committed unchanged in
  `evals/dev/count-fresh-authored-v1.json`. The file is reshaped: the
  languages sit under `questions`, `note` becomes `author_note`, and the slot
  fields are copied from the brief's table. The brief and the raw output are
  recorded verbatim on the PR.
- **The author's notes.**
  - It flagged one doubt: F02 ("how many people signed up") could be read as a
    count of bookings. The semantic reviewer accepted F02 as a generic people
    count.
  - It also noted one interpretation: F15's "the month's figures" is taken to
    mean the Overview.

| Slot | Type | Center | Month | Branch | Oracle detail |
| --- | --- | --- | --- | --- | --- |
| F01–F05 | G: generic people count | various | various | answer | Overview, assumption stated (annex) |
| F06, F07 | S: booked seats | CTR-A02, CTR-B01 | 2026-03, 2026-04 | answer | Overview, no assumption |
| F08 | U: distinct booking accounts only | CTR-A01 | 2026-03 | decline | D06 (the contract's D08) |
| F09 | U: Overview plus attendance visits | CTR-B01 | 2026-03 | decline | D04 |
| F10 | U: distinct people only | CTR-A02 | 2026-02 | decline | D06 (the contract's D08) |
| F11 | D: user undecided, seats vs booking accounts | CTR-B01 | 2026-03 | clarify | `count_basis`: booked_seats, known_booking_accounts |
| F12 | D: user undecided, seats vs distinct people | CTR-A01 | 2026-02 | clarify | `count_basis`: booked_seats, distinct_people |
| F13–F15 | B: doubt about the system's basis | various | various | answer | Overview, assumption stated (annex; #149 ruling) |
| F16, F17 | O: general overview, no count | CTR-B01, CTR-A02 | 2026-04, 2026-02 | answer | Overview, no assumption |
| F18 | K: number of bookings | CTR-A01 | 2026-02 | answer | Overview, no assumption |

The exact centers and months of every slot are in the authored file.

**Why two of the declines are D06.** The oracle parser (protected) admits
D01–D06 only. An explicit account or people count is the contract's D08, so it
is recorded as D06. `docs/coverage-matrix.md` does the same for its D7 and D9
rows, which record categories outside D01–D06 as D06. An Overview plus a
required unavailable count is D04, as in `docs/coverage-matrix.md`'s D8 row
(an Overview plus a required attendance count) and for `dev-BM8`.

## Data

`tools/build_count_fresh_panel.py <output-dir> <fixture-db>` builds every file
from the authored source and the synthetic fixture:
- `count-fresh-cases-v1.json`;
- `count-fresh-oracles-v1.json`;
- `count-fresh-panel-v1.json`;
- `count-fresh-annex-v1.json`;
- `count-fresh-read-responses-v1.json`.

Rebuilding reproduces the committed bytes. The details:
- **Families and cases.** Family ids are `dev-CF01` to `dev-CF18`, with three
  cases each (zh-TW, en, ja), in slot order, 54 inputs.
- **Exposure.** `design_seen`, `origin: development`,
  `seen_by_implementer: true`. After the step-(3) run, the panel counts as
  exposed.
- **Answer oracles** are kernel-derived Overview oracles, built as
  `tools/build_dev_panel.py` builds them.
- **The annex** lists exactly the G and B oracles (8). No other oracle expects
  an assumption.
- **The scripted correct actions** are v16-style typed actions for the offline
  mock loop:
  - G and B read `unresolved`;
  - S reads `booked_seats`;
  - O and K read `none`;
  - D is the two-choice clarification, and U is a decline.
- **Registration.** The registry entry is tier `dev`, authoring `development`,
  with the annex pinned.

## Acceptance

- **Semantics.** An independent fresh-context sub-agent accepts the oracles and
  the annex. It receives only the questions, the owner's rules and the proposed
  oracles. It sees no model output, run result or implementing conversation. A
  disagreement that needs an owner ruling is a stop. The implementing agent
  does not accept the oracles.
- **Code.** An independent fresh-context review of the PR's GitHub diff.

## Evaluation (step 3)

- **The run.** One run of the current candidate (v18) on the panel, at most 54
  calls, after this PR merges with both records.
- **The report.** The frozen grade and the annex verdict per input, by type.
- **What it does not include.** There is no gate, since no candidate pair is
  compared.

## Claims and limits

- **Evidence class.** Agent-authored development data: the sub-agent works for
  the same project. It is not frozen-fresh or holdout evidence.
- **The slot table is not independent.** The implementing agent designed it, so
  the type mix is the agent's choice.
- **Coverage.** One route and one run. 18 families cannot cover all wording.
  There is no Compare or Breakdown family, and no people count on an incomplete
  scope, because a missing period is D05, which is not scored.
- **The brief shares the prompt's vocabulary** (see Authoring). A good result
  shows the handling holds on new questions in that vocabulary, not on
  arbitrary user wording.
- **Near-paraphrases.** No question repeats a tuned or development question
  exactly. Nine pairs reach a `difflib` character similarity of 0.80 or more,
  mostly from a shared center, month and sentence shape:
  - `dev-CF16.ja` and `E01_overview.ja`, 0.86;
  - `dev-CF06.en` and `dev-MN2.en`, 0.86;
  - `dev-CF01.zh-TW` and `dev-MN3.zh-TW`, 0.85;
  - `dev-CF01.en` and `dev-MN2.en`, 0.84;
  - `dev-CF13.en` and `dev-C1.en`, 0.82, which is shaped like `dev-C1` by design.
- **F14 extends the #149 ruling.** The ruling concerned doubt between seats and
  booking accounts. F14 applies it to doubt between seats and distinct people.
  The semantic reviewer accepted F14, and the owner may confirm it.
