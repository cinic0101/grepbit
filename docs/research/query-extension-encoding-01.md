# Question rendering before another intent mechanism

2026-09-14. Research-only diagnostic; production/Web unchanged.
Plan and permission scope: [encoding diagnostic](../plan/query-extension-encoding.md).
Predecessor: [query extension study](query-extension-study-01.md).

## Why this experiment precedes a new semantic interface

The extension runner used `json.dumps(payload)` for message content, rendering
Chinese/Japanese question characters as literal backslash-u escape sequences.
The gateway parses the outer request JSON, not the JSON embedded in message
content; those escapes are therefore text presented to the model. This is
valid JSON, not lost characters or a broken HTTP charset. Nevertheless, equal
decoded data does not imply equal model inputs.

Production `plan_client.build_messages` already uses `ensure_ascii=False`.
This finding concerns the new research harness, not all historical production
metric/gate failures. The previous correct-plan injection established compiler
feasibility; it did not isolate this input-format cause.

## Method

Reuse wire v2, identical rules/schema/question order, metadata, model settings,
DB oracles and compiler. Only the question string's JSON rendering changes;
even non-ASCII metadata keeps its old encoding. Five focused tests pin decoded
equality, historical byte compatibility, ASCII identity, escaping of embedded
quotes/backslashes/control characters, and question placement.

Run the frozen seen 12-case natural panel in escaped/Unicode/escaped/Unicode
order, then Unicode on the old 21-case explicit panel. Gemma 4 31B, T=0,
thinking off, serial, no retries; readonly synthetic IoT/Service, sample limit
zero. No rows or oracle SQL are sent to the model. Each run executes independent
SQL before planning. Detailed evidence is in
`.artifacts/query-extension-encoding-20260914/`; the
[value-free manifest](../../evidence/query-extension-encoding/summary.json)
retains source/panel hashes, per-case outcomes and repeat checks.

This tests the original wording, not a researcher-supplied correct routing or
rewritten question. It does not supply gold identifiers, add examples, remove
gates in production, change oracles, or introduce another LLM certifier.

## Repeated natural-panel results

| Arm | Reference matches | Wrong values/scope | Unjustified answer | Refusal on answerable | Invalid/failed |
|---|---:|---:|---:|---:|---:|
| Escaped, round 1 | 4 | 6 | 1 | 0 | 1 |
| Unicode, round 1 | 10 | 0 | 1 | 1 | 0 |
| Escaped, round 2 | 4 | 6 | 1 | 0 | 1 |
| Unicode, round 2 | 10 | 0 | 1 | 1 | 0 |

Each encoding repeats identical parsed proposals and outcomes across its two
rounds. The ASCII work-log listing control has byte-identical messages across
both formats and remains correct. Panel/source/unit/schema hashes, dates and
full oracle results must match across each pair; the manifest builder asserts
these, rather than relying on a shared filename.

Original four: **1/4 to 4/4**, repeated. All six previously wrong answerable
cases recover: device counts, device details, site Fahrenheit averages,
Japanese Fahrenheit maxima, team/project/ticket counts and total logged hours.
The successful short original questions now work without adding schema IDs.

The two residual cases are different:

- Joined row details: the proposal now selects the right device and site
  columns, but the bounded row compiler supports base-table projections only.
  It refuses `sites.site_name` instead of silently dropping it. This remains
  lost answer coverage, not a necessary business refusal or a model success.
- Rental-device mean: both formats answer across all readings without any
  rental restriction. No reviewed rental definition exists in the IoT study
  metadata. This remains an unjustified answer, not fixed by encoding or by
  exposing an unverified interpretation.

## Interpretation and limits

The repeated one-factor improvement is strong evidence of input-rendering
sensitivity for this panel, not proof of a particular attention, tokenizer or
gateway batching mechanism. The original three failures should no longer be
described simply as persistent model incapacity: the harness representation
materially contributed. Conversely, this does not erase earlier independent
production wrong-metric or concept-gate results; that planner already uses
literal Unicode.

Counts remain development evidence, not unseen-user generalization. The two
rounds repeat the same questions, not 24 independent test cases. Identical
proposals are a bounded repeat observation, not a reliability certificate.
Scoring still requires the complete predeclared SQL result (or an allowed
complete alternative); aliases alone never certify conversion.

## Explicit controls and closeout

The Unicode explicit arm has **18 reference matches, 2 necessary refusals,
1 invalid output**, across 19 answerable and 2 unanswerable cases. The earlier
escaped-v2 arm also matched 18, but had one wrong-valid answer instead of an
invalid output. The ticket/event-count error recovers; per-ticket hours now
has a redundant wrapper around a dimension reference. This historical
comparison is not a repeated paired control arm, and unchanged totals must
not hide that tradeoff. The original 21-case oracle is unchanged.

A separate **zero-model-call PostgreSQL replay** applies the existing production
`repair_column_refs` to that single malformed proposal. It records exactly
`dimensions: unwrapped column reference`, validates without changing the
selected column/unit/aggregate, and matches the original hours oracle. The
raw live result stays invalid in the table; this is integration-reuse evidence,
not a nineteenth live success. Replay, script and normalizer hashes are in
the manifest. No new production repair was implemented.

Total **69 new model calls**, no retries or repair calls. Focused: **49 tests**;
full offline: **1,953 tests, zero skipped**; static passed. The old baseline
rendering stays selectable and remains the runner default for compatibility;
the measured new research revision is explicitly selected with
`--wire v2 --question-encoding unicode`. Production v15 is not changed.

## Next order

1. Use literal original-language question text in subsequent extension work;
   do not continue tuning an intent extractor to compensate for this harness.
   Reuse the existing production shape normalizer during a shared-path pilot,
   with traces and regression checks, rather than adding a new wrapper repair.
2. Separate joined-row projection (unsupported compiler construct) from rental
   scope (missing reviewed knowledge). Test supported and unsupported scope
   neighbors when extending metadata; do not call omission harmless just
   because the interpretation is disclosed.
3. Start a bounded base-row listing integration pilot, then SQL conversion and
   independent aggregation. Before serving, preserve the existing visibility,
   grounding, segment, evidence, deadline/cancellation and request ownership
   checks. Full independent aggregate population/identity coverage remains
   required. No need to build a new general agent framework.

The previous blanket no-go for the automatic extension planner is now narrowed:
the four original questions have repeatable research feasibility, sufficient to
justify a bounded integration experiment, but **not a production release**.
The live Web remains unchanged, and this study does not make it answer those
four questions yet. No public format, evaluation standard, authorization
boundary, identity binding or persisted database state changed. No push.
