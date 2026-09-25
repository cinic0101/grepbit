"""Single tiered evaluation runner rulers (#87 step 2): synthetic panels and mock transports only; no live call."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.bedrock import BedrockClient, BedrockConfig
from grepbit.clarification import KINDS
from grepbit.gateway import GEMMA_12B, GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate as runner, fixture, p3_admission, p3_assets, p3_eval
from tools import p3_dev_regression, p3_formal_run, p3_holdout_run, recipe_smoke
from test_p3_admission import abstract_reviews, metadata_provenance
from test_p3_holdout_policy import holdout_scaffolding

ROOT = p3_eval.ROOT
SHA = "1" * 40
GRANT = "https://github.com/cinic0101/grepbit/issues/87#issuecomment-"
BASE = "http://synthetic-evaluate.invalid/v1"
KEY = "synthetic-evaluate-key"
POLICY = dict(runner.ROUTE_POLICY)


def envelope(content='{"outcome":"declined"}', model_name=MODEL):
    return {"model": model_name, "choices": [{"index": 0, "finish_reason": "stop",
                                              "message": {"role": "assistant", "content": content,
                                                          "reasoning_content": "PRIVATE_REASONING_CANARY"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


def bedrock_response(content='{"outcome":"declined"}'):
    return {"output": {"message": {"role": "assistant", "content": [{"text": content}]}},
            "stopReason": "end_turn", "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}


class EvaluateRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env", "grepbit.bedrock.BedrockConfig.from_env"):
            mocked = self.enterContext(patch(target, side_effect=AssertionError("Real network/env forbidden")))
            self.addCleanup(mocked.assert_not_called)
        tmp = tempfile.TemporaryDirectory(prefix="p383-synthetic-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.relative = self.root.relative_to(ROOT).as_posix()
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.source = {"git_commit": SHA, "branch": "dev", "worktree_dirty": False, "files_sha256": {},
                       "context": recipe_model.context_identity(),
                       "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(self.source)))
        # Development panel copy (15 exposed inputs) and a holdout-shaped synthetic panel (18 fresh inputs).
        dev = ROOT / "evals/p3"
        for name in ("development-panel-v1.json", "development-cases-v1.json", "development-oracles-v1.json"):
            (self.root / name).write_bytes((dev / name).read_bytes())
        exposed = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        raw_cases = json.loads((dev / "development-cases-v1.json").read_text())
        seeds = {branch: next(case for case in raw_cases["cases"] if case["expected_branch"] == branch)
                 for branch in p3_assets.BRANCHES}
        synthetic = []
        for row in holdout_scaffolding():
            seed = deepcopy(seeds[row["expected_branch"]])
            seed.update({key: row[key] for key in ("case_id", "family_id", "language", "expected_branch", "cohort",
                                                   "exposure", "semantic_signature", "must_pass", "observational")})
            seed["provenance"] = metadata_provenance(row["exposure"])
            synthetic.append(seed)
        (self.root / "holdout-cases.json").write_text(json.dumps({"version": raw_cases["version"], "cases": synthetic}))
        raw_oracles = json.loads((dev / "development-oracles-v1.json").read_text())
        used = {seed["oracle_id"] for seed in seeds.values()}
        (self.root / "holdout-oracles.json").write_text(json.dumps({
            "version": raw_oracles["version"],
            "oracles": [oracle for oracle in raw_oracles["oracles"] if oracle["oracle_id"] in used]}))
        (self.root / "holdout-panel.json").write_text(json.dumps({
            "version": "p3-panel-v1", "panel_id": "synthetic-holdout", "kind": "formal",
            "cases": "holdout-cases.json", "oracles": "holdout-oracles.json",
            "order": [case["case_id"] for case in synthetic]}))
        (self.root / "holdout-intake.json").write_text('{"synthetic_metadata_only": true}\n')
        holdout_cases = tuple(p3_assets.Case.from_mapping(case) for case in synthetic)
        holdout_oracles = tuple(p3_assets.parse_oracle(o) for o in json.loads(
            (self.root / "holdout-oracles.json").read_text())["oracles"])
        review = {"state": "novelty_reviewed", "owner_review_reference": GRANT + "77",
                  "candidate_freeze_sha": p3_admission.FROZEN_CANDIDATE,
                  "families": abstract_reviews([case.metadata(i, "holdout-cases.json")
                                                for i, case in enumerate(holdout_cases, 1)]),
                  "cases": p3_eval._pin(self.root / "holdout-cases.json"),
                  "oracles": p3_eval._pin(self.root / "holdout-oracles.json")}
        self.enterContext(patch.object(p3_admission, "_intake", side_effect=lambda path: (
            deepcopy(review), holdout_cases, holdout_oracles, {"review_assertions_complete": True})))
        pins = {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in (
            "development-panel-v1.json", "development-cases-v1.json", "development-oracles-v1.json",
            "holdout-panel.json", "holdout-cases.json", "holdout-oracles.json", "holdout-intake.json")}
        (self.root / "holdout-freeze.json").write_text(json.dumps({
            "version": "synthetic-freeze", "owner_review_reference": GRANT + "77",
            "assets": {"panel": {"sha256": pins["holdout-panel.json"]}, "cases": {"sha256": pins["holdout-cases.json"]},
                       "oracles": {"sha256": pins["holdout-oracles.json"]}},
            "order": [case["case_id"] for case in synthetic]}))
        dev_assets = {"panel": pins["development-panel-v1.json"], "cases": pins["development-cases-v1.json"],
                      "oracles": pins["development-oracles-v1.json"]}
        self.panels = self.root / "panels.json"
        self.panels.write_text(json.dumps({"registry_version": runner.REGISTRY_VERSION, "panels": [
            {"panel_id": "synthetic-dev", "tier": "dev", "path": f"{self.relative}/development-panel-v1.json",
             "assets": dev_assets, "allocation_policy": None, "intake": None, "freeze": None, "authoring": "development",
             "note": "dev"},
            {"panel_id": "synthetic-regression", "tier": "regression", "path": f"{self.relative}/development-panel-v1.json",
             "assets": dev_assets, "allocation_policy": None, "intake": None, "freeze": None, "authoring": "historical",
             "note": "reg"},
            {"panel_id": "synthetic-holdout", "tier": "holdout", "path": f"{self.relative}/holdout-panel.json",
             "assets": {"panel": pins["holdout-panel.json"], "cases": pins["holdout-cases.json"],
                        "oracles": pins["holdout-oracles.json"]},
             "allocation_policy": "p3-holdout-a-allocation-v2",
             "intake": {"path": f"{self.relative}/holdout-intake.json", "sha256": pins["holdout-intake.json"]},
             "freeze": {"path": f"{self.relative}/holdout-freeze.json",
                        "sha256": hashlib.sha256((self.root / "holdout-freeze.json").read_bytes()).hexdigest()},
             "authoring": "independent", "note": "holdout"},
        ]}))
        self.routes = self.root / "routes.json"
        self.routes.write_text(json.dumps({"registry_version": runner.REGISTRY_VERSION, "routes": [
            {"route_id": "litellm-31b", "provider": "litellm", "model": MODEL, "region": None,
             "call_timeout_seconds": 60.0, "transport_security": "unencrypted_http", "note": ""},
            {"route_id": "litellm-12b", "provider": "litellm", "model": GEMMA_12B.model_alias, "region": None,
             "call_timeout_seconds": 60.0, "transport_security": "unencrypted_http", "note": ""},
            {"route_id": "bedrock-sonnet", "provider": "bedrock_converse", "model": "jp.anthropic.claude-sonnet-4-6",
             "region": "ap-northeast-1", "call_timeout_seconds": 300.0, "transport_security": "tls_verification_enabled",
             "note": ""},
        ]}))
        self.runs = self.root / "runs.jsonl"
        self.registries = {"panels_path": self.panels, "routes_path": self.routes, "runs_path": self.runs}
        self.candidate = registry.current()["candidate_id"]
        scripted = p3_eval.load_fake_responses(p3_eval.DEFAULT_RESPONSES, exposed)
        self.by_oracle = {case.oracle_id: action for case, action in zip(exposed.cases, scripted)}
        self.sent, self.serial = [], 0

    # ----------------------------------------------------------------- helpers
    def prepare(self, panel="synthetic-dev", route="litellm-31b", baseline=None, name=None):
        self.serial += 1
        packet_dir = self.root / (name or f"packet-{self.serial}")
        runner.prepare(self.database, packet_dir, candidate_id=self.candidate, panel_id=panel, route_id=route,
                       accepted_commit=SHA, gateway_policies=dict(POLICY), baseline_path=baseline, **self.registries)
        return packet_dir / "manifest.json"

    def bind(self, packet_path, output):
        path = self.root / f"authorization-{output.name}.json"
        self.serial += 1
        runner.bind_authorization(packet_path, f"{GRANT}{self.serial}", path, output)
        return path

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    def litellm_client(self, scripted=False, model_name=MODEL, cases=None):
        def respond(request):
            self.sent.append(request)
            if scripted:
                question = json.loads(request.content)["messages"][-1]["content"]
                case = next(case for case in cases if case.question == question)
                return httpx.Response(200, json=envelope(json.dumps(self.by_oracle[case.oracle_id]), model_name))
            return httpx.Response(200, json=envelope(model_name=model_name))

        return GatewayClient(GatewayConfig(BASE, KEY, model_name,
                                           expected_model=GEMMA_12B if model_name == GEMMA_12B.model_alias else None),
                             transport=httpx.MockTransport(respond))

    async def run_mock(self, packet_path, output, authorization, *, client=None, policies=None, route="litellm"):
        original = runner.validate_packet

        def with_registries(path, db, *, accepted_commit):
            return original(path, db, accepted_commit=accepted_commit, **self.registries)

        with patch.object(runner, "validate_packet", side_effect=with_registries):
            if route == "bedrock":
                with patch.object(runner, "client_from_env", return_value=client) as loader:
                    report = await runner.run_live(self.database, output, packet_path=packet_path,
                                                   authorization_path=authorization, accepted_commit=SHA,
                                                   env_file=self.root / "unused.env",
                                                   gateway_policies=policies or dict(POLICY))
                return report, loader
            with patch.object(runner, "GatewayConfig") as config_cls, \
                    patch.object(runner, "GatewayClient", return_value=client or self.litellm_client()) as factory:
                config_cls.from_env.return_value = (client or self.litellm_client()).config
                report = await runner.run_live(self.database, output, packet_path=packet_path,
                                               authorization_path=authorization, accepted_commit=SHA,
                                               env_file=self.root / "unused.env",
                                               gateway_policies=policies or dict(POLICY))
            return report, config_cls

    # ----------------------------------------------------------------- registries and claims
    def test_repository_registries_load_and_the_seeded_run_index_consumes_holdout_a_for_31b(self):
        panels = runner.load_panels()
        self.assertEqual({row["panel_id"] for row in panels["panels"]},
                         {"p3-development-v1", "p33-formal-v2", "p3-holdout-a-v2"})
        routes = runner.load_routes()
        self.assertEqual({row["route_id"] for row in routes["routes"]},
                         {"litellm-gemma-4-31b", "litellm-gemma-4-12b-it", "bedrock-jp-sonnet-4-6"})
        runs = runner.load_runs()
        self.assertGreaterEqual(len(runs), 5)
        self.assertEqual(runner.derive_claim("holdout", "p3-holdout-a-v2", "litellm-gemma-4-31b", runs),
                         "observed_regression")
        self.assertEqual(runner.derive_claim("holdout", "p3-holdout-a-v2", "bedrock-jp-sonnet-4-6", runs),
                         "fresh_holdout_observation")
        self.assertEqual(runner.derive_claim("dev", "p3-development-v1", "litellm-gemma-4-31b", runs),
                         "development_observation")
        self.assertEqual(runner.derive_claim("regression", "p33-formal-v2", "litellm-gemma-4-31b", runs),
                         "observed_regression")
        for mutate in (lambda i: i["panels"][0].update(tier="formal"),
                       lambda i: i["panels"][2].update(authoring="development"),
                       lambda i: i["panels"][2].update(freeze=None),
                       lambda i: i["panels"][2].update(intake=None),
                       lambda i: i["panels"][0].update(intake={"path": "x.json", "sha256": "0" * 64}),
                       lambda i: i["panels"][0].update(path="/etc/passwd"),
                       lambda i: i["panels"].append(dict(i["panels"][0]))):
            broken = json.loads(self.panels.read_text())
            mutate(broken)
            bad = self.root / "bad-panels.json"
            bad.write_text(json.dumps(broken))
            with self.assertRaises(p3_assets.P3Error):
                runner.load_panels(bad)
        for mutate in (lambda i: i["routes"][0].update(model="gpt-anything"),
                       lambda i: i["routes"][2].update(transport_security="unencrypted_http"),
                       lambda i: i["routes"][0].update(region="ap-northeast-1"),
                       lambda i: i["routes"][2].update(call_timeout_seconds=900)):
            broken = json.loads(self.routes.read_text())
            mutate(broken)
            bad = self.root / "bad-routes.json"
            bad.write_text(json.dumps(broken))
            with self.assertRaises(p3_assets.P3Error):
                runner.load_routes(bad)

    def test_packet_binds_candidate_panel_route_tier_and_claim_and_refuses_other_attestations(self):
        packet = json.loads(self.prepare().read_text())
        self.assertEqual(packet["version"], "evaluation-packet-v1")
        self.assertEqual((packet["tier"], packet["claim"], packet["evidence_class"]),
                         ("dev", "development_observation", "development_observation"))
        self.assertFalse(packet["promotion_eligible"])
        self.assertEqual(packet["candidate"]["candidate_id"], self.candidate)
        self.assertEqual(packet["candidate"]["candidate_sha256"], registry.current()["candidate_sha256"])
        self.assertEqual(packet["route"]["route_id"], "litellm-31b")
        self.assertEqual(packet["settings"]["call_timeout_seconds"], 60.0)
        self.assertEqual(packet["settings"]["max_client_http_attempts"], 15)
        self.assertEqual(len(packet["inputs"]), 15)
        self.assertIsNone(packet["baseline"])
        self.assertEqual(packet["observation_fields"], ["clarification_kind", "clarification_choice_count"])
        self.assertTrue(packet["run_id"].startswith("synthetic-dev--litellm-31b--"))
        for field, bad in (("promotion_eligible", True), ("claim", "fresh_holdout_observation"),
                           ("tier", "holdout"), ("evidence_class", "formal_quality"),
                           ("gateway_policy", {**packet["gateway_policy"], "retries": "enabled"}),
                           ("route", {**packet["route"], "transport_security": "tls_verification_enabled"}),
                           ("run_id", "other"), ("observation_fields", ["clarification_kind"]),
                           ("order", list(reversed(packet["order"])))):
            with self.subTest(field=field):
                changed = deepcopy(packet)
                changed[field] = bad
                with self.assertRaises(p3_assets.P3Error):
                    runner._packet_contract(changed)
        with self.assertRaises(p3_assets.P3Error):
            runner.prepare(self.database, self.root / "retries", candidate_id=self.candidate, panel_id="synthetic-dev",
                           route_id="litellm-31b", accepted_commit=SHA,
                           gateway_policies={**POLICY, "retries": "enabled"}, **self.registries)
        # The candidate binding is not recomputable offline; the rebuild at validation catches it.
        tampered = deepcopy(packet)
        tampered["candidate"]["candidate_sha256"] = "0" * 64
        runner._packet_contract(tampered)
        tampered_path = self.root / "tampered-packet.json"
        tampered_path.write_text(json.dumps(tampered))
        with self.assertRaises(p3_assets.P3Error) as rebuilt:
            runner.validate_packet(tampered_path, self.database, accepted_commit=SHA, **self.registries)
        self.assertEqual(rebuilt.exception.code, "manifest_drift")
        for kwargs, code in (({"candidate_id": "not-registered"}, "source_identity_failure"),
                             ({"panel_id": "missing"}, "invalid_panel"), ({"route_id": "missing"}, "invalid_configuration")):
            with self.assertRaises(p3_assets.P3Error) as caught:
                runner.prepare(self.database, self.root / f"bad-{code}", **{
                    "candidate_id": self.candidate, "panel_id": "synthetic-dev", "route_id": "litellm-31b", **kwargs},
                    accepted_commit=SHA, gateway_policies=dict(POLICY), **self.registries)
            self.assertEqual(caught.exception.code, code)
        # A holdout panel whose asset pins drift from the registry is refused.
        cases_path = self.root / "holdout-cases.json"
        cases_path.write_text(json.dumps(json.loads(cases_path.read_text()), indent=1))
        with self.assertRaises(p3_assets.P3Error) as drift:
            self.prepare(panel="synthetic-holdout")
        self.assertEqual(drift.exception.code, "manifest_drift")

    # ----------------------------------------------------------------- dev tier, litellm
    async def test_dev_run_records_observations_readback_and_the_run_index(self):
        packet_path = self.prepare()
        output = self.output()
        cases = p3_assets.load_panel(self.root / "development-panel-v1.json").cases
        report, config_cls = await self.run_mock(packet_path, output, self.bind(packet_path, output),
                                                 client=self.litellm_client(scripted=True, cases=cases))
        config_cls.from_env.assert_called_once_with(env_file=self.root / "unused.env")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 15)
        summary = report["summary"]
        self.assertEqual((summary["panel_kind"], summary["tier"], summary["claim"]),
                         ("evaluation", "dev", "development_observation"))
        self.assertNotIn("promotion", summary)
        self.assertEqual(sum(row["correct"] for row in summary["per_input"]), 15)
        self.assertIsNone(summary["comparison"])
        clarify_rows = [row for row in report["results"] if row["actual_action"] == "clarify"]
        self.assertTrue(clarify_rows)
        for row in report["results"]:
            if row["actual_action"] == "clarify":
                self.assertIn(row["clarification_kind"], KINDS)
            else:
                self.assertIsNone(row["clarification_kind"])
        self.assertEqual(summary["observations"]["clarify_actions"], len(clarify_rows))
        serialized = json.dumps(report)
        self.assertNotIn("PRIVATE_REASONING_CANARY", serialized)
        self.assertNotIn(KEY, serialized)
        for case in cases:
            self.assertNotIn(case.question, serialized)
        self.assertEqual(runner.read_report(output / "report.json"), report)
        for reader in (p3_formal_run.read_report, p3_holdout_run.read_report, p3_dev_regression.read_report):
            with self.assertRaises(p3_assets.P3Error):
                reader(output / "report.json")
        record = runner.record(output / "report.json", runs_path=self.runs, now="2026-09-25T00:00:00Z")
        self.assertEqual((record["tier"], record["claim"], record["correct"], record["inputs"]),
                         ("dev", "development_observation", 15, 15))
        self.assertEqual(runner.load_runs(self.runs)[0]["run_id"], report["run_id"])
        with self.assertRaises(p3_assets.P3Error) as duplicate:
            runner.record(output / "report.json", runs_path=self.runs)
        self.assertEqual(duplicate.exception.code, "artifact_conflict")
        # A second dev run compared with the first: nothing changes.
        second_packet = self.prepare(baseline=output / "report.json")
        second_output = self.output()
        second, _ = await self.run_mock(second_packet, second_output, self.bind(second_packet, second_output),
                                        client=self.litellm_client(scripted=True, cases=cases))
        comparison = second["summary"]["comparison"]
        self.assertEqual(comparison["category_counts"]["UNCHANGED_CORRECT"], 15)
        self.assertEqual((comparison["known_failures_total"], comparison["previously_correct_total"]), (0, 15))
        self.assertEqual(runner.read_report(second_output / "report.json"), second)
        # Tampered observations, claims or promotion never read back.
        path = second_output / "report.json"
        original = path.read_bytes()
        index = next(i for i, row in enumerate(second["results"]) if row["actual_action"] == "clarify")
        for mutate in (lambda r: r["results"][index].update(clarification_kind="free_text"),
                       lambda r: r.update(claim="fresh_holdout_observation"),
                       lambda r: r.update(promotion_eligible=True),
                       lambda r: r["summary"].update(claim="observed_regression"),
                       lambda r: r["summary"]["comparison"].update(new_regressions=3)):
            tampered = json.loads(original)
            mutate(tampered)
            path.write_text(json.dumps(tampered))
            with self.assertRaises(p3_assets.P3Error):
                runner.read_report(path)
        path.write_bytes(original)

    # ----------------------------------------------------------------- holdout tier and claim drift
    async def test_holdout_is_fresh_once_per_route_then_regression_and_a_stale_claim_is_drift(self):
        first_packet = self.prepare(panel="synthetic-holdout")
        first = json.loads(first_packet.read_text())
        self.assertEqual(first["claim"], "fresh_holdout_observation")
        self.assertEqual(first["panel"]["owner_review_reference"], GRANT + "77")
        self.assertTrue(all(row["exposure"] == "frozen_fresh" for row in first["inputs"]))
        self.assertEqual(first["settings"]["max_client_http_attempts"], 18)
        stale_packet = self.prepare(panel="synthetic-holdout", name="stale")
        output = self.output()
        report, _ = await self.run_mock(first_packet, output, self.bind(first_packet, output))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["claim"], "fresh_holdout_observation")
        runner.record(output / "report.json", runs_path=self.runs, now="2026-09-25T00:00:00Z")
        # The same panel on the same route is regression now; another route is still fresh.
        second = json.loads(self.prepare(panel="synthetic-holdout").read_text())
        self.assertEqual(second["claim"], "observed_regression")
        other = json.loads(self.prepare(panel="synthetic-holdout", route="litellm-12b").read_text())
        self.assertEqual(other["claim"], "fresh_holdout_observation")
        # A packet prepared before the index moved cannot run: its claim and index pin drifted.
        with patch.object(runner, "GatewayConfig") as config_cls:
            stale_output = self.output()
            with self.assertRaises(p3_assets.P3Error) as drift:
                await self.run_mock(stale_packet, stale_output, self.bind(stale_packet, stale_output))
            self.assertEqual(drift.exception.code, "manifest_drift")
            config_cls.from_env.assert_not_called()

    # ----------------------------------------------------------------- routes
    async def test_bedrock_route_uses_the_admitted_converse_client_and_records_the_profile(self):
        packet_path = self.prepare(route="bedrock-sonnet")
        packet = json.loads(packet_path.read_text())
        self.assertEqual(packet["transport_security"], "tls_verification_enabled")
        self.assertEqual(packet["settings"]["call_timeout_seconds"], 300.0)
        self.assertEqual(packet["settings"]["response_mode"], "bedrock_converse_normalized")

        def respond(request):
            self.sent.append(request)
            return httpx.Response(200, json=bedrock_response())

        client = BedrockClient(BedrockConfig("ap-northeast-1", "jp.anthropic.claude-sonnet-4-6", "synthetic-key"),
                               transport=httpx.MockTransport(respond))
        output = self.output()
        report, loader = await self.run_mock(packet_path, output, self.bind(packet_path, output), client=client,
                                             route="bedrock")
        loader.assert_called_once_with(env_file=self.root / "unused.env")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(self.sent), 15)
        self.assertTrue(all(row["evidence"]["requested_model"] == "jp.anthropic.claude-sonnet-4-6"
                            and row["evidence"]["returned_model"] is None for row in report["results"]))
        self.assertEqual(runner.read_report(output / "report.json"), report)
        # The wrong region or model never sends.
        wrong = BedrockClient(BedrockConfig("us-east-1", "jp.anthropic.claude-sonnet-4-6", "synthetic-key"),
                              transport=httpx.MockTransport(respond))
        self.sent = []
        output = self.output()
        report, _ = await self.run_mock(packet_path, output, self.bind(packet_path, output), client=wrong,
                                        route="bedrock")
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        self.assertEqual(self.sent, [])

    async def test_12b_route_admits_only_the_typed_candidate_alias(self):
        packet_path = self.prepare(route="litellm-12b")
        output = self.output()
        client = self.litellm_client(model_name=GEMMA_12B.model_alias)
        report, config_cls = await self.run_mock(packet_path, output, self.bind(packet_path, output), client=client)
        config_cls.from_env.assert_called_once_with(env_file=self.root / "unused.env", expected_model=GEMMA_12B)
        self.assertEqual(report["status"], "complete")
        self.assertTrue(all(row["evidence"]["returned_model"] == GEMMA_12B.model_alias for row in report["results"]))
        self.assertEqual(runner.read_report(output / "report.json"), report)
        # A 31B answer on the 12B route stops without fallback.
        self.sent = []
        output = self.output()
        report, _ = await self.run_mock(packet_path, output, self.bind(packet_path, output),
                                        client=self.litellm_client(model_name=MODEL))
        self.assertEqual(report["status"], "incomplete")

    # ----------------------------------------------------------------- binding
    async def test_envelope_slot_and_commit_gates_precede_env(self):
        packet_path = self.prepare()
        output = self.output()
        authorization = self.bind(packet_path, output)
        value = json.loads(authorization.read_text())
        self.assertEqual(value["run_slot"], output.relative_to(ROOT).as_posix())
        with self.assertRaises(p3_assets.P3Error):
            runner.bind_authorization(packet_path, "https://github.com/cinic0101/grepbit/issues/87",
                                      self.root / "bad.json", output)
        with patch.object(runner, "GatewayConfig") as config_cls:
            for kwargs in ({"output": self.output()}, {"commit": "2" * 40},
                           {"policies": {**POLICY, "cache": "enabled"}}):
                with self.assertRaises(p3_assets.P3Error):
                    await runner.run_live(self.database, kwargs.get("output", output), packet_path=packet_path,
                                          authorization_path=authorization, accepted_commit=kwargs.get("commit", SHA),
                                          env_file=self.root / "unused.env",
                                          gateway_policies=kwargs.get("policies", dict(POLICY)))
            holdout_envelope = self.root / "holdout-envelope.json"
            holdout_envelope.write_text(json.dumps({**value, "version": "p3-holdout-live-authorization-v1"}))
            with self.assertRaises(p3_assets.P3Error):
                await runner.run_live(self.database, output, packet_path=packet_path, authorization_path=holdout_envelope,
                                      accepted_commit=SHA, env_file=self.root / "unused.env",
                                      gateway_policies=dict(POLICY))
            config_cls.from_env.assert_not_called()

    def test_comparison_taxonomy_is_generic_over_panel_size(self):
        baseline = {"sha256": "0" * 64, "inputs": [
            {"case_id": "a", "family_id": "f", "outcome": "complete_correct", "actual_action": "answer",
             "checked_wrong": False, "correct": True},
            {"case_id": "b", "family_id": "f", "outcome": "false_clarification", "actual_action": "clarify",
             "checked_wrong": False, "correct": False},
            {"case_id": "c", "family_id": "g", "outcome": "correct_decline", "actual_action": "decline",
             "checked_wrong": False, "correct": True}], "family_correct": {"f": False, "g": True}}
        results = [{"case_id": "a", "status": "completed", "outcome": "wrong_value", "actual_action": "answer"},
                   {"case_id": "b", "status": "completed", "outcome": "complete_correct", "actual_action": "answer"},
                   {"case_id": "c", "status": "not_run", "outcome": "not_run", "actual_action": None}]
        scored = {"per_input": [{"case_id": "a", "correct": False}, {"case_id": "b", "correct": True},
                                {"case_id": "c", "correct": False}],
                  "per_family": {"f": {"family_all_variants_correct": False}, "g": {"family_all_variants_correct": False}}}
        comparison = runner._comparison(baseline, results, scored)
        self.assertEqual(comparison["category_counts"], {"UNCHANGED_CORRECT": 0, "FIXED_KNOWN_FAILURE": 1,
                                                          "NEW_REGRESSION": 1, "UNCHANGED_FAILURE": 0,
                                                          "OUTCOME_CHANGED_OTHER": 0, "UNASSESSED_OPERATIONAL": 1})
        self.assertEqual((comparison["known_failures_total"], comparison["previously_correct_total"]), (1, 2))
        self.assertEqual(comparison["action_changes"], ["b"])

    def test_cli_arguments_are_closed(self):
        with patch("sys.stdout"), patch("sys.stderr"):
            self.assertEqual(runner.main(["--prepare", "--report-path", "x"]), 2)
            self.assertEqual(runner.main(["--report", "--report-path", str(self.root / "missing.json"),
                                          "--db", str(self.database)]), 2)
            self.assertEqual(runner.main(["--record", "--report-path", str(self.root / "missing.json")]), 2)
            self.assertEqual(runner.main(["--live", "--packet", str(self.root / "none.json"), "--db", str(self.database),
                                          "--accepted-commit", SHA, "--env-file", str(self.root / "unused.env"),
                                          "--gateway-retries", "disabled", "--gateway-fallback", "disabled",
                                          "--gateway-cache", "disabled", "--output-dir", str(self.output())]), 2)


if __name__ == "__main__":
    unittest.main()
