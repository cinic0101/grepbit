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

## Observed result (2026-09-27)

The owner renewed the route attestation in chat: "確認，三者全部停用"
("Confirmed; all three are disabled"), recorded with the existing grant in
[#79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857155780).
One run executed from merged dev `83bf679d253b0b471d5ea598a66b1b06bb7307a9`:

| Input | Client elapsed seconds | Output tokens | JSON | Existing expected-result outcome |
| --- | ---: | ---: | --- | --- |
| `dev-A3.en` | 15.681300 | 431 | passed | false clarification |
| `dev-C2.zh-TW` | 12.835665 | 430 | passed | correct clarification |
| `dev-C2.en` | 13.154938 | 430 | passed | correct clarification |

All three completed with HTTP200, valid JSON and valid typed requests. No timeout,
operational failure or checked-wrong answer occurred. Semantic score is **2/3**;
1/2 families passed only across the selected variants, not full multilingual
families. All three returned `clarify` with kind `comparison_roles` and two
choices. Therefore the three-pass gate failed and **the54-input run was not
prepared, bound or executed**. No rerun or candidate change followed.

A3.en explicitly compares March2026 against February; its accepted expectation
is an answer with March as current and February as baseline. The current shared
instruction already says to preserve roles bound by question wording. C2's two
inputs leave comparison orientation open and correctly require clarification.
The recorded failure is therefore unnecessary clarification on the bound-role
input, not a transport/JSON failure. No raw completion or reasoning was retained;
this evidence does not establish why the model chose that action.

This single exposed run shows the previous timeouts were not reproduced under
the new serving profile. It does not prove causality, permanent timeout repair,
answer-path correctness, broad dev quality, stability or fresh generalization.
In particular all three chose clarification, so successful Compare answer
execution remains unverified in this retest. The next decision is a bounded
investigation of A3.en's false clarification, with existing case/oracle/prompt
identities preserved; further candidate repair or live execution is outside
this completed sequence.

Evidence: run `p3-dev-compare-retest-v1--litellm-gemma-4-31b--p3-31b-instruction-v4--bae493f1fa2f`,
slot `.artifacts/compare-serving-retest-20260927/three/run`, report SHA256
`ffed38cff258f497193609300dd2cc19140c2c84e93feb409bca8bb55a7c5793`.
The append-only index records three client calls; upstream inference attempts
remain unknown. Historical reports and expectations remain unchanged.
