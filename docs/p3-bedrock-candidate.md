# JP Bedrock candidate compatibility checkpoint (#64)

Status: offline contract and implementation on the #64 branch. No AWS request
is authorized by this document. Baseline: `dev@2b102b57515f3616480b515468154f5454e8c49e`.

## Candidate and evidence meaning

The owner selected one candidate on 2026-09-24: Amazon Bedrock Runtime Converse,
calling Region `ap-northeast-1`, inference profile
`jp.anthropic.claude-sonnet-4-6`, with processing limited to Japan. The [AWS
model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html)
lists Tokyo as a source for this JP profile and Tokyo/Osaka as destinations. It
lists Converse and structured outputs as supported. Account entitlement,
current route configuration, and provider behavior have not been observed. The
profile names Claude Sonnet 4.6, but its underlying served weight revision is
not independently observable from Converse; preserve that uncertainty in
candidate identity and every result. Recheck the AWS route documentation and
account configuration immediately before packet authorization.
Bearer API-key authentication uses the accepted `bedrock_converse` adapter from
#62 / PR #63. No fallback route or ambient AWS credential discovery is admitted.

Converse returns no model ID. A successful one-call probe may establish that the
configured route accepted the request and that the resulting action crossed
strict JSON, typed request validation and native execution. It **cannot** prove
which exact model served it. The report must retain `observed_model: null` and
separately label requested profile and route acceptance. It must not mark an
observed-model-identity check passed. One HTTP 200 does not prove server-side
JSON-schema enforcement, quality, stability, data residency or P3 promotion.

## One-call packet and stop contract

Add a purpose-specific, versioned Bedrock candidate packet, authorization
envelope, manifest and report. Keep the P3.9/10/11 versions and archived readers
unchanged. The packet pins the candidate ID, provider/API, calling Region,
profile ID, allowed JP destinations, source/accepted-dev SHA, synthetic fixture
and exposed case hash, unchanged P1/recipe semantic identities, canonical schema
hash, translated Bedrock wire-schema hash, response mode, bounds, data boundary,
credential *name*, command template and stop policy. Never include the key,
endpoint address, question text, gold, raw completion or SQL in public evidence.

The current recipe canonical schema hash is
`a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00`;
its Bedrock wire-schema hash under PR #63 is
`d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f`.
These are distinct identities, not interchangeable quality evidence. The one
probe input is the existing exposed `E01_overview.en` question, looked up from
the pinned panel after admission. The evaluated model receives the unchanged
recipe context/schema and this synthetic question, never gold/reference SQL.
The historical 12B semantic identity remains byte-identical and is labeled
`baseline_semantic_identity` in this candidate packet. A separate versioned,
hashed `effective_runtime_identity` carries the actual Bedrock provider, profile,
Region, wire schema and 300-second timeout. The archived report presents both
hashes by those names; it never presents the 60-second baseline as the executed
runtime identity.

Prepare the packet only on a clean accepted `dev` commit after the tooling PR
merges. The separate owner authorization must bind that packet's exact byte hash
and a task-specific owner reference. Before opening the explicit env file or
constructing the client, the runner verifies packet/authorization/source/DB/
candidate and route. It reserves the attempt durably before a possible send.
There is one runtime invocation, one client HTTP attempt maximum, concurrency 1,
300-second call timeout, 2,048 maximum output tokens, no retry, repair, resend,
continuation, cache or fallback. The legacy probe retains its 60-second call
and 180-second publication bounds.
A timeout or ambiguous interruption consumes the attempt and leaves compatibility
unassessed; no rerun to obtain a cleaner result. The 420-second publication
budget leaves 120 seconds beyond the call for preflight, validation and durable
reporting combined. The larger Bedrock-only call budget covers possible first-time
Structured Outputs grammar compilation; [AWS says](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)
a new schema can take a few minutes to compile and successful grammars are
cached for 24 hours. This is a bounded
allowance, not a guarantee that the first call will finish. The owner will
authorize a specific live command and output path
only after reviewing the final accepted packet. Authentication and route failures
must use safe codes without printing headers, key or private endpoint.

The report may expose closed stage/status/error codes, requested profile,
unknown observed model, bounded token/latency data, attempts and pinned hashes.
Compatibility success requires one accepted route and passed response, strict
JSON, typed request and native execution stages; it does not include observed
model-identity proof. Offline fake transport is implementation evidence only.
PR #63's non-blocking `minItems` translation note remains a separate provider
contract follow-up; the current recipe schema has no `minItems` keyword.

## Why a new contract is required

`tools/p3_candidate_probe.py` is closed to the admitted 12B LiteLLM identity,
unencrypted HTTP route, exact returned alias, and Issue #56 authorization. The
new Bedrock adapter is a provider client, not a governed candidate runner. Reusing
the old runner or setting an environment variable would either reject Bedrock or
misstate unknown model identity. The new packet/report therefore needs its own
version and reader while retaining the old evidence byte-for-byte.

Checkpoint decision: the owner approved offline implementation after the
specification and ruler review on 2026-09-24 in this task. The specification
phase had one passing adapter/schema witness and one intentionally failing
missing-runner assertion; the existing Bedrock adapter suite passed 12/12.
The new runner only adds a purpose-specific candidate/evidence contract. It
does not change the accepted recipe semantics, historical readers, thresholds,
data boundary or AWS permissions. Recovery is to leave the provider adapter
available and omit this candidate's packet/live path. Implementation requires
targeted and complete offline checks, local risk review and remote PR review.
Only after merge may the accepted-commit packet be prepared. A promising one-call
compatibility result would justify a separately authorized 28-input exposed
regression; it would not renew fresh quality evidence.
