# Coding-Agent Guide (grepbit)

The one rules file. `CLAUDE.md` imports it; do not maintain two copies.

## Mission

One question, one governed query, an honest answer. The model chooses
identifiers and typed literals inside a closed algebra (`QueryPlan`); the
server owns the schema, the SQL, the execution and the evidence. Every answer
carries a verification level and its assumptions, or a typed refusal
(`clarify`, `semantic_gap`, `unsupported`, `unsafe`). The north star is a
sub-agent other agents call (MCP).

## Read first

1. `docs/knowledge/README.md` (map), then `architecture.md`,
   `tier0-contract.md`, `environment-and-secrets.md`, `local-web.md`.
2. `docs/plan/production-integration-board.md`: the current product
   disposition per capability. `docs/plan/` holds what is being built;
   `docs/research/` holds decisions with their evidence and is history, not
   disposition. `docs/history/lessons-from-v1.md` is what must not repeat.
3. `git status --short`, `git log -5 --oneline`, and `ps aux | grep -E
   "spike_tier0|dev_web|differential"` before touching anything.

## Working with the owner

- The owner writes Traditional Chinese. Report in it, bluntly, with numbers
  and their caveats. Every slice ends with: scope, files changed, validation
  counts, known gaps, git state.
- **Raise design questions at once**: a construct's semantics, anything that
  changes what a user sees, a trade-off the evidence does not settle. Discuss
  or verify with the owner before choosing. Routine engineering is delegated.
  "One line to revert" is not approval.
- A slice that makes live model calls gets a short plan (outcome, scope,
  case set, call budget, acceptance and stop conditions) and the owner's go
  before the first call. When time is short, ask before long runs.
- Keep six counts apart and never sum them into one score: correct answers,
  wrong answers, necessary refusals, false refusals, unassessed outcomes,
  operational failures. The owner's grading words: 合理解讀 + 實際口徑揭露 +
  相關額外欄 (a reasonable reading, the effective definition disclosed, extra
  related columns allowed).

## Rules that came from mistakes

1. **Experiment before feature.** A capability enters `src/` only after a
   measurement says it helps, recorded in `docs/research/` with its artifact
   under `evidence/`. A rejected candidate does not close the capability;
   name the failing layer and choose a materially different approach, a
   smaller delivery, or an explicit block. Do not append prompt variants.
2. **No datasource knowledge in code.** Business meaning lives in the
   overlay (`docs/knowledge/overlay-format.md`), drafted by tooling, signed
   by a reviewer; cross-datasource language packs are data too. No lexical
   exception for one word to make one case pass: the concept gate's
   `Return` and `membership` false refusals stay open until a candidate
   brings new evidence.
3. **The model never writes SQL and never sees rows.** Details mode returns
   rows to the caller, not to the model. A change that needs either stops
   and records the product decision first.
4. **Prompt changes are versioned and re-measured.** Bump
   `PLAN_PROMPT_REVISION` (or the rows revisions) and rerun every case set
   that could move; a prompt tuned to one failing case is reported as such.
   Revision strings are model-visible: renaming one changes outputs, so
   `details-schema-only-v21-study` keeps its name.
5. **Author-written cases are smoke tests.** Only the owner's questions,
   unseen before a run, measure generalisation: never read them before a
   run, never tune for them, and do not relabel known cases as unseen.
6. **Refusing is cheaper than a wrong number.** Never trade a deterministic
   check for a model judgment to make a case pass. Same-model verifiers,
   more samples of the same view, and vocabulary exceptions all have
   negative evidence in `docs/research/`.
7. **Commit only when both gates pass, in one line:**
   `uv run ruff check src tests evals; R=$?; uv run pytest -q; T=$?; test $R -eq 0 -a $T -eq 0 && git add -A && git commit ...`
   A commit gated on pytest alone shipped lint errors twice.
8. **Freeze every fingerprinted input during a live run**: `src/`, `evals/`,
   tests and probe scripts. The runner imports the tree at start; an edit
   midway changes what later sets measure, and a mid-run test edit once
   changed the source digest and stopped a closeout.
