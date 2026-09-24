# Bedrock complex-const compatibility repair (#64)

Status: owner-approved specification and offline implementation. No live request
has been made with the repaired schema.

## Observed violation

The one authorized v2 Converse probe ran at accepted
`dev@025ab8fb1cf0ed8d8908b848f5b6117d3108338f`. Its immutable public report is
`.artifacts/p367-bedrock-stage-d-wD5hIm/run/report.json` (SHA-256
`c5f3a260c27298bfdfb66ef5af68fb1a354a2b8fb5e6ca4c8f4079b2f71f31f1`).
It records one HTTP 400 `ValidationException` and no native execution. The
private, access-controlled error body says the Bedrock output schema rejects
`const - complex`. The body remains local and is not a public evidence asset.

Offline inspection identifies four array-valued `const` nodes in the current
wire schema, all for Compare metrics in direct and clarification proposals.
The canonical recipe schema and its SHA-256
`a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00`
are unchanged. The failing v2 wire SHA-256 is
`d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f`.
The [Bedrock structured-output subset](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)
documents schema validation and HTTP 400 for unsupported schema features.

## Proposed repair contract

Translate only a sole-key singleton array `const: [scalar]` into an array with
`minItems: 1` and an item-level primitive `const`. Bedrock supports `minItems`
values 0 and 1. This preserves the fixed value and nonempty array constraints
at generation time. `maxItems` is outside the documented supported subset;
Grepbit's existing typed
request validator still requires the exact singleton. Other object/array
constants fail closed before HTTP send. Retain existing oneOf-to-anyOf and
unsupported-keyword translation, as well as the unchanged canonical schema.

Version the candidate packet to v3 and its effective runtime identity to v2,
with a new wire-schema SHA-256. The old v1/v2 packet hashes, effective runtime
identity and archived report readers remain valid as historical evidence; old
packets cannot authorize a new live execution. The candidate profile, Japan-only
route, one-attempt bound, 300/420-second budgets, private diagnostic opt-in,
native validation and compatibility success criteria remain unchanged.

After implementation review and merge, prepare an immutable v3 packet from the
accepted clean `dev` source and synthetic E01_overview.en fixture. A separately
bounded Bedrock call may verify whether AWS accepts the new wire schema. A 200
response alone is not quality, model-weight identity or P3 promotion evidence.

## Ruler evidence and recovery

`tests/test_bedrock_complex_const_contract.py` failed at the intended wire-shape,
rejection and version assertions against the accepted v2 code. The owner then
approved this in-scope contract checkpoint on 2026-09-24. The new v3 wire schema
SHA-256 is `93ab99c9162a43412d0588b3ded70cc41a25827582b4d11b8072e3348d201f68`;
its v2 effective runtime identity SHA-256 is
`f56e90fe54662a2929797623a74508751b25424b666227fbd699ec4d4ebf4a3c`.
The old report reader is exercised against the archived v2 HTTP 400 report with
no env or network access. Recovery is to retain v2 historical readback and stop
new probe preparation if the new wire shape or identity cannot be verified
offline.
