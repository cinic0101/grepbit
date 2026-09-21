# P2.7: fixed recipe integration runner

Issue #28 implements evaluation tooling around the accepted
[P2.6 recipe adapter](recipe-model-integration.md), not a new runtime planner.
**Gate A is implementation and offline review. Gate B is accepted-commit
preparation after the owner merges the reviewed PR. Neither authorizes live
execution.** Keep #28 open until Gate B evidence is prepared and reviewed.

`tools/recipe_smoke.py` reuses neutral internal helpers from `tools/smoke.py`:
stable exact-seed database identity, size/symlink checks, dependency/source
identity, manifest comparison, policy attestations, immutable exclusive
checkpoints, safe argument errors and interrupted-call evidence. The imported
helper file is pinned. P1's panel, CLI quality-exit behavior, source and historical
manifests are not changed or repinned.

## One fixed evaluator panel

`evals/panels/p2-recipe-smoke-v1.json` owns the explicit order and expected native
intent/coverage/values. Existing question/translation assets are read unchanged.
It contains no SQL, repair instructions, alternate interpretations or prompt
hints. The runtime adapter never imports this asset.

| Order | Family | Language |
| --- | --- | --- |
| 1 | E01_overview | zh-TW |
| 2 | E02_compare | en |
| 3 | E03_share_denominator | ja |
| 4 | E01_overview | en |
| 5 | E02_compare | ja |
| 6 | E03_share_denominator | zh-TW |
| 7 | E01_overview | ja |
| 8 | E02_compare | zh-TW |
| 9 | E03_share_denominator | en |

This is **nine paired inputs, three semantic families**, not nine independent
semantic cases. E10 is excluded and remains an injected operational control.
There is no shuffle, repetition, repair, best-of-N or synthesis.

Each call receives only its question and the unchanged shared P2.6 system
context. Case IDs, sibling questions, expected requests, oracle values and
manifest fields are not model inputs. The runner may verify the synthetic DB
before calling the adapter; the adapter's no-premature-native-execution boundary
remains unchanged.

## Intent first, values last

The pure grader checks `recipe -> request -> execution -> coverage ->
value_agreement`. It canonicalizes typed native dates to UTC, preserving Compare
current/baseline roles, exact Overview code and Breakdown k. Equivalent accepted
offset representations compare equal; matching numbers cannot rescue wrong
intent.

| Outcome | Meaning |
| --- | --- |
| correct | All five grading stages pass |
| wrong_recipe | Valid proposal chose a different recipe/version |
| wrong_request | Valid proposal chose different scope/roles/code/k, or P3.1 unnecessarily clarified an answer-only input |
| wrong_coverage | Correct intent executed, but native status/slots/binding/group coverage do not match |
| wrong_value | Intent, execution and coverage pass; representative values differ |
| false_refusal | Model declined an answerable input in this fixed panel |
| invalid_output | Malformed model content JSON or native-request schema |
| operational_failure | Transport/provider/configuration/source/budget/internal execution failure |
| not_run | Input was not attempted; reason remains explicit |

A wrong proposal remains `wrong_recipe`/`wrong_request` even if its subsequent
native execution fails. The operational error is retained separately and may
still require a stop. A native partial/failed-data pack without adapter error is
a coverage failure for this frozen fixture, not automatically an operational
error. A complete explicitly undefined ratio is resolved coverage but cannot
match this panel's nonzero expected rational value.

P3.1 keeps this historical panel answer-only. A successful `clarify` action is
persisted with explicit semantic/presentation evidence and no adapter error,
but fails request grading (`wrong_request`); recipe/execution/coverage/value
grading stay `not_run`. It is not `false_refusal`, an operational failure or a
correct answer. The panel continues under the unchanged stop policy. This
compatibility handling is not the future P3 action taxonomy or evaluator.

Overview requires all five slots checked and binding to CA; no duplicate full
gold table for optional grouped rows is added. Compare preserves roles and all
four resolved slots. Breakdown requires course top-k coverage with k=2 and all
four resolved slots. Fractions retain exact numerator/denominator representation.
Slot references must identify their own native role's fact, not merely any
checked fact in the pack; swapping two valid fact IDs is a coverage failure.

## Fixed bounds and stop semantics

One sequential pass, concurrency 1, at most nine client HTTP attempts, no retries
or repairs. Requests retain `gemma-4-31b`, temperature 0, stream false and 2048
output tokens. Per-input total allowance is at most 60 seconds; panel allowance
is 720 seconds. Accepted 4096/32768/131072-byte input/request/response bounds and
the 16 MiB exact-synthetic-database bound remain in force.

