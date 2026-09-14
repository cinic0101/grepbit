"""One invocation's cooperative deadline and active-resource cancellation.

Explicitly passed to request-owned adapters, never stored in a global context.
A stopped worker may finish a blocking call, but cannot start another stage.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Lock
from uuid import uuid4


class RequestStopped(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RequestControl:
    def __init__(self, seconds: float, *, clock: Callable[[], float] = time.monotonic):
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("request_timeout_must_be_finite_positive")
        self.run_id = uuid4().hex
        self._clock = clock
        self._deadline = clock() + seconds
        self._lock = Lock()
        self._reason: str | None = None
        self._finished = False
        self._cancel: Callable[[], None] | None = None

    def remaining(self, cap: float | None = None) -> float:
        with self._lock:
            left = self._deadline - self._clock()
            if self._reason is None and left <= 0:
                self._reason = "request_timeout"
            if self._reason:
                raise RequestStopped(self._reason)
            return left if cap is None else min(left, cap)

    def check(self) -> None:
        self.remaining()

    def stop(self, reason: str) -> Callable[[], None] | None:
        """Mark stopped now; caller runs returned I/O callback outside the lock."""
        with self._lock:
            if self._finished:
                return None
            self._reason = self._reason or reason
            callback, self._cancel = self._cancel, None
            return callback

    @contextmanager
    def cancellable(self, cancel: Callable[[], None]) -> Iterator[None]:
        self.check()
        with self._lock:
            if self._reason:
                raise RequestStopped(self._reason)
            if self._cancel is not None:
                raise RuntimeError("overlapping_request_resources")
            self._cancel = cancel
        try:
            self.check()
            yield
            self.check()
        finally:
            with self._lock:
                if self._cancel is cancel:
                    self._cancel = None

    def finish(self) -> None:
        with self._lock:
            if self._reason is None and self._clock() >= self._deadline:
                self._reason = "request_timeout"
            if self._reason:
                raise RequestStopped(self._reason)
            self._finished = True
