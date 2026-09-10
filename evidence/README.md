# Evidence

Raw artifacts of the live runs cited in `docs/research/`. Each JSON file is a
`spike_tier0.py` report (summary plus one row per case: status, plan, SQL
with placeholders, lineage, assumptions, interpretation, first rows, reference
match, latency) unless noted. They contain fixture data and model-generated
plans and text; they contain no credentials and no bound values. Artifacts
taken on the real POS test database are written with `--redact-rows` and
hold no cell value (`rows_redacted: true` in the summary).

| File | Experiment | Notes |
|---|---|---|
| `iot-01.json`, `iot-02.json`, `iot-03.json` | IoT, prompt v1, v2, v2 (final of the first day) | 19/20, 20/20, 20/20 |
| `retail-01.json` to `retail-03.json` | retail, prompt v1 to v2 | 12/12, 11/12 (reference issue), 12/12 |
| `iot-04.json`, `retail-04.json` | rerun on prompt v3 | no over-refusal |
| `pos-01.json`, `pos-02.json` | owner-supplied POS plus HR, prompt v2 then v3 | 24/26, 26/26 |
| `pos-nofk-01.json`, `pos-nofk-02.json` | foreign keys dropped, without and with inference | 17/26, 26/26 |
| `coverage-*-01.json`, `coverage-*-02.json` | concept-drop probes with coverage audit v1 and v2 | planner 22/24; audit unreliable |
| `iot-05.json`, `iot-06.json`, `retail-05.json`, `pos-03.json` | base sets with the coverage audit on (v1, then v2 for IoT) | false flags 1 then 0; latencies inflated by parallel runs |
| `parent-agent-01.json`, `parent-agent-02.json` | parent-agent relay in two then three framings | caveats 8/8 guided, 0/8 bare |
| `pos-multilingual-01.json` | English and Japanese variants | 31/32 |
| `pos-overlay-before.json`, `pos-overlay-after.json` | overlay before/after | 10/14 to 14/14 |
| `pos-features-01.json`, `pos-features-02.json` | competitor feature probes, before and after shape repair | 30/32, 31/32 |
| `pos-suggested.yaml`, `pos-suggested-01.json`, `pos-suggested-02.json` | suggested questions and their answers | 9/10 |
| `iot-07.json` | IoT rerun on the restart machine (environment check), prompt v5 | 20/20 |
| `retail-06.json`, `pos-04.json` | same-day with-sample baselines for the sampling ablation | 12/12, 26/26 |
| `iot-nosample-01.json`, `retail-nosample-01.json`, `pos-nosample-01.json` | sampling ablation, `--enum-distinct-limit 0` (`../docs/research/sampling-ablation.md`) | 19/20, 11/12, 24/26; 3 refusals, 1 wrong (partial store name) |
| `pos-real-smoke-before.json`, `pos-real-smoke-after.json` | real POS test database, enum column as `other` then as text with catalog labels (`../docs/research/pos-real-enum.md`); rows redacted | 4/7 (2 refusals, 1 driver error) to 7/7 |
| `iot-08.json`, `retail-07.json`, `pos-05.json`, `coverage-iot-03.json`, `coverage-retail-02.json`, `coverage-pos-03.json`, `pos-multilingual-02.json`, `pos-overlay-gates-01.json` | the 160-case regression with the shape gate and the literal check on (`../docs/research/deterministic-gates.md`) | all equal to their baselines; 4 shape hits on refusal cases, 17 literals checked, 0 missed |
| `pos-features-03.json` | feature probes with gates but without the overlay (run by mistake; kept as a data point, not a comparison) | 30/32 |
| `pos-features-04.json`, `pos-features-05.json` | feature probes with overlay and gates, before and after the sibling-table shape repair | 31/32 (one `invalid_structured_output`), 32/32 |
| `pos-nosample-02.json` | `pos.yaml` with sampling off and gates on: the partial store name becomes `clarify` naming the literal | 25/26, 0 wrong numbers (was 24/26 with 1 wrong) |
| `pos-real-holdout-01.json` | first run of the owner's 50 real questions on the real POS test database (`evals/cases/tier0/pos_real_holdout.yaml`), judged mode, sampling off, rows redacted, gates on; verdicts in `pos-real-holdout-01-verdicts.yaml`, numbers in `pos-real-holdout-01-tally.json` (`../docs/research/holdout-01.md`) | 42/50 judged correct after revision (39 first pass); 1 wrong number without an exposed assumption, 7 with; refusal rate 30%; P95 4.7 s |
| `pos-real-holdout-02-overlay.json` | the same 50 with the draft overlay `overlays/pos_real.json` (return metrics, absent concepts, aliases); rows redacted | 37 answered, 7 semantic_gap, 6 unsupported; q45 to q48 answered through candidate metrics, q03 and q04/q05 zero-call refusals |
| `iot-09.json`, `retail-08.json`, `pos-06.json`, `coverage-iot-04.json`, `coverage-retail-03.json`, `coverage-pos-04.json`, `pos-multilingual-03.json`, `pos-overlay-v6-01.json`, `pos-features-06.json`, `pos-nosample-03.json` | prompt v6 (per-period rule, length in units, to_date, overlay constructs) with the shape gate, literal check and segment support; all equal to their v5 baselines | 156/160 and 25/26, no over-refusal |
| `pos-real-holdout-03-v6.json` | the 50 questions with overlay v3 (returns excluded by default), prompt v6 and the per-period gate; rows redacted | 34 answered, 3 clarify (每天 misreads caught), 6 semantic_gap, 6 unsupported, 1 failed (template question, model wrote YYYY-MM-DD); q31 to q33 windows right, q03 through the paid_amount metric |
| `pos-real-smoke-v6.json` | the 7 smoke cases with overlay v3; references updated to exclude returns | 7/7, 5 default exclusions applied |
| `iot-10.json`, `retail-09.json`, `pos-07.json`, `coverage-iot-05.json`, `coverage-retail-04.json`, `coverage-pos-05.json`, `pos-multilingual-04.json`, `pos-overlay-v7-01.json`, `pos-features-07.json`, `pos-nosample-04.json`, `pos-real-smoke-v7.json` | prompt v7 (time scope optional with a grain); all equal to v6 | 156/160, 25/26, 7/7 |
| `pos-real-holdout-04-v7.json` | the 50 questions with prompt v7 and overlay v4 (`../docs/research/holdout-02-overlay-and-time.md`); rows redacted | 38 answered (9 verified), 4 semantic_gap, 6 unsupported, 2 failed (template questions); 每天 and 各月份 now per period over all data |
| `pos-real-values-01.json` | the owner's rewrites of q29 and q44 with a store name and a product name (`evals/cases/tier0/pos_real_values_01.yaml`), first value-grounded cases; rows redacted | q44b answered (exact product-name match); q29b clarify: the model cut 特約永和中正在 as 特約永和中 + 正在, the literal check caught the miss |
| `pos-real-holdout-04-verdicts.yaml`, `pos-real-holdout-04-tally.json`, `pos-real-values-01-verdicts.yaml` | the owner's verdicts for run 4 and the two value-grounded cases | 48/48 judged correct, 0 wrong numbers, refusal rate 24%, 9 verified |
| `pos-real-batch1-01.json` | `pos_real_batch1.yaml` (the 50 as a regression set, references inlined from the judged run 4) with prompt v7 and overlay v4; rows redacted; evaluation row bound raised to 1000 so 591-row and 304-row answers compare whole | 50/50, 9 verified, P50 4.2 s, P95 5.9 s |
| `pos-real-holdout2-01-tally.json` | the owner's 30 value-grounded questions (`../docs/research/holdout2-01.md`); questions, report and verdicts stay in `.artifacts/holdout2/` at the owner's request, their SHA-256 are recorded here | 26/30 judged correct; 4 silent wrong numbers, all HAVING questions; 14 literal misses to clarify; refusal rate 73% |
| `iot-11.json`, `retail-10.json`, `pos-08.json`, `coverage-iot-06.json`, `coverage-retail-05.json`, `coverage-pos-06.json`, `pos-multilingual-05.json`, `pos-overlay-v8-01.json`, `pos-features-08.json`, `pos-nosample-05.json`, `pos-real-smoke-v8.json` | prompt v8 (having); all equal to v7 | 156/160, 25/26, 7/7 |
| `pos-real-batch1-02.json` | batch 1 under prompt v8 | 49/50: q06 (訂單筆數最多的狀態) flipped from an accepted refusal to an answer over transfer_status, the recurring absent-concept miss |
| (in `.artifacts/holdout2/run-02.json`, not in git) | holdout 2 under prompt v8: q26, q29, q30 now carry their having threshold, q27 became a structural refusal, q28 stays a literal-miss clarify; owner's verdicts pending | 7 answered, 16 clarify, 1 semantic_gap, 6 unsupported |
| `having-pos-01.json` | `having_pos.yaml`, five HAVING guard cases and one row-filter control on the POS fixture, prompt v8 | 6/6, every threshold in `having`, the control in `filters` |
| `iot-12.json`, `retail-11.json`, `pos-09.json`, `coverage-iot-07.json`, `coverage-retail-06.json`, `coverage-pos-07.json`, `pos-overlay-v9-01.json`, `having-pos-02.json`, `pos-nosample-06.json`, `pos-multilingual-06.json`, `pos-features-09.json`, `pos-multilingual-07.json`, `pos-features-10.json` | prompt v9 (question_values rule) with value grounding available; author sets equal to v8. `-06`/`-09` of multilingual and features each lost one case to a transport error (`model_call_failed`) during a machine sleep and were rerun as `-07`/`-10` | 156/160, 6/6, 25/26 |
| `pos-real-smoke-v9.json`, `pos-real-values-02.json`, `pos-real-batch1-03.json` | real database under prompt v9 and overlay v5 (policies, grounding); rows redacted | 7/7; q29b now answered on a verbatim hint; batch 1 49/50 (q06 wobble) |
| (in `.artifacts/holdout2/run-03.json`, not in git) | holdout 2 with value grounding: 21 answered, 3 clarify, 6 unsupported; 16 hinted, 4 resolved; owner's verdicts pending | see `../docs/research/holdout2-01.md` |
| `pos-real-holdout2-03-tally.json`, `pos-real-holdout2-04-tally.json` | holdout 2 runs 3 and 4 judged (grounding, then the base repair) | 30/30 and 30/30, 0 wrong numbers, 21 then 22 answers |
| `iot-13.json`, `retail-12.json`, `pos-10.json`, `coverage-*-08/07/08.json`, `pos-multilingual-08.json`, `pos-overlay-v9-02.json`, `pos-features-11.json`, `having-pos-03.json`, `pos-nosample-07.json`, `pos-real-smoke-v9b.json`, `pos-real-values-03.json`, `pos-real-batch1-04.json` | full regression with the deterministic base repair; author sets equal; features-11 and batch1-04 lost cases to transport errors and were rerun as `pos-features-12.json`, `pos-real-batch1-05.json` with the one-retry rule | 156/160, 6/6, 7/7; features 32/32; batch 1 see -05 |
| `pos-features-12.json`, `pos-real-batch1-05.json` | reruns with the one-retry rule | 32/32; 49/50 (q39 malformed answer, since repaired) |
| `perturb-batch1-{hints-off,tables-reversed,tables-shuffled,columns-reversed,hidden-transfer,no-aliases,spaced}.json` | metamorphic perturbations of batch 1 (`../docs/research/perturbations-01.md`); rows redacted | correctness 49 to 50 each; structural flips only q09 (count ambiguity), q06 (no aliases), and the q38/q39 null-key shape slip |
| `iot-14.json`, `retail-13.json`, `pos-11.json`, `coverage-iot-09.json`, `coverage-retail-08.json`, `coverage-pos-09.json`, `pos-multilingual-09.json`, `pos-overlay-schema-01.json`, `pos-features-13.json`, `having-pos-04.json`, `pos-nosample-08.json`, `pos-real-smoke-schema-01.json`, `pos-real-values-04.json`, `pos-real-batch1-06.json` | constrained decoding experiment, `output_mode: json_schema` (`../docs/research/constrained-decoding-01.md`); not adopted | 151/249 against 244/249; content steered away and repetition loops |
| `pos-real-batch1-07.json`, `pos-real-holdout2-06-tally.json` | overlay v7 (transaction_count, paid_transaction_count, shipment aliases), json_object mode | batch 1 49/50 with 16 verified (q06 wobble); holdout 2 30/30, 0 wrong numbers |
| `pos-real-batch1-08.json` | overlay v8: absent concept `all_of` (訂單 and 狀態 anywhere in the question) turns q06 into a zero-call refusal | 50/50, 16 verified, 9 zero-call refusals |
