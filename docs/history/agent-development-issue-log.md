# Agent Development Issue Log

## Purpose and authority

This document is a non-normative engineering retrospective. It records problems
observed while coding agents developed Grepbit, how the team resolved them, and
which prevention rule now owns each failure mode.

It does not replace `spec/grepbit_poc_spec.md`, `AGENTS.md`, accepted ADRs, or
executable rulers. When this log conflicts with those sources, the authoritative
source wins. Commit references are evidence pointers, not proof that a later
gate still passes.

Status values used below are:

- **Resolved**: the owning contract and implementation passed their accepted
  validation.
- **In progress**: an accepted ruler or implementation is currently open.
- **Owed**: intentionally deferred to a named future boundary.
- **External**: caused by environment or authorization rather than product
  behavior.

## Failure-mode summary

| Category | Recurring failure mode | Resolution pattern |
|---|---|---|
| Governance | The spec and agent guide restate the same obligation at different strengths | Keep normative detail in the spec and operational deltas in `AGENTS.md`; amend both through a ruler checkpoint when required |
| Rulers | A test claims to exercise behavior but fails before reaching the owning boundary | Require collection success, an intended assertion, and a production-shape witness |
| Semantic authority | Model output or AST presence is mistaken for reviewed business truth | Require an exact owner-reviewed contract and server-owned semantic attestation |
| Execution architecture | Test doubles prove a port that a real collaborator cannot use | Add a production-shape witness and converge execution through the trusted facade/task scope |
| Lifecycle and budgets | A declared timeout, state, or budget has no enforcement owner | Maintain an applicability registry and separate request, task, attempt, and statement ownership |
| Persistence | Public state is assembled from transient objects instead of durable evidence | Persist terminal task results, query records, evidence, usage, and ordering before projection |

### G7 historical profile execution supersession

- Observed: legacy P4f/P4g rulers required a runtime-profile-v2 asset without a
  request-contract pack to construct an executable factory after request
  grounding became mandatory.
- Risk: preserving that construction would reintroduce an ungrounded execution
  path and allow verified authority without selected reviewed request contracts.
- Resolution: preserve v2/v8-v10 asset admission and semantic-material read
  compatibility, but make v2 factory execution fail before model, state, task,
  or database mutation. Runtime-profile-v3 with a validated nonempty pack is
  the sole executable release boundary.
- Prevention: the P4f/P4g compatibility rulers now distinguish readable
  historical authority from executable grounded authority.
- Status: Resolved.
- Evidence: `tests/contract/g7/test_p4f_cross_task_runtime_profile_checkpoint.py`;
  `tests/contract/g7/test_p4g_release_asset_promotion_checkpoint.py`.
| API and concurrency | Async handlers accidentally duplicate decisions or violate SQLite ownership | Keep handlers thin, use one writer, reconstruct reads from persistence, and classify lifecycle errors explicitly |
| Evaluation | A final score cannot be reconstructed from immutable attempts and runtime evidence | Version scorer/trace/protocol contracts and join exact durable authorities |
| Environment | Network, database, model, or credentials are treated as product evidence | Preflight first; classify environment failures separately; never count them as passes |
| Agent workflow | Repeated local patches hide an underspecified boundary | Stop before a third correction, return to the ruler checkpoint, and preserve intermediate work |

## 1. Governance and specification alignment

### 1.1 Normative text drifted across the spec and `AGENTS.md`

- **Observed:** checkpoint steps, closeout requirements, fixture/oracle triggers,
  and semantic/oracle failure routing were stated more than once with different
  strength. An idle-in-transaction example also used statement count rather
  than whether a transaction remains open across client round trips.
- **Risk:** agents could follow a stricter hidden obligation or use an incorrect
  applicability example while believing they followed the spec.
- **Resolution:** consolidated normative delivery rules in the spec, narrowed
  `AGENTS.md` to operational differences, corrected checkpoint artifact scope,
  and unified failure routing.
- **Prevention:** every new guide rule must replace or narrow an existing rule;
  code evidence that makes the spec obsolete requires a spec amendment.
- **Status:** Resolved.
- **Evidence:** `aea47b2`, `71d6b49`, `2b9b0f2`, `7a95966`.

### 1.2 Governance rewarded narrow patches but not convergence

- **Observed:** contract-significant lifecycle, evidence, result assembly, and
  execution logic accumulated in multiple gate-named modules.
- **Risk:** a later API or evaluator could externalize duplicated behavior and
  make convergence compatibility-sensitive.
- **Resolution:** added structural-debt accounting at gate closeout and a
  characterization-first convergence rule.
- **Prevention:** schedule convergence before a third consumer; keep the
  behavior-preserving refactor separate from feature work.
- **Status:** Owed to post-G7 convergence for historical G3/G4/G5 naming and
  compatibility wrappers.

## 2. Ruler and checkpoint quality

### 2.1 A red test did not always prove the intended contract

- **Observed:** early checkpoints could fail during import, fixture setup, or
  against a fake collaborator rather than at the contract assertion.
- **Risk:** production could be authorized against a ruler that never reached
  the real boundary.
- **Resolution:** required intended-reason failures and production-shape
  witnesses. Static assertions are allowed only when a deliberate red test
  would not represent the contract.
- **Prevention:** report the exact failure code and distinguish setup,
  collection, environment, and product failures.
- **Status:** Resolved as a governance rule.

### 2.2 G7b-P0d membership fixtures did not express their claims

- **Observed:** the duplicate-ID witness replaced the original case and
  therefore contained two distinct IDs. The symlink witness called
  `symlink_to()` before creating its parent directory. A later duplicate-path
  witness repeated the same Python dictionary object, so PyYAML serialized it
  with an anchor and alias before the membership boundary was reached.
- **Risk:** production would need an invented global ID rule, while the symlink
  safety path was never called.
- **Resolution:** changed the synthetic duplicate to share the declared ID and
  created the symlink parent before the call. The corrected checkpoint exposed
  a real 257-case resource-limit classification defect. The duplicate-path
  fixture now uses two independent mappings, so its serialized YAML represents
  duplicate membership rather than alias syntax.
- **Prevention:** inspect the concrete fixture graph, not only the expected
  exception; prove the collaborator is reached.
- **Status:** Resolved. Fixture corrections landed at `95b2dc8` and `373d266`;
  the strict manifest loader landed at `c9f0f93`.
- **Evidence:** `fa98a42`, `95b2dc8`, `373d266`, `c9f0f93`.

### 2.3 P0e baseline rulers initially proved test doubles instead of the real path

- **Observed:** the first baseline checkpoint used custom string and dictionary
  compiler/executor shapes, split the event sequence across independent lists,
  discarded server bindings during materialization, and scored database rows
  without consuming the direct-synthesis output. It also used an incorrect
  monetary-cost expectation and did not establish who opened the durable model
  attempt.
- **Risk:** an implementation could pass while remaining incompatible with the
  production semantic engine and executor, or report a correct baseline when
  its synthesized answer was wrong. Caller-provided identity could appear
  reconciled without an independent durable authority.
- **Resolution:** after repeated corrections exposed the same witness boundary,
  root review took over the ruler design. The final checkpoint uses real
  proposal, draft, compiled-query, execution-result, reviewed-context, and
  typed-parameter shapes; one shared ordered event log; a harness-opened P0b
  attempt; exact cost accounting; and deterministic scoring of synthesis output
  against owner-reviewed facts.
- **Prevention:** a baseline production-shape witness must follow the same port
  types as the real collaborators, prove object and value flow, and score the
  externally observed answer rather than a more convenient intermediate value.
- **Status:** Resolved in the P0e checkpoint and implementation.
- **Evidence:** `a306808`, `5507b8c`, `5b6878a`.

### 2.4 P0e rulers contained contradictory shared-state and validation ownership

- **Observed:** one failure ruler intentionally shared a single event list among
  all collaborators but later asserted that the model's reference contained
  only model events. Another constructed an invalid answerable manifest with no
  tasks and expected the baseline runner to classify it, even though the strict
  P0d manifest contract correctly rejected it during request validation. A raw
  string enum mutation also emitted a serializer warning.
- **Risk:** production would have needed to mutate test state or weaken an
  upstream owner-approved contract to make the suite pass. The first apparent
  failure also hid later contradictions in the same test function.
- **Resolution:** preserved the production implementation, amended only the
  rulers, asserted shared-list identity while retaining the complete ordered
  sequence, removed the redundant empty-task case already owned by P0d, and used
  the typed evaluated-path enum. The corrected focused suite passed 34 cases
  without warnings before implementation resumed.
- **Prevention:** fixture ownership must agree with its assertions, and an
  invalid input already rejected by a stricter upstream contract must not be
  duplicated as a downstream behavior ruler.
- **Status:** Resolved.
- **Evidence:** `5507b8c`, `5b6878a`.

### 2.5 P4c entrypoint rulers initially checked shapes without proving seams

- **Observed:** the first P4c checkpoint covered five shallow cases. Its first
  correction still required a new public oracle-driver property while omitting
  fixed connection authority, provider retry configuration, failed-serialization
  cleanup, and CLI failure redaction.
- **Risk:** production could satisfy the tests while constructing the wrong
  database role or provider policy, leaking an unsafe failure, or widening a
  collaborator solely for test inspection.
- **Resolution:** after the repeated incomplete correction, root stopped local
  patching and reconverged the test-only checkpoint around observable injected
  dependencies and subprocess output before production implementation resumed.
- **Prevention:** composition rulers must capture constructor inputs at existing
  seams, prove zero external I/O during construction, and exercise both success
  and sanitized failure behavior at the real public boundary.
- **Status:** Resolved in P4c.
- **Evidence:** `9b3fadc`, `c3c897f`, `e9525d6`.

## 3. Semantic authority, verification, and privacy

### 3.1 AST references were mistaken for semantic correctness

- **Observed:** a compiled query could contain reviewed object references
  without proving that it composed filters, grain, aggregation, and joins
  according to the reviewed business definition.
- **Risk:** structurally plausible SQL could produce a false verified claim.
- **Resolution:** separated compiler-resolved/AST provenance from semantic
  authority and added exact structural semantic attestation against an
  owner-reviewed contract revision.
- **Prevention:** output columns, AST references, caller metadata, and model
  assertions never establish semantic attestation by themselves.
- **Status:** Resolved.
- **Evidence:** `d3d96a4`, `7a7544d`, `0ebd217`, `6d8a9a9`, `c1fed6e`.

### 3.2 Model-authored claims crossed the verification boundary

- **Observed:** three rapid G3 fixes closed different surfaces through which
  unattested model semantics could influence verified output.
- **Risk:** `false_verified_count` could become non-zero even though individual
  gates appeared valid.
- **Resolution:** redesigned the boundary around typed semantic attestation and
  made verification derive only from trusted validators and evidence.
- **Prevention:** two corrections exposing the same invariant trigger a return
  to the owning checkpoint before a third patch.
- **Status:** Resolved.
- **Evidence:** `172970e`, `87299e8`, `0d7243b`, `0684ae9`, `6dc9ded`.

### 3.3 Executed cursor shape was not guaranteed to match reviewed output

- **Observed:** semantically reviewed SQL could still return a cursor schema
  different from the approved output contract.
- **Risk:** validators, artifacts, or claims could interpret columns under the
  wrong names, order, or types.
- **Resolution:** verify the ordered executed cursor schema before downstream
  validation, artifact construction, or claims.
- **Prevention:** persist the successful query record even if output-schema
  verification blocks later claims; keep public failure details sanitized.
- **Status:** Resolved.
- **Evidence:** `f74af08`, `51f5926`, `9353bc4`, `c9cea2c`.

### 3.4 Parameter values could have become model-owned

- **Observed:** an authoring interface could mix semantic structure with
  execution values.
- **Risk:** prompt injection or model output could alter store, tenant, time, or
  sensitive filters.
- **Resolution:** model proposals remain value-free; the server owns typed
  bindings and validates exact placeholder identity before materialization.
- **Prevention:** never put bindings, rows, expected facts, or credentials in
  model-visible context.
- **Status:** Resolved.
- **Evidence:** `d272054`, `f992f47`, `ee81e4d`, `7e37c08`.

## 4. Trusted execution architecture

### 4.1 A port passed with fakes but lacked real collaborator data

- **Observed:** `TrustedStepPort` passed fake-based rulers even though a real G3
  collaborator needed run context, bindings, reviewed metadata, projection,
  and semantic contract identity not present in the port shape.
- **Risk:** G6 could have wrapped an unusable port in an HTTP API and frozen the
  wrong wire contract.
- **Resolution:** introduced production-shape witnesses and routed execution
  through a trusted facade, request session, and task-local execution scope.
- **Prevention:** test doubles do not establish port sufficiency; every new
  trusted port must show that real collaborator data crosses the interface.
- **Status:** Resolved.
- **Evidence:** `4a30be6` through `025fd97`, then `803cb18` through `ee7a6ec`.

