# Concept obligations v2: ruler and validation plan

Status: approved slice COMPLETE, 2026-09-12. The owner replied to the exact
v2 interface checkpoint: "同意，依此繼續". Reference/generator corrections and
the research-only v2 checker pass validation. The 144-call main comparison and
separate authorized 18-call shadow are complete; neither arm is promoted.
See `../research/concept-obligations-v2-02.md`. The larger family expansion is
not started because targeted extraction/joint failures remain. Production
integration, Git writes and historical rescoring remain excluded.
The checkpoint results (PostgreSQL 24/24;
offline 601 passed / 4 reference failures) remain in
`../research/concept-obligations-v2-01.md` and its original evidence manifest.

## Outcome, authority and ownership

The user accepted the previous concept-search recommendations and requested
another testing/validation round, explicitly allowing web, PostgreSQL and
Gemma calls. They then added: "假如過程中有新的發現，你想測試驗證，也沒問題".
Those messages authorize this investigation and additional bounded probes;
this record is not a new source of authority. The root owns the coupled work.
Baseline: dev at 746f168 with the prior dirty work preserved. No Git writes,
package installation, customer-data sampling, persistent database mutation,
new credential copies or production integration.

The current AGENTS two-phase rule applies to the materially different
evaluation interface below. First specify and validate rulers, then obtain
explicit follow-up before implementing it. Existing-contract diagnostics
are independent and permitted. Do not reinterpret the earlier approval of
period semantics as approval of this new interface.

## The smallest interface justified by observed failures

Keep v1 inputs, prompts, checker and scores unchanged. A separately versioned
research v2 output has three required lists (extra fields forbidden):

| Field | Bounded content | Why needed |
|---|---|---|
| `requirements` | concept ID, polarity `include/exclude/unrestricted`, role `population/numerator/denominator`, exact question span | Explicit no-filter and denominator obligations cannot be encoded in v1. |
| `forbidden_groupings` | concept ID and exact question span | Not filtering and not grouping are different promises. |
| `unresolved` | aspect `measure_basis/denominator_population/qualifier` and exact span | Preserve partial known requirements without choosing an unspecified rate interpretation. |

No additional `intent` state: three empty lists mean no obligation was
extracted, **not** that the question or plan is correct. This removes redundant
state rather than adding a parallel status machine. Repeated concept IDs in
different roles are valid; duplicate `(concept, role)` entries, even if their
polarities differ, are invalid. Unknown IDs and fabricated spans are invalid.
These checks validate representation, not understanding of the question.

An explicit request whose reviewed binding is missing stays a requirement.
Binding availability is supplied by the server, not inferred away by the LLM.
No new general business ontology, keyword dictionary, SQL algebra, or universal
semantic IR is proposed. The test-only schema is an executable draft, not a
runtime implementation. Labels remain author-proposed pending this review.

### Meaning of the bounded checker

- `population` is the effective input of one plain aggregate, including its
  operand and reviewed-metric filters. For ratios, specify numerator and
  denominator separately; a population-role requirement on a ratio is outside
  this first version and returns unknown. Whole shares and complex constructs
  remain unknown in v2 until separately ruled; retain v1 measurements as history.
- Each ratio operand includes plan-wide filters, its own filters and reviewed
  metric filters. `unrestricted` forbids restriction by **that concept** at
  that scope, not every possible filter or grouping. It is never inferred from
  silence. Different concepts may have independent requirements on one operand.
- Known implicit exclusion matters too: `COUNT(binding_column)` and
  `COUNT(DISTINCT binding_column)` ignore NULL. For the present direct
  `is_null/not_null` bindings, that is not an unrestricted row count. Do not
  equate distinct count with row count or extend this into arbitrary expression
  equivalence. Check this against hand answers, not filter presence alone.
- A forbidden grouping rejects a dimension on the supplied binding column.
  This is not a classifier for every semantically related column. Unsupported
  expressions, joins, segments, ambiguous metric expansion or unrecognized
  shapes yield unknown, never an inferred pass.
- Any unresolved obligation makes the whole bounded verdict unknown, even if
  a candidate plan happens to fit one plausible reading. Missing bindings also
  prevent certification. A known supported mismatch is fail. With no extracted
  obligations the result is not_applicable, never an affirmative certificate.
