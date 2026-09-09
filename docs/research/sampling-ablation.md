# Sampling ablation: what the planner loses without sampled text values (2026-09-09)

## Question

Introspection samples the distinct values of every non-key text column that
has at most 20 of them and shows them to the planner. On a real database
those values can include personal data, so PII exclusion is the first item of
the next phase and the approach (opt-in column list versus name and value
heuristics) is undecided. Before choosing, measure what the samples are worth:
run the three base case sets with sampling on and with sampling off.

## Method

- Runner flag `--enum-distinct-limit N` (new); `0` skips the sampling query
  entirely, so no cell value leaves the database (unit test:
  `test_introspection_with_limit_zero_never_reads_a_cell_value`). The report
  summary now records `enum_distinct_limit` and `sampled_columns`.
- Same day, same model (`gemma-4-31b` through LiteLLM), same prompt
  (`plan-classify-json-v5`), no overlay, no join inference. The five new runs
  were sequential, so latencies are not inflated by parallel load. The IoT
  with-sample baseline is the environment-check run of the same morning
  (`iot-07.json`, made before the summary field existed; a dry run counts 8
  sampled columns there).

## Results

| Set | Sampled columns | With samples | Without samples | Wrong answers without | P50 / P95 with | P50 / P95 without | Artifacts (`evidence/spike-tier0/`) |
|---|---|---|---|---|---|---|---|
| IoT, 20 cases | 8 of 24 | 20/20 | 19/20 | 0 | 3.9 / 5.8 s | 3.8 / 5.5 s | `iot-07.json`, `iot-nosample-01.json` |
| Retail, 12 cases | 5 of 22 | 12/12 | 11/12 | 0 | 3.8 / 6.3 s | 4.1 / 5.1 s | `retail-06.json`, `retail-nosample-01.json` |
| POS plus HR, 26 cases | 13 of 58 | 26/26 | 24/26 | 1 | 5.5 / 7.3 s | 4.7 / 6.0 s | `pos-04.json`, `pos-nosample-01.json` |
| Total, 58 cases | 26 of 104 | 58/58 | 54/58 | 1 | | | |

Latency differences are inside the spread seen across earlier reruns of the
same sets (P50 2.7 to 6.4 s); the smaller schema payload does not change the
cost of a call in a measurable way.

The four cases that changed without samples:

1. `offline_devices_count` (IoT, "How many devices are currently offline?"):
   `clarify`, asking whether offline means `devices.status` or an unresolved
   alert. An honest refusal. Two other IoT cases in the same run filtered
   `devices.status eq offline` and `eq online` correctly, so the trigger is
   the word "currently", not the spelling.
2. `zh_avg_discount_completed` (retail, 已完成訂單的平均折扣金額):
   `semantic_gap`, "no sample value for the 'completed' status". An honest
   refusal: the Chinese question needs the stored English spelling, which only
   the sample provides. The English case `gross_july_completed` filtered
   `status eq completed` correctly in the same run.
3. `store_partial_name_jan` (POS, 2026年1月新店遠東的營業額): answered with
   `store.store_name eq 遠東`. The stored value is 特約新店遠東, the filter
   matched no row, and `SUM` came back NULL and was reported as an answer.
   This is the one wrong answer. With samples the planner resolved the partial
   name to the sampled spelling.
4. `payroll_by_dept_2025` (POS, 2025年各部門的薪資總額): `semantic_gap`,
   unsure whether 薪資 means `base_salary` alone or base plus bonus. No text
   literal is involved and the case note says both readings are defensible;
   the with-sample run answered with both sums. A borderline case that flipped
   with a different prompt context, the same undecided product rule as
   `ambiguous_temperature` (answer with the assumption stated, or clarify).

Text-literal filters across the runs: with samples, 6 distinct literals in
7 filters over 58 cases, all correct. Without samples, 7 filters: 6 correct
where the question's own spelling equals the stored value (`critical`,
`offline`, `online`, `completed`, `工程師`), 1 wrong where it does not
(`遠東`). Everything else in the plans (base table, joins, time windows,
grains, aggregates, order and limit, the other refusals) was unchanged.

## What this says for the PII decision (the owner decides)

- Samples buy exactly one thing: the stored spelling of a text value when the
  question spells it differently (another language, a partial name, a
  synonym). On these sets that is 4 of 58 cases: 3 refusals and 1 empty
  answer. Zero wrong numbers either way.
- The one wrong answer sits on `store.store_name`, a name column. A heuristic
  that excludes `*_name` columns would have lost this case as well; an opt-in
  list would need a reviewer to list that column. The enum-like columns where
  the samples were used (`status`, `severity`, `payment_method`, `job_title`)
  carry no personal data on these fixtures.
- Independent of the approach: the wrong answer was a text filter literal that
  matched no row. A server-side existence check of `eq` and `in` literals
  against the column (one bounded query with the bound parameter, no model
  involved) would turn it into `clarify`. Not built; a candidate experiment.
- The refusal texts named the missing sample, not any value, so turning
  sampling off leaks nothing through the planner's explanations either.
- The 160 author-written cases were written with the samples visible. A
  holdout of real questions will contain more spellings the schema does not
  carry (店名縮寫, 同義詞); the 4/58 here is a lower bound on what the owner's
  questions would lose without samples or an overlay alias.
