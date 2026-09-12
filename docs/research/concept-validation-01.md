# Concept validation pilot: do not promote either LLM gate

2026-09-12. Prompt `concept-shadow-v1`; Gemma4 31B, temperature 0, thinking
off. Production planner v15, orchestration v3 and all existing gates are
unchanged. Authority and predeclared stop conditions:
`../plan/concept-validation-pilot.md`. The owner approved the ruler checkpoint
with "沒問題", authorizing this bounded implementation and measurement.

## What was measured

Thirty author-written development questions: ten semantic families translated
into zh/en/ja. Twenty-four POS questions and six service questions. Fixed
candidate plans, not newly generated live planner outputs. The synthetic schema
is a projection specified in `evals/fixtures/concept_pilot.json`; the service
source supplies negative/unavailable-concept controls, not a positive reviewed
service metric. Do not call this a second-source generalization result.

Each round has 30 independent-intent calls and 51 direct-audit calls (81 total).
The 51 question/plan pairs contain 18 known wrong qualifier mutations, 24 correct
controls (including six no-qualifier controls), and nine unresolved pairs
(three missing-definition questions and six ambiguity probes). Translations,
paired plans and repeated rounds are dependent observations, not 102 independent
questions. No actual rows, SQL or golden labels are sent to either model.

- **A:** existing lexical/name-presence heuristic, unchanged.
- **B:** the same lexical extraction followed by the bounded structural check.
  The trigger does not know polarity or role; those remain Unknown.
- **C:** independent LLM extraction, then the same structural check.
- **D:** direct LLM question/plan audit with an explicit qualifier-only rubric.
- **Oracle-input diagnostic:** hand-labelled requirements, then the structural
  checker. This is a checker test, not a deployable arm or model result.

The checker handles the pilot's same-base NULL predicates, signed polarity,
population/numerator placement, verified metric filters and whole shares.
Conflicting predicates, extra predicates, segments, time/output constructs and
unrecognised shapes return Unknown. No-request returns not_applicable, **not**
semantic verification. The checker does not verify quantity/aggregate choice,
time interpretation, unsolicited qualifiers in no-request answers, arbitrary
equivalence, or all requirements of the question.

## Results

Each cell below is round 1 / round 2. A and B repeat mechanically. In these
metrics, pass or not_applicable would allow the plan past this qualifier check;
errors and Unknown do not. This measures hypothetical gate behavior, not served
answers. Not_applicable is counted as an escape when a requirement was missed.

| Arm | Known wrong pairs allowed / 18 | Correct controls blocked, unknown or error / 24 | Unresolved pairs allowed / 9 |
|---|---:|---:|---:|
| A | 15 / 15 | 7 / 7 | 5 / 5 |
| B | 3 / 3 | 19 / 19 | 2 / 2 |
| C | 0 / 1 | 6 / 5 | 2 / 2 |
| D | 0 / 0 | 0 / 0 | 1 / 1 |
| Oracle-input | 0 / 0 | 0 / 0 | 0 / 0 |

B's apparent reduction in wrong passes comes mainly from abstaining: 41 of 51
pairs are Unknown. It is not an improvement at comparable answer coverage.
C allows 20 then 22 pairs; D allows 25 in both rounds. Their answer coverage
differs, so these are not controlled risk-at-equal-coverage comparisons.
Unresolved escapes must not be hidden by the known-wrong-mutant denominator.

C matches the complete intent/polarity/role labels on **22/30 in both rounds**:
zh 7/10, en 7/10, ja 8/10; POS 18/24, service 4/6. The intersection with the
21 required concept labels is 16/21; it predicts 19 concept labels including
three spurious requirements. Errors are included as misses, not successful
abstentions. These are development-set counts, not calibrated confidence.

| Calls | Round 1 | Round 2 |
|---|---:|---:|
| C valid outputs / calls | 27/30 | 28/30 |
| D valid outputs / calls | 51/51 | 51/51 |
| Transport failures | 0 | 0 |
| C successful-call p50 / p95 | 1.162 / 2.240 s | 1.127 / 2.137 s |
| D successful-call p50 / p95 | 0.409 / 0.612 s | 0.407 / 0.419 s |
| Provider-reported total tokens | 78,442 | 78,444 |

These are added audit-call latencies, not end-to-end ask latency; failed-format
calls are excluded from these latency percentiles but retained in the reports.
The endpoint's cache/batching state was not controlled.

