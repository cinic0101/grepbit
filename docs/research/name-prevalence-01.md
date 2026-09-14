# Retained user questions: name-policy exposure and cost

2026-09-14, baseline `fda7d81`. Protocol and authority:
[`name-prevalence-study.md`](../plan/name-prevalence-study.md).
Counts/hashes: [`name-prevalence-01.json`](../../evidence/name-prevalence-01.json).
Private artifacts: `.artifacts/name-prevalence-20260914/` and
`.artifacts/name-prevalence-analysis-20260914/`.

## Decision

Do not introduce a stricter production name policy or run another prompt round
for the collision family now. The previous authored failures remain real, but
this retained user corpus supplies no measured rescue opportunity for that narrow
policy. Broadening the policy exposes substantial previously accepted behavior.
Keep existing exact/unique grounding and collision refusal mechanisms; no guard
is removed, no automatic union is approved, and no new identity contract enters
production. A5 remains open.

Reduce this research line's priority to fixed failure sentinels and new-real-case
collection. This is an allocation decision under limited evidence, not a claim
that name ambiguity is solved or absent in the product.

## Population and historical evidence

| Retained owner set | Questions | Selected historical artifact | Prompt |
|---|---:|---|---|
| Batch1 | 50 | product-baseline-20260913/live/batch1.json | v15 |
| Holdout2 | 30 | holdout2/run-26.json with verdicts-26.yaml | v14 |
| Holdout3 | 15 | holdout3/run-13.json with verdicts-13.yaml | v14 |

Artifact paths in the table are relative to `.artifacts/`. Case text is loaded
locally but never printed or copied into this report. All 95 question/datasource
identities are distinct under exact hashing; case, whitespace and punctuation
inside names are not normalized for deduplication. Cases and verdicts join by
ID, question/hash and status, and verdict files point to the selected report.
No best-run selection, repeated model sampling or score changes.

These are retained **owner-written tests**, not author-generated synthetic cases,
but also not a representative traffic sample. Holdout2 deliberately targets name
variants and Holdout3 missing constructs, as their original research records
state. They are seen development data now, not a new holdout or a source of a
population failure-rate confidence interval.

The historical files contain 81 answers and 14 refusals. Evidence levels are kept
separate: 47 historical reference matches, 33 historically judged correct answers,
one historically judged wrong answer, and 14 historically accepted refusals.
Different revisions and past oracle limitations prevent interpreting these as
current accuracy. In particular, historical holdout2 verdicts are not fresh
independent verification of ratio values.

## Current public name catalog

Read only the existing reviewed public/groundable columns from the consented POS
database, with `grepbit_ro`, schema sampling 0 and distinct cap 5000 per column.
The overlay whitelist is checked before values are loaded. None are skipped.

| Column | Distinct stored values | Normalization collision groups |
|---|---:|---:|
| category.category_name | 14 | 0 |
| pos_payment.payment_method | 12 | 0 |
| product.product_name | 720 | 2 |
| store.store_name | 5 | 0 |
| transfer_status.status | 4 | 0 |
| Total | 755 | 2 |

The two groups contain four distinct product-name spellings. Thus collisions
exist in real data, not only the fictional depot example. Values, normalized
strings and the spellings themselves are not persisted or published.

Against this catalog, the corpus has 24 questions with existing candidate hints
(batch1:2, holdout2:20, holdout3:2). Zero questions match a collision group's full
normalized spelling, and zero source occurrences remain normalization-ambiguous.
The separate selected-literal audit also finds zero historical public filters
selecting collision members among the81 covered answers. These extra checks
prevent conflating exact selection within a collision group with unresolved
ambiguity, or overlooking a selected name merely because the question used a
shorthand. Unselected/unrecognized shorthand still cannot be ruled out.

## Counterfactual policy exposure

These predicates are computed locally, not inserted into production `ask()`.

