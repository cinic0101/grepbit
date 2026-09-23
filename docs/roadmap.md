# Roadmap and phase exits

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
P3.0 (#37 / PR #38) accepted the [evaluation contract](p3-evaluation-contract.md)
at `a4bad1a8742a97021502e71208bd7162c6b37c44`. P3.1 (#39 / PR #40) accepted
[bounded clarification](clarification-action.md) at
`e8c3a455bd4e09a266a772be599fe851d405df78`. P3.2 (#41 / PR #42), including
the independent evidence-expectation correction, is accepted at
`20abb5592262c77c98f9cabeaf7cf4854edb6fbe`. Its [offline evaluator](p3-evaluator.md)
provides ordered grading and family-weighted evidence, not fresh quality results.
P3.3 (#43) prepares [independent authoring and formal admission](p3-fresh-case-authoring.md)
with product/grader behavior frozen at that SHA. The owner-approved
[exposed projection](p3-evaluator.md#exposed-material-and-unresolved-admission)
is 9 provisional families / 15 inputs: P10 deferred, P11 preserved outside the
panel as an E02 regression, P12 not admitted. Original assets remain intact.
Fresh authoring is closed. The owner-approved allocation v2 is **14 families /
28 inputs**, retaining five fresh families plus the nine exposed labels; the
historical 24/44 validator remains protected as v1, not a quota to restore.
Versioned tooling support was separate from actual admission at this preparation
stage. The later P3.5 formal 31B run on the admitted 14-family / 28-input panel
completed at **25/28 inputs and 12/14 families**, with zero checked-wrong normal
answers, but failed promotion because mandatory decline and anchor families did
not all pass. P3.7's separately authorized selected 31B stability run completed
18/18 correct trials and 18/18 comparable pairs with zero semantic flips; it
did not repair the formal quality result. The P3.8 exit disposition therefore
kept 31B quality-blocked and directed candidate-first investigation, not P3 exit.
P3.10 admitted a pinned 12B deployment identity and observed one successful
compatibility call; one call did not establish quality. P3.11's separately
authorized 12B observed regression completed **20/28 inputs and 8/14 families**.
It recorded four new semantic regressions and four typed-output/request-contract
validation failures: those four returned HTTP 200 and parsed JSON, then failed
`request_validation` before native execution. The immutable comparison taxonomy
calls them `UNASSESSED_OPERATIONAL`; their intended semantics are unassessed.
P3.11 is not fresh quality or promotion evidence, and the 12B candidate was not
advanced. These observed runs do not authorize further live execution. P3-P5
remain open, including P3 grounding, resume and synthesis. P2 is not promoted
to `main`.
GitHub Issues own current status; this document owns phase meaning and exits.

| Phase | Deliverable | Question being tested | Exit |
| --- | --- | --- | --- |
| P0: trustworthy fixture | LearningOps sources, semantics, cases, oracles, small runner, portability and local-run policy | Do we know the expected meaning/result and can wrong computations be distinguished? | Rebuildable fixture; source identities; reviewed definitions/oracles; mutation/negative controls; unresolved acceptance choices explicit |
| P1: fact kernel | Fixed fact requests -> SQLite -> Fact Pack | Can the system calculate and disclose correctly without a planner? | Admitted deterministic cases pass; required constraints preserved; one small owner-run model integration smoke |
| P2: analysis PoC | Overview/Compare/Breakdown, multiple queries, derived facts and partial results | Is composition useful without expanding a language? | Common kernel; required/optional behavior passes; at least one live natural-language path per recipe; no case-specific operators/repairs for equivalent combinations |
| P3: natural-language evaluation | Grounding, clarification/resume, fact selection, synthesis | Does the model select the intended facts and satisfy the request? | Frozen answer/action panel and stability panel; explicit outcomes/costs; candidate thresholds below met or scope reconsidered |
| P4: MVP candidate | PostgreSQL adapter, native-type parity, snapshot/cancel, one bounded drill-down, one thin service entry | Does the supported boundary hold on PG and stop within budget? | Admitted parity/lifecycle cases pass; PG-only behavior tested, not inferred; budget and source limits enforced |
| P5: real-data pilot | Owner's fresh questions, safe feedback and original-source replay | Does it transfer and does a fix work outside the fixture? | Source-confirmed results with seen/unseen distinction; protected regressions and maintenance cost reported |

P1/P2 are deterministic-first, NOT LLM-free. Separate component tests isolate
calculation failures; small live integration checks reveal unusable model
interfaces early. P3 starts formal quality measurement, not first model contact.
Every live call remains an owner-authorized local run, including smoke tests.

## P2.0 admission before implementation

[Recipes v0.1](p2-recipes.md) defines Overview, Compare and Breakdown using
E01/E02/E03 and the E10 operational control. P2.1 implements **scalar Compare first**:
one controlled multi-scope snapshot and deterministic derived facts, without
waiting for grouped execution. Q11-Q13 justify one observed-group amount
primitive; Q10's catalog-complete zero members remain outside that admission.
P2.2 implements that [bounded primitive](grouped-amount.md), with explicit
observed/top-k coverage, fixed caps and on-demand dimension admission. It retains
P1's existing FK parent requirements without widening scalar query permissions.
Compare now has a narrow typed Python API, exact input-linked difference/growth,
and one shared private scalar transaction/budget path with P1. No Compare CLI,
model selection or live recipe run is included in #16.
P2.3 adds [private required/optional composition](p2-recipes.md#p23-private-requiredoptional-composition)
with one snapshot/global budget and explicit local gaps. Component timeout is
an injected operational control, not general timer mechanics.
P2.4 adds [public Overview](p2-recipes.md#p24-public-deterministic-overview):
exact code binding and fixed-month input validation in front of that composition,
with binding sharing the facts' snapshot and budget. P2.5 adds
[public Breakdown](p2-recipes.md#p25-public-deterministic-breakdown), requiring
course selection, an independently executed whole amount and two exact,
input-linked derivations. P2.6 adds
[one shared model recipe contract and adapter](recipe-model-integration.md):
strict native validation, fixed dispatch, native evidence and no hidden repair.
[P2.7](recipe-smoke.md) implements the fixed nine-input/three-family evaluator
panel without changing the adapter. Candidate manifests are not live manifests;
accepted-commit preparation and owner-authorized live execution follow separate
gates. E10 remains an injected operational control, not a model question.
Those offline slices alone do not establish the live part of P2 exit; the later
accepted #36 evidence supplies that part without extending the recipe boundary.

## Historical P0 delivery scope

Commit the English design, AGENTS/CLAUDE instructions, new fixture sources and
P0 checks. Do not add a runtime framework, model client, credentials, live CI,
remote runner, or automatic merge. Detailed semantic/oracle review remains an
explicit P0 exit; passing code checks does not perform that review.

Initial tracking: roadmap #1; fixture/semantics #2; cases/oracles #3;
runner/evidence/local handoff #4. Open later-phase work when its scope is concrete;
do not create one ticket for every speculative feature. Normal implementation
needs an issue + test + PR/commit, not a research report.

## Candidate P3 thresholds (ratify before a formal run)

The [accepted P3.0 contract](p3-evaluation-contract.md) specifies the behavior
matrix, exposure/provenance, conditional panel allocation, family-weighted
denominators, clarification policy and separate stability/resume/synthesis gates.
Historical R1 (#37 / #38) ratified the small-PoC consequence of the thresholds below:
8/8 fresh answer families and all four exposed answer controls, hence 12/12
answer families, without padding the panel to allow a failure. Allocation v2
under #43 instead requires all retained fresh answers 2/2, exposed answer 1/1,
clarify 3/3, decline 5/5 and anchors 3/3, on every mandatory variant, with zero
checked-wrong normal answers. It supports only the retained slice, not the old
eight-fresh-answer breadth. Its stability preselection is P02/zh-TW, P04/en,
R03/ja, P14/zh-TW, P17/ja and P18/en, three trials each; exact fresh input IDs
remain unresolved and no execution follows from preselection. Missing-year/
baseline/k clarification without grounded alternatives is deferred, not desired
decline gold; E06 remains unchanged. Acceptance of the R1 design is separate
from product implementation, case freeze and authorization of any live run.
The first recipe-only action/fact panel does not complete P3's clarification/
resume and synthesis promises. Full P3 exit also requires the explicit later
product-entry grounding/routing decision among scalar P1, recipe, clarify and
decline; a recipe refusal cannot erase an accepted P1 capability.

For the declared answerable panel: at least 90% complete-correct, and zero known
wrong answers presented as checked normal answers in that observed panel.
All designated mandatory clarification/denial controls must take an appropriate
branch. Report false clarification/refusal, partial output and operational failure
separately; refusal cannot manufacture a high success score. Thresholds are small
PoC promotion rules, NOT statistical guarantees about deployment error rates.

Freeze the included case IDs, budgets and preselected repeats before running.
Do not remove failures from the denominator, rerun until green or silently
change the oracle. If thresholds fail, fix, explicitly narrow the promise, or
stop the candidate approach. Preserve the failed run.

## Stopping and complexity rules

Before an investigation, state its hypothesis, bounded panel, attempt budget and
stop condition in the issue. Default to at most two candidate fixes before a
scope/design decision; this is a work-control default, not a two-commit limit.
New investigation authority may extend it explicitly. A rejected research idea
is not automatically an open product bug.

Track production files/lines touched, new operators/repairs, semantic/recipe
branches, human review effort, live attempts/costs and displaced behavior. Moving
exceptions from Python to config does not lower complexity by itself.
Future P3 fixes must include the contract's
[system-level impact review](p3-evaluation-contract.md#e-mandatory-system-level-impact-review-for-future-p3-prs)
in the PR: protected P1/P2 behavior, privacy/leakage, sizes/costs/latency,
complexity, P4/P5 implications and any changed product promise.

P0 fixture tests and P1 unit tests do not measure language understanding. A
synthetic fix is not source confirmation. A correct answer under one backend
is not portability. Previously exposed cases are not a holdout. Keep these labels
in every closeout so phase exits do not become research theater.
