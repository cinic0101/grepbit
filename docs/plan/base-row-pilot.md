# Base-row listing shared-path pilot

## Authority and ownership

2026-09-14, baseline clean `06a4ef5`. Root owns the coupled domain/wire/compiler/
serving surface. Owner accepted the next step with "ok 可以下一步", following
the proposal to integrate basic rows first. Earlier explicit permission:
"同意你可以在 checkpoint 決定接下來的方向", authorized psql/Gemma and local
commits without asking. No push. Original grants, not this record, supply
authority. Existing Web/acknowledged Claude session are not regression workers;
preflight found no active regression.

## Contract ruler, then implementation

- Add optional `QueryPlan.rows`: explicit ordered ColumnRefs OR all_columns.
  Base table required; 1..32 visible projected columns; no duplicate projections.
  No measures, dimensions, time, latest, without, having or growth in this slice.
  Plan filters are base-table-only and keep existing typed binding/grounding.
- Explicit row ordering names projected columns. Default and tie-breaking order
  use the whole visible primary key; without a visible PK refuse. Preserve row
  multiplicity and NULL. No DISTINCT, grouping, parent-label projection or new
  formula. Reviewed segment predicates still apply through the existing compiler.
- Projection resolves all_columns using current visibility, never SELECT *.
  No implicit approval of PII visibility. Row result is unverified_semantics,
  even with a reviewed segment. Lineage exposes projection separately from
  measures; assumptions describe actual columns, filters, order and any LIMIT.
- Reuse executor/public max_rows and rows_truncated; do not inject a default
  SQL LIMIT that would hide truncation. Explicit LIMIT is a selected subset,
  not a completeness guarantee. No new total-count query or persistence.
- `DatasourceRegistration.allow_rows` defaults false. Both planner and compiler
  enforce the opt-in, including request-owned planners. The initial enabled
  direct-v16 strategy was rejected after live regressions; the current strategy
  runs v15 first and uses v16 only after unsupported (see follow-up below).
  Disabled profiles keep v15 messages. Capabilities disclose this per datasource.
  No new tool.
- Shared ask gates, grounding/recompile, SQL policy, evidence allowlist,
  deadlines/cancellation and follow-up binding remain in force. An empty/all-NULL
  projected row must not get the existing empty-aggregate explanation.
- Research rows should delegate to this compiler once implemented, retiring
  duplicate row SQL construction. Conversion/combine stay research-only and
  must not start accepting nested row plans accidentally.

Under the existing autonomous-checkpoint grant: first record intended failing
rulers, inspect failures, then proceed. This is an additive consumed plan/
registry/lineage format, not an authorization or identity policy relaxation.
Default-disabled compatibility and historical scores are explicit acceptance
conditions. Live research previously showed row feasibility; this pilot tests
the real serving path, not another independent harness.

## Validation and external budget

Focused domain, compiler/value/selfcheck and full ask tests: hidden columns/PK,
segments, named values and ambiguity, injection-safe binding, NULL/duplicates,
ordering/LIMIT, truncation, prior context and request stop. Existing request
lifecycle tests remain the concurrency ruler. One broad static/offline closeout.

Use existing internal Gemma 4 31B, serial, maximum 180 actual HTTP calls including
repairs/retries. Only fictional IoT/Service questions, value-free schema and
reviewed fictional metadata/candidates leave. Opaque current key. Local
PostgreSQL grepbit_ro, synthetic fixtures only, sample limit 0, readonly bounded
oracle/candidate SELECTs; no admin or DB writes. No other provider.

Freeze a row/oracle panel and rerun existing affected IoT/Service aggregate
case sets in the opt-in path. Count wrong values, unjustified answers, refusals,
invalids and repairs separately. Seen/authored cases are not generalization.
Do not enable the Web profile until live original-row and old-control evidence
supports a bounded pilot; failure leaves the opt-in implementation disabled.
Artifacts: `.artifacts/base-row-pilot-20260914/`.

## Ruler and first live diagnosis

