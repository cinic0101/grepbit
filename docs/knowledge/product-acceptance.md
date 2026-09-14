# Product acceptance evidence map

This is a dated evidence map, not a production-readiness certificate. Baseline
`9e86ca8`, 2026-09-14; runtime v15 / ask v5 / MCP v1 remains unchanged.
See [protocol](../plan/product-acceptance-path.md) and
[results](../research/product-acceptance-path-01.md).

## Fixed assets, distinct purposes

| Layer | Asset | What it measures |
|---|---|---|
| Authored model panel | `.artifacts/db-aware-challenge-20260914/{service,iot}-cases.yaml` | 24 fictional Service/IoT questions: 20 answerable, four refusal controls. Not unseen user questions. |
| Prospective acceptance data | `.artifacts/product-acceptance-path-20260914/{service,iot}-acceptance-v2.json` | Same `disclosed-answer-v1` grader; four previously reviewed equivalent COUNT/AVG recipes added. No historical score rewrite. |
| Gate adversarial controls | `.artifacts/source-scoped-gate-20260914/results.json` | 24 fixed question/plan pairs across four arms/multiple data instances. Not model accuracy. Retain true-omission negatives alongside false refusals. |
| Name/time mechanisms | Existing scoped-grounding and time-closure contract tests | Binding/normalization/compiler contracts, not language understanding. |
| Product transport | `.artifacts/product-acceptance-path-20260914/live/` | Six serial actual stdio MCP requests, response fingerprints, safe statuses/counts. Not upstream agent faithfulness or concurrency readiness. |
| Natural questions | [Owner intake](../plan/next-owner-holdout.md) | Awaits genuinely new user questions and provenance. Historical owner panels remain historical. |

The private `asset-map.json` hashes existing cases and evidence. `preparation.json`
freezes all 24 contexts, rule identities and independent PostgreSQL oracle hashes
before live requests. `evidence/product-acceptance-path-01.json` is the committed
hash/count manifest. Missing private artifacts block reproduction; a fresh clone
does not contain these questions/scripts. Do not regenerate substitutes and claim
to have replayed the same acceptance set.

## Rules for the next measurement

1. Verify the manifest and preserve the old artifacts. Copy the harness to a
   fresh ignored run directory, adjust output location explicitly, and freeze its
   identity before calling a model. Scripts use exclusive-create outputs; do not
   rerun into the existing `live/` directory. Recheck inherited input paths/hashes.
2. Use the registered, consented datasource and opaque credential bootstrap in
   `environment-and-secrets.md`. This run's isolated registry uses sampling zero
   for Service/IoT and does not change the deployed registry. Credentials stay in
   the invoking shell. Never pass gold plans, reference SQL or rows to the planner.
3. Reuse the metrics-only boundary in the private `client_probe.py` /
   `server_probe.py`. Bind the actual server, grade before serialization, compare
   the serialized fingerprint at the client, then discard raw tool payloads.
   `--redact-rows` by itself does not make a wholesale runner/MCP dump safe.
4. Report correct answers, known wrong answers, necessary refusals, false
   refusals, unassessed outcomes and operational failures separately. Preserve
   exact-status mismatches separately from appropriate refusal actions. An
   accepted oracle match does not upgrade `unverified_semantics` on the wire.
5. Preserve gate safety controls; no local improvement licenses disabling the
   gate. New acceptance annotations are prospective and evidence-linked. A plan
   absent from an open interpretation list is unassessed, not automatically wrong.

The private `owner-intake-template.json` is blank metadata only. The existing
question converter/intake process is ready; no new questions were supplied or
fabricated by this slice. Do not restart another authored-bank generation loop
to fill this missing input.

## Current product boundary

Serial research integration is demonstrated. General production integration is
not: same-datasource requests reuse a run ID, end-to-end cancellation/deadlines
are not established, and failed responses can include raw model debug text.
Before concurrent/untrusted consumers, specify and test per-request lifecycle
identity, safe public response projection and bounded completion. Reuse existing
registry/executor mechanisms; a new multi-agent or human-correction framework is
not required. A parent agent's faithful rendering remains a separate test boundary.
