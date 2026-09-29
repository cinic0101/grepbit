# Grepbit

**V3: bounded analytical questions -> checked facts -> evidence-linked answers.**

Grepbit interprets a request, validates its analytical intent and executes
reviewed facts through a read-only SQLite kernel. Overview, Compare and
Breakdown compose those facts; typed clarification and explicit decline keep
unsupported requirements visible. SQL is an execution backend.

## Start here

Read [STATE.md](STATE.md) for the registered candidate, panels, routes and
latest recorded results. GitHub holds active decisions and evidence:
[restructure #87](https://github.com/cinic0101/grepbit/issues/87) and the
[31B goal #79](https://github.com/cinic0101/grepbit/issues/79).
[The collaboration model](docs/collaboration-model.md) explains the workflow;
[AGENTS.md](AGENTS.md) is the authority.

The latest measured v7 evidence is 27/28 frozen regression and 17/18 holdout A
re-observation, with one remaining Compare failure and one new count-clarification
regression. Its 54/54 dev result covers 51 unchanged cases plus three explicit
C4 variants; the three original broad-revenue C4 variants remain unresolved and
unmeasured on v7. See the [evidence and denominator audit](docs/v7-regression-audit.md).

The 24-input control baseline scored 20/24 on v7. The registered v8
Compare-only context candidate scored 19/24: zero fixed failures and one new
regression. Its required control gate failed; the conditional 54/28/18 runs
were not executed. Count controls did not reproduce HA02's false decline.
v8 remains a failed development candidate, not an accepted improvement. See the
[bounded comparison checkpoint](docs/bound-compare-context-v8.md).

The primary route is Gemma 4 31B through local LiteLLM. Bedrock Sonnet is a
comparison/diagnostic control. P0/P1 and bounded P2 are accepted; P3 quality
remains open. Grounding, clarification resume, synthesis, PostgreSQL parity
and real-data transfer have separate gates. The current synthetic results
do not establish those capabilities or promotion to `main`.

## Evaluation and iteration

New evaluations use [one runner](docs/evaluation-runner.md),
`tools/evaluate.py`, with a registered candidate, panel and route.
[Candidate registration](docs/candidate-registry.md) records prompt, context,
schema, limits and wire identities, preserving prior candidates and reports.

| Tier | Purpose | Permitted claim |
| --- | --- | --- |
| dev | Agent-authored, exposed questions for developing and diagnosing candidates | Development observation |
| regression | Frozen historical questions, compared with a pinned baseline | Observed regression |
| holdout / golden | Independently authored and reviewed questions; exposure tracked | One fresh observation per panel and route, then regression |

The [coverage matrix](docs/coverage-matrix.md) guides dev and independent
panel authoring. Gold and oracles never change to fit a candidate. Run results
are recorded in `evals/runs/index.jsonl`; regenerate `STATE.md` after registry
or run-index changes. Current counts and evidence digests belong there,
while grants, remaining budgets and owner decisions belong on the goal issue.

Live execution requires an owner grant, a merged `dev` identity and one bound
output slot. Preparation and offline checks do not authorize model calls.
See [local execution](docs/local-execution.md) and the
[roadmap](docs/roadmap.md) for gates and stopping rules.

## Offline quick start

Requires `uv` and Python 3.11+ with SQLite 3.37+ (STRICT tables). P0 fixture
tooling remains stdlib-only; `pyproject.toml` declares the runtime dependencies
and `uv.lock` pins their complete closure. After `uv sync`, the checks and
example need no credentials or network.

```bash
uv sync --locked --python 3.11
uv run --locked --offline python -m unittest discover -s tests -v
mkdir -p .artifacts
run_dir=$(mktemp -d .artifacts/learningops-local-XXXXXX)
uv run --locked --offline python tools/fixture.py build --db "$run_dir/learningops.sqlite"
uv run --locked --offline python tools/fixture.py check --db "$run_dir/learningops.sqlite" --report "$run_dir/report.json"
uv run --locked --offline python -m grepbit --db "$run_dir/learningops.sqlite" \
  --request examples/march-facts.json --output "$run_dir/facts.json"
```

`uv sync` creates `.venv`; existing `.venv/bin/python` examples still use that
environment. The legacy requirements files remain byte-identical frozen
verification witnesses, not installation inputs. See the
[dependency-management boundary](docs/fact-kernel.md#dependency-management).

Use a new output directory on each rerun: existing DBs/reports are never replaced.
An interrupted/unreadable report is not success. Generated databases and reports
are ignored by Git; rebuild from the committed source instead of committing a DB.

## Project map

| Path | Purpose |
| --- | --- |
| [STATE.md](STATE.md) | Generated candidate, panel, route and result summary |
| [Architecture](docs/architecture.md), [roadmap](docs/roadmap.md) | Product boundaries and phase exits |
| [P3 contract](docs/p3-evaluation-contract.md), [clarification](docs/clarification-action.md) | Accepted action, scoring and clarification semantics |
| [Fact kernel](docs/fact-kernel.md), [recipes](docs/p2-recipes.md), [grouped amount](docs/grouped-amount.md) | Deterministic execution contracts |
| [Model integration](docs/recipe-model-integration.md) | Shared recipe interpretation and native execution |
| [Evaluation runner](docs/evaluation-runner.md), [candidate registry](docs/candidate-registry.md) | Current evaluation entry and identities |
| [Coverage matrix](docs/coverage-matrix.md), [independent authoring](docs/p3-fresh-case-authoring.md) | Panel coverage and independent acceptance |
| [LearningOps](evals/fixtures/learningops/README.md) | Synthetic schema, definitions and source limitations |
| `grepbit/` | Runtime and provider adapters |
| `evals/candidates/`, `evals/panels/`, `evals/routes/`, `evals/runs/` | Registries and append-only run index |
| `evals/cases/`, `evals/oracles/`, `evals/p3/`, `evals/dev/` | Evaluator-only assets; never model context |
| `tools/evaluate.py`, `tools/candidate_registry.py`, `tools/state.py` | Evaluation, candidate registration and handoff generation |
| `tools/`, `tests/` | Shared evaluator/kernel checks and offline regression suite |
| [Historical records](docs/history/README.md), `tools/history/`, `tests/history/` | Prior phase documents, archive readers and their regressions |
| `pyproject.toml`, `uv.lock` | Active dependencies and reproducible offline environment |
| `requirements.in`, `requirements.txt` | Byte-preserved frozen witnesses; not install inputs |

## Development

Work on `dev` or a branch based on it. Follow [AGENTS.md](AGENTS.md) for
contract checkpoints, fresh-context review, Git permissions and live grants.
`main` is owner-only. The full offline suite discovers both current and
historical tests. Passing it is not a model evaluation, semantic acceptance
or original-source confirmation.

The LearningOps fixture has 10 tables and 88 rows, with 18 reference-SQL
checks and 12 behavioral scenarios. The fixture checker still marks those
scenarios `not_implemented`; runtime and model-adapter tests are separate.
The [offline example](examples/march-facts.json) remains supported.
All documentation, issues and PRs use English; multilingual test inputs are
intentional. Local archives under `.artifacts/` stay outside Git.

License: [Apache-2.0](LICENSE).
