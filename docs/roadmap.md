# Roadmap and phase exits

Phase baseline: 2026-09-18; current status follows #13/#14. Work is on `dev`;
promotion to `main` requires owner review. P0 and P1 are accepted at
`6d6be30bed321806e0a2ef90fec53a1fc1118373`. The first smoke (#10) failed
envelope validation on all 12 inputs and remains unchanged. After P1.3a
(#11 / PR #12), the separately authorized second smoke (#13) passed 12/12
inputs, with 4/4 families all-three-correct. This satisfies the bounded P1 exit,
not P3 generalization, PostgreSQL parity or real-data transfer.
P2.0 (#14) is a design/admission checkpoint; no P2-P5 runtime delivery is claimed.
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
E01/E02/E03 and the E10 operational control. It proposes **scalar Compare first**:
one controlled multi-scope snapshot and deterministic derived facts, without
waiting for grouped execution. Q11-Q13 justify one observed-group amount
primitive; Q10's catalog-complete zero members remain outside that admission.
Required/optional composition, the remaining recipes, model instantiation and
separately authorized recipe live paths follow. Neither the design checkpoint
nor Compare alone completes the P2 exit above.

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

P0 fixture tests and P1 unit tests do not measure language understanding. A
synthetic fix is not source confirmation. A correct answer under one backend
is not portability. Previously exposed cases are not a holdout. Keep these labels
in every closeout so phase exits do not become research theater.
