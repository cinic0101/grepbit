# Decision: continue with the schema-first architecture (2026-09-09)

## The question

Is "model chooses inside a closed algebra, server owns schema, SQL, execution,
evidence; reviewed knowledge is an overlay, not a prerequisite" a foundation
worth building a product on?

## Evidence (all live with gemma-4-31b through an OpenAI-compatible gateway)

| Experiment | Result | Artifact |
|---|---|---|
| IoT schema the model never saw, zero definitions, 20 cases | 20/20 correct, P95 3.8 s | `evidence/spike-tier0/iot-03.json` |
| Retail schema, zero definitions, 12 cases | 12/12 | `retail-03.json` |
| Owner-supplied POS plus HR schema (13 tables), 26 cases | 24/26 then 26/26 after one general prompt rule | `pos-01.json`, `pos-02.json` |
| Same schema, all foreign keys dropped | 17/26 with 0 wrong answers; 11/11 keys re-inferred, 0 false positives; 26/26 with inference | `pos-nofk-01.json`, `pos-nofk-02.json` |
| 24 concept-drop probes | planner refused 22/24; LLM audit unreliable (1/2 then 0/2 caught) | `coverage-*.json` |
| Parent agent relaying 14 results | numbers and refusals preserved always; caveats 8/8 guided, 0/8 unguided | `parent-agent-02.json` |
| 32 English and Japanese variants | 31/32; 27/28 plans identical to the Chinese question | `pos-multilingual-01.json` |
| Semantic overlay on 14 weak cases | 10/14 to 14/14; 0 to 8 verified; 4 zero-call refusals | `pos-overlay-before.json`, `pos-overlay-after.json` |
| 32 feature probes from competitor claims | 31/32; follow-ups 6/6; time intelligence 8/8 | `pos-features-02.json` |
| Suggested questions | 9/10 answered, 1 correctly refused | `pos-suggested-02.json` |

Across roughly 200 live cases: zero invented identifiers, zero non-SELECT
statements, zero answers outside the table allowlist.

## Why this supports continuing

1. The core bet held on every schema tried: the model can select correctly
   inside the algebra, and the failures that remain are structural rejections
   (honest refusals), not wrong numbers.
2. The two worst real-world conditions had answers: no foreign keys (inference
   with evidence, marked as assumption) and undefined concepts (planner rule
   plus overlay; residual is the first occurrence of a concept).
3. The overlay converts wrong or refused answers into verified ones without a
   separate compiler or manifest format, so the two tiers share one code path.
4. Language is not a layer: Chinese, English, and Japanese questions produced
   the same plans over a Chinese-labelled schema.
5. Nothing depends on the model vendor: the contract is JSON plans; the model
   is a replaceable generator.

## What this evidence does not show

- Generalization to real user questions: every case was author-written.
- Behaviour on 50 to 300 table schemas (latency already grows with size).
- Derived metrics (ratios, share, growth): not in the algebra; the share
  question was answered as plain sums, the one remaining wrong-answer class.
- Governance: access control, row-level security, PII handling in sampling.

## Decision

Continue. Build the product on this core, in the order given by
`../plan/next-phase.md`, and treat the owner's real questions as the first
measurement that counts.
