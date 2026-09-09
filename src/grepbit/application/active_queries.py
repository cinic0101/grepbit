"""In-process registry of running physical queries, for cancellation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from grepbit.ports.active_query_lifecycle import ActiveQueryHandle


@dataclass(frozen=True)
class CancellationResult:
    status: Literal["cancelled", "already_completed", "not_found"]


class ActiveQueryRegistry:
    """Implements ActiveQueryLifecyclePort; safe to share across threads."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: dict[str, ActiveQueryHandle] = {}
        self._cancelled: set[str] = set()
        self._completed: set[str] = set()

    def register(self, handle: ActiveQueryHandle) -> None:
        cancel_safe: Callable[[], None] | None = None
        with self._lock:
            self._active[handle.run_id] = handle
            self._completed.discard(handle.run_id)
            if handle.run_id in self._cancelled:
                cancel_safe = handle.cancel_safe
        if cancel_safe is not None:
            cancel_safe()

    def revoke(self, run_id: str, completion_recorded: bool) -> None:
        with self._lock:
            self._active.pop(run_id, None)
            if completion_recorded:
                self._completed.add(run_id)

    def cancel(self, run_id: str) -> CancellationResult:
        with self._lock:
            if run_id in self._completed:
                return CancellationResult(status="already_completed")
            handle = self._active.get(run_id)
            if handle is None:
                return CancellationResult(status="not_found")
            if run_id in self._cancelled:
                return CancellationResult(status="cancelled")
            self._cancelled.add(run_id)
        handle.cancel_safe()
        return CancellationResult(status="cancelled")

    def is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._cancelled
