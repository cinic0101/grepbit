"""Amazon Bedrock Converse adapter with explicit API-key authentication."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

import httpx

from .gateway import (
    CALL_TIMEOUT_SECONDS, GatewayClient, GatewayResponse, MAX_INPUT_BYTES,
    MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, ModelError, _env_values,
    json_schema_response_format,
)

ENV_NAMES = ("GREPBIT_BEDROCK_REGION", "GREPBIT_BEDROCK_MODEL_ID",
             "GREPBIT_BEDROCK_API_KEY")
_SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties", "description",
                "const", "enum", "items", "anyOf", "allOf", "oneOf"}
_STRIP_KEYS = {"minLength", "maxLength", "pattern", "minItems", "maxItems",
               "minimum", "maximum"}


@dataclass(frozen=True)
class BedrockConfig:
    region: str
    model: str
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.region) is not str
                or re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-[1-9][0-9]*", self.region) is None
                or type(self.model) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.model) is None
                or type(self.api_key) is not str or not 1 <= len(self.api_key) <= 4096
                or any(not 33 <= ord(c) <= 126 for c in self.api_key)):
            raise ModelError("invalid_configuration")

    @property
    def base_url(self) -> str:
        return f"https://bedrock-runtime.{self.region}.amazonaws.com"

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/model/{quote(self.model, safe='.:-')}/converse"

    @property
    def transport_security(self) -> str:
        return "tls_verification_enabled"

    @property
    def expected_model(self) -> None:
        # Converse does not return an observed model ID. Never invent one.
        return None

    @classmethod
    def from_env(cls, *, environ: Mapping[str, str] | None = None,
                 env_file: Path | None = None) -> BedrockConfig:
        values = _env_values(ENV_NAMES, environ=environ, env_file=env_file)
        return cls(*(values.get(name, "") for name in ENV_NAMES))


def _schema_node(node: object) -> dict[str, object]:
    """Translate only the accepted schema subset; unknown keywords fail closed."""
    if not isinstance(node, dict) or not node or set(node) - _SCHEMA_KEYS - _STRIP_KEYS:
        raise ModelError("invalid_input")
    if ("oneOf" in node and "anyOf" in node
            or "additionalProperties" in node and node["additionalProperties"] is not False):
        raise ModelError("invalid_input")
    result: dict[str, object] = {}
    for key, value in node.items():
        if key in _STRIP_KEYS:
            continue
        if key == "properties":
            if not isinstance(value, dict) or not value:
                raise ModelError("invalid_input")
            result[key] = {name: _schema_node(child) for name, child in value.items()}
        elif key == "items":
            result[key] = _schema_node(value)
        elif key in ("oneOf", "anyOf", "allOf"):
            if not isinstance(value, list) or not value:
                raise ModelError("invalid_input")
            result["anyOf" if key == "oneOf" else key] = [_schema_node(child) for child in value]
        else:
            result[key] = value
    return result


def converse_schema(constraint: object) -> tuple[dict[str, object], str]:
    wrapper = json_schema_response_format(constraint)
    entry = wrapper["json_schema"]
    schema = _schema_node(entry["schema"])
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return ({"type": "json_schema", "structure": {"jsonSchema": {
        "name": entry["name"], "schema": canonical,
    }}}, hashlib.sha256(canonical.encode("utf-8")).hexdigest())


def _normalize_converse(body: bytes) -> bytes:
    # Import lazily so the common content parser does not depend on this adapter.
    from .model import strict_json

    data = strict_json(body, code="invalid_response")
    if not isinstance(data, dict):
        raise ModelError("invalid_response")
    stop = data.get("stopReason")
    if stop == "max_tokens":
        raise ModelError("truncated_output")
    if stop != "end_turn":
        raise ModelError("unsupported_output")
    output = data.get("output")
    message = output.get("message") if isinstance(output, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or not isinstance(content, list) or len(content) != 1
            or not isinstance(content[0], dict) or set(content[0]) != {"text"}
            or not isinstance(content[0]["text"], str)):
        raise ModelError("unsupported_output")
    raw_usage = data.get("usage")
    if not isinstance(raw_usage, dict):
        raise ModelError("invalid_response")
    usage = {}
    for source, target in (("inputTokens", "prompt_tokens"),
                           ("outputTokens", "completion_tokens"),
                           ("totalTokens", "total_tokens")):
        value = raw_usage.get(source)
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise ModelError("invalid_response")
        usage[target] = value
    normalized = {"choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": content[0]["text"],
    }}], "usage": usage}
    result = json.dumps(normalized, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(result) > MAX_RESPONSE_BYTES:
        raise ModelError("response_too_large")
    return result


def normalize_converse_response(response: GatewayResponse) -> GatewayResponse:
    try:
        normalized = _normalize_converse(response.body)
    except ModelError as exc:
        raise ModelError(exc.code, http_status=response.status_code) from None
    return GatewayResponse(normalized, response.status_code)


class BedrockClient(GatewayClient):
    """Converse uses the shared transport, with separate request and response rules."""

    response_mode = "bedrock_converse_normalized"

    def __init__(self, config: BedrockConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(config, transport=transport)

    async def complete(self, messages: list[dict[str, str]], *,
                       timeout_seconds: float = CALL_TIMEOUT_SECONDS,
                       json_schema_constraint: dict[str, object] | None = None) -> GatewayResponse:
        self._validate_call(messages, timeout_seconds)
        # Inspect the schema tree before its JSON string encoding can escape a
        # private key or property name beyond safe_export's literal matching.
        canonical_format = (json_schema_response_format(json_schema_constraint)
                            if json_schema_constraint is not None else None)
        self._validate_private(messages, canonical_format)
        payload: dict[str, object] = {
            "system": [{"text": messages[0]["content"]}],
            "messages": [{"role": "user", "content": [{"text": messages[1]["content"]}]}],
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0},
        }
        if json_schema_constraint is not None:
            payload["outputConfig"] = {"textFormat": converse_schema(json_schema_constraint)[0]}
        try:
            question_size = len(messages[1]["content"].encode("utf-8"))
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ModelError("invalid_input") from None
        if question_size > MAX_INPUT_BYTES or len(body) > MAX_REQUEST_BYTES:
            raise ModelError("input_too_large")
        self._validate_private(messages, payload.get("outputConfig"))
        return await self._post_json(body, timeout_seconds)
