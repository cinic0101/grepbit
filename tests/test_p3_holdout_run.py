"""Holdout runner rulers (#79): synthetic metadata and exposed development objects only; no live call."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import fixture, p3_admission, p3_assets, p3_eval, p3_formal_policy, p3_holdout_run as holdout
from tools import recipe_smoke, smoke
from test_p3_admission import abstract_reviews, metadata_provenance
from test_p3_holdout_policy import holdout_scaffolding

SHA = "1" * 40
GRANT = "https://github.com/cinic0101/grepbit/issues/79#issuecomment-"
POLICIES = {"retries": "disabled", "fallback": "disabled", "cache": "disabled"}
BASE = "http://synthetic-holdout-test.invalid/v1"
KEY = "synthetic-holdout-secret-key"


def envelope(content='{"outcome":"declined"}'):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


class HoldoutRunTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            mocked = self.enterContext(patch(target, side_effect=AssertionError("Real network/env forbidden")))
            self.addCleanup(mocked.assert_not_called)
        tmp = tempfile.TemporaryDirectory(prefix="p379-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.db_hash = smoke._fixture_identity(self.database)
        self.enterContext(patch.object(smoke, "_fixture_identity", return_value=self.db_hash))
        self.enterContext(patch.object(smoke, "_stable_database", return_value=self.db_hash))
        self.source = {"git_commit": SHA, "branch": "dev", "worktree_dirty": False, "files_sha256": {},
                       "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(self.source)))
        from p3_historical_source import historical_candidate
        self.enterContext(patch.object(p3_admission, "candidate_identity", return_value=historical_candidate()))
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        seeds = {branch: next(c for c in exposed.cases if c.expected_branch == branch) for branch in p3_assets.BRANCHES}
        self.cases = tuple(replace(seeds[row["expected_branch"]], **{
            key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort", "exposure",
                                     "semantic_signature", "must_pass", "observational")},
            provenance=p3_assets.Provenance.from_mapping(metadata_provenance("frozen_fresh"), "frozen_fresh"))
            for row in holdout_scaffolding())
        self.oracles = tuple(exposed.oracle_for(seed) for seed in seeds.values())
        for filename in ("development-cases-v1.json", "development-oracles-v1.json"):
            (self.root / filename).write_bytes((p3_eval.DEFAULT_PANEL.parent / filename).read_bytes())
        self.panel_path = self.root / "synthetic-holdout-panel.json"
        self.panel_path.write_text(json.dumps({
            "version": "p3-panel-v1", "panel_id": "SyntheticHoldoutNotAdmitted", "kind": "formal",
            "cases": "development-cases-v1.json", "oracles": "development-oracles-v1.json",
            "order": [c.case_id for c in self.cases]}, indent=2) + "\n")
        self.intake_path = self.root / "synthetic-intake.json"
        self.intake_path.write_text('{"synthetic_metadata_only": true}\n')
        panel = p3_assets.Panel("SyntheticHoldoutNotAdmitted", "formal", self.cases, self.oracles, self.panel_path,
                                self.root / "development-cases-v1.json", self.root / "development-oracles-v1.json")
        review = {"state": "novelty_reviewed", "owner_review_reference": GRANT + "1",
                  "families": abstract_reviews(panel.inputs()),
                  **{name: p3_eval._pin(self.root / filename) for name, filename in (
                      ("cases", "development-cases-v1.json"), ("oracles", "development-oracles-v1.json"))}}
        self.enterContext(patch.object(p3_admission, "_intake", side_effect=lambda path: (
            deepcopy(review), self.cases, self.oracles, {"review_assertions_complete": True})))
        self.frozen = self.root / "synthetic-freeze"
        p3_admission.freeze_panel(self.database, self.intake_path, self.panel_path, self.frozen,
                                 accepted_commit=SHA, allocation_policy=p3_formal_policy.HOLDOUT_A)
        self.prepared = self.root / "synthetic-offline-prepared"
        p3_eval.prepare(self.database, self.prepared, panel_path=self.frozen / self.panel_path.name,
                        accepted_commit=SHA, formal_freeze=self.frozen / "report.json")
        self.packet_dir = self.root / "packet"
        holdout.prepare(self.database, self.packet_dir, freeze_path=self.frozen / "report.json",
                        preparation_path=self.prepared / "manifest.json", accepted_commit=SHA,
                        gateway_policies=POLICIES, transport_security="unencrypted_http")
        self.packet_path = self.packet_dir / "manifest.json"
        self.packet = json.loads(self.packet_path.read_text())
        self.sent, self.serial = [], 0

    def grant(self):
        self.serial += 1
        return f"{GRANT}{self.serial}"

    def bind(self, output):
        path = self.root / f"authorization-{output.name}.json"
        holdout.bind_authorization(self.packet_path, self.grant(), path, output)
        return path

    def client(self, handler=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=envelope())

        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def run_mock(self, output, authorization, *, client=None, policies=None):
        with patch.object(holdout, "GatewayConfig") as config_cls, \
                patch.object(holdout, "GatewayClient", return_value=client or self.client()) as factory:
            config_cls.from_env.return_value = GatewayConfig(BASE, KEY)
            self.config_cls, self.factory = config_cls, factory
            report = await holdout.run_live(
                self.database, output, packet_path=self.packet_path, authorization_path=authorization,
                accepted_commit=SHA, env_file=self.root / "unused.env", gateway_policies=policies or dict(POLICIES))
        return report, factory

    def test_packet_is_a_holdout_observation_bound_to_the_holdout_allocation(self):
        self.assertEqual(self.packet["version"], "p3-holdout-live-packet-v1")
        self.assertEqual(self.packet["purpose"], holdout.PURPOSE)
        self.assertEqual(self.packet["evidence_class"], "fresh_holdout_observation")
        self.assertFalse(self.packet["promotion_eligible"])
        self.assertEqual(self.packet["panel_kind"], "holdout")
        self.assertEqual(self.packet["allocation_policy"], p3_formal_policy.identity(p3_formal_policy.HOLDOUT_A))
        self.assertEqual(len(self.packet["inputs"]), 18)
        self.assertEqual(self.packet["settings"]["max_client_http_attempts"], 18)
        self.assertEqual(self.packet["settings"]["call_timeout_seconds"], 60.0)
        self.assertTrue(all(row["exposure"] == "frozen_fresh" for row in self.packet["inputs"]))
        for field, bad in (("promotion_eligible", True), ("panel_kind", "formal"),
                           ("allocation_policy", p3_formal_policy.identity(p3_formal_policy.V2)),
                           ("evidence_class", "formal_quality")):
            with self.subTest(field=field):
                changed = deepcopy(self.packet)
                changed[field] = bad
                with self.assertRaises(p3_assets.P3Error):
                    holdout._packet_contract(changed)

    def test_v2_formal_freeze_is_not_a_holdout(self):
        frozen = self.root / "v2-freeze"
        with self.assertRaises(p3_assets.P3Error):
            p3_admission.freeze_panel(self.database, self.intake_path, self.panel_path, frozen,
                                     accepted_commit=SHA, allocation_policy=p3_formal_policy.V2)

    async def test_one_observation_per_slot_with_grant_bound_envelope_and_readback(self):
        output = self.root / "run-1"
        authorization = self.bind(output)
        envelope_value = json.loads(authorization.read_text())
        self.assertEqual(envelope_value["run_slot"], holdout._run_slot(output))
        self.assertTrue(envelope_value["owner_authorization_reference"].startswith(GRANT))
        report, factory = await self.run_mock(output, authorization)
        self.assertEqual(report["status"], "complete")
        self.assertEqual((report["client_http_attempts"], report["runtime_invocations"], len(self.sent)), (18, 18, 18))
        self.assertEqual(report["evidence_class"], "fresh_holdout_observation")
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["summary"]["panel_kind"], "holdout")
        self.assertFalse(report["summary"]["promotion"]["eligible"])
        self.assertEqual(report["summary"]["outcomes"].get("correct_decline"), 6)
        self.assertNotIn(KEY, json.dumps(report))
        self.assertNotIn("synthetic-holdout-test.invalid", json.dumps(report))
        self.assertEqual(holdout.read_report(output / "report.json"), report)
        # The same envelope cannot start a second observation anywhere.
        with self.assertRaisesRegex(smoke.SmokeError, "artifact_conflict"):
            await self.run_mock(output, authorization)
        other = self.root / "run-other"
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_manifest"):
            await self.run_mock(other, authorization)
        self.assertFalse(other.exists())
        self.config_cls.from_env.assert_not_called()
        self.factory.assert_not_called()
        self.assertEqual(len(self.sent), 18)
        moved = self.root / "moved"
        output.rename(moved)
        with self.assertRaises(p3_assets.P3Error):
            holdout.read_report(moved / "report.json")

    async def test_foreign_grant_reference_or_policy_drift_stops_before_env(self):
        output = self.root / "run-foreign"
        authorization = self.root / "foreign.json"
        with self.assertRaises(p3_assets.P3Error):
            holdout.bind_authorization(self.packet_path,
                                       "https://github.com/cinic0101/grepbit/issues/49#issuecomment-1",
                                       authorization, output)
        self.assertFalse(authorization.exists())
        bound = self.bind(output)
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_configuration"):
            await self.run_mock(output, bound, policies={**POLICIES, "retries": "enabled"})
        self.assertEqual(self.sent, [])
        self.config_cls.from_env.assert_not_called()
        self.factory.assert_not_called()
        for field, bad in (("gateway_policy", {**self.packet["gateway_policy"], "attestation": "tampered"}),
                           ("locations", "not-a-dict"), ("preparation_assets", {"manifest": self.packet["preparation_assets"]["manifest"]}),
                           ("assets", {**self.packet["assets"], "extra": self.packet["assets"]["panel"]})):
            with self.subTest(field=field):
                changed = deepcopy(self.packet)
                changed[field] = bad
                with self.assertRaises(p3_assets.P3Error):
                    holdout._packet_contract(changed)

    def test_cli_arguments_are_closed(self):
        self.assertEqual(holdout.main(["--report"]), 2)
        self.assertEqual(holdout.main(["--live", "--db", "x"]), 2)
        self.assertEqual(holdout.main(["--bind-authorization", "--packet", str(self.packet_path),
                                       "--owner-authorization-reference", GRANT + "9",
                                       "--output", str(self.root / "cli-auth.json")]), 2)


if __name__ == "__main__":
    unittest.main()
