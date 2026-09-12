# Root causes and a program to fix them so it generalises (proposed 2026-09-11)

## What the evidence says, grouped by cause

Eight problem classes came out of the v13 work (`../research/operand-filters-01.md`,
`../research/holdout3-01.md`, `../../evidence/README.md`). They reduce to three
root causes plus one infrastructure fact.

| Root cause | Problems it produces | Evidence today |
|---|---|---|
| **RC1. The model is asked to do too much free generation in one shot.** One 8,000 to 9,300 token prompt carries the whole schema, ten rules and a nested schema; the model must emit exact nesting and exact literal strings. | shape slips (misplaced brackets: `numerator` beside `ratio`, `ratio` on the plan, `ColumnRef` nested twice); literals rewritten (特約新店遠東 -> 遠東, 平版商品類 -> 平版商品); plan variance at temperature 0; time slips (range end 2060-01-01, forward 30-day window) | shape repairs per set 1 to 2 under v12, 11 under v13; 2 of 50 and 2 of 39 malformed per run; same payload valid on one call and malformed on the next; 4 of 12 ratio plans differ across runs |
| **RC2. The algebra's meaning lives in the compiler's code paths, not in an executable specification.** A construct's meaning next to another construct is whatever the code happens to do; before a construct exists the validator's rejection hides the combination. | silent wrong numbers at construct intersections (operand filter x share = 1.0; operand filter x metric expansion = 1.0 marked verified); time gates added one by one; verification level over-claims | both wrong numbers were shapes the validator used to reject; neither exposed itself; the second waited for a holdout rerun |
| **RC3. Evaluation has an oracle problem at our scale.** 95 real questions, one model, one real datasource, strict reference matching, verdict carry only on identical SQL. | regressions cost a human read; a correct answer with an extra column counts as a miss; generalisation to another schema or model is unmeasured | holdout 3: 15 questions decide a construct; ratio set: 12 |
| **Infra. Shared inference endpoints are not deterministic and not always up.** | variance that is not the model's; timeouts | temperature 0 differs call to call (batch-size dependence, Thinking Machines 2025); 3 transport failures on battery, 1 in 273 calls on mains |

The three causes are not specific to POS data or to this model. Anything that
maps language to a governed query has them, so the fixes below are stated as
principles first and as work items second.

## Principles (what generalises)

1. **Shrink the model's decision space; let code own everything code can own.**
   The model selects among offered identifiers and candidates; it never types a
   string that exists in the database, never sees a rule it does not need,
   never sees a table the question cannot touch. Semantic layers report the
   same effect at the extreme: dbt's 2026 benchmark has the same model at 84 to
   90% writing SQL and 98 to 100% choosing metrics and dimensions; the paired
   ClickHouse study finds three frontier models statistically indistinguishable
   once business semantics are supplied, so *what the model is asked to do*
   matters more than which model.
