"""Neutral active-query cancellation boundary used by application and adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ActiveQueryHandle:
    run_id: str
    cancel_safe: Callable[[], None]


class ActiveQueryLifecyclePort(Protocol):
    def register(self, handle: ActiveQueryHandle) -> None: ...

    def revoke(self, run_id: str, completion_recorded: bool) -> None: ...
