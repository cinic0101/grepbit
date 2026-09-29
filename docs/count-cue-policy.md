# Count cues and kernel count policy v11 (#79, #120)

The owner approved decision [#120](https://github.com/cinic0101/grepbit/issues/120)
Option C in chat on 2026-09-29, together with the count definition below and a
fresh-context semantic reviewer. The owner also chose Overview counts only and
cue-derived decline authority. The agent recorded these at
[#120 #issuecomment-5886052261](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5886052261).
The standing grant for measurement is
[#79 #issuecomment-5886058844](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5886058844).
This is the third count-family fix, and the owner approved it explicitly.

## Why

Up to v10, the model authors every count decision directly as its action: the
Overview request, the `count_basis` choice set, or a decline. Temperature-0
serving is repeatable (65/65 identical signatures, #79), so each prose edit
moves near-boundary decisions for real. v5 to v9 each fixed one group of inputs
and regressed another. The recorded reports show:

| Candidate | Input | Result |
|---|---|---|
| v7 (= v10) | `dev-BM6.zh-TW` | four `count_basis` choices, where three were expected |
| v7 (= v10) | `dev-BM6.en`, `dev-BM6.ja` | answered without clarifying |
| v8 | `dev-MN2` ×3 | four choices, where three were expected |
| v8 | `dev-MN1.en`, `dev-MN3.en` | declined, where a clarification was expected |
| v9 | `dev-MN2` ×3, `dev-BM6` ×3 | four choices, where three were expected |
| v9 | `dev-C1` ×3 | four choices, where the question states two meanings |
| v7 | `HA02...en` (holdout-a) | declined, where a clarification was expected |

v11 makes the model first report what the question says about the count, as
typed cues. One reviewed, deterministic kernel policy then derives the action.
The model no longer authors a `count_basis` choice set.

## Count vocabulary (owner-approved product semantics)

This follows the common booking-analytics distinction between bookings and
attendance: attendance happens after a booking, and not every booking is
attended (no-shows). The four reviewed meanings are unchanged
([clarification action](clarification-action.md), contract row C01):
`booked_seats`, `known_booking_accounts`, `attendance_visits` and
`distinct_people`. Only `booked_seats` is executable through the Overview
recipe.

1. **Booking event.** A count tied to a booking event means something that was
   booked: `booked_seats`, `known_booking_accounts`, or the `distinct_people`
   who booked. `attendance_visits` is excluded. Booking events include booked,
   reserved, registered or signed up, and a booking overview or booking
   activity.
2. **Attendance event.** A count tied to an attendance event (attended, showed
   up, checked in, visits) means attendance. It is `attendance_visits`, or
   `distinct_people` when deduplicated persons are asked for.
3. **Generic count noun.** A generic count noun with no stated event, such as
   headcount or how many people, leaves all four meanings open.
4. **Stated contrast.** An explicit either/or contrast between meanings leaves
   exactly those meanings open, even after an earlier generic noun.
5. **Explicit meaning.** An explicitly stated meaning binds the count to it:
   - booked seats;
   - booking accounts;
   - an attendance event;
   - deduplicated, unique or individual actual persons.

A count of bookings (number of bookings or reservations) is the Overview's
existing `bookings` output. It is not one of these count meanings.

## Cue contract: output envelope

The output contract is `recipe-request-json-v3` and the structured output is
`recipe-structured-output-v3`. In every top-level schema branch,
`overview_count` is the **first** property. Constrained decoding therefore
emits the count reading before any action.

`overview_count` has four values:

- `"none"`: the question has no count of the four meanings, or it lacks a
  complete explicit Overview scope. The rest of the object is exactly one v10
  action:
  - `request` (overview, compare or breakdown);
  - `{"outcome":"declined"}`;
  - `clarify` with kind `comparison_roles`, `center` or `metric_meaning`.

  **`count_basis` is not an admitted model-authored kind.**
- `"bound"`: one explicitly stated meaning. Adds `meaning` (one of the four).
- `"contrast"`: an explicit either/or between stated meanings. Adds `meanings`:
  2 to 4 distinct values.
- `"generic"`: a generic count noun without a stated meaning. Adds `event`:
  `"booking"` for a booking framing, `"none"` otherwise. An attendance event is
  not generic; it is `bound` to `attendance_visits`.

A **complete explicit Overview scope** means one explicitly supplied center code
and one explicit full month with its year. A count question without one uses
`"none"` with the model's own action. That action is normally a decline,
because C01 requires an explicit center and month.

Every other reading (`bound`, `contrast` or `generic`) also has:

- `other_unsupported` (boolean): true when the question has any requirement,
  besides the count, that one Overview of the scope cannot satisfy, or a second
  unresolved ambiguity. Examples: profit, cash, a target, another center or
  period, a comparison or ranking, or an unrelated question. This preserves
  the existing contracts: requirements that no recipe can satisfy decline the
  whole request, and multiple ambiguities remain unimplemented.
- `scope`: the unchanged native Overview request shape (`center_code`, `start`,
  `end`, `timezone`).

The property order is:
- `none`: `overview_count`, then the v10 action fields;
- other readings: `overview_count`, then `meaning`, `meanings` or `event`, then
  `other_unsupported`, then `scope`.

**Absent cue (owner decision b2,
[#120 #issuecomment-5886436408](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5886436408)).**
The published schema requires `overview_count`, but the runtime reads a parsed
object without the key exactly as a `none` reading. The rest of the object is
then one v10 action, and a model-authored `count_basis` clarification is still
rejected. The evidence records the absence (`count_reading: "absent"`), so it
never passes silently.

## Kernel count policy

`grepbit/count_policy.py` maps a validated cue to exactly one action. It never
reads question text. The first matching rule applies:

| Rule ID | Condition | Action |
|---|---|---|
| `other_unsupported` | `other_unsupported` is true | decline |
| `bound_seats` | `bound`, `meaning = booked_seats` | request `overview` with `scope` |
| `bound_unsupported` | `bound`, any other meaning | decline |
| `contrast_unexecutable` | `contrast` without `booked_seats` | decline |
| `contrast` | `contrast` with `booked_seats` | clarify `count_basis`, exactly `meanings` |
| `generic_booking` | `generic`, `event = booking` | clarify: `booked_seats`, `known_booking_accounts`, `distinct_people` |
| `generic_unframed` | `generic`, `event = none` | clarify: all four meanings |

Kernel-built clarifications:
- Choices appear in `COUNT_BASES` order. Each choice ID equals its meaning
  value, for example `booked_seats`.
- Every choice carries the cue's `scope`.
- The unchanged `Clarification` validators and `render_clarification` apply.

The user-visible clarification object, presentation, choice values and resume
binding are unchanged. `contrast_unexecutable` follows the existing rule that a
`count_basis` clarification must include `booked_seats`: a choice between
unsupported meanings can only end in a decline.

## Authority, validation and evidence

**Authority.** For a `none` or absent reading, the model's action is used as in
v10, with `count_basis` excluded. For any other reading, the kernel policy is the only
author of the action. For Overview counts, the model's decline authority moves
into the cues: a `bound` unsupported meaning, or `other_unsupported`.

**Validation.** Every non-`none` cue is validated before any rule applies,
whichever action results:
- its exact key set and value types;
- the meaning values;
- the native `OverviewRequest` scope;
- the question binding: the scope's center code must appear literally in the
  question, as `Clarification.validate_question` already requires.

A rejected cue raises `invalid_request` with one of three new closed reasons:

| Reason | Cause |
|---|---|
| `count_cue_shape` | unknown key set or value type |
| `count_cue_values` | unknown meaning or event, fewer than two or duplicate contrast meanings, or an invalid native scope |
| `count_cue_binding` | the scope's center code does not appear in the question |

A `none` or absent-cue object carrying a model-authored `count_basis`
clarification is rejected with the existing reason `clarification_shape`. An
`overview_count` value outside the four strings is `count_cue_shape`. A cue is
a typed contract, so no rejected cue falls back to a decline.

**Decline code.** A policy decline raises the existing action-level error
`model_declined`, with the same stages as a v10 model decline. Grading,
`model_outcome` and the report outcome are therefore unchanged.

**Runtime evidence.** Four new fields, none containing question text:
- `count_reading`: `absent`, `none`, `bound`, `contrast` or `generic`. It is
  null when no JSON object was parsed, or when `overview_count` is not one of
  the four strings.
- `action_source`: `model` or `count_policy`. It is null exactly when
  `model_outcome` is null (no action admitted).
- `count_policy_rule`: the rule ID when the source is `count_policy`,
  otherwise null.
- `count_cue`: the validated non-`none` cue, including its native scope, or
  null.

**Live report projection.** The closed projection in
`tools/p3_live_evidence.py` additionally keeps `count_reading`,
`action_source` and `count_policy_rule`, which are closed enumerations. Their
values are validated, a rule is present exactly when the source is
`count_policy`, and that source requires a `bound`, `contrast` or `generic`
reading. `count_cue` is not projected, because it carries the scope. Historical
reports lack the three fields and stay valid. The observation fields, report
version, grader and scorer are unchanged.

## Runtime context and identity

- **Context `learningops-recipe-context-v6` and instruction
  `recipe-selection-instruction-v7`.** These start from v10's bytes (v7) with
  these changes:
  - `clarification.count_basis` is replaced by a top-level `count_cues`
    section stating the vocabulary above;
  - the Overview `unsupported` entry "people counts" is removed, because the
    cues now represent it;
  - the instruction's count choice-set sentence is replaced by the cue order:
    read the count first, report it, then act. The `metric_meaning`
    requirements stay.

  The Compare, Breakdown, center and metric_meaning text is unchanged.
- **Registration:** candidate `p3-count-cue-policy-v11`, registered after v10,
  with a new semantic identity.
- **Unchanged:**
  - `grepbit/clarification.py` (the model schema is filtered in
    `recipe_model`);
  - cases, oracles, panels, gold, grader and scorer;
  - the P1/P2 paths.

## Request size (owner decision A, #120)

v11 does not fit within the complete-request cap of 32,768 bytes.
- **v10:** 31,808 bytes with a maximal 4,096-byte question, leaving about
  960 bytes of headroom.
- **v11:** 36,888 bytes with a maximal question. Even a 73-byte question
  exceeds 32,768 bytes.
- **Why v11 is larger:**
  - the three cue branches each carry the full Overview scope shape;
  - the output schema is sent twice: once in the prompt context and once as
    `response_format`.

The owner chose in chat on 2026-09-29
([#120 #issuecomment-5886754433](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5886754433))
to raise the complete-request cap:
- `grepbit.gateway.MAX_REQUEST_BYTES` becomes 40,960 for every path.
- The `tools/p3_eval.settings()` manifest value changes with it.
- The question cap (4,096 bytes) and response cap (131,072 bytes) are
  unchanged.
- The model-visible prompt stays exactly as specified above.

The historical statement of the old cap in
`docs/clarification-action.md` is kept, with a dated amendment note. Baseline
comparison checks only case order, so v7 and v10 baselines stay comparable.

**Correction (2026-09-29, defect #122, owner decision A recorded there).** The
last sentence above was wrong. Archive readers validate the whole archived
packet, including its `settings`, not only case order. After the v11 merge
(`6050dc0`), every archive prepared before it failed read-back as
`invalid_manifest`, because it records `max_request_bytes` 32,768. That
included all five baselines that grant #79 names. The fix records the cap per
candidate:
- `tools/p3_eval.settings(n, max_request_bytes=40960)` keeps 40,960 as the
  current default. The known caps are exactly 32,768 and 40,960; any other
  value is `invalid_manifest`.
- `tools/evaluate.py` prepares a packet at the candidate's registered
  `limits.request`: 32,768 for v7–v10 and 40,960 for v11. Archive read-back
  stays registry-free and accepts an exact settings match at a known cap.
- The `p3_eval` manifest reader and the `p3_admission` freeze validator accept
  an exact match at the cap the archive recorded, if that cap is known.
- The six `tools/history/*` readers validate at the historical 32,768. Every
  archive they read predates v11; they are not the entry for new runs.

The gateway cap, the v11 runtime, schema and ruler are unchanged.

## Compatibility (owner decision, #120)

The owner decided both points in chat on 2026-09-29
([#120 #issuecomment-5886436408](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5886436408)).

**Offline fake responses.** The four v1 fake-response files stay
byte-unchanged:
- `evals/dev/dev-responses-v1.json`
- `evals/dev/bound-meaning-responses-v1.json`
- `evals/dev/mechanism-probe-responses-v1.json`
- `evals/p3/development-responses-v1.json`

Their actions carry no cue, so under b2 they run as `none` readings. The 22
model-authored `count_basis` actions among them are rejected in v11:
- C1 ×3 in dev54;
- BM6 ×3 and BM7 ×3 in bound-meaning;
- BM6 ×3 and MN1–MN3 ×3 in the mechanism probe;
- `C01_count_basis.en` in the P3 development panel.

Each file therefore gets a `*-cued-responses-v1.json` sibling, with the same
script envelope (`p3-fake-responses-v1`). Only those 22 actions are replaced,
by cued actions:
- For the dev panels, each cue is the reviewer's reading of the question, from
  `tests/fixtures/count-cue-readings-v1.json`. The scope is the Overview scope
  of the v1 action's choices.
- `C01_count_basis.en` was not in the review packet. Its cue is agent-authored
  scripted reference data: `contrast` with `booked_seats` and
  `known_booking_accounts`, the two meanings the question names.

Offline tests that run these actions through the current runtime are
re-pointed to the cued files. Tests that pin the v1 files' identities are
unchanged.

**Bedrock.** `grepbit/bedrock.py` pins the v10 recipe schema hash, so the
`bedrock_converse` route fails closed (`invalid_input`) for v11 before any
transport call. v11 makes no Bedrock claim. The Bedrock compaction tests keep
exercising the unchanged compaction against a frozen copy of the v10 schema,
`tests/fixtures/recipe-output-schema-v2.json`. Its canonical JSON (sorted keys,
compact separators, as `converse_schema` hashes it) must hash to the Bedrock
pin.

## Frozen source change (owner decision, #120)

`tests/test_recipe_clarification.py` is an accepted source of the frozen
baseline `20abb5592262c77c98f9cabeaf7cf4854edb6fbe`, pinned in
`tests/test_p3_exposed.py`. Four of its tests encode the P2 behavior that
Option C and `b2_absent_is_none` replace:
- a model-authored `count_basis` clarification succeeds;
- the default clarification payload is a model-authored `count_basis`;
- the output schema has exactly five branches, the first four P2-exact.

The owner approved amending the file in chat on 2026-09-29
([#120 #issuecomment-5887377752](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5887377752)):
- `count_basis` is exercised through a policy-authored contrast cue, and a
  model-authored `count_basis` is asserted to fail with `clarification_shape`;
- the default payload becomes `metric_meaning`;
- the schema test strips `overview_count: "none"` from the first four
  branches, which must still hash to the P2 output contract and
  response-format identities, and expects eight branches.

`tests/test_p3_exposed.py` pins the new hash. It keeps the baseline hash
`42b0ce5c…` as superseded ancestry, checked against the Git snapshot at
`20abb55`, and cites the decision. The frozen evaluator files and P3 assets
stay byte-identical.

## Semantic acceptance and readings

The owner designated a fresh-context semantic reviewer (#120). Its steps:

1. It reads only a review packet:
   - the vocabulary, cue contract and policy table sections of this document;
   - the accepted P3 contract rows A01, A02, C01, C04, D04 and D08;
   - the [clarification action](clarification-action.md) contract;
   - a questions-only projection of the unique inputs of the three current dev
     panels: bound-meaning, mechanism probe and dev54. Inputs are keyed by
     opaque IDs; case IDs encode the expected branch, so they are left out.
2. It checks the policy table against C01 and the accepted contracts, and
   reports any conflict.
3. It writes one cue reading per input. It never sees branches, oracles,
   results, the runtime context or earlier readings.

The agent stores the readings verbatim as
`tests/fixtures/count-cue-readings-v1.json`, keyed by question SHA-256, with
the reviewer's disclosure and the packet's SHA-256. The ruler then compares the
policy outcome of every reading against the accepted oracles.

A mismatch, or a reviewer conflict, is a stop before production code. The
oracles are never edited to match, and the readings are not re-authored from
the oracles. The readings are ruler data, never runtime context.

**Outcome (2026-09-29)**, recorded at
[#120 #issuecomment-5886276590](https://github.com/cinic0101/grepbit/issues/120#issuecomment-5886276590):
- Policy review: no blocker.
- 93 readings with no uncertain ones: 30 non-`none` and 63 `none`.
- The agent's mechanical comparison found 0 mismatches across the 33 panel
  rows with a non-`none` reading.
- Every `count_basis` oracle has a non-`none` reading.

## Ruler

`tests/test_count_cue_policy.py` is committed failing before production code.
It checks:

- **The policy table:** every rule, the rule order, choice order and IDs, and
  the invariants (2–4 choices, `booked_seats` present).
- **The schema:**
  - `overview_count` is first in every top-level branch;
  - model `clarify` excludes `count_basis`;
  - the non-`none` shapes;
  - the new closed reasons.
- **Fake-transport end-to-end:**
  - policy clarify and decline;
  - seats execution against the fixture database;
  - the `none` and absent-cue passthrough;
  - rejection of model `count_basis` under `none` and absent cues;
  - every rejected-cue reason;
  - the evidence fields;
  - the live projection.
- **Readings consistency:**
  - for every non-`none` reading, the policy action matches the accepted
    oracle's branch: an `overview` request, the exact `count_basis` value set,
    or a decline;
  - every `count_basis` oracle has a non-`none` reading, since v11 reaches
    `count_basis` only through cues.
- **Compatibility:**
  - the v1 fake-response files are byte-unchanged;
  - each cued file differs from its v1 sibling exactly in the 22 listed
    actions, and its dev-panel cues equal the readings fixture;
  - every cued file is graded correct end-to-end through the fake transport;
  - a Bedrock client fails closed on the v11 schema before transport;
  - the frozen v10 schema fixture hashes to the Bedrock pin.
- **Request size:**
  - the caps are 4,096, 40,960 and 131,072 bytes, both in the gateway and in
    the evaluation settings;
  - a maximal 4,096-byte question is sent within the cap.
- **Frozen source:**
  - the amended `tests/test_recipe_clarification.py` matches its new pin;
  - its superseded baseline hash equals the file at `20abb55`.
- **Identity:**
  - v11 is registered and current;
  - the v10 registry entry is byte-identical.

## Measurement

Measurement happens only under grant #issuecomment-5886058844, strictly in
order, stopping at the first failed gate:

1. probe 22: the count group 12/12;
2. bound-meaning 24: v7's 20 correct inputs stay correct, plus `dev-BM6` ×3;
3. dev54: 54/54;
4. formal 28: no failure beyond `E02_compare.en`;
5. holdout-a 18: `HA02...en` fixed, and no new failure (observed_regression).

A failed gate falls back to Option A (v10). No rerun, and no fourth
count-family fix.

## Result: step 1 failed, sequence stopped (2026-09-29)

Step 1 ran from `dev` `43bf6d3`, after the #122 archive read-back fix (#123)
and before any other step. Run
`p3-dev-mechanism-probe-v1--litellm-gemma-4-31b--p3-count-cue-policy-v11--277108e76945`,
report `5e51cd65…965d5d57`, recorded in `evals/runs/index.jsonl`; details are
in #79 #issuecomment-5890680433.

Execution was clean: 22/22 inputs, 22 client attempts, all HTTP 200 from
`gemma-4-31b`, no operational error, 135.2 s. Overall 12/22 inputs (v9
baseline 12/22), 8/14 families. Against v9: 7 fixed, **7 new regressions**.

**The gate failed: 5/12 in the count group, not 12/12.**
- `dev-BM6` en/ja and `dev-MN2` ×3 are now correct (`generic`, rule
  `generic_booking`, three choices).
- `dev-MN1` ×3 and `dev-MN3` ×3 regressed. Each got the three-choice booking
  set (rule `generic_booking`) instead of all four meanings. The model set
  `event = booking` in all three languages, though the questions ("…overview …
  including the headcount", "What was the headcount…") contain no booking
  wording. The kernel applied the table as reviewed. The evidence is
  consistent with the Overview context's booking framing leaking into the
  per-question `event` cue. That is not established causally.
- `dev-BM6.zh-TW` was read as a bound `booked_seats` count and answered, a
  missed clarification.

On the ungated diagnostic Compare inputs, which the model still authors:
- `E02_compare.en` and `dev-MC4.en` became complete correct;
- `dev-A3.en` became a false `comparison_roles` clarification.

This is exposed development data at temperature 0, one observation per input.

Per the grant, the sequence stopped: no rerun and no fourth count-family fix.
Steps 2–5 did not run, and 22 of 146 calls were used. The fallback to v10 is
the owner's decision. v11 is not an accepted improvement.

## Limits and risks

- **Cue errors still exist.** A wrong reading still gives a confident wrong
  action. Examples:
  - `bound booked_seats` for a two-month question executes a one-month
    Overview, unless `other_unsupported` is set;
  - reading headcount as `generic` rather than `bound distinct_people` is the
    model's judgment.

  Only the derivation of the choice set becomes deterministic.
- **Changed context.** The context change is larger than a sentence and may
  move Compare decisions (v9 moved `dev-A4`). Steps 2–4 measure this.
- **Unverified property order.** That the serving grammar emits
  `overview_count` first follows from the schema's property order and
  constrained decoding. It is not verified on the route. The prompt shows the
  schema with sorted keys.
- **Diagnostic limit.** Live reports keep the reading kind, the rule and the
  action source, but not the cue's meanings or scope.
- **Absent cues.** An absent cue (b2) runs the model's own v10 action. A route
  that does not enforce required properties could bypass the cues; the reports
  show this as `count_reading: "absent"`.
- **Out of scope.** `E02_compare.en` and the comparison roles (Option D) are
  not addressed.
