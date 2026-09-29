# Bound count meanings candidate (#79)

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
