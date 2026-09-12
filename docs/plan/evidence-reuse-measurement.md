# Existing-evidence measurement: historical strata and one current panel

2026-09-12. Owner approved proceeding after `artifact-reuse-01.md` with
"好 沒問題 可以開始". Root owns the complete analysis. Baseline `d1aee71`,
runtime/test source `e01de711`. Existing psql/Gemma and local-commit authority
remain valid. No push, production or prompt changes, new acceptance threshold,
automatic carry of judgments, human correction UI or training experiment.

## Frozen scope

1. Reuse the prior inventory, check source manifests and input hashes, and
   classify every runner outcome under its original recorded oracle. Keep
   unknowns, status-only passes, real failures and repeat exposures explicit.
2. Audit historical carried verdicts. The tool compares status/SQL/row count,
   whereas plan/bindings may differ; do not infer semantic correctness from a
   copied verdict or silently fix/rewrite the old scores. Report uncertainty.
3. Replay the existing fictional cross-language proposals through current ask,
   if their frozen fixture/context identity can be reconstructed. No new model
   calls in this replay; it measures deterministic gates, not fresh planning.
4. A current end-to-end result is missing: old whole-suite results precede
   current gate/normalisation repairs, and many store only hashes. Run one
   frozen, unchanged-v15 panel using existing golds. Do not repeat for luck.

The current panel is 15 sets / 292 case executions: author 160, features 39,
settled batch 1 50, real smoke 7, service 24 and service adversarial 12.
Keep the 26-case no-sampling control separate from its repeated POS questions;
report scenarios and exact-question deduplication, not 292 independent intents.
Unjudged holdout2/holdout3/ratio questions are not sent again merely to obtain
another answer without a trustworthy new correctness label. Their old evidence
stays in the historical audit. No fresh holdout/generalization claim.

## External scope (explicit follow-up approved)

After the local report, the owner replied "同意，並在結束後告訴我驗證結果，
以及你怎麼判斷這些結果？" to the explicit request naming existing real POS
questions, schema/overlay, eligible candidate values, the private endpoint
http://10.12.0.187:4000/v1 and the 900-attempt cap. This supplies the previously
missing payload/destination permission, subject to managed review. No result
rows, SQL or credentials go to the model. The frozen panel/settings below are
unchanged; no additional model experiment is authorized by this record.

Historical blocker: automatic review rejected the prior invocation before
process creation. Generic owner permission for psql/Gemma did not satisfy its requirement for explicit
real POS question/schema/overlay transmission to the named gateway. No command
ran, credentials were not loaded, and no live artifacts were created. This
scope record cannot grant that permission; do not retry or route around the
denial. Historical analysis and in-memory fictional replay remain in scope.

- Destination: existing configured Gemma4 31B gateway at the previously approved
  private endpoint; opaque `LITELLM_API_KEY` from the original ignored `.env`.
  Serial temperature-0, thinking-off calls, unchanged v15/json_object, existing
  repair limit. At most 292 scheduled cases / 900 transport attempts including
  repair/retry; stop after two consecutive transport errors, any source drift,
  unexpected case universe or budget exhaustion. No Best-of-N.
- Outbound model data: existing consented questions, visible schema/definitions
  and eligible value hints under existing policies; no SQL, result rows, DSNs
  or credentials in model messages. Real POS sampling remains zero.
- Database: existing localhost PostgreSQL, only `grepbit_ro`, existing POS test,
  POS real, IoT, retail and fictional service databases. SELECT/introspection/
  reference comparison only. No setup/admin account, schema/data change or grant.
  Verify current role before running; DSNs exist only as shell environment
  values and CLI names. No second credential copy.
- Outputs: fresh `.artifacts/reuse-measurement-20260912/current/` only; metrics,
  status/reference outcomes, plan/question hashes and source/input identity.
  The writer strips raw fields before writing, suppresses runner stdout/stderr,
  and never writes questions, SQL, rows, assumptions, raw model output or values.
  `--redact-rows` remains on but is not the sole protection. No review sheet.
- Input windows are the case-file as_of, except real POS pinned to the existing
  accepted 2026-02-04 18:00 Taipei. All input hashes and this override are recorded
  before the first call. Partial/failed attempts remain in the ledger.

## Interpretation and completion

Do not conflate reference row agreement, accepted refusal, old human judgment,
compiler differential agreement and intent correctness. Current reference
matches on settled cases remain regression evidence based on accepted prior
answers; they are not independently authored golds or product-population rates.
Recovered historical provenance can bind an old report, not make it current.

Use small private research scripts, not a new runtime framework. Test the
metrics writer/budget and analysis accounting with fictional counterexamples.
No production scoring contract is replaced. Preserve all historical artifacts;
publish a counts/hash-only research report and the exact safety/non-claims.
The already passing `d1aee71` static/offline gate may be reused if tracked source
is unchanged; validate the new private drivers and bind their separate hashes.

## Results by phase

The initial local phase completed historical accounting, carry-lineage audit,
current-source fictional replay and 20 private driver/analysis tests. No
model/PostgreSQL calls occurred in that phase.
That initial local result and exact non-claims are preserved in
`../research/evidence-reuse-measurement-01.md`. After explicit follow-up approval,
the live panel completed on 2026-09-13 Taipei: 292 cases, 283 successful model
attempts, no transport errors. 283 expectations met (228 reference-matched
answers, 54 accepted refusals, one status-only answer); four reference
mismatches, four unaccepted refusals and one unexpected answer remain.
Source/inputs unchanged; five new analysis tests pass. See
`../research/evidence-reuse-live-01.md` for the counts, artifact bindings and
why this is a regression baseline rather than an intent/generalization proof.
