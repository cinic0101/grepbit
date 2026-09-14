# Query extension input-encoding diagnostic

## Work and authorization (2026-09-14)

Baseline: clean `448a453`. Owner resumed with "現在可以繼續了" after
the safe-stop commit. Scope continues the previously authorized query-family
research, read-only PostgreSQL/Gemma experiments, self-directed checkpoints,
and local commits; original permission sources are in query-extension-study.md.
Root owns all edits. No production/Web change, push, data mutation, new provider,
credential storage or public/evaluation contract change.

Preflight: existing Web and the previously acknowledged Claude session remain;
no running regression process found. Do not stop or modify either process.

## Hypothesis and frozen procedure

The research runner renders question characters as ASCII JSON escapes in the
message content. A model reads that text, not a parsed Python question. Test
whether literal Unicode improves selection before building another intent
interface. This is a hypothesis, not a diagnosis or proof of a model defect.

- Change ONLY the question value's JSON rendering. All metadata, order,
  schema/rules, model settings, compiler and scoring stay fixed. Decoded JSON
  must be equal. ASCII questions have byte-identical messages across arms.
- Preserve default escaped behavior and all historical artifacts.
- Reuse frozen 12-case original/natural panel from
  `.artifacts/query-extensions-20260914/followup.yaml`. Run escaped, Unicode,
  escaped, Unicode in serial (48 calls); then Unicode on the frozen 21-case
  explicit panel (21 calls). Maximum **69 actual HTTP calls**, no retries.
- Endpoints: existing on-prem Gemma 4 31B gateway and localhost PostgreSQL;
  opaque existing key/DSN environment, grepbit_ro, synthetic IoT/Service only,
  sample limit zero. Model sees fictional question/schema/unit metadata only,
  not rows, oracle SQL or credentials. Each run uses existing bounded SELECTs.
- Original questions are seen development cases; no new holdout claim.
  Original four, other probes, necessary/unnecessary refusals, wrong answers
  and invalid output remain separate. No post-hoc oracle loosening.
- A repeated paired gain supports input-format sensitivity on this panel,
  not independent intent certification or a gateway batching explanation.
  ASCII controls and repeated baseline expose uncontrolled endpoint variation.
- Record remaining entity/population, measure, group/limit and conversion
  failures directly from plans and oracle values. Do not repair meanings with
  vocabulary rules. Decide further work from these results; no Web promotion.

## Validation

Focused roundtrip/byte-identity tests before live calls; existing 44 compiler
and value checks unchanged. One static/offline closeout after implementation.
Fresh artifacts: `.artifacts/query-extension-encoding-20260914/`.

## Completed measurement

All 69 calls completed; both natural-panel rounds go from 4/12 to 10/12,
including original four from 1/4 to 4/4. Same-format parsed proposals and
outcomes repeat exactly. Explicit Unicode controls: 18 correct, 2 necessary
refusals, 1 malformed dimension wrapper. Rental-scope omission and joined-row
projection remain separate gaps. See `../research/query-extension-encoding-01.md`.
49 focused and 1,953 offline tests pass; static green. No production changes.
One additional zero-model readonly replay confirmed the existing production
dimension-wrapper normalizer recovers the correct hours value; its result is
diagnostic, never added to live accuracy or used to rewrite the raw run.
