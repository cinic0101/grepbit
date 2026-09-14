# Semantic bottleneck diagnosis: information, wording, gate and oracle

2026-09-14, baseline `7444676`, production prompt `plan-classify-json-v15`.
Plan and delegated checkpoint decisions:
[`semantic-bottleneck-20260914.md`](../plan/semantic-bottleneck-20260914.md).
Durable counts/hashes: [`semantic-bottleneck-01.json`](../../evidence/semantic-bottleneck-01.json).
Private primary artifacts: `.artifacts/semantic-bottleneck-20260914/`;
post-observation analysis: `.artifacts/semantic-bottleneck-analysis-20260914/`.

## Decision

Do not promote the corrective-metadata candidate, build retrieval or add a
post-plan knowledge pass. Its only demonstrated semantic rescue is the missing
lease definition, not a second context. Two apparent COUNT gains are an oracle
representation gap, not improved model understanding. The predeclared screen
requires gains on two cases in two data contexts without control losses.

Keep the architecture and production unchanged. The panel isolates three live
failure mechanisms, not one universal cause: a missing scope being guessed,
a wrong semantic choice despite definitions, and a correct plan blocked by the
concept heuristic. Name alternatives being combined is a separate intent/binding
boundary; exact value validity does not authorize a union.

The bounded study is complete; the wider product roadmap is not. No human
correction card, new provider, production prompt, gate, API or identity contract
was introduced. The root exercised the owner's delegated checkpoint authority
for the research specification and a separate annotation correction below.

## Design and execution

Thirty authored/adapted cases, five six-case families:

- Records versus distinct entities versus non-NULL references.
- Amount components versus filtered populations, in payroll, goods and services.
- Missing/present definitions for lease, cancellation and billing scopes.
- Output imperative versus business-return concept, including both in one question.
- Exact names, explicit union, prefix ambiguity, normalization collision,
  nonexistent negative name and unavailable grounding index.

Four arms use the existing production planner and `ask()`:

| Arm | Intervention | Diagnostic question |
|---|---|---|
| A | Original authored question and fixture metadata | What fails now? |
| B | Neutral descriptions at the same metadata sites | Does merely adding context change it? |
| C | Authored scope/contrastive knowledge in descriptions | Does the relevant information help? |
| D | More explicit same-intent question; original metadata | Does clearer wording help? |

C does not change schema identifiers, metric definitions, data or grounding
policy. D does not choose an ambiguous entity or invent a missing business
definition. These are diagnostic interventions, not ordinary-user accuracy.

All 120 arm contexts, independent SQL, expected plans and 23 foils were frozen
before calls. A ran first. Component/population was already 6/6, so its 18 B/C/D
jobs were skipped. The other four families ran all arms, including their controls.
Comparisons therefore use **the same 24 cases**, not A's 30 against the others' 24.

Completed 102 initial/actual Gemma4 31B calls, zero validation repairs or transport
errors, within 120 initial / 240 actual budget. Serial calls to the existing
gateway, T=0, thinking off, one permitted validation repair, no transport retries.
Configured max tokens is 512; the unchanged planner applies its 768-token floor.
Overall call p50 1.878 seconds. Full-arm p50: A 1.857, B 1.933, C 1.615, D 1.975
seconds; these are endpoint call times, not user-facing latency or a paired speed
claim (A includes the extra six cases).

The model receives authored questions, fictional schemas/definitions and approved
public fictional name candidates, never SQL or rows. No real POS rows were read.
PostgreSQL checks used read-only `grepbit_ro` and inline VALUES, without persistent
data/schema changes. Credentials remained opaque; no raw model responses were
saved. Artifacts retain hashes and allowlisted plan facts, not arbitrary text.

## Frozen results

`disclosed-answer-v1` and frozen live grades remain unchanged. Correct answers
require the same permitted interpretation across all four data instances.

| Same 24 cases | Correct answer | Necessary refusal | Wrong answer | False refusal | Unassessed |
|---|---:|---:|---:|---:|---:|
| A baseline | 13 | 5 | 3 | 1 | 2 |
| B neutral metadata | 13 | 5 | 3 | 1 | 2 |
| C corrective metadata | 15 | 6 | 2 | 1 | 0 |
| D explicit wording | 13 | 7 | 0 | 2 | 2 |

A's full 30-case baseline adds six correct component answers: 19 correct, five
necessary refusals, three wrong, one false refusal, two unassessed. No operational
failures in any arm. Refusal classification here accepts `clarify`, `semantic_gap`
or `unsupported` for predeclared unanswerable/ambiguous cases; it does not certify
the exact refusal reason or a successful clarification round trip.

For the frozen paired results, answered/24 and correct/24 are respectively
A/B 18/24 and 13/24; C 17/24 and 15/24; D 15/24 and 13/24. With W known wrong
and U unassessed among A answers, the unresolved-error range is [W/A,(W+U)/A]:
A/B [3/18,5/18], C [2/17,2/17], D [0/15,2/15]. These are annotation uncertainty
bounds in this selected panel, not population confidence intervals. D's zero
known wrong answers does not establish a usable autonomous replacement: it edits
the input and adds an unnecessary refusal. No threshold sweep was performed, so
these are operating points, not a calibrated risk-coverage curve.

## What changed, case by case

