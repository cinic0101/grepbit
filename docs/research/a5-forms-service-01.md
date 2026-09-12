# A5 form ablation and non-POS absence semantics

2026-09-12. This batch fixes evaluation, expands non-POS coverage and rejects
another prompt candidate. Production remains prompt v15 / orchestration v3;
A5 is still provisional. No production code, credential policy or existing
database contents changed. Authority and limits: `../plan/a5-forms-and-service.md`.
Artifacts: `.artifacts/a5-forms-service-20260912/`; durable manifest:
`evidence/a5-forms-service-01.json`.

## 1. An evaluator shortcut, exposed by the service source

For tickets that have no event records, SUM(estimate_minutes) must be 99.
The compiler returned 99; the reference returned 3, the number of tickets.
`_evaluate_without` returned a separate count-only result regardless of the
requested measure, skipping normal aggregation, grain, share, growth and
HAVING. The generator only offered count for absence plans, hiding this gap.

The fix makes `without` select base rows, then uses the reference's existing
aggregation pipeline. It deletes the duplicate counting path rather than
adding arithmetic-specific repairs. The generator now draws multi-hop
activity tables and ordinary measures/output selection beside `without`.
This is an existing-contract repair, not a new algebra or semantic default.

Evidence:

- First ruler: 25 passed, one intended failure (reference 3 versus 99).
- Expanded ruler initially had seven failures; six were real missing behavior
  (SUM, NULL SUM, ratio, share, HAVING, growth). The seventh wrongly expected
  the reference to apply LIMIT. That test was corrected: the reference
  deliberately returns the full population; `differential.compare` checks
  the top-k boundary. Its explicit wrong-top-1 control still must fail.
  Do not count this test-author error as a product defect.
- Final service-focused suite: 41 passed, including 18 hand-counted plans
  against compiled DuckDB SQL and the reference, two compile-time join
  refusals, generator reachability/non-count guards and the new NL goldens.
- The same 18 hand-counted plans pass on readonly PostgreSQL. No production
  window helper or evaluator computes their expected answers.
- Four named matrix gaps close: ratio/share/growth/HAVING with `without`.
  Seventeen named-test gaps remain; a named test does not exhaust its cell.

### Differential after the repair

Sampling 0, redacted reports; each generation budget is 500, with fixed
source/schema/data during execution. The service source contains only
fictional data; IoT/POS runs below use random in-memory instances after
readonly schema introspection, not copied customer rows.

| Report | Seed | Valid generated plans | Typed refusals | Comparisons / agreements |
|---|---:|---:|---:|---:|
| service-diff-pg | 51 | 339 | 106 | 233 |
| service-diff-duck, 3 instances | 51 | 339 | 106 | 699 |
| iot-diff-duck, 3 instances | 52 | 365 | 101 | 792 |
| pos-diff-duck, 3 instances | 53 | 353 | 98 | 765 |

Total **2,489 comparisons**, zero disagreements or recorded errors. Refusals
are not comparisons; repeated instances/engines are not unique plans. The
service plan list has 23 absence plans, 20 with a non-count measure; eight
have HAVING and two have LIMIT. No growth-with-absence was drawn in that
sample, so its value evidence is the named ruler, not this random count.
Named segments and sampled value-index literals remain generator gaps.
Window-boundary independence remains limited by shared time helpers.

## 2. Mutually exclusive shown forms: do not promote

The trial adds presence-based `oneOf` clauses to the shown measure and
operands: aggregate, metric, or both ratio operands, not a hybrid. It does
not introduce hard schema decoding, change domain validation, invent a
denominator, or forbid legitimate ratio-plus-share. Eighteen offline schema
checks verify allowed/rejected examples with and without candidate refs.
The model-visible revision stays v15 in both arms; reports have separate
trial labels. No production prompt edit was made.

All Gemma4 calls are serial, thinking off, json_object. First: six synthetic
intent families in zh/en/ja, two interleaved arms (36 proposals), each plan
checked against hand-computed results on two different fictional instances.
Both arms match the exact expected result shape/values on 16/18; baseline
uses three repair turns, exclusive zero. The two composite ratio/share
questions fail this exact comparison in both arms; this strict probe alone
does not classify extra-column versus wrong-value failures. It is not a
measured wrong-valid rate or generalisation result.

The repair-cost signal justified an 84-case follow-up, not adoption:

| Set | v15 baseline | Exclusive-form trial |
|---|---|---|
| q25, two repeats | answered twice | unsupported twice, after repair |
| h2_q23, two repeats | answered twice | answered twice |
| authored member-ratio, two repeats | correct twice | correct twice |
| original service 24, public-label overlay | 23/24, unknown-work-date case failed output | 24/24 |
| new service adversarial 12, same overlay | 10/12 | 10/12 |

The real q25/h2_q23 cases are unjudged and already seen: answered is not
accuracy. Nevertheless the repeated loss of answer availability is enough
to reject this candidate for promotion. One improved authored set does not
justify overriding the regression. Earlier q25 failures under v15 remain
evidence; two successful baseline repeats do not erase them.

No full new-revision regression was run because no trial was adopted. The
existing v15 implementation is not thereby accepted or released.

## 3. The new source exposes language-policy limits

`service_adversarial.yaml` adds twelve authored cases, four intents in three
languages: SUM after absence, three-hop activity absence within a child time
window, records versus distinct entities, and created versus closed time.
Goldens are fixed independently and checked against hand-counted answers.
Keep this set separate from the original 24; do not inflate historical scores.

Two synthetic-only diagnostic reruns reproduce the failures:

- **svc_units_en:** the valid plan counts work logs and distinct ticket IDs,
  but `Return both totals` triggers the return/refund concept gate. Keeping
  exactly the same plan and removing only that imperative sentence changes
  `unmapped_concepts` from returns/return to no hit. This is a deterministic
  false positive, not a schema-linking or candidate-binding failure.
- **svc_absent_feb_ja:** the model declines because it believes absence needs
  an unsupported anti-join, although `without` already supports the requested
  three-hop query (verified by the fixed-plan ruler). Static inspection shows
  rule 8 is present for the corresponding zh/en cases but absent for this
  Japanese question: the trigger list contains no matching Japanese phrase.
  That identifies missing guidance, not proof an appended rule fixes it.

Neither concept protection nor trigger behavior is silently changed. Avoid
another one-word exception; a next bounded design should consider offering
capability guidance from the schema and handling ambiguous concept words
without turning off protection against dropped business meaning. Those are
separate prompt/policy changes and cannot inherit this experiment's scores.

## Validation, privacy and closeout

Static gate passes; **396 offline tests**, no errors/failures/skips. Only four
code/test/case files changed relative to the previous A5 follow-up snapshot:
`evals/reference_eval.py`, `evals/plan_generator.py`, the new service value
test file and the new adversarial case file. Existing uncommitted work is
preserved. No stage, commit or push; HEAD remains 746f168. Verify source
hashes identify the tested dirty tree, not the baseline SHA alone.

Real runs used existing grepbit_ro, sampling 0, redacted rows and the
metrics-only writer; no raw customer values/questions/SQL/plans persisted.
Only the two wholly fictional service diagnostics additionally retain their
synthetic plan and refusal explanation. There are 36 synthetic proposals and
86 runner case executions (84 pilot, two diagnostics), not a claim of 122
model calls: repair and zero-call gates change that count. PostgreSQL golden
script initially missed an import path and was corrected before any DB call;
it is setup evidence, not a failing value ruler. All runs have ended.
