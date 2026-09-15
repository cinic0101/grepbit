"""Readonly acceptance of the isolated, real PostgreSQL catalog fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from grepbit.adapters.postgres.introspect import infer_foreign_keys, introspect_schema
from grepbit.application.policies import propose_policies

FIXTURE_DATABASE = "grepbit_catalog_boundary_v1"


def verify_catalog(connect):
    """No query replacement, catalog mock, injected containment or setup rights."""
    with connect() as con:
        database, role, readonly = con.execute(
            "SELECT current_database(), current_user, "
            "current_setting('transaction_read_only')"
        ).fetchone()
        assert (database, role, readonly) == (FIXTURE_DATABASE, "grepbit_ro", "on")
        assert con.execute(
            "SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole) "
            "FROM pg_roles WHERE rolname = current_user"
        ).fetchone() == (True,)
        assert con.execute(
            "SELECT has_database_privilege(current_user,current_database(),'CREATE'), "
            "has_schema_privilege(current_user,'a','CREATE'), "
            "has_schema_privilege(current_user,'b','CREATE'), "
            "has_table_privilege(current_user,'a.child','INSERT,UPDATE,DELETE')"
        ).fetchone() == (False, False, False, False)
        physical = con.execute(
            "SELECT n.nspname, c.relname, rn.nspname, rc.relname "
            "FROM pg_constraint f JOIN pg_class c ON c.oid=f.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_class rc ON rc.oid=f.confrelid "
            "JOIN pg_namespace rn ON rn.oid=rc.relnamespace "
            "WHERE f.contype='f' AND n.nspname='a' AND c.relname='child'"
        ).fetchall()
        assert physical == [("a", "child", "b", "parent")]
        decoy = con.execute(
            "SELECT actual.label, decoy.label FROM a.child c "
            "JOIN b.parent actual ON actual.id=c.parent_id "
            "JOIN a.parent decoy ON decoy.id=c.parent_id ORDER BY c.id"
        ).fetchall()
        assert decoy == [("actual-x", "decoy-x"), ("actual-y", "decoy-y")]

    source = introspect_schema(
        connect,
        datasource_id="catalog_boundary",
        schema_name="a",
        enum_distinct_limit=8,
    )
    assert {t.name for t in source.tables} == {
        "child",
        "parent",
        "local_parent",
        "normal_child",
    }
    assert not source.parent_links("child")
    child = source.table("child")
    assert child.foreign_key_columns == ["parent_id"]
    assert child.column("parent_id").sample_values == []
    assert child.column("parent_id").distinct_estimate is None
    assert set(child.column("note").sample_values) == {"alpha", "beta"}
    expected = {
        ("local_parent_id", "local_parent", "id"),
        ("code", "local_parent", "code"),
    }
    assert {
        (f.column, f.referenced_table, f.referenced_column)
        for f in source.parent_links("normal_child")
    } == expected
    assert source.table("normal_child").column("code").sample_values == []
    policies = propose_policies(source)
    assert next(p for p in policies if p.column.id == "child.parent_id").ground is False
    inferred = infer_foreign_keys(connect, source)
    assert not inferred.parent_links("child")
    assert inferred.foreign_keys == source.foreign_keys

    # Discriminating control: removing only the raw-key protection from an
    # in-memory copy must expose the tempting but wrong local containment link.
    missing_key = source.model_copy(deep=True)
    missing_key.table("child").foreign_key_columns = []
    mutant = infer_foreign_keys(connect, missing_key)
    links = mutant.parent_links("child")
    assert (
        len(links) == 1 and links[0].referenced_table == "parent" and links[0].inferred
    )
    return {
        "runtime_role": role,
        "readonly": True,
        "physical_cross_schema_fk": physical,
        "cross_schema_edge_omitted": True,
        "raw_text_key_retained_unsampled": True,
        "ordinary_text_sampled": True,
        "pk_and_unique_links_preserved": True,
        "key_not_groundable": True,
        "inference_does_not_recreate_decoy": True,
        "missing_key_mutant_infers_decoy": True,
        "decoy_has_different_values": True,
        "schema_digest": source.digest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn-env", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    dsn = os.environ[args.dsn_env]
    reports = []
    for path in ("a,b", "b,a"):

        def connect():
            return psycopg.connect(
                dsn,
                connect_timeout=5,
                options=f"-c default_transaction_read_only=on -c search_path={path}",
            )

        reports.append({"search_path": path, **verify_catalog(connect)})
    assert reports[0]["schema_digest"] == reports[1]["schema_digest"]
    result = {
        "at": datetime.now(UTC).isoformat(),
        "database": FIXTURE_DATABASE,
        "physical_model_calls": 0,
        "runtime_writes": False,
        "reports": reports,
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
    print("CATALOG_BOUNDARY_PASS paths=2 model_calls=0 runtime_writes=false")


if __name__ == "__main__":
    main()
