# Next owner holdout: ready for intake, awaiting new questions

2026-09-14, baseline `a759a54`. Owner authorised the next step after the
gate-exposure audit. Root owns preparation; no worker, production change or
new model/DB calls. Existing local commit authority applies; no push.

## Current stop

The inspected case/question entry points under `evals/cases/` and `.artifacts/`
are the already-used POS holdout, Holdout2, Holdout3 and ratio cases. Existing
service and service-adversarial sets are authored fictional cases, not unseen
owner questions. No provenance-confirmed unused non-POS owner set was found
in these entry points; this is not a claim to have inspected every possible
external source or arbitrary file. Do not open potential new question text
merely to decide whether it looks new.

The original latest approval permits preparing and running the next measurement;
it cannot supply missing questions or their intent. Do not fabricate an owner
holdout, relabel old translations, or repeatedly sample known failures instead.

## Small input needed

Prefer 15–25 naturally phrased, previously unsubmitted questions from a user or
domain colleague, linked to one existing consented datasource, e.g. service_test,
iot_spike or the HR portion of pos_test. This is a collection target, not a
minimum required to start. Include naturally used English/Japanese where possible;
do not ask a model to translate known failing questions and call them independent.

Provide a private UTF-8 file with one question per line, plus datasource ID and
the intended reporting date/as_of. Use a non-sensitive filename. Exclude real
personal names, member IDs and other PII. Separate from questions, identify
origin, author-confirmed lack of prior exposure, any reviewed business definitions,
and an available domain reviewer. A new datasource or unapproved data transfer
requires its own scope, not an automatic extension of this preparation.

## Reuse the existing workflow

1. Before viewing questions or outputs, freeze current runtime/prompt/overlay,
   model settings, reporting date, source-file hash and case count. Compare exact
   question hashes against retained cases locally without printing text. Exact
   nonduplication cannot prove semantic-family novelty; retain provenance caveats.
2. Convert with `evals/questions_to_cases.py` into a **new** ignored artifact
   directory. Assert destination does not exist: this legacy tool overwrites its
   output. Its boilerplate comment does not prove blindness; the work record does.
   Preserve judged mode, no expected status or invented answer labels.
3. Freeze a one-pass baseline schedule before calls. Reuse the metrics-only
   output boundary; `--redact-rows` alone is insufficient. Capture enough safe
   identity for independent review without exporting private literals. Only then
   record exact endpoint, opaque credential variables and bounded call budget.
   No gate-off arm or prompt intervention is authorised merely by a baseline.
4. Judge intended unit, scope, denominator and time basis independently of model
   choices. Apply the existing disclosed-answer policy, allowing reviewed reasonable
   readings. Verify answer values via independent SQL where available. If such
   annotations were not frozen before the run, label review retrospective rather
   than prospectively oracle-scored. Unknown judgments remain unknown.
5. Report correct answers, wrong answers, necessary/false refusals, unassessed
   cases and operational failures separately, by datasource/language/family.
   Diagnose a new confirmed failure before proposing an intervention. Once read,
   this batch is development data; reserve another unseen set for generalization.

Preparation validation uses only synthetic strings and existing converter/runner
tests, not a new evaluation contract or model-accuracy result. No new framework,
public format, safety boundary or identity binding is introduced. Runtime remains
v15 / ask v5. Formal holdout execution waits for the owner's new input file.

## Preparation evidence

Three synthetic converter checks and 19 existing runner contract tests pass;
static passes. Artifacts are under `.artifacts/owner-holdout-intake-20260914/`,
with hashes in `../../evidence/owner-holdout-intake-01.json`. No broad suite or
live experiment was rerun for this documentation-only preparation. The missing
input, not a checkpoint or tooling failure, is the remaining prerequisite.
