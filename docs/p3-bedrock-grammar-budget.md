# Bedrock structured-output grammar budget (#64)

Status: owner-approved specification and offline implementation. No additional
AWS request is included here.

## Observed boundary

The separately authorized v3 packet at accepted
`dev@6d8e2ee8c1ed20095cd5f8d9b349d05a48b60079` consumed one Converse HTTP
attempt and stopped at HTTP 400 `ValidationException`. The private diagnostic
says the compiled structured-output grammar is too large. Public report:
`.artifacts/p368-bedrock-stage-d-BsGc30/run/report.json`, SHA-256
`6efa30f1549851d36fa8c660f181b51d23db5d8832e9d5f77e97440d0f22c0b0`.
There was no model output or native execution. This distinguishes the new
grammar-size rejection from the prior complex-const rejection; it does not
establish route acceptance or a candidate quality result.

The v3 wire schema is 7,607 compact JSON bytes with 131 object nodes. Its
clarification branch alone is 4,698 bytes and repeats the Overview and Compare
native request shapes in nested alternatives. The `minItems`/`maxItems` removal
also leaves choice arrays without a provider-side upper bound. These are
offline complexity observations, not proof of which AWS grammar limit was hit.
An in-memory prototype of the proposed flattening and description removal is
3,962 compact JSON bytes with 94 object nodes. That reduction is an engineering
target, not an AWS acceptance threshold.
AWS [documents](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)
its supported JSON Schema subset and first-use grammar compilation, but does
not publish a numeric grammar-size budget that can be used as an offline pass
threshold.

## Proposed bounded change

Keep the shared canonical output schema, its prompt copy, strict JSON parsing,
typed action/clarification validators, and native execution unchanged. For this
exact pinned recipe schema, generate a Bedrock-only compact wire schema:

- Use one closed top-level object with required `outcome` in
  `request | clarify | declined` and optional `recipe_id`, `recipe_version`,
  `request`, and `clarification` fields.
- Keep the three native request object shapes under `request.anyOf`, while
  allowing the native validator to enforce the `recipe_id`/shape pairing.
- Flatten clarification to one `kind` enum and one `choices` item shape;
  `semantic_value.anyOf` retains the four existing typed value shapes. The
  native clarification validator still enforces kind/value pairing, choice
  count, uniqueness, scope preservation, and question binding.
- Remove descriptions only from the Bedrock wire schema. They remain in the
  canonical schema embedded in the unchanged system message.
- Reject a changed schema under the pinned recipe name instead of silently
  applying this product-specific compression to it. Preserve the existing
  generic Bedrock schema translation for unrelated named schemas.

This is a deliberate provider-side constraint reduction: AWS grammar can
generate combinations that native validation rejects. It may change model
quality, so one successful compatibility call is still not quality evidence.
No fallback, repair, extra turn, SQL path, or new data destination is admitted.

Version the Bedrock candidate packet, wire-schema hash, and effective runtime
identity again. Keep v1-v3 packet/report readers and old byte identities, but
only the new packet may bind a new live attempt. The Japan-only route, one HTTP
attempt, 300/420-second budgets, private HTTP 400 diagnostic capture, and
synthetic E01 input remain fixed. After implementation review and merge,
prepare a fresh packet from accepted clean `dev` and conduct at most one new
owner-bounded compatibility call. Another grammar rejection ends this repair
line pending a separate design decision; it is not permission to keep shrinking
the schema or retry until green.

## Alternatives and evidence limit

`$defs` factoring could shorten the JSON bytes while the compiler may still
expand the same grammar. Removing structured output entirely would change the
response contract more sharply and is outside this proposal. The proposed
flattening reduces duplicate branching while keeping bounded typed request
shapes at the provider; it cannot guarantee Bedrock acceptance offline.

The specification ruler failed at three intended assertions against accepted
v3 code: compact wire structure, same-name schema drift rejection, and new
identity. The owner approved this in-scope checkpoint in the local conversation
on 2026-09-24. The implementation leaves the canonical schema SHA-256
`a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00`
unchanged. The new 3,962-byte Bedrock wire schema has SHA-256
`ea4e03d02732c0c45f9905ccd9b7c0010bedc87a190666e7b31895867c43e53b`;
the v3 effective runtime identity has SHA-256
`4d1f27ded8138dbe9618c6f8c4b32ca4555d8a244ac5e7d94e1287f9de4fb2ed`.
Native rulers verify rejection of request/recipe and clarification kind/value
mismatches newly possible at the provider wire. The old v2 and v3 HTTP 400
reports remain readable without env or network access. These offline facts do
not establish AWS grammar acceptance or candidate quality.
