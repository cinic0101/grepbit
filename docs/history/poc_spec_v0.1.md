# Grepbit POC Specification and Coding-Agent Delivery Guide

- **Product version:** 0.1
- **Document revision:** 0.1.43
- **Status:** Implementation Draft
- **Date:** 2026-09-08
- **Audience:** Product owners, coding agents, reviewers, and engineers
- **Primary datasource:** PostgreSQL
- **Authority:** This is the single normative Grepbit POC document

---

## 1. How to Use This Document

This document defines both the product contract and the delivery process.
Before modifying files, a coding agent MUST read the applicable `AGENTS.md`
instructions and Sections 1, 3.2, 6.4, 7, 8, and 12. Read the affected product
contracts and accepted ADRs before changing their owning surfaces; follow their
references when they affect the proposed change. Read Sections 1 through 12 in
full for core architecture or trust-boundary changes spanning subsystems.

For delivery-gate work, the coding agent MUST:

1. Identify the current delivery gate in Section 13.
2. Work only inside that gate's allowed scope.
3. Establish required rulers before compatibility-sensitive implementation.
4. Run focused validation while iterating.
5. Run the gate validation once at closeout.
6. Produce the evidence packet defined in Section 12.6.
7. Proceed only after the gate outcome is `PASS` and the next gate is authorized.

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
normative.

`AGENTS.md` is the repository's operational delta: exact commands, ownership,
authorization, architecture reminders, and Git policy. Normative product,
delivery, evaluation, and evidence contracts live here and are referenced rather
than independently restated. A new normative rule MUST replace or narrow an
existing rule, or explain why it cannot be folded into one.

Code does not silently override this specification. If accepted executable
evidence, an accepted ADR, or an owner decision proves a statement wrong or
obsolete, amend the statement, record the proof and compatibility impact, and
bump the document revision. A descriptive layout correction does not require a
product-version change, but it still updates the document revision.

When an unresolved requirement materially affects business semantics, product
or architecture decisions, public contracts, persistence, safety, scope, or
authorization, the coding agent MUST stop the dependent work and report:

- The exact conflicting or missing requirements.
- The files and components affected.
- The smallest set of product or architecture choices needed.
- A recommended choice and its trade-offs.

Routine, reversible implementation choices within the approved scope follow
existing conventions and do not require renewed approval. Continue independent
authorized work while a material decision is pending. The agent MUST NOT
silently invent business semantics, relax safety, broaden scope, or bypass an
explicit ruler checkpoint or stop-the-line condition.

---

## 2. Product Definition

### 2.1 Product statement

> Grepbit plans, executes, validates, and explains data analysis as a bounded,
> traceable sequence of evidence-producing steps.

Grepbit is not a generic Text-to-SQL endpoint. The POC must prove that reviewed
semantics, explicit evidence requirements, deterministic validation, and
transparent SQL can produce more trustworthy analytical answers than an
unvalidated SQL-generation call.

### 2.2 POC success condition

The POC succeeds only when it can:

- Produce correct structured facts against an owner-reviewed fixed dataset.
- Detect, repair, refuse, or mark inconclusive known analytical traps.
- Avoid reporting inconclusive evidence as verified truth.
- Trace each answer to semantic definitions, query attempts, parameters,
  results, validations, and claim evidence.
- Support one direct task and one dependent A-to-B task.
- Remain inside explicit query, model, time, and result budgets.
- Run a reproducible evaluation suite from a clean checkout.

Generating executable SQL by itself does not establish POC success.

### 2.3 Core runtime

```text
User question
  -> TaskIntent
  -> EvidenceRequirements
  -> short AnalysisPlan
  -> deterministic PlanGate
  -> semantic query authoring
  -> Wren compile/dry-plan
  -> physical SQL policy gate
  -> PostgreSQL execution
  -> deterministic validations
  -> ObservationDecision
       -> complete
       -> repair one query
       -> request bounded additional evidence
       -> block
  -> evidence-backed answer
```

Independent questions become separate tasks. Dependent clauses remain one task
with explicit relation dependencies.

### 2.4 Goals

The final POC MUST:

1. Register PostgreSQL datasources through secret references.
2. Introspect schemas, relations, columns, types, nullability, keys,
   constraints, and comments.
3. Load a human-reviewed Wren semantic project.
4. Preserve semantic provenance, review state, revision, and digest.
5. Produce typed task intents, evidence requirements, and plans.
6. Validate plans deterministically before execution.
7. Execute through a read-only, allowlisted PostgreSQL role.
8. Support direct and A-to-B relation-filter workflows.
9. Apply risk-based deterministic result validation.
10. Replan only when recorded evidence requirements remain unmet.
11. Return SQL by default subject to redaction policy.
12. Preserve failed attempts and validation failures.
13. Return one result per independent task.
14. Persist an inspectable evidence chain.
15. Run fixed, repeatable product and trap evaluations.

### 2.5 Non-goals

The following MUST NOT become prerequisites for v0.1:

- A new semantic SQL compiler or relational optimizer.
- Arbitrary Python or shell execution.
- A vector database or knowledge graph.
- Cross-datasource joins.
- Parallel or distributed workflows.
- Durable pause/resume across workers.
- Production authentication or tenant-level authorization.
- Automatic production semantic-model mutation.
- Tuple-level provenance.
- Numeric confidence scores.
- An LLM-as-judge as the sole correctness mechanism.
- Dashboards, scheduling, or a semantic-review UI.
- Conditional best-of-N planning.

---

## 3. Adopted Architecture Decisions

### 3.1 Build versus borrow

| Capability | Component | Grepbit responsibility |
|---|---|---|
| Semantic model and compilation | Wren Python SDK | Adapter, lifecycle, capability verification |
| PostgreSQL execution | psycopg 3 | Connection, transaction, timeout, cancellation policy |
| SQL parsing and AST inspection | SQLGlot | Grepbit-specific safety and validation rules |
| Domain and structured output | Pydantic v2 | Provider-neutral contracts |
| Model integration | `ModelPort` plus one approved adapter | Prompts, schemas, budgets, redaction |
| HTTP API | FastAPI | Async run contract and response schemas |
| Runtime evidence storage | SQLite | Migrations, repositories, atomic state transitions |
| Authorization boundary | PostgreSQL | Least-privilege roles and object grants |

Grepbit owns analyst orchestration, validation policy, evidence, and evaluation.
It MUST NOT fork Wren or SQLGlot unless a blocking defect is proven and recorded.

### 3.2 Query ownership

The only accepted v0.1 execution path is:

```text
ModelPort.author()
  -> SemanticQueryProposal (untrusted and value-free)
  -> QueryAuthor parameter and plan gates
  + server-owned typed bindings
  -> SemanticQueryDraft
  -> WrenSemanticEngine.compile()
  -> CompiledQuery
  -> SqlPolicy.evaluate()
  -> PsycopgQueryExecutor.execute()
```

Rules:

- The model emits Wren semantic SQL, requested parameter names, semantic
  references, relation uses, and the expected output schema. It never receives
  or emits parameter values.
- QueryAuthor receives reviewed parameter specifications and server-owned typed
  bindings through a separate application boundary. It requires exact unique
  names, matching types and sensitivity, matching SQL placeholders, and no
  binding-value literals before materializing `SemanticQueryDraft`.
- Wren independently rejects placeholder and binding-name mismatches before
  compilation.
- Wren owns semantic compilation but does not own runtime execution.
- psycopg owns all physical PostgreSQL execution.
- Grepbit owns parameters, SQL policy, transactions, budgets, validation, and
  evidence.
- Successful compilation and execution do not attest a model-authored metric,
  join, filter, period comparison, or ranking rule. AST-derived semantic
  provenance proves only which recognized references occur in the submitted
  query; it does not prove that those references were combined correctly.
- Model-authored semantic SQL is marked `model_authored_unattested` until an
  executable, server-owned semantic contract independently establishes the
  requested business meaning. Caller-supplied metadata cannot remove or
  override that state.
- No code path may sometimes execute through Wren and sometimes through psycopg.
- Wren-specific types remain inside `adapters/wren/`.

### 3.3 Wren dependency decision

- Gate G1 starts with a provisional, exact Wren package version and target
  platform recorded in the spike packet.
- That version becomes the accepted locked version only after G1 passes.
- A failed version is not silently replaced. The failure is recorded and the
  next candidate requires authorization.
- In-process operation is required for v0.1 unless G1 proves it technically
  infeasible and the product owner approves a revised deployment decision.

### 3.4 Parameter modes

The preferred mode is preserved binding:

```text
model-visible parameter specifications (no values)
  + model-authored semantic SQL placeholders
  + server-owned typed values
  -> deterministic parameter gate
  -> trusted semantic SQL placeholders + typed values
  -> physical SQL placeholders + the same typed values
```

G1 MUST prove parameter identity across compilation. If Wren cannot preserve
bindings, only one fallback may be evaluated:

```text
typed parameters
  -> adapter-owned, AST-tested safe semantic literalization
  -> compiled physical SQL
  -> AST-redacted public SQL
```

The LLM MUST NOT interpolate, quote, or concatenate parameter values. A fallback
cannot be accepted until injection, type, timezone, Unicode, NULL, decimal, and
redaction rulers pass.

### 3.5 Task execution

- Independent tasks execute sequentially in v0.1.
- The domain permits future parallel scheduling but does not implement it.
- A task plans only its next useful evidence horizon.
- Completed steps are immutable.
- Replanning can modify only unexecuted steps.
- One query repair and two replans are the default configurable maxima.

### 3.6 A-to-B scope

`ResultRef` represents a logical relation dependency, never a copied value list.

G1 MUST prove and select one A-to-B composition protocol before production plan
models are frozen. Approved spike candidates are:

1. A Wren-supported dynamic semantic relation/view backed by A's query recipe.
2. A constrained physical AST composition using a structured semi-join relation
   filter on declared keys.

The selected protocol MUST be recorded in an architecture decision and satisfy
G4. No other protocol may be introduced silently.

For v0.1, a `ResultRef` may only filter B by declared relation keys. Arbitrary
value substitution, scalar expression injection, cross-datasource input, and
LLM-generated `IN (...)` expansion are unsupported.

### 3.7 API surface

The canonical analysis API is asynchronous:

```text
POST /ask -> 202 Accepted + run_id
GET /runs/{run_id}
GET /runs/{run_id}/evidence
POST /runs/{run_id}/cancel
```

There is no separate synchronous `/ask` contract in v0.1. Until production
authentication exists, the service binds to loopback by default and is an
internal/trusted POC only.

---

## 4. Normative Domain Contracts

Exact Python placement may vary, but legal states and invariants are normative.

### 4.1 Run context

Every run records:

```text
run_id
datasource_id
original_question
as_of
business_timezone
semantic_revision + digest
catalog_revision + digest
validation_policy_revision
prompt_schema_revision
model_identifier + structured-output settings
fixture_revision when evaluating
evaluation_protocol_revision when evaluating
scorer_revision when evaluating
trace_schema_revision
snapshot_consistency
query/model/time/result budgets
```

Relative time is resolved once from `as_of` and reused by all steps.

### 4.2 Task intent

For a selected reviewed request contract, the server materializes one or more
independent tasks deterministically. Numbered formatting alone does not create
dependencies. Clauses that use the result of an earlier clause remain one task.
Independent questions have separate plans, budgets, evidence, status, and
answers. The server MUST enforce the request task budget before task
materialization.

```text
TaskIntent
  task_id
  question
  goal
  analysis_shape
  measures
  dimensions
  time_scope
  comparison_scope
  requested_limit
  requires_relation_dependency
  ambiguities
```

Supported initial `analysis_shape` values:

```text
direct_metric
group_and_rank
compare_periods
filter_then_drill_down
diagnose_count_vs_average
```

PlanGate checks the structured intent. It MUST NOT claim to deterministically
infer question shape directly from free text.

### 4.2.1 Request grounding

Before creating an executable task, a deterministic server-owned request
grounding gate MUST complete two distinct phases. It is independent of model
assertions, query semantics, SQL policy, execution, and validation. A model
cannot create, alter, approve, or veto reviewed request grounding.

1. **Selection:** select exactly one reviewed request contract from the exact
   original request using server-owned versioned normalization, reviewed
   literals, and typed slot rules. No match terminates as `semantic_gap` in v1;
   multiple matches terminate as `clarification_required`; a reviewed unsafe or
   nonanswerable contract becomes its exact nonexecuting terminal.
2. **Materialization:** build the canonical server-owned ordered task graph,
   resolved task intents, immutable grounding evidence, and grounded
   dependencies exclusively from the selected contract and typed slot bindings.
   The selected-contract execution path consumes no request-decomposition model
   call and no model proposal. Injection text, a wrong semantic reference or
   capability, wrong task intent, missing/extra/reordered tasks, and wrong
   dependency edges therefore cannot enter this path as model authority.

A reviewed request contract is versioned, deterministic, and value-free:

```text
ReviewedRequestContract
  contract_id
  revision
  normalization_revision
  reviewed_literals
  typed_slots
  tasks
  dependencies
  contract_digest
```

`normalization_revision` identifies the exact deterministic normalization used
for matching. `reviewed_literals`, `typed_slots`, tasks, and dependencies are
declarative reviewed data; they MUST NOT contain case IDs, oracle facts, SQL,
rows, bindings, prompts, arbitrary executable regex, or another executable
matcher. `contract_digest` is canonically derived from, or validated against,
the contract content; a caller-supplied digest is not authority.

Each reviewed task declares enough human-reviewable data to construct the
complete canonical task intent: ordinal; exact reviewed value or a slot-aware
question and goal template; analysis shape; resolution and exact reason code
when nonanswerable; measures; dimensions; time scope; comparison scope;
requested limit; capability identity; requested semantic references; dependency
expectation; and every typed slot reference. The server, not the model,
constructs the canonical resolved intent and computes its digest.

Text templates may contain only exact `{slot_name}` fields. Attribute or index
access, conversions, and format specifications are invalid. Every referenced
slot must be declared, and unknown or unused slots are invalid.

Each reviewed dependency pins producer ordinal, consumer ordinal, and the exact
reviewed `ResultRef` contract identity and digest. The server resolves the real
`ResultRef` from reviewed assets. The model MUST NOT provide SQL, columns,
bindings, result-ref values, evidence, attestation, or any digest authority.

The v1 normalization and matching algorithm is deterministic:

