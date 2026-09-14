# Database-aware authored baseline (2026-09-14)

## Scope and authority

The owner requested database-derived questions, then said "可開始下一步" after
the 24-question bank was prepared at `689baca`. Existing explicit authorization
covers needed psql/Gemma calls, autonomous research checkpoints and local commits;
not a push. This slice measures that unchanged authored bank. It does not tune
production, prompts, gates, overlays or historical scores.

Use the existing fictional service and IoT databases, SELECT-only `grepbit_ro`,
opaque DSN environment variables and ignored gateway key. No administrator role,
database writes or personal/customer database. Model destination is the existing
Gemma gateway; only question, schema, existing reviewed overlay/public candidates
and normal planning instructions go out. Gold plans, SQL, foils and result rows
remain evaluator-side. No raw completions, reasoning, secrets or rows in evidence.

## Frozen protocol

- Original 14 service / 10 IoT cases, explicit as_of from the bank, sampling 0,
  `--redact-rows`, actual `evals/spike_tier0.py` / `ask()` path, gates unchanged.
- `gemma-4-31b`, prompt v15, temperature 0, thinking off, 20-second initial
  deadline, one existing validation repair. Serial, at most 24 initial requests
  and 48 actual model calls. Disable transport retries; stop after two transport
  failures or source/input/schema/data drift. No success-seeking repetitions.
- Before planning, freeze source/input/overlay/schema hashes, all 20 typed golds,
  independent SQL and differing foils; repeat read-only checks at the end.
- Keep legacy value matching separate from `disclosed-answer-v1`. Each answerable
  case has its existing authored gold recipe, full values and disclosure checks.
  Rules stay open: an unlisted recipe is unassessed, not automatically incorrect.
  Subsequent manual semantic analysis is separately labelled post-hoc, never
  substituted into the frozen score. No arbitrary dropping of extra columns.
- Four refusal controls retain their original preferred and accepted statuses.
  Also report the existing broader refusal-only rule separately. A wrong refusal
  reason is not proof of correct understanding even if its status is accepted.
- Report correct answers, known wrong answers, necessary refusals, unnecessary
  refusals, unassessed answers and operational failures separately. Correct/all,
  answered/all and known-wrong/answered cannot be replaced by a total pass rate.

## Execution and closeout

Private driver, tests, preparation, per-case sanitized traces and summaries live
under `.artifacts/db-aware-baseline-20260914/`; the prior bank stays immutable.
Focused tests cover budgets, leaks, unknown interpretations and exclusive writes.
Use static validation at closeout; reuse source-identical offline evidence if
available because runtime is unchanged. Record actual calls, errors, case counts,
hashes, limitations and next decision in a research note and counts-only manifest.

These are data-aware author challenges, not unseen owner questions or a product
generalization estimate. Completion means an honest baseline and failure
classification, not improving its score during this run.
