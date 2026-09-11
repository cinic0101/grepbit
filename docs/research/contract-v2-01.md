# Wire contract v2 and prompt v14: what changed, what it cost, what it found (2026-09-11)

## Setting

Items A2 and A3 of the root-cause program (`../plan/root-cause-program.md`):
the schema shown to the planner became a hand-built flat form of 6,671
characters instead of the 11,838-character pydantic schema, the
normaliser accepts a documented superset of that form, and rules 8 to 10
enter the prompt only on their trigger words (`../knowledge/tier0-contract.md`,
"Wire contract v2"). Prompt size on the POS fixture 27,304 to 20,993
characters; on the real database 31,048 to 24,733. Every set reran; the
12B control model too.

## Shape

| Set | v13 shape repairs | v14 | v13 result | v14 |
|---|---|---|---|---|
| pos (26) | 11 to 12 | 1 | 24 to 25/26 | 26/26 |
| batch 1 (50) | 3 to 11 | 8 (five are Chinese aliases, see below) | 49/50 | 50/50 |
| features (39) | 8 | 4 | 36 to 38/39 | 38/39 |
| multilingual (32) | 7 | 0 | 30 to 31/32 | 30/32 |
| having, overlay, iot | 5, 2, 3 | 0, 0, 0 | all correct | all correct |
| author sets (160) | | 2 | 153 to 155 | 154 |
| 12B pos (26) | 13 | 0 | 17/26 | 14/26 |
| 12B batch 1 (50) | 38 | 6 | 21/50 | 33/50 |

Two repairs in 160 fixture cases is 1.25%; the program's exit for A2 was
under 5%. p50 latency fell about 20% on every set (pos 5.4 to 4.1 s, batch
1 5.0 to 4.3 s, iot 3.9 to 2.8 s), the prompt being a fifth shorter. q49
answers for the first time in six runs: its shape is now the shown form.
The 12B gains 12 real questions; its 17 remaining misses are the unasked
dimensions of `repair-turn-01.md` and 9 outputs still malformed after the
repair turn.

## What the shorter, flatter prompt cost

Three things moved, all caught by the judged sets rather than the fixtures.

1. **Chinese aliases.** With the flat schema the 31B writes aliases in the
   question's language (付款總額) in about one case in ten on batch 1; the
   alias pattern rejected them and the repair turn fixed each at the cost of
   a call. The normaliser now renames a non-identifier alias to `measure_N`
   and follows the references, so no call is spent.
2. **A share's own filter on the grouped column** (holdout 2 q25, 保健‧保養
   category's product share). Under v13 the filter was a plan filter and the
   after-share selection returned one row, 0.0597. Under v14 the model put it
   on the operand: `count where category = X`, share of total, by category,
   which is 1.0 for that category and 0 for the others, 14 rows. Operand
   filters are two days old and the after-share rule predates them; the cell
   was a gap in the construct matrix. The normaliser now moves such a filter
   to the plan's filters, where the after-share rule applies.
3. **Operands on the plan.** Holdout 2 q23 spelled its two operands out as
   measures and put `numerator` and `denominator` on the plan; the repair
   turn then wrote an aggregate and column beside them on the measure. Both
   are accepted variants now.

None of the three is a wrong reading of the question; all three are the
model choosing a placement the contract had not named. The lesson from the
morning holds: a construct's meaning next to another construct is a cell,
and the cell was empty.

## Generated plans

`tests/contract/t0/test_plan_properties.py` (Hypothesis) draws plans over
the IoT fixture and requires every one to compile cleanly or refuse with a
typed error. First run at 200 examples: a ratio of identical operands
(`count / count`) reached the compiler and was caught only by the
serve-time self-check; now `plan_ratio_operands_identical` at validation.
First run at 10,000: a `latest` scope inside `without` escaped as a bare
`ValueError` from the domain (the served path would have labelled it
`unsafe`); now `plan_without_takes_no_latest_scope`. Second run at 10,000:
`count(*)` over the metric `all_alerts`, identical once expanded; now
`ratio_operands_identical` in the compiler. Third run at 10,000: clean in
38 s. Three defects in an afternoon that no fixture case had reached.

## Owner decisions applied

An answer with an extra column passes its reference when the extra is a
plan dimension and the rows agree once it is set aside
(`matched_with_extra_columns`); an extra measure or a row-changing
dimension still fails. A dimension the plan's own equality filter fixes to
one value is dropped with an assumption (`constant_dimensions_dropped`). A
month, day or year written as a filter literal on a date column becomes the
window it can only mean; any other literal on a date column is refused
before execution. Dropping an id grouped beside its name was withdrawn: it
is not row-preserving when two names collide.
