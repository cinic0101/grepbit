"""Dev regression runner rulers (#79): synthetic metadata and MockTransport only; no live call."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit.clarification import KINDS
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import fixture, p3_admission, p3_assets, p3_eval, p3_formal_policy, p3_formal_run, p3_holdout_run
from tools import p3_candidate_regression as historical, p3_dev_regression as runner, smoke
from test_p3_admission import metadata_provenance
from test_p3_formal_policy import revised_scaffolding

SHA = "1" * 40
GRANT = "https://github.com/cinic0101/grepbit/issues/79#issuecomment-"
BASE = "http://synthetic-dev-regression.invalid/v1"
KEY = "synthetic-dev-regression-key"


def envelope(content='{"outcome":"declined"}'):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": content,
                                                     "reasoning_content": "PRIVATE_REASONING_CANARY"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


class DevRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            mocked = self.enterContext(patch(target, side_effect=AssertionError("Real network/env forbidden")))
            self.addCleanup(mocked.assert_not_called)
        tmp = tempfile.TemporaryDirectory(prefix="p382-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        seeds = {branch: next(case for case in exposed.cases if case.expected_branch == branch)
                 for branch in p3_assets.BRANCHES}
        self.cases = tuple(replace(seeds[row["expected_branch"]], **{
            key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort",
                                     "exposure", "semantic_signature", "must_pass", "observational")},
            provenance=p3_assets.Provenance.from_mapping(metadata_provenance(row["exposure"]), row["exposure"]))
            for row in revised_scaffolding())
        self.panel = p3_assets.Panel("SyntheticDevRegressionOnly", "formal", self.cases,
                                     tuple(exposed.oracle_for(case) for case in seeds.values()),
                                     self.root / "panel.json", self.root / "cases.json", self.root / "oracles.json")
        scripted = p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES, exposed)
        self.by_oracle = {case.oracle_id: action for case, action in zip(exposed.cases, scripted)}
        self.enterContext(patch.object(historical, "_ORDER", tuple(case.case_id for case in self.cases)))
        by_family = {}
        for case in self.cases:
            by_family.setdefault(case.family_id, []).append(case)
        groups = [group for group in by_family.values() if len(group) >= 2]
        self.failures = {groups[0][0].case_id, groups[0][1].case_id, groups[1][0].case_id}
        self.enterContext(patch.object(historical, "_KNOWN_FAILURES", frozenset(self.failures)))
        rows = []
        for case in self.cases:
            failed = case.case_id in self.failures
            rows.append({"case_id": case.case_id, "family_id": case.family_id, "status": "completed",
                         "outcome": "false_clarification" if failed else {
                             "answer": "complete_correct", "clarify": "correct_clarification",
                             "decline": "correct_decline"}[case.expected_branch],
                         "actual_action": "clarify" if failed else case.expected_branch,
                         "checked_wrong": False, "correct": not failed})
        self.baseline = {"inputs": rows, "family_correct": {
            key: not any(case.case_id in self.failures for case in group) for key, group in by_family.items()}}
        self.source = {"git_commit": SHA, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {"synthetic": "1" * 64}}
        self.pins = {name: {"reference": name + ".json", "sha256": sha} for name, sha in historical._PINS.items()}
        self.enterContext(patch.object(runner, "_sources", side_effect=lambda *a, **kw: (
            self.panel, deepcopy(self.pins), deepcopy(self.source), deepcopy(self.baseline),
            p3_admission.FROZEN_CANDIDATE)))
        self.packet_dir = self.root / "packet"
        runner.prepare(self.database, self.packet_dir, intake_path=self.root / "intake.json",
                       panel_path=self.root / "panel.json", historical_path=self.root / "historical.json",
                       accepted_commit=SHA, gateway_policies=dict(runner.ROUTE),
                       transport_security="unencrypted_http")
        self.packet_path = self.packet_dir / "manifest.json"
        self.packet = json.loads(self.packet_path.read_text())
        self.sent, self.serial = [], 0

    def grant(self):
        self.serial += 1
        return f"{GRANT}{self.serial}"

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    def bind(self, output):
        path = self.root / f"authorization-{output.name}.json"
        runner.bind_authorization(self.packet_path, self.grant(), path, output)
        return path

    def client(self, handler=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=envelope())

        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    def scripted(self):
        def respond(request):
            case = self.cases[len(self.sent) - 1]
            return httpx.Response(200, json=envelope(json.dumps(self.by_oracle[case.oracle_id])))

        return self.client(respond)

    async def run_mock(self, output, authorization, *, client=None, policies=None, commit=SHA):
        with patch.object(runner, "GatewayConfig") as config_cls, \
                patch.object(runner, "GatewayClient", return_value=client or self.client()) as factory:
            config_cls.from_env.return_value = GatewayConfig(BASE, KEY)
            report = await runner.run_live(
                self.database, output, packet_path=self.packet_path, authorization_path=authorization,
                accepted_commit=commit, env_file=self.root / "unused.env",
                gateway_policies=policies or dict(runner.ROUTE))
        return report, config_cls

    def test_packet_is_an_observed_dev_regression_bound_to_the_formal_allocation(self):
        packet = self.packet
        self.assertEqual(packet["version"], "p3-dev-regression-packet-v1")
        self.assertEqual(packet["purpose"], runner.PURPOSE)
        self.assertEqual(packet["evidence_class"], "observed_regression")
        self.assertFalse(packet["promotion_eligible"])
        self.assertEqual(packet["promotion_result"], "not_applicable")
        self.assertEqual(packet["panel_kind"], "dev_regression")
        self.assertEqual(packet["allocation_policy"], p3_formal_policy.identity(p3_formal_policy.V2))
        self.assertEqual(len(packet["inputs"]), 28)
        self.assertEqual(packet["settings"]["max_client_http_attempts"], 28)
        self.assertEqual(packet["settings"]["call_timeout_seconds"], 60.0)
        self.assertEqual(packet["candidate"], p3_holdout_run.candidate_identity(SHA, p3_admission.FROZEN_CANDIDATE))
        self.assertEqual(packet["observation_fields"], ["clarification_kind", "clarification_choice_count"])
        self.assertEqual(packet["gateway_policy"]["retries"], "disabled")
        self.assertEqual(packet["historical_31b"]["sha256"], historical._BASELINE_SHA)
        self.assertNotIn("owner_authorization_reference", packet)
        self.assertIsNone(runner._expected_model(packet))
        for field, bad in (("promotion_eligible", True), ("promotion_result", "passed"),
                           ("panel_kind", "formal"), ("evidence_class", "fresh_holdout_observation"),
                           ("allocation_policy", p3_formal_policy.identity(p3_formal_policy.HOLDOUT_A)),
                           ("candidate", {**packet["candidate"], "accepted_commit": "2" * 40}),
                           ("authoring_baseline_sha", "0" * 40),
                           ("observation_fields", ["clarification_kind"]),
                           ("gateway_policy", {**packet["gateway_policy"], "retries": "enabled"}),
                           ("historical_31b", {**packet["historical_31b"], "sha256": "0" * 64}),
                           ("order", list(reversed(packet["order"])))):
            with self.subTest(field=field):
                changed = deepcopy(packet)
                changed[field] = bad
                with self.assertRaises(p3_assets.P3Error):
                    runner._packet_contract(changed)
        with self.assertRaises(p3_assets.P3Error):
            runner.prepare(self.database, self.root / "retries", intake_path=self.root / "intake.json",
                           panel_path=self.root / "panel.json", historical_path=self.root / "historical.json",
                           accepted_commit=SHA, gateway_policies={**runner.ROUTE, "retries": "enabled"},
                           transport_security="unencrypted_http")

    async def test_authorization_binds_the_grant_and_one_slot_before_env(self):
        output = self.output()
        authorization = self.bind(output)
        value = json.loads(authorization.read_text())
        self.assertEqual(value["version"], "p3-dev-regression-authorization-v1")
        self.assertEqual(value["packet_sha256"], hashlib.sha256(self.packet_path.read_bytes()).hexdigest())
        self.assertEqual(value["run_slot"], output.relative_to(p3_eval.ROOT).as_posix())
        for reference in ("https://github.com/cinic0101/grepbit/issues/58#issuecomment-123",
                          "https://github.com/cinic0101/grepbit/issues/79", "not-a-reference"):
            with self.assertRaises(p3_assets.P3Error):
                runner.bind_authorization(self.packet_path, reference, self.root / "bad.json", output)
        # The same envelope cannot run into another slot, and a foreign envelope never loads env.
        with patch.object(runner, "GatewayConfig") as config_cls:
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, self.output(), packet_path=self.packet_path,
                                      authorization_path=authorization, accepted_commit=SHA,
                                      env_file=self.root / "unused.env", gateway_policies=dict(runner.ROUTE))
            holdout_envelope = self.root / "holdout-envelope.json"
            holdout_envelope.write_text(json.dumps({**value, "version": "p3-holdout-live-authorization-v1"}))
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, output, packet_path=self.packet_path,
                                      authorization_path=holdout_envelope, accepted_commit=SHA,
                                      env_file=self.root / "unused.env", gateway_policies=dict(runner.ROUTE))
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, output, packet_path=self.packet_path,
                                      authorization_path=authorization, accepted_commit=SHA,
                                      env_file=self.root / "unused.env",
                                      gateway_policies={**runner.ROUTE, "cache": "enabled"})
            config_cls.from_env.assert_not_called()

    async def test_mocked_run_records_closed_clarification_observations_and_the_baseline_delta(self):
        output = self.output()
        authorization = self.bind(output)
        report, config_cls = await self.run_mock(output, authorization, client=self.scripted())
        config_cls.from_env.assert_called_once_with(env_file=self.root / "unused.env")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 28)
        self.assertEqual(len(self.sent), 28)
        self.assertFalse(report["promotion_eligible"])
        summary = report["summary"]
        self.assertEqual(summary["panel_kind"], "dev_regression")
        self.assertNotIn("promotion", summary)
        self.assertEqual(sum(row["correct"] for row in summary["per_input"]), 28)
        comparison = summary["comparison"]
        self.assertEqual(comparison["known_failures_fixed"], 3)
        self.assertEqual(comparison["new_regressions"], 0)
        self.assertEqual(comparison["category_counts"]["UNCHANGED_CORRECT"], 25)
        clarify_rows = [row for row in report["results"] if row["actual_action"] == "clarify"]
        self.assertTrue(clarify_rows)
        for row in report["results"]:
            if row["actual_action"] == "clarify":
                self.assertIn(row["clarification_kind"], KINDS)
                self.assertGreaterEqual(row["clarification_choice_count"], 2)
            else:
                self.assertIsNone(row["clarification_kind"])
                self.assertIsNone(row["clarification_choice_count"])
        observations = summary["observations"]
        self.assertEqual(observations["clarify_actions"], len(clarify_rows))
        self.assertEqual(sum(observations["kinds"].values()), len(clarify_rows))
        self.assertEqual(sum(observations["false_clarification_kinds"].values()), 0)
        serialized = json.dumps(report)
        self.assertNotIn("PRIVATE_REASONING_CANARY", serialized)
        self.assertNotIn(KEY, serialized)
        for case in self.cases:
            self.assertNotIn(case.question, serialized)
        self.assertEqual(runner.read_report(output / "report.json"), report)
        for reader in (p3_formal_run.read_report, p3_holdout_run.read_report, historical.read_report):
            with self.assertRaises(p3_assets.P3Error):
                reader(output / "report.json")
        with patch.object(runner, "_sources", side_effect=AssertionError("No source in archive")), \
                patch.object(smoke, "_fixture_identity", side_effect=AssertionError("No DB in archive")):
            self.assertEqual(runner.read_report(output / "report.json"), report)
        # The archive cannot gain text, a free kind, an out-of-range count or a promotion.
        path = output / "report.json"
        original = path.read_bytes()
        index = next(i for i, row in enumerate(report["results"]) if row["actual_action"] == "clarify")
        answer_index = next(i for i, row in enumerate(report["results"]) if row["actual_action"] == "answer")
        for mutate in (lambda r: r["results"][index].update(clarification_kind="free_text"),
                       lambda r: r["results"][index].update(clarification_kind=None),
                       lambda r: r["results"][index].update(clarification_choice_count=9),
                       lambda r: r["results"][answer_index].update(clarification_kind="count_basis"),
                       lambda r: r["results"][index].update(clarification_question="leaked"),
                       lambda r: r.update(promotion_eligible=True),
                       lambda r: r["summary"].update(promotion_result="passed"),
                       lambda r: r["summary"]["observations"].update(clarify_actions=0)):
            tampered = json.loads(original)
            mutate(tampered)
            path.write_text(json.dumps(tampered))
            with self.assertRaises(p3_assets.P3Error):
                runner.read_report(path)
        path.write_bytes(original)
        with self.assertRaises(smoke.SmokeError):
            await self.run_mock(output, authorization, client=self.scripted())

    async def test_unchanged_decline_only_run_reports_false_refusals_without_promotion(self):
        output = self.output()
        report, _ = await self.run_mock(output, self.bind(output))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["observations"]["clarify_actions"], 0)
        self.assertTrue(all(row["clarification_kind"] is None for row in report["results"]))
        counts = report["summary"]["comparison"]["category_counts"]
        self.assertEqual(sum(counts.values()), 28)
        self.assertGreater(counts["NEW_REGRESSION"], 0)
        self.assertFalse(report["summary"]["promotion_eligible"])
        self.assertEqual(runner.read_report(output / "report.json"), report)

    async def test_wrong_commit_or_unbound_slot_stops_before_env(self):
        output = self.output()
        authorization = self.bind(output)
        with patch.object(runner, "GatewayConfig") as config_cls:
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, output, packet_path=self.packet_path,
                                      authorization_path=authorization, accepted_commit="2" * 40,
                                      env_file=self.root / "unused.env", gateway_policies=dict(runner.ROUTE))
            config_cls.from_env.assert_not_called()

    def test_shared_loop_only_observes_for_policies_that_ask(self):
        self.assertTrue(hasattr(runner._LiveEvidence, "observe_result"))
        self.assertFalse(hasattr(p3_holdout_run._LiveEvidence, "observe_result"))
        self.assertEqual(runner._LiveEvidence.observe_result(object()),
                         {"clarification_kind": None, "clarification_choice_count": None})

    def test_cli_arguments_are_closed(self):
        with patch("sys.stderr"):
            self.assertEqual(runner.main(["--prepare", "--report-path", "x"]), 2)
            self.assertEqual(runner.main(["--report", "--report-path", str(self.root / "missing.json"),
                                          "--db", str(self.database)]), 2)
            self.assertEqual(runner.main(["--live", "--packet", str(self.packet_path), "--db", str(self.database),
                                          "--accepted-commit", SHA, "--env-file", str(self.root / "unused.env"),
                                          "--gateway-retries", "disabled", "--gateway-fallback", "disabled",
                                          "--gateway-cache", "disabled", "--output-dir", str(self.output())]), 2)
            self.assertEqual(runner.main(["--bind-authorization", "--packet", str(self.packet_path),
                                          "--owner-authorization-reference", self.grant(),
                                          "--output", str(self.root / "cli-envelope.json")]), 2)


if __name__ == "__main__":
    unittest.main()
