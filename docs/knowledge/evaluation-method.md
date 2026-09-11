# Evaluation method

## Case files (`evals/cases/tier0/*.yaml`)

```yaml
datasource_id: pos_test
as_of: "2026-02-10T12:00:00+08:00"
cases:
  - case_id: sales_by_store_dec
    question: "2025年12月各門市的營業額"
    expected: {status: answered}
    reference_sql: "SELECT s.store_name, SUM(p.total_amount) FROM ... GROUP BY 1"
    reference_sql_alternatives: ["SELECT store_id, SUM(total_amount) FROM ... GROUP BY 1"]
  - case_id: returns_dec_gap
    question: "2025年12月的退貨金額"
    expected: {status: semantic_gap}
    accept_statuses: [semantic_gap, clarify, unsupported]
  - case_id: fu_change_month
    follow_up_of: sales_by_store_dec
    question: "那1月呢？"
    expected: {status: answered}
    reference_sql: "..."
```

- An answerable case is correct when the status is accepted and the returned
  rows, normalized (Decimals to 4 places, dates ISO, NULL), equal the rows of
  the reference SQL or of one alternative. Column names and row order do not
  matter; values do.
- A refusal case is correct when the status is in `accept_statuses`.
- `follow_up_of` hands the earlier case's question and plan to the planner as
  the previous turn.
- A case with no `expected` block is judged by a human (real questions have
  no reference SQL). The runner records `correct: null` for it and leaves it
  out of every correctness count; see "Judged runs" below.

## Sets that exist

| File | Purpose | Cases |
|---|---|---|
| `iot.yaml`, `retail.yaml` | zero-definition generalization on two synthetic schemas | 20, 12 |
| `pos.yaml` | owner-supplied fixture schema with traps | 26 |
| `coverage_{iot,retail,pos}.yaml` | concept-drop probes; any refusal is correct | 8 each |
| `pos_multilingual.yaml` | English and Japanese variants of POS questions | 32 |
| `pos_overlay.yaml` | before/after set for the overlay | 14 |
| `pos_features.yaml` | competitor feature probes and follow-ups | 32 |
| `having_pos.yaml` | aggregate-threshold (HAVING) guard on the POS fixture, thresholds chosen to split groups, plus one row-filter control; part of every regression from prompt v8 on | 6 |
| `pos_real_smoke.yaml` | compatibility check on the owner's real POS test database (enum column, joins); run with `--enum-distinct-limit 0 --redact-rows --overlay overlays/pos_real.json` | 7 |
| `pos_real_holdout.yaml` | the owner's 50 real questions as received, judged mode (no expectations); the record behind `docs/research/holdout-*.md`, not rerun | 50 |
| `pos_real_batch1.yaml` | the same 50 settled as a regression set: references are the run-4 SQL the owner judged correct with bound values inlined, refusals accept any typed refusal; q29/q44 replaced by the value-grounded q29b/q44b | 50 |
| `pos_real_values_01.yaml` | the first value-grounded questions (a store name, a product name), judged mode | 2 |

The sets above the `pos_real_*` rows were written by the agent that built the
system, after looking at the data. They are smoke signals and regression
guards. The owner's 50 questions were the first real set; they were pasted
into the build conversation, so they are a dev set now, not a holdout. The
next generalization measurement is the owner's next batch, which the build
side does not open (`../plan/next-phase.md`).

## Runner (`evals/spike_tier0.py`)

```sh
.venv/bin/python evals/spike_tier0.py --dsn-env <ENV_VAR_WITH_DSN> \
  --datasource-id <id> --cases <file.yaml> --output <dir>/<name>.json \
  --live [--infer-joins] [--overlay <overlay.json>] \
  [--enum-distinct-limit N] [--redact-rows] \
  [--review-sheet <dir>/<name>.md] [--verdicts <dir>/<name>.yaml] \
  [--no-shape-gate] [--no-literal-check] [--no-grounding] \
  [--propose-policies <file.json>]
```

Since 2026-09-10 the runner is a loop over `application.ask.ask()`, the
same function the MCP server serves: it builds the `AskServices` once, calls
`ask()` per case and maps the `AskResult` onto the report keys below, so a
number measured here is a number the served path would produce
(`../research/runner-on-ask-01.md`). Two report fields changed meaning with
the move: a row's `excluded_segments` lists the segments that shaped the SQL
(`CompiledPlan.applied_segments`, query-wide or per operand), and
`question_values` hints are recorded for every case, refusals included.
The coverage audit and its `--verify-coverage` flag were removed with the move (across 163 recorded artifacts it changed 2 of 3512 case statuses; old artifacts still carry `status_without_coverage`).

