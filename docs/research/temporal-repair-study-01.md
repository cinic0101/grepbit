# Preserve precise instants during repair: promising bounded evidence

2026-09-15, baseline `ccb91de`. Generic timestamp representation guidance fixes
the observed precision failures on a small panel. A separate deterministic guard
blocks five unfaithful repairs on exact-output replay, but cannot fix initial
generation mistakes. **Research only; no runtime or Web-default promotion.**

[Protocol and authority](../plan/temporal-repair-study.md),
[durable evidence](../../evidence/temporal-repair-study-01.json).
Artifacts: `.artifacts/temporal-repair-20260915/`.

## Method and corrected oracle evidence

13 authored/seen cases: 11 answerable and two missing-definition refusals,
synthetic IoT and Service, multilingual precise intervals, date boundaries,
fractional seconds, UTC-equivalent bounds and without scope. No blind holdout.
Unchanged v15 and `time-precision-guidance-v1` are the two live streams; each
stream's exact raw replies are replayed through shared `ask()` with the guard.
Guard replay uses no model calls and is not a fresh independent success.

Gemma 4 31B, serial T=0, thinking off, 30-second request control. Independent
SQL executes against read-only PostgreSQL before calls; actual compiled plans
also execute on isolated DuckDB boundary witnesses. No DB writes, customer
rows, SQL/gold plans sent to the model, or additional business vocabulary.

One scalar Service witness was insufficient: adding records before the intended
start exactly cancelled dropping records before the intended end. Both exact
Feb 2 noon–Feb 5 noon and rounded midnight intervals counted three. Original
`main/results.json` remains unchanged and records that false pass. The append-only
`corrected-replay/results.json` adds independent start/end instances:

| Instance | Exact reference | Recorded baseline plan | Guided plan |
|---|---:|---:|---:|
| Start boundary only | 1 | 2 | 1 |
| End boundary only | 3 | 1 | 3 |

The same plan must match both instances. These witnesses were added after seeing
the cancellation, so this is a diagnostic correction, not prospective holdout
evidence. Two offline tests pin their distinguishing power. Initial replay setup
lacked required model settings and stopped before DB/model access; the corrected
run made zero model calls. No old score was silently overwritten.

## Main results: corrected multi-instance values

| Outcome / 13 | v15 live | v15 + guard replay | Guidance live | Guidance + guard replay |
|---|---:|---:|---:|---:|
| Correct answer | 4 | 4 | 11 | 11 |
| Wrong answer | 6 | 1 | 0 | 0 |
| Necessary refusal | 2 | 2 | 2 | 2 |
| Invalid-output / failed repair | 1 | 6 | 0 | 0 |

Original v15 score before the witness correction was five correct, five wrong,
two necessary refusals and one failure. The guard does **not** turn failures into
successful refusals. It prevents five wrong repairs, retains four correct
answers, and leaves the first-generation inclusive-date mistake untouched.
Of the five stopped repairs, three have changed explicit anchors; two are
unverifiable because the invalid draft does not resolve all required identities
or timezone information. This distinction matters for future false-block tests.

Guidance teaches an existing representation: timezone-aware instants belong in
typed timestamp filters; date-only range scopes must not be repaired by removing
the time. No compiler or public RangeScope changes are needed for these cases.
All guided live plans bypass this specific repair guard, so live evidence does
**not** establish how often valid temporal repairs are retained. That behavior
is covered by deterministic two-turn tests, not a fabricated live denominator.

## Fresh-process repeat and limits

Three controls were selected before the main results: precise noon, timestamp
without and missing MTTR. Baseline again gives one wrong answer, one invalid
output and one necessary refusal. Guidance gives two correct answers and the
same necessary refusal. Exact-output guarding blocks the wrong baseline repair;
it cannot rescue the already invalid without output.

Main: 32 actual calls (26 initial + six repairs). Repeat: eight calls (six initial
+ two repairs). Total **40/96**. No transport failures were reported; model
validation failures remain operational failures in the outcome accounting.
No source edits during either live phase. The guard-only malformed-identity
robustness fix between phases is explicitly recorded, not a prompt revision.

This is not intent certification: a faithfully preserved draft may itself be
wrong. The guard only covers recognized timezone-aware endpoints in invalid
plan/without range scopes, not all filters, ambiguity, unreadable JSON, other
measure changes, or first-pass mistakes. Its bounds compare effective same-column
restrictions, so retaining a literal alongside a stronger rounded constraint does
not pass. Missing identities/zones are not guessed. A safe decline remains legal.

## Validation, boundaries and next step

23 focused tests pass, including equivalent UTC/midnight forms, scope/operator/
column protection, stronger versus redundant bounds, real two-turn repair and
decline paths, malformed identity, and independent scalar witnesses. The malformed
identity ruler first failed at the intended exception (20 passed, one failed),
then passed after a research-only fix. Final offline gate: **2,058 tests, zero
skips**; static passes. Exact result hashes are in the durable evidence manifest.

No production source, evaluation acceptance policy, API, persisted schema,
security boundary or identity-binding contract changed. The new guard and prompt
are isolated under `evals/`. Pilot validation prevented a fixture coincidence
from being misreported as a false guard block or a correct answer.

Next, freeze this guidance and the earlier composition candidate and run a wider
paired **baseline / guidance / composition / combination** regression on rows,
aggregates, without, ordinary dates and missing definitions. Include boundary
witnesses, retain separate wrong-answer/failure/refusal counts, and do not add an
independent router without evidence. Prioritize unseen question collection for
generalization. Japanese rows+without and the Return gate remain separate gaps;
passing this small temporal panel does not resolve them or authorize promotion.
