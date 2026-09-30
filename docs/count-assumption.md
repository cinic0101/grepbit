# Count assumption: evaluation side (#136)

Contract `count-assumption-eval-v1`. It implements the evaluation half of
ADR #136, as amended in
[#136 #issuecomment-5904225044](https://github.com/cinic0101/grepbit/issues/136#issuecomment-5904225044),
for the owner's people-count decision
([#79 #issuecomment-5903677393](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903677393),
rule table approved at
[#issuecomment-5903712127](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5903712127)):

> A generic people or count question whose meaning is unresolved is answered
> with booked seats, the only executable count, with the assumption stated and
> the unavailable meanings named.

This contract changes the oracle format, the grader and the dev panels. It
changes no `grepbit/` runtime file, so the current candidate (v12) stays
current and can still be evaluated on the new panels. The runtime half, where
the model emits the assumption, is candidate v13 in a later PR.

## Oracle field

An **answer** oracle for the **Overview** recipe may carry one optional field:

```json
"assumption": {"count_basis": "booked_seats"}
```

- The object is closed: exactly the key `count_basis`, with the value
  `booked_seats`.
- An oracle for any other recipe, or any other shape or value, is
  `invalid_oracle`.
- An oracle without the field is unchanged: it expects no assumption.

## Grading

The grader's existing `request` layer compares the proposal's assumption
together with its native request:

- **passed** when the canonical native request equals the oracle's and the
  proposal's assumption equals the oracle's `assumption`.
- A proposal without an `assumption` attribute, which is every v12 proposal,
  counts as having none. So does an oracle without the field.
- **A missing assumption** (the oracle has one, the proposal does not) fails
  the layer. That is a silent substitution: the count was answered without
  saying what it means.
- **A spurious assumption** (the proposal has one, the oracle does not) also
  fails the layer.
- No layer is added and no report field changes. For every existing oracle and
  every existing proposal the layer's result is unchanged, so the grader keeps
  its version, `p3-evaluator-v1`. Bumping it would make every archived
  evaluation report fail readback, because the manifest pins
  `evaluator_version`. The oracle digests in each panel identity pin the new
  rule instead.

## Revised oracles and new panels

The four count families that the rule table changes get new oracle revisions:
`dev-BM6.v2`, `dev-MN1.v2`, `dev-MN2.v2` and `dev-MN3.v2`.
- Each is an Overview answer for `CTR-A01`, 2026-03-01 to 2026-04-01
  `+08:00`, `Asia/Taipei`.
- Each carries the assumption, plus the coverage, values, slots, states and
  units of the accepted `dev-BM5.v1`. Those are kernel-derived; the scope is
  the same.
- Each case of these families is re-pointed to its v2 oracle, with
  `expected_branch` and `cohort` set to `answer` and a new
  `semantic_signature`.
- The question text, language, exposure, provenance history and every other
  case are unchanged.

| New panel | Cases file | Oracles file | Changed cases |
| --- | --- | --- | --- |
| `p3-dev-bound-meaning-v2` | `bound-meaning-cases-v2.json` | `bound-meaning-oracles-v2.json` | `dev-BM6` ×3 |
| `p3-dev-mechanism-probe-v2` | `mechanism-probe-cases-v2.json` | `mechanism-probe-oracles-v2.json` | `dev-BM6` ×3, `dev-MN1` ×3, `dev-MN2` ×3, `dev-MN3` ×3 |

The v2 oracles files contain exactly the oracles the v2 cases reference: every
unchanged v1 oracle byte-for-byte, with the four families' v1 oracles replaced
by their v2 revisions. The v1 panels, files and archived results are
unchanged. Both new panels are registered as `dev` tier with `development`
authoring.

The families the rule table leaves unchanged keep their oracles: `dev-BM5`
(answer), `dev-BM7` (clarify with the stated meanings) and `dev-BM8`
(decline).

## Acceptance

The v2 oracles and cases need independent semantic acceptance. It is given
by the owner-designated fresh-context reviewer, which sees only:
- the questions;
- the approved rule table;
- the proposed v2 oracles and case metadata.

It sees no model output, run result or implementing conversation. Its prompt,
disclosure and verdict are recorded on the PR, and the implementing agent does
not accept the oracles.

## Claims and limits

- The new panels measure the owner's rule on exposed development inputs. Any
  result on them is a development observation.
- v12 cannot emit an assumption. On the new panels it is expected to fail
  every changed case: a silent answer fails the `request` layer, and a
  clarification or decline has the wrong action. That is the baseline v13
  must improve on under the candidate gate.
- Holdout and formal oracles are untouched. `HA02` and any other held-out
  count case keep their accepted expectations until their own independent
  process revises them.
