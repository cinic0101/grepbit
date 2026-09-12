# Metric selection and lexical-gate development screen

2026-09-12. Complete; no candidate promoted. Owner approved the annotation
checkpoint and Gemma calls: "同意，gemma 呼叫也 ok". This slice consumed the
initial 180 attempts only. No challenge, replication, P4, new provider, DB or
Git writes. No production prompt/gate, original ruler or old v2 change.

## Outcome

Adding an all-row count candidate, hiding metric IDs, and making definitions
explicit did not fix either stable wrong answer. The contextual interpreter
mostly failed its interface, so it cannot replace the lexical gate. This is
negative evidence about these interventions, not proof that the product or
contextual interpretation is impossible.

Thirty-six authored development questions: 33 with a clear annotated reading,
three genuinely unresolved rate questions. Six minimal-pair families in three
languages; not 36 independent families and not a blind real-user holdout.
The 24 author-visible frozen challenge questions received no model calls.

| Planner arm | Clear bounded matches /33 | Wrong plans | Format errors /36 | Correct plans blocked by lexical gate |
|---|---:|---:|---:|---:|
| P0 current catalog | 30 | 2 | 2 | 7 |
| P1 add fixture-only all-sale-row count | 30 | 2 | 1 | 7 |
| P2 P1 with opaque metric IDs | 31 | 2 | 0 | 7 |
| P3 P1 with operation/population cards | 31 | 2 | 3 | 7 |

P2/P3 rescue only `rate_count_defined` Japanese, where P0's response was
malformed. Neither improves two families. No previously correct clear plan
is lost. All three candidates fail the predeclared confirmation entry gate.
The existing correct/unblocked count is only 23/33 for P0/P1 and 24/33 for
P2/P3. These are bounded authored-plan outcomes, not overall accuracy.

All four arms repeat both failures:

- `output_count_all` Chinese: "回傳交易筆數。" selects `return_count`, not the
  all-row count, even when that reviewed all-row candidate is explicitly offered.
- `service_rows` Chinese: counts DISTINCT `work_logs.ticket_id` instead of
  work-log rows despite the question distinguishing repeated logs per ticket.

The first remains a scope error; the second is a counted-entity/DISTINCT error.
The non-POS failure has no competing reviewed POS catalog. The catalog change
therefore cannot explain all failures. P2 still retains names/descriptions, so
it does not remove all language cues. Repeated service requests across arms
are identical controls, not four independently randomized treatments.

## L1: the interface is not ready

One of 36 independent question-first extractions passes integrity validation.
That one's semantic core matches gold, but its exact span selection differs.
The remaining 35 fail: 22 schema-validation errors and 13 invalid text offsets.
Within schema failures, fixed error types are 20 `value_error`, one
`literal_error` plus `value_error`, and one `literal_error`.

No raw rejected model content, reasoning text, provider exception text or
Pydantic input/context is retained. Consequently the 22 schema failures cannot
be attributed more finely from this run. They might include semantic-field
inconsistencies as well as serialization errors. Do not call all 35 mere
offset failures or infer that their underlying meanings were correct.

All 60 authored payloads pass the actual runtime parser with the appropriate
source context; it does not unconditionally reject valid input. The original
test-only schema remains unchanged and is compared to the research schema.

The one valid extraction (`output_count_returns`, Chinese) retains two correct
fixed plans and rejects two wrong ones. Only four pairs were actually checked
under model-supplied annotations. One captured correct plan per planner arm
receives a contextual pass; most receive unknown. Zero wrong contextual passes
is therefore **not** evidence of a useful safe replacement: coverage collapsed.

## Actual ask replay and value checks

Replayed the 138 valid captured proposals through actual `ask()`, default
shape gates, compiler, SQL policy and local fictional DuckDB execution. Each
uses three instances under current policy and a local counterfactual that
empties only the lexical concept list: 828 workflows, 744 SQL executions,
zero fresh model calls. Invalid model responses are not reinterpreted as
semantic refusals or silently repaired. No PostgreSQL driver, live grounding
retrieval, MCP surface or deployment validation is claimed. The literal path
asserts there are no literal checks; all other supplied gates are unchanged.

| Arm | Current policy: correct / wrong / unresolved answered | No-lexical shadow: correct / wrong / unresolved answered |
|---|---|---|
| P0 | 23 / 2 / 2 | 30 / 2 / 2 |
| P1 | 23 / 2 / 3 | 30 / 2 / 3 |
| P2 | 24 / 2 / 3 | 31 / 2 / 3 |
| P3 | 24 / 2 / 0 | 31 / 2 / 0 |

