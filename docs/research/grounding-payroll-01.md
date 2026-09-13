# Public-name grounding and payroll time roles

2026-09-13. Baseline `98654f7`. Two independent authored mechanism studies,
not a holdout, production rollout, prompt revision or historical rescore.
Owner authority and external scope: `../plan/active-work.md` current slice;
approved study order: `../plan/answer-acceptance-and-cause-studies.md`.

## Frozen protocol

`.artifacts/grounding-payroll-20260913/cases.json` contains the 12 authored
questions and allowed populations/time roles/components. `study.py` is a
one-off research driver, kept outside production/evals surfaces; `frozen.json`
records driver/case/schema/source identities, every initial message hash,
predeclared interpretation and value-oracle hash, and the full 60-job schedule.
These were frozen before the first Gemma request. The driver composes the
same `application.ask` and adapters as `evals/spike_tier0.py`; it does not fork
the served pipeline or patch it. Raw results exist only in memory; saved output
contains identifiers, codes, counts and hashes, not SQL/bindings/provider text
or returned row values. No personal column is indexed or sampled.

| Study | Questions | Arms | Repeats |
|---|---|---|---|
| Grounding | exact Chinese name, partial Chinese name, unique partial name in an English request, tied fragment, missing name, explicit exclusion | identical minimal public-store-name overlay; index absent versus present | 2 (24 jobs) |
| Payroll | unspecified quarters, explicit attribution, explicit payment in English, payment delayed into January, separate base/bonus outputs, non-payroll transaction-time control | original metadata; factual date comments expanded in memory; only the existing `base_salary_total` metric offered | 2 (36 jobs) |

Every second-repeat arm order is reversed. Calls are serial to the existing
Gemma4 31B endpoint, temperature 0, thinking off, 20-second per-call timeout,
one repair turn, maximum 180 total transport attempts. This is not randomized
assignment or proof against endpoint batch effects. The frozen initial payload
must match the actual first call. Stop on source/context/oracle drift, exhausted
budget or two consecutive transport failures. Context/reference checks repeat
at the end, but there is no shared cross-query DB snapshot.

Only the POS test DB is read, with `grepbit_ro` and sampling limit zero.
The public store-name index has five existing names. Exact/exclusion questions
have one verbatim hint; the partial, unique-fragment, tied and missing questions
have none. Resolver preflight shows two unique fragments, one ambiguous
five-name prefix, and one absent name. Both grounding arms receive the same
overlay; loading unrelated aliases/metrics/segments is deliberately excluded.
This isolates index availability, not full-overlay-versus-no-overlay behavior.

Payroll metadata treatment adds only factual paid-date/attribution-date roles,
including that no fixed one-month lag is guaranteed. No live DB `COMMENT` is
changed. The metric arm retains the existing definition (base salary excluding
bonuses, attributed to period start), not a new definition tailored to a failure.
Its effect includes offering the metric and the existing overlay instructions;
it is not a pure wording-only comparison with the comments arm.

## Oracles and interpretation

Before live requests, 47 fixed plan/arm combinations agreed with independent
PostgreSQL SELECTs. Setup caught two research-oracle issues: explicit ascending
period order duplicates the compiler's default recipe; transaction timestamp
buckets return a timestamp, while payroll DATE buckets return DATE. Duplicate
oracles were removed and the control query's return type corrected before
freezing. Runtime/comparator semantics and legacy answers were unchanged.
The local driver has 17 passing checks (schedule, allowed plan constraints,
transport stops and exclusion of raw error/provider/row text from reports).

The new `disclosed-answer-v1` grader is opt-in and separate from historical
correctness. It checks predeclared complete recipes, independent values and
faithful disclosure. Unknown recipes remain **unassessed**: a representational
miss is not automatically a wrong answer. A known wrong time basis is also
recorded separately from recipe matching, and value coincidence never overrides
the required time role. Appropriate refusal is separated from answered cases.
This study's unspecified payroll baseline permits either payment or attribution
time for base salary with disclosure; salary-component alternatives not
predeclared here remain unassessed rather than retroactively accepted.

Initial versus final plans, offered hints, post-plan resolutions, missing
literals, selected raw column/metric, effective time role, value agreement,
disclosure, model retries/repairs and latency are recorded separately. This
prevents a compiler override from being credited as correct planner selection.

## Results

Completed **60/60 jobs in 60 transport attempts**, zero transport failures,
model retries or repair turns. End-of-run source/schema/context/reference
identities matched the frozen identities. Both repeats had the same status and
acceptance outcome for every case/arm; 29/30 final-plan hashes matched. The
remaining exact-name/no-index pair differed only in the retained plan hash,
not its retained semantic facts or refusal; raw output was not retained, so
its precise cosmetic/ordering difference is not claimed.

| Arm | Jobs | Accepted answers | Appropriate refusals | Unassessed | p50 ask seconds |
|---|---:|---:|---:|---:|---:|
| Grounding, no index | 12 | 2 | 4 | 6 (answerable-name refusals) | 4.65 |
| Grounding, index | 12 | 8 | 4 | 0 | 3.96 |
| Payroll, original metadata | 12 | 10 | 0 | 2 (same English case) | 3.76 |
| Payroll, expanded comments | 12 | 12 | 0 | 0 | 3.35 |
| Payroll, minimal metric | 12 | 12 | 0 | 0 | 3.75 |

