# Eight-input reason diagnostic (#74)

Status: owner-approved diagnostic contract and offline implementation. The
owner accepted this path and granted its Bedrock calls in the local
conversation on 2026-09-24; the tool still reaches a live run only after PR
review and merge, from clean accepted `dev`.

## Purpose and evidence class

The JP Bedrock observed regression (#70) archived six `invalid_request`
outcomes and two checked-wrong outcomes without the violated rule or the
output structure. The [#72 postmortem](p3-shared-observed-regression.md#observed-run-follow-up-2026-09-24)
added a closed `invalid_request_reason` for future runs, but the archived
report cannot be reinterpreted. This diagnostic re-observes exactly those eight
inputs once, with the reason code, a closed structural fingerprint of the
parsed output and a private raw-completion capture, so the failures can be
attributed to model behavior, the request/clarification contract or case
wording.

Evidence class is `diagnostic_regression_data`, `promotion_eligible=false`.
The eight inputs have informed a fix; they are regression data, never fresh
evaluation. The result does not change the archived #70 score, does not admit
a candidate and does not authorize a rerun. The frozen grader still runs on
each input for orientation only; its outcome is not a panel result.

## Fixed panel, provider and bounds

| Item | Pinned value |
| --- | --- |
| Inputs | `FA04_A04_compare_year_on_baseline_nonadjacent.en`, `FA09_C02_comparison_roles_symmetric.r2.zh-TW`, `FA09_C02_comparison_roles_symmetric.r2.en`, `FA09_C02_comparison_roles_symmetric.r2.ja`, `E02_compare.en`, `P15_center.en`, `P16_metric_meaning.zh-TW`, `P22_center_compare.ja`, in this order |
| Question pins | Each question's SHA-256 is compared with the archived #70 report row before any send |
| Assets | The frozen intake, cases, oracles and panel pinned by the observed runner (`PINS`), loaded through the same admission path |
| Provider | Bedrock Converse, `jp.anthropic.claude-sonnet-4-6`, calling Region `ap-northeast-1`, Japan-only route, TLS verification |
| Runtime | Unchanged prompt, context, canonical schema and compact wire schema; baseline semantic, effective runtime, canonical and wire identities must equal the observed runner's pins |
| Attempts | At most 8 runtime invocations and 8 client HTTP attempts, one per input; concurrency 1 |
| Time | 300 seconds per call; 2,520 seconds for the run (8 x 300 + 120) |
| Tokens | 2,048 output tokens per call (client fixed); existing request/response size limits |
| Gateway policy | Retries, fallback and cache attested `disabled`; resend, repair, continuation and resume are not implemented |
| Data | Synthetic LearningOps DB (`DB_SHA256` of the observed runner); no gold, oracle or reference SQL in model context |

## Public report and private capture

The public `report.json` records identities, counters, settings, stop policy
and one row per input: case metadata, the frozen grader outcome, safe runtime
evidence through the shared P3 projection (including `invalid_request_reason`),
and a closed structural fingerprint of the parsed completion:

| Field | Meaning |
| --- | --- |
| `parsed` | Whether strict JSON parsing succeeded |
| `root_type` | `object`, `array`, `string`, `number`, `boolean` or `null` |
| `root_known_keys`, `root_unknown_key_count` | Known contract keys present at the root and how many other keys appeared |
| `outcome`, `recipe_id` | The enum value, `other` or `missing`; never the text of an unknown value |
| `request_known_keys`, `request_unknown_key_count` | Same observation for the `request` object |
| `scope_known_keys`, `scope_unknown_key_count` | Same observation for each Compare scope object, keyed by role |
| `kind`, `choice_count`, `choice_key_sets_valid`, `semantic_value_types`, `semantic_value_unknown_key_count` | Clarification structure: enum-or-other kind, number of choices, whether every choice has exactly `id` and `semantic_value`, each value's enum-or-other type and how many unknown keys appeared |

No key name outside the contract, no value and no text enters the fingerprint
or the report. The raw completion of each input is written once to a sibling
`<output>-private/` directory (mode 0700, files 0600) and referenced from the
public report only by SHA-256 and byte length. That directory is git-ignored,
never printed, never posted and never sent to another service. The public
report reader must not need it.

## Admission and stop rules

Before credential access the tool verifies: clean accepted `dev` at the exact
commit, the pinned assets and DB, the eight question pins against the archived
#70 report, the observed runner's runtime and schema identities, the Bedrock
provider/Region/profile/transport, the attested gateway policy and exclusive
creation of both output directories. Any drift stops before any send. Two
consecutive network failures or timeouts stop the run. A stopped or interrupted
run is preserved; it is not rerun to obtain a cleaner result. Each input is one
attempt; there is no retry, fallback, resend or second run.

## What this is not

Not fresh quality, stability or promotion evidence; not a candidate admission;
not a prompt, schema, oracle or threshold change; not a reinterpretation of the
archived #70 report; not permission for any other model call. The E02 English
case wording review (#75) is separate and independent of this tool.
