"""Formal execution contract rulers. Only synthetic metadata and exposed inputs."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError
from tools import fixture, p3_admission, p3_assets, p3_eval, p3_formal_run as formal, p3_formal_policy
from tools import recipe_smoke, smoke
from test_p3_admission import abstract_reviews, metadata_provenance
from test_p3_formal_policy import revised_scaffolding

SHA = "1" * 40
OWNER = "https://github.com/cinic0101/grepbit/issues/49#issuecomment-123456789"
POLICIES = {"retries": "enabled", "fallback": "disabled", "cache": "disabled"}
BASE = "http://synthetic-formal-test.invalid/v1"
KEY = "synthetic-formal-secret-key"


def envelope(content):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


class BoundaryRulers(unittest.TestCase):
    def test_historical_formal_settings_cannot_be_relabelled_live(self):
        self.assertEqual(p3_eval.settings(28)["execution"], "explicit_mock_transport_only")
        self.assertEqual(p3_eval.settings(28)["panel_timeout_seconds"], 1800)
        self.assertEqual(p3_eval.stop_policy()["version"], "p3-stops-v1")
        self.assertIn("Not admitted", p3_eval.stop_policy()["live"])

    def test_current_development_boundary_rejects_live_before_any_materials(self):
        with patch.object(p3_assets, "load_panel", side_effect=AssertionError("must not load")) as load:
            with self.assertRaisesRegex(p3_assets.P3Error, "live_not_admitted"):
                asyncio.run(p3_eval.run_panel(Path("unused"), Path("unused"),
                                             manifest_path=None, origin="live"))
            load.assert_not_called()

    def test_neutral_engine_contract_is_explicitly_private(self):
        # Static contract assertion: no formal call is attempted to make a red
        # behavior test. Existing live rejection above remains mandatory.
        self.assertTrue(callable(getattr(p3_eval, "_execute_panel", None)),
                        "One private engine is required; do not duplicate the evaluator loop")


class FormalTests(unittest.IsolatedAsyncioTestCase):
    """Native publication with synthetic allocation and a mocked intake authority.

    Questions/oracles are unchanged exposed development objects, never fresh
    authoring. The mocked intake deliberately does not claim semantic admission
    of repeated exposed oracles as independent families. All real transports and
    real env loading are poisoned; run_live tests replace only the config loader
    and client factory with synthetic values/MockTransport after authorization.
    """
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            mocked = self.enterContext(patch(target, side_effect=AssertionError("Real network/env forbidden")))
            self.addCleanup(mocked.assert_not_called)
        tmp = tempfile.TemporaryDirectory(prefix="p35-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.db_hash = smoke._fixture_identity(self.database)
        self.fixture_identity = self.enterContext(patch.object(smoke, "_fixture_identity", return_value=self.db_hash))
        self.enterContext(patch.object(smoke, "_stable_database", return_value=self.db_hash))
        self.source = {"git_commit": SHA, "branch": "dev", "worktree_dirty": False, "files_sha256": {},
                       "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(self.source)))
        candidate = p3_admission.candidate_identity()
        self.enterContext(patch.object(p3_admission, "candidate_identity", return_value=candidate))
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        seeds = {branch: next(c for c in exposed.cases if c.expected_branch == branch) for branch in p3_assets.BRANCHES}
        self.e01 = next(c for c in exposed.cases if c.case_id == "E01_overview.en")
        seeds["answer"] = self.e01
        self.cases = tuple(replace(seeds[row["expected_branch"]], **{
            key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
                                     "semantic_signature", "must_pass", "observational")},
            provenance=p3_assets.Provenance.from_mapping(metadata_provenance(row["exposure"]), row["exposure"]))
            for row in revised_scaffolding())
        self.oracles = tuple(exposed.oracle_for(seed) for seed in seeds.values())
        for filename in ("development-cases-v1.json", "development-oracles-v1.json"):
            (self.root / filename).write_bytes((p3_eval.DEFAULT_PANEL.parent / filename).read_bytes())
        self.panel_path = self.root / "synthetic-formal-panel.json"
        self.write(self.panel_path, {"version": "p3-panel-v1", "panel_id": "SyntheticOnlyNotAdmitted", "kind": "formal",
                                   "cases": "development-cases-v1.json", "oracles": "development-oracles-v1.json",
                                   "order": [c.case_id for c in self.cases]})
        self.intake_path = self.root / "synthetic-intake.json"
        self.write(self.intake_path, {"synthetic_metadata_only": True})
        self.review = {"state": "novelty_reviewed", "owner_review_reference": "synthetic-admission-only",
                       "families": abstract_reviews(self.panel(self.panel_path).inputs()),
                       **{name: p3_eval._pin(self.root / filename) for name, filename in (
                           ("cases", "development-cases-v1.json"), ("oracles", "development-oracles-v1.json"))}}
        self.enterContext(patch.object(p3_admission, "_intake", side_effect=lambda path: (
            deepcopy(self.review), self.cases, self.oracles, {"review_assertions_complete": True})))
        self.frozen = self.root / "synthetic-freeze"
        p3_admission.freeze_panel(self.database, self.intake_path, self.panel_path, self.frozen,
                                 accepted_commit=SHA, allocation_policy=p3_formal_policy.V2)
        self.prepared = self.root / "synthetic-offline-prepared"
        p3_eval.prepare(self.database, self.prepared, panel_path=self.frozen / self.panel_path.name,
                        accepted_commit=SHA, formal_freeze=self.frozen / "report.json")
        self.packet_dir = self.root / "packet"
        formal.prepare(self.database, self.packet_dir, freeze_path=self.frozen / "report.json",
                       preparation_path=self.prepared / "manifest.json", accepted_commit=SHA,
                       gateway_policies=POLICIES, transport_security="unencrypted_http")
        self.packet_path = self.packet_dir / "manifest.json"
        self.packet = self.read(self.packet_path)
        self.auth_path = self.root / "authorization.json"
        formal.bind_authorization(self.packet_path, OWNER, self.auth_path)
        self.sent, self.serial = [], 0

    def panel(self, path):
        return p3_assets.Panel("SyntheticOnlyNotAdmitted", "formal", self.cases, self.oracles,
                               path, path.parent / "development-cases-v1.json", path.parent / "development-oracles-v1.json")

    def write(self, path, value):
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def read(self, path):
        return json.loads(path.read_text())

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    def client(self, handler=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def run_formal(self, handler=None, **options):
        self.sent = []
        self.current_output = options.pop("output_dir", self.output())
        client = self.client(handler)
        with patch.object(formal.GatewayConfig, "from_env", return_value=client.config) as config, \
                patch.object(formal, "GatewayClient", return_value=client) as factory:
            result = await formal.run_live(self.database, self.current_output, packet_path=self.packet_path,
                                          authorization_path=options.pop("authorization_path", self.auth_path),
                                          accepted_commit=options.pop("accepted_commit", SHA),
                                          env_file=options.pop("env_file", self.root / "explicit-synthetic.env"),
                                          gateway_policies=options.pop("gateway_policies", POLICIES), **options)
        self.config_calls, self.factory_calls = config.call_count, factory.call_count
        return result

    async def reject_before_config(self, **options):
        with patch.object(formal.GatewayConfig, "from_env", side_effect=AssertionError("Must not load")) as load, \
                patch.object(formal, "GatewayClient", side_effect=AssertionError("Must not construct")) as factory:
            with self.assertRaises((p3_assets.P3Error, smoke.SmokeError, recipe_smoke.RecipeSmokeError)):
                await formal.run_live(self.database, self.output(), packet_path=self.packet_path,
                    authorization_path=options.pop("authorization_path", self.auth_path),
                    accepted_commit=options.pop("accepted_commit", SHA), env_file=self.root / "unused.env",
                    gateway_policies=options.pop("gateway_policies", POLICIES))
            load.assert_not_called()
            factory.assert_not_called()

    def test_versions_packet_pins_and_no_owner_circularity(self):
        self.assertEqual(self.packet["version"], "p3-formal-live-packet-v1")
        self.assertNotIn("owner_authorization_reference", self.packet)
        self.assertNotIn(OWNER, json.dumps(self.packet))
        auth = self.read(self.auth_path)
        self.assertEqual(set(auth), {"version", "packet_sha256", "owner_authorization_reference"})
        self.assertEqual(auth["version"], "p3-formal-live-authorization-v1")
        self.assertEqual(auth["packet_sha256"], hashlib.sha256(self.packet_path.read_bytes()).hexdigest())
        self.assertEqual(self.packet["stop_policy"]["version"], "p3-stops-v2")
        self.assertEqual(self.packet["settings"]["max_client_http_attempts"], 28)
        self.assertEqual(self.packet["settings"]["panel_timeout_seconds"], 1800)
        self.assertEqual(self.packet["allocation_policy"], p3_formal_policy.identity(p3_formal_policy.V2))
        self.assertIn("tools/p3_formal_run.py", self.packet["identities"]["files_sha256"])
        self.assertEqual(self.packet["command_template"], formal.command_template(SHA, POLICIES))
        self.assertNotIn(OWNER, " ".join(self.packet["command_template"]))

    def test_authorization_binding_is_exclusive_and_does_not_modify_packet(self):
        before = self.packet_path.read_bytes()
        with self.assertRaisesRegex(p3_assets.P3Error, "artifact_conflict"):
            formal.bind_authorization(self.packet_path, OWNER, self.auth_path)
        self.assertEqual(self.packet_path.read_bytes(), before)

    def test_packet_preparation_is_exclusive_and_offline(self):
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            formal.prepare(self.database, self.packet_dir, freeze_path=self.frozen / "report.json",
                preparation_path=self.prepared / "manifest.json", accepted_commit=SHA,
                gateway_policies=POLICIES, transport_security="unencrypted_http")
        self.assertEqual(self.read(self.packet_dir / "report.json")["state"], "prepared_not_authorized")

    async def test_missing_authorization_before_config(self):
        await self.reject_before_config(authorization_path=self.root / "missing.json")

    async def test_authorization_rejects_reference_variants_before_config(self):
        original = self.read(self.auth_path)
        for reference in (None, "", " ", OWNER.replace("/49#", "/47#"), OWNER + " ", "https://example.invalid"):
            with self.subTest(reference=reference):
                self.write(self.auth_path, {**original, "owner_authorization_reference": reference})
                await self.reject_before_config()

    async def test_authorization_wrong_version_hash_unknown_fields(self):
        original = self.read(self.auth_path)
        for change in ({"version": "other"}, {"packet_sha256": "0"*64}, {"extra": True}):
            self.write(self.auth_path, {**original, **change})
            await self.reject_before_config()

    async def test_stale_commit_and_dirty_non_dev_before_config(self):
        await self.reject_before_config(accepted_commit="2"*40)
        for changes in ({"git_commit": "2"*40}, {"worktree_dirty": True}, {"branch": "feature"}):
            original = deepcopy(self.source)
            self.source.update(changes)
            await self.reject_before_config()
            self.source.clear()
            self.source.update(original)

    async def test_source_and_database_drift_before_config(self):
        self.source["files_sha256"]["synthetic-drift"] = "a"*64
        await self.reject_before_config()
        self.source["files_sha256"].clear()
        self.fixture_identity.return_value = "f"*64
        await self.reject_before_config()

    async def test_snapshot_and_preparation_drift_before_config(self):
        for filename in ("development-cases-v1.json", "development-oracles-v1.json", self.panel_path.name, "report.json"):
            path = self.frozen / filename
            before = path.read_bytes()
            path.write_bytes(before + b" ")
            await self.reject_before_config()
            path.write_bytes(before)
        prep = self.prepared / "manifest.json"
        data = self.read(prep)
        data["settings"]["max_tokens"] = 1
        self.write(prep, data)
        await self.reject_before_config()

    async def test_packet_order_policy_and_unknown_fields_rejected(self):
        for mutate in (lambda p: p["order"].reverse(),
                       lambda p: p.update(allocation_policy=p3_formal_policy.identity(p3_formal_policy.V1)),
                       lambda p: p["command_template"].append("--unreviewed-setting"),
                       lambda p: p.update(owner_authorization_reference=OWNER)):
            packet = deepcopy(self.packet)
            mutate(packet)
            self.write(self.packet_path, packet)
            auth = self.read(self.auth_path)
            auth["packet_sha256"] = hashlib.sha256(self.packet_path.read_bytes()).hexdigest()
            self.write(self.auth_path, auth)
            await self.reject_before_config()

    async def test_route_attestations_must_match_before_config(self):
        await self.reject_before_config(gateway_policies={**POLICIES, "cache": "enabled"})

    async def test_transport_security_mismatch_before_client_and_send(self):
        config = GatewayConfig("https://synthetic-formal-test.invalid/v1", KEY)
        with patch.object(formal.GatewayConfig, "from_env", return_value=config), \
                patch.object(formal, "GatewayClient", side_effect=AssertionError("Must not construct")) as factory:
            report = await formal.run_live(self.database, self.output(), packet_path=self.packet_path,
                authorization_path=self.auth_path, accepted_commit=SHA, env_file=self.root / "explicit.env",
                gateway_policies=POLICIES)
        factory.assert_not_called()
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["stop_reason"], "invalid_configuration")

    async def test_explicit_configuration_failure_is_terminal_before_client(self):
        output = self.output()
        explicit = self.root / "only-this-synthetic.env"
        with patch.object(formal.GatewayConfig, "from_env", side_effect=ModelError("invalid_configuration")) as load, \
                patch.object(formal, "GatewayClient", side_effect=AssertionError("Must not construct")) as factory:
            report = await formal.run_live(self.database, output, packet_path=self.packet_path,
                authorization_path=self.auth_path, accepted_commit=SHA, env_file=explicit, gateway_policies=POLICIES)
        load.assert_called_once_with(env_file=explicit)
        factory.assert_not_called()
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        self.assertEqual(formal.read_report(output / "report.json"), report)

    async def test_valid_authorization_28_sequential_semantic_failures_continue(self):
        report = await self.run_formal()
        self.assertEqual(report["status"], "complete")
        self.assertEqual((self.config_calls, self.factory_calls), (1, 1))
        self.assertEqual(len(self.sent), 28)
        self.assertEqual([r["case_id"] for r in report["results"]], self.packet["order"])
        self.assertEqual(report["client_http_attempts"], 28)
        self.assertEqual(report["live_model_attempts"], 28)  # synthetic mocked live path, not real model calls
        self.assertEqual(report["runtime_invocations"], 28)
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertFalse(report["summary"]["promotion"]["passed"])
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)
        self.assertTrue(any(r["outcome"] == "false_refusal" for r in report["results"]))

    async def test_retained_slice_success_uses_unchanged_grader_and_summary(self):
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        scripted = p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES, exposed)
        by_oracle = {case.oracle_id: action for case, action in zip(exposed.cases, scripted)}
        report = await self.run_formal(lambda request: httpx.Response(200, json=envelope(json.dumps(
            by_oracle[self.cases[len(self.sent)-1].oracle_id]))))
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["summary"]["promotion"]["passed"])
        self.assertEqual(report["summary"], p3_formal_policy.summarize(
            report["results"], report["results"], panel_kind="formal", run_status="complete",
            allocation_policy=self.packet["allocation_policy"]))
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_reservation_and_invocation_are_durable_before_every_send(self):
        def respond(request):
            durable = self.read(self.current_output / "report.json")
            row = durable["results"][len(self.sent)-1]
            self.assertEqual(row["phase"], "invoked")
            self.assertTrue(row["runtime_invoked"])
            self.assertTrue(row["attempt_may_be_in_flight"])
            self.assertEqual(durable["possible_in_flight_attempts"], 1)
            return httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        report = await self.run_formal(respond)
        self.assertEqual(report["status"], "complete")
        phases = {self.read(path)["results"][0]["phase"] for path in self.current_output.glob("checkpoint-*.json")}
        self.assertTrue({"reserved", "invoked", "returned", "graded"} <= phases)

    async def test_runtime_is_sequential_and_each_timeout_bounded(self):
        invoke = p3_eval.interpret_recipe_and_execute
        active, calls = 0, []
        async def observe(question, database, client, **options):
            nonlocal active
            self.assertEqual(active, 0)
            active += 1
            calls.append(question)
            self.assertGreater(options["timeout_seconds"], 0)
            self.assertLessEqual(options["timeout_seconds"], 60)
            try:
                return await invoke(question, database, client, **options)
            finally:
                active -= 1
        with patch.object(p3_eval, "interpret_recipe_and_execute", side_effect=observe):
            report = await self.run_formal()
        self.assertEqual(calls, [case.question for case in self.cases])
        self.assertEqual((len(calls), len(self.sent), report["runtime_invocations"]), (28, 28, 28))

    async def test_panel_deadline_before_send_and_after_return(self):
        ticks = iter([0, 1800, 1800])
        report = await self.run_formal(clock=lambda: next(ticks, 1800))
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)
        now = [0]
        def respond(request):
            now[0] = 1801
            return httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        report = await self.run_formal(respond, clock=lambda: now[0])
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["results"][0]["phase"], "graded")

    async def test_drift_after_reservation_stops_before_send(self):
        persist = smoke._Artifacts.persist
        def drift(artifacts, report):
            result = persist(artifacts, report)
            if report.get("results") and report["results"][0].get("phase") == "reserved":
                self.fixture_identity.return_value = "f"*64
            return result
        with patch.object(smoke._Artifacts, "persist", autospec=True, side_effect=drift):
            report = await self.run_formal()
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["possible_in_flight_attempts"], 0)
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_invocation_checkpoint_cannot_send_after_panel_deadline(self):
        persist = smoke._Artifacts.persist
        now = [0]
        def expire(artifacts, report):
            result = persist(artifacts, report)
            if report.get("results") and report["results"][0].get("phase") == "invoked":
                now[0] = 1801
            return result
        with patch.object(smoke._Artifacts, "persist", autospec=True, side_effect=expire):
            report = await self.run_formal(clock=lambda: now[0])
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["possible_in_flight_attempts"], 0)
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_output_snapshot_drift_after_send_is_terminal(self):
        def respond(request):
            path = self.current_output / "packet.json"
            path.write_bytes(path.read_bytes() + b" ")
            return httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        report = await self.run_formal(respond)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "manifest_drift")
        with self.assertRaises(p3_assets.P3Error):
            formal.read_report(self.current_output / "report.json")

    async def test_network_and_timeout_streaks_are_independent(self):
        errors = [httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.ReadTimeout]
        def respond(request):
            raise errors[len(self.sent)-1]("PRIVATE_PROVIDER_CANARY")
        report = await self.run_formal(respond)
        self.assertEqual(len(self.sent), 5)
        self.assertEqual(report["stop_reason"], "consecutive_timeouts")
        self.assertEqual(report["network_failure_streak"], 0)
        self.assertNotIn("PRIVATE_PROVIDER_CANARY", json.dumps(report))
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_transport_failure_stops_after_two_no_retry(self):
        def respond(request):
            raise httpx.ConnectError("PRIVATE_PROVIDER_CANARY")
        report = await self.run_formal(respond)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(report["stop_reason"], "consecutive_network_failures")

    async def test_provider_envelope_configuration_resource_failures_stop_immediately(self):
        for status, body in ((401, {}), (200, {}), (413, {}), (302, {})):
            with self.subTest(status=status, body=body):
                report = await self.run_formal(lambda request: httpx.Response(status, json=body))
                self.assertEqual(len(self.sent), 1)
                self.assertEqual(report["status"], "incomplete")

    async def test_invalid_json_and_action_do_not_retry_or_quality_stop(self):
        for content in ("PRIVATE_BAD_JSON_CANARY", '{"outcome":"request","not_a_request":true}'):
            report = await self.run_formal(lambda request: httpx.Response(200, json=envelope(content)))
            self.assertEqual(len(self.sent), 28)
            self.assertEqual(report["status"], "complete")
            self.assertTrue(all(row["outcome"] == "invalid_output" for row in report["results"]))
            self.assertNotIn("PRIVATE_BAD_JSON_CANARY", json.dumps(report))

    async def test_cancellation_preserves_observed_and_possible_send(self):
        def respond(request):
            raise asyncio.CancelledError
        report = await self.run_formal(respond)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertEqual(report["results"][0]["phase"], "invoked")
        self.assertEqual(report["stop_reason"], "interrupted")
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_one_use_guard_blocks_second_send_before_transport(self):
        client = self.client()
        guard = formal._PerInputClient(client)
        messages = recipe_model.messages_for(self.e01.question)
        await guard.complete(messages)
        with self.assertRaisesRegex(p3_assets.P3Error, "attempt_budget"):
            await guard.complete(messages)
        self.assertEqual(len(self.sent), 1)
        client.http_attempts = 28
        with self.assertRaisesRegex(p3_assets.P3Error, "attempt_budget"):
            await formal._PerInputClient(client).complete(messages)
        self.assertEqual(len(self.sent), 1)

    async def test_wire_isolation_no_previous_output_and_e01_parity(self):
        report = await self.run_formal()
        sent = list(self.sent)
        for request, case in zip(sent, self.cases):
            wire = json.loads(request.content)
            self.assertEqual(wire["messages"], recipe_model.messages_for(case.question))
            self.assertEqual(set(wire), {"model","messages","temperature","max_tokens","stream","response_format"})
            self.assertNotIn(case.case_id, request.content.decode())
            self.assertNotIn(case.family_id, request.content.decode())
            self.assertNotIn(OWNER, request.content.decode())
            self.assertNotIn("synthetic-allocation-only", request.content.decode())
        from tools.p3_probe import _SingleAttempt
        self.sent = []
        result = await recipe_model.interpret_recipe_and_execute(
            self.e01.question, self.database, _SingleAttempt(self.client()))
        self.assertEqual(sent[0].content, self.sent[0].content)
        self.assertEqual(report["runtime_invocations"], 28)
        grade = p3_eval.p3_grading.grade(result, self.oracles[0])
        for key, value in grade.items():
            self.assertEqual(report["results"][0][key], value)

    async def test_live_projection_excludes_full_native_objects_and_provider_canaries(self):
        action = next(action for action in p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES,
            p3_assets.load_panel(p3_eval.DEFAULT_PANEL)) if action.get("recipe_id") == "overview")
        def respond(request):
            payload = envelope(json.dumps(action))
            payload["choices"][0]["message"]["reasoning_content"] = "RAW_REASONING_CANARY"
            payload["provider_specific_fields"] = {"raw": "RAW_PROVIDER_CANARY"}
            return httpx.Response(200, json=payload)
        report = await self.run_formal(respond)
        for row in report["results"]:
            self.assertTrue(set(row["evidence"]) <= formal._EVIDENCE_FIELDS)
            self.assertNotIn("analysis_pack", row["evidence"])
            self.assertNotIn("proposal", row["evidence"])
        for path in self.current_output.glob("*.json"):
            text = path.read_text()
            for canary in ("RAW_REASONING_CANARY","RAW_PROVIDER_CANARY",BASE,KEY,"Authorization"):
                self.assertNotIn(canary, text)
        self.assertEqual(report["status"], "complete")

    def test_projector_drops_unapproved_keys_and_rejects_invalid_allowed_values(self):
        value = {"client_http_attempts":1, "proposal":{"secret":KEY}, "raw_completion":"CANARY",
                 "presentation":"CANARY", "analysis_pack":{"values":[999]}, "headers":{"Authorization":KEY}}
        self.assertEqual(formal._evidence(value), {"client_http_attempts":1})
        for change in ({"returned_model":"PRIVATE_CANARY"}, {"error_code":"PRIVATE_CANARY"},
                       {"usage":{"unknown":1}}, {"elapsed_seconds":float("nan")}, {"client_http_attempts":True}):
            with self.assertRaises(p3_assets.P3Error):
                formal._evidence(change)

    async def test_exclusive_run_output_cannot_be_reused(self):
        await self.run_formal()
        before = (self.current_output / "report.json").read_bytes()
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            await self.run_formal(output_dir=self.current_output)
        self.assertEqual((self.current_output / "report.json").read_bytes(), before)
        self.assertFalse(self.sent)

    async def test_terminal_failure_preserves_incomplete_evidence(self):
        with patch.object(p3_eval, "stage_terminal", side_effect=smoke.SmokeError("artifact_io")):
            report = await self.run_formal()
        self.assertEqual(len(self.sent), 28)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "artifact_io")
        self.assertEqual(formal.read_report(self.current_output / "report.json"), report)

    async def test_atomic_commit_failure_never_publishes_success(self):
        with patch.object(p3_eval, "commit_terminal", side_effect=smoke.SmokeError("artifact_io")):
            with self.assertRaisesRegex(smoke.SmokeError, "artifact_io"):
                await self.run_formal()
        durable = formal.read_report(self.current_output / "report.json")
        self.assertEqual(durable["status"], "incomplete")
        self.assertEqual(len(self.sent), 28)
        self.assertTrue((self.current_output / "terminal-candidate.json").exists())
        self.assertTrue((self.current_output / "terminal.next.json").exists())

    async def test_terminal_success_visible_only_at_commit(self):
        commit = p3_eval.commit_terminal
        def check(pending, target):
            self.assertEqual(self.read(target)["status"], "incomplete")
            self.assertEqual(self.read(pending)["status"], "complete")
            commit(pending, target)
        with patch.object(p3_eval, "commit_terminal", side_effect=check) as mocked:
            report = await self.run_formal()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(mocked.call_count, 1)

    async def test_persistent_write_failure_preserves_last_reservation(self):
        persist = smoke._Artifacts.persist
        def fail_after_send(artifacts, report):
            if self.sent:
                raise smoke.SmokeError("artifact_io")
            return persist(artifacts, report)
        with patch.object(smoke._Artifacts, "persist", autospec=True, side_effect=fail_after_send):
            with self.assertRaisesRegex(smoke.SmokeError, "artifact_io"):
                await self.run_formal()
        self.assertEqual(len(self.sent), 1)
        durable = formal.read_report(self.current_output / "report.json")
        self.assertEqual(durable["status"], "incomplete")
        self.assertEqual(durable["client_http_attempts"], 0)
        self.assertEqual(durable["possible_in_flight_attempts"], 1)
        self.assertEqual(durable["attempt_budget_used"], 1)
        self.assertEqual(durable["results"][0]["phase"], "invoked")

    async def test_archive_independent_and_cannot_masquerade_as_legacy(self):
        report = await self.run_formal()
        with patch.object(formal, "validate_packet", side_effect=AssertionError("No current identity read")), \
                patch.object(p3_admission, "validate_freeze", side_effect=AssertionError("No current freeze read")), \
                patch.object(smoke, "_fixture_identity", side_effect=AssertionError("No DB read")):
            self.assertEqual(formal.read_report(self.current_output / "report.json"), report)
        report["report_version"] = "p3-report-v2"
        self.write(self.current_output / "report.json", report)
        with self.assertRaises(p3_assets.P3Error):
            formal.read_report(self.current_output / "report.json")

    async def test_reader_rejects_count_summary_raw_and_authorization_tampering(self):
        report = await self.run_formal()
        for mutate in (lambda r:r.update(client_http_attempts=0), lambda r:r.update(upstream_inference_attempts=28),
                       lambda r:r.update(possible_in_flight_attempts=False),
                       lambda r:r.update(attempt_budget_used=0),
                       lambda r:r.update(network_failure_streak=None),
                       lambda r:r["results"][0].update(phase="returned"),
                       lambda r:r["results"][0]["evidence"].update(client_http_attempts=0),
                       lambda r:r["results"][0]["evidence"].update(raw_completion="CANARY"),
                       lambda r:r.update(owner_authorization_reference=OWNER+"0"),
                       lambda r:r["summary"]["promotion"].update(passed=True)):
            changed = deepcopy(report)
            mutate(changed)
            self.write(self.current_output / "report.json", changed)
            with self.assertRaises(p3_assets.P3Error):
                formal.read_report(self.current_output / "report.json")

    def test_live_flag_alone_and_extra_arguments_never_authorize(self):
        for arguments in ([], ["--live"], ["--prepare","--live"], ["--report","--report-path","unused","--env-file","unused"]):
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(formal.main(arguments), 2)

    def test_legacy_preparation_reader_unchanged(self):
        archived = p3_eval.read_report(self.prepared / "report.json")
        self.assertEqual(archived["report_version"], "p3-report-v2")
        self.assertEqual(archived["live_model_attempts"], 0)
        self.assertTrue(all(row["outcome"] == "not_run" for row in archived["results"]))
