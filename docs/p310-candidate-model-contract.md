# P3.10 candidate-aware compatibility

Status: implemented offline after the two-phase ruler checkpoint was accepted in
[Issue #56 comment 5779387041](https://github.com/cinic0101/grepbit/issues/56#issuecomment-5779387041).
The owner-approved implementation direction is recorded in
[Issue #56 comment 5779208948](https://github.com/cinic0101/grepbit/issues/56#issuecomment-5779208948).
The initial checkpoint passed 156 historical tests and produced eight passing
new rulers plus six expected missing-admission assertions before runtime edits.
Those rulers now pass. This document is
not live authorization and does not change any historical evaluation contract.

## Baseline and admitted scope

Start: `dev@16d33c4fe0abeebeee10047a4c07d8aae87c74a8`.
Default identity remains `gemma-4-31b`. The only alternative is the complete tuple:

| Field | Exact value |
| --- | --- |
| candidate_id | p39-gemma-4-12b-it-deployed-v1 |
| candidate_identity_sha256 | 2267efd409cae69270a3e72837218081256bf00ea7cdfe7c952f7b44e0cae802 |
| model_alias | gemma-4-12b-it |

The SHA is the byte hash of the accepted sanitized deployment identity, not a
hash of this smaller tuple. Alias-only selection is insufficient. No route,
credential, arbitrary provider parameter, or model registry discovery is added.

## Identity API and ownership

`grepbit.gateway` owns a small frozen `ExpectedModel` value and a closed identity
validator. The legacy default is explicit in code, never derived from arbitrary
environment values. The only non-default valid tuple is the one above.
`tools/p3_candidate_model.py::admit_candidate(mapping)` delegates to that closed
validator and returns the immutable value; it rejects missing/extra fields and
all tuple mismatches with a safe `invalid_configuration`. The runtime does not
import tools, artifact paths, deployment documents, or evaluation assets.

`GatewayConfig(..., expected_model=identity)` and
`GatewayConfig.from_env(..., expected_model=identity)` receive that typed value
as a keyword-only argument. No argument preserves the existing 31B default.
Strings, dictionaries, and duck-typed identity objects are not substitutes for
the validated value. Validate this argument before reading an explicit env file.
An identity object is admission data, not a cryptographic authority token or a
sandbox against malicious Python callers. The governed runner enforces live
authorization separately before it constructs configuration or a client.

Required relationship:

```text
exact admitted candidate tuple
  -> immutable expected identity
  -> configured model equals expected alias
  -> request payload model
  -> explicit parser expectation
  -> requested/returned evidence
```

The env loader keeps existing precedence and defaults. An omitted model env
variable still resolves to 31B; under an explicit 12B identity that is a mismatch,
not permission to silently change route. Supplying 12B only through env remains
invalid. Configured 31B with expected 12B (or the reverse) is invalid. The new
candidate runner also validates the accepted candidate-document byte hash.

The shared parser gets its expectation from validated client configuration,
never from a provider field or mutable evidence dictionary. A different returned
alias is `unexpected_model`, stops native execution, and triggers no fallback.
Malformed known model metadata remains rejected. Missing/null model metadata
retains the historical parser meaning, unknown; however, a candidate
compatibility success additionally REQUIRES an observed exact 12B identity.
Unknown identity cannot pass the new probe. Recipe evidence continues to suppress
unaccepted returned aliases, preserving the safe reporting boundary.

P1's normal/default entry and all existing runner CLIs stay 31B-only. There is no
new candidate option in historical formal/stability/development runners. The
shared parser can carry the explicit expectation without changing P1 semantics.

## Semantic and wire rulers

`tests/fixtures/p310_identity_baseline.json` was captured before any production
edit from the exact accepted commit. It pins P1 and recipe context identities,
instruction/schema/response-format hashes, limits, 24 protected source hashes,
and two serialized wire-body hashes. The question is existing exposed E01
English; no fresh questions were inspected or authored. Synthetic responses
and mock HTTP are test fixtures, not evaluation evidence.

| Identity | Unchanged SHA-256 |
| --- | --- |
| Recipe instruction | 8fbfa08c428220d452b7f83ccea7c908fdc2349641510bd8911d0055fa35acf5 |
| Recipe context | 1cae4d1955ab76ed2205b5b22fc85a33fabaa3274dca618af5cd4cade656d151 |
| Recipe system message | 911ebd780de32eadc535c2b52f55c3c013a7ca809f3c5905f9c0913dcebfc3cb |
| Output schema | a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00 |
| response_format wrapper | 4f4e3ea6ec8ba6951d353d15c6388633f7c687ae0d19bb5925e80047dbc7fc86 |
| E01 recipe wire body, 31B | 6ba240b00959589ef5579527019c8e37dee6856bc6bb50705c01ebd41c2749bf |

The baseline recipe body is 25,259 bytes. Post-change 31B body must be identical.
The equivalent 12B body must differ only by the model field. System/user strings,
schema wrapper, temperature=0, max_tokens=2048 and stream=false are identical.
Input/request/response caps remain 4096/32768/131072 bytes; call timeout remains
at most 60 seconds. No prompt/context/schema version bump is justified.

The rulers retain default 12B rejection. The initial red assertion instead names
the missing full-candidate admission API; accepting an alias through env would
be the wrong repair. The guarded module-existence assertion is intentional
static contract evidence, not an ImportError/setup failure. Once implemented,
the same rulers execute tuple tampering, config mismatch, exact wire parity,
returned-model mismatch and native Overview dispatch with mocked responses.

## New compatibility artifact boundary

Narrow entry: `tools/p3_candidate_probe.py`. The existing probe's private
`_run_probe` owns one shared reservation/runtime/publication lifecycle; closed
legacy and candidate callers provide their respective admission and evidence
policies. Transport/config/parser are not duplicated. The historical
`tools/p3_probe.py` public 31B contract and report versions stay intact.

Purpose-specific identities:

- `p3-candidate-compatibility-packet-v1`
- `p3-candidate-compatibility-authorization-v1`
- `p3-candidate-compatibility-manifest-v1`
- `p3-candidate-compatibility-report-v1`

The immutable pre-authorization packet contains no owner URL. It pins the exact
candidate tuple/document hash, final accepted clean-dev tooling SHA, current
source graph (including all new helpers), semantic identities, runtime entry,
synthetic DB/source identity, exposed question reference/hash, route/settings,
single-attempt stop contract and sanitized command template. Unknown fields or
drift fail closed. The only input is `E01_overview.en`, question SHA
`634a6e868a355af50ee7ca122282776aab6159573b16b5bd19f0277b4c67e57a`.
It does not contain questions/gold as model context or authorize regression.

Route remains retries enabled / fallback disabled / cache disabled;
transport `unencrypted_http`. Expected loaded model and transport must match.
One runtime invocation and one client attempt maximum; concurrency 1; timeout
at most 60 seconds; no client retry/repair/fallback/resend/resume. Upstream attempts
are unknown. Reservation must be durable before the possible send. Publication
or interruption failures preserve evidence; no second run to obtain clean output.

After merge, preparation uses final clean dev. The owner accepts the exact packet
byte hash on Issue #56. A separate immutable authorization envelope binds that
hash and a nonblank exact-shape Issue #56 comment reference. Validate envelope,
packet, checkout, candidate, source, DB and route before env/config/client/runtime.
`--live` alone is never sufficient. No GitHub/provider lookup by the runner.

The new report may expose only closed compatibility stages, native execution
stage, exact admitted requested/observed model, safe usage/latency/status/errors,
reservation/attempt counters and pinned identities. No raw completion/reasoning,
proposal, native payload/facts/SQL, gold, private endpoint or credentials.
Missing returned-model metadata cannot produce compatibility success. Schema
request acceptance is not proof of server-side enforcement. Native execution
stage is explicit; success criteria must not silently equate valid clarification
or decline with exercising the native request path. No grader or quality score
is used by this compatibility runner.

## Historical source and archive boundary

The three intended protected runtime edits are `grepbit/gateway.py`,
`grepbit/model.py`, and `grepbit/recipe_model.py`, only for identity plumbing.
The remaining 21 protected files stay byte-identical. The new code/source
identity will differ from the old full protected freeze; report that honestly.

Do NOT weaken `p3_admission.candidate_identity()` or repin historical freezes to
make new sources look frozen. The candidate path uses a new current-source
identity plus explicit immutable semantic rulers and ancestry. Legacy freeze
validation may correctly reject execution under changed sources. Archived readers
must still validate historical evidence independently of current execution
eligibility. Regression fixtures for old freeze creation should use the matching
historical source witness, with an explicit real-current-source rejection test;
never patch away drift to admit a new live run.

No historical manifest/report is relabeled for 12B. Old formal/stability results
stay final, and old 31B compatibility does not become 12B proof. Candidate live
support does not authorize 28-case regression, fresh authoring, stability or P4.

## Offline verification and future command shape

The initial rulers are extended with synthetic packet/auth/source/DB drift tests,
authorization-before-env guards, one-attempt success/failure/interruption and
publication tests, exact observed-model success gating, report whitelist and
wrong-version archive rejection. Test historical 31B archive readability.
Only synthetic configs and MockTransport are used; never load the real env or create
the real candidate packet/authorization on the feature branch.

Run targeted gateway/model/recipe and candidate suites first, then one complete
offline suite covering P1/P2/P3/formal/stability/probe/archive. No dependencies
change. Review full diff/source changes and close out under the authorized Git
workflow; do not merge or close Issue #56. Implementation approval is not live
authorization.

After merge, the offline preparation and binding modes are separate:

```bash
.venv/bin/python tools/p3_candidate_probe.py --prepare \
  --candidate-identity "<ACCEPTED_CANDIDATE_DOCUMENT>" \
  --db "<ACCEPTED_SYNTHETIC_DB>" --accepted-commit "<FINAL_CLEAN_DEV_SHA>" \
  --gateway-retries enabled --gateway-fallback disabled --gateway-cache disabled \
  --transport-security unencrypted_http --output-dir "<FRESH_PACKET_OUTPUT>"

.venv/bin/python tools/p3_candidate_probe.py --bind-authorization \
  --packet "<EXACT_PACKET>" --owner-authorization-reference "<ISSUE_56_OWNER_COMMENT>" \
  --output "<FRESH_AUTHORIZATION_FILE>"
```

Only after review of the exact packet SHA and separate owner authorization:

```bash
.venv/bin/python tools/p3_candidate_probe.py --live \
  --packet "<EXACT_PACKET>" --authorization "<EXACT_AUTHORIZATION>" \
  --db "<ACCEPTED_SYNTHETIC_DB>" --accepted-commit "<FINAL_CLEAN_DEV_SHA>" \
  --env-file "<EXPLICIT_LOCAL_ENV_FILE>" \
  --gateway-retries enabled --gateway-fallback disabled --gateway-cache disabled \
  --output-dir "<FRESH_LIVE_OUTPUT>"
```

No mode defaults to live. The runner verifies local HEAD, clean `dev`, local
`dev` and cached `origin/dev` at that exact final SHA without fetching. The
candidate document must remain under the repository at the pinned relative path.
Never reuse a feature-branch packet. The env loader uses only the established
`GREPBIT_LITELLM_BASE_URL`, `GREPBIT_LITELLM_API_KEY`, and
`GREPBIT_LITELLM_MODEL` names; do not print their values.

Offline archived inspection is `--report --report-path "<LIVE_OUTPUT>/report.json"`.
It validates the candidate-specific versions and byte-identical packet/auth
snapshots without consulting current runtime source or loading configuration.
Stopped and interrupted runs remain evidence, not permission for a retry.
