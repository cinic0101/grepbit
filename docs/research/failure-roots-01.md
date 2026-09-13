# Nine regression failures: causal diagnosis, not nine model mistakes

2026-09-13 (Taipei). Baseline `acd4ad3`, tracked source `e01de711` unchanged.
The owner requested root causes for the author five, features two and
multilingual-challenge two failures in `evidence-reuse-live-01.md`, and whether
the causes admit general solutions. This is diagnosis only, not a repair,
new prompt, new verdict, or a human-correction/card proposal.

## Bottom line

These are **not one metric-selection failure class**. Four numerical
mismatches have isolated plan-level explanations; some expose underspecified
reference semantics rather than an unambiguously wrong reading. One correct
plan is blocked by a lexical guard, one partial entity name cannot be grounded,
one required population is silently omitted, and one supported capability is
declined with missing language-triggered guidance. The original member-ratio
refusal remains unattributed.

Seven non-null original plan identities were recovered exactly. Two fixed-
setting repeats reproduce five of them; bounded reconstruction recovers the
two features plans by exact original SHA equality. This identifies the final
plans, not the original raw model output or the sequence of repairs. The
Japanese refusal has no plan: equality of the hash of null is **not** evidence
that the original refusal rationale was the same.

## Per-case findings

| Cohort / case | Observed cause and controlled evidence | Interpretation / remaining uncertainty |
|---|---|---|
| Author: `member_ratio_gap` | The original run returned unsupported after a validation repair. Both new runs produce a reference-matched filtered-count / total-count ratio, with a different plan hash. A bounded search of 189 candidate plans did not recover the original hash. | The intended computation is supported. Original rejection reason/plan remains unknown; do not call this fixed, blame the compiler, or infer a specific ratio error from history. |
| Author: `en_engineers_avg_base_salary` | Exact original plan averages base salary for both the engineer and senior-engineer job titles. Both are offered samples. Reference SQL includes only the engineer title. Keeping the original plan and narrowing only that filter makes the PostgreSQL result match. | Population extension, not AVG failure or an invented literal. “Engineers” can reasonably include senior engineers; the reference's narrower category is not explicit in the question. A reviewed category definition is missing from this case's context. |
| Author: `alerts_trend_daily_july_first_week` | Exact original plan treats July 8 as included, using July 9 as `end_exclusive`; reference excludes July 8. Changing only that endpoint makes the result match. | The actual question says “Daily number of alerts between 2026-07-01 and 2026-07-08”, **not “first week”**. This is an endpoint-convention mismatch, not demonstrated bad week arithmetic. The previous report's first-week shorthand was misleading and is corrected. |
| Author: `store_partial_name_jan` | Exact original plan is refused with `filter_value_not_found`. Its chosen store-name literal occurs in the question but differs from the stored value in the reference. This is the no-sampling run, without an overlay or value index. | Missing entity grounding. The literal checker is correctly rejecting a nonexistent equality value. Candidate/alias evidence is needed; removing the check would turn a refusal into a misleading empty/zero answer. |
| Author: `cov_leased_fee` | Exact original plan simply sums `devices.monthly_fee`, with no population filter or reviewed metric. The fixture has connectivity status and subscription fees, but no lease/ownership predicate. | Genuine lost scope: “leased devices” became all devices. The available fee column does not establish the requested population. A missing-definition refusal is appropriate; no lease keyword exception is added. |
| Features: `ft_compare_last_two_months` | Both fresh runs match the reference, but the exactly reconstructed original plan has an additional growth output. Replaying it yields three columns and fails; deleting only growth gives the reference-matched two columns. | Extra output intent, not a demonstrated wrong revenue value. “Comparison” does not uniquely specify whether a rate should also be returned. The existing comparator rejects extra measures. Do not restore a multilingual keyword-based growth deletion rule. |
| Features: `ft_quarterly_payroll` | The reconstructed original uses `paid_at`; the reference uses `period_start`. Changing only the time column makes the result match. Its original full-year endpoint already agrees with the reference. New repeats fail with another plan hash; date-versus-datetime normalization alone does not help. | Payment-date versus accounting-period semantics. The original failure is not a date serialization issue or a wrong year endpoint. “Salary by quarter” needs a reviewed time-role convention; raw column validity does not select it. |
| Challenge: `svc_absent_feb_ja` | Both runs return semantic_gap without a plan. A handwritten three-hop `without` plan with a child February window executes and matches the reference. Rule 8 is included for the corresponding Chinese/English questions but absent for Japanese. | Capability is present in the algebra. Missing language-triggered guidance is a concrete input asymmetry and plausible contributor, **not yet a causally proven fix**. An earlier diagnostic recorded the model's unsupported-anti-join explanation; this run stores only a rationale hash and cannot assert the same explanation. |
| Challenge: `svc_units_en` | Exact original plan correctly requests COUNT of logs and COUNT DISTINCT of tickets. `Return both totals.` triggers `returns/return` and `concept_not_mapped`. Removing just that imperative clears the deterministic gate; executing the unchanged original plan directly matches the reference. | Confirmed lexical false positive. The planner got this one right; the guard confused an output instruction with a business concept. This is not a rows-versus-entities selection mistake in this run. |

All four original numerical mismatches reproduce on the current read-only
database and become reference matches after one isolated change. This proves
the **proximate source of the reference disagreement on these data**, not why
the model chose that reading, that the reference is the sole valid intent, or
that automatic selection of the changed plan will generalize.

## Shared causes and generalization opportunities

### 1. Valid identifiers do not resolve semantic roles

