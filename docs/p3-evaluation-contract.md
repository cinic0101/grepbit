# P3.0: natural-language quality and stability contract

**Status: proposed for owner review under #37, not accepted or executable.**
Contract revision: `p3-evaluation-contract-v0.1`.
Design baseline: `dev@f21c914915f34656c1e8c0069c28afadb5bbc7ae`.
This document admits no product change, live request, case freeze or P3 exit.

## 1. Thesis, evidence and route boundary

P3 asks whether the system chooses the intended action and facts and satisfies
the whole request. A legal native request with correct SQL and numbers can still
answer the wrong question. Intent is therefore graded before execution, coverage
and values; fluent language cannot rescue a failure upstream.

The owner's [P2 exit decision](https://github.com/cinic0101/grepbit/issues/1#issuecomment-5754274130)
and closed #36 establish the three-family, nine-input regression result, not
fresh quality evidence. #34 / PR #35 preserved strict verification while adding
a generation constraint. Successful JSON is not proof of semantic correctness
or of the serving backend's actual constrained-decoding internals.

The first P3 panel targets the **recipe entry only**, not a new universal front
door. P1 stays available and protected separately. Do not silently route an
unsupported recipe question through P1, a fixture reference query or another
executor. In particular, a fixture definition is not a product capability.

| Existing recipe | Admitted meaning and required evidence |
| --- | --- |
| Overview | One exact supplied center code and explicit full month; confirmed booked amount, distinct booking count, booked seats; observed booking-day and category amount views or explicit native gaps |
| Compare | All centers; confirmed booked amount; two distinct explicit full months with current/baseline roles; amounts, difference and baseline-relative change |
| Breakdown | All centers; one explicit full month; amount-ranked courses, explicit integer k in 1-3; ranked subset, independent whole amount, subtotal and share |

All use current confirmed bookings and booking **creation** time, not status
history or payment/refund/session/attendance time. Money is `TWD_minor`; seats,
booking IDs, booking accounts and people are different units/populations.
Overview/Breakdown retain the fixed UTC+08:00 month profile labeled Asia/Taipei;
Compare retains its native calendar validation. Preserve accepted equivalent
instant representations without introducing inferred dates.

Current recipe output has only request and declined branches. Clarification,
resume and synthesis are **not implemented**. A future accepted action-contract
revision is a prerequisite for scoring clarification controls. Do not score the
old adapter against a new policy and claim a product regression or repair its
output in the evaluator.

