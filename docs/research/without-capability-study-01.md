# Without composition helps locally; timestamp repair exposes a separate risk

2026-09-15, baseline `e08af91`. **Retain the generic composition explanation as
a research candidate, not a production replacement.** A local rescue is observed,
but the baseline flips on an identical-message repeat; Japanese row/absence
composition still fails. A boundary witness additionally exposes timestamp
precision loss that ordinary fixture execution would score as correct.

[Protocol/authority](../plan/without-capability-study.md);
[durable evidence](../../evidence/without-capability-study-01.json).
Fresh artifacts `.artifacts/without-capability-20260915/`. No runtime, gate,
compiler, public format, identity, security or Web-default changes. No router,
correction card, new business dictionary or customer-data access.

## Frozen intervention, same wire and execution path

Three arms: unchanged v15, unchanged `query-kind-joint-v1`, and
`query-kind-without-composition-v1`. The last replaces just one generic passage
in joint-v1 with: without restricts the base population; COUNT/SUM/AVG and
supported grouping operate on the surviving base rows. It explicitly retains
the prohibition on combining rows with without. No source/table vocabulary,
examples, SQL, gold plans, or additional definitions are supplied to the model.
The historical v16 research wire and all other context remain identical.

24 seen/authored capability controls: 12 absence questions (three languages,
SUM/COUNT, Service/IoT and multi-hop selection), three ordinary aggregates,
three row projections and six required refusals. Three separately named date
controls follow. Arm order rotates per case, calls are serial, Gemma 4 31B,
T=0, thinking off. Actual shared ask with 30-second RequestControl, readonly
synthetic PostgreSQL, sampling zero and the existing reviewed Service overlay.
Oracle queries execute before model requests. Typed full values, row projection
and declared order are checked; failed/truncated outcomes are not answers.

## Main capability panel: 24 cases

| Outcome | v15 | Joint v1 | Composition |
|---|---:|---:|---:|
| Correct answers / 18 answerable | 14 | 15 | 17 |
| Unnecessary refusal | 3 | 2 | 0 |
| Invalid model output | 0 | 0 | 1 |
| Wrong answers on answerable cases | 1 | 1 | 0 |
| Necessary refusals / 6 | 5 | 6 | 6 |
| Wrong answer on refusal control | 1 | 0 | 0 |

The composition arm improves two cases relative to joint-v1 in this run:

- Chinese SUM of estimates for tickets without event records: joint refuses;
  composition correctly uses SUM on tickets restricted by without ticket_events.
- English count of devices with no alerts: joint adds device_id grouping,
  returning no rows instead of scalar zero on this fixture; composition preserves
  the scalar COUNT. Full typed values distinguish these, not just SQL validity.

The remaining Japanese multi-hop case is **not rescued**. Joint refuses;
composition proposes `rows + without`, which is not legal. Repair repeats the
same invalid combination. This is a model-output validation failure, not a
backend transport outage or a necessary semantic refusal.

### Fresh-process, predeclared four-case repeat

Chinese SUM, Japanese multi-hop absence, zero-minute rows and missing MTTR were
selected before main results. Both joint and composition now answer two of three
answerable cases and correctly refuse MTTR. Joint still refuses the Japanese
case; composition again produces invalid rows+without.

Crucially, **joint answers Chinese SUM on repeat without any change**. Its first
request message hash equals the main-run hash, as does composition's own pair.
Composition answers it twice, but the treatment advantage does not recur on this
repeat. The previous slice's two joint refusals and this main-run refusal remain
valid observations; they do not establish deterministic failure. No causal
claim about endpoint batching, scheduling or model weights is justified here.

This supports further testing of composition guidance, not a stability or
generalization claim. These are authored/seen cases, not held-out user questions.

## What the prompt audit establishes, and what it does not

The current conditional without rule describes entity labels and COUNT as its
recipe; it does not explain arbitrary aggregation after population restriction.
Its language triggers enable that detailed rule for the Chinese/English absence
cases in this panel, but none of the Japanese absence cases. This is concrete
unequal information supply by the harness, not proof that all failures are
model-only. The separate always-present composition paragraph provides a more
accurate description without another keyword list.

