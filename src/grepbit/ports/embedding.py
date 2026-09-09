"""Provider-neutral text embedding boundary used for candidate retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

EmbeddingKind = Literal["query", "document"]
_EMBEDDING_ERROR_CODES = frozenset(
    {
        "credential_unavailable",
        "embedding_settings_missing",
        "embedding_call_failed",
        "invalid_embedding_output",
        "openai_sdk_unavailable",
    }
)


class EmbeddingModelError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in _EMBEDDING_ERROR_CODES:
            raise ValueError("embedding_error_code_invalid")
        super().__init__(code)
        self.code = code


class EmbeddingPort(Protocol):
    @property
    def revision(self) -> str:
        """Model plus prompt format; a change invalidates thresholds and indexes."""
        ...

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        """Return one vector per text, in input order, all of one dimension."""
        ...