| Case/family | Observation | Supported interpretation |
|---|---|---|
| Missing lease definition | A/B answer the unrestricted population; C/D refuse | Explicit support information helps this known family |
| Missing cancellation/billing definitions | Already refuse in A; present-definition neighbors answer in every arm | Controls survive, but there is no second incremental rescue |
| Chinese output-count imperative | A/B/C choose the returned subset; D proposes the right count but the gate rejects it | Both planner interpretation and downstream heuristic matter |
| English output-count imperative | All four arms refuse; same captured plans answer correctly with only the concept gate disabled offline | A reproducible gate false positive, not a compiler or planner failure |
| Name normalization collision | A/B/C combine alternatives; D clarifies without choosing one | Metadata alone does not enforce source-mention ambiguity |
| Two non-NULL reference counts | A/B/D unassessed, C accepted | Separate exact-plan replay proves equivalent calculations, below |
| Component/population | Baseline 6/6 on three small schemas | No intervention benefit measurable; historical complex cases remain open |

The English case is `Return the transaction count.`. The Chinese explicit
diagnostic excludes filtering by `returned`; a negated mention can still trigger
the presence-based concept gate. Therefore a sentence-start English exception
would not address the underlying role/polarity problem.

The name collision has two legitimate database values that normalize alike.
The explicit-union positive control is correct in every arm. Globally rejecting
multiple value IDs would fix one case by breaking another. Grounding needs to
distinguish alternatives for one source mention from an explicitly requested
set; individual valid IDs do not contain that information. The unavailable-index
control must also remain distinct from an absent business definition.

### Downstream injection and gate ablation

There are 106 fixed-plan/foil executions across gate-on/off settings. Of the
30 primary injections per setting, only 23 are gold answer plans. Three are
deliberate unrestricted-population injections into missing-definition questions;
four probe name refusals. They must not be reported as 30 correct-plan tests.

For the 23 answerable gold plans, gate-on allows 22 and falsely rejects the English
output count; gate-off allows all 23. Across all 30 injections, disabling the gate
also changes the missing-cancellation foil from a refusal into a wrong answer
(known wrong 2 to 3). Thus the offline ablation is diagnostic only, not evidence
for removing the production gate wholesale. Live captured plans were replayed
through the same two settings where a plan was available; no new model judgment
was used to decide which answer was right.

### Separate post-observation annotation correction

For the two questions asking for records with a ticket reference, both
`COUNT(ticket_id)` and `COUNT(*) WHERE ticket_id IS NOT NULL` are correct in this
unperiodized scalar context. The frozen rule only recognized one compiled recipe.
This equivalence is not a general rule to rewrite arbitrary grouped counts.

The root approved a separately identified `bottleneck-count-annotation-v2-posthoc`
after tests established duplicate/NULL/empty behavior and rejected all-row and
DISTINCT controls. A finite search over the two forms and 17 aliases recovered
the **full plan hash** of all eight recorded plans (two questions x four arms).
Each captured plan was then replayed on four instances with the new rule;
32/32 replays pass with one consistent interpretation per plan. No model calls,
no edits to primary helpers, old records, historical scores or general grader.

This resolves all six unassessed invocations of those two questions in A/B/D,
while confirming the two already accepted C invocations. It means C's apparent
two-answer improvement is not a semantic rescue. The companion annotation is
post hoc and cannot turn this development panel into holdout evidence.

## Validation and limitations

- Nineteen primary study tests; seven post-observation annotation tests, all pass.
- Each frozen preparation checks 368 compiled-versus-independent-SQL results in
  DuckDB and 368 in PostgreSQL, plus 23 separating foil witnesses. Preparation
  before and after live calls agrees exactly; repeated preparations are not new
  cases and their counts are not pooled as additional coverage.
- Four instances per context: three nonempty and one empty. Nonempty amount
  contributions vary, but entity/count multiplicities are held fixed. This is
  bounded witness coverage, not exhaustive random-data or compiler correctness.
- PostgreSQL validates the predeclared answer/oracle matrix; foil separation and
  captured live-plan replays use DuckDB. Do not claim every foil or live plan was
  independently run on PG.
- Primary helper hashes and tracked runtime/evaluation source digest match the
  frozen preparation after the run. Fresh static verification passes; prior
  1,841-test offline gate is reused only with matching source and artifact hash.
- No production changes or new general-purpose framework. Research helpers are
  intentionally private; committed evidence contains counts, paths and hashes.
  Reproduction needs the retained private helpers, not the manifest alone.

These are small authored adaptations, not unseen user questions, not exact
reproductions of every historical failure. The component cases remove the
historical quarterly/time context. One Japanese question contains the Chinese
spelling `工單`; translations have no independent blind review. There is one
measured output per intervention, so differences are observations, not a causal
claim about batching or a stability estimate. Screens guide development effort;
they do not prove metadata cannot work in other settings.

## Next order

1. Carry the COUNT annotation correction forward explicitly in future panels;
   retain the frozen primary scores. Maintain distinct error/refusal/unknown
   categories rather than optimizing a total-pass number.
2. Address the bounded source-mention/name boundary next: exact names and explicit
   sets must still work, alternatives must not silently become a union, missing
   configuration must not become a false business claim. Establish identity
   rulers before implementation. Do not add a UI/card or a broad conversation
   framework; use the existing typed clarification surface where necessary.
3. Keep role-sensitive gate work a separate candidate with actual captured right
   and wrong plans, including negation and true business concepts. A model-labeled
   span is not independent intent proof; global disabling and one-word exceptions
   fail the demonstrated bidirectional requirements. No replacement qualifies yet.
4. Only resume knowledge delivery experiments when a new information intervention
   demonstrates benefit in a second context. Keep temporal sentinels, Japanese
   failures and demand-driven A4 separate. A5's candidate offering/binding results
   still do not establish correct entity selection or broad completion.
