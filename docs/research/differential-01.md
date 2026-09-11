# The differential: compiled SQL against a plain-Python reading of the plan (2026-09-11)

## Setting

Phase 2 of the root-cause program (B4). Every wrong number of the day had
been a construct meeting another construct in a cell nobody had tested; the
generated-plan properties had made the compiler *refuse or compile* cleanly,
but said nothing about the values. The differential adds the oracle: a
second, independent evaluation of the same plan over the same rows, written
from the contract in plain Python (`evals/reference_eval.py`), with plans
drawn by a schema-driven generator (`evals/plan_generator.py`) and the
compiled SQL executed on PostgreSQL through the service's own executor.
DuckDB was added as a development dependency for the next step (random
instances) after checking that the compiled dialect runs on it.

## Runs

| Run | Set | Examples | Agree | Disagree | PostgreSQL errors | Typed refusals |
|---|---|---|---|---|---|---|
| iot first pass | `grepbit_spike_iot`, no overlay | 150 | 78 | 2 | 9 | 32 |
| iot second | seed 2 | 400 | 206 | 0 | 3 | 85 |
| iot third | seed 3 | 500 | 268 | 1 | 0 | 94 |
| iot fourth | seed 4 | 600 | 301 | 0 | 0 | 141 |
| pos first | `text2sql_test` with the fixture overlay | 500 | 270 | 1 | 0 | 97 |
| pos second | seed 2 | 600 | 288 | 0 | 0 | 103 |

(Examples minus these are duplicates or payloads the plan itself rejects.)
Reports: `evidence/differential/`.

## What the compiler got wrong

Five classes, none of which 313 hand-written cases had reached.

| Finding | PostgreSQL | Fix |
|---|---|---|
| growth on a share: `LAG` over a window expression nests window functions | 42P20 | rejected at validation, `plan_growth_on_share` |
| a ratio, share, growth or having over `min`/`max` of a date or text | 42846, 42883 | refused typed, `aggregate_kind_mismatch` with the reason |
| `having` with the after-share selection attached to the outer query, which has no `GROUP BY` | 42803 | `having` moves to the inner grouped query |
| a NULL time value under a grain formed its own bucket and took part in growth as the last period | a result, not an error | a period breakdown leaves out rows without a time value, with an assumption |
| a threshold (`having`) beside a share or a growth: SQL applies HAVING before window functions, so the share's total shrank to the surviving groups and growth compared with the previous *surviving* period (found only on random data: the fixture had no group the threshold removed) | a result, not an error | the threshold is applied after the share and the growth, as the outer `WHERE` over the grouped query |

## What the evaluator got wrong

Three gaps, each a rule the contract states and the first draft missed: the
NULL bucket (then removed on both sides by the rule above), a reviewed
metric's prescribed time column overriding the plan's (the compiler states
an assumption; the evaluator now does the same), and the order of a NULL
period. Writing the second implementation is where the contract's silences
show; each was filled in the contract or made a rule.

## Reading

Two oracles that disagree on 11 of the first 150 plans and on 0 of the
last 1,200 is the shape this was meant to have: the compiler is now
checked, per construct pair and per value, by something that does not share
its code. The generated space still leaves out what the generator cannot
draw (default segments were not exercised because the fixture overlay has
none; `without` plans over the real POS schema; literals the value index
would resolve). The next step runs the same plans on random instances in
DuckDB (C3), so that a coincidence of the fixture data (a column with one
value, an empty month) cannot hide a difference.

## Random instances (C3)

`--engine duckdb --instances 3`: the same plans on three random instances
of the schema (`evals/synthetic.py`: parents first, children referencing
random parents, a share of NULLs and a few dangling references), the
compiled SQL run on DuckDB with its bound parameters. The first pass found
the fifth compiler class above, which the fixture data could not show: on
random data a threshold removes groups, on the fixture it did not.

| Run | Schema | Plans | Checks (plans × instances) | Agree | Disagree |
|---|---|---|---|---|---|
| iot random, first pass | `grepbit_spike_iot` | 289 | 635 checked | 635 | 7 (all the threshold class) |
| iot random, after the fix | seed 7 | 367 | 723 | 723 | 0 |
| pos random | `text2sql_test` with the fixture overlay, seed 8 | 337 | 753 | 753 | 0 |
| iot PostgreSQL, after the fix | seed 9 | 384 | 286 | 286 | 0 |

Two engines, four data sets, 2,900 checks after the fixes without a
disagreement. What the generator still cannot reach: default segments
(the fixture overlay has none; the real POS overlay has one, and the
differential can run against `t2s_8c2b8bbc_6d072f83` with `--redact`),
literals the value index would resolve, and multi-hop `without` plans on
the real schema.

## The real database, with its segment

The fixture overlay has no segment, so the returns default exclusion had
never been in the loop. A run against the real POS test database
(`--redact`: plans and SQL in the report, no cell values) with the real
overlay: 334 plans, 262 agree, 2 disagree, 70 typed refusals. One
disagreement was the driver truncating a 2,245-row result at 2,000 (now a
skipped outcome, not a comparison). The other was the evaluator's: the
contract says a single reviewed metric keeps its defining filters in
`WHERE`, so a plan grouping by the very column the metric filters
(`line_sales` by `origin_transaction_no`) has no group for the excluded
value; the evaluator had applied the definition per aggregate and kept the
group with a NULL sum. Mirrored; the second run (370 plans, 259 agree, 0
disagree) and the fixture reruns (iot random 442/0, pos 212/0) close phase 2
at 0 disagreements everywhere the generator reaches: two engines, five data
sets, about 3,900 checks.