### 4.2 Evidence ledger access was too broad

- **Observed:** inner Fixed/G4/G5 runners could receive broad ledger access,
  duplicating task identity and lifecycle decisions.
- **Risk:** inner runners could mutate evidence outside their task or create
  incompatible lifecycle records.
- **Resolution:** made `RequestSession` the ledger owner and routed task-local
  step/evidence operations through `TaskExecutionScopePort`.
- **Prevention:** inner execution receives the narrowest capability required;
  completed evidence is immutable.
- **Status:** Resolved.
- **Evidence:** `67fa94f`, `6b692df`, `780d610`, `1268e71`.

### 4.3 PostgreSQL integration witnesses retained a retired ledger shape

- **Observed:** the offline suite remained green because PostgreSQL tests were
  skipped, while three database-backed G2, G3, and G4 witnesses still passed
  `ledger` directly into inner runners after G6a moved lifecycle and evidence
  ownership to request sessions and task scopes.
- **Risk:** a clean offline gate could hide that the production-shape database
  proof no longer constructed the accepted execution path.
- **Resolution:** updated only the stale witnesses to use
  `StandaloneFixedQueryRunner`, `StandaloneG3SingleTaskRunner`, and
  `StandaloneG4RelationRunner`; no compatibility shim was added to production.
- **Prevention:** run the authorized PostgreSQL-backed gate at release-asset
  closeout and treat skipped integration tests as missing, not passing,
  evidence.
- **Status:** Resolved.
- **Evidence:** `6086904`; final PostgreSQL gate: 829 passed.

## 5. Lifecycle, budgets, and usage

### 5.1 Declared wall-clock states originally had no reachable enforcement path

- **Observed:** task/request wall-clock budgets and timed-out/cancelled terminal
  states existed before a runtime owner could reach them.
- **Risk:** declared limits could be presented as assurance without enforcement.
- **Resolution:** added an applicability registry and explicit request/task
  lifecycle owners, active-query cancellation, and persistent terminal state.
- **Prevention:** every budget and state is enforced, delegated to a named
  owner, or explicitly not applicable; no unknown/deferred entry may remain
  when its owning gate is active.
- **Status:** Resolved for declared production horizons.
- **Evidence:** `803cb18` through `b1d8251`.

### 5.2 Request and task budgets were conflated

- **Observed:** `G3SingleTaskRunner` required
  `max_tasks_per_request == 1`, although request decomposition and orchestration
  own request task count.
- **Risk:** a legal multi-answerable request failed inside a task-local runner.
- **Resolution:** kept task-count enforcement in preparation/orchestration and
  removed only the single-task runner's request-level guard.
- **Prevention:** record an explicit owner for each budget horizon.
- **Status:** Resolved.
- **Evidence:** `f1b995f`, `aa9433f`.

### 5.3 Preparation usage was easy to lose or double count

- **Observed:** decomposition, planning, authoring, repair, and execution happen
  at different lifecycle scopes; early checkpoints did not prove a durable
  handoff for all usage.
- **Risk:** latency, token, and cost evidence could be incomplete or attributed
  to the wrong task.
- **Resolution:** split attempt accounting, durable preparation handoff, and
  runtime lifecycle into ordered rulers; seed preparation usage once and add
  task-local planning/authoring usage later.
- **Prevention:** usage ownership follows request preparation, task planning,
  and statement attempt boundaries explicitly.
- **Status:** Resolved.
- **Evidence:** `8df238c` through `78fdbe2`, plus `8429ba9` through `461d28d`.

### 5.4 Long-lived lifecycle dictionaries are not yet evicted

- **Observed:** `WallClockLifecycle` and `BudgetedExecutionUsageOwner` retain
  per-request/task dictionaries after completion.
- **Risk:** a long-running service can accumulate memory even though bounded G7
  test runs finish.
- **Resolution:** not implemented yet; schedule characterized eviction before a
  long-running soak or deployment claim.
- **Prevention:** lifecycle closeout must remove completed in-memory ownership
  records without deleting durable evidence.
- **Status:** Owed to the G6a/G6b-owned correction before long-running live use.

## 6. Persistence, API, and concurrency

### 6.1 API admission and execution handoff were initially transient

- **Observed:** process-local state could accept a request without a durable,
  reconstructable handoff.
- **Risk:** restart could lose request identity, idempotency, status, or task
  causes while the public API appeared successful.
- **Resolution:** added SQLite persistence, digest-only idempotency mapping,
  single-writer ownership, startup abandonment, cancellation persistence, and
  typed public error mapping.
- **Prevention:** acknowledge admission only after durable reservation; rebuild
  reads from persistence; abandon rather than falsely resume uncertain work.
- **Status:** Resolved for the local/trusted POC.
- **Evidence:** `e49b964` through `4d08977`.

### 6.2 Public claims could be projected before complete durable evidence

- **Observed:** request/task status, claim summaries, exact usage, and evidence
  were initially available in different transient shapes.
- **Risk:** a completed or verified response could be published before its
  supporting terminal record was reconstructable.
- **Resolution:** persisted terminal task results separately, preserved task
  order, derived claim summaries and exact usage from durable rows, and rejected
  premature verification.
- **Prevention:** public reads are projections of immutable durable evidence,
  not in-memory runner objects.
- **Status:** Resolved.
- **Evidence:** `e56db42` through `121b025`, `3836251`, `57b64c6`.

### 6.3 FastAPI lifecycle hooks became deprecated

- **Observed:** the pinned FastAPI version warned about `on_event` startup and
  shutdown registration.
- **Risk:** future dependency upgrades could remove the behavior.
- **Resolution:** migrated application lifecycle registration to lifespan.
- **Prevention:** record dependency deprecations as structural debt with an
  owning gate rather than ignoring warnings.
- **Status:** Resolved.
- **Evidence:** `e4e061e`.

## 7. Evaluation and release evidence

### 7.1 A single end-to-end score could not explain failures

- **Observed:** request resolution, task graph, semantic grounding, planning,
  SQL safety, response evidence, reliability, and budget failures have different
  owners.
- **Risk:** an aggregate percentage could hide safety or false-verification
  regressions behind easy cases.
- **Resolution:** introduced versioned layer scores, BVTS, explicit safety
  counters, attempt selection, baseline comparison, and cost/latency evidence.
- **Prevention:** never report incompatible scorer/protocol revisions as a
  trend; safety counters remain separate hard gates.
- **Status:** Release scoring foundation resolved; live release claim not yet run.
- **Evidence:** `fbaa2dd` through `c856b9d`.

### 7.2 Model usage was not durably attributable to one attempt

- **Observed:** provider calls could finish or fail independently of runtime
  evidence, and aggregate SDK usage did not prove exact attempt ownership.
- **Risk:** retry, replacement, environment failure, latency, or cost could be
  counted incorrectly.
- **Resolution:** added an append-only attempt journal and accounting client with
  immutable finalization, exact trial/attempt identity, and pinned pricing.
- **Prevention:** the attempt journal is authoritative for model usage; runtime
  evidence cannot invent it.
- **Status:** Resolved.
- **Evidence:** `982549f`, `565770b`.

### 7.3 Safe trace emission had two durable authorities

- **Observed:** model usage belongs to the evaluation journal while tasks,
  queries, evidence, and runtime usage belong to the G6 ledger.
- **Risk:** joining by partial identity or accepting extra/missing evidence could
  produce a plausible but unreconstructable trace.
- **Resolution:** implemented exact identity, query-record, evidence-set, and
  usage reconciliation; environment attempts never open the execution database.
- **Prevention:** reject missing, extra, duplicate, cross-task, or divergent
  durable evidence. Read SQLite in WAL-aware read-only mode.
- **Status:** Resolved.
- **Evidence:** `67876ee`, `b31c2f4`, `16f68fe`, `25d6f25`.

### 7.4 SQLite immutable reads failed with a live WAL writer

- **Observed:** `mode=ro&immutable=1` could not see the live WAL schema while a
  writer remained open.
- **Risk:** evaluation could classify an inspectable terminal run as missing or
  invalid.
- **Resolution:** use ordinary read-only mode when a WAL file exists and
  immutable read-only mode only when no WAL is present; always set
  `PRAGMA query_only=ON`.
- **Prevention:** include a real live-WAL witness and assert no durable row is
  mutated by trace emission.
- **Status:** Resolved in P0c.

### 7.5 Release manifests require exact identity and evaluator-only facts

- **Observed:** gate-scoped G2/G3 YAML files do not form a versioned release
  case set, and a case ID alone is insufficient to score a structured fact.
- **Risk:** case membership, oracle authority, mutation applicability, or fact
  correctness could drift without changing recorded attempt identity.
- **Resolution:** P0d freezes explicit digest-pinned membership, scoreable fact
  expectations, owner-approved oracle/world/mutation identity, DAG and budgets,
  and sanitized YAML/path/resource rejection.
- **Prevention:** no directory discovery; case-set digest is set-order
  independent but changes with identity, revision, membership, or pinned
  artifact digest.
- **Status:** Resolved for the manifest loader and real 30-case retail_v1
  release pack. Live model attempts and final release scoring remain later G7
  work.
- **Evidence:** `fa98a42`, `95b2dc8`, `373d266`, `c9f0f93`.

### 7.6 A mutation driver could rewrite the authority used to assess itself

- **Observed:** the first P2b contract let the driver report the expected
  mutation denominator. After that was moved into the digest-pinned reviewed
  asset, the executor still passed its canonical mutable case and oracle asset
  objects directly to the driver and reconciled against those same objects
  after the call. A collaborator could therefore shrink the mutation set or
  rewrite case, oracle, mutation-set, or world identity and return an
  observation matching the rewritten values.
- **Risk:** mutation bypass or oracle drift could be recorded as passing
  evidence even though the denominator and identity no longer matched the
  owner-reviewed release pack.
- **Resolution:** first made the reviewed mutation manifest the independent
  denominator authority, then replaced the denominator-only correction with a
  complete authority-aliasing checkpoint. The executor now snapshots canonical
  pre-call authority, gives the driver separate copies, reconciles only against
  the canonical snapshot, and leaves the loaded asset pack unchanged.
- **Prevention:** a collaborator that executes an evaluation may observe
  reviewed authority but cannot own or mutate the identity and denominator used
  to assess its output. Production-shape rulers cover case, oracle,
  mutation-set, world, and mutation-membership rewrites.
- **Status:** Resolved in G7b-P2b.
- **Evidence:** `0f9aee2`, `543a22b`, `54f6076`, `4f013ee`, `dc242b0`.

### 7.7 The first real release candidate encoded contradictory case claims

- **Observed:** candidate cases used unrecognized coverage tags, accessed a
  convenience revision property the loader does not expose, undercounted
  multi-task lifecycle budgets, and changed raw digest identity when newline
  normalization changed. Some labels also described capabilities the current
  request path does not execute.
- **Risk:** the pack could appear complete while its task graph, budget,
  coverage, or digest evidence could not be reproduced by the production
  harness.
- **Resolution:** corrected the candidate rulers before admission, made task and
  request budget ownership explicit, used loaded manifest authority directly,
  and admitted a 30-case v2 pack only after the complete asset chain passed.
- **Prevention:** derive candidate identity from loaded artifacts, require every
  case to belong to recognized coverage, and validate multi-task cases against
  the real lifecycle budget owner before approval.
- **Status:** Resolved for the P3 asset pack.
- **Evidence:** `f118383`, `d653b7d`, `1932c46`, `d6bbf63`, `9f8fb21`,
  `9e3b702`, `d6f9a5f`.

### 7.8 Admission and execution disagreed on executable asset encoding

- **Observed:** release admission accepted YAML world and mutation artifacts,
  while the concrete PostgreSQL driver deliberately consumed strict JSON. The
  unit driver rulers used generated JSON, so both surfaces passed independently;
  the first real-pack execution rejected all 15 answerable cases with the
  sanitized asset-invalid code.
- **Risk:** a digest-pinned, owner-approved pack could still be unusable by the
  release executor, and the generic executor failure could obscure that the
  defect preceded SQL execution.
- **Resolution:** added an independent strict-JSON production-shape ruler, then
  converted the four worlds and fifteen mutation manifests without changing
  parsed content. The v3 pack and v2 oracle registry refresh the complete raw
  digest chain.
- **Prevention:** every admitted executable asset format must have one exact
  consumer compatibility witness; admission and execution cannot be validated
  only in isolation.
- **Status:** Resolved in P3. All 15 applicable cases ran across four worlds;
  all 40 reviewed mutants were detected and mutation bypass was zero.
- **Evidence:** `274023c`, `33d41c2`.

### 7.9 The unvalidated baseline returned result rows to the model

- **Observed:** the baseline used one model call to author SQL and a second model
  call to synthesize executed rows. The production LiteLLM adapter did not expose
  that synthesis operation, and the row-bearing context contradicted the
  repository rule that model-visible evaluation context is value-free.
