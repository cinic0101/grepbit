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

Continuing in a new session: read the [September 30 handoff](docs/handoff-2026-09-30.md)
for the v9–v12 results, the noise measurement, the unfinished candidate gate and
the current stop boundary. The [September 29 handoff](docs/handoff-2026-09-29.md)
covers the earlier v8 attempt.

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
A 22-input mechanism probe on unchanged v8 scored 8/22. It reproduced an
HA02-class English false decline for attendance-compatible generic counts,
supported a year-placement reading of the BM2 regression, and found a new v8
false clarification of `dev-A3.en`. E02's wording sensitivity is not a robust
lexical factor. See the [mechanism probe](docs/mechanism-probe-controls.md).

The registered v9 candidate restores v7's context and adds one sentence: a
generic people or count noun alone, with no stated basis, leaves the count
meanings unresolved rather than requiring a decline. It withdraws the failed v8
Compare text and does not target E02, which is recorded as a known Gemma 31B
limitation. On the probe, v9 no longer declined the English generic-count
inputs and scored 12/22 (v8: 8/22). It matched v7 on the controls (20/24).
It then failed the 54/54 dev gate at 49/54. `dev-C1` ×3 offered four count
meanings instead of the two the question states, and `dev-A4` zh-TW/en falsely
clarified comparison roles. The sequence stopped before the formal and holdout
runs. v9 is not an accepted improvement. See the
[generic-count checkpoint](docs/generic-count-context-v9.md).

v10 restored v7's exact runtime bytes by owner decision. Its semantic identity
equals v7's; it is not a new fix. v10 has no run of its own, and v7's recorded
results and limitations describe the same wire bytes. See the
[v7 restoration](docs/v7-context-restoration-v10.md).

v11 followed decision #120 (Option C). For an Overview
count, the model reports only a typed count reading: none, a bound meaning, a
contrast or a generic count. A deterministic kernel policy then chooses the
action from a closed table. Bound booked seats execute. Other bound meanings,
contrasts without booked seats and unsupported extra requirements decline.
Other contrasts and generic counts clarify. The model can no longer author a
count-basis clarification. By owner decision, the complete-request cap was
40,960 bytes, and the Bedrock route failed closed for v11. v11 failed its first
gate, the mechanism probe. The count group scored 5/12: `dev-BM6` en/ja and
`dev-MN2` were fixed, but the model marked the unframed `dev-MN1` and `dev-MN3`
headcount questions as booking-framed in every language. Those got three count
choices instead of four. The sequence stopped after 22 calls, the remaining
steps did not run, and v11 is not an accepted improvement. See the
[count cue policy](docs/count-cue-policy.md).

v12 returns to v10's exact runtime bytes, which are
v7's, by owner decision after v11's stop. It is a restoration, not a new fix.
The frozen clarification test, the 32,768-byte request cap and the Bedrock
route are restored; v11 archives stay readable. v7's recorded limitations carry
over. By owner decision, ADR #125 Option A stops the count family. One
authorized confirmation run on the 24-input control scored 20/24, as v7 did.
Twenty-three per-input outcomes matched. `dev-BM6.zh-TW` failed differently on
identical input tokens, so that input's failure mode is not stable. Raw output
length varied on 4 of 24 inputs. Four later authorized noise runs of the same
bytes followed. Both control runs matched the confirmation run input for input,
and the two 22-input mechanism-probe runs matched each other, with 0 flaky
inputs. Against v12, the earlier count fixes changed many inputs: v11 fixed 7
and broke 6 on the probe. That is consistent with their byte changes, but
between-session drift was not measured on the probe and cannot be excluded per
input. See the
[v10 restoration](docs/v10-restoration-v12.md).

v13 implemented the owner's count rule (ADR #136): a
generic people count that names no count meaning is answered with booked
seats and the assumption stated, not clarified. An Overview answer may carry the typed
`assumption` `{"count_basis": "booked_seats"}`, and `count_basis` clarification
is kept for questions that are themselves undecided between named meanings.
The kernel is unchanged, Bedrock fails closed and the 32,768-byte request cap
is kept. Against v12 on the two new v2 dev panels of #138
(`p3-dev-bound-meaning-v2` and `p3-dev-mechanism-probe-v2`), whose annexes
check the assumption, the pre-registered gate verdict is **regression**. One
run per panel fixed all 12 distinct generic people-count inputs, but it broke
6 stable-correct ones: `dev-BM5` in three languages gained a spurious
assumption, and three Compare inputs became false clarifications. Under the
grant that is a stop with no rerun. See the
[v13 contract](docs/count-assumption-v13.md), the
[evaluation side](docs/count-assumption.md) and the
[gate result](docs/count-assumption-v13-result.md).

