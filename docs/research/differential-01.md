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
disagree) and the fixture reruns (iot random 442/0, pos 212/0) close the
compiler side of phase 2 at 0 disagreements everywhere the generator
reaches. The count is in the table below, per report; an earlier version of
this note said "about 3,900 checks", which was neither the sum of the last
report per set (1,952) nor of every non-first-pass report (3,264).

## Every report, counted (2026-09-11)

*Distinct valid plans* leaves out Hypothesis examples that repeated an
earlier plan or that the plan model rejected; reports up to `pos-02`
recorded those two counts separately (`duplicate`, `invalid_plan`) and later
reports count only distinct valid plans as `generated`. `compared` = agree +
disagree, and on DuckDB each plan is compared once per instance. Database
errors and the driver's truncated results are neither compared nor refused.
Reports up to `pos-02` also count `ordered_or_limited_compared_as_sets`: the
plans whose rows the comparison of the time treated as sets, which is the
review's `LIMIT` finding, fixed in 586f130 (12, 64, 60 and 74 such plans in
those four reports; their agreements stand as set agreements, and the
ordering-aware reruns below cover the class).

| Report | Data | Engine, instances | Distinct valid plans | Typed refusals | Compared | Agree | Disagree | DB errors |
|---|---|---|---|---|---|---|---|---|
| `iot-01-first-pass.json` | `grepbit_spike_iot` | postgres | 121 (of 150 examples) | 32 | 80 | 78 | 2 | 9 |
| `iot-02.json` | same | postgres | 442 (of 600) | 141 | 301 | 301 | 0 | 0 |
| `iot-03.json` | same | postgres | 384 | 98 | 286 | 286 | 0 | 0 |
| `iot-duck-01-first-pass.json` | random instances of the iot schema | duckdb, 3 | 289 | 75 | 642 | 635 | 7 | 0 |
| `iot-duck-02.json` | same | duckdb, 3 | 367 | 126 | 723 | 723 | 0 | 0 |
| `iot-duck-03.json` | same | duckdb, 2 | 292 | 71 | 442 | 442 | 0 | 0 |
| `pos-01-first-pass.json` | `text2sql_test`, fixture overlay | postgres | 368 (of 500) | 97 | 271 | 270 | 1 | 0 |
| `pos-02.json` | same | postgres | 391 (of 600) | 103 | 288 | 288 | 0 | 0 |
| `pos-03.json` | same | postgres | 291 | 79 | 212 | 212 | 0 | 0 |
| `pos-duck-01.json` | random instances of the pos schema | duckdb, 3 | 337 | 86 | 753 | 753 | 0 | 0 |
| `pos-real-01-first-pass.json` | `t2s_8c2b8bbc_6d072f83`, real overlay, `--redact` | postgres | 334 | 70 | 264 | 262 | 2 | 0 |
| `pos-real-02.json` | same | postgres | 370 | 111 | 259 | 259 | 0 | 0 |
| first passes together | | | 1,112 | 274 | 1,257 | 1,245 | 12 | 9 |
| every report after a fix | | | 2,874 | 815 | 3,264 | 3,264 | 0 | 0 |
| last report per data set (`iot-03`, `iot-duck-03`, `pos-03`, `pos-duck-01`, `pos-real-02`) | | | 1,674 | 445 | 1,952 | 1,952 | 0 | 0 |

The 12 disagreements and 9 errors of the first passes are the five compiler
classes and three evaluator gaps above; every one was fixed and the set
rerun. A report's `git_sha` says which code produced it (reports before
586f130 have none; their commits are in `evidence/README.md`).

## Review close-out (2026-09-11)

A second agent reviewed 4b0d04f..88a57de and found four tool defects; all
four are fixed (586f130, 0a40a98, 1dbe413) and the sets rerun.

