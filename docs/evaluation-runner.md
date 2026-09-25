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
| `--baseline <report.json>` (optional) | a prior report of the same panel, read through its own reader (`evaluation-report-v1` or the P3.5 formal reader) | six-class comparison in the summary |
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

## Historical tools

`p3_formal_run`, `p3_stability_run`, `p3_candidate_regression`,
`p3_bedrock_candidate_probe`, `p3_bedrock_observed_regression`,
`p3_reason_diagnostic`, `p3_holdout_run` and `p3_dev_regression` remain as
readers of their archives and are not used for new runs. They still bind the
frozen P3.3 semantic identity to the live code and therefore refuse to prepare
on any other registered candidate, by design; step 5 of #87 moves them under
`tools/history/`.
