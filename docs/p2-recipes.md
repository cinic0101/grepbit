# P2 recipes v0.1: design and admission checkpoint

Status: design accepted in #14 / PR #15 on `dev` at
`ea1c62c6ceecd5c12e4a359d8532d04f80b59850`, under roadmap #1.
P2.1 (#16) implements only the offline scalar Compare slice described below;
the remaining matrix is admission for future work, not implemented capability.
No grouping, optional execution, model prompt, dependency, fixture, gold or live
run changes are part of P2.1.

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

Both public execution entries use the same private compilation, source
admission, read-only transaction, authorizer and scalar-result checks. Compare
opens one connection/transaction, validates the source once, and runs both
scopes under one `_Budget`: timeout, VM callbacks and source-validation rows
are not reset. The existing defaults/hard maxima remain unchanged.
Compatibility checks cover catalog/digest, metric/unit, population/grain,
filters, time basis/timezone, complete checked coverage, bound role ranges and
the common snapshot. No user-editable compatibility rules are introduced.

Only `difference` and `relative_change` are implemented derivations. Grouped
facts, subtotal/share, Overview/Breakdown, optional slots, rendering, model
instantiation and live recipe evidence remain future work. P2.1 does not
complete the P2 exit or establish model quality, backend parity or generalization.

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
The narrow P2.1 types above implement only Compare and identified scalar outputs.
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
duplicating all of its evidence fields. Grouped coverage remains future work.
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

These are trusted SQLGlot/catalog bindings, not a new relational AST. Grouped
execution must extend source/relationship admission and row-budget enforcement
inside the common kernel; the current scalar-only executor does not already
support it. The Taipei date rule is not a general timezone/DST promise.

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

For later optional execution, a query failure must not invalidate previously
materialized independent required facts. If the transaction/snapshot is lost,
do not reopen it to fill gaps or mix new facts with old ones. Mark affected
optional slots unavailable; any affected required coverage makes analysis fail.
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

## 9. Smallest next implementation issue

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

Then, each as separately authorized work:

1. **Reusable grouped amount fact:** Q11-Q13 and existing tie witness; three
   reviewed dimensions, observed membership, stable order and k=1-3. Prove NULL,
   empty, row-budget and fan-out behavior. Q10 member completion stays out.
2. **Required/optional composition:** controlled analysis-batch failure isolation
   and explicit coverage; E10 plus required-failure counterparts.
3. **Overview and Breakdown instantiation:** the same facts and finite
   derivations, with explicit denominator provenance; no case-ID branches.
4. **Model selection/instantiation:** one shared bounded recipe contract and the
   same execution path, not separate recipe parsers or repair turns.
5. **Owner-authorized integration:** at least one live natural-language path
   per admitted recipe. Declare panels and budgets separately; E10 stays an
   injected operational control.

P2 exit still requires common-kernel reuse, required/optional behavior, a live
path per recipe and no special operator/repair for equivalent combinations.
Completing this document or scalar Compare alone does not complete P2.

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