- Apply Unicode NFKC, Unicode casefold, trim outer whitespace, and collapse
  each internal whitespace run to one ASCII space. Preserve every other code
  point and punctuation.
- `reviewed_literals` are ordered normalized segments and `typed_slots` are
  ordered unique declarations; their lengths satisfy
  `len(reviewed_literals) == len(typed_slots) + 1`. Matching is exact
  prefix/interleaving/suffix segmentation only; no regex or executable matcher
  is permitted. Normalization applies to the fully assembled literal-slot
  request pattern. Literals own their boundary whitespace: a slot-adjacent
  single space is valid when it is part of a reviewed segment, but the matcher
  MUST NOT synthesize, trim, or skip whitespace at that boundary. The first
  literal cannot begin with whitespace and the last literal cannot end with
  whitespace; internal and slot-boundary single spaces remain exact segments.
- v1 slot kinds are `TEXT` (normalized nonempty, maximum 128 code points),
  `POSITIVE_INTEGER` (canonical ASCII digits and greater than zero), `ISO_DATE`
  (`YYYY-MM-DD` and a real calendar date), and `ISO_MONTH` (`YYYY-MM`).
- A contract matches only when segmentation yields exactly one valid binding.
  No valid internal binding is no match for that contract. Multiple valid
  bindings make that contract ambiguous and contribute to
  `clarification_required`; the server never guesses.

Canonical contract, evidence, task, graph, and reviewed `ResultRef` digests use
the named `grepbit-canonical-json-v1` revision: UTF-8; sorted keys; compact
separators; enum values; tuples and lists as arrays; the digest field excluded;
and SHA-256 prefixed `sha256:`. Digest values are computed or
supplied-and-validated, never trusted as caller authority.

The gate computes only digests for raw request material. Its immutable evidence
contains no raw question:

```text
RequestGroundingEvidence
  grounding_id
  original_request_digest
  request_contract_id + revision + digest
  capability_id
  task_intent_digest
  task_graph_digest
  run_id
  task_id
  status
  reason
  evidence_digest
```

The original-request digest is computed from the normalization revision and the
exact original request. The task-intent digest is computed from the exact
server-owned resolved task. The task-graph digest covers the complete ordered
graph, including independent tasks and every A-to-B edge and `ResultRef`; it is
not a digest of a selected task alone. Every listed identity is checked against
the current run and task. Stale, foreign, tampered, or partial proofs are
invalid.

The typed grounding result records selection and materialization phase separately
and uses sanitized typed status/reason values, never loose string comparison.
The server-owned materialized task and graph contract is the only request-level
authority before query execution, claim creation, or verified-evidence mutation.
A reviewed A-to-B dependency is bound to the real reviewed relation asset:
`ReviewedRelationPairDefinition` pins a result-ref
contract ID and the canonically validated digest of its
`G4RelationDefinition.relation_ref`; the cross-task adapter compares both to
the grounding contract before it prepares the relation. The grounding result
carries a minimal server-owned `GroundedDependency` with the producer/consumer
task identities and reviewed result-ref contract
ID/digest. Resolved and prepared task boundaries may carry that object; inner
query runners and the model never receive the reviewed request contract.

On grounding failure or inconclusive grounding, the system MUST fail closed:
it creates no query, claim, or grounding-backed verified evidence and starts no
trusted query execution. The public state is a sanitized non-verified terminal
with a stable grounding reason. It may retain the ordinary request lifecycle
record and sanitized failure accounting, but it MUST NOT persist raw questions
in grounding evidence.

Selection happens before model work. No match, multiple or ambiguous match, and
a reviewed nonanswerable or unsafe contract create exactly one sanitized
server-owned terminal and consume zero model calls. An answerable selection
deterministically materializes its reviewed tasks with zero preparation model
calls. By default, model participation starts at task-local planning and
authoring; explicitly opted-in reviewed initial plans use the exception below.
Each actual model operation receives that operation's pinned provider-neutral
prompt-schema revision. A retired request-decomposition revision MUST NOT be
reused as a task-local planning revision. On success, the server creates one
immutable
`RequestGroundingEvidence` per canonical task. Each row shares the exact
original-request, selected-contract, and complete-graph digests, while retaining
the exact task run/task/capability/task-intent identity; raw questions remain
absent.

`RequestGroundingGate.ground` and request-decomposition proposal types remain
available only for direct historical comparison/read compatibility. They do not
grant new authority to historical evidence and MUST NOT be used by the selected
reviewed-contract execution path. In that legacy direct comparison, an observed dependency proposal with an incorrect reviewed edge yields `proposal_mismatch`, never a no-match result.

Historical evidence remains readable and revision-labelled. It does not gain
new request-grounding authority merely because a later contract or schema is
introduced. SQLite schema-v6 implements the runtime request-grounding evidence
boundary and rejects grounding inserts after their parent task becomes terminal;
historical schema-v5 and v4 rows remain readable without retrofitting authority.
A later G7 release identity must consume this durable safe projection.
Inner task runners and task factories receive grounding evidence only through
the resolved-task/prepared-task boundary; they never receive the reviewed
request contract.

#### Reviewed initial-plan exception

An explicitly opted-in independent single-query capability MAY supply a
server-owned reviewed initial-plan template instead of requesting model
planning. The template MUST carry explicit evidence requirements, criticality,
validator/completion associations, semantic references, the exact output schema,
and complete step-to-requirement bindings. Missing metadata MUST NOT be guessed
from an allowed-value list or repaired after a model proposal fails.

The trusted capability definition MUST independently pin capability identity,
revision and digest, and template identity, revision and digest. A template's own digest
or review assertion is not authority. Admission MUST verify those pins and
reconcile the template with the accepted task intent, reviewed context and
trusted execution metadata before model dispatch. A malformed, foreign, stale,
mutated or mismatched template fails closed with sanitized errors and zero
model calls. No model-supplied template is admitted; the template MUST NOT
contain execution parameter values.

The capability digest covers canonical value-free capability identity/revision,
reviewed model context, fixed-query ID, expected output, parameter specifications,
projection and the reviewed semantic-contract payload (or null). It excludes
runtime task/run identity and execution bindings. Admission MUST recompute this
envelope and the complete template digest, then compare both with independently
pinned expectations. Runtime task identity changes do not alter capability
identity; changed reviewed control metadata cannot reuse the old digest.

The server materializes runtime task/plan identity and uses the existing
task-owned durable step identity. The resulting plan MUST satisfy the existing
PlanGate evidence, validator, completion and output-schema checks. Template
acceptance does not attest query semantics or create verification state.
The first model operation on this path is authoring through the unchanged
Section 3.2 query path; all existing attestation, validation and evidence
requirements still apply.

Actual preparation usage MUST cross the request-task execution boundary:
reviewed materialization consumes zero planning calls, while legacy model
planning retains its actual dispatched usage. Success and every failure path
MUST account for authoring, repair and replan calls without an assumed extra
planning call. A one-call budget admits at most one author call on the reviewed
path; an exhausted budget prevents dispatch. This exception grants no retries,
additional candidates or silent budget increase.

The exception is opt-in through trusted server configuration. Existing model
planning, historical V11 composition, and reviewed A-to-B execution retain
their contracts. R1 establishes the template/request-task capability and its
production-shaped witnesses only. A successor release pack MUST independently
pin its template assets, runtime profile, prompt and evaluation identities and
complete all consumers before activating this behavior for release evaluation.
Historical evidence MUST NOT be relabelled or rescored to claim the exception.

### 4.3 Evidence requirements

```text
EvidenceRequirement
  id
  claim_or_question
  required_relation_schema
  required_validations
  completion_rule_id
  criticality
```

`completion_rule_id` references a code-defined or template-defined predicate.
It MUST NOT be arbitrary LLM-authored executable text.

### 4.4 Plan and steps

```text
AnalysisPlan
  task_id
  goal
  revision
  steps

QueryStep
  id
  goal
  input_refs
  control_dependencies
  semantic_refs_requested
  expected_output
  evidence_requirement_ids

SynthesisStep
  id
  control_dependencies
  evidence_requirement_ids
```

Rules:

- `input_refs` are the source of truth for data dependencies.
- `control_dependencies` are only non-data ordering constraints.
- The two forms MUST NOT contradict.
- `expected_output` is required when another step or structured answer consumes
  the query output.
- Step IDs are unique and the dependency graph is acyclic.
- All references point to ancestor query steps and declared columns.

### 4.5 Query draft and compiled query

```text
QueryParameterSpec
  name
  type_name
  purpose
  required = true
  sensitive

SemanticQueryProposal
  semantic_sql
  requested_parameter_names
  requested_semantic_refs
  expected_output
  input_relation_uses

SemanticQueryDraft
  semantic_sql
  typed_parameters
  requested_semantic_refs
  expected_output
  input_relation_uses

CompiledQuery
  physical_sql
  execution_parameters
  parameter_mode
  semantic_refs
  semantic_ref_source = compiler_resolved | semantic_sql_ast | requested
  warnings
  compiler_revision

ExecutionResult
  rows
  row_count
  columns
  truncation
  error_code
```

`QueryParameterSpec` and `SemanticQueryProposal` are the only parameter-related
contracts that cross the model boundary. They contain metadata and names only.
`SemanticQueryDraft` is a trusted post-gate application contract: its
`typed_parameters` come only from server-owned bindings and are never copied
from model output. Repair requests carry the rejected value-free proposal, not
the materialized draft.

`ExecutionResult.columns` is the ordered database cursor-description schema,
including when the result has zero rows. After a successful execution and
before projection, validators, artifacts, or claims, it MUST exactly equal the
trusted draft's expected columns in name, order, and uniqueness. A mismatch
persists the successful query attempt but produces a critical blocked
`result_completeness` outcome and no relation artifact or claim evidence.

`semantic_ref_source` is required even when `semantic_refs` is empty. It means:

- `compiler_resolved`: authoritative references exposed by the semantic compiler;
- `semantic_sql_ast`: validated references derived from the semantic SQL AST; or
- `requested`: validated requested references, explicitly labelled as request
  provenance.

If Wren cannot expose authoritative compiler-resolved semantic references, G1
MUST choose and document one honest fallback:

- Validated references derived from the semantic SQL AST; or
- Validated requested references explicitly labelled as request provenance.

The selected Wren fallback is `semantic_sql_ast`. AST-derived or requested
references MUST NOT be labelled `compiler_resolved`.

### 4.6 Relation and query artifacts

```text
ResultRef
  producer_step_id
  relation_name
  required_columns
  key_mapping
  use_mode = semi_join_filter

RelationArtifact
  artifact_id
  producer_step_id
  schema
  query_recipe_id
  row_count
  bounded_preview
  result_digest
  truncation
  snapshot_consistency

QueryRecord
  query_id
  step_id
  attempt
  execution_sql_evidence
  physical_sql_public
  stored_parameter_evidence
  semantic_provenance
  status
  row_count
  elapsed_ms
  truncation
  error_code
```

An inline CTE artifact is a query recipe, not a frozen result. Reuse may execute
A again. SQL and parameters are namespaced per step.

`execution_sql_evidence` is parameterized SQL when preserved binding is used. If
the approved fallback embeds a classified value, persistence stores redacted SQL
plus an execution digest; plaintext sensitive literals exist only in bounded
process memory.

### 4.7 Validation and public verification

Internal validation outcomes:

```text
passed | failed | inconclusive | blocked
```

Evidence completeness:

```text
sufficient | partial | insufficient
```

Public answer states:

```text
verified | partially_verified | unverified | blocked
```

Mandatory mapping:

| Mandatory validations | Completeness | Claim result truncated | Public state |
|---|---|---:|---|
| All passed | Sufficient | No | `verified` |
| All passed | Partial | No | `partially_verified` |
| Any inconclusive | Any | Any | `unverified` |
| Any failed but safe partial claim remains | Partial | No | `partially_verified` |
| Critical failure or policy block | Any | Any | `blocked` |
| All passed | Any | Yes | `partially_verified` at best |

`verified` and `partially_verified` additionally require a passed,
server-owned request-grounding attestation for the exact original-request
digest, reviewed request-contract identity/revision, capability identity,
task-intent digest, complete task-graph digest, run/task identity, status,
reason, and evidence identity. This is conjunctive with, not a substitute for,
human-reviewed relevant semantics, acceptable snapshot consistency, no
unresolved critical ambiguity, and all existing trusted execution and
validation requirements. A `TaskAnswer` MUST NOT expose either public verified
state without a nonempty grounding evidence ID for its exact task. In other
words, public verification is `request-grounded AND existing execution
verification`. `TaskAnswer` performs only that structural check: it may accept
a nonempty ID but cannot query persistence. `RequestSession.finish_task` is the
authority that reconciles the exact passed immutable task-scope evidence before
a verified or partially verified answer is authoritative. It rejects missing,
duplicated, foreign, stale, non-grounded/non-passed, or invented IDs and IDs
that do not occur exactly once in `TaskResult.evidence_ids`.

For model-authored queries, output-schema equality establishes only the result
shape. It cannot establish the correctness of a formula, join, filter, grouping,
ordering, comparison, or limit. Until an executable server-owned semantic
attestation passes, `semantic_definition` is mandatory and `inconclusive`,
evidence completeness is `insufficient`, `semantics_reviewed` is false, and the
public state is `unverified`. The successful execution may persist a query
record and bounded relation artifact for diagnosis and evaluation, but it MUST
NOT create claim evidence or complete the task as verified.

The current G3 attestation mechanism uses a typed, server-owned reviewed query
contract and conservative PostgreSQL AST structural equality. The contract pins
its ID/revision, reviewed semantic SQL, ordered output schema, exact parameter
names, and semantic references. Cosmetic whitespace and keyword case may vary;
any structural or contract-field difference remains inconclusive. The sanitized
validation evidence records the matched contract identity/revision but never
the SQL or parameter values. Prompt instructions, model assertions, AST
reference lists, and matching cursor columns are not attestations by themselves.

### 4.8 Claim evidence

Grepbit does not need to persist every full query result. It MUST persist the
bounded structured facts used by the answer:

```text
ClaimEvidence
  claim_id
  task_id
  claim_type
  structured_facts
  units
  dimensions
  exact_time_boundaries
  source_artifact_ids
  validation_ids
  semantic_provenance
  result_digest
  completeness
```

This makes an answer reconstructable without pretending that a preview is the
full result.

