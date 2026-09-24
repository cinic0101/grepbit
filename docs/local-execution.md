# Owner-triggered local execution

## Current policy

The owner explicitly chose manual authorization and execution by their local
coding agent. This repository does not establish a connection from ChatGPT to a
local Codex/Claude CLI. Do not add a remote-control bridge, AWS OIDC setup, live
GitHub Actions, scheduled runs or model-calling CI as part of this scaffold.

P0 and P1 are accepted. For the offline kernel, dependency setup, example
and separate P0/kernel test commands, see [the fact-kernel guide](fact-kernel.md).
Installing its pinned Python dependency is not a live evaluation.

P1 implements the owner's selected local LiteLLM / `gemma-4-31b` path. The
separately authorized first smoke (#10) failed envelope compatibility; after
P1.3a, the second smoke (#13) passed 12/12 inputs across four semantic families.
These completed authorizations do not permit more calls. See the
[integration guide](model-integration.md) for `.env.example`, explicit
`--env-file` behavior, offline preparation and the implemented live command.
The default/dry-run loads no credentials and makes no network calls. An offline
[Bedrock Converse adapter](p3-provider-adapters.md) is available for future
candidate tooling, but the historical runners remain pinned to LiteLLM. Bedrock
is not a fallback or an admitted live candidate. Formal measurement starts at P3.
P2.0 is [design/admission only](p2-recipes.md), not recipe execution or live
authorization.

[P2.7 recipe-runner tooling](recipe-smoke.md) has two offline gates: candidate
implementation/review, then a fresh final manifest on the clean accepted dev
merge commit after owner merge. A feature-branch manifest is never eligible for
live reuse. Neither gate permits a model call; explicit live authorization and
fresh route-policy attestations remain separate.

The coding agent used to edit this repository is distinct from the model being
evaluated. Authorization to develop code is not authorization to send fixture or
real-data context to a model endpoint or to consume API/GPU resources for an eval.

## Historical P0 reproduction task

This preserves the fixture-only reproduction procedure, not a request to repeat
P0 acceptance or a new authorization. Full test discovery now includes the
SQLGlot-dependent kernel tests; the explicit P0 selector below remains stdlib-only.

```text
Work in cinic0101/grepbit on dev. Read AGENTS.md, README.md and the current P0
issues. Inspect git status before any branch change; preserve unrelated work.
Fetch/switch/fast-forward dev only if the worktree is clean and it is safe.
Do not modify or merge main, force-push, or alter existing evidence.

For this task, run only the stdlib offline fixture checks. Do not call LiteLLM,
Gemma, Bedrock, another model endpoint, any external database, or a remote runner.
Do not inspect, print or upload credentials or environment dumps.

Run the commands below in a fresh output directory. Review whether the schema,
semantic definitions and 30 authored cases agree. Separate 18 reference-SQL
checks from 12 unimplemented behavioral scenarios. Do not change gold to make a
check pass. Return commit/dirty state, command results, source hash, limitations
and proposed issues. Do not start P1 or a live run without separate authorization.
```

From the repository root after safely updating `dev`:

```bash
git status --short
git rev-parse HEAD
PYTHONPATH=tests python3.11 -m unittest test_fixture test_multilingual_cases test_review_witnesses -v
python3.11 tools/fixture.py build --db .artifacts/p0-local/learningops.sqlite
python3.11 tools/fixture.py check --db .artifacts/p0-local/learningops.sqlite --report .artifacts/p0-local/report.json
```

Existing output paths are intentionally refused. Use another fresh directory,
not deletion/overwrite. Exit code 0 means the selected offline checks passed,
not that P0 was human-reviewed or that the product/model works.

## Standing grant for a delegated goal

When the owner delegates a goal (see `AGENTS.md`, "Goal-scoped delegation"),
one comment on the goal issue is the standing grant. It states, in one place:
the goal, the allowed step sequence (for example compatibility call, observed
panel, diagnostic), the provider and profile for each step, the maximum number
of runs per step, per-call and per-run time bounds, output token caps, the
data boundary (synthetic only unless stated), the stop conditions and the
reporting expectation. Each tool still binds every run to one authorization
envelope and one exclusive output slot, so the grant is consumed run by run
and cannot be replayed; the agent records each run's factual result under the
issue that owns that step. A run outside the listed steps or above the listed
counts is not covered and needs a separate authorization. The owner may revoke
the grant at any time by saying so; runs already recorded stay as evidence.

## Live run authorization procedure

Before the owner initiates each live run, provide:

| Field | Required information |
| --- | --- |
| Identity | Issue, reviewed commit/source digest, cases/scenarios, semantic/recipe/prompt versions |
| Provider | One explicit local alias or Bedrock model/profile; no hidden fallback |
| Data boundary | Synthetic-only initially; allowed schema, questions, facts and output fields |
| Limits | Case IDs, repetitions, max actual attempts/retries, input/output token caps, wall-clock timeout, concurrency |
| Stop rules | Budget exhaustion, unexpected data/config drift, leakage risk, repeated transport failure |
| Execution | Exact implemented command, environment variable NAMES only, fresh private output path |
| Return | Safe summary, counts, observed model identity, token/latency data, errors/stop reason and source confirmation needs |

A CLI flag alone is not authorization: the P1.2 runner enforces a pinned panel
and bounds every client attempt, but upstream inference counts remain unknown.
The owner must confirm the selected gateway route's retry/fallback/cache policy
before authorizing a live run. Authentication failure must not
print headers, environment values or verbose SDK traces. Do not fall back from
local to cloud on failure, particularly for real data.

Credentials stay in the owner's secret store/environment. Prefer provider-native
short-lived credentials where available, but configure them locally only after
owner authorization. Do not create keys or ask for them in chat/public issues.

Review safe output before returning it. Git-ignored is not equivalent to redacted.
Do not upload full raw traces automatically. ChatGPT may analyze a sanitized
report and prepare a fix/next bounded request; it does not imply the next run is
authorized. The owner may stop or decline any live run.