`p2.7-stops-v2` counts only `transport_error`, `gateway_error` and `rate_limited`
as network-like failures. Two consecutive such codes stop as
`consecutive_network_failures`. Separately, two consecutive `timeout` codes stop
as `consecutive_timeouts`. A result outside a streak's own code set resets that
streak, so a timeout and a network error do not combine.

P2.6's `transport_failure` boolean is **not** used to make this decision.
Timeout origin remains unknown and may include local post-model work.
Immediate adapter stops are configuration, envelope incompatibility and
response/token/global-budget exhaustion. Manifest/source/database drift,
panel/attempt limits and artifact/leakage safety failures also stop the runner.
The cooperative panel limit includes calls, native execution, grading, ordinary
checkpoints and preparing/flushing the terminal payload. Final admission occurs
after that preparation, immediately before atomic publication; the publication
commits the eligible result. Its scheduling/syscall return latency and later CLI
acknowledgement do not trigger a new deadline check or retract the committed
report. This is not a larger timeout or a check only before the heavy write.
Wrong intent, wrong coverage/value, false refusal and ordinary malformed
model-content JSON/schema do not independently stop it.

Preparation and an operationally completed panel exit **0 even with poor semantic
quality**. Stopped/incomplete/preflight/internal failures exit nonzero. Read
quality from report.json; do not rerun a completed panel until its answers turn
green.

## Candidate preparation: Gate A only

Use the existing verified pinned Python environment. Preparation loads no
credentials, constructs no model client and makes no network request.

```bash
P="<verified-pinned-python>"
R="<fresh-ignored-candidate-directory>"
"$P" tools/fixture.py build --db "$R/learningops.sqlite"
"$P" tools/fixture.py check --db "$R/learningops.sqlite" --report "$R/fixture-report.json"
"$P" tools/recipe_smoke.py --db "$R/learningops.sqlite" --output-dir "$R/prepared"
```

The parent directory must exist and each output directory/file must be fresh.
Default manifests are labeled `preparation.kind=candidate`, including on a clean
feature commit. They cannot be used in live mode or copied forward after merge.
Mock execution is the Python `run_panel(..., origin="mock", client=...)` entry;
it requires an explicit offline transport rather than GatewayClient's default
network transport.

## Accepted preparation: Gate B, only after owner merge

After explicit owner merge, use the resulting accepted **dev** commit, verify a
clean worktree, build/check a new fixture and run preparation with
`--accepted-commit "<owner-accepted-dev-merge-sha>"`.

The tool requires that exact SHA, branch `dev` and a clean worktree. The explicit
SHA is an owner-supplied acceptance assertion, not an automatic proof of GitHub
review/approval. Do not generate this final manifest during Gate A.

The new manifest identity is `p2.7-recipe-smoke-v1`. It pins commit/dirty state,
branch, Python/SQLite and all dependency versions, runtime/native/adapter/helper/
runner sources, panel and case/language/fixture/oracle assets, recipe
context/schema/instruction/system-message hashes, database bytes, settings and
stop-policy hashes, and all nine question hashes/references. Evaluator oracle
data is kept separate from model evidence. Raw question text is not duplicated
into the manifest or report.

P2.11 added `identities.structured_output`: initially `recipe-structured-output-v1`,
JSON-schema mode, the fixed schema name, canonical schema SHA-256 and complete
response-format wrapper SHA-256. Current gateway/adapter source hashes remain
included. That change left semantic context, panel, grading and stop policy
unchanged. P3.1 separately versions the shared recipe action/generation identity
to v2 and adds the clarification compatibility branch above; native meanings,
frozen answers and stop policy remain intact. Both new runtime modules are
covered by the existing source-file hashing. No new panel/manifest version is needed: exact manifest comparison
rejects old source/policy identities, including a missing generation identity.
Historical manifests must not be edited or repinned. This identifies the
requested generation constraint, not deployed schema compatibility or enforcement.

Preparation checks source identity again after construction. Execution compares
the prepared manifest exactly and rechecks source/database before and after
possible sends. No symlink, unstable sidecar, existing output directory or
identity drift is silently accepted.
The resolved question's actual UTF-8 hash, metadata and nine-entry count are
also checked against the manifest before sending, not inferred from file hashes.

