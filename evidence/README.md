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
| `pos-real-holdout-01.json` | first run of the owner's 50 real questions on the real POS test database (`evals/cases/tier0/pos_real_holdout.yaml`), judged mode, sampling off, rows redacted, gates on; verdicts in `pos-real-holdout-01-verdicts.yaml`, numbers in `pos-real-holdout-01-tally.json` (`../docs/research/holdout-01.md`) | 39/50 judged correct; 4 wrong numbers without an exposed assumption, 7 with; refusal rate 30%; P95 4.7 s |
