"""Offline wire contracts and bounded structured-output admission; no provider proof."""
from contextlib import contextmanager, ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import inspect
import io
import json
import logging
from pathlib import Path
import sqlite3
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx

from grepbit import gateway, json_diagnostics, model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError
from tools import fixture, recipe_smoke as runner, smoke
from test_json_diagnostics import P2_IDENTITY
from test_model import request_content
from test_recipe_model import envelope, proposal


BASE = "https://structured-private.invalid/v1"
KEY = "dummy-structured-private-key"
CANARY = "PROVIDER_ONLY_CANARY_Q7"
SCHEMA_CANARY = "SCHEMA_ONLY_CANARY_Q7"
QUESTION = "March 2026 bookings; \u4e09\u6708\u9810\u8a02."
MESSAGES = [{"role": "system", "content": "Return JSON."}, {"role": "user", "content": QUESTION}]
RECIPES = ("overview", "compare", "breakdown")
MOCK_HTTP_ATTEMPTS = 0
GENERATION = {
    "version": "recipe-structured-output-v1", "mode": "json_schema",
    "schema_name": "grepbit_recipe_request",
    "schema_sha256": "ac6ca4d71fbe6a69c978231458bc6d4be7fca3f5ebbee732d4cdedad0dec9a02",
    "response_format_sha256": "4333d65dede04246311681767015be7438503ff019b239d1d0c0194ab9a037ab",
}


def wrapper(schema, name="grepbit_recipe_request"):
    return {"type": "json_schema", "json_schema": {"name": name, "schema": schema}}


def historical_payload(messages):
    return {"model": MODEL, "messages": messages, "temperature": 0, "max_tokens": 2048, "stream": False}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(model.canonical_json(value).encode()).hexdigest()


class StructuredOutputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport"):
            guard = patch(target, side_effect=AssertionError("Real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(GatewayConfig, "from_env", side_effect=AssertionError("Real configuration forbidden"))
        self.loader = guard.start()
        self.addCleanup(guard.stop)
        temporary = tempfile.TemporaryDirectory(dir=runner.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "structured.sqlite"
        self.sent = []
        self.secrets = {BASE, KEY, CANARY, SCHEMA_CANARY, "structured-private.invalid"}

    def assert_private(self, value):
        text = str(value).casefold()
        fragments = {part.casefold() for secret in self.secrets for part in
                     (secret, json.dumps(secret)[1:-1], repr(secret)[1:-1])}
        self.assertFalse(any(part in text for part in fragments), "Configuration, schema or provider text escaped")

    @contextmanager
    def captured_output(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger()
        previous = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            with redirect_stdout(output), redirect_stderr(output):
                yield
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous)
            self.assert_private(output.getvalue())

    def client(self, content='{"outcome":"declined"}', *, config=None, status=200, document=None):
        self.sent = []
        config = config or GatewayConfig(BASE, KEY)
        self.secrets.update((config.api_key, config.base_url, config.endpoint, urlsplit(config.base_url).hostname))
        if document is None:
            document = envelope(content)
            document["choices"][0]["message"].update(
                reasoning_content=json.dumps(proposal("breakdown")), reasoning=CANARY)
            document[CANARY] = {SCHEMA_CANARY: CANARY}
        body = encoded(document)

        def respond(request):
            global MOCK_HTTP_ATTEMPTS
            MOCK_HTTP_ATTEMPTS += 1
            self.sent.append(request)
            return httpx.Response(status, content=body, headers={"content-type": "application/json"})

        return GatewayClient(config, transport=httpx.MockTransport(respond))

    async def rejected_constraint(self, constraint, *, code="invalid_input", config=None):
        client = self.client(config=config)
        with self.captured_output():
            try:
                await client.complete(MESSAGES, json_schema_constraint=constraint)
            except ModelError as error:
                failure = error
                self.assertEqual(error.code, code)
                for value in (str(error), repr(error), "".join(traceback.format_exception(error))):
                    self.assert_private(value)
            else:
                self.fail("Invalid constraint did not raise a fixed ModelError")
        self.assertEqual((client.http_attempts, len(self.sent)), (0, 0))
        return failure

    async def recipe(self, content, *, execute=False, status=200, document=None):
        client = self.client(content, status=status, document=document)
        with ExitStack() as stack:
            stack.enter_context(self.captured_output())
            complete = stack.enter_context(patch.object(client, "complete", wraps=client.complete))
            executions = [stack.enter_context(patch.object(
                recipe_model, "execute_" + name, wraps=getattr(recipe_model, "execute_" + name))) for name in RECIPES]
            if not execute:
                stack.enter_context(patch.object(
                    sqlite3, "connect", side_effect=AssertionError("Rejected response opened a database")))
            result = await recipe_model.interpret_recipe_and_execute(QUESTION, self.database, client)
        self.assertEqual((client.http_attempts, len(self.sent), complete.call_count), (1, 1, 1))
        self.assertEqual(sum(call.call_count for call in executions), int(execute))
        self.assertEqual(result.evidence["client_http_attempts"], 1)
        for value in (result.evidence, repr(result), repr(result.error), str(result.error),
                      client.safe_export(result.evidence)):
            self.assert_private(value)
        if result.error:
            self.assert_private("".join(traceback.format_exception(result.error)))
            self.assertIsNone(result.analysis_pack)
            self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        return result, complete

    async def test_explicit_signature_rejects_unknown_keywords_without_passthrough(self):
        parameters = inspect.signature(GatewayClient.complete).parameters
        self.assertEqual(tuple(parameters), ("self", "messages", "timeout_seconds", "json_schema_constraint"))
        for name in ("timeout_seconds", "json_schema_constraint"):
            self.assertIs(parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameters["json_schema_constraint"].default)
        self.assertEqual(parameters["timeout_seconds"].default, 60.0)
        for name in ("response_format", "extra_body", "provider_options", "guided_json", "strict"):
            with self.subTest(keyword=name):
                client = self.client()
                with self.assertRaises(TypeError) as caught:
                    await client.complete(MESSAGES, **{name: {"description": SCHEMA_CANARY}})
                self.assert_private(str(caught.exception))
                self.assertEqual((client.http_attempts, len(self.sent)), (0, 0))

    async def test_default_and_explicit_none_preserve_exact_historical_wire_bytes(self):
        expected = historical_payload(MESSAGES)
        for explicit in (False, True):
            with self.subTest(explicit_none=explicit):
                client = self.client()
                await client.complete(MESSAGES, **({"json_schema_constraint": None} if explicit else {}))
                self.assertEqual((client.http_attempts, len(self.sent)), (1, 1))
                self.assertTrue(self.sent[0].content == encoded(expected), "Default serialization changed")
                actual = json.loads(self.sent[0].content)
                self.assertTrue(actual == expected, "Default payload changed")
                self.assertEqual(set(actual), {"model", "messages", "temperature", "max_tokens", "stream"})
                self.assertNotIn("response_format", actual)

    async def test_p1_adapter_keeps_wire_messages_context_and_no_generation_argument(self):
        fixture.build(self.database)
        client = self.client(request_content())
        with patch.object(client, "complete", wraps=client.complete) as complete, self.captured_output():
            result = await model.interpret_and_execute(QUESTION, self.database, client)
        self.assertIsNone(result.error)
        self.assertEqual([fact.value for fact in result.fact_pack.facts], [158000, 7, 12, 5])
        self.assertEqual((client.http_attempts, complete.call_count, len(self.sent)), (1, 1, 1))
        self.assertEqual(set(complete.call_args.kwargs), {"timeout_seconds"})
        messages = model.messages_for(QUESTION)
        self.assertTrue(self.sent[0].content == encoded(historical_payload(messages)), "P1 wire bytes changed")
        identity = model.context_identity()
        self.assertEqual(identity["context_sha256"], "70545dbc5ed67b33b907301933a5556d7575d014bcc19472119d10ba11647fc6")
        self.assertEqual(identity["instruction_sha256"], "bff03c3ac45478f5530e9f3e152c277466ec838eeb960eda233ee1e30a73188c")
        self.assertEqual(hashlib.sha256(messages[0]["content"].encode()).hexdigest(),
                         "9384bdc712370a3276c5f508f88d019582fe5151af7af97fdc6fcd21b5d25ef2")
        self.assertNotIn("structured_output_identity", result.evidence)
        self.assert_private(result.evidence)

    async def test_wrapper_names_and_nested_snapshot_survive_caller_mutation(self):
        schema = {"type": "object", "properties": {"x": {"enum": [0, 1.5, False, None, "value"]}}, "required": ["x"]}
        for name in ("x", "A_z-09", "N" * 64):
            with self.subTest(name_length=len(name)):
                constraint = {"name": name, "schema": copy.deepcopy(schema)}
                result = gateway.json_schema_response_format(constraint)
                self.assertTrue(result == wrapper(schema, name), "Closed wrapper changed")
                self.assertEqual(set(result), {"type", "json_schema"})
                self.assertEqual(set(result["json_schema"]), {"name", "schema"})
                self.assertIsNot(result["json_schema"]["schema"], constraint["schema"])
                constraint["schema"]["properties"]["x"]["enum"].append("later")
                constraint["name"] = "changed"
                self.assertTrue(result == wrapper(schema, name), "Snapshot retained mutable caller data")
        constraint = {"name": "snapshot", "schema": copy.deepcopy(schema)}
        original = gateway.json_schema_response_format

        def snapshot_then_mutate(value):
            result = original(value)
            value["schema"]["properties"]["x"]["enum"].append("after_snapshot")
            return result

        client = self.client()
        with patch.object(gateway, "json_schema_response_format", side_effect=snapshot_then_mutate):
            await client.complete(MESSAGES, json_schema_constraint=constraint)
        actual = json.loads(self.sent[0].content)["response_format"]
        self.assertTrue(actual == wrapper(schema, "snapshot"), "Wire used caller mutation after snapshot")
        self.assertEqual(client.http_attempts, 1)

    async def test_all_native_recipes_use_exact_six_field_wire_and_matching_identities(self):
        fixture.build(self.database)
        schema = recipe_model.output_schema()
        self.assertEqual(recipe_model.context_identity(), P2_IDENTITY)
        self.assertEqual(recipe_model.structured_output_identity(), GENERATION)
        self.assertTrue(recipe_model.runtime_context()["output_schema"] == schema, "Multiple recipe schemas")
        for name in RECIPES:
            with self.subTest(recipe=name):
                result, complete = await self.recipe(json.dumps(proposal(name)), execute=True)
                self.assertIsNone(result.error)
                self.assertEqual(result.proposal.recipe_id, name)
                self.assertEqual(result.analysis_pack.status, "complete")
                actual = json.loads(self.sent[0].content)
                expected = {**historical_payload(recipe_model.messages_for(QUESTION)),
                            "response_format": wrapper(schema)}
                self.assertEqual(set(actual), set(historical_payload([])) | {"response_format"})
                self.assertTrue(actual == expected, "P2 wire has changed messages, defaults or provider extensions")
                self.assertTrue(self.sent[0].content == encoded(expected), "P2 wire serialization changed")
                self.assertEqual(set(complete.call_args.kwargs), {"timeout_seconds", "json_schema_constraint"})
                self.assertTrue(complete.call_args.kwargs["json_schema_constraint"] ==
                                {"name": "grepbit_recipe_request", "schema": schema}, "Adapter changed constraint")
                identity = result.evidence["structured_output_identity"]
                self.assertEqual(identity, GENERATION)
                self.assertEqual(identity["schema_sha256"], digest(actual["response_format"]["json_schema"]["schema"]))
                self.assertEqual(identity["response_format_sha256"], digest(actual["response_format"]))
                self.assertEqual(result.evidence["context_identity"], P2_IDENTITY)
                self.assertNotIn("invalid_json_fingerprint", result.evidence)

    async def test_generation_identity_is_derived_from_actual_authoritative_context_schema(self):
        schema = recipe_model.output_schema()
        schema["description"] = SCHEMA_CANARY
        with patch.object(recipe_model, "output_schema", return_value=schema) as source:
            result, _ = await self.recipe('{"outcome":"declined"}')
        self.assertEqual(source.call_count, 1)
        actual = json.loads(self.sent[0].content)["response_format"]
        self.assertTrue(actual == wrapper(schema), "Adapter sent a second schema")
        identity = result.evidence["structured_output_identity"]
        self.assertEqual(identity["schema_sha256"], digest(schema))
        self.assertEqual(identity["response_format_sha256"], digest(actual))
        self.assertNotEqual(identity["schema_sha256"], GENERATION["schema_sha256"])
        self.assertEqual(recipe_model.context_identity(), P2_IDENTITY)

    async def test_malformed_constraints_are_fixed_errors_before_http(self):
        base = {"name": "valid", "schema": {"type": "object"}}
        cases = [("list", []), ("string", SCHEMA_CANARY), ("boolean", True), ("number", 1),
                 ("empty", {}), ("missing_name", {"schema": base["schema"]}),
                 ("missing_schema", {"name": "valid"}), ("extra_field", {**base, "strict": True}),
                 ("prewrapped", wrapper(base["schema"]))]
        cases += [(f"name_{index}", {**base, "name": name}) for index, name in enumerate(
            ("", "x" * 65, "has space", "dot.name", "slash/name", "line\n", "\u6e2c", chr(0xD800), None, 1, True))]
        cases += [(f"schema_{index}", {**base, "schema": schema})
                  for index, schema in enumerate(({}, [], None, "object", True, 1))]
        for label, constraint in cases:
            with self.subTest(case=label):
                await self.rejected_constraint(constraint)
        with self.assertRaises(ModelError) as caught:
            gateway.json_schema_response_format(None)
        self.assertEqual(caught.exception.code, "invalid_input")

    async def test_non_json_schema_values_and_keys_cannot_be_coerced(self):
        values = [object(), b"bytes", {1, 2}, (1, 2), float("nan"), float("inf"),
                  -float("inf"), float("1e999"), chr(0xD800)]
        cases = [(f"value_{index}", {"description": SCHEMA_CANARY, "enum": [value]})
                 for index, value in enumerate(values)]
        cases += [(f"key_{index}", {"properties": {key: {"description": SCHEMA_CANARY}}})
                  for index, key in enumerate((1, 1.5, True, None, b"bytes", ("tuple",), chr(0xD800)))]
        for label, schema in cases:
            with self.subTest(case=label):
                await self.rejected_constraint({"name": "valid", "schema": schema})

    async def test_cycles_depth_and_numeric_limits_are_safe_zero_attempt_rejections(self):
        cycle = {}
        cycle["self"] = cycle
        array = []
        array.append(array)
        deep = {"type": "object"}
        for _ in range(sys.getrecursionlimit() + 50):
            deep = {"child": deep}
        previous = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, previous)
        sys.set_int_max_str_digits(640)
        for label, schema in (("dict_cycle", cycle), ("array_cycle", {"enum": array}),
                              ("depth", deep), ("numeric_limit", {"const": 10 ** 641})):
            with self.subTest(case=label):
                await self.rejected_constraint({"name": "valid", "schema": schema})

    async def test_schema_byte_cap_is_exact_and_separate_from_complete_request_cap(self):
        self.assertEqual(gateway.MAX_REQUEST_BYTES, 32768)
        schema = {"description": ""}
        schema["description"] = "x" * (32768 - len(encoded(schema)))
        constraint = {"name": "valid", "schema": schema}
        result = gateway.json_schema_response_format(constraint)
        self.assertEqual(len(encoded(result["json_schema"]["schema"])), 32768)
        await self.rejected_constraint(constraint, code="input_too_large")
        schema["description"] += "x"
        with self.assertRaises(ModelError) as caught:
            gateway.json_schema_response_format(constraint)
        self.assertEqual(caught.exception.code, "input_too_large")
        await self.rejected_constraint(constraint, code="input_too_large")

    async def test_total_request_exact_boundary_includes_ascii_and_multibyte_schema(self):
        for character in ("x", "\u6e2c"):
            with self.subTest(utf8_width=len(character.encode())):
                schema = {"type": "object", "description": ""}
                expected = {**historical_payload(MESSAGES), "response_format": wrapper(schema, "boundary")}
                room = 32768 - len(encoded(expected))
                count, remainder = divmod(room, len(character.encode()))
                schema["description"] = character * count + "x" * remainder
                self.assertEqual(len(encoded(expected)), 32768)
                constraint = {"name": "boundary", "schema": schema}
                client = self.client()
                await client.complete(MESSAGES, json_schema_constraint=constraint)
                self.assertEqual((client.http_attempts, len(self.sent), len(self.sent[0].content)), (1, 1, 32768))
                self.assertTrue(self.sent[0].content == encoded(expected), "Request boundary measured the wrong bytes")
                schema["description"] += "x"
                self.assertEqual(len(encoded(expected)), 32769)
                await self.rejected_constraint(constraint, code="input_too_large")

    async def test_shared_dag_expansion_stops_incrementally_at_the_byte_budget(self):
        schema = {"const": SCHEMA_CANARY}
        for _ in range(24):
            schema = {"anyOf": [schema, schema]}
        original = json.JSONEncoder.iterencode
        sizes = []
        client = self.client()

        def bounded(encoder, value, _one_shot=False):
            self.assertFalse(_one_shot, "Schema expansion must not use the unbounded one-shot encoder")
            for chunk in original(encoder, value, _one_shot=False):
                sizes.append(len(chunk.encode()))
                self.assertLessEqual(len(sizes), 32769, "Incremental expansion did not stop")
                yield chunk

        with patch.object(json.JSONEncoder, "iterencode", new=bounded), self.captured_output():
            with self.assertRaises(ModelError) as caught:
                await client.complete(MESSAGES, json_schema_constraint={"name": "dag", "schema": schema})
        self.assertEqual(caught.exception.code, "input_too_large")
        self.assertGreater(sum(sizes), 32768)
        self.assertLessEqual(sum(sizes), 32768 + 64)
        self.assertEqual((client.http_attempts, len(self.sent)), (0, 0))
        self.assert_private(str(caught.exception))

    async def test_configuration_values_and_dictionary_keys_are_private_before_send(self):
        config = GatewayConfig(BASE, KEY)
        fragments = (KEY, BASE, config.endpoint, "structured-private.invalid", "StRuCtUrEd-PrIvAtE.InVaLiD")
        for index, fragment in enumerate(fragments):
            for location in ("value", "key"):
                with self.subTest(fragment=index, location=location):
                    schema = ({"description": fragment} if location == "value"
                              else {"properties": {fragment: {"type": "string"}}})
                    await self.rejected_constraint({"name": "valid", "schema": schema}, config=config)

    async def test_private_names_and_json_escaped_api_keys_are_checked_as_raw_strings(self):
        await self.rejected_constraint({"name": KEY, "schema": {"type": "object"}})
        bare = GatewayConfig("http://StructuredPrivateHost/v1", "another-private-schema-key")
        await self.rejected_constraint(
            {"name": "sTrUcTuReDpRiVaTeHoSt", "schema": {"type": "object"}}, config=bare)
        escaped = GatewayConfig(BASE, 'dummy-"quoted\\private-key')
        for location in ("value", "key"):
            with self.subTest(location=location):
                schema = ({"description": escaped.api_key} if location == "value"
                          else {"properties": {escaped.api_key: {"type": "string"}}})
                self.assertFalse(escaped.api_key in json.dumps(schema), "Witness must require decoded-string scanning")
                await self.rejected_constraint({"name": "valid", "schema": schema}, config=escaped)

    async def test_ignored_constraint_never_repairs_content_or_uses_separate_reasoning(self):
        valid = json.dumps(proposal())
        for label, content in (("fence", "```json\n" + valid + "\n```"),
                               ("think", "<think>" + CANARY + "</think>" + valid),
                               ("trailing", valid + CANARY), ("malformed", '{"broken":')):
            with self.subTest(case=label):
                result, _ = await self.recipe(content)
                self.assertEqual((result.error.code, result.error.stage), ("invalid_json", "json_parse"))
                self.assertEqual(result.evidence["structured_output_identity"], GENERATION)
                self.assertTrue(result.evidence["invalid_json_fingerprint"] ==
                                json_diagnostics.invalid_json_fingerprint(content), "Diagnostic behavior changed")
                self.assertIsNone(result.proposal)
                self.assertEqual(result.evidence["stages"]["response_validation"], "passed")
                self.assertEqual(result.evidence["stages"]["request_validation"], "not_run")
                self.assertIn("response_format", json.loads(self.sent[0].content))

    async def test_wrong_schema_decline_and_envelope_failures_keep_existing_codes(self):
        wrong = {**proposal(), "recipe_id": "unknown"}
        bad_envelope = envelope(json.dumps(proposal()))
        bad_envelope["choices"][0]["message"]["role"] = "user"
        cases = [("schema", json.dumps(wrong), None, "invalid_request", "passed"),
                 ("decline", '{"outcome":"declined"}', None, "model_declined", "passed"),
                 ("envelope", "", bad_envelope, "invalid_response", "not_run")]
        for label, content, document, code, parsed in cases:
            with self.subTest(case=label):
                result, _ = await self.recipe(content, document=document)
                self.assertEqual(result.error.code, code)
                self.assertEqual(result.evidence["stages"]["json_parse"], parsed)
                self.assertNotIn("invalid_json_fingerprint", result.evidence)
                self.assertEqual(result.evidence["structured_output_identity"], GENERATION)

    async def test_provider_format_rejection_is_one_http_configuration_failure_without_fallback(self):
        result, complete = await self.recipe("", status=400,
                                             document={"error": {"message": CANARY, SCHEMA_CANARY: KEY}})
        self.assertEqual((result.error.code, result.error.http_status), ("http_configuration", 400))
        self.assertEqual(result.error.stop_reason, "configuration_failure")
        self.assertEqual((complete.call_count, result.evidence["client_http_attempts"]), (1, 1))
        self.assertEqual(result.evidence["structured_output_identity"], GENERATION)
        self.assertIn("response_format", json.loads(self.sent[0].content))
        self.assertNotIn("invalid_json_fingerprint", result.evidence)

    def test_candidate_manifest_pins_generation_sources_and_frozen_protocol_surfaces(self):
        fixture.build(self.database)
        manifest = runner.build_manifest(self.database)
        self.assertEqual(manifest["preparation"], {"kind": "candidate", "accepted_commit": None})
        identity = manifest["identities"]
        self.assertEqual(identity["structured_output"], GENERATION)
        self.assertEqual(identity["context"], P2_IDENTITY)
        for name in ("grepbit/gateway.py", "grepbit/recipe_model.py", "grepbit/json_diagnostics.py"):
            self.assertEqual(identity["files_sha256"][name], hashlib.sha256((runner.ROOT / name).read_bytes()).hexdigest())
        for name, expected in (
            ("grepbit/model.py", "c0fad390d0fe3e685b342f9b5a99348b5c412f631a007c3caa03de02e1d5403c"),
            ("grepbit/json_diagnostics.py", "56d9ad89b2427e2e90faf97bec6da58826feb7e809940e6e333b6d7c1c348db6"),
            ("tools/smoke.py", "91de6225de4f653b23310f29fcebdba5ce91d4e35c6ea413a5bbb73563070c42"),
            (runner.PANEL_ASSET, "93d08e2901e58f324db7eded85f578e7b6ac32a5ac4de912194ac07f705f085f"),
        ):
            self.assertEqual(hashlib.sha256((runner.ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertEqual((manifest["manifest_version"], manifest["panel_id"]),
                         ("p2.7-recipe-smoke-v1", "p2-recipe-smoke-v1"))
        self.assertEqual(manifest["stop_policy"], {
            "version": "p2.7-stops-v2", "network_codes": ["gateway_error", "rate_limited", "transport_error"],
            "consecutive_network_limit": 2, "timeout_code": "timeout", "consecutive_timeout_limit": 2,
            "reset": "Each streak resets on a result outside its own code set.",
            "immediate_adapter_stops": ["configuration_failure", "envelope_incompatibility", "budget_exhausted"],
            "runner_stops": ["panel_budget", "attempt_budget", "manifest_drift", "database_drift",
                             "source_identity_failure", "artifact_conflict", "artifact_io", "leakage_risk"],
            "timeout_origin": "Unknown; timeout is not evidence of a network failure.",
            "completion_commit": "Atomic report replacement after terminal payload fsync and final validity/deadline admission.",
            "panel_deadline": "Cooperative limit through publication preparation, not publication return or CLI acknowledgement.",
            "elapsed_sample": "Before final checkpoint/terminal preparation, not publication or acknowledgement time.",
        })
        self.assertEqual(runner.GRADING_STAGES, ("recipe", "request", "execution", "coverage", "value_agreement"))
        self.assertEqual((manifest["settings"]["max_request_bytes"], manifest["settings"]["max_client_http_attempts"]),
                         (32768, 9))
        self.assertFalse(self.sent)
        self.loader.assert_not_called()

    def test_missing_or_modified_generation_and_source_pins_reject_before_environment_loading(self):
        fixture.build(self.database)
        manifest = runner.build_manifest(self.database)
        variants = [("policy_missing", None, "missing")]
        variants += [(f"{field}_{operation}", field, operation) for field in GENERATION
                     for operation in ("missing", "modified")]
        variants += [("gateway_source", "grepbit/gateway.py", "source"),
                     ("adapter_source", "grepbit/recipe_model.py", "source")]
        for index, (label, field, operation) in enumerate(variants):
            with self.subTest(case=label):
                altered = copy.deepcopy(manifest)
                if field is None:
                    del altered["identities"]["structured_output"]
                elif operation == "source":
                    altered["identities"]["files_sha256"][field] = "0" * 64
                elif operation == "missing":
                    del altered["identities"]["structured_output"][field]
                else:
                    altered["identities"]["structured_output"][field] = "changed"
                path = self.root / f"changed-{index}.json"
                with path.open("x", encoding="utf-8") as stream:
                    json.dump(altered, stream)
                with self.assertRaises(smoke.SmokeError) as caught:
                    runner.live_preflight(path, manifest, gateway_policies=None,
                                          env_file=self.root / "never-read.env", environ={})
                self.assertEqual(caught.exception.code, "manifest_drift")
                self.loader.assert_not_called()
        valid = self.root / "candidate.json"
        with valid.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream)
        with self.assertRaises(runner.RecipeSmokeError) as caught:
            runner.live_preflight(valid, manifest, gateway_policies=None, env_file=None, environ={})
        self.assertEqual(caught.exception.code, "accepted_commit_required")
        self.assertFalse(self.sent)
        self.loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