### 4.9 Observation decision

```text
ObservationDecision
  action = complete | repair_query | request_more_evidence | blocked
  reason_codes
  satisfied_requirement_ids
  unmet_requirement_ids
  proposed_next_goals
```

Every new step maps to an unmet evidence requirement. A repeated or no-op replan
terminates with partial or blocked evidence.

### 4.10 Task and request results

Every `TaskResult` includes:

```text
task_id
question
status
answer_or_null
structured_errors
caveats
query_records
evidence_ids
```

Blocked and failed tasks do not require a successful answer object. Request
status is derived from task statuses and never hides an individual failure.

---

## 5. Datasource, Catalog, and Semantic Model

### 5.1 Datasource registration

```json
{
  "name": "sales_pg",
  "type": "postgres",
  "connection_secret_ref": "SALES_PG_DSN",
  "allowed_schemas": ["public"],
  "business_timezone": "Asia/Taipei"
}
```

Plaintext credentials MUST NOT be accepted, stored, logged, or returned.

### 5.2 Catalog introspection

The introspector MUST collect:

- Schemas, tables, and views.
- Columns, physical types, nullability, and defaults.
- Primary, foreign, unique, and check constraints.
- Table and column comments.
- Estimated row counts when inexpensive.

Catalog output has a canonical revision and digest. Comments are untrusted
candidate metadata, not verified business truth.

### 5.3 Semantic source of truth

The POC uses a human-reviewed Wren project defining:

- Models and fields.
- Relationships and cardinality.
- Metrics and units.
- Entity grain and keys.
- Business timezone and time fields.
- Sensitivity classification.
- Business descriptions and knowledge.

Metadata records source and review state:

```text
source: human_manual | database_comment | external_authoritative | inference
review_state: verified | candidate | rejected | superseded
```

Verified definitions override candidate metadata. Candidate or inferred
metadata cannot silently replace verified definitions.

For the small v0.1 fixture, the full reviewed semantic project MAY be supplied
when it fits the context budget. Otherwise context selection uses deterministic
model/metric scope and recorded references. Vector retrieval and Wren memory are
not implicit dependencies and require a later approved capability.

### 5.4 Canonical evaluation fixture

Before production adapters are implemented, G0 creates:

```text
evals/fixtures/retail_v1/
  schema.sql
  seed.sql
  semantic/
  catalog_snapshot.json
  expected_facts.yaml
  trap_manifest.yaml
  README.md
```

The fixture MUST define exact rules for revenue, returns, cancellations, tax,
discounts, entity grain, relationship cardinality, currency, and time handling.

The coding agent may propose the fixture and rulers but MUST stop for owner
approval before using them as product truth. An agent MUST NOT author both the
business oracle and production behavior without this checkpoint.

---

## 6. Query Execution and A-to-B Relations

### 6.1 Query lifecycle

```text
Author semantic query draft
  -> validate structured draft
  -> Wren compile/dry-plan
  -> parse full physical SQL
  -> apply SQL policy
  -> optional non-executing EXPLAIN
  -> execute with psycopg
  -> validate actual cursor schema against trusted expected output
  -> build relation artifact
  -> run mandatory validators
  -> create claim evidence
  -> accept, repair, replan, or block
```

### 6.2 A-to-B requirements

For a dependent flow:

- A is compiled and its exact query recipe is recorded.
- B declares a typed `ResultRef` and key mapping.
- The selected G1 composition protocol creates one fully parseable physical SQL
  statement or one bounded execution-scoped relation.
- The composed physical SQL is safety-checked as a whole.
- A and B parameter namespaces cannot collide.
- A failure, unsafe truncation, missing key, or critical validation failure
  prevents B from supporting a verified claim.

Required composition rulers include:

- A already contains a `WITH` clause.
- A and B reuse parameter names with different values.
- A returns zero rows.
- A logically returns thousands of keys but no keys enter the prompt.
- B uses a composite key.
- Source data changes between statements.

### 6.3 Snapshot policy

| Task horizon | Snapshot policy |
|---|---|
| One query | Statement snapshot |
| Pre-authored bounded A-to-B | One short read-only repeatable-read transaction when G1 proves it practical |
| LLM replan between queries | Close the transaction; subsequent evidence is `best_effort` |

The runtime MUST NOT hold a database transaction open during an unbounded model
call. A task requiring guaranteed cross-step consistency is blocked if it cannot
fit one bounded execution horizon.

### 6.4 Default budgets

All limits are configurable. Defaults:

```yaml
max_tasks_per_request: 5
max_steps_per_task: 6
max_queries_per_task: 10
max_query_repairs_per_step: 1
max_replans_per_task: 2
max_llm_calls_per_task: 8
statement_timeout_seconds: 30
idle_in_transaction_timeout_seconds: 60
max_task_wall_clock_seconds: 180
max_request_wall_clock_seconds: 600
max_result_rows: 5000
preview_rows: 100
```

Budget exhaustion returns partial or blocked evidence. Limits are not silently
raised and retries are not added to hide deterministic failures.

Every declared budget field, limit, and public terminal state MUST appear in an
executable applicability registry with exactly one status:

```text
enforced(path)
delegated(named owner and observable evidence)
not_applicable(reason)
scheduled(owning gate)
```

`scheduled` is a temporary planning state, not evidence of support. Once its
owning gate begins its ruler checkpoint, the entry becomes required and that
gate cannot pass while the entry remains `scheduled` or unknown. Applicability
follows the actual connection and transaction lifecycle, not the number of
authored query statements. Any path that can remain idle with an open transaction
across client round-trips MUST enforce or explicitly delegate the idle-in-
transaction timeout. A server-side cursor drained in batches is such a path.
Marking that limit `not_applicable` requires an executable witness that no such
idle interval can occur. A declared but unaccounted budget or terminal state is a
false assurance.

---

## 7. Security, Privacy, and Trust Boundaries

### 7.1 PostgreSQL boundary

The POC base execution role MUST:

- Be non-owner and non-superuser.
- Have `SELECT` only on explicitly allowlisted objects.
- Have no DDL/DML privileges on source objects.
- Have no base `TEMP` privilege.
- Have no execute access to non-allowlisted user or extension functions.
- Use an explicit read-only transaction, statement timeout, and constrained
  `search_path`.

Fixture provisioning uses a separate setup role that is never available to the
runtime.

### 7.2 SQL policy

The SQL policy MUST:

- Parse exactly one PostgreSQL statement.
- Allow only side-effect-free `SELECT`/`WITH` roots.
- Reject DML, DDL, `COPY`, `CALL`, locking clauses, and data-modifying CTEs.
- Enforce schema and object allowlists.
- Enforce a built-in and catalog-backed function allowlist.
- Reject non-allowlisted volatile or security-definer functions.
- Reject unsupported recursion and known resource-amplification patterns.
- Apply result limits without changing aggregate semantics.

The security ruler corpus, allowed function list, role DDL, and expected denial
errors are versioned fixture artifacts. "No bypass" claims apply only to that
declared threat model and corpus.

### 7.3 Untrusted model input

User questions, database comments, semantic descriptions, result values, and
database errors are untrusted content.

- Prompts separate policy, reviewed semantics, and untrusted content.
- Candidate comments cannot create instructions or permissions.
- Result values cannot authorize tools, SQL exceptions, or replans.
- Raw large relations are never placed in prompts.
- Database errors are classified and sanitized before model use.

### 7.4 Parameter and result representations

```text
QueryParameterSpec
  reviewed name, type, purpose, required flag, and sensitivity; no value

ExecutionParameters
  actual typed values in process memory

StoredParameterEvidence
  non-sensitive typed values or redacted value plus digest

PublicQueryRecord
  redacted parameters and policy-safe SQL
```

Model calls receive `QueryParameterSpec` metadata only. The application keeps
execution bindings outside request serialization, validates the model's exact
placeholder/name set, and materializes values only after the proposal passes
the parameter gate. The compiler repeats the placeholder/binding-name check
before dry-plan as defense in depth.

Sensitive preview values are omitted or masked according to reviewed semantic
classification. Logs never contain plaintext secrets or unrestricted raw rows.
Exact execution SQL containing sensitive fallback literals is not persisted;
the system stores redacted SQL, typed redacted parameter evidence, and a digest.

---

## 8. Deterministic Validation Contracts

Planner suggestions may add checks but cannot remove mandatory checks.

| Validator | Trigger | Conclusive pass | Inconclusive when | Failure effect |
|---|---|---|---|---|
| SQL safety | Every query | AST and database policy allow it | Never; unavailable policy is blocked | Block query |
| Semantic definition | Every claim; mandatory for model-authored queries | An executable server-owned contract attests the authored query's relevant business semantics | Query is model-authored and no independent attestation exists | Unverified; retain artifacts but create no claim evidence |
| Time boundary | Time question or filter | Boundaries equal run-resolved half-open interval and timezone/type handling is known | Ambiguous time field/type/timezone | Repair or unverified |
| Fanout | Join plus aggregation | Relationship is key-preserving at measure grain, or an independent reconciliation passes | Cardinality/grain unknown | Unverified or block critical metric |
| Grain/distinct | Entity count, composite entity, multi-table aggregate | Declared entity key and query grain agree | Entity key or grain missing | Repair or unverified |
| NULL/denominator | Average, ratio, nullable metric/group key | NULL and zero behavior matches reviewed metric policy and counts are recorded | Metric NULL policy absent | Repair or unverified |
| Reconciliation | Period comparison, ratio, top-N, grouped or multi-stage total | Independent query shape agrees within reviewed metric tolerance | Check repeats the same derivation or tolerance is absent | Partial/unverified |
| Result completeness | Every answer claim | Actual cursor schema exactly matches the trusted output schema, including for zero rows; required rows/facts are present and not unsafe-truncated | Full claim cannot be established from bounded result | Block on schema mismatch; otherwise partial/unverified |

Additional rules:

- Counts use exact equality unless the metric definition says otherwise.
- Decimal/currency tolerance comes from reviewed metric metadata; there is no
  hidden global tolerance.
- Top-N defines deterministic tie-breaking and whether ties are included.
- Reconciliation evidence records both values, delta, tolerance, and query IDs.
- Unknown required metadata produces `inconclusive`, never an assumed pass.
- Validation repair is allowed once per query by default.

---

## 9. Persistence and Observability

SQLite stores POC runtime and evidence metadata using migrations:

```text
request_runs
task_runs
plan_revisions
step_runs
query_records
relation_artifacts
validation_results
claim_evidence
```

SQLite schema-v6 stores request-grounding evidence. A later public projection has this exact allowlist;
the existing API projection uses no broader fields:
`grounding_id`, status, reason, request-contract ID/revision/digest,
original-request digest, task-intent digest, task-graph digest, run ID, task
ID, and capability ID. It MUST NOT expose raw questions, reviewed literals,
slots, model output, SQL, rows, bindings, prompts, or oracle facts.

The schema-v6 `request_grounding_evidence` table has immutable
`grounding_id` primary-key identity and explicit safe columns: status, reason,
contract ID/revision/digest, original-request/task-intent/task-graph digests,
optional capability ID, run ID, task ID, and evidence digest. It has no generic
unconstrained payload column. `task_runs` gains a unique `(run_id, task_id)`
pair. The evidence table independently permits exactly one row for that pair
and has a composite foreign key `(run_id, task_id)` to it; separate foreign keys
are insufficient. A schema-v6 before-insert guard admits evidence only while
its exact parent task is running; schema-v5 and v4 remain readable and
historical rows are never retroactively grounded.

`RequestSession.open_task(task_intent, *, grounding_evidence=...)` creates the
task row and has the ledger persist exactly one evidence row before it returns a
scope, before any step, query, validation, relation, or claim mutation. The
scope exposes only a read-only grounding evidence ID; append/get evidence
methods belong to `EvidenceLedgerPort` and its SQLite adapter, not inner
runners. `AnswerableResolution`, `NonexecutingResolution`, `OrchestratedTask`,
grouped prepared tasks, and terminal prepared tasks carry the exact applicable
evidence and minimal grounded dependencies. The orchestrator passes evidence to
the session, and the cross-task adapter compares a grounded dependency with the
real reviewed relation-pair identity/digest before constructing a group.
`record_terminal_task`
accepts optional exact evidence for reviewed nonanswerable/unsafe terminals;
no-match, multiple-match, and comparison-mismatch terminals have none.
Duplicate, foreign, stale, or mismatched evidence fails closed. Every
post-grounding completed, partial, blocked, failed, timed-out, cancelled, or
budget terminal carries its exact grounding ID once in `evidence_ids`; pre-task
selection/profile/budget terminals carry none.

Rules:

- State transitions are atomic.
- Completed step and evidence records are immutable.
- Startup marks stale `running` records as `abandoned`; durable resume is a
  non-goal.
- SQLite uses one application writer/process in v0.1.
- A restart leaves prior records inspectable and never marks incomplete work as
  completed.

Stable identifiers:

```text
run_id task_id plan_revision step_id query_id artifact_id validation_id claim_id
```

Model-authored plan and step identifiers are untrusted, ephemeral planning data.
Every persisted step uses a collision-resistant server-owned identity derived
from the exact ordered pair `(durable task ID, reviewed local step ID)`. The
canonical input is the UTF-8 encoding of a compact JSON array serialized with
`ensure_ascii=false` and separators `(',', ':')`; the durable ID is `step_`
followed by the first 56 lowercase hexadecimal characters of its SHA-256 digest.
The resulting 61-byte ID is an admissible PostgreSQL unquoted identifier. The
step payload MUST retain the original `reviewed_local_step_id` verbatim; the
digest is persistence identity, not semantic provenance. G3 uses the
server-owned local identity `step_1`, and the model-authored identifier never
becomes persistent identity.

Every other task-owned record in a global SQLite primary-key table MUST be
namespaced either directly by the exact durable task ID or by that canonical
step ID. Fixed-query and direct-G4 evidence keys use
`<task_id>:<kind>:<reviewed-local-id>`, where `kind` is one of `query`,
`artifact`, `validation`, or `claim`. A fixed-query attempt after attempt 1
prefixes its local identity with `attempt-N:`. Cross-task G4 query and artifact
keys retain their trace-compatible prefix format, but their embedded step ID is
the canonical collision-resistant step ID. Returned task results, answers, and
claims MUST reference the exact persisted IDs and MUST NOT contain foreign or
stale task evidence. Historical rows remain readable; this new-write identity
contract does not require a schema migration.