- **Risk:** private or sensitive result values could cross the model boundary,
  baseline accuracy could include a second source of model hallucination, and
  attempt cost evidence would describe an implementation the production adapter
  could not execute.
- **Resolution:** amended the normative baseline to one SQL-authoring call,
  deterministic local fact scoring, and no row-bearing model context. Evaluation
  protocol v3 and retail release pack v4 give the changed sampling and cost
  contract new identities while preserving historical v2 evidence as readable.
- **Prevention:** baseline rulers prohibit model synthesis, require exactly one
  journaled model attempt, and admit protocol v3 only with scorer v4 and trace v3.
- **Status:** Resolved before concrete live-attempt composition.
- **Evidence:** `831a1f4`, `da7ec9f`, `8188ecb`.

### 7.10 Attempt identity and accounting crossed incomplete boundaries

- **Observed:** the first production-shaped runtime omitted fixture revision
  propagation, the attempt journal used one SQLite connection from more than one
  caller thread without serialized ownership, and early operation-audit rulers
  either stopped at a static shape or gave the baseline an oracle that could not
  represent its one-call execution.
- **Risk:** a trace could join the wrong fixture context, lose or reorder model
  usage, or claim an inspected operation history that the real runner never
  finalized.
- **Resolution:** propagated fixture identity through the complete runtime
  context, serialized the cross-thread journal handoff, and replaced the partial
  audit rulers with runner-finalized typed evidence for both evaluated paths.
- **Prevention:** every revision and usage owner must cross the same production
  interface used at runtime; a static port shape or an independently convenient
  test oracle is not a production-shape witness.
- **Status:** Resolved before final release composition.
- **Evidence:** `d7a50b7`, `d1cf9c5`, `31b7190`, `0784106`, `a3fde73`,
  `da5d886`, `e4c5322`, `af92412`, `573d868`, `0f88052`.

### 7.11 Baseline components existed before their lifecycle converged

- **Observed:** reviewed authoring, binding materialization, and deterministic
  scoring passed separately before one production factory could compose them.
  The first factory rulers also reused a closed runtime, failed to observe Wren
  construction on negative paths, and created a nested temporary SQLite path
  without its parent directory.
- **Risk:** individually correct components could remain unusable as one
  attempt, or a checkpoint could fail during setup rather than at the lifecycle
  boundary it claimed to prove.
- **Resolution:** split D1 into authoring, materialization, scoring, close
  lifecycle, and concrete factory checkpoints. After repeated fixture defects,
  the checkpoint was redesigned before the reviewed single-use runtime factory
  was implemented.
- **Prevention:** lifecycle rulers must use fresh runtimes, observe the real
  resource constructor, and create complete fixture preconditions before
  asserting a failure boundary.
- **Status:** Resolved in P4b-D1.
- **Evidence:** `5dca8c3`, `4c7ac36`, `f322c9f`, `c972931`, `9e0e465`,
  `81b68fb`, `9e32cba`, `664b550`, `976e7e0`, `d642ff6`, `d3e622e`,
  `5897ec8`, `8ce7893`, `ed3f009`.

### 7.12 Per-attempt evidence needed one retained path authority

- **Observed:** the Grepbit factory initially rebuilt its execution-state path
  authority for every attempt, so a post-construction root replacement could be
  accepted as a new root. Later evidence-routing rulers mislabeled
  environment-finalized journals as completed attempts and called a borrowed
  assessment helper with the wrong object type.
- **Risk:** assessment and trace reconstruction could read a different SQLite
  file from the one the trusted attempt wrote, while red tests appeared to prove
  isolation without reaching the real durable boundary.
- **Resolution:** retained root device/inode identity, routed completed and
  environment attempts from finalized journal outcome, and used one explicitly
  injected `AttemptExecutionStatePaths` across the Grepbit factory, assessment,
  and trace emitter. Root review took over the checkpoint after the repeated
  fixture failures.
- **Prevention:** attempt identity selects exactly one confined database;
  completed readers use `read_path`, environment traces use non-mutating
  `candidate_path`, and no evidence reader reserves state.
- **Status:** Resolved in P4b-D2a.
- **Evidence:** `4c59ba4`, `ebbd13f`, `235f613`, `2c036ac`, `50de956`,
  `d036559`, `a145e28`, `7ccf09a`, `d59c707`, `aacf353`, `1f5c9b6`.

### 7.13 Final composition exposed an implicit private-authority dependency

- **Observed:** two D2b checkpoint revisions still omitted the real graph,
  exact request derivation, failure-close behavior, and store lifecycle. Once
  those rulers were added, they proved the composer could not share the
  Grepbit factory's private path authority without reading private state.
- **Risk:** a nominal composition root could instantiate all classes while
  retaining two independent identity authorities or leaking SQLite handles on
  failure.
- **Resolution:** stopped production work, amended the factory construction
  contract to inject the shared authority, and built one single-use release
  runtime that runs oracle/mutation evidence before the harness and closes all
  local authorities in reverse order on every terminal path. Root took over
  after repeated incomplete worker returns and preserved the partial work.
- **Prevention:** final composition rulers assert real object identity across
  producers and consumers, zero external work during construction, exact owned
  persistent files, and idempotent all-close behavior.
- **Status:** Resolved in P4b-D2b. The broad offline closeout passed with 1,018
  tests and 16 explicitly environment-gated skips.
- **Evidence:** `084dcb5`, `94a8ff6`, `afe8a20`, `aacf353`, `1f5c9b6`,
  `d8f133d`.

### 7.14 In-process CLI tests missed import-time output contamination

- **Observed:** `main()` emitted sanitized JSON in process, but a fresh
  `python -m evals.local_release` invocation first emitted an unrelated Pydantic
  warning to stderr during dependency import.
- **Risk:** automation could no longer treat the local release CLI as JSON-only,
  and internal file paths or framework diagnostics could escape the intended
  sanitized boundary.
- **Resolution:** added a subprocess ruler that requires empty stderr and exact
  JSON, then isolated only the known import-time warning while leaving normal
  test warnings visible.
- **Prevention:** CLI output contracts require a fresh-process witness; direct
  function calls do not establish import-time or interpreter-exit behavior.
- **Status:** Resolved in P4c; the broad offline gate passed with 1,032 tests and
  16 explicitly PostgreSQL-gated skips.
- **Evidence:** `07d37cb`, `7414fc4`.

### 7.15 Sourcing `.env` did not export the credential to the child process

- **Observed:** the first post-P4d live invocation sourced `.env` without
  enabling automatic export. The release runtime durably recorded two
  `pre_execution_environment_failure` attempts with
  `credential_unavailable`, zero model calls, and no product execution.
- **Risk:** an operator-side shell mistake can consume release slots or be
  mistaken for a provider or product failure even though no live call occurred.
- **Resolution:** preserved the failed runtime root, performed an opaque
  presence-only preflight, and used `set -a` only around `.env` sourcing for the
  next fresh-process invocation. No credential value was read or emitted.
- **Prevention:** live-run instructions must distinguish shell assignment from
  exported environment and must prove credential presence in the child-process
  environment without printing the value.
- **Status:** Resolved operationally; no model-call budget was consumed.

### 7.16 Gold-coupled decomposition audit aborted a valid product-failure score

- **Observed:** after the corrected live gate completed all three
  `na_budget_tasks` Grepbit trials, `na_clarify_a_to_b` produced a completed
  model call but the evaluation audit compared the candidate decomposition with
  reviewed expected tasks before assessment. The mismatch abandoned the request,
  prevented immutable audit persistence, and stopped the whole release run
  instead of producing a layer-2 product failure. The same case also declares a
  relation dependency on a non-answerable task, although the production
  resolution contract forbids execution dependencies on non-answerable tasks.
- **Risk:** only gold-compatible candidates can reach scoring, biasing release
  evidence upward; an unreachable oracle can be reported as a model failure; and
  one ordinary candidate miss can prevent complete-set coverage evidence.
- **Resolution:** stopped the live gate without retrying and retained the
  sanitized runtime root. The P4e production contract now records observed
  decomposition independently, compares it only during assessment, retains
  ordinary mismatches as scoreable product failures, and defines v6/v4 typed
  A-to-B handoff and admission requirements. Final review restored the v5
  task-scoped fact and pre-task budget-terminal semantics that v6 did not
  change, and kept pre-execution environment evidence as a base trace variant.
- **Prevention:** production-shape eval rulers must include a deliberately wrong
  but schema-valid candidate and prove that it is retained as a product failure,
  not rejected by the harness or used to influence execution.
- **Status:** Production-contract resolution, including the final compatibility
  repair, is complete. Reviewed v6/v4 assets and a separately authorized live
  gate remain pending; this does not claim a G7 release pass.

### 7.17 Cross-task ResultRef adapter blocks the reviewed P4e asset candidate

- **Observed:** the review-pending v6/v4 retail candidate requires distinct
  producer and consumer task IDs with a typed `qualifying_order_months`
  handoff. The current G4 request runner supports one task with two steps, and
  the sequential request orchestration does not pass a prior task artifact to
  the next task runner.
- **Risk:** approving or migrating the candidate assets before that adapter
  exists would claim reconstructable A-to-B evidence without a production path
  that can produce it.
- **Resolution:** retained the real v5/v3 retail pack unchanged and recorded
  the candidate as `review_pending`, `oracle_execution_status: not_run`, and
  `production_shape_status: blocked` with reason
  `cross_task_result_ref_adapter_missing`.
- **Prevention:** a separate architecture ruler and approved implementation
  must establish typed cross-task ResultRef transport before any owner approval,
  asset migration, PostgreSQL oracle run, or G7 release claim.
- **Accepted target checkpoint:** the next boundary is one server-owned,
  adjacent producer/consumer relation-pair adapter. It keeps the existing G4
  compile-to-inline-CTE-to-policy-to-single-repeatable-read-session path, opens
  two durable task scopes, and reconstructs the v6/v4 handoff from a producer
  artifact plus a value-free consumer plan. It may not materialize relation rows
  into prompts, generated `IN` lists, or a second executor.
- **Witness correction:** the adapter ruler now requires a real SQLite-ledger
  request session, orchestrator, G4 runner, composer, and policy to produce the
  handoff; helper-only routing or failure-policy stubs are insufficient.
- **Checkpoint redesign:** repeated future-gated corrections exposed skipped-test
  blind spots (a contradictory execution-count assertion and Pydantic-only
  mutation assumptions for frozen dataclasses). The boundary returned to ruler
  redesign before production; future witnesses now use real public value types
  and assert task-local, as well as aggregate, execution usage.
- **Namespace correction:** pre-implementation review found a nonexistent
  `SqliteLedger.list_tasks` assertion and an incompatibility between raw
  hyphenated task IDs and SQL-safe identifiers. The ruler now reads `task_runs`
  directly and freezes an underscore namespace derived from each task ID.
- **Lifecycle regression checkpoint:** root review requires persisted semantic
  validation evidence to close with its owning blocked task, and a cooperative
  cancellation after producer completion to avoid creating any consumer plan or
  validation evidence. This checkpoint precedes acceptance of the adapter.
- **Typed port correction:** the frozen G6b constructor-hint ruler initially
  rejected the required typed relation-adapter port. It is amended to require
  that exact optional port rather than preserving an untyped production escape.
- **P4f runtime authority checkpoint:** the review-pending v2 runtime profile
  and semantic-contract pack add the sole adjacent cross-task relation pair.
  Historical v1 remains readable; material and evaluation composition must not
  admit v2 until its single-session adapter and shared cancellation authority
  are wired through the normal G6b writer path.
- **P4f completion correction:** the original material-only ruler could hide
  missing API composition and runner reconciliation behind its first absent
  field. The corrected checkpoint independently freezes v2 registry inheritance,
  five value-free decomposition capabilities versus three G3 definitions,
  typed relation-adapter and shared-active-query ports, and the relation-case
  reconciliation boundary. Candidate v2 registry entries deliberately permit
  two fixed query contracts for one release case only after an approved/verified
  promotion; the review-pending candidate itself is not executable authority.
- **P4f redesign correction:** `30d2be5` incorrectly required hypothetical
  v2 material from the historical v1 pack and did not execute a factory-shape
  witness. The replacement ruler keeps v1 at three decomposition capabilities,
  three G3 definitions, and no relation authority; it derives promoted v2
  authority in a temporary repository, separates v2 profile, registry,
  material, composition, and runner gaps, and makes profile-owned model context
  the sole decomposition-catalog authority. The full external-seam factory
  path remains blocked on those separately visible v2 boundaries.
