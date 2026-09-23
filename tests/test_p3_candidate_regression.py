"""Issue #58 contract rulers; synthetic transports only, never live authority."""
import importlib.util
import asyncio
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit.gateway import GEMMA_12B, GatewayClient, GatewayConfig
from tools import fixture, p3_assets, p3_candidate_model, p3_eval, p3_live_evidence, smoke
from tools import p3_formal_run, p3_stability_run
from tools import p3_candidate_regression as candidate_regression
from test_p3_formal_policy import revised_scaffolding
from test_p3_admission import metadata_provenance

SOURCE_IMPL = candidate_regression._sources


class CandidateRegressionRulers(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec("tools.p3_candidate_regression"),
                             "A purpose-specific candidate regression runner is required")
        from tools import p3_candidate_regression
        return p3_candidate_regression

    def test_purpose_specific_versions_and_closed_identity(self):
        runner = self.runner()
        self.assertEqual(runner.PACKET_VERSION, "p3-candidate-regression-packet-v1")
        self.assertEqual(runner.AUTHORIZATION_VERSION, "p3-candidate-regression-authorization-v1")
        self.assertEqual(runner.MANIFEST_VERSION, "p3-candidate-regression-manifest-v1")
        self.assertEqual(runner.REPORT_VERSION, "p3-candidate-regression-report-v1")
        self.assertEqual(runner.STOP_VERSION, "p3-candidate-regression-stops-v1")
        with patch.object(runner, "_packet_contract") as closed:
            self.assertEqual(runner._expected_model({"candidate": p3_candidate_model.identity()}), GEMMA_12B)
        closed.assert_called_once()

    def test_12b_safe_projector_is_exact_and_31b_default_stays_closed(self):
        self.assertEqual(p3_live_evidence._evidence({"requested_model": "gemma-4-12b-it"},
                                                   expected_model=GEMMA_12B)["requested_model"],
                         "gemma-4-12b-it")
        with self.assertRaises(p3_assets.P3Error):
            p3_live_evidence._evidence({"returned_model": "gemma-4-31b"}, expected_model=GEMMA_12B)
        with self.assertRaises(p3_assets.P3Error):
            p3_live_evidence._evidence({"requested_model": "gemma-4-12b-it"})

    def test_synthetic_all_correct_never_becomes_promotion(self):
        runner = self.runner()
        rows = [{"case_id": f"synthetic-{index}", "correct": True} for index in range(28)]
        with patch.object(runner.allocation, "validate_allocation"), \
             patch.object(runner, "_comparison", return_value={"known_failures_fixed": 3}), \
             patch.object(runner.scoring, "summarize", return_value={
                "per_input": rows, "per_family": {},
                "promotion": {"eligible": True, "passed": True, "gates": {"all": True}}}):
            report = {"results": rows, "status": "complete", "panel_kind": "candidate_regression",
                      "historical_31b": {"projection": {}}}
            runner._summarize(report)
        self.assertFalse(report["summary"]["promotion_eligible"])
        self.assertEqual(report["summary"]["promotion_result"], "not_applicable")
        self.assertNotIn("promotion", report["summary"])
        self.assertEqual(report["summary"]["per_input"], rows)


