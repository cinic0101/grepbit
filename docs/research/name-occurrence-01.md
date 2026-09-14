# Name alternatives: truthful hints and occurrence provenance

2026-09-14, baseline `c349881`, production `plan-classify-json-v15` unchanged.
Root scope/checkpoints: [`name-occurrence-study.md`](../plan/name-occurrence-study.md).
Evidence: [`name-occurrence-01.json`](../../evidence/name-occurrence-01.json).
Primary private artifacts: `.artifacts/name-occurrence-20260914/`;
analysis: `.artifacts/name-occurrence-analysis-20260914/`.

## Decision

Neither candidate qualifies for confirmation or production. Truthful descriptions
of the existing candidates do not rescue a case; adding occurrence provenance
also does not rescue a case. Do not add a production occurrence interface, another
model verifier, lexical exception or blanket ambiguity gate on this evidence.

This narrows the previous diagnosis: loss of provenance is real, but supplying
it does not by itself correct the planner's set selection in this experiment.
Deterministic matching proves where text matches, not whether the user wants one
entity or every matching spelling. This is not evidence that all possible uses
of provenance fail, or that Gemma cannot serve other product queries.

## What was isolated

Current `ValueIndex.mentions` matches normalized strings, then sends flat
column/value pairs. Its rule 11 calls the candidates verbatim question values.
For lower-case `harbor east`, both `Harbor-East` and `Harbor East` are offered,
although neither occurs verbatim. The missing distinction is visible before a
model call. A second existing behavior drops a shorter value globally when a
longer matched value contains it, even if the short name occurs independently
elsewhere in the question. Neither observation is a new production fix here.

Twenty-four authored questions cover 12 behaviors in each of two fictional
schemas: depot amounts and laboratory charges. They include exact hyphen/space
spellings, single unresolved names, explicit unions, separately occurring short
and long names, repeated mentions, exact/ambiguous negative filters, incomplete
and absent names, unfiltered totals and explicitly requested normalized sets.
Names and schemas are paired adaptations, not independent unseen-user families.

| Arm | Intervention |
|---|---|
| A | Exact existing planner messages and candidate catalog |
| B | Same catalog/wire; rule says normalized candidates are not necessarily verbatim mentions or separate requested entities |
| C | B plus request-local source ranges, exact/normalized match type and per-occurrence candidate IDs |

C does not add values missing from the existing candidate catalog, nor change
reference resolution, grounding, compilation or execution. It reports a missing
offered ID instead. The ordinary literal path remains available in every arm.
C includes a short explanation of the new metadata, so it is metadata plus its
instructions, not a pure metadata-only treatment.

The research extractor maps normalized characters back to original ranges,
keeps repeated occurrences, applies containment suppression locally and narrows
an occurrence to exact stored spelling when available. Cross-character Unicode
composition that invalidates the mapping returns unavailable. Latin/digit boundary
checks are limited heuristics, not a general language parser. Its hash binds the
question and column/value snapshot only: no tenant/session authorization, predicate
role or proof of intended choice is conferred. No model-generated source labels
or second model judgment supply the evidence.

## Live results

All 72 jobs completed: 78 actual Gemma4 31B calls, six validation repairs,
zero transport errors. Serial existing gateway, T=0, thinking off, timeout20s,
at most one validation repair, no transport retries. Configured max tokens512;
the production planner's effective minimum is768. All arms have the same24 cases.

| Arm | Correct answer | Necessary refusal | Wrong answer | False refusal | Unassessed | Operational failure |
|---|---:|---:|---:|---:|---:|---:|
| A | 16 | 4 | 4 | 0 | 0 | 0 |
| B | 16 | 4 | 2 | 0 | 0 | 2 |
| C | 16 | 4 | 4 | 0 | 0 | 0 |

All six repairs occur on the negative-ambiguity questions. B's two operational
failures are `invalid_structured_output`, not gateway outages or appropriate
clarifications. Fewer emitted wrong answers because output validation failed is
not better understanding. No correct-control losses occur, but there are zero
rescues, so the two-context screen fails for both B and C.

Call p50 A/B/C: 2.516/2.500/2.549 seconds, including repair calls as individual
calls. Not user-facing turn latency or a stability estimate. Answer coverage is
20/24,18/24,20/24; effective correct-answer coverage is16/24 in every arm. Known
wrong among answers is4/20,2/18,4/20. Operational failures are shown separately,
not removed from the denominator of the overall requested tasks.

