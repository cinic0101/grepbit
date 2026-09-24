"""Offline contract rulers for the JP Bedrock observed regression (#70)."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit.bedrock import BedrockClient, BedrockConfig
from grepbit.gateway import GatewayClient, GatewayConfig
from tools import fixture, p3_assets, p3_eval, p3_live_evidence
from tools import p3_bedrock_observed_regression as runner
from test_p3_admission import metadata_provenance
from test_p3_formal_policy import revised_scaffolding


PROFILE = runner.PROFILE
REGION = runner.REGION


def response(content='{"outcome":"declined"}'):
    return {"output": {"message": {"role": "assistant", "content": [{"text": content}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}


class BedrockObservedRulers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
        temporary = tempfile.TemporaryDirectory(prefix="p370-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "synthetic.sqlite"
        fixture.build(self.database)
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        seeds = {branch: next(case for case in exposed.cases if case.expected_branch == branch)
                 for branch in p3_assets.BRANCHES}
        cases = tuple(replace(seeds[row["expected_branch"]], **{
            key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort",
                                     "exposure", "semantic_signature", "must_pass", "observational")},
            provenance=p3_assets.Provenance.from_mapping(
                metadata_provenance(row["exposure"]), row["exposure"]))
            for row in revised_scaffolding())
        self.panel = p3_assets.Panel("SyntheticBedrockOnly", "formal", cases,
                                     tuple(exposed.oracle_for(case) for case in seeds.values()),
                                     self.root / "panel.json", self.root / "cases.json", self.root / "oracles.json")
        synthetic_order = tuple(case.case_id for case in cases)
        self.enterContext(patch.object(runner, "ORDER", synthetic_order))
        self.enterContext(patch.object(runner.historical, "_ORDER", synthetic_order))
        by_family = {}
        for case in cases:
            by_family.setdefault(case.family_id, []).append(case)
        groups = [group for group in by_family.values() if len(group) >= 2]
        failed = {groups[0][0].case_id, groups[0][1].case_id, groups[1][0].case_id}
        self.enterContext(patch.object(runner.historical, "_KNOWN_FAILURES", frozenset(failed)))
        rows = []
        for case in cases:
            wrong = case.case_id in failed
            rows.append({"case_id": case.case_id, "family_id": case.family_id,
                         "status": "completed", "outcome": "false_clarification" if wrong else
                         {"answer": "complete_correct", "clarify": "correct_clarification",
                          "decline": "correct_decline"}[case.expected_branch],
                         "actual_action": "clarify" if wrong else case.expected_branch,
                         "checked_wrong": False, "correct": not wrong})
        baseline = {"inputs": rows, "family_correct": {
            key: not any(case.case_id in failed for case in group)
            for key, group in by_family.items()}}
        runner.historical._validate_baseline(baseline)
        self.source = {"git_commit": "1" * 40, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {"synthetic": "1" * 64}}
        self.pins = {name: {"reference": name + ".json", "sha256": digest}
                     for name, digest in runner.PINS.items()}
        self.enterContext(patch.object(runner, "_sources", return_value=(
            self.panel, deepcopy(self.pins), deepcopy(self.source), deepcopy(baseline))))
        self.packet_dir = self.root / "packet"
        runner.prepare(self.database, self.packet_dir, intake_path=self.root / "intake.json",
                       panel_path=self.root / "panel.json", compatibility_path=self.root / "compatible.json",
                       historical_path=self.root / "historical.json", accepted_commit="1" * 40,
                       gateway_policies=dict(runner.POLICIES), transport_security=runner.TRANSPORT)
        self.packet_path = self.packet_dir / "manifest.json"
        self.auth_path = self.root / "authorization.json"
        runner.bind_authorization(
            self.packet_path, "https://github.com/cinic0101/grepbit/issues/70#issuecomment-123",
            self.auth_path)
        self.sent = []
        self.serial = 0

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    async def run_mock(self, *, handler=None, packet_path=None, authorization_path=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=response())

        client = BedrockClient(BedrockConfig(REGION, PROFILE, "synthetic-key"),
                               transport=httpx.MockTransport(respond))
        with patch.object(runner, "client_from_env", return_value=client) as load:
            result = await runner.run_live(
                self.database, self.output(), packet_path=packet_path or self.packet_path,
                authorization_path=authorization_path or self.auth_path,
                accepted_commit="1" * 40, env_file=self.root / "unused-synthetic.env",
                gateway_policies=dict(runner.POLICIES))
        return result, load

    def test_packet_binds_profile_runtime_and_nonpromotion(self):
        packet = p3_assets.read_asset(self.packet_path)
        self.assertEqual(packet["candidate"], runner.bedrock_probe.candidate_identity())
        self.assertEqual(packet["settings"]["call_timeout_seconds"], 300.0)
        self.assertEqual(packet["settings"]["panel_timeout_seconds"], 8520.0)
        self.assertEqual(packet["compatibility"]["sha256"], runner.COMPATIBILITY_SHA256)
        self.assertEqual(packet["wire_schema_sha256"], runner.bedrock_probe.WIRE_SCHEMA_SHA256)
        self.assertFalse(packet["promotion_eligible"])
        self.assertEqual(packet["evidence_class"], "observed_regression")
        self.assertEqual(p3_assets.read_asset(self.auth_path)["packet_sha256"],
                         hashlib.sha256(self.packet_path.read_bytes()).hexdigest())
        for field, bad in (("wire_schema_sha256", "0" * 64),
                           ("effective_runtime_identity_sha256", "0" * 64),
                           ("database_sha256", "0" * 64),
                           ("settings", {**packet["settings"], "panel_timeout_seconds": 1800.0}),
                           ("promotion_eligible", True)):
            with self.subTest(field=field):
                changed = deepcopy(packet)
                changed[field] = bad
                with self.assertRaises(p3_assets.P3Error):
                    runner._packet_contract(changed)

    def test_preparation_recomputes_current_runtime_and_schema_identities(self):
        self.assertEqual(runner._current_identities(), {
            "baseline_semantic_identity_sha256": runner.bedrock_probe.semantic.SEMANTICS_SHA256,
            "effective_runtime_identity_sha256": runner.bedrock_probe.EFFECTIVE_RUNTIME_SHA256,
            "canonical_schema_sha256": runner.bedrock_probe.CANONICAL_SCHEMA_SHA256,
            "wire_schema_sha256": runner.bedrock_probe.WIRE_SCHEMA_SHA256,
        })
        original = runner.bedrock_probe.semantic.semantic_identity
        with patch.object(runner.bedrock_probe.semantic, "semantic_identity",
                          side_effect=lambda: {**original(), "unexpected": "drift"}):
            with self.assertRaisesRegex(p3_assets.P3Error, "source_identity_failure"):
                runner._current_identities()
        with patch.object(runner.bedrock_probe, "_schemas",
                          return_value=(runner.bedrock_probe.CANONICAL_SCHEMA_SHA256, "0" * 64)):
            with self.assertRaisesRegex(p3_assets.P3Error, "source_identity_failure"):
                runner._current_identities()

    def test_compatibility_reader_uses_safe_projection(self):
        projection = {"compatibility_passed": True, "status": "complete", "origin": "live",
                      "client_http_attempts": 1, "report_sha256": runner.COMPATIBILITY_SHA256,
                      "requested_profile": PROFILE, "observed_model": None,
                      "baseline_semantic_identity_sha256": runner.bedrock_probe.semantic.SEMANTICS_SHA256,
                      "effective_runtime_identity_sha256": runner.bedrock_probe.EFFECTIVE_RUNTIME_SHA256}
        path = self.root / "compatible.json"
        with patch.object(runner, "_pin"), \
             patch.object(runner.bedrock_probe, "read_report", return_value=projection):
            self.assertEqual(runner._compatible_report(path), projection)
        with patch.object(runner, "_pin"), \
             patch.object(runner.bedrock_probe, "read_report",
                          return_value={**projection, "requested_profile": "other"}):
            with self.assertRaises(p3_assets.P3Error):
                runner._compatible_report(path)

    async def test_mocked_28_input_run_uses_shared_loop_and_archives_safe_evidence(self):
        observed = []
        original = p3_eval.interpret_recipe_and_execute

        async def observe(question, database, client, **options):
            observed.append(options["timeout_seconds"])
            return await original(question, database, client, **options)

        with patch.object(p3_eval, "interpret_recipe_and_execute", side_effect=observe):
            report, load = await self.run_mock()
        self.assertEqual(report["status"], "complete")
        self.assertEqual((report["client_http_attempts"], report["runtime_invocations"], len(self.sent)),
                         (28, 28, 28))
        self.assertEqual(len(observed), 28)
        self.assertTrue(all(0 < budget <= 300 for budget in observed))
        self.assertTrue(any(budget > 60 for budget in observed))
        self.assertEqual(load.call_count, 1)
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["summary"]["promotion_result"], "not_applicable")
        self.assertEqual(sum(report["summary"]["comparison"]["category_counts"].values()), 28)
        self.assertEqual(runner.read_report(self.root / "run-1" / "report.json"), report)
        for row in report["results"]:
            self.assertEqual(row["evidence"]["requested_model"], PROFILE)
            self.assertIsNone(row["evidence"]["returned_model"])
        self.assertNotIn("synthetic-key", json.dumps(report))
        self.assertNotIn("bedrock-runtime.", json.dumps(report))
        path = self.root / "run-1" / "report.json"
        changed = deepcopy(report)
        changed["results"][0]["evidence"]["returned_model"] = PROFILE
        path.write_text(json.dumps(changed))
        with self.assertRaises(p3_assets.P3Error):
            runner.read_report(path)

    async def test_invalid_typed_request_is_unassessed_after_json_parse(self):
        report, _ = await self.run_mock(handler=lambda _: httpx.Response(200, json=response(
            '{"outcome":"request","recipe_id":"overview","recipe_version":"0.1",'
            '"request":{"center_code":"CTR-001"}}')))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 28)
        row = report["results"][0]
        self.assertEqual(row["error_code"], "invalid_request")
        self.assertEqual(row["evidence"]["stages"]["json_parse"], "passed")
        self.assertEqual(row["evidence"]["stages"]["request_validation"], "failed")
        self.assertEqual(row["evidence"]["stages"]["kernel_execution"], "not_run")
        self.assertEqual(report["summary"]["comparison"]["taxonomy"][0]["category"],
                         "UNASSESSED_OPERATIONAL")

    async def test_outer_deadline_preserves_profile_and_timeout_streak(self):
        calls = 0

        async def timeout(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise TimeoutError

        with patch.object(p3_eval, "interpret_recipe_and_execute", side_effect=timeout):
            report, _ = await self.run_mock()
        self.assertEqual(calls, 2)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "consecutive_timeouts")
        self.assertEqual(report["timeout_streak"], 2)
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(runner.read_report(self.root / "run-1" / "report.json"), report)
        for row in report["results"][:2]:
            self.assertEqual(row["error_code"], "timeout")
            self.assertEqual(row["evidence"]["requested_model"], PROFILE)
            self.assertIsNone(row["evidence"]["returned_model"])

    async def test_wrong_provider_or_region_stops_before_send(self):
        for wrong in (GatewayClient(GatewayConfig("http://synthetic.invalid/v1", "key"),
                                    transport=httpx.MockTransport(lambda _: AssertionError("sent"))),
                      BedrockClient(BedrockConfig("us-east-1", PROFILE, "synthetic-key"),
                                    transport=httpx.MockTransport(lambda _: AssertionError("sent")))):
            with self.subTest(client=type(wrong).__name__), \
                 patch.object(runner, "client_from_env", return_value=wrong):
                report = await runner.run_live(
                    self.database, self.output(), packet_path=self.packet_path,
                    authorization_path=self.auth_path, accepted_commit="1" * 40,
                    env_file=self.root / "unused.env", gateway_policies=dict(runner.POLICIES))
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["stop_reason"], "invalid_configuration")
                self.assertEqual(report["client_http_attempts"], 0)
                self.assertEqual(self.sent, [])

    async def test_bad_packet_and_authorization_stop_before_env(self):
        packet = p3_assets.read_asset(self.packet_path)
        changed = deepcopy(packet)
        changed["candidate"]["calling_region"] = "us-east-1"
        bad_packet = self.root / "bad-packet.json"
        bad_packet.write_text(json.dumps(changed))
        for packet_path, authorization_path in ((bad_packet, self.auth_path),
                                                (self.packet_path, self.root / "missing-auth.json")):
            with self.subTest(packet=packet_path), \
                 patch.object(runner, "client_from_env", side_effect=AssertionError("env")) as env:
                with self.assertRaises((p3_assets.P3Error, ValueError)):
                    await runner.run_live(self.database, self.output(), packet_path=packet_path,
                                          authorization_path=authorization_path, accepted_commit="1" * 40,
                                          env_file=self.root / "unused.env", gateway_policies=dict(runner.POLICIES))
                env.assert_not_called()
        wrong_auth = self.root / "wrong-issue-auth.json"
        wrong_auth.write_text(json.dumps({"version": runner.AUTHORIZATION_VERSION,
            "packet_sha256": hashlib.sha256(self.packet_path.read_bytes()).hexdigest(),
            "owner_authorization_reference":
                "https://github.com/cinic0101/grepbit/issues/64#issuecomment-123"}))
        with patch.object(runner, "client_from_env", side_effect=AssertionError("env")) as env:
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, self.output(), packet_path=self.packet_path,
                                      authorization_path=wrong_auth, accepted_commit="1" * 40,
                                      env_file=self.root / "unused.env", gateway_policies=dict(runner.POLICIES))
            env.assert_not_called()

    def test_bedrock_evidence_requires_requested_profile_and_unknown_returned_model(self):
        value = {"requested_model": PROFILE, "returned_model": None,
                 "client_http_attempts": 1}
        self.assertEqual(p3_live_evidence._evidence(value, requested_profile=PROFILE), value)
        for mutation in ({"returned_model": PROFILE}, {"requested_model": "other"}):
            with self.subTest(mutation=mutation), self.assertRaises(p3_assets.P3Error):
                p3_live_evidence._evidence({**value, **mutation}, requested_profile=PROFILE)
        with self.assertRaises(p3_assets.P3Error):
            p3_live_evidence._evidence({"requested_model": PROFILE, "client_http_attempts": 1},
                                      requested_profile=PROFILE)


if __name__ == "__main__":
    unittest.main()