Engineer categories, calendar endpoints, payroll time roles and the requested
outputs in a comparison all require choices beyond syntactic validity. A
single “planner picked the wrong metric” description hides these differences.
These cases have no reviewed metric overlay supplying the relevant defaults;
they do not establish that a present, correctly scoped metric definition was
ignored. The service overlay has no metric definitions either.

The promising reusable surface is explicit, reviewed semantics for population,
time role/boundaries and output meaning, followed by deterministic checking of
the selected contract. It can reduce ambiguity, but selecting the right
definition from a question remains probabilistic; a catalog does not prove
that choice. Changing an existing default or reference expectation needs an
owner decision and the relevant ruler checkpoint, not a silent score repair.

### 2. Language-triggered policy both overfires and underexposes capability

The service English guard overfires on an imperative; the Japanese planner
does not receive an existing capability rule because none of its trigger
phrases match. Both make behavior depend on surface wording. They are
different paths: one is a post-plan guard with a demonstrated false positive,
the other prompt assembly with an untested causal link to model decline.

A general experiment should separate capability visibility from keyword
presence and test semantic guards with positive concepts, negations and
instructional uses across languages. Do not replace deterministic algebra
checks with a same-model verdict, and do not interpret removal of the lexical
guard as evidence of improved understanding. No gate or prompt changed here.

### 3. Missing evidence is not an invitation to invent a scope

The store case lacks a usable mapping to a stored entity. The leased-fee case
lacks the data/definition needed to identify a population. These need
different responses: policy-approved candidate grounding can resolve the
first; the second must not manufacture a filter or silently drop it.

Testing explicit scope support/absence is reusable across sources. However,
extracting every required scope from unrestricted natural language remains
the difficult intent problem. A new lease word in a denylist would patch a
case, not solve that problem. Overlay absence declarations can communicate
known limits, but their selection is not an independent intent oracle.

### 4. Variability remains; it is not the explanation for everything

The member-ratio and comparison questions now match twice. For comparison,
exact hash recovery establishes the original added-growth cause; for member
ratio it does not. Two successful repeats do not erase either original
failure. No experiment here isolates endpoint load, batch composition or
model build as the cause of the cross-run change.

## Recommended next experiment, not implemented

1. First make a semantic-policy decision for category membership, date
   endpoints, salary time role and comparison outputs. Preserve original
   scores while separately recording defensible alternative readings. This
   avoids optimizing against an unstated gold convention.
2. Run one bounded capability-exposure ablation on the Japanese absence
   family and unrelated controls, with identical settings except existing
   rule visibility. Include multiple absence phrasings and languages; adding
   a Japanese trigger alone is not the generalization target.
3. Independently measure a lexical-guard alternative with genuine business
   returns, imperative return, negation and missing-scope controls. Report
   false refusals **and** newly exposed wrong answers, not just pass count.
4. Test policy-approved entity candidates on partial names and ambiguous
   names, and explicit unsupported scopes on non-POS data. Keep these apart
   from the guard ablation so gains and regressions can be attributed.
5. Retain safe diagnostic reason/structure evidence on the next member-ratio
   failure. Do not spend additional repeated calls now just to obtain a
   preferred outcome or add a repair without the original cause.

These experiments can test reusable mechanisms; this nine-case diagnosis is
not new holdout evidence and cannot supply a generalization success rate.
None depends on human correction cards or a model certifying its own intent.

## Execution, authority and evidence

Scope is recorded in `../plan/active-work.md`: nine existing fixture questions,
two repeats, serial, max54 attempts including repair/retry, the already
authorized Gemma4 31B gateway. This new diagnostic used **18 attempts, all
successful**, no transport retry or validation-repair turn. Configuration:
`plan-classify-json-v15`, temperature 0, thinking off, JSON object, 20-second
timeout, one permitted repair, planner minimum 768 tokens. No additional
prompt experiment or model call occurred during the counterfactual checks.

Only the existing POS-test, IoT and fictional-service PostgreSQL databases
were accessed by `grepbit_ro`; no real POS, admin credential, DB write or
grant. Credentials were read opaquely from the original location; model
requests contained the authorized questions/schema/eligible hints, never
SQL, results or credentials. Counterfactual connections enforced read-only
transactions and a ten-second statement timeout, with sampling disabled.

The 11 fixed-plan PostgreSQL executions include ten unique plans; the payroll
“time column plus full year” check duplicates the time-column-only plan
because its original year window was already correct. Do not count that as
another independent causal test. There were also matching reference queries
and introspection/role checks. Two script setup failures (import path and
case-path type) occurred before DB comparisons; both were corrected and are
not model failures, ruler evidence or favorable reruns.

Fresh live diagnostics retain schema-bound plan structure, literal/alias
hashes, fixed reason codes and reference-match flags, not SQL, raw provider
text, bindings or result rows. Bounded reconstruction used historic plans
and accepted candidates **only** on exact canonical plan SHA equality. Seven
original plan identities were recovered; the member plan was not. The
Japanese null plan cannot be reconstructed as an intent or rationale.

Evidence manifest: `evidence/failure-roots-01.json`. Detailed reports and
research-only drivers: `.artifacts/failure-roots-20260913/` (`live/`,
`counterfactual.json`, `reconstruction-02.json`). Ten private diagnostic and
evidence-audit tests pass; five existing hand-counted service rulers pass.
Tracked source remains
`sha256:e01de711a9ebb6e0da5b67fe9b6b2773184f64bc5f6abf307b6ee71c53943361`.
Reuse the source-identical previous static/offline gate of 1,646 passing
tests; do not call it a new full-suite run. DB contents are not snapshot-
locked across sessions, and the configured model name is not an immutable
provider-build fingerprint.

Production, prompt, fixtures, thresholds and all original 292-case scores
are unchanged. Only the report, evidence manifest, work record and a factual
date-question description correction are committed. No push.