However, Japanese SUM and COUNT already succeed without that conditional rule,
while Japanese multi-hop listing still fails with the new explanation. Missing
rule text alone is therefore not a complete root cause. Likewise, the single
replacement includes multiple explanatory clauses; this experiment does not
identify which clause caused each change. No keyword-trigger retirement or
production prompt rewrite is licensed by these observations alone.

## Prospective date acceptance, without rewriting history

New `evals/cases/tier0/iot_date_acceptance.yaml` applies the existing approved
policy with new IDs. The original iot.yaml SHA-256 is pinned by a regression
test and was not changed. Original scores remain original scores.

| Date control | v15 | Joint v1 | Composition |
|---|---|---|---|
| Date-only BETWEEN: include July 8 | Wrong boundary | Correct | Correct |
| Explicit July 8 exclusive | Correct | Correct | Correct |
| Precise July 8 noon exclusive | Wrong boundary | Wrong boundary | Wrong boundary |

Stored-plan replay independently confirms the older joint result agrees with
the inclusive policy, whereas the older v15 result agrees only with the old
exclusive oracle. Replay is not a fresh model success. Fresh planning yields
the table above, so policy reconciliation is distinct from capability improvement.

### New finding: repair changes noon to midnight

Every arm initially emits the correct instant `2026-07-08T12:00:00+08:00` in a
range scope. The existing `RangeScope` accepts **dates only**, so validation
rejects it. The model repair removes the time and produces end-exclusive July 8
midnight. That valid plan is then served, losing twelve hours of requested scope.

On the current PostgreSQL fixture, **all three wrong repairs match the reference
values**: no distinguishing records occur during the lost hours. Seven synthetic
boundary rows explicitly cover before/start, midnight, just before noon, noon,
late evening and next midnight. The precise reference has daily counts `[1, 2]`;
the repaired plans produce `[1]`. The study's boundary witness catches all three.
No existing database data was altered to create this test.

An independent manually constructed plan uses the **existing typed timestamp
gte/lt filters plus day grain**, not a new time-range contract. It matches both
the PostgreSQL reference and the boundary witness. Thus SQL/compiler capability
exists: the planner chooses the wrong representation, and repair corrects shape
by changing meaning. This is stronger evidence than speculating about model
intent, but not yet a production fix. Normalization and the evaluator were not
changed to hide this finding.

## Validation and closeout

Five date/panel rulers plus two prompt invariants; 18 focused tests pass with the
existing query-kind tests. Static passes, offline **2,035 tests, zero skips**.
The initial three date-test failures were DuckDB search-path setup failures,
not evidence of a product bug; corrected before live. A separate diagnostic
initially lacked required model configuration and stopped before any query/model
call; its corrected zero-model-call replay is recorded separately.

Main: 88 calls (81 initial + seven repair calls); repeat: nine (eight initial +
one repair). Total **97/120 actual model calls**. No source/evals changes during
live phases; broad-gate and live source hashes agree. SQL is readonly against
synthetic IoT/Service only. No push/deployment or promotion is implied by tests.

The pilot-validation discipline is material here: keeping boundary witnesses,
stored-plan replay, false refusals and invalid output separate prevented both
the timestamp false pass and an overclaim about the SUM rescue.

## Next recommended order

1. Prioritize the now-reproducible **repair precision-loss** path. First establish
   rulers for a failed timestamp-in-date-slot proposal and its semantically
   changed repair. Compare explicit guidance to use existing timestamp filters
   against stopping an unfaithful repair. Do not truncate timestamps, silently
   widen date scopes or expand public RangeScope without a separate decision.
2. Keep the composition candidate frozen for a later wider regression across
   rows, without and missing-definition controls. Do not tune further on the
   single Chinese question or use this small panel as a promotion threshold.
3. Keep Japanese rows+without and the Return gate as distinct tracked problems.
   Another router or disabling checks does not resolve either demonstrated
   failure. Fixture-only Web promotion still requires a separate acceptance
   decision after these risk/coverage tradeoffs are measured.
