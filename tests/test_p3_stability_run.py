"""Governed stability tests: synthetic metadata + exposed payloads + MockTransport only."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import fixture, p3_admission, p3_assets, p3_eval, p3_formal_policy, p3_formal_run
from tools import p3_live_evidence, p3_stability_run as stability, recipe_smoke, smoke
from test_p3_admission import abstract_reviews, metadata_provenance
from test_p3_formal_policy import revised_scaffolding
from test_p3_stability_contract import IDS

SHA = "1" * 40
OWNER = "https://github.com/cinic0101/grepbit/issues/52#issuecomment-123456789"
POLICIES = {"retries": "enabled", "fallback": "disabled", "cache": "disabled"}
BASE = "http://synthetic-stability-test.invalid/v1"
KEY = "synthetic-stability-secret-key"


def envelope(content):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


def metadata():
    rows = revised_scaffolding()
    groups = {}
    for row in rows:
        groups.setdefault(row["family_id"], []).append(row)
    selected = [
        next(g for g in groups.values() if g[0]["cohort"] == "answer" and g[0]["exposure"] == "frozen_fresh" and len(g) == 3),
        next(g for g in groups.values() if g[0]["cohort"] == "answer" and g[0]["exposure"] == "frozen_fresh" and len(g) == 1),
        next(g for g in groups.values() if g[0]["cohort"] == "anchor"),
        next(g for g in groups.values() if g[0]["cohort"] == "clarify" and g[0]["exposure"] == "frozen_fresh"),
        *[g for g in groups.values() if g[0]["cohort"] == "decline" and g[0]["exposure"] == "frozen_fresh"],
    ]
    for group, (case_id, family, cohort, revision) in zip(selected, stability._SELECTED):
        for row in group:
            row.update(family_id=family, case_id=family + (".r2" if revision == "v2" else "") + "." + row["language"],
                       oracle_id=family + "." + revision)
    return rows


class StabilityRunTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Real network/env forbidden")))
            self.addCleanup(guard.assert_not_called)
        tmp = tempfile.TemporaryDirectory(prefix="p37-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.db_hash = smoke._fixture_identity(self.database)
        self.db_identity = self.enterContext(patch.object(smoke, "_fixture_identity", return_value=self.db_hash))
        self.enterContext(patch.object(smoke, "_stable_database", return_value=self.db_hash))
        self.source = {"git_commit": SHA, "branch": "dev", "worktree_dirty": False, "files_sha256": {},
                       "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(self.source)))
        candidate = p3_admission.candidate_identity()
        self.enterContext(patch.object(p3_admission, "candidate_identity", return_value=candidate))
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        script = p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES, exposed)
        seeds = {branch: next(c for c in exposed.cases if c.expected_branch == branch) for branch in p3_assets.BRANCHES}
        actions = {case.oracle_id: action for case, action in zip(exposed.cases, script)}
        cases, oracles, self.actions = [], {}, {}
        for row in metadata():
            seed = seeds[row["expected_branch"]]
            # Exposed runtime objects only. These synthetic aliases do NOT claim
            # that exposed payloads are real fresh families or semantic admission.
            oid = row["family_id"] + (".v2" if row["family_id"].startswith("FA09") else ".v1")
            cases.append(replace(seed, **{k: row[k] for k in (
                "case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
                "semantic_signature", "must_pass", "observational")}, oracle_id=oid,
                provenance=p3_assets.Provenance.from_mapping(metadata_provenance(row["exposure"]), row["exposure"])))
            oracles[oid] = p3_assets.parse_oracle({**exposed.oracle_for(seed).to_dict(), "oracle_id": oid})
            self.actions[row["case_id"]] = actions[seed.oracle_id]
        self.cases, self.oracles = tuple(cases), tuple(oracles.values())
        for filename in ("development-cases-v1.json", "development-oracles-v1.json"):
            (self.root / filename).write_bytes((p3_eval.DEFAULT_PANEL.parent / filename).read_bytes())
        self.panel_path = self.root / "synthetic-formal-panel.json"
        self.write(self.panel_path, {"version": "p3-panel-v1", "panel_id": "SyntheticOnlyNotAdmitted", "kind": "formal",
                                   "cases": "development-cases-v1.json", "oracles": "development-oracles-v1.json",
                                   "order": [case.case_id for case in self.cases]})
        intake_path = self.root / "synthetic-intake.json"
        self.write(intake_path, {"synthetic_metadata_only": True})
        self.review = {"state": "novelty_reviewed", "owner_review_reference": "synthetic-admission-only",
                       "families": abstract_reviews(self.panel(self.panel_path).inputs()),
                       **{name: p3_eval._pin(self.root / filename) for name, filename in (
                           ("cases", "development-cases-v1.json"), ("oracles", "development-oracles-v1.json"))}}
        self.enterContext(patch.object(p3_admission, "_intake", side_effect=lambda path: (
            deepcopy(self.review), self.cases, self.oracles, {"review_assertions_complete": True})))
        self.frozen, self.prepared = self.root / "synthetic-freeze", self.root / "synthetic-prepared"
        p3_admission.freeze_panel(self.database, intake_path, self.panel_path, self.frozen,
                                 accepted_commit=SHA, allocation_policy=p3_formal_policy.V2)
        p3_eval.prepare(self.database, self.prepared, panel_path=self.frozen / self.panel_path.name,
                        accepted_commit=SHA, formal_freeze=self.frozen / "report.json")
        self.enterContext(patch.object(stability, "_ASSET_SHA", {
            name: p3_eval._pin(path)["sha256"] for name, path in (
                ("cases", self.root / "development-cases-v1.json"),
                ("oracles", self.root / "development-oracles-v1.json"), ("panel", self.panel_path))}))
        self.packet_dir = self.root / "packet"
        stability.prepare(self.database, self.packet_dir, freeze_path=self.frozen / "report.json",
                          preparation_path=self.prepared / "manifest.json", accepted_commit=SHA,
                          gateway_policies=POLICIES, transport_security="unencrypted_http")
        self.packet_path = self.packet_dir / "manifest.json"
        self.packet = self.read(self.packet_path)
        self.auth_path = self.root / "synthetic-authorization.json"
        stability.bind_authorization(self.packet_path, OWNER, self.auth_path)
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

    async def run_stability(self, handler=None, **options):
        self.sent = []
        self.current_output = options.pop("output_dir", self.output())
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        with patch.object(stability.GatewayConfig, "from_env", return_value=client.config) as config, \
                patch.object(stability, "GatewayClient", return_value=client) as factory:
            report = await stability.run_live(self.database, self.current_output, packet_path=self.packet_path,
                authorization_path=options.pop("authorization_path", self.auth_path),
                accepted_commit=options.pop("accepted_commit", SHA), env_file=self.root / "synthetic-explicit.env",
                gateway_policies=options.pop("gateway_policies", POLICIES), **options)
        self.config_calls, self.factory_calls = config.call_count, factory.call_count
        return report

    async def reject_before_config(self, **options):
        with patch.object(stability.GatewayConfig, "from_env", side_effect=AssertionError("Must not load")) as load, \
                patch.object(stability, "GatewayClient", side_effect=AssertionError("Must not construct")) as factory:
            with self.assertRaises((p3_assets.P3Error, smoke.SmokeError, recipe_smoke.RecipeSmokeError)):
                await stability.run_live(self.database, self.output(), packet_path=self.packet_path,
                    authorization_path=options.pop("authorization_path", self.auth_path),
                    accepted_commit=options.pop("accepted_commit", SHA), env_file=self.root / "unused.env",
                    gateway_policies=options.pop("gateway_policies", POLICIES))
            load.assert_not_called()
            factory.assert_not_called()

    def test_packet_pins_schedule_versions_and_no_authorization_circularity(self):
        self.assertEqual(self.packet["version"], "p3-stability-packet-v1")
        self.assertEqual(self.packet["stop_policy"]["version"], "p3-stability-stops-v1")
        self.assertEqual([r["case_id"] for r in self.packet["schedule"]], list(IDS) * 3)
        self.assertEqual(len(self.packet["inputs"]), 28)  # unchanged source membership
        self.assertEqual(len(self.packet["selection"]), 6)
        self.assertEqual(self.packet["schedule_sha256"], p3_assets.digest(self.packet["schedule"]))
        self.assertNotIn(OWNER, json.dumps(self.packet))
        self.assertIsNone(self.packet["upstream_inference_attempts"])
        self.assertIn("tools/p3_stability_run.py", self.packet["identities"]["files_sha256"])
        entries = stability._entries(self.panel(self.panel_path), self.packet)
        self.assertEqual(len(entries), 18)
        self.assertIs(entries[0].case, entries[6].case)
        self.assertIs(entries[0].oracle, entries[12].oracle)

    async def test_missing_wrong_blank_or_stale_authorization_never_loads_env(self):
        await self.reject_before_config(authorization_path=self.root / "missing.json")
        original = self.read(self.auth_path)
        for change in ({"version": "wrong"}, {"packet_sha256": "0"*64}, {"extra": True},
                       *({"owner_authorization_reference": v} for v in (
                           None, "", " ", OWNER.replace("/52#", "/49#"), OWNER + " "))):
            self.write(self.auth_path, {**original, **change})
            await self.reject_before_config()
        self.write(self.auth_path, original)
        await self.reject_before_config(accepted_commit="2"*40)
        for change in ({"branch": "feature"}, {"worktree_dirty": True}, {"git_commit": "2"*40}):
            original_source = deepcopy(self.source)
            self.source.update(change)
            await self.reject_before_config()
            self.source = original_source

    def test_packet_contract_rejects_boolean_numeric_aliases(self):
        for mutate in (lambda p:p["settings"].update(concurrency=True),
                       lambda p:p["comparison_policy"]["gate"].update(semantic_flips=False),
                       lambda p:p["historical_quality"].update(quality_promotion_remains_failed=1)):
            changed = deepcopy(self.packet)
            mutate(changed)
            with self.assertRaises(p3_assets.P3Error):
                stability._packet_contract(changed)

    async def test_packet_order_assets_policy_and_source_drift_before_env(self):
        original = deepcopy(self.packet)
        original_auth = self.read(self.auth_path)
        for mutate in (lambda p:p["schedule"].reverse(), lambda p:p["selection"].reverse(),
                       lambda p:p["assets"]["cases"].update(sha256="f"*64),
                       lambda p:p["allocation_policy"].update(version="p3-formal-allocation-v1"),
                       lambda p:p["historical_quality"].update(promotion="passed"),
                       lambda p:p["gateway_policy"].update(cache="enabled")):
            changed = deepcopy(original)
            mutate(changed)
            self.write(self.packet_path, changed)
            self.write(self.auth_path, {**original_auth,
                                       "packet_sha256": p3_eval._pin(self.packet_path)["sha256"]})
            await self.reject_before_config()
        self.write(self.packet_path, original)
        self.write(self.auth_path, original_auth)
        self.source["context"]["context_sha256"] = "f"*64
        await self.reject_before_config()

    async def test_db_and_freeze_drift_before_env(self):
        self.db_identity.return_value = "a"*64
        await self.reject_before_config()
        self.db_identity.return_value = self.db_hash
        path = self.frozen / "report.json"
        value = self.read(path)
        value["accepted_tooling_sha"] = "2"*40
        self.write(path, value)
        await self.reject_before_config()

    async def test_cache_or_attestation_mismatch_before_env(self):
        for key in POLICIES:
            changed = {**POLICIES, key: "disabled" if POLICIES[key] == "enabled" else "enabled"}
            await self.reject_before_config(gateway_policies=changed)

    async def test_transport_mismatch_before_client(self):
        config = GatewayConfig("https://synthetic-stability-test.invalid/v1", KEY)
        with patch.object(stability.GatewayConfig, "from_env", return_value=config), \
                patch.object(stability, "GatewayClient", side_effect=AssertionError("Must not construct")) as factory:
            output = self.output()
            report = await stability.run_live(self.database, output, packet_path=self.packet_path,
                authorization_path=self.auth_path, accepted_commit=SHA, env_file=self.root / "synthetic.env",
                gateway_policies=POLICIES)
        factory.assert_not_called()
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        self.assertEqual(stability.read_report(output / "report.json"), report)

    async def test_18_attempts_wrong_semantics_continue_no_promotion(self):
        report = await self.run_stability()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(self.sent), 18)
        self.assertEqual(report["runtime_invocations"], 18)
        self.assertEqual(report["client_http_attempts"], 18)
        self.assertEqual(report["attempt_budget_used"], 18)
        self.assertEqual(report["summary"]["comparable_pairs"], 18)
        self.assertEqual(report["summary"]["semantic_flips"], 0)
        self.assertFalse(report["summary"]["stability_passed"])
        self.assertTrue(report["summary"]["quality_promotion_remains_failed"])
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)

    async def test_all_correct_stability_does_not_rescue_formal(self):
        def respond(request):
            cid = self.packet["schedule"][len(self.sent)-1]["case_id"]
            return httpx.Response(200, json=envelope(json.dumps(self.actions[cid])))
        report = await self.run_stability(respond)
        self.assertTrue(report["summary"]["stability_passed"])
        self.assertEqual(report["summary"]["correct_trials"], 18)
        self.assertEqual(report["historical_quality"]["promotion"], "failed")
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)

    async def test_reservation_before_every_send_and_original_trial_identity(self):
        def respond(request):
            durable = self.read(self.current_output / "report.json")
            row = durable["results"][len(self.sent)-1]
            self.assertEqual(row["phase"], "invoked")
            self.assertTrue(row["attempt_may_be_in_flight"])
            self.assertEqual(row["execution_order"], len(self.sent))
            self.assertEqual(row["round_number"], (len(self.sent)-1)//6+1)
            return httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        report = await self.run_stability(respond)
        self.assertEqual(report["status"], "complete")
        checkpoints = [self.read(path) for path in self.current_output.glob("checkpoint-*.json")]
        for i in range(18):
            self.assertTrue({"reserved", "invoked", "returned", "graded"} <= {
                item["results"][i]["phase"] for item in checkpoints})

    async def test_sequential_runtime_and_bounded_timeout(self):
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
            await self.run_stability()
        self.assertEqual(len(calls), 18)
        self.assertEqual(calls[:6], calls[6:12])

    async def test_network_timeout_streaks_separate_no_retry(self):
        errors = [httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.ReadTimeout]
        def respond(request):
            raise errors[len(self.sent)-1]("PRIVATE_PROVIDER_CANARY")
        report = await self.run_stability(respond)
        self.assertEqual(len(self.sent), 5)
        self.assertEqual(report["stop_reason"], "consecutive_timeouts")
        self.assertEqual(report["network_failure_streak"], 0)
        self.assertEqual(report["summary"]["comparable_pairs"], 0)
        self.assertIsNone(report["summary"]["flip_rate"])
        self.assertNotIn("PRIVATE_PROVIDER_CANARY", json.dumps(report))
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)

    async def test_network_and_immediate_operational_stops(self):
        def fail(request):
            raise httpx.ConnectError("PRIVATE_PROVIDER_CANARY")
        report = await self.run_stability(fail)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(report["stop_reason"], "consecutive_network_failures")
        for code in (401, 413, 302, 200):
            report = await self.run_stability(lambda request: httpx.Response(code, json={}))
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(report["status"], "incomplete")

    async def test_invalid_outputs_continue_but_no_synthetic_agreements(self):
        for content in ("PRIVATE_BAD_JSON", '{"outcome":"request","invalid":true}'):
            report = await self.run_stability(lambda r:httpx.Response(200, json=envelope(content)))
            self.assertEqual(len(self.sent), 18)
            self.assertEqual(report["summary"]["invalid_trials"], 18)
            self.assertEqual(report["summary"]["comparable_pairs"], 0)
            self.assertEqual(report["summary"]["semantic_flips"], 0)
            self.assertFalse(report["summary"]["stability_passed"])
            self.assertNotIn(content, json.dumps(report))

    async def test_cancellation_preserves_inflight_and_never_resumes(self):
        def respond(request):
            raise asyncio.CancelledError
        report = await self.run_stability(respond)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertEqual(report["attempt_budget_used"], 1)
        self.assertEqual(report["results"][0]["phase"], "invoked")
        self.assertEqual(report["stop_reason"], "interrupted")
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)
        with self.assertRaises(smoke.SmokeError):
            await self.run_stability(output_dir=self.current_output)
        self.assertEqual(len(self.sent), 0)

    async def test_deadline_recheck_after_invocation_checkpoint(self):
        persist = smoke._Artifacts.persist
        now = [0]
        def expire(artifacts, report):
            result = persist(artifacts, report)
            if report.get("results") and report["results"][0].get("phase") == "invoked":
                now[0] = 1201
            return result
        with patch.object(smoke._Artifacts, "persist", autospec=True, side_effect=expire):
            report = await self.run_stability(clock=lambda: now[0])
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["stop_reason"], "panel_budget")

    async def test_drift_after_reservation_stops_without_send(self):
        persist = smoke._Artifacts.persist
        def drift(artifacts, report):
            result = persist(artifacts, report)
            if report.get("results") and report["results"][0].get("phase") == "reserved":
                self.db_identity.return_value = "f"*64
            return result
        with patch.object(smoke._Artifacts, "persist", autospec=True, side_effect=drift):
            report = await self.run_stability()
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(report["runtime_invocations"], 0)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)

    async def test_one_use_guard_has_stability_18_send_limit(self):
        sent = []
        def respond(request):
            sent.append(request)
            return httpx.Response(200, json=envelope('{"outcome":"declined"}'))
        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        guard = stability._LiveEvidence().invocation_client(client)
        messages = recipe_model.messages_for(self.cases[0].question)
        await guard.complete(messages)
        with self.assertRaisesRegex(p3_assets.P3Error, "attempt_budget"):
            await guard.complete(messages)
        client.http_attempts = 18
        with self.assertRaisesRegex(p3_assets.P3Error, "attempt_budget"):
            await stability._LiveEvidence().invocation_client(client).complete(messages)
        self.assertEqual(len(sent), 1)

    async def test_live_whitelist_drops_provider_and_native_canaries(self):
        invoke = p3_eval.interpret_recipe_and_execute
        async def inject(*args, **kwargs):
            result = await invoke(*args, **kwargs)
            return replace(result, evidence={**result.evidence,
                "reasoning": "PRIVATE_REASONING", "raw_completion": "PRIVATE_COMPLETION",
                "proposal": {"private": "PRIVATE_NATIVE"}, "analysis_pack": {"rows": "PRIVATE_FACTS"},
                "headers": {"Authorization": KEY}, "endpoint": BASE})
        with patch.object(p3_eval, "interpret_recipe_and_execute", side_effect=inject):
            report = await self.run_stability()
        for canary in ("PRIVATE_REASONING", "PRIVATE_COMPLETION", "PRIVATE_NATIVE", "PRIVATE_FACTS", BASE, KEY):
            self.assertNotIn(canary, json.dumps(report))
            self.assertNotIn(canary, (self.current_output / "report.json").read_text())
        self.assertEqual(stability.read_report(self.current_output / "report.json"), report)

    async def test_stateless_wire_bytes_repeat_and_metadata_absent(self):
        report = await self.run_stability()
        cases = {case.case_id: case for case in self.cases}
        for request, row in zip(self.sent, self.packet["schedule"]):
            wire = json.loads(request.content)
            self.assertEqual(wire["messages"], recipe_model.messages_for(cases[row["case_id"]].question))
            self.assertEqual(set(wire), {"model", "messages", "temperature", "max_tokens", "stream", "response_format"})
            for canary in (row["case_id"], row["family_id"], row["oracle_id"], OWNER,
                           "trial_number", "execution_order", "round_number", "semantic_flips", "outcome"):
                # 'outcome' is legitimately in the unchanged system/schema, so
                # exact messages comparison above protects previous output instead.
                if canary != "outcome":
                    self.assertNotIn(canary, request.content.decode())
        for i in range(6):
            self.assertEqual(self.sent[i].content, self.sent[i+6].content)
            self.assertEqual(self.sent[i].content, self.sent[i+12].content)
        self.assertIsNone(report["upstream_inference_attempts"])
        for forbidden in (BASE, KEY, "raw_completion", "reasoning", "proposal", "native_request", "fact_values"):
            self.assertNotIn(forbidden, json.dumps(report))

    async def test_atomic_terminal_success_and_failure_preserve_evidence(self):
        commit = p3_eval.commit_terminal
        def observe(pending, target):
            self.assertEqual(self.read(target)["status"], "incomplete")
            self.assertEqual(self.read(pending)["status"], "complete")
            commit(pending, target)
        with patch.object(p3_eval, "commit_terminal", side_effect=observe):
            report = await self.run_stability()
        self.assertEqual(report["status"], "complete")
        def correct(request):
            cid = self.packet["schedule"][len(self.sent)-1]["case_id"]
            return httpx.Response(200, json=envelope(json.dumps(self.actions[cid])))
        with patch.object(p3_eval, "commit_terminal", side_effect=smoke.SmokeError("artifact_io")):
            with self.assertRaises(smoke.SmokeError):
                await self.run_stability(correct)
        self.assertEqual(self.read(self.current_output / "report.json")["status"], "incomplete")
        for name in ("terminal-candidate.json", "terminal.next.json"):
            candidate = self.current_output / name
            self.assertTrue(self.read(candidate)["summary"]["stability_passed"])
            with self.assertRaises(p3_assets.P3Error):
                stability.read_report(candidate)
        durable = stability.read_report(self.current_output / "report.json")
        self.assertFalse(durable["summary"]["stability_passed"])

    async def test_archive_independent_and_formal_versions_disjoint(self):
        report = await self.run_stability()
        with patch.object(stability, "validate_packet", side_effect=AssertionError("No current identity")), \
                patch.object(p3_admission, "validate_freeze", side_effect=AssertionError("No freeze")), \
                patch.object(smoke, "_fixture_identity", side_effect=AssertionError("No DB")):
            self.assertEqual(stability.read_report(self.current_output / "report.json"), report)
        with self.assertRaises(p3_assets.P3Error):
            p3_formal_run.read_report(self.current_output / "report.json")
        self.assertEqual(p3_eval.read_report(self.prepared / "report.json")["report_version"], "p3-report-v2")

    async def test_archive_rejects_counter_summary_trial_and_raw_tampering(self):
        report = await self.run_stability()
        for mutate in (lambda r:r["summary"].update(stability_passed=True),
                       lambda r:r["summary"].update(comparable_pairs=17),
                       lambda r:r["historical_quality"].update(promotion="passed"),
                       lambda r:r["results"][0].update(trial_number=3),
                       lambda r:r["results"][0].update(trial_number=True),
                       lambda r:r["results"][0]["evidence"].update(raw_completion="CANARY"),
                       lambda r:r.update(client_http_attempts=0),
                       lambda r:r.update(upstream_inference_attempts=18)):
            changed = deepcopy(report)
            mutate(changed)
            self.write(self.current_output / "report.json", changed)
            with self.assertRaises(p3_assets.P3Error):
                stability.read_report(self.current_output / "report.json")

    def test_binding_preparation_exclusive_and_cli_not_live_by_default(self):
        packet = self.packet_path.read_bytes()
        with self.assertRaisesRegex(p3_assets.P3Error, "artifact_conflict"):
            stability.bind_authorization(self.packet_path, OWNER, self.auth_path)
        self.assertEqual(self.packet_path.read_bytes(), packet)
        for argv in ([], ["--live"], ["--report", "--report-path", "unused", "--env-file", "unused"]):
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(stability.main(argv), 2)


if __name__ == "__main__":
    unittest.main()
