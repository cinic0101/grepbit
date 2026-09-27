# Compare retest after the serving configuration repair

Owner decision in chat on 2026-09-27: "cool 我們開始吧" ("Cool, let's start"). The approved sequence is one three-input run, then one full 54-input dev
run only if all three inputs complete, produce valid JSON, and pass their
existing expected results. This continues goal #79 and the #87 dev grant.
Route retry/fallback/cache attestation must be renewed for the changed profile
before any live send. Git closeout to dev is already authorized in chat.

## Accepted scope and ruler checkpoint

Register `p3-dev-compare-retest-v1` using exact copies of the existing exposed
`dev-A3.en`, `dev-C2.zh-TW`, `dev-C2.en` case objects and their two existing oracle
objects, in that order. The loader requires case/oracle files to contain exactly
the selected cases/oracles. This is a projection, with no edits to question text,
answers, metadata, acceptance thresholds, original files, or historical reports.
A subset family result covers only selected variants, not the full family.

Keep candidate `p3-31b-instruction-v4`, model alias, prompt/schema, and the
existing route ID. Add a SHA-256 reference to a versioned serving witness in the
route's existing `note` field (already copied and compared in every packet).
No runner/registry format change or new route identity is needed. Keeping the
route ID also prevents resetting its previously consumed holdout freshness.
The witness records the observed image, configuration and adapter hashes,
installed versions, infra commit, and xgrammar/disable_any_whitespace settings.
This is a pinned observation, not automatic verification of remote state.

Commit these rulers before adding the registry/assets. Intended initial failures
are the absent panel and profile binding. The existing grant's within-scope
contract workflow permits this checkpoint; the user approved this run sequence.
Validate exact projection equality and normal runner time/token limits, run the
full offline suite once, obtain local risk review and fresh GitHub diff review,
and merge to dev before preparing live packets.

## Bounded execution

- Same local LiteLLM 31B route; synthetic LearningOps only; one run in flight.
- First run: at most 3 calls, 60 seconds and 2,048 output tokens per call;
  runner panel bound 300 seconds. No retries, fallback, cache, repair or resume.
- All three must complete and score correct. Otherwise stop before the54.
  Standard runner anomaly/timeout stops may end the three-input run earlier.
- If eligible, prepare a new packet and slot for `p3-dev-matrix-compare-first-v1`:
  at most 54 calls, 60 seconds/call, 2,048 tokens/call, 3,360 seconds/panel.
  This full run includes the three inputs again; maximum total57 calls.
- Preserve all evidence and record each cited run in the append-only index.
  Bind each envelope to the renewed grant comment and a distinct exclusive slot.
- Report operational results, latency and semantic correctness separately.
  Dev evidence cannot establish freshness, stability, promotion or causality.

The prior 90-second diagnostic grants are consumed. This run uses normal limits
and does not authorize another prompt candidate or changes to gold/authority text.
