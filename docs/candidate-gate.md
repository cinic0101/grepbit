# Candidate gate (#79)

Contract `evaluation-gate-v3`. It is the pre-registered acceptance rule the
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

**v3 (#168).** A stable baseline class needs at least three assessed runs.
- **The rule.** Runs that disagree are `flaky` at any count. Fewer than three
  that agree are `insufficient`. The gate excludes both.
- **Why.** In v2, two agreeing runs made a class: `dev-BM2.en` was
  `stable_correct` on two v18 runs, then declined on v18's own bytes (#162,
  #167).
- **Recorded results.** Gate results recorded under v1 or v2 keep their
  verdicts. Re-running them under v3 is a counterfactual, not a re-gate.

**v2 (#164).** v1 selected and compared by `candidate_sha256` alone. v2 uses
the behaviour identity. For every candidate registered before #164 the two
give the same groups, so no earlier gate result changes.

## Selection (by identity only)

For each named panel, on the named route:

- **Baseline runs.** Every indexed run whose candidate's behaviour identity
  equals the baseline candidate's ([behaviour identity](behavior-identity.md):
  the model-input identity plus the runtime files). This is the same
  selection as `--aggregate`, so a run registered under another id with the
  same bytes and runtime (v7 for v12, v18 for v20) is included.
- **Sentinel.** At least one baseline run must carry `grant` equal to the given
  reference, and at least one of those runs must be `complete`. One owner
  authorization is the gate's definition of "the same session". The sentinel
  makes the baseline classes hold in the candidate's session, not only in
  earlier ones. An incomplete sentinel still counts as a baseline run, but
  alone it gives no same-session evidence.
- **Candidate run.** Exactly one indexed run whose candidate's behaviour
  identity equals the gated candidate's, with the same `grant`. Several runs under one
  authorization are refused, so there is no best-of and no rerun to green.
- **Integrity checks.**
  - The gated candidate's behaviour identity must differ from the
    baseline's. The same behaviour is a noise measurement, not a candidate.
    A runtime-only candidate, with the same model-facing bytes, can be gated.
  - Every selected report must read back and match its index digest, as in
    `--aggregate`.
  - Every selected report's `candidate_sha256` must equal the registry bytes
    of its index `candidate_id`.
  - The candidate report's panel id, panel asset digests, annex digest
    (`panel.annex_sha256`, when the panel has one), case order and question
    hashes must equal each baseline report's.
  - Every selected report's authorization reference, panel id, route id and
    status must equal its index entry's grant, the named panel, the named route
    and the entry's status. The index decides the selection, so it must agree
    with the digest-pinned reports.

## Per-input classes

On a panel with an annex (`docs/count-assumption.md`), every row below is
first replaced by its annex verdict. This applies to baseline rows, the
candidate row and sentinel rows alike. A frozen-correct row with no persisted
validated action cannot have its assumption checked, so it is unassessed.

The baseline class of each input comes from `--aggregate` over all baseline
runs, the sentinel included. The class is one of these:
- `flaky`, when at least one assessed run is correct and one wrong;
- `insufficient`, when fewer than three assessed runs agree;
- `stable_correct` or `stable_wrong`, when at least three assessed runs agree
  (v3, #168).

The candidate row is `correct` or `wrong` as graded, or `unassessed`.
Unassessed means that no model result was usable: the row did not complete,
is `not_run` or `operational_failure`, has a runner error, or has an error
that was not raised on the model's own content.
- A graded row whose error was raised on the model's content, after the
  envelope was accepted, is the model's answer and counts as wrong. These are
  `invalid_json`, `invalid_request` and `constraint_conflict`. For example,
  malformed JSON on an input the baseline consistently got right is a break,
  not an inconclusive gate.
- Any other error leaves the row unassessed, even when the grader records the
  row as `invalid_output`. Examples are an envelope or gateway failure
  (`invalid_response`, `unsupported_output`), a transport, budget, kernel or
  source failure, and a missing result. A route failure never becomes a
  regression.

The baseline classes keep the aggregate taxonomy, which also counts a graded
row with an operational error as unassessed. That difference only makes a pass
harder:
- An input with such a row in one baseline run and correct answers in the
  others is `stable_correct`, so a wrong candidate row counts as a break.
- An input with too few assessed baseline rows is `insufficient`, so a correct
  candidate row is not counted as a fix.

A fix also needs same-session evidence: at least one sentinel row on that
input must be assessed (in the aggregate taxonomy). Otherwise a correct
candidate row on a `stable_wrong` input rests on earlier sessions only, and it
is `excluded`. A break needs no such evidence, which again only makes a pass
harder.

The first matching row of the table applies, so an unassessed candidate row
is `unassessed` whatever the baseline class.

| Baseline class | Candidate row | Gate class |
| --- | --- | --- |
| any | unassessed | `unassessed` |
| `stable_correct` | wrong | `broke` |
| `stable_wrong`, a sentinel row assessed | correct | `fixed` |
| `stable_wrong`, no sentinel row assessed | correct | `excluded` |
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

- `version` `evaluation-gate-v3`, `promotion_eligible` false, `claim`
  `development_observation`;
- `route_id` and `owner_authorization_reference`;
- `candidate` and `baseline`, each with `candidate_id`, `candidate_sha256`
  and `behavior_sha256`;
- `run_index_sha256`;
- `panels`, in the order named. Each entry has:
  - `panel_id`, `baseline_runs`, `sentinel_runs` and `candidate_run`;
  - `recorded_at`: the index times of the sentinel runs and the candidate run;
  - `other_candidate_runs`: runs with the candidate's behaviour identity on the panel and
    route under other authorizations, which this gate ignores;
  - `inputs`, in panel order: `case_id`, `family_id`, `baseline_class`,
    `sentinel_assessed`, `candidate` (`correct`, `wrong` or `unassessed`), the
    candidate row's graded `outcome` and the gate `class`;
  - `counts` per gate class;
  - the case-id lists `fixed`, `broke`, `excluded` and `unassessed`;
  - `verdict`;
- the overall `counts` and `verdict`.

## Refusals

A refusal prints the existing safe code `invalid_manifest` with one closed
`gate_refusal` reason on stderr and exits 2:

| Reason | Meaning |
| --- | --- |
| `same_bytes` | The candidate's behaviour identity equals the baseline's (the name is kept from v1). |
| `not_dev_panel` | A named panel is not registered with tier `dev`. |
| `no_baseline_runs` | A panel has no baseline run. |
| `no_sentinel` | No baseline run on the panel was recorded under the given authorization. |
| `sentinel_incomplete` | No baseline run on the panel recorded under the given authorization is complete. |
| `no_candidate_run` | No candidate run on the panel was recorded under the given authorization. |
| `multiple_candidate_runs` | More than one candidate run on the panel was recorded under the given authorization. |
| `candidate_identity` | A selected report's candidate bytes differ from its index entry's registry bytes. |
| `inputs_differ` | The candidate report's panel, case order or question hashes differ from a baseline report's. |
| `index_mismatch` | A selected report's authorization, panel, route or status differs from its index entry or the named panel and route. |

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
- One authorization bounds neither time nor order. A grant may span hours or
  days, and the sentinel may be recorded after the candidate. The output
  gives the index times so a reader can see the gap; the gate does not limit
  it.
- The gate refuses a second candidate run under the same authorization. Runs
  under other authorizations are listed in `other_candidate_runs`, so a
  re-gate under a new authorization stays visible.
- The panels are named before the run, in the proposal the owner authorizes,
  and the output lists them. For #79 count candidates the panels were
  `p3-dev-bound-meaning-v1` and `p3-dev-mechanism-probe-v1`. Under ADR #136 a
  count-assumption candidate (v13) is gated on `p3-dev-bound-meaning-v2` and
  `p3-dev-mechanism-probe-v2`. On the v1 panels, that candidate's intended
  answers would be breaks by design. Each such gate needs a sentinel plus a
  candidate run on both panels, 92 calls per candidate, and v2 also needs at
  least two baseline runs per panel.
- The gate reads recorded runs only. It does not replace the regression and
  holdout rules or the independent semantic acceptance in AGENTS.md.
- A candidate that changes model-facing bytes still needs a live run. A
  change that leaves them unchanged can be screened first with `--replay`
  ([replayable observations](replayable-observations.md)).
