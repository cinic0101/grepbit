"""Explicit provider selection for the shared one-call LLM application boundary."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

import httpx

from .bedrock import BedrockClient, BedrockConfig, converse_schema, normalize_converse_response
from .gateway import (GatewayClient, GatewayConfig, GatewayResponse, ModelError,
                      _env_values)

PROVIDER_NAME = "GREPBIT_LLM_PROVIDER"


class LLMClient(Protocol):
    config: GatewayConfig | BedrockConfig
    http_attempts: int

    async def complete(self, messages: list[dict[str, str]], *, timeout_seconds: float,
                       json_schema_constraint: dict[str, object] | None = None) -> GatewayResponse: ...

    def safe_export(self, data: dict[str, object]) -> dict[str, object]: ...


def response_mode(config: GatewayConfig | BedrockConfig) -> str:
    return ("bedrock_converse_normalized" if isinstance(config, BedrockConfig)
            else "json_content")


def wire_identity(config: GatewayConfig | BedrockConfig,
                  constraint: dict[str, object], identity: dict[str, str]) -> dict[str, str]:
    if isinstance(config, BedrockConfig):
        _, wire_hash = converse_schema(constraint)
        return {**identity, "provider": "bedrock_converse", "wire_schema_sha256": wire_hash}
    return identity


def normalize_response(config: GatewayConfig | BedrockConfig,
                       response: GatewayResponse) -> GatewayResponse:
    return normalize_converse_response(response) if isinstance(config, BedrockConfig) else response


def client_from_env(*, environ: Mapping[str, str] | None = None,
                    env_file: Path | None = None,
                    transport: httpx.AsyncBaseTransport | None = None,
                    bedrock_error_body_sink: Callable[[bytes], None] | None = None) -> LLMClient:
    """No implicit file, network, provider fallback, or ambient AWS discovery."""
    selected = _env_values((PROVIDER_NAME,), environ=environ, env_file=env_file)
    provider = selected.get(PROVIDER_NAME, "litellm")
    if provider == "litellm":
        if bedrock_error_body_sink is not None:
            raise ModelError("invalid_configuration")
        return GatewayClient(GatewayConfig.from_env(environ=environ, env_file=env_file),
                             transport=transport)
    if provider == "bedrock_converse":
        return BedrockClient(BedrockConfig.from_env(environ=environ, env_file=env_file),
                             transport=transport, error_body_sink=bedrock_error_body_sink)
    raise ModelError("invalid_configuration")
