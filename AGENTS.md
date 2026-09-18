# Grepbit working agreements

## Start here

Read `README.md`, then the current GitHub issue. Read only the relevant design
section in `docs/`; do not reload the legacy research history for every task.
This is V3: analytical intent -> checked facts, not another expanding Text2SQL
language. P0 fixture tooling is separate from the bounded P1.1 scalar kernel.
P1.2 adds a thin model adapter and offline smoke preparation, not P1 acceptance
or authorization to begin P2 or make live requests.

## Authority and branches

- Work on `dev` (or a task branch based on `dev`). Never commit to, merge into,
  or force-push `main` without explicit owner approval. Preserve unrelated work.
- A repository instruction is not permission to make external calls. Live runs
  are owner-triggered and executed by the owner's local coding agent only.
- Do not invoke LiteLLM, Gemma, Bedrock, external databases, remote runners, or
  paid services merely because credentials or an issue are available. Do not
  add scheduled/live GitHub Actions or a remote-control bridge.
- For a live run, prepare the exact command, code/source identity, case IDs,
  provider, allowed data, attempt/token/time bounds, output location and stop
  conditions. The owner authorizes that run separately. See `docs/local-execution.md`.
- Never print or commit keys, connection strings, local endpoint addresses,
  environment dumps, real customer data or unreviewed live traces.

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
the pinned `requirements.txt` dependencies. See `docs/fact-kernel.md` for setup,
the strict request contract, resource limits and an offline example.
See `docs/model-integration.md` for the P1.2 fake-transport suite, safe local
configuration and pinned smoke preparation; live mode needs separate approval.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/fixture.py build --db .artifacts/p0-local/learningops.sqlite
.venv/bin/python tools/fixture.py check --db .artifacts/p0-local/learningops.sqlite --report .artifacts/p0-local/report.json
```

Build and report paths are exclusive-create. Use a fresh directory on reruns;
do not delete/overwrite evidence to make a run appear clean. These commands are
OFFLINE fixture/kernel checks, not model evaluations. Report P0, P1.1 kernel/CLI
and P1.2 adapter/runner suites separately; protect the original 107 tests.
Run targeted checks while editing and the complete small offline suite before
handoff. Report failures honestly.

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
