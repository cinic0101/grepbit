# Semantic contrast v1 and approved ratio-wrapper rejection

Status: COMPLETE, 2026-09-12. Production safety repair implemented; no research
arm passes the pre-recorded development screen. Exactly 108 model calls;
conditional replication, challenge, legacy-model and fresh ask-model allocations
were not consumed. Plan: `../plan/semantic-contrast-program.md`.

## Ratio boundary: approved and implemented

The initial checkpoint has three expected failures (raw, reviewed-metric and
share ratios accept nonempty wrapper filters) and three legal-position controls.
The owner then explicitly replied "同意，實作拒絕規則". The boundary now rejects
nonempty ratio-wrapper filters without guessing their scope. Plan filters and
either operand's filters retain existing meanings; an empty wrapper is legal.

- Domain: `plan_ratio_wrapper_filters_unsupported` validation failure.
- Compiler: unchecked in-memory models receive typed
  `ratio_wrapper_filters_unsupported` before SQL generation.
- SQL self-check: the unsupported shape is flagged even if a similarly named
  predicate occurs somewhere in the SQL; presence is not a scope definition.
- Normalizers: a ratio share cannot move its wrapper filter into plan filters;
  a redundant aggregate cannot erase a nonempty wrapper filter. Both nested
  and flat forms are tested. Filter-free duplicate aggregates remain legal.

This is an explicitly approved narrowing of accepted input, including a
previously accepted filtered duplicate-aggregate variant. The compact shown
schema remains an overapproximation with domain validation as the boundary;
neither its text nor production prompt revision v15 changed. A malformed
model response follows the existing bounded validation/repair/error path,
not necessarily the same status as a compiler refusal. No new algebra.

Five production files changed by only these additions. Removing the exact
added snippets reproduces their pre-slice SHA-256 hashes, preserving the
earlier dirty work. The old v2 checker test now constructs an unchecked model
to retain its unknown safety-net assertion; old main scores replay unchanged.

## Frozen experiment and results

Six authored minimal pairs, two members each, three languages = 36 questions.
Baseline uses concept-obligations-extract-v2-01 verbatim. Definitions changes
only concept definition prose, preserving bindings, offered concepts and
metrics. Task adds one generic instruction distinguishing output action,
population selection and specified versus genuinely unspecified measure basis.
No new payload, runtime keyword list, schema linking or ontology was introduced.
This is targeted development on known weaknesses, not a generalization claim.

108 serial calls, shuffled fixed order, Gemma 4 31B, thinking off, temperature
0, max_tokens 4096, timeout 60 s, no retries. All 108 structured responses
succeeded. The source was frozen at
sha256:ab54a0c773cba81dbc2a90eaf323e17bbbf31b2b50df9e7bf13ebc6c4002436d.
Input digest: 66b5b9f7dbb4d340520e940c3e0655f87bb33df1d934ac266e827f7666c3557f.
Raw model reasoning, invalid output and exception messages are not stored.

| Metric | Baseline | Definitions | Task |
|---|---:|---:|---:|
| Exact authored obligation cores | 27/36 | 27/36 | 27/36 |
| Exact qualifier-pair verdicts | 72/78 | 72/78 | 72/78 |
| Correct qualifier controls retained | 32/36 | 32/36 | 32/36 |
| Known qualifier violations allowed | 0/24 | 0/24 | 0/24 |
| Unresolved pairs allowed | 0/18 | 0/18 | 0/18 |
| Correct full-answer controls not blocked | 27/30 | 27/30 | 27/30 |
| Wrong full-answer controls not blocked | 5/30 | 5/30 | 5/30 |
| Wrong full-answer controls affirmatively passed | 2/30 | 2/30 | 2/30 |
| p50 / p95 seconds | 1.65 / 2.56 | 1.69 / 2.63 | 1.74 / 2.66 |
| Reported total tokens | 48,999 | 50,317 | 54,026 |

Equal counts do NOT mean all outputs are identical: definitions matches
baseline cores on 33/36 cases, task on 30/36. All 36 request hashes differ
from baseline for each intervention. These observations do not support a
claim that the gateway ignored the interventions or cached identical answers.
The changed cores mostly describe unresolved rates differently; do not call
every strict-core mismatch an unsafe answer. No candidate earns the required
two additional exact cores, let alone a measured improvement in joint safety.

