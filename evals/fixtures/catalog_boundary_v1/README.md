# Catalog boundary fixture v1

Entirely fictional, isolated `grepbit_catalog_boundary_v1`, PostgreSQL only.
Two ordinary schemas, five tables. Same-name parents have equal keys but different
labels. A cross-schema TEXT FK must be omitted from the single-schema graph while
remaining a key for sampling/inference policy. The local PK and UNIQUE FK controls
must survive. This is NOT an enabled Web datasource or cross-schema query support.

Setup: create the new database separately, fail if it exists, then use psql with
ON_ERROR_STOP and `schema.sql`. A setup-only local postgres connection performs
DDL/grants. No password/DSN in this fixture; never reseed an existing database.
The runtime uses existing grepbit_ro with only CONNECT, schema USAGE and SELECT.

Run `evals/catalog_boundary.py --dsn-env GREPBIT_CATALOG_DSN --output <fresh.json>`.
It requires this exact fixture database and grepbit_ro, enforces readonly sessions,
uses unmodified production introspection/inference, and never creates objects.
Sampling limit 8 is deliberate **only on these fictional data**, with ordinary
TEXT sampled as a positive control. Do not copy this setting to customer data.
