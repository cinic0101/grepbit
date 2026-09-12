# Semantic contrast program and ratio-filter boundary

Status: completed bounded slice, 2026-09-12. Owner request: "幫我組織整體計劃，並開始實作、測試、驗證".
Ratio repair implemented; 108 development calls yielded no eligible candidate.
The conditional replication/challenge/legacy/fresh-ask calls were not started.
See `../research/semantic-contrast-01.md` for results and limitations. A separate
zero-model-call replay ran the old captured proposals through actual ask().
Ratio checkpoint crossed: 3 intended validation failures, 3 accepted-position
controls passed; owner explicitly replied "同意，實作拒絕規則" to that evidence.
Domain rejection plus compiler/self-check safety nets are now authorized.
The preceding plan proposed rejecting undefined ratio-wrapper filters and a
small independent extraction ablation, followed conditionally by actual ask
shadow validation. Earlier owner authority permits necessary PostgreSQL and
Gemma calls and bounded experiments on new discoveries. This record cannot
grant additional authority. Root owns this coupled slice, no delegates.

Baseline: dev @ 746f168, dirty source digest
sha256:e2ec1c886fb6995372496bfbff48da27482cc74352f0d6f27b4148e688d85b00.
Preserve every earlier source/evidence change. No stage, commit, push, installs,
production prompt promotion, customer sampling or persistent database writes.

## Two tracks and exits

1. Ratio wrapper: specify rejection rather than invent filter scope. Add a
   red domain ruler with ordinary ratio/operand/plan-filter controls. This
   changes an accepted input boundary, so stop this track after ruler evidence
   for explicit follow-up, without changing src, migrations or persistent state.
   Independent research below continues. After approval: domain/compiler/wire
   paths, self-check and generator mutants must not silently erase the filter;
   focused values and one broad gate. Completed after the approval recorded
   above: focused 193/static pass, offline 760 pass. This is not new algebra.
2. Research: retain v2 payload/checker and old inputs. Six authored minimal
   pairs x two members x three languages = 36 development questions. Compare
   baseline, clearer concept-definition prose, and a generic task clarification.
   The definition arm changes only concept definition strings, not bindings,
   offered concepts, metrics, SQL, or gold. The task arm changes only an extra
   system instruction. Both are tuned development hypotheses, not established
   root causes. No language-specific production heuristic or new semantic IR.
3. Conditional replication: select at most one arm with >=2 additional exact
   cores, no fewer correct qualifier controls retained, no extra known-wrong or
   unresolved escapes, no increase in full-answer wrong no-block controls,
   and no additional failed extractions versus baseline.
   Ties: exact cores, retained controls, fewer errors, arm name. Repeat baseline
   and the selected arm, unchanged source/data. Improvement must repeat; no
   changing labels or deleting failures to qualify. This is a screening rule,
   not statistical significance or a release threshold.
4. Only if replicated: run the original 36 v2 questions and 12 pre-frozen
   authored challenge questions for baseline and candidate. Challenge families
   are distinct from the development pairs; author-visible, NOT a blind user
   holdout. Any new joint escape or lost unresolved protection blocks promotion.
5. If still promising: actual ask() shadow with existing v15 planner, gates,
   compiler, policy and local synthetic executor. At most 12 questions, one
   planner call plus independent baseline/candidate calls = 36 calls. No
   candidate verdict changes served behavior. Hand-counted multiple instances
   distinguish wrong SQL from coincidences; record refusals and wrong-valid
   answers separately. No claim of complete MCP/DB/deployment coverage.
6. Resume A5 acceptance and non-POS checks only after a defensible result;
   A4 requires a measured full-schema bottleneck. No larger N or reasoning-on
   default based solely on repeated identical incorrect extractions.

## External scope and budgets

One serial process to existing http://10.12.0.187:4000/v1, gemma-4-31b;
opaque source of the existing ignored .env key, no new credential copies.
Outbound: fictional questions, value-free schema, definitions/metrics and
response schema. Never rows, SQL, labels, gold plans or other model answers.
Temperature 0, reasoning explicitly off, max_tokens 4096, 60-second timeout,
no retries, stop at three consecutive transport failures. Raw errors, invalid
content and reasoning are never retained. Fresh exclusive-create artifacts.

Budgets: development 108, selected replication 72, challenge 24, legacy 72,
ask shadow 36; maximum 312 calls, conditional rather than precommitted spend.
No extra calls if the development screen fails. No need for PostgreSQL in
the extraction experiment; compiler values may run on fictional in-memory
DuckDB. If PG is needed for a new arithmetic finding: existing grepbit_ro,
localhost:5432, inline VALUES only, bounded SELECTs, opaque DSN variable name.
No admin access, new datasource, actual customer rows or sampling this slice.

## Evidence and maintenance

Artifact root: .artifacts/semantic-contrast-20260912/. Record source snapshots,
question/definition/prompt hashes, call schedule, failures, costs and all
denominators. Freeze executable inputs during every live run. Offline/focused
tests cover single-variable isolation, label blindness, exact spans, bounded
calls, error retention, fresh outputs and conditional-selection behavior.
Keep ratio checkpoint failures visible, not xfailed or relabelled as green.
At closeout report broad counts with their expected checkpoint failures and
separate research validation. Historical v1/v2 scores remain unchanged.
