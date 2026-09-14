# Support-state metadata: useful locally, not a reliable boundary

2026-09-14; complete from `7b0c4b9`. Research plan:
`../plan/support-state-confirmation.md`. Production v15 / ask v5 unchanged.

## Decision

Do not promote metadata-only scope enforcement or start a retrieval/knowledge
service on this evidence. The first-pass screen fails; its conditional second
pass was not run. One lease-unknown error becomes a safe refusal, but the
confirmed-absent lease question still produces an unrestricted total even with
the full limitation delivered. Warranty/insurance controls already succeed
without the intervention. No cross-domain incremental benefit was established.

This is not evidence that descriptions never help. It is evidence against
treating this description candidate as a dependable safety boundary. It also
does not establish endpoint drift: the earlier successful lease experiment used
different wording and column-level metadata, while this one uses table comments.
Those differences were not independently varied here.

## Frozen design and actual work

18 authored English cases: lease, warranty repairs, insured shipments × defined,
confirmed absent, undocumented configuration × scoped request/unrestricted total.
The new domains are authored diagnostics, not unseen real-user holdouts. Small
one-table schemas are deliberate isolation, not representative product context.

A has original amount descriptions and defined code mappings; B adds neutral
table prose; C adds reviewed support-state facts in the same table-comment site.
Mappings in defined schemas are identical in every arm. Unknown schemas have an
opaque status code and no approved mapping; absent schemas have no scope field.
C also states that unrestricted totals remain supported. Its text includes
handling guidance as well as facts, and B is not token-length matched: this is
an information-package comparison, not a pure wording/length causality estimate.
No gate, overlay, identifier, sample values, SQL algebra or query text changes.

54 contexts and oracle identities frozen before calls; fixed shuffled case order,
rotated arm order. **54 initial/actual Gemma 4 31B calls**, no repairs or transport
errors. Serial existing gateway, T=0, thinking off, effective 768-token floor,
20-second timeout, SDK and application transport retries suppressed. Four fictional
instances per answerable computation; SQL/rows never sent to the model.

| Per-arm 18 cases | Correct answer | Necessary refusal | Wrong answer | False refusal | Unassessed / failure |
|---|---:|---:|---:|---:|---:|
| A original | 12 | 4 | 2 | 0 | 0 / 0 |
| B neutral | 12 | 4 | 2 | 0 | 0 / 0 |
| C support facts | 12 | 5 | 1 | 0 | 0 / 0 |

All 12 answerable controls survive in every arm. Both A/B wrong answers are the
lease scoped requests in absent and unknown states. C rescues **unknown only**.
Effective answer yield stays **12/18**; answered coverage is A/B 14/18, C 13/18.
Known wrong among answered is A/B 2/14, C 1/13, on this selected panel only.
No score combining correct answers and refusals is reported as answer accuracy.
Call p50: A 1.473s, B 1.488s, C 1.566s; not a user-facing latency claim.

## Two independent diagnoses

**Delivered information can still be ignored.** The failed C lease-absent
request's complete 325-character table comment is present in the exact frozen
message payload (hash rechecked), including the confirmed lack of scope support.
Thus it is not a missing/truncated metadata transport issue. A post-observation
11-alias bounded search recovers exactly one full captured plan hash: a bare
SUM(monthly_fee), no population filter. Four DuckDB replays confirm the all-device
totals, including NULL on empty data. These are replays of one proposal, not four
new failures. The oracle rejects this because the required population cannot be
identified; no fictional numeric answer for the unavailable subset is invented.

**Typed refusal does not identify why support is missing.** All three C unknown
requests return `semantic_gap`, not the study's desired `clarify`. A/B do likewise
for warranty and insurance; their lease-unknown request instead answers wrongly.
However, existing system rule 7 explicitly routes an unmappable concept to
`semantic_gap` and describes `ambiguous` as two equally plausible readings.
An undocumented code mapping need not supply two plausible candidate readings.

Consequently, this secondary ruler asks for a distinction the current contract
does not clearly promise. Its mismatch is **not** proof that Gemma believes the
business concept is absent, nor a new production regression. Free-text rationale
is hash-only and was not independently certified. Primary refusal accounting is
unchanged; the stricter research match is reported separately (14/18 in each arm).
Even removing this secondary requirement would not pass the primary screen:
only one domain improves and a known wrong answer remains.

## Verification and limits

- 16 primary focused tests, plus 4 post-observation integrity/diagnosis tests.
- Each preparation checks 180 compiled-gold/oracle pairs in DuckDB and 180 in
  PostgreSQL, with independent hand arithmetic. Each PostgreSQL pair executes
  a reference SELECT and a compiled SELECT. Preparation runs twice, before
  freeze and before live; repeated checks are not independent case coverage.
- Three wrong-population foils are distinguished. 54 fixed-plan ask injections
  retain all 36 arm/control answers; all 18 broader answers on refusal-only
  contexts are correctly classified as wrong by the research oracle. The server
  accepting those injections demonstrates why metadata is not a hard boundary.
- Live answerable proposals are checked on all four DuckDB instances using the
  same permitted recipe and full disclosure/value grading. Refusal-only requests
  have no numerical gold; answering them is evaluated against their frozen
  support constraint, not an invented subset total.
- PostgreSQL uses `grepbit_ro` and inline VALUES only: no stored customer rows,
  persistent data changes or new credentials. Live ask execution uses DuckDB;
  this is not full PostgreSQL-driver/MCP serving validation.
- Fresh static passes. Source/hash-matched offline 1,841 reused, not rerun.
  Frozen helpers, payloads and source remain unchanged. No arbitrary raw model
  output, reasoning or exception text is persisted.

## Next boundary

Stop broad metadata/prompt expansion for this candidate. Preserve its positive
control and the newly documented wrong-valid as regressions. Do not replace the
existing checks with a same-model intent certificate or add a lease keyword rule.

If pursuing the earlier column-metadata gain, the next useful *bounded diagnostic*
is identical facts at table versus amount-column location, including unrestricted
neighbors; no simultaneous rewording or new schema. It would test delivery
sensitivity, not certify scope intent or justify automatic promotion. Do not
attribute the current difference to location or batching before that comparison.

Separately, any externally exposed defined/absent/unknown distinction should come
from reviewed configuration provenance, not be reverse-inferred from a model's
refusal code. A future contract must specify that distinction explicitly; none
is added in this slice. Wrong metric selection and role-sensitive gate false
refusals remain separate open problems.

Artifacts: `.artifacts/support-state-20260914/`,
`.artifacts/support-state-analysis-20260914/`; durable manifest:
`evidence/support-state-01.json`. Only docs/evidence enter Git; no production,
public format, identity, safety-boundary or historical-score changes. No push.
