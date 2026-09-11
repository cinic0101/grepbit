# grepbit: working rules for agents

Read `docs/knowledge/README.md` for the architecture and `docs/plan/` for
what is being built. The owner writes in Traditional Chinese; report in it,
with numbers and caveats, and end every slice with scope, files changed,
validation counts, known gaps, git state.

## Rules that came from mistakes

- **Commit only when both gates pass, in one line:**
  `uv run ruff check src tests evals; R=$?; uv run pytest -q; T=$?; test $R -eq 0 -a $T -eq 0 && git add -A && git commit ...`
  A commit gated on pytest alone shipped lint errors twice on 2026-09-11.
- **Never edit `src/` or `evals/` while a regression is running.** The runner
  starts one process per set and imports the tree at start; an edit midway
  changes what later sets measure. Check `ps aux | grep spike_tier0` first.
- **One agent session per working tree.** Two sessions wrote to the same tree
  on 2026-09-11 (one had crashed and restarted). For parallel work use
  `git worktree add`.
- **Raise design questions at once** (a construct's semantics, anything that
  changes what a user sees, a trade-off the evidence does not settle) and
  discuss or verify with the owner before choosing. Routine engineering is
  delegated.
- **Freeze new algebra constructs until shape repairs are under 5% of cases**
  (decision of 2026-09-11, `docs/plan/root-cause-program.md`).

## Evidence and process

- Every number in a report has an artifact under `evidence/`; judged runs on
  real questions stay in `.artifacts/` (never in git) with SHA-256 in
  `evidence/README.md`.
- A prompt change bumps `PLAN_PROMPT_REVISION` and reruns every case set that
  could move; the author sets are smoke tests, the owner's questions are the
  holdout: never read them before a run, never tune for them.
- Real-database runs use `--enum-distinct-limit 0 --redact-rows`.
- Adding a construct means filling its row and column in the construct matrix
  of `docs/knowledge/tier0-contract.md` before merging.

## Boundaries and secrets

- `sqlglot` only under `src/grepbit/adapters/sqlglot/`; the domain imports
  nothing but the standard library and pydantic (`tests/contract/test_module_boundaries.py`).
- Credentials never in files or output: `set -a; . ./.env; set +a`; DSNs are
  composed in the shell and passed by name with `--dsn-env`.
- Never push unless asked. Work on `dev`.
