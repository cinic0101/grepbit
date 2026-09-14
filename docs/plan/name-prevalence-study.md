# Retained-user name-policy exposure audit (2026-09-14)

Root owns this slice at `fda7d81`. The owner approved the proposed next step
and previously delegated in-scope checkpoints, psql/Gemma and local commits.
No push. Scope is measurement, not a production policy or evaluation rewrite.

## Frozen populations and evidence levels

Use exactly three retained owner-question sets: batch1 (50), holdout2 (30),
holdout3 (15). Deduplicate by exact question plus datasource, preserving case,
punctuation and distinct name spellings. Keep batch results separate. These are
seen, deliberately designed tests, not a random product-traffic sample.

Use the existing product-baseline batch1 result and fixed historical holdout2
run26 / holdout3 run13 results. Validate case identities and any verdict joins;
do not select a different run because it looks better. Historical reference
matches and verdict labels remain historical, not fresh value verification.
Unknown correctness and different prompt/runtime revisions stay visible.

Measure separate signals: current same-column normalization collisions in the
authorized name catalog; collision exposure at source occurrences; multiple
flat candidates on one column; multiple distinct source mentions; unresolved
historical bound literals and withheld-column coverage. A matched occurrence or
fuzzy alternative is not a confirmed semantic ambiguity. A missing index or
withheld personal column must never be counted as zero risk.

Counterfactual policies: reject any ambiguous normalized occurrence; reject any
multi-candidate column; reject any selected public-name literal not appearing
exactly in the question. Report affected historical answers, their evidence
classes and unknowns, not a claimed live rescue. Keep source-based and plan-based
denominators distinct; hashed-only plans cannot supply unknown raw literals.

## Root checkpoint and privacy

Root approves the audit contract: independent fictional tests pin deduplication,
same-column collisions, exact-over-normalized precedence, missing-catalog versus
zero hits, unrelated columns, incomplete/unknown result joins, and no raw data in
output. A checkpoint test of this observational contract does not need to pretend
that production should already implement it. No acceptance scores are changed.

Existing consented real POS database, `grepbit_ro` only: inspect schema with sample
limit0; load only these five currently reviewed public/groundable columns into
process memory: category.category_name, pos_payment.payment_method,
product.product_name, store.store_name, transfer_status.status. Cap5000 per column,
bounded SELECTs and statement timeout. Verify the overlay and schema before reads;
no salesperson names, member IDs or other stored columns are queried. No persistent
DB writes. DSN remains an opaque shell variable; no new credential copies.

This narrower DB read is for the owner's authorized real-corpus measurement;
the previous synthetic-only call scope is not reused as permission. The source
authority is the owner's approval of this next step and existing consent to this
DB, with read-only psql explicitly delegated in the preceding turn.

No Gemma calls needed (budget0), no rows/schema sent to a new provider. Existing
private questions/reports are processed locally without printing raw fields.
Artifacts contain only counts, fixed codes, hashes and safe case IDs; no original
questions, stored names, normalized names, plan literals, SQL or verdict notes.
Errors suppress exception text. Helpers live in `.artifacts/name-prevalence-20260914/`.

Stop on identity mismatch, unapproved columns, caps, drift or unsafe persistence.
Publish partial/unknown coverage explicitly rather than widening data access.
If the candidate policy has no measurable opportunity in this retained corpus,
do not manufacture examples or rerun Gemma to create an improvement. Keep the
previous authored collision failures as regressions, not estimated prevalence.

## Closeout

Fourteen audit tests and three counterfactual-report tests pass. The direct CLI
initially failed before DB access because its repository import path was missing;
the helper was fixed and preflight rerun before the successful audit. This is not
checkpoint or product-failure evidence. No Gemma calls were needed.

95 distinct retained questions; five authorized columns hold 755 distinct values.
There are two normalization collision groups (four values), both in product names.
Neither their complete normalized names nor their members in historical selected
public literals are encountered in the measured corpus. Supplementary source and
literal checks use the same catalog hash and preserve the original audit.

The narrow occurrence-ambiguity policy flags zero cases. Broader same-column
multi-candidate and non-verbatim-selected-name policies flag five and fourteen
historical answers respectively, all previously labeled correct in holdout2.
These labels are not independently revalidated numeric correctness; no score is
rewritten. Source coverage is 95/95 under the public catalog; plan coverage is
81/81 historical answers, with six plan-unavailable historical refusals. Private
columns, unseen shorthand and entity identity behind duplicate identical strings
remain outside the measurement.

Root decision: do not narrow production name policy or start another Gemma prompt
round on this evidence. Retain collision safeguards and the authored failure
sentinels, lower this research priority, and require new real-question exposure
or a specifically measured incremental candidate before reopening it. This is
not proof of zero product risk, nor a fresh estimate of deployment accuracy.
