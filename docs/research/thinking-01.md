# gemma-4-31b thinking mode on the planner (2026-09-11)

## Setting

The owner asked whether the model's thinking mode
(`chat_template_kwargs.enable_thinking`) helps on the hard cases, off for
simple ones. The gateway passes the switch to vLLM; the reasoning comes back
in `reasoning_content` and the answer stays valid JSON in `content` (in text
mode it arrives fenced as ```json, which the normaliser now accepts).
`GREPBIT_MODEL_THINKING = off | on | repair` (`dae3a94`'s repair turn plus
`72dbf49`) switches it on every planner call or on the repair turn only,
with a 120 s budget of its own. The ablation ran with `on`, the same code,
prompt v14 and overlay v12 as the judged runs of the same hour.

## Numbers

| Set | thinking off | thinking on | p50 off | p50 on | p95 on |
|---|---|---|---|---|---|
| batch 1, gemma-4-31b (50) | 50/50, 15 shape repairs, 0 repair turns | 50/50, 9 shape repairs, 0 repair turns | 4.2 s | 14.2 s | 31.2 s |
| batch 1, gemma-4-12b-it (50) | 39/50, 4 malformed after repair | 38/50, 8 malformed after repair (each 48 to 56 s) | 2.9 s | 27.5 s | 48.7 s |
| holdout 3 (15) | 15/15: 7 answers, 8 structural refusals (run 8) | 14/15: the same 8 answers, q03 the same misread as run 6, two refusals changed reason from `unsupported` to `semantic_gap` (run 9) | 5.1 s | 24.0 s | 30.6 s |

Completion tokens per call rise from about 80 to 340 to 630 (the probe on
會員交易佔比: 18 s in text mode, 47 s in JSON mode).

## Reading

No set gained an answer. On the 31B the plans are already right where the
algebra reaches; thinking made them slightly tidier (fewer qualified order
fields) at 3.4 times the latency. On the 12B thinking did not cure the
unasked dimensions and produced more malformed outputs, each at the edge
of the budget. On holdout 3 the eight refusals are structural (time parts,
rolling averages, custom-length period growth): no amount of thinking
produces a construct the algebra lacks, and q03 was misread the same way
with or without it.

So thinking mode is a negative result for this task on this model, at
least as a default or as a first call: the failures we have are not
reasoning failures. Two uses remain plausible and untested: `repair` mode
(think only when the first call failed validation, a few percent of
calls) and a future construct whose planning is genuinely harder (a
multi-step decomposition). The setting stays in the code, default `off`.
