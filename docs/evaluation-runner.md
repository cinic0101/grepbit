# Single tiered evaluation runner (#87 step 2)

Status: implemented offline with rulers. No live call in the implementing PR.
A live run needs a recorded owner grant and one exclusive run slot.

## One runner, three registries, one index

`tools/evaluate.py` replaces the purpose-specific runners for new work. Its
inputs are registry entries:

| Input | Registry | Entry |
| --- | --- | --- |
| `--candidate <id>` | `evals/candidates/` ([candidate registry](candidate-registry.md)) | the live runtime must `check()` as this id |
| `--panel <id>` | `evals/panels/index.json` | path to a `p3-panel-v1` panel, tier (`dev`, `regression`, `holdout`), pinned asset digests, allocation policy or null, freeze reference for holdouts, authoring (`development`, `historical`, `independent`) |
| `--route <id>` | `evals/routes/index.json` | provider (`litellm` or `bedrock_converse`), model alias or inference profile, region, call timeout, transport security |
| `--baseline <report.json>` (optional) | a prior report of the same panel, read through its own reader (`evaluation-report-v1`, `evaluation-report-v2` or the P3.5 formal reader) | six-class comparison in the summary |
| `--repetition <N>` (optional, `--prepare` only) | integer 1..99, default 1 | a separately authorized repeated observation of the same bytes; the run id gains `--r<N>` |
| `--owner-authorization-reference` | any issue comment URL | recorded on the envelope, not interpreted |

`evals/runs/index.jsonl` is the append-only run index: one line per recorded
run (run id, candidate, panel, tier, route, claim, report digest, slot,
commit, grant, status, counts, outcomes). The runner reads it to derive the
claim; `--record` appends a line after offline readback and refuses a
duplicate run id. The index is committed with the run it records.

Panel paths may point into the local `.artifacts/` archive (the frozen formal
panel and holdout A live there); the registry pins their digests, so a run
elsewhere fails closed until the same bytes are present.

## Claim is derived, never chosen

| Tier | Claim | Notes |
| --- | --- | --- |
| `dev` | `development_observation` | agent-authored, unlimited, never fresh |
| `regression` | `observed_regression` | exposed data; comparison against a baseline is the useful output |
| `holdout` | `fresh_holdout_observation` once per (panel, route), then `observed_regression` | the panel must be independently authored with a freeze that carries the owner review reference; every input `frozen_fresh` |

The packet pins the run-index digest at preparation. If the index moves
before `--live` (for example a fresh holdout run was recorded in between),
the rebuild yields a different claim or digest and the run stops with
`manifest_drift` before any credential is read. Nothing in this runner is
promotion: `promotion_eligible` is always false and the summary carries
`tier`, `claim`, `evidence_class`, `observations` (closed clarification kind
and choice count per clarify action) and `comparison`.

## Lifecycle

`--prepare` builds the packet (registry entries, source identity on a clean
accepted `dev` commit, database digest, settings derived from the route,
claim) and validates it by rebuilding. `--bind-authorization` writes the
envelope (packet digest, grant reference, one repository-relative run slot).
`--live` reuses the shared loop `p3_live_evidence._run_live`; the route
decides the client: LiteLLM default 31B, LiteLLM typed 12B candidate, or the
Bedrock Converse client for the registered profile and region, all admitted
before any send. `--report` reads an archive back offline. `--record` appends
the run to the index.

Since evaluation v2 ([replayable observations](replayable-observations.md)),
packets, manifests and reports are `-v2` and persist the validated typed
action per input; v1 archives still read back and serve as baselines but no
longer run live. `--replay --report-path <v2 report> --db <db> --output
<new file>` feeds the recorded actions through the current kernel and grader
with zero model calls and refuses (`manifest_drift` with a closed
`replay_refusal`) when the model-facing bytes, panel assets, inputs or
database differ. `--aggregate --panel <id> --route <id> --candidate <id>`
reads every indexed run of that panel and route whose candidate has the same
behaviour identity ([behaviour identity](behavior-identity.md)) and classifies each input as `stable_correct`,
`stable_wrong`, `flaky` or `insufficient`. Neither mode is a live run, a
claim upgrade or promotion.

`--gate` ([candidate gate](candidate-gate.md), `evaluation-gate-v3`) applies
the pre-registered acceptance rule offline. It compares one candidate run on
each named dev panel with the baseline's aggregate classes, and needs a
baseline sentinel run under the same owner authorization. Its verdict is
`regression`, `inconclusive`, `passed` or `no_fix`, and it is a development
observation only.

`--reading-diagnostic` ([reading diagnostic](reading-diagnostic.md),
`reading-diagnostic-v1`) is a separate, owner-authorized diagnostic call per
dev-panel input. It asks the model, in closed codes, how it read the question,
and leaves the current candidate's bytes unchanged. It is never a run-index
entry, a gate input or promotion evidence.

## Historical tools

The prior route tools and candidate helper now live under `tools/history/`;
`tests/history/` remains included by the full offline unittest discovery.
They provide archive readers and are not the entry for new runs. The frozen
P3.3 registry entry supplies their semantic identity, so later registered
candidates do not change the identity of old reports. Frozen-candidate route
preparation still refuses a different live candidate.

Recorded `command_template` strings retain their original paths because those
strings are part of historical packet validation. They are evidence, not
commands to replay from the current checkout. Inspect an archive with its
reader at the new path (for example, `tools/history/p3_formal_run.py --report
--report-path <archive>/report.json`); new work uses `tools/evaluate.py`.
Current source identities include `tools/history/p3_*.py`; archived source
identities, report versions and evidence bytes remain unchanged.
