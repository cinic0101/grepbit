# Bounded recipe interpretation (P2.6 / P3.1)

Issue #26 / PR #27 accepted one model-facing route over the native
[Overview, Compare and Breakdown APIs](p2-recipes.md). Offline fake-transport
checks are not live model validation or the P2 exit. This is separate from the
unchanged [P1 scalar contract](model-integration.md).
Issue #39 extends this same route with [bounded clarification](clarification-action.md);
it does not replace the accepted native recipes or add another planner.

```text
question + one shared English instruction, recipe meanings and clarification admission
  -> one GatewayClient.complete call with the same schema as a generation constraint
  -> existing provider-envelope normalization
  -> strict JSON and closed typed action validation
  -> request: exactly one native recipe -> original native pack
     clarify: no analytics -> typed choices + deterministic presentation
     declined: no analytics -> existing model_declined result
  -> sanitized interpretation evidence
```

The explicit import is `grepbit.recipe_model`. Ordinary `import grepbit` and
deterministic recipe calls do not import this module, gateway configuration or
network libraries. There is no new CLI, runner, discovery call or configuration.

## Closed output contract

`recipe-request-json-v2` preserves the v1 request/decline alternatives and adds
one closed clarification alternative. The unchanged request shape is:

```json
{
  "outcome": "request",
  "recipe_id": "overview",
  "recipe_version": "0.1",
  "request": {
    "center_code": "<explicit code>",
    "start": "<explicit month start instant>",
    "end": "<exclusive next month start instant>",
    "timezone": "Asia/Taipei"
  }
}
```

The angle-bracket strings above describe required data, not valid date defaults.
`recipe_id` is exactly `overview`, `compare` or `breakdown`; request branches have
exactly the four root fields shown. Each selects its existing strict validator:

| Recipe | Native request | Native execution |
| --- | --- | --- |
| `overview` | `OverviewRequest`: exactly `center_code`, `start`, `end`, `timezone` | `execute_overview` |
| `compare` | `CompareRequest`: exactly `current`, `baseline`, each a restricted `FactRequest` | `execute_compare` |
| `breakdown` | `BreakdownRequest`: exactly `start`, `end`, `timezone`, `top_k` | `execute_breakdown` |

Each Compare scope requires `metrics: ["confirmed_booked_amount"]`, `start`,
`end`, `timezone: "Asia/Taipei"`; `center_id` is absent or null. Periods must be
distinct full months with explicit current/baseline roles. Other metrics and
non-null filters reject, rather than being removed or replaced. Compare retains
its native IANA calendar validation; Overview and Breakdown retain their reviewed
fixed-UTC+08:00 month profile. Equivalent instant representations are permitted
where the native validator permits them.

Overview echoes the exact explicit code, without trimming, name resolution or
model-authored canonical IDs. Its public executor binds the code inside its
existing transaction. Breakdown requires an actual JSON integer `top_k` in 1-3,
not a boolean, decimal, string, inferred default or denominator override.

The unchanged decline branch is:

```json
{"outcome":"declined"}
```

The new branch is `{"outcome":"clarify","clarification":{...}}`, with one of
four explicitly typed kinds, 2-4 exclusive choices and no model-authored labels.
The complete [semantic and presentation contract](clarification-action.md)
defines native scope reuse, reversed comparison roles, supplied code checks and
the closed alternative meanings. No resume or value lookup is implemented.

No mixed branches, extra root/nested fields, explanations, answers, reasoning,
SQL or task lists are admitted. Existing `strict_json` rejects duplicate keys at
every depth, invalid Unicode, nonfinite numbers and multiple values. There is no
markdown stripping, fragment extraction or separate-reasoning rescue.
`output_schema()` describes all native shapes in the prompt; native validators
remain authoritative, including byte bounds and calendar semantics. No second
schema-validation dependency or month/period language is introduced.

## Shared runtime meanings and identities

Every question receives the same English system message, including all three
recipes, their native fields, fixed semantics and unsupported boundaries. Only
the user-message question changes. There is no language detection, keyword
router, evaluator constraint channel, recipe preselection or second model call.

Meanings come from the reviewed runtime catalog and bounded recipe contracts:
current confirmed bookings; booking creation time; amount before refunds; seats,
accounts and people are different; server-owned roles, ordering, reconciliation,
arithmetic and independent whole-scope denominator. The model may clarify one
admitted ambiguity. Missing years, periods, baseline or k remain deferred and
currently decline without earning necessary-refusal credit; unsupported
requirements are not silently rewritten.
A stated year shared by two named Compare months can apply to both. No clock or
`AS_OF` value supplies an absent year. Profit, targets, annual aggregation and
unrelated multi-question requests must not be reduced to convenient subsets.