Structured logs and metrics record stage latency, query/repair/replan counts,
validation outcomes, verification states, token usage, and budgets. They use IDs
rather than sensitive result values.

---

## 10. API Contract

All endpoints consume and produce `application/json`. Request models reject
unknown fields. Public errors use one sanitized envelope and never include raw
exceptions, SQL, bindings, rows, secret references, or validation-library
details:

```json
{
  "error": {
    "code": "run_not_found",
    "message": "run_not_found"
  }
}
```

The stable error status mapping is:

| HTTP status | Codes |
|---|---|
| `400` | `invalid_request`, `inline_secret_rejected`, `datasource_name_invalid`, `schema_name_invalid` |
| `404` | `run_not_found`, `datasource_not_found` |
| `409` | `idempotency_key_conflict`, `datasource_already_exists` |
| `503` | `runner_capacity_exceeded`, `persistence_unavailable`, `datasource_unavailable` |

Framework-default validation bodies are not part of the public contract.

### 10.1 Create analysis run

`POST /ask` returns `202 Accepted`:

```json
{
  "datasource": "sales_pg",
  "question": "What was revenue last month?",
  "include_sql": true,
  "include_evidence": false
}
```

```json
{
  "run_id": "run_01K...",
  "status": "accepted",
  "status_url": "/runs/run_01K...",
  "evidence_url": "/runs/run_01K.../evidence"
}
```

`include_sql` defaults to `true`; `include_evidence` defaults to `false`.
`datasource` and `question` are required nonempty strings. Unknown request
fields are rejected. The server creates the run ID, persists the `accepted`
record and response-visibility flags, and reserves bounded runner capacity
before returning `202`. An immediately following read MUST therefore find the
run. Persistence or capacity failure MUST NOT enqueue work or return an accepted
run.

An optional `Idempotency-Key` header prevents accidental duplicate runs. When
present it is an opaque 1-128 byte value. The service stores only its digest and
a canonical request fingerprint:

- the same key and same normalized request return the original `202` response
  and do not enqueue another run;
- the same key and a different normalized request return `409` with
  `idempotency_key_conflict`;
- concurrent submissions of the same key are atomic; and
- the mapping survives process restart.

`include_sql` controls policy-visible query records in the terminal run result.
`include_evidence` controls inline evidence summaries; the dedicated evidence
endpoint remains the canonical detailed view.

### 10.2 Read run

`GET /runs/{run_id}` returns:

- Run and task statuses.
- Budgets and usage.
- Plan revisions and step states.
- Terminal results when available.
- Structured errors and caveats.

The top-level response fields are:

```text
run_id
status
budgets
usage
tasks
plan_revisions
steps
structured_errors
caveats
evidence_summary when include_evidence was true
```

Each task contains `task_id`, `question`, `status`, nullable `answer`,
`structured_errors`, `caveats`, `evidence_ids`, and policy-visible
`query_records` only when `include_sql` was true. Reads of accepted or early
running work may have no tasks. A pre-task terminal `cancelled` or `abandoned`
run may also have no tasks and MUST carry a sanitized run-level cause; this API
view does not fabricate a `TaskResult` merely to satisfy a transport shape.

Legal run states:

```text
accepted -> running -> completed | partially_completed | blocked | failed |
                         budget_exceeded | timed_out | cancelled | abandoned
```

### 10.3 Read evidence

`GET /runs/{run_id}/evidence` returns policy-visible semantic provenance, query
records, validations, relation metadata, and claim evidence. It never returns
private SQL/parameters or sensitive preview values.

The exact top-level fields are `run_id`, `semantic_provenance`, `query_records`,
`validations`, `relations`, and `claims`. A public query record may contain
`query_id`, `step_id`, `attempt`, `physical_sql_public`, typed/redacted parameter
metadata, status, row count, truncation, and sanitized error code. It MUST NOT
contain `execution_sql_evidence` or parameter values. Public relation metadata
may contain identity, schema, query recipe, row count, digest, truncation, and
snapshot consistency, but never `bounded_preview`. Validation and claim entries
are explicit safe summaries rather than raw persisted payloads.

### 10.4 Cancel run

`POST /runs/{run_id}/cancel` sets a cooperative cancellation flag and attempts
PostgreSQL cancellation for an active query. Cancellation is idempotent and
best-effort.

The response contains `run_id` and `cancellation_status`. A found nonterminal
run returns `202` and `cancellation_requested`; a repeated request returns the
same response without a second cancellation callback. A durably terminal run
returns `200` and `already_completed`. An unknown run returns the standard `404`
envelope. Cancellation of accepted work prevents its analysis callback from
starting and persists a terminal sanitized cause.

### 10.5 POC execution model

- One API process.
- One bounded in-process task runner.
- Sequential independent tasks.
- No external queue or durable resume.
- Loopback bind by default.

The task runner has one writer thread and bounded pending capacity. The writer
thread owns the long-lived SQLite writer connection; read endpoints use
short-lived caller-owned read connections. Startup recovery runs before the
service accepts traffic. Because the queue is not durable, stale `accepted` as
well as stale `running` records become `abandoned`; they are never resumed or
reported completed. Shutdown stops accepting work and bounds the wait for the
active task without inventing a successful terminal state.

Configuration defaults to `127.0.0.1` and MUST reject a non-loopback bind unless
a later authentication/security contract is approved. The POC does not enable
CORS, trusted proxy headers, or public ingress by default.

The coding agent MUST NOT introduce Redis, Celery, or a workflow framework
without a separately approved requirement.

### 10.6 Datasource administration

The local/trusted POC also exposes:

```text
POST /datasources
POST /datasources/{name}/introspect
```

Registration accepts only secret references and allowlisted schemas.
Introspection returns catalog metadata, provenance, revision, and digest. Both
operations use structured error envelopes and never return connection secrets.

Registration request fields are exactly:

```json
{
  "name": "sales_pg",
  "secret_ref": {
    "provider": "environment",
    "key": "GREPBIT_SALES_PG_DSN"
  },
  "allowed_schemas": ["analytics"]
}
```

`name` and every schema use PostgreSQL unquoted-identifier syntax and
`allowed_schemas` is nonempty and unique. The only v0.1 secret-reference
provider is `environment`; its key is an uppercase environment-variable name.
Credential-bearing fields or values, including a DSN, password, token,
connection string, or URI, are rejected before persistence. The service stores
the reference name, never resolves it in an API handler, and returns `201` with
`name`, `allowed_schemas`, and `secret_configured: true` without echoing the
reference.

`POST /datasources/{name}/introspect` returns `200` with `name`,
`catalog_revision`, `catalog_digest`, provenance, and allowlisted object
metadata. Secret resolution and database introspection occur behind application
ports in the single bounded runner, and public errors remain sanitized.

SQLite schema revision 3 adds immutable datasource registration metadata and a
digest-only idempotency mapping. The idempotency row binds key digest, canonical
request fingerprint, and run ID atomically. No plaintext idempotency key or
credential value is stored.

---

## 11. Evaluation and Release Policy

The detailed working evaluation roadmap is maintained in
`docs/evaluation-strategy.md`. It distinguishes current evidence from proposed
multi-world, mutation, P0, and production-replay capabilities. The requirements
in this section and G7 remain normative until a roadmap item is promoted through
an executable critical-evaluation ruler checkpoint.

### 11.1 Evaluation layers

1. Deterministic domain, safety, validator, and persistence tests with no model.
2. Fixed-dataset integration tests with pinned database, semantic model, clock,
   timezone, and policy revisions.
3. End-to-end model evaluations using an approved provider configuration.

The release evaluation also runs an informative unvalidated baseline using the
same model and reviewed, value-free semantic context. The model performs exactly
one SQL-authoring attempt and never receives bindings, result rows, oracle facts,
or execution errors:

```text
question -> one semantic SQL draft -> compile -> safety policy -> execute
         -> deterministic local projection -> deterministic fact scoring
```

The baseline has no Grepbit plan gate, deterministic result validators, repair,
replan, or model-based result synthesis. Its deterministic local projection is
not a second trusted execution path and cannot create verification state. The
release report compares structured accuracy, trap handling, false-verification,
latency, and cost on cases supported by both paths. Grepbit MUST have zero
critical false verification and MUST NOT regress structured-fact accuracy below
this baseline.

Correctness uses structured facts and plan/evidence properties, not exact SQL
string equality or answer-text similarity alone.

### 11.2 Case manifest

Every case declares:

```text
id
question
critical flag
expected task intent
expected structured facts or blocked reason
required semantic references
required validators and allowed outcomes
maximum queries/replans/model calls
public verification state
evaluation protocol revision
scorer revision
trace schema revision
```

The final set contains at least 30 cases covering direct metrics, grouping,
ranking, joins, time, fanout, grain, NULL, empty/truncated results, A-to-B,
progressive diagnosis, multiple tasks, ambiguity, unsafe SQL, prompt injection,
redaction, and budget exhaustion.

### 11.3 Model evaluation protocol

The evaluation protocol, scorer set, and trace schema are separate versioned
contracts:

- `evaluation_protocol_revision` identifies sampling, repetition, baseline, and
  aggregation rules.
- `scorer_revision` identifies every predicate that decides pass, fail, or false
  verification.
- `trace_schema_revision` identifies the evidence fields available to those
  scorers.

A material scoring-predicate change requires the Section 12.2 ruler checkpoint
and a scorer revision bump. Results recorded under different protocol or scorer
revisions MUST NOT be presented as a trend or regression comparison unless both
sets are re-scored under one common declared revision. A trace-schema change that
alters scorer input or claim reconstructability also requires that checkpoint.

The grounding-aware release-candidate identity is exactly
`g7-release-protocol-v3` / `g7-release-scorer-v8` /
`g7-release-trace-v5` / `retail_v1-release-v11` /
`retail_v1-release-v10`. Its reviewed retail assets and versioned runtime,
trace, and scorer implementations are admitted by the repository. This is not
a release claim: live run `g7-live-20260831-14` exercised this exact identity
and produced a G7 `FAIL`, as recorded in ADR 0007.
It consumes the already accepted runtime SQLite schema-v6 request-grounding
evidence contract, while historical schema-v5 rows remain readable, and
introduces no protocol-v4 identity. A protocol bump
requires a separately accepted executable contradiction to the protocol-v3
sampling, baseline, or aggregation rules.

A v11 pack historically pinned an owner-approved
`reviewed-release-runtime-profile-v3`. That profile pins an immutable
`request-contract-pack-v1` artifact by repository-relative path and exact
artifact digest, used `prompt-schema-v2` for request decomposition, and supplied
the loaded reviewed request contracts to `RequestPreparationProfile`. Pack
admission MUST validate every
contract's `request-normalization-v1` and `grepbit-canonical-json-v1` identity,
canonical contract digest, unique contract ID, reviewed capability/output/task
authority, and reviewed dependency topology. It MUST reject an absent, empty,
duplicate, digest-mismatched, or unreviewed pack. A request contract contains
only value-free reviewed request structure and exact canonical identities; it
MUST NOT contain case IDs, oracle facts, expected answers, SQL, rows, bindings,
prompts, or secrets. Initial retail-v1 promotion may use one exact no-slot
contract per distinct reviewed question. Reviewed nonanswerable or unsafe
contracts select their exact zero-model-call terminal.

That historical promotion extended `evals.release_assets.load_release_asset_pack`
and its versioned descriptor/runtime-profile admission,
`evals.grepbit_runtime_factory` construction of `RequestPreparationProfile`,
the former LiteLLM decomposition adapter path, and the existing
attempt-assessment, trace-emitter, and release scorer versioned surfaces. A
successor MUST NOT introduce a second release-pack loader, evaluation-only
request materializer, or bypass admission path. A real
v11/v10 promotion transforms the complete historical v10/v9 authority: all 39
case artifacts and their nested digests, coverage, performance-sample policy,
pricing, oracle registry, model identity/configuration, and the complete
runtime-profile-v2 content remain pinned unless an independently versioned
artifact explicitly changes them. An illustrative subset cannot claim the
`retail_v1-release-v11` or `retail_v1-release-v10` identity.

`prompt-schema-v2` is a retired, provider-neutral request-decomposition
revision retained only to label and read the historical v11 evidence. It MUST
NOT be supplied to a selected reviewed-contract execution as a planning or
authoring revision. Deterministic materialization renders the selected reviewed
task templates and A-to-B identity server-side; no task blueprint or observed
dependency proposal crosses a model boundary. For the historical/default
composition, the first model-visible request is task-local planning, and it
MUST carry the pinned provider-neutral
`g6b-g3-task-local-json-object-v1` revision. The model never supplies a digest,
`ResultRef` values, reviewed request semantics, evidence, or attestation.

Historical protocol-v4/scorer-v9/trace-v6/retail-v1-release-v12/case-set-v11
evidence remains readable under its original semantics, but MUST NOT be newly
executed, reinterpreted, or promoted. The successor identity is exactly
`g7-release-protocol-v4` / `g7-release-scorer-v10` /
`g7-release-trace-v6` / `retail_v1-release-v13` /
`retail_v1-release-v12`. It retains the structurally compatible
`reviewed-release-runtime-profile-v4` / `retail-v1-runtime-v4` and
`release-case-v6` / `release-case-set-v6` only when the successor descriptor
independently pins their exact reviewed bytes. The tuple is atomic: a mixed
historical/new protocol, scorer, trace, pack, case-set, prompt, runtime-profile,
or governed-artifact digest MUST reject admission.

For v10, deterministic selected reviewed-contract materialization consumes
exactly zero decomposition calls and tokens. Completed answerable attempts MUST
contain nonempty task-local planning, authoring, repair, or replan usage, and
per-operation calls/tokens MUST reconcile exactly to durable totals. The
baseline remains isolated: grounding and materialization are not applicable to
it, while retained candidate failures remain informative but cannot make a
release pass. V10 requires non-vacuous completed passing A-to-B coverage.

SQLite schema v7 MUST persist a separate immutable `RequestTaskGraphEvidence`
record for every candidate graph used by v10 assessment. It contains the
candidate task identity/order, contract-relevant task facts, exact dependency
and ResultRef identities/digests, and durable grounding linkage. Terminal
`TaskResult` MUST NOT acquire evaluation-only fields. Candidate graph evidence
is derived only from durable runtime and grounding sources; reviewed expectations
enter only during assessment comparison. The v10 audit, store, and assessment
path MUST consume this evidence rather than a standalone evaluator type.

