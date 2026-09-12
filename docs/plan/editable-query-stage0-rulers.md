# Editable-query Stage-0: calculation fidelity and review identity rulers

2026-09-12. Status: ruler checkpoint complete, awaiting implementation approval.
Final focused 272 pass / 3 fail; static pass; offline 1,858 pass / the same
3 fail. They expose reference_eval ignoring named_segments; no missing-import
failure or editor readiness claim. See `../research/editable-query-ruler-01.md`
and `evidence/editable-query-ruler-01.json`. Implementation remains untouched.
Owner request: "好...可以開始下一步 應該是 主線照常推進 editable-query Stage-0 rulers?".
This authorizes the ruler phase of `editable-query-feasibility.md`, not the
editor, confirmation handler, human study or production integration. Root owns
the complete surface, baseline clean dev `8c9e7c5`. Standing local-commit
permission remains valid; no push. Earlier plan-only/no-Git text is historical.

## Scope and permission boundary

Write new test-only specification fixtures, contract tests and research records.
Read existing source and fictional fixtures; run local Python/DuckDB/reference
and captured-plan actual-ask checks. No new evals/src implementation, model or
external DB calls, credential access, packages, migrations, participant contact,
production gate/status change or persisted user preference. No new live budget.
Preserve old inputs, scores and unrelated work. Stop at the completed ruler for
explicit implementation follow-up, even if static specification tests pass.

## What this checkpoint establishes

Separate three things: the intended card/edit contract, correctness of the
existing computations used by it, and whether a future renderer/editor actually
implements the contract. This slice establishes the first two only. A future
renderer is not required to exist for a meaningful ruler: missing imports would
be setup failures, not evidence. Test-only hand cards and transition vectors
are the executable specification. They must never be imported by an editor as
its implementation or presented as a completed UI/human-recognition test.

Existing computation violations are ordinary failing behavioral tests. Keep
them visible, name the subsystem, and do not repair implementation in this
ruler-only phase. An existing compact interpretation may be characterized as
insufficient for the new full-card requirement without calling its old contract
broken or quietly changing it.

## Initial closed fragment

- One explicit base table; one scalar count, count-distinct or sum, or a ratio
  of two such operands; one output label. Raw or existing reviewed metrics.
- Same-table NULL/not-NULL predicates at plan, metric and operand scope; the
  fixture's invertible NULL-based default/named segment. Other predicates must
  remain outside this initial prototype until their fidelity has rulers.
- No time, grouping, joins, order/LIMIT, having, share, growth, latest or without.
  No field may be silently removed to fit. Unknown identifiers, ratio wrapper
  filters and existing forbidden shapes keep their domain/compiler refusals.
- Display/selection use the visible source-bound fixture schema and definitions;
  a full unfiltered registry cannot expose hidden columns. No real PII or sampled
  values enter this research. This is not the deferred production PII UI design.
- Segment state is supplied from actual orchestration, never guessed by the
  renderer from the question. A named segment can still exclude its rows from
  the other ratio operand; "named" does not mean globally unrestricted.

## Hand-written card fact contract

`tests/fixtures/editable_query_rulers.json` contains 19 cards, using the frozen
three instances in `evals/fixtures/metric_selection.json` plus four explicit
plan fixtures. Values are hand-authored, not derived from the compiler or grader.
All synthetic origins and file hashes are recorded; no captured customer inputs
are necessary. The new cards are specification examples, not participant tasks
or an estimate of natural model error frequency.

Every card explicitly gives:

1. Base table, unrestricted time and no grouping for this fragment.
2. Output label separate from population. A label containing "退貨" does not
   add a return filter. Human edits may supply any domain-valid explicit label;
   a model selector's old "label must appear in the question" restriction is
   not silently changed or reused as human-edit parsing.
3. Value, or numerator and denominator separately. Each states aggregate,
   counted/summed column, counting unit, duplicate and NULL behavior, and the
   zero-row outcome. Count counts zero; sum over no non-NULL values is NULL.
   A ratio with a zero/NULL denominator is NULL, never an invented zero.
4. Plan-wide predicates plus each operand's expanded predicates, retaining
   origin (question plan, operand, reviewed metric or segment). All predicates
   are conjunctive here. The display includes both levels; it must not omit a
   common predicate merely because it is absent from the operand's own list.
