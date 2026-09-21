# P3.2 offline evaluator

Issue #41; implementation baseline:
`dev@e8c3a455bd4e09a266a772be599fe851d405df78` (accepted P3.1 #39 / PR #40).
This evaluator admission follows the accepted [P3.0 contract](p3-evaluation-contract.md).
It does not change product semantics, authorize live traffic or freeze fresh cases.

P3.2, including R1, was accepted through #41 / PR #42 at
`20abb5592262c77c98f9cabeaf7cf4854edb6fbe`. The original 755-test candidate and
764-test R1 evidence retain their own source identities. The P3.3 preparation
extension below does not change the accepted grader, scoring or expectations.

## Boundary and modules

The dependency direction is evaluator -> product, never product -> evaluator.
`tools/p3_assets.py` owns strict evaluator-only records/oracles;
`tools/p3_grading.py` owns deterministic action/layer observations;
`tools/p3_scoring.py` owns family/exposure/language accounting; and
`tools/p3_eval.py` owns preparation, fake execution and immutable reporting.
Any shared terminal-publication extraction remains evaluator tooling.

The runner extracts **only the question string** and calls the accepted
`interpret_recipe_and_execute(question, database, client, ...)`. Expectations,
exposure, family metadata and oracle values never enter messages, generation
schema, runtime context, presentation or pre-grading runtime evidence.
Fake completions are separate evaluator fixtures, not a second interpreter.
There is no repair, fallback, extra execution path, LLM judge or rerun policy.
All `grepbit/` sources and P1/P3.1 wire/context identities remain protected.

## Versioned assets

JSON assets live under `evals/p3/`, never the runtime package.
Case, oracle and panel formats use `p3-cases-v1`, `p3-oracles-v1` and
`p3-panel-v1`. Unknown fields,
invalid UTF-8/JSON, duplicate keys, excessive sizes and invalid native semantics
reject with fixed evaluator errors; no raw exception/payload logging.

A case records `case_id`, `family_id`, `question`, `language`, `expected_branch`,
`cohort`, `exposure`, `provenance`, `semantic_signature`, `must_pass`,
`observational` and `oracle_id`. Branches are answer/clarify/decline; cohorts
are answer/clarify/decline/anchor. An anchor is an answer regression, not a
quality-answer family. Family identity and required variants are explicit:
translations and paraphrases are not automatically new semantic families.
Variants must agree on oracle meaning, signature, exposure, cohort and status.

Provenance identifies historical/development/independent origin, source
references, implementer visibility and exposure history. Exactly three exposure
labels are recognized: `exposed_regression`, `design_seen`, `frozen_fresh`.
Historical descendants cannot be relabeled fresh; prior exposed/design-seen
history cannot be laundered away. An unchanged original run keeps its recorded
exposure; subsequent use needs a new case/panel identity and appropriate label.
These checks cannot independently certify human authorship, novelty or blindness.

Panels pin explicit input order and relative case/oracle asset references.
Development preparation/execution accepts only exposed/design-seen material.
Formal allocation validation is infrastructure, not a formal panel asset or
permission to run it. No actual frozen-fresh questions/oracles are authored here.
Scoring tests may use abstract allocation metadata without questions or gold.

## Closed oracle types

Answer oracles retain the reviewed P2 native request, recipe/version,
coverage and exact value shapes; they also identify user-required versus
permitted auxiliary slots and any additional expected auxiliary values/states.
Native request canonicalization is reused, not reimplemented: equivalent
admitted instant offsets agree, role orientation/code bytes/top-k remain exact.
No SQL-string comparison or generic formula/grading language is admitted.
Gold comes from reviewed prior oracle sources or independently hand-authored
contract expectations, never captured candidate output.

Clarification oracles use the accepted typed clarification union. Grading
compares kind and the complete canonical semantic set. Oracle/model choice IDs
need not match; display ordering and labels are not semantic gold. Presentation
must expose every actual semantic ID exactly once through choices(single).

Decline oracles identify designated control eligibility and a bounded
capability category, without requiring model-authored reason text. Deferred
missing-year/baseline/k ambiguity is not eligible decline gold; D05/P21 cannot
become a scored decline control. An ineligible decline oracle cannot earn
`correct_decline`, including in negative unit controls.

## Ordered grading and diagnostics

Primary outcomes use `p3-evaluator-v1` vocabulary:
`complete_correct`, `false_refusal`, `false_clarification`,
`missed_clarification`, `wrong_action`, `correct_clarification`,
`correct_decline`, `wrong_recipe`, `wrong_request`, `wrong_coverage`,
`wrong_fact_selection`, `wrong_value`, `partial`, `invalid_output`,
`operational_failure`, `not_run`. `synthesis_error` is reserved and not emitted.
Historical P1/P2 taxonomy and result records are not relabeled.

Expected answers grade action -> recipe -> complete request -> execution ->
coverage -> fact selection -> values. Expected clarification grades action ->
kind -> semantic alternatives/bindings -> presentation references/completeness.
Expected decline grades action -> control eligibility -> absence of a
substituted answer. Matching values never rescue an earlier semantic failure.

Each layer retains passed/failed/not_assessed independently. Later observable
evidence is not erased just because an earlier layer determines the primary
outcome. Wrong recipe/request takes precedence over a subsequent native error;
the operational error remains separate. A partial pack is `partial` only when
its available fact semantics, selection and values are otherwise correct.
Wrong available facts cannot hide behind optional gaps.

Coverage observes status/slots/grain/population/time/filter obligations.
Fact selection checks fixed native roles, IDs, derived-source links and
irrelevant/invented selections; numeric collision cannot rescue a wrong role.
Values include exact integer/rational/null/undefined/unit/order distinctions.
Empty SUM remains null; empty booking COUNT remains integer zero. Population
metadata must remain consistent with emptiness, not merely numeric equality.
This preserves the accepted [scalar contract](fact-kernel.md), including the
distinction between absent and measured-zero populations.
Runtime objects are observed, not rewritten to make an existing checker pass.
Reused P2 checks retain their historical classification and behavior.

### R1: independent semantic-evidence expectations

`tools/p3_expectations.py` owns `p3-evidence-expectations-v1`: the scalar and
grouped required check IDs, accepted grouped dimension profile ID, and ordering
for booking day, category and course. These are explicit immutable values, not
aliases, copies or import-time snapshots of candidate runtime constants.
Per-expectation provenance cites accepted `e8c3a455` source/test contracts;
ordering also cites the accepted grouped-amount documentation.

The deterministic SHA-256 covers the version, expectations and provenance.
P3 manifest `identities.evidence_expectations` records that identity, and the
existing source inventory also hashes the module. Changing the expectation
contract requires a separately reviewed identity; historical manifests/reports
are not repinned. This does not change runtime schema/context identities.

Required checks remain a subset of actual checks; additional compatible checks
are allowed. Reused `recipe_smoke` helpers retain independent responsibilities:
`canonical_request` normalizes native requests, `_values` extracts output,
`coverage_shape` compares supplied expectations, and `selection_shape` checks
evaluator-owned fixed slot/link structure. None derives expected truth from
runtime-private semantic constants.

Import/reload controls corrupt product constants first. Paired controls require
unchanged valid output to pass and co-mutated invalid output to remain
`wrong_coverage` with `checked_wrong=true`, including explicitly mutated
dataclass profile fields. This fixes evaluator independence, not a demonstrated
runtime defect or product improvement. Check IDs are evidence obligations, not
proof that the implementation actually performed each check. The deliberate
duplication is limited to semantic evidence: no physical schema, FK inventory,
SQL, SourceProfile, planner or generic oracle language is copied or introduced.

`checked_wrong` is an independent veto whenever a claimed complete normal
answer has wrong action, recipe, request, coverage, selection or values.
Decline/clarify/explicit partial is not a checked-normal answer, but still fails
its applicable denominator when inappropriate.
`not_run` means no attempt, not malformed output, timeout or a started call.

## Family scoring

Every required variant must pass its branch oracle for family correctness.
Each family counts once. Report `family_all_variants_correct` separately from
`family_all_variants_agree`; agreement uses canonical actual meaning/results,
not just outcome names, and can mean every variant is wrong.
Actual signatures retain bound scope, fact semantics, exclusions and slot/source
roles, excluding ephemeral snapshot/fact IDs. Unresolved references cannot
establish agreement. Unassessed agreement is null, not vacuous success.

Preserve every frozen input in per-input/language reporting. Invalid output,
operational failure, not-run, partial and inappropriate non-answer branches
contribute zero successes without leaving their fixed denominators.
Observational families remain explicit and cannot inflate promotion scores.
Incomplete/prepared runs cannot pass a promotion gate.

The accepted formal allocation validator requires 24 families / 44 inputs:
8 fresh answer families, 4 exposed answer controls, 4 clarification controls,
5 decline controls and 3 P2 anchors. Exposure is 12 fresh / 12 exposed families;
language totals are zh-TW 14, en 15, ja 15. Design-seen and deferred P21 are
not formal scored slots. The underlying >=90% rule uses exact ceiling:
ceil(0.90 * 8)=8; all four exposed controls are mandatory, hence 12/12 answers.
Clarification (4), decline (5) and anchors (3) have separate all-mandatory
denominators. No control boosts answer score; any checked-wrong answer vetoes
promotion. A development panel never establishes a formal promotion result.

## Evidence and execution admission

P3 has distinct manifest/report/stop-policy identities. Source/runtime,
DB, cases, oracles, panel order, settings and stop policy are pinned.
Candidate preparation remains distinct from an owner-supplied accepted clean
dev commit. Neither preparation kind is live authorization.

Default CLI preparation is zero-network. P3.2 fake execution requires an
explicit mock transport and uses the same production entry. No environment
loader, real transport or live mode is activated. Future live execution and a
minimal v2 compatibility probe require separate admission and owner approval.

Reuse existing fixture/source identity checks and exclusive artifact writing.
Durable per-input reservations precede sending; actual client HTTP attempts,
possible in-flight reservations and live input attempts remain separate.
Upstream inference attempts remain unknown. Timeout and network streaks are
independent; configuration/provider incompatibility, budgets, source/DB/manifest
drift, leakage and artifact/publication failures stop explicitly.

Terminal success is staged, flushed and admitted before atomic publication;
incomplete or failed publication never becomes success. Existing output paths
reject; no accepted evidence is overwritten. No post-commit revalidation or
compensating write retracts a successfully published terminal report.
Reports retain sanitized runtime evidence and grading metadata, not raw
completion/reasoning/provider bodies.

## Offline development workflow

The committed `development-*-v1.json` assets contain 15 inputs in 9 families:
the original nine P2 anchor inputs in their original order, four P3.1
clarification kinds, and historical D01/D02 decline controls. All are
`exposed_regression`, including explicitly synthetic development extensions.
They are neither a fresh evaluation nor the formal 44-input panel.

Answer gold reuses reviewed P2 requests/values and P0 reference SQL. Overview
daily/category auxiliary gold is independently calculated from that reference
source. The separate response script contains explicit fake actions; execution
never generates responses by copying the oracle. Script format is
`p3-fake-responses-v1`, with ordered `case_id` and typed `action` entries.

After the normal dependency setup, use a fresh directory each time:

```bash
run_dir=$(mktemp -d .artifacts/p3-offline-XXXXXX)
.venv/bin/python tools/fixture.py build --db "$run_dir/learningops.sqlite"
.venv/bin/python tools/fixture.py check --db "$run_dir/learningops.sqlite" \
  --report "$run_dir/fixture-report.json"
.venv/bin/python tools/p3_eval.py prepare --db "$run_dir/learningops.sqlite" \
  --output-dir "$run_dir/prepared" \
  --responses evals/p3/development-responses-v1.json
.venv/bin/python tools/p3_eval.py fake-run --db "$run_dir/learningops.sqlite" \
  --output-dir "$run_dir/panel" --manifest "$run_dir/prepared/manifest.json" \
  --responses evals/p3/development-responses-v1.json
.venv/bin/python tools/p3_eval.py report --report "$run_dir/panel/report.json" \
  --manifest "$run_dir/prepared/manifest.json"
```

The default panel is `evals/p3/development-panel-v1.json`; `--panel` admits
another strictly validated development panel, not a formal run. Preparation is
the default subcommand. `--accepted-commit` is an identity check for clean dev,
not permission to use live transport. Direct injected-mock tests may omit a
response script; script-backed CLI preparation/execution pins its bytes.

Bounds are explicit: at most 64 inputs, one attempt per input, concurrency one,
zero retries, 60 seconds per call and a panel budget of `60 * inputs + 120`
seconds. Assets are at most 1 MiB. Existing request and fixture/DB bounds remain
unchanged. No new environment variables, dependencies or live flags are added.

## Manifest and report

Preparation emits an exclusive manifest with source/runtime/action/context
identities, DB/asset/script hashes, input order, settings, stop-policy identity
and candidate/accepted status. Source, DB and manifest are checked during a
run; a preparation from an earlier candidate is not silently repinned.

New manifests also hash `pyproject.toml` and `uv.lock`. The uv migration changes
environment management, not installed dependency versions or frozen shared
helpers: legacy requirements files remain byte-identical verification witnesses.
See [dependency management](fact-kernel.md#dependency-management). Historical
manifests/reports keep their original identities.

The report identifies its manifest digest, panel, origin and preparation.
It records run status, stop/error codes, elapsed time, client HTTP attempts,
live-model attempts, possible-in-flight reservations, budget use and independent
network/timeout streaks. Upstream inference attempts remain unknown.
Per-input records link question hash/reference, family/language/exposure and
oracle metadata to native observations, usage/latency, action, primary outcome,
all layer states, operational error and checked-wrong flag.

The summary contains per-input, per-family, per-language, cohort and exposure
views; separate answer/fresh-answer scores; checked-wrong counts/case IDs; and
promotion eligibility plus reasons. Prepared/incomplete/aborted and development
runs cannot claim formal promotion.

`tools/evaluation_evidence.py` extracts the existing P2 staging/ownership and
atomic-commit mechanism. P1's artifact writer remains unchanged. P2 continues
using its historical grading policy; extracted coverage and selection helpers
allow P3 to observe them separately without relabeling old results.

## Development corrections and review boundary

Failed attempts remain under the local evidence root, not rewritten as passes.
Parser controls exposed backward exposure-history transitions, non-integer
top-k values and NUL paths; these reject explicitly. Mutation fixtures were
corrected to retain semantic fact links when `dataclasses.replace` generated a
new derived-fact ID. Runner comparisons ignore independently generated
snapshot IDs while still requiring identical model request bytes.

A new empty-Overview unit oracle initially misstated empty COUNT as null, and
the new grader shared that mistaken assumption. The accepted contract at
`docs/fact-kernel.md:103-106` and existing
`tests/test_overview.py:308-314` already require `(null, 0, null)`.
Only the newly authored unit oracle was revised to
`unit-empty-overview-v2`, revision 2, with explicit provenance. The evaluator
now distinguishes COUNT and SUM and rejects null-count/zero-sum mutations.
Historical gold and runtime outputs were not changed. This is an evaluator
and development-oracle correction, not product improvement; independent
review/owner acceptance remains required.

## Limits and deferred review

### P3.3 intake, freeze and preparation

`tools/p3_admission.py` adds a thin `p3-intake-v1` wrapper over the unchanged
case/oracle formats, `p3-formal-freeze-v1` snapshots and
`p3-compatibility-preparation-v1` offline probe plans. The
[independent-author handoff](p3-fresh-case-authoring.md) defines the metadata and
human review boundary. Required reviewer assertions are not machine-certified
novelty, authorship, truth or technical blindness.

The candidate is frozen at `20abb559`; its runtime/dependency sources and
accepted grading/scoring/expectation/shared-helper sources must match that Git
snapshot. The later accepted **tooling** commit is separately pinned and must
be exact, clean and on dev for formal freeze/preparation. A feature-branch
candidate cannot manufacture that acceptance.

Examples below are future owner-side operations, not a claim that independent
fresh inputs or an accepted formal freeze already exist:

```bash
.venv/bin/python tools/p3_admission.py audit --intake "$BUNDLE/intake.json"
.venv/bin/python tools/p3_admission.py freeze --intake "$BUNDLE/intake.json" \
  --panel "$BUNDLE/panel-v1.json" --db "$DB" --output-dir "$FROZEN" \
  --accepted-commit "$ACCEPTED_TOOLING_SHA"
.venv/bin/python tools/p3_eval.py prepare --panel "$FROZEN/panel-v1.json" \
  --formal-freeze "$FROZEN/report.json" --db "$DB" --output-dir "$PREPARED" \
  --accepted-commit "$ACCEPTED_TOOLING_SHA"
.venv/bin/python tools/p3_admission.py probe-prepare --db "$DB" \
  --output-dir "$PROBE_PLAN" --accepted-commit "$ACCEPTED_TOOLING_SHA"
```

Each output directory is fresh. Actual submitted basenames must be used.
Intake may be incomplete/draft; freeze requires independently reviewed complete
material, an owner reference, exact formal allocation and clean accepted
tooling. The freeze keeps byte-identical submitted case/oracle/panel/intake
snapshots under existing exclusive artifact-directory ownership. One bounded
raw-byte snapshot helper avoids changing their hashes through JSON formatting.
Existing staging/fsync/atomic publication mechanics publish the terminal
freeze only after asset, DB and source revalidation. Partial publication remains
incomplete; drift or any changes need a new reviewed identity.

Formal preparation additionally pins the freeze as an asset in the existing
manifest. Formal execution, including fake execution, remains rejected.
Archived formal reports may describe preparation only; historical development
reports remain readable without requiring the current checkout.

Probe preparation selects the already exposed English E01 input, pins source,
DB and the unchanged v2 route, and performs zero model calls. A feature branch
can produce only a candidate probe plan. There is no live command, credentials
loader or automatic prepare/probe/formal chain. The later probe is one attempt,
60 seconds, 2,048 tokens, no retries/repairs/fallbacks and no quality score.

### Exposed material and unresolved admission

The active exposed-side projection for future formal admission is
[`exposed-projection-panel-v1.json`](../evals/p3/exposed-projection-panel-v1.json),
panel ID `p3-exposed-projection-v1`. It remains **development-only**, not an
admitted or frozen formal panel. The original `exposed-panel-v1.json` remains an
unchanged historical development snapshot: 18 inputs / 12 provisional labels,
including all P10/P11/P12 questions, oracles and provenance. Existing historical
checks still inspect that snapshot; the default development evaluator is unchanged.

#### Owner decisions and projection ancestry

On 2026-09-21 the owner approved the following disposition for [#43](https://github.com/cinic0101/grepbit/issues/43)
after exposed requirement review and a family/oracle compatibility preflight:

| Historical candidate | Current formal-panel treatment | Preserved meaning and evidence |
| --- | --- | --- |
| P10_required_views | Deferred; excluded from the projection | Explicitly required views are meaningful user obligations, but the current action/fact evaluator does not sufficiently discriminate the broader synthesis obligation: missing views collapse into partial-result behavior. Revisit at the appropriate synthesis gate, not by adding fact-level machinery or a replacement here. |
| P11_nonchronological_roles | Excluded from the projection; retained as an exposed `E02_compare` semantic regression | Role binding remains useful regression evidence. Semantic taxonomy relationship is not formal family membership: P11's reversed request/values differ from E02's oracle meaning. Its historical family ID and oracle remain unchanged outside this panel. |
| P12_ranked_courses | Not admitted; excluded from the projection | Ranking is exercised, but the three unequal observed totals and `k=3` select all three courses. Neither a top-k truncation boundary nor a tied cutoff is exercised. Ranking-only may be meaningful apart from E03's share obligations, but this case is insufficient evidence. A future separately reviewed exposed cutoff witness may be considered; no replacement, fixture change or tie-coverage requirement is added here. |

The owner disposition is recorded in [PR #45](https://github.com/cinic0101/grepbit/pull/45)
under the active P3.3 decision context of [Issue #43](https://github.com/cinic0101/grepbit/issues/43).
A local transition review informed the decision but is not committed repository evidence.
The owner subsequently chose this 9/15 projection explicitly; the earlier
23/43 illustration was not adopted. No new novelty judgment is made here.

The derivation is only exclusion of `P10_required_views.en`,
`P11_nonchronological_roles.zh-TW` and `P12_ranked_courses.ja` from the historical
order, cases and referenced oracle set. Retained case/oracle objects, including
questions, gold, family IDs, signatures, exposure and provenance, are **exactly
unchanged**. New paths/panel ID distinguish this projection from its ancestors.
All files below are under `evals/p3/`; SHA-256 binds the exact raw bytes:

| Asset | Historical source at accepted tooling `7ad3fece7f94fe5effa94fefeac902db4cea5249` | Derived projection |
| --- | --- | --- |
| Cases | `exposed-cases-v1.json`: `c2c4a54bc4a7fb7fc808ef95bd351b206bbe00b18d7549320ac6606609fb7ed5` | `exposed-projection-cases-v1.json`: `fb424442495c0440a544c71a8d32d57341cc1ad3ef42f669ea024310c941c7f8` |
| Oracles | `exposed-oracles-v1.json`: `a1685b8183d37199406c59a68aa32319e6b51e13cbe7548978f348fb0371af77` | `exposed-projection-oracles-v1.json`: `0d2cb0a782cd349ceb1b716e8df182c78ee637f9c0c26b3482a5a320de4de1a4` |
| Panel | `exposed-panel-v1.json`: `5fdc59af24c96e58ebeec00e2cf274e040e3522d8343982648360ffacef39944` | `exposed-projection-panel-v1.json`: `b613fefea35b5cb106a4a0567eeab915aa7d686d32eb08a59b76e75170e44584` |

Existing schemas suffice. The panel loader requires exact case/order/oracle
membership, so separate subset assets are necessary; a shortened order pointing
at the original complete assets would be invalid. No new intake review claims,
owner-status fields or state machine are introduced. Both `p3_assets` and
`p3_admission` still require consistent oracle meaning within one formal family.
In particular P11 is not relabeled or assigned E02's gold to evade that rule.

#### Mechanical allocation, not admission

| Inventory | Families / inputs | Answer | Clarify | Decline | P2 anchor | Languages zh-TW / en / ja |
| --- | --- | --- | --- | --- | --- | --- |
| Preserved historical exposed snapshot | 12 / 18 | 4 / 4 | 2 / 2 | 3 / 3 | 3 / 9 | 5 / 6 / 7 |
| Active exposed projection | 9 / 15 | 1 / 1 | 2 / 2 | 3 / 3 | 3 / 9 | 4 / 5 / 6 |

Composition cells are families / inputs. Retained labels are `E01_overview`,
`E02_compare`, `E03_share_denominator`, `P09_empty_overview`, `P15_center`,
`P16_metric_meaning`, `P19_profit`, `P20_cash_received` and `P22_center_compare`.
Their retention is not certification that all nine independently satisfy every
formal admission requirement. No additional family is admitted by this change;
the nine remain provisional for this formal-panel admission, without undoing
the three P2 anchors' historical acceptance.

The accepted **24 families / 44 inputs target and its validator are unchanged**.
Both exposed-only inventories fail that validator. With the originally planned
12 fresh families / 26 inputs (language reservations 9/9/8), the projection would
total only 21 families / 41 inputs: answer families/inputs 9/15 instead of 12/18,
exposed families/inputs 9/15 instead of 12/18, and languages 13/14/14 instead of
14/15/15. Clarify, decline and anchor totals would retain their target counts.
This arithmetic is not a new panel allocation or evidence of supplied fresh
material. The current projection plus original reservations cannot satisfy the
fixed target; fresh supply/fillability remains unknown. Never pad back to 24/44.

No fresh question/gold is authored or inspected here, and no complete formal
panel has been frozen. Independent material/review, owner allocation/admission,
formal freeze and accepted-commit preparation remain outstanding. Compatibility
probe and formal scoring each still need their separate owner authorization.

The accepted representative v2 request remains 25,250 bytes under 32,768.
Evaluator metadata must leave bytes/content identical for the same question.
No prompt/schema optimization is part of this evaluator task. Fake success
does not prove provider compatibility, grounding or language quality.

Fresh formal cases, the 44-input panel, grounding/free values, resume/replay,
synthesis, multi-select/table/chart, product-entry routing, the live v2 probe,
stability and P4/P5 source/backend confirmation remain unimplemented/unassessed.
Evaluator correctness is not product improvement or demonstrated RSI.
Final handoff must include source/commands/results/complexity and separate
A-E review under the accepted contract.
