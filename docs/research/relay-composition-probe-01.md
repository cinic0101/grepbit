# Composition probe stopped; use the requested local web entry next

2026-09-14, baseline `61c38e9`. No production/model/DB changes.
Protocol: [relay composition](../plan/relay-composition-probe.md).
Private work: `.artifacts/relay-composition-20260914/`.

## What was completed and what was not

Twenty-three offline checks pass: exact/deep copy of twelve synthetic payloads,
eight field-mutation controls, swapped/missing evidence, wrong-source/conflicting-
prose non-certification, and preservation of historical review counts. These
measure local copy/accounting behavior, not correctness of a delivered answer.

The stdio fixture probe did **not** complete its twelve-result replay:

1. Startup failed before a tool call because the research script used the old
   `FastMCP` import. Installed MCP v2 calls it `MCPServer`. This was a probe bug,
   not a production failure. The first preparation remains immutable.
2. A new preparation with that import corrected initialized and made the first
   fixture call, then stopped at the exact-payload assertion. The fixture's bare
   `-> dict` annotation does not provide the structured output schema expected
   by this client. Local SDK metadata inspection confirms `output_schema=None`;
   production `ask` uses `dict[str, Any]`. Do not blame Gemma or change the real
   MCP contract for this research adapter mistake.

The predeclared unexpected-shape stop was respected. No successful transport
matrix, combination gain, new live-model result or 12/12 retention claim is
made. No new Gemma or database calls were made. The owner then requested a
simple streaming web instead of connecting an external upstream consumer;
do not spend further calls repairing an unnecessary surrogate. Retain scripts
and failed-attempt preparations privately, not in runtime.

## Answer to the composition question

Yes, complementary mechanisms may work better together. Their effects need not
add linearly: better definitions can improve selection, but an unchanged gate
can still reject that improved plan; correct structured output can then lose
its caveats during prose relay. Existing scoped grounding, validation and compiler
checks already form a composition. There is no evidence that all remaining
problems require one particular bundle, or that adding more reviewers fixes
correlated intent errors.

Choose a pair by a specific causal hypothesis, then compare baseline/X/Y/X+Y on
the same frozen questions and fixtures. Record paired rescues, newly wrong answers,
false refusals, unknowns and latency separately. Different panels cannot supply
an interaction estimate. An oracle that chooses the best historical answer is
an evaluation upper bound, not an available production selector.

For the immediate UI, deterministic rendering of the original result eliminates
the need for a second prose model in that path. It cannot fix an upstream wrong
metric, a gate false refusal or missing business definition. For a future prose
consumer, exact evidence retention is useful but cannot excuse contradictory prose
or establish that disclosures were displayed/read. Do not promote the previous
8/12-to-10/12 checklist on the strength of this copy probe.

## Next and checkpoint

[Local streaming web](../plan/local-streaming-web.md) is the scoped next step:
browser -> HTTP/SSE -> actual stdio MCP -> existing ask pipeline. Its new HTTP
boundary has static contract rulers and existing-public-payload controls, not a
running server. Approval of that checkpoint precedes the web implementation.
No natural user holdout has been supplied; authored E2E tests will remain authored.
