# Generic-count context v9 (#79)

The owner approved this repair in chat on 2026-09-29: "同意按照你的計劃來修正"
("Agree to proceed with the fix according to your plan"). The owner then selected
`base=v7, grant=full` on the agent's concrete proposal. Both are recorded, with the
full bounded sequence and stop conditions, in the
[standing grant](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5884877697).
This is the single approved count-family exception for goal #79.

## Evidence and hypothesis

The [mechanism probe](mechanism-probe-controls.md) on unchanged v8 reproduced
an HA02-class English false decline on dev. `dev-MN1.en` asks for an Overview
"including the headcount"; `dev-MN3.en` asks for "the headcount". Both declined,
while their zh-TW and ja variants gave the four-choice `count_basis`
clarification. v7 showed the same class on holdout re-observation:
`HA02_C01_headcount_ctr_b01.en` was `wrong_action` (a decline). Count guidance is
byte-identical in v7 and v8.

Hypothesis, not proof: v7's count guidance tells the model that a generic
people or count noun can express attendance events, and that attendance
requires declining the whole request. The English generic noun alone is then
read as the declined meaning. The repair says what that noun without a stated
basis means: none of the declined meanings, only an unresolved count. The
sentence was drafted from the dev probe inputs. Holdout question text was not
consulted.

## Exact context specification

Candidate `p3-generic-count-context-v9` is registered after v8, so its
registry ancestor is v8. Its runtime context is v7's, with exactly one sentence
added and a new version:

- `CONTEXT_VERSION`: `learningops-recipe-context-v5`.
- `recipes.compare.scope` and `clarification.comparison_roles` return to their
  exact v7 (b332881) strings. This withdraws the failed v8 Compare text rather
  than repairing it:
  - scope: "Distinct explicit current and baseline months; no center filter."
  - comparison_roles: "Two explicit months without orientation; preserve both months and offer both roles."
- `clarification.count_basis` gets one sentence, inserted immediately after the
  sentence "If the question requires attendance_visits, distinct_people or
  known_booking_accounts, decline the whole request, including when it also
  requires a supported Overview." It sits there so that "those meanings" names
  exactly those three:

  > A generic people or count noun alone, without a stated attendance event, deduplication of actual persons or a booking-account basis, requires none of those meanings and leaves the count meanings unresolved.

Intended canonical context SHA256:
`fda52fcfa93210dbe80632ac218db73d1221ab024c0572b9fe70d40c3b89c68e`.

Everything else is unchanged: the instruction, output contract and schema,
native validators and execution, catalog, source profile and limits. That
includes the Overview `unsupported` entry "people counts". No case, oracle,
panel or gold changes. Old candidates and reports stay immutable.

The ruler `tests/test_generic_count_context_candidate.py` is committed failing
before the production edit. It checks four things:

- the exact context digest;
- the two v7 Compare strings;
- the inserted sentence and its position;
- that removing that sentence and restoring the v3 version reproduces v7's
  registered context digest byte for byte.

It also checks the invariant instruction, schema, P1 and limits identities, the
v7 and v8 archive digests, and wire sizes. All of this is static identity
evidence. It does not show whether the model follows the rule.

## Gates

This is a strictly sequential live sequence. Each step runs only after the
previous gate passes, with at most 146 calls. The bounds, route and stop
conditions are those in the recorded grant.

| Step | Panel | Baseline | Gate |
|---|---|---|---|
| 1 | `p3-dev-mechanism-probe-v1`, 22 inputs | v8 `77c92631` | `dev-MN1.en` and `dev-MN3.en` become the correct clarification; no MN1–MN3 input declines |
| 2 | `p3-dev-bound-meaning-v1`, 24 inputs | v7 `d9216e88` | all 20 v7-correct inputs stay correct |
| 3 | `p3-dev-matrix-compare-first-v2`, 54 inputs | v7 `920e2e9e` | 54/54 |
| 4 | `p33-formal-v2`, 28 inputs, regression | v7 `cf87960c` | no failure beyond `E02_compare.en` |
| 5 | `p3-holdout-a-v2`, 18 inputs, observed regression only | v7 `4d102110` | `HA02_C01_headcount_ctr_b01.en` fixed; no new failure |

Pre-registered known failures stay in every denominator: `E02_compare.en`
everywhere, and `dev-BM6` ×3 on step 2. They are reported but not gated.

- **Step 1 compares against a v8 baseline.** Step 1's Compare inputs change
  base text between baseline and candidate, so their changes there are
  diagnostic. Its gate covers only the count group.
- **Choice-set discrimination is not a target.** v8 emits one fixed four-choice
  menu, which leaves `dev-BM6` and `dev-MN2` failing. Changes among failing
  outcomes are reported as diagnostic.
- **A failed gate stops the sequence.** There is no rerun, no further count
  fix and no automatic next candidate.

## Limitations

- E02 is recorded as a known Gemma 31B limitation: a safe false clarification.
  Its structural extraction-before-action alternative would change the output
  contract, so it is deferred to a separate decision.
- All five panels are exposed data. HA02 is regression data once it informs
  this fix, so step 5 is not fresh generalization evidence.
- One temperature-0 observation per input cannot isolate the causal effect of
  one sentence.
- The restored v7 Compare text brings back v7's measured Compare behavior,
  including E02's failure; it does not repair it.
