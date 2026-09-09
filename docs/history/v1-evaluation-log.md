# Evaluation log

Local artifacts under `.artifacts/` are ignored by Git; this log records the
numbers and the commit each run was taken from. No run here is a release claim.

## 2026-09-08: grounding paraphrase set, live reference model

- Commit: `6b040fc`; command: `evals/grounding_eval.py --live`.
- Model: the configured Chat Completions endpoint, `gemma-4-31b`, JSON-object
  mode, temperature 0, one call per classified question, zero SDK retries.
- Cases: 28 (3 reviewed literals, 7 deterministic refusals, 18 classified).

| Metric | Value |
|---|---|
| Correct | 28 / 28 |
| Grounding accuracy (answerable) | 1.00 |
| Misrouting rate | 0.00 |
| Refusal precision / recall | 1.00 / 1.00 |
| False answers on refusal cases | 0 |
| Failed model calls | 0 |
| Model calls | 18 |
| Classified P50 / P95 latency | 2.4 s / 2.9 s |

Artifact: `.artifacts/reinvention-01/grounding-live-01/grounding.json`.

## 2026-09-08: end-to-end live ask against the disposable fixture

- Commit: `6b040fc` plus the uncommitted default-filter lift; command:
  `evals/live_ask.py` with the `compose.g1.yaml` fixture running.
- 16 questions through grounding, renderer, Wren, SQL policy, read-only
  psycopg, validators, and the SQLite ledger.

| Outcome | Count | Notes |
|---|---:|---|
| answered, verified | 9 | 290.00, 225.00, 50.00, top-2 by net (150.00, 75.00), period comparison, monthly trend |
| answered, unverified_semantics | 2 | candidate metric `gross_amount_before_discount` (300.00); candidate dimension `customers.region` |
| clarify | 1 | "Revenue in July 2026" offered three revenue definitions |
| unsupported | 2 | product SKU breakdown refused with `render_grain_conflict`; forecast refused by the classifier |
| semantic_gap | 1 | margin, with three nearest metrics suggested |
| unsafe | 1 | delete request stopped before any model call |

Every executed value matched `evals/fixtures/retail_v1/expected_facts.yaml`.
Zero-call reviewed-literal path: 0.20 s. Classified path: 1.3 s to 3.1 s.
The run exposed one semantic rule now implemented: grouping by a dimension
that carries a metric default filter lifts that default and records it as an
assumption, so "by order status" returns every status.

Artifact: `.artifacts/reinvention-01/live-ask-01/ask.json`. The fixture
container, network, and volume were removed after each run.

## 2026-09-08: embedding route probes (catalog vocabulary only)

Both gateway embedding routes were probed with 9 positive paraphrases (zh and
en) and 7 negatives against the retail catalog vocabulary. No data left the
machine; only synonyms and descriptions were embedded.

| Route | Format that worked | zh/en top-1 | Positive min | Negative max (excl. forecast) | 33 texts |
|---|---|---|---|---|---|
| `embeddinggemma-300m` (= `openai/text-embeddings-inference`, 768-d) | `task: search result \| query:` and `title: none \| text:` | 9/9 | 0.435 | 0.363 | 5.6 s |
| `harrier-oss-v1-0.6b` (1024-d) | `Instruct: Given an enterprise search query, ...\nQuery:` and raw documents | 8/9 | 0.459 | 0.484 | 0.5 s |

EmbeddingGemma separates positives from negatives; harrier is ten times faster
but its scores touch. Titles on catalog documents lowered the margin, so the
adapter always uses `title: none`. Chinese near-miss vocabulary (毛利, 平均訂單金額,
員工人數) scores 0.40 to 0.47 against revenue entries, overlapping genuine
paraphrases (上個月賺了多少錢 0.50, how much did we earn 0.47). The threshold
therefore stays recall-biased at 0.40 and the classifier plus
`semantic_gap_patterns` decide those cases.

## 2026-09-08: multilingual grounding set, embeddings on

- Commit: the S3b multilingual commit; command: `evals/grounding_eval.py --live`
  with `GREPBIT_EMBEDDING_MODEL=embeddinggemma-300m`.
