# Bound meaning development controls (#79)

Owner decision given in chat on 2026-09-29 Asia/Taipei:
"okay 按照你的建議來進行下一步" ("Okay, proceed according to your recommendation").
The [recorded grant](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882825384)
accepts the [bounded proposal](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882755374).
This document specifies only the control panel needed before a candidate repair.
The runtime stays v7 until one merged-source baseline has been observed.

## Panel contract

Register `p3-dev-bound-meaning-v1`: 24 inputs, eight families, each in zh-TW,
English and Japanese, one fixed order. Reuse the three exposed E02 cases and
their oracle without changing any fields. The other seven families are authored
development controls. All inputs are exposed regression material in the dev
tier, never fresh questions; no holdout question text is inspected or copied.

| Family | Meaning | Expected branch |
| --- | --- | --- |
| E02_compare | Existing grammatical target/reference, March versus February | answer |
| dev-BM2 | Same directed comparison with reference mentioned first | answer |
| dev-BM3 | Earlier February target against later March reference | answer |
| dev-BM4 | Two months with direction unresolved | clarify: exactly reversed roles |
| dev-BM5 | Overview explicitly requiring supported booked seats | answer |
| dev-BM6 | Complete booking Overview with generic count meaning, no listed alternatives | clarify: seats, booking accounts, distinct people |
| dev-BM7 | Explicit seats/accounts alternative | clarify: exactly those two meanings |
| dev-BM8 | Overview plus independently required distinct natural persons | decline |

New count controls use CTR-A01, March 2026. Comparison controls use all-center
confirmed booked amount, February/March 2026, preserving the explicit shared
year. All time bounds are full calendar months in Asia/Taipei. This is a bounded
control set, not a factorial experiment isolating each wording difference.
Do not infer that a generic count noun always admits all enum values. BM6's
concrete question/choice set requires independent semantic acceptance before
registration. This does not settle original broad-revenue C4.

Production assets will be new files under `evals/dev/bound-meaning-*-v1.json`:
cases, oracles, panel and scripted responses. Existing assets and registry
entries remain byte-identical. New answer values derive from the fixture kernel;
clarification and decline expectations are authored semantic judgments, not
kernel-derived. Scripted responses validate evaluator plumbing, not a model.

Commit this specification and a registration/history/control ruler while it
fails at the missing-panel assertion, before registering assets. Independent
semantic acceptance must precede registration. Root cannot supply it through
code review. Record the reviewer designation, disclosure and decision here.

## Observation gate

After semantic acceptance, full offline checks and local/fresh GitHub reviews,
merge the panel into dev. Prepare one v7 baseline with tools/evaluate.py, bind
the recorded grant and one exclusive slot, and observe each of the 24 inputs
once. Same 31B route/profile, maximum 24 calls, 60 seconds and 2,048 output tokens
per call, 1,560 seconds per run, one run in flight; retries/fallback/cache off.
Only synthetic questions/runtime go on wire, with opaque credentials and no raw
completion/reasoning retention. Operational/drift/privacy stops remain in force.

Semantic baseline errors are diagnostic and retain the full denominator. A
mechanism absent from these controls cannot be assumed reproduced: stop that
repair surface, retain the evidence and narrow any candidate specification to
the supported surface. No reading holdout text to force reproduction. Candidate
controls must all pass before the conditional 54-input dev observation; only
after those gates may the authorized 28-input regression and 18-input holdout
regression follow. The grant's 148-call maximum is not a quota.

## Semantic acceptance

The owner explicitly designated the new fresh-context semantic session in chat:
"指定本次 fresh-context 語意 reviewer" ("Designate this new fresh-context semantic
reviewer"), recorded in [#79](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882857450).
Its [accepted disposition](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5882915786)
covers all 24 corrected inputs, before registration or any baseline call.

The session read questions/contracts before oracles and rejected the initial
BM6 four-choice set: attendance visits were not grounded by booking-only generic
headcount wording. It accepted unchanged questions with only that alternative
removed, leaving booked seats, known booking accounts and distinct people at
the identical Overview scope. The concrete correction was independently checked;
all other oracle content stayed identical. This is a pre-execution draft repair,
not a change prompted by candidate output or a rewrite of historical gold.

Question projection SHA256:
`470ddaf1122d5ce1d60befbeeb771739b642aa69459da9427df0a5a1bae4634e`.
Accepted draft-oracle SHA256:
`aac9c61dc406079e3edf596b4a12ee0dd0dbe11b1b9e3d73c7e59861d7a4fd55`.
Original draft retained locally with SHA256:
`17f8ccfdf2e19e5e06dff36e9799dcaafcff891bedd800711495862760a3cea9`.
Production oracle provenance cites the acceptance; semantic payloads are
unchanged from the accepted draft. E02's entire original oracle is preserved.

The reviewer independently recomputed fixture values without native recipe code
and found no translation discrepancy. Disclosure: task/repository/general
context, questions and contracts before oracles, fixture/catalog definitions,
exposed E02 and the corrected artifacts; no model results, candidate prompt,
implementing conversation, frozen/holdout payloads, network, edits or subagents.
An earlier code-QA session's findings were not treated as semantic acceptance.
Root accepts the checkpoint under the approved plan; code review and merged-source
execution remain separate gates.
