# Grepbit

**V3: bounded analytical questions -> checked facts -> evidence-linked answers.**

Grepbit is being rebuilt around analytical intent rather than an expanding
Text2SQL grammar. Recipes compose facts; SQL is an execution backend. Typed
clarification, explicit limitations and scoped verification are product features.

## Current state

P0 and P1 are accepted at `6d6be30bed321806e0a2ef90fec53a1fc1118373`.
The bounded **offline fact kernel** accepts explicit
requests for four reviewed LearningOps metrics, compiles their runtime bindings
with SQLGlot and returns scoped Fact Packs from read-only SQLite.
**P1.2** adds a thin local LiteLLM / `gemma-4-31b` interpretation adapter and
a network-free preparation command for a 12-input trilingual smoke.
The first authorized live smoke (#10) completed 12 HTTP attempts, all rejected
at response-envelope validation; its failures remain preserved. After accepted
P1.3a normalization (#11 / PR #12), the second authorized smoke (#13) passed
12/12 inputs, with all three languages correct in 4/4 semantic families.
This meets the bounded P1 exit, not generalization or broad language-quality
claims. Every future live run still requires separate owner authorization.
This is not a general natural-language resolver, recipe engine,
PostgreSQL adapter, API or MCP server.

**P2.0** (#14 / PR #15) admitted Overview, Compare and Breakdown.
**P2.1** (#16 / PR #17) provides the accepted
[offline scalar Compare](docs/p2-recipes.md#p21-offline-scalar-compare):
two explicit months, one read snapshot, exact difference/relative change and
input-linked evidence. **P2.2** (#18 / PR #19) accepted one
[observed grouped-amount primitive](docs/grouped-amount.md) for category,
booking day and course top-k. **P2.3** (#20 / PR #21) accepted a
[private required/optional composition witness](docs/p2-recipes.md#p23-private-requiredoptional-composition):
one snapshot and global budget, explicit optional gaps, and fail-closed
required/global errors. Component-local timeout semantics are injected, not a
new timer engine. **P2.4** (#22 / PR #23) accepted
[public deterministic Overview](docs/p2-recipes.md#p24-public-deterministic-overview):
strict explicit center-code/month inputs, exact binding in the same snapshot,
and the reused five-slot composition. **P2.5** (#24 / PR #25) accepted
[deterministic Breakdown](docs/p2-recipes.md#p25-public-deterministic-breakdown):
course top-k, an independently executed whole-scope denominator, exact selected
subtotal/share and required-slot evidence. **P2.6** (#26 / PR #27) accepted
[bounded model recipe selection](docs/recipe-model-integration.md):
one shared versioned prompt/contract, one proposal and one unchanged native
recipe execution, with strict parsing and wrong-interpretation visibility.
**P2.7** (#28) adds a [fixed recipe integration runner](docs/recipe-smoke.md):
intent-first grading, separate timeout/network stops and immutable evidence for
nine paired inputs across three families, with separate implementation and
accepted-commit preparation gates. After the preserved #30 format failures and
P2.11 structured-output change (#34 / PR #35), the separately authorized #36
panel passed **9/9**, satisfying the owner-reviewed P2 exit on dev at
`f21c914915f34656c1e8c0069c28afadb5bbc7ae`. This is exposed three-family
regression evidence, not fresh language-quality evidence or promotion to main.
**P3.0** (#37 / PR #38) accepted the [evaluation contract](docs/p3-evaluation-contract.md)
at `a4bad1a8742a97021502e71208bd7162c6b37c44`:
intent/action correctness, checked-fact coverage, explicit clarification/decline
policy and separate stability scoring. **P3.1** (#39 / PR #40) accepted
[bounded clarification](docs/clarification-action.md) on dev at
`e8c3a455bd4e09a266a772be599fe851d405df78`, in the existing
recipe entry: one typed action, no analytical execution on clarify, and
deterministic single-select presentation. P1 and native recipes remain unchanged.
**P3.2** (#41 / PR #42) accepted the [offline evaluator](docs/p3-evaluator.md)
at `20abb5592262c77c98f9cabeaf7cf4854edb6fbe`:
independent action/request/fact grading, family-weighted denominators and
immutable evidence using the unchanged production entry. Its development
fixtures are exposed regressions, not the future fresh/formal panel.
**P3.3** (#43) prepares [independent authoring and formal admission](docs/p3-fresh-case-authoring.md)
against that frozen behavior. Intake/freeze tooling and exposed draft controls
are not an admitted 24/44 panel: independent fresh material and historical
family-distinctness review remain required. No live probe/run or full P3 exit
follows from this preparation; grounding, resume and synthesis remain separate.

The seed has 10 tables and 88 rows. There are 30 authored case descriptions:
18 reference-SQL checks and 12 behavioral scenarios. The fixture checker still
marks those scenarios `not_implemented`; separate runtime tests exercise E01-E03's
deterministic composition, Q11-Q13 grouped witnesses and E10's injected
optional-failure semantics. P2.6 separately checks model-route wiring with fake
transport, not live model quality or the complete behavioral bank.
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
| [P3 evaluation contract](docs/p3-evaluation-contract.md) | Accepted intent matrix, provenance, branch policy, scoring and conditional panel costs |
| [P3.1 clarification action](docs/clarification-action.md) | Closed semantic alternatives, deterministic choices, offline evidence and deferred capabilities |
| [P3.2 offline evaluator](docs/p3-evaluator.md) | Evaluator-only assets, ordered grading, family scoring, immutable evidence and development-only execution |
| [P3.3 independent authoring](docs/p3-fresh-case-authoring.md) | Fresh-author separation, bounded intake/review/freeze, conditional allocation and future probe gates |
| [Portability](docs/portability.md) | SQLite-first and PostgreSQL P4 preparation |
| [Local execution](docs/local-execution.md) | Owner-triggered work and copy/paste handoff |
| [P1.1 fact kernel](docs/fact-kernel.md) | Explicit request contract, installation, example and bounded execution guarantees |
| [P1 model integration](docs/model-integration.md) | Accepted adapter boundaries, smoke history and separately authorized execution |
| [P2 recipe model integration](docs/recipe-model-integration.md) | Shared one-shot recipe contract, native dispatch, safe evidence and offline-only scope |
| [P2 recipe integration runner](docs/recipe-smoke.md) | Fixed evaluator panel, intent-first grading, explicit stops and two-gate manifest preparation |
| [P2 recipes v0.1](docs/p2-recipes.md) | Accepted admission matrix, offline Compare/Overview/Breakdown APIs and shared execution |
| [Grouped amount](docs/grouped-amount.md) | One bounded observed-group primitive, source-extension isolation and coverage |
| [LearningOps](evals/fixtures/learningops/README.md) | Schema, reviewed-for-development semantics and limitations |
| `evals/cases/`, `evals/oracles/` | Evaluator-only material; never model context |
| `tools/fixture.py`, `tools/smoke.py`, `tests/` | Evaluator-only checks, smoke preparation/grading and offline regressions |
| `grepbit/`, `requirements.in`, `requirements.txt` | Checked scalar/grouped runtime, deterministic recipes, thin model adapter and pinned dependencies |

## Development and execution

Implement on `dev`, review before merging into `main`. GitHub Issues are the
single active-work tracker. The roadmap is not a second chronological work log.
Track roadmap #1 and current P3.2 evaluator work in #41; P3.1 was accepted through
#39 / PR #40, P3.0 through #37 / PR #38 and P2 exit after #36.
No future live run or main promotion is implied.
P2.0 design, P2.1 Compare and P2.2 grouping were accepted through #14 / PR #15,
#16 / PR #17 and #18 / PR #19; P2.3 through #20 / PR #21 and public Overview
through #22 / PR #23; deterministic Breakdown through #24 / PR #25; recipe
interpretation through #26 / PR #27. Accepted P1 includes
#6 / PR #7, #8 / PR #9, #11 / PR #12 and the successful smoke #13;
the first smoke's failed envelope results remain in #10.
P0 history is in #2, #3, #4 and merged PR #5.
All project documents and issue/PR text are English; fixture questions may be
multilingual. A future real-data pilot is distinct from this synthetic regression
family and must protect private data.

Live LiteLLM/Gemma or AWS Bedrock evaluations are triggered by the owner and run
by their local coding agent. There is no remote CLI bridge, cloud fallback or
live CI workflow. Smoke defaults to offline preparation, not model invocation.
Prepare a bounded request first; never infer authorization from an available key.

License: [Apache-2.0](LICENSE).
