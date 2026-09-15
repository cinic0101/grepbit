# Identifier and duplicate-row-wire closeout

Baseline: dev `daeaf77`; root is the only writer. Owner approved the review's
ordering with “同意”: repair identifier binding first, then bounded exact-column
deduplication replay. Earlier authorization permits checkpoint decisions, readonly
fixture PostgreSQL/Gemma and local commits; no push, owner-Web restart, customer
DDL/data mutation, new provider or credential copying. This record cites that
authorization; it does not grant new permissions.

## Acceptance

1. Preserve exact schema/table/column/output identity through every shared
   compiler path. Quote identifiers requiring case preservation at the final AST
   serialization boundary; preserve already-safe lowercase SQL. Independent
   self-check must reject unquoted case-sensitive identifiers, including mutated
   JOIN operands, relation names, predicates and aliases. No query capability or
   namespace inference changes. SELECT-only PostgreSQL witnesses must distinguish
   same-spelling mixed-case and lowercase columns, not rely on DuckDB folding.
2. Only identical, nonempty, ordered lists of well-formed column references in
   `plan.columns` and `plan.rows.columns` may drop the former. Reject conflicts,
   reordering, malformed lists, missing nested projection and all_columns=true;
   retain extra=forbid and all downstream checks. Record a shape variant, not a
   meaning normalization. Prompt and shown schema stay unchanged. Rulers precede
   implementation; saved raw response evidence must establish unchanged proposals,
   values/refusals and reduced repair calls before accepting runtime integration.
3. Preserve historical scores and raw outputs. Report original noncanonical
   output rate, deterministic normalizations and model repairs separately.
   Keep Return/minutes false refusal and cross-schema catalog debt open.

Artifacts: `.artifacts/identifier-row-wire-closeout/`. No new live model call is
needed if actual saved-response replay is conclusive; new-query generalization
and live latency improvement are explicitly not claimed. Freeze source, tests
and probes during measurements; run one broad offline gate after final edits.

## Work record

- Read-only review reproduced wrong parent data in PostgreSQL, self-check empty.
- All ten saved duplicate-column outputs become the exact historical repair
  JSON by deleting only plan.columns. This is evidence for a narrow candidate,
  not permission to ignore arbitrary extras.
- Identifier ruler: 12 expected failures / 1 lowercase control pass. Independent
  writer/reader correction implemented; PostgreSQL six-path SELECT witnesses pass.
- Wire ruler: 4 expected failures / 10 negative controls pass. Exact variant
  implemented; 35 paired ask/readonly-DB replays keep identical proposals/results,
  model repair 10 -> 0, completion attempts 45 -> 35, ten recorded shape variants.
- Candidate accepted within the approved narrow scope; no new prompt or routing.
  Final static and 2,313 offline tests pass (zero skips), same source digest as
  the successful replay. Residual limitations are recorded in the research
  closeout. Root reviewed the full runtime/test/documentation delta; no push or
  owner-Web restart is authorized by this closeout.
