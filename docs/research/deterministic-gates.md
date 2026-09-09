# Two deterministic gates: unsupported shapes and literal existence (2026-09-09)

## Question

Two wrong-answer classes were left after the earlier experiments, both of
them cases where the planner answers a narrower question than the one asked:

1. A share or growth question answered as plain sums (`ft_share_by_method`
   in `pos_features.yaml`; "the one remaining wrong-answer class" in
   `decision-continue.md`).
2. A text filter literal that matches no row, so `SUM` returns NULL and is
   reported as an answer (`store_partial_name_jan` without sampling, in
   `sampling-ablation.md`).

Both can be caught without a model judgment. Does catching them cost any
correct answer on the 160 author-written cases?

## What was built

- Unsupported-shape language pack, `src/grepbit/resources/unsupported_shapes.json`
  (revision `unsupported-shapes-v1`): share, ratio and percentage words and
  growth, period-over-period words in Chinese, English and Japanese. Matched
  with the same script-aware phrase rule as overlay absent concepts, before
  any model call; a hit is `unsupported` with the pack's clarification (ask
  for the underlying amounts). A unit test asserts that every case the pack
  refuses accepts `unsupported`, so an over-refusal on an author case fails
  the suite.
- Literal existence check, `application/literals.py` (which literals) and
  `adapters/postgres/value_check.py` (one bounded `SELECT EXISTS` per literal,
  the literal bound, read-only transaction, statement timeout): every `eq`
  or `in` literal on a text column is checked after compilation and before
  execution. A miss is `clarify` naming the literal from the question; no
  stored value is read back, so nothing leaks through the clarification.
- Found during the rerun and fixed in the same slice: the model sometimes
  writes a filter as `{"column": "store_name", "table": "store", ...}`. The
  shape repair now folds that into a column reference when the named table
  owns the column (shape only; an unknown table still fails validation).

Prompt unchanged (`plan-classify-json-v5`), model `gemma-4-31b`, sequential
runs, sampling on unless stated.

## Results on the 160 author cases

| Set | Baseline | With gates | Shape hits | Literals checked / missed | Artifacts (`evidence/spike-tier0/`) |
|---|---|---|---|---|---|
| IoT 20 | 20/20 | 20/20 | 0 | 5 / 0 | `iot-07.json`, `iot-08.json` |
| Retail 12 | 12/12 | 12/12 | 0 | 2 / 0 | `retail-06.json`, `retail-07.json` |
| POS plus HR 26 | 26/26 | 26/26 | 1 | 2 / 0 | `pos-04.json`, `pos-05.json` |
| Coverage IoT, retail, POS, 24 | 7/8, 8/8, 7/8 | 7/8, 8/8, 7/8 | 0 | 0 | `coverage-*-0{2,1,2}.json`, `coverage-*-0{3,2,3}.json` |
| Multilingual 32 | 31/32 | 31/32 | 0 | 5 / 0 | `pos-multilingual-01.json`, `-02.json` |
| Overlay 14 | 14/14 | 14/14 | 0 | 0 | `pos-overlay-after.json`, `pos-overlay-gates-01.json` |
| Feature probes 32, with overlay | 31/32 | 31/32, then 32/32 after the shape-repair fix | 3 | 1 then 3 / 0 | `pos-features-02.json`, `-04.json`, `-05.json` |
| Total 160 | 156/160 | 157/160 | 4 | 17 / 0 | |

- The one gained case is `ft_share_by_method` (各付款方式的收款佔比): plain sums
  reported as an answer before, `unsupported` with the share clarification
  now. The three other shape hits were already refusals from the model
  (`member_ratio_gap`, `ft_share_top3`, `ft_growth_rate`); they are now zero
  cost and deterministic.
- No answerable case was refused by either gate: 17 literals checked, all
  present; 4 shape hits, all on refusal cases.
- The three cases still wrong are the ones that were wrong before: two
  coverage probes the planner answers instead of refusing, and the English
  transliteration of a store name in the multilingual set.
- `pos-features-04.json` lost `ft_two_stores_compare` to
  `invalid_structured_output`: the flattened column reference above,
  reproduced twice at temperature 0. `pos-features-05.json`, after the repair,
  answers it with the repair recorded. `pos-features-03.json` is the same set
  run without the overlay by mistake (30/32); it is kept as a data point, not
  a comparison: without the overlay the planner picks `paid_at` instead of
  `period_start` for the quarterly payroll.
- Latency: P50 per set moved by at most 0.4 s in either direction, inside the
  spread of earlier reruns. The literal check is one indexed-or-small `EXISTS`
  per literal; the shape gate costs nothing.

## The motivating case, sampling off

`pos.yaml` with `--enum-distinct-limit 0`, the setting the first real run
will use:

| Run | Correct | Wrong numbers | `store_partial_name_jan` | Artifact |
|---|---|---|---|---|
| ablation, no gates | 24/26 | 1 (`遠東` matched no row, `SUM` NULL reported) | `answered`, wrong | `pos-nosample-01.json` |
| with gates | 25/26 | 0 | `clarify`: "No row matches store.store_name = '遠東'" | `pos-nosample-02.json` |

The case still counts as incorrect against its `answered` expectation, which
is right: without the sample the system cannot know the stored spelling, and
a clarification that names the literal is the honest outcome. The other
change in that run, `payroll_by_dept_2025` back to `answered`, is the
borderline case the ablation already described flipping between runs.

## What this says

- Refusing is cheaper than a wrong number (AGENTS rule 6) held with zero
  cost here: the two gates removed the two known wrong-answer classes and
  refused nothing that was answerable.
- The literal check is what makes running with sampling off acceptable: a
  spelling the schema does not carry becomes a named clarification rather
  than an empty aggregate. It does not recover the answer; only a sample, an
  alias or the user's corrected spelling can.
- The pack's words are a first list. The real questions will show which
  ratio and growth phrasings it misses (平均客單價 and other per-entity
  averages are a ratio of two aggregates the pack does not name; the planner
  answers them as a plain `AVG`, which is right only when the base table has
  one row per entity).