9. **One writer per working tree.** Two sessions wrote to the same tree
   twice (2026-09-11, 2026-09-16). For parallel work use `git worktree add`;
   do not copy credentials into another directory.
10. **Freeze new algebra constructs until `shape_variants` stays under 5% of
    cases on every set** (2026-09-11; the metric excludes meaning
    normalisations, which are intended rules). No blanket thaw.
11. **Adding a construct means filling its row and column in the construct
    matrix of `docs/knowledge/tier0-contract.md` before merging.**

## Evidence

- Every number in a report points to an artifact under `evidence/`; reruns
  after a change get a new artifact name and the earlier one stays.
- Judged runs on the owner's questions, raw model outputs and anything with
  row values stay in `.artifacts/` (never in git), with a manifest and
  SHA-256 in `evidence/README.md`. A fresh clone lacks them: say so rather
  than fabricate.
- Reports name the exact case file, prompt revision, model, call count
  (repairs, retries and fallbacks counted), and artifact path. Numbers
  without an artifact are not results.
- Serialize model calls; a run sharing the endpoint with other load is
  marked as inflated.
- Do not carry verdicts with `evals/carry_verdicts.py` until its identity
  gap is closed (same fingerprint, different value).

## Validation

- The commit gate above is mandatory for every commit.
- For a slice closeout that must leave evidence, persist the profiles:
  ```sh
  .venv/bin/python tools/verify.py static  --output .artifacts/<run>/static
  .venv/bin/python tools/verify.py offline --output .artifacts/<run>/offline
  .venv/bin/python tools/verify.py focused --tests <paths> --output .artifacts/<run>/focused
  ```
- Live runs use `evals/spike_tier0.py`; the value oracle is
  `evals/differential.py` (compiled SQL against `evals/reference_eval.py`,
  PostgreSQL or random DuckDB instances). Window boundaries are proven by
  the time-closure golden tests, not by the differential.

## Architecture boundaries

```text
application -> domain
      |
      v
    ports <- adapters
```

- `domain/`: pydantic contracts and pure functions; imports stdlib,
  pydantic, domain only.
- `ports/`: protocols; imports stdlib and domain only.
- `application/`: orchestration; never imports adapters or providers.
- `adapters/`: sqlglot, psycopg, OpenAI-compatible clients, MCP. SQL is
  built only in `adapters/sqlglot/`; `sqlglot` is imported nowhere else.

`tests/contract/test_module_boundaries.py` enforces this; keep it green.

## Secrets and external state

- Credentials never in files or output. `.env` holds `LITELLM_API_KEY`:
  `set -a; . ./.env; set +a`, never print or commit it. The read-only
  password is in `~/.grepbit_spike_ro_password` (mode 600).
- DSNs are composed in the shell and passed by name (`--dsn-env`); programs
  receive variable names, never values. Runtime role `grepbit_ro`, SELECT
  only; setup credentials are never given to application code or model
  calls and never retained.
- Real-database runs: runner `--enum-distinct-limit 0 --redact-rows`,
  differential `--redact --enum-distinct-limit 0`. Neither is universal PII
  redaction; questions, plans and assumptions can still carry values. Never
  write personal names or identifiers to files under version control.
- Live runs go only against fixture databases or databases the owner has
  consented to (today the real POS test copy). Enable a real datasource in
  Details mode (`allow_rows`) only after its column visibility is reviewed.
- Local Web (`tools/dev_web.py`) binds `127.0.0.1` only and needs
  `--confirm-synthetic-fixtures`; it is not authentication.
- Work on `dev`. Commit when authorised; **never push unless asked**.

## Delivery style

Conventional Commits, imperative subject under 72 characters, body for why.
Keep diffs narrow; rewrite tests that pin a superseded contract in the same
commit and say so. Remove a replaced runtime implementation in the same
slice; keep minimal replay adapters and the historical evidence.
