# Candidate v19: the server answers a count_basis clarification (#158)

Candidate `p3-count-basis-answer-v19`, whose ancestor is `p3-count-scope-v18`.
It is scope 1 of ADR #158 and step (3) of the grant
[#158 #issuecomment-5927141003](https://github.com/cinic0101/grepbit/issues/158#issuecomment-5927141003)
(owner: 「ok 同意 with 308 次」).

## Why

The owner decided that a clarification is offered only when every offered
choice can be answered (#158). Booked seats is the only executable count, so
no `count_basis` choice set is fully answerable.

On the fresh count panel (#157), v18 handled the user's own undecided choice as
a two-choice clarification (D, 6/6 under the old oracles). It also clarified
every doubt about the system's basis (B, 0/9). The count ablation found no
prompt text that moves B.

The read-then-decide pattern already used for Compare orientation (v15) and
the count reading (v16) fits: the model's clarification is a reading, and the
code decides the action.

## The change

**Runtime** (`grepbit/recipe_model.py`):
- When a model `count_basis` clarification passes the existing validators (the
  shape, the choices, the scope and the question check), the server does not
  present it. Instead it answers the clarification's own Overview scope with
  `count_request: "unresolved"`, so the stated assumption follows as in v16:
  booked seats, with the unavailable meanings named.
- The rule is `_server_answers(clarification)`: a clarification is offered
  only when every choice is answerable, and booked seats is the only
  executable count.
- `RecipeInterpretation.source_clarification` and the evidence key
  `source_clarification` keep the model's clarification for as long as the
  server-built proposal is kept. So a kernel failure or a timeout after the
  answer still persists the model's own action.
- **Unchanged:** other clarification kinds, model requests, declines, the v15
  roles clarification and the v16 decline.
- **Changed by the answer:** a `count_basis` clarification whose scope is a
  one-month Overview is answered with that Overview, whatever the question's
  analysis type. A `count_basis` clarification always binds an Overview scope.

**Evaluator and diagnostics:**
- `tools/evaluate.py` persists the model's own clarification as the validated
  action, so replay rebuilds the answer.
- **The recorded row decides, never the action alone.** Before v19 the same
  action was a real clarification, and archives keep both kinds of row:
  - A `count_basis` clarification on a row whose recorded `actual_action` is
    `answer` is a v19 server answer. It states the assumption, and the row has
    no clarification observation.
  - On a `clarify` row it is the clarification it was, with its kind and
    choice-count checks, and it states no assumption.
- `_check_action`, `_stated_assumption` and `annexed` apply this rule, so do
  `tools/routing_upper_bound.py`, `tools/reading_diagnostic.py` (`_recorded`)
  and `tools/count_ablation.py`.
- **Without a recorded row**, as with a scripted action, the current runtime's
  answer applies.
- So v18 archives read back, aggregate and gate against v19 unchanged. The
  ruler builds a v18-shaped archive and gates it.

**Model-facing context:**
- The context's `count_basis` entry gains one sentence at its end: "The server
  answers a count_basis clarification with booked seats and states that
  assumption, because no other count meaning is executable here."
- `CONTEXT_VERSION` becomes `learningops-recipe-context-v7`. The instruction,
  output contract and structured-output schema are unchanged.
- **Why the sentence is needed.** The registry's candidate identity covers only
  model-facing bytes, so a runtime-only change cannot be registered (#158). The
  sentence also tells the model the truth about the action.

## Frozen-test amendment (owner-approved in principle, #158 item 3)

`tests/test_recipe_clarification.py`:
- **The generic tests' default clarification** becomes `center`. A
  `count_basis` clarification now executes an Overview, which those tests
  forbid.
- **The non-executing kinds** are `comparison_roles`, `center` and
  `metric_meaning`. `count_basis` leaves that list, and its new behaviour is
  covered by `tests/test_v19_count_basis_answer.py`.
- **The pin** in `tests/test_p3_exposed.py` moves to the amended file. Its
  ancestry entry keeps the accepted baseline digest and now cites #158.

The exact diff is on the PR.

## Historical panels and tests (#158 item 2)

Several oracles still expect a `count_basis` clarification. They predate #158
and stay unchanged as history:
- `p3-development-v1`'s C01, which is frozen by `tests/test_p3_exposed.py`;
- the dev-matrix v1/v2 `dev-C1.v1`;
- bound-meaning v1 (`dev-BM6.v1`, `dev-BM7.v1`) and v2 (`dev-BM7.v1`);
- mechanism-probe v1;
- count-fresh v1 `dev-CF11`/`dev-CF12`.

Tests that run a scripted `count_basis` clarification against them now state
that v19 answers it. Against a historical clarify oracle, that answer is
graded `missed_clarification`.

**The synthetic harness.** The harness copies `p3-development-v1`, so its one
C01 input (`C01_count_basis.en`, `SERVER_ANSWERED` in `tests/test_evaluate.py`)
grades wrong: at most 14 of 15 inputs are correct.
- **Expectations moved:** `test_evaluate`, `test_evaluate_replay`,
  `test_evaluate_gate`, `test_count_assumption`, `test_compare_first_v3`,
  `test_count_ablation`, `test_reading_diagnostic`, `test_p3_eval` and
  `test_p3_admission`. `test_p3_admission` now takes the signature of the
  actual action.
- **Historical-panel mock loops:** `test_dev_panel` (dev-C1 ×3),
  `test_mechanism_probe_controls` (12 rows), `test_bound_meaning_controls`
  (BM6 and BM7, 6 rows) and `test_count_fresh_panel` (v1, CF11 and CF12,
  6 rows) now expect `missed_clarification` on those rows.
- **`test_invalid_request_reason`** keeps a `count_basis` default for its
  validation cases, because the validators run before the answer.

**The history tools.** The historical P3 tools' tests
(`tests/history/test_p3_candidate_regression.py`, `test_p3_dev_regression.py`,
`test_p3_formal_run.py`, `test_p3_stability_run.py`) run with their era's
behaviour: they patch `recipe_model._server_answers` to `False`.
- **Why.** They guard those tools' archive, observation and promotion logic,
  including the clarify-row tamper checks and the formal and stability success
  paths, and they do so unchanged.
- **The #158 item-6 consequence**, that frozen expectations asking for a
  `count_basis` clarification count as missed under v19, is ruled by
  `tests/test_v19_count_basis_answer.py`. There a v18-shaped archive gates
  against v19, and the C01 input is a `broke`.

## Evaluation (grant steps 4 and 5)

**Result: `regression`.** 21 inputs were fixed (`dev-C1` ×3, `dev-BM7` ×3,
`dev-CF11` to `dev-CF15` ×15), and `dev-BM2.en` broke on both panels that
contain it. A regression is a stop, so v19 is to be reverted. See the
[gate results](count-basis-answer-v19-result.md). The amendment
(#158 #issuecomment-5932057637) added a second v18 run on the two new panel
versions, so all four panels were gated.

The four panels are `p3-dev-bound-meaning-v3`, `p3-dev-count-fresh-v2`,
`p3-dev-matrix-compare-first-v3` and `p3-dev-mechanism-probe-v2`. Each gets
one v18 sentinel (step 2) and one v19 run (step 4): 154 + 154 = 308 calls. The
gate runs against v18, and `regression` is a stop and a revert.

**Offline prediction** (0 calls; not evidence). Re-reading v18's recorded
actions under v19's rule, and assuming the model is unchanged:
- `dev-C1` ×3 and the fresh panel's B ×9 become correct;
- the D rows stay correct under the revised oracles;
- `dev-A1` and the fresh panel's O rows stay wrong.

## Claims and limits

- **Not fixed.** The `dev-A1` class, a spurious assumption on a no-count
  overview, is out of scope (#158).
- **Risks the gate measures:**
  - The new context sentence could change readings beyond `count_basis`.
  - The model could stop clarifying and read a named meaning instead (for
    example `known_booking_accounts`), which the server declines.
  - Compare and decline inputs could move under the byte change.
  - A `count_basis` clarification given for a Compare or Breakdown question
    would now run its one-month Overview scope, not a clarification.
- **Formal and holdout panels are frozen** and may expect `count_basis`
  clarifications, so a promotion claim needs a new formal panel (#158 item 6).
- **Scope.** One route and one run per panel, on exposed development inputs.
