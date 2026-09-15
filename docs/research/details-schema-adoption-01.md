# Details-only displayed schema adopted after versioned order adjudication

2026-09-16, baseline 91c5b46. Owner authorized the conditional adoption and
`rows-direction-adjudication-v1`; [execution contract](../plan/details-schema-adoption.md).
The exact measured candidate is now in the shared planner. No OrderSpec default,
normalizer, gate, Default/fallback strategy, canonical wire, permission or public
response format change. No second prompt arm or repeat of the 180-call study.

## Corrected attribution and post-observation decision

Original native calls 29/119 include `direction: asc`. Candidate calls 74/164
omit direction: that is legal in both shown schemas. Existing OrderSpec supplies
`desc`, then the compiler explicitly writes DESC and discloses it. The prior
report's new-order mismatch was real against its frozen oracle, but was **not
an explicit model choice of descending direction**. SQL's default direction is
not involved; no runtime default is changed to force a test pass.

The owner accepts either disclosed direction for reviewed complete untruncated
details with the specified keys and no explicit/implied direction, ranking or
subset selection. This never means ignore order: stable primary-key ties and
NULLS LAST still apply. OFFSET/paging, LIMIT/Top-N, truncated outputs, arbitrary
permutations, lost/duplicated rows, wrong keys or missing disclosure do not qualify.

Reused the existing `disclosed-answer-v1` evaluator with two context-bound typed
interpretations and two independently written ordered SQL references. No parser,
new evaluator engine or model judge was added. Four saved ordering results pass
both the grader and fresh readonly PostgreSQL replay of their actual SQL. Original
model responses, frozen scores and first study's analysis are untouched. The new
annotation explicitly records post-observation owner adjudication, not a
predeclared gain. This ruling is not itself a general language-recognition system.

After this adjudication and the previously recorded parent output-key correction,
**both arms in each original 45-case round** have 27 correct answers, 16 allowed
necessary refusals, one Return gate false refusal and one genuine lease-population
wrong answer. Original automated totals remain stored separately; do not compare
the revised numerator with an unrevised baseline or call it model improvement.

The same original wire evidence remains: historical Details 8/32 -> 1/32 and
recent Details 2/4 -> 0/4 in both rounds, without fewer proposals or more refusals.
These are separate groups, not diluted with Default or pooled with the smoke.
Candidate side request messages (72 Details plus 18 Default) match current
production exactly; the 18 baseline Default contexts also match. The 72 baseline
Details contexts match after **only** the original measured schema transform.
All 180 context checks use actual current introspection/overlay, zero model calls.

## Implementation boundary

`plan_wire.shown_schema` builds the existing wire first, including request-bound
candidate reference forms, then applies the measured projection only when
`build_messages` passes explicit_rows for `query_kind=rows`. The shared prompt
rules are unchanged. Unknown extra properties remain forbidden; no top-level
columns are legalized or new repairs introduced. The existing disabled-rows
permission and final proposal kind guard remain in place.

Retained `details-schema-only-v21-study` as the explicit prompt revision so the
measured request is byte-identical despite its historical suffix. The old v20
revision assertions in two serving tests are updated intentionally. Default v15,
legacy row fallback v17 and the separate guided response format are unchanged.
This is adoption of the measured JSON-object path, not new guided-decoding proof.

## Six-request actual Web/MCP acceptance

Temporary loopback Web on 8766, unchanged production stdio MCP and shared ask,
readonly synthetic PostgreSQL, and existing LAN gemma-4-31b T=0/thinking off.
A private standard-library loopback relay counts each actual outbound completion
and forwards credentials opaquely; no request headers/keys/DSNs are saved.
Six initial requests, **six physical calls**, against the fixed cap of 18 (186
including the original study, below its 240 cap). No repair, retry, row fallback
or raw shown-schema variant. All frozen source/probe/protocol pins match.

| Original question case | Result |
|---|---|
| parent_worklog_status | Correct ten rows, actual model explicitly supplies ASC this time; full fields/order/disclosure match |
| explicit_minutes_duplicates (S7) | Correct ten ordered values, including duplicates and NULL |
| kind_minutes_records (S8) | Same correct typed proposal as S7; existing concept_not_mapped false refusal retained |
| parent_alert_models | Correct 15 alert records, flat devices.model key and ascending alert_id |
| kind_critical_count | Appropriate ambiguous mode conflict; no rows execution |
| parent_missing_lease | Appropriate semantic_gap for missing lease identity; no all-device substitution |

Three correct answers, two appropriate refusals, one **known false refusal**, no
new wrong answer or operational failure. Values/keys/order were checked against
independent readonly SQL prepared before the six calls, not status alone. Raw
native proposals and public results were checked separately; request IDs are
unique, kind is rows, raw/debug-only fields remain absent from public responses.

The fresh ASC output differs from the original candidate's omitted direction;
do not attribute this to an untested endpoint mechanism or treat it as proof that
the model now reliably provides directions. Stored DESC adjudication and new
HTTP/MCP success are different evidence. No blind generalization claim.

The user's existing Web on 8765 (PID 78063 at verification) was not interrupted.
No launcher, assets, registry or startup-cached configuration changed: each
request starts a fresh MCP process which loads the new planner. Therefore no
restart is required for this change. The temporary smoke Web/relay were stopped.
This is local integration, not external deployment or multi-user readiness.

## Validation, limitations and next step

- Ruler: four intended shown-schema assertion failures, 26 passes. The existing
  evaluator already handled the newly authorized ordering alternatives.
- Focused integration: 115 passed; then one extra candidate-reference/guided
  compatibility test was added and included in the broad gate.
- Broad offline: 2,382 passed, zero skips. Static passes. After the broad gate,
  one long test string was formatting-only reflowed; its Python AST hash is
  identical. Production code and all other tested source hashes are unchanged.
  No duplicate full suite was run for that whitespace-only correction.
- Private probe setup failures (missing import path/model config/optional HTTP
  package) occurred before model requests. Fixed using inert binder config and
  stdlib; no dependency added, no failed setup counted as study evidence.

Close this measured Details wire adoption blocker. The **existing <5% per-set
construct rule remains in force**; no global/permanent threshold relaxation or
claim about unmeasured configurations. The next conversion slice is no longer
blocked by this candidate's ordering oracle. It can start with the prepared
source-unit/public-contract rulers, final SQL conversion semantic self-check and
per-capability shared-service acceptance. New prompt effects still need their
affected-group regression; the six smoke requests are not a replacement for it.

Return gate remains unresolved. The short Default lease question still has a
confirmed 3100.00 all-device wrong answer in both original arms; a longer question
or Details refusal does not clear it. Preserve both wordings as separate controls
in subsequent capability validation; no vocabulary exception or forced lease
definition is introduced here. Unit conversion itself remains research-only in
this commit.

Private evidence: `.artifacts/details-schema-adoption-20260916/` (`ruler`,
`focused`, `adjudication.json`, `smoke`, `service-review.json`, `offline`,
`static-pass`). Durable summary:
[`details-schema-adoption-01.json`](../../evidence/details-schema-adoption-01.json).
Local commit only; no push.
