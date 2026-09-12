# Retire lexical grain deletion (2026-09-12)

Authority: the owner answered "ok" to the explicit proposal to remove the
rule that drops a grain when period words are absent, following the reproduced
`svc_month_minutes` failure. Earlier permission to use local readonly psql
and serial Gemma4 remains in force; no Git stage/commit/push is authorised.
Preserve all existing uncommitted work. This record is not an authority source.

Scope: remove the rule, helper, result field, repair label and misleading
assumption; keep single-period clarification and its period word list.
Keep the model-proposed valid grain and the compiler's existing interpretation
and assumptions. No new words, new algebra, prompt changes or A5 repair.
Version the served orchestration, not the unchanged v15 prompt.

Validation: red/green orchestration rulers including multilingual and absent
period words, plain aggregates/share/growth, then broad offline/static gates.
Execute a fixed monthly plan through the real readonly database and compare
with the independent golden SQL; run fresh service raw/label and IoT model cases serially.
Keep previous reports intact. Persist metrics only for any real-source work.

Preflight: worktree delta matches the prior slice; elevated read-only process
check found no running spike/regression/pytest process. No delegated writer.

## Completed evidence

Artifacts: `.artifacts/grain-retirement-20260912/`; counts and hashes in
`evidence/grain-retirement-01.json`. Orchestration is v3; prompt remains v15,
and the language pack is unchanged. The period list still serves the separate
single-window clarification gate. No live process remains.

- Ruler: 15 multilingual/plain/share/growth cases, initially 6 failures and
  9 passes; all pass after retirement. Focused ask/gates: 38 passes.
- Full offline: 343 passed, no failures/errors/skips. Final static checks
  pass. The only post-offline code/test edit splits an import in a test file;
  all six gate tests pass again afterwards.
- Fixed plan through readonly PostgreSQL: one case, three monthly rows match
  independent golden SQL, no model call. No DB writes or fixture changes.
- Gemma4 serial live: `evals/cases/tier0/service.yaml`, raw schema **22/24**
  (previously 21/24); public-label overlay **24/24** (previously 23/24).
  `svc_month_minutes` now has the correct three periods. Raw mode's two
  existing name-resolution refusals remain. Five label references resolve
  without errors; this is not a new A5 accuracy claim.
- `evals/cases/tier0/iot.yaml`: **19/20**, unchanged; the first-week wording
  case remains wrong. No model-output failures in these 68 case executions.
- Case files, golden SQL and scoring were not modified. This validates the
  small authored fixture, not generalisation or arbitrary model grouping.

The first focused invocation used a nonexistent runner-test path (zero tests,
recorded as setup failure); the corrected invocation and broad gate passed.
The first fixed-planner diagnostic needed a `settings` attribute for report
metadata, then passed. Neither setup failure is counted as a behavior ruler.

Only three production files and two test files differ from the prior slice's
source hashes. Documentation/evidence updated; no staged or committed changes.
The prior A5 implementation and its unresolved q25 acceptance warning remain
unchanged. Its investigation is the next independent work item, not silently
bundled into this semantic change.
