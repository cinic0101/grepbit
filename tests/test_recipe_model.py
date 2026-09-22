"""Offline recipe wiring and protocol controls; fake outputs are not model-quality evidence."""
import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from grepbit import (
    BreakdownAnalysisPack, BreakdownRequest, CompareAnalysisPack, CompareRequest,
    ExecutionLimits, KernelError, OverviewAnalysisPack, OverviewRequest,
)
from grepbit import gateway, model, recipe_model
from grepbit.catalog import LEARNINGOPS
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import fixture
from p3_historical_source import historical_bytes


ROOT = Path(__file__).parent.parent
BASE = "https://recipe-private.invalid/v1"
KEY = "dummy-recipe-private-key"
MARKER = "PRIVATE_RECIPE_PROVIDER_CANARY"
QUESTION = "How were bookings at CTR-A01 in March 2026?"
RECIPES = ("overview", "compare", "breakdown")
MOCK_HTTP_ATTEMPTS = 0


def period(month=3):
    return dict(start=f"2026-{month:02}-01T00:00:00+08:00",
                end=f"2026-{month + 1:02}-01T00:00:00+08:00", timezone="Asia/Taipei")


def proposal(recipe="overview"):
    native = {
        "overview": dict(period(), center_code="CTR-A01"),
        "compare": {role: dict(period(month), metrics=["confirmed_booked_amount"])
                    for role, month in (("current", 3), ("baseline", 2))},
        "breakdown": dict(period(), top_k=2),
    }[recipe]
    return dict(outcome="request", recipe_id=recipe, recipe_version="0.1", request=native)


def envelope(content=None, **changes):
    return {
        "model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content":
                                               json.dumps(proposal()) if content is None else content}}],
        **changes,
    }


class RecipeModelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                     "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "grepbit.gateway.GatewayConfig.from_env"):
            guard = patch(name, side_effect=AssertionError("Real network/config access forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "recipe.sqlite"
        fixture.build(self.database)

    def mutate(self, sql, parameters=()):
        with sqlite3.connect(self.database) as conn:
            conn.execute(sql, parameters)
        conn.close()

    def assert_private(self, value):
        self.assertFalse(any(part in str(value) for part in (KEY, BASE, "recipe-private.invalid", MARKER)),
                         "Provider-controlled values or configuration escaped")

    async def invoke(self, *, content=None, document=None, body=None, question=QUESTION, status=200,
                     headers=None, handler=None, clock=None, timeout_seconds=60):
        if body is None:
            body = json.dumps(envelope(content) if document is None else document).encode()
        calls, connections, packs, executions = [], [], [], {}
        connect = sqlite3.connect

        def capture(*args, **kwargs):
            self.assertEqual(len(calls), 1, "Database opened before the sole model response")
            self.assertIn("?mode=ro", args[0])
            conn = connect(*args, **kwargs)
            connections.append(conn)
            return conn

        def respond(request):
            global MOCK_HTTP_ATTEMPTS
            MOCK_HTTP_ATTEMPTS += 1
            calls.append(request)
            self.assertFalse(connections, "Model call attempted after database execution began")
            return handler(request) if handler else httpx.Response(
                status, content=body, headers={"content-type": "application/json", **(headers or {})})

        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        with ExitStack() as stack:
            stack.enter_context(patch.object(sqlite3, "connect", side_effect=capture))
            complete = stack.enter_context(patch.object(client, "complete", wraps=client.complete))
            for recipe in RECIPES:
                name = f"execute_{recipe}"
                execute = getattr(recipe_model, name)

                def tracked(*args, _execute=execute, **kwargs):
                    self.assertEqual(len(calls), 1)
                    pack = _execute(*args, **kwargs)
                    packs.append(pack)
                    return pack

                executions[recipe] = stack.enter_context(patch.object(recipe_model, name, side_effect=tracked))
            kwargs = {} if clock is None else {"clock": clock}
            result = await recipe_model.interpret_recipe_and_execute(
                question, self.database, client, timeout_seconds=timeout_seconds, **kwargs)
        self.assertEqual((client.http_attempts, result.evidence["client_http_attempts"]), (len(calls), len(calls)))
        self.assertLessEqual(len(calls), 1)
        self.assertLessEqual(complete.call_count, 1)
        self.assertLessEqual(len(connections), 1)
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
        for value in (result.evidence, repr(result), repr(result.proposal), repr(result.error)):
            self.assert_private(value)
        if result.error:
            self.assert_private("".join(traceback.format_exception(result.error)))
            self.assertIsNone(result.error.__traceback__)
            self.assertIsNone(result.error.__cause__)
            self.assertIsNone(result.error.__context__)
        return SimpleNamespace(result=result, calls=calls, executions=executions,
                               complete=complete, connections=connections, packs=packs)

    def assert_rejected(self, observed, code, *, before_execution=True):
        result = observed.result
        self.assertEqual(result.error.code, code)
        self.assertEqual(result.evidence["error_code"], code)
        self.assertEqual(result.evidence["stages"][result.error.stage], "failed")
        self.assertIsNone(result.analysis_pack)
        self.assertIsNone(result.evidence["analysis_pack"])
        self.assertIsNone(result.evidence["pack_status"])
        if before_execution:
            self.assertFalse(observed.connections)
            self.assertTrue(all(call.call_count == 0 for call in observed.executions.values()))
            self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")

    async def test_each_recipe_preserves_native_request_pack_and_one_executor(self):
        types = ((OverviewRequest, OverviewAnalysisPack), (CompareRequest, CompareAnalysisPack),
                 (BreakdownRequest, BreakdownAnalysisPack))
        for recipe, (request_type, pack_type) in zip(RECIPES, types):
            with self.subTest(recipe=recipe):
                candidate = proposal(recipe)
                if recipe == "compare":
                    candidate["request"]["baseline"]["center_id"] = None
                observed = await self.invoke(content=json.dumps(candidate))
                result = observed.result
                self.assertIsNone(result.error)
                self.assertIs(type(result.proposal.request), request_type)
                self.assertIs(type(result.analysis_pack), pack_type)
                self.assertIs(result.analysis_pack, observed.packs[0])
                self.assertIs(result.analysis_pack.request, result.proposal.request)
                self.assertEqual(result.proposal.recipe_id, recipe)
                self.assertEqual(result.proposal.recipe_version, "0.1")
                self.assertEqual(set(result.proposal.to_dict()), {"outcome", "recipe_id", "recipe_version", "request"})
                self.assertEqual(result.evidence["proposal"], result.proposal.to_dict())
                self.assertEqual(result.evidence["analysis_pack"],
                                 json.loads(json.dumps(result.analysis_pack.to_dict())))
                self.assertEqual((len(observed.calls), len(observed.connections)), (1, 1))
                for name, execution in observed.executions.items():
                    self.assertEqual(execution.call_count, int(name == recipe))
                selected = observed.executions[recipe].call_args
                self.assertEqual(selected.args[0], self.database)
                self.assertIs(selected.args[1], result.proposal.request)
                self.assertEqual(selected.kwargs["limits"], ExecutionLimits())
                self.assertEqual(result.evidence["stages"], dict.fromkeys(model.STAGES, "passed"))
                self.assertEqual((result.evidence["pack_status"], result.evidence["model_outcome"]), ("complete", "request"))
                self.assertEqual(result.evidence["context_identity"], recipe_model.context_identity())
                self.assertEqual([fact.value for fact in result.analysis_pack.facts],
                                 {"overview": [68000, 4, 6], "compare": [158000, 50000], "breakdown": [158000]}[recipe])
                if recipe != "overview":
                    self.assertEqual(result.analysis_pack.derived_facts[-1].value,
                                     Fraction(54, 25) if recipe == "compare" else Fraction(64, 79))
                with self.assertRaises(FrozenInstanceError):
                    result.proposal.recipe_id = "other"
                with self.assertRaises(FrozenInstanceError):
                    result.analysis_pack = None

    async def test_e01_e02_e03_three_languages_share_one_unbound_system_message(self):
        cases = json.loads((ROOT / "evals/cases/learningops.json").read_text())["cases"]
        variants = json.loads((ROOT / "evals/cases/learningops-languages.json").read_text())["variants"]
        bases = {case["id"]: case["question"] for case in cases}
        translated = {case["case_id"]: case for case in variants}
        system_messages = []
        for case_id, recipe in zip(("E01_overview", "E02_compare", "E03_share_denominator"), RECIPES):
            for language in ("zh-TW", "en", "ja"):
                with self.subTest(case=case_id, language=language):
                    question = bases[case_id] if language == "zh-TW" else translated[case_id][language]
                    observed = await self.invoke(question=question, content=json.dumps(proposal(recipe)))
                    self.assertIsNone(observed.result.error)
                    payload = json.loads(observed.calls[0].content)
                    self.assertEqual(set(payload), {"model", "messages", "temperature", "max_tokens",
                                                    "stream", "response_format"})
                    self.assertEqual(payload["response_format"], {
                        "type": "json_schema", "json_schema": {
                            "name": "grepbit_recipe_request", "schema": recipe_model.output_schema(),
                        },
                    })
                    self.assertEqual((payload["model"], payload["temperature"], payload["max_tokens"], payload["stream"]),
                                     (MODEL, 0, 2048, False))
                    self.assertEqual(payload["messages"], recipe_model.messages_for(question))
                    self.assertEqual(payload["messages"][1], {"role": "user", "content": question})
                    system_messages.append(payload["messages"][0]["content"])
        self.assertEqual(len(set(system_messages)), 1)
        for forbidden in ("E01_overview", "E02_compare", "E03_share_denominator", "CTR-A01",
                          '"CA"', "2026-03-01", "2026-02-01", '"top_k":2', "68000", "128000", "158000",
                          "reference_sql", "expected_behavior", "siblings", "source_rows"):
            self.assertNotIn(forbidden, system_messages[0])

    def test_common_schema_catalog_context_and_actual_system_hashes(self):
        context = recipe_model.runtime_context()
        identity = recipe_model.context_identity()
        system = recipe_model.messages_for(QUESTION)[0]["content"]
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(json.loads(system.split("\n", 1)[1]), context)
        self.assertEqual(identity["context_sha256"], digest(model.canonical_json(context)))
        self.assertEqual(identity["output_contract_sha256"], digest(model.canonical_json(context["output_schema"])))
        self.assertEqual(identity["instruction_sha256"], digest(recipe_model.SYSTEM_INSTRUCTION))
        self.assertEqual(identity["system_message_sha256"], digest(system))
        self.assertEqual(identity["catalog_sha256"], LEARNINGOPS.digest())
        self.assertNotIn("as_of", context)
        self.assertNotIn("bound_constraints", context)
        shapes = context["output_schema"]["oneOf"]
        self.assertEqual([branch["properties"]["recipe_id"]["const"] for branch in shapes[:3]], list(RECIPES))
        self.assertTrue(all(branch["additionalProperties"] is False for branch in shapes))
        requests = {branch["properties"]["recipe_id"]["const"]: branch["properties"]["request"] for branch in shapes[:3]}
        self.assertEqual(set(requests["overview"]["properties"]), {"center_code", "start", "end", "timezone"})
        self.assertEqual(set(requests["breakdown"]["properties"]), {"start", "end", "timezone", "top_k"})
        self.assertEqual(set(requests["compare"]["properties"]), {"current", "baseline"})
        for scope in requests["compare"]["properties"].values():
            self.assertEqual(set(scope["required"]), {"metrics", "start", "end", "timezone"})
            self.assertEqual(scope["properties"]["metrics"], {"const": ["confirmed_booked_amount"]})
            self.assertEqual(scope["properties"]["center_id"], {"type": "null"})
            self.assertIs(scope["additionalProperties"], False)

    async def test_frozen_p1_identities_and_protocol_helper_reuse(self):
        self.assertIs(recipe_model.protocol, model)
        expected = {
            "context_sha256": "70545dbc5ed67b33b907301933a5556d7575d014bcc19472119d10ba11647fc6",
            "instruction_sha256": "bff03c3ac45478f5530e9f3e152c277466ec838eeb960eda233ee1e30a73188c",
        }
        before = model.context_identity()
        for key, value in expected.items():
            self.assertEqual(before[key], value)
        # Preserve the original witness; P3.10 changes identity plumbing, not P1 wire/semantics.
        self.assertEqual(hashlib.sha256(historical_bytes("grepbit/model.py")).hexdigest(),
                         "c0fad390d0fe3e685b342f9b5a99348b5c412f631a007c3caa03de02e1d5403c")
        # The optional gateway extension is guarded by exact P1 wire tests, not a source repin.
        document = envelope()
        document["choices"][0]["message"]["role"] = "user"
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(model, name, wraps=getattr(model, name))) for name in
                     ("_content", "strict_json", "canonical_json", "_usage", "_response_shape")]
            observed = await self.invoke(document=document)
        self.assert_rejected(observed, "invalid_response")
        self.assertTrue(all(spy.call_count > 0 for spy in spies))
        self.assertEqual(tuple(observed.result.evidence["stages"]), model.STAGES)
        self.assertEqual(model.context_identity(), before)

    async def test_strict_json_rejects_duplicates_nonfinite_unicode_and_wrappers(self):
        valid = json.dumps(proposal())
        bad = ["{bad", "SELECT 1", "```json\n" + valid + "\n```", "prose " + valid, valid + valid,
               '{"outcome":"declined","outcome":"request"}',
               '{"outcome":"request","recipe_id":"breakdown","recipe_version":"0.1","request":{"top_k":1,"top_k":2}}',
               '{"outcome":"request","recipe_id":"compare","recipe_version":"0.1",'
               '"request":{"current":{"metrics":[],"metrics":["confirmed_booked_amount"]},"baseline":{}}}',
               '{"outcome":"declined","extra":NaN}', '{"outcome":"declined","extra":1e999}',
               '{"outcome":"declined","extra":"\\ud800"}']
        for index, content in enumerate(bad):
            with self.subTest(case=index):
                observed = await self.invoke(content=content)
                self.assert_rejected(observed, "invalid_json")
                self.assertEqual(len(observed.calls), 1)
                self.assertEqual(observed.result.evidence["stages"]["response_validation"], "passed")

    async def test_closed_root_recipe_version_and_branch_contract(self):
        bad = [None, [], "SELECT 1", {}, {"outcome": "declined", "request": {}},
               {**proposal(), "recipe_version": "0.2"}, {**proposal(), "recipe_version": 0.1},
               {**proposal(), "recipe_id": "overview|compare|breakdown"}, {**proposal(), "recipe_id": "unknown"},
               {**proposal(), "outcome": "declined"}, {**proposal(), "sql": "SELECT 1"},
               {**proposal(), "recipe_id": "breakdown"}, {**proposal(), "request": []}]
        for field in ("outcome", "recipe_id", "recipe_version", "request"):
            bad.append({key: value for key, value in proposal().items() if key != field})
        for index, candidate in enumerate(bad):
            with self.subTest(case=index):
                self.assert_rejected(await self.invoke(content=json.dumps(candidate)), "invalid_request")

    async def test_native_invalid_fields_are_rejected_not_stripped_or_repaired(self):
        cases = []
        for recipe, changes in (
            ("overview", {"center_code": 7}), ("overview", {"start": "2026-03-02T00:00:00+08:00"}),
            ("overview", {"center_id": "CA"}), ("overview", {"start": "2026-03-01T00:00:00"}),
            ("overview", {"end": "2026-05-01T00:00:00+08:00"}), ("overview", {"timezone": "UTC"}),
            ("breakdown", {"denominator": "selected_subtotal"}), ("breakdown", {"dimension": "category"}),
            ("breakdown", {"metrics": ["booked_seats"]}), ("breakdown", {"center_id": "CA"}),
        ):
            candidate = proposal(recipe)
            candidate["request"].update(changes)
            cases.append(candidate)
        for k in (True, 1.0, "2", None, 0, 4):
            candidate = proposal("breakdown")
            candidate["request"]["top_k"] = k
            cases.append(candidate)
        for role, change in (
            ("current", {"metrics": ["booked_seats"]}), ("baseline", {"center_id": "CA"}),
            ("current", {"filters": {"center_id": "CA"}}), ("baseline", {"metrics": "confirmed_booked_amount"}),
            ("current", {"timezone": "UTC"}), ("baseline", period(3)),
        ):
            candidate = proposal("compare")
            candidate["request"][role].update(change)
            cases.append(candidate)
        for index, candidate in enumerate(cases):
            with self.subTest(case=index):
                self.assert_rejected(await self.invoke(content=json.dumps(candidate)), "invalid_request")

    async def test_decline_is_one_attempt_without_database_or_repair(self):
        observed = await self.invoke(content='{"outcome":"declined"}')
        self.assert_rejected(observed, "model_declined")
        self.assertIsNone(observed.result.proposal)
        self.assertEqual(observed.result.evidence["model_outcome"], "declined")
        self.assertEqual(len(observed.calls), 1)

    async def test_wrong_but_valid_recipe_roles_k_and_center_are_not_intent_success(self):
        swapped = proposal("compare")
        swapped["request"]["current"], swapped["request"]["baseline"] = (
            swapped["request"]["baseline"], swapped["request"]["current"])
        wrong_k, wrong_center = proposal("breakdown"), proposal()
        wrong_k["request"]["top_k"] = 1
        wrong_center["request"]["center_code"] = "CTR-A02"
        questions = {
            "overview": QUESTION,
            "compare": "How did all-center booked amount in March 2026 compare with February 2026?",
            "breakdown": "What share of all March 2026 booked amount came from the top two courses?",
        }
        for candidate, intended in ((proposal(), proposal("breakdown")), (swapped, proposal("compare")),
                                    (wrong_k, proposal("breakdown")), (wrong_center, proposal())):
            with self.subTest(recipe=candidate["recipe_id"], request=candidate["request"]):
                observed = await self.invoke(content=json.dumps(candidate), question=questions[intended["recipe_id"]])
                result = observed.result
                self.assertIsNone(result.error)
                self.assertEqual(result.evidence["pack_status"], "complete")
                native = {"overview": OverviewRequest, "compare": CompareRequest,
                          "breakdown": BreakdownRequest}[candidate["recipe_id"]].from_mapping(candidate["request"])
                self.assertEqual(result.proposal.request, native)
                expected = {"overview": OverviewRequest, "compare": CompareRequest,
                            "breakdown": BreakdownRequest}[intended["recipe_id"]].from_mapping(intended["request"])
                self.assertNotEqual((result.proposal.recipe_id, native), (intended["recipe_id"], expected))
                self.assertIn("do not prove user-intent coverage", result.evidence["limitations"][0])
                self.assertNotIn("intent_correct", result.evidence)
                if candidate is swapped:
                    self.assertEqual([f.value for f in result.analysis_pack.facts], [50000, 158000])
                    self.assertEqual(result.analysis_pack.derived_facts[1].value, Fraction(-54, 79))
                elif candidate is wrong_k:
                    self.assertEqual(result.analysis_pack.derived_facts[1].value, Fraction(34, 79))
                elif candidate is wrong_center:
                    self.assertEqual([f.value for f in result.analysis_pack.facts], [30000, 1, 3])

    async def test_provider_extensions_and_separate_reasoning_are_not_proposals(self):
        document = envelope(usage={"prompt_tokens": 11, "completion_tokens": 17, "total_tokens": 28,
                                   "vendor": {KEY: MARKER}})
        document[MARKER] = BASE
        document["choices"][0]["provider_specific_fields"] = {KEY: MARKER}
        document["choices"][0]["message"].update(
            reasoning_content=json.dumps(proposal("breakdown")), reasoning=MARKER + KEY,
            **{BASE: KEY})
        observed = await self.invoke(document=document)
        self.assertIsNone(observed.result.error)
        self.assertEqual(observed.result.proposal.recipe_id, "overview")
        self.assertEqual(observed.result.evidence["usage"], {"prompt_tokens": 11, "completion_tokens": 17, "total_tokens": 28})
        self.assertIsNone(observed.result.evidence["response_shape"])
        self.assertEqual(observed.result.evidence["returned_model"], MODEL)

    async def test_absent_model_and_usage_remain_unknown_without_invented_counters(self):
        document = envelope()
        del document["model"]
        del document["choices"][0]["index"]
        observed = await self.invoke(document=document)
        self.assertIsNone(observed.result.error)
        self.assertIsNone(observed.result.evidence["returned_model"])
        self.assertEqual(set(observed.result.evidence["usage"].values()), {None})
        self.assertEqual(observed.result.evidence["finish_reason"], "stop")

    async def test_unapproved_model_alias_is_rejected_without_exporting_the_alias(self):
        for alias in ("openai/gemma-4-31b", MARKER):
            with self.subTest(alias_kind="unapproved"):
                observed = await self.invoke(document=envelope(model=alias))
                self.assert_rejected(observed, "unexpected_model")
                self.assertIsNone(observed.result.evidence["returned_model"])
                self.assertTrue(observed.result.evidence["response_shape"]["model_present"])
                self.assertEqual(observed.result.error.stop_reason, "configuration_failure")
                self.assertNotIn(alias, json.dumps(observed.result.evidence))

    async def test_invalid_envelope_fingerprint_and_malformed_payload_never_leak_canaries(self):
        document = envelope()
        document.update({f"{MARKER}_{i}": KEY for i in range(200)})
        choice = document["choices"][0]
        choice[KEY] = BASE
        choice["message"].update({BASE: MARKER, "reasoning_content": KEY})
        del choice["finish_reason"]
        observed = await self.invoke(document=document)
        self.assert_rejected(observed, "unsupported_output")
        shape = observed.result.evidence["response_shape"]
        self.assertEqual(shape["top_level"]["unknown_key_count"], 200)
        self.assertEqual(shape["choice"]["unknown_key_count"], 1)
        self.assertEqual(shape["message"]["unknown_key_count"], 1)
        self.assertEqual(shape["failure_code"], "unsupported_output")
        self.assertLess(len(json.dumps(shape)), 1500)
        for body in (b"\xff", (KEY + MARKER + "not JSON").encode(),
                     b'{"choices":[],"choices":[]}', b'{"private":NaN}'):
            with self.subTest(body_kind="malformed"):
                observed = await self.invoke(body=body)
                self.assert_rejected(observed, "invalid_response")
                self.assertIs(observed.result.evidence["response_shape"]["json_parsed"], False)
        bad_request = proposal()
        bad_request[MARKER] = {KEY: BASE}
        self.assert_rejected(await self.invoke(content=json.dumps(bad_request)), "invalid_request")
        private_center = proposal()
        private_center["request"]["center_code"] = KEY
        observed = await self.invoke(content=json.dumps(private_center))
        self.assert_rejected(observed, "kernel_failure", before_execution=False)
        self.assertEqual(observed.result.evidence["kernel_error_code"], "unknown_entity")
        self.assertEqual(observed.result.proposal.request.center_code, KEY)
        self.assertEqual(observed.result.evidence["proposal"]["request"]["center_code"], "[redacted]")

    async def test_http_and_transport_failures_are_classified_once_without_database(self):
        for status, code, transport in ((401, "auth_failed", False), (302, "redirect_blocked", False),
                                         (429, "rate_limited", True), (503, "gateway_error", True)):
            with self.subTest(status=status):
                observed = await self.invoke(status=status, body=(KEY + MARKER).encode())
                self.assert_rejected(observed, code)
                self.assertEqual(observed.result.evidence["http_status"], status)
                self.assertIs(observed.result.error.transport_failure, transport)
                self.assertEqual(len(observed.calls), 1)
        for error, code in ((httpx.ConnectError(KEY + BASE + MARKER), "transport_error"),
                            (httpx.ReadTimeout(KEY + MARKER), "timeout")):
            with self.subTest(code=code):
                def fail(_):
                    raise error
                observed = await self.invoke(handler=fail)
                self.assert_rejected(observed, code)
                self.assertEqual(len(observed.calls), 1)

    async def test_output_token_byte_and_truncation_bounds_precede_execution(self):
        truncated = envelope()
        truncated["choices"][0]["finish_reason"] = "length"
        for kwargs, code in (
            ({"document": envelope(usage={"completion_tokens": 2049})}, "output_token_budget"),
            ({"document": truncated}, "truncated_output"),
            ({"body": b"x" * (gateway.MAX_RESPONSE_BYTES + 1)}, "response_too_large"),
            ({"document": envelope(usage={"prompt_tokens": True})}, "invalid_response"),
        ):
            with self.subTest(code=code):
                observed = await self.invoke(**kwargs)
                self.assert_rejected(observed, code)
                self.assertEqual(len(observed.calls), 1)

    async def test_input_byte_boundary_invalid_unicode_and_request_size_are_offline(self):
        accepted = await self.invoke(question="x" * gateway.MAX_INPUT_BYTES)
        self.assertIsNone(accepted.result.error)
        for question, code in ((None, "invalid_input"), (" ", "invalid_input"), ("\ud800", "invalid_input"),
                               ("x" * (gateway.MAX_INPUT_BYTES + 1), "input_too_large")):
            with self.subTest(code=code, kind=type(question).__name__):
                observed = await self.invoke(question=question)
                self.assert_rejected(observed, code)
                self.assertFalse(observed.calls)
        with patch.object(recipe_model, "_messages", return_value=[
            {"role": "system", "content": "x" * gateway.MAX_REQUEST_BYTES},
            {"role": "user", "content": QUESTION},
        ]):
            observed = await self.invoke()
        self.assert_rejected(observed, "input_too_large")
        self.assertFalse(observed.calls)

    async def test_real_optional_category_gap_is_partial_native_data_not_model_error(self):
        self.mutate("ALTER TABLE courses RENAME COLUMN category TO unavailable_category")
        observed = await self.invoke()
        result = observed.result
        self.assertIsNone(result.error)
        self.assertEqual([f.value for f in result.analysis_pack.facts], [68000, 4, 6])
        self.assertEqual(result.evidence["pack_status"], "partial")
        self.assertEqual(result.analysis_pack.slots[-1].reason, "unsupported_source")
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "passed")

    async def test_empty_compare_and_breakdown_are_failed_data_packs_and_zero_is_undefined(self):
        for recipe in ("compare", "breakdown"):
            candidate = proposal(recipe)
            if recipe == "compare":
                candidate["request"]["baseline"].update(period(1))
            else:
                candidate["request"].update(period(1))
            with self.subTest(recipe=recipe, data="empty"):
                observed = await self.invoke(content=json.dumps(candidate))
                self.assertIsNone(observed.result.error)
                self.assertEqual(observed.result.analysis_pack.status, "failed")
                self.assertEqual(observed.result.evidence["pack_status"], "failed")
                self.assertEqual(observed.result.evidence["stages"]["kernel_execution"], "passed")
                self.assertTrue(any(slot.state == "unavailable" for slot in observed.result.analysis_pack.slots))
        self.mutate("UPDATE booking_items SET unit_price_minor=0,discount_minor=0")
        for recipe in ("compare", "breakdown"):
            with self.subTest(recipe=recipe, data="zero"):
                observed = await self.invoke(content=json.dumps(proposal(recipe)))
                self.assertIsNone(observed.result.error)
                self.assertEqual(observed.result.evidence["pack_status"], "complete")
                derived = observed.result.analysis_pack.derived_facts[-1]
                self.assertEqual((derived.value, derived.state), (None, "undefined"))
                self.assertEqual(derived.reason, "zero_baseline" if recipe == "compare" else "zero_total")

    async def test_native_kernel_code_allowlist_and_unknown_code_are_safe(self):
        cases = {
            "budget_exceeded": "budget_exhausted", "output_limit_exceeded": "budget_exhausted",
            "unsupported_source": "source_failure", "invalid_catalog": "source_failure",
            "invalid_limits": "source_failure", "unknown_entity": "kernel_failure",
            "invalid_request": "kernel_failure", "unknown_metric": "kernel_failure",
            "component_timeout": "kernel_failure",
            "ambiguous_entity": "kernel_failure", "incompatible_facts": "kernel_failure",
            "arithmetic_overflow": "kernel_failure", "snapshot_lost": "kernel_failure",
            "execution_failure": "kernel_failure", MARKER: "kernel_failure",
        }
        for native, expected in cases.items():
            with self.subTest(code="unknown" if native == MARKER else native):
                with patch.object(recipe_model, "execute_overview", side_effect=KernelError(native, KEY + BASE + MARKER)):
                    observed = await self.invoke()
                self.assert_rejected(observed, expected, before_execution=False)
                self.assertEqual(observed.result.evidence["kernel_error_code"], "unknown" if native == MARKER else native)
                self.assertEqual(observed.executions["overview"].call_count, 1)
                self.assertFalse(observed.connections)

    async def test_real_required_overflow_and_native_global_snapshot_failure_drop_packs(self):
        execute = recipe_model.execute_overview
        with patch.object(recipe_model, "execute_overview", side_effect=lambda db, req, **_: execute(
                db, req, limits=ExecutionLimits(max_source_rows=48))):
            observed = await self.invoke()
        self.assert_rejected(observed, "budget_exhausted", before_execution=False)
        self.assertEqual(observed.result.evidence["kernel_error_code"], "budget_exceeded")
        from grepbit import overview
        bind = overview._bind_center_code

        def corrupt(conn, code, snapshot, *args):
            result = bind(conn, code, snapshot, *args)
            snapshot["id"] = "trusted-metadata-corruption"
            return result

        with patch.object(overview, "_bind_center_code", side_effect=corrupt):
            observed = await self.invoke()
        self.assert_rejected(observed, "kernel_failure", before_execution=False)
        self.assertEqual(observed.result.evidence["kernel_error_code"], "snapshot_lost")
        self.mutate("UPDATE booking_items SET seats=1,unit_price_minor=?,discount_minor=0 "
                    "WHERE item_id IN ('I01','I02')", (2**62,))
        observed = await self.invoke()
        self.assert_rejected(observed, "kernel_failure", before_execution=False)
        self.assertEqual(observed.result.evidence["kernel_error_code"], "execution_failure")

    async def test_remaining_prompt_and_model_time_bounds_native_execution(self):
        clock = [100.0]
        messages = recipe_model._messages

        def prompt(*args):
            result = messages(*args)
            clock[0] += 0.2
            return result

        def model_response(_):
            clock[0] += 0.5
            return httpx.Response(200, json=envelope())

        with patch.object(recipe_model, "_messages", side_effect=prompt):
            observed = await self.invoke(clock=lambda: clock[0], timeout_seconds=1, handler=model_response)
        self.assertIsNone(observed.result.error)
        self.assertAlmostEqual(observed.complete.call_args.kwargs["timeout_seconds"], 0.8)
        self.assertAlmostEqual(observed.executions["overview"].call_args.kwargs["limits"].timeout_seconds, 0.3)
        self.assertAlmostEqual(observed.result.evidence["elapsed_seconds"], 0.7)

    async def test_deadline_covers_prompt_model_native_serialization_and_safe_export(self):
        messages, execute = recipe_model._messages, recipe_model.execute_overview
        serialize, export = OverviewAnalysisPack.to_dict, GatewayClient.safe_export
        for phase in ("prompt", "model", "native", "serialization", "export"):
            with self.subTest(phase=phase):
                clock = [100.0]

                def prompt(*args):
                    result = messages(*args)
                    clock[0] = 101.0
                    return result

                def native(*args, **kwargs):
                    result = execute(*args, **kwargs)
                    clock[0] = 101.0
                    return result

                def serialized(pack):
                    result = serialize(pack)
                    clock[0] = 101.0
                    return result

                def exported(client, evidence):
                    result = export(client, evidence)
                    if "stages" in evidence:
                        clock[0] = 101.0
                    return result

                def response(_):
                    if phase == "model":
                        clock[0] = 101.0
                    return httpx.Response(200, json=envelope())

                targets = {
                    "prompt": (recipe_model, "_messages", prompt),
                    "native": (recipe_model, "execute_overview", native),
                    "serialization": (OverviewAnalysisPack, "to_dict", serialized),
                    "export": (GatewayClient, "safe_export", exported),
                }
                with ExitStack() as stack:
                    if phase in targets:
                        owner, name, replacement = targets[phase]
                        stack.enter_context(patch.object(owner, name, new=replacement))
                    observed = await self.invoke(clock=lambda: clock[0], timeout_seconds=1, handler=response)
                ran = phase not in ("prompt", "model")
                self.assert_rejected(observed, "timeout", before_execution=not ran)
                self.assertEqual(len(observed.calls), 0 if phase == "prompt" else 1)
                self.assertEqual(observed.executions["overview"].call_count, int(ran))
                self.assertEqual(observed.result.evidence["stages"]["kernel_execution"], "failed" if ran else "not_run")
                self.assertEqual(observed.result.error.stage, "transport")
                self.assertTrue(observed.result.error.transport_failure)

    async def test_invalid_deadline_types_and_bounds_never_attempt_transport(self):
        for timeout in (None, True, False, "1", 0, -1, 61, 10**400, float("nan"), float("inf")):
            with self.subTest(kind=type(timeout).__name__):
                observed = await self.invoke(timeout_seconds=timeout)
                self.assert_rejected(observed, "invalid_configuration")
                self.assertFalse(observed.calls)
                observed.complete.assert_not_called()

    async def test_runtime_execution_reads_no_evaluator_files_or_local_configuration(self):
        open_file, import_module = builtins.open, builtins.__import__

        def guarded_open(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(file)).absolute()
                self.assertNotEqual(path.name, ".env")
                self.assertFalse(any(path.is_relative_to(ROOT / name) for name in ("tools", "tests", "evals")))
            return open_file(file, *args, **kwargs)

        def guarded_import(name, *args, **kwargs):
            self.assertFalse(any(name == prefix or name.startswith(prefix + ".") for prefix in ("tools", "tests", "evals")))
            return import_module(name, *args, **kwargs)

        with (patch("builtins.open", side_effect=guarded_open), patch("io.open", side_effect=guarded_open),
              patch("builtins.__import__", side_effect=guarded_import)):
            for recipe in RECIPES:
                observed = await self.invoke(content=json.dumps(proposal(recipe)))
                self.assertIsNone(observed.result.error)


if __name__ == "__main__":
    unittest.main()
