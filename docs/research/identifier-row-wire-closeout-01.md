# Exact identifiers and duplicate row columns

Baseline `daeaf77`. Owner approved repairing the reproduced identifier bug before
evaluating the ten saved identical-column slips. Shared runtime changes only;
no model prompt/schema change, gate change, UI/router expansion, deployment or
owner-Web restart. Permission/scope record: `../plan/identifier-and-row-wire-closeout.md`.

## Identifier finding and correction

The previous row compiler generated `records.ParentId` for a declared
`records."ParentId"` FK. With a lowercase `parentid` also present, PostgreSQL
selected the wrong parent while SQLGlot-based selfcheck returned no violations.
The common aggregate/latest/without builders had the same construction pattern.
The previous lowercase panel did not test this legitimate schema boundary.

Rather than special-case the new JOIN, the shared final AST serializer quotes
every identifier containing ASCII capitals. Schema, table/qualifier, column and
output alias are treated consistently through nested scopes; lowercase SQL and
bound literals stay unchanged. Both aggregate and rows call this boundary.
The independent reader checks parsed quote state itself and emits
`identifier_case_unquoted`, not a comparison using raw spelling alone. It does
not reuse the writer's function or infer a new relation allowlist.

Ruler: **12 expected failures, one lowercase control pass**. Six path families:
rows, grouped SUM, filtered COUNT operand, correlated without, latest row and
latest calendar scope. Each also mutates individually removable identifier quotes
(relation/schema, columns, aliases, JOIN/predicate references). A dotted flat
output alias with its quote removed is syntactically invalid SQL, so it is not
counted as a parseable case-folding mutation. An initial focused test attempted
that invalid mutation; the test was narrowed, not the production invariant.

Readonly PostgreSQL verification executes six compiled queries against inline
VALUES/CTE witnesses with `ParentId=10` vs `parentid=20`, `Value` vs `value`,
NULL FK, repeated parents, asymmetric measures and different months. Independent
hand-computed names/values all match. Removing the necessary FK quote yields B
instead of A/NULL for three records and is rejected by the new selfcheck.

The probe replaces only schema-qualified relation nodes with same-name CTEs;
it is not a new catalog fixture or proof of cross-schema serving support. Mixed
schema quote state is covered by AST rulers; current SQL policy's namespace
allowlist remains unchanged. No tables, roles, grants or data were modified.
DuckDB is not the authority for PostgreSQL case-sensitive identifier behavior.

## Duplicate-column evidence and acceptance

All ten initial slips in `.artifacts/parent-rows-impl/main/call-*.json` satisfy
ordered exact equality of `plan.columns` and `plan.rows.columns`. Deleting only
the top-level member gives the exact full historical repair-response JSON.

Accepted rule: nonempty lists up to 32 entries of qualified reference strings or
strict table/column objects, ordered equality **before** reference coercion,
all_columns absent or literal false. Drop only the duplicate field and record
`dropped exact duplicate plan.columns matching rows.columns`. Domain validation,
extra=forbid, source permission, request-kind guard, visibility, compiler and SQL
policy remain in the same path. No guessing equivalence, merging or unknown-key
ignore. Invalid projection identities/duplicates are still downstream failures.

Ruler: **4 expected failures / 10 negative controls passed** before implementation.
Controls include different order/content, missing nested projection, all_columns
conflict/type, empty/malformed/unqualified/non-list references, and unrelated
extra requirements. Integrated tests also exercise one-call validation and
disabled-row permission. The final focused group passed **124 tests**.

## Paired full ask and value replay

The old normalizer is loaded read-only from `daeaf77`; both arms otherwise use
the same fixed corrected compiler/runtime. Each gets exactly the same archived
initial/repair responses through a fake transport, including the Default legacy
planner's internal call. Original input files are not rewritten. Every answer
executes via shared ask/SQL policy/executor on the existing synthetic PostgreSQL
sources and matches the panel's independent SQL reference. Proposal and all
result fields except timing/normalization/raw-repair diagnostics are identical
between arms. The two source schemas are not sent to any new provider.

| 35-question archived panel | Old normalizer | Exact duplicate candidate |
|---|---:|---:|
| Correct answers | 20 | 20 |
| Appropriate refusals, reason checked | 14 | 14 |
| Existing false refusal | 1 | 1 |
| Wrong answers / operational failures | 0 / 0 | 0 / 0 |
| Simulated completion invocations | 45 | 35 |
| Model repair turns | 10 | 0 |
| New exact-duplicate normalization events | 0 | 10 |

`parent_unique_nonpk` still fails with `plan_row_projection_unsupported` after
normalization. The existing Return/minutes `concept_not_mapped` false refusal
remains; changing Return to List is not counted as a repair. MTTR/lease and mode
conflict refusals are not conflated. Normalizer gains no new ability to answer.

**Zero new physical model calls.** The 45 -> 35 replay count establishes that ten
historical repairs were avoidable (22.2% fewer completion invocations on this
panel). It is not a new Gemma success rate, E2E latency measurement or holdout.
The initial-output duplicate rate remains **10/32 Details**, irrespective of
whether a second call is needed. These ten events remain shape_variants, never
meaning_normalisations; new-construct freeze and historical scores are unchanged.

Probe setup corrections: the first replay lacked the service factory's model
settings (no model call). The next subclass-level replay seam missed Default's
internally created planner and failed on the first Default control; its fake
client had no network methods. The final fake transport covers both planners,
and the entire pair was rerun. No partial run is credited as a passing panel.

## Disposition and limits

Final static gate passes; **2,313 offline tests pass, zero skips**. The final
focused/replay/static/offline source digests agree. No source/test edits follow
the broad gate; documentation and evidence closeout are separate.

Both narrow changes are accepted into shared runtime. The identifier fix restores
the existing catalog-identity contract; the normalization removes only proven
redundancy. No additional research prompt or evaluator framework is warranted.

Keep the separate gate false-refusal and actual cross-schema catalog fixture
debts open. Continue new owner questions in the existing UI; automatic routing,
other new query constructs and PII deployment approval are not part of this work.
The original Web process remains unchanged and requires its normal controlled
reload to pick up new code; no browser/HTTP transport acceptance was rerun here.

Evidence: `.artifacts/identifier-row-wire-closeout/` (red rulers, focused group,
PostgreSQL values/mutant, complete paired replay, static/offline gate).
Durable closeout counts and hashes: `evidence/identifier-row-wire-closeout-01.json`.
