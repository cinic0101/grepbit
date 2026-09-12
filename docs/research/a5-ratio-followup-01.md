# A5 ratio output: diagnosis and rejected remedies

2026-09-12. This slice adds guards and evidence, **not a production fix or A5
acceptance**. Production remains prompt v15 / ask v3. No SQL, schema, policy,
normalisation or prompt behavior changed. Existing uncommitted work is preserved.

## What was actually observed

An opaque trace captures allowlisted key structure before reference resolution
and before/after normalisation. It never persists customer questions, literals,
raw responses, SQL or rows. Error traces retain only types and allowlisted paths.

- Six initial case executions: q25 answered twice; the authored member-ratio
  case answered correctly twice; h2_q23 failed once with extra forbidden
  plan keys, then answered. This does not erase earlier q25 failures.
- In the metadata-free counterfactual, q25 reproduced the missing denominator
  twice. The **raw model JSON already contains only a numerator**, plus a bare
  aggregate and `share_of_total`. Normalisation turns that into an incomplete
  ratio and validation rejects it. A supplied denominator was not lost in
  these traces. The failure mixes two arithmetic representations.
- Eight new tests check preservation of both operands through flat, nested
  and mixed wire forms, with/without reference resolution. Four tests verify
  that a missing numerator or denominator is rejected without guessing.
  All pass with the existing implementation. They are regression guards,
  not red/green evidence for a production repair.

## Three bounded experiments

All Gemma4 calls were serial, thinking off, json_object. Real-source calls
used existing grepbit_ro, sampling 0, overlay pos_real, redacted rows and
the additional metrics-only output writer. Real as_of is fixed to
2026-02-04 18:00 Taipei; authored POS to 2026-02-10. See the manifest for
artifact hashes and the diagnostic scripts for exact case selection.

### 1. Paired operands and incidental metadata

Three arms, three previously seen cases, two repetitions, interleaved within
each case (18 case executions). Only one change per arm:

| Arm | Completed answers | Failed outputs | Observation |
|---|---:|---:|---|
| unchanged v15 | 6/6 | 0 | a short local run, not proof of stability |
| shown schema adds numerator/denominator `dependentRequired` | 4/6 | 2 | h2_q23 repeats extra forbidden fields |
| omit model-visible `prompt_revision` | 4/6 | 2 | q25 repeats the incomplete mixed-share ratio |

Both modifications are rejected for promotion. The two real cases are
unjudged; "completed answers" is **not accuracy**. Only the authored member
case has a golden, and it passes twice in every arm. The model-visible
revision remains v15 in the schema-only arm; trial identities are recorded
separately in reports. No endpoint-causation claim follows from these runs.

### 2. Synthetic repair feedback, domain path vs flat wire path

The model sees a fabricated malformed proposal, not a newly generated first
answer. Both arms receive the same question, schema, candidates and malformed
text. Only the error path changes from `...ratio.denominator` to
`...denominator`, matching the flat schema. Three languages, two malformed
forms, two arms: **12 model calls**, no real DB or customer data.

Five synthetic rows have two critical events; a valid repaired plan must
compile and return the single scalar 0.4 in DuckDB. Domain-path feedback
repairs 5/6 correctly; wire-path feedback repairs 6/6. This is a small
repair-only result on constructed failures, not end-to-end generalisation.

### 3. Same initial prompt, real q25 repair-path counterfactual

Both arms use the metadata-free initial prompt above to reproduce the same
malformed shape. Two repetitions per arm (four case executions): domain-path
feedback fails both times; flat-path feedback validates the proposal but ends
in `unsupported` both times. **No answer is recovered.** Reference binding
succeeds in the latter, which does not make the resulting plan semantically
correct. Do not count the refusal as a successful repair of the user's task.

Conclusion: neither a generic field-presence hint, metadata removal nor error
path translation is currently an evidenced end-to-end fix. In particular, do
not special-case this hybrid shape into a guessed denominator or silently
erase share semantics. No tested prompt change enters production in this slice.

## Validation and next boundary

38 focused tests pass; **355 offline tests**, zero failures/errors/skips, and
static checks pass. Only `test_value_reference_contract.py` changed among
code/test files relative to the grain-retirement slice. A5 remains provisional;
no stage, commit, push, DB write, package install or new credential file.

Artifacts are under `.artifacts/a5-ratio-20260912/`; durable counts and hashes
are in `evidence/a5-ratio-followup-01.json`. A few diagnostic setup mistakes
(import path, required fixture metadata, setup slicing) were corrected before
their model calls; none is counted as a model failure or a behavior ruler.

The next useful experiment is mutual exclusion of raw/metric/ratio measure
forms in the shown contract, with checks that legitimate ratio+share forms
remain representable. Presence constraints alone did not address the mixed
representation. Measure this on synthetic malformed/valid controls first;
do not add another repair guess or call a now-seen holdout independent.
Any production prompt change still needs a new revision and affected-set
regression. Do not stack A4 before A5 has a justified acceptance result.