class SyntheticCandidateExecution(unittest.IsolatedAsyncioTestCase):
    """Synthetic metadata and MockTransport; no accepted live artifact is created."""

    def setUp(self):
        from tools import p3_candidate_regression as runner
        self.runner = runner
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
            self.addCleanup(guard.assert_not_called)
        temp = tempfile.TemporaryDirectory(prefix="p311-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "synthetic.sqlite"
        fixture.build(self.db)
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        seeds = {branch: next(case for case in exposed.cases if case.expected_branch == branch)
                 for branch in p3_assets.BRANCHES}
        self.cases = tuple(replace(seeds[row["expected_branch"]], **{
            key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort",
                                     "exposure", "semantic_signature", "must_pass", "observational")},
            provenance=p3_assets.Provenance.from_mapping(metadata_provenance(row["exposure"]), row["exposure"]))
            for row in revised_scaffolding())
        self.panel = p3_assets.Panel("SyntheticCandidateOnly", "formal", self.cases,
                                     tuple(exposed.oracle_for(case) for case in seeds.values()),
                                     self.root / "panel.json", self.root / "cases.json", self.root / "oracles.json")
        self.enterContext(patch.object(runner, "_ORDER", tuple(case.case_id for case in self.cases)))
        by_family = {}
        for case in self.cases:
            by_family.setdefault(case.family_id, []).append(case)
        groups = [group for group in by_family.values() if len(group) >= 2]
        failures = {groups[0][0].case_id, groups[0][1].case_id, groups[1][0].case_id}
        self.enterContext(patch.object(runner, "_KNOWN_FAILURES", frozenset(failures)))
        baseline_rows = []
        for case in self.cases:
            failed = case.case_id in failures
            baseline_rows.append({"case_id": case.case_id, "family_id": case.family_id,
                                  "status": "completed", "outcome": "false_clarification" if failed else
                                  {"answer": "complete_correct", "clarify": "correct_clarification",
                                   "decline": "correct_decline"}[case.expected_branch],
                                  "actual_action": "clarify" if failed else case.expected_branch,
                                  "checked_wrong": False, "correct": not failed})
        self.baseline = {"inputs": baseline_rows,
                         "family_correct": {key: not any(c.case_id in failures for c in group)
                                            for key, group in by_family.items()}}
        self.source = {"git_commit": "1" * 40, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {"synthetic": "1" * 64}}
        self.pins = {name: {"reference": name + ".json", "sha256": sha}
                     for name, sha in runner._PINS.items()}
        self.sources = self.enterContext(patch.object(runner, "_sources", side_effect=lambda *a, **kw:
            (self.panel, deepcopy(self.pins), deepcopy(self.source), deepcopy(self.baseline))))
        self.packet_dir = self.root / "packet"
        runner.prepare(self.db, self.packet_dir, intake_path=self.root / "intake.json",
                       panel_path=self.root / "panel.json", candidate_path=self.root / "candidate.json",
                       compatibility_path=self.root / "compatibility.json",
                       historical_path=self.root / "historical.json", accepted_commit="1" * 40,
                       gateway_policies=dict(runner._ROUTE), transport_security=runner._TRANSPORT)
        self.packet_path = self.packet_dir / "manifest.json"
        self.authorization = self.root / "authorization.json"
        runner.bind_authorization(self.packet_path,
                                  "https://github.com/cinic0101/grepbit/issues/58#issuecomment-123", self.authorization)
        self.sent = []
        self.serial = 0

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    async def run_candidate(self, handler=None, *, packet_path=None, authorization_path=None, commit=None,
                            policies=None, output=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json={
                "model": GEMMA_12B.model_alias,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": '{"outcome":"declined"}',
                                         "reasoning_content": "PRIVATE_REASONING_CANARY"}}]})
        client = GatewayClient(GatewayConfig("http://synthetic-p311.invalid/v1", "synthetic-key",
                                             GEMMA_12B.model_alias, expected_model=GEMMA_12B),
                               transport=httpx.MockTransport(respond))
        with patch.object(GatewayConfig, "from_env", return_value=client.config) as config, \
             patch.object(self.runner, "GatewayClient", return_value=client):
            result = await self.runner.run_live(
                self.db, output or self.output(), packet_path=packet_path or self.packet_path,
                authorization_path=authorization_path or self.authorization,
                accepted_commit=commit or "1" * 40, env_file=self.root / "unused-synthetic.env",
                gateway_policies=policies or dict(self.runner._ROUTE))
        return result, config

    def test_packet_identity_and_exclusive_binding(self):
        packet = p3_assets.read_asset(self.packet_path)
        self.assertEqual(packet["candidate"], p3_candidate_model.identity())
        self.assertFalse(packet["promotion_eligible"])
        self.assertEqual(packet["order"], [case.case_id for case in self.cases])
        self.assertEqual(packet["settings"]["max_client_http_attempts"], 28)
        self.assertEqual(packet["settings"]["panel_timeout_seconds"], 1800)
        self.assertNotIn("owner_authorization_reference", packet)
        self.assertEqual(self.runner._expected_model(packet), GEMMA_12B)
        self.assertEqual(p3_assets.read_asset(self.authorization)["packet_sha256"],
                         hashlib.sha256(self.packet_path.read_bytes()).hexdigest())
        with self.assertRaises(p3_assets.P3Error):
            self.runner.bind_authorization(self.packet_path,
                "https://github.com/cinic0101/grepbit/issues/58#issuecomment-124", self.authorization)
        with self.assertRaises(smoke.SmokeError):
            self.runner.prepare(self.db, self.packet_dir, intake_path=self.root / "intake.json",
                panel_path=self.root / "panel.json", candidate_path=self.root / "candidate.json",
                compatibility_path=self.root / "compatibility.json", historical_path=self.root / "historical.json",
                accepted_commit="1" * 40, gateway_policies=dict(self.runner._ROUTE),
                transport_security=self.runner._TRANSPORT)

    async def test_auth_candidate_and_route_fail_before_env(self):
        packet = p3_assets.read_asset(self.packet_path)
        for mutation in (lambda p: p["candidate"].update(model_alias="gemma-4-31b"),
                         lambda p: p.update(candidate={"model_alias": GEMMA_12B.model_alias}),
                         lambda p: p["order"].reverse(),
                         lambda p: p.update(promotion_eligible=True),
                         lambda p: p["historical_31b"].update(sha256="0" * 64),
                         lambda p: p["compatibility"].update(sha256="0" * 64),
                         lambda p: p["assets"]["cases"].update(sha256="0" * 64),
                         lambda p: p["assets"]["oracles"].update(sha256="0" * 64),
                         lambda p: p["assets"]["panel"].update(sha256="0" * 64),
                         lambda p: p.update(database_sha256="0" * 64),
                         lambda p: p["allocation_policy"].update(sha256="0" * 64),
                         lambda p: p["source_identity"]["files_sha256"].update(synthetic="0" * 64)):
            altered = deepcopy(packet)
            mutation(altered)
            path = self.root / f"bad-{self.serial}.json"
            self.serial += 1
            path.write_text(json.dumps(altered))
            with patch.object(GatewayConfig, "from_env", side_effect=AssertionError("env")) as env:
                with self.assertRaises((p3_assets.P3Error, ValueError)):
                    await self.runner.run_live(self.db, self.output(), packet_path=path,
                        authorization_path=self.authorization, accepted_commit="1" * 40,
                        env_file=self.root / "unused.env", gateway_policies=dict(self.runner._ROUTE))
                env.assert_not_called()
        with patch.object(GatewayConfig, "from_env", side_effect=AssertionError("env")) as env:
            with self.assertRaises(p3_assets.P3Error):
                await self.runner.run_live(self.db, self.output(), packet_path=self.packet_path,
                    authorization_path=self.authorization, accepted_commit="1" * 40,
                    env_file=self.root / "unused.env", gateway_policies={**self.runner._ROUTE, "cache": "enabled"})
            env.assert_not_called()

    async def test_missing_or_malformed_owner_binding_never_loads_env(self):
        original = self.authorization.read_bytes()
        for value in (None, {"version": self.runner.AUTHORIZATION_VERSION, "packet_sha256": "0" * 64,
                              "owner_authorization_reference": "https://github.com/cinic0101/grepbit/issues/58#issuecomment-123"},
                      {"version": self.runner.AUTHORIZATION_VERSION,
                       "packet_sha256": hashlib.sha256(self.packet_path.read_bytes()).hexdigest(),
                       "owner_authorization_reference": "https://github.com/cinic0101/grepbit/issues/56#issuecomment-123"}):
            if value is None:
                self.authorization.unlink()
            else:
                self.authorization.write_text(json.dumps(value))
            with patch.object(GatewayConfig, "from_env", side_effect=AssertionError("env")) as env:
                with self.assertRaises(p3_assets.P3Error):
                    await self.runner.run_live(self.db, self.output(), packet_path=self.packet_path,
                        authorization_path=self.authorization, accepted_commit="1" * 40,
                        env_file=self.root / "unused.env", gateway_policies=dict(self.runner._ROUTE))
                env.assert_not_called()
            self.authorization.write_bytes(original)

    def test_source_pin_drift_is_detected_by_native_source_path(self):
        for name in ("intake.json", "panel.json", "formal-cases-v2-draft.json",
                     "formal-oracles-v2-draft.json", "candidate.json", "compatibility.json", "historical.json"):
            (self.root / name).write_text("synthetic-" + name)
        pins = {key: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for key, name in (
            ("intake", "intake.json"), ("cases", "formal-cases-v2-draft.json"),
            ("oracles", "formal-oracles-v2-draft.json"), ("panel", "panel.json"))}
        original_pin = self.runner._pin

        def candidate_pin(path, expected):
            if path == self.root / "candidate.json":
                return {"reference": path.name, "sha256": expected}
            return original_pin(path, expected)

        with patch.object(self.runner, "_PINS", pins), \
             patch.object(self.runner, "_DB_SHA", smoke._fixture_identity(self.db)), \
             patch.object(self.runner, "_COMPAT_SHA", hashlib.sha256((self.root / "compatibility.json").read_bytes()).hexdigest()), \
             patch.object(self.runner, "_BASELINE_SHA", hashlib.sha256((self.root / "historical.json").read_bytes()).hexdigest()), \
             patch.object(self.runner, "_pin", side_effect=candidate_pin), \
             patch.object(p3_candidate_model, "load_identity", return_value=GEMMA_12B), \
             patch.object(self.runner.admission, "_policy_materials", return_value=(self.panel, {})), \
             patch.object(self.runner.evaluator, "_source_identity", return_value=self.source), \
             patch.object(self.runner.candidate_probe, "_checkout"), \
             patch.object(self.runner.candidate_probe, "read_report", return_value={
                 "compatibility_passed": True, "candidate": p3_candidate_model.identity()}), \
             patch.object(self.runner.formal, "read_report", return_value={}), \
             patch.object(self.runner, "_baseline_projection", return_value=self.baseline):
            # Call the undecorated implementation through a separate function
            # reference; no accepted panel or live packet is built.
            def inspect():
                return SOURCE_IMPL(self.db, intake_path=self.root / "intake.json",
                    panel_path=self.root / "panel.json", candidate_path=self.root / "candidate.json",
                    compatibility_path=self.root / "compatibility.json", historical_path=self.root / "historical.json",
                    accepted_commit="1" * 40)
            self.assertEqual(inspect()[1]["cases"]["sha256"], pins["cases"])
            for name in ("intake.json", "panel.json", "formal-cases-v2-draft.json",
                         "formal-oracles-v2-draft.json", "compatibility.json", "historical.json"):
                path = self.root / name
                before = path.read_bytes()
                path.write_bytes(before + b"drift")
                with self.assertRaises(p3_assets.P3Error):
                    inspect()
                path.write_bytes(before)

    async def test_one_mocked_28_input_execution_is_nonpromoting_and_archived(self):
        output = self.output()
        report, config = await self.run_candidate(output=output)
        config.assert_called_once_with(env_file=self.root / "unused-synthetic.env", expected_model=GEMMA_12B)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 28)
        self.assertEqual(report["runtime_invocations"], 28)
        self.assertEqual(len(self.sent), 28)
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["summary"]["promotion_result"], "not_applicable")
        self.assertNotIn("promotion", report["summary"])
        self.assertEqual(sum(report["summary"]["comparison"]["category_counts"].values()), 28)
        self.assertEqual(self.runner.read_report(output / "report.json"), report)
        self.assertNotIn("PRIVATE_REASONING_CANARY", json.dumps(report))
        checkpoints = [p3_assets.read_asset(path) for path in sorted(output.glob("checkpoint-*.json"))]
        self.assertTrue(any(item["results"][0]["phase"] == "reserved"
                            and item["results"][0]["attempt_may_be_in_flight"]
                            and item["client_http_attempts"] == 0 for item in checkpoints))
        self.assertTrue(any(item["results"][0]["phase"] == "invoked"
                            and item["results"][0]["attempt_may_be_in_flight"]
                            and item["client_http_attempts"] == 0 for item in checkpoints))
        by_question = {}
        for request in self.sent:
            body = json.loads(request.content)
            self.assertEqual(body["model"], GEMMA_12B.model_alias)
            self.assertNotIn("owner_authorization_reference", json.dumps(body))
            serialized = json.dumps(body)
            for case in self.cases:
                self.assertNotIn(case.case_id, serialized)
                self.assertNotIn(case.family_id, serialized)
            self.assertNotIn("PRIVATE_REASONING_CANARY", serialized)
            self.assertNotIn("synthetic-key", serialized)
            by_question.setdefault(body["messages"][-1]["content"], set()).add(bytes(request.content))
        self.assertEqual(len(by_question), 3)
        self.assertTrue(all(len(bodies) == 1 for bodies in by_question.values()))
        with self.assertRaises(smoke.SmokeError):
            await self.run_candidate(output=output)
        with self.assertRaises(p3_assets.P3Error):
            p3_formal_run.read_report(output / "report.json")
        with self.assertRaises(p3_assets.P3Error):
            p3_stability_run.read_report(output / "report.json")
        with patch.object(self.runner, "_sources", side_effect=AssertionError("No source in archive")), \
             patch.object(GatewayConfig, "from_env", side_effect=AssertionError("No env in archive")), \
             patch.object(smoke, "_fixture_identity", side_effect=AssertionError("No DB in archive")):
            self.assertEqual(self.runner.read_report(output / "report.json"), report)

    async def test_31b_returned_model_does_not_fall_back_or_retry(self):
        output = self.output()
        report, _ = await self.run_candidate(output=output, handler=lambda request: httpx.Response(200, json={
            "model": "gemma-4-31b", "choices": [{"index": 0, "finish_reason": "stop",
                                                   "message": {"role": "assistant", "content": '{"outcome":"declined"}'}}]}))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["summary"]["promotion_eligible"])

    async def test_actual_mocked_28_of_28_correct_still_cannot_promote(self):
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        scripted = p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES, exposed)
        by_oracle = {case.oracle_id: action for case, action in zip(exposed.cases, scripted)}

        def respond(request):
            case = self.cases[len(self.sent) - 1]
            return httpx.Response(200, json={"model": GEMMA_12B.model_alias,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                    "content": json.dumps(by_oracle[case.oracle_id])}}]})

        output = self.output()
        report, _ = await self.run_candidate(handler=respond, output=output)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(sum(row["correct"] for row in report["summary"]["per_input"]), 28)
        self.assertFalse(report["promotion_eligible"])
        self.assertFalse(report["summary"]["promotion_eligible"])
        self.assertEqual(report["summary"]["promotion_result"], "not_applicable")
        self.assertNotIn("promotion", report["summary"])
        self.assertEqual(self.runner.read_report(output / "report.json"), report)

    async def test_report_tamper_cannot_create_promotion(self):
        output = self.output()
        await self.run_candidate(output=output)
        path = output / "report.json"
        original = path.read_bytes()
        tampered = json.loads(original)
        tampered["promotion_eligible"] = True
        path.write_text(json.dumps(tampered))
        with self.assertRaises(p3_assets.P3Error):
            self.runner.read_report(path)
        path.write_bytes(original)
        tampered = json.loads(original)
        tampered["summary"]["promotion_result"] = "passed"
        path.write_text(json.dumps(tampered))
        with self.assertRaises(p3_assets.P3Error):
            self.runner.read_report(path)

    def test_comparison_taxonomy_keeps_operational_unassessed(self):
        baseline = self.baseline
        results = [{"case_id": row["case_id"], "family_id": row["family_id"], "status": "completed",
                    "outcome": row["outcome"], "actual_action": row["actual_action"],
                    "checked_wrong": False} for row in baseline["inputs"]]
        scored = {"per_input": [{"case_id": row["case_id"], "correct": row["correct"]}
                                for row in baseline["inputs"]],
                  "per_family": {key: {"family_all_variants_correct": value}
                                 for key, value in baseline["family_correct"].items()},
                  "checked_wrong_count": 0}
        first, second, third = (next(i for i, row in enumerate(results) if row["case_id"] == case)
                                for case in list(self.runner._KNOWN_FAILURES))
        scored["per_input"][first]["correct"] = True
        scored["per_input"][second]["correct"] = False
        results[second]["outcome"] = "wrong_action"
        results[third].update(status="not_run", outcome="not_run", actual_action=None)
        result = self.runner._comparison(baseline, results, scored)
        self.assertEqual(result["known_failures_fixed"], 1)
        self.assertEqual(result["category_counts"]["UNASSESSED_OPERATIONAL"], 1)
        self.assertEqual(result["not_run_count"], 1)
        self.assertEqual(result["new_regressions"], 0)

    def test_all_six_comparison_classes_and_denominators(self):
        baseline = self.baseline
        results = [{"case_id": row["case_id"], "family_id": row["family_id"], "status": "completed",
                    "outcome": row["outcome"], "actual_action": row["actual_action"],
                    "checked_wrong": False} for row in baseline["inputs"]]
        scored = {"per_input": [{"case_id": row["case_id"], "correct": row["correct"]}
                                for row in baseline["inputs"]],
                  "per_family": {key: {"family_all_variants_correct": value}
                                 for key, value in baseline["family_correct"].items()},
                  "checked_wrong_count": 1}
        failed = [i for i, row in enumerate(baseline["inputs"]) if not row["correct"]]
        formerly_correct = [i for i, row in enumerate(baseline["inputs"]) if row["correct"]]
        scored["per_input"][failed[0]]["correct"] = True
        results[failed[0]].update(outcome="complete_correct", actual_action="answer")
        results[failed[2]].update(outcome="wrong_action", actual_action="decline")
        scored["per_input"][formerly_correct[0]]["correct"] = False
        results[formerly_correct[0]].update(outcome="wrong_request")
        results[formerly_correct[1]].update(status="in_progress", outcome=None, actual_action=None,
                                            operational_error="transport_error")
        scored["per_input"][formerly_correct[1]]["correct"] = False
        result = self.runner._comparison(baseline, results, scored)
        counts = result["category_counts"]
        self.assertEqual(counts["FIXED_KNOWN_FAILURE"], 1)
        self.assertEqual(counts["UNCHANGED_FAILURE"], 1)
        self.assertEqual(counts["OUTCOME_CHANGED_OTHER"], 1)
        self.assertEqual(counts["NEW_REGRESSION"], 1)
        self.assertEqual(counts["UNASSESSED_OPERATIONAL"], 1)
        self.assertEqual(counts["UNCHANGED_CORRECT"], 23)
        self.assertEqual((result["known_failures_fixed"], result["known_failures_total"]), (1, 3))
        self.assertEqual((result["new_regressions"], result["previously_correct_total"]), (1, 25))
        self.assertEqual(result["checked_wrong_delta"], 1)
        self.assertEqual(len(result["family_delta"]), 14)


if __name__ == "__main__":
    unittest.main()
