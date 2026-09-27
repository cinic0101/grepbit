# Compare completion diagnostic v1

Owner approved on 2026-09-27: [one-run grant](https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855110091).
Original owner decision: "同意，依此方案完成並執行一次" ("Agreed; complete it according to this plan and execute it once.").
This document specifies that diagnostic, not a new product promise or general run authority.

## Scope and identity

The only entry is `tools/evaluate.py --completion-diagnostic`; normal evaluation remains unchanged.
The diagnostic uses the current registered `p3-31b-instruction-v3`, the original
`p3-dev-matrix-v1` registered panel, and `litellm-gemma-4-31b`. Select exactly
`dev-A3.en`, `dev-C2.zh-TW`, `dev-C2.en` in that order, without changing any case or oracle.
The normal packet is retained as canonical evidence and rebuilt at live admission.
Pin the full merged dev/source identity, candidate, source panel assets, fixture,
three selected question hashes, and exact serialized request hashes. Never send
case IDs, evaluator metadata, reference SQL or oracle data to the model.

The canonical route is 60 seconds; only the explicitly admitted diagnostic client
uses 90 seconds. Record both. Same non-streaming request, temperature zero, schema,
prompt, model, 2,048-token output cap and 4,096/32,768/131,072-byte input/request/response
caps. No runtime production file or candidate registration change is necessary.
No native recipe execution or semantic grading occurs. Evidence class is diagnostic
observation, never candidate acceptance or promotion, and must not enter the normal
quality run index as a development score.

## Lifecycle and admission

`--describe`, `--prepare`, `--bind-authorization`, `--live`, `--report` are distinct
modes. No general deadline, model, input or raw-capture override is exposed.
After the diagnostic code is merged on `dev`, the offline and live CLI shapes are:

```bash
.venv/bin/python tools/evaluate.py --completion-diagnostic --describe
.venv/bin/python tools/evaluate.py --completion-diagnostic --prepare --db <PINNED_DB> --accepted-commit <MERGED_DEV_SHA> --output .artifacts/<PREPARATION>/packet.json
.venv/bin/python tools/evaluate.py --completion-diagnostic --bind-authorization --packet .artifacts/<PREPARATION>/packet.json --owner-authorization-reference https://github.com/cinic0101/grepbit/issues/79#issuecomment-5855110091 --output .artifacts/<PREPARATION>/authorization.json
.venv/bin/python tools/evaluate.py --completion-diagnostic --live --db <PINNED_DB> --packet .artifacts/<PREPARATION>/packet.json --authorization .artifacts/<PREPARATION>/authorization.json --accepted-commit <MERGED_DEV_SHA> --env-file <EXPLICIT_LOCAL_ENV_FILE>
.venv/bin/python tools/evaluate.py --completion-diagnostic --report --report-path .artifacts/compare-completion-3dc99bb3b3f23ad252b5/report.json
```

Create the preparation directory before `--prepare`; the packet and authorization
files use exclusive creation. The fixed run slot above is derived from the exact
grant URL. The live command takes no output override and consumes that slot before
loading credentials. `complete` means all three selected calls have a terminal
client observation; individual calls may have failed. The report and CLI mark the
result `diagnostic_observation` and `promotion_eligible=false`.
Use one packet, authorization and exclusive run directory. Bind the exact grant
URL and deterministic grant-derived run slot so the grant cannot be reused at a
second path. Creating the run slot consumes the grant before credential reads;
interrupted/partial attempts remain evidence and cannot be replayed. No symlinks,
path traversal or overwrites. Preparation and archive reading are offline.

Live execution requires the reviewed, clean accepted dev commit and exact rebuilt
packet, default model identity and unchanged route policy before sending. Existing
opaque gateway credentials only; retries, fallback and cache disabled. One run,
concurrency one, one attempt per case, maximum three sends, 90 seconds/call and
390 seconds total including publication preparation. Checkpoint attempted/in-flight
state before each send; preserve incomplete states on interruption. A failure of
artifact persistence must stop subsequent sends. Unknown upstream attempts remain
unknown. Stop on two consecutive timeouts or transport failures, any credential,
identity, route or privacy anomaly, budget exhaustion, or applicable AGENTS stops.

## Closed response observation

Process bytes only in memory, including responses with finish_reason=length.
Persist only allowlisted enums, key names, booleans and bounded numerical fields:

- returned model (exact expected alias only), finish reason, HTTP status, attempt
  and elapsed counts, prompt/completion/total usage and optional reasoning-token count;
- content/reasoning byte lengths, never their contents or hashes;
- strict JSON parse/error category and position, root type, known contract key and
  enum observations, unknown-key counts (never unknown names or values);
- numeric repetition statistics with an explicit bounded algorithm (for example,
  maximum repeated non-overlapping 32-character block count; no repeated text).

For repetition, scan each 32-character window left to right. For each window
value, count an occurrence only when its start is at least 32 characters after
the prior counted occurrence of that same value; publish only the maximum count.

Absent usage or fields are unknown, not zero. Invalid envelopes fail closed without
publishing unvalidated model labels or arbitrary exception strings. The report
reader validates exact field sets, types/bounds, grant/slot/pins, prefix/attempt
accounting, stop state and summary without needing source files, secrets or raw
responses. Malformed envelopes, unexpected model, too-large response, missing usage,
length, repeated content and reasoning-only responses all need offline witnesses.
Raw output and reasoning must never reach artifacts, logs, terminal, GitHub or another
service. Synthetic canaries verify this boundary. Historical reports are preserved.

## Checkpoint and validation

First commit this contract and a behavioral ruler: the opt-in `--describe` invocation
must expose exactly the closed identity and bounds. Before implementation it fails
at status assertion (unsupported opt-in entry), not import, setup or timeout.
Implementation follows this red commit in the same PR. Add focused fake-transport
privacy, timeout, cap, drift and replay regressions, then one full offline suite.
Local risk review and independent fresh-context actual GitHub diff review precede
merge. From merged dev, record exact command, pins and output slot before the single
live run. Publish safe results on #79; no rerun to improve the observation.

## Limits and recovery

The 90-second result may expose a truncated or malformed completion; a longer wait
is not a quality fix. Structural repetition is not proof of its semantic cause.
The cached template's thinking defaults do not establish the tokenizer loaded in
memory or every gateway override. Do not claim a causal mechanism beyond observed
fields. No prompt repair, candidate2, ordinary timeout change, NTP correction,
deployment or restart is part of this diagnostic. Recovery from a stopped run needs
a new explicit grant; preserve the old slot and all evidence.
