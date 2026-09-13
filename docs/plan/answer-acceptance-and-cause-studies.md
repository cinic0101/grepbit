# Answer acceptance and independent cause studies

2026-09-13. Owner-approved principles; implementation checkpoint pending.
Authority and current execution are in `active-work.md`. The owner approved
"合理解讀＋實際口徑揭露＋相關額外欄", independent overlay/grounding/prompt/gate
experiments, and subsequently applying the same principle to ambiguous payroll
time roles. Japanese absence is low priority. No human-correction cards.

## Acceptance contract ruler

This is a versioned **new evaluation policy**, not permission to rewrite the
292-case report, broaden `verified`, or globally drop unmatched output columns.
The existing runner's `correct` remains its legacy reference agreement.
Future evaluation reports must keep that measure beside the new adjudication
with explicit policy version, predeclared interpretations and evidence IDs.
Do not carry old verdicts into a changed policy by question/SQL/row count alone.

An answer is eligible only when all of these hold:

1. Its interpretation is permitted by the question and the applicable
   reviewed definitions. Evaluation alternatives are fixed before candidate
   results are inspected, not invented from whichever answer the model gave.
2. Explicit instructions constrain the alternatives: “only engineers, not
   senior engineers” cannot receive the broad population. “By payment date”
   cannot silently become accounting-period time. Conflicting reviewed
   definitions must be exposed, not overridden silently in either direction.
3. The effective computation is faithfully disclosed: selected population,
   measure/unit, DISTINCT/NULL basis where material, effective time column,
   timezone/window endpoints, grouping and default exclusions. This uses the
   compiled/expanded plan, not an independent model-written explanation or
   only the pre-normalization proposal. Generic uncertainty text is insufficient.
4. Required outputs agree with the appropriate independent value oracle,
   preserving row identity/multiplicity, grouping, necessary order/LIMIT,
   NULLs, units and existing precision. Missing evidence is unassessed,
   not correct. Matching a different population by numerical coincidence
   does not establish the requested meaning.
5. Additional outputs are allowed only when predeclared as relevant to this
   question family, independently value-checked and labeled as supplementary.
   They must not alter required rows, aggregation, window or threshold scope.
   Unknown relevance is unassessed; incorrect or unrelated extras fail.
   “Ignore every non-reference column” is explicitly rejected.
6. Disclosure cannot rescue a contradicted request, unsupported concept,
   invented binding, wrong number, privacy violation or unsafe SQL.
   Query authorization and personal-value display policies stay unchanged.

These are scoring conditions, not a complete automatic language oracle.
Researchers supply the approved interpretation sets; runtime model selection
remains fallible. No model self-certification and no mandatory user repair turn.
Use existing answer interpretation/assumptions for delivery if sufficient;
do not add another card, standalone explanation framework or API field here.

### Owner decisions and boundary examples

| Family | Eligible with truthful disclosure | Still fails / remains unresolved |
|---|---|---|
| Engineers' base salary | The engineer plus senior-engineer category is allowed for the unspecified request; name the actual included categories and salary basis. | Ignoring an explicit exclusion, adding non-engineering jobs, or claiming broader coverage than the filter. |
| Date-only between A and B | Include both calendar dates in business timezone, compiled as `[A 00:00, day-after-B 00:00)`. | Ignoring an explicit exclusive endpoint or treating a precise end timestamp as an entire day. Internal range semantics remain half-open. |
| Monthly comparison | Required month values plus correctly calculated, relevant growth. | Wrong growth, unrelated metric, extra grouping changing rows, missing periods filled as zero. |
| Quarterly payroll | Without a conflicting definition/instruction, either actual-payment or salary-attribution quarters may answer, with that basis and base/bonus scope stated. | Calling payment time accounting time; assuming payments always belong to the previous month; hiding a metric time override. |
| Leased-device fee | Only if an applicable definition actually binds the lease population to available data. | Summing all device fees because a lease predicate is unavailable; disclosure does not make this answer acceptable. |
| Partial store name | A policy-eligible uniquely resolved stored entity, with the substitution disclosed. | Guessing among tied names, applying LIKE and summing several stores without evidence, indexing personal columns implicitly. |

## Ruler evidence and required checkpoint

`tests/contract/t0/test_answer_acceptance_ruler.py` contains a hand-calculated
100-to-200 monthly comparison with NULL then 100% growth and unchanged core
rows. The legacy matcher rejects it. The strict xfail is a **capability-gap
exhibit**, not a specification that the legacy value-only API should accept
extras without relevance/disclosure evidence. Run with `--runxfail` to see the
intended failed assertion. Its negative controls preserve wrong-growth,
wrong-core-value and missing-row rejection. Other passing probes distinguish
literal hints/resolution and raw/metric time-column behavior.