Successor descriptor closure independently pins exact bytes for the case set,
runtime profile, request-contract pack, trace schema, scorer contract, pricing,
and oracle registry. Recomputing candidate artifact or descriptor digests after
a semantic mutation MUST NOT nominate those candidate bytes as reviewed v10
authority. A future live run MUST use a fresh runtime root and the successor
pack; it MUST NOT retry `g7p5v9a`.

`g7-release-trace-v5` records one sanitized grounding projection for each
Grepbit task that has durable grounding. The exact projection fields are
`task_id`, `grounding_id`, status, reason, request-contract ID/revision/digest,
original-request digest, task-intent digest, task-graph digest, run ID,
capability ID, and evidence digest. The trace MUST contain no request text,
normalized literals, slot values, model content, SQL, rows, bindings, prompts,
or oracle facts. The trace projection is sufficient only when it reconciles to
the exact immutable SQLite-v6 evidence row for the same run/task pair; it is not
a second authority or a substitute for that row.

`g7-release-scorer-v8` MUST require this exact durable reconciliation for every
Grepbit task publicly marked `verified` or `partially_verified`. Missing,
duplicated, foreign, stale, non-grounded, wrong-run/task, or field-mismatched
grounding is a BVTS failure with a sanitized grounding failure reason. The
candidate-observed decomposition graph remains independent of reviewed expected
tasks; its comparison occurs only in assessment and never lets a candidate
create grounding authority. The unvalidated baseline remains isolated:
request grounding is `not_applicable` to its representation, it cannot acquire
verified or partially-verified state, and it is not included in the v8 durable
grounding predicate.

All v11 artifact digests MUST identify exact bytes. JSON admission artifacts use
the declared `canonical-json-v1` byte serializer: UTF-8, sorted keys, compact
separators, `ensure_ascii=false`, `allow_nan=false`, and one trailing newline;
their SHA-256 digest is prefixed `sha256:`. A release descriptor pins exact
digests of its runtime profile, request-contract pack, case set, trace schema,
and scorer contract; the case set pins every case artifact digest. The request
contracts inside that pack retain their separate `grepbit-canonical-json-v1`
content digests. A byte, path, revision, or nested artifact-digest mismatch
rejects admission.

The complete reviewed v11/v10 promotion records two reviewed case-contract
corrections required by request-grounding v1. Historical
`na_unsupported_multitask` becomes one reviewed `UNSUPPORTED` terminal task
with a bumped case-contract revision, retaining the request-level unsupported
outcome and zero model/query behavior. Historical `na_budget_tasks` gains three
reviewed independent direct-revenue task blueprints and a bumped case-contract
revision. After exact selection, a reviewed task count above
`max_tasks_per_request` terminates before a model call as
`request_task_budget_exceeded`, with zero runtime tasks, queries, and grounding
rows and no verified state. Its candidate graph is empty; the reviewed
over-budget count remains separate authority. Scorer-v8 marks task, plan, and
SQL layers not applicable for that blocked terminal and requires no per-task
grounding. These are v11 reviewed asset corrections, not retroactive changes to
historical v7/v4 reads.

Runtime-profile-v3 relation-pair authority pins the exact
`result_ref_contract_id` and digest derived from production
`G4RelationDefinition.relation_ref`, including physical producer step ID
`producer_step`. This lets the existing runtime factory construct the required
`ReviewedRelationPairDefinition` fields. Request-contract task and rendered
blueprint fields are exactly the accepted `ReviewedTaskContract` /
`TaskIntentProposal` authority; output schema remains capability and
server-owned and is not a request-contract or blueprint field.

Historical scorer-v7/trace-v4 and earlier evidence remains readable only under
its original semantics. Historical runtime-profile-v2 and its v8/v9/v10 pack
identities may be admitted and reconstructed for read compatibility, but they
MUST NOT construct `RequestPreparationProfile`, an API handle, or an executable
`ReviewedGrepbitRuntimeFactory` runtime after request grounding is mandatory.
They confer no request-grounding authority. Only an admitted runtime-profile-v3
with a nonempty validated request-contract pack may cross that execution
boundary. This supersedes earlier v2 executable test composition; it does not
weaken historical read compatibility. Historical evidence MUST NOT be rerun as
v8, rescored as v8, or retroactively labelled request-grounded. The obsolete standalone
`StandaloneG3SingleTaskRunner` live evaluator is superseded and
non-authoritative for G7 release proof. Only the admitted local release harness
and its durable release-assets/runtime-factory path may produce v11 evidence;
legacy evaluator test helpers cannot do so.

`g7-release-protocol-v3` owns the one-attempt unvalidated baseline and its
deterministic local projection defined in Section 11.1. Release packs evaluated
under that protocol require a new pack and case-set identity; historical v2
evidence remains readable but is not directly comparable.

`g7-release-scorer-v5` is admitted only with `g7-release-protocol-v3` and
`g7-release-trace-v3`. It corrects pre-task budget terminals to retain the
finalized decomposition input/output token counts and journal-derived monetary
cost while preserving zero execution, task, query, result, tool, plan, repair,
and evidence work. Historical scorer-v4 evidence remains readable, but v4 and
v5 results MUST NOT be used for trend or regression comparison.

`g7-release-scorer-v6` is admitted only with `g7-release-protocol-v3` and
`g7-release-trace-v4`. It records the candidate-derived decomposition graph
without comparing it to reviewed tasks before assessment, then scores reviewed
graph and typed A-to-B handoff compatibility from durable value-free evidence.
It otherwise inherits v5 task-scoped structured-fact attribution and pre-task
budget-terminal semantics: the durable observed over-budget graph is retained
without comparison to the empty reviewed graph, while finalized usage and cost
remain exact and executable work remains zero. Pre-execution environment
evidence remains the generic base trace variant without request lifecycle or
A-to-B fields under both historical v5/v3 and v6/v4 identities.
Historical trace-v3 evidence remains readable; trace-v3 and trace-v4 results
MUST NOT be aggregated or presented as a trend. A v6/v4 release requires a new
reviewed pack and case-set identity, and a release pass requires at least one
completed, passing reviewed A-to-B handoff case.

`g7-release-scorer-v7` is admitted only with `g7-release-protocol-v3` and
`g7-release-trace-v4`. It inherits the v6/v4 candidate-observed graph,
task-local fact, budget-terminal, typed A-to-B, and release-coverage behavior.
When the single completed and accounted decomposition call is rejected before
it yields a typed `RequestDecompositionProposal`, the evaluation audit records
an explicit rejected outcome and the canonical empty candidate graph. It MUST
NOT substitute the reviewed graph, fabricate a task, or infer rejection merely
from absent durable tasks. Accepted and rejected decomposition outcomes are
mutually exclusive, and omission of both remains an audit failure. Historical
v5/v3 evidence does not gain this candidate-observed rejection semantic.
After exactly one completed and accounted baseline model call, a known
unvalidated baseline candidate failure may be retained as completed product
evidence with a typed sanitized stage and code, zero correct supported facts,
the exact reviewed fact total, and exact usage, cost, and latency. It never
fabricates query or result content. Provider, accounting, context, oracle,
scorer, finalization, and unexpected system failures remain evaluator or
environment failures. A complete comparable v7 baseline aggregate remains
informative when its `passed` value is false; historical v6 remains readable
and retains its strict baseline-comparability behavior.

The reviewed retail v7/v4 release authority is `retail_v1-release-v10` with
case set `retail_v1-release-v9`, oracle registry
`retail-v1-oracle-registry-v5`, runtime profile `retail-v1-runtime-v2`, and
semantic contract pack revision `retail_v1-cross-task-attestation-v2`. Its
`release-asset-pack-v3` descriptor pins
`g7-performance-sample-capacity-v1`: three selected Grepbit trials per
completed measured case and at least 30 selected executions for every enabled
`direct_single_task` or `multi_step` category. The current pack has 42 direct
and 30 multi-step selected executions. Its P0 A-to-B oracle and runtime both
aggregate cancelled recognized revenue at customer-month grain. The reviewed
distractor world contains two qualifying cancelled rows in one customer-month,
and the mutation set must reject a non-aggregating consumer; single-row
fixtures do not establish that contract. Historical v6/v4 retail v9/v8 and
v5/v3 assets remain readable, but are not interchangeable with the current
v10/v9/v7 authority. Live release run `g7-live-20260831-12` completed this
authority and produced a G7 `FAIL`; ADR 0007 owns the sanitized aggregate and
Section 12.6 closeout evidence. The result does not support a release claim and
must not be described as pending, inconclusive, or passing.

The grounding-aware v11/v10 authority was evaluated independently in live run
`g7-live-20260831-14`; it is not a rescore or trend comparison with the
historical v7/v4 run. All 159 scheduled attempts finalized: 117 Grepbit and 42
isolated baseline attempts. Fifteen of 39 cases passed all three Grepbit trials;
the remaining 24 answerable cases produced 53 `proposal_mismatch` and 19
`resolution_mismatch` outcomes, zero queries, and zero correct structured facts.
The required A-to-B case was evaluated but did not pass. Safety violations,
false verification, mutation bypass, secret disclosure, and large-relation
prompt violations were all zero, and both declared latency categories passed.
The aggregate outcome remains G7 `FAIL` because answerable BVTS coverage,
noncritical fact accuracy, and A-to-B coverage failed. ADR 0007 owns the exact
sanitized aggregate and Section 12.6 evidence. A future candidate must use the
accepted deterministic reviewed-contract materialization and task-local prompt
identity under a new critical-evaluation checkpoint and fresh release identity;
it MUST NOT weaken grounding, facts, mutation, or safety predicates, combine
prior runtime roots, or rerun this identity as sampling retry evidence.

Historical protocol-v4/scorer-v10/trace-v6/retail-v1-release-v13/case-set-v12
evidence remains readable only under its original semantics. The current
scorer-v11 successor identity is exactly `g7-release-protocol-v4` /
`g7-release-scorer-v11` / `g7-release-trace-v6` /
`retail_v1-release-v15` / `retail_v1-release-v13`. It uses
`reviewed-release-runtime-profile-v5` / `retail-v1-runtime-v5` and
`release-case-v6` / `release-case-set-v6` only when the successor descriptor
independently pins their exact reviewed bytes. Historical release-v14/runtime-v4
evidence remains readable under its original identity. The full tuple, all 39
case revision tuples, scorer contract, case-set membership digests, runtime
profile, and descriptor digest are atomic; v10/v11, v14/v5, v15/v4, or other
mixed tuples MUST reject new execution. The v11 scorer contract declaratively
identifies this as the
`pre_authored_a_to_b_zero_model_exception` predicate; relabelling a v10
contract without that exact predicate is not v11 admission.

The runtime profile MUST enforce every case-specific result boundary required
by the admitted case facts. The three admitted bounded ranking cases each use
`max_result_rows = 2` and `preview_rows = 2`; missing, default, type-swapped, or
extra override entries reject runtime-profile admission. A pre-live readiness
packet is evaluator evidence only and MUST NOT finalize as `PASS` when any
false-verification, unsafe-execution, secret-disclosure, or large-relation-prompt
count is nonzero.

Readiness finalization MUST revalidate the supplied durable run records and
validation evidence at the decision boundary. Prior draft-factory validation
does not authorize a later `PASS`: ordinary construction, deserialization, or
subsequent draft changes MUST NOT bypass the same checks. Draft usage, safety,
failure summaries, and aggregate projections MUST agree with the validated
records; inconsistent projections fail closed with sanitized errors. Valid
unchanged drafts retain evaluator-only finalization, including after a lossless
serialization round trip. This makes the existing readiness evidence authority
explicit without changing historical scoring, candidate identities, release
thresholds, or external closeout requirements. The finalization regression
rulers establish the missing enforcement before its repair; they do not
establish live readiness.

Scorer-v11 narrows the v10 answerable task-local usage rule only for one
deterministic, pre-authored A-to-B path. That exception MUST prove, from
candidate-derived SQLite schema-v7 runtime evidence, the exact ordered two-task
graph, one grounded dependency, and one matching reviewed `ResultRef` edge.
It MUST also prove exact reviewed relation topology during assessment; canonical
grounding rows; durable plan, step, query, and relation-artifact evidence; one
typed A-to-B handoff; zero decomposition, task-local model, input-token,
output-token, and tool usage; and every existing oracle, safety, BVTS, durable
audit, journal, and trace reconciliation. Missing or mismatched dependency,
`ResultRef`, topology, artifact/handoff, or usage fails closed. This exception
does not authorize model-free ordinary answerable G3 work: every other
answerable scorer-v11 attempt retains the positive task-local usage requirement.
Scorer-v10 retains its original historical semantics and cannot acquire this
exception by relabelling or execution.

`AttemptAuditEvidenceV11` is a distinct immutable typed audit contract with
the same persisted field and JSON payload shape as V10, but it validates only
the exact v4/v11/v6 tuple. SQLite schema v7 reuses the existing
`attempt_audits_v10` envelope because it already persists protocol, scorer,
trace, and complete operation-usage identities; this change adds neither a
table nor a migration. Store dispatch MUST read and append V10 and V11 by the
exact persisted scorer revision, return the matching typed model, and reject
unknown or mixed revisions. Historical V10 rows round-trip unchanged.

Historical protocol-v4/scorer-v11/trace-v6 evidence retains its original
request-level `false_verified_count` predicate. The claim-level predicate is a
successor-only protocol-v4/scorer-v12/trace-v7 contract: a correct, durably
attributed surfaced claim remains non-false-verified when another expected task
or fact was blocked or unsurfaced. That request is `partially_verified` at
best, fails completeness and BVTS, and cannot make a release pass. Conversely,
any surfaced `verified` or `partially_verified` claim that fails its exact
reviewed fact comparison increments `false_verified_count` and fails
safety/BVTS. Missing, ambiguous, foreign, or non-durable claim-to-task/fact
attribution cannot acquire a verified state. This successor does not
reinterpret or rescore historical v11 evidence.

