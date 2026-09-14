# User web probes: query capability boundaries (2026-09-14)

Owner requested recording useful interactive questions and adding regression
coverage where warranted. Exact user wording stays in
`.artifacts/user-web-probes-20260914/iot.yaml` (judged runner input, no changed
historical scores). This is a seen development case, not a blind holdout.

## Observation and diagnosis

The user reported `semantic_gap` for per-device telemetry and alert counts.
The supplied explanation identified two child tables and a join multiplication
risk. The full MCP payload, request ID and effective reporting time were not
captured; this is user-reported evidence, not a replayed model result.

The refusal is safe under the current algebra: `readings -> devices` and
`alerts -> devices` cannot be combined by the compiler's parent-only traversal.
`_parent_path` raises `grain_conflict`, mapped to `unsupported`. A planner can
decline earlier with `semantic_gap`; this case alone does not establish its
exact internal path. Prefer `unsupported` in the explanation: the data and
counting meaning exist, but the supported plan constructs are insufficient.
No production classification or prompt was changed here.

This is not impossible in one SQL SELECT: aggregate each child by device,
then LEFT JOIN those two aggregate relations onto devices. A naive join of
2 readings and 3 alerts for one device yields 6 rows and inflated counts.
The all-devices population also matters: include devices with readings only,
alerts only, neither, and both; absent child rows mean count 0, not an unknown
measurement coerced to zero. Group by device identity, not a nonunique label.
Two ordinary child-based queries alone do not preserve the complete population.

## Regression and follow-up

- Added compiler regressions for explicit devices/readings/alerts bases:
  all must reject the sibling-count shape with `grain_conflict`.
- Added supported controls: each child separately can be counted by device;
  these controls do not claim inclusion of zero-activity devices.
- The private natural-language case remains judged until a live replay captures
  configuration and the full response. Separate refusal safety, status quality
  and answer coverage; do not credit refusal as product capability.
- A future capability experiment should compare independent aggregation with
  an independently written SQL oracle using asymmetric counts and all four
  activity populations above. Do not add keyword exceptions or weaken joins.
  Supporting this requires an explicitly designed algebra extension, not an
  overlay description or a model asked to write SQL.

Validation: 32 compiler tests (including 5 new cases) and the static profile
passed; artifacts are `.artifacts/user-web-probes-20260914/{focused,static}`.
No new live model calls, DB mutations or public-contract changes in this slice.

## General device details (second user report)

The user next reported `unsupported` for listing all device details. Exact
wording and the supplied request ID are recorded in the private case file.
The local web launcher intentionally keeps no query/result logs, so an ID
alone cannot retrieve the original response. No live replay is claimed.

Current `QueryPlan.names_are_unique` requires measures or `latest`; there is
no general row-projection construct. `latest` is a restricted per-group row
selection with at most four take columns, not an all-details API. Special
unique-key grouping tricks can mimic a limited projection but do not establish
general support or justify silently narrowing "all details".

The reported refusal is consistent with this boundary. Unlike a missing
business definition, this is a harness/algebra capability gap; it does not
demonstrate a model-understanding or lexical-gate defect. Existing
`test_latest_row_per_group_ranks_rows_and_returns_the_taken_columns` covers
the no-measures domain boundary;
retain this as a separate seen natural-language regression candidate, without
adding a redundant test or changing expected statuses across old panels.

If row listing is prioritized, first specify visible output columns, stable
ordering, row limits/truncation (and whether paging is needed), permissions
and PII exposure. "All devices" must not silently mean only the first page,
and "details" must not override column visibility. No new construct or
automatic query logging is authorized or implemented by recording this case.

Clarification after owner feedback: column visibility enforcement, a 200-row
MCP output cap, `row_count`/`rows_truncated`, and the web truncation warning
already exist. Reuse them for any future projection construct; do not build a
second protection layer. An SQL-level LIMIT can still yield an untruncated
result of a limited query, so disclosure must not imply database completeness.
Column visibility is configuration-based, not automatic comprehensive PII
classification.

## Average temperature in Fahrenheit (third user report)

User reported `unsupported` for site-grouped mean temperature converted to
Fahrenheit; wording, explanation and request ID are in the private case file.
No complete response or replay was obtained. Code inspection supports the
capability diagnosis: an AVG over readings with a site dimension is expressible
via readings -> devices -> sites, but Measure and ReviewedMetric do not expose
a unit-conversion or scalar affine-transform operation. Ratios, shares and
growth do not supply arbitrary multiplication by a constant plus an offset.

For the same non-NULL observations and unweighted arithmetic mean,
`mean_F = mean_C * 9 / 5 + 32`. This is deterministic arithmetic, not a need
for a stronger model or a vocabulary exception. The reported refusal is safe
under today's contract but still loses an otherwise answerable product request.
Changing an alias to Fahrenheit without converting the values is wrong.

Future narrow experiment: a server-owned, explicitly selected unit conversion,
using a trusted source-unit binding, with disclosed source/target units and
conversion. Compare server post-aggregation conversion against an independent
SQL oracle that converts each reading before AVG; do not allow model-written
formulas, SQL or computed answers. Include 0 C -> 32 F, 100 C -> 212 F,
-40 C -> -40 F, mixed values, NULL-only groups, and a Celsius no-conversion
control. Preserve NULL and grouping; round only after conversion. Do not
generalize affine AVG commutation to sums, growth or nonlinear conversions.
Whether the conversion lives in the compiler or a typed server result stage
is a future design decision, not an implementation made by this record.

This case is queued as a seen natural-language regression candidate. No new
production tests pretending the unsupported feature exists, prompt edits or
live model calls are included; only documentation and private case intake.

## Temperature at the site with most alerts (fourth user report)

The owner reported `unsupported` for selecting the highest-alert-count site
and returning its mean temperature. The exact question and request ID are
in the private case file. This remains user-reported, not a captured/replayed
model result. Inspection of QueryPlan and compiler ordering confirms a single
base plus output ORDER/LIMIT, not independent fact aggregation composition.

This shares the first probe's independent-fact gap, with a cross-metric
selection requirement. The alert-count-by-site and mean-temperature-by-site
components are individually expressible. A future composed query could
aggregate both independently at site grain, select the winner(s) by alert
count, and attach the temperature by site identity. One SQL statement can
express this; a new general-purpose multi-step agent framework is not implied.
Do not rank only sites with temperature readings, since that can replace the
true winner. A naive readings/alerts join can inflate counts and reweight
temperature toward devices with more alerts.

Before promoting an answer oracle, specify tied maxima (return all tied sites
or an explicit approved tie policy), each metric's time scope, and temperature
population. Pooled reading-level AVG is not necessarily an equal-weight average
of device averages. A winning site with no non-NULL temperature should remain
the winner with NULL temperature, not be silently substituted. These are
candidate acceptance concerns, not newly approved defaults.

Future witnesses should include a unique winner, tied sites, a winner with no
readings, unequal per-device reading/alert counts, and explicit time windows.
Reject ranking by temperature, counting joined rows, or silently changing site
identity. Reuse the first probe's independent-aggregation experiment, adding
selection controls rather than implementing another case-specific mechanism.

No production change or live call; private YAML was checked for four unique
case IDs and the documentation diff passed whitespace validation.

Follow-up implementation/measurement is now recorded in
[query-extension-study-01](query-extension-study-01.md): research-only SQL
mechanisms work with correct plans, but automatic natural planning is not ready
for promotion. The original intake observations above remain historical.
