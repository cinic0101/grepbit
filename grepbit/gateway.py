"""Explicit local-gateway configuration and one bounded, stateless HTTP attempt."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import io
import json
import logging
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from dotenv.parser import parse_stream
import httpx

MODEL = "gemma-4-31b"
MAX_INPUT_BYTES = 4096
MAX_REQUEST_BYTES = 32768
MAX_RESPONSE_BYTES = 131072
CALL_TIMEOUT_SECONDS = 60.0
ENV_NAMES = (
    "GREPBIT_LITELLM_BASE_URL", "GREPBIT_LITELLM_API_KEY", "GREPBIT_LITELLM_MODEL",
)

# Codes, stages and stopping classifications are application-owned, never error text.
_ERRORS = {
    "invalid_configuration": ("configuration", "configuration_failure", False),
    "invalid_input": ("configuration", "configuration_failure", False),
    "constraint_conflict": ("request_validation", None, False),
    "input_too_large": ("configuration", "budget_exhausted", False),
    "response_too_large": ("response_validation", "budget_exhausted", False),
    "output_token_budget": ("response_validation", "budget_exhausted", False),
    "auth_failed": ("transport", "configuration_failure", False),
    "http_configuration": ("transport", "configuration_failure", False),
    "redirect_blocked": ("transport", "configuration_failure", False),
    "rate_limited": ("transport", None, True),
    "gateway_error": ("transport", None, True),
    "transport_error": ("transport", None, True),
    "timeout": ("transport", None, True),
    "invalid_response": ("response_validation", "envelope_incompatibility", False),
    "unexpected_model": ("response_validation", "configuration_failure", False),
    "unsupported_output": ("response_validation", "envelope_incompatibility", False),
    "truncated_output": ("response_validation", "budget_exhausted", False),
    "invalid_json": ("json_parse", None, False),
    "invalid_request": ("request_validation", None, False),
    "model_declined": ("request_validation", None, False),
    "kernel_failure": ("kernel_execution", None, False),
    "source_failure": ("kernel_execution", "configuration_failure", False),
    "budget_exhausted": ("kernel_execution", "budget_exhausted", False),
}


class ModelError(Exception):
    """Safe fixed-code failure; no response bodies, headers, URLs or exception causes."""

    def __init__(self, code: str, *, http_status: int | None = None):
        self.stage, self.stop_reason, self.transport_failure = _ERRORS[code]
        self.code = code
        self.http_status = http_status
        super().__init__(f"Model integration failed: {code}.")


def json_schema_response_format(constraint: object) -> dict[str, object]:
    """One closed JSON-schema wrapper, not a provider-parameter passthrough."""
    if (not isinstance(constraint, dict) or set(constraint) != {"name", "schema"}
            or not isinstance(constraint["name"], str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", constraint["name"]) is None
            or not isinstance(constraint["schema"], dict) or not constraint["schema"]):
        raise ModelError("invalid_input")
    chunks, size = [], 0
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False).iterencode(constraint["schema"]):
            size += len(chunk.encode("utf-8"))
            if size > MAX_REQUEST_BYTES:
                raise ModelError("input_too_large")
            chunks.append(chunk)
        schema = json.loads("".join(chunks))
        # Reject JSON coercions such as non-string keys or tuple-valued arrays.
        if schema != constraint["schema"]:
            raise ModelError("invalid_input")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ModelError("invalid_input") from None
    return {"type": "json_schema", "json_schema": {"name": constraint["name"], "schema": schema}}


@dataclass(frozen=True)
class GatewayConfig:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    model: str = MODEL

    def __post_init__(self) -> None:
        try:
            if (not isinstance(self.base_url, str) or not 1 <= len(self.base_url) <= 2048
                    or any(ord(c) <= 32 or ord(c) == 127 for c in self.base_url)
                    or not isinstance(self.api_key, str) or not 1 <= len(self.api_key) <= 4096
                    or any(not 33 <= ord(c) <= 126 for c in self.api_key)
                    or self.model != MODEL):
                raise ValueError
            url = urlsplit(self.base_url)
            if (url.scheme not in ("http", "https") or not url.hostname
                    or url.username is not None or url.password is not None
                    or url.query or url.fragment or url.port == 0
                    or url.path.count("/chat/completions") > 1):
                raise ValueError
            httpx.URL(self.endpoint)
        except (ValueError, UnicodeError, httpx.InvalidURL):
            raise ModelError("invalid_configuration") from None

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else base + "/chat/completions"

    @property
    def transport_security(self) -> str:
        return ("tls_verification_enabled" if urlsplit(self.base_url).scheme == "https"
                else "unencrypted_http")

    @classmethod
    def from_env(cls, *, environ: Mapping[str, str] | None = None,
                 env_file: Path | None = None) -> GatewayConfig:
        values: dict[str, str] = {}
        if env_file is not None:
            try:
                with env_file.open("rb") as stream:
                    raw = stream.read(16385)
                if len(raw) > 16384:
                    raise ValueError
                for binding in parse_stream(io.StringIO(raw.decode("utf-8"))):
                    if binding.error:
                        raise ValueError
                    if binding.key in ENV_NAMES:
                        if binding.key in values or binding.value is None:
                            raise ValueError
                        values[binding.key] = binding.value
            except (OSError, ValueError, UnicodeError):
                raise ModelError("invalid_configuration") from None
        source = os.environ if environ is None else environ
        for name in ENV_NAMES:
            if name in source:
                values[name] = source[name]
        return cls(values.get(ENV_NAMES[0], ""), values.get(ENV_NAMES[1], ""),
                   values.get(ENV_NAMES[2], MODEL))


_PRIVATE_TRANSPORT: ContextVar[bool] = ContextVar("grepbit_private_transport", default=False)


class _PrivateTransportFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Resolver diagnostics run without our context and may finish after timeout.
        # Keep this narrow stdlib origin suppressed for the rest of the process.
        if (record.name == "asyncio" and record.module == "base_events"
                and record.funcName == "_getaddrinfo_debug"):
            return False
        return not _PRIVATE_TRANSPORT.get()


_PRIVATE_FILTER = _PrivateTransportFilter()


@contextmanager
def _private_transport_logs():
    # Retain filters after exit: executor DNS diagnostics can arrive late.
    names = {"asyncio", "httpx", "httpcore", "httpcore.connection", "httpcore.http11", "httpcore.http2",
             "httpcore.proxy", "httpcore.socks"}
    names.update(name for name in tuple(logging.Logger.manager.loggerDict)
                 if name.startswith(("httpx.", "httpcore.")))
    for name in names:
        logger = logging.getLogger(name)
        if _PRIVATE_FILTER not in logger.filters:
            logger.addFilter(_PRIVATE_FILTER)
    token = _PRIVATE_TRANSPORT.set(True)
    try:
        yield
    finally:
        _PRIVATE_TRANSPORT.reset(token)


@dataclass(frozen=True, repr=False)
class GatewayResponse:
    body: bytes
    status_code: int


class GatewayClient:
    """No constructor/import probes, session history, cookies, retries or fallback."""

    def __init__(self, config: GatewayConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self._transport = transport
        self.http_attempts = 0

    def safe_export(self, data: dict[str, object]) -> dict[str, object]:
        url = urlsplit(self.config.base_url)
        canonical = httpx.URL(self.config.endpoint)
        fragments = (self.config.api_key, self.config.base_url.rstrip("/"),
                     self.config.endpoint)
        # A short local hostname must not match letters inside ordinary words.
        addresses = [
            re.compile(r"(?<![\w-])" + re.escape(part) + r"(?![\w-])", re.IGNORECASE)
            for part in {url.netloc, url.hostname, canonical.netloc.decode("ascii"),
                         canonical.raw_host.decode("ascii")} if part
        ]

        def clean(value: object) -> object:
            if isinstance(value, str):
                private = (any(part in value for part in fragments)
                           or any(pattern.search(value) for pattern in addresses))
                return "[redacted]" if private else value
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [clean(item) for item in value]
            return value

        return {key: clean(value) for key, value in data.items()}

    async def complete(self, messages: list[dict[str, str]], *,
                       timeout_seconds: float = CALL_TIMEOUT_SECONDS,
                       json_schema_constraint: dict[str, object] | None = None) -> GatewayResponse:
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= CALL_TIMEOUT_SECONDS):
            raise ModelError("invalid_configuration")
        if (not isinstance(messages, list) or len(messages) != 2
                or any(not isinstance(m, dict) or set(m) != {"role", "content"}
                       or not isinstance(m["content"], str) for m in messages)
                or [m["role"] for m in messages] != ["system", "user"]):
            raise ModelError("invalid_input")
        payload: dict[str, object] = {
            "model": self.config.model, "messages": messages,
            "temperature": 0, "max_tokens": 2048, "stream": False,
        }
        if json_schema_constraint is not None:
            payload["response_format"] = json_schema_response_format(json_schema_constraint)
        try:
            question_size = len(messages[1]["content"].encode("utf-8"))
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ModelError("invalid_input") from None
        if not messages[1]["content"].strip():
            raise ModelError("invalid_input")
        if question_size > MAX_INPUT_BYTES or len(body) > MAX_REQUEST_BYTES:
            raise ModelError("input_too_large")
        if self.safe_export({"messages": messages})["messages"] != messages:
            raise ModelError("invalid_input")
        if json_schema_constraint is not None:
            pending, names = [payload["response_format"]], []
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    names.extend(value)
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
            private = {"response_format": payload["response_format"], "field_names": names}
            try:
                if self.safe_export(private) != private:
                    raise ModelError("invalid_input")
            except RecursionError:
                raise ModelError("invalid_input") from None
        status = None
        try:
            async with asyncio.timeout(timeout_seconds):
                transport = self._transport
                if transport is None:
                    transport = httpx.AsyncHTTPTransport(
                        verify=True, trust_env=False, retries=0, http2=False,
                        limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
                    )
                with _private_transport_logs():
                    async with httpx.AsyncClient(
                        transport=transport, trust_env=False, follow_redirects=False,
                        timeout=httpx.Timeout(timeout_seconds),
                    ) as client:
                        self.http_attempts += 1
                        async with client.stream(
                            "POST", self.config.endpoint, content=body,
                            headers={"Authorization": "Bearer " + self.config.api_key,
                                     "Content-Type": "application/json", "Accept": "application/json",
                                     "Accept-Encoding": "identity"},
                        ) as response:
                            status = response.status_code
                            if status in (401, 403):
                                raise ModelError("auth_failed", http_status=status)
                            if 300 <= status < 400:
                                raise ModelError("redirect_blocked", http_status=status)
                            if status == 429:
                                raise ModelError("rate_limited", http_status=status)
                            if status == 408 or 500 <= status <= 599:
                                raise ModelError("gateway_error", http_status=status)
                            if status != 200:
                                raise ModelError("http_configuration", http_status=status)
                            if (response.headers.get("content-type", "").split(";")[0].strip().lower()
                                    != "application/json"
                                    or response.headers.get("content-encoding", "identity").strip().lower()
                                    != "identity"):
                                raise ModelError("unsupported_output", http_status=status)
                            length = response.headers.get("content-length")
                            if length is not None:
                                if not length.isascii() or not length.isdecimal():
                                    raise ModelError("invalid_response", http_status=status)
                                if len(length) > 9 or int(length) > MAX_RESPONSE_BYTES:
                                    raise ModelError("response_too_large", http_status=status)
                            result = bytearray()
                            if response.is_stream_consumed:
                                if len(response.content) > MAX_RESPONSE_BYTES:
                                    raise ModelError("response_too_large", http_status=status)
                                result.extend(response.content)
                            else:
                                async for chunk in response.aiter_raw(chunk_size=8192):
                                    if len(result) + len(chunk) > MAX_RESPONSE_BYTES:
                                        raise ModelError("response_too_large", http_status=status)
                                    result.extend(chunk)
                            if length is not None and len(result) != int(length):
                                raise ModelError("invalid_response", http_status=status)
                            return GatewayResponse(bytes(result), status)
        except (TimeoutError, httpx.TimeoutException):
            raise ModelError("timeout", http_status=status) from None
        except (httpx.HTTPError, OSError):
            raise ModelError("transport_error", http_status=status) from None
