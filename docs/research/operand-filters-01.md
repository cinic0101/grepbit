# Operand filters: two wrong numbers, and what a kept raw output shows (2026-09-11)

## Setting

Prompt v13 (latest row per entity) made the model sloppier on JSON shape:
shape repairs per set rose from at most 2 under v12 to 11 on `pos` and on
batch 1, and 19 fixture cases failed as malformed output in the first pass
(`../../evidence/README.md`, rows `pos-features-22` to `pos-21`;
`holdout3-01.md` has the holdout side). Three shape repairs and one algebra
construct followed the same morning, the last being operand filters
(`76dcf9b`): a ratio operand may restrict its own rows, compiled as
`FILTER (WHERE ...)`, so 會員交易佔比 is `count where member_id not_null /
count`. The session that built them crashed mid-regression; this note
records what the recovery found when it finished the measurement.

## Two wrong numbers the construct let through

Both were shapes the validator used to reject; the construct made them
executable, and neither exposed itself.

| Case | Plan the model wrote | What compiled | Answer | Right answer | Exposed? |
|---|---|---|---|---|---|
| `member_ratio_gap` (fixture, 會員交易佔比) | one `count` with its own filter `member_id not_null` and `share_of_total: true`, no dimensions | the window total was the same filtered count, so filtered / filtered | 1.0 | 0.4643 | the assumption said "share of the total over all groups", with no groups |
| holdout 2 q22 (one store's sales as a multiple of another's) | a ratio of the `gross_sales` metric filtered on store A over the same metric filtered on store B | the metric expansion rebuilt each operand from the metric alone and dropped both store filters: total / total | 1.0 | 0.9685 (7,175,037 over 7,408,127, run directly against the database) | no: the interpretation named both stores, the SQL had neither, and the answer was marked `verified` |

Fixes, both in the compiler and both stated in the lineage and an
assumption (`../knowledge/tier0-contract.md`):

- Whole share (`58ee765`). A `share_of_total` with no groups and no grain has
  nothing else to be a share of. When the operand (or its metric) carries a
  filter, the share is the part over the whole: the filter shapes the
  numerator and the total is the same aggregate over every row of the
  window; a metric's own filters then compile as `FILTER` on the part instead
  of `WHERE`. Without such a filter every share is 1 and the plan is refused
  with the remedy in the detail (`share_requires_groups`).
- Metric operands keep their filters (`cbc4581`), and a plan whose operands
  add filters of their own is at most `partially_verified`: the reviewed
  definition covers the aggregate, not the rows the question picked.

The lesson is about method, not about these two rules: a new algebra
construct needs a contract test for each existing construct it can meet
(share, reviewed metric, default segment), because the validator's rejection
had been doing that work silently. The `pos` fixture caught the first within
the same regression; the second waited for the holdout rerun.

## Malformed outputs, now with their text

Until today the runner discarded the model's text when it failed
validation, so a `failed` row said `invalid_structured_output` and nothing
else. The planner now keeps the text of the last malformed output, the ask
result carries it as `raw_output`, and the report row records it
(`8e7e01d`). The first regression with it (`99db787`) and the reruns after
the two fixes show three shapes:

| Shape | Seen on | Runs | Repaired? |
|---|---|---|---|
| `ratio` written on the plan beside `measures`, its operands also spelled out as measures | `member_ratio_gap`, sampled schema | one probe call of four at temperature 0 | yes (`8e7e01d`): the ratio moves into a measure, operand duplicates dropped; it has not fired in a run since |
| `numerator` written beside `ratio` instead of inside it | batch 1 q49 (return quantity over sold quantity by product) | three runs in a row (`pos-real-batch1-20` to `-22`, ratio set runs 11 to 13) | no |
| a `ColumnRef` nested inside `column` with a redundant sibling `table` on a dimension and a measure | `fu_base_payment` (各付款方式的收款總額), and its follow-up therefore has no previous turn | two runs in a row (`pos-features-25`, `-26`) | no |

The second and third were left as they are on purpose. The session before
the crash had promised the owner to stop adding shape repairs one by one
and put the choice to them: trim the v13 wording (or attach rules 9 and 10
only when the question carries a latest-row trigger word), give the model
one repair turn that feeds the validation error back (one extra call, only
on the 2 to 4 percent of cases that fail), or both. The raw texts above are
the evidence for that decision: every slip is a misplaced bracket, none is
a wrong reading of the question.

## Numbers

| Set | v12 | v13 first pass | after repairs (`8e7e01d`) | after the two fixes |
|---|---|---|---|---|
| author sets (160) | 156 | 151 | 153 | 155 (`pos-23`, `pos-nosample-21`; other sets as in the `99db787` row) |
| features | 37/37 | 38/39 | 37/39 | 36/39 |
| batch 1 | 50/50 | 49/50 | 49/50 | 49/50 |
| holdout 2 | 30/30 | 30/30 (run 16) | run 18: q22 answered 1.0, marked verified | 30/30 (run 19): q22 answers 0.9685, verified against the database, `partially_verified`; refusal rate 13% |
| ratio set | 12/12 | 12/12 (run 10) | run 12: h2_q22 1.0, b1_q49 malformed | 11/12 (run 13): h2_q22 0.9685; b1_q49 malformed a third time, judged `refusal_bad` |

Standing misses in the author sets: `store_partial_name_jan` (the model
cuts 特約新店遠東 to 遠東 and the literal check turns it into a clarify),
`en_engineers_avg_base_salary`, `cov_leased_fee`, `cov_discounted_sales`,
and this run `bonus_by_month_2025`, whose plan ends its range at
2060-01-01 (a slip no gate catches: a range end in the future is legal).
The transport failed once in 273 calls on mains power
(`ft_without_sales_in_range`, 42 s after the retry), against three in the
morning's runs on battery.
