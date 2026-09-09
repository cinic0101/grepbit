# ADR 0008: Reinvention as an agent-callable data agent

Status: Accepted 2026-09-08 by the product owner. Supersedes the G7 release
program in ADR 0007 and the delivery-gate ladder of the v0.1 specification.

## Context

Between 2026-08-21 and 2026-09-08 the repository reached 611 commits. G0
through G6b were all started within three days (2026-08-23 to 2026-08-25). G7,
the release evaluation, started on 2026-08-26 and accounted for 443 of the
remaining commits; of those, 22 touched `src/`, 111 touched `evals/`, 286
touched `tests/`, and 86 touched `docs/`. Five live evaluation runs ended in
`FAIL`. The last one, R4, passed every Grepbit predicate (117/117 trials,
177/177 facts, zero safety violations) and failed only on a scorer rule about
the unvalidated baseline comparator.

Three problems were visible at that point:

1. The answerable surface was a lookup table. Request grounding matched a
   normalized question against 39 reviewed literal templates. Any other
   question terminated as `semantic_gap`. The reviewed context handed the
   model the SQL shape, and server bindings were fixed literal values.
2. The release evaluation was sized for a production release, not a proof of
   concept: exact identity pinning across protocol, scorer, trace, pack, and
   profile revisions; three repeated trials; a baseline comparator; mutation
   testing; cold readback. Each change to a rule produced a new identity
   tuple and a new copy of the 452 KB release pack.
3. The service could not start. No entrypoint, CLI, or `uvicorn` invocation
   existed; the production composition function was called only from tests.

The G4 relation flow, G5 progressive replanning, and G6b multi-task machinery
(about 3,200 lines) were built but never exercised by the release evaluation:
R4 recorded zero planning, repair, replan, and retry calls, and its runtime
profile fixed `max_steps_per_task` at 1.

## Decision

1. **Product direction.** Grepbit becomes an agent-callable data agent. The
   north star is a bounded *data probe sub-agent* that an upstream agent
   delegates investigative questions to and that returns a structured report
   with per-finding verification. The first delivered slice is the
   single-shot capability that probe steps are built from: one question, one
   structured query, one verified or honestly-refused answer with
   interpretation, assumptions, SQL, and evidence.
2. **Model role.** The model classifies intent and fills typed slots against
   a small semantic catalog. It phrases clarification questions and result
   summaries. It does not write SQL, does not choose table or column names
   outside the catalog, and does not plan multi-step work in this slice.
   Deterministic code renders SQL from the structured query, derives server
   bindings from typed slots, and produces the assumptions list from the
   catalog definitions and defaults that were applied.
3. **Removal.** The G7 release harness is removed: `evals/*.py`,
   `evals/scorers/`, `evals/release_packs/`, `tests/contract/g7/`,
   `tests/fixtures/g7/`, `tools/release_evidence.py`, and
   `docs/checkpoints/`. Evaluation returns to answering the product
   hypothesis: a paraphrase-based grounding set, refusal precision,
   misrouting rate, `false_verified_count = 0`, and latency, run once per
   change and reviewed by hand. No scorer or protocol identity versioning.
4. **Retained.** The trust chain is unchanged: reviewed semantics with review
   states, server-owned typed bindings, Wren compilation, the SQLGlot SQL
   policy, the read-only psycopg executor, deterministic validators, the
   SQLite evidence ledger, sanitized error codes, and the typed terminal
   states. The retail_v1 fixture, the G2/G3 case manifests, all production
   code, and the G2 through G6b contract tests remain.
5. **Dormant, not deleted.** G4 relation flow and G5 progressive replanning
   stay in the codebase for the probe loop. They are not part of the first
   slice and are not evaluated until then.
6. **Documents.** The v0.1 specification moves to
   `docs/history/poc_spec_v0.1.md` and stays authoritative for the retained
   runtime contracts it describes (domain models, execution, security,
   validation, persistence, API) where the new specification does not
   supersede them. The agent development issue log moves to `docs/history/`
   as a retrospective. `spec/grepbit_spec.md` is the new normative product
   document. `AGENTS.md` is rewritten as a short operational guide.
7. **Process.** Delivery proceeds in small slices with focused tests, one
   offline suite run and static checks per commit series, and a concise
   report. The two-phase ruler checkpoint applies only to persistent schema,
   public API or wire format, and security boundaries. Section 12.6 evidence
   packets and gate outcomes are no longer required.

## Consequences

- The offline suite runs in about 6 seconds instead of 368 seconds, with 514
  tests instead of about 1,800.
- Historical R1 through R5 evidence under `.artifacts/` remains readable on
  disk but has no consumer in the repository. It is not a release authority.
- Changing the model output contract from Wren semantic SQL text to a
  structured query will break G3 and G6b tests that pin the old contract.
  Those tests are rewritten or removed in the slice that makes the change,
  never weakened to pass.
- Slot values that originate from the user's question (a month, a limit, an
  enumerated status) may be extracted by the model. They are typed, validated,
  and bound as parameters by the server. The invariant that the model never
  emits data-derived values, SQL, or unlisted identifiers is unchanged.
- The unvalidated-baseline comparison is dropped as a release predicate. A
  side-by-side comparison may return as a demonstration once both paths
  receive the same catalog information.

## Follow-ups

Ordered slices are listed in `spec/grepbit_spec.md` Section 13. The first
code slice is the structured query contract, the deterministic renderer, and
assumption generation, validated offline against the retail_v1 fixture before
any model call.
