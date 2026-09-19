# P1.1: bounded offline SQLite fact kernel

The accepted P1 kernel from #6 implements explicit requests, not analytical
recipe planning. The scalar executor itself has no model client, synthesis,
service endpoint or PostgreSQL adapter. The separate
[P1.2 adapter](model-integration.md) uses this same execution entry; it does not
change these four definitions. P1 was accepted after the separately authorized
successful smoke #13; the earlier #10 failures remain preserved. The fixture
checker does not execute the twelve P0 behavioral scenarios. The [P2 design](p2-recipes.md)
admits multi-scope/optional composition. P2.1 adds only
[offline Compare](p2-recipes.md#p21-offline-scalar-compare), using the same
private transaction and scalar helpers. Optional execution remains future work.
P2.2's [grouped-amount primitive](grouped-amount.md) reuses that transaction,
budget and native query construction without broadening scalar admission.

## Install and run

From the repository root, use Python 3.11+ and SQLite 3.37+. The kernel itself
requires only `sqlglot==30.18.0`; repository `requirements.txt` also pins the
separate P1.2 adapter's dependencies. No optional SQLGlot extras are needed.
Using the kernel or its existing CLI does not construct a model client.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

mkdir -p .artifacts
run_dir=$(mktemp -d .artifacts/p11-local-XXXXXX)
.venv/bin/python tools/fixture.py build --db "$run_dir/learningops.sqlite"
.venv/bin/python -m grepbit \
  --db "$run_dir/learningops.sqlite" \
  --request examples/march-facts.json \
  --output "$run_dir/facts.json"
```

If a relocated Python distribution cannot bootstrap `venv`, an already-installed
`uv` can create it instead:

```bash
uv venv --python python3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

Use a new output directory for each attempt. CLI outputs are exclusive-create:
success writes a Fact Pack; a handled failure writes `status: failed` with an
error code; interruption leaves incomplete or unparsable evidence. Existing
outputs are never replaced. Failed commands exit nonzero. Do not treat the
existence of a file or a prior successful output as evidence of a new success.

Run the protected P0 and new kernel tests separately:

```bash
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_fixture test_multilingual_cases test_review_witnesses -v
.venv/bin/python -m unittest discover -s tests -p 'test_kernel*.py' -v
.venv/bin/python -m unittest discover -s tests -v
```

These commands access only synthetic local SQLite files. Dependency installation
is not a live evaluation. No credentials or evaluated-model endpoint is used.

## Request and bindings

The P1 scalar entry remains `grepbit.execute_facts(Path, FactRequest, ...)`.
`grepbit.execute_compare(Path, CompareRequest, ...)` is the finite P2.1 entry;
both share one internal executor, not separate SQL paths.
`FactRequest.from_mapping` validates the CLI's JSON shape:

| Field | Contract |
| --- | --- |
| `metrics` | One to four distinct admitted metric IDs; order is preserved |
| `start`, `end` | Explicit offset-aware ISO instants with seconds and up to six fractional digits; `[start, end)`, strictly increasing |
| `timezone` | Explicit valid IANA business timezone; retained as context |
| `center_id` | Optional already-bound center ID, such as `CA`, not its code or name |

Unknown fields, duplicate JSON fields, invalid types, naive/inverted periods,
unknown metrics and unknown centers fail explicitly. Relative dates, name
resolution, SQL, custom formulas, units, grouping and ranking are not request
options. The input file is capped at 16 KiB.

`grepbit/catalog.py` mechanically binds four accepted definitions:

| Metric | Source grain | Aggregate | Unit |
| --- | --- | --- | --- |
| `confirmed_booked_amount` | Booking line | Sum of seats * price - line discount, before refunds | `TWD_minor` |
| `confirmed_booking_count` | Booking | Count distinct booking IDs | `bookings` |
| `booked_seats` | Booking line | Sum of seats | `seats` |
| `known_booking_accounts` | Booking | Count distinct non-null account IDs | `booking_accounts` |

Every metric uses current confirmed status and booking creation time. Account
facts disclose both anonymous exclusion and the number of excluded bookings.
Bookings with multiple lines do not multiply booking/account counts. Only the
reviewed many-to-one line-to-booking join is used, including center equality.
Payments, refunds and attendance are not joined.

Catalogs are trusted, reviewed Python configuration, not caller-supplied JSON or
model output. Identical definitions under another admitted ID use the same
compiler; there is no metric-ID dispatch or question-specific SQL template.
Bindings use native SQLGlot expressions and a small allowed expression set,
not a replacement relational AST. Catalog changes require semantic review;
passing structural validation alone does not approve a new business definition.

Empty source populations are complete empty results, not execution failures.
SQL sums remain `null` and counts remain `0`; `population_rows` and
`empty_population` distinguish absence from a measured zero. An anonymous-only
booking population is not empty, even though its known-account count is zero.

## Time and physical profile

Only the accepted canonical whole-second UTC TEXT and INTEGER minor-unit
profile is admitted. The runtime checks the three used STRICT tables' columns,
nullability, primary keys, declared CHECK expressions, declared/actual foreign
keys, timestamp encoding, status/currency domain and exact line arithmetic. CHECK
expressions are compared using SQLGlot's existing DDL nodes; arbitrary equivalent
constraint rewrites are not automatically admitted. Explicit collations,
views, generated columns, changed required schema and other physical encodings
fail; this is not generic schema discovery. Related FK parent tables must exist
and satisfy SQLite's relationship checks.
In particular, valid session parent keys were already required by the item FK;
this does not mean scalar queries validate or query course/category dimensions.
Booking-day grouping inherits that prerequisite. Only category/course grouping
adds the reviewed sessions/courses dimension profile; see the
[admission clarification](grouped-amount.md#why-the-existing-fk-parent-requirement-is-retained).

Input offsets define absolute instants. The business timezone is preserved, not
used to guess a calendar period or override those instants. Fractional bounds
are preserved in the Fact Pack; because stored instants lie on a whole-second
grid, both SQL bounds are rounded **up** to the next stored second. This exactly
preserves half-open membership, unlike truncation or comparing fractional TEXT
directly with the fixture's `...SSZ` encoding.

The scalar API has no historical-status reconstruction, local-wall-time
interpretation or date bucketing. P2.2 separately admits fixed UTC+08:00
booking-day grouping, not general timezone/PostgreSQL parity. Integer
multiplication overflow is rejected during validation; aggregate overflow is an
explicit batch failure, never a float conversion or fallback value.

## Execution evidence and limits

A batch uses one short read-only SQLite transaction for validation, center
binding and every required fact. `mode=ro`, `query_only`, disabled trusted schema,
bound values, approved identifiers/expressions and an authorizer for fact-query
table/column/function access constrain execution. The authorizer rejects writes,
attachments and non-allowlisted functions. Trusted schema/profile inspection
uses fixed internal statements before that authorizer is installed; there is
no public raw-SQL executor. Connections close on success and failure.

All facts are required: any failure raises `KernelError` and prevents a complete
Fact Pack. There is no partial-success orchestration or hidden retry.

Default trusted execution limits are two seconds, 1,000,000 SQLite VM steps
(checked every 100), and 100,000 total rows scanned by encoding validation.
Limits can be reduced; hard configured maxima are 30 seconds, 1,000,000 steps
and 100,000 rows. SQLite lock waits are disabled. SQL length, value length and
parameter counts are capped; at most four scalar result rows are admitted.
Validation scans used source tables, so a small output does not imply cheap
work. These are cooperative budgets, not a hard memory, filesystem I/O or
hostile-database sandbox. Backend-specific cancellation/isolation remains P4.

A Fact Pack contains the preserved request, metric/catalog identity and digest,
integer/null values and units, grain/population, range/time basis/timezone,
filters, empty/exclusion disclosures, generated SQL and parameters, named checks,
backend/dependency versions, limits and observed execution counters. The snapshot
UUID identifies only this batch's read transaction. Its schema digest is not a
data digest or a persistent database version.

P2.1 adds an opaque server-generated UUID `fact_id` to each `Fact`, including
P1 FactPack JSON. This is an intentional **additive serialization change**;
all existing fields, values and public `execute_facts` parameters are preserved.
IDs are batch-local references, not durable metric/business identifiers or a
promise of the same identity on repeated execution. Facts are output evidence,
not accepted caller-supplied execution inputs.

Checked execution does not certify user intent, source truth, authorization for
arbitrary real data, multilingual quality or generalization. Evaluator cases,
reference SQL and expected answers are never imported by the runtime. Tests may
use them and isolated scenario copies; accepted core data and gold stay frozen.
