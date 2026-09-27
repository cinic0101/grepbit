# Historical evaluation records

These documents describe earlier phases and their recorded decisions. Start
with [STATE.md](../../STATE.md), the [current runner](../evaluation-runner.md)
and the goal issue for current work. [AGENTS.md](../../AGENTS.md) remains the
authority; historical commands are not new execution grants.

- [Phase status before consolidation](phase-status-2026-09.md)
- [P2 recipe smoke](recipe-smoke.md)
- [12B candidate identity](p310-candidate-model-contract.md)
- [Provider adapters](p3-provider-adapters.md)
- [Bedrock candidate](p3-bedrock-candidate.md), [grammar budget](p3-bedrock-grammar-budget.md), [complex const repair](p3-bedrock-complex-const-repair.md), [wire coupling](p3-bedrock-wire-coupling.md)
- [Shared observed regression](p3-shared-observed-regression.md)
- [Reason diagnostic](p3-reason-diagnostic.md)
- [Holdout observation](p3-holdout-observation.md)
- [Development regression](p3-dev-regression.md)

The corresponding readers are in `tools/history/` and their regression tests
in `tests/history/`. Packet command templates preserve the original paths to
keep archives verifiable. Use the relocated reader for offline inspection and
`tools/evaluate.py` for new evaluations. The tag `p3-archive-2026-09` preserves
the state before restructuring. Frozen assets, candidate entries, legacy
requirements and local evidence have not been rewritten by this move.
