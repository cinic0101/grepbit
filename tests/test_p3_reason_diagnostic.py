"""Offline rulers for the closed eight-input reason diagnostic (#74); fake transport, no AWS."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit.bedrock import BedrockClient, BedrockConfig
from tools import fixture, p3_assets, p3_eval
from tools import p3_reason_diagnostic as diagnostic

OWNER_REFERENCE = "https://github.com/cinic0101/grepbit/issues/74#issuecomment-123"
SINGLE_CHOICE = ('{"outcome":"clarify","clarification":{"kind":"center","choices":[{"id":"a",'
                 '"semantic_value":{"type":"center","request":{"center_code":"CTR-A01",'
                 '"start":"2026-03-01T00:00:00+08:00","end":"2026-04-01T00:00:00+08:00",'
                 '"timezone":"Asia/Taipei"}}}]}}')
EXTRA_FIELD = ('{"outcome":"request","recipe_id":"compare","recipe_version":"0.1","request":{'
               '"current":{"metrics":["confirmed_booked_amount"],"start":"2026-03-01T00:00:00+08:00",'
               '"end":"2026-04-01T00:00:00+08:00","timezone":"Asia/Taipei","center_id":null,"label":"x"},'
               '"baseline":{"metrics":["confirmed_booked_amount"],"start":"2026-02-01T00:00:00+08:00",'
               '"end":"2026-03-01T00:00:00+08:00","timezone":"Asia/Taipei"}}}')


def response(content='{"outcome":"declined"}'):
    return {"output": {"message": {"role": "assistant", "content": [{"text": content}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}


class ReasonDiagnosticRulers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport"):
            self.enterContext(patch(target, side_effect=AssertionError("Network forbidden")))
        temporary = tempfile.TemporaryDirectory(prefix="p374-synthetic-", dir=p3_eval.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "synthetic.sqlite"
        fixture.build(self.database)
        self.panel = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        chosen = tuple(case for case in self.panel.cases)[:8]
        self.case_ids = tuple(case.case_id for case in chosen)
        hashes = {case.case_id: hashlib.sha256(case.question.encode()).hexdigest() for case in chosen}
        self.enterContext(patch.object(diagnostic, "CASE_IDS", self.case_ids))
        self.enterContext(patch.object(diagnostic, "QUESTION_SHA256", hashes))
        pins = {name: {"reference": name + ".json", "sha256": digest}
                for name, digest in diagnostic.observed.PINS.items()}
        self.enterContext(patch.object(diagnostic, "_materials", return_value=(self.panel, pins)))
        self.enterContext(patch.object(diagnostic, "_verify_archive",
                                       return_value={"reference": "synthetic-report.json", "sha256": "1" * 64}))
        self.source = {"git_commit": "1" * 40, "branch": "dev", "worktree_dirty": False,
                       "files_sha256": {"synthetic": "1" * 64}}
        self.enterContext(patch.object(diagnostic, "_verify_source", return_value=deepcopy(self.source)))
        self.enterContext(patch.object(diagnostic.observed, "_current_identities", return_value={
            "baseline_semantic_identity_sha256": "2" * 64, "effective_runtime_identity_sha256": "3" * 64,
            "canonical_schema_sha256": "4" * 64, "wire_schema_sha256": "5" * 64}))
        self.sent = []
        self.serial = 0

    def output(self):
        self.serial += 1
        return self.root / f"run-{self.serial}"

    async def run_mock(self, *, handler=None, owner_reference=OWNER_REFERENCE, client=None, output=None,
                       policies=None):
        def respond(request):
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=response())

        client = client or BedrockClient(BedrockConfig(diagnostic.REGION, diagnostic.PROFILE, "synthetic-key"),
                                         transport=httpx.MockTransport(respond))
        output = output or self.output()
        with patch.object(diagnostic, "client_from_env", return_value=client) as load:
            report = await diagnostic.run_live(
                self.database, output, accepted_commit="1" * 40, owner_reference=owner_reference,
                env_file=self.root / "unused-synthetic.env", gateway_policies=policies or dict(diagnostic.POLICIES))
        return report, output, load

    def test_pinned_panel_provider_and_bounds(self):
        original_ids = ("FA04_A04_compare_year_on_baseline_nonadjacent.en",
                        "FA09_C02_comparison_roles_symmetric.r2.zh-TW",
                        "FA09_C02_comparison_roles_symmetric.r2.en", "FA09_C02_comparison_roles_symmetric.r2.ja",
                        "E02_compare.en", "P15_center.en", "P16_metric_meaning.zh-TW", "P22_center_compare.ja")
        source = Path(diagnostic.__file__).read_text()
        for case_id in original_ids:
            self.assertIn(f'"{case_id}"', source)
        self.assertEqual(diagnostic.MAX_CALLS, 8)
        self.assertEqual(diagnostic.settings()["call_timeout_seconds"], 300.0)
        self.assertEqual(diagnostic.settings()["run_timeout_seconds"], 2520.0)
        self.assertEqual(diagnostic.settings()["max_client_http_attempts"], 8)
        self.assertEqual(diagnostic.settings()["client_retries"], 0)
        self.assertEqual(diagnostic.PROFILE, "jp.anthropic.claude-sonnet-4-6")
        self.assertEqual(diagnostic.REGION, "ap-northeast-1")
        self.assertEqual(diagnostic.EVIDENCE_CLASS, "diagnostic_regression_data")
        self.assertIsNone(diagnostic.OWNER.fullmatch(
            "https://github.com/cinic0101/grepbit/issues/70#issuecomment-123"))

    async def test_eight_inputs_one_attempt_each_with_private_capture_and_readback(self):
        report, output, load = await self.run_mock()
        self.assertEqual(report["status"], "complete")
        self.assertEqual((report["runtime_invocations"], report["client_http_attempts"], len(self.sent)), (8, 8, 8))
        self.assertEqual(load.call_count, 1)
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["evidence_class"], "diagnostic_regression_data")
        self.assertEqual(report["requested_profile"], diagnostic.PROFILE)
        self.assertIsNone(report["returned_model"])
        self.assertEqual(report["private_capture"]["files"], 8)
        private_dir = output.with_name(output.name + "-private")
        self.assertEqual(oct(private_dir.stat().st_mode & 0o777), "0o700")
        files = sorted(private_dir.iterdir())
        self.assertEqual(len(files), 8)
        for row, path in zip(report["results"], files):
            self.assertEqual(row["status"], "completed")
            self.assertEqual(row["client_http_attempts"], 1)
            self.assertEqual(row["actual_action"], "decline")
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
            private = json.loads(path.read_text())
            self.assertEqual(private["completion_text"], '{"outcome":"declined"}')
            self.assertEqual(row["private_capture"]["reference"], path.name)
            self.assertEqual(row["private_capture"]["sha256"], private["body_sha256"])
            self.assertTrue(row["private_capture"]["text_captured"])
            self.assertEqual(row["fingerprint"]["outcome"], "declined")
            self.assertEqual(row["fingerprint"]["root_known_keys"], ["outcome"])
            self.assertEqual(row["evidence"]["requested_model"], diagnostic.PROFILE)
            self.assertIsNone(row["evidence"]["returned_model"])
            self.assertIsNone(row["invalid_request_reason"])
        text = json.dumps(report)
        for secret in ("synthetic-key", "bedrock-runtime.", "completion_text", "raw_body_utf8", '{\\"outcome'):
            self.assertNotIn(secret, text)
        self.assertEqual(diagnostic.read_report(output / "report.json"), report)
        for question in (case.question for case in self.panel.cases[:8]):
            self.assertNotIn(question, text)

    async def test_single_choice_clarification_is_named_and_fingerprinted(self):
        report, output, _ = await self.run_mock(
            handler=lambda _: httpx.Response(200, json=response(SINGLE_CHOICE)))
        self.assertEqual(report["status"], "complete")
        row = report["results"][0]
        self.assertEqual(row["error_code"], "invalid_request")
        self.assertEqual(row["invalid_request_reason"], "choice_count")
        self.assertEqual(row["evidence"]["invalid_request_reason"], "choice_count")
        self.assertEqual(row["evidence"]["stages"]["request_validation"], "failed")
        self.assertEqual(row["fingerprint"]["outcome"], "clarify")
        self.assertEqual(row["fingerprint"]["kind"], "center")
        self.assertEqual(row["fingerprint"]["choice_count"], 1)
        self.assertTrue(row["fingerprint"]["choice_key_sets_valid"])
        self.assertEqual(row["fingerprint"]["semantic_value_types"], ["center"])
        self.assertEqual(report["summary"]["invalid_request_reasons"], {"choice_count": 8})
        self.assertEqual(diagnostic.read_report(output / "report.json"), report)
        self.assertNotIn("CTR-A01", json.dumps(report))

    async def test_extra_request_field_is_named_and_counted_without_its_name(self):
        report, output, _ = await self.run_mock(
            handler=lambda _: httpx.Response(200, json=response(EXTRA_FIELD)))
        row = report["results"][0]
        self.assertEqual(row["invalid_request_reason"], "request_values")
        self.assertEqual(row["fingerprint"]["recipe_id"], "compare")
        self.assertEqual(row["fingerprint"]["request_known_keys"], ["baseline", "current"])
        self.assertEqual(row["fingerprint"]["scopes"]["current"],
                         {"known_keys": ["center_id", "end", "metrics", "start", "timezone"], "unknown_key_count": 1})
        self.assertNotIn("label", json.dumps(report))
        self.assertEqual(diagnostic.read_report(output / "report.json"), report)

    def test_fingerprint_is_closed_and_never_carries_values(self):
        self.assertEqual(diagnostic.fingerprint(None), {"version": diagnostic.FINGERPRINT_VERSION,
                                                          "normalized": False, "parsed": False})
        self.assertEqual(diagnostic.fingerprint("not json")["parsed"], False)
        self.assertEqual(diagnostic.fingerprint("[1]")["root_type"], "array")
        shaped = diagnostic.fingerprint('{"outcome":"bogus","secret":"PRIVATE","recipe_id":"overview",'
                                        '"request":{"center_code":"X","sql":"SELECT 1"}}')
        self.assertEqual(shaped["outcome"], "other")
        self.assertEqual(shaped["root_unknown_key_count"], 1)
        self.assertEqual(shaped["request_known_keys"], ["center_code"])
        self.assertEqual(shaped["request_unknown_key_count"], 1)
        for forbidden in ("PRIVATE", "bogus", "secret", "sql", "SELECT", "X"):
            self.assertNotIn(forbidden, json.dumps(shaped))
        diagnostic._check_fingerprint(shaped)
        for bad in ({**shaped, "outcome": "bogus"}, {**shaped, "request_known_keys": ["sql"]},
                    {**shaped, "extra": 1}, {**shaped, "root_unknown_key_count": -1}):
            with self.subTest(bad=sorted(set(bad) ^ set(shaped)) or "value"), \
                    self.assertRaises(p3_assets.P3Error):
                diagnostic._check_fingerprint(bad)

    async def test_admission_drift_stops_before_any_send(self):
        with self.assertRaises(p3_assets.P3Error):
            await self.run_mock(owner_reference="https://github.com/cinic0101/grepbit/issues/70#issuecomment-1")
        with self.assertRaises(p3_assets.P3Error):
            await self.run_mock(policies={**diagnostic.POLICIES, "retries": "enabled"})
        wrong_profile = BedrockClient(BedrockConfig(diagnostic.REGION, "other.profile", "synthetic-key"),
                                      transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        report, _, _ = await self.run_mock(client=wrong_profile)
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "invalid_configuration"))
        wrong_region = BedrockClient(BedrockConfig("us-east-1", diagnostic.PROFILE, "synthetic-key"),
                                     transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        report, _, _ = await self.run_mock(client=wrong_region)
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        with patch.object(diagnostic, "QUESTION_SHA256", {case_id: "0" * 64 for case_id in self.case_ids}):
            with self.assertRaisesRegex(p3_assets.P3Error, "manifest_drift"):
                await self.run_mock()
        self.assertEqual(self.sent, [])

    async def test_consecutive_timeouts_stop_and_preserve_the_partial_run(self):
        calls = 0

        async def timeout(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            from grepbit.gateway import ModelError
            from grepbit.recipe_model import RecipeInterpretation
            evidence = {"requested_model": diagnostic.PROFILE, "returned_model": None, "client_http_attempts": 0,
                        "elapsed_seconds": 300.0, "http_status": None, "transport_security": diagnostic.TRANSPORT,
                        "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
                        "stages": {**dict.fromkeys(diagnostic.model.STAGES, "not_run"), "configuration": "passed",
                                   "transport": "failed"},
                        "error_code": "timeout", "stop_reason": None, "invalid_request_reason": None}
            return RecipeInterpretation(None, None, ModelError("timeout"), evidence)

        with patch.object(diagnostic, "interpret_recipe_and_execute", side_effect=timeout):
            report, output, _ = await self.run_mock()
        self.assertEqual(calls, 2)
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "consecutive_timeouts"))
        self.assertEqual(report["timeout_streak"], 2)
        self.assertEqual([row["status"] for row in report["results"]], ["completed"] * 2 + ["not_run"] * 6)
        self.assertEqual(report["private_capture"]["files"], 0)
        self.assertEqual(diagnostic.read_report(output / "report.json"), report)
        with self.assertRaisesRegex(diagnostic.smoke.SmokeError, "artifact_conflict"):
            await self.run_mock(output=output)

    async def test_readback_rejects_tampering_and_private_text(self):
        report, output, _ = await self.run_mock()
        path = output / "report.json"
        for change in (lambda r: r.update(promotion_eligible=True),
                       lambda r: r["results"][0].update(invalid_request_reason="free text"),
                       lambda r: r["results"][0]["evidence"].update(returned_model=diagnostic.PROFILE),
                       lambda r: r["results"][0].update(private_capture=None),
                       lambda r: r["results"][0]["fingerprint"].update(outcome="anything"),
                       lambda r: r["results"][0].update(completion_text="leaked"),
                       lambda r: r.update(client_http_attempts=7)):
            changed = deepcopy(report)
            change(changed)
            path.write_text(json.dumps(changed))
            with self.subTest(change=change.__code__.co_firstlineno), self.assertRaises(p3_assets.P3Error):
                diagnostic.read_report(path)
        path.write_text(json.dumps(report))
        self.assertEqual(diagnostic.read_report(path), report)

    def test_cli_arguments_are_closed(self):
        self.assertEqual(diagnostic.main(["--report"]), 2)
        self.assertEqual(diagnostic.main(["--live", "--db", "x"]), 2)
        self.assertEqual(diagnostic.main(["--report", "--report-path", str(self.root / "missing" / "report.json")]), 2)


if __name__ == "__main__":
    unittest.main()
