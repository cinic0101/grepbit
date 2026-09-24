# Grepbit working agreements

## Start here

Read `README.md`, then the current GitHub issue. Read only the relevant design
section in `docs/`; do not reload the legacy research history for every task.
This is V3: analytical intent -> checked facts, not another expanding Text2SQL
language. Use the current task's accepted contracts and exact evidence pins to
establish phase and scope; historical phase descriptions do not grant authority.
See `docs/roadmap.md` for gates and the relevant P1/P2/P3 contract for the task.
These agreements are shared across coding tools. Keep model choices, effort,
subagent names and tool-specific orchestration in personal/tool configuration.

## Authority and branches

- Work on `dev` (or a task branch based on `dev`). Never commit to, merge into,
  or force-push `main` without explicit owner approval. Preserve unrelated work.
- A repository instruction is not permission to make external calls. Live runs
  are owner-triggered, directly or through an owner-posted standing grant (see
  Goal-scoped delegation), and executed by the owner's local coding agent only.
- Do not invoke LiteLLM, Gemma, Bedrock, external databases, remote runners, or
  paid services merely because credentials or an issue are available. Do not
  add scheduled/live GitHub Actions or a remote-control bridge.
- For a live run, prepare the exact command, code/source identity, case IDs,
  provider, allowed data, attempt/token/time bounds, output location and stop
  conditions. The owner authorizes that run separately unless an owner-posted
  standing grant covers it (see Goal-scoped delegation). See `docs/local-execution.md`.
- Never print or commit keys, connection strings, local endpoint addresses,
  environment dumps, real customer data or unreviewed live traces.

## Collaboration and review

- One task owner is accountable for requirements, planning, integration and
  acceptance evidence, whether working alone or with assistants. Assign one writer
  per shared contract surface and preserve other contributors' changes.
- For a material new or changed compatibility-sensitive contract, establish the
  contract and meaningful ruler/test evidence before production implementation.
  Follow the current task's owner checkpoint and delegated-authority boundaries;
  a repair to an already accepted contract does not itself create a new checkpoint.
- High-risk changes need an additional review of the actual delta and evidence:
  product behavior, public API/schema, security/permissions, persistence/transactions,
  concurrency, cross-module refactors, backward compatibility, evaluation/evidence
  contracts and protected/frozen sources. No specific coding tool or model is
  required. If required review is unavailable, report it pending, not self-certified.
- Open a PR for one coherent tracked change after implementation, relevant checks
  and self-review; read-only investigation and local evidence do not need a PR.
  For substantive PRs, request independent remote review of the actual GitHub
  diff before merge. Send a compact objective, invariants, test results, risks
  and review focus; the summary does not replace diff review. Small mechanical
  changes may use owner review. Tests, local QA and remote review do not authorize
  merge. Merge requires explicit owner approval unless the owner explicitly
  delegates it for the current task; follow task-specific Git and execution
  permissions.
- Preserve independent semantic/oracle acceptance required by the evaluation
  contract. A coding assistant's local review does not satisfy that requirement
  merely because it ran in a separate conversation.

## Goal-scoped delegation

- The owner may delegate one goal through a goal issue plus one standing grant
  comment **typed by the owner, not posted by an agent using the owner's
  credentials**. The comment itself states or pins the goal, the allowed step
  sequence, providers, run counts and call/run bounds, data boundary, route
  retry/fallback/cache attestation per provider and stop conditions; an
  agent-drafted goal issue or table is a proposal until then. Inside the grant
  the agent proceeds without per-step chat approval and reports at milestones
  and stops. The `main` rule above is unchanged.
- Inside the scope: a contract checkpoint is the contract document plus a
  ruler committed failing before the implementation commit and passing after,
  in the same PR. Code review is the high-risk delta review and satisfies the
  independent review of the GitHub diff above: an independent fresh-context
  agent session that receives only the PR reference, objective and review
  focus, reads the actual GitHub diff and `dev` files through GitHub, has no
  access to the implementing conversation, and discloses any other context it
  was given; the PR names its high-risk category and records the review prompt
  and verdict. The agent may
  merge into `dev` after that review reports no blocker and the full offline
  suite passes. A reviewer blocker is fixed and re-reviewed, or escalated to
  the owner as a stop; it is not debated. Semantic, oracle and case acceptance
  stay with an independent human or a reviewer the owner names; the
  implementing agent never decides them.
- Live runs inside the scope bind one authorization envelope to the standing
  grant comment and to one output slot each, and execute a tool from a merged `dev` commit whose digest
  the run record keeps; a tool that cannot bind grant and slot is outside the
  grant. A run outside the grant's steps or budgets needs separate authorization.
