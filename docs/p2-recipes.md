# P2 recipes v0.1: design and admission checkpoint

Status: design accepted in #14 / PR #15 on `dev` at
`ea1c62c6ceecd5c12e4a359d8532d04f80b59850`, under roadmap #1.
P2.1 (#16 / PR #17) accepted the offline scalar Compare slice below. P2.2
(#18 / PR #19) accepted the [observed grouped-amount primitive](grouped-amount.md).
P2.3 (#20 / PR #21) accepted the private required/optional witness below.
P2.4 (#22 / PR #23) accepted public deterministic Overview using that composition.
P2.5 (#24 / PR #25) accepted deterministic Breakdown with an independent
whole-scope denominator and two exact derivations. P2.6 (#26) adds the bounded
[one-shot model route](recipe-model-integration.md), pending owner acceptance.
It introduces a separate shared recipe prompt/contract, not a change to P1's
prompt. Dependencies, deterministic APIs, fixtures, gold and live-run
authorizations remain unchanged; recipe live evidence remains future work.

**Question:** is composition useful without expanding a language?

The three stable recipe IDs are `overview`, `compare` and `breakdown`, each
version `0.1`. A recipe is an application-owned, reviewed **structured slot
template + ID/version + human explanation**. Tables below define those
templates; they are not executable YAML, a user-editable formula system or
question-specific routing. Case IDs below are evaluator witnesses only. They
must not appear in runtime dispatch or evaluated-model context.

## P2.1 offline scalar Compare

The typed Python API is `grepbit.execute_compare(database, request, *, limits)`.
It accepts only `CompareRequest(current, baseline)`, containing two explicit
FactRequests. Both must use only `confirmed_booked_amount`, all centers and
`Asia/Taipei`. Their absolute instants must describe distinct full calendar
months in that timezone. Equivalent offset representations are allowed;
explicit cross-year comparisons are allowed. No baseline, year or metric is
inferred. Same-month, partial-month and multi-month comparisons are rejected.

```python
from pathlib import Path
from grepbit import CompareRequest, execute_compare

request = CompareRequest.from_mapping({
    "current": {
        "metrics": ["confirmed_booked_amount"],
        "start": "2026-03-01T00:00:00+08:00",
        "end": "2026-04-01T00:00:00+08:00",
        "timezone": "Asia/Taipei",
    },
    "baseline": {
        "metrics": ["confirmed_booked_amount"],
        "start": "2026-02-01T00:00:00+08:00",
        "end": "2026-03-01T00:00:00+08:00",
        "timezone": "Asia/Taipei",
    },
})
pack = execute_compare(Path("learningops.sqlite"), request)
document = pack.to_dict()
```

`from_mapping` admits exactly `current` and `baseline`, each with the strict P1
FactRequest fields; unknown recipe/formula/filter/third-scope fields are errors.
The recipe ID/version are fixed output metadata, not configurable parameters.
There is no new CLI or model route, no custom catalog parameter, and no public
API for supplying facts, SQL, connections or execution callbacks.

The public output types are `CompareAnalysisPack`, `CompareDerivedFact` and
`CompareSlotResult`: their fixed shapes describe only Compare, not reusable
P2-wide contracts. The broader AnalysisPack/DerivedFact concepts below remain
design vocabulary, not generic exported Python types. The former unaccepted
generic type names have no compatibility aliases; callers must update imports
and type annotations. Serialized JSON field names and values are unchanged,
and `Fact.fact_id` remains generic.

| Output | P2.1 shape / behavior |
| --- | --- |
| `recipe_id`, `recipe_version`, `request` | `compare`, `0.1`, both preserved explicit scopes |
| `facts` | Checked current/baseline Facts, including SQL/parameters, scalar checks, source population/empty evidence and opaque `fact_id` |
| `derived_facts` | Difference and relative-change records: own ID, ordered input IDs, unit, common snapshot ID, value, state and reason |
| `slots` | Exactly current/baseline/delta/growth; all required; each has state and fact reference, with reason where needed |
| `snapshot`, `runtime`, `execution`, `limitations` | Common read-transaction/source identity, dependency versions, aggregate budget/counters and bounded claims |
| `status` | `complete` if all required slots are checked/contract-defined undefined; `failed` if a required derivation is unavailable; no partial state |

Difference uses signed-64-bit integer arithmetic with explicit overflow rejection.
Growth is a reduced stdlib `Fraction`, serialized as
`{"numerator": 54, "denominator": 25}` for E02, not binary float or percentage
text. Delta references current/baseline fact IDs; growth references delta and the
same baseline. Fact IDs are server-assigned opaque UUIDs without cross-run
persistence. Adding `Fact.fact_id` also adds that field to existing P1 JSON;
no existing field is removed or reinterpreted.

A nonempty baseline amount of zero yields checked delta and
`growth: undefined, reason: zero_baseline`, including zero versus zero.
An empty baseline stays a checked null Fact with empty-population evidence;
delta is unavailable (`empty_input`), growth is unavailable
(`unavailable_difference`) and status is failed. Source, budget, compatibility
and overflow errors raise `KernelError`, never a partial or success-shaped pack.
Checked facts with null values are not converted into zero.

The scalar and Compare execution entries use the same private compilation, source
admission, read-only transaction, authorizer and scalar-result checks. Compare
opens one connection/transaction, validates the source once, and runs both
scopes under one `_Budget`: timeout, VM callbacks and source-validation rows
are not reset. The existing defaults/hard maxima remain unchanged.
Compatibility checks cover catalog/digest, metric/unit, population/grain,
filters, time basis/timezone, complete checked coverage, bound role ranges and
the common snapshot. No user-editable compatibility rules are introduced.

Compare implements only `difference` and `relative_change`. P2.2 separately adds
grouped facts and P2.3 adds private required/optional execution. P2.4 adds public
Overview, and P2.5 adds Breakdown's selected subtotal/share below. Rendering,
model instantiation and live recipe evidence remain future work. P2.1 does not
complete the P2 exit or establish model quality, backend parity or generalization.

## P2.3 private required/optional composition

`grepbit.composition._execute_required_optional` is an internal fixed witness,
not a public recipe API. It accepts a local database Path and an already-bound
FactRequest with exactly `confirmed_booked_amount`, `confirmed_booking_count`,
`booked_seats` in that order, a canonical non-null center ID, and one explicit
full month in the reviewed fixed UTC+08:00 Asia/Taipei profile. There is no center
code/name resolution or caller-selected slot list in this private entry.
P2.4's separate public request/binding boundary is described below.

| Fixed slot | Role | Computation |
| --- | --- | --- |
| amount | Required | Scalar confirmed_booked_amount |
| bookings | Required | Scalar confirmed_booking_count |
| seats | Required | Scalar booked_seats |
| daily_amount | Optional, first | Full observed booking_day amount |
| category_amounts | Optional, second | Full observed category amount |

The roles are fixed before execution. One existing multi-metric scalar helper
executes the required core; P2.2's admitted grouped query helper executes each
optional view. All use one read-only connection, one actual transaction/snapshot,
one base admission and one `_Budget`. Public scalar/grouped wrappers are not
chained, and no transaction is reopened to fill a gap.

The small private `_CompositionSlot` references a checked fact ID, or carries an
unavailable reason with no fact reference. `_CompositionResult` retains the
three scalar facts, only checked grouped facts, all five named slots, shared
snapshot and final execution evidence. It returns `complete` only when all five
slots are checked, or `partial` when required coverage is checked and at least
one optional has a reviewed local failure. P2.3 exported no new type/function
from `grepbit`; its private types are not the public P2.4 contract.

Recoverability is stage-specific, not inferred from an error string:

| Failure | Disposition |
| --- | --- |
| `unsupported_source` during optional category dimension admission | Category unavailable; retain checked core/daily |
| `output_limit_exceeded` during an optional grouped query | That optional unavailable; no truncated fact |
| Trusted private `_ComponentTimeout` injection at an optional query boundary | That optional unavailable: `component_timeout` |
| Otherwise-compatible optional amount/absence does not reconcile | That optional unavailable: `reconciliation_failed`; no row repair |
| Invalid base, required failure, incompatible semantic/coverage/snapshot evidence, global budget exhaustion, transaction/connection loss, SQLite error, interruption or unknown KernelError | Abort; no composition result |

Even an `unsupported_source` from grouped query execution, rather than category
admission, remains fatal. An arbitrary KernelError with code `component_timeout`
is not the trusted injected control. No exception message/source text is copied
into an unavailable reason. The same global budget is checked after recoverable
failures, and the existing transaction must still be active and readable.
Its original batch ID is retained separately and checked through recovery and
finalization; comparing two references to the same mutable snapshot dictionary
is not sufficient evidence of identity consistency.

E10 timeout semantics are **injected in P2.3; general component timer mechanics
are not implemented**. Tests inject the private timeout at the category query
boundary, after required facts and the independent daily view. Production has no
case-ID route, timer knob, per-node budget, scheduler, retry or fallback. A
global deadline/VM/source-row failure always wins over a local injection.

Before accepting an optional fact, its amount semantics, scope, full observed
coverage, named checks and snapshot must match the checked required amount.
Compatible nonempty rows must sum exactly to that amount; an empty required
amount requires an empty grouped result, never `sum([]) == 0`. A checked-empty
view remains checked. In a no-data scope, core values remain NULL amount,
zero bookings and NULL seats. Measured zero on a real population remains zero.

A recoverable daily failure does not suppress category; a recoverable category
failure preserves daily. Both may be unavailable, with both slots retained.
If a global/snapshot failure follows a successful view, the entire analysis
still aborts. The result is materialized only after successful transaction exit.
Grouped execution counters are cumulative checkpoints; composition execution
contains final cumulative counters. Source-validation row counts do not measure
all FK/query/sort work, and cooperative budgets are not OS resource isolation.

Focused regressions cover failed-admission permission restoration within an
existing transaction, finite recoverable/fatal classifications, empty/zero and
reconciliation, and a real WAL writer changing both amount and category between
required and optional reads. These are deterministic synthetic regression
controls, not model evaluations or proof of a public Overview recipe.

## P2.4 public deterministic Overview

`grepbit.execute_overview(database, request, *, limits)` exposes `overview@0.1`
with `OverviewRequest(center_code, start, end, timezone)`. The typed constructor
requires aware datetimes; `from_mapping` uses the existing strict offset-aware
ISO parsing. Both bounds must be explicit and describe exactly one full month
in the reviewed **fixed UTC+08:00** profile labeled `Asia/Taipei`. Equivalent
absolute instants with other explicit offsets are allowed, not alternate
business timezones or historical IANA/DST calendar behavior.

```python
from pathlib import Path
from grepbit import OverviewRequest, execute_overview

request = OverviewRequest.from_mapping({
    "center_code": "CTR-A01",
    "start": "2026-03-01T00:00:00+08:00",
    "end": "2026-04-01T00:00:00+08:00",
    "timezone": "Asia/Taipei",
})
pack = execute_overview(Path("learningops.sqlite"), request)
document = pack.to_dict()
```

Only those four request fields are accepted. There is no missing-year/month
default, partial/multi-month period, canonical-ID override, metric/role/optional
selection, formula, SQL, callback or recipe-version override. Trusted callers
may supply the existing global `ExecutionLimits`; there is no component budget
or injection parameter.

The code is preserved exactly and bounded to **1-64 UTF-8 bytes**. A parameterized
`centers.code = ?` lookup returns at most two matches under the existing read-only
policy. Zero matches raises `unknown_entity`; more than one raises
`ambiguous_entity`, before fact execution. The inherited base validator does
not establish code uniqueness, even though the fixture declares it. Overview
therefore checks this lookup's cardinality without tightening scalar/Compare
admission. There is no trimming, case-folding, LIKE, name/ID fallback, default
center or hard-coded code-to-ID mapping. A name/ID-shaped or punctuation-bearing
string works only if it is an actual exact stored code.

Binding happens **inside the same transaction, snapshot and global budget**
as all five fixed slots from P2.3. The original snapshot ID is captured before
binding. A narrow private extraction lets the retained P2.3 entry and Overview
call the same inner composition, stage-specific recovery, reconciliation and
post-transaction finalizer. Neither calls a second public executor or starts
another transaction. The public pack is constructed only after successful exit
and final budget/original-ID checks.

The public types are Overview-specific: `OverviewAnalysisPack`,
`OverviewCenterBinding` and `OverviewSlotResult`, not exports/aliases of private
`_Composition*` types or a common superclass with Compare.

| Output | P2.4 shape / behavior |
| --- | --- |
| `recipe_id`, `recipe_version`, `request` | Fixed `overview`, `0.1`, validated original request; dates serialize as ISO instants |
| `binding` | Exact supplied code, canonical center ID, common snapshot ID and `method: exact_unique_code` |
| `scope` | Resolved three-metric FactRequest with the original period/timezone and bound canonical center |
| `facts`, `grouped_facts` | Original checked scalar/grouped objects and fact IDs, not reconstructed computations |
| `slots` | All five fixed slots, required/optional role, checked/unavailable state, fact reference or bounded gap reason; no copied metric definitions |
| `status` | `complete` when all five are checked; `partial` only for P2.3's admitted optional gaps |
| `snapshot`, `runtime`, `execution`, `checks`, `limitations` | Shared source/snapshot identity, final cumulative execution evidence, binding/composition checks and bounded claims |

Binding, base, required, incompatible-evidence, global-budget and
transaction/snapshot failures abort with **no Overview pack**. The public wrapper
does not add recovery rules. A known center without activity is checked-empty:
amount NULL, bookings 0, seats NULL, and both optional rowsets empty/checked.
Measured zero remains distinct. E10 is still private fault injection, **not**
real component timeout/cancellation mechanics or a runtime option.

Binding adds one explicit validation-loop visit per returned match. On the
unmodified fixture a successful Overview visits 49 rows: 31 base, 1 binding and
17 category-extension visits; grouped checkpoints are 32 and 49. The retained
private P2.3 entry still visits 48. `source_rows_validated` is not total database
work; query/FK/join/sort work remains subject to the same cooperative VM/time
budget. No counter resets, raised limits or new progress handler are introduced.

Public regressions cover exact/duplicate/literal binding, request rejection,
five-slot evidence/JSON, real missing-category partial output, injected E10,
empty/zero, binding/global budgets and post-exit construction. A real WAL writer
changes both code mapping and amounts after binding: the in-flight result
retains the original binding/data, while a fresh run observes the changes.
Separate metadata-corruption/exit-failure controls do not stand in for WAL
isolation. Existing P2.3 regressions protect the full recovery/precedence matrix.

This is a deterministic Python API, not natural-language recipe selection,
rendering, an API/CLI framework or live recipe validation. No analytical
primitive, derived operation, dependency, configuration, model path or evaluator
asset changes in P2.4. Breakdown is the separate P2.5 slice below; the remaining
P2 exit stays open.

## P2.5 public deterministic Breakdown

`grepbit.execute_breakdown(database, request, *, limits)` accepts
`BreakdownRequest(start, end, timezone, top_k)`. All four fields are required.
The typed constructor and strict `from_mapping` path reuse existing aware
instant parsing and grouped full-month validation: exactly one explicit month
in the fixed UTC+08:00 profile labeled `Asia/Taipei`, with equivalent absolute
offset representations allowed. `top_k` must be an actual integer from 1 to 3,
not bool/float/string, an inferred default or a clamped value.

```python
from pathlib import Path
from grepbit import BreakdownRequest, execute_breakdown

request = BreakdownRequest.from_mapping({
    "start": "2026-03-01T00:00:00+08:00",
    "end": "2026-04-01T00:00:00+08:00",
    "timezone": "Asia/Taipei",
    "top_k": 2,
})
pack = execute_breakdown(Path("learningops.sqlite"), request)
document = pack.to_dict()
```

Only those request fields are admitted. Metric, dimension, all-center scope,
population/time basis and ranking are recipe-owned. Center filters/codes,
selected-course predicates, denominator overrides, formulas, SQL, ordering,
callbacks, role changes and recipe-version overrides are rejected. There is no
new CLI/model route or public supplied-fact API.

| Fixed required slot | Evidence |
| --- | --- |
| `top_courses` | Existing checked course top-k GroupedAmountFact, amount descending / course ID ascending |
| `all_amount` | Independently executed scalar amount over the original unranked all-center period |
| `top_subtotal` | `selected_subtotal`, with exactly one logical input: the grouped fact ID |
| `share` | `share_of_scope`, with ordered inputs: subtotal ID, independent whole-amount ID |

Execution opens one existing admitted read transaction and cumulative `_Budget`,
reads the whole scalar first, then runs the existing course admission/query
helper on the same scope. It does not chain public wrappers, invoke Overview's
five-slot composer or copy optional recovery. Only neutral transaction-boundary
and finalization checks are shared with that module. The original snapshot ID
and independently read denominator identity are captured separately. Public
construction follows successful transaction exit and final budget/ID checks.

Both sources must match the bound recipe, not merely one another: approved
catalog/digest/amount, unit, booking-line grain, current-confirmed population,
creation-time range, timezone, all-center filters, original snapshot and required
checks. Scalar whole-scope completeness/empty evidence and grouped course
profile/admission, requested k, complete declared top-k coverage, bounded integer
rows, valid distinct keys and exact ordering are checked. Returned SQL/parameters
must match the independently compiled needs; expected parameter dictionaries
are copied before execution rather than compared through shared aliases.

The denominator has no rank, limit or selected-course predicate. Membership
rests on trusted independent scalar execution and the reviewed grouped partition,
not merely `subtotal <= total`. No second verifier query is added. A selection
may contain fewer than k observed courses; it is never padded. Coverage stays
`top_k` even when subtotal equals total or share is 1; equality does not establish
whole-universe coverage.

Exactly two fixed derivations are added, not a formula registry. Subtotal sums
only returned integer amounts, with signed-64-bit overflow rejection. Share
validates the subtotal's actual selection reference, value/state and unit/snapshot
plus the captured denominator role before dividing. Each derived fact has its
own opaque ID; source IDs are unchanged. Share uses stdlib Fraction and serializes
as integer `numerator` / positive `denominator`, with no float truth or renderer.
The source population label is now a shared private constant; its existing
scalar/grouped output text is unchanged.

| Data or failure condition | Result |
| --- | --- |
| Compatible nonempty inputs, positive total | Checked subtotal/share; `complete` |
| Nonempty zero total and zero subtotal | Checked zero subtotal; share `undefined`, `zero_total`, no numeric value; `complete` |
| Valid empty scope | Checked NULL scalar and empty grouped source; subtotal `unavailable: empty_input`, share `unavailable: unavailable_subtotal`; `failed` |
| Subtotal above total, positive subtotal over zero, contradictory or incompatible evidence | Error; no pack, repair or clamping |
| Required admission/query, overflow, budget, interruption, SQLite/connection/transaction/snapshot or finalization failure | Abort; no pack, retry or reopened transaction |

Public output types are `BreakdownAnalysisPack`, `BreakdownDerivedFact` and
`BreakdownSlotResult`, not Compare aliases or a generic superclass. The pack
contains the original request, resolved all-center FactRequest scope, original
scalar/grouped facts, two derived facts, all four explicitly required slots,
common snapshot and final runtime/execution/check/limitation evidence. Status is
derived from required slot states and is only `complete` or `failed`, never
`partial`. Output DTOs cannot be used as trusted execution requests.

On the unchanged fixture, base admission visits 31 rows and required course
admission adds 17, for 48 validation-loop visits. No limits/counters/progress
handler are reset or raised. Course grouping does not require category columns;
the inherited session parent/FK prerequisites and permission restoration remain.
These counters do not measure all query/FK/join/sort work.

Focused controls cover E03 and k=1/2/3, an unselected-course mutation that changes
only the denominator/share, ranking/ties, role/metadata incompatibility, zero/
empty distinctions, pure arithmetic overflow, and an actual WAL writer between
the scalar and grouped reads. Scalar SUM may legitimately overflow before the
derived subtotal stage; the pure overflow control does not claim otherwise.
E10 remains private optional fault injection for Overview, not an optional
policy or component timer for Breakdown.

This slice does not change dependencies, configuration, evaluator/gold/translation
assets or model paths. It adds no metric, dimension or SQL/grouping primitive.
Model recipe selection, authorized live paths and the remaining P2 exit stay open.

## 1. Admission and evidence

P1 remains the common trusted calculation path. P2 does not introduce another
SQL executor, model-authored code, a serialized execution DAG or a QueryPlan
language. Synthesis and resumable clarification belong to P3; drill-down and
PostgreSQL belong to P4.

| Existing case | Decision for P2 v0.1 | Reason / boundary |
| --- | --- | --- |
| `E01_overview` | Admit Overview | Three required scalar facts, two fixed optional amount views |
| `E02_compare` | Admit Compare | Same amount definition, two bound months, deterministic change |
| `E03_share_denominator` | Admit Breakdown | Ranked course amounts with an independent all-scope denominator |
| `E10_budget_partial` | Admit operational control | Inject failure of Overview's optional category fact; never send this scenario as a model question |
| `E04_ambiguous_entity` | Defer to P3 | Duplicate center names need typed clarification; no silent CA/CB choice |
| `E05_ambiguous_count` | Defer to P3 | Accounts, seats and visits are not interchangeable people counts |
| `E06_ambiguous_year` | Defer to P3 | No missing-year default, including from `as_of` |
| `E07_missing_profit` | Defer | No reviewed profit/cost definition; do not substitute booked amount |
| `E08_visibility` | Defer | No learner-email product or authorization subsystem admitted |
| `E09_unit_conversion` | Defer | Duration conversion is unnecessary for these recipes |
| `E11_zero_missing` | Defer | Targets have their own binding/absence semantics; not a generic-ratio justification |
| `E12_absence_extension` | Defer | No anti-join or general absence analysis |

Classify each supporting reference **exactly once**:

| Reference | Classification | What it establishes, not an extra recipe promise |
| --- | --- | --- |
| `Q01_booked_amount` | Direct P2 v0.1 capability | Inherited all-scope scalar amount for Compare/Breakdown |
| `Q05_center_amount` | Direct P2 v0.1 capability | Inherited bound-center scalar amount for Overview |
| `Q09_previous_amount` | Direct P2 v0.1 capability | Inherited previous-month scalar for Compare |
| `Q10_center_breakdown` | Evaluator-only reference | All catalog centers, including zero-activity CZ; member completion is deferred |
| `Q11_category_breakdown` | Primitive witness | Observed category grouping, including a NULL category when present |
| `Q12_daily_trend` | Primitive witness | Observed booking days in Asia/Taipei, not a filled calendar |
| `Q13_top_courses` | Primitive witness | Amount descending, course ID ascending for ties, top three |

The direct classifications describe fact capabilities within the recipes, not
three new natural-language routes. Primitive witnesses justify common machinery,
not automatic support for every standalone authored question. Existing case
wording, authored statuses, language review labels and oracles stay unchanged.

### Can Q10-Q13 use one grouped abstraction?

**They share aggregation, but not the same membership contract.** One bounded
observed-group fact explains Q11, Q12 and Q13: reviewed amount + scope +
dimension + reviewed ordering + optional top-k. It also serves Overview's
optional views and Breakdown's ranked input.

Q10 additionally enumerates the complete `centers` catalog, left-completes absent
members and deliberately reports zero for CZ. Dimension/order/limit alone
cannot express that difference from observed groups. Do not silently omit CZ,
claim Q10 passed, or turn an empty scalar SUM into zero. Catalog-member
completion is deferred; no `include_empty`, join language, domain-filling or
anti-join operator is added just for Q10. A later reviewed catalog policy could
share the aggregation core without creating a separate Breakdown/Trend/TopK AST.

## 2. Recipe capability matrix

All v0.1 periods are explicit calendar months in **Asia/Taipei**. The model may
select a supported recipe and bind stated parameters; the server validates them
against this matrix. It must reject an incompatible metric rather than replace
it with the recipe's metric. Scalar-only P1 requests remain available separately.

| Contract | `overview@0.1` | `compare@0.1` | `breakdown@0.1` |
| --- | --- | --- | --- |
| Human purpose | Summarize confirmed booking activity | Compare the same booked amount over two months | Show top courses' amount and share of the whole scope |
| Supported question shape | Registration overview for one explicit center code and month | All-center current month vs explicitly identified baseline month | Top-k courses' share of all booked amount in an explicit month |
| Required parameters | Bound center, year/month, timezone | Current and baseline year/month, timezone; all centers | Year/month, timezone; course dimension; requested k |
| Metric binding | Fixed amount/count/seats core; amount-only optional views | `confirmed_booked_amount` only | `confirmed_booked_amount` only |
| Required slots | `amount`, `bookings`, `seats` | `current`, `baseline`, `delta`, `growth` | `top_courses`, `all_amount`, `top_subtotal`, `share` |
| Optional slots | `daily_amount`, `category_amounts`, both declared by the template | None | None |
| Reviewed grouped dimensions | `booking_day`, `category` | None | `course` |
| Ranking / limit | All observed groups, dimension ascending; no top-k | None | Integer k from 1 through 3; amount descending, course ID ascending; exactly up to k groups, not all tied groups |
| Denominator | None | Growth uses the named baseline, never current or absolute baseline | `all_amount` uses the identical source scope without ranking, limit or selected-course filtering |
| Server derivations | None required; compatible amount reconciliation is a check | Difference and relative change; percentage is a rendering | Subtotal of returned top groups and share of all-scope amount |
| Coverage | Three required slots; either optional unavailable makes result partial | All four required slots must resolve | All four required slots must resolve; top-k is intentional coverage, not the whole population |
| Compatibility | Same center/month/snapshot; metric-specific units; optional amount views reconcile only with amount | Same definition/unit/population/center/time basis/snapshot; two deliberately different months | Same amount definition, scope/unit/snapshot; disjoint course groups; explicit subset/whole relationship |
| Result shape | Three scoped scalars, ordered optional rowsets or named gaps | Two scoped scalars plus input-linked delta/growth | Ordered course/value rows, subtotal, separate total, input-linked share |
| Follow-up / drill-down | None | None | None |
| Unsupported | Targets, causes, forecasts, custom core/optional slots, arbitrary details | Grouped comparisons, other metrics, implicit periods, per-day normalization | Other ranked dimensions, k outside 1-3, arbitrary filters, zero-filled/absent courses |
| Witnesses | E01, E10; Q05, Q11, Q12 | E02; Q01, Q09 | E03; Q01, Q13 |

Two optional Overview slots are fixed in this version, not an open selection
language. They may be unavailable under execution limits; they may not disappear
from the result. Adding optional slots or broadening k/metrics/dimensions needs
a reviewed recipe revision, not a branch for a particular question.
The top-k cap of 3 covers the largest reused witness, Q13; every positive k
through that bound uses the same operation. Reject out-of-range requests
explicitly rather than silently clamp them.

### Tiny binding prerequisite, not general clarification

An exact unique center **code** such as `CTR-A01` may be bound by the server to
canonical ID `CA` using `centers.code`. This is needed by E01 and Q05. It is not
fuzzy name matching or an alias guess: `centers.name` is not unique. A missing or
non-unique binding, ambiguous count or absent year stops admission without
executing facts. The explanatory refusal is not a P3 clarification/resume engine.
The year explicitly stated for E02's comparison applies to its two named months;
the fixed `as_of` supplies no missing year.

## 3. Minimum contracts, not a serialized plan

These are the broader accepted **sketch**, not a generic runtime API.
The narrow public types above describe Compare, Overview and Breakdown separately.
Parameters express WHAT; a reviewed server template supplies HOW. No caller
provides tasks, dependency graphs, operators, SQL, arbitrary filters or expressions.

| Concept / fields | Meaning | Reuse or semantic necessity |
| --- | --- | --- |
| Recipe: `recipe_id`, `recipe_version`, explanation, ordered slot definitions | Stable reviewed template, not case ID dispatch | All three recipes; E01 and E10 instantiate the same Overview |
| Bound parameters: one `scope` or named `current_scope` / `baseline_scope`; Overview's exact `center_code` binding input; `dimension_id`, `top_k` only where admitted | Values validated against the recipe matrix; metric/slot defaults come from its version; HOW resolves the code before constructing a canonical FactRequest scope | Scope reused everywhere; code binding E01/Q05; comparison roles unavoidable for E02; top-k E03/Q13 |
| Scope: existing `start`, `end`, `timezone`, bound `center_id` | Half-open absolute instants, explicit month/year and canonical center; `None` means all centers | E01/E02/E03; no new filter-tree concept |
| FactNeed: `metric_id`, `scope`; optional reviewed `dimension_id`, `order`, `limit` | Scalar when ungrouped; otherwise one dimension and one amount metric | All recipes reuse scalars; E01/E03 and Q11-Q13 reuse grouped needs |
| Dimension registry: ID, key type/null policy, reviewed source binding, time rule, additive partition guarantee | Trusted catalog knowledge; no client-written group expression or join path | Category/day/course share the abstraction; preserves Q11 NULLs, Q12 dates, Q13 IDs |
| Group ordering / limit | Server-bound finite order: `dimension_asc` or `amount_desc_key_asc`; limit absent or admitted k | Q11/Q12 ordering and Q13/E03 ranking; model cannot supply sort expressions |
| Slot: `slot_id`, required/optional role, bound need or fixed derivation | Obligation known before execution, not selected by success | E01/E10 and required derived slots in E02/E03 |
| Fact identity: `fact_id` plus existing fact evidence | Server-assigned opaque identity for a checked scalar or grouped rowset | E02/E03 need input references; E01/E10 need coverage/provenance linkage |
| Grouped value: ordered `(dimension_key, amount)` rows | Stable keys, integer minor units; nullable category stays NULL | Q11-Q13, E01/E03; no arbitrary result-column projection |
| Coverage: full scalar scope, all observed groups, or ordered top-k (with k/order) | Intentional subset is distinct from lost rows or exhausted budget | E01 optional views and E03 denominator/subtotal; Q10 is the counterexample |
| DerivedFact: `fact_id`, fixed `derivation`, ordered `input_fact_ids`, typed value/unit, state/reason | Server calculation with direct and transitive provenance | E02/E03; links are output evidence, not an executable user DAG |
| Exact dimensionless value: integer numerator/positive denominator | Preserve exact arithmetic; percentage rendering does not replace it | E02 growth and E03 non-terminating share; not nested expressions |
| Slot result: slot ID/role, state, fact reference or named reason | `checked`, `undefined` or `unavailable`; see rules below | E10 optional gap; E02/E03 zero/missing inputs |
| AnalysisPack: recipe identity, bound parameters, common snapshot reference, ordered slot results and their facts, derived overall status | Checked analysis, not a free-form narrative or an execution plan | All four admitted E anchors |

Reuse the existing facts' catalog ID/digest, metric ID, grain/population,
time basis/range/timezone, filters, unit, population/empty disclosures, checks,
SQL/parameters and snapshot provenance. Do not duplicate them as editable
recipe parameters. A checked fact with `value=null` and `empty_population=true`
is not a measured zero.

P2.1 adds individual `fact_id` values to the existing `Fact` rather than
duplicating all of its evidence fields. P2.2's `GroupedAmountFact` has its own
identified rowset and observed/top-k coverage; it is not a generic recipe pack.
The snapshot UUID is an ephemeral read-transaction identity. A schema hash or
source filename is **not** a database-data version.

## 4. One bounded grouped-fact primitive

Admit observed grouping of **confirmed booked amount only**, using the same
confirmed-booking population and booking-creation time as the scalar metric:

| Dimension | Reviewed meaning and source relation | Membership / order | Reuse |
| --- | --- | --- | --- |
| `category` | Booking line -> session -> course category, reviewed many-to-one relations | Observed groups only; retain NULL as its own key, sorted before text; no relabel/merge of NULL with a real category | Overview mix, Q11 |
| `booking_day` | Booking creation instant assigned to its Asia/Taipei date | Only days with eligible data; chronological ascending, no calendar filling | Overview trend, Q12 |
| `course` | Booking line -> session -> canonical course ID | Observed courses; amount descending then course ID ascending under top-k | Breakdown, Q13 |

These are trusted SQLGlot/catalog bindings, not a new relational AST. P2.2
implements them with shared scalar query construction/transactions and
on-demand dimension admission, without globally extending scalar permissions.
The [runtime guide](grouped-amount.md) defines fixed output/key caps and explains
why existing FK parent requirements remain. The Taipei date rule is not a
general timezone/DST promise.

Each eligible line belongs to exactly one member of each admitted dimension.
Amounts are additive under these partitions; the accepted discount constraints
keep line amounts non-negative. Do not extend that assertion to distinct
booking/account counts across courses. Optional all-group amount views may be
reconciled with the compatible required amount; a failed check makes that view
unavailable, not repaired.
For an empty population, a null scalar and empty observed-group rowset agree
as absence, not as an invented numeric zero.

Full observed-group output must fit trusted row/byte/deadline budgets or be unavailable.
Never silently truncate it. Top-k returns at most k correctly ranked groups
from the entire bound population; it is a complete **top-k selection**, not a
complete group universe. Do not infer the total from those rows. Empty observed
groups are an empty checked rowset, not generated zero-valued members.

## 5. Compatibility and snapshot admission

| Axis | Required rule before composition |
| --- | --- |
| Semantic/catalog version | Same approved catalog identity/digest and metric definition; derivation and dimension bindings are versioned reviewed definitions, not coincidentally equal names |
| Population and grain | Same confirmed/current-status population, exclusions and center filter; permitted many-to-one dimension binding cannot multiply lines |
| Time basis | Booking creation time only; no payment/refund/session-time substitution |
| Range / timezone | Overview amount views and Breakdown numerator/denominator share exact scope. Compare deliberately uses two explicit, non-overlapping calendar months in the same timezone; unequal month lengths are disclosed, not normalized away |
| Unit | Same `TWD_minor` for amount inputs. Difference preserves that unit; share/growth are dimensionless. No currency/physical-unit conversion |
| Coverage / truncation | Inputs must be checked for their declared need. Incomplete/budget-truncated results cannot feed derivation. Top-k can feed its subtotal, never substitute for all-scope total |
| Snapshot / source | One admitted source and one controlled read snapshot for all participating facts, including both Compare months and Breakdown denominator; no cross-snapshot reconciliation |

**Execution order:** select/bind intent first (including any future model call);
then open a bounded read-only analysis batch, validate source/bind exact codes,
execute required needs before independent optional needs, check/derive, materialize
results and close. Use one shared analysis budget, not a fresh budget per slot.
Do not hold a transaction across a model call or synthesis.
A write-race witness must prove that neither comparison nor denominator can
observe a different snapshot.

Current `execute_facts()` opens and closes a transaction for **one FactRequest
scope**, and all its metrics are required. Calling it twice is not a same-snapshot
Compare implementation. P2.1 instead runs the two named scopes using shared
private transaction/scalar helpers, reusing the existing compiler, admission,
authorizer and execution path. No raw connection/SQL or generic multi-scope
planner is exposed to callers or models.

For optional execution, a reviewed component-local failure need not invalidate
previously materialized independent required facts. If the transaction/snapshot
is lost, abort the analysis even when some required facts were materialized.
Do not reopen it to fill gaps, mix snapshots or call a global failure partial.
Global interruption/incomplete evidence is not a successful AnalysisPack.
Exact SQLite cleanup/isolation mechanics need offline witnesses in implementation;
PostgreSQL cancellation/isolation remains P4.

## 6. Derived arithmetic: finite server policies

Every derived fact names input fact IDs, inherits compatible scope/snapshot
evidence and records its unit/definedness. No operation is model-authored.

| Fixed derivation | Inputs and checks | Zero / NULL / failure | Justification |
| --- | --- | --- | --- |
| Difference | Two checked integer amount facts in current/baseline roles; same definition/unit/population, intentional period difference | Zero is a value. NULL or unavailable/incompatible input -> unavailable; no substitute zero | E02 explicitly needs delta; semantically unavoidable, reusable across admitted month pairs |
| Relative change | Checked delta and its exact baseline fact; delta provenance must identify that baseline and the current fact; compute delta / baseline | Baseline 0 -> `undefined: zero_baseline`, including 0 vs 0; NULL/missing baseline or unavailable delta -> unavailable | E02 explicitly needs growth; not target attainment |
| Selected subtotal | One checked course amount rowset with complete declared top-k coverage; sum exactly the returned rows | Nonempty all-zero rows -> measured 0; empty rowset -> null/no population, not invented money; incomplete rows -> unavailable | E03 needs a numerator; Q13's ranked vector is the reusable input |
| Share of scope | Checked subtotal and separate all-scope amount; same metric/range/filter/snapshot, proven selected subset of whole | Total 0 with compatible zero subtotal -> `undefined: zero_total`; NULL/missing input -> unavailable. Positive subtotal with zero total is inconsistent, not a ratio | E03 explicitly needs share; a constrained subset/whole operation, not arbitrary division |

Difference and subtotal use exact integers and explicit overflow failure.
Relative change and share retain exact rational values. Display percentages
multiply that ratio by 100 deterministically, rounding to two decimal places
with half-even rounding when needed (trailing zeros may be omitted).
The exact ratio and its input IDs remain available. No infinity, NaN, guessed
denominator, absolute-value baseline, clamping or hidden conversion is allowed.

The low-level division arithmetic is reusable across E02/E03, but denominator
**roles** are different. This admits neither a generic ratio-expression operator
nor E11's target lookup/missing-target semantics. These four finite derivation
tags are server-owned provenance labels, not a callable expression language.
No new arithmetic primitive is needed for Overview.

## 7. Required, optional and result status

The recipe version determines slot roles **before** execution:

- **Required fact/derivation:** an obligation; it cannot be removed or demoted.
- **Optional fact:** a declared enhancement independent of required outputs.
  It remains a visible slot even when unavailable.
- **Checked:** its declared computation completed and checks passed. A source
  fact may legitimately contain the existing empty-population null; that null
  cannot be used as numeric zero in arithmetic.
- **Undefined:** complete compatible numeric inputs prove a specified zero-
  denominator condition. It has a reason and input IDs, but no numeric result.
  It is not an execution failure and must be displayed as undefined.
- **Unavailable optional:** missing input, timeout, failed check or other
  inability to supply the slot; preserve its name/reason, never synthesize it.
- **Failed required:** any required slot is unavailable/incompatible/incomplete.
  Other checked facts may be retained as evidence, not promoted into an overview.

| Overall AnalysisPack status | Rule |
| --- | --- |
| `complete` | All declared slots resolve as checked or explicitly undefined; no unavailable slot |
| `partial` | Every required slot resolves, but at least one declared optional slot is unavailable |
| `failed` | At least one required slot is unavailable, incompatible or incomplete |

Complete means complete **coverage**, not that every requested ratio has a
numeric value. For example, a checked zero baseline yields a complete comparison
with growth explicitly undefined. A missing/null baseline prevents delta/growth:
their required slots are unavailable, so the analysis fails with that data
condition disclosed; it is not silently treated as a transport failure or 0%.

E10 injects timeout into `overview@0.1.category_amounts` after independent core
facts have been checked. Return core evidence (and any checked daily view),
`status=partial`, and that named slot as unavailable. Injecting the same failure
into a core slot must instead yield `failed`. A dependency on an unavailable
fact is unavailable too; successful unrelated facts never repair it.
P2.3's fixed private witness and P2.4's public Overview share the finite local
failure classification above. They represent required/global failure by
raising, not by returning a failed or partially successful pack.

## 8. Worked WHAT -> HOW decompositions

Numbers here explain existing evaluator witnesses to reviewers. **They are not
runtime constants, model context, expected-value lookups or per-case branches.**

### Overview / E01, with E10 control

Question: "CTR-A01 2026年3月的報名狀況如何？"

1. **Bound intent:** explicit center code, March 2026, Asia/Taipei, confirmed
   booking activity. The code is the unambiguous binding input, not a chosen name.
2. **Recipe:** `overview@0.1` with that month and center.
3. **WHAT:** required amount/bookings/seats; optional daily amount/category mix.
4. **HOW:** after selection, one controlled batch resolves `CTR-A01` to `CA`
   and constructs the existing three-metric scalar FactRequest plus two amount
   grouped needs.
   The UTC range is `[2026-02-28T16:00:00Z, 2026-03-31T16:00:00Z)`.
   The server supplies reviewed dimension bindings, ordering, budgets and checks.
5. **Checked AnalysisPack:** required values are 68000 TWD_minor, 4 bookings,
   6 seats, each with its own fact ID and common snapshot. Optional rows either
   carry checked evidence or a named unavailable reason. E10's injected category
   timeout makes this partial, not a different recipe or model question.

**Model may:** select Overview and echo the explicit center/month meaning.
**Server owns:** canonical binding, FactRequests/grouping, reconciliation and
coverage/status. **Model must not:** choose a center by duplicate name, replace
seats with people, invent targets/causes, calculate values or delete a core slot.

### Compare / E02

Question: "2026年3月全體已確認報名金額比2月如何？"

1. **Bound intent:** same confirmed booked amount, all centers; March vs February
   2026, Asia/Taipei. No per-day normalization or refund subtraction.
2. **Recipe:** `compare@0.1`, named current/baseline month scopes.
3. **WHAT:** two amounts, their difference and relative change.
4. **HOW:** two scalar FactRequests in one controlled snapshot, using the
   existing reviewed binding. February is
   `[2026-01-31T16:00:00Z, 2026-02-28T16:00:00Z)`;
   March is the range above. Server checks compatibility, then derives delta
   from input IDs A/B and growth from delta ID D plus baseline ID B.
5. **Checked AnalysisPack:** A=158000, B=50000 TWD_minor; D=A-B=108000
   TWD_minor; growth=54/25=2.16, displayed as 216%. Provenance reaches A and B.
   Zero/missing baseline follows section 6, not a repaired denominator.

**Model may:** select Compare, the admitted metric and stated comparison roles.
**Server owns:** both requests, shared snapshot, subtraction/division, definedness
and checks. **Model must not:** compute growth, invent a missing month/year,
swap current/baseline, silently change metric/population or use evaluator gold.

### Breakdown / E03

Question: "2026年3月報名金額前兩名課程合占全部金額多少？"

1. **Bound intent:** confirmed booked amount, all-center March scope; course
   dimension, top two; denominator is explicitly **all** that scope's amount.
2. **Recipe:** `breakdown@0.1`, course, k=2, explicit month.
3. **WHAT:** ranked course amounts, their subtotal and all-scope share.
4. **HOW:** one grouped amount task ranks the full eligible population before
   applying limit 2; a separate scalar need obtains all amount in the same
   snapshot. Top-k changes returned coverage, **not** the source scope.
   The server sums the selected rows and binds the denominator to the scalar
   fact, never the ranked subset. Stable tie-break is course ID ascending.
5. **Checked AnalysisPack:** K1=68000 and K3=60000; subtotal=128000;
   independent total=158000 TWD_minor; share=64/79, displayed as 81.01%.
   Subtotal cites the grouped fact; share cites subtotal and total IDs.
   For k=3, Q13 exercises the same grouping/order/limit, not another operator.

**Model may:** select Breakdown, admitted metric/dimension and requested k.
**Server owns:** ranking/ties, subtotal, whole-scope denominator, exact share and
coverage. **Model must not:** calculate share, choose denominator membership,
insert selected-course filters into the total or replace total with subtotal.

Across all recipes: no model SQL/Python, arithmetic, invented metric/period,
causal claims, silent requirement removal or evaluator/gold context.

## 9. Bounded implementation sequence

**P2.1 scope (#16): offline scalar Compare on one controlled analysis snapshot.**
Compare can come first: it needs no grouping, new metric or relational operator.
It cannot be a wrapper making two unrelated `execute_facts()` calls.

Its delivery is bounded to E02 + Q01/Q09: reuse the scalar compiler/executor in a
multi-scope batch, add opaque fact IDs, validate compatibility, and implement the
two fixed Compare derivations plus required coverage. Prove 158000/50000,
108000 and 54/25; zero vs missing baseline; incompatible unit/population/time/
catalog/snapshot; failed required input; exact arithmetic and write-race
consistency. Use disposable scenarios, not edits to core seed or gold.
No grouped runtime, optional execution, prompt change or live call in that issue.

The following slices require separate authorization; the sections above record
what is implemented, not authorization to begin the next slice:

1. **Reusable grouped amount fact:** Q11-Q13 and existing tie witness; three
   reviewed dimensions, observed membership, stable order and k=1-3. Prove NULL,
   empty, row-budget and fan-out behavior. Q10 member completion stays out.
2. **Required/optional composition:** controlled analysis-batch failure isolation
   and explicit coverage; E10 plus required-failure counterparts.
3. **Overview instantiation (P2.4):** exact same-snapshot code binding and public
   request/result contracts over the shared fixed composition; no new primitive.
   **Breakdown instantiation (P2.5):** independently executed denominator,
   selected subtotal and exact share with role-linked provenance; no case-ID
   branches or optional recovery.
4. **Model selection/instantiation (P2.6, #26):** the
   [shared one-shot adapter](recipe-model-integration.md) validates one closed
   proposal and dispatches the selected unchanged native request. It preserves
   native outcomes and wrong-but-valid interpretations, without a second model,
   repair, evaluator constraints or per-language routing. Offline fake-transport
   checks do not establish model quality or complete P2.
5. **Owner-authorized integration:** at least one live natural-language path
   per admitted recipe. Declare panels and budgets separately; E10 stays an
   injected operational control.

P2 exit still requires common-kernel reuse, required/optional behavior, a live
path per recipe and no special operator/repair for equivalent combinations.
Completing these offline slices does not complete P2.

## 10. Operational metadata and expansion stop

The last operator-confirmed route has gateway retry enabled, fallback disabled
and response cache disabled; upstream inference attempts remain unknown.
That belongs to execution/evaluation reporting. Do **not** add retry, provider
or cache policy fields to recipes, analytical needs or AnalysisPack semantics.

Stop design expansion and report before implementation if any admitted anchor
requires a SELECT/JOIN/filter language, nested generic expression AST, one
operator per case, question-specific recipe, generic repair framework,
recipe-specific parser, model-written code, hidden semantic repair, second
execution path, combined WHAT/HOW mega-plan, or gold in model context.
A finite reviewed analytical enum is not permission to grow a SQL grammar.

## Evidence references

- [Architecture](architecture.md), [phase gates](roadmap.md),
  [existing kernel guarantees](fact-kernel.md), [evaluation boundaries](evaluation.md).
- [Existing cases](../evals/cases/learningops.json) and
  [reference SQL/values](../evals/oracles/learningops.json).
- [Accepted metric definitions](../evals/fixtures/learningops/README.md),
  [schema](../evals/fixtures/learningops/schema.sql),
  [seed](../evals/fixtures/learningops/seed.json).
- Current one-scope/all-required mechanics: `grepbit/kernel.py:execute_facts`;
  existing evidence fields: `grepbit/contracts.py:Fact` and `FactPack`.
- GitHub #1 records P1 completion and #14 owns this design decision. No test or
  live result is created by a design example.