Sources: [recipe contract](recipe-model-integration.md),
[native recipe admission](p2-recipes.md#2-recipe-capability-matrix),
[P2 grader](recipe-smoke.md#intent-first-values-last),
[evaluation boundaries](evaluation.md), [phase gates](roadmap.md).

## 2. Matrix before examples

This is a wording-independent category matrix, **not authored fresh questions**.
Category IDs are evaluator vocabulary and never runtime routes. One category
may contain several distinct requirement bundles; several categories may test
one family. Do not sum category rows to obtain semantic breadth.

Common matrix scope **S**: the route boundary above, explicit full months in
Asia/Taipei, current-confirmed population, creation-time filtering, booking-line
amount/seats and distinct booking-ID count. Any deviation must be explicit.

Oracle abbreviations: **N** exact accepted native-semantic set; **F** independent
facts, units, required coverage and provenance; **A** exact action;
**C** accepted clarification field/closed choice set; **D** unsupported category;
**H** human semantic/translation review, never a substitute for N/F.
**M** means a proposed scored/control slot; **O** means observational design
coverage only, no first-panel score. Answer slots use the threshold in section 7;
mandatory clarification/decline/regression controls require every variant.
Language allocations below are exact in section 6; `single` means its assigned
language, not permission to select the easiest language after execution.

Provenance shorthand: **HIST** names an exposed historical seed/trap;
**SYN** is a synthetic boundary design, visible here; **NEW** means a future
independently authored candidate, not an existing fresh case. Concrete HIST
descendants are `exposed_regression`; concrete new examples designed with the
implementer are `design_seen`. NEW may become `frozen_fresh` only under section 5.
No real private problem/source confirmation is claimed.

| ID | Behavior / user intent | Recipe or action | Trap / ambiguity | Branch | Required scope, metric, population, grain | Languages | Provenance / exposure | Gate / slots | Oracle | Current support | Architecture pressure / later boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | Answer: scoped booking overview | Overview | Wrong code/month, inactive center mistaken for zero | answer | S, exact center; three core units; null/empty disclosures | all + single | HIST E01/Q05 and native empty controls; NEW only with novel bundle | M: P01/P09 | N/F/H | Native supported | No name resolver, new metric or data filling |
| A02 | Answer: several compatible overview requirements; false-refusal control | Overview | Dropped daily/category requirement; count interpreted as people; reordered/negated phrasing | answer | S; one center/month; fixed core plus both observed amount views | all + single | HIST E01/Q02/Q03/Q11/Q12; NEW conditional | M: P02/P07/P10 | N/F/H | Fixed five-slot pack supported | No selectable-slot DSL or unrelated decomposition |
| A03 | Answer: explicit comparison roles; false-refusal control | Compare | Current/baseline swapped; chronological order mistaken for role | answer | S, all centers, two role-bound months, amount/delta/growth | all + single | HIST E02 and wrong-valid adapter controls; NEW conditional | M: P03/P11 | N/F/H | Supported, including earlier current month | No inferred baseline or second planner |
| A04 | Answer: unambiguous temporal reference | Compare | Shared explicit year lost; month assigned to wrong year | answer | S; both full months and roles recoverable solely from text | single | HIST native period controls; NEW conditional | M: P04 | N/F/H | Shared stated year and explicit cross-year requests supported | No clock/as_of defaults or date language |
| A05 | Answer: explicit ranked selection; false-refusal control | Breakdown | Wrong k, all boundary ties, filled absent courses | answer | S, all centers, course grain, explicit k; fixed tie policy | single | HIST E03/Q13 and k/tie controls; NEW conditional | M: P05/P12 | N/F/H | k=1/2/3 supported | No top-k inference, tie-policy override or new dimension |
| A06 | Answer: selection and whole-scope share | Breakdown | Top subset used as denominator; share=1 mistaken for universal coverage | answer | S; independent unranked whole denominator, exact rational share | single | HIST E03 and denominator controls; NEW conditional | M: P06/P08 | N/F/H | Supported | No generic ratio/formula operator |
| C01 | Ambiguous count inside an otherwise supported overview | Typed count clarification | Seats vs accounts vs visits vs distinct people | clarify | Explicit center/month and overview; only one count interpretation unresolved | all | HIST E05 trap; NEW only if substantively different bundle | M: P13 | A/C/H | No clarify branch today | Bounded interpretation choice; no P1 fallback or invented people metric |
| C02 | Two explicit months, ambiguous comparison orientation | Typed role clarification | Either named month could be current | clarify | S, amount/all centers; choose one of two complete role assignments | all | SYN; NEW conditional | M: P14 | A/C/H | Declines today | One typed role choice, not a planning loop |
| C03 | One-center overview with two explicitly supplied code candidates | Typed entity-choice clarification | Arbitrary code chosen or centers combined | clarify | S, one center; choices must be the supplied codes | single | HIST E04 binding trap; adapted scope is not fresh | M: P15 | A/C/H | No clarify branch today | No name-to-code lookup in first slice |
| C04 | Ambiguous amount notion in otherwise bounded overview | Typed metric-meaning clarification | Booked amount vs cash/refunds treated as synonyms | clarify | Explicit overview center/month; one named supported interpretation and unsupported alternatives | single | HIST Q01/Q06-Q08/Q15-Q16 contrasts | M: P16 | A/C/H | Declines today | Choice can end in decline; do not promise all alternatives |
| D01 | Profit, cost, target attainment or causal request | Explicit capability decline | Convenient amount substituted, cause invented | decline | Financial/causal meaning not in S | single | HIST E07/E11/Q18; SYN causes | M: P19 profit only; others O | A/D/H | Decline representable, quality unmeasured | Definitions/data/product admission, not more operators |
| D02 | Cash, refunds or historical booking-state analysis | Explicit semantic decline | Correct number for wrong population/time basis | decline | Posting-time/refund/history rather than S | single | HIST Q06-Q08/Q15-Q16; native history boundary | M: P20 posting-time cash only; others O | A/D/H | Decline representable | No accounting or temporal ledger expansion |
| D03 | Annual, multi-month or partial-month aggregation | Explicit period decline | One convenient month silently substituted | decline | Requested period cannot be a native full month | all | HIST P2 boundary; NEW conditional composite bundle | M: P17 multi-month only; others O | A/D/H | Decline representable | No aggregation DSL; explicit two-month Compare is different |
| D04 | Related answerable request plus an unrelated requirement | Explicit whole-request decline | Answerable subset hides unmet requirement | decline | No single admitted recipe covers the full requirement list | all | HIST P2 decomposition boundary; NEW conditional | M: P18 | A/D/H | Decline representable | No arbitrary multi-question planner |
| D05 | Missing year, month, baseline or k | Explicit incomplete-request decline | Invented defaults or unnecessary state expansion | decline | S cannot be instantiated; finite alternatives not supplied | single | HIST E06 and P2 incomplete-input policy | M: P21 missing year only; others O | A/D/H | Current conservative decline policy | E06's broader clarification aspiration deferred within P3 |
| D06 | Unsupported filter, population, grain or dimension | Explicit capability decline | Silently remove center filter or replace grouping/metric | decline | E.g. center-filtered Compare, non-confirmed population, account-ranked Breakdown | single | HIST native scope/metric guards; SYN composites | M: P22 center-filtered Compare only; others O | A/D/H | Decline representable | No generic filters/relational DSL |
| D07 | Arbitrary formula or conversion | Explicit capability decline | Alias changes units without calculation | decline | Outside fixed delta/growth/share or original units | none | HIST E09; SYN currency/formula boundaries | O | A/D/H | Decline representable | New semantics require separate admission; not P3.0 |
| D08 | Explicit account/people/attendance count through recipe entry | Explicit capability decline | Seats substituted for requested unit | decline | Count not provided by these recipes; P1 accounts stay separate | none | HIST Q02-Q04/E05 | O | A/D/H | Decline representable | No silent narrowing of global P1 capability |
| D09 | Empty-member enumeration or arbitrary details | Explicit capability decline | Observed groups called whole catalog; source rows leaked | decline | Catalog completion/anti-join/detail grain outside S | none | HIST Q10/Q14/E12 | O | A/D/H | Not admitted | Bounded drill-down P4; arbitrary details non-goal |
| C05 | Bare ambiguous entity name, free missing year or several ambiguities | Deferred clarification/resume design | Invented choices, unsafe lookup or multiple hidden repairs | clarify target; first-slice decline | No closed choice can be built from current supplied semantics | none | HIST E04/E05/E06, original expectations retained | O | A/C/H | Not implemented | Later P3 entity/year policy; not evidence of successful original cases |
| X01 | Partial native pack under injected optional failure | Offline operational control | Omitted required fact called complete | not a model action | E10, fixed required/optional native roles | none | HIST E10, exposed_regression | O, offline only | F | Accepted offline injection | Real cancel/deadline and PG lifecycle remain P4 |

Required wrong-valid traps are covered by A01-A06, C01/C04 and D01-D06:
metric, count unit, population, scope, grain, comparison roles, month/year,
center, k, denominator and booked/cash/refund/profit distinctions. They are
**not all live-measured by the first allocation**. The subcategory labels above
explicitly delimit the sample; a pass of one D06 filter control is not evidence
for all populations/dimensions. No new fixture or gold is authored in P3.0.

## 3. Answer, clarify or decline

Apply capability/requirement coverage first, then ambiguity. A request with a
definite unsupported requirement declines as a whole; do not ask a cosmetic
clarification about a different field. Otherwise clarify only when one material
semantic choice has two to four grounded interpretations and at least one
leads to an admitted request. Answer only when all required meanings are bound.

| Situation | Proposed first-slice policy | Why |
| --- | --- | --- |
| All requirements fit one recipe; explicit parameters or unambiguous shared stated year | answer | Natural phrasing is not a capability restriction |
| Several requested outputs already in one fixed recipe | answer | Preserve all requirements; do not invent arbitrary decomposition |
| People/count ambiguity in an otherwise complete Overview | clarify | Do not equate seats, accounts, visits and humans; some choices end in decline |
| Bare all-center people question without a recipe-compatible scope | decline in first slice | Choosing a count alone cannot make it a supported recipe request |
| Two explicit comparison months with no role assignment | clarify | Exactly two grounded role assignments; no baseline invented |
| Missing baseline month/year, missing month/year, or missing k without closed alternatives | decline in first slice | Filling a field is not the same as choosing among grounded meanings |
| Ambiguous period assignment with two complete alternatives explicitly in text | clarify | One bounded semantic choice; no date from clock or fixture |
| Explicit code plus unique unambiguous period | answer | Preserve code bytes; trusted executor binds it |
| Two supplied candidate codes for one otherwise supported Overview | clarify | Select a code, never guess or combine centers |
| Name-only/novel alias requiring name lookup | decline in first slice; later P3 decision | Current model has no mapping; first slice admits no resolver or code hints |
| Ambiguous financial term in otherwise complete Overview | clarify if closed supported/unsupported meanings can be stated | Clarification must not imply that profit/cash become available |
| Explicit profit, cash/refunds, targets, people metric, formula or conversion | decline | Meaning is clear but unsupported by the recipe route |
| Unsupported dimension/filter/grain, annual or multi-month total | decline | No convenient narrowing; two explicit Compare months are not aggregation |
| Unrelated requirements, or supported plus unsupported requirement | decline | No partial convenient answer to a compound unsupported request |
| More than one independent missing/ambiguous field | decline in first slice | One clarification cannot complete it; no workflow engine |

These are **explicit initial P3 scope decisions**, not changes to historical
oracles. E04/E05/E06 remain authored clarification aspirations in their original
assets. In particular E06 says ask for a year; this first slice defers free-form
year collection rather than marking that original case passed by a decline.
Original E04's name lookup and E05's broader count question are also not solved
by C03/C01. Owner ratification must acknowledge these deferred capabilities.
The first slice does not establish full P3 clarification/resume completion.

### Minimal clarification contract, design only

Recommend a new closed action alternative alongside the unchanged native
request alternatives and decline. The exact serialization/version belongs to
a later separately accepted P3.1 design; no schema below is a runtime API.

Minimum semantic content: action `clarify`, one allowlisted ambiguity field,
two to four typed interpretation choices, and the already bound scope. Candidate
field meanings are count basis, comparison-role assignment, explicit center-code
choice and booked-versus-other amount meaning. A choice contains semantic IDs
or supplied values, never SQL, formulas, executable tasks or a new metric.
Reject irrelevant/redundant/duplicate choices and fields not ambiguous in the
question. An unsupported interpretation may be a choice only if explicitly
labeled unavailable and resolving to decline, not to a substitute metric.

Prefer server-rendered, reviewed question/choice templates over model-authored
free text. This bounds misleading promises, instructions and private-data
echoing. Text fluency is not the oracle; accepted field/choice meaning is.
The server must validate typed choices, not look up evaluator gold. Semantic
choice correctness still needs evaluation; schema validation cannot prove it.

Surface one ambiguity per turn. Do not answer an assumed interpretation while
asking for confirmation. No analytical execution before choice binding, no
model-generated entity map, and no automatic second call.

### Resume: compare A and B, recommend A first

| Option | Evidence value | Cost / risk |
| --- | --- | --- |
| A: action/clarification decision first; resume later in P3 | Isolates the primary legal-but-wrong-action risk; exposes false clarification cheaply | Does not demonstrate task completion or a usable conversation |
| B: clarification plus one-turn resume immediately | Tests that choices actually bind and complete the task | Adds state, expiry, stale scope, replay, invalid-choice and revalidation failure modes before branch quality is known |

Recommend **A**, not because resume is optional for the eventual P3 promise,
but because debugging branch selection and state binding simultaneously would
obscure failure attribution. A later gate must implement/test one bounded resume
before claiming the roadmap's clarification/resume deliverable.

Later resume needs an opaque server-issued binding token (or equivalent
server-held reference), bound to immutable normalized scope, ambiguity/choices,
contract/catalog/source identities, expiry and a single accepted choice.
No cross-session persistence is required for the first one-turn local gate;
cross-process persistence is a separate decision, not a conversational store.
Revalidate entity binding and applicable source semantics on resume; do not
reuse a stale snapshot as current truth. Invalid/expired choices fail explicitly.
Bind the typed choice deterministically; do not ask the model to reinterpret
everything or silently change already bound parameters. If original text must
be retained, keep its approved bounded form as untrusted user data, separate
from system instructions; never append gold or the whole evaluation transcript.
P3.0 introduces neither token code nor a hidden resume protocol.

## 4. Separate grading layers and synthesis

| Layer | Ordered assessment | Evidence / comparison |
| --- | --- | --- |
| 1: action and intent | expected branch, then recipe/version, then complete request semantics or clarification choices | Exact accepted semantic sets; preserve role, metric, population, unit, period, scope, center, grain, k and denominator obligation |
| 2: checked facts | execution, native slot/coverage states, selected fact roles/provenance, then values | Independent oracle; exact integers/rationals/ordered rows, null vs zero vs unavailable; compare meaning, not SQL strings or random UUID text |
| 3: synthesis, later gate | supported claims, coverage, limitations and linked facts; style separately | Claim-to-fact references and human-reviewed rubric; any new arithmetic must be server-derived |

For first formal scoring, choose **action plus checked-fact selection/coverage
only**, with synthesis explicitly `not_assessed` (a layer state, not a successful
outcome). Adding synthesis now would mix intent failures with a second generation
surface and extra token/latency cost. A later P3.x gate must assess synthesis
before claiming the full P3 deliverable; this choice does not silently remove it.

There is no new free-form fact selector in the first slice: recipe selection
selects its fixed fact set. Grade whether that set covers the requested facts.
Allow only the recipe's predeclared auxiliary slots; they are not user-requested
claims and must not imply unsupported answers. Wrong-scope facts, extra invented
facts or irrelevant substitutions fail even when other facts are correct.
Custom requested exclusions/outputs that require changing the template decline.

Native optional is not synonymous with optional to the user. An explicitly
requested daily/category view is a required user obligation. A disclosed native
partial pack remains partial, never complete-correct. For the first scored
answerable set, select independently verified complete-data cases; native
checked-empty Overview or defined-undefined ratios may be included only with
explicit corresponding gold. Empty Compare/Breakdown data-condition failures
are not complete answers and are not mislabeled as transport failures.

Do not change native statuses in evaluation. Retain every layer's status and
reason, even when a higher-priority semantic error determines the primary outcome.

## 5. Exactly three exposure labels and provenance

| Label | Definition and allowed claim |
| --- | --- |
| `exposed_regression` | Previously executed/discussed concrete meaning with known expectation, any repair-informing case, or a descendant whose only novelty is paraphrase/translation/date/code/k substitution around the same known trap. Protects regressions, not fresh generalization. |
| `design_seen` | A new concrete case/requirement bundle visible during candidate design or implementation, not already an exposed regression. Development evidence only. |
| `frozen_fresh` | Independently authored, reviewed and frozen before first scored use, after candidate freeze, without case-specific feedback to candidate authors or candidate modification from it. First-run evidence only, subject to the isolation audit below. |

Known behavior classes may be public; that does not automatically expose every
future distinct requirement bundle. Conversely, unseen wording is not a fresh
semantic family. A changed month, code, k or translation alone is not sufficient.
Every future family needs a semantic signature (action, requirement list,
scope/roles/grain/units/time/coverage obligations), historical-parent references,
trap/novelty rationale and exposure history. Deduplicate siblings into one family.

Provenance records separately identify historical P0/P1/P2 material, a previous
observed problem, synthetic boundary design or newly designed case. The first
panel is synthetic only. Historical descendants inherit exposed status even
if a new file or language is used. Cases from real problems, if ever admitted,
are already exposed and require private-source protection; no such case is
silently included here.

**No frozen-fresh case exists in this change.** Reserve the slots below; do not
author their questions/gold in this implementation conversation. Freeze candidate
source/prompt/schema first, then have an independent case author/reviewer inspect
the historical corpus, design distinct bundles and author gold without querying
the candidate. Record who saw which case material and when. If implementation
authors see case-specific expectations and adjust the candidate, downgrade
before running; do not use a new paraphrase to launder exposure.

There is no claimed technical access isolation today, so do not say "blind
holdout." A later local evaluator may read frozen gold to grade, but its
pre-run review cannot become candidate feedback. Explicitly record that access.
After first scored execution (or repair use), store subsequent-use exposure as
`exposed_regression`; never mutate the immutable original run's first-run label.
Publish first-run and later regression results separately.

## 6. Bounded first formal panel proposal

Propose **25 family slots / 45 inputs**, conditional on the novelty/admission
audit: 22 quality/control slots plus the three original P2 anchor families.
Target **12 frozen-fresh** slots (8 answer, 2 clarify, 2 decline), **13 exposed
regression** slots (4 answer, 2 clarify, 4 decline, 3 P2 anchors), and **0
design-seen** scored slots. Design-seen development examples remain outside
this first-run score. None of the 12 reserved slots is already certified fresh.

This is a capacity target, not a claim of 25 independent semantic discoveries.
The three-recipe boundary may not support that many genuinely distinct bundles.
If deduplication/novelty review cannot fill the target, **stop before freezing
the run and return a smaller, explicitly revised contract for owner review**.
Do not pad with paraphrases, switch labels or broaden runtime semantics to fill
a quota. Panel slots below are not executable case IDs or question assets.

`NEW` rows require independently authored new bundles. `HIST` rows name their
ancestry and test a different obligation from the P2 anchor where applicable.
If a proposed historical bundle collapses onto another family, merge its inputs
under that family and revise counts before approval; never count it twice.

| Slot | Category | Branch | Languages | Proposed label | Provenance / discriminating obligation |
| --- | --- | --- | --- | --- | --- |
| P01 | A01 | answer | zh-TW,en,ja | frozen_fresh reservation | NEW scope/population bundle, not a code/month swap |
| P02 | A02 | answer | zh-TW,en,ja | frozen_fresh reservation | NEW compatible multi-requirement bundle; false-refusal control |
| P03 | A03 | answer | zh-TW,en,ja | frozen_fresh reservation | NEW role/requirement composition, not E02 paraphrase |
| P04 | A04 | answer | en | frozen_fresh reservation | NEW temporal-binding bundle beyond changing year values |
| P05 | A05 | answer | zh-TW | frozen_fresh reservation | NEW ranking/selection obligations; false-refusal control |
| P06 | A06 | answer | ja | frozen_fresh reservation | NEW whole/subset requirement composition |
| P07 | A02 | answer | en | frozen_fresh reservation | NEW distinct compatible obligation bundle, not P02 rewording |
| P08 | A06 | answer | zh-TW | frozen_fresh reservation | NEW distinct denominator/coverage bundle, not P06 rewording |
| P09 | A01 | answer | ja | exposed_regression | HIST native empty Overview: null/empty vs measured zero |
| P10 | A02 | answer | en | exposed_regression | HIST E01/Q11/Q12: explicitly required observed views; false-refusal control |
| P11 | A03 | answer | zh-TW | exposed_regression | HIST role-swap controls: explicit nonchronological roles |
| P12 | A05 | answer | ja | exposed_regression | HIST Q13/native k/ties: explicit rank-boundary membership |
| P13 | C01 | clarify | zh-TW,en,ja | frozen_fresh reservation | NEW count ambiguity in a distinct otherwise supported bundle; not E05 translation |
| P14 | C02 | clarify | zh-TW,en,ja | frozen_fresh reservation | NEW bounded role ambiguity with all periods supplied |
| P15 | C03 | clarify | en | exposed_regression | HIST E04 wrong-entity risk, adapted supplied-code choice; original name case still deferred |
| P16 | C04 | clarify | zh-TW | exposed_regression | HIST booked/payment/refund meaning contrast |
| P17 | D03 | decline | zh-TW,en,ja | frozen_fresh reservation | NEW multi-month obligation bundle, not an annual-keyword paraphrase |
| P18 | D04 | decline | zh-TW,en,ja | frozen_fresh reservation | NEW composite unsupported requirement, not rearranged old questions |
| P19 | D01 | decline | ja | exposed_regression | HIST E07 profit substitution |
| P20 | D02 | decline | en | exposed_regression | HIST Q06 posting-time cash vs current-confirmed creation-time amount |
| P21 | D05 | decline | zh-TW | exposed_regression | HIST missing-year trap; first-slice policy, not regrading E06 |
| P22 | D06 | decline | ja | exposed_regression | HIST native rejection of center-filtered Compare |
| R01 | A01 | answer | zh-TW,en,ja | exposed_regression | Unchanged E01_overview |
| R02 | A03 | answer | zh-TW,en,ja | exposed_regression | Unchanged E02_compare |
| R03 | A06 | answer | zh-TW,en,ja | exposed_regression | Unchanged E03_share_denominator |

Counts: answer 12 families / 18 inputs, clarify 4 / 8, decline 6 / 10,
P2 anchors 3 / 9. Fresh reservation: 12 / 26; exposed: 13 / 19.
Overall language inputs: **zh-TW 15, en 15, ja 15**. False-refusal controls are
P02/P05/P10 (3 families / 5 inputs), a subset of answerable cases, not extra
denominators. All have explicit supported meanings, not synonym-only changes.

All-three-language selection prioritizes multi-requirement binding, roles,
count ambiguity and dangerous narrowing, plus original anchors. Single-language
slots buy semantic breadth at lower cost; they are not evidence about the other
two languages. Ensure explicit k=1 and k=3 occur somewhere in A05/A06, with k=2
retained by R03; these are bindings/coverage, not three independent discoveries.

Freeze exact order, wording hashes, language pairings, gold, source/DB identities,
budgets and policy before any formal run. Interleave languages/families with a
recorded order, no answer carry-over. Translators preserve ambiguity, negation,
required output and exclusions; do not make one language easier. Human review
must explicitly record uncertain Japanese/other-language equivalence. Unresolved
translation/oracle ambiguity blocks admission, not a post-score exclusion.

## 7. Taxonomy, denominators and thresholds

This proposed P3 taxonomy refines the general dimensions in
[evaluation.md](evaluation.md); it does not rename historical P1/P2 outcomes.
Keep primary outcome, layer results and operational diagnostics separately.
Use these mutually exclusive primary labels with this precedence:

| Priority | Outcome / rule |
| --- | --- |
| 1 | `not_run`: no attempt made. In-progress/possible-in-flight remains an execution status until resolved, not a completed not-run result. |
| 2 | `invalid_output`: observed malformed envelope/content/native action shape; retain whether the error is provider-envelope or model-content. Otherwise `operational_failure` if no usable action because transport/config/source/budget/internal execution failed. |
| 3 | Valid action differs: answer expected + decline -> `false_refusal`; answer or decline expected + clarify -> `false_clarification`; clarify expected + answer -> `missed_clarification`; remaining mismatches -> `wrong_action` (including clarify expected + decline, decline expected + answer). |
| 4 | Expected clarify, correct field and complete accepted choice set -> `correct_clarification`; wrong/irrelevant choices -> `wrong_action`. Expected decline -> `correct_decline` only if it declines the whole request without a substituted answer or false capability promise. |
| 5 | Expected answer + admitted request: `wrong_recipe`, then `wrong_request` for any semantic mismatch. These take precedence over a later native error; preserve that error separately. |
| 6 | Correct request but operational execution failure -> `operational_failure`. Native disclosed optional gaps/partial pack -> `partial` only if all available facts pass applicable coverage, selection and value checks; otherwise retain their semantic error. Missing/incorrect status, slot, grain or membership -> `wrong_coverage`. |
| 7 | `wrong_fact_selection` for incorrect fact roles, references, irrelevant/invented selected facts after intent/coverage pass; `wrong_value` for incorrect units/values/rationals/state after those pass. |
| 8 | `synthesis_error` only in the later synthesis gate. Otherwise all in-scope layers pass -> `complete_correct`. |

A parse/schema failure is not an intentional refusal. Native unavailable data
is not automatically an infrastructure failure. `partial` never hides wrong
intent or incorrect available facts: any such error keeps its corresponding
semantic outcome, with partial status also retained. Layer `not_assessed` and
capability `not_implemented` are metadata, not passes or new exposure labels.
If a mandatory capability is absent before freezing, the panel is not eligible.
If execution nevertheless discovers an absent capability, count a failure with
its evidence/reason; never remove that input.

Current decline has no reason payload. In the first slice D is an oracle-side
unsupported category, not a requirement to invent/read a model explanation.
A genuine accepted decline branch can earn correct_decline without reason text.
If a later contract adds a typed reason, freeze its accepted categories first.

### Exact score rules

For each answerable family f with predeclared language variants L(f), define
`pass(f) = 1` only if **every** required variant is `complete_correct`; otherwise
0. Count a family once, not once per language or retry.

| Report / gate | Numerator | Fixed denominator under the proposal |
| --- | --- | --- |
| Primary fresh answer score | Passing P01-P08 families | 8 fresh answerable families |
| Declared non-anchor answerable score, exposure strata also shown | Passing P01-P12 families | 12 answerable families |
| Fresh branch-control score, not added to answer score | Fully correct P13/P14/P17/P18 families | 4; all mandatory |
| All branch-control score | Fully correct P13-P22 families | 10; all mandatory |
| Exposed answer controls | Passing P09-P12 families | 4; all mandatory regression controls |
| Original P2 anchors | Passing R01-R03 families | 3; all mandatory regression controls, excluded from fresh/quality numerator |

Preserve **>=90% complete-correct** on the declared answerable panel and require
the same threshold for the fresh answer stratum; exposed passes cannot mask
fresh failure. This means at least **11/12** non-anchor answer families and
**8/8** fresh answer families because ceil(0.90 * 8)=8. Combined with mandatory
exposed controls the proposal effectively needs 12/12; disclose this small-N
consequence rather than falsely advertise tolerance for one failure. The owner
may choose a different size before freezing; do not lower thresholds after
seeing scores. These are PoC gates, not statistical deployment guarantees.

**Zero known wrong answers presented as checked normal answers** is an additional
veto across all formal/control inputs and the stability panel. A complete native
pack with wrong action, recipe, request, coverage, selected facts or value trips
it even if its kernel checks passed. Record a separate checked-wrong flag; do
not let the primary outcome or a correct number conceal it. Later synthesis
false claims also trip it. Explicit failures/declines are not checked-normal
answers but still fail their applicable denominator.

False refusals, false clarifications, partials, invalid outputs, operational
failures and not-run entries all contribute **zero** to the frozen answer
numerator and remain in the denominator. Correct declines/clarifications never
add to answer quality; they have separate mandatory-control denominators.
All language variants of a mandatory control must take the correct branch and
meet its oracle; matching action text alone does not validate its choices.
An incomplete run cannot pass, even with a favorable assessed-only subtotal.
Report assessed-only diagnostics if useful, explicitly secondary, without
dropping operational/not-run entries from promotion accounting.

Per-input and per-language tables retain every outcome, required coverage,
unassessed layer, usage and attempt. Report family all-variants-correct and
all-variants-agree separately: agreement can mean all are wrong. Different
language mixes preclude a population-level language ranking.

If a gold defect is discovered after running, preserve the original score,
declare the gate unresolved, and issue a reviewed oracle revision/new identity.
Do not retroactively upgrade the run, remove the case, or reuse it as fresh.

## 8. Stability is separate from semantic breadth

Preselect P01 (Overview, zh-TW), P03 (Compare, en), P06 (Breakdown, ja),
P10 (false-refusal control, en), P13 (clarification, zh-TW) and P17 (decline, ja).
Run **three trials per selected input: 18 additional client attempts**, in
three preordered interleaved rounds. These are six existing families, not 18
new families. The first formal calls are not counted as one of these trials.

Same candidate, fixture, prompt/context/schema, model and recorded route policy;
temperature 0, stream false, max_tokens 2048, concurrency 1, client retries 0.
Fresh stateless requests; no previous answer, hidden repair or best-of-three.
Pin policy/version/source identities; a changed candidate/config needs a new
stability disposition, not pooling with the old trials. Disable no server
feature under this design authority. If response cache is enabled, repeated
responses cannot establish generation stability; require separate owner
disposition before the stability run. Upstream retries/attempts remain separately
attested/unknown; deterministic settings do not guarantee deterministic output.

Invariants: action; recipe and full native-semantic signature; clarification
field and accepted semantic choices; decline action (and category only if a
future contract exports one). Equivalent timestamps, fact UUIDs, key order and
approved rendering differences are not flips. No exact prose-match requirement.

For three valid trials per input there are three unordered trial pairs.
Across six inputs the denominator is **18 pairs**. Semantic flip rate is
different valid semantic signatures / comparable valid pairs; report the
comparable count out of 18. Invalid/operational/not-run trials are not invented
semantic flips or agreements; report them and mark stability incomplete.
False-refusal flip counts answer/decline disagreements for answerable inputs;
clarification flip counts disagreements in clarify action/field/choice meaning;
recipe/request instability compares valid answer signatures. Report overlapping
diagnostic counts, not another mutually exclusive taxonomy.

Proposed stability gate: all 18 trials complete with their expected oracle,
18/18 pairs comparable, **zero semantic flips and zero checked-wrong answers**.
All-three-identically-wrong is stable but fails correctness. This is a bounded
stability witness, not a stochastic error-rate estimate. After quality fixes,
these cases are exposed; first-run generalization results remain separate.
Never keep repeating until a stable batch appears.

## 9. Oracles and isolation

Each frozen family must contain evaluator-only fields for provenance/exposure,
requirement list, expected branch, accepted native/choice sets, mandatory facts
and allowed auxiliary roles, units/null/empty policy, coverage/order/ties,
expected values or explicit undefined state, translation review and novelty
rationale. Pin references and hashes, not candidate-derived expected outputs.
The source fixture and case/oracle revisions are immutable once frozen.

N/F oracles are independently authored from reviewed semantics and source
ledger/reference computations, not snapshots of candidate output. Existing P0
SQL and Python ledger were co-authored, so independent algorithm agreement alone
is not independent human oracle acceptance. Review all proposed gold before use.
Prefer the unmodified synthetic fixture; if it cannot distinguish a trap or
support a complete-data answer, use a separately reviewed evaluator-only fixture
revision before candidate/case freeze, never opportunistic live-time mutation.

Deterministic comparison covers exact recipe/version, all request fields after
accepted date canonicalization, exact scope/roles/code/k, metric/population/unit/
grain/time, ordered membership, slot-to-own-fact references and derivation inputs.
Compare fact identities relationally, not opaque UUID equality. Use exact
integers and rationals; no universal float tolerance. Numeric collisions cannot
rescue an incorrect semantic signature or top-k denominator provenance.

Use accepted semantic sets where more than one representation is legitimate.
Clarification compares the required field and all materially necessary choices,
not arbitrary question wording. Human review covers ambiguity, supported
paraphrases and translation equivalence; unresolved disagreement prevents
case admission. Never let a fluent LLM judge override deterministic disagreement.

The evaluated entry receives **only question text plus approved runtime context**
(later, a validated user choice/token for resume). Do not pass expected action,
recipe/request, gold facts, reference SQL, rubric, family/case ID, language label,
exposure label, sibling wording or manifest into model messages. Keep evaluator
records structurally separate from the plain runtime input; do not serialize a
whole case and ask the adapter to ignore private fields. Future offline tooling
must prove that split and reject canary leakage before live eligibility.

No judge model is proposed for the first panel: deterministic grading plus
independent human review suffices. A later LLM judge requires its own authorization
and budget, pinned model/version/prompt/input evidence, recorded disagreement
and human adjudication; never sole authority for exact comparison or gold edits.
Only accepted sanitized proposal/pack/transport evidence may be persisted.
No raw completion, reasoning, provider body, endpoint, secret or arbitrary
exception internals; generated synthetic questions/gold stay evaluator-only.

## 10. Not measured by the first P3 panel

| Scenario class / gap | Disposition and reason |
| --- | --- |
| Bare duplicate/novel names, aliases, free missing-year collection | Deferred P3; supplied-code choice is not name resolution or original E04/E06 completion |
| Broad people/account ambiguity across P1/recipes | Deferred P3 product-entry decision; C01 is deliberately narrower than original E05 |
| Cross-recipe ambiguity or several unresolved fields | Deferred P3; first slice handles one bounded ambiguity, not clarification chains |
| One-turn resume, expired/stale/invalid choices | Deferred P3 gate, necessary before claiming resume |
| Synthesis factuality, omissions, disclosures and style | Deferred P3 gate; first panel returns checked packs/actions, not prose |
| Broad paraphrase robustness and code switching | Deferred P3; three false-refusal controls and selected translations are not distribution coverage |
| Unselected language counterparts and language-specific terminology | Deferred P3; monolingual slots make no trilingual claim |
| False clarification for every unambiguous near-boundary form | Partly measured by answer/decline controls, broader class deferred P3 |
| Unsupported-but-near-supported inputs outside selected D rows | Intentionally unsupported; decline quality unmeasured for targets/causes, other financial/time meanings, missing baseline/k, other dimensions/populations, formulas/conversions |
| Arbitrary formulas, open-ended analytics, arbitrary multi-question decomposition | Intentionally unsupported, not incentive to grow a DSL |
| Catalog completion/absence analysis, arbitrary source details | Not admitted; one bounded drill-down is P4, arbitrary details remain non-goal |
| Operational outage, injected optional gaps, full negative parser matrix | Existing offline P1/P2 controls, not expanded into new semantic model questions |
| PostgreSQL/native types, IANA/DST parity, snapshot/cancel/deadline and thin service entry | P4; SQLite results and SQL transpilation cannot establish these |
| Real/fresh user demand, production data quality, source inconsistency or ambiguity, source confirmation and feedback/replay | P5; synthetic success is not transfer |
| Large schemas, unseen business domains | P5/new domain admission; outside this bounded fixture |
| Adversarial security prompts, authorization penetration testing | Future dedicated security scope; protected existing safeguards are not a new security evaluation |
| High concurrency, latency/SLO certification, deployed constrained-decoding proof | Future operational scope; observed timings/valid JSON are insufficient |
| Long conversations, cross-session memory | Future/non-goal; do not add a workflow engine to satisfy this panel |

Coverage report must list measured categories/subcategories, exposure and language
cells and these gaps even when every scored input passes. Distinguish runtime
absence from an evaluation gap; neither becomes a product pass.

## 11. Five system-review gates

### A. Intent alignment

A01/A03/A04/A05 catch legal wrong code/month/role/k. C01/C04 and D01/D02/D06
catch wrong unit/metric/population/time/filter substitutions. A02/D04 catch
dropped requirements and inappropriate decomposition. A06 catches denominator
and subset/whole confusion. A02/A03/A05 false-refusal controls penalize brittle
wording routes; C01-C04 penalize answering an unresolved interpretation.
Every numeric comparison follows these gates; no legal SQL certificate is an
intent certificate. Unselected D subcategories remain explicit missing evidence.

### B. Architecture consistency

Do not introduce QueryPlan, a relational/formula DSL, per-case or per-language
prompt routes, parser repair, hidden model repair, retry-until-valid, evaluator
hints, generic provider kwargs or semantic operators to satisfy examples.
A category ID may exist only in evaluator records, never dispatch or prompts.
Legitimate pressure is limited to typed action/choice validation, later bounded
resume and later synthesis. Name lookup, broader metric routing and mixed
requests need explicit admission, not a "small fix." A case quota is never
authorization to expand the product.

### C. Missing cases

Section 10 is mandatory in run reports; compare measured behavior classes, not
test counts. First-panel passing still leaves important cross-recipe/entity,
resume, synthesis, paraphrase, language and source/data uncertainties. Stability
adds repeated-measure evidence, not semantic breadth or new fresh families.

### D. Protected strategic assumptions

Any change requires an explicit owner-reviewed design decision, not an incidental
local refactor:

1. Model chooses WHAT.
2. Server owns HOW, calculation and checking.
3. Structured output constrains format, not semantic correctness; requesting it does not prove backend enforcement.
4. Strict JSON and native validation remain necessary.
5. Checked facts do not prove user-intent alignment or source truth.
6. Refusal cannot inflate quality score.
7. Exposed regressions are not fresh evidence.
8. Synthetic success is not source confirmation.
9. One serving backend is not portability evidence.
10. Evaluator gold/reference SQL never enters runtime/model context.
11. Clarification is explicit typed behavior, not hidden repair.
12. No silent narrowing of supported product scope, including the separate P1 route.

### E. Mandatory system-level impact review for future P3 PRs

The [PR template](../.github/pull_request_template.md) requires this review.
For each row record baseline and candidate identities, measured delta or
**unknown**, supporting evidence, and blocker/optional disposition. Absence of
measurement is not zero cost. No need to rerun unrelated suites for a docs-only PR.

| Surface | Required evidence / decision |
| --- | --- |
| P1 regressions | Original 107 P0/P1.1 protections plus affected P1 adapter/wire/runner suites; no implicit new recipe-to-P1 route |
| P2 regressions | Native semantics, required/optional behavior, strict parser, structured output, stop/publication and fixed-family protections |
| Security/privacy | Approved data, typed bounds, no new payload/exception logging, code/SQL bypass, secret or endpoint exposure |
| Evaluator leakage | Import/context/input separation, canary checks; gold/acceptance reviewer independent of repair |
| Prompt/context size | Exact before/after bytes/hashes, unchanged caps or separately approved change |
| Token and live-attempt cost | All actual/possible attempts, first failures, usage and unknowns; no free hidden probes/retries |
| Latency | Actual comparable timing with boundary definition; no inference from test counts |
| Configuration and maintenance | Files/lines, semantic/operator/repair branches, config complexity, dependencies, human effort and candidate attempts |
| P4 compatibility | No SQLite-specific product semantics that silently preclude later PG/native-type/lifecycle parity |
| P5 compatibility | Synthetic assumptions, private-source constraints and original-source confirmation still needed |
| Product promise | Any widening/narrowing, displaced behavior or changed protected assumption needs explicit scope approval |

## 12. Cost, complexity and stop conditions

No prices are known; quote token volumes and relative work, not invented dollars.
P2 #36 observed 16,482 prompt + 1,074 completion = 17,556 tokens for nine inputs,
or 1,831.33 + 119.33 = 1,950.67 per input on average. Its elapsed sample was
35.145697 seconds; this is not a P3 timing guarantee.

| Proposed phase | Families | Inputs / maximum client attempts | P2-like prompt / completion / total estimate |
| --- | --- | --- | --- |
| First formal panel | 25 slots (12 fresh reserved, 13 exposed) | 45 | 82,410 / 5,370 / 87,780 |
| Separate stability | 6 reused families, three trials each | 18 | 32,964 / 2,148 / 35,112 |
| Combined proposed budget | Still at most 25 distinct families | 63 | 115,374 / 7,518 / 122,892 |

Combined work is about **7 times** P2 #36's input count and P2-like token total,
not a pricing estimate. New clarification schema/context may increase tokens.
For planning only, allow 25% above the P2-like prompt estimate plus 2,048
completion tokens per attempt: roughly 273,242 total tokens for 63 attempts.
This is not a hard token guarantee or an accepted raised cap; re-estimate using
the final offline request identities before authorization. Actual prompt usage
is unknown until observed; record missing usage as unknown, not zero.

Propose unchanged 60-second per-call maximum, with separately reviewed panel
budgets of 2,820 seconds for 45 calls and 1,200 seconds for 18 calls (120 seconds
each for non-call work within final-publication admission). These are ceilings,
not expected latency/SLOs; existing P2's 720-second limit is not silently reused
for a larger panel. The future P3 runner must pin its own policy.

One invocation per separately authorized panel, concurrency 1, client retries 0.
Reuse P2's reviewed network/timeout/immediate safety-stop distinctions and
non-complete-until-publication evidence design; do not rewrite the trusted runner
merely to change case counts. Preserve unrun entries when stopped; no recovery
resend, top-up or "finish the remaining cases" under consumed authority.
Gateway retries/fallback/cache are separately attested; upstream inference work
may exceed client attempts and remains unknown without evidence. No health,
warm-up, discovery, judge or synthesis calls are included in the 63-call proposal.

Estimated human effort: 4-8 hours independent family/oracle/translation admission,
2-4 hours first-result review and 1-2 hours stability/disagreement review.
These are planning estimates, not measured effort or RSI evidence; record actual
active review effort, elapsed time, interventions and failed attempts later.

| Area | Forecast, not authorization |
| --- | --- |
| Necessary product capability before first panel | One bounded typed clarification alternative, validation and safe rendering; versioned shared contract change, no new recipe/operator |
| Later P3 product gates | One-turn binding/revalidation and evidence-linked synthesis, each separately designed/reviewed; no conversation engine |
| Evaluation-only work | Distinct question/gold records, provenance/novelty audit, accepted semantic sets, layer grades, fixed denominator summaries and pinning |
| Runner work | Adapt/reuse accepted neutral safety/evidence helpers; preserve P1/P2 identities and terminal-publication regressions, no second runtime execution path |
| Hazards, not admitted | Name resolver creep, dynamic metric routing, state machine, planner retries, growing DSL/config, prompt exceptions, evaluator-derived hints |

Before each later repair state hypothesis, source/oracle identity, cost bound
and stop condition. Default to at most two candidate fixes per investigation,
then a scope/design decision under the roadmap. Preserve failures. A changed
grader/oracle needs independent review and cannot establish product improvement
by itself. Process improvements remain hypotheses until comparable later work
shows transfer; extra test counts or written lessons do not establish RSI.

## 13. Recommended independently reviewable sequence

1. **P3.0:** owner reviews this contract, especially conservative incomplete-input
   policy, conditional novelty quota, effective small-N threshold, no initial
   resume/synthesis, and protected assumptions. No runtime changes.
2. **P3.1:** separately admit and implement minimal action/clarification contract,
   version identities, strict validation and fake-transport regressions. Keep
   existing native recipes/P1 path; use design-seen development cases only.
3. **P3.2:** offline evaluator records/grader/reporting and isolation checks,
   frozen denominators, budgets and failure/publication witnesses. No live calls.
4. **Candidate and case freeze:** owner accepts a candidate; independent authors
   freeze/review actual fresh families and controls. Audit provenance/novelty,
   translations, oracles and complete-data eligibility. If quota fails, revise
   this contract before running; no padding or candidate tuning on fresh cases.
5. **First formal quality panel:** prepare accepted source/DB/manifest and exact
   command, request separate local owner authorization, execute once and preserve
   all outcomes. No stability/live authority is implied by the quality result.
6. **Failure analysis/minimal fixes:** keep first-run evidence; do not relabel
   repair cases fresh. Explicitly decide fix/scope/stop, review impacts and gates.
7. **Stability gate:** separately freeze and authorize the 18-call panel on one
   accepted candidate. A post-fix pass is exposed stability evidence, not an
   upgraded first-run generalization result.
8. **Later bounded P3 gates:** one-turn resume and separately graded synthesis,
   each with accepted contracts/oracles and its own authorization/budget.
9. **P3 exit review:** owner considers all promised P3 layers, quality, mandatory
   controls, stability, costs and remaining gaps. Passing the first panel alone
   is not full P3 completion; do not pull PG/service or real-data work forward.

## 14. P3.0 verification and acceptance boundary

This change contains documentation/review-template text only: no new case text,
gold values, executable evaluator, dependency, prompt, schema or product code.
Validate Markdown structure/local links, unique category/slot IDs, ancestry
references, panel arithmetic/language counts, threshold rounding, repeat costs
and the allowed changed-file set. Verify runtime/evaluator/fixture tree identity
against the accepted baseline and preserve prior artifacts. Do not rerun model
traffic or a full runtime suite to validate a design document.

Document review is not owner acceptance, case freeze or live validation.
Current-task live attempts: **0**. Stop at design delivery.
