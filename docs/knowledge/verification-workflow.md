# Reproducible local verification

Use the locked Python 3.12 `.venv`. These tools run installed local dependencies;
they do not install packages, source `.env`, start Docker or invoke a live model.
Use the current work record to resolve existing external authorization.

## Validation profiles

```sh
.venv/bin/python tools/verify.py focused \
  --tests tests/contract/g7/test_baseline_materialization_characterization.py \
  --output .artifacts/example-focused
.venv/bin/python tools/verify.py offline --output .artifacts/example-offline
.venv/bin/python tools/verify.py static --output .artifacts/example-static
```

| Profile | Commands and scope |
|---|---|
| `focused` | Explicit Python test files/node IDs under `tests/`; no PostgreSQL flags |
| `offline` | Full pytest without PostgreSQL flags; skips are reported |
| `static` | Ruff lint, format check and `git diff --check` |
| `postgres` | Full pytest with the G1/G2/G3 fixture flags |

PostgreSQL profiles require the already-authorized disposable `compose.g1.yaml`
fixture to be running, plus `--allow-postgres`. That flag acknowledges the scope;
it is not user permission and does not create infrastructure. Follow AGENTS for
fixture ownership and removal. No profile enables older, unselected live or
PostgreSQL configurations. Ambient PostgreSQL flags and pytest option/plugin
overrides are cleared before launching a profile.

Every output directory must be new. The tool saves `command-*.log`, `junit.xml`
for pytest, and `result.json` with commands, exit codes, elapsed time, exact test
counts and before/after source identity. Relevant Python, configuration, spec,
cases, fixtures, semantic and release-pack inputs participate in source identity.
Missing or unsupported source identity cannot produce PASS.

Run a long profile once in a resumable tool execution session. If the tool yields
a session ID, poll that session until its final exit; do not start another copy.
An optional `--timeout` bounds each child command and terminates its process group.
A runner killed before finalization may leave logs without `result.json`; that
is incomplete validation. Logs may include local test diagnostics and should not
be pasted into model-visible reports without checking their permitted content.

PASS requires completed successful commands and consistent source identity. For
pytest, JUnit counts must match actual testcases and at least one test must run.
Missing/malformed counts, all-skipped runs, interruption and timeout cannot PASS.
Partial skips must still be reviewed against the claim: an offline PASS is not
PostgreSQL evidence, and test PASS is not evaluator or product release PASS.
