# LearningOps fixture

New fictional multi-center course/booking operations. Source: the owner-provided
V3 draft of 2026-09-18. No legacy schemas, rows, names, mappings, questions or
reference SQL were imported. Domain fixture version: `learningops-v0.1`.

Ten domain tables, 88 seed rows. DDL and seed are here; cases and gold/reference
queries live separately at repository-root paths `evals/cases/learningops.json`
and `evals/oracles/learningops.json`.
The case questions intentionally use Traditional Chinese; this documentation
and all workflow text are English. P0 does not validate multilingual quality.

Run `python3 tools/fixture.py` from the repository root; see the root README for
commands. Keep generated DBs/reports in `.artifacts/`. This is fixture/reference
code, not a production SQL policy, runtime, model test or PostgreSQL validation.
SQL references and the Python ledger were authored together: different
algorithms are not independent human oracle review.

## Physical model and grains

| Table | Row meaning | Important features |
|---|---|---|
| centers | One operating center | Duplicate names, stable codes, zero-activity center |
| learners | One known booking account | Duplicate names, fictional restricted email |
| courses | One course product | Category can be NULL |
| sessions | One scheduled offering | Duration in minutes; zero and unknown capacities |
| bookings | One registration order | Confirmed/cancelled/draft; nullable account; booking time |
| booking_items | One course-session line | Seats, unit price, line discount; same-center FK constraints |
| payments | One payment attempt | Split payments; posting time; success/pending/failure |
| refunds | One line refund event | Partial refund; next-period refund; pending refund |
| attendance | One attendee's visit on one booked line | Not the booking account or a booking |
| monthly_targets | One center/metric/month target | Zero target is distinct from missing target |

Only `centers`, `learners`, `courses`, `sessions`, `bookings`, `booking_items`,
`payments`, `refunds`, `attendance`, and `monthly_targets` are domain tables.
Evaluation labels, expected answers, issue links and canonical questions remain
outside the database and must never be included in model-visible schema context.

## Development semantic baseline — detailed P0 review remains open

All money values are TWD minor units (100 = TWD 1). No currency conversions or
accounting/revenue-recognition promises are made.

- `confirmed_booked_amount`: sum(seats * unit_price_minor - discount_minor) for
  confirmed bookings, filtered by booking creation time. Grain: booking line.
  Refunds are NOT subtracted. Never call this profit or recognized revenue.
- `confirmed_booking_count`: count distinct booking IDs in the same population.
  A course breakdown can overlap when one booking contains multiple courses;
  sums of per-course counts must NOT be equated with total bookings.
- `booked_seats`: sum line seats in the same population. These are seats, not
  unique humans and not attendance visits.
- `known_booking_accounts`: distinct non-null learner IDs in that population.
  Anonymous bookings are excluded and their absence must be disclosed.
- `cash_received`: successful payment events in a posting-time window, regardless
  of booking status or booking creation period.
- `posted_refunds`: successful refund events in a posting-time window.
- `net_cash_inflow`: cash_received - posted_refunds for the same posting window.
- `cohort_net_booked_amount`: confirmed_booked_amount minus successful refunds
  attached to that booking cohort before the explicit as_of cutoff. This is a
  separate definition from posting-period net cash.
- `session_duration_hours`: reviewed duration_minutes / 60, calculated by the
  trusted derived-fact evaluator, not by relabeling output.
- Target attainment: undefined for zero target; unavailable for missing target.
  Do not coerce either case to 0%.

The March scenario uses business timezone Asia/Taipei and frozen cutoff
`2026-04-01T00:00:00+08:00`. The UTC interval is
`[2026-02-28T16:00:00Z, 2026-03-31T16:00:00Z)`.
The dataset deliberately includes later event rows to test filtering. Current
status fields do not model status history: this is NOT a historical bitemporal
ledger. `as_of` anchors query requirements, not a claim of time-travel storage.

The `+8 hours` in the authored daily reference applies ONLY to this Taipei
fixture. It is not a general timezone implementation. PostgreSQL parity must
include typed dates/timestamps, IANA zones, DST, decimal behavior and NULLs.

### Sanity ledger for March

| Fact | Expected |
|---|---:|
| Confirmed booked amount, minor units | 158000 |
| Confirmed bookings | 7 |
| Confirmed booking lines | 8 |
| Booked seats | 12 |
| Known booking accounts | 5 |
| Successful cash received, minor units | 183000 |
| Successful posted refunds, minor units | 20000 |
| Net cash inflow, minor units | 163000 |
| Cohort net booked amount at cutoff, minor units | 153000 |

These numbers are intentionally different. The fixture is designed to reject
substitution of payments, bookings, seats, people and monetary populations.

## Versioning and extension

One logical fixture family, multiple immutable instances: core; focused scenario
mutations; later deterministic stress seeds. Do not keep hand-editing a shared
SQLite file. Rebuild from versioned sources; runtime reads an immutable instance.
A run records commit, fixture content hash, case and oracle versions, semantic
and recipe revisions, backend/runtime version, model/prompt/settings, as_of,
result classes, attempts/latency/token usage and known unassessed cases.

For real-data feedback, first recreate the causal structure with wholly synthetic
values. Preserve the original observation privately. A similar synthetic failure
is a reproduction hypothesis until the reporter confirms the repair on the real
source. Once feedback has informed a fix, it is regression data, not fresh holdout.

## Security and public data

`example.invalid` emails are fictional, but intended to test visibility denial.
The fixture connection is read-only; this does not implement an authorization
policy. Do not publish real schema comments, customer names, SQL literals,
connection strings, screenshots or row dumps in the public repository/issues.
A production boundary needs allowlisted schemas/columns/functions, parameterized
values, bounded execution and result size, and database-enforced read-only access.