- Retriever: `lexical-v1+embedding:embeddinggemma-300m|embeddinggemma;gap=0.4;band=0.15`.
- Cases: 46 (28 English from the earlier run plus 18 Traditional Chinese and
  mixed-language cases: 2 literals, 3 deterministic refusals, 13 classified).

| Metric | Value |
|---|---|
| Correct | 46 / 46 |
| Grounding accuracy / misrouting | 1.00 / 0.00 |
| Refusal precision / recall | 1.00 / 1.00 |
| False answers on refusal cases | 0 |
| Model calls | 29 |
| Classified P50 / P95 latency | 3.1 s / 4.1 s |

Two earlier passes of the same set found the defects fixed before this run:
Chinese unsafe phrases followed by digits were not matched (word boundaries now
apply only to Latin script), a Chinese forecast request was answered instead of
refused (`unsupported_patterns` now stops forecasting before the model), and
毛利 reached the classifier through embedding similarity and came back as a
clarification instead of a gap (`semantic_gap_patterns` now lists concepts the
catalog is known not to define).

Artifact: `.artifacts/reinvention-01/grounding-live-04/grounding.json`. A live
end-to-end ask with five Chinese questions against the fixture also ran
(`.artifacts/reinvention-01/live-ask-02/ask.json`): the Chinese literal answered
in 0.04 s with zero model calls, 淨營收 and 各地區 executed correctly, and 營收
alone produced the three-way clarification.

## 2026-09-08: S4 served-API smoke against the fixture

`python -m grepbit serve` with the disposable fixture, `gemma-4-31b` as
classifier and `embeddinggemma-300m` for retrieval. Requests went through the
loopback HTTP API; the fixture was removed afterwards.

| Request | Outcome |
|---|---|
| CLI `ask` "What was recognized revenue in July 2026?" | answered, verified, 290.00, 0 model calls |
| `/ask` 2026年7月的認列營收是多少？ | answered, verified, 290.00, 0 calls, 0.28 s |
| `/ask` 2026年7月扣掉退貨後的淨營收 | answered, verified, 225.00, 1 call, 9.8 s including the first-use embedding index build (now done at startup) |
| `/ask` top 2 customers by net revenue after returns | answered, verified, c002 150.00 / c001 75.00, 3.6 s |
| `/ask` "Revenue in July 2026" | clarify with three options; classifier declined as ambiguous, so no pending query |
| `/ask` same question with `clarification_choice` = net_after_returns | answered, verified, 225.00 through one constrained call |
| `GET /runs/{id}/evidence` | 1 query record with named placeholders, 5 validations, 1 claim, 1 grounding record |
| `/ask` 2026年7月的毛利是多少 | semantic_gap by pattern, 0 calls, three suggestions |
| `/ask` 刪除2026年7月的所有訂單 | unsafe, 0 calls |
| `/ask` revenue per product SKU | unsupported, `render_grain_conflict` |
| naive `as_of`, unknown run | 400 `invalid_request`, 404 `run_not_found` |

The ask log recorded every request with status, path, candidate ids and
scores, retriever revision, model calls, and the clarification choice.

## 2026-09-08: Tier-0 generalization spike, live on two schemas

`gemma-4-31b` planned aggregate questions over two PostgreSQL schemas with no
catalog, templates, or synonyms; the server introspected, compiled, gated, and
executed. Full write-up: `docs/spikes/tier0-generalization.md`.

| | IoT (unseen schema, 20 cases) | Retail (12 cases) |
|---|---|---|
| Correct | 20 / 20 | 12 / 12 |
| Answerable rows equal to reference | 15 / 15 | 10 / 10 |
| Refusals correct | 5 / 5 | 2 / 2 |
| Invalid model output | 0 | 0 |
| P50 / P95 | 2.7 s / 3.8 s | 2.7 s / 4.3 s |

