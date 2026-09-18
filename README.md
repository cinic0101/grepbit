# Grepbit

**V3: bounded analytical questions -> checked facts -> evidence-linked answers.**

Grepbit is being rebuilt around analytical intent rather than an expanding
Text2SQL grammar. Recipes compose facts; SQL is an execution backend. Typed
clarification, explicit limitations and scoped verification are product features.

## Current state

P0 is accepted. The bounded **P1.1 offline fact kernel** on `dev` accepts explicit
requests for four reviewed LearningOps metrics, compiles their runtime bindings
with SQLGlot and returns scoped Fact Packs from read-only SQLite.
It does **not** implement a natural-language resolver, recipe engine, model
client, PostgreSQL adapter, API or MCP server. P1.1 does not complete P1.

The seed has 10 tables and 88 rows. There are 30 authored case descriptions:
18 reference-SQL checks and 12 behavioral scenarios awaiting implementation.
Passing fixture checks is NOT passing 30 product cases or a live model eval.
No legacy data, question text, business mapping or production code was imported.

## Offline quick start

Requires Python 3.11+ with SQLite 3.37+ (STRICT tables). P0 fixture tooling remains
stdlib-only; the kernel and its tests require the single pinned dependency.
After installation, the checks and example need no credentials or network.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
mkdir -p .artifacts
run_dir=$(mktemp -d .artifacts/learningops-local-XXXXXX)
.venv/bin/python tools/fixture.py build --db "$run_dir/learningops.sqlite"
.venv/bin/python tools/fixture.py check --db "$run_dir/learningops.sqlite" --report "$run_dir/report.json"
.venv/bin/python -m grepbit --db "$run_dir/learningops.sqlite" \
  --request examples/march-facts.json --output "$run_dir/facts.json"
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
| [P1.1 fact kernel](docs/fact-kernel.md) | Explicit request contract, installation, example and bounded execution guarantees |
| [LearningOps](evals/fixtures/learningops/README.md) | Schema, reviewed-for-development semantics and limitations |
| `evals/cases/`, `evals/oracles/` | Evaluator-only material; never model context |
| `tools/fixture.py`, `tests/` | Offline fixture utilities; not production execution |
| `grepbit/`, `requirements.txt` | Offline scalar runtime and its pinned SQLGlot dependency |

## Development and execution

Implement on `dev`, review before merging into `main`. GitHub Issues are the
single active-work tracker. The roadmap is not a second chronological work log.
Track roadmap #1 and the bounded P1.1 implementation in #6; P0 history is in
#2, #3, #4 and merged PR #5.
All project documents and issue/PR text are English; fixture questions may be
multilingual. A future real-data pilot is distinct from this synthetic regression
family and must protect private data.

Live LiteLLM/Gemma or AWS Bedrock evaluations are triggered by the owner and run
by their local coding agent. There is no remote CLI bridge, model invocation,
cloud credential configuration or live workflow in this scaffold. Prepare a
bounded request first; never infer authorization from an available key.

License: [Apache-2.0](LICENSE).
