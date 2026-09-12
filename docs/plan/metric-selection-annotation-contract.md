# Metric-selection annotation ruler v1

Follow-up 2026-09-12: owner said "同意，gemma 呼叫也 ok", approving the bounded
research implementation and initial 180 serial calls. The checkpoint snapshot
below remains historical; no gold or production contract was changed. Runtime
research types are checked against this original ruler's schema and annotations.

Status: RULER CHECKPOINT, 2026-09-12. Root owns this bounded slice.
Permission source: owner said "沒問題...按照你的想法/順序組織測試驗證"
after the literature follow-up. This authorizes the planned Phase-0 rulers;
follow-up approval is still required before implementing the new grader.
No production gate/prompt, old v2 evaluator, model, database or Git writes.

## Outcome and artifacts

- `evals/cases/concepts/metric_selection_ruler.yaml`: 36 development questions
  in six paired families, 24 author-visible challenge questions in four other
  families; three languages. The author knows these questions and golds.
- `tests/contract/t0/test_metric_selection_ruler.py`: test-only payload schema,
  18 plans, three fictional instances, hand answers, distinguishing-witness
  assertions and characterization of the existing lexical gate/v2 checker.
- `../research/metric-selection-ruler-01.md`: validation and known limits.
- `.artifacts/metric-selection-ruler-20260912/`: local validation artifacts.
- `evidence/metric-selection-ruler-01.json`: durable evidence summary.

The test-only types are specifications, not a language parser, generalized
semantic grader, inference payload builder or production implementation.
No src/ or existing evals Python module changed. Fixtures contain only authored
questions and fictional data. One writer; process-name-only preflight found
no Python/regression process. No command arguments or environments were read.

## Proposed annotation contract

Each translated question has these fields:

| Field | Meaning |
|---|---|
| `state` | `clear`, `ambiguous`, or `missing_definition` |
| `basis` | Logical operation (`count`, `sum`, `count_distinct`), entity/table, column if needed, and value/numerator/denominator role |
| `populations` | Explicit `all_rows`, `constrained`, or `unresolved`, separately for population/numerator/denominator |
| `requirements` | Named concept, include/exclude/unrestricted polarity, and operand scope |
| `grouping` | `none` or `unspecified` within this bounded study |
| `spans` | Exact occurrence text, start/end Unicode code-point offsets, role and scope; end exclusive |
| `unresolved` | Missing measure basis, denominator population or business binding |
| `output_label` | Exact requested label, otherwise null; applied to the fixed plan in that language, never a population predicate |

No field means "the answer is certified". `clear` expresses the annotator's
or future model's claim, not a server guarantee. Shape validation cannot prove
the claim. Valid spans can still be assigned the wrong meaning; a test pins
this limitation explicitly.

`populations` is required. Empty `requirements` alone must never infer
`all_rows`: a model must explicitly claim it, and gold reviews judge that claim.
In this fixture there are no default-excluded segments or hidden population
restrictions. The unqualified transaction-count imperative has an authored
total-count reading in that context, not a universal business default.
Unknown or missing definitions cannot receive a full match merely because no
predicate was extracted. `ambiguous_rate` intentionally leaves the measure
and denominator unresolved; an unbound refund request remains a real request.

The basis is logical, not a demand for exact syntax or a specific metric ID.
For example, COUNT(member_id) ignoring NULL and COUNT(*) filtered to non-NULL
members answer the same member-transaction count; COUNT(DISTINCT member_id)
does not. Raw and reviewed returns aggregates are equivalent controls.
Three instances support these fixture results; general equivalence requires
supported laws, not finite-data coincidence alone.

Spans describe occurrences, not a global word list. A question may contain
both an output action and a business predicate, or a quoted label and a
predicate. Negation targets its explicit scope. Grouping negation is not
population exclusion. Binding maps use the existing reviewed POS definition;
the service projection deliberately has no refund definition.

## Evaluation boundary to approve next

The next grader should compare the model's annotation with the frozen authored
annotation, and separately evaluate fixed/captured plans on these bounded
measure/population/grouping/label obligations. Record unknown/unsupported
instead of guessing outside the covered fragment. Do not turn the new fields
into a universal whole-answer certificate or reinterpret v2's `pass`.

Gold plan lists are reviewed specification candidates, not the inference-time
candidate generator. Structural/identifier/offset validation is implemented
only in tests; no NL correctness function or new judge is implemented yet.
Challenge integrity and local plan values were checked, but no model has been
tested or tuned on the challenge. This is not a real-user blind holdout.

## Why the checkpoint does not force a red v2 test

Three characterizations show that v2 passes the required returns/member
constraint while the plan uses the wrong count/sum/DISTINCT basis. Independent
hand answers, compiler execution and reference evaluation establish the numeric
difference. Requiring v2 to reject these would silently extend its existing
contract, so these are green characterization tests, not missing-import or
artificial red failures. The new test-only schema establishes the intended
larger research contract for review, without implementing its grader.

## Next order and stops

After explicit checkpoint follow-up: implement the research grader and exact
input-exposure guards; verify with fake clients and fixed plans; then execute
the previously proposed 144 planner + 36 activation calls serially. Freeze
catalog transformations and confirm their effective definitions before calls.
The 180/444 call ceilings remain unchanged and unconsumed. No production
promotion, gate replacement, verification-status change, SQL/rows to models,
new model provider or administrative DB action is authorized by this document.

New semantic gaps stop only their dependent work; continue independent checks.
No commit or push in this slice. Preserve the original dirty worktree.
