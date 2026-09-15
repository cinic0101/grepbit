# Unique-parent row projection: pending contract

2026-09-15. Baseline 8cc6189; root is the sole writer.

## Authority and current boundary

Owner approved the preceding next-step plan with 「同意 可以開始」. Earlier
grants permit local commits and readonly synthetic PostgreSQL / existing Gemma
calls. No push, customer writes or restart of the owner's Web. This slice needs
no external calls. The newest supplied AGENTS requires a two-phase contract
checkpoint; parent projection stops at rulers until explicit follow-up.
The independently authorized HTTP failure-context repair is not a new meaning.

## Proposed first contract

- A rows query still means one output row per matching base record. Add columns
  from at most one other table, reached by exactly one declared, non-inferred,
  single-column FK to that parent's sole primary-key column. No self joins,
  multi-hop, reverse/child joins, multiple candidate paths or unique-key guessing.
- Projection alone uses LEFT JOIN. Missing parent yields NULL; no deduplication,
  fan-out, implicit parent filter or dropped base records. Existing reviewed
  population/segment restrictions remain meaningful and must not be stripped.
  Before promotion, explicitly test their interaction with the added join.
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
- Existing schema/compiler/policy/grounding/executor remain the owners. No raw
  SQL from the model, new query system, router, vocabulary exceptions or wider
  visibility permission. The final-proposal kind guard is not draft protection.

## Rulers and implementation exit

`tests/contract/t0/parent_rows_pending.py` is explicitly invoked, deliberately
outside normal `test_*.py` discovery while the contract is pending. It is not
xfail-masked. Report its red result separately from the current-runtime gate;
rename it into standard discovery during implementation.

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
