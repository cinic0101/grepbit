# Observed 31B dev regression of the frozen formal panel (#79)

Status: goal-delegated tooling; offline implementation with rulers. A live run
needs the owner's standing grant on #79 ("31B observed/formal 28-input run",
at most four runs) and one bound run slot.

## Purpose

The accepted P3.5 formal run (`.artifacts/p35-formal-live-1bekGO/report.json`,
SHA-256 `be8c381f…`) is the 31B baseline: 25/28 inputs and 12/14 families
correct, with three `false_clarification` outcomes (FA11 zh-TW, FA11 ja,
E02 en). The P3.6 independent review kept the oracles, the evaluator and the
prompt as they are and classified the three failures as model wording
robustness; the archived evidence deliberately omits what the model asked, so
the failing clarification kind is `unknown_not_persisted` and a harness fix
cannot be designed or checked against it.

Every one of the 28 inputs is regression data now. This runner observes the
same panel again on an accepted `dev` commit, compares each input with the
baseline through the shared six-class taxonomy of the 12B runner
(`UNCHANGED_CORRECT`, `FIXED_KNOWN_FAILURE`, `NEW_REGRESSION`,
`UNCHANGED_FAILURE`, `OUTCOME_CHANGED_OTHER`, `UNASSESSED_OPERATIONAL`) and
records two closed observations per clarify action:

| Field | Values | Why |
| --- | --- | --- |
| `clarification_kind` | one of the four admitted kinds, or `null` | Which admitted ambiguity the model claimed; a false clarification's kind is what a general prompt restatement must explain |
| `clarification_choice_count` | integer 2..4, or `null` | Whether the model offered the minimum or the full alternative set |

No question text, choice value, presentation or completion text is persisted;
the reader rejects any other value, a kind on a non-clarify row and a missing
kind on a clarify row. The summary adds `observations` (clarify actions by
kind and false clarifications by kind) next to `comparison`.

## Contract

- Packet `p3-dev-regression-packet-v1`: the four formal V2 asset pins, the
  accepted 31B baseline pin and its projection, the accepted `dev` commit with
  a clean worktree, the full source identity (so a prompt or runtime change
  produces a new packet), the fixture digest, the P3.3 authoring baseline, the
  candidate identity `accepted_dev_behavior` shared with the holdout runner,
  28 inputs in the frozen order, 60-second calls, the grant's route
  attestation (retries, fallback and cache disabled; any other attestation is
  `invalid_configuration`), `evidence_class: observed_regression`,
  `promotion_eligible: false`, `promotion_result: not_applicable`.
- Authorization `p3-dev-regression-authorization-v1` binds the packet digest,
  one Issue #79 grant comment and one exclusive repository-relative run slot
  before credential access; a holdout envelope or another slot is rejected.
- The shared loop gained one optional hook: a purpose-specific evidence policy
  may expose `observe_result(result)` and the loop merges its closed fields
  into the graded row after the frozen grade. Policies without the hook are
  unchanged, so formal, stability, holdout, 12B and Bedrock archives keep
  their exact row shape.
- The report reader validates offline (no checkout, DB, env or network) and
  rejects promotion claims, a foreign reader's archive and tampered
  observations. The formal, holdout and 12B readers reject this archive.

## What it is not

Not fresh quality evidence, not stability evidence and never promotion: the
inputs are exposed regression data and the model has seen them before. A fix
motivated by this run needs a fresh holdout for any generalization claim, and
a prompt change stays within the roadmap's two-fix default per failure
family before a mandatory stop.

## Commands

```bash
.venv/bin/python tools/p3_dev_regression.py --prepare \
  --intake .artifacts/p35-stage-c-pIKdCM/freeze/intake.json \
  --panel .artifacts/p35-stage-c-pIKdCM/freeze/formal-panel-v2-draft.json \
  --historical-report .artifacts/p35-formal-live-1bekGO/report.json \
  --db <ACCEPTED_DB> --accepted-commit <MERGED_DEV_COMMIT> \
  --transport-security unencrypted_http \
  --gateway-retries disabled --gateway-fallback disabled --gateway-cache disabled \
  --output-dir .artifacts/<FRESH_PACKET_DIR>
.venv/bin/python tools/p3_dev_regression.py --bind-authorization \
  --packet .artifacts/<FRESH_PACKET_DIR>/manifest.json \
  --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/79#issuecomment-<GRANT> \
  --output .artifacts/<FRESH_SLOT>/authorization.json --run-output-dir .artifacts/<FRESH_SLOT>/run
.venv/bin/python tools/p3_dev_regression.py --report --report-path .artifacts/<FRESH_SLOT>/run/report.json
```

The `--live` command template is recorded in the packet.
