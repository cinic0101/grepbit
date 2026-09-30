# Candidate v16: typed count reading (#146)

Candidate `p3-count-reading-v16`, whose ancestor is `p3-compare-orientation-v15`.
It implements ADR #146, option A. The owner delegated this step at
[#142 #issuecomment-5913563185](https://github.com/cinic0101/grepbit/issues/142#issuecomment-5913563185),
and the grant is
[#146 #issuecomment-5913589336](https://github.com/cinic0101/grepbit/issues/146#issuecomment-5913589336).

**The model reads the count, and code decides.** Every Overview request carries a
typed `count_request`. The code decides whether the answer states the owner's
count assumption (ADR #136) or declines an unavailable count. v15's Compare
orientation is unchanged.

The only runtime file that changes is `grepbit/recipe_model.py`. The kernel,
`compare.py`, `clarification.py`, `presentation.py` and the frozen P3.3
evaluator stay byte-identical.

## Model-facing changes

1. **Output.** An Overview proposal carries exactly one extra top-level key:

   ```json
   {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
    "count_request": "unresolved",
    "request": {"center_code": "...", "start": "...", "end": "...", "timezone": "Asia/Taipei"}}
   ```

   - It is required on Overview and absent on Compare and Breakdown.
   - The values are the reading diagnostic's (`docs/reading-diagnostic.md`):
     - `none`: the question asks for no count;
     - `booked_seats`, `known_booking_accounts`, `attendance_visits` or
       `distinct_people`: the count it names;
     - `unresolved`: it asks for a count whose meaning it leaves open.
2. **Schema.** The Overview request branch gains the required property
   `count_request`, with those six values in that order. No other branch changes.
3. **Instruction.**
   - Every Overview request carries `count_request`, with the definition above.
   - The server answers an unresolved count with booked seats and states the
     assumption, and it declines a named unavailable count.
   - `count_basis` is used only when the question itself is undecided between
     named meanings.
4. **Context.**
   - The `count_basis` clarification note is narrowed the same way.
   - The Overview recipe's unsupported item "people counts" becomes "named
     account/attendance/distinct-people counts".
5. **Versions.** The instruction, context, output-contract and
   structured-output versions all change, so the candidate identity changes.

## Runtime changes (`grepbit/recipe_model.py`)

- **Parsing.** `_proposal` requires `count_request` on Overview and
  `orientation` on Compare, each with one of its values, and refuses them on any
  other recipe. Anything else is `invalid_request`, with reason `root_shape`.
- **The proposal object.** `RecipeProposal` keeps `count_request`, and
  `to_dict()` includes it only when present.
  - A proposal constructed directly without it stays valid.
  - `assumption` is `{"count_basis": "booked_seats"}` exactly when
    `count_request` is `unresolved`.
- **The decision in code:**
  - `none` or `booked_seats`: execute as v15 does, with no assumption.
  - `unresolved`:
    - execute as v15 does;
    - the evidence carries `count_assumption`, the ADR #136 statement:
      `{"count_basis": "booked_seats", "reported_as": "confirmed booked seats", "unavailable": ["known_booking_accounts", "attendance_visits", "distinct_people"]}`.
  - `known_booking_accounts`, `attendance_visits` or `distinct_people`:
    - nothing executes, and the result is the decline `model_declined`, exactly
      as when the model declines itself;
    - `source_proposal` keeps the model's request, as for v15's server-built
      clarification.
- **The model's `count_basis` clarification** stays a model action and is
  unchanged. It is limited by the text to questions that are themselves
  undecided between named meanings.

## Evaluation side

- **Persisted action.** The persisted validated action is the model's typed
  request, including for a server decline, so replay rebuilds the same result.
- **`tools/evaluate.py`:**
  - `_action_shape` admits `count_request` only on an Overview request, with one
    of its values. It never admits it together with v13's `assumption`.
  - `_check_action` reads an Overview request with an unavailable count as the
    action `decline`, with the evidence of a decline.
- **The annex verdict** (`docs/count-assumption.md`) reads the assumption that
  an action states:
  - a v13 action states it with `assumption`;
  - a v16 action states it with `count_request: "unresolved"`.

  So a `count_request` other than `unresolved` states none.
- `tools/reading_diagnostic.py` and `tools/routing_upper_bound.py` read the
  derived decline the same way.

## Frozen source change (needs the owner's approval, #146)

This change is made only after the owner approves it and the approval is
recorded:
- `tests/test_recipe_clarification.py`'s P2 schema pin is checked after
  removing the Overview `count_request` property and its `required` entry,
  whose exact form it asserts.
- The P2 Overview meanings carry `count_request: "none"` through the shared,
  unfrozen `proposal()` helper.
- `tests/test_p3_exposed.py` pins the new hash and keeps `42b0ce5c…` as
  superseded ancestry.

## Offline scripts

The v1 scripts stay immutable, and so do v15's `*-oriented-responses-v1.json`.
Each gets a derived v16 sibling, `*-read-responses-v1.json`:
- The derivation is `tests/oriented_actions.py` `read()` applied after
  `orient()`: an Overview request gains `count_request: "none"`, which executes
  exactly as before. Every other action is unchanged.
- The ruler checks each sibling byte for byte.

## Routes and limits

- **LiteLLM 31B** is the route under evaluation.
- **Bedrock** fails closed, as for v15.
- **Request size.** The ruler checks every dev-tier question and a full
  4,096-byte input against the unchanged 32,768-byte cap.

## Evaluation (the grant's steps 3 and 4)

- **Runs.** One v16 run on each of `p3-dev-bound-meaning-v2` and
  `p3-dev-mechanism-probe-v2`, 46 calls, after the v15 sentinels of step 1.
- **Gate.** `tools/evaluate.py --gate --candidate p3-count-reading-v16
  --baseline-candidate p3-compare-orientation-v15 --route litellm-gemma-4-31b
  --owner-authorization-reference <grant> --panels p3-dev-bound-meaning-v2
  p3-dev-mechanism-probe-v2`.
- **Verdict.** It is pre-registered. `regression` is a stop and a revert,
  with no rerun.

## Claims and limits

- **The hypothesis under test.** 31B's accurate diagnostic `count_request`
  reading carries over to the production call. And with the assumption
  decided in code, a named-seats question can no longer gain one.
- **The model's `count_basis` clarification remains prose-decided.** The v12
  failure was false clarifications on generic counts, and it may persist.
- **Scope.** One route, one run per panel, exposed inputs. It is not promotion.
