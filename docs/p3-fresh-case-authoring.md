# Independent P3 case authoring and admission

Protocol: `p3-intake-v1`; Issue #43. This is an author/reviewer handoff, not a
fresh question bank, a novelty certificate or permission to run a model.

## Frozen candidate and separate tooling identity

The frozen product/evaluator baseline is
`20abb5592262c77c98f9cabeaf7cf4854edb6fbe`. The owner declared that freeze in
[Issue #43](https://github.com/cinic0101/grepbit/issues/43), created at
`2026-09-21T06:32:04Z`. Fresh authoring must occur after that declaration.
Product sources, prompts, action/presentation schemas, native semantics,
grading, scoring and `p3-evidence-expectations-v1` must not change.

Owner-approved allocation v2 is a separate admission/tooling identity, not a
change to those frozen sources. `p3_formal_policy` routes explicit v1/v2 policy
admission and reuses frozen accounting; the historical scorer and asset loader
remain byte-identical and protected by `candidate_identity()`.

Admission tooling is a different identity. It must first be reviewed and merged;
accepted preparation then requires that exact clean **dev tooling commit**,
while checking frozen behavior against `20abb559`. Do not pretend new admission
commands existed at the older commit or treat a feature branch as accepted.

## Independent roles and permitted evidence

An independent author supplies questions and gold; an independent reviewer
reviews meaning, ancestry, translations and novelty. Record role references,
not credentials or personal contact details. Distinct references and role
attestations do not technically prove that different people performed the work.
Owner review remains a separate required assertion.

Authors/reviewers may inspect accepted product contracts, the supported recipe
semantics, synthetic fixture/reference definitions, historical family taxonomy
and independently computed reference facts. Historical ancestry is not secret.
They must not run the frozen candidate, inspect its completions, use candidate
output as gold, or use case-specific repair notes to tailor supposedly unseen
cases. Do not ask the implementation agent or another model in its workflow to
generate the reserved fresh questions or gold.

The implementation agent may build intake tools and historical exposed controls.
It must not inspect actual fresh payloads. Return an independently reviewed
bundle to the owner outside the implementation chat; run local validation with
sanitized status/count/hash output. Do not paste questions, oracle semantics or
novelty explanations into that chat. This is an operational separation, **not
technical blindness**: access and exposure must be truthfully recorded.

## Reuse the native case and oracle formats

Supply existing `p3-cases-v1` and `p3-oracles-v1` JSON assets. Do not invent a
second question or query schema. Cases carry the question, language, expected
branch, cohort, proposed exposure, semantic signature, provenance and oracle
reference. A completed panel uses the unchanged `p3-panel-v1` format and exact
input order. A draft intake may be smaller than the formal target.

The thin `p3-intake-v1` wrapper binds the candidate SHA and the case/oracle asset
hashes. Its bounded family records add:

- author/reviewer role and reference, authoring/review timestamps;
- ancestry references and a substantive novelty rationale;
- a reviewed, parameter-independent requirement-bundle signature;
- a checklist covering distinct requirements, non-paraphrase/non-translation,
  non-parameter-only changes, supported frozen capability, independent gold,
  reviewed ancestry and language equivalence;
- whether implementation authors saw the case-specific semantics before use.

The wrapper has only `draft` and `novelty_reviewed` intake states. A separate
immutable freeze artifact records `frozen`. These are not configurable workflow
steps. A complete shape or an affirmative checklist is not proof of novelty.
The owner review reference must identify the specific submitted bundle.

Wrapper shape (placeholders only, not a case or gold):

```json
{
  "version": "p3-intake-v1",
  "intake_id": "<new submission identity>",
  "candidate_freeze_sha": "20abb5592262c77c98f9cabeaf7cf4854edb6fbe",
  "state": "draft",
  "cases": {"reference": "cases-v1.json", "sha256": "<original byte hash>"},
  "oracles": {"reference": "oracles-v1.json", "sha256": "<original byte hash>"},
  "owner_review_reference": null,
  "families": [{
    "family_id": "<native family ID>",
    "case_ids": ["<native variant ID>"],
    "author": {"role": "independent_author", "reference": "<role reference>"},
    "reviewer": {"role": "independent_reviewer", "reference": "<different role reference>"},
    "authored_at": "<UTC ISO timestamp ending Z>",
    "reviewed_at": null,
    "ancestry": ["<reviewed historical family/contract reference>"],
    "novelty_rationale": "<substantive requirement difference, not selector changes>",
    "reviewed_signature": "<parameter-independent requirement bundle>",
    "checklist": {
      "distinct_requirements": false,
      "not_paraphrase_or_translation": false,
      "not_parameter_only": false,
      "supported_frozen_capability": false,
      "independent_gold": false,
      "ancestry_reviewed": false,
      "language_equivalence": false
    },
    "implementer_visible_before_run": false
  }]
}
```

All listed fields are required; unknown fields reject. References are distinct
local JSON basenames beside the intake, not URLs or traversal paths. Timestamps
must be ordered and not future-dated. Native case provenance and wrapper
visibility must agree. Historical authors may use `historical_curator` or
`implementation_author`; fresh authors may not. In a reviewed submission every
check is affirmative, review timestamps are present and an owner review
reference is supplied. These remain assertions to independently review, not
identity authentication or cryptographic signatures.

## Gold and semantic novelty

For answers, provide exact native request and independent fact/value gold using
reviewed reference semantics or fixture/reference computation. Preserve metric,
population, grain, units, time basis, filters, role orientation and required
coverage. Explicitly requested native optional views become user-required
obligations; extra native output does not remove those obligations.

For clarification, supply the complete typed semantic alternative set for only
`count_basis`, `comparison_roles`, `center` or `metric_meaning`. Labels and order
are not semantic gold. No free-value or missing-year grounding is admitted.

For decline, justify a clear unsupported capability under the frozen recipe
entry. A missing year/baseline/k is not necessary-refusal gold; P21/D05 is not a
scored slot. Do not convert implementation inability into a desired decline.

A requirement-bundle signature must describe action/capability, requirements,
scope, metric/population/grain/time basis, period-role policy, entity binding,
coverage, ranking/denominator obligations and ambiguity/capability boundary as
applicable. It must not gain a new family merely from a different date, code,
`k`, language, synonym or sentence order. Historical signatures containing
literal selectors are ancestry records, not automatic proof of a new bundle.

Deterministic checks catch repeated signatures and identical oracle meanings.
Review fixtures can also identify explicitly declared parameter-only changes.
Tools do not understand arbitrary natural-language novelty or detect dishonest
attestations. Human review must resolve suspected historical overlap, including
controls derived from Overview, Compare and Breakdown anchors. Do not turn
subjective novelty into a numeric score or a model-judge call.

## Exposure and immutable revisions

Only `frozen_fresh`, `design_seen` and `exposed_regression` exist. Historical
descendants remain exposed. Fresh proposals require independent authoring after
the freeze, independent review, truthful unseen status and a passing novelty
audit; ancestry alone neither proves nor disproves novelty.

If implementation authors see fresh case-specific expectations before first
scored use, the submission is no longer fresh-eligible. Preserve its original
record and create a new submission/asset identity with a monotonic exposure
history and truthful visibility. Do not overwrite it or refresh it by
paraphrasing. Any product change motivated by exposure needs a separately
reviewed candidate and genuinely independent replacement authoring.

Once frozen, case/oracle bytes, order, exposure and candidate identity cannot
silently change. Drift must reject preparation. Preserve the submitted bundle
and every previous intake/freeze artifact; edits require a new identity and
explicit provenance, not deletion of an inconvenient failure.

## Versioned allocation and remaining gates

The historical v1 target remains 24 families / 44 inputs in the unchanged P3.2
validator. Fresh authoring is now closed; that breadth cannot honestly be filled.
The owner-approved [v2 retained slice](p3-evaluation-contract.md#current-retained-slice-policy-allocation-v2)
is 14 families / 28 inputs: fresh 5/13, exposed including anchors 9/15;
cohort families 3/3/5/3, inputs 5/5/9/9, languages zh-TW 8 / en 10 / ja 10.
No design-seen, observational, non-mandatory or P21 slots are admitted.
Seven original fresh slots remain intentionally unfilled, not a request for more
authoring. The same frozen accounting engine is reused; this is not a new scorer.

The [owner-approved exposed projection](p3-evaluator.md#exposed-material-and-unresolved-admission)
now retains 9 provisional families / 15 inputs (zh-TW 4 / en 5 / ja 6).
P10 is deferred, P11 is an E02 semantic regression outside the formal panel,
and P12 is not admitted; all historical assets remain intact. This projection
does not certify the retained labels or relax same-family oracle consistency.
The retained fresh set is FA01/P02, FA04/P04, FA09 r2/P14, FA10/P17 and FA11/P18.
No formal panel has been frozen. Counts and owner declarations do not substitute
for the exact independently reviewed asset hashes and review references.

Before an actual freeze the owner must supply a **sanitized identity manifest**:
exact fresh case IDs, family/slot and language mapping, case/oracle asset hashes,
author/reviewer references and timestamps, exposure/review state, and the exact
FA09 r2 reviewed asset hash plus review reference. Bind the native intake asset
pins and specific owner review reference to that reviewed bundle; preserve any
component ancestry identities. Never substitute a label/path, old revision or
implementation-inspected payload hash. The implementation agent must not open
fresh artifact directories to obtain these identities.

Future owner-side freeze uses explicit `--allocation-policy p3-formal-allocation-v2`.
The versioned freeze pins that policy; preparation inherits it from the verified
freeze, never from row count. Legacy v1 artifacts remain distinguishable/readable.
Native intake still reads payloads in the isolated owner/reviewer flow, not this
implementation task. Metadata-only policy tests do not attest real fresh admission.

Keep four gates distinct: panel freeze, clean accepted-commit preparation,
provider compatibility probe, and formal scored run. This phase authorizes
tooling support only; this allocation-policy task authorizes no actual freeze
or real formal preparation. Preparation is not live
authorization. Actual independent content, novelty/owner acceptance and clean
accepted tooling are prerequisites, not outcomes of scaffold tests.

## Future compatibility probe: preparation only

Use one previously exposed input, never a fresh formal question. Pin its
question hash, frozen product/schema/context, accepted tooling, synthetic DB,
model route, settings, output location and stop policy.

The later separately authorized probe is exactly one client attempt,
concurrency one, zero retries/repairs/fallbacks, at most 60 seconds and 2,048
output tokens, using the unchanged request/response bounds and v2 route.
Provider-internal inference attempts remain unknown unless separately attested.
Inspect reachability, HTTP/provider envelope, accepted response format, strict
JSON, one admitted parsed action and request-size compatibility only.

Failure is retained evidence, not permission to rerun, tune the candidate or
start formal scoring. A successful probe is not quality evidence. P3.3 does not
provide a live execution command or load credentials; a later owner-authorized
execution gate must specify its exact runnable command and source identity.
Formal scoring requires another explicit authorization after probe review.
Stability, resume, synthesis, grounding, product routing and P4 SourceProfile
remain outside this preparation.
