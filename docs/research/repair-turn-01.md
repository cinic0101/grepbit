# The repair turn, the serve-time self-check, and a second model as control (2026-09-11)

## Setting

First two items of the root-cause program (`../plan/root-cause-program.md`):
the compiled SQL is read back and checked against its plan before it is
served (B1, `b1c4c37`), and a plan that fails validation gets one repair
turn carrying the validation errors (A1, `dae3a94`). Same prompt (v13),
same overlay (v12). gemma-4-12b-it, the only other text model on the
gateway, ran the `pos` set and batch 1 on the same code as a control.

## Self-check

Calibration over 312 recorded plan and SQL pairs flagged exactly the three
known wrong numbers and none of the 309 correct rows
(`operand-filters-01.md`). Live on `pos` and batch 1: 25/26 and 49/50, no
self-check refusal (`pos-24`, `pos-real-batch1-23`).

## Repair turn

| Model | Set | Slips | Rescued by the repair turn | Left |
|---|---|---|---|---|
| gemma-4-31b | pos (26) | 0 | | |
| gemma-4-31b | features (39) | 1 (`fu_base_payment`: a redundant `table` beside a `ColumnRef` on a measure) | 1 | 0 |
| gemma-4-31b | batch 1 (50) | 1 (q49: `numerator` beside `ratio`) | 0 | 1 |
| gemma-4-12b-it | pos (26) | 11 | 9 | 2 |
| gemma-4-12b-it | batch 1 (50) | 26 | 25 | 1 (q49, the same shape) |

Two findings. First, the repair turn works on most slips, on both models
(35 of 39). Second, q49 is sticky: at temperature 0 the 31B returned the
byte-identical text when shown its own output and the two errors
(`ratio.numerator: Field required`, `numerator: Extra inputs are not
permitted`), and the 12B failed the same way. Five runs in a row now. The
remedy for a sticky slip is not another turn but a contract that accepts
the shape, which is what the model is telling us it finds natural: item A2.

## The control model

The 12B slips far more (37 of 76 calls against 2 of 115) and, once
repaired, answers 46 of 50 real questions, of which 21 are right. Every
one of the 28 wrong answers adds a dimension the question did not ask for:
an id column beside the name column it already groups by (`store_id`
beside `store_name`, `product_id`, `sales_id`), or `sale_date`. The 31B
did the same once today (`store_partial_name_jan`: the filtered store as an
extra dimension). Two of the 12B's fixture cases failed with PostgreSQL
`22007`: a month written as a literal on a date column (`sale_date IN
('2025-12')`) instead of a time scope; the literal check covers text
columns only.

So the model-dependence splits cleanly: shape slips are model-dependent
and the repair turn plus a tolerant contract absorb them; over-answering
(unasked dimensions) is model-dependent too and neither absorbs it.

## Time budget

Under the earlier 30 s limit, 407 single calls across the day's runs had a
maximum of 9.6 s (p95 7.0, p99 8.6); nothing succeeded between 20 and 30 s.
The failures (36 s and 42 s with the retry) are hung requests, not slow
answers, so the 20 s budget loses no answer and fails 10 s sooner. One
transport failure in 115 calls on mains power today (`fu_base_top3`), and a
lost first turn still costs its follow-up (`fu_change_limit` clarified
without context).

## Questions for the owner

1. **Redundant dimensions.** Two mechanical rules would have fixed
   `store_partial_name_jan` and 22 of the 12B's 28 misses: drop an id
   column grouped beside the name column of the same table; drop a
   dimension whose column carries an equality filter with one value (it is
   constant). Both keep the row set and change only the columns shown, and
   both would be stated as assumptions. They change what a user sees, so
   they are a product decision, not a repair.
2. **Date literals.** A filter literal on a date or timestamp column that
   does not parse as a date should be refused before execution
   (`filter_kind_mismatch`) instead of failing in PostgreSQL. Mechanical;
   proposed for B5 unless there is an objection.