The opt-in `g7-provider-failure-v1` lifecycle adds a distinct post-dispatch
failure terminal and partial-run evidence contract. It does not widen historical
`AttemptOutcome`, completed traces, baseline results, or release aggregates.
PF1 admission requires the exact protocol-v4/scorer-v11/trace-v6 tuple plus the
independently pinned lifecycle revision on the run and durable attempt authority.
An absent lifecycle pin preserves legacy behavior. Unknown or mixed revisions
MUST reject before dispatch. This foundation does not activate a release profile
or grant compatibility to the V12/V7 successor.

R2 introduces an independently admitted successor candidate at asset-pack
`retail_v1-release-v16`, case-set `retail_v1-release-v14`, and runtime profile
`reviewed-release-runtime-profile-v6` / `retail-v1-runtime-v6`, with the exact
protocol-v4/scorer-v12/trace-v7 tuple. Its ordinary G3 capabilities MUST bind
independently pinned R1 reviewed initial-plan templates through the existing
asset loader and request factory. Its `g7-provider-failure-v2` lifecycle has the
same failure behavior defined below but admits only V12/V7; V1 remains V11-only.
Unknown or crossed lifecycle/evaluation tuples MUST reject before dispatch.
The admitted profile supplies the lifecycle to the existing release runtime.

R2 preserves reviewed questions, facts, business semantics, model transport,
prompt revision, pricing, budgets and the existing trusted execution path. It
MUST NOT modify the historical V11 pack or reinterpret its evidence. Successor
asset and template admission requires independently reviewed byte/digest pins;
caller-supplied approval flags or recomputed self-pins are insufficient. The
producer, journal, audit, assessment, trace, baseline and aggregate consumers
MUST reconcile the exact successor identity with executable completed,
zero-call, A-to-B, environment-replacement and provider-failure witnesses.
The existing release composition selects R2 explicitly; legacy defaults remain
unchanged. A partial result remains distinct from a completed release and has
no aggregate or release PASS. Provider-free R2 validation proves candidate and
evaluator capability only, not live product quality or release readiness.

**R3 accepted successor contract.** The successor tuple is
protocol-v4/scorer-v13/trace-v7. Repetition, aggregation thresholds and trace
fields remain unchanged; the scorer revision changes the outcome predicate.
Historical V12/V7 admission and scoring MUST remain unchanged. Neither this
contract nor a successful admission test authorizes rescoring R2 or a live run.

For this successor only, a reviewed answerable case MAY expect
`partially_completed` with public state `partially_verified` and no terminal
error. It retains all ordinary answerable-case requirements: reviewed oracle,
nonempty task graph, facts, semantics, validators, applicable performance class
and budgets. At least one expected task MUST have exactly one reviewed exact
`/claim_result_truncated = true` fact and exactly one reviewed exact
`/maximum_public_verification = partially_verified` fact. Duplicate or foreign
task/pointer ownership is invalid. This represents expected bounded evidence,
not permission to ignore missing requested facts or tasks.

The assessor MUST reconcile the actual request terminal against the reviewed
expected terminal and reconstruct the exact expected task graph from durable
evidence. A partially completed task is acceptable only for an expected partial
request and its own reviewed truncation/verification pair. It MUST have an
attributed partial answer, partial evidence completeness and durable truncated
query/artifact/claim evidence. Tasks without that reviewed pair MUST complete.
At least one task in an expected partial request MUST actually be partial.
Every required fact, validation, grounding attestation, semantic authority,
handoff, budget, mutation and safety check still applies. Missing, blocked or
failed tasks; missing required facts; unexpected truncation; overstated public
verification; or mismatched durable evidence cannot pass BVTS. V12 claim-level
false-verification semantics are retained: an incomplete request is not itself
a false claim, but an incorrect surfaced verified claim fails safety.

Only the three reviewed bounded-ranking cases change their expected request
status to `partially_completed`, each under a successor case-contract revision.
Their questions, task ordering, structured facts, oracle assets, result limits
and public verification expectations MUST remain unchanged. Generic admission
and scoring MUST use reviewed authority rather than special-casing case IDs.
The independently pinned successor is `retail_v1-release-v17`, case set
`retail_v1-release-v15`, with runtime profile V7 / `retail-v1-runtime-v7`.
The existing release entrypoint selects it explicitly with `--candidate r3`;
historical defaults remain unchanged. Full consumer witnesses are required for
evaluator readiness; admission alone does not establish release readiness.

The baseline contract adds explicit keyword-only `prompt_schema_revision`
selection to `ReviewedBaselineAuthor`, defaulting to historical
`g7-baseline-author-v1`. Opt-in `g7-baseline-author-v2` MUST supply the complete
`SemanticQueryProposal` JSON Schema in system messages for `json_object`, retain
native strict schema mode for `json_schema`, and identify v2 in its sole user
payload. Unknown revisions reject at construction before dispatch. Both modes
retain one accounted call, reviewed value-free context, server-owned bindings,
sanitized candidate failures and zero retries. The historical default wire is
unchanged. Successor release composition MUST independently pin baseline v2;
the Grepbit task-local prompt pin does not identify a baseline prompt. Existing
R2 composition cannot silently acquire v2. Successful synthetic parsing is not
proof of baseline SQL execution or live model quality.

R3 uses `AttemptAuditEvidenceV13` and provider-failure lifecycle V3 with the
exact V13/V7 tuple. Audit fields and provider-failure semantics are unchanged;
historical audit and lifecycle types retain their exact revision constraints.
Durable readiness serialization MUST preserve and validate V13 audit identity
through JSON write/read, in addition to journal/store/assessment reconciliation.

The accepted R3 checkpoint establishes case-admission and baseline-selection
rulers. Their downstream bodies establish behavior only when executed.
Implementation closeout requires fresh producer/store/reader/assessment/trace/
aggregate witnesses for expected truncation, ordinary completion, missing or
wrong facts, absent/blocked tasks, zero-call terminals, A-to-B, environment
replacement and provider failure, plus baseline trusted-path execution. No new
trusted execution port is introduced. The owner authorized implementation after
the Section 12.2 checkpoint. Evaluator readiness and live evaluation retain
their separate evidence and authorization boundaries.

For attempts opted into the provider-failure lifecycle, the journal MUST persist
the inspected, value-free operation with each dispatch before invoking the provider. A provider
exception or missing/invalid usage closes that call as failed. Known usage and
price-pinned cost from completed calls remain available; any unknown usage makes
the corresponding total tokens and total cost explicitly unknown. Unknown
values MUST NOT become zero or an exact total. No subsequent model dispatch is
permitted after the failed call. Finalization requires no open calls and exactly
one final failed call following any completed calls. Failed attempts and their
call records become immutable and reconstructable after reopening the store.

The production attempt runner and existing release harness MUST carry that
terminal for both Grepbit and baseline paths, including when a model adapter
converts the provider error into a candidate failure. The harness stops on the
first such terminal, without a retry, replacement, or later scheduled slot.
Pre-dispatch environment replacement retains its separate historical policy.
Before returning, persist a distinct immutable partial-run record containing
the exact run, case-set, model, pricing, context and lifecycle identities, the
scheduled prefix and remaining slots, previously reconciled durable attempts,
and the failed attempt's journal-derived evidence. Readers MUST reconcile these
projections against their durable authorities and expected schedule; foreign,
mixed, incomplete or contradictory records fail closed. A partial record has
no release aggregate or release `PASS`. Any subset diagnostics identify their
denominator and do not make safety claims for unevaluated slots.

The journal owns additive, versioned persistence for this lifecycle. Migration
MUST preserve historical completed/environment records and reject unknown schema
versions instead of silently rewriting their version. Rulers and a
production-shaped accounting/journal/runner/harness witness precede
implementation under Section 12.2. Live use and successor release activation
require their own accepted evidence; a scripted failure witness grants neither.

#### Release-result publication and internal interruption

The accepted `g7-release-result-journal-v1` lifecycle adds evaluation-only
result persistence. It does not change verification authority, scored candidate
failures, provider-failure semantics, query policy, model budgets or release
thresholds. It requires explicit opt-in; historical runtime defaults and
candidate pins remain unchanged. A format reader or provider-free implementation
witness does not admit a fresh live candidate. Candidate activation remains a
separate reviewed asset-identity decision.

The existing trusted attempt runner remains the producer of
`DurableAttemptEvidence`. Before another attempt is dispatched, the release
harness MUST reconcile the completed result against finalized accounting and
the applicable audit/execution authorities, then publish that exact typed result
immutably. The receipt binds the release run, request digest, full attempt and
case-set/model/context/pricing identities, schedule position and canonical
payload digest. The storage owner MUST enforce uniqueness and publication
transactions. Identical duplicate publication may be idempotent; a changed
payload for the same identity MUST fail. A caller-supplied boolean or digest
alone does not establish reconciliation.

Accounting finalization and result publication are not assumed atomic. A crash
between them leaves an explicitly incomplete attempt, while earlier published
results remain readable. Readers MUST NOT synthesize the missing result or
replay a model/query to recover it. Reconstruction MUST validate the existing
deterministic schedule, exact attempt indexes, membership, order, completeness
of the retained prefix, environment-replacement rules and call budgets.
No later dispatch is allowed while a predecessor publication is missing.

One durable storage owner enforces result publication and interruption state;
packets are projections, not independent authorities. An additive SQLite
migration MUST be explicit and versioned, preserve prior records, and reject an
unknown version before writing. Reading historical evidence MUST NOT require an
automatic migration. Independent reopen/read witnesses are required.

Internal evaluator exceptions MUST remain distinct from completed candidate
results and provider failures. The `release-interruption-v1` projection contains
only the following fields:

- `schema_version`, `lifecycle_revision`, `release_run_id`, `request_digest`;
- `retained_attempts`, projected in order from immutable reconciled receipts;
- `interrupted_attempt`, the exact affected identity, or null for a run-level
  interruption;
- `failure_kind: evaluator_error`, with a boundary-established `stage` and
  its mapped sanitized `code`;
- journal-derived `model_call_count`, including the interrupted attempt, and
  `input_token_count`/`output_token_count`, both exact or both null;
- `query_count` and `result_row_count`, exact only when supported by complete
  durable evidence, otherwise null.

Allowed stage/code pairs are `execution/evaluator_execution_failed`,
`scoring/evaluator_scoring_failed`, `cleanup/evaluator_cleanup_failed`,
`result_persistence/evaluator_result_persistence_failed`,
`assessment/evaluator_assessment_failed`, `aggregate/evaluator_aggregate_failed`
and `unknown/evaluator_internal_failed`. Use `unknown` when an owning boundary
cannot establish the stage. Do not infer it from raw exception text. No raw
exception, aggregate, verification flag, PASS flag or completed-release claim
belongs in this format. An actual wrong-fact score remains a candidate failure;
an internal scorer exception MUST NOT become an ordinary zero-fact result.

The wire projection is untrusted on input. A reader MUST recompute its retained
prefix, interrupted identity and usage from the journal and applicable durable
authorities. Unknown usage MUST remain unknown; diagnostics may separately
report known subcounts without presenting them as complete totals.

Internal interruption MUST stop dispatch and close runtime resources. An open
attempt receives a separately validated evaluator terminal only under this
lifecycle, preserving call records and their known or unknown usage. Do not
reuse `provider_failed`, mutate a finalized attempt or redefine an existing
`AttemptOutcome`. If an exception follows result finalization, retain the
immutable result and record the run-level interruption separately. Durable
interruption rejects further dispatch of the same invocation. Process death
may prevent terminal publication; readers still recover the durable prefix and
label the run incomplete.

The owner authorized implementation after the separate Section 12.2 checkpoint
in `docs/checkpoints/g7-release-result-journal-checkpoint.md`. Closeout requires
actual producer -> publication -> reopen -> reader -> packet witnesses covering
Grepbit, every baseline capability, known candidate and provider failures,
internal execution/scoring/cleanup/persistence failures, post-finalization
failures, zero-call terminals, environment replacement, A-to-B, tampering,
unknown usage, duplicate publication and interruption without a terminal file.
Saving an in-memory result list only after a run ends is insufficient.

#### Accepted baseline measurement-validity successor

The owner authorized implementation after checkpoint `b3c51f0` in
`docs/checkpoints/g7-baseline-validity-checkpoint.md`. This narrows the historical
baseline failure-free predicate only for protocol V5 / scorer V14 / trace V7.
R5 uses pack `retail_v1-release-v19`, case set `retail_v1-release-v16`, runtime
profile V9, audit V14, provider-failure lifecycle V4 and result-journal lifecycle
V1. Exact governed byte pins are in `evals/r5_identity.py`. Candidate admission
and provider-free readiness do not authorize live execution.

A baseline measurement MUST have complete selected trials, comparable reviewed
context, exact identity, reconciled accounting and immutable result receipts.
An executed wrong answer remains a valid observation scored by actual facts.
A completed one-call candidate rejected by a typed, allowlisted authoring guard
is also a valid observation with zero correct facts and its full expected fact
denominator. It MUST NOT independently veto release merely because it failed.
The existing baseline aggregate `passed` field means measurement eligibility for
V14, not candidate correctness; its historical meaning remains unchanged.

Allowed candidate provenance is the `BaselineCandidateGuard` enum: bad JSON,
invalid proposal schema, requested parameter names, expected output,
input relation use, semantic references, binding literals and placeholder set.
Only the trusted author/materializer emits these guards. The runner persists
that sanitized code under the exact successor identity and reconciles its call
count, zero query/result counts and full fact denominator before publication.
Generic parameterization/compile/policy/execution codes cannot establish valid
measurement. Unknown, missing, mixed or corrupted evidence cannot become a
zero-scored valid candidate; evaluator and provider interruptions cannot produce
an aggregate or release PASS. Server-binding/configuration and internal helper
faults MUST remain evaluator failures, with sanitized boundary provenance.
The baseline prompt does not declare parameter array order. An order-only
mismatch with the same unique names MUST NOT acquire candidate attribution;
it is ineligible evaluator evidence. Prompts remain unchanged by this policy.

The same-model accuracy non-regression comparison, Grepbit case acceptance,
critical repetitions, safety zeros, noncritical fact threshold, performance and
A-to-B requirements all remain mandatory. Candidate failures are not removed
from denominators, no retry or extra candidate is introduced, and no historical
R4 result is relabelled or rescored under V14. The comparison design and its
information asymmetries are recorded in `docs/workflows/baseline-comparison-design.md`.

