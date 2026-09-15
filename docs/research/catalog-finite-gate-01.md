# Catalog acceptance closed; finite request gate stopped

2026-09-15. Baseline `e8ff36f`; authorization and frozen protocol:
[`catalog-and-finite-gate.md`](../plan/catalog-and-finite-gate.md).
Two independent deliveries. No production source, prompt, gate, dependency,
external response format or runtime permission boundary changed. No model calls,
Web restart, push or claim of new natural-question success.

## A. Real cross-schema catalog: accepted

Created the authorized, isolated database `grepbit_catalog_boundary_v1` in the
existing PostgreSQL 17.6 container. It contains two ordinary schemas and five
fictional tables, not TEMP tables or a mocked catalog. The database is retained
for repeatable acceptance and is not registered in Web.

Setup used the local postgres container session and granted the existing
`grepbit_ro` CONNECT, schema USAGE and SELECT only. No setup credential was
copied or given to runtime. Runtime asserted its role, read-only transaction,
lack of superuser/CREATEDB/CREATEROLE and lack of database/schema CREATE or table
INSERT/UPDATE/DELETE privileges. No customer database changed.

Unmodified production introspection and inference passed with both `a,b` and
`b,a` search paths, with identical schema digests:

- Catalog FK is `a.child.parent_id -> b.parent.id`, while `a.parent` is the
  tempting same-key, different-label local table. The cross-schema relation is
  omitted, not flattened into the local relation.
- The TEXT source key remains in `foreign_key_columns`, is not sampled at
  nonzero limit 8, is not groundable, and is not inferred into a decoy relation.
- Ordinary TEXT is actually sampled. Thus a zero sampling limit cannot hide a
  lost-key regression.
- Both the same-schema single-PK target and the non-PK UNIQUE target retain
  their exact source/target table/column links.
- Negative diagnostic: clearing only the raw source-key marker in an in-memory
  schema copy causes unchanged inference to invent the wrong local relation.
  The correct and decoy parent labels differ, so the fixture can expose wrong
  values as well as wrong metadata. Persistent data is never mutated by this
  diagnostic.

This closes the previously missing actual catalog evidence, **not** support for
cross-schema queries. The fixture and reusable readonly verifier are tracked at
`evals/fixtures/catalog_boundary_v1/` and `evals/catalog_boundary.py`.
The verifier was rerun after strengthening the positive-control assertion to
include the target table as well as source/target column names.

## B. Finite request gate v1: do not adopt or expand

Frozen before measurement: one English grammar, three command verbs, exact
schema identifiers, unrestricted base-row projection, explicit preservation of
duplicates/NULL and ascending ordering, optional limit. No fuzzy names, condition
parser, business scope, aggregate, join, language rewriting or new dependency.
The recognizer/checker is 93 nonblank lines; prototype and tests stay in ignored
artifacts, not production or a new maintained parser subsystem.

Requests are derived independently of the plan. Full QueryPlan comparison checks
projection, base, filters, sort, limit and absent extra constructs. Relevant base
or reachable-parent segments, named/excluded segment inputs and unrepresented
defaults are unknown, not an inferred equivalent population. Only an exact leading
command occurrence can be exempted. A second business occurrence or non-target
concept retains its original check. Existing compiler/visibility checks remain.

### Results and denominator boundaries

| Evidence | Observation | Interpretation |
|---|---|---|
| Authored controls on two renamed schemas | 76 tests pass | Frozen mechanics, not natural-language generalization |
| Complete historical parent-row panel | 2/35 requests recognized; 22 typed plans replayed, 13 no-proposal outcomes retained | Gate-only replay, not 35 new model calls or served answers |
| Complete earlier row-integration panel | 1/55 requests recognized | Recognition only; overlaps the parent panel and must not be pooled as 90 users |
| Predeclared false-block targets | Only `kind_minutes_records` gains a gate exemption; `svc_units_en` and `output_en` remain out of scope | 1/3 historical target recovery; only one familiar request benefits |
| Actual saved minutes proposal | Matches independent projection/order request; two DuckDB witnesses each preserve four rows, duplicate values and NULL | Computation evidence for this proposal, not independent proof of all English intent |

The second recognized parent-panel request, `explicit_minutes_duplicates`, was
already correct and passed the old gate; recognizing it creates no incremental
recovery. The parent panel's historical labels remain 20 correct answers,
14 necessary refusals and one false refusal. They are not relabeled as new live
scores; the original mode-specific refusal judgments are retained.

The 22 proposals are the stored final typed plans from the original 35 cases,
not newly synthesized planner outputs. They are checked against freshly read
synthetic fixture metadata with sampling zero and the current overlay. Original
questions are unchanged; source/result/schema hashes are recorded. This is not
a claim to recreate every historical prompt or run the complete service anew.

Safety/control evidence is deliberately separate:

- Sixteen same-question wrong-plan controls cover wrong projection, extra filter,
  sort, limit, base, aggregate, extra projection and all-columns. None receives a
  new exemption. Negation, quoted labels, fragments, mixed language, hidden fields
  and segment/default uncertainty retain the original gate.
- Two additional wrong plans (one per fictional schema) already pass the old gate
  because their wrong projection mentions `return`. They still pass it: candidate
  `mismatch` is **not** a new rejection rule. Report them as existing wrong passes,
  not repaired errors and not new regressions.
- The historical 35-case panel contains no labeled wrong answers; therefore its
  zero new wrong releases alone is not evidence of broad error detection. The
  authored wrong-plan controls provide the explicit counterexamples.

Ruler history: the first stub run had four fixture setup failures (missing required
segment note), which are not policy evidence. After fixing only the fixture,
26 intended assertion failures and 50 controls passed. Implementation then passed
all 76. Two early measurement attempts stopped on the probe's incorrect compiled
SQL attribute before any gate report was written; it was corrected to
`compiled.compiled.physical_sql`. Neither failure changed the frozen grammar.

**Decision: stop this candidate, leave production gate unchanged.** It meets the
bounded controls but fails the predeclared usefulness requirement of recovering
more than the familiar minutes-row request. Do not rescue the research score by
adding count grammar, more templates or datasource exceptions. This does not
close the product's gate false-refusal problem or prove that every parser approach
is impossible. The two aggregate false-block families are still unresolved.

## Validation, impact and follow-up

Catalog accepted independently; no pending language study keeps that debt open.
Focused existing schema/policy/parent-row tests: **65 passed**. Private gate
controls: **76 passed**. Static passes; the single broad offline gate has
**2,313 passed, zero skips**. Focused/static/offline source digests agree.
Durable evidence records counts, hashes and local artifact locations.

No change to evaluation thresholds, historical scores, public formats, identity
binding, safety policies or runtime grants on existing databases. New persistent
state is only the retained synthetic catalog fixture and its scoped read grants.
The earlier raw wire variant rate remains 10/32; saving model repairs does not
erase it or release the construct freeze.

Keep using the existing interface and record new, authorized questions. Gate work
needs a materially different evidence source or an explicit product tradeoff
before another candidate; template expansion is not the default next step.
Existing Details and unique-parent projection remain usable within their accepted
boundaries. Other capability work retains its own existing acceptance/freeze rules.

Local evidence: `.artifacts/catalog-finite-gate-20260915/` (catalog-final.json,
gate-v1.json, ruler-corrected.xml, implemented.xml, focused/static/offline).
Durable counts, catalog checks and replay/probe hashes:
[`evidence/catalog-finite-gate-01.json`](../../evidence/catalog-finite-gate-01.json).
