from __future__ import annotations

import pytest

from grepbit.adapters.sqlglot.policy import PostgresSqlPolicy


def policy_checker() -> object:
    policy = PostgresSqlPolicy()
    checker = getattr(policy, "assert_safe_select_statement", None)
    if not callable(checker):
        pytest.fail(
            "SQL policy contract requires "
            "PostgresSqlPolicy.assert_safe_select_statement"
        )
    return checker


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT customer_id FROM public.customers WHERE customer_id = %(customer_id)s",
        "WITH monthly_revenue AS ("
        "SELECT customer_id, SUM(gross_amount) AS revenue "
        "FROM public.orders GROUP BY customer_id"
        ") SELECT customer_id, revenue FROM monthly_revenue",
    ],
)
def test_sql_policy_accepts_only_complete_allowed_select_shapes(sql: str) -> None:
    checked_sql = policy_checker()(sql)
    assert isinstance(checked_sql, str)


def test_sql_policy_preserves_named_bindings_through_inspection() -> None:
    sql = "SELECT customer_id FROM public.customers WHERE customer_id = %(customer_id)s"
    checked_sql = policy_checker()(sql)
    assert "%(customer_id)s" in checked_sql


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO public.orders VALUES ('o999')",
        "CREATE TABLE public.unapproved_table (id integer)",
        "COPY public.orders TO STDOUT",
        "CALL public.unsafe_procedure()",
        "BEGIN",
        "LOCK TABLE public.orders IN ACCESS EXCLUSIVE MODE",
        "WITH changed AS (DELETE FROM public.orders RETURNING *) SELECT * FROM changed",
        "WITH RECURSIVE orders AS (SELECT 1 AS n UNION ALL "
        "SELECT n + 1 FROM orders) SELECT * FROM orders",
        "SELECT customer_id INTO temporary_copy FROM public.customers",
        "SELECT * FROM pg_catalog.pg_roles",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM public.unapproved_table",
        "SELECT * FROM other_schema.orders",
        "SELECT * FROM orders",
        "SELECT pg_sleep(1)",
        "SELECT set_config('app.role', 'admin', false)",
        "SELECT nextval('public.orders_order_id_seq')",
        "SELECT pg_notify('channel', 'payload')",
        "SELECT pg_terminate_backend(1)",
        "SELECT lo_import('/tmp/file')",
        "SELECT dblink_connect('host=example.test')",
        "SELECT unknown_network_function()",
    ],
)
def test_sql_policy_fails_closed_for_unapproved_statements_objects_and_functions(
    sql: str,
) -> None:
    with pytest.raises(ValueError):
        policy_checker()(sql)