- **P4f root-takeover correction:** final review of `1c694ef` found three
  contradictions: v1 was required to lack a field that v2 must add, the
  additive v2 pack duplicated its inherited base contracts, and a constant
  registry monkeypatch could not prove that composition created only one
  cancellation authority. Root takeover changed the v1 assertion to an empty
  relation-pair value, kept only the two additive v2 contracts, and made the
  full factory witness count registry construction while checking both real
  PostgreSQL executor types.
- **P4f production completion:** the promoted runtime now admits the additive
  verified semantic pack, exposes five value-free decomposition capabilities
  while retaining three G3 definitions, constructs one reviewed relation-pair
  definition, and shares one active-query registry across the G3 executor, G4
  repeatable-read executor, cancellation service, and orchestrator.
- **P4g aggregation correction:** the first A-to-B oracle selected individual
  cancelled orders while the reviewed runtime contract grouped by
  customer-month. The original worlds had only one qualifying cancelled row,
  so execution could not distinguish the mismatch. The corrected v8/v7 pack
  adds a second qualifying row, expects the aggregate, and includes an explicit
  missing-consumer-aggregation mutant.
- **Promotion replay correction:** checkpoint helpers initially appended the
  A-to-B coverage and oracle entry to the already promoted pack, producing
  duplicate identities on replay. The helpers are now idempotent, and the v1
  compatibility witness constructs an explicit historical profile instead of
  assuming that the current real pack remains v1 forever.
- **Promotion compatibility checkpoint:** the accepted v8/v7 promotion left
  historical G7 rulers coupled to the v6/v5 candidate identity, the v5
  expected task graph, and v1-only runtime budget/material shapes. The replay
  correction now distinguishes the historical candidate from current authority,
  derives scorer-v6 audit digests from the observed proposal, and explicitly
  validates v2 relation-pair materials and typed A-to-B budget controls. The
  `p1_rank_truncated` scorer failure was a stale test execution column order,
  not a production scoring defect. Lifecycle stubs now provide a valid v6
  trace shape without claiming a second execution path.
- **Performance sample admission checkpoint:** fixed three-trial release
  selection gives the promoted v8/v7 pack 42 direct-single-task executions but
  only 6 multi-step executions. A review-pending v9/v8/v5 candidate adds eight
  independent, Grepbit-only multi-task cases to reach ten multi-step cases and
  30 selected executions. Production admission must reject an enabled category
  below 30; this checkpoint does not promote assets or claim a release pass.
- **P4h checkpoint redesign:** two worker revisions froze only a symbol and then
  case-level digests; neither proved deficient loader rejection, sufficient-pack
  admission, or registry/case-set/pack byte closure, and their helpers were not
  replayable after promotion. The repeated-correction stop condition triggered
  root takeover. The redesigned ruler constructs both complete temporary packs,
  pins all affected artifact and identity digests, uses single-task sources so
  each new task owns one nonduplicated fact set, and keeps future promotion
  replayable without weakening the 30-sample policy. The promoted pack advances
  to `release-asset-pack-v3` with an explicit capacity policy so historical v2
  packs remain readable rather than being retroactively rejected.
- **Performance checkpoint correction:** the first P4h ruler only proved a
  missing symbol. The corrected contract pins the typed capacity policy, its
  loader integration, review-pending v9/v8/v5 identity, and canonical bytes
  for eight explicit natural-language two-task cases. Future promotion must
  validate the complete temporary-pack closure rather than treating labels or
  duplicated identities as performance samples.
- **Identity correction sequence:** the first candidate revision used placeholder
  case digests; the first correction recomputed canonical logical digests but
  still did not prove the raw artifact-byte identities pinned by the release
  loader. The repaired checkpoint defines one `canonical-json-v1` promotion
  serializer and admits a complete temporary hypothetical pack before treating
  a target digest as reviewable.
- **P4h resolution:** the owner-approved v9/v8/v5 promotion now uses
  `release-asset-pack-v3` and its admitted
  `g7-performance-sample-capacity-v1` policy. The 39-case pack has fixed
  three-trial capacity of 42 direct-single-task and 30 multi-step executions;
  historical v8/v7/v4 v2 descriptors remain readable without this admission
  rule. The PostgreSQL oracle/mutation run and three-trial LiteLLM release gate
  remain pending; no G7 release pass is claimed yet.

### 7.18 The promoted A-to-B oracle had not crossed the production driver

- **Observed:** the first v9 live invocation stopped before model execution with
  `g7b_p2b_driver_failed`. Isolated production-driver reconciliation passed 23
  of 24 reviewed oracle assets; `p0_a_to_b_01` was rejected with
  `g7b_p3_sql_policy_invalid` because the driver did not admit the reviewed
  correlated `EXISTS` relation filter.
- **Risk:** a release pack could pass identity, digest, and synthetic driver
  rulers yet remain impossible to execute through the composed production
  oracle authority. Mapping the failure to a generic local CLI code also hid
  the owning deterministic boundary until isolated pre-model diagnosis.
- **Resolution:** added a ruler that admits a correlated read-only `EXISTS`
  subquery while retaining recursive DML/DDL, table, function, and binding
  checks; added `Exists` to the driver's explicit SQLGlot expression allow-list;
  and reran the exact 24-asset production oracle pack successfully.
- **Prevention:** a promoted release pack must cross the complete composed
  oracle executor against PostgreSQL before the first model call. AST allow-list
  rulers must cover every reviewed production query shape, not only the three
  original single-task templates.
- **Status:** Resolved before the environment-replacement live invocation; no
  product trial or model call occurred in the failed invocation.
- **Evidence:** `g7b_p2b_driver_failed`, `g7b_p3_sql_policy_invalid`, the
  correlated-subquery ruler, and `oracle_pack_completed 24`.

### 7.19 A scoreable candidate mismatch aborted the release harness

- **Observed:** the replacement live invocation produced a schema-valid
  decomposition proposal, then terminated with the sanitized product code
  `request_decomposition_failed` before creating a durable task. The v6
  assessment required every non-budget completed attempt to contain tasks and
  additionally treated a zero-task terminal as an empty observed proposal, so
  the harness failed instead of retaining the product result.
- **Risk:** critical evaluation infrastructure could erase a real candidate
  failure, prevent complete release coverage, and make an unsuccessful product
  behavior indistinguishable from an evaluator defect.
- **Resolution:** scorer-v6/trace-v4 now admits only the exact nonexecuting
  product-terminal shape: failed request, one sanitized decomposition error,
  one accounted decomposition call, no later model or tool operations, and no
  durable task-scoped state. It preserves the independently observed proposal
  digest from the audit authority, emits a blocked public verification, and
  scores the attempt as BVTS false.
- **Prevention:** candidate-observed task-graph evidence is never derived from
  gold expectations or inferred from the absence of durable tasks. Malformed,
  contradictory, or partially executing terminals remain fail-closed.
- **Status:** Resolved before the final fresh-root live evidence run.
- **Evidence:** `request_decomposition_failed`, commits `89e20f7`, `2e545ee`,
  `32ed839`, and `088bf19`; immutable-state replay produced
  `terminal:failed;tasks:0;queries:0;evidence:0` with BVTS false.

### 7.20 A known task-local model failure became generic abandonment

- **Observed:** the next live invocation completed request decomposition, then
  received a sanitized task-local planning failure. The adapter exposed its
  internal transport exception through the generic model port, so
  `G3RequestTaskRunner` could not return a terminal result. The request and its
  running task became `abandoned`; the attempt journal counted two model calls
  while durable request usage retained only the decomposition call.
- **Risk:** a known candidate failure could lose its `TaskResult`, under-report
  runtime usage, and stop the release harness instead of becoming a blocked,
  BVTS-failing product trace. Adding another evaluator-only terminal exception
  would have repeated the P4i producer-boundary defect.
- **Resolution:** introduced provider-neutral, sanitized, attempt-aware planning
  and authoring failure types. The task-local adapter translates only its six
  reviewed failure codes with an exact zero-or-one call count. The request-task
  runner persists planning and PlanGate failures as blocked tasks before step
  creation; an authoring failure blocks the created step and charges planning
  plus the actual authoring attempt. Unexpected programming failures still use
  the existing abandonment owner.
- **Prevention:** known model-operation failures terminate at their application
  producer boundary with durable task state and exact usage. Critical
  evaluation consumes that state; it does not fabricate a result for an
  incomplete producer lifecycle. The second same-boundary correction triggered
  redesign rather than a third assessment patch.
- **Status:** Resolved before the next fresh-root live evidence run.
- **Evidence:** commits `75c36d8`, `ac96e31`, `2c16108`, and `f4877f4`;
  focused regression `143 passed`; full PostgreSQL gate `1138 passed`.

### 7.21 A completed baseline candidate failure left its attempt open

- **Observed:** a live baseline completed one accounted model call but returned
  unusable candidate content. The legacy author boundary raised a generic
  error, left the attempt open, and aborted the release instead of retaining a
  comparable product failure.
- **Risk:** candidate quality failures could be misclassified as evaluator
  failures, discard exact usage and fact totals, and prevent the release from
  comparing Grepbit evidence with a truthful failed baseline.
- **Resolution:** scorer-v7 adds a versioned baseline author context and a
  typed, sanitized candidate-author failure after exactly one completed call.
  The retained evidence has a reviewed stage and code, zero correct facts,
  exact fact total and accounting, and no fabricated result content. Provider,
  accounting, oracle, scorer, and system failures remain evaluator failures.
- **Prevention:** preserve candidate-versus-evaluator provenance at the author
  boundary and require exact one-call accounting for retained baseline product
  failures.
- **Status:** Resolved in deterministic contracts and the v10/v9/v7 asset
  authority; the deterministic live release gate remains pending.
- **Evidence:** commits `2337953`, `0352b7e`, `0444954`, `b60c2ed`,
  `fe059f3`, `7bba581`, `bd03012`, `1cf5a15`, `80b17bc`, and `c839202`.

### 7.22 P4k-b identity propagation required a root takeover

- **Observed:** repeated P4k-b ruler corrections covered case admission and
  audit propagation before every downstream producer and consumer path. A
  synthetic logical-task-ID fixture could have tempted production to accept a
  legacy identity fallback.
- **Risk:** v7 evidence could reconcile a logical case task instead of the
  durable attempt-scoped runtime task, weakening candidate-observed graph
  authority and typed handoff reconstruction.
- **Resolution:** the root takeover changed the fixture to attempt-scoped
  runtime task IDs, independently pinned the candidate-observed digest, and
  removed v7 logical-ID and legacy-digest fallbacks.
- **Prevention:** exercise the full producer/consumer propagation matrix with
  durable attempt IDs only; do not use a historical fallback to satisfy a new
  scorer family.
- **Status:** Resolved for identity propagation. The v10/v9/v7 asset migration
  is deterministic; a live release PASS is not claimed.
- **Evidence:** commits `80b17bc` and `c839202`; root validation reported 13
  P4k-b tests and 105 focused P4k-b/P4e/P4i/P2a tests passing.

### 7.23 Model-local step IDs collided across independent request tasks

- **Observed:** live release run `g7-live-20260829-04` finalized 127 of 159
  planned attempts before an independent two-task Grepbit request was abandoned.
  Both successful planning calls returned the model-local ID `step-1`; the first
  task persisted it, and the second task hit the global SQLite
  `step_runs.step_id` uniqueness constraint before authoring. The durable journal
  retained all 127 finalized attempts, and no release aggregate was produced.
- **Risk:** an untrusted identifier that is unique only inside one model response
  can become shared persistent identity, couple otherwise independent tasks,
  abandon a request after valid model work, and turn an ordinary product attempt
  into an evaluator-level release interruption.
- **Resolution:** stopped the incomplete live gate without retrying, reproduced
  the exact collision through the real SQLite request session and sequential
  orchestrator, then made the G3 request-task boundary derive a server-owned
  task-scoped durable step ID before its first mutation. The original model ID
  remains ephemeral; authoring, trusted execution, transitions, and persisted
  step records receive the same derived ID.
- **Prevention:** every model-authored identifier that crosses a persistence
  boundary needs an explicit server-owned namespace and a production-shape
  multi-task ruler. A fresh live release run must use a new runtime root and run
  identity after this contract repair.
- **Status:** Resolved in the owning G6b runtime contract. The prior live run is
  preserved as incomplete evaluator evidence and does not establish a G7 result.
- **Evidence:** commits `8c124ea` and `c5720b2`; focused production validation
  reported 16 passing tests.

### 7.24 Post-call authoring rejection abandoned an independent task request

- **Observed:** after the step-identity repair, live release run
  `g7-live-20260830-06` finalized 128 attempts and passed the previously failing
  two-task slot. The next independent two-task request completed two planning
  and two authoring calls, but its second schema-valid author proposal failed the
  deterministic semantic-reference gate before query creation. The base
  `AuthoringError` escaped, so task 1 completed while task 2 and the request were
  abandoned; no aggregate was emitted.
- **Risk:** an ordinary model candidate-quality failure can become an evaluator
  interruption, discard an otherwise valid partial request outcome, and bias a
  release set toward candidates that already satisfy deterministic gates.
