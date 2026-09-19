# Grepbit

**V3: bounded analytical questions -> checked facts -> evidence-linked answers.**

Grepbit is being rebuilt around analytical intent rather than an expanding
Text2SQL grammar. Recipes compose facts; SQL is an execution backend. Typed
clarification, explicit limitations and scoped verification are product features.

## Current state

P0 and P1.1 are accepted. The bounded **offline fact kernel** accepts explicit
requests for four reviewed LearningOps metrics, compiles their runtime bindings
with SQLGlot and returns scoped Fact Packs from read-only SQLite.
**P1.2** adds a thin local LiteLLM / `gemma-4-31b` interpretation adapter and
a network-free preparation command for a 12-input trilingual smoke.
The first authorized live smoke (#10) completed 12 HTTP attempts, all rejected
at response-envelope validation; multilingual interpretation remains unassessed.
P1.3a (#11) normalizes provider metadata offline while keeping the FactRequest
contract strict. Another live run requires separate owner authorization.
This is not a general natural-language resolver, recipe engine,
PostgreSQL adapter, API or MCP server; P1 is not complete.

The seed has 10 tables and 88 rows. There are 30 authored case descriptions:
18 reference-SQL checks and 12 behavioral scenarios awaiting implementation.
Passing fixture checks is NOT passing 30 product cases or a live model eval.
No legacy data, question text, business mapping or production code was imported.

## Offline quick start

Requires Python 3.11+ with SQLite 3.37+ (STRICT tables). P0 fixture tooling remains
stdlib-only; the kernel and adapter tests use the pinned dependencies.
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
| [P1.2 model integration](docs/model-integration.md) | Local credential configuration, strict adapter and unexecuted smoke command |
| [LearningOps](evals/fixtures/learningops/README.md) | Schema, reviewed-for-development semantics and limitations |
| `evals/cases/`, `evals/oracles/` | Evaluator-only material; never model context |
| `tools/fixture.py`, `tools/smoke.py`, `tests/` | Evaluator-only checks, smoke preparation/grading and offline regressions |
| `grepbit/`, `requirements.in`, `requirements.txt` | Scalar runtime, thin model adapter and pinned dependency closure |

## Development and execution

Implement on `dev`, review before merging into `main`. GitHub Issues are the
single active-work tracker. The roadmap is not a second chronological work log.
Track roadmap #1 and P1.2 in #8; accepted P1.1 is #6 / PR #7.
P0 history is in #2, #3, #4 and merged PR #5.
All project documents and issue/PR text are English; fixture questions may be
multilingual. A future real-data pilot is distinct from this synthetic regression
family and must protect private data.

Live LiteLLM/Gemma or AWS Bedrock evaluations are triggered by the owner and run
by their local coding agent. There is no remote CLI bridge, cloud fallback or
live CI workflow. Smoke defaults to offline preparation, not model invocation.
Prepare a bounded request first; never infer authorization from an available key.

License: [Apache-2.0](LICENSE).
