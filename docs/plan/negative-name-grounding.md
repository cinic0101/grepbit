# Negative name grounding ruler (proposed, not implemented)

Owner approved adding the contract and tests after `b8334e2`. This is the
two-phase checkpoint: specifications and executable rulers only, no runtime,
prompt, overlay schema, DB state or historical score changes. Local commit is
authorized by the owner's standing instruction; no push. Root owns this slice.
No model calls, network data or live DB are needed; all values are fictional.

Status: RULER READY, waiting for explicit checkpoint approval. Final new ruler:
53 cases, **36 expected assertion failures, 17 passes**, zero errors/skips.
Existing grounding/ask/acceptance controls: **91 passes**. The first draft had
an incorrectly assigned enum in its positive control; it was fixed in the test
fixture and is not counted as checkpoint evidence. Final artifacts:
`.artifacts/negative-grounding-ruler-20260913/{ruler-final,existing-controls}`.
Manifest: `../../evidence/negative-name-grounding-ruler-01.json`.

Evidence: `../research/reliability-stage-01.md` demonstrates short-name NE
filters escaping EQ/IN-only existence checks and post-miss grounding. A server
can execute that plan correctly while answering the wrong population.

## Proposed boundary

With ordinary literal-check and grounding settings enabled, extend binding
checks to **model-authored text NE filters on visible, explicitly groundable
overlay columns**. Use effective overlay switches, not the mere presence of a
column in an index. No new lexical trigger, datasource name or special business
word. An injected index must not authorize an unlisted, hidden or ground-off
column. Existing explicit personal-column overrides are neither added nor
expanded; existing personal defaults remain ground-off.

The affected occurrences are plan filters, plain/reviewed measure extra filters,
either ratio operand's extra filters, and `without.filters`. Do not traverse
reviewed metric definitions or segment definitions, which remain reviewed data.
No new ratio-wrapper filters. This does not broaden nested positive EQ/IN checks
as a side effect; their existing coverage remains a separately recorded gap.

| Evidence for an eligible NE literal | Proposed behavior |
|---|---|
| Exact stored value exists | Keep it and NE unchanged, even if other names share the prefix. |
| Exact value absent, existing resolver finds one clear candidate | Replace only that eligible occurrence's value; keep column, operator, scope and siblings unchanged. Recompile, recheck SQL policy and recheck the selected value before execution. |
| Exact value absent, candidates ambiguous | `clarify / filter_value_ambiguous`; do not execute a query answer. |
| Exact value absent, no candidate | `clarify / filter_value_not_found`; do not pretend the intended named population was successfully excluded. |
| Exact value absent, index unavailable/column skipped | Same protective not-found refusal; an unavailable index is not proof of an empty candidate universe. |
| Selected candidate fails the authoritative recheck | Refuse; no query answer using a stale candidate. |
| Unlisted/non-groundable column, non-text NE, other operator | No new NE lookup/rewrite/refusal. Keep existing SQL behavior and guards. |

The no-candidate row is a **proposed product default requiring follow-up approval**:
ground opt-in currently permits matching, whereas this adds binding assurance
to negative name use. It can refuse an intentional exclusion of an absent name
on an opted-in column. We prefer exposing that uncertainty to silently accepting
an unbound name. It is not a claim that every absent negative literal is invalid:
ordinary non-grounded category predicates retain their existing meaning. If
intentional absent-name exclusion must also be supported on opted-in columns,
decide an explicit literal-intent mechanism separately; do not infer it with a
word list or silently weaken this ruler. No new API escape flag is proposed here.

Existing research ablations (`grounding=False` or `literal_check=False`) remain
ablations, not a production safety claim or a user-intent certification path.

## Preservation and disclosure

- Preserve SQL three-valued logic: `name <> X` does not include NULL names.
  Do not add `OR name IS NULL`, drop the predicate or substitute LIKE/NOT LIKE.
- Do not move a numerator restriction into the denominator/global scope, or a
  `without` condition out of its child. Repeated occurrences remain separate;
  a lookup may be deduplicated but may not merge predicate scopes.
- Do not mutate the input proposal, overlay definitions or unrelated predicates.
- Keep existing verification levels; grounding similarity never proves intent.
- Reuse existing grounding trace and assumptions to name original/stored values
  and the column; effective-computation disclosure must still describe the
  actual negative predicate and its scope, including nested paths. No new card
  or model-written certification. Hidden/personal values must not leak through
  candidate diagnostics. Candidate strings are bound parameters, not SQL text.
- Existing positive EQ/IN behavior, numeric component filters (e.g. bonus = 0),
  time rules and other gates remain unchanged.

## Acceptance after the ruler checkpoint

First make the new rulers pass without modifying their expected populations.
Then run existing grounding, ask, candidate-wire, policy and acceptance tests;
one broad offline gate at implementation closeout. Replay the frozen negative
plans against independent values, then separately budget the affected live
grounding panel (both names supplied fully and abbreviated). Keep authored
smoke evidence separate from unseen-user generalization. No implementation or
model experiment is authorized merely by this document.
