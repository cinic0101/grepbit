# P2.2: bounded observed grouped amount

Issue #18 adds one offline fact primitive, not Overview, Breakdown or a generic
GROUP BY API. It starts from accepted P2.1 on
`dev@c2cf2826994d8d198e12232a19a0a28d7bf8fa1e`. Model selection, optional
orchestration, subtotal/share, rendering and live recipe runs remain future work.

## Public contract

`execute_grouped_amount(database: Path, request: GroupedAmountRequest, *,
limits: ExecutionLimits)` returns a checked `GroupedAmountFact` or raises
`KernelError`. It does not accept SQL, connections, callbacks, catalogs or plans.
The existing [dependency/setup instructions](fact-kernel.md) apply.

```python
from pathlib import Path
from grepbit import GroupedAmountRequest, execute_grouped_amount

request = GroupedAmountRequest.from_mapping({
    "scope": {
        "metrics": ["confirmed_booked_amount"],
        "start": "2026-03-01T00:00:00+08:00",
        "end": "2026-04-01T00:00:00+08:00",
        "timezone": "Asia/Taipei",
        "center_id": None,
    },
    "dimension": "course",
    "top_k": 2,
})
fact = execute_grouped_amount(Path("learningops.sqlite"), request)
document = fact.to_dict()
```

The typed constructor is `GroupedAmountRequest(scope, dimension, top_k=None)`,
where scope is a FactRequest. Only `confirmed_booked_amount` is admitted.
Both absolute bounds must be explicit and describe one full calendar month in
the reviewed fixed UTC+08:00 profile, labeled `Asia/Taipei`. This is not a
historical IANA/DST calendar engine. Equivalent representations of the same
absolute bounds are accepted; there is no implicit year/month.

Optional `center_id` is a canonical ID, not a code/name to resolve. Unknown IDs
fail. Other metrics, aggregates, filters, joins, order expressions, multiple
dimensions, arbitrary limits, formulas and `include_empty` are not fields.
P1 FactRequest itself is unchanged.

| Dimension | Reviewed key | Fixed ordering | Request / coverage |
| --- | --- | --- | --- |
| `category` | `courses.category` via line -> session -> course | NULL first, then binary text ascending | No top-k; `all_observed_groups` |
| `booking_day` | Booking creation date using `date(created_at_utc, '+8 hours')` | Chronological ascending | No top-k; `all_observed_groups` |
| `course` | Canonical `courses.course_id` via the same relation | Amount descending, course ID ascending | Integer top-k 1..3; `top_k` coverage |

The compiler extends the same native SQLGlot scalar query construction with one
reviewed dimension. It groups the full eligible population, then orders and
limits the grouped result. It never limits source rows before aggregation.
Ties do not increase row count beyond k. There is no per-question dispatch.

## Why the existing FK parent requirement is retained

The accepted scalar profile directly validates `centers`, `bookings` and
`booking_items`, but these are **not three independent tables**. Its existing
foreign-key checks also require valid referenced parent keys, including
`booking_items(session_id, center_id) -> sessions(session_id, center_id)`.
This prerequisite predates P2.2.

The baseline was reproduced offline without changing source or assets:

| Disposable source variation | Existing scalar result |
| --- | --- |
| Remove `courses` | Pass; amount 158000 |
| Remove `sessions` | Reject: `unsupported_source` |
| Retain only session parent keys/unique pair; remove `courses` | Pass; amount 158000 |

The owner confirmed preserving that behavior. Therefore “booking_day does not
require sessions/courses” means **no additional dimension-source requirements**:
day does not require course/category columns, a courses table, extension scans
or dimension-query permissions. Existing session parent keys still must satisfy
the base FK checks. Removing those checks would weaken accepted P1 admission;
giving day a bypass would create a different admission path. Neither is done.

## On-demand source and permission extension

Scalar and Compare retain the same base profile and query authorizer.
Booking-day grouping also uses that base admission, with only the fixed date
function enabled while its grouped query executes.

