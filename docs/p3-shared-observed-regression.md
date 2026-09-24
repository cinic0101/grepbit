# Shared observed candidate regression contract (#70)

Status: owner-approved specification and offline implementation. No Bedrock
call or 28-input live authorization is included here.

## Evidence and intent

PR #69's one-shot v4 compatibility report
`.artifacts/p369-bedrock-stage-d-bQVTg9/run/report.json` (SHA-256
`ea4747388b8c47b6f762e521816f5daeebf4da67901a445e8745cc375f3c49e1`)
records one HTTP 200 attempt with all eight compatibility checks and native
execution passed for the JP Sonnet 4.6 profile. It is one exposed synthetic
E01 observation, not 28-input quality evidence. The historical 12B observed
regression remains immutable at 20/28 correct and 8/14 families correct.

The existing 28-input loop, scorer, evidence projection and reservation logic
are shared in `p3_eval.py` and `p3_live_evidence.py`. The 12B caller
`p3_candidate_regression.py` closes admission around its candidate identity,
Issue #58 authorization reference, 12B compatibility report, Gateway client,
and observed returned-model identity. Those cannot be replaced by a free-form
`--llm` switch. Before this change, `p3_eval._execute_panel` capped each call
at 60 seconds even when the packet said otherwise. The initial behavior ruler
demonstrated this mismatch: its legacy 60-second assertion passed, while the
intended 300-second Bedrock assertion failed with an observed 60-second call
budget. This was a direct behavior failure, not an import/setup failure.

## Proposed contract

- Keep the existing 12B v1 packet, reader, source/semantic identities and
  archived report interpretation unchanged. Do not repin its compatibility
  witness or change its 60/1800-second bounds.
- Reuse one 28-input execution loop, frozen grader, allocation check and
  31B comparison taxonomy. Move only genuinely shared comparison/panel logic
  to a provider-neutral helper if needed; do not duplicate or change the
  oracles, input order, frozen case hashes, scorer, thresholds or exposure
  labels. All 28 inputs are **observed regression** for this candidate, never
  new fresh evidence or promotion eligibility.
- Add a closed Bedrock purpose-specific admission and report contract rather
  than accepting a raw model ID at live invocation. Offline preparation may
  select the one admitted JP Sonnet 4.6 profile; the packet pins that selection.
  Live mode derives and validates provider, model profile, calling Region,
  Japan route, compact wire-schema hash, canonical schema hash, effective
  runtime identity, source, synthetic DB, panel assets, compatibility report,
  historical 31B baseline, gateway policy, command, limits and stop rules
  before credential access. An authorization envelope binds the exact packet
  hash, an Issue #70 factual reference and one normalized repository-relative
  `.artifacts/` output directory. Live mode checks the slot before credential
  access, and the exclusive output-directory creation consumes that slot.
  Actual permission comes from the owner's separate live instruction, not the
  comment itself.
- Reuse the v4 compatibility report as a **pinned prerequisite**, not as a
  substitute for observed regression results. Its report reader must pass
  without live access. The Bedrock candidate identity is
  `p3-jp-sonnet-46-bedrock-converse-v1`, model profile
  `jp.anthropic.claude-sonnet-4-6`, calling Region `ap-northeast-1`, allowed
  destination Regions `ap-northeast-1` and `ap-northeast-3`. The wire schema
  SHA-256 is `ea4e03d02732c0c45f9905ccd9b7c0010bedc87a190666e7b31895867c43e53b`;
  effective runtime identity SHA-256 is
  `4d1f27ded8138dbe9618c6f8c4b32ca4555d8a244ac5e7d94e1287f9de4fb2ed`.
- For Bedrock, allow at most 28 sequential runtime invocations and 28 client
  HTTP attempts, one per input. Each call is capped at 300 seconds; the whole
  panel at 8,520 seconds (28 x 300 + 120 overhead). Retain 2,048 max output
  tokens per call and existing request/response size limits. Disable retry,
  repair, fallback, resend, continuation and cache. Preserve reservation
  before possible send, immutable checkpoints, no resume/replay, and current
  consecutive network/timeout stops. A failed or interrupted authorized panel
  is preserved; it is never rerun to obtain a cleaner score.
- Public evidence reports the exact requested Bedrock profile and
  `returned_model=null` because Converse does not supply an observed model ID.
  The safe projector must reject any contradictory returned-model claim and
  never persist raw completion, reasoning, HTTP body, key or endpoint. For the
  28-input run, use safe closed error codes and no private raw-body capture;
  the v4 compatibility diagnostic remains separate. Unknown upstream inference
  attempts and unobserved processing destination stay unknown.
- The packet, authorization, manifest and report get new purpose-specific
  versions/hashes. Historical readers remain valid. A completed report must
  read back without current source, DB, credentials or network access. The
  archive reader verifies its own directory against the authorization's bound
  slot; moving the archive invalidates that readback. The authorization,
  manifest and report use v2 because v1 was never live-authorized or merged.

## Offline acceptance before PR

1. A focused fake-transport 28-input run uses the shared loop, produces exactly
   one sequential attempt per input, preserves the frozen scorer/comparison,
   and remains explicitly non-promoting. The 300-second configured call cap
   reaches the interpreter; legacy formal/12B calls remain capped at 60.
2. Tampered packet, compatibility pin, provider/region/profile, wire/effective
   identity, authorization, route, source, DB and case/order are rejected
   before environment or network access. Report readback rejects identity,
   counter, stage and evidence drift. An authorization bound to run A rejects
   run B before credential access; run A cannot be created twice; readback
   retains and verifies its bound slot.
3. Fake Bedrock responses prove `returned_model=null` is accepted only for the
   exact pinned profile, while an invented returned identity and private-text
   canary are rejected. HTTP, timeout and request-validation outcomes retain
   separate classifications. The archived 12B and v4 compatibility reports
   still read with their original meanings.
4. Run targeted tests and the full offline suite once at closeout. No AWS call
   occurs in implementation or tests. After PR review and merge, prepare a
   fresh source-bound packet and request a separate exact owner authorization
   for any 28-call live run.

## Decision and risk

The owner accepted the shared-core, candidate-specific-contract approach and
then approved this exact offline implementation checkpoint in the local
conversation on 2026-09-24. The red ruler recorded the original 60-second
runtime mismatch before implementation; it now passes with 60-second legacy
and 300-second Bedrock assertions. The implementation uses the existing
28-input execution loop and scorer, with one closed Bedrock admission wrapper.
It does not provide a free-form live model selector. Fake-transport tests cover
28 attempts, native request-validation classification, packet/auth/provider
drift before send, safe identity projection and archive readback. Historical
12B, 31B and Bedrock compatibility reports still read independently.

After merge, binding requires `--run-output-dir <FRESH_ARTIFACTS_RUN_DIRECTORY>`
alongside the authorization output file. The selected directory must remain
available as immutable evidence after the first invocation. Binding prevents
reusing one authorization at another output; it does not grant live permission
or prevent a person from creating a different envelope and seeking new approval.

This contract records the Bedrock evidence identity and 300/8520-second
envelope for a future separately authorized packet.
The main risks are accidentally changing legacy evidence semantics, accepting
an unpinned provider at live time, and overstating a 28-input observed run as
fresh quality. The original ruler failure was the intended 300-versus-60-second
call budget assertion; the corrected implementation now passes it. A local
review also found and led to corrections for outer-timeout evidence projection
and current runtime/schema identity verification before packet preparation.