The two affirmative wrong full-answer passes per arm are Chinese
回傳交易筆數 and 回傳交易總金額 paired with a return-only count/sum. Three other
wrong full-answer controls are not_applicable, not affirmative certificates.
The correct Japanese no-qualifier extraction should not be marked an extraction
error merely because this partial checker cannot detect an unrequested filter.
That is precisely why qualifier scores cannot stand in for whole-answer risk.
Error-free transport also does not make the answers semantically correct.

The 12-question challenge was authored and frozen before calls, including
quoted-heading versus predicate use, qualified-but-ungrouped counts, conjunctive
exclusions and unbound non-POS refunds. It was NOT run because the development
screen failed. Its author has seen the labels, so it cannot later be described
as a blind real-user holdout. No unseen questions were opened or relabelled.

## Zero-call actual ask replay

During the development run, independently replayed the prior six captured
planner proposals through actual ask(), default shape/absent-concept gates,
compiler, SQL policy and a local DuckDB executor over three fictional instances.
The literal-check path asserts it receives no literals; no grounding retrieval,
PostgreSQL driver, fresh planner call, MCP or deployment validation is claimed.
Prior independent off/on extractions are reused, not new model observations.

For each of the two captured rounds:

| Language | Actual ask outcome | Three instances |
|---|---|---|
| Chinese | answered, verified; wrong return_count metric | 2/3/1 instead of 4/5/3 |
| English | clarify, concept_not_mapped before SQL | correct COUNT plan blocked by existing lexical gate |
| Japanese | answered, unverified_semantics; correct COUNT | 4/5/3 |

The Chinese plan is still passed by both research verifiers. The English
refusal differs from the previous planner-adapter-only result and must be
reported rather than hidden. Eighteen local executions of the ask workflow
reuse six proposals; only twelve reach SQL. They are not eighteen independent
model samples. `verified` currently describes reviewed metric provenance, not
proof that the question requested that metric. Neither that status contract nor
the existing lexical concept gate is changed in this slice.

## Validation, disposition and next decisions

- Focused final: 193 passed. Full offline: 760 passed, no failures/skips/errors.
- Static passes. Property stress: max_examples=10000, one test passed in
  37.55 s. No explicit Hypothesis seed; not a 10,000-unique-plan claim.
- Fourteen ratio boundary tests cover accepted positions, raw/metric/share
  rejects, normalization bypasses, unchecked models and schema-driven filter
  mutants. Earlier red artifact remains; no xfails or relaxed golds.
- An intermediate compiler test found the new PlanError code missing from its
  registry; corrected before live freeze. Initial YAML parsing and an import
  ordering issue were instrument/setup failures, not semantic measurements.
- Existing 144-call v2 analysis replays identically after the production repair.
  No new PostgreSQL differential was run: arithmetic is unchanged; offline
  golden/differential contract tests and property coverage establish the bounded
  regression evidence. Do not quote previous live DB counts as this run's work.

No extractor is promoted and no larger-N or reasoning allocation starts.
The accepted production safety repair is complete independently of the failed
research hypothesis. This stops the planned conditional study, not the overall
product roadmap. Merely making a mistaken obligation disappear would change
pass into not_applicable, not establish that the candidate's population is
correct. A stronger completeness/whole-answer certificate would need a new
explicit contract, not a silent reinterpretation of v2.

Before another large model study, decide which boundary is being improved:
planner semantic selection, the lexical gate's false positives, or a precisely
scoped independent verifier. A different-model comparison may test shared-error
dependence, but no such improvement is established here. Preserve v2's limited
claims and measure actual ask-level false blocks/wrong-valids in any next study.

Evidence: `evidence/semantic-contrast-01.json`,
`evidence/semantic-contrast-ask-replay-01.json`; raw local report/journal in
`.artifacts/semantic-contrast-20260912/development.json[l]`. All own runs ended;
dev remains at 746f168, prior dirty work preserved, no stage/commit/push.
