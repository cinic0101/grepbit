-- Setup only in the newly created isolated database, never in a customer DB.
\set ON_ERROR_STOP on
SELECT current_database() = 'grepbit_catalog_boundary_v1' AS correct_database \gset
\if :correct_database
\else
\quit 3
\endif
BEGIN;
CREATE SCHEMA a;
CREATE SCHEMA b;
CREATE TABLE b.parent (id text PRIMARY KEY, label text NOT NULL);
CREATE TABLE a.parent (id text PRIMARY KEY, label text NOT NULL);
CREATE TABLE a.child (
    id integer PRIMARY KEY,
    parent_id text REFERENCES b.parent(id),
    note text
);
CREATE TABLE a.local_parent (id integer PRIMARY KEY, code text UNIQUE, label text);
CREATE TABLE a.normal_child (
    id integer PRIMARY KEY,
    local_parent_id integer REFERENCES a.local_parent(id),
    code text REFERENCES a.local_parent(code),
    note text
);
INSERT INTO b.parent VALUES ('x', 'actual-x'), ('y', 'actual-y');
INSERT INTO a.parent VALUES ('x', 'decoy-x'), ('y', 'decoy-y');
INSERT INTO a.child VALUES (1, 'x', 'alpha'), (2, 'y', 'beta'), (3, NULL, 'alpha');
INSERT INTO a.local_parent VALUES (10, 'p', 'local-p'), (20, 'q', 'local-q');
INSERT INTO a.normal_child VALUES (1, 10, 'p', 'gamma'), (2, 20, 'q', 'delta');
GRANT CONNECT ON DATABASE grepbit_catalog_boundary_v1 TO grepbit_ro;
GRANT USAGE ON SCHEMA a, b TO grepbit_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA a, b TO grepbit_ro;
COMMIT;
