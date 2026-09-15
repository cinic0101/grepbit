# Explicit details mode: accepted as a bounded shared-service capability

2026-09-15, baseline fe96f5e. The joint strategy remains rejected; this delivery
adds an explicit caller choice to the existing service, not automatic routing.
Owner approved the plan and autonomous checkpoint decisions. Root sole writer;
readonly synthetic Service/IoT and the existing Gemma gateway only. No customer
DB writes, provider change, deployment, push or restart of the owner's Web.

## Contract and implementation

`query_kind=rows` is distinct from datasource `allow_rows`. The existing default
planner/fallback is unchanged. Disabled sources stop before binding/planning;
invalid mode values are input errors. Shared ask stops a non-rows proposal before
normalization/compilation with failed/request_query_kind_mismatch. This is an
operational failure, not a necessary refusal. Ordinary row permissions, filters,
grounding, compiler, SQL policy, executor, visibility, limits and lifecycle remain
shared. No new query algebra, router or second query system.

The v17 row wire gains only the frozen explicit-mode instruction and separate
request field, revision `plan-classify-json-v19-explicit-rows`. Original questions
are not rewritten. The instruction is not a deterministic scope certificate.
An aggregate question in Details asks for a mode change (ambiguous); a defined
but unrepresentable rows+without/join declines unsupported; missing definitions
decline semantic_gap. Correct rejection reasons are assessed separately.

The additive response echoes query_kind, including failed requests. MCP
capabilities and local Web config advertise allowed kinds. The English page
locks mode with the other query inputs and resets to Default on source change.
Only the new `evals/fixtures/dev_web_rows_datasources.json` profile permits rows;
the original profile is untouched. See `../knowledge/local-web.md` to launch it.

## Rulers and validation

Private prototype ruler: five intended failures/two passes against the old
fallback, then seven passes. An earlier fake-client setup failure and the verify
wrapper's rejection of ignored test paths are explicitly NOT behavioral evidence.
The corrected private ruler uses a simulated transport, not a live request.

Public entry ruler: ten intended failures/four passes, after correcting one
test-local missing fixture. Tests cover source permission, output-kind mismatch,
mode echo, ordinary aggregate compatibility, preserved declines, invalid input,
factory isolation, cancellation and HTTP/MCP forwarding. Final related focused
gate: **114 pass**. Final static gate and **2,233 offline tests pass**, zero skips.
No source edits followed that broad gate. JavaScript syntax check also passes.

Private artifacts: `.artifacts/explicit-rows-20260915/`; portable counts and
hashes: `../../evidence/explicit-rows-entry-01.json`. Source/probe inputs freeze
within each phase. Adoption intentionally creates a new runtime fingerprint;
pre-integration and integrated evidence are not described as one unchanged tree.

## Live and value evidence

| Phase | Requests | Correct answers | Appropriate refusals | False refusals | Wrong / operational | Gemma calls |
|---|---:|---:|---:|---:|---:|---:|
| Explicit-mode known panel | 24 | 13 | 10 | 1 | 0 / 0 | 25 |
| Prespecified targeted repeat | 4 | 2 | 1 | 1 | 0 / 0 | 4 |
| Integrated HTTP/MCP exact-output replay | 24 | 13 | 10 | 1 | 0 / 0 | 0 |
| Integrated HTTP/MCP new requests | 9 | 4 | 5 | 0 | 0 / 0 | 10 |

Total **39/100 actual model attempts**, including repairs, zero transport errors.
These are known regression/owner-style cases, not unseen-user generalization.
Refusals are not included in the correct-answer numerator. The original 13 row
cases yield 12 correct answers; the additional non-PK minutes projection yields
one more. All **14 proposed plans are rows**, including the one gate-blocked
proposal. This is different from claiming 14 correct answers or rewriting the
previous fallback's 7/13 value-correct score as a plan-kind score.

Independent PostgreSQL SQL establishes complete projection, values and order.
Every answered row plan also matches the same reference on two in-memory DuckDB
instances: source identities/FKs and times are preserved, while non-key minutes
and fees vary to distinguish duplicates, NULL/zero, and top-k ties. These extra
instances are discriminating value checks, not additional user questions. No
reference SQL, answer rows or witness values enter model prompts.

`kind_minutes_records` still selects the right rows plan but the existing
concept_not_mapped gate blocks English "Return". Its repeat is the same false
refusal. The equivalent "List" control succeeds including duplicate/NULL values.
No vocabulary exception or gate relaxation was used. Ten refusal controls have
an appropriate reason: missing scope, mode conflict or unsupported row construct;
none passes just because an unrelated guard failed.

Before integrated calls, all 24 candidate contexts match the private measurement,
and all 110 legacy/fallback contexts over 55 prior cases match the prior baseline.
The 24 stored raw-response sequences then travel through real loopback HTTP,
stdio MCP and shared ask against readonly PostgreSQL. Outcomes and public
projections agree, including mode, question, NULLs, assumptions and request ID
ownership; debug raw outputs remain excluded. Replay is not new model sampling.

The nine fresh HTTP requests include ordinary/top-k/duplicate details, lease
details, aggregate-mode conflict and rows+without. Default-mode controls retain
MTTR/lease semantic gaps and correctly answer the Chinese February-without case.
Same question: unsupported in the bounded Details mode, answered in Default;
the mode is a capability constraint, not an assertion that the data cannot answer.

Browser DOM smoke on an isolated temporary tab confirms English UI, default mode,
enabled Details in the opt-in profile, and source-change reset/reporting date.
No additional browser-submitted model question; this is not a full visual or
accessibility audit. Both owned temporary Web probes and the tab were closed;
the owner's original Web was not restarted.

## Decision, limits and follow-up

Accepted: a usable, explicit base-record request through shared runtime/MCP/Web,
on deliberately enabled sources. Not accepted/claimed: automatic routing,
universal scope understanding, joined details, rows+without, PII-whitelist or
multi-tenant deployment readiness. Existing default behavior and historical
scores remain intact; the new profile does not silently change the old profile.
Research-only adapter/runners remain ignored evidence, not a production strategy.

Next, use the explicit entry for owner testing and preserve new counterexamples.
Continue the independent unit-conversion integration slice with value/unit and
missing-definition controls. Keep the Return gate issue separately visible;
do not block every capability on a universal gate replacement. Any future scope-
binding proposal must explain what new request evidence it uses before another
support-metadata experiment. Merely repeating definitions is not new evidence.
