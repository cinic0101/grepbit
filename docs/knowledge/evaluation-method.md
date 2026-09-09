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

All of these were written by the agent that built the system, after looking
at the data. They are smoke signals and regression guards. The first
generalization measurement is a holdout of real questions nobody on the build
side has seen (`../plan/next-phase.md`).

## Runner (`evals/spike_tier0.py`)

```sh
.venv/bin/python evals/spike_tier0.py --dsn-env <ENV_VAR_WITH_DSN> \
  --datasource-id <id> --cases <file.yaml> --output <dir>/<name>.json \
  --live [--infer-joins] [--overlay <overlay.json>] [--verify-coverage] \
  [--enum-distinct-limit N] [--redact-rows] \
  [--review-sheet <dir>/<name>.md] [--verdicts <dir>/<name>.yaml]
```

`--enum-distinct-limit` (default 20) bounds the distinct values sampled per
non-key text column and shown to the planner; `0` disables sampling so no
cell value leaves the database (the summary records the limit and the
number of sampled columns).

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

## Judged runs (real questions)

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
