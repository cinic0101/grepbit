# Constrained decoding (JSON Schema guided generation): a negative result (2026-09-10)

## Question

Shape slips (a column written as a string, the table as a sibling key,
`"reason": null` inside a plan) reach the caller as `invalid_structured_output`
unless a deterministic shape repair knows the pattern. Guided decoding makes
the model emit only tokens that keep the output inside the schema, which
would remove the class at the source. Does it, with this gateway and model?

## Setup

`GREPBIT_MODEL_OUTPUT_MODE=json_schema`: the plan client sends
`response_format={"type": "json_schema", "json_schema": {"schema": PlanProposal.model_json_schema(), "strict": true}}`
through LiteLLM to vLLM (`gemma-4-31b`). A probe accepted the mode in 0.9 s
and refused an extra key. Everything else as in the v9 regression: prompt v9,
overlay v6, grounding on. Every set was run once.

## Results

| Set | json_object | json_schema | Failures | Latency |
|---|---|---|---|---|
| IoT 20 | 20 | 13 | 6 `invalid_structured_output` | P50 3.9 to 3.0 s |
| Retail 12 | 12 | 6 | 6 | P50 3.8 to 23.5 s |
| POS 26 | 26 | 12 | 13 | P95 6.6 to 25.3 s |
| Multilingual 32 | 31 | 14 | 16 | P95 25.3 s |
| Features 32 (overlay) | 32 | 24 | 4 | P95 25.7 s |
| HAVING guard 6 | 6 | 3 | 3 | P50 25.2 s |
| Batch 1, 50 | 49 | 27 | 21 | P95 25.3 s |
| All judged sets, 249 | 244 | 151 | 93 | |

Shape repairs did fall from 1 to 0, as the grammar promises. Artifacts
`iot-14.json`, `retail-13.json`, `pos-11.json`, `coverage-*-09/08/09.json`,
`pos-multilingual-09.json`, `pos-overlay-schema-01.json`, `pos-features-13.json`,
`having-pos-04.json`, `pos-nosample-08.json`, `pos-real-smoke-schema-01.json`,
`pos-real-values-04.json`, `pos-real-batch1-06.json` (`output_mode: json_schema`
in the summary).

## Two failure modes, reproduced on single calls

1. **Content steered away.** `downtime_by_model_july` came back as valid JSON
   with `{"aggregate": "sum", "alias": ...}` and no `column`, no dimensions:
   `column` is optional in the schema because `count` needs none, so the
   grammar allowed the shortest path and the model took it. Validation then
   rejected the plan (`plan_measure_requires_column`).
2. **Repetition loop.** `zh_downtime_by_site` produced an alias
   `total_downtime_minutes_sumsumsum...` until the 768-token limit
   (`finish_reason: length`, 23.6 s) and the JSON was cut. Every 25-second
   case in the tables is this loop. Token masking under a grammar is a known
   trigger for it with some backends and models.

## Decision

Not adopted. `json_object` plus deterministic shape repairs stays the
default; the repairs now cover every slip seen (string column, sibling table,
null extra keys), each recorded in `shape_repairs`, which is the health
metric to watch. The `json_schema` mode remains in the code, off by default,
for a backend that handles the grammar well. Options if the class grows:
retry once in `json_schema` mode only after an invalid answer (bounded cost,
but the repetition loop would add 25 s to those cases), a schema with fewer
optional fields split into a decide call and a plan call, or a different
guided-decoding backend on the vLLM side.
