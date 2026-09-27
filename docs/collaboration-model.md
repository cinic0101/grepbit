# Collaboration model (as of 2026-09-27)

How the owner and the coding agent work together on Grepbit after the
2026-09-25 process change (#79) and the 2026-09-27 restructure decision (#87).
`AGENTS.md` is the authority; this page is the explanation a new agent needs
to apply it without reading the history. Where the two disagree, `AGENTS.md`
wins.

## 1. Roles

| Role | Who | Decides | Does not decide |
| --- | --- | --- | --- |
| Owner | the repository owner, in the CLI session (Traditional Chinese) | goals, approvals, grants and budgets, semantic contract, gold/oracle/case text, product promises, `main`, deletions, real-data boundary | day-to-day implementation |
| Implementing agent | the coding agent in the owner's local CLI | implementation, tooling, tests, docs, dev-tier authoring, PRs, merges into `dev` after review, GitHub records | anything in the owner column; semantic acceptance of golden cases |
| Fresh-context reviewer | a sub-agent session spawned per PR with no access to the implementing conversation | blocker / no blocker on the actual GitHub diff | merge |
| Independent author / reviewer / ratifier | sub-agent sessions for golden and holdout panels | question text, oracles, novelty, translation equivalence | implementation |

Nothing is delegated to a remote agent, hosted reviewer or remote-control
bridge; every step runs in the owner's local CLI.

## 2. How decisions are made and recorded

- The owner decides in chat. The agent records each decision, approval or
  grant on the relevant issue or PR **verbatim** (the owner's words in the
  original language, quoted) plus an English rendering, dated and attributed
  "owner decision given in chat, recorded by the agent". The agent never
  records a decision the owner did not give; the owner may void or amend one
  by saying so, recorded the same way.
- GitHub is the record, chat is not retained. Issue labels: `decision`
  (ADR form: context, options, decision, consequences), `defect` (issue,
  regression, PR), `evidence` (run index entry, identities, claim level).
  One tracking issue per goal (#79 for the 31B goal, #87 for the
  restructure).
- Agent-drafted proposals (tables, matrices, budgets) are proposals until the
  owner's approval is recorded.

## 3. Goal-scoped delegation and grants

- The owner delegates a goal through a goal issue plus a standing grant
  recorded on it. Inside the grant the agent proceeds without per-step
  approval and reports at milestones and stops.
- A grant names the tool, the allowed steps, providers/routes, data boundary
  (synthetic LearningOps only unless the owner says otherwise), route
  attestation (retries, fallback and cache disabled), bounds (calls per day,
  runs per step, time per call) and stop conditions.
- Current grants: #79 (frozen panel and holdout runs, per-step run counts;
  see the issue for what is used) and #87 comment 5852775731 (dev-tier runs
  on the 31B route, at most 1,000 calls per day).
- Every live run binds one grant comment and one exclusive `.artifacts/`
  slot before credentials are read; the run executes from a merged `dev`
  commit whose digest the run record keeps.

## 4. Mandatory stops (report before changing, then wait)

A needed change to a protected or frozen source, an oracle, gold or case
text, a product promise or accepted product contract, or authority text
(`AGENTS.md`, `CLAUDE.md`, `docs/local-execution.md`); a third candidate
fix on one failure family; budget exhaustion; any credential, route or
privacy anomaly; a reviewer blocker still open after one fix round;
evidence that the goal is unreachable as stated. Authority text is approved
by the owner in session, recorded, and still reviewed before merge.

## 5. Change flow for one tracked change

1. Branch from `dev` in a worktree (`uv sync --locked --offline --python
   3.11`; create `.artifacts/`).
2. For a new or changed contract: commit the contract document and the
   rulers first (failing), then the implementation (passing), in the same PR.
3. Run the full offline suite (`uv run --locked --offline python -m unittest
   discover -s tests`, about 1,200 tests, about 4 minutes) and `git diff
   --check`; record counts on the PR.
4. Open the PR with: scope and risk category, changes and evidence, commands
   actually run, P3 impact review, boundaries checklist, review focus.
5. Spawn a fresh-context reviewer with only the PR reference, objective and
   review focus; it reads the GitHub diff and `dev` files through `gh`,
   discloses its context, and reports blocker / no blocker with file:line
   evidence. Fix should-fixes, ask the same reviewer to re-check the delta.
