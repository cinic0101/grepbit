# Compare completion diagnostic v2

The owner approved one v2 run on 2026-09-27: [grant on #79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855499028), following the [reviewed proposal](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855468861). The owner's words were “同意，依此方案完成並執行一次” (“Agreed; complete it according to this plan and execute it once.”). This version adds structural content counts to diagnose `dev-C2.en`; it creates no quality or semantic acceptance claim.

## Closed identity and bounds

`tools/evaluate.py --completion-diagnostic-v2` is the sole entry. It has the v1 modes `--describe`, `--prepare`, `--bind-authorization`, `--live`, and `--report`, with no override for cases, model, timeout, output cap, destination, or raw capture. `--describe` returns exactly:

```json
{"version":"compare-completion-diagnostic-v2","case_ids":["dev-C2.en"],"candidate_id":"p3-31b-instruction-v3","route_id":"litellm-gemma-4-31b","canonical_call_timeout_seconds":60,"diagnostic_call_timeout_seconds":90,"run_timeout_seconds":180,"max_calls":1,"max_output_tokens":2048,"raw_text_persisted":false,"promotion_eligible":false}
```

The canonical packet is rebuilt from registered `p3-31b-instruction-v3`, original `p3-dev-matrix-v1`, and `litellm-gemma-4-31b`. Select only `dev-C2.en`. Pin its exact question and serialized request hashes, the canonical packet, full accepted `dev` source identity, and all code used by the diagnostic. Keep the model alias, prompt, runtime context, JSON schema, temperature zero, non-streaming request, 2,048-token output cap, and 4,096/32,768/131,072-byte input/request/response caps byte-for-byte as in v1. The route remains canonically 60 seconds; only the admitted diagnostic client uses 90 seconds. No case IDs, evaluator metadata, reference SQL, or oracle data go on the wire. No native recipe execution or scoring occurs.

The v2 grant URL is exactly `https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855499028`. Its deterministic exclusive slot is `.artifacts/compare-completion-v2-2f40da8046841da2297d` (the first 20 hex characters of SHA-256 of the UTF-8 grant URL). One packet and authorization consume this one slot before credential reads. No replay, path override, symlink, overwrite, retry, fallback, cache, or second run is admitted. One call has a 90-second transport deadline; the whole run has a 180-second cooperative deadline including publication preparation. Preserve reserved and possible in-flight evidence on interruption. Unknown upstream inference attempts remain unknown. Stop on identity, route, credential, privacy, persistence, or budget anomaly. Report `diagnostic_observation`, `promotion_eligible=false`, and no normal run-index entry.

## Versioned observation fields

V2 retains the v1 allowlisted response fields and adds exactly five nullable numeric fields to each successful observation:

| Field | Meaning |
| --- | --- |
| `json_whitespace_char_count` | Number of Unicode code points equal to JSON whitespace: U+0020 space, U+0009 tab, U+000A LF, or U+000D CR. |
| `non_whitespace_char_count` | Number of other Unicode code points in the content string. |
| `longest_json_whitespace_run` | Maximum consecutive code points in that four-character whitespace set. |
| `max_repeated_32_char_whitespace_block_count` | Maximum repeated, non-overlapping 32-code-point block count among blocks containing only JSON whitespace. |
| `max_repeated_32_char_nonwhitespace_block_count` | The same maximum among blocks containing at least one non-whitespace code point. |

For each exact 32-code-point window, scan left to right. Count an occurrence of an identical block only if its start is at least 32 code points after the prior counted occurrence of that block. The maximum for a class is zero when no block in that class repeats non-overlappingly. The retained v1 `max_repeated_32_char_block_count` is the maximum of the two v2 class maxima. A present empty content string produces zero for all five new fields. If content is absent/null, all five are null and the v1 JSON parse state is `absent`; reasoning-only output does not turn content counts into zero. `content_bytes` continues to count UTF-8 bytes; the new counts use Unicode code points. Malformed JSON content is still counted. The reader validates exact key sets and numeric bounds, whitespace plus non-whitespace totals against the content byte bound, longest run against whitespace count, repetition bounds, and the total-versus-class maximum relationship. No characters, fragments, repeated blocks, body hashes, raw content, or reasoning leave memory.

## Compatibility and validation checkpoint

The implementation uses an explicit immutable diagnostic profile through one shared runner and its validators. Default v1 calls and CLI remain v1, with the original grant, three cases, 390-second deadline, deterministic slot, exact source-pin shape, and historical archive reader unchanged. The v2 packet, authorization, report, slot, and observation key set are versioned; v1/v2 cross-profile packet, grant, case, slot, and report substitution fails closed. The v2 source identity pins every touched diagnostic and dispatcher source file without changing v1 archived pin requirements.

Commit this document and a failing `--completion-diagnostic-v2 --describe` ruler before production changes. The pre-implementation failure must be the unsupported entry's status assertion, not an import, setup, or timeout error. Then add focused offline fake-transport tests for byte-identical wire, privacy canaries, mixed JSON whitespace, Unicode, malformed JSON, absent content, cross-field tampering, profile isolation, replay, and deadline/attempt accounting. Run the full offline gate once at root closeout. Live execution requires the merged accepted `dev` commit and the recorded one-run grant; one observation cannot establish a causal model explanation or candidate acceptance. Preserve v1 and historical evidence throughout.
