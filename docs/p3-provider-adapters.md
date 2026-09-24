# P3 provider adapter checkpoint (#62)

Status: offline contract for the requested LiteLLM / Amazon Bedrock refactor.
Baseline: `dev@ea099ceb84d3b9b205b26fbad6b075d434e2c918`.
This document and its offline rulers precede runtime implementation. They do
not admit a Bedrock model or authorize a model call.

## Shared boundary

The application submits exactly one system message, one user message, and an
optional named JSON schema. A provider client returns a bounded response with
the same `GatewayResponse` shape, safe error codes, HTTP-attempt count, and
redaction operation expected by the P1/recipe entry. No provider may repair,
retry, fall back, execute a recipe, inspect evaluation gold, or add a model turn.
The existing LiteLLM `GatewayConfig` / `GatewayClient` API, default 31B identity,
closed 12B admission, wire bytes, and P1/recipe semantic identities stay intact.
Historical runners remain tied to their frozen LiteLLM route.

An explicit `GREPBIT_LLM_PROVIDER` selects `litellm` (default) or
`bedrock_converse` in a new client factory. Provider credentials are isolated:
Bedrock reads only `GREPBIT_BEDROCK_REGION`, `GREPBIT_BEDROCK_MODEL_ID`, and
`GREPBIT_BEDROCK_API_KEY`, plus the explicit selector. It does not discover
ambient `AWS_*` credentials, a profile, endpoint URL, or another provider's key.
An explicit env file retains literal parsing, bounded size, duplicate rejection,
and process-environment precedence. Construction makes no network call.
`.env.bedrock.example` shows the four non-secret setting names; keep the actual
key in an ignored local file. `client_from_env()` is the new provider-aware
factory. Historical runner CLIs continue to construct `GatewayClient` directly.

## Bedrock Converse wire contract

The first Bedrock mode uses a Bedrock API key as a Bearer token over verified
TLS to the fixed regional `bedrock-runtime` `/model/{modelId}/converse` path.
The owner confirmed this credential type on 2026-09-24; AWS access key ID /
secret key SigV4 authentication is outside this change.
This follows AWS's [API-key](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html)
and [Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
contracts; the [API compatibility table](https://docs.aws.amazon.com/bedrock/latest/userguide/models-api-compatibility.html)
shows why an OpenAI-compatible endpoint cannot cover every Bedrock model.
Region and model ID are explicit, validated data; model IDs are limited to base
and inference-profile identifiers, excluding ARNs and custom endpoint overrides.
The request carries the unchanged system/user text, `maxTokens=2048`,
`temperature=0`, and one optional `outputConfig.textFormat` JSON schema. The
client validates input and encoded-body limits before one POST. It rejects
redirects, compressed/non-JSON responses, oversized bodies, and unsafe status
classes using the existing safe codes. The transport never logs response text.

The recipe's canonical output schema and its existing identity do not change.
AWS's [structured-output subset](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)
motivates the provider-specific translation below.
The provider wire schema converts `oneOf` to `anyOf` and removes only keywords
that Bedrock's published subset does not support: `minLength`, `maxLength`,
`pattern`, `minItems`, `maxItems`, `minimum`, `maximum`. All other schema keywords
must be supported by a closed allowlist or fail before a send. The wire schema
hash is reported separately from the canonical schema hash. This weakens only
provider-side generation constraints; existing strict JSON, typed proposal,
clarification, and native request validation are unchanged. A generated value
outside those constraints still fails closed as `invalid_request`.
The later [complex-const repair](p3-bedrock-complex-const-repair.md) adds one
closed exception: a sole-key singleton array `const` becomes an array with
`minItems: 1` and a primitive item `const`. Other complex constants fail before
send. Its new wire hash and effective runtime identity belong only to new v3
candidate packets; v1/v2 evidence retains the original hash and interpretation.
The subsequent [grammar-budget repair](p3-bedrock-grammar-budget.md) compacts
only the exact pinned recipe schema for Bedrock after a v3 grammar-size HTTP 400.
It keeps native typed validation authoritative and versions the wire/runtime
identity again; other named schemas continue through the generic translator.
The original schema tree is checked for private credentials and endpoint text
before wire serialization, because JSON escaping can hide a literal secret from
checks on the serialized schema string.

Converse responses have no observed model ID. The adapter must not invent one.
It accepts exactly one assistant text block, `stopReason=end_turn`, and bounded
integer usage, then normalizes to the application's existing envelope for the
unchanged content parser. `max_tokens` maps to `truncated_output`; tool use,
guardrail/content-filter results, malformed envelopes, and non-text blocks do
not execute native work. `returned_model` remains unknown. Requested model and
regional route are configuration evidence, not independent proof of what was
served. Provider-specific response mode and wire-schema identity must be visible
in new offline evidence without changing historical LiteLLM evidence.

## Execution and admission boundary

This change adds offline-capable adapter code and fake-transport tests only.
The user will supply a Bedrock API key later. The actual region/model, model
availability, data boundary, spending bounds, and candidate identity require a
separate admission/compatibility packet and explicit owner live authorization.
The old P3.9/10/11 runners and evidence cannot be repurposed for Bedrock merely
by changing environment variables. Bedrock first-time schema compilation may
exceed those runners' 60-second call bound; a timeout is a failed attempt, not
permission to retry or raise the budget silently.
The [shared observed regression contract](p3-shared-observed-regression.md)
reuses the 28-input loop and scorer behind a separately pinned JP Bedrock
admission wrapper. It preserves the historical 12B packet/reader and requires
a new owner-scoped live packet after review and merge.

## Checkpoint evidence

Checkpoint decision: the owner's 2026-09-24 request explicitly asks for the
complete reversible adapter refactor before they provide credentials and start
execution. The root accepted this in-scope contract after the missing-module
ruler failed for all five tests in the specification phase. No released API,
historical evidence, threshold, persistent state, or external data boundary is
changed. Recovery is to retain the existing LiteLLM route and omit Bedrock
selection; the default and historical runners remain LiteLLM.

The offline ruler in `tests/test_bedrock_adapter.py` covers provider selection,
legacy parity, Bedrock wire shape, strict schema adaptation, response/usage
normalization, fail-closed behavior, attempt bounds, and secret redaction. The
existing P3.10 identity baseline remains the immutable legacy parity witness.