- A pass proves only the supplied qualifier/grouping obligations. It does NOT
  prove their completeness, measure choice, dates, full grouping or NL intent.
  The experiment must report those separate dimensions and joint failures.

Ambiguity already exists in v1's representation. Adding a list cannot force an
LLM to retain it. If the model again drops ambiguity/prohibitions, that remains
an extraction failure and can still produce a joint escape. No deterministic
checker can recover missing language meaning from this interface alone.

## Stage 0: specification and counterexample validation now

1. Freeze v1 input and executable hashes, retain its 430 + 8 call scores.
2. Draft targeted multilingual obligations, including prohibitions, explicit
   ratio scopes, partial ambiguity, unbound requests, and no-qualifier controls.
   They are development rulers, not a held-out sample.
3. Replay all five recorded escapes with their exact observed cores. Separately
   probe implicit COUNT-column restriction and scope leakage. Never relabel the
   old fixed pairs or call the observed core a correct v2 extraction.
4. Check hand-computed asymmetric and coincidental fictional instances against
   compiled DuckDB SQL and the independent reference. PostgreSQL may execute
   the same synthetic VALUES only, in a read-only transaction as grepbit_ro.
5. Validate the draft's representations, positive controls and forbidden
   encodings statically. This is a meaningful green characterization checkpoint:
   no v2 checker exists to assert against, and demanding that v1 infer omitted
   NL meaning or accept a v2 payload would falsely specify a repair to v1.
   Record the actual v1 escapes, not xfails/import errors as intended failures.

Executed finding: the schema/legacy-characterization assertions are green,
but four independent hand-answer assertions are RED. The existing reference
counts NULL input values for `COUNT(column)`, unlike compiled DuckDB/PostgreSQL
SQL. These are actual current-contract implementation defects, not intended
v2 failures. Leave their goldens unchanged. Before model work, repair the
reference to SQL count semantics and add nullable-column count generation;
that is an existing-contract correction, not a new product-semantic decision.
This checkpoint-only slice leaves implementation files untouched.

PostgreSQL scope: localhost:5432, existing read-only fixture connection, at
most 120 bounded SELECTs including role/timeout checks, 5-second connect and
statement timeouts; no real table reads or writes. Only fictional inline rows
are sent. DSN stays in shell memory and is selected by an environment-variable
name; errors expose only exception kind/SQLSTATE. No model call is needed to
prove these arithmetic/representation failures.

## Stage 1: implement only after this interface checkpoint

Execution scope after the owner's explicit approval: use existing grepbit_ro
connections to the IoT and synthetic service fixture databases at localhost:5432
for schema introspection only (enum sampling 0); run generated SQL on 3 in-memory
DuckDB instances per schema, up to 500 generation examples each. Also repeat the
24 PostgreSQL inline VALUES goldens. Credentials remain opaque, reports use
fresh paths and redact values, no persistent writes or customer table reads.
This is a bounded prerequisite to the already specified 144-call Gemma budget.

First resolve the reference defect above and add empty/all-NULL/mixed-input,
plain/ratio/reviewed-metric regression coverage. Re-run affected synthetic
differentials on fresh artifacts; historical reports retain their original
source identity. The generator's raw count branch currently never emits a
column, so prior clean runs did not cover this form.

Implement a separate research v2 extractor/parser and bounded checker, not a
production gate. Before live work, oracle-input tests must discriminate every
supported mutant and preserve all positive controls; unknown remains explicit
for unsupported forms. Test whole-report identity, fresh outputs, sanitized
failures and model-input projection. Test two independent axes:

1. Gold obligations + candidate plans: deterministic checker soundness within
   the supported forms. Gold never reaches a live arm.
2. Extracted obligations + the same plans: extraction errors and joint escapes.

Mismatched aggregate choices must remain visible in full-answer labels even
when qualifier-only verdicts legitimately pass. A correct numeric coincidence
on one instance does not erase a structural or intent error.

## Stage 2: bounded live development, then a frozen challenge

