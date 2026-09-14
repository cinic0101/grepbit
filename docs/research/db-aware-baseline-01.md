# Database-aware baseline: answers succeed; one lexical gate blocks a correct plan

2026-09-14, baseline `689baca`, unchanged runtime digest
`sha256:e082cb9bfcaffb40f96f2f533d635cf085c9222731eb8330a76d89a9b16880ad`.
Protocol: [frozen baseline](../plan/db-aware-baseline.md). Questions and independently
authored gold/foil preparation: [bank](db-aware-challenge-01.md).

## Result

All 24 authored questions completed through `evals/spike_tier0.py` / `ask()`:
14 service and 10 IoT. Actual Gemma calls **25**, including one validation repair
on i06; zero transport failures. Prompt `plan-classify-json-v15`, temperature 0,
thinking off, initial timeout 20 seconds, actual token cap 768, serial execution.
Request latency p50 approximately **2.58 seconds**. No second model, new prompt,
gate/overlay change or success-seeking retry.

| Evidence layer | Service (14) | IoT (10) | Total |
|---|---:|---:|---:|
| Answered, frozen recipe/disclosure/value accepted | 9 | 6 | 15 |
| Answered, frozen rule says unlisted interpretation | 3 | 1 | 4 |
| Necessary refusal action/status | 2 | 2 | 4 |
| Unnecessary clarification | 0 | 1 | 1 |
| Operational failure | 0 | 0 | 0 |

Post-hoc review confirms the four unlisted plans are equivalent computations,
so the adjudicated outcome is **19 correct answers, zero confirmed wrong answers,
four necessary refusals and one unnecessary clarification**. This does not replace
the frozen score or constitute a new general-purpose equivalence checker.

All 19 answers match the full independent result values; none relies on dropping
extra columns. Effective-computation disclosure is present. The four safe refusal
statuses are s13 `semantic_gap`, s14 `semantic_gap`, i09 `semantic_gap`, i10
`unsupported`. **s14 is a status taxonomy mismatch**: timestamp columns exist but
their per-row subtraction/average is outside the algebra; the authored preferred
status is `unsupported` (also accepts `clarify`), not `semantic_gap`. Its refusal
action is appropriate, but the broad refusal-only checker does not prove its
explanation identifies the correct capability boundary. Raw refusal prose was
not retained, so do not infer more from the status.

Legacy runner pass: **22/24** (13 service, 9 IoT), failing s14's status and i01's
refusal. Frozen open-recipe acceptance: 15 answered matches plus four accepted
refusal statuses, four unassessed answers, one unassessed non-answer. Those are
distinct metrics, not competing estimates of product accuracy.

After the labelled semantic review, answer coverage and effective-answer yield
are both **19/24 (79.2%)**; answerable-case completion is **19/20 (95%)**. Observed
known wrong answers are **0/19**. That is a small authored-panel count, not a
population risk bound. Necessary refusals must not inflate effective-answer yield.

## Four equivalent plans, not four model errors

- s01: `COUNT(minutes)` versus `COUNT(*) FILTER (WHERE minutes IS NOT NULL)`.
- s11: the same identity for the ratio numerator's `closed_at`; denominator
  remains all tickets, including those with unknown creation time.
- s08 / i05: a sole, ungrouped `AVG(column)` versus the same aggregate with
  `WHERE column IS NOT NULL`. This equivalence is not generally a license to
  remove that filter from a grouped or multi-measure plan.

The original recorded plans were recompiled and matched their recorded full
outputs and independent SQL. Separately, four PostgreSQL CTE instances (mixed
NULL/zero/positive values, all NULL, empty, all zero) confirm three identities each:
nullable count, average, and nullable-count/all-row-count ratio. Nine post-hoc
tests include controls forbidding the average rewrite for different filter columns,
zero exclusion, grouping and additional measures. No model calls in this review.

These are narrow SQL algebra arguments plus regression witnesses. Production
normalization and the evaluator were not widened after observing these answers.

## i01: same plan, gate on versus off

Question: "For alerts raised in July 2026, return the number of alert records and
the number of distinct devices that raised them."

Gemma selected `alerts`, row count and distinct `device_id`, using the correct
July scope on `raised_at`. The runtime returned `clarify / concept_not_mapped`.
The sanitized plan retained a hash for its month string; the review reconstructed
only the question's public `2026-07` and verified that hash before replay.

Replaying **the same recorded plan**, without Gemma:

- Existing concepts enabled: `clarify`, unmapped concept `returns`.
- Only concept list empty, all other checks unchanged: `answered`; the frozen
  gold recipe, full values and disclosure checker accept it.

The global vocabulary treated the imperative **return** as a returns-business
obligation, even on an alerts datasource. This localizes the refusal to the gate,
not planner selection, schema linking, grounding, time parsing or SQL compilation.
It extends the observed false-positive surface beyond POS; the word/failure family
is already known, so it is not a new generalization result.

## Interpretation and next step

This explicit question panel shows Gemma can express the tested nullable counts,
population/component distinction, NULL dates, date roles, denominator scope,
multi-hop absence, fan-out avoidance and post-share threshold correctly. Its
wording often explicitly disambiguates intent and names columns. It does **not**
establish that short natural questions, unseen users or the earlier failures are
fixed, and does not support a causal attribution to endpoint batching.

Do not add a special-case `return` exception, retune this already successful panel
or blanket-disable the gate. Add i01 to the fixed false-refusal controls alongside
the previously observed **wrong plans released by gate removal**. A replacement
must recover these correct answers without releasing those wrong answers; the
existing bounded studies remain negative evidence, not experiments to rebrand.
Any relaxation still needs a separately frozen paired intervention. Also retain
these four algebraically equivalent recipes as future evaluator design examples,
without silently changing historical acceptance. Real owner questions remain the
next source of generalization evidence when available.

## Evidence and boundaries

Private `.artifacts/db-aware-baseline-20260914/`: frozen preparation, per-case
sanitized plans/metrics, complete live summary, unchanged end checks, post-hoc
review and two nine-test JUnit reports. Selected gold/foil outputs and schema/input
hashes match before and after; this is not a continuous whole-database snapshot.
The prior bank is immutable. No raw completions, reasoning, rows, credentials or
DSNs were persisted. The gateway saw only existing fictional schema/overlay,
questions and normal planner context, not gold plans/SQL/foils/answers.

Focused research checks **18 passed**; static passes. Source-identical offline
**1,841 tests** were verified and reused, not rerun or counted as live evidence.
Tracked delta: protocol, this note, counts/hashes manifest and roadmap. Runtime,
public formats, security boundaries, identity binding and evaluation code are
unchanged. Only research orchestration/outputs were added under ignored artifacts.
Local commit, no push. Manifest: `../../evidence/db-aware-baseline-01.json`.
