# Metric selection and lexical gates: deeper literature review

Date: 2026-09-12. Completed literature follow-up, not a completed model study.
Owner requested "好...幫我繼續研究下" after the
[proposed experiment](../plan/metric-selection-and-lexical-gate.md).
Scope: primary-source reading, local contract inspection and plan refinement.
No production, grader, fixture or historical-score changes; no model/DB calls,
package installs, stage, commit or push. Prior dirty work remains intact.

## 1. Candidate selection: borrow a witness, not a new oracle

[DPC, ACL 2026 according to the authors' repository](https://github.com/HKUSTDial/DPC)
uses SQL/Python consistency on a small distinguishing database.
The [paper's Sections 3.2-3.5](https://arxiv.org/html/2604.15163v2) first group
candidates by original-database results, choose two dominant groups, synthesize
distinguishing data, then compare against a model-generated Python answer.
Its normalization includes rounding numbers to four decimals and reducing
timestamps to dates. Table 2 reports BIRD Qwen selection accuracy of 47.6%
against 46.4% self-consistency, below the 57.6% candidate-pool ceiling.

Our assessment, not a paper guarantee: a generated Python answer does not prove
that either program understood the question. Original-data clustering can hide
distinct plans with coincidentally equal results. The normalization is not
suitable as Grepbit's strict financial/time comparator.

Adopt only the distinguishing-witness idea for local evaluation. Do not copy
the agents, send rows/SQL to a model, execute model-generated Python, or change
the result comparator. Every known non-equivalent plan pair should have a
fixture witness where its results differ. Failure to find one means
`not_distinguished`, not equivalent. The witness reveals a difference; reviewed
question meaning still determines which answer is correct.

## 2. Best-of-N: isolate generation from selection

[GradeSQL, SURGeLLM workshop at ACL 2026](https://arxiv.org/html/2606.30851)
compares selectors using the same candidate pools. Its verifier is trained
using execution-labelled candidates; Section 3.2 discards execution failures
from that training data. The reproduction uses stochastic generation, including
temperature 0.8 and N=8. The paper notes that verifier training is additional
compute, so this is not a fully compute-matched comparison.

A trained scorer is not equivalent to asking Gemma again, and these results
do not rehabilitate repeated identical T=0 samples. Execution labels can
inherit coincidental matches or incorrect golds. No fine-tuning proposal until
labels and candidate coverage are trustworthy. Log generation, selection and
training costs separately. Failed candidates remain in attempted-call and
pipeline denominators even if later excluded from training data.

For P4, distinguish end-to-end joint planner versus candidate selector
(different generation workflows) from selection on an identical frozen pool.
The latter can reuse captured pools and offline majority/oracle baselines.
Another model-based selector must replace an arm or have a revised budget.
Represent missing correct candidates, all-wrong pools, multiple acceptable
plans and unresolved questions; an argmax always choosing one is not abstention.

## 3. SQLens is an offline debugging reference

[SQLens, Sections 3.3 and 6](https://arxiv.org/html/2506.04494)
aggregates noisy signals using weak supervision and explicitly positions itself
as an offline asynchronous debugging tool, not a latency-sensitive pipeline.
Its correction study records fixes and breakages; database-derived signals
are not automatically semantic proofs either.

Borrow a per-stage error ledger and detection-before-repair discipline. Do not
install weak supervision or iterative correction merely to resolve two known
lexical cases. Distinguish sound structural checks from heuristics such as
"this result looks unusual"; zero/empty answers can be correct.

## 4. Word-sense research supports diagnosis, not a turnkey gate

[Do Large Language Models Understand Word Senses?, EMNLP 2025](https://arxiv.org/html/2509.13905v1)
compares sense selection and generative explanations. Its limitations explicitly
state that all experiments are English; strong explanation results do not
establish Chinese/Japanese business-scope accuracy.
[Prompt Balance Matters, GlobalNLP 2025](https://aclanthology.org/2025.globalnlp-1.2/)
studies English, German, Spanish, French and Italian and finds language-dependent
effects of imbalanced few-shot examples. It does not test our languages/model.
[WiC/WSD transfer, LREC 2026](https://aclanthology.org/2026.lrec-1.785/)
uses English datasets and a trained sentence transformer; a multilingual
backbone is not evidence of multilingual validation.

Our adaptation: annotate contextual meaning separately from business binding,
and measure rather than assume cross-language transfer. Do not replace the JSON
vocabulary with WordNet/BabelNet, an expanding sense dictionary, or a trained
encoder before showing an advantage on this task.

Ruler examples, not measured cases or frozen challenge material:

| Question | What must be distinguished |
|---|---|
| Return the transaction count. | Output action, not a returns predicate |
| Return the count of returned transactions. | First occurrence is output action; second is population selection |
| 回傳交易筆數。 / 回傳退貨交易筆數。 | Similar output request, different business population |
| 把所有交易筆數的欄名設成「退貨統計」。 | Label mention must not add a return-only filter |
| 不要按門市分組，列出退貨交易筆數。 | Negation targets grouping, not the returns predicate |
| 原交易編號有值的交易筆數。 | Can express the fixture's return condition without a returns keyword |

Annotate per occurrence/span and scope, not one role for the entire question.
Correct sense identification still does not prove correct aggregation, polarity,
operand placement or counted entity. A short gloss may help manual diagnosis;
it is not a trusted reasoning trace or a production certificate. No extra
explanation-generation arm is added now.

## 5. Reviewed definitions are not selection proofs

[dbt's April 2026 benchmark](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026)
is vendor evidence, not a peer-reviewed paper. It reports eleven questions
with twenty repetitions and includes question-driven remodeling to make those
questions answerable through the semantic layer. Useful engineering evidence,
but not broad unseen-question generalization.

For Grepbit, a reviewed formula establishes what a metric computes, not whether
the question requested it. P1 remains a knowledge/choice-set intervention;
P2/P3 must preserve meanings. A balanced catalog is an experiment, not a change
to the existing business definition of `transaction_count`. Do not infer an
ontology is needed or that catalog coverage alone solves selection.

## 6. Concrete refinements to the next ruler slice

Keep three distinct questions, not necessarily three runtime services:

1. Language: did the request actually require the concept/operation/scope?
   LLM inference at this boundary remains fallible.
2. Alignment: given explicit reviewed requirements, does the expanded plan
   implement them? Check supported semantics; missing bindings remain unknown.
3. Execution: does compiled SQL implement that plan? Existing differential and
   golden tests address this boundary, not natural-language correctness.

`application/shapes.py::unmapped_concepts` checks lexical/name traces, not the
stronger predicate/scope alignment above. Changing its refusal authority or
strengthening its contract requires the existing ruler checkpoint.

Next rulers should:

- Include explicit all-population controls, not only requests whose silence
  could be treated as unrestricted. Preserve genuinely unresolved populations;
  do not broaden v2's certificate.
- Include mixed-use spans, negation scope and predicates without vocabulary hits.
- Record operation/entity, DISTINCT/NULL behavior and effective predicates from
  each reviewed metric. Check presentation transforms preserve these signatures.
  Map opaque IDs back before existing gate replay, isolating ID priming from
  changes to the gate's name-based behavior.
- Require distinguishing witnesses for inequivalent mutants. Respect schema
  constraints: a PK violation cannot distinguish plans equivalent under that PK.
  Preserve exact column roles, NULLs, duplicates, required ordering, time
  precision and current numeric tolerances. No soft-score oracle.
- Record paired fixes, false blocks, newly allowed omissions, correct-to-wrong
  transitions and appropriate/unnecessary clarification, not averages alone.

Human-supplied requirements and gold-curated candidates are useful diagnostic
ceilings, not deployable language interpreters or candidate generators. Six
development families also do not support a precise release-risk estimate from
cluster bootstrap; show family counts and paired changes without treating
translations, repetitions or DB instances as independent new questions.

## Disposition and evidence limits

Keep the initial 180-call and conditional 444-call ceilings. None consumed.
First rule the question/plan/witness matrix, then run planner/activation studies
after follow-up authorization at the grading checkpoint. No DPC agents,
reward-model training, WSD service or semantic-layer framework is proposed now.

Read public HTML method/evaluation sections for DPC, GradeSQL, SQLens and the
EMNLP WSD study; publication abstracts for the two additional WSD/WiC studies;
the first-party dbt benchmark article. No reproduction, released-code audit or
exhaustive literature review is claimed. The current application gate and plan
were inspected locally. This note and the plan amendment are the only changes.
