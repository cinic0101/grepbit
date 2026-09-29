# Bound count meanings candidate (#79)

Subsequent [regression and denominator audit](v7-regression-audit.md): 27/28
frozen regression and 17/18 holdout A regression; v7 has not converged. The
historical dev observation below remains valid within its stated panel scope.

## Authorized scope and evidence

Owner decision given in chat on 2026-09-29 Asia/Taipei: "授權，依此方案完成並測試一次"
("Authorized; complete this plan and test it once"), recorded in
[#79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5881751825).
This explicitly approves the third targeted D8 fix and the exact proposal in
[comment5881729539](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5881729539).
Prior v3 and v6 instruction repairs left D8.zh-TW as false count-basis clarification;
v5 also observed that outcome. English/Japanese D8 passed in those observations.
v6 fixed C1's excess alternatives but did not fix D8.zh-TW. Its completed panel
scored 53/54 under the revised C4 identity; original C4 broad-term questions
remain outside this panel and are not resolved by these results.

Hypothesis: make count clarification admission explicit next to the count-meaning
vocabulary in runtime context. The top-level v6 instruction already states the
required-output priority. The current context lists count meanings and their
availability but does not locally distinguish bound attendance requirements from
unresolved alternatives. This is a testable presentation hypothesis, not an
inference about internal reasoning. D8's 7.596632-second valid typed response was
not a timeout or format failure.

## Exact specification and ruler checkpoint

Register `p3-31b-count-context-v7`, ancestor `p3-31b-instruction-v6`.
Change only context version to `learningops-recipe-context-v3` and
`runtime_context().clarification.count_basis` to this exact text:

> Use count_basis only when the question leaves mutually exclusive count meanings unresolved. First preserve any specified event or population: a count of actual attendance events is attendance_visits, even when expressed using a generic people/count noun. If the question requires attendance_visits, distinct_people or known_booking_accounts, decline the whole request, including when it also requires a supported Overview. A question that explicitly leaves the count basis undecided instead admits only its stated alternatives. Use one explicit Overview scope. The available count meanings are booked_seats, known_booking_accounts, attendance_visits and distinct_people. Seats are booked line quantities; accounts are distinct non-null booking-account IDs, excluding anonymous bookings; visits are attendance events, not distinct humans. Only booked_seats is executable through this recipe.

Preserve all other context fields and every v6 instruction byte, including its
version and Compare rules. Schema, native execution, P1, catalog, output limits,
serving, case/oracle/panel/grader assets and historical candidates stay unchanged.
These are existing recipe-entry semantics; known accounts remain a separate P1
capability and no broader product-routing or attendance implementation is added.
No case-specific routing, Chinese phrase matching, new examples or extra calls.

Expected canonical context SHA256:
`d9edaf450dd088cf5975704d6504d1019a437fbf51c91502fd9fc023d6e027d7`.
Unchanged instruction SHA256:
`fb32abe3adc5018ed637dae4c7a47c3146f1c726b9b8f80f8820a1ec738390d4`.

Commit this specification and the archived identity ruler before implementation.
The ruler initially fails at the missing candidate assertion, then passes after
registration. This meaningful identity/scope checkpoint does not simulate model
obedience. The owner has approved the exact plan; root accepts this checkpoint
within that authority. Recovery after a failed observation is to retain the
candidate and evidence and stop, not rewrite history or automatically iterate.

## Verification and one observation

Focused checks while editing and one full offline suite at closeout, plus fixture
check, local risk review and fresh-context actual GitHub diff review. Merge to dev
before model execution. Offline mock transport already checked all 54 questions:
maximum request 27,924 bytes, below 32,768; this is feasibility only.

Execute `p3-dev-matrix-compare-first-v2` once, against the same-panel v6 report
`.artifacts/clarification-boundaries-v6-20260928/run/report.json` (SHA256
`f9dae48e0d54026a60c93a311df48b5097aa7b5029362ca5e3c8b0a8deb39237`).
Keep its order and 54 cases/oracles exactly. Report D8 three-language results,
C1 clarification controls, D4 mixed-requirement controls, Compare and all outcomes.
The same panel permits the runner's baseline comparison; no fresh or causal claim.

Bind one new packet and output slot to the approval above, standing dev grant
[#87comment5852775731](https://github.com/cinic0101/grepbit/issues/87#issuecomment-5852775731)
and unchanged-route attestation
[#79comment5857155780](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5857155780).
Same LiteLLM 31B and serving profile; synthetic LearningOps only; opaque existing
local credentials. Maximum 54 client calls, 60 seconds and 2,048 output tokens per
call, 3,360 seconds per panel; one run in flight, 1,000/day Asia/Taipei ceiling.
No retries/fallback/cache/repair/resume/raw completion or reasoning retention.
Stop on existing runner operational limits, source/route/privacy/credential drift
or budget exhaustion. Finish this observation and stop; no fourth targeted fix or
rerun is authorized here. This remains exposed development evidence, not stability,
fresh generalization, original-C4 repair or promotion.

## Observed result (2026-09-29 Asia/Taipei)

[PR #108](https://github.com/cinic0101/grepbit/pull/108) merged as
`b33288141089fa9454e59979fc8b1fb7c59a1e36` after focused 18/18, the complete
1,243-test offline gate, fixture 27/27 and local/fresh GitHub reviews without
actionable findings. Read-only preflight matched the registered serving
image/configuration and healthy service. No serving change was made.

The single authorized 54-input run completed from that merged commit. Offline
archive readback passed. All 54 inputs and 18 families passed: 18 complete
answers, 12 correct clarifications and 24 correct declines. Exactly 54 observed
client calls; valid JSON throughout, no timeout or operational failure. Upstream
inference attempts remain unknown. Run duration was 217.524375 seconds; per-call
latency median 3.317570 seconds, range 0.361041–13.996096 seconds.

Same-panel comparison against v6: 1 `FIXED_KNOWN_FAILURE` (D8.zh-TW),
53 `UNCHANGED_CORRECT`, 0 `NEW_REGRESSION`, 0 `UNCHANGED_FAILURE`,
0 `OUTCOME_CHANGED_OTHER`, 0 `UNASSESSED_OPERATIONAL`. Only D8.zh-TW changed
action/outcome, from false count-basis clarification to correct decline.

| Controls | Observed result |
| --- | --- |
| D8 explicit attendance requirement, zh-TW/en/ja | 3/3 correct declines |
| C1 genuinely undecided count basis, zh-TW/en/ja | 3/3 correct clarifications |
| D4 overview plus unsupported required output, zh-TW/en/ja | 3/3 correct declines |
| A3/A4/C2 Compare controls | 9/9 |
| Revised C4 v2 explicit amount alternatives | 3/3 correct clarifications |

D8.zh-TW returned in 0.386585 seconds with 8 completion tokens; en in 0.386483,
ja in 0.406286, also 8 completion tokens each. All three recorded the expected
`model_declined` action. The adapter represents this deliberate branch with
`request_validation: failed` and `kernel_execution: not_run`; it is not a
malformed-output or transport failure. No native attendance query was added or
executed. Raw output/reasoning was not retained, so internal cause is unknown.

This observation supports the targeted repair within this exposed panel and
shows no newly failing case in that run. It does not establish stability, fresh
generalization, causal isolation or promotion. The 51 cases unchanged from the
old v1 panel now score 51/51; the other three are C4 v2. Original broad-term C4
questions remain outside this run and unresolved; C4 v2 passes cannot be relabeled
as fixes to those questions. No oracle/case text or scoring threshold changed.
The authorized sequence ends here: no rerun, further candidate, frozen regression
or golden/holdout consumption was started.

Evidence is appended to `evals/runs/index.jsonl` and generated `STATE.md`:

- Run ID: `p3-dev-matrix-compare-first-v2--litellm-gemma-4-31b--p3-31b-count-context-v7--5296619ac53c`.
- Slot: `.artifacts/d8-count-context-v7-20260929/run`.
- Report SHA256: `920e2e9e1c76a3c65290c236fb0386deb1187375efa2775593f4e117bf427d25`.
- Packet SHA256: `c932444afb8d040a2691952da0f933d45538a26ffd2f038772c4c19b37ee0b61`.
- Authorization reference: [owner approval](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5881751825), linked to the standing grant and route attestation above.
- Claim: `development_observation`, promotion-ineligible. Local readback and
  analysis summaries remain beside the immutable run archive.
