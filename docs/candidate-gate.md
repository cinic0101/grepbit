# Candidate gate (#79)

Contract `evaluation-gate-v1`. It is the pre-registered acceptance rule the
owner chose as step A of "A+B"
([#79 #issuecomment-5900353252](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5900353252)).
The gate is an offline mode of the single runner, `tools/evaluate.py --gate`.
It makes no model call, writes nothing, and prints canonical JSON.

## Why

The noise measurement ([v10 restoration](v10-restoration-v12.md#noise-measurement-2026-09-29))
found that the same model-facing bytes gave the same graded result on every
input within a session. The earlier count candidates changed many inputs in
both directions: v11 fixed 7 probe inputs and broke 6. A single total, such as
"12/22 against 11/22", hides that trade. The gate compares each input against
the baseline's measured classes. Its verdict is mechanical, so a regression is
a stop, not a debate about net gain.

## Invocation

```
.venv/bin/python tools/evaluate.py --gate --candidate <id> --baseline-candidate <id> \
    --route <id> --owner-authorization-reference <grant URL> --panels <panel id> [<panel id> ...]
```

The arguments are closed: every one is required and no other is accepted.
The run index and the archives it pins are the only inputs. Only `dev`-tier
panels are accepted, and the output's claim is `development_observation`.
Regression and holdout panels keep their own rules.

## Selection (by identity only)

For each named panel, on the named route:

- **Baseline runs.** Every indexed run whose candidate's registry
  `candidate_sha256` equals the baseline candidate's. This is the same
  selection as `--aggregate`, so a run registered under another id with the
  same bytes (v7 for v12) is included.
- **Sentinel.** At least one baseline run must carry `grant` equal to the given
  reference. One owner authorization is the gate's definition of "the same
  session". The sentinel makes the baseline classes hold in the candidate's
  session, not only in earlier ones.
- **Candidate run.** Exactly one indexed run whose candidate's registry bytes
  equal the gated candidate's, with the same `grant`. Several runs under one
  authorization are refused, so there is no best-of and no rerun to green.
- **Integrity checks.**
  - The gated candidate's bytes must differ from the baseline's. The same
    bytes are a noise measurement, not a candidate.
  - Every selected report must read back and match its index digest, as in
    `--aggregate`.
  - Every selected report's `candidate_sha256` must equal the registry bytes
    of its index `candidate_id`.
  - The candidate report's panel id, panel asset digests, case order and
    question hashes must equal each baseline report's.

## Per-input classes

The baseline class of each input comes from `--aggregate` over all baseline
runs, the sentinel included: `stable_correct`, `stable_wrong`, `flaky` or
`insufficient`.

The candidate row is `correct` or `wrong` as graded, or `unassessed`.
Unassessed means that no model result was usable: the row did not complete,
is `not_run` or `operational_failure`, or has a runner error. A graded row
with an error is the model's answer and counts as wrong. For example,
`invalid_output` (malformed model content) on an input the baseline
consistently got right is a break, not an inconclusive gate.

The baseline classes keep the aggregate taxonomy, which also counts a graded
row with an operational error as unassessed. That difference only makes a pass
harder:
- An input with such a row in one baseline run and correct answers in the
  others is `stable_correct`, so a wrong candidate row counts as a break.
- An input with too few assessed baseline rows is `insufficient`, so a correct
  candidate row is not counted as a fix.

The first matching row of the table applies, so an unassessed candidate row
is `unassessed` whatever the baseline class.

| Baseline class | Candidate row | Gate class |
| --- | --- | --- |
| any | unassessed | `unassessed` |
| `stable_correct` | wrong | `broke` |
| `stable_wrong` | correct | `fixed` |
| `stable_correct` | correct | `unchanged_correct` |
| `stable_wrong` | wrong | `unchanged_wrong` |
| `flaky` or `insufficient` | correct or wrong | `excluded`: reported with the candidate result, never counted as a fix or a break |

## Verdict

The verdict is pre-registered and leaves no discretion. It is computed per
panel and overall, and the first matching rule applies:

1. `regression`: any `broke`. On any named panel, a fix elsewhere never
   offsets it.
2. `inconclusive`: any `unassessed` candidate row. The same authorization
   cannot produce a second candidate run, so an inconclusive gate needs a new
   owner authorization. It is not rerun under the old one.
3. `passed`: at least one `fixed`.
4. `no_fix`: otherwise.

The overall verdict applies the same rules to the union of the panels.

## Output

The gate prints one canonical JSON object and exits 0 whatever the verdict:

- `version` `evaluation-gate-v1`, `promotion_eligible` false, `claim`
  `development_observation`;
- `route_id` and `owner_authorization_reference`;
- `candidate` and `baseline`, each with `candidate_id` and `candidate_sha256`;
- `run_index_sha256`;
- `panels`, in the order named. Each entry has:
  - `panel_id`, `baseline_runs`, `sentinel_runs` and `candidate_run`;
  - `inputs`, in panel order: `case_id`, `family_id`, `baseline_class`,
    `candidate` (`correct`, `wrong` or `unassessed`), the candidate row's
    graded `outcome` and the gate `class`;
  - `counts` per gate class;
  - the case-id lists `fixed`, `broke`, `excluded` and `unassessed`;
  - `verdict`;
- the overall `counts` and `verdict`.

## Refusals

A refusal prints the existing safe code `invalid_manifest` with one closed
`gate_refusal` reason on stderr and exits 2:

| Reason | Meaning |
| --- | --- |
| `same_bytes` | The candidate's bytes equal the baseline's. |
| `not_dev_panel` | A named panel is not registered with tier `dev`. |
| `no_baseline_runs` | A panel has no baseline run. |
| `no_sentinel` | No baseline run on the panel was recorded under the given authorization. |
| `no_candidate_run` | No candidate run on the panel was recorded under the given authorization. |
| `multiple_candidate_runs` | More than one candidate run on the panel was recorded under the given authorization. |
| `candidate_identity` | A selected report's candidate bytes differ from its index entry's registry bytes. |
| `inputs_differ` | The candidate report's panel, case order or question hashes differ from a baseline report's. |

An archive that is missing or does not match its digest fails closed with
`manifest_drift`, as in `--aggregate`. A malformed grant reference or a
repeated panel is `invalid_arguments`.

## Claims and limits

- `passed` means only this: in this session, on these development panels, the
  candidate fixed at least one input the baseline consistently got wrong, and
  broke none it consistently got right.
  - It is a development observation, not promotion, a probability or
    generalization.
  - Excluded inputs remain unknown.
- The panels are named before the run, in the proposal the owner authorizes,
  and the output lists them. For #79 count candidates the panels are
  `p3-dev-bound-meaning-v1` and `p3-dev-mechanism-probe-v1`. A sentinel and a
  candidate run on both cost 92 calls per candidate.
- The gate reads recorded runs only. It does not replace the regression and
  holdout rules or the independent semantic acceptance in AGENTS.md.
- A candidate that changes model-facing bytes still needs a live run. A
  change that leaves them unchanged can be screened first with `--replay`
  ([replayable observations](replayable-observations.md)).
