"""Offline synthetic lifecycle and privacy checks for the Compare diagnostic."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import MODEL
from tools import evaluate, fixture, p3_completion_diagnostic as diagnostic, recipe_smoke


class CompletionDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="compare-diagnostic-test-", dir=evaluate.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        slot = (self.root / "run").relative_to(evaluate.ROOT).as_posix()
        self.enterContext(patch.object(diagnostic, "SLOT", slot))
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.commit = "1" * 40
        source = {"git_commit": self.commit, "branch": "dev", "worktree_dirty": False,
                  "files_sha256": {}, "context": recipe_model.context_identity(),
                  "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(source)))
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            self.enterContext(patch(target, side_effect=AssertionError("external access forbidden")))
        self.packet = self.root / "packet.json"
        self.authorization = self.root / "authorization.json"

    def prepare(self):
        diagnostic.prepare(self.database, self.packet, accepted_commit=self.commit)
        diagnostic.bind_authorization(self.packet, self.authorization, diagnostic.GRANT)

    def client_factory(self, response, sent):
        def make(_env, expected_sha):
            def respond(request):
                sent.append(request)
                self.assertEqual(hashlib.sha256(request.content).hexdigest(), expected_sha)
                return response(request)
            config = diagnostic.DiagnosticGatewayConfig("http://diagnostic.invalid/v1", "synthetic-token")
            return diagnostic.DiagnosticGatewayClient(config, expected_sha,
                                                      transport=httpx.MockTransport(respond))
        return make

    @staticmethod
    def envelope(content='{"outcome":"declined"}', *, finish="stop", model=MODEL, usage=True):
        result = {"model": model, "choices": [{"index": 0, "finish_reason": finish,
                  "message": {"role": "assistant", "content": content,
                              "reasoning_content": "PRIVATE_REASONING_CANARY"}}]}
        if usage:
            result["usage"] = {"prompt_tokens": 10, "completion_tokens": 11, "total_tokens": 21,
                               "completion_tokens_details": {"reasoning_tokens": 3}}
        return result

    async def run_synthetic(self, response):
        self.prepare()
        sent = []
        result = await diagnostic.run_live(self.database, self.packet, self.authorization,
                                           accepted_commit=self.commit, env_file=self.root / "unused.env",
                                           client_factory=self.client_factory(response, sent))
        return result, sent

    async def test_full_lifecycle_wire_privacy_and_archive_reader(self):
        def response(_):
            return httpx.Response(200, json=self.envelope("{" + '"outcome":"declined","canary":"PRIVATE_CONTENT_CANARY"}'))
        result, sent = await self.run_synthetic(response)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["client_http_attempts"], 3)
        self.assertEqual(len(sent), 3)
        self.assertEqual(result["summary"], {"selected": 3, "reserved": 0, "returned": 3, "failed": 0})
        for request, selected in zip(sent, json.loads(self.packet.read_text())["selected"]):
            self.assertEqual(hashlib.sha256(request.content).hexdigest(), selected["request_sha256"])
            self.assertEqual(json.loads(request.content)["messages"][1]["content"].encode(),
                             next(case.question.encode() for case in evaluate.load_panel_entry(
                                 diagnostic.PANEL, self.database)[1].cases if case.case_id == selected["case_id"]))
        for path in (self.root / "run").iterdir():
            if path.is_file():
                raw = path.read_bytes()
                self.assertNotIn(b"PRIVATE_REASONING_CANARY", raw)
                self.assertNotIn(b"PRIVATE_CONTENT_CANARY", raw)
                self.assertNotIn(b"synthetic-token", raw)
        self.assertEqual(diagnostic.read_report(self.root / "run/report.json"), result)

    async def test_length_repetition_and_missing_usage_are_observed_without_text(self):
        content = "x" * 96
        result, _ = await self.run_synthetic(lambda _: httpx.Response(200, json=self.envelope(content, finish="length", usage=False)))
        observation = result["results"][0]["observation"]
        self.assertEqual(observation["finish_reason"], "length")
        self.assertEqual(observation["max_repeated_32_char_block_count"], 3)
        self.assertEqual(observation["json_parse"], "error")
        self.assertEqual(observation["usage"]["total_tokens"], None)

    async def test_unexpected_model_stops_without_publishing_label(self):
        result, sent = await self.run_synthetic(lambda _: httpx.Response(200, json=self.envelope(model="PRIVATE_MODEL_CANARY")))
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["stop_reason"], "anomaly")
        self.assertEqual(result["results"][0]["error_code"], "invalid_envelope")
        self.assertNotIn("PRIVATE_MODEL_CANARY", (self.root / "run/report.json").read_text())

    async def test_two_transport_failures_stop(self):
        def response(_):
            raise httpx.ConnectError("PRIVATE_ERROR_CANARY")
        result, sent = await self.run_synthetic(response)
        self.assertEqual(len(sent), 2)
        self.assertEqual(result["stop_reason"], "network_streak")
        self.assertEqual([row["state"] for row in result["results"]], ["failed", "failed", "not_started"])
        self.assertNotIn("PRIVATE_ERROR_CANARY", (self.root / "run/report.json").read_text())

    async def test_two_timeouts_stop(self):
        result, sent = await self.run_synthetic(lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("PRIVATE_TIMEOUT")))
        self.assertEqual(len(sent), 2)
        self.assertEqual(result["stop_reason"], "timeout_streak")
        self.assertNotIn("PRIVATE_TIMEOUT", (self.root / "run/report.json").read_text())

    async def test_one_timeout_then_two_returns_completes_attempt_plan(self):
        index = 0
        def response(_):
            nonlocal index
            index += 1
            if index == 1:
                raise httpx.ReadTimeout("synthetic")
            return httpx.Response(200, json=self.envelope())
        result, sent = await self.run_synthetic(response)
        self.assertEqual(len(sent), 3)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summary"]["failed"], 1)

    async def test_response_byte_cap_stops_immediately(self):
        result, sent = await self.run_synthetic(lambda _: httpx.Response(
            200, content=b"x" * 131073, headers={"content-type": "application/json"}))
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["stop_reason"], "anomaly")
        self.assertEqual(result["results"][0]["error_code"], "response_too_large")

    async def test_usage_over_output_cap_stops(self):
        def response(_):
            body = self.envelope()
            body["usage"]["completion_tokens"] = 2049
            return httpx.Response(200, json=body)
        result, sent = await self.run_synthetic(response)
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["stop_reason"], "anomaly")
        self.assertEqual(result["results"][0]["error_code"], "invalid_envelope")

    async def test_malformed_usage_is_safe_terminal_archive(self):
        def response(_):
            body = self.envelope()
            body["usage"]["prompt_tokens"] = -1
            return httpx.Response(200, json=body)
        result, sent = await self.run_synthetic(response)
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["stop_reason"], "anomaly")
        self.assertEqual(result["results"][0]["error_code"], "invalid_envelope")
        self.assertEqual(diagnostic.read_report(self.root / "run/report.json"), result)

    async def test_explicit_null_usage_fields_remain_unknown(self):
        def response(_):
            body = self.envelope()
            body["usage"] = {"prompt_tokens": None, "completion_tokens": None,
                             "total_tokens": None,
                             "completion_tokens_details": {"reasoning_tokens": None}}
            return httpx.Response(200, json=body)
        result, _ = await self.run_synthetic(response)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["results"][0]["observation"]["usage"],
                         dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens")))

    def test_malformed_usage_categories_fail_closed(self):
        for value in (-1, True, "PRIVATE_USAGE_CANARY", [], {}):
            with self.subTest(value=value):
                body = self.envelope()
                body["usage"]["prompt_tokens"] = value
                with self.assertRaises(diagnostic.DiagnosticError) as caught:
                    diagnostic.observe(json.dumps(body).encode(), 200)
                self.assertEqual(caught.exception.code, "invalid_envelope")

    async def test_env_symlink_prevents_credential_read_and_send(self):
        self.prepare()
        real = self.root / "synthetic.env"
        real.write_text("synthetic")
        linked = self.root / "linked.env"
        linked.symlink_to(real)
        def forbidden(*_):
            self.fail("client factory must not read credentials or send")
        result = await diagnostic.run_live(self.database, self.packet, self.authorization,
                                           accepted_commit=self.commit, env_file=linked,
                                           client_factory=forbidden)
        self.assertEqual(result["client_http_attempts"], 0)
        self.assertEqual(result["stop_reason"], "anomaly")
        self.assertEqual(result["results"][0]["error_code"], "artifact_conflict")

    async def test_https_route_mismatch_prevents_transport(self):
        self.prepare()
        sent = []
        def https_client(_env, expected_sha):
            config = diagnostic.DiagnosticGatewayConfig("https://diagnostic.invalid/v1", "synthetic-token")
            return diagnostic.DiagnosticGatewayClient(config, expected_sha,
                transport=httpx.MockTransport(lambda request: sent.append(request)))
        result = await diagnostic.run_live(self.database, self.packet, self.authorization,
                                           accepted_commit=self.commit, env_file=self.root / "unused.env",
                                           client_factory=https_client)
        self.assertEqual(sent, [])
        self.assertEqual(result["results"][0]["error_code"], "invalid_configuration")

    async def test_reader_rejects_forced_later_send_and_elapsed_completion(self):
        index = 0
        def response(_):
            nonlocal index
            index += 1
            if index == 1:
                raise httpx.ReadTimeout("synthetic")
            return httpx.Response(200, json=self.envelope())
        report, _ = await self.run_synthetic(response)
        invalid = deepcopy(report)
        invalid["results"][1].update(state="failed", error_code="timeout", observation=None)
        invalid["summary"] = diagnostic._summary(invalid["results"])
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic._report(invalid, report["packet_sha256"], report["authorization_sha256"])
        invalid = deepcopy(report)
        invalid["elapsed_seconds"] = 390.25
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic._report(invalid, report["packet_sha256"], report["authorization_sha256"])
        allowed = deepcopy(report)
        allowed["results"][2]["elapsed_seconds"] = 90.25
        diagnostic._report(allowed, report["packet_sha256"], report["authorization_sha256"])

    async def test_drift_before_second_send_stops(self):
        self.prepare()
        sent = []
        original = diagnostic.build_packet
        calls = 0
        def changed(database, accepted_commit):
            nonlocal calls
            calls += 1
            packet = original(database, accepted_commit)
            if calls >= 3:
                packet["source_pins"]["tools/evaluate.py"] = "0" * 64
            return packet
        with patch.object(diagnostic, "build_packet", side_effect=changed):
            result = await diagnostic.run_live(self.database, self.packet, self.authorization,
                                               accepted_commit=self.commit, env_file=self.root / "unused.env",
                                               client_factory=self.client_factory(lambda _: httpx.Response(
                                                   200, json=self.envelope()), sent))
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["stop_reason"], "anomaly")

    async def test_persistence_failure_before_second_send_stops(self):
        self.prepare()
        sent = []
        original = diagnostic._persist
        calls = 0
        def fail_after_first(artifacts, report):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise diagnostic.DiagnosticError("artifact_io")
            return original(artifacts, report)
        with patch.object(diagnostic, "_persist", side_effect=fail_after_first):
            with self.assertRaises(diagnostic.DiagnosticError):
                await diagnostic.run_live(self.database, self.packet, self.authorization,
                                          accepted_commit=self.commit, env_file=self.root / "unused.env",
                                          client_factory=self.client_factory(lambda _: httpx.Response(
                                              200, json=self.envelope()), sent))
        self.assertEqual(len(sent), 1)
        self.assertEqual(diagnostic.read_report(self.root / "run/report.json")["client_http_attempts"], 1)

    async def test_publication_preparation_overrun_is_budget_stop(self):
        self.prepare()
        sent = []
        now = [0.0]
        calls = 0
        original = diagnostic._persist
        def advance_after_third_result(artifacts, report):
            nonlocal calls
            calls += 1
            original(artifacts, report)
            if calls == 7:
                now[0] = 391.25
        with patch.object(diagnostic, "_persist", side_effect=advance_after_third_result):
            result = await diagnostic.run_live(self.database, self.packet, self.authorization,
                                               accepted_commit=self.commit, env_file=self.root / "unused.env",
                                               client_factory=self.client_factory(lambda _: httpx.Response(
                                                   200, json=self.envelope()), sent), clock=lambda: now[0])
        self.assertEqual(len(sent), 3)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["stop_reason"], "budget")
        self.assertEqual(result["elapsed_seconds"], 391.25)

    async def test_cancellation_keeps_reserved_possible_attempt(self):
        self.prepare()
        sent = []
        def cancel(_):
            raise __import__("asyncio").CancelledError()
        with self.assertRaises(__import__("asyncio").CancelledError):
            await diagnostic.run_live(self.database, self.packet, self.authorization,
                                      accepted_commit=self.commit, env_file=self.root / "unused.env",
                                      client_factory=self.client_factory(cancel, sent))
        report = diagnostic.read_report(self.root / "run/report.json")
        self.assertEqual(len(sent), 1)
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertEqual(report["results"][0]["state"], "reserved")

    def test_observation_envelope_and_reasoning_only(self):
        envelope = self.envelope(None)
        observation = diagnostic.observe(json.dumps(envelope).encode(), 200)
        self.assertEqual(observation["json_parse"], "absent")
        self.assertEqual(observation["content_bytes"], None)
        self.assertGreater(observation["reasoning_bytes"], 0)
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic.observe(json.dumps(self.envelope(model="other")).encode(), 200)
        malformed = self.envelope('{"outcome":[],"recipe_id":{}}')
        observed = diagnostic.observe(json.dumps(malformed).encode(), 200)
        self.assertEqual(observed["json_parse"], "valid")
        self.assertIsNone(observed["outcome"])
        self.assertIsNone(observed["recipe_id"])
        malformed["choices"][0]["index"] = False
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic.observe(json.dumps(malformed).encode(), 200)
        alternate = self.envelope(None)
        alternate["choices"][0]["message"].pop("reasoning_content")
        alternate["choices"][0]["message"]["reasoning"] = "PRIVATE_REASONING_ALIAS"
        self.assertGreater(diagnostic.observe(json.dumps(alternate).encode(), 200)["reasoning_bytes"], 0)

    async def test_reader_rejects_tampered_report_and_replay(self):
        result, _ = await self.run_synthetic(lambda _: httpx.Response(200, json=self.envelope()))
        with self.assertRaises(Exception):
            await diagnostic.run_live(self.database, self.packet, self.authorization,
                                      accepted_commit=self.commit, env_file=self.root / "unused.env")
        path = self.root / "run/report.json"
        report = json.loads(path.read_text())
        report["results"][0]["observation"]["unknown_key_count"] = "PRIVATE_CANARY"
        path.write_text(json.dumps(report))
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic.read_report(path)

    def test_binding_requires_exact_grant(self):
        diagnostic.prepare(self.database, self.packet, accepted_commit=self.commit)
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic.bind_authorization(self.packet, self.authorization,
                                          "https://github.com/cinic0101/grepbit/issues/79#issuecomment-2")
        self.assertFalse(self.authorization.exists())


if __name__ == "__main__":
    unittest.main()
