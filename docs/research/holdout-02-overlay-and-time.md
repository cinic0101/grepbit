# The 50 questions after the overlay constructs and the time fixes (2026-09-09)

Continues `holdout-01.md`. Same database, same 50 questions
(`evals/cases/tier0/pos_real_holdout.yaml`), same settings (sampling off, rows
redacted, gates on), `gemma-4-31b`, sequential runs.

## What changed between the runs

| Run | Prompt | Overlay | Code |
|---|---|---|---|
| 1 `pos-real-holdout-01.json` | v5 | none | shape gate, literal check |
| 2 `pos-real-holdout-02-overlay.json` | v5 | draft-1: return metrics (candidate), absent concepts, column aliases | same |
| 3 `pos-real-holdout-03-v6.json` | v6: per-period rule, length in units, `to_date`, overlay fields | v3: metrics signed, `paid_amount`, table aliases, payment-method value names, default time columns, returns segment excluded by default | segments, `relative_window_reaches_future`, `to_date`, empty-result warning, per-period gate |
| 4 `pos-real-holdout-04-v7.json` | v7: scope optional when a grain is set | v4: `average_ticket` (客單價) | `TimeSpec.scope` optional |

Every prompt and code change was also run on the 160 author cases, the
sampling-off set and the 7 real-database smoke cases: v6 and v7 both left
them equal to their baselines (156/160, 25/26, 7/7 after the smoke references
were rewritten for the confirmed return rule). Artifacts `*-09`/`*-10`,
`pos-nosample-03/04`, `pos-real-smoke-v6/v7`.

## Statuses of the 50

| Run | answered | clarify | semantic_gap | unsupported | failed | verified answers | P50 / P95 |
|---|---|---|---|---|---|---|---|
| 1 | 35 | 0 | 9 | 6 | 0 | 0 | 3.6 / 4.7 s |
| 2 | 37 | 0 | 7 | 6 | 0 | 0 (4 partially) | 4.0 / 5.2 s |
| 3 | 34 | 3 | 6 | 6 | 1 | 5 | 4.2 / 5.7 s |
| 4 | 38 | 0 | 4 | 6 | 2 | 9 | 4.5 / 6.1 s |

## Case by case, run 1 to run 4

| Class | Cases | Run 1 | Run 4 |
|---|---|---|---|
| 每天 read as today | q22, q23, q24, q47 | answered for today (wrong) | run 3: `clarify` by the per-period gate; run 4: answered per day over all data (56 days; q47 55 days) once the scope became optional. Root cause was structural: a grain required a scope and there was no "all data" scope, so the planner invented one |
| invented window | q27 (各月份) | 2025-02 only, 0 rows | run 3 year-to-date (2 months); run 4 per month over all data (3 months), the reading the owner chose |
| length in days for unit week | q31, q32 | 7 weeks | length 1, Jan 26 to Feb 1 |
| month to date | q33 | whole month | `to_date`, Feb 1 to Feb 4 |
| returns | q45, q46, q48 | refused | answered through verified metrics; q47 per day |
| returns not excluded | q14 (and every sales answer) | min picked a return | 30 answers now exclude returns by the default segment, stated as a reviewed assumption |
| 已付款 | q03 | summed every payment, no definition | `paid_amount` metric, verified |
| 客單價 | q07, q13, q24 | raw `AVG` | `average_ticket` metric, verified, with its preconditions in the description |
| absent concepts | q04, q05 | model refusals | zero-call refusals with the reviewer's note |
| 訂單狀態 via transfer_status | q06 | wrong table | run 4: model refusal (table alias 訂單 -> pos_sale made the mismatch visible); the absent-concept phrase does not occur in this question |
| shares and ratios | q10, q17, q21, q34, q41, q49, q50 | refused | unchanged, next phase |
| templates without values | q29, q44 | refused | `failed`: the model filled the range with the literal `YYYY-MM-DD`, which fails validation. Known model-failure class on placeholder questions; the owner is rewriting both with values |

The owner judges run 4 from `.artifacts/holdout-04/review.md`; the verdict
file is pre-filled for the 29 cases whose status and plan are unchanged since
run 1 (their values now exclude returns) and left open for 21.

## What this says

- Two of the three biggest wrong-number classes were structural, not model
  quality: the algebra could not say "every day over all data", and it let a
  past window run into the future. Fixing the structure fixed the cases
  without tuning to them; the prompt rule alone (v6) did not.
- The overlay did what it is for: seven refusals or unreviewed answers became
  verified answers with the owner's definitions, and the return rule now
  applies everywhere as an exposed assumption.
- What remains is the ratio family (7 of 50) and value grounding, which this
  batch does not exercise.