Counts in this table are captured question/arm proposals, with outcomes
repeated across three instances, not independent new samples. P3's zero
unresolved answers comes from **three malformed responses**, not correct
recognition/refusal of ambiguity. P1/P2 convert P0's malformed Japanese
unspecified rate into an answer, not a semantic improvement.

Each arm has the same seven false blocks: four English output-action questions
(including both service questions) and the quoted-label question in all three
languages. Removing the lexical gate recovers them in this fixture but leaves
both wrong answers and unresolved rate interpretations untouched. It does not
establish removal is safe on genuine omission cases outside this small bank.
`verified` still denotes reviewed-metric provenance, not NL-intent correctness.

Separately, all 138 compilable proposals were compared with the independent
Python reference over three fictional instances: 414/414 compiler/reference
agreements, no local execution errors. Every bounded-match plan also matches
the gold plan's values. SQL agreeing with its plan does not make either wrong
question interpretation correct. Hand answers and distinguishing witnesses for
the original fixed plans remain in `metric-selection-ruler-01.md`.

## Measurement and implementation boundaries

- Source: `5c53e1f6911e813e00e0d1edbedfa4ee5cad3fbcaea173e79b68a74ca6afb671`;
  static, offline, dry run, live start/end and actual-ask replay agree.
- New source files only: `evals/metric_selection.py`,
  `evals/metric_selection_study.py`, `evals/fixtures/metric_selection.json`,
  `tests/contract/t0/test_metric_selection_study.py`. Prior source hashes,
  original gold YAML/tests and production are unchanged from the ruler slice.
- Grader covers one aggregate or same-table ratio, supported NULL predicates,
  explicit population/basis, grouping prohibition and requested label. It
  expands reviewed metrics and recognizes COUNT(nullable column) and unique
  nonnullable primary-key COUNT DISTINCT laws; it never infers NL intent.
  Time, ordering, limits, HAVING, share, growth, joins and other unsupported
  constructions return unknown rather than being silently ignored.
- P0 uses current v15 prompt and wire normalizer, but intentionally one shot
  without the production model repair turn. All arms share that restriction.
- P1 adds knowledge as well as a reviewed choice. It does not redefine the
  real overlay's payment-based `transaction_count`.
- P3 retains names/descriptions and adds typed cards derived from those
  definitions and the algebra's NULL rules. This makes implicit facts explicit;
  it is not a pure layout-only or identical-byte-information intervention.
- Gemma `gemma-4-31b`, serial, temperature 0, thinking off, max 4096 tokens,
  timeout 60 seconds, SDK retries 0. All 180 attempts completed, no transport
  failures; 139 parsed replies and 41 format failures. No reasoning observed.
  Planner p50: 1.38/1.34/1.44/1.51 seconds; L1 p50 6.25 seconds. Provider usage
  totals 624,611 tokens. Existing opaque credential reused; no rows, SQL,
  proposed plans or gold labels in independent interpretation requests.
- Focused second: 364 pass. Final offline: 1,124 pass; static pass.
  Earlier focused run had one assertion mismatch between omitted optional
  concept and default null; corrected the comparison, not the frozen ruler.
  Final offline includes the subsequent P2 unoffered-ID rejection assertion.

## Next minimal experiments, not production changes

1. Diagnose L1 with safe fixed validation-reason codes before more accuracy
   claims. Separate interpretation failure from offset/representation failure.
   Consider a new inference wire form using verbatim spans plus occurrence,
   with deterministic server offset resolution; ambiguous locations must stay
   unknown. Preserve the original final annotation/gold and report wire metrics
   separately. Any material wire-contract change needs its own ruler first.
2. The conditional P4 question is now meaningful: correct alternatives are
   available but selection still fails. Test a small server-generated typed
   candidate selector (not gold candidates) against a fresh planner, measuring
   both stable errors, correct controls, ambiguity and candidate-order effects.
   Do not conflate this with larger-N repeated sampling.
3. Do not promote a catalog tweak, remove the lexical gate, add multilingual
   word exceptions, or expand the frozen challenge on this evidence. Establish
   usable interpretation coverage and cross-family improvement first.

Artifacts: `.artifacts/metric-selection-development-20260912/` (`live.json`,
`live.jsonl`, `ask-replay.json`, the replay driver, dry run and validation).
Durable summary/hashes: `evidence/metric-selection-development-01.json`.
Dev remains at `746f168`; original dirty work preserved; no stage/commit/push.