6. Record on the PR: category, focus, disclosure, verdicts, dispositions,
   checks on the final head. Merge into `dev` (squash) after no blocker plus
   the full suite; `main` stays owner-only. A step the goal's table assigns to
   the owner waits for the owner's merge or an in-session "merge".
7. Remove the worktree; record the milestone on the goal issue.

## 6. Evidence tiers and claims

| Tier | Who authors | Exposure | Claim a run can make |
| --- | --- | --- | --- |
| dev | the agent (`tools/build_dev_panel.py`, `evals/dev/`) | `design_seen` or `exposed_regression` | `development_observation`; unlimited iteration; recorded only when cited |
| regression | frozen historical panels | `exposed_regression` | `observed_regression`, compared against a baseline |
| holdout / golden | independent author + reviewer sessions, owner ratifies | `frozen_fresh` | `fresh_holdout_observation` once per panel and route, then regression |

The claim is derived by `tools/evaluate.py` from the tier and the run index;
nothing here is promotion. Gold, oracles and case text are never changed to
fit a candidate; a justified change gets a new identity and keeps old
results. The implementing agent never reads fresh question text; the
coverage matrix (`docs/coverage-matrix.md`) says what the panels must cover.

## 7. Registries the agent maintains

- `evals/candidates/` — semantic identity of every runtime candidate
  (`tools/candidate_registry.py register --id … --note …` after any prompt,
  context, schema or limit change; then update `EXPECTED_CURRENT` /
  `EXPECTED_ENTRIES` in `tests/test_candidate_registry.py`). Append-only; a
  modified existing entry is a review blocker.
- `evals/panels/index.json`, `evals/routes/index.json` — panels with tier and
  pinned digests, routes with provider and model.
- `evals/runs/index.jsonl` — append-only run records (`tools/evaluate.py
  --record` after offline readback), committed with the evidence they cite.
- `STATE.md` — generated (`tools/state.py --write`) from the above; a ruler
  keeps it current.

## 8. Live run procedure (any tier)

```bash
.venv/bin/python tools/evaluate.py --prepare --candidate <id> --panel <id> --route <id> \
  --db .artifacts/p381-db-LU2Jft/learningops.sqlite --accepted-commit <merged dev sha> \
  --gateway-retries disabled --gateway-fallback disabled --gateway-cache disabled \
  --output-dir .artifacts/<fresh-packet-dir> [--baseline <prior report.json>]
.venv/bin/python tools/evaluate.py --bind-authorization --packet <packet>/manifest.json \
  --owner-authorization-reference <grant comment URL> \
  --output .artifacts/<fresh-slot>/authorization.json --run-output-dir .artifacts/<fresh-slot>/run
.venv/bin/python tools/evaluate.py --live … --env-file .env --output-dir .artifacts/<fresh-slot>/run
.venv/bin/python tools/evaluate.py --report --report-path .artifacts/<fresh-slot>/run/report.json
.venv/bin/python tools/evaluate.py --record --report-path …   # only when the run is cited as evidence
```

The packet pins the run index; any commit to `dev` between prepare and live
makes the packet stale by design (`accepted_commit_required` or
`manifest_drift`): prepare again on the new head. Never print keys, endpoints
or raw completions; reports carry closed fields only.

## 9. Working with this owner

- Reply in Traditional Chinese; be blunt; give numbers with their caveats;
  distinguish implemented / tested / reviewed / live-validated.
- Report at milestones and stops, not per step; ask only when a reading
  would materially change the work.
- The owner approves in chat and expects the agent to keep GitHub complete;
  do not ask the owner to type on GitHub.
- Budget: the owner watches token usage; keep replies short and stop cleanly
  with a handoff when asked (`docs/handoff-<date>.md`).

## 10. Session start checklist

1. Read `README.md`, `STATE.md`, the latest `docs/handoff-*.md`, then the
   open goal issue(s) with label `decision` or `evidence`.
2. `uv sync --locked --offline --python 3.11`; `mkdir -p .artifacts`;
   confirm `.venv/bin/python tools/state.py --check` and
   `tools/candidate_registry.py check` pass on `dev`.
3. Confirm the local archives the registries pin exist
   (`.artifacts/p381-db-LU2Jft/learningops.sqlite`, the frozen formal and
   holdout freezes); without them regression and holdout runs cannot prepare.
4. Pick up the first open item in the handoff; open a worktree; follow §5.
