"""OpenAI-compatible embeddings transport with model-specific prompt formats."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from grepbit.adapters.litellm.grounding_client import (
    BASE_URL_ENV,
    DEFAULT_CREDENTIAL_ENV,
)
from grepbit.ports.embedding import EmbeddingKind, EmbeddingModelError, EmbeddingPort

EMBEDDING_BASE_URL_ENV = "GREPBIT_EMBEDDING_BASE_URL"
EMBEDDING_MODEL_ENV = "GREPBIT_EMBEDDING_MODEL"
EMBEDDING_CREDENTIAL_ENV_NAME_ENV = "GREPBIT_EMBEDDING_CREDENTIAL_ENV"
EMBEDDING_TIMEOUT_ENV = "GREPBIT_EMBEDDING_TIMEOUT_SECONDS"
EMBEDDING_PROMPT_FORMAT_ENV = "GREPBIT_EMBEDDING_PROMPT_FORMAT"
EMBEDDING_INSTRUCTION_ENV = "GREPBIT_EMBEDDING_INSTRUCTION"
EMBEDDING_BATCH_SIZE_ENV = "GREPBIT_EMBEDDING_BATCH_SIZE"

PromptFormat = Literal["embeddinggemma", "instruct", "none"]
DEFAULT_INSTRUCTION = (
    "Given an enterprise search query, retrieve relevant documents that answer "
    "the query"
)


@dataclass(frozen=True)
class EmbeddingModelSettings:
    base_url: str
    model: str
    credential_env_var: str = DEFAULT_CREDENTIAL_ENV
    timeout_seconds: float = 30.0
    prompt_format: PromptFormat = "embeddinggemma"
    instruction: str = DEFAULT_INSTRUCTION
    batch_size: int = 32

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> EmbeddingModelSettings:
        source = os.environ if environ is None else environ
        model = source.get(EMBEDDING_MODEL_ENV, "").strip()
        base_url = (
            source.get(EMBEDDING_BASE_URL_ENV, "").strip()
            or source.get(BASE_URL_ENV, "").strip()
        )
        if not model or not base_url:
            raise EmbeddingModelError("embedding_settings_missing")
        prompt_format = source.get(
            EMBEDDING_PROMPT_FORMAT_ENV, "embeddinggemma"
        ).strip()
        if prompt_format not in {"embeddinggemma", "instruct", "none"}:
            raise EmbeddingModelError("embedding_settings_missing")
        try:
            return cls(
                base_url=base_url,
                model=model,
                credential_env_var=source.get(
                    EMBEDDING_CREDENTIAL_ENV_NAME_ENV, DEFAULT_CREDENTIAL_ENV
                ).strip()
                or DEFAULT_CREDENTIAL_ENV,
                timeout_seconds=float(source.get(EMBEDDING_TIMEOUT_ENV, "30")),
                prompt_format=prompt_format,  # type: ignore[arg-type]
                instruction=source.get(EMBEDDING_INSTRUCTION_ENV, DEFAULT_INSTRUCTION),
                batch_size=int(source.get(EMBEDDING_BATCH_SIZE_ENV, "32")),
            )
        except ValueError:
            raise EmbeddingModelError("embedding_settings_missing") from None

    @property
    def revision(self) -> str:
        return f"{self.model}|{self.prompt_format}"

    def format(self, text: str, kind: EmbeddingKind) -> str:
        """Apply the prompt the model was trained with; documents never get titles."""

        if self.prompt_format == "embeddinggemma":
            if kind == "query":
                return f"task: search result | query: {text}"
            return f"title: none | text: {text}"
        if self.prompt_format == "instruct":
            if kind == "query":
                return f"Instruct: {self.instruction}\nQuery: {text}"
            return text
        return text


ClientFactory = Callable[[EmbeddingModelSettings], Any]


class OpenAICompatibleEmbeddings(EmbeddingPort):
    def __init__(
        self,
        settings: EmbeddingModelSettings,
        *,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._client_factory = client_factory

    @property
    def revision(self) -> str:
        return self._settings.revision

    @property
    def settings(self) -> EmbeddingModelSettings:
        return self._settings

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        if not texts:
            return []
        client = self._client or self._create_client()
        formatted = [self._settings.format(text, kind) for text in texts]
        vectors: list[list[float]] = []
        size = max(1, self._settings.batch_size)
        for start in range(0, len(formatted), size):
            vectors.extend(self._embed_batch(client, formatted[start : start + size]))
        dimensions = {len(vector) for vector in vectors}
        if len(vectors) != len(texts) or len(dimensions) != 1:
            raise EmbeddingModelError("invalid_embedding_output")
        return vectors

    def _embed_batch(self, client: Any, batch: list[str]) -> list[list[float]]:
        try:
            response = client.embeddings.create(
                model=self._settings.model, input=batch, encoding_format="float"
            )
        except Exception:
            raise EmbeddingModelError("embedding_call_failed") from None
        try:
            items = sorted(response.data, key=lambda item: item.index)
            vectors = [[float(value) for value in item.embedding] for item in items]
        except (AttributeError, TypeError, ValueError):
            raise EmbeddingModelError("invalid_embedding_output") from None
        if len(vectors) != len(batch) or any(not vector for vector in vectors):
            raise EmbeddingModelError("invalid_embedding_output")
        return vectors

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(self._settings)
        credential = os.environ.get(self._settings.credential_env_var)
        if not credential:
            raise EmbeddingModelError("credential_unavailable")
        try:
            from openai import OpenAI
        except ImportError:
            raise EmbeddingModelError("openai_sdk_unavailable") from None
        return OpenAI(
            api_key=credential,
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
            max_retries=0,
        )
