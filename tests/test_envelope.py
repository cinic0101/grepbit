"""P1.3a offline compatibility witnesses; fake HTTP and real disposable SQLite."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import kernel, model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import fixture, smoke
from test_model import envelope, request_content, request_mapping, VALUES
from test_smoke import envelope as panel_envelope


KEY = "p13a-private-key-canary"
BASE = "https://p13a-private.invalid/v1"
MARKER = "P13A_PRIVATE_PROVIDER_VALUE"


class _OfflineCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name in ("socket.socket.connect", "socket.socket.connect_ex",
                     "socket.create_connection", "socket.getaddrinfo",
                     "httpx.AsyncHTTPTransport"):
            guard = patch(name, side_effect=AssertionError("Real network forbidden."))
            guard.start()
            self.addCleanup(guard.stop)
        artifacts = smoke.ROOT / ".artifacts"
        artifacts.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.sent = []

    def client(self, handler):
        def respond(request):
            self.sent.append(request)
            return handler(request)

        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    def assert_private(self, value):
        self.assertFalse(
            any(part in str(value) for part in (KEY, BASE, "p13a-private.invalid", MARKER)),
            "Provider-controlled keys or values escaped into evidence.",
        )


class EnvelopeModelTests(_OfflineCase):
    async def interpret(self, document=None, *, body=None, headers=None):
        if body is None:
            body = json.dumps(envelope() if document is None else document).encode()
        before = len(self.sent)
        client = self.client(lambda _: httpx.Response(
            200, content=body, headers={"content-type": "application/json", **(headers or {})},
        ))
        with patch("grepbit.model.execute_facts", wraps=kernel.execute_facts) as execution:
            result = await model.interpret_and_execute(
                "Four explicit March 2026 facts in Asia/Taipei.", self.database, client,
            )
        self.assertEqual(client.http_attempts, 1)
        self.assertEqual(len(self.sent) - before, 1)
        self.assert_private(result.evidence)
        self.assert_private(repr(result))
        if result.error:
            self.assert_private(str(result.error))
        return result, execution

    def assert_success(self, result, execution):
        self.assertIsNone(result.error)
        self.assertEqual(tuple(f.value for f in result.fact_pack.facts), VALUES)
        execution.assert_called_once()
        self.assertIsNone(result.evidence.get("response_shape"))

    def assert_envelope_failure(self, result, execution):
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.stage, "response_validation")
        self.assertEqual(result.error.stop_reason, "envelope_incompatibility")
        self.assertEqual(result.evidence["stages"]["json_parse"], "not_run")
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        self.assertIsNone(result.request)
        self.assertIsNone(result.fact_pack)
        execution.assert_not_called()

    async def test_minimal_response_allows_absent_index_and_optional_metadata(self):
        document = envelope()
        del document["model"]
        del document["choices"][0]["index"]
        result, execution = await self.interpret(document)
        self.assert_success(result, execution)
        self.assertIsNone(result.evidence["returned_model"])
        self.assertEqual(set(result.evidence["usage"].values()), {None})

    async def test_unknown_top_level_metadata_is_not_a_closed_schema(self):
        for value in (None, False, 42, 1.5, MARKER, [KEY], {"private": BASE}):
            with self.subTest(kind=type(value).__name__):
                document = envelope(vendor_extension=value)
                result, execution = await self.interpret(document)
                self.assert_success(result, execution)
                self.assertNotIn("vendor_extension", json.dumps(result.evidence))

    async def test_choice_provider_specific_fields_are_ignored(self):
        document = envelope()
        document["choices"][0]["provider_specific_fields"] = {
            "stop_reason": 106, "token_ids": [1, 2], "private": MARKER + KEY + BASE,
        }
        result, execution = await self.interpret(document)
        self.assert_success(result, execution)

    async def test_direct_vllm_choice_metadata_and_unrecognized_names_are_ignored(self):
        document = envelope()
        document["choices"][0].update(
            stop_reason=106, token_ids=[1, 2], cumulative_logprob=-2.0,
            future_provider_field={"private": MARKER + KEY + BASE},
        )
        result, execution = await self.interpret(document)
        self.assert_success(result, execution)

    async def test_message_metadata_and_separate_reasoning_are_not_content(self):
        document = envelope()
        document["choices"][0]["message"].update(
            annotations=[{"private": MARKER}], future_metadata={"private": KEY + BASE},
            reasoning="not JSON " + MARKER, reasoning_content=request_content(metrics=["booked_seats"]),
        )
        result, execution = await self.interpret(document)
        self.assert_success(result, execution)
        self.assertEqual(result.request.metrics, tuple(request_mapping()["metrics"]))

    async def test_unknown_usage_metadata_does_not_invent_known_counters(self):
        document = envelope(usage={
            "prompt_tokens": 11, "extra_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 2, "provider_extension": MARKER},
            "completion_tokens_details": {"reasoning_tokens": 1, "private": KEY + BASE},
            "provider_specific_fields": {"private": MARKER},
        })
        result, execution = await self.interpret(document)
        self.assert_success(result, execution)
        self.assertEqual(result.evidence["usage"], {
            "prompt_tokens": 11, "completion_tokens": None, "total_tokens": None,
        })

    async def test_required_semantic_fields_and_invalid_types_still_fail(self):
        mutations = [
            lambda d: d.pop("choices"),
            lambda d: d.update(choices=None),
            lambda d: d.update(choices={}),
            lambda d: d.update(choices=[]),
            lambda d: d["choices"].append(copy.deepcopy(d["choices"][0])),
            lambda d: d.update(choices=[None]),
            lambda d: d.update(choices=[7]),
            lambda d: d["choices"][0].pop("message"),
            lambda d: d["choices"][0].update(message=[]),
            lambda d: d["choices"][0]["message"].pop("role"),
            lambda d: d["choices"][0]["message"].update(role="user"),
            lambda d: d["choices"][0]["message"].pop("content"),
            lambda d: d["choices"][0].pop("finish_reason"),
        ]
        for value in (None, True, 1, -1, 1.0, "0", [], {}):
            mutations.append(lambda d, value=value: d["choices"][0].update(index=value))
        for value in (None, False, 1, [], {}):
            mutations.append(lambda d, value=value: d["choices"][0]["message"].update(content=value))
        for value in (None, False, 1, [], {}, "unknown", "error"):
            mutations.append(lambda d, value=value: d["choices"][0].update(finish_reason=value))
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                document = envelope()
                mutate(document)
                result, execution = await self.interpret(document)
                self.assert_envelope_failure(result, execution)

    async def test_competing_error_stream_text_audio_and_tools_are_not_metadata(self):
        mutations = [
            lambda d: d.update(error={"message": MARKER}),
            lambda d: d.update(object="chat.completion.chunk"),
            lambda d: d["choices"][0].update(delta={"content": MARKER}),
            lambda d: d["choices"][0].update(text=MARKER),
            lambda d: d["choices"][0].update(logprobs={}),
            lambda d: d["choices"][0]["message"].update(audio={"data": MARKER}),
            lambda d: d["choices"][0]["message"].update(tool_calls=[]),
            lambda d: d["choices"][0]["message"].update(function_call={}),
        ]
        for finish in ("tool_calls", "function_call", "content_filter"):
            mutations.append(lambda d, finish=finish: d["choices"][0].update(finish_reason=finish))
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                document = envelope()
                mutate(document)
                result, execution = await self.interpret(document)
                self.assert_envelope_failure(result, execution)

    async def test_provider_refusal_is_explicit_and_never_parsed_or_executed(self):
        document = envelope()
        document["choices"][0]["message"].update(refusal=MARKER + KEY + BASE, content=None)
        result, execution = await self.interpret(document)
        self.assertEqual(result.error.code, "model_declined")
        self.assertIsNone(result.error.stop_reason)
        self.assertIsNone(result.request)
        execution.assert_not_called()
        self.assertEqual(result.evidence["stages"]["json_parse"], "not_run")

    async def test_truncation_usage_budget_and_model_identity_remain_strict(self):
        cases = [
            ({"model": "other-model"}, "stop", "unexpected_model", "configuration_failure"),
            ({"model": "openai/gemma-4-31b"}, "stop", "unexpected_model", "configuration_failure"),
            ({}, "length", "truncated_output", "budget_exhausted"),
            ({"usage": {"completion_tokens": 2049}}, "stop", "output_token_budget", "budget_exhausted"),
        ]
        for fields, finish, code, stop in cases:
            with self.subTest(code=code):
                document = envelope(content="{not JSON", **fields)
                document["choices"][0].update(finish_reason=finish, provider_extension=MARKER)
                result, execution = await self.interpret(document)
                self.assertEqual(result.error.code, code)
                self.assertEqual(result.error.stop_reason, stop)
                self.assertEqual(result.evidence["response_shape"]["failure_code"], code)
                self.assertEqual(result.evidence["stages"]["json_parse"], "not_run")
                execution.assert_not_called()

    async def test_metadata_acceptance_does_not_relax_known_usage_validation(self):
        cases = [
            {"prompt_tokens": True}, {"completion_tokens": -1}, {"total_tokens": 2**63},
            {"prompt_tokens_details": []},
            {"completion_tokens_details": {"reasoning_tokens": "1"}},
        ]
        for number, usage in enumerate(cases):
            with self.subTest(number=number):
                document = envelope(usage=usage, provider_extension=MARKER)
                result, execution = await self.interpret(document)
                self.assert_envelope_failure(result, execution)

    async def test_product_json_and_request_schema_stay_closed_after_normalization(self):
        bad_json = [
            "{bad", "```json\n" + request_content() + "\n```",
            "explanation " + request_content(), request_content() + request_content(),
            '{"outcome":"declined","outcome":"request"}',
            '{"outcome":"request","request":{"metrics":[],"metrics":["booked_seats"]}}',
            '{"outcome":"declined","extra":NaN}', '{"outcome":"declined","extra":1e999}',
            '{"outcome":"declined","extra":"\\ud800"}',
        ]
        bad_requests = [
            "null", "[]", json.dumps({"outcome": "declined", "extra": True}),
            request_content(answer=7), request_content(sql="SELECT 7"),
            request_content(metrics="booked_seats"), request_content(metrics=["unknown"]),
            request_content(start="2026-04-01T00:00:00+08:00"),
        ]
        for code, contents in (("invalid_json", bad_json), ("invalid_request", bad_requests)):
            for number, content in enumerate(contents):
                with self.subTest(code=code, number=number):
                    document = envelope(content=content, provider_extension=MARKER)
                    document["choices"][0]["message"]["reasoning_content"] = request_content()
                    result, execution = await self.interpret(document)
                    self.assertEqual(result.error.code, code)
                    self.assertIsNone(result.error.stop_reason)
                    self.assertEqual(result.evidence["stages"]["response_validation"], "passed")
                    self.assertIsNone(result.evidence["response_shape"])
                    execution.assert_not_called()

    async def test_wrong_but_valid_request_and_constraints_are_not_repaired(self):
        document = envelope(content=request_content(metrics=["confirmed_booking_count"]))
        document["choices"][0]["provider_specific_fields"] = {"ignored_request": request_mapping()}
        result, execution = await self.interpret(document)
        self.assertIsNone(result.error)
        self.assertEqual(result.request.metrics, ("confirmed_booking_count",))
        self.assertEqual(result.fact_pack.facts[0].value, 7)
        execution.assert_called_once()
        client = self.client(lambda _: httpx.Response(200, json=document))
        with patch("grepbit.model.execute_facts") as execution:
            conflict = await model.interpret_and_execute(
                "Explicit booked seats.", self.database, client, constraints={"metrics": ["booked_seats"]},
            )
        self.assertEqual(conflict.error.code, "constraint_conflict")
        self.assertEqual(conflict.request.metrics, ("confirmed_booking_count",))
        self.assertIsNone(conflict.evidence["response_shape"])
        execution.assert_not_called()

    async def test_fingerprint_is_allowlisted_and_never_records_arbitrary_names_or_values(self):
        document = envelope(usage={"prompt_tokens": 11})
        document[KEY] = BASE
        choice = document["choices"][0]
        choice[BASE] = MARKER
        choice.update(stop_reason=MARKER, provider_specific_fields={"private": KEY})
        choice["message"].update({MARKER: KEY, "reasoning_content": BASE})
        choice.pop("finish_reason")
        result, execution = await self.interpret(document)
        self.assert_envelope_failure(result, execution)
        shape = result.evidence["response_shape"]
        self.assertEqual(shape["top_level"]["keys"], ["choices", "model", "usage"])
        self.assertEqual(shape["top_level"]["unknown_key_count"], 1)
        self.assertEqual(shape["choice"]["keys"], [
            "index", "message", "provider_specific_fields", "stop_reason",
        ])
        self.assertEqual(shape["choice"]["unknown_key_count"], 1)
        self.assertEqual(shape["message"]["keys"], ["content", "reasoning_content", "role"])
        self.assertEqual(shape["message"]["unknown_key_count"], 1)
        self.assertEqual(shape["index"], {"present": True, "type": "integer", "value_class": "zero"})
        self.assertEqual(shape["finish_reason"], {
            "present": False, "type": "absent", "value_class": None,
        })
        self.assertTrue(shape["model_present"])
        self.assertTrue(shape["usage_present"])
        self.assertEqual(shape["failure_code"], "unsupported_output")
        self.assertEqual(shape["failure_stage"], "response_validation")

    async def test_fingerprint_index_and_finish_values_are_bounded_classifications(self):
        cases = [
            (1, "integer", "nonzero"), (12345678901234567890, "integer", "nonzero"),
            (True, "boolean", None), (KEY, "string", None), ({KEY: BASE}, "object", None),
        ]
        for index, kind, value_class in cases:
            with self.subTest(kind=kind):
                document = envelope()
                document["choices"][0].update(index=index, finish_reason=MARKER + BASE)
                result, execution = await self.interpret(document)
                self.assert_envelope_failure(result, execution)
                shape = result.evidence["response_shape"]
                self.assertEqual(shape["index"], {
                    "present": True, "type": kind, "value_class": value_class,
                })
                self.assertEqual(shape["finish_reason"], {
                    "present": True, "type": "string", "value_class": None,
                })
        document = envelope()
        document["choices"][0].pop("index")
        document["choices"][0]["finish_reason"] = "error"
        result, _ = await self.interpret(document)
        self.assertEqual(result.evidence["response_shape"]["index"]["type"], "absent")
        self.assertEqual(result.evidence["response_shape"]["finish_reason"]["value_class"], "error")

    async def test_many_untrusted_extension_names_do_not_expand_the_fingerprint(self):
        document = envelope()
        document.update({f"{KEY}_{i}": MARKER for i in range(400)})
        document["choices"][0]["message"].pop("role")
        result, execution = await self.interpret(document)
        self.assert_envelope_failure(result, execution)
        shape = result.evidence["response_shape"]
        self.assertEqual(shape["top_level"]["unknown_key_count"], 400)
        self.assertLess(len(json.dumps(shape)), 1500)

    async def test_unparseable_and_unavailable_envelopes_have_no_invented_shape(self):
        bodies = [
            b"not JSON", b'{"choices":[],"choices":[]}', b'{"provider_metadata":NaN}',
            b'{"provider_metadata":"\\ud800"}', b"\xff",
        ]
        for number, body in enumerate(bodies):
            with self.subTest(number=number):
                result, execution = await self.interpret(body=body)
                self.assert_envelope_failure(result, execution)
                shape = result.evidence["response_shape"]
                self.assertFalse(shape["json_parsed"])
                self.assertEqual(shape["top_level"]["type"], "unavailable")
                self.assertIsNone(shape["model_present"])
                self.assertIsNone(shape["usage_present"])
                self.assertIsNone(shape["index"]["present"])
                self.assertIsNone(shape["finish_reason"]["present"])
        result, execution = await self.interpret(headers={"content-type": "text/event-stream"})
        self.assert_envelope_failure(result, execution)
        self.assertFalse(result.evidence["response_shape"]["json_parsed"])


class EnvelopeSmokeTests(_OfflineCase):
    def setUp(self):
        super().setUp()
        self.prepared = self.root / "prepared"
        smoke.prepare(self.database, self.prepared)
        self.manifest_path = self.prepared / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        self.by_question = {entry["question"]: entry for entry in self.manifest["inputs"]}
        self.output = self.root / "panel"

    def response(self, request):
        question = json.loads(request.content)["messages"][1]["content"]
        family = self.by_question[question]["family"]
        return panel_envelope(copy.deepcopy(self.manifest["oracle"][family]["request"]))

    async def run_panel(self, handler):
        return await smoke.run_panel(
            self.database, self.output, manifest_path=self.manifest_path, client=self.client(handler),
        )

    def assert_stop(self, report, attempted):
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["stop_reason"], "envelope_incompatibility")
        self.assertEqual(report["stop_classification"], "envelope_incompatibility")
        self.assertEqual(report["client_http_attempts"], attempted)
        self.assertEqual(report["completed_client_http_attempts"], attempted)
        self.assertEqual(report["possible_in_flight_attempts"], 0)
        self.assertEqual(len(self.sent), attempted)
        self.assertEqual(report["results"][attempted - 1]["outcome"], "invalid_output")
        for entry in report["results"][attempted:]:
            self.assertEqual(entry["status"], "not_run")
            self.assertEqual(entry["not_run_reason"], "envelope_incompatibility")
            self.assertEqual(entry["client_http_attempts"], 0)
            self.assertIsNone(entry["evidence"]["response_shape"])
        self.assertEqual(json.loads((self.output / "report.json").read_text()), report)

    async def test_metadata_compatibility_reaches_twelve_genuine_packs_without_new_prompts(self):
        def handler(request):
            document = self.response(request)
            document[MARKER] = KEY
            choice = document["choices"][0]
            choice.pop("index")
            choice.update(stop_reason=106, provider_specific_fields={"private": BASE})
            choice["message"].update(reasoning_content=MARKER, future_metadata=KEY)
            return httpx.Response(200, json=document)

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 12)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertEqual(report["summary"]["all_three_correct_families"], 4)
        contexts = []
        for request, entry in zip(self.sent, report["results"], strict=True):
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], MODEL)
            self.assertFalse(payload["stream"])
            self.assertEqual(payload["max_tokens"], 2048)
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["messages"][1]["content"], entry["question"])
            contexts.append(payload["messages"][0])
            self.assertEqual(entry["evidence"]["fact_pack"]["status"], "complete")
            self.assertIsNone(entry["evidence"]["response_shape"])
        self.assertTrue(all(context == contexts[0] for context in contexts))
        self.assert_private(json.dumps(report))

    async def test_first_incompatible_envelope_stops_without_a_second_send(self):
        def handler(request):
            self.assertEqual(len(self.sent), 1, "No repeated deployment mismatch calls.")
            return httpx.Response(200, json={"choices": []})

        report = await self.run_panel(handler)
        self.assert_stop(report, 1)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertEqual(report["summary"]["outcomes"], {"invalid_output": 1, "not_run": 11})

    async def test_incompatibility_after_success_keeps_both_results_and_remaining_not_run(self):
        def handler(request):
            self.assertLessEqual(len(self.sent), 2)
            if len(self.sent) == 1:
                return httpx.Response(200, json=self.response(request))
            return httpx.Response(200, json={"choices": []})

        report = await self.run_panel(handler)
        self.assert_stop(report, 2)
        self.assertEqual(report["results"][0]["outcome"], "correct")
        self.assertEqual(report["summary"]["outcomes"], {"correct": 1, "invalid_output": 1, "not_run": 10})

    async def test_model_json_schema_wrong_interpretation_and_decline_continue_per_input(self):
        def handler(request):
            document = self.response(request)
            document["provider_specific_fields"] = MARKER
            message = document["choices"][0]["message"]
            if len(self.sent) == 1:
                message["content"] = "{bad JSON"
            elif len(self.sent) == 2:
                proposal = json.loads(message["content"])
                proposal["request"]["unsupported"] = True
                message["content"] = json.dumps(proposal)
            elif len(self.sent) == 3:
                proposal = json.loads(message["content"])
                proposal["request"]["metrics"] = ["confirmed_booking_count"]
                message["content"] = json.dumps(proposal)
            elif len(self.sent) == 4:
                message["content"] = '{"outcome":"declined"}'
            return httpx.Response(200, json=document)

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 12)
        self.assertEqual([r["outcome"] for r in report["results"][:4]],
                         ["invalid_output", "invalid_output", "wrong", "false_refusal"])
        self.assertTrue(all(r["evidence"]["response_shape"] is None for r in report["results"]))
        self.assertEqual(report["results"][2]["grading"]["value_agreement"], "not_run")

    async def test_safe_fingerprint_survives_all_checkpoints_without_private_names_or_values(self):
        def handler(request):
            self.assertEqual(len(self.sent), 1)
            document = self.response(request)
            document[KEY] = BASE
            choice = document["choices"][0]
            choice[BASE] = MARKER
            choice["finish_reason"] = KEY
            choice["message"].update({MARKER: KEY, "reasoning": BASE})
            return httpx.Response(200, json=document)

        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            report = await self.run_panel(handler)
        self.assert_stop(report, 1)
        for path in self.output.glob("*.json"):
            self.assert_private(path.read_text())
        self.assert_private(output.getvalue())
        shape = report["results"][0]["evidence"]["response_shape"]
        self.assertEqual(shape["top_level"]["unknown_key_count"], 1)
        self.assertEqual(shape["finish_reason"]["type"], "string")
        self.assertIsNone(shape["finish_reason"]["value_class"])
        self.assertGreater(len(list(self.output.glob("checkpoint-*.json"))), 2)

    async def test_live_branch_stop_is_transport_mocked_and_uses_no_secret_file(self):
        client = self.client(lambda _: httpx.Response(200, json={"choices": []}))
        with patch("tools.smoke.GatewayClient", return_value=client) as constructor:
            report = await smoke.run_panel(
                self.database, self.output, manifest_path=self.manifest_path, origin="live",
                gateway_policies={"retries": "enabled", "fallback": "disabled", "cache": "disabled"},
                environ={"GREPBIT_LITELLM_BASE_URL": BASE, "GREPBIT_LITELLM_API_KEY": KEY},
            )
        constructor.assert_called_once()
        self.assert_stop(report, 1)
        self.assertEqual(report["live_model_attempts"], 1)  # Simulated counter; socket I/O is forbidden.
        self.assert_private(json.dumps(report))


if __name__ == "__main__":
    unittest.main()
