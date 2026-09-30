# Candidate v13: stated count assumption (#136)

Candidate `p3-count-assumption-v13`, whose ancestor is `p3-v10-restoration-v12`. It is
the runtime half of ADR #136, as amended in
[#136 #issuecomment-5904225044](https://github.com/cinic0101/grepbit/issues/136#issuecomment-5904225044),
and step (3) of the owner's grant
[#79 #issuecomment-5904208402](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5904208402).
The evaluation half, meaning the annex, the v2 dev panels and the annex
verdict, is `docs/count-assumption.md` (#138). The v12 baseline on the v2
panels is `docs/count-assumption-evaluation.md` (#139).

The owner's rule, approved at
[#79 #issuecomment-5903712127](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903712127):

| Question type | Expected behaviour |
| --- | --- |
| A generic people or count noun, meaning unresolved | Answer with booked seats, stating the assumption and the unavailable meanings |
| A count bound to booked seats | Answer |
| The user says the basis is undecided between named meanings | Clarify with the stated meanings |
| An unsupported meaning is required | Decline |

Only the identity plumbing files of `tests/fixtures/p310_identity_baseline.json`
(`grepbit/recipe_model.py`, and `grepbit/gateway.py` and `grepbit/model.py` if
needed) may change. The kernel, the presentation module and the frozen
evaluator stay byte-identical.

## Model-facing changes

1. **Output.** An Overview proposal may carry exactly one extra top-level key:

   ```json
   {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
    "request": {"center_code": "...", "start": "...", "end": "...", "timezone": "Asia/Taipei"},
    "assumption": {"count_basis": "booked_seats"}}
   ```

   The key is absent, never null, when there is no assumption.
2. **Schema.** Only the Overview request branch of the output schema gains the
   optional property `assumption`: a closed object whose only property,
   `count_basis`, is the constant `booked_seats`. It is not required. No other
   branch changes.
3. **Instruction.** `SYSTEM_INSTRUCTION` states the rule:
   - a generic people or count noun (headcount, number of people, how many
     people) with no named event, population or basis is answered with the
     Overview request and `assumption`;
   - `count_basis` is used only when the question itself leaves the basis
     undecided between named meanings, and then offers exactly those meanings;
   - an explicitly required unsupported meaning still declines.
4. **Context.**
   - The `count_basis` clarification text is narrowed the same way.
   - A new context entry, `count_assumption`, gives the assumed basis, what
     the answer reports ("confirmed booked seats") and the unavailable
     meanings.
   - The Overview recipe's unsupported item "people counts" becomes
     "required account/attendance/distinct-people counts".
5. **Versions.** The instruction, context, output-contract and
   structured-output versions all change, so the candidate identity changes.

## Runtime changes (`grepbit/recipe_model.py`)

- **Parsing.** `_proposal` accepts the optional `assumption` only on an
  Overview request and only with the exact value above. Anything else is
  `invalid_request`, with reason `root_shape`.
- **The proposal object.** `RecipeProposal` keeps the assumption, and
  `to_dict()` includes it only when present. So the persisted validated action
  carries it, in the closed shape that `docs/count-assumption.md` admits.
- **Execution** is unchanged: the native `OverviewRequest` and the kernel see
  the same request, and the pack already carries seats.
- **Statement.** `assumption_statement(proposal)` returns the closed statement
  the product shows, or `None`:

  ```json
  {"count_basis": "booked_seats", "reported_as": "confirmed booked seats",
   "unavailable": ["known_booking_accounts", "attendance_visits", "distinct_people"]}
  ```

  The unavailable meanings are the catalog's other count bases, in their
  catalog order. The statement is not graded by the evaluator. Its content is
  pinned by the ruler.

## Routes and limits

- **LiteLLM 31B** is the route under evaluation.
- **Bedrock fails closed for v13.** `grepbit/bedrock.py` pins the v12 recipe
  schema digest, so the changed schema is refused before any send. This is as
  v11 did. The Bedrock tests keep exercising the frozen v12 schema.
- **Request size.** The complete request stays within the unchanged
  32,768-byte cap for every question on the dev panels and for a full
  4,096-byte input. The ruler checks this through the gateway client. For the
  4,096-byte input the request grows from 31,826 bytes (v12) to 32,671 bytes,
  so the headroom is now 97 bytes. The owner said the cap may be raised; v13
  does not use that, so the limits stay part of the unchanged identity. A later
  candidate that adds model-facing text will need it.

## Evaluation (the grant's steps 4 and 5)

- **Runs.** One v13 run on each v2 dev panel under the grant, 46 calls.
- **Gate.** Then `tools/evaluate.py --gate --candidate p3-count-assumption-v13
  --baseline-candidate p3-v10-restoration-v12 --route litellm-gemma-4-31b
  --owner-authorization-reference <grant> --panels p3-dev-bound-meaning-v2
  p3-dev-mechanism-probe-v2`.
- **Verdict.**
  - It is pre-registered. `regression` is a stop: no rerun, and a further PR
    restores v12.
  - `passed` is a development observation on exposed inputs, not promotion.

## Claims and limits

- The rule is checked on the typed assumption only (`docs/count-assumption.md`).
  The statement function is tested offline, and no user-facing UI renders it
  yet.
- This is a single instruction change on one route, one run per panel. It may
  also move unrelated decisions. The gate measures that against v12's stable
  classes.
