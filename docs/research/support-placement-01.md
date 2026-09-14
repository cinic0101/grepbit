# Support text placement: no observed benefit

2026-09-14, complete from `850e967`. Plan:
`../plan/support-placement-study.md`. Production prompt v15 / ask v5 unchanged.

## Result and decision

Moving the identical support statement from table to amount-column comments
does **not** rescue the observed lease-absent wrong answer. Stop this candidate;
the conditional second pass was not run. No production change, lexical exception,
metadata promotion or additional wording search follows from this experiment.

| 18 known questions per arm | Correct answer | Necessary refusal | Wrong answer | False refusal / unassessed / failure |
|---|---:|---:|---:|---:|
| T: table comment | 12 | 5 | 1 | 0 / 0 / 0 |
| F: amount-column comment | 12 | 5 | 1 | 0 / 0 / 0 |

All **13 answered pairs have identical full QueryPlan hashes**, including the
wrong bare SUM of all device monthly fees. Refusal status agrees on the other
five pairs; this does not claim identical free-text rationales. The T arm also
matches the prior study's C arm on all 18 statuses/categories and all 13 answered
plan hashes. No baseline disappearance masks the treatment comparison.

Effective answer yield remains 12/18, coverage 13/18, known wrong among answered
1/13, for this selected authored panel. No combined pass rate is called answer
accuracy. Unknown scope requests still receive semantic_gap in both arms; under
existing rule 7 this is not proof of a mistaken belief that the concept is absent.
The earlier secondary desired-status check is recorded but does not gate this
placement experiment.

## What was controlled

Same 18 authored English questions, three one-table domains, defined/absent/
unknown states, amount descriptions, approved code mappings, NULL semantics,
four data instances and gold recipes as support-state-01. T uses that study's
C messages byte-for-byte by content hash. F moves the complete support paragraph
to the amount column after its original description, separated by one newline;
the table comment is removed. The support paragraph appears exactly once in
both payloads. Tests restore F to T and verify every other schema field is equal.

Only placement and its JSON framing/token positions differ; the facts are not
reworded, duplicated or shortened. All 30 arm/recipe checks produce identical
compiler recipes. No SQL, data rows, expected plans or grading instructions are
provided to the model. Normal total questions remain answerable neighbors.

This comparison does not explain *why* the model ignores the limitation. It
specifically fails to support location alone as a remedy for this fixed text.
Earlier successful column descriptions used different wording/context; their
gain cannot now be attributed to column placement alone. Nor does this establish
that placement never matters in other schemas or models.

## Execution and validation

- 36 initial/actual Gemma 4 31B calls, no validation repairs or transport errors.
  Seed 615 case order, alternating paired arm order, serial existing gateway,
  T=0, thinking off, effective 768-token floor and 20s timeout. No transport retry.
  No rescue, so the predeclared positive-signal screen fails. No second pass.
- Call p50 T 1.470s / F 1.486s, not user-facing latency or a speed improvement.
- 14 primary focused tests plus 3 post-observation integrity tests; static passes.
  The exact source/hash-matched 1,841-test offline gate is reused, not rerun.
- 120 hand-checked compiled/oracle pairs per engine per preparation; PostgreSQL
  executes an independent SELECT and compiled SELECT for each pair. Preparations
  run twice (freeze and live preflight); duplicate checks are not extra coverage.
- 36 fixed-plan ask injections: 24 answerable controls pass; the research oracle
  rejects 12 injected broad answers on refusal-only contexts. This is grader
  validation, not production enforcement. Live answerable proposals use the same
  allowed recipe across four DuckDB instances and full disclosure/value grading.
- PostgreSQL uses existing grepbit_ro and READ ONLY inline VALUES, without stored
  customer-row reads or persistent writes. Live model jobs use actual ask() with
  a DuckDB executor, not full PostgreSQL-driver/MCP serving validation.
- Frozen inputs/helpers/runtime and old evidence remain unchanged. New output is
  hashes, counts and allowlisted facts; no raw completions, reasoning, arbitrary
  exception text, customer data or credentials. No new dependencies.

## Next boundary

Retain the wrong-valid as a regression and stop table/column placement tuning on
this known case. Support text is contextual help, not an enforceable semantic
constraint. A future controlled-refusal proposal must measure both caught scope
omissions and falsely blocked normal/negative/quoted mentions; do not add a lease
keyword exception or infer request intent merely from a proposed plan.

No substitute semantic certifier is authorized or implemented by this result.
If the product needs a stronger unsupported-scope guarantee, separately decide
what reviewed scope information the interface actually receives and what it must
refuse when that information is unavailable. The existing same-model joint-error
findings still apply; rearranging descriptions supplies no independent intent
evidence. Wrong metric selection and role-sensitive gate false positives remain
separate open problems, not solved by these checks.

Evidence: `evidence/support-placement-01.json`,
`.artifacts/support-placement-20260914/`,
`.artifacts/support-placement-analysis-20260914/`. Only plan/report/manifest/roadmap
enter Git; production, public formats, safety and identity boundaries are unchanged.
Local commit only; no push.
