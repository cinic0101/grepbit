# Query-kind selection: the extra call did not earn its cost

2026-09-14. **Prefer the one-call joint-policy candidate for the next wider
regression; do not introduce a router service or promote to production yet.**
Production sources, prompt defaults, gates and Web registrations are unchanged.
Plan/authority: [query-kind-study](../plan/query-kind-study.md).
Durable evidence: [query-kind-study-01.json](../../evidence/query-kind-study-01.json).
Detailed artifacts: `.artifacts/query-kind-study-20260914/`.

## What to distinguish during planning

Treat two questions separately inside the existing planning task:

1. What result is requested: individual records, an aggregate, or an existing
   latest/without entity selection? Preserve rows/duplicates/NULL for a real
   projection; do not fabricate GROUP BY/count to simulate a general listing.
2. Can the supplied definitions express the requested population, conditions
   and quantity? A related numeric field does not establish a business metric;
   having an amount does not establish the requested subpopulation. If required
   support is absent, refuse rather than silently removing the qualifier.

Explicit columns and ordinary aggregates already supported by the schema do
not require invented extra business definitions. A command such as list/show/
return does not alone determine the computation. These are generic instructions
to the model, NOT lexical Python gates or deterministic intent certification.
No new business facts, examples, retrieval or source-specific terms were added.

## Why this experiment, rather than assuming a router is better