v14 reverted v13 by owner decision: it returns to
v12's exact runtime bytes (v10's and v7's) and restores the frozen
clarification test, which also reopens the Bedrock route. It is a
restoration, not a new fix, and v12's results are its results. The next change is ADR #142: the model reads a typed Compare
orientation and code decides whether to clarify the roles. See the
[v12 restoration](docs/v12-restoration-v14.md).

v15 implements ADR #142:
- The model returns every two-month comparison as a Compare request with a
  typed `orientation`, `stated` or `unresolved`.
- The code executes a `stated` request. For `unresolved` it builds the
  `comparison_roles` clarification, so the model no longer emits that kind.
- Count behaviour is v12's. The kernel is unchanged, and Bedrock fails closed.
- The pre-registered gate against v12's bytes on the two v2 dev panels is
  **passed**, with one run per panel:
  - it fixed the three stable-wrong Compare inputs (`E02_compare.en`,
    `dev-MC2.en` and `dev-MC4.en`) and broke none;
  - all 22 Compare inputs are correct;
  - v12's 12 wrong count inputs stay wrong.

  This is a development observation, not promotion.

See the [v15 contract](docs/compare-orientation-v15.md) and the
[gate result](docs/compare-orientation-v15-result.md).

v16 implements ADR #146. It applies the same
read-then-decide split to counts:
- Every Overview request carries a typed `count_request`.
- The code states the owner's booked-seats assumption for an `unresolved`
  count, and it declines a named unavailable count.
- A question read as `booked_seats` or `none` states no assumption; one that
  names booked seats gains one only if the model reads it as `unresolved`.
- The model still asks its own `count_basis` clarification when a question is
  undecided between named meanings.
- The pre-registered gate against v15 on the two v2 dev panels is **passed**,
  with one run per panel:
  - it fixed `dev-BM6` (all languages) and `dev-MN1.en`, and broke none;
  - `p3-dev-bound-meaning-v2` is 24/24;
  - the eight remaining count inputs (`dev-MN1` zh-TW/ja, `dev-MN2`, `dev-MN3`)
    are the model's own four-meaning `count_basis` clarifications.

  This is a development observation, not promotion.

See the [v16 contract](docs/count-reading-v16.md) and the
[gate result](docs/count-reading-v16-result.md).

v17 adds one sentence to v16. Given a complete Overview
scope, a generic people count that names no seats, accounts, attendance or
distinct individuals is answered with the Overview request and
`count_request: "unresolved"`, not a `count_basis` clarification. That is
v13's scoped action directive, which v16's text had dropped, adapted to the
typed reading. The assumption stays
code-decided. Against v16, the gate `passed` overall on the two v2 dev panels:
8 fixed, 0 broke, and 46/46 on one v17 run. On `p3-dev-matrix-compare-first-v3`
(#149) it gave `no_fix`, with 0 broke, at 48/54. `dev-A1` (a spurious
assumption on a no-count Overview) and `dev-C1` (a count_basis clarification
where the owner ruled for an answer) stay wrong. See the
[v17 contract](docs/count-directive-v17.md) and the
[gate results](docs/count-directive-v17-result.md).

The current candidate, v18 (ADR #152), changes three places in v17's
instruction text. It tells the model:
- that a general overview of bookings that asks for no number of people is
  `count_request: "none"`;
- to use `count_basis` only when the user says they are undecided between
  named meanings;
- to answer a people count that names seats or accounts only in doubt about the
  system's basis with `count_request: "unresolved"`, so that the stated
  assumption tells the basis.

It targets `dev-A1` and `dev-C1`. Against v17, both gates gave `no_fix`: no
input changed outcome on the three panels, and both targets stayed wrong. v17's
second run reproduced its first (46/46 and 48/54). See the
[v18 contract](docs/count-scope-v18.md) and the
[gate results](docs/count-scope-v18-result.md).

On a fresh count panel written outside the tuned inputs (#155), v18 scored 39/54.
Every generic count, named-seats, unavailable-count, user-undecided and
bookings row was correct. Every system-basis-doubt row (the `dev-C1` class)
and every no-count overview row (the `dev-A1` class) was wrong. A count
ablation (#156) found no support for either root-cause hypothesis: the enum
labels or the older clarification rules. See the
[results](docs/count-fresh-ablation-result.md).

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
