# Bedrock wire schema v5: outcome coupled to its fields (#77)

Status: owner-directed harness repair; contract, rulers and offline
implementation. No AWS request is included here. A separately authorized
compatibility call and, only if accepted, a new observed run follow later.

## Observed defect

The [#74 diagnostic](p3-reason-diagnostic.md) reproduced all six
`invalid_request` outcomes of the #70 JP Bedrock observed run with one closed
reason, `clarification_shape`, and one structure: root keys exactly
`outcome, recipe_id, recipe_version, request`, `outcome=clarify`, a complete
valid native request and no `clarification` object (report SHA-256
`4d5a662972060ab15d6f7377e338bf00736c06a4130cc4d157424cb2a30c484d`).

The canonical output schema cannot produce this shape. Its `oneOf` has three
request branches with `outcome` fixed to `request`, one declined branch and a
clarify branch that requires `clarification`. The
[v4 compact wire](p3-bedrock-grammar-budget.md) traded that structure for
grammar size: one root object, `outcome` as a three-value enum and
`recipe_id`, `recipe_version`, `request` and `clarification` all optional.
Under that grammar a clarify signal on a request body is admissible, the
native validator always rejects it, and Sonnet 4.6 took that path
deterministically (6/6 in two runs at temperature 0). The clarify cohort in
#70 was 0/5 for this reason, not because of the `minItems: 1` choice bound
suspected in #72.

## Contract

The Bedrock-only compaction of the exact pinned recipe schema becomes a root
`anyOf` of five closed objects, each with `additionalProperties: false`:

| Branch | Required | Properties |
| --- | --- | --- |
| request x3 | `outcome`, `recipe_id`, `recipe_version`, `request` | `outcome` const `request`; `recipe_id` const `overview`, `compare` or `breakdown`; `recipe_version` const `0.1`; that recipe's own native `request` shape |
| declined | `outcome` | `outcome` const `declined` |
| clarify | `outcome`, `clarification` | `outcome` const `clarify`; the v4-flattened `clarification` (`kind` enum, `choices` items with `id` and `semantic_value.anyOf` of the four typed values) |

Descriptions stay stripped from the wire. `choices` keeps `minItems: 1`
because Bedrock supports only 0 or 1; the native two-to-four rule, kind/value
pairing, uniqueness, scope preservation and question binding remain
authoritative. The canonical schema, its prompt copy, the system message,
context, strict JSON parsing, typed validators, native execution, oracles,
thresholds and the LiteLLM path are unchanged. A changed schema under the
pinned recipe name still fails closed instead of being compacted.

Root `anyOf` passed Bedrock schema validation in v3, which was rejected later
only for compiled-grammar size (7,607 bytes, five branches with the
clarification shapes repeated). v5 keeps v4's single flattened clarification
and adds only the branch wrappers: 4,663 compact bytes against v4's 3,962
and v3's rejected 7,607. AWS publishes no numeric budget, so acceptance is unknown until
one compatibility call.

## Identities and archived evidence

| Identity | v4 (grammar budget) | v5 (coupled) |
| --- | --- | --- |
| Candidate packet | `p3-bedrock-candidate-packet-v4` | `p3-bedrock-candidate-packet-v5` |
| Effective runtime | `p3-bedrock-effective-runtime-v3`, SHA-256 `4d1f27ded8138dbe9618c6f8c4b32ca4555d8a244ac5e7d94e1287f9de4fb2ed` | `p3-bedrock-effective-runtime-v4`, SHA-256 `ef60af9db5fe329603fca28b4c9bc13fc6d3effd2387d9f27140cb1f79ec6480` |
| Wire schema | `ea4e03d02732c0c45f9905ccd9b7c0010bedc87a190666e7b31895867c43e53b` (3,962 bytes) | `e377c4f0807d90674e3d30c8274533fc0c70c363d15d6c1a07019849a6a6c456` (4,663 bytes) |
| Canonical schema | `a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00` | unchanged |

Readers for v1-v4 candidate packets keep their pinned hashes. The observed
runner's v1 packet is bound to the v4 wire and the v4 compatibility witness,
so the archived #70 report reads unchanged; preparing a new v1 packet now
fails with `source_identity_failure` because the live wire has moved. A new
observed run needs a v5 compatibility witness and a new observed packet
version, each a separate gate. The #74 diagnostic pins its own v4 identities
so its archive reads unchanged and its consumed grant cannot be replayed on
the new wire.

## One-shot compatibility authorization (v2)

Remote review of the implementation found that the compatibility probe's
authorization bound only the packet digest and the Issue #64 reference, so
one envelope could in principle start another attempt at a fresh output path.
The envelope is now `p3-bedrock-candidate-authorization-v2` and also binds the
exact repository-local run slot (`--run-output-dir` at binding). Live mode
checks the slot against `--output-dir` before credential access, and the
slot's exclusive creation consumes it, so a complete, stopped or interrupted
attempt can never be followed by a second send under the same envelope. A v1
envelope still reads back for the archived p368/p369 evidence but never admits
a live attempt; a moved v2 archive fails readback.

## Rulers and acceptance

The specification ruler `tests/test_bedrock_wire_coupling_contract.py` failed
against the accepted v4 code at three intended assertions: root branch
coupling, rejection of the two diagnostic shapes, and the new identities. It
uses a minimal validator for the closed keyword subset to show that v5 rejects
every diagnostic shape and a recipe/shape mismatch while admitting a valid
request, decline and two-choice clarify, and that the v4 root admitted the
diagnostic shapes. Archived p368 (v3 grammar rejection), p369 (v4
compatibility), p370 (observed) and p374 (diagnostic) reports must read back
unchanged. The full offline suite runs once at closeout. No AWS call occurs in
implementation or tests.

## After merge

One owner-authorized v5 compatibility call on the exposed E01 input under the
#64 procedure, recorded as before. Another grammar-size rejection ends this
repair line pending a separate design decision; it is not permission to keep
reshaping the schema. Only an accepted witness admits a new observed packet
version and a separately authorized 28-input observed run. Neither is fresh
quality, stability or promotion evidence.

## v6b: two-branch root after the v5 grammar rejection (#77, decision A)

The single owner-granted v5 compatibility attempt on accepted `dev@5e9aecf1`
(packet `ea641bfe…`, slot `.artifacts/p375-bedrock-stage-d-8RHP4H/run`,
report SHA-256 `90d9e74ae8f486ccb2424e1f361d0746a10913cd49ce51f1447789c099f601d2`)
stopped at HTTP 400 `ValidationException` with the same private diagnostic
class as v3: the compiled structured-output grammar is too large. No model
output, no native execution. Observed boundary so far:

| Wire | Root | Compact bytes | Bedrock |
| --- | --- | --- | --- |
| v3 | five branches, clarification shapes repeated | 7,607 | rejected |
| v4 | one object, every branch field optional | 3,962 | accepted (admits the #74 defect) |
| v5 | five coupled branches | 4,663 | rejected |

The owner chose, in the local conversation on 2026-09-25, the order A (smaller
coupled root) → B (no provider-side grammar for Bedrock) → C (smaller
clarification contract, a P3.1 change). v6b is A: a root `anyOf` of **two**
closed objects. The action object has `outcome` enum `request | declined`,
`recipe_id` enum, `recipe_version` const and `request` anyOf of the three
native shapes, with only `outcome` required; the clarify object has `outcome`
const `clarify` and the required v4-flattened `clarification`. A clarify
signal can therefore never carry a request body and never omit
`clarification`, which is exactly the #74 defect. Deliberately left to native
validation, as in v4, are the recipe/shape pairing and a bare
`{"outcome":"request"}` or `declined` with a body; none of these was observed
in #70 or #74. Offline size 4,095 compact bytes, 133 above the accepted v4.
Acceptance is unknown until one compatibility call; a rejection of v6b moves
to decision B, not to further reshaping.

Identities: candidate packet v6, effective runtime v5; v5 constants stay as
`COUPLED_*` and v4 as `GRAMMAR_BUDGET_*`, so the p368, p369, p370, p374 and
p375 archives read unchanged. The observed runner's v1 packet and the #74
diagnostic remain bound to v4.