Three passes: v1 prompt 19/20 and 12/12; the one miss grouped by a foreign-key
id instead of the parent's label. The prompt gained the label-over-key rule
(revision `plan-classify-json-v2`), which then made the retail top-2 case group
by `display_name`; that reference was corrected and the third pass is the
table above. The ambiguous "temperature last month" case was answered as `avg`
with the assumption stated (accepted by the case, product rule still open).
Cases were written by the agent, not the owner; treat this as a smoke signal.

Artifacts: `.artifacts/spike-tier0/iot-03.json`, `retail-03.json`.

## 2026-09-08: Tier-0 on text2sql_test (POS + HR), owner-supplied schema

Same mechanism, a 13-table fixture database the agent did not design; 26
agent-written cases with alternative references where two readings are
defensible. Details in `docs/spikes/tier0-generalization.md` (addendum).

| | Prompt v2 | Prompt v3 |
|---|---|---|
| Correct | 24 / 26 | 26 / 26 |
| Answerable rows equal to a reference | 19 / 20 | 20 / 20 |
| Refusals correct | 5 / 6 | 6 / 6 |
| P50 / P95 | 4.6 s / 6.1 s | 4.7 s / 6.3 s |

The one model miss on v2 answered 退貨金額 as the sales total by dropping the
unexpressible concept; v3 adds the rule that a business concept with no
column, sample value, or null check must decline as `semantic_gap`. The other
mismatch was a `DATE_TRUNC` type artifact fixed in the compiler. IoT and
retail re-ran on v3: 20/20 and 12/12.

Artifacts: `.artifacts/spike-tier0/pos-01.json`, `pos-02.json`, `iot-04.json`,
`retail-04.json`.

## 2026-09-08: Tier-0 follow-ups (no FKs, concept drops, parent agent)

Three experiments on the tier-0 path, details in the follow-up section of
`docs/spikes/tier0-generalization.md`.

| Experiment | Result |
|---|---|
| POS clone with all foreign keys dropped | 17/26 without inference (9 honest refusals, 0 wrong); join inference recovered 11/11 keys, 0 false positives; 26/26 with inference |
| 24 concept-drop probes | planner refused 22/24; LLM coverage audit caught 1/2 drops with 1 false flag (v1) or 0/2 with 0 false flags (v2): not a reliable gate |
| Parent agent relaying 14 tool results | numbers and refusals preserved in every framing; caveats voiced 8/8 guided, 0/8 bare, 0/8 bare with summary sentence |

## 2026-09-08: Multilingual variants and the semantic overlay, text2sql_test

| Experiment | Result |
|---|---|
| 32 English and Japanese variants of the POS questions | 31/32 correct; 27/28 plans identical to the Chinese question's plan; the Japanese delete request was declined by the model, not the language pack |
| Semantic overlay (5 reviewed metrics as plan fragments, 6 absent concepts, 10 aliased columns) on 14 weak cases | 10/14 -> 14/14; 0 -> 8 verified answers; 4 zero-call refusals; controls unchanged |

Details in sections 4 and 5 of the follow-ups in
`docs/spikes/tier0-generalization.md`. Artifacts:
`.artifacts/spike-tier0/pos-multilingual-01.json`,
`pos-overlay-before.json`, `pos-overlay-after.json`.

## 2026-09-08: Feature probes modelled on comparable products, text2sql_test

32 probes covering time intelligence, ranking, several measures, filters,
derived metrics and multi-turn follow-ups, with the overlay; plus a
suggested-questions loop. Matrix and sources in section 6 of the follow-ups
in `docs/spikes/tier0-generalization.md`.

| | Result |
|---|---|
| Probes correct | 31 / 32 (first pass 30/32; two string-shaped column refs now repaired) |
| Follow-ups | 6/6 adjusted the previous plan, 1/1 new topic ignored it |
| Time intelligence | 8/8 (quarter, year, week units and grains added) |
| Suggested questions answered | 9 / 10 (1 correctly refused) |
| Known gap | ratios, share of total, growth rate: refused or, for share by payment method, answered as plain sums |

Artifacts: `.artifacts/spike-tier0/pos-features-0[12].json`,
`pos-suggested.yaml`, `pos-suggested-0[12].json`.