| Finding | Was | Now |
|---|---|---|
| a `LIMIT` plan passed when the actual rows were *any* subset of the reference (Top-1 of {100, 1} returning 1 passed) | `compare` tested subset inclusion | `compare` orders the reference as SQL would (`ORDER BY` items, NULLS FIRST ascending / NULLS LAST descending, else the dimension columns): every row strictly inside the top *k* must be present, the rows on the boundary tie are drawn as a multiset; a test carries the reviewer's counterexample |
| `--redact` kept cell values out but left plan literals in the disagreement and error records; the driver hard-coded `enum_distinct_limit=20` | possible path from sampled column values to a committed report | `--enum-distinct-limit` is an argument, default 0; with sampling off the generator's only literals are its own constants and enum type labels (schema, not rows; a test pins this), so plans stay as they are; with sampling on and `--redact`, literals are scrubbed at every record site and the report says `plans_redacted` |
| the evaluator joined a child to its parent on the parent's *first primary key*, not `fk.referenced_column` | `tickets.project_key -> projects.project_key` would have joined on `projects.id` | keyed by `(referenced_table, referenced_column)`; the fixtures only have id-keyed references, so the bug had not shown |
| `--seed` did not reach Hypothesis and a report could not be replayed | the same seed drew different plans | `@seed` on the generation; `--replay <report>` reruns the recorded plans with the segment exclusion recorded for each (a replay of `pos-real-03` gives the same 71 refusals and 191 agreements); reports carry `git_sha`, `seed`, `schema_digest`, `enum_distinct_limit`, `overlay_revision`, and a replay says whether the digest still matches |

Reruns on the fixed tool (all at 1dbe413):

| Report | Data | Engine, instances | Seed | Distinct valid plans | Typed refusals | Compared | Agree | Disagree | DB errors |
|---|---|---|---|---|---|---|---|---|---|
| `iot-04.json` | `grepbit_spike_iot`, literals sampled (20) | postgres | 21 | 287 | 54 | 233 | 233 | 0 | 0 |
| `pos-04.json` | `text2sql_test`, fixture overlay, sampled (20) | postgres | 22 | 285 | 79 | 206 | 206 | 0 | 0 |
| `iot-duck-04.json` | random instances, iot | duckdb, 3 | 23 | 228 | 51 | 531 | 531 | 0 | 0 |
| `pos-duck-02.json` | random instances, pos | duckdb, 3 | 24 | 207 | 55 | 456 | 456 | 0 | 0 |
| `pos-real-03.json` | `t2s_8c2b8bbc_6d072f83`, real overlay, `--redact --enum-distinct-limit 0` | postgres | 25 | 262 | 71 | 191 | 191 | 0 | 0 |
| `pos-real-03-replay.json` | the plans of `pos-real-03` replayed | postgres | (recorded) | 262 | 71 | 191 | 191 | 0 | 0 |
| together (without the replay) | | | | 1,269 | 310 | 1,617 | 1,617 | 0 | 0 |

The ordering-aware comparison did not turn any earlier agreement into a
disagreement: the `LIMIT` plans the generator draws order by a measure over
data with few exact ties, so the subset test had been passing them for the
right reason. That was luck, not evidence, until this rerun.

### What "independent" means here, precisely

The evaluator does not share the compiler's code for joins, filters,
aggregates, shares, growth, having, or the two row shapes. It **does**
import two production functions, `resolve_time_scope` and
`widened_for_previous_period` (`domain/structured_query.py`), to turn a time
scope into bucket boundaries. A wrong boundary in those functions would be
wrong on both sides and invisible to the differential. The independent check
of the windows is the golden table in
`tests/contract/t0/test_time_closure_contract.py` (the contract's time
closure table, 9 windows resolved by hand plus the clamping, widening,
NULL-row and empty-bucket cases), not the differential. The claim the
differential supports is therefore: *given the window boundaries, the
compiled SQL computes what the contract says.*

### Two semantics the review asked to have ruled, not defaulted

- Growth with a missing period: `LAG` compares a bucket with the previous
  bucket that has rows, so with no rows in February, March compares with
  January. Zero-filling the empty bucket or returning NULL for March are the
  alternatives. The current behaviour is pinned by a test and marked an open
  decision in the contract, not approved.
- The growth drop (`unrequested_growth`) as first written removed a growth
  column whenever the question carried no growth word, which would have
  deleted a requested percentage (本月告警數比上月多百分之幾). It now fires
  only on a comparison word with no rate word, and the default pack names no
  comparison word, so the rule is inactive until the owner rules;
  `ft_compare_last_two_months` may flap again meanwhile (pack v8, cd8535c).
