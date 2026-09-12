# A5 candidate references and non-POS service fixture

Follow-up: the owner approved lexical grain retirement; see
`grain-retirement.md`. The pending-decision text below is the earlier slice's
historical record. A5 acceptance is still open and its prompt is unchanged.

## Scope and authority

The owner instructed "好 直接繼續", explicitly reiterated permission to call
local psql/Gemma4, and requested longer continuous work batches with fewer
checkpoints. Continue the approved roadmap through reversible implementation,
experiments and corrections. New product meaning, compatibility breaks,
data-exposure boundaries and irreversible actions remain explicit decisions.
This record grants no authority beyond those original messages. No commit,
push, new credential copy or new runtime role is authorised here.

Preserve the existing uncommitted 0A/0B work at baseline 746f168. One writer.
Do not modify imported source during a regression. A5 is separate from A4.

## A5 wire ruler

- A request advertises only its existing, visible, explicitly groundable
  question-value candidates. Do not index more columns or widen recall as
  part of this wire change. Missing candidates remain a separate metric.
- Each candidate has a deterministic opaque ID tied to column and exact
  stored spelling, independent of list order. IDs are valid only if supplied
  in this request; no global cache or persistent lookup.
- Filter `value_refs` is an alternative to `values`, never both. Resolve
  only eq/ne/in text filters, including operand/ratio and without filters.
  Unknown IDs, wrong columns, invalid shapes or an unavailable catalog fail
  validation before SQL. A string in `values` is always a literal, even if
  it resembles an ID. Do not guess, normalize spelling or silently fallback
  from an invalid reference.
- The domain QueryPlan and compiler continue to receive typed literals.
  Public resolved plans and follow-ups do not retain request-scoped IDs.
  Existing literal spelling remains accepted; report reference usage apart
  from candidate availability, literal misses and answer correctness.
- Candidate references do not prove the model chose the right entity or
  filter. Wrong-valid intent remains a separate evaluation concern.
- Version the prompt independently. Experiment first with synthetic data;
  then focused contracts, fixture/real regression with preserved privacy,
  and compare the same frozen sets. No old report is relabelled a new run.

## Proposed synthetic service-operations source

Fictional support projects and work tickets, not POS or personal data.
Business names are synthetic team/project labels, not people. Proposed
isolated database name: `grepbit_spike_service`. No existing DB is dropped,
overwritten or altered. Setup-only credentials stay in shell memory; only
the existing `grepbit_ro` receives runtime CONNECT/USAGE/SELECT.

Six small relations, each justified by a current risk:

| Relation | Purpose / trap |
|---|---|
| teams | natural unique team code, multilingual long names and overlapping prefixes |
| projects | FK to team code; distinct numeric PK and natural project key |
| tickets | FK to project key, status, created/closed timestamps, nullable estimate; missing calendar months |
| work_logs | FK to ticket, logged timestamp and nullable/zero minutes; three-hop dimension path to team |
| ticket_events | another child of tickets; fan-out and multi-hop without probes; activity is not a ticket count |
| team_links | two FKs to teams; deliberately ambiguous join must refuse |

Seed includes empty projects, tickets without events/logs, NULL effective
times, multiple time columns, zero and NULL aggregate values, equal Top-k
boundaries and deterministic integer totals. No fake orphan with a declared
FK: orphan cases belong in the separate random-instance harness.

Golden SQL and 20-30 smoke questions must distinguish counts of tickets,
events and logs, and refuse unsupported cross-child aggregation rather than
multiply rows. Synthetic questions are author tests, not blind real-user
generalisation. Business overlay is a draft, never marked user-reviewed by
the agent; reviewed business decisions can be discussed after schema/data
and raw-schema measurements are ready. A4 is justified only by a measured
full-schema limitation, not by making this fixture artificially wide.

## Current evidence

Closeout: all planned case sets have complete reports after repairing the
service-discovered assertion. No live process remains. A5 is **not accepted**:
q25 repeats a missing-denominator failure; same-index service controls show
no accuracy improvement. Detailed results and limits are in
`../research/a5-service-01.md`; durable counts/hashes are in
`evidence/a5-service-01.json`. 329 offline tests and final static checks pass.
Natural-key generation and grain/growth dependency repairs are complete.
The owner has been asked about retiring lexical grain deletion; it remains
unchanged apart from preserving growth's required grain. No A4, Git stage,
commit or push. The chronological observations below are preserved as such.

The isolated paired synthetic probe completed 18 serial calls to the
authorised Gemma4 gateway: nine selections per arm, both 9/9; p50 2.047 s
literal versus 1.908 s reference. This tiny probe shows format usability and
shorter output, not an accuracy or reliable latency improvement. Artifacts:
`.artifacts/a5-20260912/probe.py` and `probe-result.json`.

A5 is implemented as wire-v3 / prompt v15, separate from A4. Focused client,
wire, grounding, ask and runner tests passed; request-stale ID and nested
filter tests are included. Literal/domain/compiler formats are unchanged.

The synthetic database `grepbit_spike_service` has been created and seeded
using container-local PostgreSQL setup authentication; the supplied admin
password was not read, copied or retained. No old database was changed.
Existing grepbit_ro holds only CONNECT/USAGE/SELECT on it. The fixture-only
overlay opts in fictional labels and contains no agent-approved business
metrics. Golden SQL checks passed in DuckDB before model calls.

New-source differential: PostgreSQL 160 agreements. The first random-DuckDB
run had 120 disagreements and 360 agreements. Root cause: random generation
did not preserve uniqueness of FK targets that are not primary keys, so it
could create impossible fan-out at a declared many-to-one join. An isolated
in-memory generator patch replayed the same 216 valid plans (56 refusals)
on three instances: 480 agreements, no disagreement. Formal generator repair
waits until the live source freeze ends. Artifacts: `service-differential-*.json`,
`service-natural-key-probe.json`, `natural-keys-red/`.

Live regression now running from frozen source: a v14-wire control on batch 1
and holdout 2, then v15 across the existing 313 questions and two service
runs of 24 questions each (raw schema / fictional-label policy). The v14
control uses the same accepted period compiler and candidate eligibility/order
as v15, not the old missing-period bug or an exact historic deployment.
It isolates the wire/rule change. Existing holdout2/holdout3/ratio files are unjudged, so no new
correctness score is inferred without a judge. All real-source runs fix
as_of to 2026-02-04 18:00 Taipei (including the older smoke file's override).

The experimental regression driver persists only allowlisted metrics and
plan SHA-256, never questions, values, raw outputs or row data. It performs
golden comparisons in memory and suppresses value-bearing stdout. Its
synthetic sentinel self-test passed. Source/candidate recall/selection/final
correctness remain distinct; a candidate existing somewhere in a question
does not prove an unresolved literal had the right candidate.

Early results: batch 1 is 50/50 in both arms. Both of its eligible candidate
cases use references in v15, with zero reference errors; p50 4.171 s control
versus 4.086 s v15 is not a strong performance claim. Holdout 2 has 20 hinted
cases: v15 validates references in 19 (28 references), with no reference
errors or final literal misses; q25 fails structured output after a repair
turn. The failure is retained for targeted counterfactual/repeat checks,
not discarded as noise or counted as a successful reference case.

Frozen runtime SHA-256 (sorted src Python/JSON and evals top-level Python,
path-NUL-content-NUL concatenation) during the live run:
`2c4da6d3d9481d30aa9fdc66ba7eea27b6505e1ef9be931e9c5b151d36dd0aa9`.