## Concrete failures and what they imply

1. **Unavailable meaning becomes no request.** Both rounds classify the Chinese
   and English service refund-amount requests as not_requested, despite the
   prompt explicitly distinguishing unavailable bindings from user intent. C
   therefore lets a work-minutes plan pass this qualifier check. The Japanese
   version identifies the request and the checker returns binding_unavailable.
   A blocks the Chinese example; replacing A with C would introduce an escape.
2. **Including a subset is mistaken for restricting to it.** All three member
   share translations specify the denominator includes returns. C adds a
   return-only population requirement as well as the correct member numerator
   requirement. The checker cannot validate this mixed shape and returns
   Unknown even on the correct ratio. Adding vocabulary exceptions would hide,
   not solve, the inclusion-versus-restriction distinction.
3. **The same total score hides different risk.** All three direct return-amount
   extractions fail output validation in round 1. In round 2, Chinese/Japanese
   still fail; English instead returns not_requested, allowing the inverted
   return predicate. Exact intent score remains 22/30. The second instrument
   records a schema-validation value_error for its two format failures; it
   deliberately stores neither raw invalid model text nor validation inputs.
   The evidence does not identify the exact first-round invalid payload cause.
4. **A direct judge can certify an unspecified reading.** D labels the Chinese
   ambiguous return-rate question with a raw return-amount SUM as pass in both
   rounds. It never emits Unknown on any of the nine unresolved pairs: eight
   become fail and one pass. Passing the 18 deliberate predicate mutations is
   therefore not sufficient to trust its judgment about missing meaning.

All 81 corresponding request payload hashes match across the two rounds. D's
51 verdicts match exactly; C's English return-amount outcome changes. The first
round runs at 02:26:18-02:27:12 UTC and the second at 02:28:54-02:29:43 UTC.
This is a short time-separated repeat, not a broad session/load stability study.
It does not establish batching as the cause of variation.

## Decision and next direction

**Do not promote C or D; do not expand to 120 questions in this slice.** The
predeclared stop criteria are met: C introduces a missing-meaning escape and
adds wrong requirements; D mishandles unresolved interpretation. D performs
better than the proposed decomposition on the bounded controls, which is
evidence against claiming the split architecture is already the better design.

The structural checker is useful for diagnosis given correct requirements; it
does not make an incorrect premise reliable. Keep these two experiment
modules outside src, with no runtime hook, extra production model call or new
language exceptions. The 30 questions remain development data. A new hypothesis
must get separate evidence rather than reinterpret this pilot as acceptance.

Potential follow-up is narrower: investigate distinguishing requested metrics
from qualifier restrictions and explicitly inclusive populations, or use D only
as an offline reviewer whose disagreements are adjudicated. Neither is approved
as a new served policy here. Capability-rule selection and A5/A4 remain separate
work; no evidence from this study resolves those issues.

## Validation, artifacts and limits

Final full offline: **484 passed**, no errors/failures/skips. Static gate passes.
The new instrument has 41 focused tests; the 47 original ruler tests remain
unchanged. Initial import/setup errors were corrected before measurement; the
first live startup failed on an immutable settings assignment **before sending
any request**. A fake-client full-run/circuit-breaker test now covers that path.
These setup failures are not semantic failures or model calls.

Artifacts under `.artifacts/concept-pilot-20260912/`:
- `offline-baseline.json`: deterministic A/B/oracle baseline.
- `live-02.json` and `.jsonl`: first complete round.
- `live-03.json` and `.jsonl`: second complete round, safe format-error codes.
- `focused-03/`: 85 passes before the three diagnostic-code tests.
- `focused-04/`: 41 instrument tests including the diagnostic-code tests.
- `static-final/`, `offline-final/`: final code validation.

Durable manifest: `evidence/concept-validation-01.json`. Each complete live report
has input/source/request hashes and confirms source unchanged during its run.
Only error diagnostics and their tests change between rounds; prompts, cases,
decisions and all 81 request hashes do not. Runtime code and earlier source/test
files match the ruler baseline byte-for-byte. Prior uncommitted work is preserved.
162 real model requests total; zero PostgreSQL calls, row reads, installations,
stage/commit/push or persistent database changes. Existing ignored credentials
are loaded opaquely; outputs contain no credential or endpoint URL. All own runs
finished. HEAD remains 746f168; source hashes identify the dirty implementation.
