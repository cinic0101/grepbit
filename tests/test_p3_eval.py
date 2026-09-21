"""Offline evaluator admission, accounting and publication; not fresh product cases."""
import ast
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError
from tools import fixture, p3_assets, p3_eval as runner, p3_expectations, smoke


BASE = "https://p3-test-private.invalid/v1"
KEY = "p3-test-private-token"
CANARY = "P3_PROVIDER_BODY_NEVER_EXPORTED"


def envelope(action):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
             "message": {"role": "assistant", "content": json.dumps(action)}}]}


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class P3EvalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                     "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "grepbit.gateway.GatewayConfig.from_env"):
            guard = patch(name, side_effect=AssertionError("Network/configuration forbidden"))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)
        temporary = tempfile.TemporaryDirectory(dir=runner.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.panel = p3_assets.load_panel(runner.DEFAULT_PANEL)
        self.actions = runner.load_fake_responses(runner.DEFAULT_RESPONSES, self.panel)
        self.prepared = self.root / "prepared"
        runner.prepare(self.database, self.prepared)
        self.manifest_path = self.prepared / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        self.sent = []
        self.serial = 0

    def path(self, label):
        self.serial += 1
        return self.root / f"{label}-{self.serial}"

    def write_json(self, path, value):
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        return path

    def client(self, handler=None):
        def respond(request):
            self.sent.append(request)
            if handler is not None:
                return handler(request)
            return httpx.Response(200, json=envelope(self.actions[len(self.sent) - 1]))
        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def run_panel(self, handler=None, **kwargs):
        self.sent = []
        self.output = self.path("run")
        client = kwargs.pop("client", None)
        report = await runner.run_panel(
            self.database, self.output, manifest_path=kwargs.pop("manifest_path", self.manifest_path),
            client=client or self.client(handler), **kwargs)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertFalse(report["summary"]["promotion"]["passed"])
        self.assert_private(report)
        return report

    def assert_private(self, value):
        for fragment in (BASE, KEY, CANARY, "p3-test-private.invalid"):
            self.assertNotIn(fragment, str(value))

    def durable(self):
        return json.loads((self.output / "report.json").read_text())

    def assert_tail(self, report, index, reason):
        for row in report["results"][index:]:
            self.assertEqual((row["status"], row["outcome"], row["not_run_reason"]),
                             ("not_run", "not_run", reason))
            self.assertEqual(row["client_http_attempts"], 0)
            self.assertFalse(row["runtime_invoked"])
            self.assertEqual(set(row["layers"].values()), {"not_assessed"})

    def test_manifest_pins_sources_assets_order_hashes_and_fixed_limits(self):
        manifest = runner.build_manifest(self.database, responses_path=runner.DEFAULT_RESPONSES)
        self.assertEqual(manifest["manifest_version"], "p3-manifest-v1")
        self.assertEqual(manifest["panel_kind"], "development")
        self.assertEqual(manifest["preparation"], {"kind": "candidate", "accepted_commit": None})
        self.assertEqual(manifest["order"], [case.case_id for case in self.panel.cases])
        self.assertEqual(manifest["inputs"], self.panel.inputs())
        self.assertEqual(manifest["database_sha256"], hashlib.sha256(self.database.read_bytes()).hexdigest())
        for case, item in zip(self.panel.cases, manifest["inputs"]):
            self.assertNotIn("question", item)
            self.assertEqual(item["question_sha256"], hashlib.sha256(case.question.encode()).hexdigest())
        for name in ("p3_eval", "p3_assets", "p3_grading", "p3_scoring", "p3_expectations",
                     "evaluation_evidence", "recipe_smoke"):
            path = f"tools/{name}.py"
            self.assertEqual(manifest["identities"]["files_sha256"][path],
                             hashlib.sha256((runner.ROOT / path).read_bytes()).hexdigest())
        for path in ("pyproject.toml", "uv.lock"):
            self.assertEqual(manifest["identities"]["files_sha256"][path],
                             hashlib.sha256((runner.ROOT / path).read_bytes()).hexdigest())
        self.assertEqual(manifest["identities"]["context"], recipe_model.context_identity())
        self.assertEqual(manifest["identities"]["structured_output"], recipe_model.structured_output_identity())
        self.assertEqual(manifest["identities"]["evidence_expectations"], p3_expectations.identity())
        self.assertEqual(manifest["assets"]["responses"]["sha256"],
                         hashlib.sha256(runner.DEFAULT_RESPONSES.read_bytes()).hexdigest())
        for oracle, pin in zip(self.panel.oracles, manifest["oracles"]):
            self.assertEqual(pin["revision"], oracle.revision)
            self.assertEqual(pin["sha256"], p3_assets.digest(oracle.to_dict()))
        self.assertEqual(runner.settings(15)["panel_timeout_seconds"], 1020)
        self.assertEqual(runner.settings(44)["panel_timeout_seconds"], 2760)
        self.assertEqual(runner.settings(64)["max_client_http_attempts"], 64)
        for bad in (0, 65, True, 2.0):
            with self.assertRaises(p3_assets.P3Error):
                runner.settings(bad)
        self.assertEqual(runner.stop_policy()["version"], "p3-stops-v1")

    def test_candidate_and_explicit_clean_dev_preparation_are_distinct(self):
        identity = {**deepcopy(self.manifest["identities"]), "git_commit": "1" * 40,
                    "worktree_dirty": False, "branch": "dev"}
        with patch.object(runner, "_source_identity", return_value=identity):
            accepted = runner.build_manifest(self.database, accepted_commit="1" * 40)
            self.assertEqual(accepted["preparation"], {"kind": "accepted", "accepted_commit": "1" * 40})
            identity["worktree_dirty"] = True
            with self.assertRaisesRegex(runner.recipe_smoke.RecipeSmokeError, "accepted_commit_required"):
                runner.build_manifest(self.database, accepted_commit="1" * 40)
        self.assertEqual(self.manifest["preparation"]["kind"], "candidate")

    def test_prepare_inspection_cli_and_unknown_options_are_zero_network(self):
        prepared = runner.read_report(self.prepared / "report.json")
        self.assertEqual((prepared["status"], prepared["client_http_attempts"]), ("prepared", 0))
        self.assert_tail(prepared, 0, "offline_preparation")
        output = self.path("cli-prepared")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = runner.main(["--db", str(self.database), "--output-dir", str(output)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "prepared")
        self.assertEqual(json.loads((output / "manifest.json").read_text())["fake_responses"], runner.SCRIPT_VERSION)
        for args in (["--live"], ["--env-file", KEY], ["--gateway-retries", BASE],
                     ["report"], ["fake-run", "--db", str(self.database)]):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(runner.main(args), 2)
            self.assertEqual(json.loads(stderr.getvalue())["error_code"], "invalid_arguments")
            self.assert_private(stdout.getvalue() + stderr.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["report", "--report", str(output / "report.json")]), 0)

    def test_explicit_fake_run_cli_uses_script_and_report_inspection(self):
        prepared = self.path("cli-script-prepared")
        runner.prepare(self.database, prepared, responses_path=runner.DEFAULT_RESPONSES)
        output = self.path("cli-fake-run")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = runner.main(["fake-run", "--db", str(self.database), "--output-dir", str(output),
                                "--manifest", str(prepared / "manifest.json")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["client_http_attempts"], 15)
        report = runner.read_report(output / "report.json")
        self.assertEqual(report["status"], "complete")
        for path in output.glob("*.json"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(runner.main(["report", "--report", str(output / "report.json")]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "complete")

    async def test_development_script_e2e_all_fifteen_inputs_and_no_oracle_synthesis(self):
        directory = self.path("script-preparation")
        runner.prepare(self.database, directory, responses_path=runner.DEFAULT_RESPONSES)
        self.output = self.path("script-run")
        with patch.object(runner, "interpret_recipe_and_execute",
                          wraps=recipe_model.interpret_recipe_and_execute) as call:
            report = await runner.run_panel(
                self.database, self.output, manifest_path=directory / "manifest.json",
                responses_path=runner.DEFAULT_RESPONSES)
        self.assertEqual(call.await_count, 15)
        for invocation, case in zip(call.await_args_list, self.panel.cases):
            self.assertEqual(invocation.args[:2], (case.question, self.database))
            self.assertIsInstance(invocation.args[2], GatewayClient)
            self.assertEqual(set(invocation.kwargs), {"timeout_seconds", "clock"})
        self.assertEqual((report["status"], report["client_http_attempts"],
                          report["possible_in_flight_attempts"], report["attempt_budget_used"]),
                         ("complete", 15, 0, 15))
        self.assertEqual(report["summary"]["outcomes"],
                         {"complete_correct": 9, "correct_clarification": 4, "correct_decline": 2})
        self.assertEqual(report["summary"]["semantic_families"], 9)
        self.assertEqual(report["summary"]["answer_score"]["denominator"], 0)
        self.assertEqual(report["summary"]["by_cohort"]["anchor"]["family_count"], 3)
        self.assertEqual(report["summary"]["by_exposure"]["exposed_regression"]["family_count"], 9)
        self.assertFalse(report["summary"]["promotion"]["eligible"])
        self.assertEqual(runner.read_report(self.output / "report.json"), report)
        self.assertEqual((self.output / "report.json").stat().st_ino,
                         (self.output / "terminal-candidate.json").stat().st_ino)
        for checkpoint in self.output.glob("checkpoint-*.json"):
            self.assertNotEqual(json.loads(checkpoint.read_text())["status"], "complete")
        persisted = json.dumps(report, ensure_ascii=False)
        for case in self.panel.cases:
            self.assertNotIn(case.question, persisted)

    def test_script_schema_order_duplicate_ids_size_and_symlink_reject(self):
        original = json.loads(runner.DEFAULT_RESPONSES.read_text())
        for fault in ("order", "duplicate", "missing", "extra", "version", "action"):
            value = deepcopy(original)
            if fault == "order":
                value["responses"].reverse()
            elif fault == "duplicate":
                value["responses"][1]["case_id"] = value["responses"][0]["case_id"]
            elif fault == "missing":
                value["responses"].pop()
            elif fault == "extra":
                value["question"] = CANARY
            elif fault == "version":
                value["version"] = CANARY
            else:
                value["responses"][0]["action"] = []
            with self.subTest(fault=fault), self.assertRaisesRegex(p3_assets.P3Error, "invalid_fake_script"):
                runner.load_fake_responses(self.write_json(self.path("script"), value), self.panel)
        bad = self.path("invalid-json")
        bad.write_text('{"version":1,"version":2}')
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_fake_script"):
            runner.load_fake_responses(bad, self.panel)
        oversized = self.path("oversized")
        oversized.write_bytes(b" " * (p3_assets.MAX_ASSET_BYTES + 1))
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_fake_script"):
            runner.load_fake_responses(oversized, self.panel)
        link = self.path("symlink")
        link.symlink_to(runner.DEFAULT_RESPONSES)
        with self.assertRaises(smoke.SmokeError):
            runner.load_fake_responses(link, self.panel)

    async def test_script_order_is_checked_against_actual_question(self):
        client = runner.fake_client(self.panel, runner.DEFAULT_RESPONSES)
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_fake_script"):
            await recipe_model.interpret_recipe_and_execute(self.panel.cases[1].question, self.database, client)
        self.assertEqual(client.http_attempts, 1)

    async def test_no_live_real_default_reused_transport_or_script_client_mix(self):
        for origin in ("live", "invalid", None):
            with self.assertRaisesRegex(p3_assets.P3Error, "live_not_admitted"):
                await self.run_panel(origin=origin)
        for client in (GatewayClient(GatewayConfig(BASE, KEY)),
                       GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.AsyncBaseTransport())):
            with self.assertRaisesRegex(p3_assets.P3Error, "invalid_configuration"):
                await self.run_panel(client=client)
        client = self.client()
        client.http_attempts = 1
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_configuration"):
            await self.run_panel(client=client)
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_configuration"):
            await self.run_panel(responses_path=runner.DEFAULT_RESPONSES)
        self.assertFalse(self.sent)

    async def test_formal_panels_are_rejected_before_preparation_or_runtime(self):
        formal = replace(self.panel, kind="formal")
        with patch.object(p3_assets, "load_panel", return_value=formal):
            with self.assertRaisesRegex(p3_assets.P3Error, "formal_not_admitted"):
                runner.prepare(self.database, self.path("formal"))
            with self.assertRaisesRegex(p3_assets.P3Error, "formal_not_admitted"):
                await self.run_panel()
        self.assertFalse(self.sent)

    async def test_exact_wire_equality_and_metadata_canaries_never_enter_runtime(self):
        canary = "EVALUATOR_METADATA_ONLY_CANARY"
        cases = tuple(replace(case, semantic_signature=case.semantic_signature + canary,
                              provenance=replace(case.provenance, references=(canary,)))
                      for case in self.panel.cases)
        panel = replace(self.panel, cases=cases)
        prepared = self.path("canary-preparation")
        with patch.object(p3_assets, "load_panel", return_value=panel):
            runner.prepare(self.database, prepared)
            report = await self.run_panel(manifest_path=prepared / "manifest.json", clock=Clock())
        runtime_requests = list(self.sent)
        self.sent = []
        direct = await recipe_model.interpret_recipe_and_execute(
            panel.cases[0].question, self.database, self.client(), clock=Clock())
        self.assertEqual(runtime_requests[0].content, self.sent[0].content)
        # Native snapshots/fact IDs differ across independent executions, not their meaning.
        self.assertEqual({key: value for key, value in report["results"][0]["evidence"].items()
                          if key != "analysis_pack"},
                         {key: value for key, value in direct.evidence.items() if key != "analysis_pack"})
        self.assertEqual(report["results"][0]["actual_signature"],
                         runner.p3_grading.actual_signature(direct, "answer"))
        self.assertEqual(report["status"], "complete")
        for request, row in zip(runtime_requests, report["results"]):
            self.assertNotIn(canary, request.content.decode())
            self.assertNotIn(canary, str(row["evidence"]))
            for identity_part in p3_expectations.identity().values():
                self.assertNotIn(identity_part, request.content.decode())
                self.assertNotIn(identity_part, str(row["evidence"]))
            self.assertEqual(set(json.loads(request.content)), {
                "model", "messages", "temperature", "max_tokens", "stream", "response_format"})
        self.sent = []
        await recipe_model.interpret_recipe_and_execute(
            "March 2026 bookings; \u4e09\u6708\u9810\u8a02.", self.database, self.client())
        self.assertEqual(len(self.sent[0].content), 25250)

    def test_no_runtime_imports_evaluator_modules(self):
        for path in (runner.ROOT / "grepbit").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("tools"))
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(item.name.startswith("tools") for item in node.names))

    async def test_reservation_is_durable_before_each_send(self):
        def handler(request):
            report = self.durable()
            index = len(self.sent) - 1
            row = report["results"][index]
            self.assertEqual((row["status"], row["outcome"]), ("in_progress", None))
            self.assertTrue(row["attempt_may_be_in_flight"])
            self.assertEqual((report["client_http_attempts"], report["attempt_budget_used"],
                              report["possible_in_flight_attempts"]), (index, index + 1, 1))
            return httpx.Response(200, json=envelope(self.actions[index]))
        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "complete")
        self.assertTrue(all(row["attempt_evidence_status"] == "matched" for row in report["results"]))

    async def test_local_zero_send_runtime_errors_are_completed_not_not_run(self):
        client = self.client()
        with patch.object(client, "complete", new=AsyncMock(side_effect=ModelError("invalid_input"))):
            report = await self.run_panel(client=client)
        self.assertEqual(report["stop_reason"], "configuration_failure")
        row = report["results"][0]
        self.assertEqual((row["status"], row["outcome"], row["client_http_attempts"],
                          row["runtime_http_attempts"]), ("completed", "operational_failure", 0, 0))
        self.assertTrue(row["runtime_invoked"])
        self.assertEqual(report["attempt_budget_used"], 0)
        self.assert_tail(report, 1, "configuration_failure")
        self.assertEqual(runner.read_report(self.output / "report.json"), report)

    async def test_missing_invalid_mismatched_runtime_attempt_evidence_stops(self):
        original = recipe_model.interpret_recipe_and_execute
        for value, expected in (("missing", "missing"), (True, "invalid"), (-1, "invalid"),
                                (2, "invalid"), (0, "mismatch")):
            async def altered(*args, **kwargs):
                result = await original(*args, **kwargs)
                evidence = dict(result.evidence)
                evidence.pop("client_http_attempts")
                if value != "missing":
                    evidence["client_http_attempts"] = value
                return replace(result, evidence=evidence)
            with self.subTest(value=value), patch.object(runner, "interpret_recipe_and_execute", new=altered):
                report = await self.run_panel()
            self.assertEqual(report["stop_reason"], "internal_failure")
            self.assertEqual(report["client_http_attempts"], 1)
            self.assertEqual(report["results"][0]["attempt_evidence_status"], expected)
            self.assert_tail(report, 1, "internal_failure")

    async def test_missing_result_and_invalid_client_counter_are_distinct(self):
        original = recipe_model.interpret_recipe_and_execute
        for fault in ("result", "counter"):
            async def altered(question, database, client, **kwargs):
                result = await original(question, database, client, **kwargs)
                if fault == "counter":
                    client.http_attempts = None
                    return result
                return None
            with self.subTest(fault=fault), patch.object(runner, "interpret_recipe_and_execute", new=altered):
                report = await self.run_panel()
            self.assertEqual(report["stop_reason"], "internal_failure")
            self.assertEqual(report["results"][0]["status"], "completed")
            self.assertEqual(report["client_http_attempts"], None if fault == "counter" else 1)
            self.assert_tail(report, 1, "internal_failure")
            self.assertEqual(runner.read_report(self.output / "report.json"), report)

    async def test_extra_client_attempt_stops_without_repair_or_retry(self):
        original = recipe_model.interpret_recipe_and_execute
        async def extra(question, database, client, **kwargs):
            result = await original(question, database, client, **kwargs)
            await client.complete(recipe_model.messages_for(question))
            return result
        with patch.object(runner, "interpret_recipe_and_execute", new=extra):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], len(self.sent), report["client_http_attempts"]),
                         ("attempt_budget", 2, 2))
        self.assertEqual(report["results"][0]["client_http_attempts"], 2)
        self.assert_tail(report, 1, "attempt_budget")

    async def test_outer_timeout_and_invalid_clock_remain_explicit_failures(self):
        with patch.object(runner, "interpret_recipe_and_execute", new=AsyncMock(side_effect=TimeoutError)):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], report["client_http_attempts"]), ("consecutive_timeouts", 0))
        self.assertTrue(all(row["status"] == "completed" for row in report["results"][:2]))
        self.assert_tail(report, 2, "consecutive_timeouts")
        clock = Clock()
        def handler(request):
            clock.value = float("nan")
            return httpx.Response(200, json=envelope(self.actions[0]))
        report = await self.run_panel(handler, clock=clock)
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        self.assertIsNone(report["elapsed_seconds"])
        self.assertNotEqual(self.durable()["status"], "complete")

    async def test_interruption_keeps_actual_counter_and_inflight_reservation(self):
        def interrupted(request):
            if len(self.sent) == 2:
                raise KeyboardInterrupt(CANARY)
            return httpx.Response(200, json=envelope(self.actions[0]))
        report = await self.run_panel(interrupted)
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "interrupted"))
        self.assertEqual((report["client_http_attempts"], report["attempt_budget_used"],
                          report["possible_in_flight_attempts"]), (2, 2, 1))
        self.assertEqual((report["results"][1]["status"], report["results"][1]["outcome"]),
                         ("in_progress", None))
        self.assert_tail(report, 2, "interrupted")
        self.assertEqual(runner.read_report(self.output / "report.json"), report)
        with patch.object(runner, "interpret_recipe_and_execute",
                          new=AsyncMock(side_effect=asyncio.CancelledError)):
            report = await self.run_panel()
        self.assertEqual((report["client_http_attempts"], report["attempt_budget_used"],
                          report["possible_in_flight_attempts"]), (0, 1, 1))
        self.assert_tail(report, 1, "interrupted")

    async def test_independent_network_and_timeout_streaks_and_semantic_continuation(self):
        sequences = ((["network", "timeout", "network", "network"], "consecutive_network_failures"),
                     (["timeout", "network", "timeout", "timeout"], "consecutive_timeouts"),
                     (["network", "semantic", "network", "network"], "consecutive_network_failures"))
        for sequence, reason in sequences:
            def handler(request):
                code = sequence[len(self.sent) - 1]
                if code == "network":
                    return httpx.Response(503, text=CANARY)
                if code == "timeout":
                    raise httpx.ReadTimeout(CANARY)
                return httpx.Response(200, json=envelope({"outcome": "declined"}))
            with self.subTest(sequence=sequence):
                report = await self.run_panel(handler)
            self.assertEqual((report["stop_reason"], report["client_http_attempts"]), (reason, 4))
            self.assertEqual(report["timeout_streak"], 2 if reason == "consecutive_timeouts" else 0)
            self.assertEqual(report["network_failure_streak"], 2 if reason == "consecutive_network_failures" else 0)
            self.assert_tail(report, 4, reason)
        report = await self.run_panel(lambda request: httpx.Response(200, json=envelope({"outcome": "declined"})))
        self.assertEqual((report["status"], report["client_http_attempts"]), ("complete", 15))
        self.assertEqual(report["summary"]["outcomes"]["false_refusal"], 9)

    async def test_immediate_provider_envelope_configuration_and_budget_stops(self):
        for response, reason in (
            (httpx.Response(401, text=CANARY), "configuration_failure"),
            (httpx.Response(200, json={**envelope(self.actions[0]), "model": "unapproved"}), "configuration_failure"),
            (httpx.Response(200, json={"private": CANARY}), "envelope_incompatibility"),
            (httpx.Response(200, content=b"x" * 131073, headers={"content-type": "application/json"}), "budget_exhausted"),
        ):
            with self.subTest(reason=reason):
                report = await self.run_panel(lambda request: response)
            self.assertEqual((report["stop_reason"], len(self.sent)), (reason, 1))
            self.assert_tail(report, 1, reason)

    async def test_source_failure_after_reservation_before_runtime_leaves_no_attempt_tail(self):
        persist = smoke._Artifacts.persist
        source = runner._source_identity
        armed = [False]
        def saved(artifacts, report):
            persist(artifacts, report)
            if report["possible_in_flight_attempts"]:
                armed[0] = True
        def changed(*args):
            if armed[0]:
                raise p3_assets.P3Error("source_identity_failure")
            return source(*args)
        with patch.object(smoke._Artifacts, "persist", new=saved), patch.object(runner, "_source_identity", new=changed):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], len(self.sent), report["attempt_budget_used"]),
                         ("source_identity_failure", 0, 0))
        self.assert_tail(report, 0, "source_identity_failure")

    async def test_source_database_manifest_and_script_drift_stop(self):
        source = runner._source_identity
        for fault in ("source", "database", "manifest", "owned_manifest"):
            armed = [False]
            def identity(*args):
                value = source(*args)
                return {**value, "drift": True} if armed[0] and fault == "source" else value
            def handler(request):
                armed[0] = True
                if fault == "database":
                    with self.database.open("ab") as stream:
                        stream.write(b"drift")
                if fault in ("manifest", "owned_manifest"):
                    target = self.manifest_path if fault == "manifest" else self.output / "manifest.json"
                    target.write_text("{}")
                return httpx.Response(200, json=envelope(self.actions[0]))
            original_db, original_manifest = self.database.read_bytes(), self.manifest_path.read_bytes()
            with self.subTest(fault=fault), patch.object(runner, "_source_identity", new=identity):
                report = await self.run_panel(handler)
            self.assertIn(report["stop_reason"], ("manifest_drift", "database_drift"))
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(report["results"][0]["outcome"], "complete_correct")
            self.assertEqual(report["results"][0]["runner_error_code"], report["stop_reason"])
            self.database.write_bytes(original_db)
            self.manifest_path.write_bytes(original_manifest)
        script = self.write_json(self.path("script"), json.loads(runner.DEFAULT_RESPONSES.read_text()))
        prepared = self.path("script-prepared")
        runner.prepare(self.database, prepared, responses_path=script)
        script.write_text(script.read_text() + "\n")
        self.output = self.path("script-drift")
        report = await runner.run_panel(self.database, self.output, manifest_path=prepared / "manifest.json",
                                        responses_path=script)
        self.assertEqual(report["stop_reason"], "manifest_drift")
        self.assert_tail(report, 0, "manifest_drift")

    async def test_expectation_identity_drift_stops_before_runtime(self):
        with patch.object(p3_expectations, "DIMENSION_PROFILE_ID", "unreviewed_profile"):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], len(self.sent), report["attempt_budget_used"]),
                         ("manifest_drift", 0, 0))
        self.assert_tail(report, 0, "manifest_drift")

    async def test_script_loaded_after_manifest_and_rechecked_before_send(self):
        script = self.write_json(self.path("race-script"), json.loads(runner.DEFAULT_RESPONSES.read_text()))
        prepared = self.path("race-prepared")
        runner.prepare(self.database, prepared, responses_path=script)
        factory = runner.fake_client
        def changed(panel, path):
            client = factory(panel, path)
            path.write_text(path.read_text() + "\n")
            return client
        with patch.object(runner, "fake_client", new=changed):
            report = await runner.run_panel(
                self.database, self.path("race-run"), manifest_path=prepared / "manifest.json",
                responses_path=script)
        self.assertEqual((report["stop_reason"], report["client_http_attempts"]), ("manifest_drift", 0))
        self.assert_tail(report, 0, "manifest_drift")

    def test_fixture_identity_rejects_symlinks_sidecars_nonfixture_and_oversize(self):
        link = self.path("linked.sqlite")
        link.symlink_to(self.database)
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            runner.build_manifest(link)
        sidecar = Path(str(self.database) + "-wal")
        sidecar.touch()
        with self.assertRaises(smoke.SmokeError):
            runner.build_manifest(self.database)
        sidecar.unlink()
        invalid = self.path("untrusted.sqlite")
        invalid.write_bytes(b"not sqlite")
        with self.assertRaises(smoke.SmokeError):
            runner.build_manifest(invalid)
        oversized = self.path("oversized.sqlite")
        with oversized.open("xb") as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        with self.assertRaises(smoke.SmokeError):
            runner.build_manifest(oversized)

    async def test_wrong_intent_remains_primary_with_native_and_later_runner_error(self):
        original = recipe_model.interpret_recipe_and_execute
        persist = smoke._Artifacts.persist
        def failure(artifacts, report):
            if report["results"][0]["status"] == "completed" and report["stop_reason"] is None:
                raise smoke.SmokeError("artifact_io")
            return persist(artifacts, report)
        async def altered(*args, **kwargs):
            result = await original(*args, **kwargs)
            request = replace(result.proposal.request, center_code="WRONG-CENTER")
            return replace(result, proposal=replace(result.proposal, request=request),
                           analysis_pack=None, error=ModelError("kernel_failure"))
        with patch.object(runner, "interpret_recipe_and_execute", new=altered), \
                patch.object(smoke._Artifacts, "persist", new=failure):
            report = await self.run_panel()
        row = report["results"][0]
        self.assertEqual((row["outcome"], row["operational_error"], row["runner_error_code"]),
                         ("wrong_request", "kernel_failure", "artifact_io"))
        self.assert_tail(report, 1, "artifact_io")

    async def test_safe_export_checks_values_and_nested_field_names(self):
        original = recipe_model.interpret_recipe_and_execute
        for leaked in ({"private": KEY}, {KEY: {"nested": 1}}, {"nested": [{BASE: 1}]}):
            async def altered(*args, **kwargs):
                result = await original(*args, **kwargs)
                return replace(result, evidence={**result.evidence, "extra": leaked})
            with patch.object(runner, "interpret_recipe_and_execute", new=altered):
                report = await self.run_panel()
            self.assertEqual(report["stop_reason"], "leakage_risk")
            self.assertIsNone(report["results"][0]["evidence"])
            self.assertEqual(self.durable(), report)

    async def test_failed_completed_checkpoint_keeps_counts_without_new_send(self):
        persist = smoke._Artifacts.persist
        failed = [False]
        def saved(artifacts, report):
            if report["results"][0]["status"] == "completed" and not failed[0]:
                failed[0] = True
                raise OSError(errno.ENOSPC, CANARY)
            return persist(artifacts, report)
        with patch.object(smoke._Artifacts, "persist", new=saved):
            report = await self.run_panel()
        self.assertEqual((len(self.sent), report["client_http_attempts"], report["attempt_budget_used"]), (1, 1, 1))
        self.assertEqual(report["stop_reason"], "artifact_io")
        self.assertEqual(report["results"][0]["runner_error_code"], "artifact_io")
        self.assertEqual(report["results"][0]["evidence"]["client_http_attempts"], 1)
        self.assertEqual(self.durable(), report)
        self.assert_tail(report, 1, "artifact_io")

    async def test_exclusive_symlink_outputs_and_manifests_preserve_foreign_files(self):
        before = (self.prepared / "report.json").read_bytes()
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            runner.prepare(self.database, self.prepared)
        self.assertEqual((self.prepared / "report.json").read_bytes(), before)
        link = self.path("output-link")
        link.symlink_to(self.prepared)
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            runner.prepare(self.database, link)
        manifest = self.path("manifest-link")
        manifest.symlink_to(self.manifest_path)
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            await self.run_panel(manifest_path=manifest)
        self.assertFalse(self.sent)

    async def test_panel_deadline_before_send_and_after_response(self):
        for phase in ("reservation", "response"):
            clock = Clock()
            persist = smoke._Artifacts.persist
            def saved(artifacts, report):
                persist(artifacts, report)
                if phase == "reservation" and report["possible_in_flight_attempts"]:
                    clock.value = 1020
            def handler(request):
                clock.value = 1020
                return httpx.Response(200, json=envelope(self.actions[0]))
            with self.subTest(phase=phase), patch.object(smoke._Artifacts, "persist", new=saved):
                report = await self.run_panel(handler, clock=clock)
            self.assertEqual(report["stop_reason"], "panel_budget")
            self.assertEqual(report["client_http_attempts"], int(phase == "response"))
            self.assertEqual(report["possible_in_flight_attempts"], 0)
            self.assert_tail(report, int(phase == "response"), "panel_budget")

    async def test_terminal_enospc_interrupt_and_late_staging_never_publish_success(self):
        write = smoke._Artifacts._write
        for fault in ("enospc", "interrupt", "deadline"):
            clock = Clock()
            def staged(artifacts, name, value):
                if name == "terminal-candidate.json":
                    if fault == "enospc":
                        raise OSError(errno.ENOSPC, CANARY)
                    if fault == "interrupt":
                        raise KeyboardInterrupt(CANARY)
                    result = write(artifacts, name, value)
                    clock.value = 1020
                    return result
                return write(artifacts, name, value)
            with self.subTest(fault=fault), patch.object(smoke._Artifacts, "_write", new=staged):
                report = await self.run_panel(clock=clock)
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual(report["stop_reason"], {
                "enospc": "artifact_io", "interrupt": "interrupted", "deadline": "panel_budget"}[fault])
            self.assertEqual(report["client_http_attempts"], 15)
            self.assertEqual(self.durable(), report)

    async def test_persistent_disk_full_preserves_last_incomplete_checkpoint(self):
        write, open_file = smoke._Artifacts._write, os.open
        armed = [False]
        prior = []
        clock = Clock()
        def staged(artifacts, name, value):
            result = write(artifacts, name, value)
            if name == "terminal-candidate.json":
                prior.append((self.output / "report.json").read_bytes())
                clock.value = 1020
                armed[0] = True
            return result
        def disk_full(path, flags, *args, **kwargs):
            if armed[0] and flags & os.O_CREAT:
                raise OSError(errno.ENOSPC, CANARY)
            return open_file(path, flags, *args, **kwargs)
        with patch.object(smoke._Artifacts, "_write", new=staged), patch.object(os, "open", new=disk_full):
            with self.assertRaisesRegex(smoke.SmokeError, "artifact_io"):
                await self.run_panel(clock=clock)
        self.assertEqual((self.output / "report.json").read_bytes(), prior[0])
        self.assertEqual(self.durable()["status"], "incomplete")

    async def test_publication_commit_boundary_has_no_postcommit_checks_or_compensation(self):
        atomic, persist = os.replace, smoke._Artifacts.persist
        for fault in ("none", "failed", "before_interrupt", "late_return", "after_interrupt"):
            committed = [False]
            clock = Clock()
            prior = []
            def now():
                self.assertFalse(committed[0], "No clock check after publication")
                return clock()
            def saved(*args):
                self.assertFalse(committed[0], "No checkpoint after publication")
                return persist(*args)
            def publish(source, target):
                if Path(source).name != "terminal.next.json":
                    return atomic(source, target)
                prior.append(Path(target).read_bytes())
                if fault == "failed":
                    raise OSError(errno.ENOSPC, CANARY)
                if fault == "before_interrupt":
                    raise KeyboardInterrupt(CANARY)
                result = atomic(source, target)
                committed[0] = True
                clock.value = 1021
                if fault == "after_interrupt":
                    raise KeyboardInterrupt(CANARY)
                return result
            with self.subTest(fault=fault), patch.object(os, "replace", new=publish), \
                    patch.object(smoke._Artifacts, "persist", new=saved):
                if fault in ("before_interrupt", "after_interrupt"):
                    with self.assertRaises(KeyboardInterrupt):
                        await self.run_panel(clock=now)
                elif fault == "failed":
                    with self.assertRaisesRegex(smoke.SmokeError, "artifact_io"):
                        await self.run_panel(clock=now)
                else:
                    report = await self.run_panel(clock=now)
                    self.assertEqual(report["status"], "complete")
            if committed[0]:
                self.assertEqual(self.durable()["status"], "complete")
            else:
                self.assertEqual((self.output / "report.json").read_bytes(), prior[0])
                self.assertNotEqual(self.durable()["status"], "complete")

    async def test_terminal_owned_pending_link_conflict_does_not_replace_report(self):
        link = os.link
        foreign = self.write_json(self.path("foreign"), {"sentinel": "unchanged"})
        def linked(source, target):
            result = link(source, target)
            if Path(target).name == "terminal.next.json":
                Path(target).unlink()
                link(foreign, target)
            return result
        with patch.object(os, "link", new=linked):
            report = await self.run_panel()
        self.assertEqual(report["stop_reason"], "artifact_conflict")
        self.assertNotEqual(self.durable()["status"], "complete")
        self.assertEqual(json.loads(foreign.read_text()), {"sentinel": "unchanged"})

    async def test_terminal_stage_rechecks_source_database_and_prepared_manifest(self):
        write, identity = smoke._Artifacts._write, runner._source_identity
        for fault in ("source", "database", "manifest"):
            armed = [False]
            original_db, original_manifest = self.database.read_bytes(), self.manifest_path.read_bytes()
            def source(*args):
                current = identity(*args)
                return {**current, "changed": True} if armed[0] and fault == "source" else current
            def staged(artifacts, name, value):
                result = write(artifacts, name, value)
                if name == "terminal-candidate.json":
                    armed[0] = True
                    if fault == "database":
                        with self.database.open("ab") as stream:
                            stream.write(b"changed")
                    elif fault == "manifest":
                        self.manifest_path.write_text("{}")
                return result
            with self.subTest(fault=fault), patch.object(smoke._Artifacts, "_write", new=staged), \
                    patch.object(runner, "_source_identity", new=source):
                report = await self.run_panel()
            self.assertEqual(report["status"], "incomplete")
            self.assertIn(report["stop_reason"], ("manifest_drift", "database_drift"))
            self.assertNotEqual(self.durable()["status"], "complete")
            self.database.write_bytes(original_db)
            self.manifest_path.write_bytes(original_manifest)

    async def test_report_reader_rejects_shape_summary_counts_and_false_completion(self):
        report = await self.run_panel(lambda request: httpx.Response(503))
        for fault in ("version", "manifest", "summary", "counts", "budget", "complete", "row", "extra"):
            value = deepcopy(report)
            if fault == "version":
                value["report_version"] = "other"
            elif fault == "manifest":
                value["manifest_sha256"] = "0" * 64
            elif fault == "summary":
                value["summary"]["promotion"]["passed"] = True
            elif fault == "counts":
                value["client_http_attempts"] = 0
            elif fault == "budget":
                value["attempt_budget_used"] = 0
            elif fault == "complete":
                value["status"] = "complete"
                value["stop_reason"] = value["error_code"] = None
            elif fault == "row":
                value["results"][0]["question_sha256"] = "0" * 64
            else:
                value["question"] = CANARY
            path = self.write_json(self.path("bad-report"), value)
            with self.subTest(fault=fault), self.assertRaises(p3_assets.P3Error):
                runner.read_report(path, manifest_path=self.output / "manifest.json")
        invalid = self.path("bad-json")
        invalid.write_text('{"private":"' + CANARY)
        with self.assertRaises(p3_assets.P3Error):
            runner.read_report(invalid, manifest_path=self.output / "manifest.json")


if __name__ == "__main__":
    unittest.main()
