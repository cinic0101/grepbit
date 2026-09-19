# P1.2: local Gemma integration and smoke preparation

Issue #8 adds one bounded interpretation call, **not** a general planner or P1
acceptance. Implementation and fake-transport checks do not authorize live calls.
The first authorized smoke (#10) is preserved separately. P1.3a (#11) corrects
provider-envelope compatibility offline; it does not authorize a second live run.

```text
One question + shared runtime meanings
  -> one explicit LiteLLM /chat/completions POST
  -> strict JSON-content contract -> existing FactRequest
  -> the same execute_facts() -> scoped FactPack
```

`grepbit/gateway.py` owns local configuration and HTTP boundaries.
`grepbit/model.py` projects the four reviewed runtime meanings, parses the
model's proposal and calls the existing kernel. Neither reads evaluator assets.
`tools/smoke.py` alone selects paired questions and grades against the frozen
oracle. It never sends IDs, case records, SQL, expected answers, sibling
translations or expected periods to the model.

There is no synthesis call, automatic repair, client retry, provider fallback,
recipe framework, custom relational AST, per-case/per-language prompt or date
grammar. Current metric definitions and SQLGlot remain unchanged. Unsupported
or ambiguous requests can be declined; resumable clarification, general entity
resolution, the twelve P0 behavioral scenarios, PostgreSQL and P2 are not added.

## Dependencies and local credentials

Use Python 3.11+ and the pinned `requirements.txt` closure. The three direct
dependencies are `sqlglot==30.18.0`, `httpx==0.28.1` and `python-dotenv==1.2.3`.
`requirements.in` declares them; the lock includes their tested required
transitive dependencies, without optional extras. No LiteLLM/OpenAI SDK or
in-process proxy is installed. The existing fact CLI still works offline.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For a relocated Python unable to bootstrap `venv`, an existing `uv` can create
the environment as documented in [the kernel guide](fact-kernel.md).
Installing declared dependencies is not an evaluation-model call.

The owner may copy `.env.example` to an ignored local `.env` and fill values
locally, without displaying them in a transcript. Keep that plaintext file
private (for example, mode `0600`); Git ignore rules are not secret storage:

| Variable | Requirement |
| --- | --- |
| `GREPBIT_LITELLM_BASE_URL` | Explicit gateway API base, including `/v1` where required; no external-provider default |
| `GREPBIT_LITELLM_API_KEY` | Local bearer key; used only in the HTTP Authorization header |
| `GREPBIT_LITELLM_MODEL` | Defaults to exactly `gemma-4-31b`; this slice rejects other aliases/prefixes |

Only an explicit `--env-file` in live mode reads a dotenv file. Nothing searches
for `.env`, loads keys on import or validates credentials against a gateway.
Only the three application variables are read from the process environment,
which wins over file values, even when an existing value is empty.

The pinned dotenv tokenizer supports quoting/comments and `export` assignments
without executing shell code or expanding `${...}`/command substitutions.
Malformed statements, duplicate application keys, bare keys and files above
16 KiB are rejected. Unrelated variables are not applied to the environment.
`.env` and `.env.*` remain ignored; `.env.example` is the placeholder exception.

The client appends `/chat/completions` once, does not discover models/health,
does not follow redirects, does not use ambient proxies and verifies HTTPS TLS.
An explicitly configured HTTP gateway is **unencrypted**, not a secure channel;
use it only on the operator's trusted local network. There is no alternate host.
Each call uses a fresh client without conversation history or cookie reuse.
The `transport_security` field describes configured policy
(`tls_verification_enabled` or `unencrypted_http`), not a mock TLS handshake or
proof that an unsuccessful connection negotiated TLS. Custom CA/proxy settings
are not added; HTTPS uses the pinned client's default verified certificate bundle.

Keys/URLs are absent from prompts and public reports. HTTP error bodies,
exception strings, request headers, raw completions and separate reasoning are
not exported. HTTPX, HTTPcore and asyncio records emitted in the protected
request context are suppressed, including connection diagnostics.

**R1 process-wide effect:** the first guarded request also installs a persistent
filter on the `asyncio` logger for records whose module is `base_events` and
function is `_getaddrinfo_debug`. All records from that specific stdlib DNS
diagnostic origin are suppressed for the rest of the process, including
unrelated DNS lookups. This is deliberately not task-local: resolver executor
threads lack the request's `ContextVar`, and can log after timeout/cancellation.
The filter retains no keys, URLs or address registry and is not removed when a
request ends. It does not disable logging, change logger levels or turn off loop
debugging. Ordinary application logging and non-DNS asyncio diagnostics outside
the protected context remain available. Applications must not remove/bypass
these filters; other event-loop implementations or diagnostic origins require
separate verification rather than a claim of general log sanitization.

Config/response reprs hide sensitive fields; typed public evidence is additionally
checked for known key/endpoint fragments. This is not a general sensitive-data
detector for arbitrary real questions or databases: P1.2 is synthetic-only.

## Shared context and strict response contract

The versioned context projects catalog IDs, descriptions, units, source grains
and disclosures, plus this profile's confirmed population and booking-creation
time basis. It contains no SQLGlot expressions or source rows.
All twelve inputs use the same English system instructions, timezone
`Asia/Taipei` and `as_of = 2026-03-31T16:00:00Z`. Exact question periods are not
looked up or supplied by the evaluator.

The only supported response mode is **non-streaming JSON in message content**.
The request does not set `response_format`, tools or a reasoning flag; their
deployment support is unknown. Plain prompting does not guarantee valid JSON.

The assistant must return exactly one of these shapes:

```json
{"outcome":"request","request":{"metrics":["PERMITTED_METRIC_ID"],"start":"OFFSET_AWARE_ISO_INSTANT","end":"LATER_OFFSET_AWARE_ISO_INSTANT","timezone":"IANA_TIMEZONE","center_id":null}}
```

```json
{"outcome":"declined"}
```

The placeholders describe fields, not runnable requests. `center_id` is optional;
every other request field is required. Existing `FactRequest` validation applies,
including distinct admitted metrics, explicit offsets, positive half-open period
and an IANA timezone. Extra fields, SQL, answer values, duplicate keys, non-finite
numbers, invalid Unicode, wrong types, prose, code fences, multiple JSON values,
inline reasoning and unknown output modes fail explicitly. No JSON-fragment
extraction or reasoning stripping is attempted.

The provider envelope is an open interoperability boundary; the model-authored
FactRequest is a closed product contract. The HTTP response must be UTF-8 JSON
with exactly one assistant choice, string content and `finish_reason: stop`.
`index` is optional, but when present must be integer zero (not a boolean).
Unknown top-level, choice, message and usage metadata is ignored, not exported
or passed to the content parser. This includes provider-specific wrappers and
direct-vLLM choice fields such as `stop_reason` and token metadata.

Known semantic fields retain strict validation: competing error/streaming/text/
audio output, truncation, tool/function calls, logprobs and invalid required
fields are rejected. Known usage counters and detail counters must remain
bounded non-negative integers when supplied; unknown counters do not fill
missing known counters. Known optional OpenAI metadata is still type-checked.
Separately returned
string `reasoning`/`reasoning_content` is ignored, never parsed or exported.
Missing model/usage metadata is unknown, not fabricated. A returned different
model identity stops the panel as a configuration failure; if a deployment
returns an underlying identity rather than the requested alias, that requires
an explicit reviewed policy change, not an automatic alias/fallback repair.

Envelope failures retain an allowlisted `response_shape`: sorted recognized
top-level/choice/message key names, counts of unknown keys, object/array types,
choice count, index presence/type/zero-or-nonzero class, bounded known finish
reason or its type, model/usage presence, and fixed failure code/stage.
Unknown field names can themselves contain secrets, so only a fixed diagnostic
vocabulary is named; all others are counted. No arbitrary provider values, content, reasoning,
headers or addresses are copied. Unparseable/unavailable envelopes are marked
as such. Successful responses and content-level errors do not need a fingerprint.
Existing `invalid_response`/`unsupported_output` codes now stop a panel with
`envelope_incompatibility`; this is separate from malformed model JSON or a
wrong-but-valid request. Model-identity and budget stopping rules are unchanged.

The design lesson matches legacy V2's content extraction boundary, not its
planner or repair loop. This does not identify the precise rejected field in
the first live run: that run intentionally retained no raw responses. Its
manifest, reports and outcome remain historical evidence, not repaired results.

For trusted programmatic callers, optional partial `constraints` use the same
request field names. They are validated before sending, included in shared
context and checked against the proposal (instants normalized to UTC).
Conflicts reject execution rather than replacing fields. The evaluator never
uses this facility to pass gold. Without a bound constraint, a wrong but valid
metric/time/center interpretation executes unchanged and remains wrong.

## Prepare offline, then obtain separate authorization

From the repository root:

```bash
mkdir -p .artifacts
run_dir=$(mktemp -d .artifacts/p12-local-XXXXXX)
.venv/bin/python tools/fixture.py build --db "$run_dir/learningops.sqlite"
.venv/bin/python tools/fixture.py check --db "$run_dir/learningops.sqlite" \
  --report "$run_dir/fixture-report.json"
.venv/bin/python tools/smoke.py --db "$run_dir/learningops.sqlite" \
  --output-dir "$run_dir/prepared"
```

The default command is preparation only: **zero network calls**, no real key
needed and no environment-file loading. It writes a pinned manifest and a
dry-run report, not simulated model answers. Existing output directories are
refused; use fresh paths rather than removing prior evidence.

The panel is exactly Q01_booked_amount, Q02_booking_count, Q03_booked_seats and
Q04_known_learners in zh-TW/en/ja: **12 inputs, four semantic families, one model**.
The recorded interleaved order rotates languages across three rounds. Calls
are independent and stateless. The earlier proposed 24-input panel is not run.

The manifest pins code/commit/dirty state, runtime versions, prompt/context,
catalog, accepted case/language/oracle/schema/seed identities, question hashes,
database bytes and settings. Live execution refuses drift rather than silently
repinning. Use a stable, disposable fixture without active SQLite journal/WAL
sidecars or concurrent writers. Synthetic source admission is capped at 16 MiB
and requires the accepted schema and complete seed, not an arbitrary local DB.
Installed dependencies must match the lock before preparation or execution.
Reports preserve all unrun cases and reasons.
The manifest is evaluator-only: it contains accepted question text and one gold
scope/value per family. The runner passes neither that object nor its oracle
fields to the model. Do not use the manifest as model context.

**Prepared live command — NOT EXECUTED; requires a subsequent owner instruction:**

```bash
.venv/bin/python tools/smoke.py --live \
  --manifest "$run_dir/prepared/manifest.json" \
  --db "$run_dir/learningops.sqlite" \
  --env-file .env \
  --gateway-retries disabled --gateway-fallback disabled --gateway-cache disabled \
  --output-dir "$run_dir/live-01"
```

Do not copy those three policy assertions blindly. Before authorizing the run,
the owner must obtain the operator's effective selected-route retry, fallback
and cache policy. These flags record an operator attestation, not independently
verified gateway evidence; actual enabled policies must be reported honestly.
The tool never changes shared gateway configuration. An available key or a
`--live` flag alone is not authorization.

| Bound | First panel |
| --- | --- |
| Client attempts | At most 12; one per input, concurrency 1 |
| Client retries / planner repairs | 0 / 0 |
| Requested settings | Model `gemma-4-31b`, temperature 0, max_tokens 2048, stream false |
| Total per-call / panel deadline | At most 60 / 900 seconds |
| Input / serialized request / HTTP response | 4 / 32 / 128 KiB, measured as bytes |
| Kernel | Same read-only path; default two-second budget reduced to remaining call time |

The asynchronous total deadline covers sending and reading the whole response,
not just individual socket operations. Kernel time is also checked against the
remaining call budget, subject to the kernel's documented cooperative/OS I/O
limitations. The panel checks its remaining deadline before each call.
Timeouts cancel client work and close connections; they do **not** prove remote
GPU inference stopped. Client attempts do not prove upstream generation counts;
server retry, fallback and cache can change the relationship. Temperature 0 is
not proof of determinism.

Stop on auth/configuration failure, two consecutive transport/timeouts, or
budget exhaustion. Stop after the first deployment-envelope incompatibility;
preserve that failed input and mark remaining inputs not-run. HTTP 429/5xx count
as transport failures. A model-content JSON or
interpretation failure is recorded without rescue; the next distinct input may
still run. Attempt/output accounting is checkpointed before requests so an
interruption remains incomplete, with not-run cases preserved.
Immutable exclusive-create checkpoints retain earlier states; `report.json`
atomically points to the latest owned checkpoint. On an abrupt process loss,
an `in_progress` reservation is a possible unfinished attempt, not proof of zero
sends or completed upstream inference. Do not resume it as a new authorized run.

## Evidence and offline validation

Safe reports separate transport, response validation, JSON parsing, request
validation, interpretation, kernel execution and value agreement. Grading checks
exact metric coverage and normalized time/center/timezone before declaring a
number correct. Matching values under a wrong scope are not correct answers.
Malformed model content is `invalid_output`, not a transport operational failure.
Wrong typed scope remains `wrong` even when an unknown entity prevents execution;
numeric agreement is unassessed when scope is wrong, rather than rescuing it.
Per-language counts and all-three-correct families retain errors, refusals and
not-run inputs. A complete Fact Pack proves a scoped calculation, not that the
model understood the question.

Run the protected suites separately from P1.2 tests:

```bash
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_fixture test_multilingual_cases test_review_witnesses -v
.venv/bin/python -m unittest discover -s tests -p 'test_kernel*.py' -v
PYTHONPATH=tests .venv/bin/python -m unittest test_gateway test_model test_smoke -v
PYTHONPATH=tests .venv/bin/python -m unittest test_gateway_logging -v
PYTHONPATH=tests .venv/bin/python -m unittest test_envelope -v
.venv/bin/python -m unittest discover -s tests -v
```

The first two selectors preserve the 27 P0 and 80 kernel/CLI tests. Fixture
checking separately retains 18 references and 9 mechanisms. New tests use fake
transports and disposable real SQLite databases, including wrong-but-valid
requests and failures; they are **offline/mock evidence, not live model quality**.
Protected gold and question text are not changed to make checks pass.
The additive R1 regressions retain the stock HTTPX/HTTPcore/AnyIO and asyncio
diagnostic path with DNS/TCP stubbed and real-socket guards. They cover debug
on/off, success/failure, delayed executor completion after timeout/cancellation,
and unrelated benign logging. Log capture continues until resolver work finishes;
returning from the request alone is not proof that late diagnostics are safe.

Live deployment compatibility, quality of Gemma's trilingual interpretation,
native-language equivalence, repeated-run stability, real-data transfer and
generalization remain unestablished. Owner review precedes main promotion;
P1 completion still needs the separately authorized smoke and assessment.

Protocol references (documentation only, not deployment probes):
[LiteLLM compatibility](https://docs.litellm.ai/docs/proxy/user_keys),
[JSON-mode support](https://docs.litellm.ai/docs/completion/json_mode),
[gateway retry/fallback](https://docs.litellm.ai/docs/proxy/reliability).
