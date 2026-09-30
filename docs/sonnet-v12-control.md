# Sonnet control run of v12 on the mechanism probe (#79)

One development observation of the current candidate on the Bedrock Sonnet
route. Sonnet is a control and diagnostic model only (#79 owner decision of
2025-09-25). This run is neither promotion nor gate evidence, and it changes
no candidate, oracle, gold or case text.

## Authorization and identity

- Owner decision: [#79 #issuecomment-5902758076](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5902758076), item 4.
- Authorization and envelope: [#79 #issuecomment-5902967830](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5902967830). It includes the owner's Bedrock route attestation that retry, fallback and cache are disabled.
- Run: `p3-dev-mechanism-probe-v1--bedrock-jp-sonnet-4-6--p3-v10-restoration-v12--e483c3468cdd--r1`.
  - Code: `dev@4561a56858aaf70feb77bdf67524642575e5393e`.
  - Packet: `958b03b07a2b…`.
  - Report: `6571a6d54418…`, recorded in `evals/runs/index.jsonl`.
- Candidate: `p3-v10-restoration-v12`, candidate SHA256 `6d707b8dc2d5…`. These are the same model-facing bytes as the 31B runs.
- Route: `bedrock-jp-sonnet-4-6` (`jp.anthropic.claude-sonnet-4-6`, `ap-northeast-1`).
- Execution: complete, 22 of 22 calls, no stop, retry or rerun, 82 s.

## Result

Sonnet scored 10/22 and 10/14 families. For comparison, 31B scored 11/22 and 7/14 families on the same bytes (`432b797b`).

| Group | Inputs | Sonnet | 31B (v12) |
| --- | --- | --- | --- |
| Directed English Compare (`E02_compare.en`, `dev-MC1`–`MC5`, `dev-A3.en`, `dev-BM2.en`, `dev-MY1`/`MY2`) | 10, expect answer | 10 correct | 7 correct; `E02_compare.en`, `dev-MC2.en`, `dev-MC4.en` falsely clarify `comparison_roles` |
| Count (`dev-BM6`, `dev-MN1`, `dev-MN2`, `dev-MN3`, three languages each) | 12, expect `count_basis` clarification | 0 correct; all 12 decline (`{"outcome":"declined"}`) | 4 correct; 4 answer, 3 offer four choices where three are expected, 1 declines |

## What it shows

- **Directed Compare.** A stronger model answers every directed English Compare variant under v12's unchanged instruction. So the `comparison_roles` false clarifications are specific to 31B on this instruction; the instruction text does not force them.
- **Count.** Sonnet declines every count input, in every language and framing. That includes the booking-framed `dev-BM6` and `dev-MN2`, where the oracle expects a clarification.
  - The runtime context both lists "people counts" as unsupported for Overview and tells the model to clarify `count_basis` when count meanings are unresolved.
  - Sonnet's uniform decline is consistent with it resolving that tension towards decline. The cause is not established: a decline carries no reason.
  - The count failures are therefore not only a 31B limitation. The model-facing count instruction is itself open to a decline reading.

## Limits

- This is one run per input, at temperature 0, with no repetition. Between-session variation on this route is unmeasured.
- Only the probe panel ran; Sonnet has no v12 run on the 24-input control panel.
- The claim is a development observation on exposed, agent-authored inputs; it is not fresh generalization evidence.
- Declines are the constant `{"outcome":"declined"}`, so their reason is not observable. The planned reading diagnostic (#79 decision item 1) is meant to observe it.
