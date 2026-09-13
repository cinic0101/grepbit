# Lexical policy, semantic defaults and what the evidence supports

2026-09-13. Targeted primary-source follow-up plus repository/DB diagnosis;
not a systematic literature review or a new Gemma experiment. Owner decisions
and proposed independent experiments: `../plan/answer-acceptance-and-cause-studies.md`.

## Updated local diagnosis

### Store: absent index, not a failed trigger

In the frozen current panel, `store_partial_name_jan` passes in sampled POS
and refuses in no-sampling POS. Both have zero candidate hints and no overlay,
hence no value index. Sampled success is not evidence that post-plan grounding
ran. A different full plan hash establishes different outputs, not a causal
isolation of sampling from service variability.

The current code has two distinct mechanisms: `ValueIndex.mentions` supplies
verbatim full-value hints before planning; `resolve_plan_literals` attempts
resolution after a text equality literal misses the DB. A shortened store
name need not generate a pre-plan hint to be resolvable afterwards.

A new read-only diagnostic loads only the five public store names into an
in-memory index, with introspection sampling zero. This question yields zero
verbatim hints but the missed literal resolves uniquely to the reference
store. No model call or runtime index enablement occurred. A fictional tied-
name control stays ambiguous and an unindexed column has no resolution.
The existing POS metric overlay also has **no store grounding opt-in**;
merely loading that overlay is not enough. A minimal reviewed column policy
is the relevant next intervention, not more language triggers or global LIKE.

### Payroll: available columns, different semantic roles

Both current DB comments (“actual payment date” and “payroll period start”)
reach the schema payload. The columns are valid; information has not been
dropped by serialization. Three fixed-plan PostgreSQL checks show:

| Proposal | Context | Agrees with the legacy period-based reference |
|---|---|---|
| Raw base-salary SUM, payment-date quarters | No overlay | No |
| Same raw plan | Existing POS overlay loaded | No |
| Existing `base_salary_total` metric, payment date still proposed | Existing POS overlay loaded | Yes: compiler applies metric's period date |

This demonstrates raw-versus-reviewed time binding, not model selection
accuracy. The existing metric definition is usable, but only if selected;
loading it does not force raw aggregates to follow it. We have not measured
whether richer factual column descriptions improve selection.

The owner now accepts either reasonable payroll time basis when the question
and applicable business definition leave it open, provided the **effective**
basis is faithfully disclosed. Consequently the two legacy nonmatches above
are not automatically errors under the new policy. They remain nonmatches in
the unchanged old report. Existing department-payroll cases already allow both
time roles while quarterly payroll has only one reference; the new policy
must address this inconsistency, not silently call metadata changes a fix.

## Literature and project-specific application

1. **Behavior, not vocabulary size.** [CheckList, ACL 2020](https://aclanthology.org/2020.acl-main.442/)
   organizes tests by linguistic capability and behavioral transformation.
   Apply minimal changes that should preserve meaning (adding an output
   imperative) and changes that must alter scope (adding a genuine returns
   condition). Lexicons can generate test cases without being runtime verdicts.
   The paper does not establish a monotonic relation between dictionary size
   and error rate; our observed problem is assigning semantic authority to
   surface matches.
2. **Reasonable alternatives need explicit evaluation.**
   [Disambiguate First, Parse Later, Findings ACL 2025](https://aclanthology.org/2025.findings-acl.863/)
   studies interpretation coverage and LLM preference for some readings of
   ambiguous requests. Borrow the distinction between a defensible alternative
   and a wrong parse. Do not import its specialized infilling model or claim
   Gemma can enumerate every interpretation. Our approved disclosure policy
   is a product decision, not a result demonstrated by that paper.
3. **Balance answerability and refusal controls.**
   [Query Carefully, December 2025 preprint](https://arxiv.org/html/2512.21345v1)
   tests 80 authored no-answer questions in eight categories with Llama 3.3
   70B. Balanced examples help in that study, but column ambiguity and missing
   values remain difficult. Its few-shot retrieval draws from the same
   no-answer set excluding the current question; it is not a clean unseen-
   family estimate. Borrow category-separated errors and positive/negative
   controls, not its scores or blanket ambiguity refusal. Our product permits
   bounded, disclosed alternatives and never sends SQL/results to the LLM.
4. **Measure both failure directions.**
   [TrustSQL](https://arxiv.org/html/2403.15879v4), first posted 2024, evaluates
   feasible answers and infeasible-question abstention with penalty-based
   scoring. Borrow the separate false-refusal/wrong-answer accounting. Do not
   import its penalty weights as product policy or assume a second detector
   supplies independent evidence. A gate that always refuses is not success.
5. **Reasoning is not an abstention guarantee.**
   [AbstentionBench, NeurIPS 2025](https://papers.nips.cc/paper_files/paper/2025/hash/fb122bfc3f0127a94ded048b5b03496f-Abstract-Datasets_and_Benchmarks_Track.html)
   reports persistent abstention problems across models and tasks. This
   supports testing rather than assuming that reasoning or a confidence
   prompt fixes refusal behavior; it does not measure our Gemma deployment.
6. **Validate extras on discriminating data.**
   [Semantic Evaluation with Distilled Test Suites, EMNLP 2020](https://aclanthology.org/2020.emnlp-main.29/)
   uses multiple generated databases to assess query behavior. Reuse our
   hand-value/differential assets with distinguishing cases for scope, missing
   periods, zero denominators and NULLs. This validates computations, not
   whether a question requested a given extra measure.

Reading depth: CheckList, Disambiguate, AbstentionBench and distilled-suite
publication abstracts; Query Carefully HTML methods/results; TrustSQL abstract
and task framing. No reproduction or blanket claim of best practice. Prior
word-sense and SQLens/DPC review remains in `metric-selection-literature-02.md`;
we do not restart the failed same-model verifier/selector studies.

## Conclusion: apply methods, not another lexical framework

Keep type, identifier, authorization, literal-existence and SQL checks. Treat
linguistic matching as a heuristic, not proof of a business predicate. Measure
its false blocks and genuine omission catches using paired fixed plans before
altering its authority. No universal replacement gate is established by these
papers or our evidence. A shadow no-veto arm is a risk measurement, not a
production recommendation.

The approved product direction is narrower than “any answer plus a disclaimer”:
choose an admissible reading, expose the actual computation, and validate
related additions. Explicit contradictions and unrepresentable lease scope
still fail. This may correct overly narrow evaluation while preserving safety;
it is not proof that the model selected the user's unspoken intent.

## Validation and boundaries

Private evidence: `.artifacts/semantic-policy-20260913/preflight.json` binds
its driver hash; three read-only fixed-plan comparisons plus reference/metadata
queries on POS-test, zero model calls, no DB mutation, personal columns or
raw rows/bindings in output. Ten component/ruler controls pass; one strict
xfail demonstrates the intended old-matcher gap (one failure under
`--runxfail`). A draft test initially assumed quoted SQL identifiers; that
assertion was corrected, not counted as a product defect or ruler failure.
Full offline gate: 1,656 passed, one expected xfail, zero failures/errors.
The final static gate passes after a formatting-only wrap of the same test
reason string; no behavior changed after the offline run. Public count/hash
manifest: `evidence/lexical-policy-and-defaults-01.json`.
No production, prompt, original case/gold or historical score changed.
The new evaluation/disclosure implementation awaits its explicit ruler
checkpoint; unrelated diagnosis has been completed rather than blocked by it.