5. Actual applied segment IDs, distinct from requested/named segment IDs.
6. Definition source and unchanged current verification level. A reviewed
   definition being selected does not prove that the question requested it.

Business labels and unit names live in fixture/overlay data. The future card
must expose the bound computation, not paraphrase the question, invoke a model
or normalize a wrong proposal toward gold. Repeated IDs and nullable values in
the fixtures distinguish rows, non-NULL column counts and distinct entities.
Hand facts also include default exclusion, named lifting, operand-level segment
exclusion, filtered ratios, empty sums and zero-denominator controls.

The test-only facts-to-raw-plan projection is solely a check that the declared
facts have the independently specified values. It neither generates facts from
a proposal nor proves a renderer correct by round-tripping its own output.
Original compiled SQL and the reference each face the hand answers separately.

## Editing contract, not model-based correction

Allowed later actions: replace one whole operand with an offered source-bound
candidate, edit the explicit output label, no-op, or decline/abstain. Do not
invent a basis/population Cartesian product or edit a reviewed metric's internal
filter while retaining its reviewed name. The catalog is derived without gold,
question meaning or current error labels; options are not tailored to reveal
the expected answer.

Whole-operand replacement intentionally replaces its old extra predicates too;
the new complete definition and any removed restrictions must be displayed.
The action must say it replaces the complete calculation, not pretend to be a
basis-only toggle when it also changes population. Preserve plan-wide filters, the
other ratio operand, output label and unrelated context. Unknown/cross-source
candidates or incompatible combinations fail atomically, leaving the previous
state intact. Existing validation/policy/literal/self-check/ask gates remain
mandatory. No convenience edit can convert a production refusal into an answer.

Do not use semantic-catalog canonicalization as an implicit no-op rewrite:
equivalent raw/reviewed forms can have different provenance and verification.
A no-op preserves the exact bound plan. A label-only edit changes no computation,
but it still changes what the user reviewed and invalidates that review.

## Review identity and lifecycle

This is an in-memory research identity, not a signature, credential, persistent
API, authorization grant or secure anti-tampering mechanism. Bind all fields in
`required_identity_fields`: request and question, full schema and overlay,
requested/default/named/applied segment state, as_of, source revision, display
revision, full offered catalog, complete plan including label, effective card
facts, gate state, fictional data revision, and a monotonic review revision.
Use deterministic JSON hashing; missing fields are invalid, not empty defaults.
Semantic candidate IDs alone do not bind current descriptions or provenance.

An explicit human confirm event for the current complete identity may record
review only after the current gate permits answering. Agent-inferred agreement,
timeout, no choice, "none of these", missing definition, inability to decide,
stale identity and refusal are not confirmation. Neither a click nor a matching
hash certifies human comprehension, correct intent, or upgrades `verified`.

Any accepted change of a bound field invalidates confirmation and marks old
results stale. Changing A to B and back to A needs a fresh review revision; an
old event must not resurrect. Invalid edits leave state unchanged, while a
genuine no-op preserves it. Post-review normalization or context drift requires
redisplay and new confirmation, never silent execution of a changed meaning.
The fixture data hash binds this local experiment only; it is not a production
database-snapshot/freshness guarantee. Numeric results remain attached to the
exact local calculation/data identity and cannot be resubmitted as a new result.

Cards remain accessible even without a disagreement alert: a detector may
miss a consistently wrong plan. Its absence cannot grant confirmation, hide the
definition, or remove the correction path. There is no detector integration here.

## Acceptance and next checkpoint

Ruler evidence must account for every card, instance, engine, missing result and
refusal. Report specification-vector passes separately from behavioral failures.
Do not suppress a failed named-segment comparison to claim value readiness.
After owner review, implementation must test actual render/edit/confirmation
functions against these rulers and repair any confirmed existing-contract gap
before Stage-0 can pass. Only then can a separately coordinated human pilot test
whether people notice and fix mistakes. Scripted edits do not answer that question.

Focused tests during authoring, one static/offline closeout on the final source.
No live study, hypothesis expansion, production promotion or human recruitment
is authorized by a passing ruler alone.
