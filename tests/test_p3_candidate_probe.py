"""Candidate packet/auth/one-shot regressions; synthetic identity witness and fake HTTP only."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GEMMA_12B, GatewayClient, GatewayConfig, ModelError
from tools import fixture, p3_assets as assets, p3_eval, p3_probe as legacy, recipe_smoke, smoke
from tools import p3_candidate_model as candidate, p3_candidate_probe as runner
from test_recipe_model import proposal
from test_recipe_clarification import clarify

COMMIT = "1" * 40
OWNER = "https://github.com/cinic0101/grepbit/issues/56#issuecomment-1"
BASE = "http://candidate-probe.invalid/v1"
KEY = "dummy-candidate-probe-key"
RAW = "PRIVATE_PROVIDER_COMPLETION_CANARY"
CHECKOUT = runner._checkout


class CandidateProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Real network forbidden")))
            self.addCleanup(guard.assert_not_called)
        self.loader = self.enterContext(patch.object(
            GatewayConfig, "from_env", side_effect=AssertionError("Real env forbidden")))
        temporary = tempfile.TemporaryDirectory(prefix="p310-synthetic-", dir=runner.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "synthetic.sqlite"
        fixture.build(self.database)
        self.candidate_path = self.root / "synthetic-candidate.json"
        self.candidate_path.write_text(json.dumps({"synthetic_fixture_only": True}))
        self.candidate_hash = p3_eval._pin(self.candidate_path)["sha256"]

        def fixture_identity(path):
            if path != self.candidate_path or p3_eval._pin(path)["sha256"] != self.candidate_hash:
                raise ModelError("invalid_configuration")
            return GEMMA_12B

        self.enterContext(patch.object(candidate, "load_identity", side_effect=fixture_identity))
        self.source = {"git_commit": COMMIT, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {}, "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(self.source)))
        # Only the checkout witness is synthetic; packet/source/DB rebuilding remains native.
        self.enterContext(patch.object(runner, "_checkout", side_effect=recipe_smoke._accepted))
        self.prepared = self.root / "prepared"
        runner.prepare(self.database, self.prepared, candidate_path=self.candidate_path,
                       accepted_commit=COMMIT, gateway_policies=runner.POLICIES,
                       transport_security=runner.TRANSPORT)
        self.packet_path = self.prepared / "manifest.json"
        self.packet = assets.read_asset(self.packet_path)
        self.authorization = self.root / "synthetic-authorization.json"
        runner.bind_authorization(self.packet_path, OWNER, self.authorization)
        self.serial = 0
        self.sent = []

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    def client(self, *, content=None, returned_model=GEMMA_12B.model_alias, handler=None, base=BASE):
        def respond(request):
            self.sent.append(bytes(request.content))
            if handler:
                return handler(request)
            return httpx.Response(200, json={"model": returned_model, "choices": [{
                "index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                    "content": json.dumps(proposal()) if content is None else content,
                    "reasoning_content": RAW}}], "unrecognized_provider_value": RAW})
        return GatewayClient(GatewayConfig(base, KEY, GEMMA_12B.model_alias, expected_model=GEMMA_12B),
                             transport=httpx.MockTransport(respond))

    async def run_probe(self, **kwargs):
        self.out = self.output()
        defaults = {"packet_path": self.packet_path, "authorization_path": self.authorization,
                    "accepted_commit": COMMIT, "gateway_policies": dict(runner.POLICIES),
                    "client": self.client(), "clock": lambda: 0.0}
        defaults.update(kwargs)
        return await runner.run_probe(self.database, self.out, **defaults)

    def rewrite(self, path, value):
        path.write_text(json.dumps(value))

    def test_packet_pins_closed_candidate_current_source_and_unchanged_semantics(self):
        self.assertEqual(self.packet["candidate"], candidate.identity())
        self.assertEqual(self.packet["case_id"], "E01_overview.en")
        self.assertEqual(self.packet["question_sha256"], legacy.QUESTION_SHA256)
        self.assertEqual(self.packet["semantic_identity_sha256"], candidate.SEMANTICS_SHA256)
        self.assertIn("tools/p3_candidate_probe.py", self.packet["source_identity"]["files_sha256"])
        self.assertIn("tools/p3_candidate_model.py", self.packet["source_identity"]["files_sha256"])
        self.assertEqual(self.packet["state"], "prepared_not_authorized")
        self.assertNotIn("owner_authorization_reference", self.packet)
        self.assertEqual(self.packet["settings"], runner.settings())
        self.loader.assert_not_called()

    def test_real_candidate_loader_rejects_any_nonpinned_file(self):
        # Exercise production loader separately from the synthetic deployment witness.
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location("candidate_loader_witness", candidate.__file__)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(ModelError):
            module.load_identity(self.candidate_path)

    def test_checkout_requires_current_clean_dev_and_cached_refs(self):
        with patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=COMMIT)):
            CHECKOUT(self.source, COMMIT)
            for changed in ({"branch": "feature"}, {"worktree_dirty": True}, {"git_commit": "2" * 40}):
                with self.assertRaises((legacy.ProbeError, recipe_smoke.RecipeSmokeError)):
                    CHECKOUT({**self.source, **changed}, COMMIT)
        with patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="2" * 40)):
            with self.assertRaises(legacy.ProbeError):
                CHECKOUT(self.source, COMMIT)

    def test_bind_is_exclusive_and_does_not_change_packet(self):
        before = self.packet_path.read_bytes()
        with self.assertRaises(assets.P3Error):
            runner.bind_authorization(self.packet_path, OWNER, self.authorization)
        self.assertEqual(self.packet_path.read_bytes(), before)
        self.assertEqual(assets.read_asset(self.authorization)["packet_sha256"], smoke._digest(before))
        self.loader.assert_not_called()

    async def test_missing_bad_authorization_fails_before_env_client_or_runtime(self):
        valid = assets.read_asset(self.authorization)
        invalid = [None, {**valid, "owner_authorization_reference": ""},
                   {**valid, "owner_authorization_reference": OWNER.replace("/56#", "/52#")},
                   {**valid, "packet_sha256": "0" * 64}, {**valid, "unknown": True},
                   {**valid, "version": "p3-formal-live-authorization-v1"}]
        for value in invalid:
            if value is not None:
                self.rewrite(self.authorization, value)
            with patch.object(runner, "GatewayClient") as factory, \
                    patch.object(legacy, "interpret_recipe_and_execute") as runtime:
                report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env",
                                             authorization_path=None if value is None else self.authorization)
            self.assertEqual((report["client_http_attempts"], report["runtime_invocations"]), (0, 0))
            factory.assert_not_called()
            runtime.assert_not_called()
            self.loader.assert_not_called()
            self.assertEqual(runner.read_report(self.out / "report.json")["status"], "stopped")

    async def test_stale_packet_candidate_source_and_route_fail_before_env(self):
        changes = {"candidate": {**candidate.identity(), "candidate_identity_sha256": "0" * 64},
                   "accepted_commit": "2" * 40, "database_sha256": "0" * 64,
                   "question_sha256": "0" * 64, "exposure": "frozen_fresh",
                   "settings": {**runner.settings(), "max_client_http_attempts": 2},
                   "semantic_identity_sha256": "0" * 64, "transport_security": "tls_verification_enabled"}
        for field, value in changes.items():
            packet = {**self.packet, field: value}
            self.rewrite(self.packet_path, packet)
            self.rewrite(self.authorization, {"version": runner.AUTHORIZATION_VERSION,
                "packet_sha256": p3_eval._pin(self.packet_path)["sha256"], "owner_authorization_reference": OWNER})
            report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
            self.assertEqual(report["runtime_invocations"], 0, field)
            self.loader.assert_not_called()

    async def test_current_source_or_db_or_candidate_drift_fails_before_env(self):
        for field, value in (("branch", "feature"), ("worktree_dirty", True), ("git_commit", "2" * 40)):
            before = deepcopy(self.source)
            self.source[field] = value
            report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
            self.assertEqual(report["runtime_invocations"], 0)
            self.source = before
        self.candidate_path.write_text("{}")
        report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
        self.assertEqual(report["runtime_invocations"], 0)
        self.loader.assert_not_called()

    async def test_database_drift_fails_before_env(self):
        with self.database.open("ab") as stream:
            stream.write(b"drift")
        report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
        self.assertEqual(report["runtime_invocations"], 0)
        self.loader.assert_not_called()

    async def test_runtime_source_hash_drift_fails_before_env(self):
        self.source["files_sha256"]["grepbit/recipe_model.py"] = "0" * 64
        report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
        self.assertEqual(report["runtime_invocations"], 0)
        self.loader.assert_not_called()

    async def test_runtime_cannot_send_a_second_request(self):
        actual = legacy.interpret_recipe_and_execute
        async def misbehaving(question, database, client, **kwargs):
            await actual(question, database, client, **kwargs)
            return await actual(question, database, client, **kwargs)
        with patch.object(legacy, "interpret_recipe_and_execute", side_effect=misbehaving):
            report = await self.run_probe()
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(report["error_code"], "attempt_limit")
        self.assertFalse(report["compatibility_passed"])

    async def test_snapshot_failure_preserves_readable_incomplete_evidence_before_env(self):
        with patch.object(runner._CandidateProbe, "snapshot", side_effect=smoke.SmokeError("artifact_io")):
            report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env")
        self.assertIsNone(report["identity"])
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(runner.read_report(self.out / "report.json")["error_code"], "artifact_io")
        self.loader.assert_not_called()

    async def test_cli_attestations_must_match_before_env(self):
        for key in runner.POLICIES:
            wrong = {**runner.POLICIES, key: "disabled" if runner.POLICIES[key] == "enabled" else "enabled"}
            report = await self.run_probe(origin="live", client=None, env_file=self.root / "unread.env",
                                         gateway_policies=wrong)
            self.assertEqual(report["client_http_attempts"], 0)
        self.loader.assert_not_called()

    async def test_valid_authorization_reaches_only_mocked_config_and_client(self):
        client = self.client()
        with patch.object(GatewayConfig, "from_env", return_value=client.config) as loader, \
                patch.object(runner, "GatewayClient", return_value=client):
            report = await self.run_probe(origin="live", client=None, env_file=self.root / "synthetic.env")
        self.assertTrue(report["compatibility_passed"])
        self.assertEqual(loader.call_args.kwargs["expected_model"], GEMMA_12B)
        # This exercises live accounting with MockTransport, not a real live call.
        self.assertEqual(report["live_model_attempts"], 1)

    async def test_success_is_single_reserved_call_with_safe_evidence_and_archived_readback(self):
        def handle(request):
            active = assets.read_asset(self.out / "report.json")
            self.assertEqual((active["reservation"], active["runtime_invocations"], active["possible_in_flight_attempts"]),
                             ("in_progress", 1, 1))
            return httpx.Response(200, json={"model": GEMMA_12B.model_alias, "choices": [{
                "index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                    "content": json.dumps(proposal("compare")), "reasoning": RAW}}]})
        # Structurally valid Compare for the Overview question is still compatibility, not quality.
        report = await self.run_probe(client=self.client(handler=handle))
        self.assertTrue(report["compatibility_passed"])
        self.assertEqual((report["client_http_attempts"], report["runtime_invocations"], report["live_model_attempts"]), (1, 1, 0))
        self.assertEqual(report["reservation"], "settled")
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertEqual((self.out / "packet.json").read_bytes(), self.packet_path.read_bytes())
        self.assertEqual((self.out / "authorization.json").read_bytes(), self.authorization.read_bytes())
        with patch.object(runner, "build_packet", side_effect=AssertionError("Current source consulted")):
            self.assertTrue(runner.read_report(self.out / "report.json")["compatibility_passed"])
        for path in self.out.glob("*.json"):
            text = path.read_text()
            for unsafe in (BASE, KEY, RAW, "proposal", "analysis_pack", "reasoning", "Authorization"):
                self.assertNotIn(unsafe, text)
        payload = json.loads(self.sent[0])
        self.assertEqual(set(payload), {"model", "messages", "temperature", "max_tokens", "stream", "response_format"})
        self.assertEqual(payload["messages"], recipe_model.messages_for("How were bookings at CTR-A01 in March 2026?"))
        for private in (legacy.CASE_ID, GEMMA_12B.candidate_id, OWNER, GEMMA_12B.candidate_identity_sha256):
            self.assertNotIn(private.encode(), self.sent[0])

    async def test_mismatch_absent_model_decline_and_invalid_json_never_pass_or_retry(self):
        for options, expected in (({"returned_model": "gemma-4-31b"}, "unexpected_model"),
                                  ({"returned_model": None}, "unexpected_model"),
                                  ({"content": '{"outcome":"declined"}'}, "model_declined"),
                                  ({"content": RAW}, "invalid_json"),
                                  ({"content": '{"outcome":"request"}'}, "invalid_request")):
            before = len(self.sent)
            report = await self.run_probe(client=self.client(**options))
            self.assertFalse(report["compatibility_passed"])
            self.assertEqual(report["error_code"], expected)
            self.assertEqual(len(self.sent) - before, 1)
            self.assertEqual(runner.read_report(self.out / "report.json")["status"], "stopped")

    async def test_transport_timeout_envelope_failures_never_retry(self):
        for failure in (httpx.ConnectError(RAW), httpx.ReadTimeout(RAW)):
            def handler(request):
                raise failure
            report = await self.run_probe(client=self.client(handler=handler))
            self.assertEqual(report["client_http_attempts"], 1)
            self.assertFalse(report["compatibility_passed"])
        report = await self.run_probe(client=self.client(handler=lambda r: httpx.Response(200, json={"bad": RAW})))
        self.assertEqual(report["error_code"], "invalid_response")
        self.assertEqual(report["client_http_attempts"], 1)

    async def test_valid_clarification_does_not_claim_native_execution_compatibility(self):
        report = await self.run_probe(client=self.client(content=json.dumps(clarify())))
        self.assertEqual(report["compatibility"]["typed_action"], "passed")
        self.assertEqual(report["compatibility"]["native_execution"], "not_run")
        self.assertEqual(report["error_code"], "invalid_probe")
        self.assertFalse(report["compatibility_passed"])
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(runner.read_report(self.out / "report.json")["status"], "stopped")

    async def test_transport_classification_mismatch_prevents_send(self):
        report = await self.run_probe(client=self.client(base="https://candidate-probe.invalid/v1"))
        self.assertEqual(report["client_http_attempts"], 0)

    async def test_cancellation_preserves_possible_in_flight(self):
        def interrupt(request):
            raise asyncio.CancelledError
        report = await self.run_probe(client=self.client(handler=interrupt))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual((report["client_http_attempts"], report["runtime_invocations"], report["possible_in_flight_attempts"]), (1, 1, 1))
        self.assertEqual(runner.read_report(self.out / "report.json")["stop_reason"], "interrupted")

    async def test_publication_failure_preserves_incomplete_and_never_resends(self):
        with patch.object(legacy, "commit_terminal", side_effect=smoke.SmokeError("artifact_io")):
            with self.assertRaises(smoke.SmokeError):
                await self.run_probe()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(assets.read_asset(self.out / "report.json")["status"], "incomplete")
        self.assertTrue((self.out / "terminal-candidate.json").exists())
        self.assertTrue((self.out / "terminal.next.json").exists())

    async def test_output_exclusive_and_staging_does_not_expose_complete_early(self):
        original = legacy.stage_terminal
        def stage(artifacts, terminal, **kwargs):
            self.assertEqual(assets.read_asset(artifacts.directory / "report.json")["status"], "incomplete")
            return original(artifacts, terminal, **kwargs)
        with patch.object(legacy, "stage_terminal", side_effect=stage):
            await self.run_probe()
        with self.assertRaises(smoke.SmokeError):
            await runner.run_probe(self.database, self.out, packet_path=self.packet_path,
                                   authorization_path=self.authorization, accepted_commit=COMMIT,
                                   gateway_policies=runner.POLICIES, client=self.client())
        self.assertEqual(len(self.sent), 1)

    async def test_post_reservation_deadline_recheck_prevents_runtime(self):
        now = [0.0]
        original = smoke._Artifacts.persist
        def persist(artifacts, report):
            original(artifacts, report)
            if report["reservation"] == "in_progress":
                now[0] = 181.0
        with patch.object(smoke._Artifacts, "persist", new=persist):
            report = await self.run_probe(clock=lambda: now[0])
        self.assertEqual((report["client_http_attempts"], report["runtime_invocations"]), (0, 0))
        self.assertEqual(report["error_code"], "panel_budget")

    async def test_invocation_checkpoint_cannot_send_after_deadline_or_snapshot_drift(self):
        for drift in (False, True):
            now = [0.0]
            original = smoke._Artifacts.persist
            def persist(artifacts, report):
                original(artifacts, report)
                if report["status"] == "running" and report["runtime_invocations"] == 1:
                    if drift:
                        (artifacts.directory / "packet.json").write_text("{}")
                    else:
                        now[0] = 181.0
            with patch.object(smoke._Artifacts, "persist", new=persist):
                report = await self.run_probe(clock=lambda: now[0])
            self.assertEqual(report["client_http_attempts"], 0)
            self.assertEqual(report["runtime_invocations"], 1)
            self.assertEqual(report["error_code"], "manifest_drift" if drift else "panel_budget")

    async def test_reader_rejects_raw_and_counter_tampering(self):
        await self.run_probe()
        original = assets.read_asset(self.out / "report.json")
        for changed in ({"raw_completion": RAW}, {"runtime_invocations": 2},
                        {"observed_model": "gemma-4-31b"}, {"client_http_attempts": 0},
                        {"upstream_inference_attempts": 1}, {"requested_model": BASE},
                        {"http_status": 401}, {"http_class": "not_run"},
                        {"transport_security": None}, {"gateway_policy": smoke.policy_attestation()},
                        {"runtime_stages": {**original["runtime_stages"], "transport": "failed"}}):
            self.rewrite(self.out / "report.json", {**original, **changed})
            with self.assertRaises(legacy.ProbeError):
                runner.read_report(self.out / "report.json")

    async def test_candidate_and_legacy_readers_reject_cross_version(self):
        await self.run_probe()
        with self.assertRaises(legacy.ProbeError):
            legacy.read_report(self.out / "report.json")
        directory = self.output()
        manifest = {"version": legacy.VERSION, "runner": {"version": legacy.VERSION, "sha256": "0" * 64},
                    "plan_sha256": None, "accepted_commit": None}
        artifacts = smoke._Artifacts(directory, manifest)
        artifacts.persist(legacy._report(manifest, "mock"))
        self.assertEqual(legacy.read_report(directory / "report.json")["status"], "incomplete")
        with self.assertRaises(legacy.ProbeError):
            runner.read_report(directory / "report.json")

    def test_default_cli_and_live_flag_alone_never_authorize(self):
        for argv in ([], ["--live"], ["--prepare", "--env-file", "must-not-read"]):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(argv), 2)
        self.loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