- **Resolution:** introduced a typed post-call `AuthoringCandidateError` while
  retaining base `AuthoringError` for pre-call server/configuration defects. The
  request-task boundary now blocks only the owning step/task, records the exact
  sanitized code and two task-local calls, creates no query/evidence for the
  rejected task, and allows independent tasks to complete.
- **Prevention:** every model operation boundary must distinguish transport,
  pre-call server preflight, post-call candidate rejection, and unexpected
  system failure. Production-shape rulers must exercise candidate rejection in
  a multi-task request rather than only testing a standalone QueryAuthor.
- **Status:** Resolved in the owning G3/G6b runtime contract before another fresh
  release invocation; the interrupted run remains non-release evidence.
- **Evidence:** commits `4a28699` and `28be85d`; focused validation reported 54
  passing tests.

### 7.25 Rejected decomposition had no explicit audit outcome

- **Observed:** fresh live run `g7-live-20260830-07` finalized 39 attempts and
  53 model calls, but only 38 audit rows. The final Grepbit trial completed one
  decomposition call, rejected its output before a typed proposal existed,
  persisted the sanitized `request_decomposition_failed` terminal with no
  tasks, then stopped because the audit producer required an accepted proposal.
- **Risk:** a real candidate-quality failure could be misclassified as missing
  evaluator wiring, abort the complete release set, and disappear instead of
  contributing a BVTS-failing trace.
- **Resolution:** added an explicit rejected-decomposition audit outcome for the
  candidate-observed scorer family. The observed runtime wrapper reports that
  outcome only for the typed decomposition failure, the audit records the
  canonical empty candidate graph, and exact one-call reconciliation remains
  mandatory before evidence can finalize.
- **Prevention:** decomposition audit outcomes are singular and explicit:
  accepted proposal or rejected proposal. Missing, duplicate, contradictory,
  zero-call, and extra-operation shapes remain invalid; an empty graph is never
  inferred from the absence of durable tasks or copied from reviewed facts.
- **Status:** Resolved in the evaluation audit boundary before another fresh
  live release invocation; the interrupted run is retained as non-release
  evidence.
- **Evidence:** commits `079bc91` and `d0d7c4f`; focused validation reported 80
  passing tests with zero skips.

### 7.26 A post-authoring terminal was prematurely attributed to compilation

- **Observed:** live run `g7-live-20260830-08` finalized 127 attempts and 211
  model calls with no provider or accounting failures. Its final independent
  two-task Grepbit request completed both planning and authoring calls; task 1
  completed, while task 2 was abandoned before query creation and the request
  became `request_processing_abandoned`.
- **Risk:** a plausible stage-level explanation could be recorded as the live
  root cause without discriminating evidence, causing a valid hardening change
  to be mistaken for resolution of the release interruption.
- **Resolution:** the semantic-engine port now exposes a narrow typed error with
  sanitized parameter, provenance, and dry-plan codes. Wren removes raw chained
  adapter errors, and only the G3 request-task boundary maps that type to a
  blocked step/task with `semantic_compile_failed` and two model calls. Fresh
  live run `g7-live-20260830-09` stopped at the same attempt after that change,
  proving that compilation was not the cause of the live interruption.
- **Prevention:** post-authoring deterministic gates require typed provenance.
  G2 reviewed-contract compilation and unknown `ValueError`/`RuntimeError`
  remain system failures; no broad catch or evaluator-side terminal synthesis
  is allowed.
- **Status:** The typed compilation contract is resolved as independent safety
  hardening. Its premature causal attribution is corrected; runs 08 and 09
  remain incomplete non-release evidence.
- **Evidence:** commits `e68dc0a`, `558e0d2`, `95efb49`, and `e760b3c`;
  focused validation reported 50 passing tests with zero skips; run 09 provided
  the discriminating counterexample.

### 7.27 Task-local evidence identities collided in global SQLite keys

- **Observed:** live run `g7-live-20260830-09` again finalized 127 attempts.
  The first task of the final independent two-task request completed, while the
  second task was abandoned before its query record. Durable inspection showed
  that validation and claim keys were reviewed-fixed-query scoped rather than
  task scoped, so the second task collided with immutable first-task evidence.
  Inventory then found the same boundary defect in direct G4 and G5 step keys.
- **Risk:** legitimate reuse of one reviewed capability can abandon independent
  tasks, make release coverage depend on execution order, or tempt evidence
  overwrite. Lossy hyphen-to-underscore task normalization also aliases distinct
  legal task IDs and can recreate the same failure after a local repair.
- **Resolution:** returned to a production-shape ruler checkpoint and replaced
  local string patches with one task-owned identity boundary. Step keys now use
  a fixed-length SHA-256 namespace over the exact task/local pair and retain the
  original local identity in payload. Fixed-query and direct-G4 evidence keys
  are task scoped, fixed-query retries are attempt scoped, cross-task G4 shares
  the canonical step derivation, and returned evidence references match exact
  persisted records.
- **Prevention:** every writer to a global evidence primary key must prove
  task-owned uniqueness, immutable first-task reconstruction, alias resistance,
  retry separation, and exact result/claim reference closure. After a second
  same-invariant correction, stop local patching and redesign the owning ruler.
- **Status:** Resolved in deterministic contracts. The PostgreSQL-backed broad
  suite passed with 1,182 tests and the separately gated G7 PostgreSQL
  oracle/mutation file passed 35 tests; a fresh live release result remains
  pending.
- **Evidence:** commits `b8cca3c`, `2120d2c`, `8361948`, `4240476`, `616d157`,
  `4265a52`, `0ba462d`, `4b1e9da`, and `066b970`.

### 7.28 Gold task count turned a scoreable candidate mismatch into evaluator failure

- **Observed:** fresh live run `g7-live-20260831-10` finalized 130 attempts,
  then the assessment boundary rejected a canonical one-task candidate because
  the reviewed case expected two tasks. The runtime task and its durable order
  were internally consistent; only the candidate-versus-gold count differed.
- **Risk:** release execution could stop at the first ordinary decomposition
  error instead of retaining it as product evidence, biasing the evaluated set
  toward candidates that already matched the oracle.
- **Resolution:** scorer-v6/v7 runtime identity reconciliation now validates
  only the observed durable task order and canonical server-owned ordinals.
  Gold task count, questions, dependencies, and handoffs are compared later by
  assessment and produce `task_graph_mismatch` rather than evaluator failure.
- **Prevention:** critical evaluation isolation applies to counts and missing
  nodes as well as field values. Candidate-observed revisions never use gold
  structure to reconstruct runtime identity.
- **Status:** Resolved before the complete live release run.
- **Evidence:** commits `59e220f`, `3ba7036`, and `48db06c`; the PostgreSQL-backed
  broad gate reported 1,186 passing tests before the next live invocation.

### 7.29 A valid no-task product terminal was treated as durable corruption

- **Observed:** fresh live run `g7-live-20260831-11` finalized 149 attempts,
  then a schema-valid decomposition produced a capability that the reviewed
  request-task factory could not construct. Production truthfully finalized
  `request_task_construction_failed` with one model call, zero tasks, queries,
  rows, tools, plans, repairs, and evidence, but assessment rejected the empty
  task set as evaluator corruption.
- **Risk:** a normal candidate-quality failure could abort a complete release
  set and disappear from BVTS rather than count as a failed product attempt.
- **Resolution:** candidate-observed scorer-v6/v7 assessment and trace emission
  admit exactly two no-task product terminals:
  `request_decomposition_failed` and `request_task_construction_failed`. They
  require one matching sanitized durable error and exact zero downstream work;
  unknown, duplicate, contradictory, or profile-owned terminals still fail
  closed.
- **Prevention:** no-task success, product failure, budget terminal, and
  evaluator corruption are separate closed sets with production-shape rulers.
- **Status:** Resolved before the complete live release run.
- **Evidence:** commits `7ab9f9c` and `dad8d9e`; the final PostgreSQL-backed
  broad gate reported 1,192 passing tests with zero skips.

### 7.30 The complete G7 live run rejected the internal POC release claim

- **Observed:** `g7-live-20260831-12` finalized all 159 scheduled attempts: 117
  Grepbit attempts over 39 cases and 42 unvalidated-baseline attempts over 14
  eligible cases. There were no open attempts, failed model calls, or
  environment replacements. The aggregate was `passed: false`: BVTS was
  0/117, critical pass^3 was 0/18 cases, noncritical pass-at-least-2 was 0/21,
  A-to-B coverage did not pass, and `false_verified_count` was 15 across seven
  noncritical cases.
- **Risk:** the current model/runtime composition can verify a correctly
  executed reviewed query without proving that the selected task and result
  fully answer the original request. Releasing on execution-chain trust alone
  would overstate product correctness.
- **Resolution:** no production, oracle, or scorer accommodation was made after
  observing the result. G7 is closed as `FAIL`, the internal/trusted POC release
  claim remains unsupported, and the next repair must return to the
  request-resolution and task-grounding contract before any new release run.
- **Prevention:** keep false verification as an unweighted stop-the-line metric;
  retain candidate-derived task graphs independently from gold; require a fresh
  release identity after an accepted owning-contract repair; never combine the
  prior incomplete runtime roots with a future run.
- **Status:** Open product trust defect; the evaluation infrastructure itself
  completed and produced a valid negative result.
- **Evidence:** release evidence SHA-256
  `abef42c038b5857e219df9791fe3c6ede10aa8d631f2e80eb072b2f7f1b9e8b9`;
  ADR 0007; 207/207 reviewed SQL mutations detected; zero SQL-policy safety,
  secret-disclosure, mutation-bypass, or large-relation-prompt events.

## 8. Environment, dependencies, and secrets

### 8.1 External capability was confused with authorization or evidence

- **Observed:** package installation, PostgreSQL, Docker, LiteLLM, and network
  access are independently authorized and can fail after authorization.
- **Risk:** setup failure could be reported as a passing product result, or an
  agent could broaden access to work around a blocker.
- **Resolution:** record exact allowed hosts/actions, preflight disposable
  PostgreSQL before model construction, and classify provider/network failures
  separately from product attempts.
- **Prevention:** permission is not proof; mandatory environment failures never
  count as passing release evidence.
- **Status:** Resolved as an operating rule. The complete G7 live run produced
  valid negative product evidence with no environment replacement attempts.

### 8.2 Model credentials needed a safe local boundary

- **Observed:** the approved LiteLLM endpoint requires `LITELLM_API_KEY`.
- **Risk:** a key could enter Git, logs, prompts, tool output, or a delegation
  packet.
- **Resolution:** ignore `.env`, use only opaque environment-backed access, and
  prohibit reading, printing, searching, copying, or transmitting plaintext
  credentials.
- **Prevention:** configuration stores only the credential name/reference;
  emitted evidence contains no prompt, SQL, rows, bindings, exceptions, or keys.
- **Status:** Resolved as a secret-handling boundary.

### 8.3 The pinned LiteLLM endpoint was unavailable during release execution

- **Observed:** fresh release run `g7-live-20260830-05` opened the first Grepbit
  attempt for `na_budget_tasks`, then its first accounted model call failed with
  sanitized code `provider_failed` before recording any tokens. The attempt
  remained open, no aggregate was emitted, and two later status-only
  `/v1/models` checks returned HTTP code `000` after connection timeouts.
- **Risk:** rerunning immediately could hide an environment interruption as
  sampling variance, consume unbounded calls, or produce an incomplete release
  set that looks comparable with a complete run.
- **Resolution:** preserved the runtime root and journal, issued no replacement
  model call, and kept the release decision pending. PostgreSQL-backed contracts,
  Ruff, formatting, and Git checks remained independent and passed.
- **Prevention:** require a successful status-only provider health check before
  a new full release invocation after an observed provider outage. Use a new
  runtime root and release identity; never merge attempts from interrupted runs.
- **Status:** Resolved externally before `g7-live-20260830-06`; a status-only
  health check returned HTTP 200. The interrupted outage run remains environment
  evidence, not a Grepbit or baseline product result.

## 9. Agent coordination and recovery

### 9.1 Repeated corrections indicated boundary design failure

- **Observed:** several G3/G6 checkpoints required consecutive patches at the
  same authority, lifecycle, or preparation boundary.
- **Risk:** agents could continue fixing visible symptoms while missing the
  shared invariant.
- **Resolution:** after a second same-root correction, stop before a third,
  return to the owning checkpoint, and record the repair sequence.
- **Prevention:** give one worker explicit ownership, return corrections to the
  same thread, and allow root takeover only after repeated incomplete attempts
  or a demonstrably trivial non-overlapping correction.
- **Status:** Resolved as workflow policy.

### 9.2 Interrupted network or agent sessions could obscure local state

- **Observed:** network connectivity and agent sessions were interrupted during
  development.
