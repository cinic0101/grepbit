"""One-shot interface contract; synthetic configuration and poisoned real networking."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from test_recipe_model import proposal
from tools import fixture, p3_admission as admission, recipe_smoke, smoke
from tools import p3_probe as probe

COMMIT = "1" * 40
BASE = "https://probe-private.invalid/v1"
KEY = "dummy-probe-secret-Z93"
RAW = "PRIVATE_COMPLETION_REASONING_CANARY"
POLICIES = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
SYNTHETIC_ENV_LOADER = GatewayConfig.from_env


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            self.enterContext(patch(target, side_effect=AssertionError("Real network forbidden")))
        self.loader = self.enterContext(patch.object(
            GatewayConfig, "from_env", side_effect=AssertionError("Real config forbidden")))
        temporary = tempfile.TemporaryDirectory(dir=admission.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / "synthetic.sqlite"
        fixture.build(self.db)
        self.source = {"git_commit": COMMIT, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {"grepbit/recipe_model.py": "2" * 64},
                       "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity",
                                       side_effect=lambda: copy.deepcopy(self.source)))
        self.enterContext(patch.object(admission, "candidate_identity", return_value={
            "candidate_freeze_sha": admission.FROZEN_CANDIDATE,
            "files_sha256": {"grepbit/recipe_model.py": "2" * 64}}))
        self.prepared = self.root / "prepared"
        self.plan = admission.prepare_probe(self.db, self.prepared, accepted_commit=COMMIT)
        self.plan_path = self.prepared / "manifest.json"
        self.serial = 0
        self.sent = []

    def output(self):
        self.serial += 1
        return self.root / f"attempt-{self.serial}"

    def rewrite(self, data):
        self.plan_path.write_text(json.dumps(data), encoding="utf-8")

    def client(self, handler=None, content=None):
        def respond(request):
            self.sent.append(request)
            if handler:
                return handler(request)
            return httpx.Response(200, json={"model": MODEL, "choices": [{
                "index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                    "content": json.dumps(proposal("compare")) if content is None else content,
                    "reasoning_content": RAW}}]})
        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def run_probe(self, client=None, **kwargs):
        self.out = self.output()
        report = await probe.run_probe(
            self.db, self.out, plan_path=self.plan_path, accepted_commit=COMMIT,
            client=client or self.client(), gateway_policies=POLICIES, **kwargs)
        self.assertLessEqual(report["client_http_attempts"], 1)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertIsNone(report["upstream_inference_attempts"])
        for path in self.out.glob("*.json"):
            text = path.read_text()
            for secret in (BASE, KEY, RAW, "probe-private.invalid", "Authorization", "reasoning_content"):
                self.assertNotIn(secret, text)
        return report

    def test_native_prepared_plan_and_runner_identity(self):
        plan, question = probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)
        self.assertEqual(plan, self.plan)
        self.assertEqual(smoke._digest(question.encode()), self.plan["question_sha256"])
        self.assertEqual(plan["source_identity"]["files_sha256"]["tools/p3_probe.py"],
                         probe.runner_identity()["sha256"])

    def test_rejects_modified_plan_shape_and_pins(self):
        changes = {
            "version": "wrong", "state": "frozen", "question_sha256": "0" * 64,
            "question_reference": {"asset": "fresh.json", "case_id": "FA01", "field": "question"},
            "exposure": "frozen_fresh", "database_sha256": "0" * 64,
            "candidate": {}, "source_identity": {}, "settings_sha256": "0" * 64,
            "max_future_client_http_attempts": 2, "retries": 1, "repairs": 1, "fallbacks": 1,
            "execution": "admitted", "owner_authorization_required": False,
            "runtime_entry": "other", "live_model_attempts": 1,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                self.rewrite({**self.plan, field: value})
                with self.assertRaises(probe.ProbeError):
                    probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)
        self.rewrite({**self.plan, "exposure": "design_seen"})
        with self.assertRaises(probe.ProbeError):
            probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)

    def test_rejects_premerge_plan_and_wrong_explicit_commit(self):
        self.source["git_commit"] = "3" * 40
        for supplied in (COMMIT, "3" * 40, None):
            with self.subTest(supplied=supplied), self.assertRaises(probe.ProbeError):
                probe.validate_plan(self.plan_path, self.db, accepted_commit=supplied)

    def test_rejects_dirty_nondev_source_and_candidate_drift(self):
        for key, value in (("worktree_dirty", True), ("branch", "feat/unaccepted"),
                           ("files_sha256", {})):
            original = copy.deepcopy(self.source)
            self.source[key] = value
            with self.subTest(key=key), self.assertRaises(probe.ProbeError):
                probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)
            self.source = original
        with patch.object(admission, "candidate_identity", return_value={}), self.assertRaises(probe.ProbeError):
            probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)

    def test_rejects_database_drift(self):
        with self.db.open("ab") as stream:
            stream.write(b"drift")
        with self.assertRaises(probe.ProbeError):
            probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)

    async def test_pre_send_identity_failure_has_zero_calls_and_safe_evidence(self):
        self.rewrite({**self.plan, "version": BASE + KEY})
        report = await self.run_probe()
        self.assertEqual((report["status"], report["client_http_attempts"],
                          report["possible_in_flight_attempts"]), ("stopped", 0, 0))
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(self.sent, [])
        self.loader.assert_not_called()

    async def test_success_is_one_call_and_not_semantic_quality(self):
        with patch.object(probe, "interpret_recipe_and_execute", wraps=recipe_model.interpret_recipe_and_execute) as call:
            report = await self.run_probe()
        self.assertEqual(call.await_count, 1)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(report["compatibility_passed"])
        self.assertEqual(report["stop_reason"], "single_attempt_complete")
        self.assertEqual(report["reservation"], "settled")
        # Compare is intentionally not the Overview question's expected recipe.
        self.assertNotIn("outcome", report)
        self.assertNotIn("grading", report)
        self.assertNotIn("promotion", report)
        self.assertNotIn("proposal", report)
        self.assertEqual(report["compatibility"]["typed_action"], "passed")

    async def test_question_only_wire_and_unchanged_structured_output(self):
        report = await self.run_probe()
        body = json.loads(self.sent[0].content)
        _, question = probe.validate_plan(self.plan_path, self.db, accepted_commit=COMMIT)
        self.assertEqual(body["messages"], recipe_model.messages_for(question))
        self.assertEqual(smoke._digest(json.dumps(body["response_format"], sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False).encode()),
                         recipe_model.structured_output_identity()["response_format_sha256"])
        for forbidden in ("E01_overview.en", "exposed_regression", "question_sha256", "oracle_id",
                          "reviewer", "FA09", "candidate_freeze_sha"):
            self.assertNotIn(forbidden, self.sent[0].content.decode())
        self.assertEqual({key: body[key] for key in ("model", "temperature", "max_tokens", "stream")},
                         {"model": MODEL, "temperature": 0, "max_tokens": 2048, "stream": False})
        self.assertTrue(report["compatibility_passed"])

    async def test_failure_stages_never_retry(self):
        handlers = [
            (lambda _: (_ for _ in ()).throw(httpx.ConnectError(RAW)), "transport_error", "not_run", "not_run"),
            (lambda _: (_ for _ in ()).throw(httpx.ReadTimeout(RAW)), "timeout", "not_run", "not_run"),
            (lambda _: httpx.Response(401, text=RAW), "auth_failed", "not_run", "not_run"),
            (lambda _: httpx.Response(400, text=RAW), "http_configuration", "not_run", "not_run"),
            (lambda _: httpx.Response(200, json={"private": RAW}), "invalid_response", "not_run", "not_run"),
        ]
        for handler, code, json_stage, action_stage in handlers:
            self.sent = []
            with self.subTest(code=code):
                report = await self.run_probe(self.client(handler))
                self.assertEqual(report["error_code"], code)
                self.assertEqual(len(self.sent), 1)
                self.assertFalse(report["compatibility_passed"])
                self.assertEqual(report["compatibility"]["strict_json"], json_stage)
                self.assertEqual(report["compatibility"]["typed_action"], action_stage)
        for content, code, json_stage, action_stage in (("bad " + RAW, "invalid_json", "failed", "not_run"),
                (json.dumps({"outcome": RAW}), "invalid_request", "passed", "failed")):
            self.sent = []
            report = await self.run_probe(self.client(content=content))
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(report["error_code"], code)
            self.assertEqual(report["compatibility"]["envelope"], "passed")
            self.assertEqual(report["compatibility"]["strict_json"], json_stage)
            self.assertEqual(report["compatibility"]["typed_action"], action_stage)

    async def test_reservation_is_durable_before_send(self):
        def handler(request):
            saved = json.loads((self.out / "report.json").read_bytes())
            self.assertEqual(saved["reservation"], "in_progress")
            self.assertEqual(saved["possible_in_flight_attempts"], 1)
            self.assertEqual(saved["attempt_budget_used"], 1)
            self.assertEqual(saved["client_http_attempts"], 0)
            self.assertTrue(list(self.out.glob("checkpoint-*.json")))
            return httpx.Response(200, json={})
        await self.run_probe(self.client(handler))

    async def test_interruption_preserves_unknown_send_and_never_retries(self):
        for sent in (False, True):
            with self.subTest(sent=sent):
                self.sent = []
                if sent:
                    client = self.client(lambda _: (_ for _ in ()).throw(asyncio.CancelledError()))
                    report = await self.run_probe(client)
                else:
                    with patch.object(probe, "interpret_recipe_and_execute", side_effect=asyncio.CancelledError()):
                        report = await self.run_probe()
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["possible_in_flight_attempts"], 1)
                self.assertEqual(report["attempt_budget_used"], 1)
                self.assertEqual(report["client_http_attempts"], int(sent))
                self.assertFalse(report["compatibility_passed"])
                self.assertEqual(probe.read_report(self.out / "report.json")["possible_in_flight_attempts"], 1)

    async def test_guard_prevents_second_send_even_from_faulty_caller(self):
        async def faulty(question, database, client, **kwargs):
            messages = recipe_model.messages_for(question)
            await client.complete(messages)
            await client.complete(messages)
        with patch.object(probe, "interpret_recipe_and_execute", side_effect=faulty):
            report = await self.run_probe()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["error_code"], "attempt_limit")

    async def test_exclusive_outputs_and_archived_readback(self):
        report = await self.run_probe()
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaises(smoke.SmokeError):
            await probe.run_probe(self.db, self.out, plan_path=self.plan_path, accepted_commit=COMMIT,
                                  client=self.client(), gateway_policies=POLICIES)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
        self.source.update(branch="unrelated", git_commit="4" * 40)
        self.plan_path.unlink()
        with patch.object(probe, "validate_plan", side_effect=AssertionError("Archived reader must be local")):
            archived = probe.read_report(self.out / "report.json")
        self.assertEqual(archived["compatibility_passed"], report["compatibility_passed"])

    async def test_publication_failure_preserves_incomplete_evidence(self):
        with patch.object(probe, "stage_terminal", side_effect=smoke.SmokeError("artifact_io")):
            report = await self.run_probe()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["compatibility_passed"])
        self.assertEqual(probe.read_report(self.out / "report.json")["status"], "incomplete")

    async def test_success_is_never_checkpointed_before_terminal_commit(self):
        persisted = smoke._Artifacts.persist
        def checked(artifacts, report):
            self.assertNotEqual(report["status"], "complete")
            self.assertFalse(report["compatibility_passed"])
            return persisted(artifacts, report)
        with patch.object(smoke._Artifacts, "persist", checked):
            report = await self.run_probe()
        self.assertEqual(report["status"], "complete")

    async def test_commit_failure_retains_candidate_and_incomplete_report(self):
        with patch.object(probe, "commit_terminal", side_effect=smoke.SmokeError("artifact_io")):
            with self.assertRaises(smoke.SmokeError):
                await self.run_probe()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue((self.out / "terminal-candidate.json").exists())
        self.assertTrue((self.out / "terminal.next.json").exists())
        self.assertEqual(probe.read_report(self.out / "report.json")["status"], "incomplete")

    async def test_reservation_write_failure_prevents_runtime_and_send(self):
        persisted = smoke._Artifacts.persist
        fail = [True]
        def stopped(artifacts, report):
            if report["reservation"] == "in_progress" and fail[0]:
                fail[0] = False
                raise smoke.SmokeError("artifact_io")
            return persisted(artifacts, report)
        with patch.object(smoke._Artifacts, "persist", stopped):
            report = await self.run_probe()
        self.assertEqual(report["error_code"], "artifact_io")
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(self.sent, [])

    async def test_post_send_drift_is_terminal_not_success(self):
        call = recipe_model.interpret_recipe_and_execute
        async def drift(*args, **kwargs):
            result = await call(*args, **kwargs)
            self.source["files_sha256"] = {}
            return result
        with patch.object(probe, "interpret_recipe_and_execute", side_effect=drift):
            report = await self.run_probe()
        self.assertEqual(len(self.sent), 1)
        self.assertFalse(report["compatibility_passed"])
        self.assertEqual(report["error_code"], "manifest_drift")

    async def test_unknown_http_rejection_is_not_claimed_to_be_schema_rejection(self):
        report = await self.run_probe(self.client(lambda _: httpx.Response(400, text=RAW)))
        self.assertEqual(report["compatibility"]["response_format"], "unknown")
        self.assertEqual(report["compatibility"]["request_size"], "unknown")

    async def test_reader_rejects_contradictory_reservation_accounting(self):
        await self.run_probe()
        path = self.out / "report.json"
        original = json.loads(path.read_bytes())
        for field, value in (("live_model_attempts", 1), ("attempt_budget_used", 0),
                             ("reservation", "not_reserved"), ("runtime_invocations", 0)):
            with self.subTest(field=field):
                path.write_text(json.dumps({**original, field: value}))
                with self.assertRaises(probe.ProbeError):
                    probe.read_report(path)

    async def test_attestations_required_recorded_and_not_route_configuration(self):
        out = self.output()
        report = await probe.run_probe(self.db, out, plan_path=self.plan_path, accepted_commit=COMMIT,
                                      client=self.client(), gateway_policies=None)
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["error_code"], "gateway_policy_required")
        report = await self.run_probe()
        self.assertEqual({k: report["gateway_policy"][k] for k in POLICIES}, POLICIES)
        self.loader.assert_not_called()

    async def test_external_client_without_mock_transport_is_refused_offline(self):
        client = GatewayClient(GatewayConfig(BASE, KEY))
        report = await self.run_probe(client)
        self.assertEqual(report["error_code"], "invalid_configuration")
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(self.sent, [])

    async def test_outer_timeout_has_no_retry_and_preserves_reservation(self):
        with patch.object(probe, "interpret_recipe_and_execute", side_effect=TimeoutError):
            report = await self.run_probe()
        self.assertEqual(report["error_code"], "timeout")
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertEqual(report["attempt_budget_used"], 1)
        self.assertEqual(self.sent, [])

    async def test_postcommit_has_no_clock_check_or_checkpoint(self):
        persisted, commit = smoke._Artifacts.persist, probe.commit_terminal
        committed = [False]
        def checked_persist(artifacts, report):
            self.assertFalse(committed[0])
            return persisted(artifacts, report)
        def checked_commit(pending, target):
            commit(pending, target)
            committed[0] = True
        def clock():
            self.assertFalse(committed[0])
            return 0.0
        with patch.object(smoke._Artifacts, "persist", checked_persist), patch.object(probe, "commit_terminal", checked_commit):
            report = await self.run_probe(clock=clock)
        self.assertTrue(committed[0])
        self.assertTrue(report["compatibility_passed"])

    def test_explicit_synthetic_env_only(self):
        with self.assertRaises(probe.ProbeError):
            probe.live_client(None)
        env = self.root / "synthetic.env"
        env.write_text("GREPBIT_LITELLM_BASE_URL=" + BASE + "\nGREPBIT_LITELLM_API_KEY=" + KEY + "\n")
        self.loader.side_effect = lambda *, env_file: SYNTHETIC_ENV_LOADER(env_file=env_file, environ={})
        client = probe.live_client(env)
        self.loader.assert_called_once_with(env_file=env)
        self.assertEqual(client.http_attempts, 0)
        self.assertIsNone(client._transport)

    def test_cli_default_with_all_execution_arguments_still_cannot_send(self):
        args = ["--plan", str(self.plan_path), "--db", str(self.db), "--accepted-commit", COMMIT,
                "--env-file", str(self.root / "must-not-open.env"), "--output-dir", str(self.output()),
                "--gateway-retries", "disabled", "--gateway-fallback", "disabled", "--gateway-cache", "disabled"]
        out, err = io.StringIO(), io.StringIO()
        with patch.object(probe, "run_probe", side_effect=AssertionError("No explicit live flag")), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(probe.main(args), 2)
        self.loader.assert_not_called()

    def test_default_cli_is_not_live_and_errors_do_not_echo_values(self):
        for arguments in ([], ["--plan", str(self.plan_path)], ["--unknown", BASE + KEY]):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertNotEqual(probe.main(arguments), 0)
            self.assertNotIn(BASE, out.getvalue() + err.getvalue())
            self.assertNotIn(KEY, out.getvalue() + err.getvalue())
        self.loader.assert_not_called()

    async def test_reader_does_not_echo_injected_report_fields(self):
        await self.run_probe()
        path = self.out / "report.json"
        report = json.loads(path.read_bytes())
        report["error_code"] = BASE + KEY
        path.write_text(json.dumps(report))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertNotEqual(probe.main(["--report", str(path)]), 0)
        self.assertNotIn(BASE, out.getvalue() + err.getvalue())
        self.assertNotIn(KEY, out.getvalue() + err.getvalue())
