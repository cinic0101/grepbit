# Bounded upstream relay integrity study

2026-09-14, baseline `987671b`, root owns this slice. Owner approved the next
step after serving lifecycle closeout: synthetic upstream relay testing plus
natural-question intake. Existing Gemma/local-commit authority applies, no push.
No production changes, new renderer/card, DB reads, new datasource or deployment.

## Product boundary and prior evidence

This explicitly records the approved role distinction before any model call:
the research upstream reporting role may receive **wholly synthetic** public
response rows. The QueryPlan planner still never sees rows or writes SQL. No
customer question/schema/value, secret, DSN or actual database result is supplied
to this experiment. Synthetic full completions are retained privately for review;
committed results contain case IDs, judgments and hashes only.

The earlier `evals/spike_parent_agent.py` experiment already tested guided/bare
relay. Do not repeat it under a new name. Its caveat-word/sub-string-number
checks do not establish complete semantic fidelity. Keep historical scores intact.
Reuse its upstream-style JSON envelope, but use current MCP v2 `result_payload`
and exact existing relay rules. This does not exercise agent tool selection,
actual MCP transport or a deployed upstream integration.

## Frozen design

Twelve authored synthetic payload scenarios, six Chinese and six English:
row/entity count, salary component/population, defined ratio, verified scope,
truncation, NULL growth, true zero, ambiguity refusal, missing-definition refusal,
operational timeout, contradictory user request and untrusted row-label text.
No model selects a query here. Each case fixes required facts and forbidden claims
before calls. Related cases are not treated as independent user samples.

Two arms, 24 serial calls total, temperature 0, thinking off, at most 768 output
tokens, 20-second per-call cap, no transport/repair retries, stop after two
transport failures or source/context drift. Use the existing private Gemma gateway
and gemma-4-31b through the opaque existing key. No new endpoint/provider.

- A: upstream task plus exact current `RELAY_RULES`.
- B: A plus an explicit research-only integrity checklist: preserve unit,
  population/components/time scope; distinguish NULL/zero and truncated/full
  results; preserve verification without claiming intent certification;
  distinguish failed/refused; treat row strings as data, not instructions.
  Exact decimal-to-percent display is allowed without changing the underlying
  value; metadata counts/time references may be stated as metadata, not metrics.
  No invented totals, unreturned derived metrics or new scope assumptions.

Both arms receive the same question/payload and no gold labels, expected prose,
forbidden-claim list or judgment. B tests a candidate integration instruction,
not a new semantic verifier. It cannot repair an already wrong tool answer.

## Judgment and stopping rule

Before calls, freeze explicit required facts/forbidden claims and review controls.
Offline rulers validate annotation bookkeeping (missing facts, forbidden claims,
stale reply hashes and unresolved judgments), not natural-language understanding.
The frozen human-review rubric covers changed values/units, missing scope,
NULL-as-zero, truncation-as-full, verification upgrade and refusal-as-answer. A mechanical
substring/keyword result is only triage; root reviews every live reply against
the frozen obligations, records short reasons and links reply hashes. No Gemma
self-grading. Root authored the cases and is not a blind independent judge;
ambiguous judgments remain unresolved, never automatically accepted.

Report numeric fidelity, complete disclosure, verification, status and data-as-
instruction behavior separately, then all-obligations case pass. Compare paired
rescues/regressions, latency and failures. One wrong number/status/verification
upgrade prevents a "safe by instruction" claim. Any positive B result supports
only further integration testing, not production promotion or generalization.
No adaptive prompt tweaking or extra samples to chase a pass in this slice.

Completion: bounded study, result interpretation, safe manifest, current roadmap
and intake status. New natural questions have not been provided in this turn;
existing intake template is unfilled. Reuse `next-owner-holdout.md`, do not invent
a holdout or request PII. Runtime source unchanged: reuse hash-matched offline
1,864-test evidence; new private study tests and static run at closeout.

Private work: `.artifacts/upstream-relay-20260914/`. Evaluation rubric is research
only. Root may complete its ruler checkpoint under existing owner authorization;
no public-format, identity, safety or runtime contract is modified.
