# Grepbit

**V3: bounded analytical questions -> checked facts -> evidence-linked answers.**

Grepbit is being rebuilt around analytical intent rather than an expanding
Text2SQL grammar. Recipes compose facts; SQL is an execution backend. Typed
clarification, explicit limitations and scoped verification are product features.

## Current state

P0 scaffold on `dev`. The repository contains the new fictional **LearningOps**
fixture, reference checks, test tooling, architecture/roadmap and local-agent
instructions. It does **not** yet implement a semantic resolver, recipe engine,
SQLGlot compiler, model client, PostgreSQL adapter, API or MCP server.

The seed has 10 tables and 88 rows. There are 30 authored case descriptions:
18 reference-SQL checks and 12 behavioral scenarios awaiting implementation.
Passing fixture checks is NOT passing 30 product cases or a live model eval.
No legacy data, question text, business mapping or production code was imported.

## Offline quick start

Requires Python 3.11+ with SQLite 3.37+ (STRICT tables). No external dependencies,
credentials or network access are required by the checks.

```bash
python3 -m unittest discover -s tests -v
python3 tools/fixture.py build --db .artifacts/p0-local/learningops.sqlite
python3 tools/fixture.py check --db .artifacts/p0-local/learningops.sqlite --report .artifacts/p0-local/report.json
```

Use a new output directory on each rerun: existing DBs/reports are never replaced.
An interrupted/unreadable report is not success. Generated databases and reports
are ignored by Git; rebuild from the committed source instead of committing a DB.

## Project map

| Path | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md) | Shared coding-agent instructions |
| [Architecture](docs/architecture.md) | Responsibilities, boundaries, reuse policy |
| [Roadmap](docs/roadmap.md) | P0-P5 exits and stopping rules |
| [Evaluation](docs/evaluation.md) | Oracles, outcomes, issues and improvement loop |
| [Portability](docs/portability.md) | SQLite-first and PostgreSQL P4 preparation |
| [Local execution](docs/local-execution.md) | Owner-triggered work and copy/paste handoff |
| [LearningOps](evals/fixtures/learningops/README.md) | Schema, reviewed-for-development semantics and limitations |
| `evals/cases/`, `evals/oracles/` | Evaluator-only material; never model context |
| `tools/fixture.py`, `tests/` | Offline fixture utilities; not production execution |

## Development and execution

Implement on `dev`, review before merging into `main`. GitHub Issues are the
single active-work tracker. The roadmap is not a second chronological work log.
Track roadmap #1 and P0 work items #2, #3 and #4.
All project documents and issue/PR text are English; fixture questions may be
multilingual. A future real-data pilot is distinct from this synthetic regression
family and must protect private data.

Live LiteLLM/Gemma or AWS Bedrock evaluations are triggered by the owner and run
by their local coding agent. There is no remote CLI bridge, model invocation,
cloud credential configuration or live workflow in this scaffold. Prepare a
bounded request first; never infer authorization from an available key.

License: [Apache-2.0](LICENSE).