Gate B's handoff must include accepted commit, file/canonical manifest hashes,
DB hash, context identities, panel/order, nine question hashes, settings/stops
and the new artifact path, still with **LIVE MODEL ATTEMPTS = 0**.

## Future live template: not authorization, do not execute under #28

```bash
P="<verified-pinned-python>"
"$P" tools/recipe_smoke.py --live \
  --manifest "<fresh-accepted-prepared-directory>/manifest.json" \
  --db "<fresh-accepted-fixture-directory>/learningops.sqlite" \
  --env-file "<explicit-local-config-file>" \
  --gateway-retries "<enabled-or-disabled>" \
  --gateway-fallback "<enabled-or-disabled>" \
  --gateway-cache "<enabled-or-disabled>" \
  --output-dir "<fresh-live-output-directory>"
```

Manifest/source/database/fresh-output/acceptance/policy checks precede explicit
configuration loading. There is no automatic .env search, health check or
provider discovery. Historical gateway policy is not fresh truth: attest all
three current settings explicitly. Flags alone never authorize execution.

## Artifacts and interpretation limits

Immutable exclusive checkpoints surround each possible send; report.json is the
latest owned atomic link. Reservations retain `in_progress` and possible-in-flight
state on interruption, rather than proving no request occurred. Do not resume
an interrupted panel as another authorized run. Preserve all failed evidence.

### Terminal publication and the R1 correction

The authoritative report remains non-complete while all completed inputs,
semantic grades and actual attempt counts are checkpointed. A P2-local helper
then safe-exports a separate prospective complete report to
`terminal-candidate.json` using the unchanged exclusive writer, flush and fsync.
It prepares an exclusive `terminal.next.json` hard link in the same directory,
rechecks manifest/source/database identity and owned regular-file link identity,
and performs the final monotonic deadline admission check.

Only then does one atomic replacement of `report.json` commit completion.
There is no required checkpoint, cleanup, lstat or deadline revalidation after
that replacement. P1's complete `persist()` path is deliberately not used for
this commit: it performs additional filesystem work after updating the report
link. `tools/smoke.py` remains unchanged.

A staged candidate is **not an authoritative completion or checkpoint**, even
when its prospective payload says complete. Before publication, failure or
interruption leaves the previous non-complete report valid. A diagnostic
stopped/error checkpoint is attempted when safe, but correctness does not depend
on that write succeeding; persistent ENOSPC must not reveal an earlier complete
report. Unpublished candidates and conflicting files remain as evidence, with
no overwrite, deletion, retry or resend of completed inputs.

After a valid atomic replacement, interruption or CLI notification failure does
not invalidate the committed report. CLI acknowledgement and publication are
different events. No hard filesystem/syscall deadline, general power-loss
durability or arbitrary network-filesystem guarantee is claimed.

For a complete report, `elapsed_seconds` is a sample taken before the final
non-complete checkpoint and terminal preparation, not an exact publication,
return or acknowledgement timestamp. The written candidate is not mutated to
invent such a timestamp. Failure diagnostics sample elapsed time again when
possible.

This explicit commit boundary supersedes the unsafe publish/check/compensate
sequence identified in PR #29 R1. The stop-policy identity changes from
`p2.7-stops-v1` to `p2.7-stops-v2`; report/manifest field formats remain v1.
Source and policy hashes require fresh candidate manifests; historical pins and
the original reproducer remain unchanged. Regression tests replace the old
penultimate-complete-checkpoint expectation with the non-complete-until-commit
invariant, including deadline expiry plus persistently failing diagnostic writes.

Per-input records retain question reference/hash, status, attempts, sanitized
P2.6 evidence, proposal/native request, pack status, ordered grading, outcome,
adapter error and separate runner error/not-run reason. Native evidence is not
rewritten to fit evaluator intent. Reports exclude raw question/completion/
reasoning/configuration strings; configured-secret redaction requirements stop
reporting rather than permit an unsafe write, including secrets in dictionary
field names. If safe persistence itself fails, retain the preceding immutable
checkpoint instead of replacing it with an apparently successful report.

Summary records per-family/language outcomes, all-three-correct and
at-least-one-correct family counts, client/live/possible-in-flight attempts and
known usage/latency subtotals with unknown counts. Missing usage is not zero.
Upstream inference attempts remain unknown; client counts do not establish
server retries, cache behavior or GPU cancellation.

Offline fake-transport results establish runner mechanics, not Gemma quality.
Gate B is not live authorization; neither gate completes P2, establishes
generalization/PostgreSQL parity, or begins P3.
