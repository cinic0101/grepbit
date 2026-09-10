# Runner on the ask core: equivalence measurement (2026-09-10)

## Question

`evals/spike_tier0.py` grew its own per-case pipeline while `application/ask.py`
was written for the MCP server. Two pipelines drift. Does replacing the
runner's loop with a call to `ask()` per case change any measured number?

## Method

The runner was rewritten as a thin loop: build `AskServices` once, call
`ask(question, services, settings, previous=..., run_id=...)` per case, map
the `AskResult` onto the historical report keys (no bound values in the
report). The coverage verifier block was not carried over (`--verify-coverage`
prints a notice and does nothing). Then the two real-database sets and the
ratio review set were rerun with the same prompt (v11), overlay (v10),
`as_of` and flags as their last artifacts, and compared case by case on
status, correctness, plan, SQL, row count and reference match
(`compare_runs.py`, a throwaway; the artifacts below are the record).

Sets: `pos_real_batch1.yaml` (50 cases with references), holdout 2 (30
judged questions, text kept out of git), `.artifacts/ratios-01/cases.yaml`
(12 ratio and share questions from both sets, judged mode).

## Result

| Set | Previous artifact | Rerun on the core | Identical cases | Differences |
|---|---|---|---|---|
| batch 1 | `evidence/spike-tier0/pos-real-batch1-11.json` | `pos-real-batch1-12.json` | 49 of 50 (status, correct flag, plan, SQL, rows) | q49 SQL: the ratio's denominator now carries `FILTER (WHERE origin_transaction_no IS NULL)` |
| holdout 2 | `.artifacts/holdout2/run-09.json` | `.artifacts/holdout2/run-10.json` (SHA-256 in `evidence/README.md`) | 30 of 30 | none in status, plan, SQL or rows; `question_values` hints now recorded for the failed and the unsupported case too (18 -> 20 hinted) |
| ratios | `.artifacts/ratios-01/run.json` | `.artifacts/ratios-01/run-02.json` | 7 of 12 | q49 as above; four model-variance differences at the same revision (below) |

Batch 1 stays 43/50 with the same 7 ratio cases awaiting the owner's
judgment; P50 4.7 s, P95 6.5 s (4.9 s and 6.6 s before). Holdout 2 stays
24 answered, 4 clarify, 1 failed (`invalid_structured_output`, the same
question as before), 1 unsupported.

### The one behavioural difference: q49

The runner at HEAD passed only `exclude_segments` to the compiler. `ask()`
also passes `named_segments` (the default-excluded segments the question
named), which the compiler keeps out of every operand that does not itself
select them, so a return ratio's denominator excludes returns. That rule was
built and documented (`../knowledge/tier0-contract.md`, operand-level
segment rule) but the runner never exercised it. Under the core, q49
(退貨數量除以銷售數量) divides returned quantity by non-returned quantity;
under the old runner it divided by all quantity, returns included. The core's
behaviour is the documented one and matches the owner's decision that ratio
denominators use gross figures. The owner judges q49 on the new SQL
(`.artifacts/ratios-01/review-02.md`); the earlier review sheet showed the
old denominator.

### A reporting difference fixed before the artifacts above were taken

The first rerun reported `excluded_segments` as every default segment the
question did not lift (23 more batch-1 rows than before), because `ask()`
copied the question-level list. The old runner had derived the list from the
lineage, i.e. the segments that actually shaped the SQL. The compiler now
returns `CompiledPlan.applied_segments` (query-wide and operand-level
applications, deduplicated) and the ask result reports that, so an MCP
caller is told about an exclusion only when it changed the query.
`segment_exclusions` on batch 1 is 18 (17 before, plus q49's operand-level
application); on holdout 2 it is 10, as before.

### Model variance seen while rerunning the ratio set

Same prompt, overlay and `as_of`, different plans on four of twelve cases:

- b1_q10 and h2_q24: the output alias changed (`payment_amount` ->
  `paid_amount_share`; `sales_share` -> `gross_sales_share`); no number changes.
- h2_q21: `invalid_structured_output` in every earlier run, a valid plan this
  time (store share of total sales, 1 row); in the holdout-2 rerun of the same
  minute it failed again. Tracked as `model_failures`; one retry does not
  cover a malformed answer.
- b1_q21 (各銷售員的銷售額占同期全部銷售額的比例): the ratio set's first run
  read 同期 as one whole-data share (25 rows); this run, and batch 1 in runs
  11 and 12, add a monthly grain with no window, a share within each month
  (61 rows). The sibling questions q10, q17 and q41 with the same 同期 phrase
  never get the grain. Candidate deterministic fix if the owner rules the
  monthly reading wrong: treat a grain without a scope and without a period
  word in the question as a shape slip and drop it, mirroring the existing
  per-period gate in the other direction. Not built; the owner's verdict on
  b1_q21 decides.

### Author sets

The 13 author sets were rerun on the core the same afternoon (artifacts
listed in `evidence/README.md` under the runner-on-ask row): 156/160 on the
four base and coverage sets, 32/32 features, 6/6 having, 14/14 overlay
fixture, 7/7 real smoke, the two value cases answered. Every case is
identical to its previous artifact in status, plan, SQL and rows, with three
exceptions: `pos-nosample-11` lost one case to `model_call_failed` after the
one retry (a transport failure; the rerun `-12` is identical to `-10`), and
two real-database cases changed only their plan form with the same rows
(`cash_payments_jan` alias, `q44b` a `line_sales` metric instead of the raw
sum with the segment). The four standing misses (`cov_leased_fee`,
`cov_discounted_sales`, `en_engineers_avg_base_salary`,
`store_partial_name_jan` without sampling) are the same four as before.

## Verdict carry

Rerunning judged questions produced 30-case verdict skeletons that a human
had already judged, sometimes several times. `evals/carry_verdicts.py`
copies an earlier verdict when the new case has the same status, SQL and row
count (or the same SQL up to output column names) and notes the source run;
`unsure` is never carried and the plan JSON is not compared because its
shape grows with the algebra. On holdout-2 run 10 it carried 26 of 30 from
run 6 (13 exact, 13 alias-only), the build side pre-filled q21 (`unsure`,
malformed model output) and q24 (`refusal_ok`, a salesperson name literal
that grounding may not touch by policy), and q23 and q25 stay open; both are
the same SQL as h2_q23 and h2_q25 in the ratio review, so the owner judges
them once. On the ratio set it carried 2 (h2_q22 exact, h2_q24 alias-only);
10 stay open.

## What this does and does not show

- The served path and the measured path are now the same function; a
  regression in one is a regression in the other.
- One rule (named segments at operand level) had been measured by unit
  tests only. Its first appearance in a real artifact is q49 here.
- The coverage audit is gone from the measured path. Across the 163
  artifacts under `evidence/spike-tier0/` that recorded
  `status_without_coverage`, it changed 2 of 3512 case statuses, both in the
  first week (`coverage-iot-01`, `iot-05`). Nothing measured since depended
  on it.
- Model variance at a fixed revision is real (4 of 12 ratio cases, 1 of 50
  batch-1 cases across runs 11 and 12 differ from an earlier run of the same
  question); the perturbation suite measured it structurally
  (`perturbations-01.md`), this is another sample.
