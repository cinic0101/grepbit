"""Bounded gateway regressions using dummy configuration and no network."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
import math
from pathlib import Path
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch

import httpx

from grepbit.gateway import (
    CALL_TIMEOUT_SECONDS,
    MAX_INPUT_BYTES,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    MODEL,
    GatewayClient,
    GatewayConfig,
    GatewayResponse,
    ModelError,
)


BASE = "https://private-gateway.invalid/v1"
KEY = "dummy-runtime-secret-X9"
ENV = {
    "GREPBIT_LITELLM_BASE_URL": BASE,
    "GREPBIT_LITELLM_API_KEY": KEY,
}
MESSAGES = [
    {"role": "system", "content": "Shared semantic context."},
    {"role": "user", "content": "An explicit analytical question."},
]


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, *, delay=0):
        self.chunks = chunks
        self.delay = delay
        self.closed = False
        self.reads = 0
        self.started = asyncio.Event()

    async def __aiter__(self):
        for chunk in self.chunks:
            self.started.set()
            if self.delay:
                await asyncio.sleep(self.delay)
            self.reads += 1
            yield chunk

    async def aclose(self):
        self.closed = True


class TrackedTransport(httpx.MockTransport):
    def __init__(self, handler):
        super().__init__(handler)
        self.closed = False

    async def aclose(self):
        self.closed = True
        await super().aclose()


class OfflineAssertions:
    def setUp(self):
        super().setUp()
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            guard = patch(target, side_effect=AssertionError("Network access is forbidden."))
            guard.start()
            self.addCleanup(guard.stop)

    def assert_private(self, value):
        text = str(value)
        self.assertFalse(
            any(fragment in text for fragment in (KEY, BASE, "private-gateway.invalid")),
            "Dummy gateway configuration escaped into a public surface.",
        )

    def assert_model_error(self, code, function, *args, **kwargs):
        with self.assertRaises(ModelError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assert_private(str(caught.exception))
        self.assert_private(repr(caught.exception))
        self.assert_private("".join(traceback.format_exception(caught.exception)))
        return caught.exception


class GatewayConfigTests(OfflineAssertions, unittest.TestCase):
    def test_fixed_model_and_resource_limits(self):
        self.assertEqual(MODEL, "gemma-4-31b")
        self.assertEqual(MAX_INPUT_BYTES, 4096)
        self.assertEqual(MAX_REQUEST_BYTES, 32768)
        self.assertEqual(MAX_RESPONSE_BYTES, 131072)
        self.assertEqual(CALL_TIMEOUT_SECONDS, 60)

    def test_only_explicit_base_and_key_with_exact_optional_model(self):
        for overrides in ({}, {"GREPBIT_LITELLM_MODEL": "gemma-4-31b"}):
            with self.subTest(explicit_model=bool(overrides)):
                config = GatewayConfig.from_env(environ={**ENV, **overrides})
                self.assertEqual(config.base_url, BASE)
                self.assertEqual(config.api_key, KEY)
                self.assertEqual(config.model, "gemma-4-31b")

    def test_unrelated_provider_variables_do_not_supply_configuration(self):
        unrelated = {
            "OPENAI_API_KEY": "dummy-unrelated-key",
            "OPENAI_BASE_URL": "https://unrelated.invalid",
            "OPENAI_MODEL": "other-model",
            "AWS_ACCESS_KEY_ID": "dummy-aws",
            "AWS_SECRET_ACCESS_KEY": "dummy-aws-secret",
            "AWS_REGION": "unrelated-region",
        }
        self.assert_model_error("invalid_configuration", GatewayConfig.from_env,
                                environ=unrelated)
        config = GatewayConfig.from_env(environ={**unrelated, **ENV})
        self.assertEqual(config.model, MODEL)
        self.assertEqual(config.base_url, BASE)

    def test_missing_empty_and_prefixed_model_configuration_fails_safely(self):
        configurations = (
            {}, {"GREPBIT_LITELLM_BASE_URL": BASE},
            {"GREPBIT_LITELLM_API_KEY": KEY},
            {**ENV, "GREPBIT_LITELLM_BASE_URL": ""},
            {**ENV, "GREPBIT_LITELLM_API_KEY": ""},
            {**ENV, "GREPBIT_LITELLM_MODEL": ""},
            {**ENV, "GREPBIT_LITELLM_MODEL": "openai/gemma-4-31b"},
            {**ENV, "GREPBIT_LITELLM_MODEL": "gemma-4-31b-latest"},
        )
        for index, values in enumerate(configurations):
            with self.subTest(index=index):
                error = self.assert_model_error("invalid_configuration",
                                                GatewayConfig.from_env, environ=values)
                self.assertEqual(error.stage, "configuration")
                self.assertEqual(error.stop_reason, "configuration_failure")
                self.assertFalse(error.transport_failure)

    def test_invalid_url_and_key_values_are_rejected(self):
        bases = (
            "", "gateway.invalid/v1", "ftp://gateway.invalid", "https://",
            "https://user:password@gateway.invalid/v1", BASE + "?key=" + KEY,
            BASE + "#fragment", BASE + "\n", "https://gateway.invalid:0/v1",
            "https://gateway.invalid:65536/v1",
            BASE + "/chat/completions/chat/completions", None, 4,
        )
        for index, base in enumerate(bases):
            with self.subTest(field="base", index=index):
                self.assert_model_error("invalid_configuration", GatewayConfig, base, KEY)
        for index, key in enumerate(("", " ", "dummy\nkey", "dummy\tkey", "\u00e9", None, 4)):
            with self.subTest(field="key", index=index):
                self.assert_model_error("invalid_configuration", GatewayConfig, BASE, key)

    def test_endpoint_suffix_once_and_explicit_http_disclosure(self):
        for suffix in ("", "/", "/chat/completions", "/chat/completions/"):
            with self.subTest(suffix=suffix):
                config = GatewayConfig(BASE + suffix, KEY)
                self.assertEqual(config.endpoint, BASE + "/chat/completions")
                self.assertEqual(config.transport_security, "tls_verification_enabled")
        config = GatewayConfig("http://dummy-gateway.invalid/v1", KEY)
        self.assertEqual(config.transport_security, "unencrypted_http")

    def test_default_env_source_can_be_replaced_by_pure_dummy_mapping(self):
        with patch("grepbit.gateway.os.environ", ENV):
            config = GatewayConfig.from_env()
        self.assertEqual(config.base_url, BASE)
        self.assertEqual(config.api_key, KEY)

    def test_no_implicit_dotenv_or_constructor_transport_activity(self):
        with patch.object(Path, "open", side_effect=AssertionError("Implicit file access.")), \
                patch("grepbit.gateway.httpx.AsyncClient",
                      side_effect=AssertionError("Constructor created a client.")), \
                patch("grepbit.gateway.httpx.AsyncHTTPTransport",
                      side_effect=AssertionError("Constructor created a transport.")):
            config = GatewayConfig.from_env(environ=ENV)
            client = GatewayClient(config, transport=httpx.MockTransport(lambda request: None))
        self.assertEqual(client.http_attempts, 0)
        self.assert_private(repr(config))
        self.assert_private(repr(client))
        self.assert_private(repr(GatewayResponse((KEY + BASE).encode(), 200)))

    def test_explicit_dotenv_is_literal_without_interpolation_or_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dummy.env"
            literal = "literal-${UNRELATED}-$(whoami)-`whoami`"
            path.write_text(
                f'GREPBIT_LITELLM_BASE_URL="{BASE}"\n'
                f"GREPBIT_LITELLM_API_KEY='{literal}'\nUNRELATED=dummy-expanded\n",
                encoding="utf-8",
            )
            with patch("os.system", side_effect=AssertionError("Dotenv execution.")), \
                    patch("subprocess.Popen", side_effect=AssertionError("Dotenv execution.")):
                config = GatewayConfig.from_env(environ={"UNRELATED": "other"}, env_file=path)
            self.assertEqual(config.api_key, literal)

    def test_process_environment_wins_even_when_value_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dummy.env"
            path.write_text(
                "GREPBIT_LITELLM_BASE_URL=https://file-gateway.invalid/v1\n"
                "GREPBIT_LITELLM_API_KEY=dummy-file-key\n"
                "GREPBIT_LITELLM_MODEL=gemma-4-31b\n", encoding="utf-8",
            )
            self.assertEqual(GatewayConfig.from_env(environ=ENV, env_file=path).api_key, KEY)
            for field in ("GREPBIT_LITELLM_BASE_URL", "GREPBIT_LITELLM_API_KEY",
                          "GREPBIT_LITELLM_MODEL"):
                with self.subTest(field=field):
                    self.assert_model_error("invalid_configuration", GatewayConfig.from_env,
                                            environ={field: ""}, env_file=path)

    def test_bad_explicit_dotenv_is_non_success_not_silent_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assert_model_error("invalid_configuration", GatewayConfig.from_env,
                                    environ=ENV, env_file=root / "absent.env")
            contents = (
                b"\xff", b"GREPBIT_LITELLM_API_KEY='unterminated\n",
                b"GREPBIT_LITELLM_API_KEY=first\nGREPBIT_LITELLM_API_KEY=second\n",
                b"GREPBIT_LITELLM_API_KEY\n", b"#" + b"x" * 16384,
            )
            for index, content in enumerate(contents):
                with self.subTest(index=index):
                    path = root / f"dummy-{index}.env"
                    path.write_bytes(content)
                    self.assert_model_error("invalid_configuration", GatewayConfig.from_env,
                                            environ=ENV, env_file=path)

    def test_safe_export_recurses_without_mutating_input(self):
        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(lambda r: None))
        data = {"safe": 7, "nested": [{"key": KEY}, BASE, "private-gateway.invalid"],
                "pair": ("ok", BASE + "/chat/completions")}
        exported = client.safe_export(data)
        self.assert_private(exported)
        self.assertEqual(exported["safe"], 7)
        self.assertEqual(exported["pair"][0], "ok")
        self.assertEqual(data["nested"][0]["key"], KEY)

    def test_canonical_and_case_variant_hostnames_are_redacted(self):
        client = GatewayClient(GatewayConfig("https://b\u00fccher.invalid/v1", KEY))
        variants = ["b\u00fccher.invalid", "XN--BCHER-KVA.INVALID",
                    "https://xn--bcher-kva.invalid/other-path"]
        self.assertEqual(client.safe_export({"values": variants})["values"],
                         ["[redacted]"] * len(variants))


class GatewayTransportTests(OfflineAssertions, unittest.IsolatedAsyncioTestCase):
    def client(self, handler, *, base=BASE):
        transport = TrackedTransport(handler)
        return GatewayClient(GatewayConfig(base, KEY), transport=transport), transport

    async def assert_async_error(self, code, client, messages=None, **kwargs):
        with self.assertRaises(ModelError) as caught:
            await client.complete(MESSAGES if messages is None else messages, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assert_private(str(caught.exception))
        self.assert_private(repr(caught.exception))
        self.assert_private("".join(traceback.format_exception(caught.exception)))
        return caught.exception

    async def test_exact_single_post_payload_and_authorization(self):
        for suffix in ("", "/", "/chat/completions", "/chat/completions/"):
            with self.subTest(suffix=suffix):
                calls = []

                def handle(request):
                    calls.append(request)
                    return httpx.Response(200, json={"ok": True})

                client, transport = self.client(handle, base=BASE + suffix)
                response = await client.complete(MESSAGES)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(calls), 1)
                self.assertEqual(client.http_attempts, 1)
                sent = calls[0]
                self.assertEqual(sent.method, "POST")
                self.assertEqual(str(sent.url), BASE + "/chat/completions")
                self.assertEqual(sent.headers["authorization"], "Bearer " + KEY)
                self.assertEqual(sent.headers["content-type"], "application/json")
                self.assertEqual(sent.headers["accept"], "application/json")
                self.assertEqual(sent.headers["accept-encoding"], "identity")
                self.assertEqual(json.loads(sent.content), {
                    "model": "gemma-4-31b", "messages": MESSAGES, "temperature": 0,
                    "max_tokens": 2048, "stream": False,
                })
                self.assertTrue(transport.closed)

    async def test_each_call_is_fresh_without_cookies_or_message_history(self):
        seen = []

        def handle(request):
            seen.append(request)
            return httpx.Response(200, json={}, headers={"set-cookie": "session=dummy; Path=/"})

        client, _ = self.client(handle)
        actual_client = httpx.AsyncClient
        with patch("grepbit.gateway.httpx.AsyncClient", wraps=actual_client) as constructors:
            await client.complete(MESSAGES)
            next_messages = [MESSAGES[0], {"role": "user", "content": "A different question."}]
            await client.complete(next_messages)
        self.assertEqual(constructors.call_count, 2)
        self.assertEqual(client.http_attempts, 2)
        self.assertEqual([len(json.loads(item.content)["messages"]) for item in seen], [2, 2])
        self.assertEqual(json.loads(seen[1].content)["messages"], next_messages)
        self.assertTrue(all("cookie" not in item.headers for item in seen))

    async def test_default_transport_is_verified_proxy_free_and_has_zero_retries(self):
        fake = TrackedTransport(lambda request: httpx.Response(200, json={}))
        actual_client = httpx.AsyncClient
        with patch("grepbit.gateway.httpx.AsyncHTTPTransport", return_value=fake) as constructor, \
                patch("grepbit.gateway.httpx.AsyncClient", wraps=actual_client) as clients:
            client = GatewayClient(GatewayConfig(BASE, KEY))
            await client.complete(MESSAGES)
        constructor.assert_called_once()
        options = constructor.call_args.kwargs
        self.assertIs(options["verify"], True)
        self.assertIs(options["trust_env"], False)
        self.assertEqual(options["retries"], 0)
        self.assertIsNone(options.get("proxy"))
        self.assertIs(options["http2"], False)
        self.assertEqual(options["limits"].max_connections, 1)
        self.assertEqual(options["limits"].max_keepalive_connections, 0)
        self.assertIs(clients.call_args.kwargs["trust_env"], False)
        self.assertIs(clients.call_args.kwargs["follow_redirects"], False)
        self.assertIsNone(clients.call_args.kwargs.get("proxy"))
        self.assertTrue(fake.closed)

    async def test_status_failures_are_single_attempts_without_body_echo(self):
        cases = (
            (401, "auth_failed", "configuration_failure", False),
            (403, "auth_failed", "configuration_failure", False),
            (429, "rate_limited", None, True),
            (408, "gateway_error", None, True),
            (500, "gateway_error", None, True),
            (502, "gateway_error", None, True),
            (503, "gateway_error", None, True),
            (599, "gateway_error", None, True),
            (400, "http_configuration", "configuration_failure", False),
            (404, "http_configuration", "configuration_failure", False),
        )
        for status, code, stop, operational in cases:
            with self.subTest(status=status):
                stream = Chunks([(KEY + BASE).encode()])
                client, transport = self.client(
                    lambda request: httpx.Response(status, stream=stream,
                                                  headers={"content-type": "application/json"})
                )
                output = io.StringIO()
                with redirect_stdout(output), redirect_stderr(output):
                    error = await self.assert_async_error(code, client)
                self.assertEqual(error.http_status, status)
                self.assertEqual(error.stage, "transport")
                self.assertEqual(error.stop_reason, stop)
                self.assertEqual(error.transport_failure, operational)
                self.assertEqual(client.http_attempts, 1)
                self.assertEqual(stream.reads, 0)
                self.assertTrue(stream.closed)
                self.assertTrue(transport.closed)
                self.assert_private(output.getvalue())

    async def test_redirects_never_follow_credential_bearing_locations(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                seen = []

                def handle(request):
                    seen.append(request)
                    return httpx.Response(status, headers={
                        "location": "https://user:" + KEY + "@redirect.invalid/chat/completions",
                    })

                client, transport = self.client(handle)
                error = await self.assert_async_error("redirect_blocked", client)
                self.assertEqual(error.http_status, status)
                self.assertEqual(len(seen), 1)
                self.assertTrue(transport.closed)

    async def test_only_json_identity_responses_are_accepted(self):
        headers = (
            {}, {"content-type": "text/event-stream"}, {"content-type": "text/plain"},
            {"content-type": "application/json", "content-encoding": "gzip"},
            {"content-type": "application/json", "content-encoding": "br"},
        )
        for index, values in enumerate(headers):
            with self.subTest(index=index):
                stream = Chunks([b"{}"])
                client, transport = self.client(
                    lambda request: httpx.Response(200, headers=values, stream=stream)
                )
                await self.assert_async_error("unsupported_output", client)
                self.assertTrue(stream.closed)
                self.assertTrue(transport.closed)
        client, _ = self.client(lambda request: httpx.Response(
            200, content=b"{}", headers={"content-type": "application/json; charset=utf-8"}))
        self.assertEqual((await client.complete(MESSAGES)).body, b"{}")

    async def test_content_type_and_identity_encoding_ignore_case_and_outer_whitespace(self):
        headers = (
            {"content-type": " APPLICATION/JSON ", "content-encoding": " IDENTITY "},
            {"content-type": "Application/Json \t; charset=UTF-8", "content-encoding": "\tIdentity\t"},
            {"content-type": " application/json; charset=utf-8 "},
        )
        for index, values in enumerate(headers):
            with self.subTest(index=index):
                stream = Chunks([b"{}"])
                client, transport = self.client(
                    lambda request: httpx.Response(200, headers=values, stream=stream)
                )
                self.assertEqual((await client.complete(MESSAGES)).body, b"{}")
                self.assertTrue(stream.closed)
                self.assertTrue(transport.closed)
        for values in (
            {"content-type": " APPLICATION/JSONP "},
            {"content-type": " APPLICATION/JSON ", "content-encoding": " GZIP "},
            {"content-type": " APPLICATION/JSON ", "content-encoding": "identity, gzip"},
        ):
            with self.subTest(headers=values):
                stream = Chunks([b"{}"])
                client, _ = self.client(
                    lambda request: httpx.Response(200, headers=values, stream=stream)
                )
                await self.assert_async_error("unsupported_output", client)
                self.assertTrue(stream.closed)

    async def test_network_exceptions_are_sanitized_and_not_retried(self):
        for kind, code in (
            (httpx.ConnectError, "transport_error"), (httpx.ReadError, "transport_error"),
            (httpx.RemoteProtocolError, "transport_error"), (OSError, "transport_error"),
            (httpx.ConnectTimeout, "timeout"), (httpx.ReadTimeout, "timeout"),
        ):
            with self.subTest(kind=kind.__name__):
                def handle(request):
                    raise kind("echo " + KEY + " at " + BASE)

                client, transport = self.client(handle)
                error = await self.assert_async_error(code, client)
                self.assertTrue(error.transport_failure)
                self.assertEqual(client.http_attempts, 1)
                self.assertTrue(transport.closed)

    async def test_invalid_timeouts_fail_before_any_attempt(self):
        for value in (0, -1, 60.001, math.nan, math.inf, True, "60", None):
            with self.subTest(value=repr(value)):
                client, _ = self.client(lambda request: self.fail("Transport must not run."))
                await self.assert_async_error("invalid_configuration", client, timeout_seconds=value)
                self.assertEqual(client.http_attempts, 0)

    async def test_message_shape_empty_text_and_surrogates_fail_before_transport(self):
        cases = (
            [], MESSAGES[:1], [*MESSAGES, MESSAGES[1]], {},
            [{"role": "user", "content": "a"}, {"role": "system", "content": "b"}],
            [MESSAGES[0], {"role": "user", "content": 4}],
            [MESSAGES[0], {"role": "user", "content": "a", "name": "extra"}],
            [MESSAGES[0], {"role": "user", "content": ""}],
            [MESSAGES[0], {"role": "user", "content": " \n\t"}],
            [MESSAGES[0], {"role": "user", "content": "\ud800"}],
        )
        for index, messages in enumerate(cases):
            with self.subTest(index=index):
                client, _ = self.client(lambda request: self.fail("Transport must not run."))
                await self.assert_async_error("invalid_input", client, messages=messages)
                self.assertEqual(client.http_attempts, 0)

    async def test_question_limit_is_utf8_bytes_with_inclusive_boundary(self):
        for size, expected in ((4096, None), (4097, "input_too_large")):
            with self.subTest(size=size):
                question = "\u00e9" * 2048 + ("a" if size == 4097 else "")
                self.assertEqual(len(question.encode("utf-8")), size)
                client, _ = self.client(lambda request: httpx.Response(200, json={}))
                messages = [MESSAGES[0], {"role": "user", "content": question}]
                if expected:
                    error = await self.assert_async_error(expected, client, messages=messages)
                    self.assertEqual(error.stop_reason, "budget_exhausted")
                    self.assertEqual(client.http_attempts, 0)
                else:
                    await client.complete(messages)
                    self.assertEqual(client.http_attempts, 1)

    async def test_entire_serialized_request_has_its_own_byte_cap(self):
        sent = []

        def handle(request):
            sent.append(request)
            return httpx.Response(200, json={})

        messages = [{"role": "system", "content": ""},
                    {"role": "user", "content": "short"}]
        probe, _ = self.client(handle)
        await probe.complete(messages)
        overhead = len(sent[0].content)
        for size, allowed in ((32768, True), (32769, False)):
            with self.subTest(size=size):
                messages = [{"role": "system", "content": ""},
                            {"role": "user", "content": "short"}]
                messages[0]["content"] = "x" * (size - overhead)
                client, _ = self.client(handle)
                if allowed:
                    await client.complete(messages)
                    self.assertEqual(len(sent[-1].content), size)
                    self.assertEqual(client.http_attempts, 1)
                else:
                    await self.assert_async_error("input_too_large", client, messages=messages)
                    self.assertEqual(client.http_attempts, 0)

    async def test_secret_or_endpoint_in_prompt_is_not_sent(self):
        for fragment in (KEY, BASE, "private-gateway.invalid"):
            for role_index in (0, 1):
                with self.subTest(role_index=role_index):
                    messages = [dict(message) for message in MESSAGES]
                    messages[role_index]["content"] += " " + fragment
                    client, _ = self.client(lambda request: self.fail("Sensitive prompt was sent."))
                    await self.assert_async_error("invalid_input", client, messages=messages)
                    self.assertEqual(client.http_attempts, 0)

    async def test_single_label_host_does_not_match_inside_ordinary_words(self):
        for base in ("http://x/v1", "http://x:4000/v1"):
            with self.subTest(with_port=":4000" in base):
                client, _ = self.client(lambda request: httpx.Response(200, json={}), base=base)
                response = await client.complete(MESSAGES)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.http_attempts, 1)

    async def test_single_label_host_and_full_endpoint_remain_private_tokens(self):
        base = "http://x:4000/v1"
        for fragment in ("x", "x:4000", base, base + "/chat/completions"):
            with self.subTest(kind="endpoint" if "://" in fragment else "authority"):
                client, _ = self.client(lambda request: self.fail("Sensitive prompt was sent."),
                                        base=base)
                messages = [MESSAGES[0], {"role": "user", "content": "Report " + fragment}]
                await self.assert_async_error("invalid_input", client, messages=messages)
                self.assertEqual(client.http_attempts, 0)

    async def test_response_byte_cap_for_eager_and_streaming_bodies(self):
        for streamed in (False, True):
            for size in (131072, 131073):
                with self.subTest(streamed=streamed, size=size):
                    body = b"x" * size
                    stream = Chunks([body[:65536], body[65536:]]) if streamed else None
                    response = (httpx.Response(200, stream=stream,
                                              headers={"content-type": "application/json"})
                                if stream is not None else httpx.Response(
                                    200, content=body, headers={"content-type": "application/json"}))
                    client, transport = self.client(lambda request: response)
                    if size == 131072:
                        self.assertEqual((await client.complete(MESSAGES)).body, body)
                    else:
                        error = await self.assert_async_error("response_too_large", client)
                        self.assertEqual(error.stop_reason, "budget_exhausted")
                    self.assertTrue(transport.closed)
                    if stream is not None:
                        self.assertTrue(stream.closed)

    async def test_content_length_syntax_and_declared_cap_checked_before_read(self):
        for length, code in (
            ("-1", "invalid_response"), ("+2", "invalid_response"),
            ("2.0", "invalid_response"), ("no", "invalid_response"),
            ("2, 2", "invalid_response"), ("131073", "response_too_large"),
        ):
            with self.subTest(length=length):
                stream = Chunks([b"{}"])
                client, _ = self.client(lambda request: httpx.Response(
                    200, stream=stream,
                    headers={"content-type": "application/json", "content-length": length}))
                await self.assert_async_error(code, client)
                self.assertEqual(stream.reads, 0)
                self.assertTrue(stream.closed)

    async def test_content_length_must_match_actual_body_bytes(self):
        for streamed in (False, True):
            for length in ("1", "3"):
                with self.subTest(streamed=streamed, length=length):
                    stream = Chunks([b"{}"])
                    response = httpx.Response(
                        200, headers={"content-type": "application/json", "content-length": length},
                        **({"stream": stream} if streamed else {"content": b"{}"}),
                    )
                    client, _ = self.client(lambda request: response)
                    await self.assert_async_error("invalid_response", client)
                    if streamed:
                        self.assertTrue(stream.closed)

    async def test_valid_declared_length_includes_exact_response_byte_cap(self):
        for size in (2, 131072):
            with self.subTest(size=size):
                body = b"x" * size
                stream = Chunks([body])
                client, transport = self.client(lambda request: httpx.Response(
                    200, stream=stream,
                    headers={"content-type": "application/json", "content-length": str(size)}))
                self.assertEqual((await client.complete(MESSAGES)).body, body)
                self.assertTrue(stream.closed)
                self.assertTrue(transport.closed)

    async def test_absent_and_chunked_lengths_use_actual_bytes_not_trusted_headers(self):
        for extra in ({}, {"transfer-encoding": "chunked"}, {"content-length": "2"}):
            with self.subTest(headers=extra):
                stream = Chunks([b"x" * 8192] * 16 + [b"x"])
                client, _ = self.client(lambda request: httpx.Response(
                    200, stream=stream, headers={"content-type": "application/json", **extra}))
                await self.assert_async_error("response_too_large", client)
                self.assertTrue(stream.closed)

    async def test_total_timeout_covers_response_headers(self):
        cancelled = asyncio.Event()

        async def handle(request):
            try:
                await asyncio.sleep(0.2)
            finally:
                cancelled.set()
            return httpx.Response(200, json={})

        client, transport = self.client(handle)
        started = time.monotonic()
        await self.assert_async_error("timeout", client, timeout_seconds=0.03)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(cancelled.is_set())
        self.assertTrue(transport.closed)

    async def test_header_and_drip_body_share_one_total_deadline(self):
        stream = Chunks([b"a"] * 20, delay=0.02)

        async def handle(request):
            await asyncio.sleep(0.04)
            return httpx.Response(200, stream=stream,
                                  headers={"content-type": "application/json"})

        client, transport = self.client(handle)
        started = time.monotonic()
        error = await self.assert_async_error("timeout", client, timeout_seconds=0.09)
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(error.http_status, 200)
        self.assertLess(stream.reads, 4)
        self.assertTrue(stream.closed)
        self.assertTrue(transport.closed)

    async def test_cancellation_propagates_and_closes_stream_and_client(self):
        stream = Chunks([b"{}"], delay=5)
        client, transport = self.client(lambda request: httpx.Response(
            200, stream=stream, headers={"content-type": "application/json"}))
        clients = []
        actual_client = httpx.AsyncClient

        def construct(*args, **kwargs):
            instance = actual_client(*args, **kwargs)
            clients.append(instance)
            return instance

        with patch("grepbit.gateway.httpx.AsyncClient", side_effect=construct):
            task = asyncio.create_task(client.complete(MESSAGES))
            try:
                await asyncio.wait_for(stream.started.wait(), timeout=0.5)
            finally:
                task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(stream.closed)
        self.assertTrue(transport.closed)
        self.assertEqual(len(clients), 1)
        self.assertTrue(clients[0].is_closed)
        self.assertEqual(client.http_attempts, 1)

    async def test_body_read_exception_is_sanitized_and_closes_every_resource(self):
        class BrokenStream(Chunks):
            async def __aiter__(self):
                yield b"{"
                raise httpx.ReadError("body echo " + KEY + BASE)

        stream = BrokenStream([])
        client, transport = self.client(lambda request: httpx.Response(
            200, stream=stream, headers={"content-type": "application/json"}))
        error = await self.assert_async_error("transport_error", client)
        self.assertEqual(error.http_status, 200)
        self.assertTrue(stream.closed)
        self.assertTrue(transport.closed)
        self.assertEqual(client.http_attempts, 1)

    async def test_httpx_and_httpcore_info_debug_logs_do_not_expose_configuration(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        names = ("httpx", "httpcore", "httpcore.connection", "httpcore.http11",
                 "httpcore.http2", "httpcore.proxy", "httpcore.socks")
        loggers = [logging.getLogger(name) for name in names]
        for logger in loggers:
            old = logger.level
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            self.addCleanup(logger.setLevel, old)
            self.addCleanup(logger.removeHandler, handler)

        def handle(request):
            for logger in loggers:
                logger.debug("transport %s %s", KEY, BASE)
                logger.info("transport %s %s", KEY, BASE)
            return httpx.Response(401, content=(KEY + BASE).encode())

        client, _ = self.client(handle)
        with redirect_stdout(output), redirect_stderr(output):
            await self.assert_async_error("auth_failed", client)
        self.assert_private(output.getvalue())
        logging.getLogger("httpx").info("unrelated caller remains visible")
        self.assertIn("unrelated caller remains visible", output.getvalue())


if __name__ == "__main__":
    unittest.main()
