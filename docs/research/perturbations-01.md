# Metamorphic perturbations: how stable is the plan when only the presentation changes? (2026-09-10)

## Question

The q29 class (a plan flips when the payload changes, not the question)
will keep appearing case by case. The owner asked for a way to find these
weaknesses systematically. Method after Dr.Spider (2023): take questions
whose correct answer is known, perturb what the planner sees without
changing what the question means, and count the plans that change.

## Setup

Baseline `pos-real-batch1-05.json` (prompt v9, overlay v5, grounding on,
49/50: q39 failed on a malformed answer, see below) and holdout 2 run 4
(out of git, plan stability only). Seven perturbations on batch 1, four on
holdout 2, each a full run with the references unchanged:

| Perturbation | What changes | Implementation |
|---|---|---|
| hints off | no `question_values`, no literal resolution | `--no-grounding` |
| tables reversed / shuffled | order of tables in the payload | `--perturb` |
| columns reversed | order of columns within each table | `--perturb` |
| hidden transfer | `transfer`, `transfer_status` hidden by table policy | `evals/perturb/pos_real_overlay_hidden_transfer.json` |
| no aliases | table and column aliases removed | `evals/perturb/pos_real_overlay_no_aliases.json` |
| spaced | a space inserted inside every stored value named in a question (2 questions) | `evals/perturb/pos_real_batch1_spaced.yaml` |

## Results, batch 1 (`perturb-batch1-*.json`)

A plan flip is any change of the plan's base table, measures (aliases
ignored), dimensions, filters, time, having or limit; alias renames and
`ORDER BY` changes are listed apart because they change no value.

| Perturbation | Correct | Plan flips (structural) | Alias or order only | Newly wrong |
|---|---|---|---|---|
| hints off | 49 to 49 | q29b back to clarify (expected: the hint is what answers it) | | none |
| tables reversed | 49 to 50 | q39 (baseline failure recovered) | q35 | none |
| tables shuffled | 49 to 50 | q39, q09 (count(*) to count_distinct(transaction_no)) | q35, q37 | none |
| columns reversed | 49 to 50 | q39 | q02, q35 | none |
| hidden transfer | 49 to 49 | q39 recovered, q38 failed (malformed answer) | q35, q37 | q38 (a failure, not a number) |
| no aliases | 49 to 49 | q39 recovered, q06 answered over `transfer_status` | q19, q35, q37 | q06 |
| spaced | 49 to 49 | none | none | none |

Holdout 2 (`.artifacts/holdout2/perturb-*.json`): hints off flips the 16
hinted cases back to clarifies, as designed; tables shuffled, hidden transfer
and no aliases each change one plan cosmetically (q28 alias, q26 filter value
order). Zero structural flips.

## What the suite found

1. **A shape slip, not a plan flip, behind q38 and q39.** Both baseline
   failures and the "recoveries" are the model writing `"reason": null`
   inside the plan; the strict schema rejected the whole answer, and a
   payload change moved the model on or off the habit. The shape repair now
   drops null-valued extra keys (`dropped null keys` in the repair list), so
   this class no longer reaches the caller.
2. **One real ambiguity the references cannot see: q09.** 各付款方式的交易筆數
   is planned as `count(*)` over payments or as `count_distinct(transaction_no)`
   depending on table order. The numbers coincide on this data, so both pass.
   The fix is a definition, not code: an overlay metric for transaction count.
3. **The q06 wobble is alias-dependent.** With table aliases (訂單 for
   `pos_sale`) the model refuses; without them it answers over
   `transfer_status`; with the transfer tables hidden it is right under every
   other perturbation. Hiding tables that are out of a datasource's scope is
   the robust fix.
4. **Everything else is stable.** Table and column order, hidden tables, and
   spacing inside named values change no structural plan on 50 plus 30
   questions; aliases in measures and `ORDER BY` presence vary and are
   harmless. Value hints do the grounding work: without them the 16
   value-grounded holdout questions fall back to clarifies.

Cost: 11 runs, about 470 model calls, 32 minutes. The suite reruns with the
same commands; adding a perturbation is one line in the driver.
