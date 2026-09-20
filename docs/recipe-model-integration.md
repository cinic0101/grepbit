# P2.6: bounded recipe interpretation

Issue #26 / PR #27 accepted one model-facing route over the native
[Overview, Compare and Breakdown APIs](p2-recipes.md). Offline fake-transport
checks are not live model validation or the P2 exit. This is separate from the
unchanged [P1 scalar contract](model-integration.md).

```text
question + one shared English instruction and all three recipe meanings
  -> one GatewayClient.complete call
  -> existing provider-envelope normalization
  -> strict JSON and selected native request validator
  -> exactly one existing public deterministic recipe API
  -> original native pack + sanitized interpretation evidence
```

The explicit import is `grepbit.recipe_model`. Ordinary `import grepbit` and
deterministic recipe calls do not import this module, gateway configuration or
network libraries. There is no new CLI, runner, discovery call or configuration.

## Closed output contract

`recipe-request-json-v1` admits exactly these alternatives:

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

The other complete branch is:

```json
{"outcome":"declined"}
```

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
arithmetic and independent whole-scope denominator. The model must decline
missing years, periods, baseline or k, ambiguity and unsupported requirements.
A stated year shared by two named Compare months can apply to both. No clock or
`AS_OF` value supplies an absent year. Profit, targets, annual aggregation and
unrelated multi-question requests must not be reduced to convenient subsets.

No evaluator assets, sibling translations, case IDs, expected parameters or
values, source rows, reference SQL, fixture code-to-ID maps, previous completions,
gateway addresses or credentials enter the system context. Context construction
does not access SQLite. Documentation is not loaded as runtime context.

`context_identity()` and each result's `evidence["context_identity"]` identify:

- `learningops-recipe-context-v1`
- `recipe-request-json-v1`
- `recipe-selection-instruction-v1`
- SHA-256 of the canonical context, canonical output schema, English instruction,
  complete submitted system message and reviewed catalog.

The adapter hashes the context it actually submits, not a question-specific
expected contract. P1's system instruction, context, output contract, hashes,
partial constraints and stopping classifications remain unchanged.

## API, native results and failure evidence

```python
from grepbit.recipe_model import interpret_recipe_and_execute

# client is an explicitly constructed GatewayClient; use a fake transport offline.
result = await interpret_recipe_and_execute(question, database, client)
```

Live construction/execution requires separate owner authorization under
[local execution policy](local-execution.md); this signature is not authorization.
No actual credentials are needed or read by the offline suite.

`RecipeInterpretation` holds `proposal`, `analysis_pack`, `error`, `evidence`.
`RecipeProposal` holds the validated recipe ID/version and original typed request.
Both wrappers are frozen and repr-safe. `analysis_pack` is the actual
`OverviewAnalysisPack`, `CompareAnalysisPack` or `BreakdownAnalysisPack`, not a new
editable universal pack. Its request object, IDs, scope, snapshot, slots,
provenance, limitations and Fraction serialization are preserved.

Only native typed requests reach a fixed three-way dispatch. No database
connection, profiling, admission or lookup occurs before completion and typed
validation; no model call occurs inside a native transaction. The outer deadline
is positive and at most 60 seconds. Prompt preparation reduces the completion
allowance; the native database timeout is `min(2 seconds, remaining total time)`.
Time is checked before and after execution and after evidence export. A late
result is discarded, not returned as a successful pack.

The adapter reuses P1's envelope normalization, usage parsing, bounded failure
fingerprints, strict JSON and the existing GatewayClient/safe_export. It does not
copy those privacy-sensitive parsers or refactor P1 into a general orchestration
framework. R1 logging protection, ignored separate reasoning, provider extension
compatibility, redirect/proxy/TLS controls and byte caps stay in the same code.
The request still uses `gemma-4-31b`, temperature 0, stream false, 2048 output
tokens and zero client retries. No SDK, response_format, tool or reasoning flag
is added. Upstream inference work is not inferred from client attempts.

Evidence records P1-style stages, model/usage/finish metadata, attempts, elapsed
time, identities, validated proposal, sanitized native serialization, pack
status and fixed errors. Missing model/usage stays unknown. An unapproved model
is rejected; the new route does not export its arbitrary alias, retaining null
`returned_model`, `unexpected_model` and the bounded envelope fingerprint.
Returned error objects contain fixed codes without retained payload tracebacks.
Use `evidence` for reporting: native request/pack objects are not general-purpose
redacted logs. `safe_export` protects configured secrets/addresses; it is not a
general detector of private data. This route remains synthetic-data-only.

| Outcome | Evidence meaning |
| --- | --- |
| Declined | One attempt, `model_declined`, no native execution; necessary refusal is not established |
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
Both use the same
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

## Interpretation limits and offline validation

A wrong but well-typed recipe, swapped Compare roles, valid wrong center or k
executes unchanged. There is no gold lookup, fallback to P1, hidden repair,
partial-constraint extension or supported=true certificate. Schema validation
cannot prove that every natural-language requirement was retained. Future
evaluation must compare recipe, complete scope/roles, coverage, then values.
A numerically checked answer to the wrong question remains wrong.

Run the focused network-free suite using the verified pinned interpreter:

```bash
PYTHONPATH=tests .venv/bin/python -m unittest test_recipe_model test_json_diagnostics -v
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
unchanged adapter/context and independent one-shot attempts. Its candidate
manifests are test evidence only. Final accepted-commit preparation waits for
owner merge, and live execution still needs separate authorization. E10 remains
an injected operational control, never a model question. P1's historical runner
and pins remain unchanged; no P3, synthesis or PostgreSQL capability is implied.
