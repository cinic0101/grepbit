# Lessons from v1 (2026-08 to 2026-09-08)

The previous repository grew to 21k lines, eight ADRs, a release-evaluation
harness (G7), and a catalog-first agent API, and stalled before a single real
user asked a question. This page records why, from the documents and history
carried into `docs/history/`, so the restart does not repeat it.

## What happened

1. Scope was set as a product before the core mechanism was measured. The
   G-series (G3 chat completions, G4 relation flow, G5 progressive
   replanning, G6 async API and runtime lifecycle) built orchestration,
   cancellation, budgets, and evidence ledgers around a planner that had not
   yet been shown to generalize beyond one fixture schema.
2. Evaluation became an artifact-producing process instead of a question.
   G7 spent its effort on release packs, attestation, and evidence
   completeness rather than on whether answers were right for questions the
   team had not written themselves.
3. Knowledge was hand-written per datasource. The retail_v1 catalog carried
   synonyms, patterns, and templates typed by the agent to make its own cases
   pass. 50/50 on that set measured the catalog, not the system.
4. A heavy dependency was pinned early. Reviewed metrics compiled through the
   Wren engine (pinned 0.13.2; its repository was later archived into
   WrenAI), which shaped the whole tier-1 path around an external manifest
   format.
5. No real users, no holdout. Every case was author-written; the agent
   development issue log records repeated cycles of patching the vocabulary
   to satisfy the next case.

The redirect on 2026-09-08 (`adr-0008-reinvention-2026-09-08.md`) removed
G7 and re-centered on an agent-callable data agent. The catalog-first v0.2
specification (`spec-v0.2-catalog-first.md`) was written for that redirect and
is kept as the reference for the response contract; its assumption that a
reviewed catalog is a prerequisite for answering was overturned by the spike.

## What the restart does differently

- Mechanism first. The tier-0 spike asked one question: can a 31B model plan
  correctly over a schema it has never seen when the server owns the algebra?
  It was answered with live runs on three schemas before anything else was
  built (`../research/tier0-generalization.md`).
- Each feature is an experiment with a number attached: no foreign keys,
  concept drops, parent-agent relay, multilingual, overlay, competitor
  features. What did not measure well (the LLM coverage audit) stays out of
  the product path.
- Knowledge is data with provenance: introspected, inferred with evidence,
  or reviewed. Nothing per-datasource is written into code.
- The reviewed layer compiles through the same sqlglot compiler as tier-0
  (metrics as plan fragments), so the Wren dependency is not carried over.
- The next generalization measurement is the owner's real questions, unseen,
  on their real database (`../plan/next-phase.md`).

## Records carried over verbatim

- `poc_spec_v0.1.md`: the original v0.1 specification (2,800 lines).
- `agent-development-issue-log.md`: the issue log of the v1 development.
- `adr-0008-reinvention-2026-09-08.md`: the redirect decision.
- `spec-v0.2-catalog-first.md`: the catalog-first contract that the spike
  partially superseded; Sections 3 (invariants) and 8 (response contract)
  remain the reference.
- `v1-evaluation-log.md`: every live run of v1 and of the spike, in order.
