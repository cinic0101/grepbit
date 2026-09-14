# Query extension experiment: rows, units, independent aggregates

## Work and authority record (2026-09-14)

Owner request: expand the four interactive probes into nearby questions,
research, test, classify and implement the query families. Owner then asked
whether conversions belong in SQL; accepted the proposed compiler-owned SQL
direction and said to continue. Earlier session authorization permits local
commits, read-only PostgreSQL and Gemma calls, and self-directed checkpoints.
No push, production data mutation, schema migration or new credential storage.
Root is the sole writer; baseline `2a9210f`, clean worktree.

Permission sources include the owner's earlier explicit statements:
"同意你可以在 checkpoint 決定接下來的方向" and
"有需要時隨時可以 commit 不用特別問我". This record references those grants;
it does not grant additional authority itself.

This slice is an **isolated research implementation**, not a change to the
default QueryPlan, prompt v15, MCP tools, web result contract or scoring.
Promoting it requires measured value correctness and integration coverage for
existing gates, grounding, lifecycle, overlay/segments and evidence. Research
success is not a production release. SQL construction stays in the sqlglot
adapter; the model never emits SQL or sees result rows.

## Measurement and limits

- Freeze a small authored panel on the existing synthetic IoT and Service
  fixtures; retain original four user probes privately as seen cases.
- Compare existing ask() against the research planner on the same inputs.
  Independent, handwritten SQL defines values before candidate inspection.
  Refusals, failed calls, correct answers and wrong answers count separately.
- Unit-test adversarial fixture instances: unequal counts, no child rows,
  NULLs, hidden columns, same labels/different keys, ties and a winner without
  temperature. Use independent expected values, not just compiled shape.
- Maximum 96 actual Gemma HTTP calls, serial, no SDK retries. Destination:
  existing configured on-prem gateway; Gemma 4 31B; opaque existing key.
  Outbound: fictional schema/comments, questions, typed research schema,
  trusted fictional unit metadata. No database result rows or DSNs.
- PostgreSQL localhost:5432: existing grepbit_ro only, only the synthetic
  IoT/Service fixtures, sample limit 0. Read-only oracle/candidate SELECTs,
  bounded statement timeout and row count. No admin/setup work needed.
- Fresh ignored artifacts; preserve old scores and raw observations.
  These authored/seen cases cannot establish unseen-user generalization.

## Research ruler / acceptance decisions

Three explicit query kinds, not a general agent DAG or free-form expression:

1. **rows**: visible base-table columns only, no arbitrary SQL or JOIN fields.
   Explicit columns or all visible columns; stable primary-key tie breaking;
   finite output limit and truthful completeness disclosure. Existing overlay
   visibility and parameterized filters are reused. Hidden columns remain
   inaccessible. No new PII policy is inferred from visibility.
2. **aggregate**: existing QueryPlan, optionally a selected output converted
   between permitted units. Source units come from trusted request metadata,
   never a model assertion or column-name heuristic. Celsius/Fahrenheit:
   AVG/MIN/MAX only; minutes/hours: SUM/AVG/MIN/MAX. Preserve NULL, no premature
   rounding. Conversions are SQL arithmetic with server-owned constants.
   Reject combinations whose semantics are not supported (e.g. converted
   HAVING, ratio/share/growth, unbound or incompatible units).
3. **combine**: 1-3 independent simple aggregates, each compiled by the old
   compiler at the same entity identity, LEFT JOINed onto the visible entity
   population. Single-column entity PK required. Scope belongs explicitly to
   each component; never direct-join two raw child relations. Absent COUNT
   is zero; absent SUM/AVG remains NULL. Optional max/min selection on a
   named component output keeps all non-NULL ties. This is a disclosed study
   default, not a silent product decision. Ranking never drops an entity just
   because a different component has no rows. Entity labels are not identity.

Do not change old QueryPlan to accept these shapes during the experiment.
Malformed references, duplicate aliases, incompatible units and unsupported
combinations fail closed. No silent loss of clauses. A safe refusal is still
lost answer coverage on the positive panel. Selected extra measure columns
must be independently correct and disclosed; the grader must not ignore an
arbitrary subset. Research assumptions are not intent certification.

## Order

1. Freeze panel/oracles and record baseline.
2. Write contract tests; inspect intended red failures, self-checkpoint under
   the owner's existing autonomy authorization, then implement the prototype.
3. Run independent SQL/value checks, then bounded live planning comparison.
4. Diagnose failures; version any research prompt changes separately. Run
   full offline/static validation once at closeout. Report promotion/no-go
   separately for the three families and exact remaining product work.

## Completed slice

See [results](../research/query-extension-study-01.md). The initial 12 static
contract checks establish isolated new shapes without changing the old runtime;
they were not claimed as failing implementation tests. Under the existing
self-directed checkpoint authorization, proceeded to the opt-in compiler.
Final: 44 new focused checks, 1,948 offline tests and static green; 95 model
calls across baseline, two wire arms, natural probes and bounded diagnostics.
Correct-plan injection answers all four original questions; automatic natural
planning does not. All three mechanisms remain research-only. No new public
format, persistent schema, auth/identity binding or historical evaluation policy
was changed. No push and no DB mutation. The existing Web remains unchanged.
