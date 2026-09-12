# Interpretation wire and bounded selector experiment

2026-09-12. Ruler checkpoint passed. After the focused 306-pass result, the
owner explicitly replied "同意通過，繼續實作與測試". Ruler static/offline 1,221
also passed. The research adapters and runner are now implemented; focused 182,
static and offline 1,306 pass. The scoped 180-attempt study is COMPLETE:
zero transport errors, no candidate qualifies. A/B valid 1/36 and 12/36;
P/S1/S2 clear-plan matches 31/33, 27/33, 27/33. B passes a known-wrong
return-count interpretation; selector order pairs show four semantic differences
and one plan-to-refusal change. See `../research/metric-wire-selector-01.md` and
`evidence/metric-wire-selector-01.json` for the 318 value checks, 642 actual-ask
replays and the independently demonstrated displayed-schema/runtime gap.
No further model allocation or production integration was consumed.
The checkpoint history below remains an account of the original boundary.
Owner request: "組織並執行這次測試/驗證，然後造告訴我研究結論" follows
the proposed 180-call experiment. This is authority for that bounded outcome,
including existing Gemma use, but the supplied AGENTS instructions separately
require an explicit follow-up after material evaluation-contract rulers.
No additional endpoint/DB permission is requested. Root sole writer; preserve
the dirty worktree and original 180-call study. No stage/commit/push.

## Questions and fixed allocation

The previous run is `../research/metric-selection-development-01.md`: 35/36
L1 responses fail their interface; the same two wrong interpretations survive
all four planner arms, and seven correct questions per arm are lexically blocked.
Do not call the schema failures simple offset errors or treat unknown as safe
affirmative verification. Rejected original content was not retained and cannot
be reconstructed from the old error-type counters.

| Arm | New calls | Intervention |
|---|---:|---|
| A | 36 | Fresh original L1 interface, with safe detailed diagnostics |
| B | 36 | Same semantic fields; exact quote plus occurrence instead of model-computed offsets |
| P | 36 | Fresh one-shot current planner, P0 projected catalog |
| S1 | 36 | Select one aggregate or two ratio operands from a generated catalog |
| S2 | 36 | Same IDs, definitions and candidates as S1, reversed display order |

Same 36 authored development questions, seed-frozen interleaved schedule, one
request per arm/question. A/B and P/S1/S2 can be prepared independently; calls
remain serial to the existing configured Gemma gateway. Retain three languages
and all six families. No challenge, repeated-session confirmation, reasoning,
repair turn or extra diagnostic-call allocation in this 180-attempt budget.
No retry of failed/malformed responses. Stop after three consecutive transport
errors; source/input drift or exposure violation invalidates/stops the run.

Settings: temperature 0, thinking off, maximum 4096 output tokens, 60-second
timeout, SDK retries 0. Opaque existing .env credential; no DB credentials needed.
Outbound: authored questions, value-free schema, reviewed business definitions,
candidate aggregate/filter cards and output schemas. No SQL, rows, gold profiles,
gold plans, correctness labels, reference answers or previous model proposals.
Only S arms see independently generated typed candidates. Record request hashes,
catalog/order/ID bindings, model usage, safe diagnostic codes and source identity.

## B input ruler: exact occurrences, unchanged meaning

Keep every non-span field of the existing Interpretation, including explicit
population policy, count/sum/DISTINCT basis, uncertainty, grouping and label.
The proposed span has `text`, required nonnegative integer `occurrence`, `role`,
`scope`, `concept`. Occurrence is zero-based among all exact Unicode code-point
matches, including overlapping starts. No case folding, Unicode normalization,
whitespace repair, fuzzy retrieval or automatic first-occurrence fallback.
Boolean/float indices, missing/out-of-range occurrence and absent text fail.

An adapter will calculate start/end ONLY; it cannot alter role, concept, scope,
polarity, entity, operation, population or uncertainty. The resulting object
must pass the unchanged final Interpretation and existing integrity validator.
Locating the text does not prove its meaning. Exact-span gold scores and semantic
core scores stay separate. Old A/v1 scores are not recomputed under relaxed rules.
The new wire schema cannot be passed directly to the old parser; its rejection
is correct and remains tested. No general resolver exists in this checkpoint.

## Selector ruler: typed operands, not gold answer choices

Avoid enumerating a large Cartesian product of complete ratio plans. Offer
atomic aggregate/filter candidates; the selector chooses `slots={value: id}`
or `{numerator: id, denominator: id}`. This tests bounded operand selection,
not whole-plan menu selection or extra semantic verification.