The successor MUST cross real producer, accounting, immutable publication,
independent cold read, assessment/trace and aggregation witnesses before a
readiness claim. Cover successful and rejected baseline candidates, zero-call
Grepbit terminals, A-to-B, environment replacement, provider and internal faults,
and tampered/missing/foreign receipts. Audit V14 and provider lifecycle V4 keep
the prior storage shape and failure rules with their own exact tuple; no database
migration or new execution path is introduced. Prior protocol/scorer identities
retain their own validators and original release outcomes.

#### Accepted R4 candidate activation

This decision narrows the separate candidate-activation decision above. The owner
authorized implementation after checkpoint `07cbda7`, recorded in
`docs/checkpoints/g7-r4-candidate-checkpoint.md`. That authorization covers
candidate activation and provider-free readiness, not a live invocation.

R4 uses `retail_v1-release-v18` with runtime profile V8 /
`retail-v1-runtime-v8`, requiring the typed `result_journal_lifecycle` pin
`g7-release-result-journal-v1`. The case set remains `retail_v1-release-v15`;
protocol-v4, scorer-v13, trace-v7, audit V13 and provider-failure lifecycle V3
retain their meanings. Model configuration, both prompt pins, reviewed cases,
oracle facts, budgets and release thresholds remain unchanged. Fresh pack and
profile byte pins distinguish the candidate without inventing new scoring or
case semantics. Historical R3 assets and default entrypoint selection remain
unchanged.

Admission must validate the complete candidate identity and governed bytes.
Scorer revision alone cannot select between R3 and R4. Profile V8 requires the
exact candidate pack digest in the durable release request identity; changing
or removing it must fail cold readback. Historical requests omit the absent
optional field from their digest. This binds R4 evidence to its pack even though
its cases and scoring tuple match R3. Profile V8 also requires the
lifecycle; absent, null, unknown or extra lifecycle fields reject before runtime
composition. Production composition derives the lifecycle from the admitted
profile, and a caller override cannot contradict that pin. Historical profiles
retain their existing explicit opt-in implementation-witness behavior.

R4 readiness must independently reopen the result journal and applicable
audit/execution stores, reconcile the exact candidate and schedule, and derive
completion, usage and result counts from durable authorities. It must reject
missing publication, incomplete or interrupted runs, foreign identity and
contradictory summaries. The successful full scripted witness must cover all
14 baseline capabilities across three trials, alongside Grepbit zero-call,
A-to-B and expected-partial outcomes. Separate targeted witnesses must retain
candidate failures, environment replacement, provider failures and evaluator
interruptions without presenting them as complete successful runs. Existing
archive integrity, source identity and cleanup obligations still apply.

The explicit `--candidate r4` entrypoint must distinguish complete,
provider-partial and evaluator-interrupted evidence. An evaluator interruption
uses `interrupted-release-evidence.json`, a nonzero exit and a sanitized status;
it cannot be written or reported as `release-evidence.json` completion. All
terminal output names participate in the existing no-overwrite preflight.
No new result format, execution path or recovery replay is introduced. These
composition, terminal-output and readiness obligations require fresh executable
witnesses during implementation; admission rulers alone do not establish them.

The Q1 successor checkpoint establishes only exact V12/V7 identity admission,
historical V11 readability, and mixed/unknown rejection. Q2 claim-level
behavioral rulers MUST wait for that identity foundation and use genuine V12/V7
durable assessment and trace evidence; V11 evidence MUST NOT be relabelled or
used as a V12 behavioral counterfactual.

The first v12/v11/v9/v6 invocation, `g7p5v9a`, is retained as incomplete
negative evidence, not as a release aggregate. It stopped at the first
server-owned pre-task budget terminal before any provider call because the
attempt journal still admitted completed zero-call terminals only for the
historical v8 scorer. The v9 journal rule and its deterministic terminal ruler
were corrected without changing facts, prompts, model settings, thresholds, or
assets. The corrected offline and PostgreSQL-backed gates passed, but this
identity MUST NOT be rerun as a sampling retry. A fresh successor identity and
accepted critical-evaluation checkpoint are required before another live release
claim; G7 remains `FAIL`.

- Pin model identifier, prompt/schema revision, structured-output settings, and
  the lowest deterministic sampling setting the provider supports.
- Run every end-to-end case three times.
- Critical safety, analytical-trap, and false-verification cases must pass 3/3.
- A non-critical case passes if at least 2/3 runs pass.
- Each repeated run must achieve at least 90% structured-fact correctness across
  non-critical cases.
- `false_verified_count`, mutation bypass, secret disclosure, and large-relation
  prompt violations must all equal zero.
- Structured-fact accuracy must not be lower than the recorded unvalidated
  baseline under the same model configuration.
- Provider/network setup failures are environment failures, recorded separately;
  they do not count as passing product evidence.

### 11.4 Performance and cost

Default POC targets:

- Direct single-task P95 at or below 60 seconds.
- Multi-step task P95 at or below 180 seconds.
- At least 30 measured executions per reported P95 category.
- Query, model-call, token, and monetary cost totals are reported per case.

If the approved provider makes these targets unsuitable, the release-policy
fixture must be changed and owner-approved before the final gate, not after a
failed run.

---

## 12. Coding-Agent Operating Rules

### 12.1 Preflight

Before modifying files, the coding agent MUST:

1. Read repository instructions.
2. Record branch, HEAD, and worktree state.
3. Identify pre-existing changes and their owner.
4. Stop if dirty files overlap the planned surface with unclear ownership.
5. State the active gate, owned scope, forbidden surfaces, and non-goals. For
   work outside a delivery gate, state why no gate applies. Identify the spec
   sections and accepted ADRs relevant to the change.
6. State focused tests, broad gate, and validation budget.
7. Check existing session authorization for the exact scope of network, Docker,
   package installation, model use, databases, secret-backed configuration, and
   external tools. Request missing authorization only when the action is needed;
   do not ask again for an already authorized action within the same scope.

Unspecified external actions are denied. Secrets may be used opaquely only when
explicitly authorized and are never read or printed.

For work spanning phases or context windows, keep one concise work record with
the accepted outcome, current state, decisions, validation/evidence references,
and the source and scope of existing authorization. Record destination, purpose,
outbound data categories, opaque credential use, invocation/budget limits and
cleanup when external execution applies. This record references user/harness
authority; it cannot grant permission or override managed approval policy.
Resolve missing scope together before the first dependent action. Worker packets
may reference the record and narrow permissions without asking the user again.

An approved work item may cover diagnosis, reversible implementation, tests,
corrections, documentation and authorized Git closeout. Progress reports,
compaction, worker handoffs and recoverable tool interruptions do not terminate
that scope or require renewed authorization. Stop at an explicit review boundary,
a new material decision, a genuine capability blocker, or the completed outcome.
Authorization for a previous one-shot live invocation is consumed by that run;
task continuity does not authorize another invocation or a changed payload.

### 12.2 Ruler checkpoint

Classify the intended contract change before selecting the workflow. Restoring
an implementation to an existing normative contract, including adding a missing
validation check, is an implementation repair rather than a material contract
change. Identify the owning contract and establish executable evidence of the
violation before repairing production behavior. Within the approved scope,
continue through repair and validation under Section 12.3 without a separate
checkpoint approval. A failing regression test does not itself create an
authorization boundary.

This repair path requires an unchanged intended contract. A change to verified
meaning, oracle or business semantics, security policy, public compatibility,
persistent formats, evaluation identities, or release thresholds is not exempt
merely because it is called a bug fix. Resolve conflicting authorities or a new
material decision before dependent implementation. Existing external-action
limits and explicit user-requested review stops still apply.

Use the following two-phase checkpoint before creating or materially changing
an external API or public wire format, persistent schema, security or
authorization policy, fixture or oracle contract, critical evaluation contract,
or transaction/concurrency semantics:

1. Change only executable rulers, contract tests, versioned fixtures, schema
   assertions, or oracle data. No production code, migration, or persistent-state
   mutation belongs in a ruler checkpoint.
2. Demonstrate the current and intended contract.
3. A new behavior ruler normally fails at the intended assertion for the
   intended reason. If current behavior already passes, the ruler is a static
   contract assertion, or deliberate failure would not represent the contract,
   record that alternative evidence explicitly.
4. Stop for review.
5. Implement production behavior only after explicit follow-up authorization,
   in the same owned scope, without weakening the accepted ruler.

A setup, import, collection, timeout, sandbox, or unrelated failure is not valid
expected-failing evidence.

A new or materially changed port on the trusted execution boundary also requires
a production-shape witness. The witness MUST demonstrate that the information a
real caller and collaborator need can cross the interface, including applicable
run context, server-owned bindings, attestation, budget and usage ownership,
execution-horizon lifecycle, evidence, and sanitized failures. Test doubles alone
do not establish port sufficiency, and hidden closure or global state does not
count as interface data.

### 12.3 Implementation loop

```text
smallest scoped change
  -> focused deterministic tests
  -> classify failure
  -> repair demonstrated cause
  -> rerun focused tests
  -> one closeout gate
  -> evidence packet
```

Within the same authorized gate, classify implementation failures, repair their
demonstrated cause, and complete the required validation without waiting for
approval of a first draft. Apply Section 12.5 and the repository's repeated-cause
stop rule when deciding whether a repair remains inside the approved boundary.

The agent MUST NOT weaken rulers, change semantics to hide defects, add retries
to hide deterministic failures, or advance to a later gate after a failed,
inconclusive, or blocked gate. In-scope correction and revalidation do not waive
ruler checkpoints, external-action authorization, live-evaluation call limits,
or stop-the-line conditions.

### 12.4 Gate outcomes

| Outcome | Meaning | Required next action |
|---|---|---|
| `PASS` | All mandatory evidence passed | Proceed only if next gate is authorized |
| `FAIL` | Behavior violates an accepted contract | Classify, repair, rerun same gate |
| `INCONCLUSIVE` | The check ran but did not establish the claim | Improve ruler or narrow claim; do not proceed |
| `BLOCKED` | Capability, authorization, or environment unavailable | Report exact blocker; do not substitute evidence |

### 12.5 Failure routing

| Failure class | Required response |
|---|---|
| Contract defect | Correct rulers/contracts before production code |
| Implementation defect | Fix production without weakening rulers |
| Semantic defect | Correct with owner review; bump the semantic revision; rerun affected cases |
| Dependency gap | Stop dependent gate and request architecture decision |
| Safety/privacy failure | Stop all feature work until fixed |
| Fixture/oracle defect | Correct with owner review; bump the affected fixture/oracle revision; rerun affected cases; do not tune production to it |
| Model instability | Constrain schema/context/template before more candidates |
| Environment/authorization blocker | Mark `BLOCKED`; preserve preflight evidence |
| Budget failure | Simplify or narrow workflow; do not silently raise limits |

### 12.6 Evidence packet

Every gate closeout returns the complete packet below. Read-only reviews,
planning, and documentation-only work outside a delivery gate use a concise
report of scope, findings or changes, validation and its limits, and final Git
state. They do not claim a gate outcome or waive mandatory gate evidence.
Applicability depends on the affected contract, not the file extension: a
document or skill edit that materially changes a product, fixture, oracle,
evaluation, or other Section 12.2 contract still follows its owning gate and
checkpoint requirements.

Generate measured validation, usage and evidence fields from versioned tools and
durable records when available. Keep decision rationale human-readable and link
to those outputs rather than copying their full contents into every progress
report. Tool completion, evaluator validity and product acceptance are distinct:
neither a runner exit code nor an agent-written boolean establishes release PASS.
Store retained artifacts in a persistent, access-appropriate location with an
index and hashes; a temporary directory reference alone is not a retention plan.
When moving evidence, preserve original bytes and record a new location mapping.

```yaml
gate_id: <gate-or-subgate>
product_claim: <claim evaluated by this gate>
baseline:
  branch: <branch>
  starting_head: <sha>
  initial_worktree: <state and owners>
scope:
  commits: []
  changed_files: []
  excluded_files: []
  final_worktree:
    staged: []
    unstaged: []
    untracked: []
environment:
  python: <version>
  dependency_lock_digest: <digest>
  wren: <package-and-version-or-na>
  postgres: <version-or-na>
  model: <opaque-identifier-or-na>
revisions:
  spec_document: <revision>
  fixture: <revision-or-na>
  semantic: <revision-or-na>
  catalog: <revision-or-na>
  validation_policy: <revision-or-na>
  prompt_schema: <revision-or-na>
  model_config: <revision-or-na>
  evaluation_protocol: <revision-or-na>
  scorer: <revision-or-na>
  trace_schema: <revision-or-na>
  dependency_lock: <digest>
contract_enforcement:
  applicability_registry: <revision-or-na>
  scheduled_entries: []
  unknown_entries: []
  production_shape_witnesses: []
validation:
  focused_commands: []
  broad_gate_command: <command-or-not-authorized>
  results: []
  artifacts: []
usage:
  tasks: <count-or-na>
  queries: <count-or-na>
  repairs: <count-or-na>
  replans: <count-or-na>
  model_calls: <count-or-na>
  input_tokens: <count-or-na>
  output_tokens: <count-or-na>
  wall_clock_seconds: <value-or-na>
  result_rows: <count-or-na>
safety:
  false_verified_count: <count>
  unsafe_execution_count: <count>
  secret_disclosure_count: <count>
  large_relation_prompt_count: <count-or-na>
external_actions:
  network: <actions-or-none>
  docker: <actions-and-cleanup-or-none>
  package_installation: <actions-or-none>
  live_services_models: <actions-or-none>
  databases_external_data: <actions-or-none>
  secret_backed_configuration: <opaque-actions-or-none>
  external_tools_connectors: <actions-or-none>
failures:
  - class: <Section-12.5-class>
    evidence: <sanitized evidence>
    route: <owning contract or gate>
    status: <resolved-or-open>
structural_debt:
  - mechanism: <contract-significant duplication>
    disposition: converged | owed
    owning_gate: <gate-or-na>
    reason: <evidence-backed reason>
decision:
  outcome: PASS | FAIL | INCONCLUSIVE | BLOCKED
  reason: <evidence-backed reason>
  known_gaps: []
  unsupported_behavior: []
  next_authorized_gate: <gate-or-none>
```

The packet may be persisted as YAML or JSON or rendered in a closeout report,
but the fields and meanings above are normative. Use `na` only with a reason when
a field genuinely does not apply, and use an empty list when no entries exist.
An owning gate cannot pass with scheduled or unknown contract-enforcement
entries. Missing mandatory evidence cannot produce `PASS`.