Start with off/on single extraction, matched 4096 output tokens and 60 seconds,
temperature 0, serial calls. Draft budget: 12 targeted families x 3 languages x
2 arms x 2 time-separated rounds = 144 calls. Freeze the exact questions,
labels, source hashes, request hashes, settings, schedule and budget before
calling. No silent retries; retain invalid outputs and transport failures;
stop after three consecutive transport errors. Separation in time is a
stability observation, not proof of backend-load causality.

Destination: the existing Gemma gateway http://10.12.0.187:4000/v1, model
gemma-4-31b, existing ignored .env credential sourced opaquely. Outbound inputs
are only synthetic questions, projected schema/definitions and the versioned
response schema; no SQL, rows, labels or expected answers. Store validated
structured responses and allowlisted usage/timing/error metadata, never keys,
raw invalid provider output or reasoning text. No other provider is implied.

Then prepare up to 40 NEW semantic families, not 40 paraphrases. Whole-family
partition: 24 development, 16 challenge; all translations, minimal edits and
schema-renamed siblings stay in the same partition. Independently adjudicate
labels before model output; disputed labels are excluded pending decision.
An agent-authored/agent-visible challenge is not a blind user holdout. Record
who reviewed and saw it; if independent review is unavailable, report authored
stress-test results only. Never tune prompts after inspecting challenge results
without consuming that challenge and obtaining a new one.

Initial new-family off/on run: at most 240 calls, followed by one unchanged,
time-separated replication (another 240). Do not start this larger allocation
until the targeted test rules work. Report unsupported/unknown coverage as
well as successes, rather than selecting only questions the checker can prove.

Best-of-N is conditional, not the default: only test reranking when N=3
actually adds distinct valid meanings and candidate availability beyond N=1.
Use a separately versioned, clarified selector rubric, blinded candidate
frequencies, randomized and reversed order in replicated blocks; include
no-qualifier controls, all-wrong pools and abstention. Count pools/families,
not order permutations as independent questions. Any further budget or
post-hoc probe is recorded before calls; failed N=1 must not silently grow N.

## Stage 3: actual planner + verifier, still shadow only

Freeze the selected research baseline; run it with the real planner on
synthetic schema/overlay fixtures. Oracle label every produced plan independently
and use multi-instance hand/value checks where feasible. Compare planner alone
and planner + checker, without changing served responses. Then obtain genuinely
unseen user questions and reviewed datasource definitions for a real holdout.
No generated question set can substitute for that step.

Report separate denominators: wrong acceptances / known-wrong plans; unresolved
accepted / unresolved questions; correct plans retained / correct controls;
wrong answers / answers issued (selective risk); answers issued / all questions
(coverage); useful correct answers / all questions. A hypothetical allow policy
must be explicit: neither not_applicable nor pass is full-answer verification.
Keep schema failure, transport failure, unknown and clarification separate.
Break out language, family, available binding, source, and time block. Repeats
and translations are clustered observations, not independent confidence
samples. Do not claim a product failure rate from this diagnostic bank.

Also report extraction calls, total calls, tokens (unknown usage is not zero),
and end-to-end p50/p95 including planner, verifier, retries and fallback. Shadow
replay sums are not deployed latency. Compare risk at matched answer coverage;
blanket refusal cannot win. Product risk/coverage/latency thresholds and
production integration remain separate owner decisions, not inferred here.

## Research basis and limits

- [Zhong et al., EMNLP 2020](https://aclanthology.org/2020.emnlp-main.29/)
  motivates evaluating denotations on multiple database instances. We use small
  hand-computed distinguishing instances, not its benchmark or a correctness proof.
- [Bhaskar et al., EMNLP 2023](https://aclanthology.org/2023.emnlp-main.436/)
  demonstrates multiple plausible interpretations in text-to-SQL and distinguishes
  meaningful alternatives from token-level diversity. Our ambiguity tests require
  clarification; their top-k objective does not decide our product policy.
- [PostgreSQL aggregate semantics](https://www.postgresql.org/docs/current/functions-aggregate.html)
  distinguishes row count from non-NULL input count. The live VALUES tests
  agree with that definition; the reference evaluator currently does not.

These sources support the experimental design, not an assertion that v2 works.