- Mandatory stops, taken before the change is made and reported with the
  evidence: a needed change to a protected/frozen source, an oracle, gold or
  case text, to a product promise or accepted product contract, or to
  `AGENTS.md`, `CLAUDE.md`, `docs/local-execution.md` or other authority text
  (owner review and owner merge only); a third candidate fix on one failure
  family (the roadmap's two-fix default); budget exhaustion; any credential, route or privacy
  anomaly; a blocker still open after one fix round; evidence that the goal is
  unreachable as stated.

## Architecture boundaries

- Keep the reviewed semantic catalog, request contract, analytical intent and
  execution implementation distinct. SQL is a backend, not the product API.
- Recipes select and compose facts. Do not hide one-off question routing or a
  second programming language in YAML. Reuse before adding an operator/repair.
- Preserve grain, population, time basis, units, visibility and provenance.
  Do not silently substitute a metric or remove an inconvenient requirement.
- Clarification binds typed choices and resumes the request. Verification says
  which checks passed, not that user intent or source truth has been proved.
- Keep one future trusted execution path. No model-authored arbitrary Python,
  SQL execution bypass, hidden model fallback, or unsupported-backend rewrite.
- SQLite-first, not SQLite-shaped. PostgreSQL parity is a P4 gate, not inferred
  from SQL transpilation or SQLite results.

## Implementation and checks

Use English for documentation, comments, issues and PRs. Multilingual test inputs
are intentional. Keep `AGENTS.md` short; `CLAUDE.md` imports it instead of copying it.
Use Python 3.11+ and SQLite 3.37+. P0 tooling is stdlib-only; runtime tests require
`uv sync --locked --python 3.11` from `pyproject.toml` and `uv.lock`.
Legacy requirements files are frozen verification witnesses, not install inputs.
See `docs/fact-kernel.md` for setup,
the strict request contract, resource limits and an offline example.
See `docs/model-integration.md` for the P1.2 fake-transport suite, safe local
configuration and pinned smoke preparation; live mode needs separate approval.

```bash
uv run --locked --offline python -m unittest discover -s tests -v
.venv/bin/python tools/fixture.py build --db .artifacts/p0-local/learningops.sqlite
.venv/bin/python tools/fixture.py check --db .artifacts/p0-local/learningops.sqlite --report .artifacts/p0-local/report.json
```

Build and report paths are exclusive-create. Use a fresh directory on reruns;
do not delete/overwrite evidence to make a run appear clean. These commands are
OFFLINE fixture/kernel checks, not model evaluations. Report P0, P1.1 kernel/CLI
and P1.2 adapter/runner suites separately; protect the original 107 tests.
Run targeted checks while editing. For runtime or evaluation changes, run the
complete offline suite once at closeout, including relevant protected regressions.
For documentation-only or personal-tool configuration changes, use proportionate
syntax, link, configuration and diff checks. Explicit task-specific gates still
apply. Do not duplicate a completed broad gate without a concrete evidence gap;
report failures and checks not run honestly.

## Evidence and improvement

- Keep runtime/model context separate from cases, gold results and reference SQL.
  A coding agent may inspect tests; the evaluated model must not receive gold.
- Never change expectations solely to match a candidate. A semantic/oracle change
  needs an explicit rationale and review, plus a new identity; keep old results.
- Keep correct/partial/wrong, necessary/false refusal, clarification, unassessed,
  operational failure and not-yet-implemented separate. Never rerun until green.
- Record code, fixture/case/oracle/config identities and attempt counts. Capture
  missing evidence as unknown. Synthetic reproduction is not original-source
  confirmation and regression data is not fresh generalization evidence.
- Respect the task's protected/frozen source list and asset identities. Do not
  silently repin old freezes or rewrite historical reports; authorized identity
  changes need new evidence while preserving their historical ancestry.
- Use GitHub Issues for active work. A normal fix needs an issue, regression and
  PR/commit, not a new specification and research program. Extra decision text
  is for changes to semantics, scope, security or architecture.
- Track production code touched, operators/repairs added, config complexity,
  human effort, regressions and repair attempts. Improving the grader itself
  does not establish product improvement. Keep acceptance review independent.

## Finish a task

State changed behavior, commands actually run, results and known limitations.
Link the issue/commit or PR. Distinguish implemented, tested, owner-reviewed and
live-validated. Do not auto-close a real-data defect before source confirmation.
Do not implement the next phase just because a scaffold test passed.
