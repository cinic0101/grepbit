# Concept reasoning ablation (2026-09-12)

Completed: 162 calls, 488 offline tests and static checks pass. Reasoning improves
C exact intent from 22/30 to 26/30 and removes observed wrong/unresolved escapes,
but adds substantial latency and leaves semantic/output errors. No promotion.
See `../research/concept-reasoning-01.md` and `evidence/concept-reasoning-01.json`.

Authority: the user requested "試試開啟 reasoning" after the completed concept
pilot. This authorizes a bounded reasoning-setting experiment, not new prompts,
gold labels, release thresholds or runtime policy. The existing user authority
for Gemma4 covers the same gateway and opaque ignored credential. Root owns
the runner/test changes; no delegation, Git write, DB access or package install.
Preflight found no matching evaluation/test process IDs. Preserve the dirty
worktree at HEAD 746f168 and all prior evidence.

Reuse the exact 30 questions, 51 fixed question/plan pairs, C/D messages and
qualifier-only scoring of `concept-validation-pilot.md`. Add optional runner
settings; defaults remain thinking off, 768 tokens, 20 seconds. No src changes.
Record finish reason, reasoning character count and provider-reported reasoning
tokens when available. Never persist reasoning text, invalid model content,
provider error details, secrets or endpoint URLs.

Run one on and one off control, 81 calls each, serial, same 4,096-token maximum
and 60-second timeout, no automatic retries. The matched larger budget avoids
starving reasoning under the old 768-token cap; compare the contemporaneous
control first, not just the historical different-budget run. Maximum 162 calls
in this slice. The switch is `chat_template_kwargs.enable_thinking`; request
message hashes and every other request setting must match. Reasoning presence
is observed, not inferred solely from asking for it.

A truncated/failed response stays an error and cannot count as a successful
refusal. If the cap prevents a meaningful result, report that limitation instead
of silently changing budget midway or claiming reasoning failed semantically.
Keep source, fixtures and prompt text frozen during both runs. These short
sequential blocks are not a controlled endpoint-load/caching study.

Compare exact intent labels, known-wrong and unresolved escapes, rejection of
correct controls, format/transport errors, p50/p95 and tokens. Inspect changed
case IDs rather than only a total score. No adoption or expansion to 120 questions
follows automatically, even if this development pilot improves. Final evidence
goes under `.artifacts/concept-reasoning-20260912/` and a new research manifest.
