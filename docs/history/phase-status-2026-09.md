# Phase status before consolidation

Historical snapshot of the roadmap opening before #87 step 5.
For current work, read [STATE.md](../../STATE.md) and [the roadmap](../roadmap.md).

Phase baseline: 2026-09-18; current status below includes P3.11. Work is on `dev`;
promotion to `main` requires owner review. P0 and P1 are accepted at
`6d6be30bed321806e0a2ef90fec53a1fc1118373`. The first smoke (#10) failed
envelope validation on all 12 inputs and remains unchanged. After P1.3a
(#11 / PR #12), the separately authorized second smoke (#13) passed 12/12
inputs, with 4/4 families all-three-correct. This satisfies the bounded P1 exit,
not P3 generalization, PostgreSQL parity or real-data transfer.
P2.0 (#14 / PR #15) and offline P2.1 Compare (#16 / PR #17) are accepted on dev.
P2.2 (#18 / PR #19) accepted one observed grouped-amount primitive. P2.3
(#20 / PR #21) accepted private fixed required/optional composition and injected
local-failure semantics. P2.4 (#22 / PR #23) accepted public deterministic
Overview using that same composition. P2.5 (#24 / PR #25) accepted deterministic
Breakdown with an independent denominator and exact selected subtotal/share.
P2.6 (#26 / PR #27) accepted bounded one-shot recipe selection/instantiation.
P2.7 (#28 / PR #29) accepted the fixed evaluator runner and its separate
accepted-commit preparation gate. Historical #30 failed strict JSON on all nine
inputs. After diagnostics and P2.11 structured-output wiring (#34 / PR #35),
the separately authorized #36 panel passed 9/9 inputs across the three frozen
recipe families and three languages on accepted dev
`f21c914915f34656c1e8c0069c28afadb5bbc7ae`. The owner accepted the P2 exit in
[the roadmap handoff](https://github.com/cinic0101/grepbit/issues/1#issuecomment-5754274130).
That is exposed regression evidence, not generalization or broad NL quality.
P3.0 (#37 / PR #38) accepted the [evaluation contract](../p3-evaluation-contract.md)
at `a4bad1a8742a97021502e71208bd7162c6b37c44`. P3.1 (#39 / PR #40) accepted
[bounded clarification](../clarification-action.md) at
`e8c3a455bd4e09a266a772be599fe851d405df78`. P3.2 (#41 / PR #42), including
the independent evidence-expectation correction, is accepted at
`20abb5592262c77c98f9cabeaf7cf4854edb6fbe`. Its [offline evaluator](../p3-evaluator.md)
provides ordered grading and family-weighted evidence, not fresh quality results.
P3.3 (#43) prepares [independent authoring and formal admission](../p3-fresh-case-authoring.md)
with product/grader behavior frozen at that SHA. The owner-approved
[exposed projection](../p3-evaluator.md#exposed-material-and-unresolved-admission)
is 9 provisional families / 15 inputs: P10 deferred, P11 preserved outside the
panel as an E02 regression, P12 not admitted. Original assets remain intact.
Fresh authoring is closed. The owner-approved allocation v2 is **14 families /
28 inputs**, retaining five fresh families plus the nine exposed labels; the
historical 24/44 validator remains protected as v1, not a quota to restore.
Versioned tooling support was separate from actual admission at this preparation
stage. The later P3.5 formal 31B run on the admitted 14-family / 28-input panel
completed all 28 inputs: **25/28 correct and 12/14 families passed**, with zero
checked-wrong normal answers, but failed promotion because mandatory decline and
anchor families did not all pass. P3.7's separately authorized selected 31B
stability run completed 18/18 correct trials and 18/18 comparable pairs with
zero semantic flips; it did not repair the formal quality result. P3.8 (#54)
kept 31B quality-blocked and directed candidate-first investigation, not P3 exit.
P3.9 (#55) admitted the pinned 12B deployment identity. P3.10 (#56) observed one
successful compatibility call; one call did not establish quality. P3.11's
separately authorized 12B observed regression completed all 28 inputs:
**20/28 correct and 8/14 families correct**. It recorded four new semantic
regressions and four typed-output/request-contract validation failures: those
four returned HTTP 200 and parsed JSON, then failed
`request_validation` before native execution. The immutable comparison taxonomy
calls them `UNASSESSED_OPERATIONAL`; their intended semantics are unassessed.
P3.11 is not fresh quality or promotion evidence, and the 12B candidate was not
advanced. These observed runs do not authorize further live execution. P3-P5
remain open, including P3 grounding, resume and synthesis. P2 is not promoted
to `main`.
GitHub Issues own current status; this document owns phase meaning and exits.