The broader acceptance rules above remain a written specification; these
component probes do not implement or fully verify disclosure grading. Before
new grading or runtime disclosure implementation, stop for explicit follow-up
at this checkpoint. Then add positive/negative rule fixtures for each row,
including correct values with a false/missing disclosure and coincidental
value matches; implement only the accepted bounded scoring surface.

## Next execution order

1. **Existing-contract diagnosis (completed this slice).** Read existing
   paired reports, test literal-index behavior, verify schema comments reach
   the payload, and compare fixed raw/metric payroll plans. No model calls.
   Findings: `../research/lexical-policy-and-defaults-01.md`.
2. **Acceptance/disclosure evaluation.** Following checkpoint approval,
   implement the separate policy scoring, preserving historical labels. Use
   hand-computed small instances with deliberate differences between titles,
   payment/period dates and range endpoints. Do not count additional accepted
   interpretations as a model improvement.
3. **Grounding study.** Freeze 6 authored Chinese/English entity requests:
   exact, partial, unique, tied, missing and explicitly excluded entity.
   Compare sampling-zero with no index versus a minimal public-name-only
   policy index, two repeats = 24 planning calls. Do not load unrelated
   metrics/segments in the index arm. Record candidate hints separately from
   post-plan resolution, candidate recall, false substitutions and refusals.
   Existing full POS overlay does not opt in store grounding.
4. **Payroll metadata study.** Freeze 6 questions: unspecified quarters,
   explicit attribution, explicit payment, delayed payment, salary components,
   and a non-payroll time-role control. Three arms, two repeats = 36 calls:
   current metadata; clarified factual column comments in an in-memory schema;
   existing reviewed metric supplied through a minimal overlay. No live DB
   COMMENT or business-default rewrite. Separate availability, selected raw
   column/metric, compiler override, disclosed basis and value agreement.
   Loading a metric is not forcing the model to select it.
5. **Lexical-gate study, offline first.** Reuse the existing labeled
   minimal-pair/mutant corpus; no new same-model-verifier arm or repeat of the
   failed metric-factor study. Freeze 12 English/Chinese utterances across
   imperative return, genuine returns, mixed uses, negation scope, quoted
   labels and predicate-without-keyword families. Replay known correct and
   known wrong plans through the existing gate versus a shadow no-lexical-
   veto control. Keep compiler/policy/literal checks identical. This control
   measures the opportunity/risk of removing lexical authority; it is **not**
   a promotable safety solution. Report false blocks avoided and omissions
   newly exposed, split by language/family. Any proposed replacement rule
   needs a specified evidence source and its own gate-contract ruler first.
6. **Prompt study only if justified.** If payroll metadata does not explain
   selection or balanced intent examples offer a genuinely untested hypothesis,
   propose one paired revision with explicit controls before more calls. No
   broad prompt rewrite to fix one question; no Japanese study in this budget.

The 60 calls above are a proposed fresh research ceiling (24 + 36 completed
planning requests), with at most 180 transport attempts including existing
repair/retry, not authorization to consume old budgets. Destination remains
the owner-authorized private Gemma4 31B gateway; fixture questions and
policy-eligible metadata/hints only, never SQL/results/credentials. Before
execution freeze exact cases, payload identities and source, and verify no
other regression uses the endpoint. Serial calls; alternate arm order in the
second repeat, record it, stop at two consecutive transport failures or source
drift. These controls reduce but do not eliminate cross-session confounding.

No production prompt change without an individual revision and affected-set
regression. Advancement requires no newly exposed known wrong answer, preserved
deterministic safeguards and a repeatable benefit in the relevant family;
report coverage and wrong-answer/false-refusal counts separately. Small authored
sets are mechanism checks, never a real-user generalization success rate.

## Deferred, with resumption criteria

- Japanese absence: preserve case, missing-rule observation and supported
  fixed-plan witness; revisit after higher-priority changes or a broader
  multilingual regression reveals additional related failures.
- Member ratio: no more repeated calls to obtain a failure. At the next
  natural recurrence retain safe stage fingerprints and fixed error codes,
  with input/model identity. Do not persist raw PII-bearing model output.
- A replacement intent classifier, new ontology, sense dictionary, Best-of-N
  selector or human-correction product is not part of this plan.
