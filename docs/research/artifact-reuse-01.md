# Retire calculation cards; reuse existing evaluation evidence

2026-09-12. Owner request: remove calculation cards, keep the codebase clean,
and assess existing `.artifacts` tests together. No new model/PostgreSQL call,
production change, historical rescore, participant workflow or push.
Evidence: `evidence/artifact-reuse-01.json`; detailed private index and one-off
scanner: `.artifacts/card-retirement-20260912/inventory-v2.json`, `inventory.py`.
The index records input file hashes and metadata/counts, never questions, plans,
bindings, rows or verdict notes. It excludes its own task directory.

## Cleanup and retained repair

Remove the unfinished, uncommitted renderer, editor, confirmation session and
display fixture/test. An ignored archive preserves all four uncommitted files:
`.artifacts/card-retirement-20260912/uncommitted-card-backup.tar.gz`.
Remove the committed card-only ruler test and fixture from the active suite;
both remain recoverable at `0d58029`. Mark the old plans/report historical rather
than erase their evidence. No human study took place.

Retain the reference evaluator's independently useful segment repair. Named
segments still exclude their rows from nonreferencing ratio operands; shared
metric predicates must retain their original references before moving to row
scope. Ten hand-valued scenarios on three fictional instances and two engines
now live in `test_eval_tools_contract.py`, with no card dependencies.

Test accounting: remove 275 retired card specification tests and add 60
computation regressions. The prior suite had 1,861 tests, including three known
reference failures; the final suite has 1,646 passing tests, zero failures,
errors or skips. The count reduction is intentional retirement, not masking
the reference defect. Static passes. Both final gates identify source
`sha256:e01de711a9ebb6e0da5b67fe9b6b2773184f64bc5f6abf307b6ee71c53943361`.
The earlier focused command ran 84 passing tests but its wrapper could not
identify unstaged deleted source files; it is not reported as a passing gate.
After staging those deletions, the final offline gate includes those tests.

## Inventory, not a pooled accuracy score

| Existing material | Count | Reuse |
|---|---:|---|
| Runner-format reports | 173 | Per-run recorded outcomes and status/reference checks |
| Of those, dry reports with `not_run` | 7 / 186 records | Setup only; exclude from model-quality measurement |
| Remaining runner reports | 166 / 2,027 records | Historical observations, including repeats and ablations; not independent questions or model-call counts |
| Verification reports | 130 | Code/test evidence, not NL correctness |
| Differential reports | 17 | Computation agreement within recorded coverage, not intent |
| Research reports | 27 | Analyze under each study's arms, source and scoring contract |
| Other JSON | 16 | Needs its own format/provenance review |
| Invalid JSON | 3 | Incomplete/invalid evidence; no silent success credit |

All categories account for 366 existing JSON files. Research reports include
15 with `live: true`, 10 with `live: false` and two without that flag. Mock
transport tests can set `live: true`; the flag does not prove provider calls.
Use each study's source/ledger, not a filename or flag alone.

Across the 173 runner reports, 65 verdict files were found: 33 have complete
existing judgments bound to a matching report, 27 are incomplete, and five
name a report absent from this inventory. Matching checks case-ID uniqueness
and coverage, recorded statuses and questions where present before using the
existing tally function. This reuses prior judgments; it does not independently
review their correctness, age or data snapshot.

There is one duplicate runner content fingerprint. Only 148 exact question /
datasource hashes are observable in value-bearing reports; this is a partial
count, not the corpus size, because metrics-only reports omit questions and
paraphrases/translations are not semantically deduplicated. There are 643 row
records with a plan hash but no plan across the full runner-format inventory;
they support recorded outcomes/identity comparisons, not plan replay.

None of the 173 runner reports directly records the checked source-identity
fields (`git_sha`, `source_digest`, `source_start`). Companion study/gate records
may recover provenance; the same prompt revision alone cannot establish that
compiler, gates, overlay, sampling settings and dataset were identical.

## Examples of usable historical evidence

These are explicitly named examples, not best-run selection or current release
claims. Their complete input hashes and counts are in the evidence file.

| Artifact | What the existing record actually says |
|---|---|
| `a5-20260912/v15-batch1.json` | 47 answered/reference-matched, 3 refusal passes: 50/50 recorded passes, not 50 answered questions |
| `a5-20260912/v15-features.json` | 39 answered, 37 reference matches, 2 mismatches |
| `holdout2/run-26.json` + matching verdict | 26 correct answers, 4 acceptable refusals |
| `holdout3/run-13.json` + matching verdict | 7 correct answers, 1 wrong exposed answer, 7 acceptable refusals |
| `ratios-01/run-20.json` + matching verdict | 11 correct answers, 1 acceptable refusal |

The last three use v14; the first two use v15. Do not combine them into a
single product score. In particular, an exposed wrong answer remains wrong
without relying on a user to correct it. A judged run's `correct: null` means
unjudged by the runner, not incorrect; use its matching filled verdict file.
Some `correct: true` runner cases check only allowed status, without a recorded
reference comparison. Keep those separate from value-checked answers.

## Recommended next measurement using existing material

1. Build a fixed regression panel from existing case sets; separate authored
   smoke, settled user regression, ambiguous/refusal controls and adversarial
   semantic families. No need to author a whole new corpus. Used holdouts are
   development data now, not new generalization evidence.
2. Recover source/context and gold provenance from companion records. Group by
   actual source, model/settings, overlay/schema, as_of, case content and oracle
   strength. Missing metadata stays unknown; never silently pool it.
3. Reuse existing reference outcomes and bound judgments first. Report correct
   answers, wrong answers (exposed and silent), acceptable refusals, bad refusals,
   operational failures and unjudged cases separately. Never count unknown as
   correct or silently remove it from the denominator.
4. Where full plans and appropriate fixture/context exist, replay proposals
   through current deterministic code to isolate compiler/gate changes. This is
   not new planning performance. Metrics-only or changed-context runs need a
   targeted rerun if their missing information matters.
5. Only then run the fixed panel against one frozen current source for current
   end-to-end performance. Retain every scheduled attempt and repeat; do not
   select the best run. Tune on development cases, and reserve fresh blind
   questions for a later generalization claim.

No new pooled evaluator/score definition or live sweep is introduced by this
inventory. An offline gold-label review, if needed, is distinct from the retired
product workflow that asks a user to inspect/correct each answer. Unknown labels
cannot be manufactured by asking the same model to certify itself.
