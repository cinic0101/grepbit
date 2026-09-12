# A5 form experiment and service value coverage (2026-09-12)

Authority: the owner instructed "可以一起做的就一起做，checkpoint 有把握就繼續
go，同意 psql, gemma4 呼叫，開始吧" after the roadmap discussion. One local
owner preserves the existing dirty tree at HEAD 746f168. No stage, commit,
push, new credentials, runtime roles, packages or persistent DB writes in
this batch. Existing semantic decisions remain unchanged; new product or
data-exposure decisions remain explicit stops.

Two coupled workstreams, sequenced around frozen-source live runs:

1. Add hand-computed service value checks for natural-key joins, distinct
   counting units, missing activity across multiple hops, arithmetic and
   time-column choice. Compare compiled SQL and reference independently
   against fixed answers. Do not claim generated questions are a holdout.
2. Experiment with mutually exclusive aggregate/metric/ratio forms in the
   model-visible schema. Preserve legal ratio-plus-share forms. Initially
   at most 48 synthetic end-to-end proposals (including three languages),
   with one existing repair turn each; no new production prompt yet.
3. If justified by the synthetic controls, use a bounded seen-case pilot
   on service/POS (up to 100 case executions). No production promotion on
   validity alone. Any adoption receives a separate prompt revision and
   affected-set regression. No A4 in the same change.

External scope: serial Gemma4 requests to the previously authorised gateway
for schema, synthetic questions and already-consented case questions plus
eligible public candidate labels; never result rows. Local PostgreSQL
localhost:5432 through existing grepbit_ro, DSNs only in shell environment,
for fixture or consented SELECTs. Real data uses sampling 0, redacted rows
and metrics-only persistence. Source and data remain frozen during runs.
Artifact root: `.artifacts/a5-forms-service-20260912/`. Routine diagnostics,
tests and evidence closeout continue without repeat approval.

## Completed batch

The exclusive-form trial is not promoted: 36 synthetic proposals showed
fewer repairs but no exact-result gain; the 84-case pilot lost q25's answer
twice. Two additional synthetic diagnostics isolate language-policy gaps.
No production prompt or concept/trigger policy was changed. A5 stays open.

Service value rulers found a real evaluator defect: absence used a separate
count-only path. It now filters rows and reuses ordinary aggregation.
Generator coverage includes multi-hop absence and non-count measures. Twelve
new authored multilingual cases were added; their goldens are hand-checked.
Final focused 41, full offline 396, PostgreSQL goldens 18 and static checks
pass. Differential: 2,489 comparisons, no disagreement/error, with explicit
coverage limits. Full results: `../research/a5-forms-service-01.md`; durable
manifest: `evidence/a5-forms-service-01.json`. No active runs or Git writes.
