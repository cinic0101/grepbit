# Sonnet control run of v12 on the mechanism probe (#79)

This is one development observation of the current candidate on the Bedrock
Sonnet route. Sonnet is a control and diagnostic model only, by the owner's
decision of 2026-09-25
([#79 #issuecomment-5825679636](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5825679636)).
The run is neither promotion nor gate evidence. It changes no candidate,
oracle, gold or case text.

## Authorization and identity

- **Decision:** [#79 #issuecomment-5902758076](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5902758076), item 4.
- **Authorization and envelope:** [#79 #issuecomment-5902967830](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5902967830).
  - It includes the owner's Bedrock route attestation that retry, fallback and cache are disabled.
  - The packet records the attestation as `operator_cli_attestation_not_independently_verified`.
- **Run:** `p3-dev-mechanism-probe-v1--bedrock-jp-sonnet-4-6--p3-v10-restoration-v12--e483c3468cdd--r1`.
  - Code `dev@4561a56858aaf70feb77bdf67524642575e5393e`.
  - Packet `958b03b07a2b…`.
  - Report `6571a6d54418…`, recorded in `evals/runs/index.jsonl`.
- **Candidate:** `p3-v10-restoration-v12`, candidate SHA256 `6d707b8dc2d5…`.
  - The system message and runtime are those of the 31B runs.
  - The output constraint is provider-specific:
    - Bedrock receives the recipe schema compacted by `grepbit/bedrock.py`, with its `description` strings removed. Those strings carry format hints only: ISO instants, code length and integers.
    - The compaction also removes the length, pattern, count and range keywords and the per-branch coupling. For example, the compacted schema requires at least one clarification choice, where the native contract requires two to four, and exactly two for `comparison_roles`. Native validation still enforces these after decoding, but the decoding space on Bedrock is looser.
    - The 31B route sends the full schema as LiteLLM `response_format` to an xgrammar server.
- **Route:** `bedrock-jp-sonnet-4-6` (`jp.anthropic.claude-sonnet-4-6`, `ap-northeast-1`).
- **Execution:** complete, 22 of 22 calls, with no stop, retry or rerun.
  - 82.2 s.
  - 155,349 prompt tokens and 1,594 completion tokens.
  - The first `--prepare` attempt failed with `artifact_io` (a missing parent directory). It made 0 calls and wrote nothing.

## Result

Sonnet scored 10/22 inputs and 10/14 families. 31B scored 11/22 and 7/14 on the same candidate (`432b797b`).

| Group | Inputs | Sonnet | 31B (v12) |
| --- | --- | --- | --- |
| Directed English Compare | 10 inputs, all expecting an answer: `E02_compare.en`, `dev-MC1`–`MC5`, `dev-A3.en`, `dev-BM2.en`, `dev-MY1`/`MY2` | 10 correct | 7 correct; `E02_compare.en`, `dev-MC2.en` and `dev-MC4.en` falsely clarify `comparison_roles` |
| Count | 12 inputs, all expecting a `count_basis` clarification: `dev-BM6`, `dev-MN1`, `dev-MN2`, `dev-MN3`, three languages each. `dev-MN1` and `dev-MN3` expect four choices; `dev-BM6` and `dev-MN2` expect three. | 0 correct | 4 correct. 4 answer, 3 offer four choices where three are expected, 1 declines. |

The index records Sonnet's count outcomes only as `wrong_action` ×12. The
local report pinned by `6571a6d5…` shows the validated action
`{"outcome":"declined"}` on all 12.

## What it shows

**Directed Compare.** On this route, in one run, Sonnet did not reproduce
31B's three false `comparison_roles` clarifications. The false clarifications
therefore depend on the model or the route. The instruction text alone does
not force them.

**Count: the observation.** Sonnet declined every count input, in every
language, including the booking-framed `dev-BM6` and `dev-MN2`. The failure
modes of the two models differ. 31B mostly answers or offers four choices and
declines once; Sonnet always declines.

**Count: a separate reading of the runtime text** (not established by this run):
- The Overview recipe context lists "people counts" as unsupported.
- `SYSTEM_INSTRUCTION` says: "If any required output, scope or bound meaning
  is unsupported by the recipe, decline the whole request, even when another
  part is ambiguous."
- The `count_basis` text says: "Use count_basis only when the question leaves
  mutually exclusive count meanings unresolved." It continues: "If the
  question requires attendance_visits, distinct_people or
  known_booking_accounts, decline the whole request, including when it also
  requires a supported Overview."
- A question asking for "headcount" or "how many people" is thus open to a
  decline reading under the text itself. Sonnet's uniform decline is
  consistent with that reading, but a decline carries no reason, so the cause
  is not established.

## Limits

- One run per input at temperature 0, with no repetition. Between-session variation on this route is unmeasured.
- Model and route are confounded: the provider, the serving stack and the output-constraint encoding all differ between the two routes.
- Only the probe panel ran. Sonnet has no v12 run on the 24-input control panel.
- The inputs are exposed development inputs; `E02_compare.en` is historical, the others agent-authored. The claim is a development observation, not fresh generalization evidence.
- Declines are the constant `{"outcome":"declined"}`. The planned reading diagnostic (#79 decision item 1) is meant to observe their reason.
