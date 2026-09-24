"""Issue #62 provider rulers; dummy keys and mock HTTP only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError
from tools import fixture


REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
KEY = "dummy-bedrock-secret-X9"
ENV = {"GREPBIT_LLM_PROVIDER": "bedrock_converse", "GREPBIT_BEDROCK_REGION": REGION,
       "GREPBIT_BEDROCK_MODEL_ID": MODEL_ID, "GREPBIT_BEDROCK_API_KEY": KEY}
MESSAGES = [{"role": "system", "content": "Shared semantic context."},
            {"role": "user", "content": "An explicit analytical question."}]


class BedrockAdapterRulers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            guard = patch(target, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.assertIsNotNone(importlib.util.find_spec("grepbit.provider"),
                             "The shared provider adapter is not implemented")
        self.assertIsNotNone(importlib.util.find_spec("grepbit.bedrock"),
                             "The Bedrock Converse adapter is not implemented")
        from grepbit import bedrock, provider
        self.bedrock, self.provider = bedrock, provider

    def response(self, text='{"outcome":"declined"}', *, stop="end_turn"):
        return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}},
                "stopReason": stop, "usage": {"inputTokens": 12, "outputTokens": 8,
                                                 "totalTokens": 20}}

    def client(self, handler):
        return self.provider.client_from_env(environ=ENV,
                                              transport=httpx.MockTransport(handler))

    def test_explicit_selection_and_legacy_config_are_separate(self):
        legacy = {"GREPBIT_LITELLM_BASE_URL": "https://legacy.invalid/v1",
                  "GREPBIT_LITELLM_API_KEY": "dummy-legacy-key"}
        self.assertIsInstance(self.provider.client_from_env(environ=legacy,
                                    transport=httpx.MockTransport(lambda _: None)), GatewayClient)
        with self.assertRaises(ModelError):
            self.provider.client_from_env(environ={**ENV, "GREPBIT_LLM_PROVIDER": "unknown"})
        with self.assertRaises(ModelError):
            self.provider.client_from_env(environ={"AWS_BEARER_TOKEN_BEDROCK": KEY,
                                                   "AWS_REGION": REGION,
                                                   "GREPBIT_LLM_PROVIDER": "bedrock_converse"})
        self.assertEqual(GatewayConfig.from_env(environ=legacy).model, "gemma-4-31b")

    def test_literal_env_file_and_invalid_route_fail_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dummy.env"
            path.write_text("GREPBIT_LLM_PROVIDER=bedrock_converse\n"
                            "GREPBIT_BEDROCK_REGION=us-west-2\n"
                            f"GREPBIT_BEDROCK_MODEL_ID={MODEL_ID}\n"
                            "GREPBIT_BEDROCK_API_KEY='literal-${UNRELATED}'\n")
            client = self.provider.client_from_env(environ={"GREPBIT_BEDROCK_REGION": REGION},
                                                   env_file=path,
                                                   transport=httpx.MockTransport(lambda _: None))
            self.assertEqual(client.config.region, REGION)
            self.assertEqual(client.config.api_key, "literal-${UNRELATED}")
            self.assertEqual(client.http_attempts, 0)
        for override in ({"GREPBIT_BEDROCK_REGION": "us-east-1.invalid"},
                         {"GREPBIT_BEDROCK_MODEL_ID": "../other/model"},
                         {"GREPBIT_BEDROCK_API_KEY": "dummy\nkey"}):
            with self.subTest(override=tuple(override)):
                with self.assertRaises(ModelError) as caught:
                    self.provider.client_from_env(environ={**ENV, **override})
                self.assertEqual(caught.exception.code, "invalid_configuration")
                self.assertNotIn(KEY, str(caught.exception))

    async def test_converse_request_and_response_normalization(self):
        sent = []
        def handle(request):
            sent.append(request)
            return httpx.Response(200, json=self.response())
        client = self.client(handle)
        result = self.provider.normalize_response(client.config, await client.complete(MESSAGES))
        self.assertEqual(client.http_attempts, 1)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body and json.loads(result.body)["choices"][0]
                         ["message"]["content"], '{"outcome":"declined"}')
        self.assertNotIn("model", json.loads(result.body))
        self.assertEqual(json.loads(result.body)["usage"], {
            "prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20})
        request = sent[0]
        self.assertEqual(request.url.path, f"/model/{MODEL_ID}/converse")
        self.assertEqual(request.headers["authorization"], "Bearer " + KEY)
        self.assertEqual(json.loads(request.content), {
            "system": [{"text": MESSAGES[0]["content"]}],
            "messages": [{"role": "user", "content": [{"text": MESSAGES[1]["content"]}]}],
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0},
        })
        self.assertNotIn(KEY, repr(client))
        self.assertEqual(client.safe_export({"secret": KEY}), {"secret": "[redacted]"})

    async def test_bedrock_cold_schema_timeout_limit_is_provider_specific(self):
        sent = []
        client = self.client(lambda request: (sent.append(request) or
                                              httpx.Response(200, json=self.response())))
        await client.complete(MESSAGES, timeout_seconds=300)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].extensions["timeout"]["read"], 300)
        with self.assertRaises(ModelError) as caught:
            await client.complete(MESSAGES, timeout_seconds=301)
        self.assertEqual(caught.exception.code, "invalid_configuration")
        self.assertEqual(len(sent), 1)
        self.assertEqual(GatewayConfig.max_call_timeout_seconds, 60)

    async def test_recipe_wire_schema_is_adapted_without_changing_canonical_identity(self):
        before = recipe_model.structured_output_identity()
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=self.response())
        client = self.client(handle)
        constraint = {"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME,
                      "schema": recipe_model.output_schema()}
        self.provider.normalize_response(client.config, await client.complete(
            MESSAGES, json_schema_constraint=constraint))
        output = sent[0]["outputConfig"]["textFormat"]
        self.assertEqual(output["type"], "json_schema")
        self.assertEqual(output["structure"]["jsonSchema"]["name"], constraint["name"])
        schema = json.loads(output["structure"]["jsonSchema"]["schema"])
        self.assertIn("anyOf", schema)
        self.assertNotIn("oneOf", json.dumps(schema))
        for forbidden in ('"minimum"', '"maxItems"', '"pattern"'):
            self.assertNotIn(forbidden, json.dumps(schema))
        self.assertEqual(recipe_model.structured_output_identity(), before)
        self.assertNotEqual(self.provider.wire_identity(client.config, constraint, before), before)

    async def test_unknown_schema_and_private_prompt_fail_without_send(self):
        client = self.client(lambda _: self.fail("No request may be sent"))
        with self.assertRaises(ModelError) as caught:
            await client.complete(MESSAGES, json_schema_constraint={
                "name": "test_schema", "schema": {"type": "object", "format": "unknown"}})
        self.assertEqual(caught.exception.code, "invalid_input")
        with self.assertRaises(ModelError) as caught:
            await client.complete([MESSAGES[0], {"role": "user", "content": KEY}])
        self.assertEqual(caught.exception.code, "invalid_input")
        self.assertEqual(client.http_attempts, 0)

    async def test_escaped_key_in_schema_is_rejected_before_send(self):
        for key in ('synthetic\\key', 'synthetic"key'):
            for location in ("description", "property_name"):
                with self.subTest(key=key, location=location):
                    settings = {**ENV, "GREPBIT_BEDROCK_API_KEY": key}
                    client = self.provider.client_from_env(
                        environ=settings,
                        transport=httpx.MockTransport(lambda _: self.fail("Secret must not be sent")))
                    schema = ({"type": "string", "description": key}
                              if location == "description" else
                              {"type": "object", "properties": {key: {"type": "string"}}})
                    with self.assertRaises(ModelError) as caught:
                        await client.complete(MESSAGES, json_schema_constraint={
                            "name": "test_schema", "schema": schema})
                    self.assertEqual(caught.exception.code, "invalid_input")
                    self.assertEqual(client.http_attempts, 0)

    async def test_http_failure_is_sanitized_and_never_retried(self):
        for status, code in ((401, "auth_failed"), (302, "redirect_blocked"),
                             (429, "rate_limited"), (503, "gateway_error")):
            with self.subTest(status=status):
                client = self.client(lambda _: httpx.Response(status,
                    headers={"location": "https://" + KEY + ".invalid"}))
                with self.assertRaises(ModelError) as caught:
                    await client.complete(MESSAGES)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.http_status, status)
                self.assertEqual(client.http_attempts, 1)
                self.assertNotIn(KEY, str(caught.exception))

    async def test_invalid_response_and_non_success_stops_fail_closed(self):
        for payload, code in ((self.response(stop="max_tokens"), "truncated_output"),
                              (self.response(stop="tool_use"), "unsupported_output"),
                              ({"output": {"message": {"role": "assistant",
                                "content": [{"toolUse": {"name": "x"}}]}},
                                "stopReason": "end_turn"}, "unsupported_output"),
                              ({"output": {"message": {"role": "assistant",
                                "content": [{"text": "{}"}, {"text": "{}"}]}},
                                "stopReason": "end_turn"}, "unsupported_output")):
            with self.subTest(code=code):
                client = self.client(lambda _, p=payload: httpx.Response(200, json=p))
                with self.assertRaises(ModelError) as caught:
                    self.provider.normalize_response(client.config, await client.complete(MESSAGES))
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(client.http_attempts, 1)
                self.assertNotIn(KEY, str(caught.exception))

    async def test_application_entry_accepts_bedrock_without_model_identity_fabrication(self):
        client = self.client(lambda _: httpx.Response(200, json=self.response()))
        result = await model.interpret_and_execute("A question", Path("unused"), client)
        self.assertEqual(result.error.code, "model_declined")
        self.assertIsNone(result.evidence["returned_model"])
        self.assertEqual(result.evidence["response_mode"], "bedrock_converse_normalized")

    async def test_invalid_converse_after_http_200_is_response_validation_failure(self):
        client = self.client(lambda _: httpx.Response(200, json=self.response(stop="tool_use")))
        result = await model.interpret_and_execute("A question", Path("unused"), client)
        self.assertEqual(result.error.code, "unsupported_output")
        self.assertEqual(result.evidence["http_status"], 200)
        self.assertEqual(result.evidence["stages"]["transport"], "passed")
        self.assertEqual(result.evidence["stages"]["response_validation"], "failed")
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")

    async def test_recipe_entry_reports_wire_identity_and_stops_before_native_work(self):
        client = self.client(lambda _: httpx.Response(200, json=self.response()))
        result = await recipe_model.interpret_recipe_and_execute("A question", Path("unused"),
                                                                 client)
        self.assertEqual(result.error.code, "model_declined")
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        self.assertIsNone(result.evidence["returned_model"])
        identity = result.evidence["structured_output_identity"]
        self.assertEqual(identity["provider"], "bedrock_converse")
        self.assertEqual(identity["schema_sha256"],
                         recipe_model.structured_output_identity()["schema_sha256"])
        self.assertEqual(len(identity["wire_schema_sha256"]), 64)

    async def test_one_bedrock_text_proposal_reaches_unchanged_native_recipe(self):
        proposal = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                    "request": {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00",
                                "end": "2026-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"}}
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "synthetic.sqlite"
            fixture.build(database)
            client = self.client(lambda _: httpx.Response(200, json=self.response(
                json.dumps(proposal))))
            result = await recipe_model.interpret_recipe_and_execute(
                "March 2026 overview for CTR-A01", database, client)
        self.assertIsNone(result.error)
        self.assertEqual(result.proposal.recipe_id, "overview")
        self.assertEqual(result.analysis_pack.status, "complete")
        self.assertEqual(result.evidence["client_http_attempts"], 1)
        self.assertIsNone(result.evidence["returned_model"])