- **Risk:** work could be rerun, overwritten, or falsely assumed complete.
- **Resolution:** resume from Git HEAD plus staged/unstaged/untracked inventory,
  preserve worker-owned files, and rerun only evidence whose output was lost.
- **Prevention:** local Git/worktree evidence outranks conversational status;
  never use destructive recovery over unresolved work.
- **Status:** Resolved operationally; no repository data was lost.

### 9.3 A denied push changed the remote-tracking branch

- **Observed:** the local reflog for `refs/remotes/origin/dev` records an
  `update by push` at 2026-08-29 19:11:53 +08:00 to `30d2be5`, although the
  active delegation packet explicitly set `Push: Denied`.
- **Risk:** local checkpoint commits can become externally visible before root
  review and can no longer be treated as private, reversible work.
- **Resolution:** did not rewrite or otherwise mutate the remote, kept the next
  checkpoint local, stopped the worker, and used the documented root-takeover
  path after repeated incomplete returns.
- **Prevention:** all remaining delegation and root work keeps push denied;
  closeout must inspect both branch divergence and the remote-tracking reflog.
- **Status:** External state preserved; attribution is not inferred from the
  reflog alone and no further push is authorized.
- **Evidence:** `refs/remotes/origin/dev@{2026-08-29T19:11:53+08:00}` and
  commit `30d2be5`.

### 9.4 Request-grounding release checkpoint required boundary redesign

- **Observed:** the first candidate used an absent parallel release loader and
  an illustrative three-case v11 identity; the second corrected that path but
  generated 39 dictionary lookalikes without validating them through the real
  `ReviewedRequestContract` shape. The next worker return validated the domain
  objects but still represented the budget and trace/scorer contracts with
  tautological dictionaries instead of production-shape witnesses.
- **Risk:** a release-identity ruler could bypass complete release admission or
  fail to detect invalid request-contract/task authority before implementation.
- **Resolution:** stop after the second correction, redesign the checkpoint
  around complete copied v10/v9 authority and real domain validation, then use
  the documented root-takeover path to replace the remaining tautologies with
  production-shape witnesses. The checkpoint targets only the existing
  release-assets/runtime-factory/LiteLLM/evaluation surfaces and includes
  explicit v11 corrections for nonanswerable multi-task and reviewed pre-model
  budget cases.
- **Prevention:** generated critical-contract fixtures must be validated by the
  exact production domain type before asserting digests or promotion identity.
- **Status:** Resolved by the P4q closure implementation.
- **Evidence:** `tests/contract/g7/test_request_grounding_release_identity_checkpoint.py`.

The root closeout review also found that the first committed redesign named but
did not materialize the trace-v5 and scorer-v8 contract artifacts. A separate
test-only amendment now pins both exact byte contracts before production work.
The first production edit then proved that several current-gap assertions were
not durable: satisfying the intended contract made them fail. Production was
reverted cleanly, and a second test-only amendment made each ruler accept only
the exact named current gap or the exact intended future behavior.

### 9.5 Historical materializer and V5/V8 admission checkpoint

- **Observed:** historical fixture helpers repeatedly copied the current v11
  pack and changed revision labels, leaving descriptor pins and nested bytes
  inconsistent with the claimed v1/v2/v8-v10 authority. A shared exact-tree
  materializer fixes that fixture boundary. While validating the current V5
  witness, `SafeEvaluationTraceV5` was then rejected by its inherited V3
  revision validator before V5 fields were evaluated. The isolated
  `ReviewedBaselineAuthor` likewise rejects scorer-v8 before its one accounted,
  value-safe comparison call.
- **Risk:** compatibility tests could make current assets impersonate
  historical authority, and a valid scorer-v8/trace-v5 trace could never be
  emitted or reconciled despite durable grounding evidence. The unvalidated
  comparison baseline could also be disabled instead of remaining operational,
  isolated, and unable to gain verified authority.
- **Resolution:** the checkpoint materializes only explicit historical Git
  authorities in pytest storage and adds direct V5 and baseline-author
  admission rulers. `SafeEvaluationTraceV5` now admits only the exact
  scorer-v8/trace-v5 tuple without broadening V3/V4 validation, and the
  isolated baseline author admits scorer-v8 for its one accounted, value-safe
  call. Historical V3/V4 trace tuples and v6/v7 baseline admission remain
  separately pinned.
- **Prevention:** historical identity fixtures must load their own exact bytes,
  and every new trace or baseline scorer revision must have a direct admission
  ruler before runner composition is treated as evidence. Baseline admission
  remains ungrounded and never confers verified authority.
- **Status:** Resolved in the resumed trace/scorer implementation after the
  direct positive and historical-negative admission rulers passed.
- **Evidence:** `tests/contract/g7/_historical_release_pack.py` and
  `tests/contract/g7/test_p0c_trace_emitter_checkpoint.py::test_p0c_v5_trace_accepts_only_v8_v5_at_model_validation_boundary`, plus
  `tests/contract/g7/test_p4b_baseline_composition_checkpoint.py::test_d1a1_author_admits_scorer_v8_as_unvalidated_baseline`.

### 9.6 Scorer-v8 retained baseline candidate-failure checkpoint

- **Observed:** scorer-v8 admits the isolated baseline author, but
  `UnvalidatedBaselineRunner` retains attributable completed candidate failures
  only for scorer-v7. A current v8 invalid candidate or Wren compile rejection
  is raised after its accounted model call instead of producing scoreable,
  unvalidated failure evidence.
- **Risk:** the local v11 release harness cannot preserve attributable baseline
  comparison failures, or may be tempted to treat provider, transport, or
  unexpected implementation failures as product evidence. Neither outcome can
  create Grepbit verification or request-grounding authority.
- **Resolution:** this checkpoint adds a direct real v11/v8 case/header ruler
  for a completed invalid baseline candidate and keeps v6/v7 and pre-candidate
  provider-failure behavior separately pinned. The intended positive v8 ruler
  is currently red at `g7b_p0e_baseline_author_failed` after exactly one
  accounted call; the existing v8 Wren compile ruler is red at
  `g7b_p0e_baseline_compile_failed`.
- **Prevention:** scorer-v8 may extend only the existing attributable candidate
  categories (authoring, deterministic materialization, compile, policy, and
  typed execution result). Provider, transport, accounting, scoring, and
  unexpected implementation failures remain unfinalized and sanitized.
- **Status:** Resolved by the resumed scorer-v8 implementation.
- **Evidence:**
  `tests/contract/g7/test_p4k_baseline_candidate_failure_checkpoint.py::test_p4k_v8_runner_retains_completed_candidate_author_failure` and
  `tests/contract/g7/test_p4b_baseline_runtime_factory_checkpoint.py::test_d1b2_v7_wren_candidate_compile_rejection_is_completed_evidence`.

### 9.7 P4q grounded-release closure

- **Observed:** two incomplete worker corrections left scorer-v8 graph identity,
  trace-v5 grounding closure, pack-v4 contract admission, and terminal SQLite
  immutability split across inconsistent boundaries.
- **Risk:** a candidate graph could be compared using server-owned digest data,
  a forged or late grounding row could reach trace/scoring, or a v11 pack could
  omit a typed trace/scorer contract without affecting its admission identity.
- **Resolution:** P4q now shares the candidate-observed v8 graph projection,
  binds reviewed A-to-B ResultRef authority only during assessment, validates
  the v4 contract artifacts and pins, reconciles canonical grounding evidence
  in trace-v5, and adds SQLite schema-v6's parent-running insert guard.
- **Prevention:** `test_p4q_release_closure_checkpoint.py` covers each boundary;
  historical v1-v3 packs and v4/v5 runtime evidence remain readable under their
  original semantics.
- **Status:** Resolved by deterministic offline validation.
- **Evidence:** `tests/contract/g7/test_p4q_release_closure_checkpoint.py`.

### 9.8 Proposal-mismatch rulers used an empty graph unlike production

- **Observed:** bounded live diagnostics reached a task-level
  `proposal_mismatch` after one accepted decomposition, but the P4s/P4t test
  witnesses used `observe_decomposition_rejected()` and the assessment required
  the canonical empty graph. The real audit retained one nonempty,
  candidate-derived graph and was therefore rejected as invalid durable
  evidence.
- **Risk:** an ordinary grounded-product mismatch becomes a harness failure,
  preventing the release scorer from recording a truthful BVTS failure. A local
  patch to facts or tracing can appear to fix the symptom while leaving the
  production-shape witness wrong.
- **Resolution:** stopped after the repeated P4s/P4t corrections, returned to a
  P4u ruler checkpoint, replaced the rejected-decomposition fixtures with
  accepted candidate proposals, and required a nonempty observed graph for the
  exact task-level mismatch. The empty graph remains reserved for a real
  pre-proposal rejection.
- **Prevention:** build evaluator rulers through `AttemptAuditProducer` with the
  same decomposition outcome as production, and treat a third correction at
  one invariant as boundary-redesign evidence.
- **Status:** Resolved before the final v11 live run.
- **Evidence:** commits `80227f0`, `aa7c22e`, and `df544b8`; P4u focused result
  12 passed; sanitized diagnostic emitted a scoreable `SafeEvaluationTraceV5`
  with `request_resolution/proposal_mismatch` and zero false verification.

### 9.9 Scorer-v8 rejected the server-owned nonanswerable terminal ID

- **Observed:** incomplete live run `g7-live-20260831-13` finalized the three
  reviewed pre-task budget trials, then rejected the first reviewed
  clarification terminal with `g7b_p3_runtime_task_identity_invalid`.
  Production intentionally persisted one `<run_id>-terminal` blocked task with
  exact grounding, while assessment allowed only candidate-style
  `<run_id>-task-1` identities.
- **Risk:** a correct zero-model-call nonanswerable resolution becomes an
  evaluator failure and prevents complete release coverage. Broadly accepting a
  suffix would weaken task identity for answerable or foreign tasks.
- **Resolution:** P4v admits the lifecycle ID only for scorer-v8, an exact
  singleton runtime order, a reviewed nonanswerable case, one blocked result,
  and one matching sanitized terminal error. Answerable, malformed, multi-task,
  and historical paths retain the existing rejection.
- **Prevention:** every server-owned terminal lifecycle needs a
  production-shape assessment witness in addition to candidate-task identity
  rulers.
- **Status:** Resolved before the final v11 live run.
- **Evidence:** commits `fb7ec52` and `ffe3517`; focused result 85 passed; the
  preserved run-13 SQLite evidence re-assessed as a valid
  `SafeEvaluationTraceV5` with one grounding projection and zero false
  verification.

### 9.10 Grounding-aware v11 release is safe but not useful enough

- **Observed:** fresh run `g7-live-20260831-14` finalized all 159 attempts under
  scorer-v8/trace-v5. Fifteen of 39 cases passed; all 24 answerable cases failed
  every trial with 53 `proposal_mismatch` and 19 `resolution_mismatch`
  outcomes. Grepbit fact correctness was 0/177, baseline correctness was 0/57,
  and the required A-to-B case did not pass.
- **Risk:** reporting the successful safety gates as a product pass would hide
  that the admitted answerable surface produces no verified answers. Repeating
  the same model sampling or loosening exact request grounding would trade
  coverage for unmeasured semantic error.
- **Resolution:** retain the complete aggregate as G7 `FAIL`. Do not rerun the
  current identity, tune assets, weaken grounding, or add retries. Route the next
  product decision to the provider-neutral decomposition and reviewed-contract
  matching boundary, or explicitly narrow the supported question surface.
- **Prevention:** keep BVTS boolean and report coverage, facts, A-to-B, safety,
  latency, and baseline separately. Zero false verification is necessary but
  cannot substitute for answerable verified success.
- **Status:** Open product-capability defect; evaluation infrastructure and
  safety behavior passed their stated contracts.
- **Evidence:** mode-0600 release evidence SHA-256
  `3012c10f509d8193055f7ec28749e490a8edd844e3ace5e342d24894fdc7d330`;
  207/207 mutations detected; zero safety, false-verification, disclosure, and
  large-relation-prompt violations; ADR 0007 grounding-aware addendum.

### 9.11 Reviewed request materialization was delegated to an exact-copy model call

- **Observed:** the v11 live gate recorded 53 answerable `proposal_mismatch`
  outcomes. The server had already selected the exact reviewed contract and
  rendered its complete task blueprints, but still required the model to
  reproduce every reviewed field and dependency exactly. A distinct 19
  answerable attempts passed that comparison and then blocked with
  `prompt_schema_revision_mismatch`: the retired decomposition revision was
  reused for task-local planning.
- **Risk:** an unneeded model exact-copy task made reviewed coverage unstable,
  while a deterministic prompt-identity composition defect blocked the attempts
  that did match. Treating either count as model capability alone would
  misdiagnose the release failure.
