"""Bounded, read-only request connections, including introspection/literal I/O.

The small proxy checks every SQL/fetch boundary, not just the final executor.
It does not inspect SQL, parameters or rows and never logs connection details.
"""

from __future__ import annotations

import math
from contextlib import contextmanager, nullcontext

import psycopg

from grepbit.application.request_lifecycle import RequestControl


class _Cursor:
    def __init__(self, cursor, control):
        self._cursor, self._control = cursor, control

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)

    def _call(self, name, *args, **kwargs):
        self._control.check()
        result = getattr(self._cursor, name)(*args, **kwargs)
        self._control.check()
        return result

    def execute(self, *args, **kwargs):
        self._call("execute", *args, **kwargs)
        return self

    def fetchmany(self, *args, **kwargs):
        return self._call("fetchmany", *args, **kwargs)

    def fetchone(self):
        return self._call("fetchone")

    def fetchall(self):
        return self._call("fetchall")


class _Connection:
    def __init__(self, connection, control):
        self._connection, self._control = connection, control

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def cursor(self, *args, **kwargs):
        self._control.check()
        return _Cursor(self._connection.cursor(*args, **kwargs), self._control)

    def execute(self, *args, **kwargs):
        return self.cursor().execute(*args, **kwargs)


@contextmanager
def request_connection(dsn: str, control: RequestControl | None = None):
    left = control.remaining(5) if control else 5
    timeout_ms = max(1, int((control.remaining(10) if control else 10) * 1000))
    with psycopg.connect(
        dsn,
        connect_timeout=max(1, math.ceil(left)),
        application_name=f"grepbit:{control.run_id}" if control else "grepbit",
        options=(
            "-c default_transaction_read_only=on "
            f"-c statement_timeout={timeout_ms} "
            "-c idle_in_transaction_session_timeout=10000"
        ),
    ) as connection:
        manager = (
            control.cancellable(lambda: connection.cancel_safe(timeout=1))
            if control
            else nullcontext()
        )
        with manager:
            yield _Connection(connection, control) if control else connection