The deterministic gates are on by default; `--no-shape-gate`,
`--no-literal-check` and `--no-grounding` exist for ablations. With an
overlay that lists groundable columns the runner builds the value index at
start (printed as `value index: N columns, M values`), records
`question_values` hints and `grounding` resolutions per case, and the summary
carries a `grounding` block (columns, values, columns skipped for size,
hinted, resolved and ambiguous cases). `--propose-policies` writes the
column-policy draft and continues. `--perturb tables_reversed|tables_shuffled|columns_reversed`
reorders the schema payload without changing its meaning, for the
metamorphic suite (`../research/perturbations-01.md`); data-only variants
live in `evals/perturb/`. The summary counts
`shape_gate_refusals`, `literal_checks` (literals checked) and
`literal_misses` (cases turned into `clarify` by a literal that matched no
row); a row carries `matched_name` or `missing_literals` when a gate fired.
With an overlay the summary also counts `segment_exclusions` (cases where a
default segment exclusion applied; the row lists `excluded_segments`),
`per_period_clarifies` (per-period questions the planner answered for the
current period only), `empty_result_warnings` (answers with no rows or an
all-NULL row) and `negative_share_warnings` (a share below zero for some
group, so the total is a net); the row carries `warnings`.

`--enum-distinct-limit` (default 20) bounds the distinct values sampled per
non-key text column and shown to the planner; `0` disables sampling so no
cell value leaves the database (the summary records the limit, the number of
row-sampled columns and, separately, the number of enum columns whose labels
come from the catalog).

Without `--live` it introspects and validates the case file only. The JSON
report holds a summary (correct, answerable correct, refusals correct, false
answers on refusal cases, model failures, P50 and P95, schema size, inferred
joins, verification counts, shape repairs) and one row per case with status,
plan, SQL with placeholders, lineage, assumptions, interpretation, first rows,
whether rows matched a reference, and latency. No credentials, no bindings.

`--redact-rows` drops result rows and reference rows from the report (row
counts, SQL, lineage and assumptions stay), so an artifact taken on a real
database can be committed under `evidence/`. The summary records
`rows_redacted`, the case file, the prompt revision and `as_of`.

### Contrast cases for undocumented concepts

`returns_dec_gap` (and its Japanese twin) ask for a return amount on the
fixture without the overlay, where nothing documents what a return is. Until
2026-09-10 the model declined; since then it reads `origin_transaction_no` as
the return marker on its own. The case accepts both: a typed refusal, or an
answer that equals the overlay's definition (the reference SQL). The rule
this encodes is the product's: a concept the schema leaves undocumented may
be answered on a plausible reading only when the assumption says no reviewed
definition applied, and the number must be the documented one when a
definition exists. No prompt rule forbids the inference; the overlay is
where a business pins meaning.

## Judged runs (real questions)

A holdout arrives as a UTF-8 text file, one question per line (leading
numbers are stripped, blank lines skipped). `evals/questions_to_cases.py
--questions <file.txt> --datasource-id <id> --as-of <ISO datetime> --output
<cases.yaml>` converts it into a judged-mode case file and prints only the
count, so the build side never reads the questions before the run.

Real questions carry no reference SQL, so a run over them produces three
files: the JSON report (with `--redact-rows`), a review sheet
(`--review-sheet`, one readable page per case with question, status,
interpretation, assumptions, SQL and the first rows; it holds data, keep it
under the ignored `.artifacts/`), and a verdict skeleton (`--verdicts`). The
judge fills one verdict per case: `correct`, `wrong_exposed` (wrong number,
but an assumption states the choice that made it wrong), `wrong_silent`
(wrong number, nothing exposed it), `refusal_ok`, `refusal_bad` (should have
answered), `unsure`. Then

```sh
.venv/bin/python evals/tally_verdicts.py --report <run.json> \
  --verdicts <filled.yaml> --output <dir>/<name>-tally.json
```

checks every case has a verdict consistent with its status and writes the
stage-2 numbers: correctness over judged cases, wrong numbers without an
exposed assumption, clarify rate, refusal rate, P50 and P95. The tally holds
counts only and belongs under `evidence/`. The build side never opens the
question file before the run, never changes prompts between runs of the same
holdout, and reports which run was the first (blind) one.

Repeated runs of the same questions do not need a fresh judgment for every
case: `evals/carry_verdicts.py --report <new-run.json> --verdicts
<new-skeleton.yaml> --from <judged-run.json>:<filled.yaml> [--from ...]`
copies a human's earlier verdict onto a case whose status, plan, SQL and
row count are byte-identical to the judged run, notes which run it came
from, and leaves everything else `null`. The judge then reads only the
open cases; `unsure` verdicts are never carried.

Settling a judged batch: `evals/settle_batch.py --report <run.json>
--verdicts <filled.yaml> --cases <judged.yaml> --dsn-env <ENV> --datasource-id
<id> [--overlay <overlay.json>] --output <batch.yaml>` recompiles the plan of
every case judged `correct` (it must reproduce the judged SQL), inlines the
bound values into a `reference_sql`, turns `refusal_ok` cases into refusal
cases, and leaves out anything judged wrong or unsure. The result is a
regression set whose references are the system's own accepted output; the
file header says so. `pos_real_batch1.yaml` was produced this way.

Other runners: `spike_parent_agent.py` (relay experiment) and
`spike_suggest.py` (suggested questions written as a case file).

## Evidence discipline

- Every number in a research document points to a file under `evidence/`.
- Reruns after a prompt or code change get a new artifact name; the earlier
  one stays.
- A prompt rule added after seeing a failure is reported as such, and the
  other case sets are rerun to show no over-refusal.
- Latency numbers taken while other runs were sharing the model endpoint are
  marked as inflated.