2. **Reason free, package late.** Format restriction degrades reasoning ("Let
   Me Speak Freely?", 2024); on small and mid-size open models hard schema
   decoding raised validity to 100% while cutting answer accuracy by half
   ("The Constraint Tax", 2026). Our own json_schema ablation lost 40% to
   repetition loops. So: unconstrained thinking, then a minimal schema, then a
   repair turn on failure, and constrained decoding only as an ablation.
3. **Design the contract around the model's priors, not ours.** The three
   recurring slips are all the model flattening our nesting. When a model
   consistently writes a shape, that shape is the cheaper contract.
4. **Every construct has an executable meaning and every pair of constructs has
   a test.** Semantics as a reference evaluator, invariants as properties, a
   construct-by-construct matrix in the contract, and the same invariants
   checked at serve time so an unknown combination refuses instead of answering.
5. **Measure validity, correctness, stability and wrong-valid separately.**
   A valid plan with the wrong meaning is the failure that matters; report it
   as its own number, as the Constraint Tax paper recommends.
6. **Generate the oracle where humans are scarce.** Metamorphic relations
   (Dr.Spider, MT-Teql) need no ground truth; plans sampled from the algebra
   and rendered as questions give a round-trip oracle for every construct
   combination; several fixture instances (test-suite accuracy) tell apart SQL
   that a single database cannot.

## Work items

Each item names the problems it addresses, the change, how it is validated and
the exit number. Baselines are today's numbers.

### A. Plan generation (RC1)

| Item | Change | Validation | Exit |
|---|---|---|---|
| A1 Repair turn | On `invalid_structured_output`, one follow-up carrying the pydantic error and the raw output (Instructor pattern; recovery above 95% reported). Counted as `model_repair_turns`, never silent. | malformed rate across all sets, cost in calls | malformed after repair 0 of 273; extra calls under 5% |
| A2 Contract v2, flat | One canonical shape per idea: a column is the string `table.column` everywhere; a ratio is `numerator`/`denominator` on the measure; no sibling `table` keys; optional fields absent, never null. Repairs shrink to a coercion layer that logs when it fires. Done 2026-09-11 (9879e33, e5a9f55, 5872cca): the owner also ruled unambiguous naming variants (aliases in the question's language, qualified output names) part of the written form. | `shape_variants` per set (the metric was split from meaning normalisations on 2026-09-11); full regression under the new prompt revision | variants under 5% of cases on every set (v13: 42% on `pos`, v14 first pass: 2 of 160 on the author sets, 30% on batch 1 before the naming decision); author sets at or above 156/160 |
| A3 Rule packs by trigger | Rules 8 to 10 (`without`, `latest`, latest period) enter the prompt only when the question carries their words (the shape pack already lists them); the same for growth. | prompt tokens per call; malformed rate; over-refusal on the author sets | median prompt under 5,000 tokens (today 8,000 to 9,300); no case loses its answer for want of a rule |
| A4 Schema linking with fallback | Rank tables by name and description match, overlay metric mention and foreign-key closure; send the linked subset; on `unknown_table` or `unknown_column`, retry once with the full schema (RSL-SQL: 94% strict recall while cutting 83% of columns). | recall of tables the plan uses; prompt tokens; author sets | recall 100% on the 160 author cases and batch 1 with the fallback; tokens under 3,500 |
| A5 Literals by reference | The value index offers candidates with ids (`v1: 特約新店遠東`) for every mention it finds, exact and fuzzy; the plan writes `value_ref: v1`; a free string is allowed only when no candidate exists and is then literal-checked as today. | `literal_misses` on cases with a candidate; clarify rate | misses with a candidate 0 (today 3 recurring); PII columns still excluded by policy |
| A6 Stability as a metric, then Best-of-N | Every judged and author run repeats each case 3 times; `plan_stability` = fraction of cases whose canonical plan core agrees. If below target after A2 to A5, sample N=3 at temperature 0.7 and select deterministically: compiles, no plan error, fewest repairs, majority core (CHASE-SQL shows selection is where test-time compute pays). | stability on ratio set and batch 1 | stability at or above 95% (today 8 of 12 on the ratio set) |
| A7 Constrained decoding, revisited as ablation only | After A2, rerun json_schema mode on the flattened schema with the endpoint's current backend (xgrammar default in vLLM; JSONSchemaBench: coverage collapses with schema complexity, so the flat schema changes the test). | same as the 2026-09-10 ablation | adopt only if wrong-valid rate does not rise and repetition loops are gone |

### B. Algebra semantics and compiler (RC2)

| Item | Change | Validation | Exit |
|---|---|---|---|
| B1 Serve-time self-check | After compiling, parse the SQL back (sqlglot) and check the plan against it: every plan and operand filter appears exactly once as a predicate; ratio operands compile to distinct expressions; a share compiles to a window only when groups or a grain exist; parameter count equals literal count; `verified` only with no plan-added filters. A failure refuses with `compiler_self_check_failed` and is counted. | the two wrong numbers of 2026-09-11 replayed as tests; full regression | both refuse under the pre-fix compiler; 0 self-check failures on all sets under the fixed one |
| B2 Construct matrix in the contract | A table in `tier0-contract.md`: measure kinds (raw, metric, ratio, share, growth, having) against row constructs (plan filter, operand filter, default segment, named segment, window, grain, latest, without). Every cell names its contract test or says "excluded by validation" with the error code. Adding a construct means adding a row and filling it before merge. | review of the table; pytest ids | no empty cell |
| B3 Property tests over generated plans | Hypothesis strategies over the pydantic plan models; for every generated valid plan the compiler either produces SQL that passes B1's invariants or raises a typed `PlanError`; never a Python exception, never an invariant violation. | Hypothesis run in CI with a fixed seed budget | 10,000 plans without a finding, then keep it as a gate |
| B4 Reference evaluator | A small executable semantics over an in-memory fixture (DuckDB or pandas): plan -> result, written from the contract, not from the compiler. Differential test: compiled SQL on the fixture equals the evaluator's result for generated plans. | differential run over the B3 plans | 0 disagreements not explained by a documented convention (NULL handling, ordering) |
| B5 Time closure | Enumerate scope kinds x grain x growth x to-date as a table; each cell states its window bounds relative to `as_of` and its assumption text; a range whose end lies after `as_of` gets an assumption and a warning (the 2060-01-01 case); growth cells state the previous-bucket rule. Properties from the table go into B3. | the table; property tests | every cell has a test; `bonus_by_month_2025` returns 2025 only or warns |

### C. Evaluation (RC3)

| Item | Change | Validation | Exit |
|---|---|---|---|
| C1 Metamorphic suite, second round | Beyond the 2026-09-10 suite: utterance paraphrases (generated, checked by a human once, then fixed), synonym swaps from the overlay names, table and column renames, value spacing. Relation: plan core unchanged. | inconsistency count per relation | under 2% per relation on batch 1 |
| C2 Round-trip oracle | Sample plans from the algebra (B3 strategies), render each as a question from per-construct templates (zh and en), run, compare plan cores. Thousands of cases per construct pair with no human oracle. | agreement rate per construct pair | a heat map; every pair above 90% or a named gap |
| C3 Test-suite accuracy | Three fixture instances with random data; reference SQL and produced SQL agree on all three, so `1.0` coincidences and NULL luck stop passing. Reference matching compares column sets by name, so an extra correct column is a warning, not a miss (owner decides). | rerun of the author sets | matching rules documented; the store_partial_name class settled |
| C4 Second datasource, second model | A real datasource of a different kind (the roadmap item) run with no prompt change; and one other model on the same sets to separate design from model. | the same reports | numbers within 5 points of POS on author-style cases; model delta reported |
| C5 Metrics reported separately | Every report carries schema validity, plan stability, execution correctness, wrong-valid (answered, wrong, no exposed assumption), refusal precision and recall, p50 and p95, prompt tokens, model calls per question. | the runner summary | one row per set in `evidence/README.md` with all of them |
| C6 Judge assist | An LLM judge pre-fills a verdict by comparing the answer with a DB-computed reference the build side writes; humans confirm only disagreements and new numbers (the delegation of 2026-09-10 made formal). | agreement with the owner's past verdicts (306 available) | at or above 98% agreement before it pre-fills anything unreviewed |

### D. Serving (infra)

| Item | Change | Exit |
|---|---|---|
| D1 Time budget | 20 s per call, one retry, fail fast with `model_call_failed`; a per-question budget for A1 and A6 calls. | p95 under 12 s including repairs |
| D2 Follow-ups | A follow-up after a failed turn gets the previous question text and a note, not silence; or a typed clarify. | `fu_add_time` class answers or clarifies |
| D3 Endpoint | Ask the operator for the vLLM version and structured-output backend, and whether a batch-invariant mode is available (1.6x throughput cost reported); otherwise A6 covers it. | documented in `environment-and-secrets.md` |

### What not to do

- Not constrained decoding as the primary path (principle 2, our own ablation).
- Not free SQL from the model, even as a fallback: dbt's benchmark names the
  failure mode, a plausible wrong number, and our refusals are the product.
- Not one shape repair per observed slip. A2 replaces the pile; A1 catches the
  tail; the raw output tells us when a new shape appears.
- Not fine-tuning yet. The 400 judged plans would teach the old contract; after
  A2 stabilises, a data-efficient fine-tune (OpenSQL-style) on plan JSON is the
  candidate for a smaller or faster model, measured against the same sets.

## Order

| Sprint | Items | Why first | Exit |
|---|---|---|---|
| 1 (this week) | B1, B2, A1, C5, D1 | stop wrong numbers from reaching a user; catch the malformed tail; make every report say the same things | 0 wrong-valid on all sets; malformed after repair 0; matrix full |
| 2 | A2, A3, A4 | the prompt is the cause of the slips and the variance; three changes to the same thing, one revision bump, one regression | repairs under 5%; tokens under 5,000; author sets at or above 156 |
| 3 | A5, A6, B3, B4, B5 | literals and stability need the flat contract first; property and differential tests need the spec written in B2 | literal misses with a candidate 0; stability at or above 95%; 10,000 generated plans clean |
| 4 | C1, C2, C3, C4, C6, D2, D3 | generalisation is measured, not assumed | second datasource and second model reported on the same tables |

Each sprint ends with the usual: scope, files, counts, gaps, git state; a
prompt change bumps the revision and reruns every set that could move.

## Status and next order (takeover checkpoint after 746f168)

Current 2026-09-12: the approved 48-call cross-language slice is complete;
see `../research/cross-language-study-01.md`. Identical repeats agree 12/12;
translated planning exposes the known return-count misreading but shares the
service record/entity error. Conditional on the requested agent translation
review, there is one incremental signal among two known errors and zero false
alarms among nine correct controls. This is not independent human review:
the frozen fidelity ledger remains 2 exact / 10 unreviewed and the formal screen
is unpassed. No further calls or promotion; focused 85/static/offline 1,586 pass.
Next discussion separates independently judged confirmation from the planned
editable-query technical ruler/human-evidence route. Earlier metric wire/factor
candidates remain rejected; production and historical scores are unchanged.
A5 is still provisional. Current authority and local closeout: `active-work.md`.

Latest 2026-09-12: `../research/semantic-contrast-01.md`. Owner-approved
ratio-wrapper filter rejection is implemented through domain/compiler/self-check
and normalization bypass protection. Static/offline 760 pass. A separate
108-call three-arm semantic extraction study found no improvement; no arm is
promoted or expanded. Actual ask replay still serves a wrong Chinese metric
as verified and blocks a correct English count via the lexical concept gate.
Keep those two remaining issues distinct from the completed compiler repair.
A5 acceptance remains open; A4 is not started. Older measured slices below
remain history, not current scores. Current authority/state: `active-work.md`.

Latest combined batch: `../research/a5-forms-service-01.md`. Reference
evaluation now filters absence rows before ordinary aggregation; generated
plans cover multi-hop absence and non-count measures. Four named matrix gaps
closed (17 remain), 396 offline tests and 2,489 new differential comparisons
pass. The exclusive-form A5 prompt trial was rejected after q25 lost answer
availability twice. New non-POS three-language cases score 10/12; diagnostics
identify an imperative "return" concept false positive and omitted Japanese
absence guidance. These need a separate policy/prompt design, not more
ratio-repair guesses. Production v15 remains provisional; A4 is not started.

Latest A5 follow-up: raw JSON mixes share/ratio and lacks a denominator.
Three measured remedies did not recover a defensible end-to-end gain; no
production prompt change. Twelve guards added, 355 offline tests pass. See
`../research/a5-ratio-followup-01.md`; A5 acceptance remains open before A4.

2026-09-12 update: A5 wire-v3 / prompt v15 is implemented but **not accepted**.
The synthetic service source is provisioned; it exposed a natural-FK-target
generator defect and a grain/growth normalisation assertion, both repaired.
Same-index service v14/v15 controls are both 23/24; holdout 2 q25 repeats a
missing-denominator failure under v15. Resolve this before stacking A4.
Follow-up: the owner approved retiring lexical grain deletion. Orchestration
v3 removes it; `grain-retirement.md` records this separate slice and validation.
See `../research/a5-service-01.md` for current counts and non-claims; the
historical tables above are not updated scores.

The 746f168 handoff records A1/A2/A3, B1, C5 and D1 implemented, a historical
B3 10,000-plan run, B4 differential evidence and a B5 time-closure table.
These are bounded measurements, not proof that every exit is complete. B2's
matrix exists but still has named-test gaps; B4 shares production window
helpers. A6 remains measurement-only; batch composition is a hypothesis,
not an established cause of all observed variation. Best-of-N is deferred.

The owner has now explicitly accepted: no lexical growth deletion, NULL
growth across absent calendar periods without zero-fill, exclusion of NULL
times from periods, and thresholds after share/growth. Product direction is
settled. The executable-ruler checkpoint was reviewed and the owner authorised
implementation; compiler/reference adjacency and lexical-deletion retirement
are implemented. See
`active-work.md` for the current phase, original authority and test evidence.

| Step | Items | Exit | Notes |
|---|---|---|---|
| 0A | evaluation-tool repairs | source sensitivity survives replay; stability preserves order and rejects incomplete runs; focused and offline checks | no semantic or prompt change; historical artifacts unchanged |
| 0B | accepted semantic rulers and implementation | implemented after the authorised checkpoint; hand-computed gap, NULL-time and post-threshold results, PostgreSQL and differential checks recorded in active work | no zero-fill, new algebra or extra-measure score change |
| 1 | A5 literals by reference; synthetic datasource preparation alongside | candidate recall, reference selection and final correctness measured separately; no candidate literal misses; PII stays out | A5 wire ruler first; freeze datasource/overlay before original-prompt baseline and A5 comparison; separate prompt revision |
| 2 | non-POS generalisation and schema-size baseline | fixed synthetic cases, meaningful refusals, multilingual perturbations and touched matrix/generator gaps | synthetic questions are author tests, not a real blind holdout |
| 3 | A4 only if the full-schema baseline warrants it | measured benefit in correctness/tokens/latency, including wrong-valid cases a missing-identifier fallback cannot detect | independent prompt revision and serial regression, not a prerequisite assumed in advance |
| 4 | C4 second model, C2 round-trip oracle | model delta reported; agreement per construct pair | separates design from model; C2 gives thousands of cases without a human oracle |
| 5 | C1 metamorphic round two, C6 judge assist, D2, D3 | as in the tables above | after the second datasource shows where the variance is |
| 6 | tidy-up | PII column display settings and whitelist (owner: at the end), docs, generator gaps | |

Standing cautions: the differential proves values given the window
boundaries (the evaluator shares the time functions with production; windows
are the golden table's job); reports before 586f130 compared ordered and
limited plans as sets; the generator still cannot draw value-index literals
or named segments. Multi-hop `without` is now drawn. A single confirmed
wrong answer is defect evidence; recurrence is not required to record it.
Attributing a regression or an endpoint cause requires separate evidence.
Regressions run serially on frozen source and data; no source edits during a run.

## Sources

- Tam et al., "Let Me Speak Freely? A Study on the Impact of Format
  Restrictions on Performance of Large Language Models", EMNLP 2024,
  https://arxiv.org/abs/2408.02442
- "The Constraint Tax: Measuring Validity-Correctness Tradeoffs in Structured
  Outputs for Small Language Models", 2026, https://arxiv.org/abs/2605.26128
- Geng et al., "JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for
  Language Models", 2025, https://arxiv.org/abs/2501.10868
- vLLM, "Structured Decoding in vLLM: a gentle introduction", 2025,
  https://blog.vllm.ai/2025/01/14/struct-decode-intro.html
- Instructor, retry mechanisms with validation feedback,
  https://python.useinstructor.com/learning/validation/retry_mechanisms/
- He et al., "Defeating Nondeterminism in LLM Inference", Thinking Machines
  Lab, 2025, https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- Cao et al., "RSL-SQL: Robust Schema Linking in Text-to-SQL Generation",
  2024, https://arxiv.org/abs/2411.00073
- Talaei et al., "CHESS: Contextual Harnessing for Efficient SQL Synthesis",
  2024, https://scalingintelligence.stanford.edu/pubs/CHESSpaper.pdf
- Pourreza et al., "CHASE-SQL: Multi-Path Reasoning and Preference Optimized
  Candidate Selection in Text-to-SQL", ICLR 2025, https://arxiv.org/abs/2410.01943
- Ma and Wang, "MT-Teql: Evaluating and Augmenting Consistency of Text-to-SQL
  Models with Metamorphic Testing", 2020, https://arxiv.org/abs/2012.11163
- dbt Labs, "Semantic Layer vs. Text-to-SQL: 2026 Benchmark Update",
  https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026
- "Semantic Layers for Reliable LLM-Powered Data Analytics: A Paired Benchmark
  of Accuracy and Hallucination Across Three Frontier Models", 2026,
  https://arxiv.org/abs/2604.25149
- Li et al., "OpenSQL: Data-Efficient Text-to-SQL for Open-Source LLMs",
  VLDB 2026, https://www.vldb.org/pvldb/vol19/p1628-li.pdf
- Cockroach Labs, "Metamorphic Testing in CockroachDB",
  https://www.cockroachlabs.com/blog/metamorphic-testing-the-database/