### The remaining mistakes are concrete set operations

In both schemas, A/B/C turn a request for one unresolved positive name into
`IN` over both stored spellings. A/C turn a request to exclude one unresolved
name into two `NE` predicates, excluding both entities. Exact filter-value hashes
match the authored candidate sets; this is not just a hypothesis from the answer
status. B's negative cases fail validation after repair and have no served plan.

Every arm answers the exact-name, explicit-union, repeated-name and exact-negative
controls. Both independently occurring short/long-name questions also answer
correctly, despite the missing shorter-name hint. That hint omission is therefore
not an end-to-end failure on these cases, and its repair cannot be credited as a
measured accuracy gain here.

No post-hoc regrading or expanded acceptance recipes were needed. Answers use
the predeclared independent SUM oracles, with singleton EQ/IN alternatives where
appropriate; one permitted interpretation must match on all four instances.
For predeclared refusal-only cases an answer is rejected regardless of whether
its numeric result is internally consistent. Necessary refusals accept the
existing typed statuses; exact reason precision and follow-up success are not
certified by this panel.

## Why not simply reject every ambiguous source occurrence?

Two offline counterfactual tests isolate the tradeoff. Positive single-name,
negative single-name and explicitly requested normalized-set questions have the
same column, normalized match type and two candidate spellings. The last question
explicitly asks to combine BOTH stored spellings, so a union is correct there.

A hypothetical gate based only on multiple candidates per source occurrence
would catch the four mandatory-refusal cases but falsely refuse two correct set
queries. This is not a production gate or a measured follow-up solution. It
demonstrates that candidate multiplicity alone is insufficient; the remaining
distinction concerns the requested operation. Requiring only exact spellings or
reviewed groups would be a new product restriction, not a harmless identity fix.
No such restriction was adopted under the checkpoint authority.

## Validation, privacy and reproducibility

- Research ruler baseline: nine intended assertion failures/four passing controls
  against an unavailable occurrence stub. This is not nine production defects.
  Before live freeze, a hand-counted offset and an ill-calibrated unique-typo
  fixture were corrected with their earlier JUnit evidence retained.
- Final preflight:18 passing tests; separate counterfactual analysis:2 passing tests.
- Each preparation checks88 compiled versus independent-SQL results in DuckDB
  and88 in PostgreSQL, plus16 separating foils in DuckDB. Three nonempty amount
  instances and an empty instance; data include repeated entity rows, NULL amounts
  and an orphan FK. The two preparation runs match exactly. Repeated preparations
  and schema renamings do not multiply independent semantic coverage.
- Sixteen gold answer injections and eight name-refusal injections pass their
  separate offline expectations; explicit-union counterexamples are also checked.
  Captured live plans are replayed on DuckDB; PG checks the predeclared oracles,
  not every live plan. No broad compiler-correctness claim.
- Source/helper hashes and messages/oracles are frozen before calls and checked
  after completion. Fresh static passes; prior1,841-test offline result reused
  only after matching source/artifact hashes. No production code was changed.
- PostgreSQL uses existing `grepbit_ro` with read-only inline VALUES, no stored
  customer rows or writes. The existing gateway receives fictional metadata,
  authored questions and public fictional names only, never SQL/results. Keys
  remain opaque. Raw model output is hashed, not persisted. Committed evidence
  contains counts/hashes; rerunning requires retained private helpers.

One measurement per question/arm; no batching-causation, independent linguistic
review, customer prevalence or generalization claim. The stronger B wording is
one tested prompt, not a test of every possible instruction. The two schemas
share query topology, so agreement across them is robustness to a paired rename,
not broad cross-domain validation.

## Next research direction

Stop this prompt/provenance candidate. Keep exact-name and explicit-set behavior,
typed clarification, and the distinction between validity and intent. Occurrence
metadata can be useful diagnostic evidence without becoming an authority token.

Before introducing a stricter name policy, quantify these ambiguous-name requests
in the retained real-user corpus and measure how many currently correct set
queries it would reject. That prevalence/utility question was not measured here.
Do not count authored challenge frequency as product failure rate. A future
candidate must distinguish requested set operations without promoting a model's
own role label into independent proof; the known actual plans and normalized-set
controls should remain fixed regressions. Gate-role work and other unresolved
semantic families stay separate; no repeated same-model voting is justified by
this result. Production A5 acceptance remains open.
