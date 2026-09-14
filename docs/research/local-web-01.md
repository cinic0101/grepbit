# Local streaming web: served path works; visual browser validation remains

2026-09-14; initial implementation baseline `f0a0841`. The owner explicitly
approved the [HTTP boundary ruler](../plan/local-streaming-web.md), then requested
continuation. Root implements/reviews; no delegated writer, push or deployment.
Safe evidence: `../../evidence/local-web-01.json`.
Private artifacts: `.artifacts/local-web-20260914/`.

## Implemented scope

One dev Python bridge and local HTML/CSS/JS assets. The browser uses POST SSE,
the bridge is an actual stdio MCP client, and the normal governed ask pipeline
owns planning, grounding, compilation and readonly execution. No extra narration
model, correction card, intent selector or prompt/gate modification.

The final bridge uses **one child/session per web invocation**, not a shared
child. One active query remains the global limit. This implementation choice
satisfies invocation isolation without a reconnect supervisor: after child crash
or startup failure a subsequent user request gets a new process. Cancellation
closes no peer's shared session. Startup/cleanup costs are included in the bridge
wait; remote GPU termination is not claimed.

Host/origin checks, JSON/custom-header/body/field validation, sampling-zero explicit
fixture registry, public field projection, safe errors, no-store/CSP/text-node
rendering and late-result isolation implement the approved boundary. The server
does not infer from an arbitrary DSN that its contents are synthetic; the explicit
operator assertion and registered profile define that scope.

Starlette/uvicorn were already installed through MCP; they are now explicit dev
dependencies with no package-version changes. An attempted optional httpx testing
dependency was removed when the offline cache lacked it; no download/install was
performed. Tests instead drive ASGI directly, with separate real socket tests.

## Validation, kept separate

| Layer | Result | What it does not establish |
|---|---|---|
| New HTTP/lifecycle tests | 24 passed | Mostly ASGI requests/injected faults, not browser usability |
| Actual stdio subprocess faults within those tests | Startup failure, child exit, timeout each followed by successful next request | Not remote GPU termination |
| Real loopback socket controls, final bridge | Early progress, 429 overlap, disconnect cancellation, post-cancel success, exception, deadline and cross-origin rejection pass | Synthetic backend; no DB/model in these controls |
| Frontend JS under offline DOM shim | 12 synthetic result scenarios, hostile text sinks, NULL/zero/truncation/verification, fragmented UTF-8 SSE, incomplete stream and ignored late result pass | Not a browser, real DOM security test or screenshot/visual review |
| Final real HTTP -> stdio MCP -> Gemma/DB | Six cases, six model calls, six exact payload fingerprints, unique request IDs | Authored acceptance, not new user generalization |
| Broad gate | Fresh static and 1,899 offline tests pass, zero skipped | Not live browser validation |

Browser skill bootstrap could not start its control runtime: local Codex
configuration parsing failed (`features`, invalid map where boolean expected).
No global config was changed and no alternate unauthorized browser-control path
was used. **Actual browser interaction/visual testing is pending.** JS shim checks
are not relabeled as that missing evidence.

The final UI additionally locks query controls in flight and renders the returned
question visibly. This HTML/JS-only refinement followed the model run; the DOM
shim was rerun afterward. Model/HTTP Python source remained unchanged. Preserve
the pre-run asset hashes rather than pretending those calls exercised the later
visual refinement. No prompt change or extra model run was needed for this edit.

## Live results

Same six questions, contexts, original reviewed rules and reporting dates as
`serving-lifecycle-01`. All 24 available interpretation recipes were independently
rechecked in readonly PostgreSQL during preparation; no gold reaches the model.

| Case | Served result | Existing judgment |
|---|---|---|
| s01 | answered | disclosed reference match |
| s11 | answered | disclosed reference match |
| s14 | semantic_gap | appropriate refusal; preferred unsupported status still differs |
| i01 | clarify | known concept-gate false refusal; reference grader says unassessed/not_answered |
| i02 | answered | disclosed reference match |
| i10 | unsupported | appropriate refusal |

Three correct answers, two necessary refusal actions, one known false refusal.
Do not summarize this as five correct numerical answers or six successful user
answers. Zero model transport errors, no new interpretation or safety claim.
The complete MCP public payload matches the HTTP result fingerprint in all six
cases; raw values/completions stay out of saved live artifacts. Instrumentation
only meters calls and grades/hashes the original server output.

The first, shared-child implementation also ran these six cases once, with the
same judgments. After switching to request-owned children, they were rerun with
a fresh frozen preparation/output directory. **12 Gemma calls total this slice,
six on the final Python implementation**, within the 18-call budget. First-pass
evidence is retained separately, not added to independent sample counts. The
final UI launcher has no instrumentation or fixed-question restriction.

## Interpretation and next step

This is a usable local E2E entry and a separation of responsibilities: structured
evidence reaches the consumer without another probabilistic paraphrase step.
It does not fix wrong metric selection or the gate, and it cannot establish that
a later upstream agent will preserve the evidence. No historical scores changed.

Use the page on fixture questions; finish real-browser interaction checks once
the browser-control setup is available. Collect actual user questions for the
next acceptance panel. Do not create another framework or revive rejected gates
merely because the UI makes the existing failure easier to observe.

Closeout scope: tools/assets, two explicit dev dependencies, fixture registry,
24 tests and one synthetic MCP child, usage/research/roadmap documents and manifest.
New local HTTP format/security boundary implements the approved ruler; MCP public
format, request ID meaning, planner contract, production safety checks and grading
policy are unchanged. No DB writes, secrets persisted, public listener or push.
