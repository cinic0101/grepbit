# Temporal construction and semantic controls

2026-09-13. Owner's "ok" approves the preceding recommendation: prioritize
temporal construction, then bounded baseline/neutral/semantic comparisons.
Root owns private research helpers, documentation and evidence. Baseline
`69f6b57`; existing read-only PostgreSQL, Gemma and local-commit authority,
no push. No production, overlay-policy, gate or acceptance-contract change.

## A: reuse an existing deterministic year conversion

The current planner adapter already converts a four-digit calendar-year EQ
filter on a date column into that year's half-open range, preserving grain.
Experiment with requesting that existing form, not a new wire or new rule.
Three arms: unchanged v15, a neutral extra instruction, and a calendar-year
literal instruction. Distinct research arm revisions; production v15 unchanged.
The targeted instruction contains no case-specific year or datasource identifier.
Eight fixed POS-payroll questions: original year/quarter, English variant,
explicit paid-date year, alternate year, explicit attribution-date months,
last-year quarters, one calendar month, and a cross-year explicit range.
Two fixed original/English repeats after the panel. 30 scheduled executions.
Allow only predeclared full-value/disclosure alternatives, not any value match.
Capture raw-response temporal facts BEFORE adapter normalization, then initial
domain and final-plan facts, as allowlisted kinds/hashes/comparisons only.
This localizes generation versus normalization without retaining raw output.

## B: explicit controls plus existing difficult questions

30 cases: the frozen 24-case challenge-v2 plus four existing component-exclusion
questions (payroll Chinese/English, goods English, service English), existing
missing-lease-population and English work-log/unique-ticket regressions.
Run the unchanged baseline first. If every case is accepted against frozen
rules, stop B at the ceiling; do not run interventions just to obtain a win.
Otherwise finish neutral and targeted schema-comment arms for all 30, then
repeat the four original difficult cases (payroll-English, goods-English,
missing lease, English units) under all three arms. Maximum 102 executions.
Metadata is in-memory only, specifies field/component/support meaning, and
cannot invent a lease field or supply a lexical exception. No gate bypass.
Name policies, index, data, questions and independent SQL stay paired.

## Execution boundaries and screen

Maximum 132 question executions / 396 actual transport attempts; serial
Gemma4 31B at the existing gateway, original opaque key, T=0/thinking off,
one validation repair, 20-second timeout. Each owned client closes per call.
Only authored/consented fixture questions/schema and permitted public hints
go outbound; never SQL, rows, raw private values or credentials. PostgreSQL
uses original DSN environment names and `grepbit_ro` on POS-test, IoT and
service fixtures. Synthetic instances use in-memory DuckDB. No real-POS data,
new database or persistent mutation is needed.

Freeze all contexts, independent SQL/allowed plans and per-arm payload hashes
before the first model call. Preserve legacy grades; unknown interpretations
remain unassessed. Separate raw proposal, served answer, unnecessary refusal,
required refusal, correct-but-blocked plan and value disagreement. Validate
synthetic plans over three distinguishing instances. Stop on source/context/
oracle drift, budget exhaustion, unsafe capture or two transport errors.
Fresh `.artifacts/temporal-semantic-controls-20260913/`; no overwrites.

For A, require the targeted original-year rescue to recur and no temporal
control regression; a neutral tie or absent baseline error is inconclusive.
For B, require incremental gains beyond neutral on more than one semantic
family, with required refusals retained and no new wrong answers. This is a
bounded authored research screen, not a release criterion or generalization
claim. Stop without promotion if the screen fails. Any later production
prompt promotion requires affected-set regression; a new wire, refusal rule
or scoring contract requires its own ruler checkpoint.