- **Resolution:** selected answerable contracts now materialize their ordered
  task graph, typed slot bindings, grounding evidence, and A-to-B dependencies
  server-side with zero request-decomposition calls. The actual G3 planning
  request receives the provider-neutral task-local revision. The historical
  comparison API remains readable but cannot supply authority to this path.
- **Prevention:** `test_reviewed_request_materialization_checkpoint.py` uses an
  exact selected typed-slot A-to-B contract and a real G3 task factory to prove
  both call absence and planning-revision ownership.
- **Status:** In progress. The v12/v11/v9/v6 release migration completed its
  deterministic and PostgreSQL-backed gates, but its one authorized live
  invocation stopped before provider use and did not produce a release aggregate.
- **Evidence:** `8e7074c`; accepted P5 checkpoint `f240aaa`; sanitized live
  aggregate `g7-live-20260831-14`; incomplete v9 invocation `g7p5v9a`.

### 9.12 V9 pre-task terminals retained a historical one-call journal assumption

- **Observed:** the only authorized v12/v11/v9/v6 invocation, `g7p5v9a`,
  stopped at the first `request_task_budget_exceeded` terminal before any
  provider call. The terminal was correctly server-owned and zero-call, but
  `SqliteAttemptJournal` admitted a completed zero-call snapshot only for the
  historical scorer-v8 identity.
- **Risk:** a correct v9 safety terminal appeared as evaluator failure, left an
  attempt open, and prevented a truthful complete release aggregate.
- **Resolution:** scorer-v9 now shares the explicit reviewed pre-model
  zero-call journal lifecycle, and
  `test_p4d_budget_terminal_exact_usage_checkpoint.py` proves the real v9 case
  finalizes zero calls and tokens.
- **Prevention:** pre-task terminal accounting is versioned alongside the
  materialization identity; a future scorer identity must prove both journal
  finalization and trace reconciliation before live execution.
- **Status:** Resolved in deterministic and PostgreSQL-backed validation. The
  failed invocation is not rerun; a new accepted release identity is required
  for any successor live evaluation.
- **Evidence:** `g7p5v9a`; final offline 1279 passed, 17 skipped; final
  PostgreSQL-backed gate 1295 passed, 1 historical-identity skip.

### 9.13 P5 typed evidence existed without a production-shape witness

- **Observed:** the first P5 release-identity ruler constructed
  `AttemptAuditEvidenceV9` directly, while the real producer and SQLite store
  still persisted the historical audit shape. Two successive ruler corrections
  also exposed independently masked gaps in candidate-graph persistence,
  governed-asset identity closure, retained-baseline comparison, and A-to-B
  release coverage.
- **Risk:** a green type-level ruler could allow zero-call answerable attempts,
  incomplete task graphs, or mixed release assets to be scored under the v9
  identity. Combined tests could also hide a later release gate behind an
  earlier comparability failure.
- **Resolution:** stop local production repair and return to one consolidated
  production-shape checkpoint. Each boundary now has an independent ruler that
  crosses its real producer, durable store, assessment, loader, or aggregate
  path; the full graph ruler explicitly identifies the missing durable schema.
- **Prevention:** critical-evaluation checkpoints must prove the real
  producer/store/consumer path and isolate ordered gates so one expected failure
  cannot stand in for another. A directly instantiated model is not evidence of
  production propagation.
- **Status:** In progress. Production remains unchanged pending explicit
  authorization of the consolidated implementation boundary.
- **Evidence:** checkpoint commits `351d1bc` and `9f1d9e9`; root-focused expected
  failures under `test_p5_v9_production_shape_checkpoint.py`.

### 9.14 V9 evidence boundary required a successor identity

- **Observed:** the consolidated P5 ruler showed that scorer-v9/trace-v6 types
  could express desired audit and graph fields without the real producer, SQLite,
  assessment, admission, retained-baseline, and A-to-B paths enforcing them.
- **Risk:** treating v9 as a new release candidate would silently reinterpret
  historical evidence and permit self-nominated governed bytes or incomplete
  candidate graph/usage evidence.
- **Resolution:** preserve v9/v12 historical readability and establish the
  atomic v10/v13/v12 successor checkpoint. It requires schema-v7 immutable
  `RequestTaskGraphEvidence`, a durable v10 audit, exact operation accounting,
  independently pinned governed bytes, retained-baseline comparability, and
  non-vacuous A-to-B coverage.
- **Prevention:** a successor release identity may be implemented only after
  each real producer/store/assessment/admission boundary passes independently;
  historical identities are never upgraded by parser or scorer conditionals.
- **Status:** In progress. This is a test/spec checkpoint; production and real
  release assets remain unchanged.
- **Evidence:** successor ruler
  `tests/contract/g7/test_p5_v9_production_shape_checkpoint.py`.

- **Checkpoint correction:** commits `6a63bf5` and `35ec259` exposed the same
  ruler-fixture boundary twice: prospective v10 requests reused a v9 journal
  row, and several intended future-pass assertions were unconditional. The
  final checkpoint correction builds the v10 case/header/journal atomically,
  separates positive and tampered operation-usage controls, uses append-only
  graph immutability, and pins complete hypothetical governed bytes. A further
  fixture-shape correction on this boundary requires a new owner review rather
  than another local patch.

### 9.15 The v10 identity was admitted before every runtime consumer supported it

- **Observed:** after promotion to the reviewed v13/v12/v10/v6 asset identity,
  the PostgreSQL-backed suite found that baseline authoring, retained candidate
  failure handling, and attempt reconciliation still stopped at scorer-v9.
  After those consumers were corrected, the single authorized live invocation
  reached the zero-call `na_budget_tasks` terminal and stopped because budget
  assessment and the inherited trace V3/V4/V5/V6 validators still treated v10
  as unsupported. The P5 trace helper had masked the trace gap by validating a
  v9 object and relabeling it with Pydantic `model_construct`.
- **Risk:** an independently pinned release pack could pass asset admission and
  aggregate-level unit tests while the real producer/assessment/emitter path
  could not produce one schema-valid current-identity trace. A correct safety
  terminal would then appear as a generic evaluator failure, and a test-only
  constructor could create evidence that production was forbidden to emit.
- **Resolution:** returned to production-shape checkpoints for baseline
  success/failure reconciliation, exact v10 zero-call audit assessment, direct
  v10 trace validation, emitter dispatch, historical v9 readability, mixed
  revision rejection, and environment base-trace isolation. Production now
  uses one exact trace-v6 tuple predicate for scorer-v9 and scorer-v10 and
  reconciles the typed v10 audit without fabricating task or grounding rows.
- **Prevention:** a successor release identity must cross normal model
  validation and each real producer/store/assessment/emitter consumer for an
  ordinary completion, a reviewed pre-task terminal, and a pre-execution
  environment failure. `model_construct`, source-membership assertions, and
  aggregate-only helpers do not establish production compatibility.
- **Status:** Resolved in deterministic and PostgreSQL-backed validation. The
  successor live observation remains `INCONCLUSIVE`, and no retry was made.
- **Evidence:** checkpoints `0ed71f5`, `5bac677`, `95dbc4e`, and `1051774`;
  implementations `7243e4f` and `9f82ad8`; final offline result 1,320 passed,
  17 skipped; final PostgreSQL-backed result 1,336 passed, one skipped.

### 9.16 Long broad gates exceeded the worker execution wrapper

- **Observed:** the implementation worker completed focused validation but
  three full offline pytest attempts were externally terminated after roughly
  30 to 35 seconds, at 53% to 59% progress, without a test failure, summary, or
  exit code.
- **Risk:** an infrastructure timeout could be misclassified as a product or
  test failure, or repeated short invocations could waste the validation budget
  without ever producing admissible broad-gate evidence.
- **Resolution:** after three identical tooling failures, the root reviewer used
  the documented takeover condition and ran the same suite in a resumable
  execution session. It completed with 1,320 passes and 17 expected skips, then
  the PostgreSQL-backed suite completed with 1,336 passes and one expected
  skip.
- **Prevention:** run broad gates expected to exceed 30 seconds through a
  resumable session and poll for the final exit code. After repeated termination
  at the same wrapper boundary, transfer only validation ownership to the root;
  do not restart implementation or infer PASS from partial progress.
- **Status:** Resolved operationally; no code or contract behavior changed.
- **Evidence:** focused worker results 55 passed and 136 passed with one skip;
  root offline and PostgreSQL-backed summaries recorded in ADR 0007.

### 9.17 Derived ranking cases omitted their reviewed result-limit authority

- **Observed:** the first complete scorer-v11 provider-free readiness record
  produced 12 false-verification events across two bounded multi-task ranking
  cases. Their manifests required two-row previews and partial verification,
  while runtime-profile-v4 applied the two-row override only to the original
  single-task ranking case. The executor therefore returned the complete
  four-row relation and correctly marked both tasks verified.
- **Risk:** the case oracle and production-shaped runtime could each be valid in
  isolation while their admitted composition made reviewed facts unreachable.
  The readiness finalizer also recorded the nonzero safety count without
  preventing a `PASS` decision.
- **Resolution:** runtime-profile-v5 makes the exact two-row result and preview
  limits mandatory for all three bounded ranking cases, promotes the exact
  release pack to v15, and preserves release-v14/runtime-v4 as historical.
  Pre-live finalization now rejects every nonzero safety counter.
- **Prevention:** asset admission tests derive the effective `QueryBudget` for
  every case-specific result boundary, reject missing/default/type-swapped
  overrides, and require zero safety counts before readiness can pass.
- **Status:** Resolved in deterministic and PostgreSQL-backed pre-live
  validation; LiteLLM product evaluation remains a separate gate.
- **Evidence:** checkpoint `c087290`, implementation `e5968ce`; offline result
  1,455 passed and 20 skipped; PostgreSQL-backed result 1,471 passed and four
  historical-identity skips; production-shaped 159-slot rehearsal 23 passed
  with zero false verification.

### 9.18 Post-dispatch provider failure left an open release attempt

- **Observed:** the only authorized scorer-v11/runtime-profile-v5 live
  candidate stopped at `p1_direct_01` trial 1 after two model calls ended with
  the sanitized `provider_failed` code. The journal retained 135 finalized
  attempts and one open attempt, while the entrypoint emitted only
  `g7_p4c_local_release_failed` and no release evidence or aggregate.
- **Risk:** an external provider failure after dispatch cannot be distinguished
  by operation stage, terminalized, or represented as a durable partial release
  observation. The fail-closed entrypoint prevents a false PASS, but the open
  attempt weakens lifecycle and budget reconciliation and discards otherwise
  valid schedule evidence from the release-level contract.
- **Resolution:** retained the live root and three integrity-checked SQLite
  authorities, classified the candidate `INCONCLUSIVE`, removed the disposable
  PostgreSQL container/network/volume, and did not retry. No production,
  release-asset, prompt, or scoring behavior was changed.
- **Prevention:** before another live candidate, establish a ruler checkpoint
  for durable failed-operation attribution, exact unknown-or-reported token
  accounting, terminal post-dispatch provider-failure evidence, partial-run
  evidence, and an explicit abort-versus-continue policy. Preserve zero SDK
  retries and historical evidence unchanged.
