# SQLite-first portability plan

SQLite enables fast local fixture iteration; it is not the universal semantic
specification. PostgreSQL is an explicit P4 gate. SQLGlot transpilation and a
SQLite pass do not establish PostgreSQL correctness.

## Logical meaning and physical representation

| Meaning | Initial SQLite fixture | PostgreSQL P4 witness |
| --- | --- | --- |
| Instant | Fixed-format UTC TEXT | timestamptz; exact binding and business-zone buckets |
| Local wall time | Separate tagged variant, NOT implemented yet | timestamp without time zone; no guessed UTC/source zone |
| Calendar date | ISO TEXT variant / target month | date; sub-day requests cannot invent precision |
| Money | INTEGER minor units | bigint and numeric variants; exact arithmetic/rounding |
| Ratio / average | Explicit numerator, denominator, zero/NULL policy | Type promotion/division, numeric and float tolerances |
| IDs / categories | TEXT, stable codes, duplicate names | Quoting, case, Unicode and collation controls |

Introspection must retain physical type/precision plus reviewed logical meaning.
Do not normalize everything into a string or Python float. Parameter binding,
encoding/decoding, dialect details and lifecycle belong in a thin adapter, not
scattered recipe conditionals. Return backend_unsupported rather than silently
changing computation or pretending the user's question is ambiguous.

## Test matrix

| Concern | Present evidence | Planned gate |
| --- | --- | --- |
| Taipei month boundaries | Core UTC-text reference and membership check | PG typed binding and IANA timezone parity, P4 |
| DST / local wall time / date precision | Not implemented or validated | Explicit ambiguous/nonexistent times and typed variants, P4 |
| Exact money | Integer fixture sums; P1.1 exact integer validation and failure on overflow | Numeric precision and rounding, P4 |
| NULL vs zero / empty data | Zero/missing targets and zero-activity center | Aggregation/derived facts in P1/P2; PG parity in P4 |
| Count grain / duplicate rows | SQL ledger and isolated P1.1 scalar-kernel regressions | Broader runtime P2; PG P4 |
| Sort / Top-N ties / collation | Isolated P0 fourth-course/tied-cutoff reference witness; no runtime ranking | Native collation policy and variants, P4 |
| Identifiers / parameter escaping | P1.1 approved identifiers and bound scalar scope values | Broader backend binding, P4 |
| Snapshot / timeout / cancel | P1.1 single read transaction and cooperative SQLite execution budgets | Backend lifecycle, cancellation and hard limits, P4 |

Do not mark a planned row green because SQLite accepted some SQL. Keep
backend-specific native-type fixtures alongside shared logical scenarios.
The reference's `+8 hours` is valid ONLY for this Taipei scenario, not a timezone
implementation. Do not generate PG expectations from the candidate compiler.

## Extension strategy

Use the same logical domain with backend-specific DDL/encoding where needed.
Prefer small explicit profiles over a new type system/optimizer/capability DSL.
Future backends are not promised by a generic adapter interface. Test their
native semantics before admitting a capability.

Primary technical references (design rationale, not test evidence):
- SQLite quirks: https://www.sqlite.org/quirks.html
- SQLite STRICT tables: https://www.sqlite.org/stricttables.html
- PostgreSQL data types: https://www.postgresql.org/docs/current/datatype.html
- PostgreSQL isolation: https://www.postgresql.org/docs/current/transaction-iso.html