Proposed envelope: `decision=pick|clarify|no_candidate`, `slots`, `output_label`
and `reason`. Pick requires a complete slot form, nonempty IDs, no refusal reason,
and different IDs for a ratio. Clarify has empty slots and reason ambiguous or
missing_definition. No-candidate has empty slots and reason outside_catalog.
Declines cannot carry an output label. The binder must additionally check
membership in this catalog, same-table ratio composition, domain/compiler
validity and the requested output label. Schema-valid IDs do not prove membership.
An outside-catalog result is a candidate-coverage failure, not a correct claim
that the user's meaning is missing or unexpressible by the product algebra.

Catalog rules to implement after approval:

- Input only the projected schema and P0 reviewed overlay, never question/gold
  families, expected plans or data instances. Same source catalog for all its
  development questions; no per-question lexical pruning or targeted additions.
- Enumerate COUNT rows, SUM numeric columns and COUNT DISTINCT columns. Collapse
  single nonnullable primary-key DISTINCT to the existing row-count equivalent.
  Cross with no filter or one IS NULL/NOT NULL predicate on a nullable column.
  Include reviewed metric definitions with their provenance; do not fabricate
  business bindings. Deduplicate only with the bounded established laws, not
  because two plans happen to return equal fixture values.
- At most 64 atomic candidates per projected source; fail explicitly if the
  catalog cannot fit. Do not silently truncate based on gold coverage. Freeze
  actual cardinalities and payload sizes before model calls.
- Stable opaque IDs bound to canonical definitions within the catalog; reversal
  changes order only. A label/ID collision or stale/unknown ID refuses. Raw SQL
  and result values never appear in candidate cards. Reviewed names/provenance
  remain attached so representation changes are documented, not hidden.
- Before live work, independently check all clear gold meanings are expressible
  by at least one candidate/slot combination, and the ambiguous rates still have
  competing readings. Report coverage failure separately; never patch the
  inference catalog by copying a missing gold plan. Current ruler tests establish
  forms and invariants only, not implemented generator coverage.

S1/S2 are not isolated syntax changes relative to P: the constrained action
space and explicit cards change the task. A/B changes evidence localization,
not the final semantic standard. Record these attribution limits.

## Diagnostics and acceptance

Use an allowlist of fixed reason codes and fixed schema-path components, with
bounded numeric indices, at most eight errors/response and aggregate counts.
Unknown reasons become unclassified_validation. Never dump exception strings,
Pydantic input/ctx/msg, arbitrary returned dictionary keys, rejected raw text or
reasoning. A synthetic sentinel in arbitrary error input/keys must not survive.
Independent field diagnostics may measure semantic-core correctness even when
location fails, but such diagnostics must NEVER turn that response into a pass
or feed a downstream decision. They are distinct from final valid-output scores.

Readiness/selection conditions, frozen before calls:

- B: at least 35/36 valid final annotations is an engineering-entry threshold,
  not a product reliability estimate. Report semantic core accuracy, each field,
  exact spans, ambiguity recognition and valid/total denominators separately.
- A proposed contextual gate must retain the correct fixed controls and have
  zero affirmative passes on known wrong/unresolved controls. Unknown is never
  an allow. Both stable misreadings and genuine positive business predicates
  remain mandatory diagnostic controls.
- Selector: improve at least two families against fresh P without losing a
  previously correct control or adding unjustified answers to unresolved cases.
  Count clarity/absence decisions only against their correct gold states.
  Measure answer correctness and ID/semantic stability under order reversal;
  a semantic flip on these controls prevents advancement.
- Reuse all captured outputs for independent compiler/reference checks on the
  three fictional instances and actual ask replay. Contrast current policy,
  isolated no-lexical shadow and contextual checks; report rescued, newly wrong,
  unresolved, unknown, refused and malformed outcomes separately. No new model
  calls for this replay; preserve production gate and verification semantics.

No automatic integration of two individually promising arms. A passing screen
only justifies a separately budgeted cross-session confirmation and subsequently
the still-unrun 24-question author-frozen challenge. It is not a deployment gate
or a blind real-user generalization result. If B mainly fixes offsets but meaning
still fails, stop that line; do not expand word lists or N to manufacture a gain.

## Checkpoint evidence and exact follow-up

Specifications: `tests/fixtures/metric_wire_rulers.json` and
`tests/contract/t0/test_metric_wire_selection_rulers.py`. Test-only types are not
imported by evals/src. They pin occurrence vectors, role preservation, selector
forms/refusals, and existing inconsistency rejection on fixed synthetic inputs.

Static/green rulers are intentional: extending the old parser to accept the new
wire would violate the requirement that it remain unchanged. Missing-import
failures would provide no behavioral evidence. The future adapter and binder
must implement these specifications after explicit follow-up; no generator,
resolver, diagnostic adapter or new model runner is implemented at this stage.

Required follow-up at the checkpoint: approve implementing these two research
interfaces and then consuming the already scoped maximum 180 Gemma attempts.
This is not a renewed request for endpoint credentials, DB access, Git permission
or a production semantics decision.
