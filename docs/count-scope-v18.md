# Candidate v18: the scope of the count reading (#152)

Candidate `p3-count-scope-v18`, whose ancestor is `p3-count-directive-v17`.
It is option T of ADR #152, which the owner approved together with the two-fix
exception for this candidate
([#152 #issuecomment-5923864223](https://github.com/cinic0101/grepbit/issues/152#issuecomment-5923864223):
「方案 T + 200 沒問題」).

## Why

v17 (`docs/count-directive-v17.md`, result `docs/count-directive-v17-result.md`)
left two stable failures on `p3-dev-matrix-compare-first-v3`. Each failed in all
three languages, in all three recorded runs (v16 ×2, v17 ×1). Each failed again
in the v17 sentinel of this grant's step (1), which is recorded with the
result.

- **`dev-A1`** ("Give me the March 2026 booking picture for CTR-A01") asks for
  no count, yet it reads `count_request: "unresolved"`. The server then states
  an assumption that the annex does not expect.
- **`dev-C1`** ("How many people booked at CTR-B01 in March 2026? I am not sure
  whether you count seats or booking accounts") gets the model's own two-choice
  `count_basis` clarification. The owner ruled it rule 1 (#149): doubt about the
  *system's* basis is not the user's own undecided choice, as `dev-BM7` is.

The v17 text does not separate the two cases:
- it says `count_basis` applies "when the question itself is undecided between
  named meanings";
- v17's directive excludes every question that names seats or accounts;
- nothing in it says that a general overview asks for no count.

Two further texts describe `dev-C1`'s shape and pull toward a two-choice
clarification. Option T leaves both unchanged:
- **The context's `count_basis` entry:** "Use count_basis only when the question
  explicitly leaves the count basis undecided between named meanings, offering
  exactly those meanings".
- **The instruction's either/or rule:** "An explicit either/or contrast restricts
  the open interpretations to that contrast … two contrasted meanings require
  exactly two choices".

## The change (`grepbit/recipe_model.py`, text only)

`SYSTEM_INSTRUCTION` changes in three places:

1. **The `none` reading.** `"none" when it asks for no count;` becomes:
   > "none" when it asks for no count, including a general overview of bookings
   > that asks for no number of people;
2. **The `count_basis` limit.** "Use count_basis only when the question itself
   is undecided between named meanings." becomes:
   > Use count_basis only when the user says they are undecided between named
   > meanings.
3. **System-basis doubt.** A new sentence follows v17's directive, which stays
   word for word:
   > Doubt about which basis the system counts by is not the user being
   > undecided: a people count that names seats or accounts only in that doubt
   > is also answered with count_request "unresolved", and the stated assumption
   > tells the basis.

- **`INSTRUCTION_VERSION`** becomes `recipe-selection-instruction-v11`, so the
  candidate identity changes.
- **Unchanged:**
  - the context, including its `count_basis` entry;
  - the output contract and the structured-output schema;
  - the code, with v16's code-decided assumption and decline and v15's Compare
    orientation;
  - the frozen clarification test.
- **Kept phrases.** The edits keep "undecided between named meanings" and v17's
  directive, which earlier rulers check as live behaviour.
- **Wording versus the ADR draft.** ADR #152 option T drafted edits 2 and 3
  differently:
  - ADR edit 2: "only when the user says their own choice between named meanings
    is undecided";
  - ADR edit 3: a clause inside v17's directive, "this includes a question that
    names seats or accounts only to ask which basis the system counts by; the
    stated assumption answers it".

  The implemented edit 2 keeps the phrase "undecided between named meanings",
  which the v16 ruler checks. Edit 3 is a separate sentence, so v17's directive
  stays byte for byte. The own-choice versus system-basis distinction therefore
  sits in edit 3 rather than in edit 2. The meaning is the same as the draft's.
  Edit 1 is the draft's text exactly. The ADR left the wording open.
- **Overlap disclosed.**
  - Edit 1 targets a general overview request like `dev-A1`, but it copies none
    of its words.
  - Edit 3 states the owner's ruled distinction in general terms, not
    `dev-C1`'s text.

## Evaluation

**Result:** `no_fix` on the v2 pair and on the v3 panel. No input changed
outcome, and `dev-A1` and `dev-C1` stayed wrong. See the
[gate results](count-scope-v18-result.md).

The grant is #152 #issuecomment-5923864223, with 200 calls:
- **Step 1, while v17 is current:** one v17 sentinel on each of
  `p3-dev-bound-meaning-v2` (24 calls), `p3-dev-mechanism-probe-v2` (22) and
  `p3-dev-matrix-compare-first-v3` (54), for 100 calls.
- **Step 3:** one v18 run on each of the three panels, another 100 calls.
- **Gate.** `tools/evaluate.py --gate --candidate p3-count-scope-v18
  --baseline-candidate p3-count-directive-v17`, for the v2 pair and for v3.
  `regression` is a stop and a revert, with no rerun.

## Claims and limits

- **What v18 targets:** `dev-A1` ×3 and `dev-C1` ×3 on the v3 panel.
- **Expectation.**
  - `dev-A1` needs only a reading change, toward `none`.
  - `dev-C1` needs 31B to tell who is undecided, which is uncertain until it
    runs. The likeliest way T fails on it is the two unchanged texts named
    under Why, the context's `count_basis` entry and the either/or rule. Also,
    `dev-C1.ja` has no explicit system subject ("…数えるのか分かりません"), so
    edit 3's "which basis the system counts by" maps less directly there.
  - If T leaves `dev-C1` unchanged or breaks `dev-BM7`, ADR #152's fallback is
    option B, a server-built `count_basis`. B needs a new owner decision and
    the frozen-test amendment.
- **Risks the gate measures:**
  - **`dev-BM6` and `dev-MN1`** ask for an overview including a headcount. Edit 1
    could pull them to `none`, which would lose the assumption and make them
    annex-wrong.
  - **`dev-BM7`** says the user has not decided between seats and booking
    accounts, so it should stay a clarification. Edits 2 and 3 could turn it
    into an answer. Its en form asks for "the count" without saying "number of
    people" (the zh-TW and ja forms say 人數 and 人数), so edit 1 could also
    act on it.
  - **`dev-C3`** (a center clarification, "What did March 2026 bookings look
    like at CTR-A01 or CTR-A02?") is shaped like `dev-A1`. It should stay a
    clarification.
  - **`dev-C4-v2`** (a `metric_meaning` clarification, "I have not specified
    whether…") should stay one. Edit 3's doubt/undecided wording could spill
    onto it.
  - **`dev-MN2` and `dev-MN3`** are people counts without an overview. They
    should stay `unresolved`.
  - **`dev-BM8` and `dev-D8`** require a named unavailable count, so they
    should stay declines.
  - **Compare and Breakdown inputs.** Earlier byte changes moved some of them.
- **Safe either way.** `dev-BM5` (named seats) and `dev-A2` (bookings and
  seats) state no assumption under both `booked_seats` and `none`.
- **Unmeasured.**
  - No dev case asks a general overview in other words, or doubts the system's
    basis without naming one.
  - The server-decline path is still untested live.
- **Scope.** One route, one run per panel, on exposed panels used in tuning: a
  development observation, not generalization.