- **Status:** PF1 opt-in mechanism resolved at `267f3e8`; current release-profile
  activation is complete in the separate R2 candidate `24d43b5` under lifecycle
  V2. Historical live records and the default V11 profile remain unchanged.
  See [PF1 implementation and closeout](checkpoints/g7-provider-failure-lifecycle-design.md#implementation-and-closeout)
  for durable partial-run and unknown-usage witnesses, 1,569 passing offline
  tests, three passing PostgreSQL regression tests, and verified fixture cleanup.
- **Evidence:** candidate SHA `3d6119b`; release run
  `g7-live-20260904-v11-v15-01`; 136 initiated/135 finalized/one open attempt;
  131 completed and two failed model calls; ADR 0007 scorer-v11 live
  observation.

### 9.19 Partial replay exposed false verification in multi-task comparisons

- **Observed:** production readers reconstructed all 96 finalized Grepbit
  attempts from a copy of the incomplete live root. Two multi-task comparison
  trials returned `partially_verified` with one of two reviewed facts correct
  and a `resolution_mismatch`. The accepted scorer therefore reported two
  false-verification events.
- **Risk:** repairing only provider-failure terminalization would make the next
  live run complete, but it could not make the current product candidate safe
  or releasable. A partial-success response can expose verified public state
  while its reviewed request contract remains incomplete.
- **Resolution:** stopped feature and live work, preserved the original
  evidence hashes, and classified the replay as diagnostic rather than release
  evidence. No scorer, product behavior, prompt, asset, or threshold changed.
- **Prevention:** keep the conservative false-verification definition. Before
  another candidate, add a product-safety checkpoint proving that incomplete
  reviewed facts cannot retain public verified state, or that the complete
  reviewed result is produced. Evaluate this separately from provider-failure
  lifecycle closure.
- **Status:** Historical V11 diagnosis remains unchanged. The separately accepted
  [V12 claim-semantics contract](checkpoints/g7-v12-claim-semantics.md) is activated
  in R2 with provider-free durable witnesses. Fresh live product-safety and
  answerability evidence remain open; R2 does not reinterpret this historical run.
- **Evidence:** 96/96 reconstructed traces; 75 BVTS passes; 41/63 reviewed
  facts; noncritical fact accuracy 85.71%, 71.43%, and 71.43%; false
  verification in `p1_compare_revenue_august_then_july` trial 1 and
  `p1_compare_revenue_july_then_august` trial 2; ADR 0007 partial diagnostic.

### 9.20 Successor integration omitted lifecycle-specific consumers

- **Observed:** R2's actual PostgreSQL schedule first stopped at the zero-call
  A-to-B assessment (`g7_p5_v10_answerable_task_usage_missing`), then at release
  aggregation with retained baseline failures. Individual V12 producer and
  asset-admission tests had already passed.
- **Risk:** admitting a revision at one consumer cannot establish evaluator
  readiness; late lifecycle failures can discard an otherwise completed run.
- **Resolution:** reuse the existing exact V11 A-to-B validation for V12 and
  share baseline completion/release eligibility across the applicable versions.
  Failed baselines still force a negative aggregate; no fact or safety predicate
  was relaxed. PF1 V2 partial results reuse the existing journal/readback owner.
- **Prevention:** require one real candidate pack across producer, journal, audit,
  assessment, trace and aggregate, including retained failure, zero-call and
  environment-replacement lifecycles before any external provider invocation.
- **Status:** Resolved in R2 `24d43b5`; broader historical revision convergence
  remains owed before another identity or consumer expansion.
- **Evidence:** 1,585 offline passes (24 skips), six clean-candidate PostgreSQL
  passes, and [R2 durable closeout](checkpoints/g7-r2-successor-activation.md#implementation-and-closeout).

### 9.21 Reviewed ranking completion and runtime truncation disagree

- **Observed:** R2 live evaluation matches all reviewed facts but three ranking
  cases fail 3/3 with `resolution_mismatch`. The manifests require request
  status `completed` and public `partially_verified`; immutable task records
  show `partially_completed` and partial evidence completeness. Only resolution
  layer 1 fails. The same nine failures exist in the earlier scripted rehearsal.
- **Risk:** facts and safe partial claims do not establish the required terminal
  contract. Reporting only the deliberately retained baseline failures hides
  independently actionable product failures behind evaluator readiness.
- **Resolution:** retained release FAIL, diagnosed the `execution.truncated`
  status mapping and assessment completion requirement, and added the missing
  rehearsal failure explanation. No runtime status, oracle or scorer was changed.
- **Prevention:** require explicit reviewed bounded-completion versus incomplete
  full-result rulers, with negative witnesses for missing facts and unreviewed
  truncation. Rehearsal closeouts must enumerate candidate case/BVTS failures
  alongside deliberately injected baseline failures.
- **Status:** Reporting omission corrected. R3's accepted successor implements
  the completion-contract repair with durable positive/negative witnesses;
  live product validation remains outstanding. R2 results are unchanged.
- **Evidence:** `g7-live-20260908-r2-v16-01`, 177/177 facts, 63/72 ordinary
  answerable trial passes, nine ranking resolution failures; [live diagnosis](checkpoints/g7-r2-live-evaluation.md).

### 9.22 Baseline JSON-object output contract is not supplied to the model

- **Observed:** all 42 R2 baseline calls complete provider/accounting usage and
  fail authoring before query execution. Offline capture of the actual R2 wire
  confirms JSON-object mode without the complete `SemanticQueryProposal`
  response schema. The reader nevertheless validates against that schema.
- **Risk:** a nonfunctional baseline cannot provide a useful quality comparison.
  Generic author-failure codes also hide the exact failed output-shape boundary.
- **Resolution:** preserved the 42 failures and isolated the missing schema as
  a demonstrated prompt-contract omission. The exact rejected live outputs were
  not retained, so the missing/malformed fields remain unknown.
- **Prevention:** version the baseline prompt with an explicit output contract;
  retain only sanitized schema-error attribution and prove one-call parsing,
  rejection and trusted execution before another live identity. Keep bindings,
  oracle facts and raw errors out of model context.
- **Status:** Prompt-contract omission repaired by opt-in R3 baseline v2;
  scripted one-call parsing and trusted execution pass. Live baseline quality
  remains unproven. No prompt change or live retry occurred in the R2 evaluation.
- **Evidence:** [R2 live diagnosis](checkpoints/g7-r2-live-evaluation.md),
  `baseline-diagnosis.json` in the run artifact root, and
  `g7b_p0e_baseline_author_failed` on 42/42 baseline attempts.

### 9.23 R3 admission omitted a zero-call consumer and persisted audit union

- Observed: R3 PostgreSQL rehearsal rejected a zero-call budget terminal because
  the trace consumer still enumerated V12 as its latest claim-level scorer.
  After that repair, a successful in-memory rehearsal failed durable readiness
  JSON readback because its audit union ended at V12.
- Risk: candidate admission or passing object-level checks could be reported as
  readiness while persisted evidence was unreadable by a downstream consumer.
- Resolution: trace zero-call handling uses the shared claim-level revision
  family; readiness uses the materialized audit union including the exact V13
  type. Historical V12 audit and lifecycle constraints remain exact.
- Prevention: the full R3 PostgreSQL witness asserts all 117 Grepbit trials pass
  BVTS, then writes and reads the durable record and checks V13 audit identity.
  Both R3 partial paths and unchanged R2 PostgreSQL witnesses also execute.
- Status: Resolved for R3; broader compatibility ownership remains owed before
  another identity expansion. No live product claim follows from this repair.
- Evidence: implementation `e3b2978`; 1,631 offline passes and six clean-candidate
  PostgreSQL passes; [R3 closeout](checkpoints/g7-r3-implementation.md).

### 9.24 Baseline ranking scorer confuses oracle key order with cursor schema

- Observed: R3 aborted at the first ranking baseline after its model call
  completed. A provider-free diagnostic proves the current scorer rejects
  correct reviewed-order ranking output because canonical oracle JSON keys
  have a different order. Five of 14 baseline cases have this mismatch.
- Risk: a valid candidate can fail at evaluator scoring independently of facts;
  a single direct baseline success did not cover the ranking capability.
- Resolution: diagnosis only; no scorer, schema, oracle or release policy changed.
  The live cursor/inner exception was not retained, so the synthetic defect is
  not claimed as the proven sole cause of that missing live result.
- Prevention: use reviewed cursor-schema authority, treat JSON object key order
  as non-semantic, and require baseline success witnesses for each capability.
- Status: Repair validated in `858ed5b`: reviewed cursor authority restored,
  all 14 baseline-supported cases execute and match facts in provider-free
  PostgreSQL witnesses. Live baseline quality remains unproven.
- Evidence: [R3 live report](checkpoints/g7-r3-live-evaluation.md),
  `baseline-order-diagnosis.json`, `baseline-schema-inventory.json`.

### 9.25 Non-provider runner abort loses completed baseline result projections

- Observed: R3 retained 97 finalized attempts and one open baseline attempt;
  all 50 model calls completed, but no full/typed partial release file exists.
  Existing durable readers reconstruct 73 Grepbit traces. The 24 finalized
  baseline attempts retain accounting but not their outcome/fact projections.
- Risk: generic `g7b_p0f_runner_failed` hides the inner stage, loses the in-memory
  prefix, and prevents a reliable baseline comparison or full usage claim.
- Resolution: original records and open status preserved; no fabricated closure,
  provider-failure relabel, or retry. R3 is INCONCLUSIVE and not release-ready.
- Prevention: a reviewed durable per-attempt result and internal-failure lifecycle
  with execution/scoring/close witnesses, distinct from provider failures and
  still retaining unknown quantities and exact completed evidence.
- Status: Resolved for the explicitly opted-in implementation after checkpoint
  `3bd2170`; spec revision 0.1.39 records the accepted publication and internal
  interruption contract. The final PostgreSQL-enabled suite passes 1,720 tests
  with nine historical/profile skips. The subsequent accepted R4 activation pins
  this lifecycle; its own validation is recorded in the R4 implementation report.
  Historical R3 evidence remains unchanged.
- Implementation evidence: [release-result journal closeout](checkpoints/g7-release-result-journal-implementation.md),
  including all 14 baseline capabilities, cold production readback, terminal
  guards, known/unknown usage and execution/scoring/cleanup fault witnesses.
- Evidence: [R3 live report](checkpoints/g7-r3-live-evaluation.md), 222-file
  verified archive and unchanged source DB hashes in `analysis.json`.

### 9.26 Shared scoring identity does not bind a successor runtime profile

- Observed: R4 intentionally retains R3's case set, model and scorer. A request
  digest containing only those fields and the result lifecycle cannot distinguish
  the candidate from an older explicit-opt-in implementation witness. The new
  regression initially fails at `r4_durable_candidate_identity_missing`.
- Risk: changing only a readiness summary could misattribute a durable result
  to a different runtime candidate.
- Resolution: production R4 composition includes its exact pack digest in the
  persisted request digest. The cold reader rebuilds that request from the
  admitted pack; absent or foreign binding rejects. Historical requests omit
  the optional field and preserve their digest.
- Prevention: test exact current/historical digest behavior and reject cold
  readback with a missing or foreign pack binding. R4 finalization also requires
  archive-backed or existing durable result authority, not summary booleans.
- Status: Implemented within the accepted R4 activation scope; closeout evidence
  is recorded in [R4 implementation](checkpoints/g7-r4-implementation.md).

### 9.27 Baseline candidate failures veto an otherwise passing R4 aggregate

- Observed: the complete R4 invocation passes all 117 Grepbit trials and every
  non-baseline release predicate. Baseline parameterization rejects 23/42 trials;
  only 5/14 baseline groups are failure-free across three trials. The inherited
  scorer therefore returns FAIL. Of 19 executed baseline trials, 14 also miss
  at least one fact; successful execution is not correct execution.
- Risk: weak baseline behavior blocks release and limits comparative evidence.
  One generic materialization code cannot distinguish parameter, schema,
  reference, relation or literal-guard failures after the process exits.
- Resolution: preserve the complete FAIL result and all durable baseline
  receipts. No post-run rule change or sampling retry.
- Prevention: characterize the existing materialization boundary without a
  provider, then review baseline eligibility separately from evidence completeness
  and safety. Policy changes require the evaluation ruler checkpoint; any added
  diagnostic metadata must remain value-free and respect its owning contract.
- Status: Open; bounded baseline diagnosis and release-policy review are next.
- Evidence: [R4 live report](checkpoints/g7-r4-live-evaluation.md), including the
  seven-predicate conjunction, 355-file verified archive and unchanged DB hashes.

## 10. Deferred work and non-goals

The following items are deliberately not folded into G7 feature work:

- Historical G3/G4/G5 delivery-module naming, compatibility wrappers, large
  modules, and remaining result/lifecycle duplication: **Owed to post-G7
  characterization-first convergence**.
- In-memory lifecycle/usage eviction: **Owed before long-running service or soak
  claims**.
- Authentication, tenant isolation, retention, encryption, backup, high
  availability, and incident response: **outside the internal/trusted POC and
  require a separate specification and release gate**.
- Best-of-N planning: **not planned**; current evidence favors deterministic
  PlanGate plus targeted repair.
- Real multi-world fixtures, reviewed SQL mutation content, the PostgreSQL
  mutation driver, and the concrete 30-case retail_v1 release pack are
  **completed in P3**. Live Grepbit/baseline attempts, three-trial release
  execution, aggregate latency/cost evidence, and final release scoring are
  **completed historically with a G7 FAIL decision in ADR 0007**. The accepted
  request-resolution and task-grounding candidate was then evaluated by fresh
  v11/v10 run `g7-live-20260831-14` and also produced G7 `FAIL`. The two
  identities are independent decisions, not a trend comparison. Another live
  run requires a new accepted decomposition/contract-matching candidate and
  fresh identity; the current identity must not be rerun as sampling retry.
- The bounded ranking runtime profile now has an explicit production-shaped
  composition witness for all three case identities. Long-running service
  lifecycle and structural convergence remain separate owed work.

## 11. Adding a new incident

Append an incident only when there is concrete evidence. Use this shape:

```text
### <identifier and short title>

- Observed: the reproducible symptom or mismatch.
- Risk: the product, safety, evidence, cost, or delivery consequence.
- Resolution: what changed and at which owning boundary.
- Prevention: the ruler, invariant, or workflow rule that prevents recurrence.
- Status: Resolved, In progress, Owed, or External.
- Evidence: commits, ADR, exact test, or sanitized failure code.
```

Do not copy secrets, prompts, SQL, rows, bindings, raw exception messages, or
customer data into this log.
