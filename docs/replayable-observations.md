# Replayable observations (evaluation v2, #79)

Status: contract with offline rulers (`tests/test_evaluate_replay.py`). No
live call is authorized by this document. Owner decision given in chat and
recorded on #79 (comment 5892696354): persist the validated typed action per
input for zero-call offline replay, in parallel with a separate noise
measurement proposal. ADR #125 option A stands; no gold, oracle or case
change.

## Problem

Every earlier fix changed shared model-facing bytes and was judged on one
noisy observation per input. Identical bytes produced different outputs on
4/24 inputs and a changed parsed result on 1/24 (#79). Reports kept only a
signature hash of the action, so a kernel or grader change could be judged
only by spending new live calls, which mixes model noise into the result.

## Evaluation v2 contract

`tools/evaluate.py --prepare` now writes `evaluation-packet-v2`; `--live`
writes `evaluation-manifest-v2` and `evaluation-report-v2`.
`evaluation-authorization-v1`, the stop policy, settings, the command
template and the run index record are unchanged.

| Field | v1 | v2 |
| --- | --- | --- |
| `repetition` | absent | integer 1..99 from `--prepare --repetition N` (default 1) |
| `run_id` | `<panel>--<route>--<candidate>--<source12>` | the v1 id plus `--r<N>` |
| `observation_fields` | `clarification_kind`, `clarification_choice_count` | the v1 fields plus `validated_action` |
| `data_boundary` | no raw completion, reasoning or proposal content | adds `validated_action_persisted: true`; still no raw completion, reasoning or presentation text |

A repetition is a separately prepared, separately authorized packet with
its own run slot. It is never an automatic rerun. The run id differs per
repetition, so `--record` can index repeated observations of the same bytes.

### `validated_action`

The engine records, per completed input, the action that passed the runtime
validators, as canonical JSON text (at most 16,384 bytes):

- a recipe proposal: `{"outcome":"request","recipe_id":...,"recipe_version":"0.1","request":{...}}`;
- a clarification: `{"outcome":"clarify","clarification":{"kind":...,"choices":[{"id":...,"semantic_value":{...}}]}}`,
  with no presentation labels;
- a decline: `{"outcome":"declined"}`.

The value is `null` when there is no validated action: a timeout or other
operational failure before validation, invalid JSON, an invalid request or
clarification, or an action that fails the closed structural check below.
Such inputs are not replayable. This is a known limitation, not a hidden
fallback.

The reader checks the archive structurally, with vocabulary pinned in the
tool rather than taken from the runtime, so later candidates can still read
old archives:

- the value is null or canonical JSON with the closed top-level shape above;
- nested values are objects, arrays, strings (at most 256 characters),
  integers, booleans or null, at most 10 levels deep;
- it is non-null only on completed rows;
- its outcome matches the graded `actual_action` (`request` means `answer`,
  `clarify` means `clarify`, `declined` means `decline`);
- a clarification matches `clarification_kind` and
  `clarification_choice_count`;
- a request or clarification implies that `request_validation` passed;
- a decline implies `error_code` `model_declined`.

The summary adds `observations.validated_actions`, the count of persisted
actions.

The engine applies the same check before a value lands, so a
self-produced value never stops a live run. A value that fails it is stored
as `null`.

### Backward compatibility

`evaluation-report-v1` archives (every run recorded through v12) still read
back through `--report`. They also still serve as `--baseline` and take part
in `--aggregate`. An `evaluation-packet-v1` can no longer run live: the
rebuild at validation produces v2 and stops with `manifest_drift` before any
credential is read.

## `--replay` (offline, zero model calls)

```bash
.venv/bin/python tools/evaluate.py --replay --report-path <run>/report.json \
  --db <accepted-db> --output <fresh-path>/replay.json
```

1. The report is read through `read_report`. Only `evaluation-report-v2` is
   replayable. Anything else is refused (reason `report_version`).
2. Comparability: the current `candidate_registry.check()` must pass. Its
   registered `candidate_sha256` (semantic surfaces and wire witnesses, that
   is, the model-facing bytes) must equal the packet's (reason
   `candidate_bytes`). The registry panel assets (`panel_assets`), the
   per-input metadata and question digests (`inputs`) and the database
   digest (`database`) must equal the packet's.

   A refusal uses the existing safe code `manifest_drift` and carries one
   closed reason from the list above. The CLI prints it as
   `replay_refusal`. The safe-code vocabularies live in protected files, so
   no new code is added. A refusal happens before the output is written.
3. A row is replayable when it completed, has a `validated_action`, has no
   runner error, and its runtime evidence shows `transport` passed. For each
   replayable row, a mock transport returns exactly that action. The mock
   uses a `.invalid` address and a synthetic token, and no credentials or
   environment are read. The current `interpret_recipe_and_execute` then
   re-validates and executes the action, and the current `p3_grading.grade`
   grades it.
4. Each row is `replayed_same` (every grade field equal), `replayed_changed`
   or `not_replayable`. Rows that are not replayable keep their archived
   grade.
5. The output is `evaluation-replay-v1`, written exclusive-create. It has
   claim `offline_replay_observation`, `live_model_attempts` 0, the mock
   transport call count, the replay source identity (commit, dirty flag,
   files), the evaluator version and per-row classes. It also carries
   archived and replayed correct counts, plus the six-class comparison
   against the archived report.

A replay is never recorded in the run index. It is not live evidence, not
a model observation and never promotion. It answers one question: with the
model's recorded actions held fixed, what do the current kernel and grader
do? A change to model-facing bytes makes the recorded actions unrepresentative,
so the replay is refused.

## `--aggregate` (offline)

```bash
.venv/bin/python tools/evaluate.py --aggregate --panel <id> --route <id> --candidate <id>
```

The aggregate includes every run in `evals/runs/index.jsonl` with the same
panel and route whose registered candidate has the same `candidate_sha256`
as the named candidate. Selection is by identity, never by hand, so runs
cannot be cherry-picked. Each included archive must exist at its slot, match
its indexed `report_sha256`, and read back through its own reader
(evaluation v1/v2 or the P3.5 formal reader), all with the same input order;
otherwise the aggregate stops. An aggregate with no included run also stops.
It prints canonical JSON (`evaluation-aggregate-v1`)
with:

- the run index digest and the included runs (id, candidate, report digest,
  report version, accepted commit, evaluator version, status and correct
  count);
- per input: the number of observations, assessed observations, correct
  observations, outcome and action counts, the number of distinct action
  signatures and of distinct persisted validated actions, and a class:
  - `stable_correct`: at least 2 assessed and all correct;
  - `stable_wrong`: at least 2 assessed and none correct;
  - `flaky`: at least one correct and at least one wrong;
  - `insufficient`: fewer than 2 assessed.
- class counts.

Unassessed follows the comparison taxonomy: not completed, operational
failure, an operational error or a runner error.

Runs of the same model-facing bytes may still differ in kernel or grader
source. The aggregate lists each run's commit and evaluator version but does
not correct for such differences; a v2 replay does. An aggregate is an
analysis of already-recorded development observations, not a new claim.

## Limitations

- Invalid outputs (`invalid_json`, invalid requests or clarifications) and
  operational failures have no validated action, so they cannot be replayed.
- Replay holds the model's actions fixed. It cannot show whether a different
  prompt would change them. Model-side changes still need live repetitions.
- Stable classes are counts over a few observations. They are not
  probabilities or a statistical guarantee.
- v2 persists typed request values, such as center codes and time bounds,
  for the synthetic LearningOps source only. A real-data route needs its own
  data-boundary decision.
