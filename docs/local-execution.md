# Owner-triggered local execution

## Current policy

The owner explicitly chose manual authorization and execution by their local
coding agent. This repository does not establish a connection from ChatGPT to a
local Codex/Claude CLI. Do not add a remote-control bridge, AWS OIDC setup, live
GitHub Actions, scheduled runs or model-calling CI as part of this scaffold.

Available future candidates: the owner's local LiteLLM/Gemma deployment and AWS
Bedrock. Neither is connected or invoked by this code. There is no live command
to run yet; do not fabricate one. Implement and review a model adapter before
requesting a bounded live smoke in P1/P2. Formal measurement starts at P3.

The coding agent used to edit this repository is distinct from the model being
evaluated. Authorization to develop code is not authorization to send fixture or
real-data context to a model endpoint or to consume API/GPU resources for an eval.

## Copy/paste task for the local coding agent (offline now)

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
python3 -m unittest discover -s tests -v
python3 tools/fixture.py build --db .artifacts/p0-local/learningops.sqlite
python3 tools/fixture.py check --db .artifacts/p0-local/learningops.sqlite --report .artifacts/p0-local/report.json
```

Existing output paths are intentionally refused. Use another fresh directory,
not deletion/overwrite. Exit code 0 means the selected offline checks passed,
not that P0 was human-reviewed or that the product/model works.

## Future live run request (procedure, not implemented CLI)

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

A CLI flag alone is not an authorization or budget boundary: the future runner
must enforce limits and count every attempt. Authentication failure must not
print headers, environment values or verbose SDK traces. Do not fall back from
local to cloud on failure, particularly for real data.

Credentials stay in the owner's secret store/environment. Prefer provider-native
short-lived credentials where available, but configure them locally only after
owner authorization. Do not create keys or ask for them in chat/public issues.

Review safe output before returning it. Git-ignored is not equivalent to redacted.
Do not upload full raw traces automatically. ChatGPT may analyze a sanitized
report and prepare a fix/next bounded request; it does not imply the next run is
authorized. The owner may stop or decline any live run.