Category/course add a private source extension inside the existing transaction:

- Real STRICT `courses` with a single non-null TEXT `course_id` primary key;
  category additionally requires nullable, non-generated TEXT `category`.
- Real STRICT `sessions` with a single non-null TEXT `session_id` primary key,
  non-null TEXT `course_id` and `center_id`, the reviewed course/center FKs and
  valid relationships. The inherited item FK check requires the referenced
  unique `(session_id, center_id)` pair.
- Consumed columns require default binary collation. Unused course/session
  display, start, duration and capacity fields are not admission requirements.
- Consumed course/session rows are scanned under the same source-row budget.
  Course IDs are checked even when grouping by category; unused category values
  are not read or checked for course grouping.

Joins retain both session ID and center equality. PK/FK admission prevents
fan-out or missing dimension membership; DISTINCT/deduplication is not a repair.

Metadata/relationship inspection uses fixed trusted statements, as base
admission does. The read-only connection, query-only setting and progress
handler remain active throughout. Query permissions are dimension-specific:
only category/course get the consumed extra columns; only day gets `date`.
The scalar authorizer is restored after extension validation and after grouped
execution, including failures. Callers cannot select these permissions.

## Checked evidence and bounds

`GroupedAmountRow` contains `key` and exact integer `value`. A
`GroupedAmountFact` is not a scalar Fact or a recipe AnalysisPack. It contains:

- Opaque UUID fact ID, metric/catalog identity/digest, dimension and its reviewed
  profile ID, ordered rows and `TWD_minor`.
- Source grain (`booking_line`), population/time basis, absolute range, timezone,
  canonical center filter, SQL/parameters and named checks.
- Coverage kind, requested top-k, fixed ordering, and `empty_population`.
- Common snapshot ID/metadata, optional dimension-source schema digest, runtime
  versions, cumulative execution counters and limitations.

The catalog digest covers the existing amount definition; the separate
dimension profile identifies the bounded grouping rules. Schema digests and
snapshot UUIDs are not persistent data versions.

Trusted hard caps, not new ExecutionLimits options:

| Bound | Rule |
| --- | --- |
| Full observed output | At most 64 rows; the 65th row raises `output_limit_exceeded` |
| Course output | At most requested k, with k in 1..3 |
| Category key | NULL or valid UTF-8 text, at most 256 bytes |
| Course ID | Nonempty valid UTF-8 text, at most 64 bytes; never NULL |
| Booking-day key | Canonical ten-byte date |
| Amount | Exact nonnegative signed-64-bit integer; aggregate overflow fails |

The extra sentinel row detects over-cap output; it is never returned as a
truncated success. Row count, key byte bounds and integer widths also bound row
serialization size, including JSON escaping. No float or decimal fallback is
used. Oversized or malformed source keys fail before a fact is returned.

NULL category remains a real NULL key, distinct from text such as `"unknown"`.
An empty eligible population produces no rows and `empty_population=true`,
never a zero-filled member or one fabricated NULL group. Measured zero on a
nonempty population remains a real zero-valued group.

## Snapshot, reconciliation and limitations

The standalone wrapper uses the existing private read transaction and budget.
The private grouped helper can run alongside the scalar helper inside that same
transaction; no public multi-task API was added. Base admission runs once.
Any dimension admission, grouping/ranking and finalization use the same timeout,
VM accounting and row-validation budget. Existing defaults/hard maxima do not
change.

Full category/day sums are tested against the compatible scalar amount in one
snapshot, both all-center and center-scoped. Empty rows reconcile to scalar
NULL/empty evidence as absence, not `sum([]) == 0`. Course top-k is tested as a
selected subset and is never presented as the total/denominator.

Q11/Q12/Q13 are witnesses for one primitive, not three operators or independent
recipe promises. This does not admit distinct-count aggregation, zero-filled
members, calendar filling, Q10 completion, subtotal/share, optional failure
handling, Overview/Breakdown, model calls or PostgreSQL parity.
