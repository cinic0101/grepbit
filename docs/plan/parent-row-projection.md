# Unique-parent row projection: approved implementation

2026-09-15. Baseline 8cc6189; root is the sole writer.

## Authority and current boundary

Owner approved the preceding next-step plan with 「同意 可以開始」. Earlier
grants permit local commits and readonly synthetic PostgreSQL / existing Gemma
calls. No push, customer writes or restart of the owner's Web. The initial ruler
slice needed no external calls. Under the newest supplied AGENTS, it stopped at
the two-phase contract checkpoint before the explicit follow-up below.
The independently authorized HTTP failure-context repair is not a new meaning.

Follow-up authority: owner explicitly approved this checkpoint with 「同意，也
review 下另一個 agent 的 comment」. The three review clarifications below are
included in implementation, not a request for arbitrary JOIN expansion. Root
continues sole ownership; the configured delegation packet template is absent,
so no implementation delegation is used. Artifacts: `.artifacts/parent-rows-impl/`.

## Approved first contract

- A rows query still means one output row per matching base record. Add columns
  from at most one other table, reached by exactly one declared, non-inferred,
  single-column FK to that parent's sole primary-key column. No self joins,
  multi-hop, reverse/child joins, multiple candidate paths or unique-key guessing.
- Projection alone uses LEFT JOIN. Missing parent yields NULL; no deduplication,
  fan-out, implicit parent filter or dropped base records. Existing reviewed
  population/segment restrictions remain meaningful and must not be stripped.
  Before promotion, explicitly test their interaction with the added join.
  The preserved population is AFTER existing filters, reviewed segments and
  exclusions, BEFORE LIMIT/serving truncation. The one-parent limit applies to
  newly projected sources, not existing population JOINs. Self-check receives
  population provenance separately from the SQL being checked.
- Base filters, unprojected base sorting, stable primary-key ties, NULL placement,
  LIMIT and truncation remain unchanged. Parent filters/order and rows+without
  remain unsupported. `all_columns` means visible base columns only.
- Base output names stay unchanged. Every parent output is `table.column`, quoted
  as one SQL output alias. This avoids collisions without changing earlier keys.
  Refuse an alias exceeding PostgreSQL's 63-byte identifier limit; do not truncate
  or silently rename it into a possible collision.
  Hidden parent tables, projected fields or join keys are not available.
- PostgreSQL introspection must not flatten composite or cross-schema FKs into
  apparently local single-column edges. The current schema cannot represent
  these losslessly. Exclude them rather than using them as uniqueness proof;
  revalidate aggregate compatibility as this affects the common schema feed.
  Keep legal local single-column FK-to-UNIQUE edges in that feed: the PK-only
  restriction belongs to projection eligibility. Retain original FK columns as
  metadata for sampling/policy proposals and to prevent reinference of an omitted
  composite/cross-schema edge. Default instructions stay unchanged, but affected
  datasource schema context and schema digest can change; report separately.
- Reject rows when base/used parent relations expand inheritance descendants;
  table-local PK/FK metadata does not prove uniqueness over that expansion.
  Do not silently add ONLY or drop inherited rows. PostgreSQL documents this at
  https://www.postgresql.org/docs/current/ddl-inherit.html#DDL-INHERIT-CAVEATS .
  Capture `has_inheritance_children` and original `foreign_key_columns` from the
  catalog; fixtures may assert their own schema facts. Fresh introspection is
  required; this is not protection against concurrent schema DDL.
- Existing schema/compiler/policy/grounding/executor remain the owners. No raw
  SQL from the model, new query system, router, vocabulary exceptions or wider
  visibility permission. The final-proposal kind guard is not draft protection.

## Rulers and implementation exit

The initial `parent_rows_pending.py` ruler was explicitly invoked outside normal
discovery, without xfail masking. It was renamed to `test_parent_rows.py` upon
approval and is now part of the normal gate. Historical red counts remain
separate from current passing implementation tests.

Rulers cover shared parent / NULL parent / empty parent, duplicate base records,
same-name outputs, filters/order/LIMIT, parent-only projection, visibility,
unsupported relationships, base-only all-columns and self-check projection.
Join mutation rulers reject INNER, wrong-key, CROSS and extra joins. A separate
executed reference witness distinguishes INNER JOIN and DISTINCT from the intended
LEFT JOIN bag semantics even while the production parser still rejects parents.
The introspector test is a static contract assertion, not a DB execution proof.
Existing blanket rejection makes negative controls pass; this does not prove
their future enforcement once parent projection is enabled.

After approval: implement unique-parent compiler and independent self-check;
add mutation tests (INNER JOIN, wrong ON, duplicate join, dropped key) and catalog
execution controls for composite/cross-schema constraints. Keep default/fallback
messages unchanged; version only the explicit rows extension and measure it.
Reuse existing typed oracle/witness tooling, not a second evaluator.

Freeze schema, source/tests/probes, prompts, cases and oracles before live work.
Compare parent projections on readonly IoT and service fixtures against independent
SQL, plus multiple in-memory instances (NULLs, duplicates and limit boundaries).
Re-run the 24-case explicit-mode panel and Default refusal/without controls;
separate actual row-kind selection from correct equivalent answers. Maximum 100
serial Gemma attempts including repairs, repeats and HTTP/MCP acceptance; stop
after two transport failures. Any recurring new population/definition regression
blocks planner promotion, without reopening the closed time work.

No broad auto-routing study now: saved results first determine residual errors
under known entry selection. Historical cross-run composition is a diagnostic,
not new model accuracy, causal improvement or a deployable router.

## Completed implementation and bounded acceptance

The approved ruler is now `tests/contract/t0/test_parent_rows.py` in ordinary
discovery. Review-added controls cover existing segment joins (same/different
parent, lifted exclusions, inferred population without granting projection),
inheritance, hidden keys/tables and alias limits. A PostgreSQL TEMP-fixture probe
with grepbit_ro validates real PK/UNIQUE/composite/inheritance catalog behavior;
no persistent objects or roles changed. Cross-schema negative fixtures remain
mocked, not an actual cross-schema DDL execution claim.

35 live questions: 20 correct answers, 14 appropriate refusals, one known gate
false refusal, no wrong answers or operational failures. Five predetermined
repeats preserve the result pattern. Actual HTTP/MCP: 35 exact-response replays
and six fresh requests (four correct/two appropriate refusals). 61/100 physical
Gemma attempts total; zero transport errors. v20 explicit messages match the
candidate on all 35 cases; 110 existing Default/fallback contexts unchanged on
these fixtures. This is bounded known-case evidence, not generalization.

Ten of 32 Details questions needed one repair for redundant top-level columns;
report that overhead instead of adding a silent discard rule or changing the
shape_variants denominator. Keep the new-construct freeze and address wire/repair
health as a separate next decision. No further construct added in this slice.
See `../research/parent-row-projection-01.md` for full evidence and non-claims.
Final static and 2,286 offline tests pass (zero skips); 136 runtime-focused and
209 schema-compatibility checks pass. Original Web remains untouched; local
commit only, no push.
