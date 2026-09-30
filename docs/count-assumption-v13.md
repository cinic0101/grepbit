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

The instruction implements the first row for a generic **people** count, as the
grant's goal words it ("answers generic people counts"), and every approved
example is a people noun. A generic count noun that is not about people ("how
many were booked", "the count") falls under "otherwise omit assumption". No v2
dev case has that wording, so it is unmeasured.

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
   - with a complete explicit Overview scope, a generic people count
     (headcount, how many people, people who booked) that names no seats,
     accounts, attendance or distinct individuals is answered with the request
     and `assumption`; otherwise the assumption is omitted;
   - `count_basis` is used only when the question itself is undecided between
     named meanings, and then offers exactly those meanings;
   - an explicitly required unsupported meaning still declines. The existing
     decline rules are unchanged.

   The rule names the four count meanings instead of an "event" framing:
   under v11, 31B read booking wording as event framing even on unframed
   headcount questions (`docs/count-cue-policy.md`). The example "people who
   booked" keeps booking wording on a people count from counting as a basis.
   The rule reuses the instruction's existing term "complete explicit Overview
   scope", so a question that asks only for a count (`dev-MN2`, `dev-MN3`) is
   covered, and a count noun is not meant to turn a Compare, Breakdown or
   multi-month question into a narrowed Overview. No run-panel question
   combines a count noun with those. "Otherwise omit assumption" closes the
   rule for questions bound to seats (`dev-BM5`) and for questions without a
   people count.
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
- **The proposal object.** `RecipeProposal` keeps the stated basis as an
  immutable `count_basis` string, and `assumption` returns a fresh object.
  Constructing a proposal with a basis on another recipe, or with another
  basis, raises. `to_dict()` includes the assumption only when present. So the
  persisted validated action carries it, in the closed shape that
  `docs/count-assumption.md` admits.
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
  32,768-byte cap for every question on the registered dev-tier panels and for
  a full 4,096-byte input without JSON escapes. The ruler checks this through
  the gateway client.
  - On the evaluated 31B route, that input's request grows from 31,826 bytes
    (v12) to 32,744 bytes, so the headroom is 24 bytes. The request carries the
    model name, so the headroom depends on the route: 21 bytes on the 12B
    route, which the grant does not run.
  - A 4,096-byte input whose JSON escapes (newlines, quotes, backslashes) add
    more than 24 bytes is now refused as `input_too_large` before any send; v12
    tolerated 942. It fails closed.
  - The owner said the cap may be raised. v13 does not use that, so the limits
    stay part of the unchanged identity. A later candidate that adds
    model-facing text will need it.

## Test changes

- **Frozen source change**, by owner decision on #136
  ([#issuecomment-5905969011](https://github.com/cinic0101/grepbit/issues/136#issuecomment-5905969011),
  "照 A 做，核准", "Do it as A; approved"):
  - `tests/test_recipe_clarification.py` checks its P2 schema pin after
    removing the optional Overview `assumption`. It asserts that property's
    exact closed form, and that it is not required. The rest of the file is
    unchanged.
  - `tests/test_p3_exposed.py` pins the new hash and keeps the `20abb559` hash
    as superseded ancestry, verified against Git. This is the v11 pattern (#120).
  - The frozen grading, scoring, expectation and asset sources are unchanged.
- **Bedrock.**
  - The runner's Bedrock route test asserts the fail-closed stop: zero sends.
  - The wire test of `tests/test_invalid_request_reason.py` uses the frozen v12
    schema of `tests/frozen_recipe_schema.py`, as the adapter tests do.
- **The v12 ruler.** `tests/test_v10_restoration_v12.py` asserted that the
  frozen test holds its accepted bytes in the working tree. It now checks that
  v12's merge (#127, `71d0354b`) held them, through Git, and that a later
  amendment keeps them as superseded ancestry. The ruler is not frozen. The
  owner's option A named the frozen test, its pin and `docs/p3-evaluator.md`.
- **Same-bytes rulers.** The gate's `same_bytes` refusal and the aggregate's
  same-bytes inclusion used v7, which shares v12's bytes. They now build a
  registry copy in which the current candidate has a twin
  (`tests/registry_twin.py`), so they no longer depend on which candidate is
  current.
- **Registry pins.** `tests/test_candidate_registry.py` names v13 as current,
  with 12 entries.

## Evaluation (the grant's steps 4 and 5)

- **Runs.** One v13 run on each of the two new v2 panels of #138,
  `p3-dev-bound-meaning-v2` and `p3-dev-mechanism-probe-v2`, under the grant:
  46 calls. The other registered dev panels, including
  `p3-dev-matrix-compare-first-v2`, are not run.
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
  The statement function is tested offline. The runtime does not yet surface it:
  `RecipeInterpretation` and the evidence do not carry it, and no user-facing UI
  renders it. So ADR #136's consequence that the user sees seats labelled as
  seats is not implemented yet.
- This is a single instruction change on one route, one run per panel. It may
  also move unrelated decisions. The gate measures that only on the two run
  panels, against v12's stable classes.
- **Unmeasured near-miss.** `dev-C1` (all three languages; "How many people
  booked at CTR-B01 in March 2026? I am not sure whether you count seats or
  booking accounts.") expects a `count_basis` clarification. Its first sentence
  matches the new rule's trigger, and only its second sentence, which names
  seats and accounts, excludes it. It is on `p3-dev-matrix-compare-first-v2`,
  which the grant does not run and which has no annex. So neither a wrong
  answer there nor a spurious assumption on that panel's Overview answers
  (`dev-A1`, `dev-A2`) is measured. `dev-BM7` covers the "undecided between
  named meanings" row without the "people booked" wording; its zh-TW and ja
  forms do contain 人數 and 人数. Measuring `dev-C1` needs its own owner
  authorization.
- **A second unmeasured near-miss.** `dev-D8`, on the same unrun panel, expects
  a decline. Its zh-TW 「實際到場的人次」 and ja 「実際に出席した延べ人数」 contain
  the people noun and are excluded only because they name attendance. The run
  panels have no decline for a required attendance or account count. The
  "unsupported meaning is required" row is measured there only by `dev-BM8`
  (distinct people). That row matters more now that "people counts" has left
  Overview's unsupported list.
- **Precedence with another unsupported requirement.** The new sentence
  matches a question with a complete Overview scope, a generic people count and
  a different unsupported requirement, for example "CTR-A01 March 2026
  headcount and profit". The earlier general rule ("If any required output …
  is unsupported … decline the whole request") still governs, but the new
  sentence does not restate it. No v2 dev case combines the two, so this is a
  known, unmeasured limit. With 24 bytes of headroom it is not restated.