These are six unique questions per study, each repeated twice, **not** 12
independent questions per arm. Latency excludes index/schema load and is not
a production speed claim; payload sizes and endpoint timing differ. No
historical panel was relabeled or rerun.

### Grounding: a localized, repeatable mechanism

- The complete Chinese name was shortened by the planner without an index and
  failed literal existence. With a verbatim hint, the model used its candidate
  reference and answered correctly. This is pre-plan availability/binding.
- For the partial Chinese name and the unique fragment in an English request,
  **both arms had zero hints and the same initial plan hash** in each repeat.
  Only the index arm performed post-miss unique resolution and returned the
  independently correct value with the substitution disclosed. This directly
  isolates the post-plan resolver, not improved language understanding.
- The tied prefix remained a refusal; index-on improved its reason from
  missing literal to ambiguous value. The nonexistent name remained a refusal.
  Explicit exclusion remained `ne`, with correct values in both arms; merely
  finding a positive name mention did not turn it into an inclusion.

There were four unique answerable cases. No-index answered one correctly;
index answered all four, while both retained the two required refusals. No
observed false substitution in this small set. This supports further use of
the existing public-column opt-in index, not a new alias rule, relaxed tie
threshold, personal-column index or a claim that A5 is generally accepted.
Only two unique-reference and two post-miss-resolution case executions per
repeat are exercised here; broader A5 evidence remains separate.

### Payroll: choice of meaning versus a newly isolated scope error

For the original unspecified quarterly-salary question, original metadata
selected `paid_at`; expanded comments and the minimal metric selected
`period_start`. **All are accepted under the owner's disclosed-reading policy.**
Moving this case to attribution time is a changed default, not a newly correct
answer. Every explicit time-role question used its requested role in all arms;
no time-role conflict was observed in these 36 jobs.

The metric arm used `base_salary_total` for the unspecified and explicit
attribution questions. For explicit payment, delayed payment and separate
base/bonus outputs, it selected raw `paid_at` measures instead of the
attribution metric. The non-payroll control used transaction time. These are
observed choices, not a guarantee that a loaded overlay prevents wrong choice.
No compiler time override was needed to fix a planner time choice in this set.

The English request "sum base salary by actual payment date, excluding bonuses"
exposed a different error: original metadata added `hr_payroll.bonus = 0` in
both repeats. This excludes payroll **rows** with bonuses instead of excluding
the bonus **component** from the sum. The automatic grader kept both results
`unassessed / unlisted_interpretation`; it did not certify them or rewrite the
frozen alternatives. Post-hoc root-cause adjudication identifies them as wrong:

- The recorded literal hash matches `[0]`, and both original-metadata runs
  carry that extra row filter and fail every predeclared value oracle.
- An independent read-only PostgreSQL witness with authored
  `(base_salary, bonus) = (100,10), (200,0)` gives **300** for base salary and
  **200** with `bonus = 0`.
- The same two aggregations over the POS test fixture differ in **3 of 4
  quarters**, with rows removed in those same three periods. Actual salary
  totals are not persisted. Evidence: `bonus-witness.json` and
  `bonus_witness.py` in the artifact folder, zero extra model calls.

Both treatment arms avoid that filter in both repeats and match the independent
oracle. However, date-only comment expansion does not directly define how to
exclude a salary component. Its incidental removal of this filter could be a
broader prompt-context shift; this small study does **not** establish a robust
repair for component-versus-population confusion.

## Decision and next order

1. **Grounding is the strongest actionable result.** The old name failure has
   an existing mechanism that works repeatedly with a public-name opt-in;
   no lexical exception or runtime change is needed. Before durable overlay
   promotion, broaden name/exclusion/tie checks beyond these authored fragments
   and rerun affected POS sets. Do not expand indexing to personal fields.
2. **Document time roles factually, not as a universal payroll default.**
   Keep both permissible unspecified readings with faithful disclosure. The
   live treatments are research-only; no production overlay or DB comment was
   changed. This study supports their usefulness, not universal robustness.
3. **Carry the new root cause into the next contrast corpus.** Excluding a
   numeric component versus excluding rows with that component is a general
   ambiguity axis (salary/bonus, amount/tax, goods/shipping). Test balanced
   include/exclude minimal pairs with independently different values; do not
   add a `bonus` keyword exception or reuse the same-model verifier as a gate.
4. **Then continue the already planned offline lexical-gate comparison.**
   Keep deterministic structural/literal/authorization checks unchanged and
   report both false refusals avoided and true omissions newly exposed. A
   shadow gate-off control is not a promotable production replacement.

The repository change for this slice is documentation and a compact evidence
manifest only. The one-off driver/tests remain under `.artifacts/`; no new
production framework, interpretation policy, prompt revision, served card or
scoring relaxation was added. Gate/meaning changes still require their own
approved ruler; this evidence does not grant such authority.
