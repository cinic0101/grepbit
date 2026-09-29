"""Offline evaluator regressions only: dummy configuration, MockTransport, synthetic SQLite."""
from __future__ import annotations

import asyncio
from contextlib import closing, redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
import logging
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, mock_open, patch

import httpx

from grepbit.contracts import KernelError
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError
from grepbit.model import MODEL, context_identity, interpret_and_execute
from tools import fixture, smoke

CANARY = "dummy-canary-secret-not-a-real-key"
BASE_URL = "https://dummy-gateway.invalid/private-sentinel"


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


def envelope(request=None, *, content=None, model=MODEL, usage=None, finish="stop"):
    if content is None:
        content = json.dumps({"outcome": "request", "request": request})
    result = {
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
    }
    if model is not None:
        result["model"] = model
    if usage is not None:
        result["usage"] = usage
    return result


class SmokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        network_guard = patch("httpx.AsyncHTTPTransport", side_effect=AssertionError("network forbidden"))
        network_guard.start()
        self.addCleanup(network_guard.stop)
        artifacts = smoke.ROOT / ".artifacts"
        artifacts.mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "fixture.sqlite"
        fixture.build(self.database)
        self.database_before = self.database.read_bytes()
        self.prepared = self.root / "prepared"
        smoke.prepare(self.database, self.prepared)
        self.manifest_path = self.prepared / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        self.entries = self.manifest["inputs"]
        self.oracle = self.manifest["oracle"]
        self.by_question = {entry["question"]: entry for entry in self.entries}
        self.sent = []
        self.output = self.root / "panel"

    def request_for(self, request):
        payload = json.loads(request.content)
        entry = self.by_question[payload["messages"][1]["content"]]
        return copy.deepcopy(self.oracle[entry["family"]]["request"])

    def client(self, handler=None):
        def respond(request):
            self.sent.append(request)
            if handler is not None:
                return handler(request)
            return httpx.Response(200, json=envelope(self.request_for(request)))

        return GatewayClient(
            GatewayConfig(BASE_URL, CANARY), transport=httpx.MockTransport(respond),
        )

    async def run_panel(self, handler=None, **kwargs):
        return await smoke.run_panel(
            self.database, self.output, manifest_path=self.manifest_path,
            client=kwargs.pop("client", None) or self.client(handler), **kwargs,
        )

    def read_report(self):
        return json.loads((self.output / "report.json").read_text())

    def assert_not_run(self, report, start, reason):
        self.assertEqual(len(report["results"]), 12)
        for entry in report["results"][start:]:
            self.assertEqual(entry["status"], "not_run")
            self.assertEqual(entry["outcome"], "not_run")
            self.assertEqual(entry["not_run_reason"], reason)
            self.assertEqual(set(entry["grading"].values()), {"not_run"})
            self.assertEqual(entry["client_http_attempts"], 0)
            self.assertEqual(entry["evidence"]["requested_model"], MODEL)
            self.assertIsNone(entry["evidence"]["returned_model"])
            self.assertIsNone(entry["evidence"]["elapsed_seconds"])
            self.assertEqual(set(entry["evidence"]["usage"].values()), {None})
        self.assertEqual(report["summary"]["semantic_families"], 4)
        self.assertEqual(sum(item["total"] for item in report["summary"]["per_language"].values()), 12)
        self.assertEqual(sum(item["total"] for item in report["summary"]["per_family"].values()), 12)

    def test_dry_run_reads_no_configuration_and_constructs_no_client(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(smoke, "GatewayClient", side_effect=AssertionError("HTTP forbidden")),
              patch.object(GatewayConfig, "from_env", side_effect=AssertionError("env forbidden")),
              patch("httpx.AsyncHTTPTransport", side_effect=AssertionError("network forbidden")),
              patch("os.getenv", side_effect=AssertionError("env forbidden")),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            result = smoke.main([
                "--db", str(self.database), "--output-dir", str(self.root / "dry"),
            ])
        self.assertEqual(result, 0)
        report = json.loads((self.root / "dry/report.json").read_text())
        self.assertEqual(report["status"], "prepared")
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["origin"], "preparation")
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["gateway_policy"], smoke.policy_attestation())
        self.assert_not_run(report, 0, "dry_run")
        self.assertNotIn(str(self.database), stdout.getvalue() + stderr.getvalue())

    def test_dry_run_rejects_explicit_live_only_options_without_reading(self):
        for options in (
            ["--env-file", str(self.root / "never-read.env")],
            ["--manifest", str(self.manifest_path)], ["--gateway-retries", "disabled"],
        ):
            with (self.subTest(options=options),
                  patch.object(GatewayConfig, "from_env", side_effect=AssertionError),
                  redirect_stderr(io.StringIO())):
                self.assertEqual(smoke.main([
                    "--db", str(self.database), "--output-dir", str(self.root / "unused"), *options,
                ]), 2)
        self.assertFalse((self.root / "unused").exists())

    def test_direct_script_cli_prepares_with_explicit_empty_environment(self):
        output_dir = self.root / "cli-prepared"
        result = subprocess.run([
            sys.executable, str(smoke.ROOT / "tools/smoke.py"),
            "--db", str(self.database), "--output-dir", str(output_dir),
        ], cwd=smoke.ROOT, env={}, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "status": "prepared", "origin": "preparation", "stop_reason": None,
            "client_http_attempts": 0, "live_model_attempts": 0,
        })
        self.assertTrue((output_dir / "manifest.json").is_file())
        self.assertEqual(json.loads((output_dir / "report.json").read_text())["status"], "prepared")

    def test_manifest_pins_exact_interleaved_accepted_inputs_and_oracles(self):
        base = fixture.load(smoke.ROOT / smoke.ASSETS[0])
        translated = fixture.load(smoke.ROOT / smoke.ASSETS[1])
        questions = {case["id"]: case["question"] for case in base["cases"]}
        variants = {case["case_id"]: case for case in translated["variants"]}
        families = list(smoke.FAMILIES)
        self.assertEqual(len(self.entries), 12)
        for index, entry in enumerate(self.entries):
            family = families[index % 4]
            language = smoke.LANGUAGES[(index // 4 + index % 4) % 3]
            expected = questions[family] if language == "zh-TW" else variants[family][language]
            self.assertEqual((entry["order"], entry["family"], entry["language"]),
                             (index + 1, family, language))
            self.assertEqual(entry["question"], expected)
            self.assertEqual(entry["question_sha256"], hashlib.sha256(expected.encode()).hexdigest())
        self.assertEqual([self.oracle[family]["expected"] for family in families], [158000, 7, 12, 5])
        for family, metric in smoke.FAMILIES.items():
            self.assertEqual(self.oracle[family]["request"], {
                "metrics": [metric], "start": fixture.START, "end": fixture.END,
                "timezone": "Asia/Taipei", "center_id": None,
            })

    def test_manifest_records_actual_identities_versions_and_fixed_bounds(self):
        identities = self.manifest["identities"]
        self.assertRegex(identities["git_commit"], r"^[0-9a-f]{40}$")
        self.assertIs(type(identities["worktree_dirty"]), bool)
        self.assertEqual(identities["context"], context_identity())
        paths = identities["files_sha256"]
        for path in (smoke.ROOT / "grepbit").glob("*.py"):
            self.assertEqual(paths[str(path.relative_to(smoke.ROOT))],
                             hashlib.sha256(path.read_bytes()).hexdigest())
        for name in (*smoke.ASSETS, "tools/smoke.py", "tools/fixture.py",
                     "requirements.in", "requirements.txt"):
            self.assertIn(name, paths)
        self.assertEqual(self.manifest["database_sha256"],
                         hashlib.sha256(self.database_before).hexdigest())
        dependencies = identities["runtime"]["dependencies"]
        self.assertEqual(dependencies["httpx"], "0.28.1")
        self.assertEqual(dependencies["python-dotenv"], "1.2.3")
        self.assertEqual(dependencies["sqlglot"], "30.18.0")
        settings = self.manifest["settings"]
        self.assertEqual(settings, {
            "model": "gemma-4-31b", "response_mode": "json_content",
            "max_client_http_attempts": 12, "concurrency": 1, "client_retries": 0,
            "repairs": 0, "stream": False, "temperature": 0, "max_tokens": 2048,
            "call_timeout_seconds": 60.0, "panel_timeout_seconds": 900.0,
            "max_input_bytes": 4096, "max_request_bytes": 32768, "max_response_bytes": 131072,
            "max_database_bytes": 16 * 1024 * 1024,
            "constraints": None, "raw_diagnostics": False, "as_of": "2026-03-31T16:00:00Z",
            "business_timezone": "Asia/Taipei",
        })

    async def test_twelve_stateless_payloads_genuine_packs_no_gold_constraints_or_thirteenth(self):
        with patch.object(smoke, "interpret_and_execute", wraps=interpret_and_execute) as runtime:
            report = await self.run_panel()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["origin"], "mock")
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertEqual(report["client_http_attempts"], 12)
        self.assertEqual(report["completed_client_http_attempts"], 12)
        self.assertEqual(runtime.await_count, 12)
        self.assertEqual(len(self.sent), 12)
        for index, (call, http_request, entry) in enumerate(zip(
            runtime.await_args_list, self.sent, report["results"],
        )):
            self.assertEqual(call.args[0], self.entries[index]["question"])
            self.assertEqual(len(call.args), 3)
            self.assertIsNone(call.kwargs["constraints"])
            payload = json.loads(http_request.content)
            self.assertEqual(set(payload), {"model", "messages", "temperature", "max_tokens", "stream"})
            self.assertEqual(payload["model"], MODEL)
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["max_tokens"], 2048)
            self.assertIs(payload["stream"], False)
            self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user"])
            self.assertEqual(payload["messages"][1]["content"], self.entries[index]["question"])
            self.assertEqual(len(payload["messages"]), 2)
            for other in self.entries:
                if other["question"] != self.entries[index]["question"]:
                    self.assertNotIn(other["question"], json.dumps(payload, ensure_ascii=False))
            system = payload["messages"][0]["content"]
            for forbidden in (*smoke.FAMILIES, "158000", "evals/", "SELECT ", "expected",
                              "bound_constraints", fixture.START, fixture.END):
                # AS_OF is ordinary context; the oracle's start is never injected.
                if forbidden == fixture.END:
                    continue
                self.assertNotIn(forbidden, system)
            self.assertEqual(entry["outcome"], "correct")
            self.assertEqual(set(entry["grading"].values()), {"passed"})
            pack = entry["evidence"]["fact_pack"]
            self.assertEqual(pack["status"], "complete")
            self.assertEqual(pack["facts"][0]["value"], self.oracle[entry["family"]]["expected"])
            self.assertIn("sql", pack["facts"][0])
            self.assertEqual(entry["client_http_attempts"], 1)
        self.assertEqual(self.database.read_bytes(), self.database_before)
        self.assertEqual(report["summary"]["all_three_correct_families"], 4)
        self.assertEqual(len(report["summary"]["per_family"]), 4)
        for item in report["summary"]["per_family"].values():
            self.assertEqual(item["correct"], 3)
            self.assertTrue(item["all_three_correct"])
        for item in report["summary"]["per_language"].values():
            self.assertEqual(item["correct"], 4)

    async def test_runtime_never_reads_evaluator_assets_during_calls(self):
        original = smoke.interpret_and_execute

        async def guarded(*args, **kwargs):
            original_read = Path.read_bytes

            def reject_assets(path):
                self.assertNotIn("/evals/", str(path))
                return original_read(path)

            with (patch.object(fixture, "load", side_effect=AssertionError("evaluator in runtime")),
                  patch.object(Path, "read_bytes", reject_assets)):
                return await original(*args, **kwargs)

        before = {name: (smoke.ROOT / name).read_bytes() for name in smoke.ASSETS}
        with patch.object(smoke, "interpret_and_execute", guarded):
            report = await self.run_panel()
        self.assertEqual(report["summary"]["correct"], 12)
        self.assertEqual(before, {name: (smoke.ROOT / name).read_bytes() for name in smoke.ASSETS})

    async def test_missing_usage_and_model_identity_remain_unknown(self):
        report = await self.run_panel(lambda request: httpx.Response(
            200, json=envelope(self.request_for(request), model=None),
        ))
        self.assertEqual(report["summary"]["correct"], 12)
        for entry in report["results"]:
            evidence = entry["evidence"]
            self.assertIsNone(evidence["returned_model"])
            self.assertEqual(evidence["requested_model"], MODEL)
            self.assertEqual(evidence["usage"], {
                "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
            })

    async def test_reported_usage_and_latency_are_preserved(self):
        usage = {"prompt_tokens": 700, "completion_tokens": 80, "total_tokens": 780}
        clock = Clock()

        def handler(request):
            clock.value += 0.25
            return httpx.Response(200, json=envelope(self.request_for(request), usage=usage))

        report = await self.run_panel(handler, clock=clock)
        self.assertEqual(report["elapsed_seconds"], 3.0)
        for entry in report["results"]:
            self.assertEqual(entry["evidence"]["usage"], usage)
            self.assertEqual(entry["evidence"]["elapsed_seconds"], 0.25)

    async def test_valid_wrong_metric_time_extra_coverage_center_timezone_execute_unchanged(self):
        changes = (
            {"metrics": ["confirmed_booking_count"]},
            {"start": "2026-03-01T00:00:00Z"},
            {"end": "2026-03-31T15:59:59Z"},
            {"metrics": ["confirmed_booked_amount", "booked_seats"]},
            {"center_id": "CA"},
            {"timezone": "UTC"},
        )
        original_output = self.output
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                self.output = original_output.with_name(f"wrong-{index}")
                self.sent.clear()

                def handler(request):
                    interpreted = self.request_for(request)
                    if len(self.sent) == 1:
                        interpreted.update(change)
                    return httpx.Response(200, json=envelope(interpreted))

                report = await self.run_panel(handler)
                first = report["results"][0]
                self.assertEqual(first["outcome"], "wrong")
                self.assertEqual(first["grading"], {
                    "json_parse": "passed", "request_validation": "passed",
                    "interpretation": "failed", "kernel": "passed", "value_agreement": "not_run",
                })
                expected = {**self.oracle["Q01_booked_amount"]["request"], **change}
                self.assertEqual(first["evidence"]["request"], expected)
                pack = first["evidence"]["fact_pack"]
                self.assertEqual([fact["metric_id"] for fact in pack["facts"]], expected["metrics"])
                self.assertEqual(report["summary"]["correct"], 11)
                self.assertEqual(report["summary"]["all_three_correct_families"], 3)
                if "timezone" in change or "end" in change:
                    self.assertEqual(pack["facts"][0]["value"], 158000)
                self.assertEqual(len(self.sent), 12)

    async def test_equivalent_offset_instants_are_normalized_before_grading(self):
        def handler(request):
            interpreted = self.request_for(request)
            interpreted.update(start="2026-03-01T00:00:00+08:00", end="2026-04-01T00:00:00+08:00")
            return httpx.Response(200, json=envelope(interpreted))

        report = await self.run_panel(handler)
        self.assertEqual(report["summary"]["correct"], 12)

    async def test_wrong_unknown_center_is_wrong_even_when_kernel_cannot_execute(self):
        def handler(request):
            interpreted = self.request_for(request)
            if len(self.sent) == 1:
                interpreted["center_id"] = "UNBOUND-CENTER"
            return httpx.Response(200, json=envelope(interpreted))

        report = await self.run_panel(handler)
        first = report["results"][0]
        self.assertEqual(first["outcome"], "wrong")
        self.assertEqual(first["grading"], {
            "json_parse": "passed", "request_validation": "passed",
            "interpretation": "failed", "kernel": "failed", "value_agreement": "not_run",
        })
        self.assertEqual(first["evidence"]["request"]["center_id"], "UNBOUND-CENTER")
        self.assertEqual(first["evidence"]["kernel_error_code"], "unknown_entity")
        self.assertIsNone(first["evidence"]["fact_pack"])
        self.assertEqual(first["error_code"], "kernel_failure")
        self.assertEqual(report["summary"]["outcomes"], {"wrong": 1, "correct": 11})
        self.assertEqual(len(self.sent), 12)

    async def test_json_request_interpretation_kernel_value_stages_are_separate(self):
        responses = (
            envelope(content="{broken"),
            envelope(content=json.dumps({"outcome": "request", "request": {"metrics": []}})),
            envelope(content=json.dumps({"outcome": "declined"})),
        )

        def handler(request):
            return httpx.Response(200, json=(
                responses[len(self.sent) - 1] if len(self.sent) <= len(responses)
                else envelope(self.request_for(request))
            ))

        report = await self.run_panel(handler)
        first, second, declined, success = report["results"][:4]
        self.assertEqual(first["outcome"], "invalid_output")
        self.assertEqual(second["outcome"], "invalid_output")
        self.assertEqual(first["grading"]["json_parse"], "failed")
        self.assertEqual(first["grading"]["request_validation"], "not_run")
        self.assertEqual(second["grading"]["json_parse"], "passed")
        self.assertEqual(second["grading"]["request_validation"], "failed")
        self.assertEqual(second["grading"]["kernel"], "not_run")
        self.assertEqual(declined["outcome"], "false_refusal")
        self.assertEqual(success["grading"]["value_agreement"], "passed")
        self.assertEqual(len(self.sent), 12)

    async def test_malformed_envelope_stops_once_as_incompatibility_not_transport_failure(self):
        def handler(request):
            return httpx.Response(200, json=(
                {"choices": []} if len(self.sent) == 1 else envelope(self.request_for(request))
            ))

        report = await self.run_panel(handler)
        first = report["results"][0]
        self.assertEqual(first["outcome"], "invalid_output")
        self.assertEqual(first["error_code"], "invalid_response")
        self.assertEqual(first["evidence"]["stages"]["response_validation"], "failed")
        self.assertEqual(set(first["grading"].values()), {"not_run"})
        self.assertEqual(report["summary"]["outcomes"], {"invalid_output": 1, "not_run": 11})
        self.assertEqual(report["stop_classification"], "envelope_incompatibility")
        self.assertEqual(len(self.sent), 1)
        self.assert_not_run(report, 1, "envelope_incompatibility")

    async def test_kernel_failure_does_not_claim_value_agreement(self):
        with patch("grepbit.model.execute_facts", side_effect=KernelError("unknown_entity", CANARY)):
            report = await self.run_panel()
        first = report["results"][0]
        self.assertEqual(first["grading"], {
            "json_parse": "passed", "request_validation": "passed", "interpretation": "passed",
            "kernel": "failed", "value_agreement": "not_run",
        })
        self.assertEqual(first["outcome"], "operational_failure")
        self.assertEqual(first["evidence"]["kernel_error_code"], "unknown_entity")
        self.assertNotIn(CANARY, json.dumps(report))

    async def test_numeric_disagreement_is_not_an_interpretation_failure(self):
        original = smoke.grade

        def alternate_oracle(result, oracle):
            return original(result, {**oracle, "expected": oracle["expected"] + 1})

        with patch.object(smoke, "grade", alternate_oracle):
            report = await self.run_panel()
        for entry in report["results"]:
            self.assertEqual(entry["grading"]["interpretation"], "passed")
            self.assertEqual(entry["grading"]["kernel"], "passed")
            self.assertEqual(entry["grading"]["value_agreement"], "failed")
            self.assertEqual(entry["outcome"], "wrong")

    async def test_nonconsecutive_transport_errors_do_not_stop_and_parse_failure_resets(self):
        statuses = [429, 200, 500, 200, 503]

        def handler(request):
            index = len(self.sent) - 1
            code = statuses[index] if index < len(statuses) else 200
            body = envelope(content="{invalid") if index == 3 else envelope(self.request_for(request))
            return httpx.Response(code, json=body)

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["client_http_attempts"], 12)
        self.assertEqual(report["results"][3]["error_code"], "invalid_json")

    async def test_two_consecutive_http_transport_failures_stop_without_retry(self):
        report = await self.run_panel(lambda request: httpx.Response(429 if len(self.sent) == 1 else 503))
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["stop_reason"], "consecutive_transport_failures")
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(report["client_http_attempts"], 2)
        self.assert_not_run(report, 2, "consecutive_transport_failures")
        self.assertEqual(report["summary"]["all_three_correct_families"], 0)

    async def test_two_consecutive_timeouts_stop_without_retry(self):
        def handler(request):
            raise httpx.ReadTimeout(CANARY + BASE_URL, request=request)

        report = await self.run_panel(handler)
        self.assertEqual(report["stop_reason"], "consecutive_transport_failures")
        self.assertEqual([entry["error_code"] for entry in report["results"][:2]], ["timeout"] * 2)
        self.assert_not_run(report, 2, "consecutive_transport_failures")

    async def test_first_auth_and_http_configuration_errors_stop_immediately(self):
        for status in (401, 403, 400, 404, 302):
            with self.subTest(status=status):
                self.output = self.root / f"status-{status}"
                self.sent.clear()
                report = await self.run_panel(lambda request: httpx.Response(status))
                self.assertEqual(report["stop_reason"], "configuration_failure")
                self.assertEqual(len(self.sent), 1)
                self.assertEqual(report["results"][0]["evidence"]["http_status"], status)
                self.assert_not_run(report, 1, "configuration_failure")

    async def test_unexpected_model_is_configuration_stop(self):
        report = await self.run_panel(lambda request: httpx.Response(
            200, json=envelope(self.request_for(request), model="other-model"),
        ))
        self.assertEqual(report["stop_reason"], "configuration_failure")
        self.assertEqual(report["results"][0]["error_code"], "unexpected_model")
        self.assertEqual(report["results"][0]["evidence"]["returned_model"], "other-model")
        self.assert_not_run(report, 1, "configuration_failure")

    async def test_output_token_and_response_byte_budgets_stop_immediately(self):
        responses = (
            lambda request: httpx.Response(200, json=envelope(
                self.request_for(request), usage={"completion_tokens": 2049},
            )),
            lambda request: httpx.Response(200, json=envelope(self.request_for(request), finish="length")),
            lambda request: httpx.Response(200, content=b"x" * 131073,
                                          headers={"content-type": "application/json"}),
        )
        for index, handler in enumerate(responses):
            with self.subTest(index=index):
                self.output = self.root / f"budget-{index}"
                self.sent.clear()
                report = await self.run_panel(handler)
                self.assertEqual(report["stop_reason"], "budget_exhausted")
                self.assertEqual(len(self.sent), 1)
                self.assert_not_run(report, 1, "budget_exhausted")

    async def test_input_budget_failure_has_zero_sends_and_no_rescue(self):
        with patch("grepbit.gateway.MAX_INPUT_BYTES", 1):
            report = await self.run_panel()
        self.assertEqual(report["stop_reason"], "budget_exhausted")
        self.assertEqual(report["results"][0]["error_code"], "input_too_large")
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(len(self.sent), 0)
        self.assert_not_run(report, 1, "budget_exhausted")

    async def test_panel_deadline_before_first_send(self):
        clock = Clock()
        original = smoke.validate_manifest

        def validate(*args):
            original(*args)
            clock.value = 901

        with patch.object(smoke, "validate_manifest", validate):
            report = await self.run_panel(clock=clock)
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(len(self.sent), 0)
        self.assert_not_run(report, 0, "panel_budget")

    async def test_deadline_expiring_during_checkpoint_prevents_send(self):
        clock = Clock()
        original = smoke._Artifacts.persist

        def persist(artifacts, report):
            original(artifacts, report)
            if report["possible_in_flight_attempts"]:
                clock.value = 900

        with patch.object(smoke._Artifacts, "persist", persist):
            report = await self.run_panel(clock=clock)
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(report["attempt_budget_used"], 0)
        self.assertEqual(report["possible_in_flight_attempts"], 0)
        self.assertEqual(len(self.sent), 0)
        self.assert_not_run(report, 0, "panel_budget")

    async def test_outer_deadline_timeout_is_one_record_and_uses_transport_streak(self):
        original = smoke.interpret_and_execute

        async def timed_out(*args, **kwargs):
            if len(self.sent) < 2:
                await args[2].complete([
                    {"role": "system", "content": "dummy"},
                    {"role": "user", "content": args[0]},
                ])
                raise TimeoutError(CANARY)
            return await original(*args, **kwargs)

        with patch.object(smoke, "interpret_and_execute", timed_out):
            report = await self.run_panel()
        self.assertEqual(report["stop_reason"], "consecutive_transport_failures")
        self.assertEqual(report["client_http_attempts"], 2)
        self.assertEqual(len(self.sent), 2)
        for entry in report["results"][:2]:
            self.assertEqual(entry["error_code"], "timeout")
            self.assertEqual(entry["outcome"], "operational_failure")
            self.assertEqual(entry["grading"]["json_parse"], "not_run")
        self.assert_not_run(report, 2, "consecutive_transport_failures")

    async def test_call_deadline_is_minimum_of_sixty_and_remaining_panel_time(self):
        clock = Clock()
        original = smoke.validate_manifest

        def validate(*args):
            original(*args)
            clock.value = 875

        def handler(request):
            self.assertEqual(request.extensions["timeout"]["read"], 25.0)
            clock.value += 25
            return httpx.Response(200, json=envelope(self.request_for(request)))

        with (patch.object(smoke, "validate_manifest", validate),
              patch.object(smoke, "interpret_and_execute", wraps=interpret_and_execute) as runtime):
            report = await self.run_panel(handler, clock=clock)
        self.assertEqual(runtime.await_args.kwargs["timeout_seconds"], 25.0)
        self.assertEqual(report["stop_reason"], "panel_budget")
        self.assertEqual(report["results"][0]["error_code"], "timeout")
        self.assert_not_run(report, 1, "panel_budget")

    async def test_normal_call_timeout_is_sixty_seconds(self):
        def handler(request):
            self.assertEqual(set(request.extensions["timeout"].values()), {60.0})
            return httpx.Response(200, json=envelope(self.request_for(request)))

        with patch.object(smoke, "interpret_and_execute", wraps=interpret_and_execute) as runtime:
            report = await self.run_panel(handler, clock=Clock())
        self.assertEqual(report["status"], "complete")
        self.assertTrue(all(call.kwargs["timeout_seconds"] == 60.0
                            for call in runtime.await_args_list))

    async def test_missing_manifest_is_zero_attempt_stop_with_all_entries(self):
        report = await smoke.run_panel(
            self.database, self.output, manifest_path=None, client=self.client(),
        )
        self.assertEqual(report["stop_reason"], "missing_manifest")
        self.assertEqual(len(self.sent), 0)
        self.assert_not_run(report, 0, "missing_manifest")

    async def test_manifest_drift_broadening_reordering_and_hand_edits_are_zero_send(self):
        mutations = (
            lambda manifest: manifest["settings"].update(max_client_http_attempts=13),
            lambda manifest: manifest["inputs"].reverse(),
            lambda manifest: manifest["inputs"][0].update(question="altered"),
            lambda manifest: manifest["oracle"]["Q01_booked_amount"].update(expected=1),
            lambda manifest: manifest["identities"].update(git_commit="0" * 40),
            lambda manifest: manifest["identities"]["context"].update(context_sha256="0" * 64),
            lambda manifest: manifest["identities"]["files_sha256"].update(
                **{"grepbit/model.py": "0" * 64}),
            lambda manifest: manifest["identities"]["runtime"]["dependencies"].update(httpx="0.0"),
            lambda manifest: manifest.update(database_sha256="0" * 64),
            lambda manifest: manifest["gateway_policy"].update(cache="disabled"),
            lambda manifest: manifest.update(extra="broadening"),
            lambda manifest: manifest["settings"].update(stream=0),
            lambda manifest: manifest["settings"].update(concurrency=True),
            lambda manifest: manifest["settings"].update(temperature=False),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                modified = copy.deepcopy(self.manifest)
                mutate(modified)
                path = self.root / f"changed-{index}.json"
                path.write_text(json.dumps(modified))
                report = await smoke.run_panel(
                    self.database, self.root / f"drift-{index}", manifest_path=path,
                    client=self.client(),
                )
                self.assertEqual(report["stop_reason"], "manifest_drift")
                self.assertEqual(len(self.sent), 0)
                self.assert_not_run(report, 0, "manifest_drift")

    async def test_manifest_duplicate_keys_and_invalid_json_rejected(self):
        for index, content in enumerate(('{broken', '{"a":1,"a":2}', '{"a":NaN}')):
            path = self.root / f"invalid-{index}.json"
            path.write_text(content)
            report = await smoke.run_panel(
                self.database, self.root / f"invalid-out-{index}", manifest_path=path,
                client=self.client(),
            )
            self.assertEqual(report["stop_reason"], "invalid_manifest")
            self.assertEqual(len(self.sent), 0)

    def test_gateway_policies_require_separate_full_operator_attestation(self):
        for policies in (None, {}, {"retries": "disabled"},
                         dict.fromkeys(smoke.POLICY_KEYS, "unknown")):
            with self.subTest(policies=policies), self.assertRaisesRegex(
                smoke.SmokeError, "^gateway_policy_required$",
            ):
                smoke.policy_attestation(policies, required=True)
        policies = {"retries": "disabled", "fallback": "disabled", "cache": "enabled"}
        self.assertEqual(smoke.policy_attestation(policies, required=True), {
            **policies, "attestation": "operator_cli_attestation_not_independently_verified",
        })
        self.assertEqual(self.manifest["gateway_policy"], smoke.policy_attestation())

    def test_missing_config_with_explicit_empty_environment_does_not_construct_transport(self):
        with (patch("httpx.AsyncHTTPTransport", side_effect=AssertionError("no network")),
              self.assertRaises(ModelError) as raised):
            GatewayConfig.from_env(environ={})
        self.assertEqual(raised.exception.code, "invalid_configuration")
        self.assertEqual(len(self.sent), 0)

    def test_live_preflight_missing_policy_or_config_and_drift_are_offline_zero_send(self):
        policies = dict.fromkeys(smoke.POLICY_KEYS, "disabled")
        with patch.object(GatewayConfig, "from_env", side_effect=AssertionError("must not load")):
            with self.assertRaisesRegex(smoke.SmokeError, "^gateway_policy_required$"):
                smoke.live_preflight(
                    self.manifest_path, self.manifest, gateway_policies=None, environ={},
                )
            with self.assertRaisesRegex(smoke.SmokeError, "^missing_manifest$"):
                smoke.live_preflight(None, self.manifest, gateway_policies=policies, environ={})
            changed = copy.deepcopy(self.manifest)
            changed["settings"]["max_tokens"] = 2049
            with self.assertRaisesRegex(smoke.SmokeError, "^manifest_drift$"):
                smoke.live_preflight(
                    self.manifest_path, changed, gateway_policies=policies, environ={},
                )
        with self.assertRaises(ModelError) as raised:
            smoke.live_preflight(
                self.manifest_path, self.manifest, gateway_policies=policies, environ={},
            )
        self.assertEqual(raised.exception.code, "invalid_configuration")
        self.assertEqual(len(self.sent), 0)

    def test_live_preflight_accepts_only_explicit_dummy_config_without_loading_dotenv(self):
        with patch("grepbit.gateway.parse_stream", side_effect=AssertionError("no dotenv discovery")):
            config = smoke.live_preflight(
                self.manifest_path, self.manifest,
                gateway_policies=dict.fromkeys(smoke.POLICY_KEYS, "disabled"),
                environ={"GREPBIT_LITELLM_BASE_URL": BASE_URL, "GREPBIT_LITELLM_API_KEY": CANARY},
            )
        self.assertEqual(config.model, MODEL)
        self.assertEqual(len(self.sent), 0)

    async def test_installed_dependency_mismatch_is_rejected_before_config_or_send(self):
        original = smoke.metadata.version
        for name in ("httpx", "sqlglot", "python-dotenv", "anyio"):
            with self.subTest(dependency=name):
                def version(package):
                    return "0.0.0" if package == name else original(package)

                client = self.client()
                with (patch.object(smoke.metadata, "version", side_effect=version),
                      patch.object(GatewayConfig, "from_env", side_effect=AssertionError("no config")),
                      self.assertRaisesRegex(smoke.SmokeError, "^source_identity_failure$")):
                    await self.run_panel(client=client)
                self.assertEqual(client.http_attempts, 0)
                self.assertFalse(self.output.exists())
        self.assertEqual(len(self.sent), 0)

    async def test_unsupported_python_and_sqlite_are_rejected_before_config_or_send(self):
        for target, attribute, version in (
            (smoke.sys, "version_info", (3, 10, 99)),
            (smoke.sqlite3, "sqlite_version_info", (3, 36, 99)),
        ):
            with self.subTest(attribute=attribute):
                client = self.client()
                with (patch.object(target, attribute, version),
                      patch.object(GatewayConfig, "from_env", side_effect=AssertionError("no config")),
                      self.assertRaisesRegex(smoke.SmokeError, "^source_identity_failure$")):
                    await self.run_panel(client=client)
                self.assertEqual(client.http_attempts, 0)
                self.assertFalse(self.output.exists())
        self.assertEqual(len(self.sent), 0)

    async def test_mock_requires_fresh_injected_client_and_never_loads_environment(self):
        client = self.client()
        client.http_attempts = 12
        with patch.object(GatewayConfig, "from_env", side_effect=AssertionError("no env")):
            report = await self.run_panel(client=client)
        self.assertEqual(report["stop_reason"], "invalid_configuration")
        self.assertEqual(len(self.sent), 0)
        self.assert_not_run(report, 0, "invalid_configuration")
        no_client = await smoke.run_panel(
            self.database, self.root / "no-client", manifest_path=self.manifest_path,
        )
        self.assertEqual(no_client["stop_reason"], "invalid_configuration")
        self.assert_not_run(no_client, 0, "invalid_configuration")

    async def test_database_change_during_call_stops_before_next_input(self):
        def handler(request):
            with closing(sqlite3.connect(self.database)) as connection:
                connection.execute("UPDATE centers SET name='synthetic-change' WHERE center_id='CA'")
                connection.commit()
            return httpx.Response(200, json=envelope(self.request_for(request)))

        report = await self.run_panel(handler)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(report["stop_reason"], "database_drift")
        self.assertEqual(report["results"][0]["outcome"], "unassessed")
        self.assert_not_run(report, 1, "database_drift")

    async def test_database_sidecar_appearing_between_calls_stops(self):
        def handler(request):
            self.database.with_name(self.database.name + "-wal").touch()
            return httpx.Response(200, json=envelope(self.request_for(request)))

        report = await self.run_panel(handler)
        self.assertEqual(report["stop_reason"], "unstable_database")
        self.assertEqual(report["results"][0]["outcome"], "unassessed")
        self.assertEqual(len(self.sent), 1)
        self.assert_not_run(report, 1, "unstable_database")

    def test_active_journal_wal_shm_or_non_fixture_database_are_rejected(self):
        for suffix in ("-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                sidecar = self.database.with_name(self.database.name + suffix)
                sidecar.touch()
                with self.assertRaisesRegex(smoke.SmokeError, "^unstable_database$"):
                    smoke.build_manifest(self.database)
                sidecar.unlink()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE centers SET name='not-the-accepted-fixture' WHERE center_id='CA'")
            connection.commit()
        with self.assertRaisesRegex(smoke.SmokeError, "^unsupported_database$"):
            smoke.build_manifest(self.database)

    def test_synthetic_database_exact_size_limit_and_oversize_rejection(self):
        self.assertEqual(smoke.MAX_DATABASE_BYTES, 16 * 1024 * 1024)
        with self.database.open("r+b") as stream:
            stream.truncate(smoke.MAX_DATABASE_BYTES)
        digest = smoke._stable_database(self.database)
        self.assertEqual(digest, hashlib.sha256(self.database.read_bytes()).hexdigest())
        with self.database.open("r+b") as stream:
            stream.truncate(smoke.MAX_DATABASE_BYTES + 1)
        with (patch.object(Path, "open", side_effect=AssertionError("oversize source must not open")),
              self.assertRaisesRegex(smoke.SmokeError, "^unsupported_database$")):
            smoke._stable_database(self.database)

    def test_synthetic_database_read_is_bounded_even_if_file_grows_after_stat(self):
        reader = mock_open(read_data=b"x" * (smoke.MAX_DATABASE_BYTES + 1))
        with (patch.object(Path, "open", reader),
              self.assertRaisesRegex(smoke.SmokeError, "^unsupported_database$")):
            smoke._stable_database(self.database)
        reader().read.assert_called_once_with(smoke.MAX_DATABASE_BYTES + 1)

    def test_actual_source_fetches_only_expected_rows_plus_one(self):
        sizes = []
        original = sqlite3.connect
        with closing(original(":memory:")) as connection:
            fixture.populate(connection)
            expected_sizes = [
                connection.execute("SELECT COUNT(*) FROM sqlite_schema").fetchone()[0] + 1,
                *[connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] + 1
                  for table in fixture.TABLES],
            ]

        class BoundedCursor(sqlite3.Cursor):
            def fetchall(self):
                raise AssertionError("unbounded source fetch")

            def fetchmany(self, size=1):
                sizes.append(size)
                return super().fetchmany(size)

        class BoundedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                return self.cursor(BoundedCursor).execute(sql, parameters)

        def connect(database, *args, **kwargs):
            if database != ":memory:":
                kwargs["factory"] = BoundedConnection
            return original(database, *args, **kwargs)

        with patch.object(sqlite3, "connect", side_effect=connect):
            digest = smoke._fixture_identity(self.database)
        self.assertEqual(digest, self.manifest["database_sha256"])
        self.assertEqual(sizes, expected_sizes)

    def test_one_extra_synthetic_row_is_rejected(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "INSERT INTO centers VALUES ('CX','CTR-X99','Extra','north','Asia/Taipei')",
            )
            connection.commit()
        with self.assertRaisesRegex(smoke.SmokeError, "^unsupported_database$"):
            smoke._fixture_identity(self.database)

    def test_output_directory_and_files_are_private_and_exclusive(self):
        report_before = (self.prepared / "report.json").read_bytes()
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            smoke.prepare(self.database, self.prepared)
        self.assertEqual((self.prepared / "report.json").read_bytes(), report_before)
        self.assertEqual(stat.S_IMODE(self.prepared.stat().st_mode) & 0o077, 0)
        for path in self.prepared.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
        link = self.root / "linked"
        link.symlink_to(self.prepared, target_is_directory=True)
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            smoke.prepare(self.database, link / "new")
        self.assertFalse((self.prepared / "new").exists())

    async def test_manifest_and_database_symlink_targets_are_rejected(self):
        manifest_link = self.root / "linked-manifest.json"
        manifest_link.symlink_to(self.manifest_path)
        report = await smoke.run_panel(
            self.database, self.output, manifest_path=manifest_link, client=self.client(),
        )
        self.assertEqual(report["stop_reason"], "artifact_conflict")
        self.assertEqual(len(self.sent), 0)
        database_link = self.root / "linked.sqlite"
        database_link.symlink_to(self.database)
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            smoke.build_manifest(database_link)

    async def test_replaced_report_symlink_is_never_followed_or_overwritten(self):
        victim = self.root / "untouched.txt"
        victim.write_text("untouched")

        def handler(request):
            path = self.output / "report.json"
            path.unlink()
            path.symlink_to(victim)
            return httpx.Response(200, json=envelope(self.request_for(request)))

        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            await self.run_panel(handler)
        self.assertEqual(victim.read_text(), "untouched")
        self.assertTrue((self.output / "report.json").is_symlink())
        initial = json.loads((self.output / "checkpoint-0001.json").read_text())
        self.assertEqual(initial["status"], "incomplete")
        self.assertEqual(initial["results"][0]["status"], "in_progress")

    async def test_durable_in_progress_reservation_exists_before_send(self):
        def handler(request):
            current = self.read_report()
            index = len(self.sent) - 1
            self.assertEqual(current["status"], "incomplete")
            self.assertEqual(current["results"][index]["status"], "in_progress")
            self.assertEqual(current["client_http_attempts"], index)
            self.assertEqual(current["attempt_budget_used"], index + 1)
            self.assertEqual(current["possible_in_flight_attempts"], 1)
            self.assertTrue(current["results"][index]["attempt_may_be_in_flight"])
            return httpx.Response(200, json=envelope(self.request_for(request)))

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "complete")
        snapshots = sorted(self.output.glob("checkpoint-*.json"))
        self.assertEqual(len(snapshots), 26)
        self.assertEqual(json.loads(snapshots[0].read_text())["status"], "incomplete")
        self.assertEqual(json.loads(snapshots[1].read_text())["results"][0]["status"], "in_progress")
        self.assertEqual(self.read_report(), report)

    async def test_keyboard_interrupt_preserves_in_flight_attempt_and_prior_evidence(self):
        def handler(request):
            if len(self.sent) == 2:
                raise KeyboardInterrupt(CANARY + BASE_URL)
            return httpx.Response(200, json=envelope(self.request_for(request)))

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "interrupted")
        self.assertEqual(report["client_http_attempts"], 2)
        self.assertEqual(report["attempt_budget_used"], 2)
        self.assertEqual(report["completed_client_http_attempts"], 1)
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertEqual(report["results"][0]["outcome"], "correct")
        active = report["results"][1]
        self.assertEqual(active["status"], "in_progress")
        self.assertEqual(active["outcome"], "unassessed")
        self.assertEqual(active["client_http_attempts"], 1)
        self.assertTrue(active["attempt_may_be_in_flight"])
        self.assert_not_run(report, 2, "interrupted")
        self.assertEqual(self.read_report(), report)
        self.assertNotIn(CANARY, json.dumps(report))

    async def test_cancellation_before_runtime_send_preserves_possible_attempt(self):
        with patch.object(smoke, "interpret_and_execute", new=AsyncMock(side_effect=asyncio.CancelledError)):
            report = await self.run_panel()
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["client_http_attempts"], 0)
        self.assertEqual(report["completed_client_http_attempts"], 0)
        self.assertEqual(report["attempt_budget_used"], 1)
        self.assertEqual(report["possible_in_flight_attempts"], 1)
        self.assertEqual(report["results"][0]["status"], "in_progress")
        self.assert_not_run(report, 1, "interrupted")

    async def test_unexpected_failure_is_safe_incomplete_not_success(self):
        def handler(request):
            raise RuntimeError(CANARY + BASE_URL)

        report = await self.run_panel(handler)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stop_reason"], "internal_failure")
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertNotIn(CANARY, json.dumps(report))
        self.assert_not_run(report, 1, "internal_failure")

    async def test_explicit_boundary_error_families_preserve_safe_incomplete_reports(self):
        for index, error_type in enumerate((
            RuntimeError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError,
            AttributeError, OSError, ValueError, sqlite3.OperationalError,
        )):
            with self.subTest(error_type=error_type):
                self.output = self.root / f"boundary-{index}"
                with patch.object(
                    smoke, "interpret_and_execute",
                    new=AsyncMock(side_effect=error_type(CANARY + BASE_URL)),
                ):
                    report = await self.run_panel()
                self.assertEqual(report["status"], "incomplete")
                self.assertEqual(report["error_code"], "internal_failure")
                self.assertEqual(report["results"][0]["status"], "in_progress")
                self.assertEqual(report["client_http_attempts"], 0)
                self.assertEqual(report["attempt_budget_used"], 1)
                self.assert_not_run(report, 1, "internal_failure")
                self.assertNotIn(CANARY, json.dumps(report))
                self.assertNotIn(BASE_URL, json.dumps(report))

    def test_cli_boundary_error_families_emit_only_fixed_internal_failure(self):
        for error_type in (
            RuntimeError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError,
            AttributeError, OSError, ValueError, sqlite3.OperationalError,
        ):
            with self.subTest(error_type=error_type):
                stream = io.StringIO()
                with (patch.object(smoke, "prepare", side_effect=error_type(CANARY + BASE_URL)),
                      redirect_stderr(stream)):
                    result = smoke.main([
                        "--db", str(self.database), "--output-dir", str(self.output),
                    ])
                self.assertEqual(result, 2)
                self.assertEqual(json.loads(stream.getvalue()), {
                    "status": "incomplete", "error_code": "internal_failure",
                })

    async def test_canary_and_url_echo_never_reach_report_stdout_or_transport_logs(self):
        output, logs = io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(logs)
        logger = logging.getLogger("httpx")
        previous_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(logger.setLevel, previous_level)

        def response(request):
            if len(self.sent) == 1:
                body = envelope(content=CANARY + BASE_URL)
                body["choices"][0]["message"]["reasoning_content"] = CANARY + BASE_URL
                return httpx.Response(200, json=body)
            if len(self.sent) == 2:
                interpreted = self.request_for(request)
                interpreted["center_id"] = CANARY
                return httpx.Response(200, json=envelope(interpreted))
            if len(self.sent) == 3:
                raise httpx.ConnectError(CANARY + BASE_URL, request=request)
            return httpx.Response(401, text=CANARY + BASE_URL)

        with redirect_stdout(output), redirect_stderr(output):
            report = await self.run_panel(response)
        self.assertEqual(report["stop_reason"], "configuration_failure")
        serialized = json.dumps(report) + output.getvalue() + logs.getvalue()
        serialized += "".join(path.read_text() for path in self.output.glob("*.json"))
        for forbidden in (CANARY, BASE_URL, "dummy-gateway.invalid"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(report["results"][1]["evidence"]["request"]["center_id"], "[redacted]")

    def test_cli_errors_do_not_echo_untrusted_arguments(self):
        for options in (
            ["--unexpected-" + CANARY, BASE_URL],
            ["--gateway-cache", CANARY + BASE_URL],
            ["--env-file"],
            ["--env-file", BASE_URL + "/" + CANARY],
        ):
            with self.subTest(options=options):
                stream = io.StringIO()
                with redirect_stderr(stream):
                    result = smoke.main([
                        "--db", str(self.database), "--output-dir", str(self.output), *options,
                    ])
                self.assertEqual(result, 2)
                self.assertEqual(json.loads(stream.getvalue())["error_code"], "invalid_arguments")
                self.assertNotIn(CANARY, stream.getvalue())
                self.assertNotIn(BASE_URL, stream.getvalue())


if __name__ == "__main__":
    unittest.main()