No evaluator assets, sibling translations, case IDs, expected parameters or
values, source rows, reference SQL, fixture code-to-ID maps, previous completions,
gateway addresses or credentials enter the system context. Context construction
does not access SQLite. Documentation is not loaded as runtime context.

`context_identity()` and each result's `evidence["context_identity"]` identify:

- `learningops-recipe-context-v2`
- `recipe-request-json-v2`
- `recipe-selection-instruction-v2`
- SHA-256 of the canonical context, canonical output schema, English instruction,
  complete submitted system message and reviewed catalog.

The adapter hashes the context it actually submits, not a question-specific
expected contract. P1's system instruction, context, output contract, hashes,
partial constraints and stopping classifications remain unchanged.

## JSON-schema generation constraint (P2.11)

Issue #34 added one controlled wire change: P2 requests **prompt + JSON-schema
constrained generation + strict verification**, while P1 remains prompt-only
generation followed by strict verification. The schema remains embedded in the
P2 prompt. That historical change preserved the v1 semantic protocol. P3.1
deliberately versions the recipe action schema, context, instruction and
generation identity to v2; [old/new identities and sizes](clarification-action.md#identity-and-size-impact)
are recorded separately from unchanged native semantics and P1 wire.

`GatewayClient.complete(..., json_schema_constraint=None)` preserves the exact
historical five-field request when omitted or null. Its only additional argument
accepts exactly `{"name": ..., "schema": ...}`. The gateway constructs:

```python
{
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "grepbit_recipe_request",
            "schema": output_schema(),
        },
    },
}
```

This shows the additional request field, not a duplicated schema definition.
The recipe adapter uses the same schema object supplied by `runtime_context()`
from `output_schema()`. No arbitrary `response_format`, provider kwargs,
`extra_body`, additional output mode or capability negotiation is admitted.

Schema names use 1-64 ASCII letters, digits, underscores or hyphens; the recipe
name above is fixed. The schema must be a nonempty JSON object with finite,
UTF-8-encodable JSON values. Non-serializable/cyclic/excessively deep data,
non-string object keys and tuple-to-array coercions reject with fixed
`invalid_input`, without exporting the schema or exception text. Incremental
encoding bounds accumulated schema bytes by the existing 32768-byte request
cap. The full serialized request, including the wrapper, must also fit that
unchanged cap or fails `input_too_large` before HTTP. Configured credentials,
gateway addresses and hostnames are rejected in schema values **and keys**.
This is not a general secret detector; only the reviewed code-defined schema,
not user/model-authored schemas or configuration, belongs in the recipe route.

`structured_output_identity()` and adapter `evidence.structured_output_identity`
identify the constructed generation contract separately from semantic context:
`recipe-structured-output-v2`, `mode=json_schema`, the fixed schema name,
canonical schema SHA-256 and canonical complete response-format wrapper
SHA-256. These identify the requested policy, not proof that a server honored it.
The [recipe manifest](recipe-smoke.md) pins that identity and current source.

The accepted envelope parser, `strict_json`, RecipeProposal/native validators,
deterministic APIs, invalid-JSON fingerprint and intent-first grader remain
necessary. Constrained generation does not establish correct recipe choice,
user intent, semantics or source truth. A provider ignoring the constraint and
returning fenced/think-wrapped/trailing-prose content still gets strict rejection;
valid JSON with a wrong native schema remains `invalid_request`.

A route rejecting the parameter retains the existing HTTP/configuration error
and stops without a second request. There is no fallback to prompt-only mode,
deprecated `guided_json`, stripping, extraction, repair or retry.

The original P2.11 Stage A used fake HTTP only. Its inspected application/PATH environments did
not expose installed LiteLLM, vLLM or an eligible schema compiler or trusted
proxy configuration. Deployed versions, passthrough/`drop_params`, backend
configuration and exact support for root `oneOf`, `const` arrays, nested scopes
and other schema keywords remain **UNKNOWN**. Upstream API documentation is not
deployment evidence. No model was loaded and no endpoint was contacted. A
separately authorized P2.11 compatibility call and P2.12 panel subsequently
succeeded on the v1 contract. They do not validate P3.1's expanded v2 schema,
whose deployed compatibility and model quality remain untested. Any future
authorized call must fail closed rather than relax the schema.

## API, native results and failure evidence

```python
from grepbit.recipe_model import interpret_recipe_and_execute

# client is an explicitly constructed GatewayClient; use a fake transport offline.
result = await interpret_recipe_and_execute(question, database, client)
```

Live construction/execution requires separate owner authorization under
[local execution policy](local-execution.md); this signature is not authorization.
No actual credentials are needed or read by the offline suite.

`RecipeInterpretation` holds `proposal`, `analysis_pack`, `error`, `evidence`,
plus optional `clarification` and `presentation`.
`RecipeProposal` holds the validated recipe ID/version and original typed request.
Both wrappers are frozen and repr-safe. `analysis_pack` is the actual
`OverviewAnalysisPack`, `CompareAnalysisPack` or `BreakdownAnalysisPack`, not a new
editable universal pack. Its request object, IDs, scope, snapshot, slots,
provenance, limitations and Fraction serialization are preserved.
A successful clarify has no proposal, pack or error, and returns immutable
semantic choices plus server-rendered English presentation. Request validation
passes while `kernel_execution` stays `not_run`. It is not a decline or answer.

Only native typed requests reach a fixed three-way dispatch. No database
connection, profiling, admission or lookup occurs before completion and typed
validation; no model call occurs inside a native transaction. The outer deadline
is positive and at most 60 seconds. Prompt preparation reduces the completion
allowance; the native database timeout is `min(2 seconds, remaining total time)`.
Time is checked before and after execution and after evidence export. A late
result is discarded, not returned as a successful pack.
Clarify skips dispatch entirely: no SQLite connection, scalar/grouped executor,
snapshot or partial pack. Deadline failures clear clarification/presentation,
including evidence copies, and never report a fictitious analytical execution.

The adapter reuses P1's envelope normalization, usage parsing, bounded failure
fingerprints, strict JSON and the existing GatewayClient/safe_export. It does not
copy those privacy-sensitive parsers or refactor P1 into a general orchestration
framework. R1 logging protection, ignored separate reasoning, provider extension
compatibility, redirect/proxy/TLS controls and byte caps stay in the same code.
The request still uses `gemma-4-31b`, temperature 0, stream false, 2048 output
tokens and zero client retries. Only the bounded P2 `response_format` above is
added; no SDK, tool or reasoning flag is used. Upstream inference work is not
inferred from client attempts.

Evidence records P1-style stages, model/usage/finish metadata, attempts, elapsed
time, identities, validated proposal, sanitized native serialization, pack
status and fixed errors. Clarify records its semantic values and presentation
separately, with `model_outcome=clarify` and `clarification-presentation-v1`.
If safe export would redact either actionable object, the adapter rejects it
with fixed `invalid_request` and returns neither object. Missing model/usage
stays unknown. An unapproved model
is rejected; the new route does not export its arbitrary alias, retaining null
`returned_model`, `unexpected_model` and the bounded envelope fingerprint.
Returned error objects contain fixed codes without retained payload tracebacks.
Use `evidence` for reporting: native request/pack objects are not general-purpose
redacted logs. `safe_export` protects configured secrets/addresses; it is not a
general detector of private data. This route remains synthetic-data-only.

| Outcome | Evidence meaning |
| --- | --- |
| Declined | One attempt, `model_declined`, no native execution; necessary refusal is not established |
| Clarify | One attempt, validated bounded choices and deterministic single-select presentation; zero analytics; intent/grounding not proved |
| Malformed envelope/JSON/request | Fixed stage error, no native execution or repair |
| Valid typed proposal | Retained unchanged, not certified as the intended interpretation |
| Partial Overview | Native partial pack and explicit optional gaps |
| Nonempty zero denominator | Native complete pack with explicitly undefined ratio |
| Empty Compare/Breakdown | Native failed data-condition pack; execution stage passed, no operational error |
| Required/binding/global/snapshot failure | No pack; allowlisted native code, no arbitrary exception text |
| Budget/configuration/transport failure | Existing fixed ModelError stopping classification, not a decline |

Native `budget_exceeded`/`output_limit_exceeded` map to `budget_exhausted`;
`invalid_catalog`/`unsupported_source`/`invalid_limits` to `source_failure`.
Ambiguity, incompatible facts, overflow, snapshot loss and other allowlisted
execution failures retain their native codes under `kernel_failure`. Unknown
native error strings become `unknown`. Optional failures already handled by
Overview remain native gaps, not adapter-level errors.

## Invalid-JSON structural diagnostics (#31)

Only when P2 content fails the unchanged `strict_json` acceptance function,
`evidence.invalid_json_fingerprint` records `invalid-json-structure-v1`. Envelope
failures do not enter this path. Valid JSON with an invalid recipe shape remains
`invalid_request`, with no invalid-JSON fingerprint. Separate provider reasoning
is still ignored; it cannot rescue invalid content.

The fingerprint contains fixed keys, closed enum values, numbers, booleans and
nulls only:

| Fields | Meaning |
| --- | --- |
| `byte_length`, `char_length`, `has_ascii`, `has_non_ascii`, `newline_count` | UTF-8 bytes, Python string characters, ASCII/non-ASCII presence and LF count; byte length is null for a literal unencodable surrogate |
| `leading_whitespace_bytes`, `trailing_whitespace_bytes` | Independent edge spans of JSON whitespace only: space, tab, CR and LF |
| `first_non_whitespace_class`, `last_non_whitespace_class` | `object`, `array`, `backtick`, `angle`, `quote`, `alpha`, `other`, `empty` or `unavailable`; closing delimiters share the opening delimiter's class |
| `starts_with_object`, `starts_with_array`, `starts_with_markdown_fence`, `contains_markdown_fence` | Structural observations; fences mean the exact three-backtick marker |
| `starts_with_think_tag`, `contains_think_tag` | Exact lowercase `<think>` or `</think>` markers, including a closing-only marker |
| `decoder_error_category`, `decoder_line`, `decoder_column`, `decoder_offset` | Closed diagnostic category, one-based line/column and zero-based character offset; no exception messages |
| `raw_decode_one_value`, `parsed_root_type`, `trailing_non_whitespace_bytes` | Whether a diagnostic decoder read one value starting at the first non-JSON-whitespace character, its JSON type, and remaining UTF-8 bytes excluding all JSON whitespace |
| `duplicate_key`, `nonfinite`, `invalid_unicode` | Observed duplicate keys, nonfinite constants/overflow and unencodable strings; observations are not certificates of absence after an incomplete decode |
| `analysis_limited` | True when content exceeds the 131,072-character examination cap; unexamined metadata is null/unavailable, category is `size_limit`, and no value was decoded |

Other diagnostic categories are `malformed_json`, `trailing_content`,
`duplicate_key`, `nonfinite`, `invalid_unicode`, `depth_limit`, `decoder_limit`
and `none`. JSON root types are `object`, `array`, `string`, `number`, `boolean`
and `null`. Custom numeric/Unicode/duplicate rejections have no invented decoder
location. Marker presence can also occur inside quoted strings: it is not proof
of a markdown or reasoning wrapper.

The separate diagnostic decoder never returns its parsed value, searches for a
JSON substring, strips wrappers, repairs content or changes acceptance. Its
observations cannot upgrade an outcome. No raw prefix/suffix, completion,
reasoning, dictionary keys, token strings, content hash or provider body is
recorded. Examination is bounded by the accepted response-byte ceiling in
characters; normally the gateway's stricter wire-byte bound has already applied.
The helper adds no dependency, configuration flag or request field.

The #31 offline comparison at accepted source `5e39e391` measured:

| Protocol component | P1 characters / UTF-8 bytes | P2 characters / UTF-8 bytes |
| --- | --- | --- |
| System instruction | 1,097 / 1,097 | 2,233 / 2,233 |
| Canonical runtime context | 1,464 / 1,464 | 5,792 / 5,792 |
| Embedded output schema | Absent | 2,889 / 2,889 |
| Complete system message | 2,562 / 2,562 | 8,026 / 8,026 |

P1 requests a flat `FactRequest` under `outcome`/`request`: metrics, start, end,
timezone and optional center ID, or a decline. P2 adds recipe ID/version, three
tagged request branches plus decline, and embeds the full schema. Compare nests
two amount-only FactRequests under `current`/`baseline`. Counting the response
root as depth one, P1 has two object levels; P2 Overview/Breakdown have two and
Compare has three (four container levels including its constant metrics array).
At that historical baseline, both used the same
gateway payload (`model`, `messages`, `temperature`, `max_tokens`, `stream`) and
strict parser, with no guided-JSON, response-format, reasoning or stop override.
These size differences do **not** establish the cause of #30's nine
`invalid_json` failures. No authoritative tokenizer was available in the pinned
environment; no token counts were estimated or dependencies added.

Local repository/service inspection did not establish the server chat template,
thinking mode, vLLM reasoning parser, LiteLLM reasoning routing, guided decoding
or stop configuration. Preserved successful P1 #13 client identities match the
unchanged P1 source/context, but contain no proof of those server settings.
They remain unknown, not assumed unchanged. #30's original responses were not
retained, so this diagnostic addition cannot retrospectively identify their
structure or demonstrate a live fix.

## Invalid-request closed reason (#72)

Only when parsed JSON fails the unchanged request-validation stage as
`invalid_request`, `evidence.invalid_request_reason` records which closed rule
rejected it. The failure code, stage, stopping classification, native
validators, prompt, canonical schema and Bedrock wire schema are unchanged; no
repair, second turn or provider-specific branch is added. The value is one of
the fixed names below or `null`, never a validator message, a key, a value or
any model text. In the shared P3 evidence projection a reason is accepted only
with the failure it names: `error_code` is `invalid_request`, `json_parse`
passed, `request_validation` failed and `kernel_execution` was not run;
anything else, including a missing stage record, fails closed. Historical
evidence without the field still reads with its original meaning.

| Reason | Observed structure |
| --- | --- |
| `root_shape` | Root is not an object, or the request root's key set, `outcome` or `recipe_version` differs from the contract |
| `unknown_recipe` | `recipe_id` is not one of the three admitted recipes |
| `request_fields` | The `request` object's top-level key set is not exactly the selected recipe's fields |
| `request_values` | The key set matched, then a native request validator rejected a value or nested object |
| `clarification_shape` | The clarify root or `clarification` object key set is wrong, or `kind` is not admitted |
| `choice_count` | `choices` is not a list of two to four items |
| `choice_shape` | A choice, `semantic_value` or typed value has the wrong key set or an unknown `type` |
| `choice_values` | A choice id, enumerated value, scope or embedded native request failed its validator |
| `choice_consistency` | Cross-choice rules failed: unique ids/values, value type equals `kind`, shared scope, required member, reversed comparison roles or one center period |
| `question_binding` | A clarification center code does not appear in the question |
| `export_drift` | Safe export changed the validated action, so it was not retained |

`request_fields` and `choice_count` are the two observations that separate the
hypotheses left open by the six unassessed `invalid_request` outcomes in the
JP Bedrock observed regression (#70): the compact Bedrock wire schema keeps
`minItems: 1` for `choices` because Bedrock supports only `minItems` 0 or 1,
while native validation requires two to four choices. Recording the reason does
not recover those six intended semantics; raw completions were intentionally
not retained, and no rerun follows from this field.

## Interpretation limits and offline validation

A wrong but well-typed recipe, swapped Compare roles, valid wrong center or k
executes unchanged. There is no gold lookup, fallback to P1, hidden repair,
partial-constraint extension or supported=true certificate. Schema validation
cannot prove that every natural-language requirement was retained. Future
evaluation must compare recipe, complete scope/roles, coverage, then values.
A numerically checked answer to the wrong question remains wrong.

Run the focused network-free suite using the verified pinned interpreter:

```bash
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_clarification test_presentation test_recipe_clarification \
  test_recipe_model test_json_diagnostics test_structured_output test_recipe_smoke -v
```

Tests combine fake HTTP with real disposable synthetic SQLite, multilingual
message-identity checks, strict rejection matrices, wrong-valid proposals,
native outcome propagation, privacy, deadline and import-isolation witnesses.
Protected P1 gateway/envelope/logging/runner tests remain separate unchanged
regressions. Mock declines do not establish Gemma's refusal behavior; translated
variants are not independent semantic families.

## Separately scoped runner and live gates

[P2.7 (#28)](recipe-smoke.md) implements the fixed evaluator panel
**E01 / E02 / E03 x zh-TW / en / ja: 9 inputs, 3 semantic families**, using this
recipe adapter and independent one-shot attempts. P3.1 changes the shared action
protocol as described above, not the panel or native expectations. Its candidate
manifests are test evidence only. Final accepted-commit preparation waits for
owner merge, and live execution still needs separate authorization. E10 remains
an injected operational control, never a model question. P1's historical runner
and pins remain unchanged; the runner does not claim P3 evaluation, resume,
synthesis or PostgreSQL capability.
