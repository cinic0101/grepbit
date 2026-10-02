# Recorded count assumption (#169, step A1)

Contract `count-assumption-eval-v2`. It is step A1 of the plan for the owner's
policy A ([#169](https://github.com/cinic0101/grepbit/issues/169)): every
executed Overview states its people-count basis.

- **What it changes.** The evaluation side reads the assumption the server
  stated, not one derived from the model's action.
- **What it does not change.** No runtime, candidate, panel, annex or oracle
  changes, and no model call.

## Why

The annex verdict (`docs/count-assumption.md`) compares the assumption a row
states with its oracle's expectation. Today the evaluator derives that
assumption from the persisted model action:
- v13's explicit `assumption` key;
- v16's `count_request: "unresolved"`;
- from v19 on, a `count_basis` clarification on a row recorded `answer`.

**The derivation is exact today, on every frozen-correct row.** Through v21,
every row that can be frozen-correct states the assumption exactly when that
derivation says so. A kernel failure or a post-execution timeout records
`null` where the derivation would say stated. Those rows carry an operational
error and are never assessed.

**Under policy A it would not be.** The runtime states it on every executed
Overview, whatever the model's count reading (#169). An action with
`count_request: "none"` would then state it under v22 and not under v21, and
the action alone cannot tell the two apart.

**The runtime already reports the statement, but it is lost.** The runtime's
evidence already carries `count_assumption` (`grepbit/recipe_model.py`), but
the archived evidence projection drops it.

## The contract

- **Archived evidence records the statement.**
  - **The new field.** `count_assumption` joins the closed projection
    (`tools/p3_live_evidence.py`, `_EVIDENCE_FIELDS`).
  - **Its value** is `null`, or exactly the archived statement pinned there as
    `ARCHIVED_COUNT_ASSUMPTION`:
    `{"count_basis": "booked_seats", "reported_as": "confirmed booked seats",
    "unavailable": ["known_booking_accounts", "attendance_visits",
    "distinct_people"]}`. The value is pinned rather than imported from the
    runtime, as the other archived vocabularies are.
  - **Any other value fails readback** (`invalid_asset`).
- **The verdict reads the recorded statement first.** `annexed` uses the row's
  recorded `count_assumption` when its evidence has the key: `null` states
  none, and the statement states `{"count_basis": "booked_seats"}`.
- **Older rows keep today's derivation.** A row whose evidence lacks the key
  (every report recorded before this contract, an outer-deadline timeout, or no
  evidence) keeps the derivation from its action. Old reports read back, record,
  aggregate and gate as before.
- **Replay.** The replayed verdict reads the statement of the replayed run (the
  current runtime's evidence), never the archived one. This is the same rule as
  #161: each verdict reads its own row.
- **Consistency through v21.** On a run made under v21, the recorded statement
  equals the derivation on every completed row with a persisted action,
  frozen-correct or not. Kernel-failure and post-execution-timeout rows, which
  are never assessed, record `null`. The ruler checks this on a synthetic run.
- **A statement implies no error.** A non-null recorded statement on a row
  with an `error_code` fails readback. A replayed statement is validated
  exactly like an archived one.

## Not covered

- **The count ablation** (`tools/count_ablation.py`) archives no evidence per
  row, so its annex verdict keeps the derivation from the action. That is exact
  for every candidate through v21.
  - **Under a runtime whose statement departs from the action** (v22), its
    verdicts would be wrong.
  - **Before it is used under such a candidate,** its rows must record the
    statement too.
- **Formal and holdout readers.** Their code is unchanged, but they share the
  widened projection, so a new run through them records the field too. Old
  archives are unaffected.

## Ruler (`tests/test_recorded_count_assumption.py`)

Committed failing before the implementation and passing after it, in the same
PR:
- **The projection.** It keeps `count_assumption` (`null` or the archived
  statement), rejects any other value, and leaves a missing key missing.
- **The recorded statement wins over the derivation, both ways:** a recorded
  statement with `count_request: "none"` states it, and a recorded `null` with
  `count_request: "unresolved"` states none. A row without the key keeps the
  derivation.
- **The live path records it.** On a synthetic run under the current runtime,
  every evidence row has the key, and every frozen-correct row's recorded
  statement equals the derivation.
- **Replay** reads the replayed run's statement. Under a patched runtime that
  states the assumption on every Overview (as policy A will), an archived
  `count_request: "none"` row is `replayed_changed`, with the annex verdict
  going from `correct` to `wrong` against an oracle that expects none.