| Hypothetical policy | Flagged cases | Affected historical answers | Historical evidence for those answers |
|---|---:|---:|---|
| Reject any normalized-ambiguous source occurrence | 0 | 0 | No opportunity observed |
| Reject whenever one column has multiple flat name candidates | 5 | 5 | All labeled correct in holdout2 |
| Reject a selected public-name literal not appearing exactly in the question | 14 | 14 | All labeled correct in holdout2 |

The five and fourteen sets are disjoint. Their labels are evidence of potentially
lost accepted behavior, **not 19 freshly proven false refusals**. The one historically
wrong answer is not flagged by these policies; no known historical wrong-answer
rescue is demonstrated. The prior synthetic normalized-set counterexamples
remain the independently checked false-refusal evidence.

The five multi-candidate cases have multiple separate source occurrences on the
same column; a flat catalog alone cannot justify treating them as one unresolved
entity. The fourteen non-verbatim selections include the designed name-variant
family; a selected stored string absent from the original wording is not itself
an error. It may result from accepted grounding or an alias. Requiring verbatim
selection would restrict that capability rather than merely harden identity.

The identities are available privately for targeted follow-up without republishing
questions: multi-candidate holdout2 q22,q26-q29; non-verbatim q02-q05,q08-q11,
q13,q15-q17,q23,q25. No new judgments are assigned to them here.

## Coverage boundaries

- Source occurrence mapping is available for 95/95 questions **under the five-column
  public catalog**. This does not imply all entity mentions were recognized.
- Selected public-filter evidence is available for 81/81 historical answers.
  Batch1's sanitized literal lists are recovered only on exact hashes against
  bounded current public candidates; unmatched hashes would remain unknown.
  Holdout2/3 plans are read locally without copying raw text or literals.
- Six historical refused requests lack usable plans. They are explicitly
  unavailable for plan-based analysis, not zero-risk answered queries.
- Eight retained results contain filters outside the five-column audit. Some
  may be ordinary non-name conditions; no claim of name/PII coverage is made.
  Salesperson names and member IDs are not loaded from the DB or emitted.
- The catalog is current, the questions/results historical. Equal start/end
  hashes show no observed catalog drift during the checks, not historical
  snapshot identity or a transaction spanning all historical executions.
- DISTINCT stored values cannot establish whether identical names belong to
  different entity IDs. Partial/fuzzy ambiguity, omitted filters, business
  concepts and unsupported scope are not exhausted by normalization collisions.

## Verification and safety

Fourteen audit contract tests and three summary tests pass: exact deduplication,
same-column collision handling, exact-source precedence, unavailable-versus-zero,
hash recovery, scoped filter traversal, mismatched joins and output privacy.
The initial direct-script import failure occurred before DB access, was fixed,
and the preflight rerun; it is not a product failure or a red behavior ruler.

Fresh static verification passes. Production/evaluation source remains unchanged;
the matching 1,841-test offline gate is reused by source and artifact hash, not
rerun or presented as new tests. Source files, selected inputs, overlay, catalog
and helper hashes bind the results. No historical file is rewritten.

Zero Gemma calls; no model/server receives this corpus. PostgreSQL access is
read-only schema plus the five public-name columns; no credentials are printed
or copied, no new account or persistent DB state is created. All new artifacts
are counts, fixed codes, safe IDs and hashes. Error handling suppresses exception
text so database details cannot leak through failures.

## Next order

1. Keep the authored collision and explicit-set controls as sentinels; revisit
   when a new real request encounters the problematic selection, not merely to
   obtain a better score on the same names.
2. Prioritize independently trustworthy oracles and reproducible wrong-valid
   business scope/metric cases. Do not treat old holdout2 ratio labels as current
   proof, or retry solved/ceiling cases to manufacture an improvement.
3. Measure any future name-policy tradeoff against both accepted partial-name
   grounding and explicit sets. A restrictive fallback needs a declared product
   scope and measured cost; it must not be smuggled in as a lexical repair.
