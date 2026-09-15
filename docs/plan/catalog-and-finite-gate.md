# Catalog closure and finite request gate: bounded decision

Baseline: `e8ff36f`. Root is the sole writer. Owner explicitly approved this
two-delivery scope with “可以開工了” after agreeing to isolation/setup separation,
frozen grammar/cost and unknown outside bounded population comparison.
Earlier instructions authorize needed local PostgreSQL setup and local commits;
no push, owner-Web restart, new provider or production gate/parser integration.

## A. Catalog acceptance, independent of the language candidate

Create only new database `grepbit_catalog_boundary_v1` in the existing localhost
PostgreSQL (`pg17`, mapped port 5432). Refuse setup if it already exists. Container
local postgres setup session uses existing authentication, not a copied password.
Create fixture schemas a/b and grant the existing grepbit_ro only CONNECT,
USAGE/SELECT there. No ALTER ROLE, new account, customer-data mutation or cleanup
of pre-existing objects. Retain the isolated fixture for reproducible acceptance.

The fixture is ordinary persistent catalog data, not TEMP/CTE or a mocked query:
a.child.parent_id (TEXT) -> b.parent.id; a.parent is a same-key/different-label
decoy. Include same-schema single-PK and non-PK UNIQUE links. Original production
introspector/inference must omit the cross-schema edge, retain its raw source key,
avoid sampling it at limit 8 while sampling ordinary TEXT, and not rediscover
the decoy through containment. Clear the in-memory raw-key metadata only in a
negative diagnostic to demonstrate that the tempting wrong inference exists.
Use readonly grepbit_ro sessions and two search_path orders. No model calls.

Existing contract tests supply the policy ruler; this changes no public schema,
query support or production boundary. Setup capability was verified read-only:
target DB absent, postgres local setup usable, grepbit_ro has no superuser,
CREATEDB or CREATEROLE attribute. Implementation is the fixture and its verifier.

## B. Finite request contract v1, research only

Freeze BEFORE measuring the candidate. One English-only grammatical production,
no Stanza/model/dependency, no datasource names in parsing logic:

`Return|List|Show [only] the <columns> column[s] of every|each <table> record|row,
preserving repeated values and NULL, in <column> order[, limit <1..200>][.]`

Columns are exact ASCII schema identifiers (optionally table-qualified), ordered
comma/and lists, all on the unique exact base table. No aliases, stemming, fuzzy
names, quoted labels, extra modifiers, filters, units, joins, aggregation or
mixed-language acceptance. Match original text in full, case-sensitive identifiers;
fixed command words/grammar literals are case-insensitive. Entire unmatched
requests are unknown, not partially consumed and not rewritten.

Extract base/projection/no-filter/no-dedup/NULL-preservation/ascending single-key
order/optional limit independently from the original question and visible schema.
Compare the full eligible plan, not only projected columns. An omitted explicit
sort is equivalent ONLY when the requested order is the entire visible sole PK
that the row compiler adds. Other implicit tie-breakers are allowed only behind
the requested key. all_columns or extra clauses do not receive an exemption.
Any relevant segment (base or reachable parent), named/excluded segment input,
or unrepresented policy/default restriction returns unknown; do not construct a
SQL equivalence engine. In this v1, unrestricted population is the only certified
scope. Visibility and compiler checks remain prerequisites, not replaced gates.

The candidate may exempt ONLY the exact leading output-command occurrence of a
matched concept. Any other occurrence of that concept anywhere in the original
question, including identifiers, keeps that concept's original check. Existing
non-target gate decisions are untouched. Outcomes: match / mismatch / unknown.
No full-answer correctness, universal NL parser or intent certificate claim.

## Frozen evaluation and cost

- At most one grammar, three command lexemes, 150 nonblank recognizer/checker lines;
  no new rule after looking at measured outcomes. Implementation bug fixes must
  preserve the frozen grammar and rerun to fresh evidence; no silent v1 retuning.
- Offline authored controls: exact forms on two fictional renamed schemas;
  same-question wrong projection/filter/order/limit/base/aggregate plans; negation,
  command+business uses, quoted headings, fragments/mixed language; segment/default
  unknown. Stored actual 35-case parent-row panel used intact for gate replay;
  full earlier 55-case row-integration manifest used intact for recognition only.
- Predeclared target false blocks: kind_minutes_records (rows), svc_units_en
  (count plus distinct), and output_en (transaction count). Their family overlap
  is explicit; no claim they are three new users or live observations.
- Report authored mechanism coverage separately from untouched retained questions;
  target recovery separately from recognition, new wrong releases separately from
  already-passing wrong plans. Preserve original rejection and proposal labels.
- Continue candidate only with zero new known-wrong release, matched actual target
  proposal, and evidence of recovery beyond the one familiar minutes-row request.
  If it only rescues that request or needs more grammar rules, stop this candidate
  and keep production unchanged. Success on generated templates cannot override
  this usefulness stop. No Gemma calls, no production imports from the prototype.

Artifacts: `.artifacts/catalog-finite-gate-20260915/`. Freeze source/test/probe
hashes during each measurement. Catalog can close even if B is stopped. One broad
offline closeout gate for any new tracked evaluation/test code; no redundant suite.
