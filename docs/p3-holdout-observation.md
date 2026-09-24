# Fresh holdout observation (#79)

Status: goal-delegated tooling; offline implementation with rulers. A live
run needs the owner's standing grant on #79, a frozen holdout panel and one
bound run slot.

## Purpose

The frozen 14-family / 28-input panel is regression data: every input has
been exposed to the candidates and, since #74, to the implementing agent's
structured view of their outputs. A holdout is an independently authored,
independently reviewed, matrix-allocated set of fresh families that no
candidate has seen and the implementing agent has not read. One observation
per candidate answers "does the harness generalize past the regression set";
after that observation the holdout is regression data too, so holdouts are
prepared in pairs and refreshed.

Authoring and review follow [P3.3](p3-fresh-case-authoring.md) with role
separation through fresh-context agent sessions: an author session that reads
only the intent matrix, semantics, fixture and formats; a reviewer session that
recomputes answer facts by SQL over the fixture, checks clarify and decline
oracles against the contracts, judges novelty against every existing family
and translation equivalence, and writes a rationale in Traditional Chinese for
the owner; the owner judges realism and ratifies boundary novelty claims and
supplies the owner review reference. The implementing agent runs only the
intake audit, freeze and preparation tools with hash and count output and
never reads question text or oracle values.

## Allocation policy `p3-holdout-a-allocation-v1`

| Item | Value |
| --- | --- |
| Families / inputs | 7 / 21, all `frozen_fresh`, three languages each |
| Cohorts (families) | answer 2, clarify 3, decline 2; no anchors |
| Cohorts (inputs) | answer 6, clarify 9, decline 6 |
| Matrix cells filled | A05, C01, A04 (new bundle), C03 (new bundle), C04 (new bundle), D06 (new bundle), D02 (new bundle) |
| Not filled | A03: no distinct candidate found after two authoring rounds; recorded, not padded |

`p3_formal_policy.summarize` accepts the holdout policy with panel kind
`formal` (the frozen asset format) or `holdout` (the live report) and always
reports `panel_kind: holdout`, `promotion.eligible: false`, `promotion.passed:
false`. Family-weighted outcomes come from the unchanged frozen scorer. V1 and
V2 identities are unchanged.

## Runner `tools/p3_holdout_run.py`

Same shape as the formal runner, with: purpose
`one_fresh_holdout_observation_not_promotion`, evidence class
`fresh_holdout_observation`, `promotion_eligible=false`, 21 inputs, 60-second
calls, the default LiteLLM identity, an authorization envelope that binds the
packet digest, one Issue #79 grant comment and one exclusive run slot before
credential access, and a report reader that rejects a moved archive, a
promotion claim or a non-holdout summary. A second observation of the same
holdout needs a new grant comment and a new slot and is regression evidence.

## What it is not

Not promotion, stability or P3 exit evidence; not a replacement for the frozen
regression panel; not proof of real-data transfer (P5). A holdout family that
informs a fix becomes regression data and the pair's other holdout is used
next.