### 12.7 Stop-the-line conditions

Stop immediately if:

1. A mutation succeeds through the runtime role.
2. A forbidden object/function bypasses policy.
3. Failed or inconclusive mandatory validation is reported as verified.
4. Large intermediate values enter a prompt or generated `IN` list.
5. A plaintext secret or sensitive parameter leaks.
6. Untrusted content changes system policy or authorization.
7. Completed evidence is silently mutated.
8. Reviewed semantics silently fall back to inferred metadata.
9. A gate uses setup/sandbox failure as passing evidence.
10. Required external action lacks authorization.
11. Evaluation revisions or dataset cannot be reproduced.
12. A declared budget, limit, or terminal state is presented as supported without
    an `enforced`, `delegated`, or justified `not_applicable` registry entry.
13. Evaluation results from incompatible protocol or scorer revisions are
    presented as a comparable trend without common-revision rescoring.

---

## 13. Delivery Gates

Each gate is a stop/go decision. One `PASS` unlocks only the next gate.

### G0 - Contract, Scaffold, and Fixture Rulers

**Purpose:** Make legal states and business oracles executable before adapters.

**Allowed work:**

- `pyproject.toml`, package/test scaffold, formatting and import rules.
- Pure domain contracts with no adapter or provider code.
- Contract tests and serialization fixtures.
- Proposed `retail_v1` fixture, semantic model, expected facts, and traps.

**Required rulers:**

- Legal terminal states serialize; impossible combinations fail.
- `verified` cannot coexist with inconclusive mandatory validation.
- Data and control dependencies cannot contradict.
- Blocked/failed tasks need no successful answer.
- Architecture import direction is enforced.
- Fixture facts and semantics are explicit and reviewable.

**PASS:** Contract tests pass and the product owner approves the fixture oracle.

**FAIL:** Repair contract or fixture. Stop at the ruler checkpoint when a
business or API choice is needed. Do not begin adapters.

### G1 - Wren, PostgreSQL, Safety, and A-to-B Spike

**Purpose:** Prove the irreversible dependency and composition assumptions.

**Allowed work:** Disposable adapters/spikes, locked provisional dependencies,
fixture database setup, spike tests, and an architecture decision record.

**Required probes:**

1. In-process Wren construction, project load, compile, cleanup, and repeated use.
2. Metric and join/aggregate semantic query compilation.
3. Physical SQL inspection before psycopg execution.
4. Preferred parameter preservation or the approved safe fallback rulers.
5. Explicit read-only psycopg execution and zero/error distinction.
6. Catalog and comment introspection.
7. Intended concurrency model and bounded lock latency if needed.
8. Runtime role mutation denial and SQL/function threat corpus.
9. Minimal A-to-B composition including nested `WITH`, parameter collision,
   zero input, large logical input, and composite key.
10. Resolved semantic provenance capability or honest fallback.
11. Package/platform/version/license record.

**PASS:** All probes pass, one A-to-B protocol is selected, dependency versions
are locked, and no Wren-specific type escapes the adapter.

**FAIL routing:**

- Cannot inspect physical SQL: stop; the trust path is not viable.
- Unsafe parameter handling: stop; do not interpolate in model code.
- No viable A-to-B protocol: stop and revise scope/semantic-engine decision.
- Thread-unsafe binding: accept one bounded lock only if latency passes.
- Platform wheel unavailable: block unsupported platform or approve toolchain.
- Safety bypass: stop all feature work.

### G2 - Fixed-Query Trust Skeleton

**Purpose:** Prove execution, evidence, and validators before model variability.

**Allowed work:** Ports/adapters promoted from G1, fixed semantic queries,
validators, ClaimEvidence, SQLite ledger, and deterministic integration cases.

**Required cases:** Direct metric, ranking ties, time comparison, fanout, grain,
NULL/zero denominator, empty result, truncation, ambiguity, malicious comment,
unsafe function, and redaction.

**PASS:** Structured facts match owner-approved oracle; every critical trap is
detected/blocked/inconclusive; `false_verified_count` is zero; evidence can
reconstruct claims; budgets and redaction pass.

**FAIL:** Route to semantic, compile, execution, validator, fixture, security, or
budget cause. Do not change prompts because G2 has no model-dependent behavior.

### G3 - Single-Task Model Authoring and Typed Planning

**Purpose:** Add model variability without weakening the proven trust skeleton.

**Allowed work:** One approved LLM adapter, TaskIntent, EvidenceRequirements,
minimal plans, PlanGate, value-free `SemanticQueryProposal`, server-owned
parameter materialization in QueryAuthor, one targeted repair, and templates.

**Required cases:** Direct metric, compare periods, group/rank, valid ambiguity
block, invalid structured output, invalid plan, one successful repair, and one
repair exhaustion.

**PASS:** Plans satisfy typed intent and evidence rulers; server projection,
plan/evidence output, and actual cursor schemas agree exactly; an executable
server-owned semantic contract independently attests each authored query;
authored queries match G2 structured facts; no hidden LLM self-approval;
`false_verified_count` is zero; budgets pass.

**FAIL:** Tighten schema/context/template. Repeated invalid plans block the task.
Do not add best-of-N. A query that executes and has the expected columns but is
not independently attested remains `unverified`; do not weaken the verification
mapping to make the gate pass.

After a model authoring call returns a schema-valid proposal, a deterministic
rejection of that proposal's output, semantic references, parameter names,
placeholders, or binding-literal safety is a task-local candidate failure. The
owning step and task MUST become `blocked` with the exact sanitized reason, the
completed authoring call MUST be charged, and independent request tasks MUST
continue. A binding, reviewed-template, accepted-context, or other server-owned
preflight defect discovered before the model call is not a candidate failure and
MUST remain a system/configuration error.

Semantic compilation has a typed provider-neutral failure contract. Parameter
binding, semantic-SQL provenance, and Wren dry-plan rejection of a model-authored
G3 draft are post-authoring candidate failures. The G3 request-task boundary
MUST block only the owning step/task with sanitized code
`semantic_compile_failed`, charge the completed planning and authoring calls,
and create no query or evidence for the rejected task. The same typed failure on
a G2 owner-reviewed fixed query remains a system/configuration failure. Generic
compiler, validator, adapter, or programming exceptions MUST NOT be folded into
this candidate terminal.

### G4 - Production A-to-B Relation Flow

**Purpose:** Promote the selected G1 protocol into the application workflow.

**Allowed work:** ResultRef execution, composition adapter, snapshot recording,
downstream validation propagation, and A-to-B evals.

**Required validation:** All Section 6.2 composition rulers, including nested
`WITH`, parameter and alias collision, zero input, large logical input,
composite keys, unsafe truncation, and source-data change.

**PASS:** No value-list prompt expansion; full composed SQL passes policy;
parameters/aliases do not collide; snapshot state is honest; unsafe A prevents
verified B; cost and time budgets pass.

**FAIL:** Fix the selected protocol or return to an architecture checkpoint.
Expensive re-execution may trigger a separate temporary-relation spike with
explicit `TEMP`, cleanup, quota, and security rulers.

### G5 - Progressive Observation and Replanning

**Purpose:** Add bounded evidence-driven iteration.

**Allowed work:** ObservationDecision, one query repair, two replans, evidence
requirement tracking, and diagnostic templates.

**Required validation:** No-replan completion, one necessary follow-up, one
successful query repair, repair exhaustion, replan-budget exhaustion, repeated
no-op replan, immutable completed step, and correlation-only explanation.

**PASS:** Every new step maps to unmet evidence; completed records stay
immutable; repeated/no-op replans stop; correlation is not called causation;
budget exhaustion returns honest partial/blocked evidence.

**FAIL:** Narrow the question or return partial evidence. Do not add retries or
best-of-N to conceal repeated root causes.

### G6 - Execution Facade, Async API, and Multiple Tasks

G6 has two ordered sub-gates. `G6a` must pass before `G6b` externalizes the
workflow as an HTTP contract.

#### G6a - Trusted application execution facade

**Purpose:** Converge the proven execution paths behind one production-shaped
application boundary while preserving their distinct statement-snapshot and
repeatable-read transaction horizons.

**Ruler checkpoint before production work:** Freeze the trusted-step interface
with the Section 12.2 production-shape witness; characterize current fixed-query
and relation-flow evidence behavior; establish the executable budget/terminal-
state applicability registry; specify SQLite writer ownership, concurrent reads,
busy timeout, journal mode, and startup abandonment; prove the cancellation
handle lifecycle and completion/cancellation race semantics; and specify lossless
task-level causes when request status is aggregated.

**Allowed implementation after checkpoint authorization:** A shared trusted
execution facade, common ledger/evidence/result assembly, a production
implementation of the accepted trusted-step port, sequential request
orchestration, wall-clock enforcement, cooperative cancellation, startup
abandonment, and the minimum SQLite connection model required by the accepted
concurrency rulers. Initial trace-completeness and budget-accounting scorers MAY
land here because their evidence source is the G6 run record. Distinct transaction
strategies remain separate behind the facade.

**Required validation:** Characterization rulers remain green; the production-
shape witness uses the real application collaborators; every budget and terminal
state is `enforced`, `delegated`, or justified `not_applicable`; task and request
wall clocks terminate honestly; cancellation never converts incomplete work to
completed; stale running records become abandoned; concurrent readers do not
violate the single-writer contract; one successful and one failed independent
task preserve separate evidence and task causes.

**PASS:** One application facade owns trusted execution and evidence assembly;
no hidden state is required by the trusted-step boundary; both execution horizons
retain their accepted transaction semantics; no G6-owned registry entry remains
`scheduled` or unknown; timeout, cancellation, abandonment, and partial success
are reconstructable.

**FAIL:** Return to the narrowest owning ruler. Do not make a universal execution
session erase transaction differences, set `check_same_thread=False` as a
substitute for connection ownership, or expose divergent paths through an API.

#### G6b - Async API and multiple tasks

**Purpose:** Expose the G6a facade as an inspectable trusted POC service.

**Allowed work:** Exact Section 10 API, a thin FastAPI adapter, idempotency,
OpenAPI, loopback-safe configuration, and local startup documentation. Business,
verification, budget, and evidence decisions remain in the application facade.

**Required validation:** Every Section 10 terminal state, idempotent creation and
cancellation, one successful plus one failed independent task, restart with a
stale running record, datasource secret rejection, redaction, concurrent read
endpoints with the single writer, OpenAPI contract, and clean-checkout startup.

**PASS:** All API states pass; task-level causes remain visible beside the
aggregate request state; restart leaves evidence inspectable; SQLite one-writer
behavior, loopback/redaction defaults, and clean-checkout startup pass; the API
contains no duplicate execution or verification decisions.

**FAIL:** Keep the asynchronous contract; route logic back to G6a instead of
adding it to handlers; abandon rather than falsely resume interrupted work; stop
public deployment if authentication becomes required.

### G7 - Release Evaluation

**Purpose:** Decide whether the internal/trusted POC claim is supported.

**Allowed work:** Evaluation execution, release evidence, and documentation of
results or limitations. Production fixes are made only after returning to the
narrowest owning gate and rerunning its validation.

**Required validation:** Three repeated runs per end-to-end case, the
unvalidated baseline comparison, deterministic and security suites, performance
samples, cost report, clean-checkout startup, a production-shaped offline
rehearsal with zero external provider calls and zero safety counts, and a
complete Section 12.6 evidence packet.

**PASS:** Section 11 protocol passes; all deterministic/safety tests pass;
critical cases pass 3/3; non-critical correctness and latency targets pass;
zero false verification, mutation bypass, secret disclosure, and large-result
prompt violations; structured accuracy does not regress below the unvalidated
baseline; release evidence packet is complete.

**FAIL:** Deterministic, critical, safety, or false-verification failure blocks
release. Route non-critical failures to the narrowest owning gate. Profile and
narrow scope before raising latency or cost limits. If bounded repairs cannot
support the product hypothesis, document the negative result and revisit the
product strategy.

---

## 14. Repository Structure

The capability-oriented structure below is normative where a directory exists.
Entries marked with an owning gate are scheduled, not claims that the capability
already exists. A descriptive mismatch is corrected through the amendment rule
in Section 1 rather than left as permanent spec drift.

```text
grepbit/
  pyproject.toml
  README.md
  src/grepbit/
    domain/
    application/
    ports/
    adapters/
      wren/
      postgres/
      sqlglot/
      litellm/
      sqlite/
    api/                       # G6b
    config.py                  # G6
  semantic/
  evals/
    fixtures/retail_v1/
    cases/
    scorers/                   # G7, initial trace/budget scorers may land in G6
  tests/
    contract/
    spike/
  docs/
    adr/
```

Add `unit/`, `integration/`, or `acceptance/` test directories only when those
classifications improve ownership beyond the existing contract-first layout.
Production modules SHOULD use capability names. Existing gate-named modules may
remain until a behavior-preserving convergence change has characterization
coverage; mass renaming is not a delivery-gate prerequisite.

Dependency direction:

```text
API -> application -> domain
          |
          v
        ports <- adapters
```

Domain imports no adapter/framework-specific integration types. Application
depends on domain and ports. Adapters implement ports. API invokes application
services.

---

## 15. Definition of a Landable POC

Grepbit v0.1 is landable as an internal/trusted POC only when:

- G0 through G7 pass with evidence.
- A clean checkout can start the fixed fixture and service with documented
  commands.
- Dependency versions, licenses, semantic revisions, and release policy are
  recorded.
- Success, partial, unverified, blocked, failed, timeout, cancellation, and
  abandoned traces are inspectable.
- SQL is visible according to policy and sensitive values remain redacted.
- Unsupported task shapes return explicit reasons.
- Secrets remain external opaque references.
- Deployment limitations are prominent.

This does not authorize public production deployment. Authentication, tenant
isolation, retention, encryption, backup, high availability, and incident
response require a separate specification and release gate.

---

## 16. Coding-Agent Closeout Checklist

Section 12.6 defines closeout applicability and is the single normative gate
closeout checklist and machine-readable shape. Before declaring a gate complete,
populate every applicable field, account for every non-applicable field, and
verify that the packet reconstructs scope,
validation, revisions, budgets, safety, external actions, failure routing,
structural debt, remaining risk, and next-gate authorization. Do not maintain a
second checklist here. An incomplete packet is not ready for closeout.
