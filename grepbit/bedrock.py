"""Amazon Bedrock Converse adapter with explicit API-key authentication."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hashlib
import json
import logging
import math
from pathlib import Path
import re
from typing import ClassVar
from urllib.parse import quote

import httpx

from .gateway import (
    CALL_TIMEOUT_SECONDS, GatewayClient, GatewayResponse, MAX_INPUT_BYTES,
    MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, ModelError, _env_values,
    json_schema_response_format,
)

ENV_NAMES = ("GREPBIT_BEDROCK_REGION", "GREPBIT_BEDROCK_MODEL_ID",
             "GREPBIT_BEDROCK_API_KEY")
BEDROCK_CALL_TIMEOUT_SECONDS = 300.0
RECIPE_SCHEMA_NAME = "grepbit_recipe_request"
RECIPE_SCHEMA_SHA256 = "a2b842fedc36b77c27d05df8858d6938f67545d9d46e0219a98b8a77ad653f00"
_SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties", "description",
                "const", "enum", "items", "anyOf", "allOf", "oneOf"}
_STRIP_KEYS = {"minLength", "maxLength", "pattern", "minItems", "maxItems",
               "minimum", "maximum"}
BEDROCK_ERROR_BODY_BYTES = 32768
_ERROR_TYPES = frozenset({"ValidationException", "ResourceNotFoundException",
                          "AccessDeniedException", "ThrottlingException",
                          "ModelErrorException"})
_LOGGER = logging.getLogger(__name__)


def _error_type(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    name = value.split(":", 1)[0].rsplit("#", 1)[-1]
    return name if name in _ERROR_TYPES else "unknown"


def _request_id(value: object) -> str:
    if (isinstance(value, str) and re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value)):
        return value
    return "unknown"


def _message_hint(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    message = value.lower()
    if any(term in message for term in ("schema", "outputconfig", "textformat",
                                        "structured output", "grammar")):
        return "structured_output"
    if any(term in message for term in ("inference profile", "model identifier",
                                        "on-demand throughput")):
        return "model_route"
    if any(term in message for term in ("inferenceconfig", "maxtokens", "temperature")):
        return "inference_config"
    return "unknown"


async def _error_body(response: httpx.Response) -> bytes | None:
    if (response.headers.get("content-type", "").split(";")[0].strip().lower()
            != "application/json"
            or response.headers.get("content-encoding", "identity").strip().lower()
            != "identity"):
        return None
    length = response.headers.get("content-length")
    if length is not None and (not length.isascii() or not length.isdecimal()
                               or len(length) > 9 or int(length) > BEDROCK_ERROR_BODY_BYTES):
        return None
    try:
        raw = bytearray()
        async with asyncio.timeout(1.0):
            if response.is_stream_consumed:
                raw.extend(response.content[:BEDROCK_ERROR_BODY_BYTES + 1])
            else:
                async for chunk in response.aiter_raw(chunk_size=2048):
                    raw.extend(chunk)
                    if len(raw) > BEDROCK_ERROR_BODY_BYTES:
                        return None
        if len(raw) > BEDROCK_ERROR_BODY_BYTES:
            return None
    except Exception:
        # Diagnostics cannot change the original HTTP failure classification.
        return None
    return bytes(raw)


@dataclass(frozen=True)
class BedrockConfig:
    max_call_timeout_seconds: ClassVar[float] = BEDROCK_CALL_TIMEOUT_SECONDS
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
    if "const" in node:
        value = node["const"]
        if isinstance(value, list) and set(node) == {"const"} and len(value) == 1 \
                and (value[0] is None or type(value[0]) in (str, int, float, bool)) \
                and (type(value[0]) is not float or math.isfinite(value[0])):
            return {"type": "array", "minItems": 1, "items": {"const": value[0]}}
        if (value is not None and type(value) not in (str, int, float, bool)
                or type(value) is float and not math.isfinite(value)):
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


def _without_descriptions(node: object) -> object:
    if isinstance(node, dict):
        return {key: _without_descriptions(value) for key, value in node.items()
                if key != "description"}
    if isinstance(node, list):
        return [_without_descriptions(value) for value in node]
    return node


def _compact_recipe_schema(schema: dict[str, object]) -> dict[str, object]:
    """Couple each outcome to its required fields; flatten only the clarification alternatives.

    The v4 single-root compaction let the grammar admit a clarify signal on a
    request body, which native validation always rejects (#74). Cross-choice
    rules and the two-to-four choice count remain native.
    """
    try:
        branches = schema["anyOf"]
        if len(branches) != 5:
            raise ValueError
        requests = [(branch["properties"]["recipe_id"]["const"], branch["properties"]["request"])
                    for branch in branches[:3]]
        if [recipe for recipe, _ in requests] != ["overview", "compare", "breakdown"]:
            raise ValueError
        clarification = branches[4]["properties"]["clarification"]["anyOf"]
        if len(clarification) != 4:
            raise ValueError
        kinds = [branch["properties"]["kind"]["const"] for branch in clarification]
        values = [branch["properties"]["choices"]["items"]["properties"]["semantic_value"]
                  for branch in clarification]
    except (KeyError, IndexError, TypeError, ValueError):
        raise ModelError("invalid_input") from None

    def closed(properties: dict[str, object]) -> dict[str, object]:
        return {"type": "object", "additionalProperties": False,
                "required": list(properties), "properties": properties}

    compact = {"anyOf": [
        *[closed({"outcome": {"const": "request"}, "recipe_id": {"const": recipe},
                  "recipe_version": {"const": "0.1"}, "request": shape}) for recipe, shape in requests],
        closed({"outcome": {"const": "declined"}}),
        closed({"outcome": {"const": "clarify"}, "clarification": closed({
            "kind": {"enum": kinds},
            "choices": {"type": "array", "minItems": 1, "items": closed({
                "id": {"type": "string"}, "semantic_value": {"anyOf": values}})},
        })}),
    ]}
    return _without_descriptions(compact)


def converse_schema(constraint: object) -> tuple[dict[str, object], str]:
    wrapper = json_schema_response_format(constraint)
    entry = wrapper["json_schema"]
    schema = _schema_node(entry["schema"])
    if entry["name"] == RECIPE_SCHEMA_NAME:
        canonical = json.dumps(entry["schema"], sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != RECIPE_SCHEMA_SHA256:
            raise ModelError("invalid_input")
        schema = _compact_recipe_schema(schema)
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

    def __init__(self, config: BedrockConfig, *, transport: httpx.AsyncBaseTransport | None = None,
                 error_body_sink: Callable[[bytes], None] | None = None):
        super().__init__(config, transport=transport)
        self.error_body_sink = error_body_sink

    async def _log_bad_request(self, response: httpx.Response) -> None:
        aws_type = _error_type(response.headers.get("x-amzn-errortype"))
        # Emit the useful header data before a slow error body can exhaust the
        # outer call deadline. The body is optional and never logged verbatim.
        _LOGGER.warning("Bedrock HTTP error status=400 aws_type=%s request_id=%s",
                        aws_type, _request_id(response.headers.get("x-amzn-requestid")))
        raw = await _error_body(response)
        if raw is not None and self.error_body_sink is not None:
            try:
                self.error_body_sink(raw)
            except Exception:
                _LOGGER.warning("Bedrock HTTP error private capture failed")
        try:
            body = json.loads(raw) if raw is not None else None
        except Exception:
            # Untrusted provider JSON can also fail through recursion/depth.
            # Parsing diagnostics must never replace the known HTTP 400.
            body = None
        if isinstance(body, dict):
            body_type = _error_type(body.get("__type", body.get("code")))
            hint = _message_hint(body.get("message", body.get("Message")))
            if body_type != "unknown" or hint != "unknown":
                _LOGGER.warning("Bedrock HTTP error detail aws_type=%s message_mentions=%s",
                                body_type if aws_type == "unknown" else aws_type, hint)

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
