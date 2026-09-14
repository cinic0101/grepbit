# User web probes: independent child counts (2026-09-14)

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