Initial ruler: 10 intended row-contract failures, 2 controls passed, no setup
errors. Root proceeded under the explicit autonomous-checkpoint grant. The
first shared-path live batch exposed an implementation omission: qualified
order fields were normalized only against aggregate/latest outputs, not rows.
A targeted failing test now pins reuse of that existing rule for explicit and
all-column projections; no prompt/meaning change. 68 focused checks then pass.

Initial run stopped after 32 actual calls: 21 belong to two completed row
reports; 11 to an interrupted IoT baseline (no durable case report, not scored).
No DB mutations; the known Web process was not stopped. The original artifacts
and counter remain. To stay under 180 total calls, revised order is corrected
12-row panel, paired IoT/Service main controls (44 each arm), then pilot-only
coverage IoT/Service adversarial controls (20). Four calls reserved for MCP.
The two supplemental sets are not described as paired regressions. Avoid
repeating the entire preliminary experiment or pooling post-repair results.

## Composition follow-up, before Web enablement

The fixed pilot matches 11 base-row answers and refuses the joined-detail
negative, but changes `svc_tickets_without_logs` from an old successful query
to invalid rows+without. The model's requested combination is meaningful;
the self-imposed MVP exclusion, not missing user intent, caused this regression.
Under the same owner-authorized integration/autonomous-checkpoint scope, add a
red ruler then permit rows with the EXISTING without contract. Pass without to
the shared population compiler unchanged; retain scoped grounding, segment
rules, child windows and NOT EXISTS. Do not add a new anti-join implementation
or alter aggregate behavior. Retire only the earlier rows+without negative ruler.

Version the pilot prompt to v17; no other new combination is allowed. A separate
follow-up budget is **96 actual calls**, same destinations/data/opaque credentials,
serial. Reuse completed v15 baseline, rerun all 64 affected control cases and
12 rows plus a small explicit anti-row panel, then at most four metered MCP
calls if the coverage/safety results support the fixture pilot. This is not
permission to exceed the first batch's 180-call bound; counters stay separate.
Remaining first-batch budget may complete the two supplemental baselines.

### Revised before composition implementation

Completed old baselines show two more prompt regressions: cov_mttr and
cov_leased_fee change from semantic_gap to an unjustified answer. Therefore
the rows+without proposal above is **superseded before implementation**;
its red evidence is retained, its pending positive test replaced by strategy
rulers, and the original negative rows+without contract stays. Do not extend
the algebra to solve a prompt-induced regression.

Use the already announced 96-call follow-up budget for a conservative fallback
strategy instead: always run v15 first, unchanged; retain its plan, semantic_gap,
or ambiguous result. Only an explicit unsupported proposal can invoke the row
planner once. Only a valid rows plan may be promoted from that branch; an
aggregate result leaves the original unsupported refusal in place. All normal
ask checks/execution occur after this selection. No model certifies intent and
there is no keyword classifier. Original successful without queries retain
their old aggregate plans. Expose model_row_fallbacks so extra calls are honest.

The public strategy is `plan-v15-rows-fallback-v1`; row-stage prompt v16 remains
unchanged. Test baseline retention/decline distinction, row-only promotion and
existing total cancellation/deadline behavior before the next live run. Rerun
the 64 controls and 12 rows; multiple provider calls stay within the explicit
96-attempt phase budget. Both phases have independent counters and outcomes.

The research-only rows wrapper delegates to the shared two-sort-key contract
(previously three); this is an explicit narrowing of the experimental wire,
not a claim that historical prompts/results are unchanged. No current case
uses three keys. Production's established two-key limit is unchanged.

## Closeout

See `../research/base-row-pilot-01.md` and
`../../evidence/base-row-pilot-01.json`. First phase 171/180 calls; follow-up
80/96. Direct v16 matches 11/11 base-row answers but regresses old semantic
refusals. Fallback preserves all 64 old case outcomes but matches only 6/11
listing answers. **No Web promotion; registry unchanged; no live MCP smoke.**
The shared compiler/opt-in experiment remains available for bounded research.
Static passed, offline 1,998 passed, then four malformed-projection additions
passed within a 49-test focused run without further source changes.
