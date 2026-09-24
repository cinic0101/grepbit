"""Synthetic JP Bedrock admission, fake HTTP and archived-evidence tests."""
import asyncio
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.bedrock import BedrockClient, BedrockConfig
from tools import fixture, p3_assets as assets, p3_eval, recipe_smoke, smoke
from tools import p3_bedrock_candidate_probe as runner
from test_recipe_model import proposal

COMMIT = "1" * 40
OWNER = "https://github.com/cinic0101/grepbit/issues/64#issuecomment-1"
KEY = "dummy-bedrock-probe-key"
RAW = "PRIVATE_PROVIDER_COMPLETION_CANARY"


class BedrockCandidateProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Real network forbidden")))
            self.addCleanup(guard.assert_not_called)
        self.env_loader = self.enterContext(patch.object(runner, "client_from_env",
                                                         side_effect=AssertionError("Env access forbidden")))
        temporary = tempfile.TemporaryDirectory(prefix="p3-bedrock-synthetic-", dir=runner.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / "synthetic.sqlite"
        fixture.build(self.db)
        source = {"git_commit": COMMIT, "branch": "dev", "worktree_dirty": False,
                  "files_sha256": {}, "context": recipe_model.context_identity(),
                  "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(source)))
        self.enterContext(patch.object(runner.old_candidate, "_checkout",
                                       side_effect=recipe_smoke._accepted))
        self.prepared = self.root / "prepared"
        runner.prepare(self.db, self.prepared, accepted_commit=COMMIT,
                       gateway_policies=runner.POLICIES, transport_security=runner.TRANSPORT)
        self.packet_path = self.prepared / "manifest.json"
        self.packet = assets.read_asset(self.packet_path)
        self.auth_path = self.root / "authorization.json"
        runner.bind_authorization(self.packet_path, OWNER, self.auth_path)
        self.sent = []
        self.serial = 0

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    def client(self, *, content=None, handler=None):
        def respond(request):
            self.sent.append(bytes(request.content))
            if handler:
                return handler(request)
            return httpx.Response(200, json={
                "output": {"message": {"role": "assistant", "content": [
                    {"text": json.dumps(proposal()) if content is None else content}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 100, "outputTokens": 20,
                                                   "totalTokens": 120},
                "unrecognized_provider_value": RAW,
            })
        return BedrockClient(BedrockConfig(runner.REGION, runner.PROFILE, KEY),
                             transport=httpx.MockTransport(respond))

    async def run_case(self, **overrides):
        output = self.output()
        kwargs = {"packet_path": self.packet_path, "authorization_path": self.auth_path,
                  "accepted_commit": COMMIT, "gateway_policies": dict(runner.POLICIES),
                  "client": self.client(), "clock": lambda: 0.0,
                  "capture_http_400_body": True}
        kwargs.update(overrides)
        return output, await runner.run_probe(self.db, output, **kwargs)

    def test_packet_pins_jp_route_and_separate_schema_hashes(self):
        self.assertEqual(self.packet["candidate"], runner.candidate_identity())
        self.assertEqual(self.packet["candidate"]["allowed_destination_regions"],
                         ["ap-northeast-1", "ap-northeast-3"])
        self.assertEqual(self.packet["candidate"]["response_mode"], "bedrock_converse_normalized")
        self.assertEqual(self.packet["wire_schema_sha256"],
                         "d971f587cade56ed0096e102d5fdd12733f2fa52c038738a1da9e0f6517db21f")
        self.assertNotEqual(self.packet["canonical_schema_sha256"], self.packet["wire_schema_sha256"])
        self.assertEqual(self.packet["case_id"], "E01_overview.en")
        self.assertIn("tools/p3_bedrock_candidate_probe.py", self.packet["source_identity"]["files_sha256"])
        self.assertNotIn("owner_authorization_reference", self.packet)
        self.assertNotIn("semantic_identity", self.packet)
        self.assertEqual(self.packet["baseline_semantic_identity"]["limits"]["timeout"], 60)
        self.assertEqual(self.packet["effective_runtime_identity"]["limits"]["timeout"], 300)
        self.assertEqual(self.packet["effective_runtime_identity_sha256"],
                         assets.digest(self.packet["effective_runtime_identity"]))
        self.assertEqual(self.packet["diagnostic_capture"], {
            "http_400_body": "exclusive_private_sidecar", "max_bytes": 32768,
            "location": "sibling_private_directory"})
        self.env_loader.assert_not_called()

    def test_historical_v1_packet_contract_remains_readable(self):
        historical = deepcopy(self.packet)
        historical["version"] = runner.LEGACY_PACKET_VERSION
        historical.pop("diagnostic_capture")
        historical["command_template"] = runner.command_template(
            COMMIT, capture_http_400_body=False)
        self.assertEqual(runner._packet_contract(historical), historical)

    def test_private_body_name_is_ignored_even_outside_artifact_tree(self):
        path = runner.ROOT / "build-private" / "http-400-body.json"
        result = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", str(path)],
                                cwd=runner.ROOT, check=False, capture_output=True)
        self.assertEqual(result.returncode, 0)

    async def test_live_400_body_is_private_and_absent_from_report(self):
        raw = b'{"message":"Invalid structured output PRIVATE_AWS_CANARY"}'
        def fake_client(**kwargs):
            return BedrockClient(BedrockConfig(runner.REGION, runner.PROFILE, KEY),
                                 transport=httpx.MockTransport(lambda _: httpx.Response(
                                     400, headers={"content-type": "application/json"}, content=raw)),
                                 error_body_sink=kwargs["bedrock_error_body_sink"])
        self.env_loader.side_effect = fake_client
        output, report = await self.run_case(origin="live", client=None,
                                             env_file=self.root / "synthetic.env")
        private = output.with_name(output.name + "-private") / "http-400-body.json"
        self.assertEqual(private.read_bytes(), raw)
        self.assertEqual(stat.S_IMODE(private.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual((report["error_code"], report["http_status"]),
                         ("http_configuration", 400))
        self.assertNotIn("PRIVATE_AWS_CANARY", (output / "report.json").read_text())
        self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")

    async def test_private_capture_path_conflict_stops_before_env_or_send(self):
        output = self.output()
        output.with_name(output.name + "-private").mkdir(mode=0o700)
        report = await runner.run_probe(self.db, output, packet_path=self.packet_path,
                                        authorization_path=self.auth_path, accepted_commit=COMMIT,
                                        gateway_policies=dict(runner.POLICIES), origin="live",
                                        env_file=self.root / "synthetic.env", clock=lambda: 0.0,
                                        capture_http_400_body=True)
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["reservation"], "not_reserved")
        self.env_loader.assert_not_called()

    def test_failed_private_fsync_removes_partial_body(self):
        private_dir = self.root / "failed-private"
        private_dir.mkdir(mode=0o700)
        with patch.object(runner.os, "fsync", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                runner._write_private_error_body(private_dir, b"private partial body")
        self.assertFalse((private_dir / "http-400-body.json").exists())

    async def test_one_compatibility_success_keeps_model_identity_unobserved(self):
        output, report = await self.run_case()
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["compatibility_passed"])
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(report["observed_model"], None)
        self.assertEqual(report["model_identity"], "unobserved")
        self.assertEqual(report["compatibility"]["route_acceptance"], "passed")
        self.assertEqual(report["compatibility"]["native_execution"], "passed")
        self.assertNotIn(KEY, (output / "report.json").read_text())
        self.assertNotIn(RAW, (output / "report.json").read_text())
        projected = runner.read_report(output / "report.json")
        self.assertEqual(projected["requested_profile"], runner.PROFILE)
        self.assertEqual(projected["effective_runtime_identity_sha256"],
                         self.packet["effective_runtime_identity_sha256"])
        self.assertIsNone(projected["observed_model"])
        self.assertEqual(len(self.sent), 1)

    async def test_packet_timeout_reaches_recipe_and_client(self):
        client = self.client()
        bounded = []
        original_timeout = asyncio.timeout
        def capture_timeout(seconds):
            bounded.append(seconds)
            return original_timeout(seconds)
        with patch.object(runner.probe, "interpret_recipe_and_execute",
                          wraps=runner.probe.interpret_recipe_and_execute) as interpret, \
                patch.object(client, "complete", wraps=client.complete) as complete, \
                patch.object(asyncio, "timeout", side_effect=capture_timeout):
            output, report = await self.run_case(client=client)
        self.assertTrue(report["compatibility_passed"])
        self.assertEqual(self.packet["settings"]["call_timeout_seconds"], 300)
        self.assertEqual(interpret.call_args.kwargs["timeout_seconds"], 300)
        self.assertEqual(complete.call_args.kwargs["timeout_seconds"], 300)
        self.assertGreaterEqual(bounded.count(300), 2)
        self.assertEqual(runner.read_report(output / "report.json")["status"], "complete")

    async def test_invalid_authorization_or_route_stops_before_env(self):
        invalid = [None, {**assets.read_asset(self.auth_path), "packet_sha256": "0" * 64}]
        for value in invalid:
            if value is not None:
                self.auth_path.write_text(json.dumps(value))
            output, report = await self.run_case(origin="live", client=None,
                                                 env_file=self.root / "unread.env",
                                                 authorization_path=self.auth_path if value else None)
            self.assertEqual(report["runtime_invocations"], 0)
            self.assertEqual(report["client_http_attempts"], 0)
            self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")
            self.env_loader.assert_not_called()
        self.auth_path.write_text(json.dumps({"version": runner.AUTHORIZATION_VERSION,
            "packet_sha256": p3_eval._pin(self.packet_path)["sha256"],
            "owner_authorization_reference": OWNER}))
        changed = {**self.packet, "candidate": {**self.packet["candidate"],
                   "calling_region": "us-east-1"}}
        self.packet_path.write_text(json.dumps(changed))
        output, report = await self.run_case(origin="live", client=None, env_file=self.root / "unread.env")
        self.assertEqual(report["runtime_invocations"], 0)
        self.env_loader.assert_not_called()

    async def test_v2_live_capture_requires_explicit_programmatic_opt_in(self):
        for capture in (None, False):
            with self.subTest(capture=capture):
                output = self.output()
                kwargs = {} if capture is None else {"capture_http_400_body": capture}
                report = await runner.run_probe(
                    self.db, output, packet_path=self.packet_path,
                    authorization_path=self.auth_path, accepted_commit=COMMIT,
                    gateway_policies=dict(runner.POLICIES), origin="live",
                    env_file=self.root / "synthetic.env", clock=lambda: 0.0, **kwargs)
                self.assertEqual(report["status"], "stopped")
                self.assertEqual(report["error_code"], "invalid_configuration")
                self.assertEqual(report["reservation"], "not_reserved")
                self.assertEqual(report["client_http_attempts"], 0)
                self.assertEqual(report["runtime_invocations"], 0)
                self.assertFalse(output.with_name(output.name + "-private").exists())
        self.env_loader.assert_not_called()

    async def test_typed_failure_is_not_compatibility_pass(self):
        output, report = await self.run_case(client=self.client(content='{"outcome":"request"}'))
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["compatibility"]["typed_action"], "failed")
        self.assertEqual(report["compatibility"]["native_execution"], "not_run")
        self.assertEqual(report["observed_model"], None)
        self.assertFalse(report["compatibility_passed"])
        self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")

    async def test_wrong_region_client_stops_before_send(self):
        def respond(_request):
            self.fail("Wrong-region client must never send")
        client = BedrockClient(BedrockConfig("us-east-1", runner.PROFILE, KEY),
                               transport=httpx.MockTransport(respond))
        output, report = await self.run_case(client=client)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")

    async def test_client_timeout_limit_drift_stops_before_reservation(self):
        client = self.client()
        with patch.object(BedrockConfig, "max_call_timeout_seconds", 60):
            output, report = await self.run_case(client=client)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["reservation"], "not_reserved")
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")

    async def test_http_success_with_unsupported_response_stays_validation_failure(self):
        def respond(_request):
            return httpx.Response(200, json={"stopReason": "tool_use", "output": {}, "usage": {
                "inputTokens": 100, "outputTokens": 20, "totalTokens": 120}})
        output, report = await self.run_case(client=self.client(handler=respond))
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["runtime_stages"]["transport"], "passed")
        self.assertEqual(report["runtime_stages"]["response_validation"], "failed")
        self.assertEqual(report["compatibility"]["route_acceptance"], "passed")
        self.assertEqual(report["compatibility"]["native_execution"], "not_run")
        self.assertEqual(runner.read_report(output / "report.json")["status"], "stopped")

    async def test_reader_rejects_fabricated_observed_model(self):
        output, _ = await self.run_case()
        path = output / "report.json"
        value = assets.read_asset(path)
        value["observed_model"] = runner.PROFILE
        path.write_text(json.dumps(value))
        with self.assertRaises(runner.probe.ProbeError):
            runner.read_report(path)

    async def test_reader_rejects_effective_runtime_identity_tampering(self):
        output, _ = await self.run_case()
        path = output / "packet.json"
        value = assets.read_asset(path)
        value["effective_runtime_identity"]["limits"]["timeout"] = 60
        path.write_text(json.dumps(value))
        with self.assertRaises(runner.probe.ProbeError):
            runner.read_report(output / "report.json")

    async def test_reader_rejects_settled_reservation_without_invocation(self):
        output, _ = await self.run_case(client=BedrockClient(
            BedrockConfig("us-east-1", runner.PROFILE, KEY),
            transport=httpx.MockTransport(lambda _request: self.fail("Unexpected send"))))
        path = output / "report.json"
        value = assets.read_asset(path)
        self.assertEqual(value["runtime_invocations"], 0)
        value.update(reservation="settled", attempt_budget_used=1, possible_in_flight_attempts=0)
        path.write_text(json.dumps(value))
        with self.assertRaises(runner.probe.ProbeError):
            runner.read_report(path)

    def test_cli_invalid_choice_never_echoes_value(self):
        canary = "SYNTHETIC_PRIVATE_CANARY"
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = runner.main(["--live", "--gateway-cache", canary])
        self.assertEqual(result, 2)
        self.assertNotIn(canary, stderr.getvalue())
        self.assertIn("invalid_arguments", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