[DIN-SQL (NeurIPS 2023)](https://papers.neurips.cc/paper_files/paper/2023/file/72223cc66f63ca1aa59edaec1b3670e6-Paper-Conference.pdf)
uses query classification to select construction strategies, but its SQL
complexity classes and models differ from ours. Its decomposition evidence
justifies a comparison, not a claim that Gemma needs another call.
[TrustSQL](https://arxiv.org/html/2403.15879v4) compares pipeline and unified
methods while evaluating feasible and infeasible questions; that motivates
measuring incorrect answers and unnecessary refusals separately.
[EntSQL (June 2026)](https://arxiv.org/html/2606.03363v1) studies business knowledge
beyond question/schema, reinforcing the distinction between selecting a shape
and having sufficient business definitions. These are design inferences; none
of these papers proves this Grepbit policy or a universal refusal guarantee.

The prior 2/8 operator-restriction study and unsupported-only fallback results
remain unchanged. This experiment routes before construction, and explicitly
compares that with adding the same policy to a single planning call.

## Three arms, shared execution path

- **Direct:** row-enabled v16 unchanged, one initial planning call.
- **Joint:** same v16 wire/context plus the generic two-part policy above;
  `query-kind-joint-v1`, one initial planning call, same PlanProposal output.
- **Split:** `query-kind-router-v1` returns rows/legacy/decline; then unchanged
  v16 builds rows or v15 builds legacy queries. A decline stops construction;
  a builder may still refuse after a positive route. Route/plan-kind mismatch
  is failed, not a credited refusal. No extra model reviewer.

All use actual shared ask(), schema/overlay visibility, gates, grounding,
compiler, SQL policy, read-only execution and a total 30-second RequestControl.
Original questions/as_of/context are the same across arms. SQL oracles execute
before planning and never enter the model context. Complete typed results,
duplicates, specified order and row projection names are compared in memory;
historical lossy report rows are not reused as a typed oracle.

## Main panel: 32 questions

20 answerable (13 row, seven legacy), 12 necessary-refusal cases. 26 existing
questions plus six new authored contrasts; these are not user holdout examples.
Arm order rotates per case. Gemma 4 31B, T=0, thinking off, serial on the
existing gateway; synthetic IoT/Service, grepbit_ro, sampling 0, no DB writes.

| Arm | Correct answers / 20 | Necessary refusals / 12 | Wrong answers | Unnecessary refusals | Failed | Calls | p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Direct v16 | 17 | 10 | 2 | 1 | 2 | 34 | 2.069 s |
| Joint, one initial call | 18 | 12 | 0 | 1 | 1 | 33 | 2.243 s |
| Split, route then build | 18 | 12 | 0 | 1 | 1 | 55 | 3.179 s |

Joint and split have identical per-case outcome categories, not merely equal
totals. The split arm spends 22 additional calls without recovering another
answer. Zero observed wrong answers in this panel is not a population risk bound.

Joint fixes the two known unjustified answers (`cov_mttr`, `cov_leased_fee`)
and retains the old `without` answer that direct v16 makes invalid. Both joint
and split match all 11 original base-row positive cases. The new critical-alert
row/count pair also matches under both; the command verb is not used as a
deterministic classifier.

In the split arm, MTTR and sibling-fact aggregation are routed to legacy despite
the predeclared decline expectation. The builder subsequently refuses correctly.
Thus even a correct final outcome does not establish router answerability
accuracy: its positive route is not a certificate or a reason to override later
refusals.

## Fresh-process sentinel repeat

Eight fixed cases, chosen during this study (explicitly NOT a holdout): original
details, MTTR, leased fees, without, NULL count, rented rows, VIP rows and
minutes-only records. Same prompts, no tuning after the first observations.

| Arm | Correct answers / 4 | Necessary refusals / 4 | Wrong answers | Failed | Calls |
|---|---:|---:|---:|---:|---:|
| Direct | 2 | 2 | 2 | 2 | 10 |
| Joint | 3 | 4 | 0 | 1 | 9 |
| Split | 3 | 4 | 0 | 1 | 14 |

The same outcome differences recur. Main phase 122 calls, repeat 33: **155/160
actual calls**, including repairs and all stages. Latency is observational;
changing endpoint/batch conditions are not controlled or causally attributed.

## Residual failures: do not solve them with another planner call

1. **Unprojected sort key.** Every arm proposes minutes-only rows ordered by id,
   correctly choosing the intended base and projection, but the existing row
   contract permits explicit ordering only by projected fields. Repair removes
   the qualifier but retains id, so validation still fails. A diagnostic-only
   removal of explicit order uses the compiler's identical default visible-PK
   order; independent PostgreSQL comparison matches full typed ordered values.
   The question is expressible using the current default, but the natural
   explicit representation is unnecessarily constrained. No production rule was
   changed and the failed live case stays failed.
2. **Old Return vocabulary gate.** All three planners produce the correct
   non-NULL-minute count. The gate maps the output command `Return` to business
   concept `returns`, then returns concept_not_mapped. Read-only compilation of
   that actual plan matches the independent SQL reference. The minutes-only
   question also contains Return: after correcting its sort shape diagnostically,
   this same gate would still block it. Fixing the first error alone is not an
   end-to-end repair. Gate diagnostics are not scored answers or a gate bypass
   recommendation.

These are direct evidence for separate harness work, not grounds to declare
all remaining semantic errors solved. No new English exception or automatic
gate relaxation was added.

## Validation, boundaries and next order

60 focused tests passed (11 new), static passed, broad offline **2,013 passed**.
Two-phase research sources match the frozen hashes. The initial missing-module
collection error was setup failure, not contract evidence; placeholder failures
only marked unimplemented study behavior. No persistent/public contract changed.

1. Prefer the single-call policy candidate; do not build an independent router
   or replace the disabled production fallback yet. Run it over all 64 older
   IoT/Service controls plus new neighboring questions before any opt-in Web
   promotion. This panel deliberately sampled only six of the legacy controls.
2. Separately specify a safe representation for ordering by visible base
   columns not returned in a row projection. Test visibility, hidden keys,
   duplicates/NULL, direction, stable ties and LIMIT; do not silently add the
   order column to the answer or drop non-default ordering.
3. Reuse the existing source-scoped gate research and command/business-word
   contrast panel for the Return failure. Any replacement must restore correct
   answers AND still catch real scope omissions. Another router does neither.
4. Keep conversion/independent aggregates isolated until this single-query
   planning path is accepted. No new data source or framework is needed to
   resolve the two demonstrated residual failures.
