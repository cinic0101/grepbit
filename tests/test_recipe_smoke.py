"""Gate A runner regressions: disposable artifacts, fake HTTP, no live authorization."""
import asyncio
from contextlib import closing, contextmanager, ExitStack, redirect_stderr, redirect_stdout
import copy
from dataclasses import replace
from datetime import timedelta, timezone
import errno
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from grepbit import (
    BreakdownAnalysisPack, BreakdownRequest, CompareAnalysisPack, CompareRequest,
    OverviewAnalysisPack, OverviewRequest,
)
from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError
from grepbit.recipe_model import RecipeInterpretation, RecipeProposal
from tools import fixture, recipe_smoke as runner, smoke


BASE = "https://recipe-smoke-private.invalid/v1"
KEY = "dummy-recipe-smoke-secret"
CANARY = "PRIVATE_RECIPE_SMOKE_PROVIDER"
FAKE_COMMIT = "1" * 40
ORDER = (
    ("E01_overview", "zh-TW"), ("E02_compare", "en"), ("E03_share_denominator", "ja"),
    ("E01_overview", "en"), ("E02_compare", "ja"), ("E03_share_denominator", "zh-TW"),
    ("E01_overview", "ja"), ("E02_compare", "zh-TW"), ("E03_share_denominator", "en"),
)
MOCK_HTTP_ATTEMPTS = 0


def envelope(proposal=None, *, content=None):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(proposal) if content is None else content,
    }}]}


def changed(original, **fields):
    """Trusted output-copy corruption, preserving IDs to isolate a grading dimension."""
    result = copy.copy(original)
    for name, item in fields.items():
        object.__setattr__(result, name, item)
    return result


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class RecipeSmokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                     "socket.getaddrinfo", "httpx.AsyncHTTPTransport"):
            guard = patch(name, side_effect=AssertionError("Real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(GatewayConfig, "from_env", side_effect=AssertionError("Real configuration forbidden"))
        self.loader = guard.start()
        self.addCleanup(guard.stop)
        temp = tempfile.TemporaryDirectory(dir=runner.ROOT / ".artifacts")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.serial = 0
        self.sent = []
        self.fresh_fixture("initial")

    def fresh_fixture(self, name):
        self.database = self.root / f"{name}.sqlite"
        fixture.build(self.database)
        self.prepared = self.root / f"prepared-{name}"
        runner.prepare(self.database, self.prepared)
        self.manifest_path = self.prepared / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        self.entries, self.oracle = runner.panel_inputs()
        self.by_question = {entry["question"]: entry for entry in self.entries}

    def write_json(self, path, value):
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        return path

    def wire(self, request):
        question = json.loads(request.content)["messages"][1]["content"]
        oracle = self.oracle[self.by_question[question]["family"]]
        return {"outcome": "request", **{key: copy.deepcopy(oracle[key])
                                        for key in ("recipe_id", "recipe_version", "request")}}

    def client(self, handler=None):
        def respond(request):
            global MOCK_HTTP_ATTEMPTS
            MOCK_HTTP_ATTEMPTS += 1
            self.sent.append(request)
            return handler(request) if handler else httpx.Response(200, json=envelope(self.wire(request)))
        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def run_panel(self, handler=None, *, client=None, **kwargs):
        self.output = self.root / f"panel-{self.serial}"
        self.serial += 1
        self.sent = []
        report = await runner.run_panel(
            self.database, self.output, manifest_path=kwargs.pop("manifest_path", self.manifest_path),
            client=self.client(handler) if client is None else client, **kwargs)
        self.assertLessEqual(len(self.sent), 9)
        self.assertEqual(report["live_model_attempts"], 0)
        self.assert_private(report)
        return report

    def read_report(self):
        return json.loads((self.output / "report.json").read_text())

    def assert_private(self, value):
        self.assertFalse(any(fragment in str(value) for fragment in (BASE, KEY, CANARY, "recipe-smoke-private.invalid")))

    def assert_terminal_evidence(self, report):
        self.assert_private(report)
        self.assertEqual((len(self.sent), len(report["results"]), report["client_http_attempts"],
                          report["attempt_budget_used"], report["possible_in_flight_attempts"]), (9, 9, 9, 9, 0))
        self.assertEqual(report["live_model_attempts"], 0)
        for row in report["results"]:
            self.assertEqual((row["status"], row["client_http_attempts"], row["attempt_may_be_in_flight"]),
                             ("completed", 1, False))
            self.assertEqual(set(row["grading"]), set(runner.GRADING_STAGES))
            if row["outcome"] == "correct":
                self.assertEqual(set(row["grading"].values()), {"passed"})
        for path in self.output.glob("checkpoint-*.json"):
            snapshot = json.loads(path.read_text())
            self.assert_private(snapshot)
            self.assertNotEqual(snapshot["status"], "complete",
                                "An ordinary checkpoint must never publish terminal success")

    def assert_mock_cli_exit(self, outcome, expected):
        behavior = {"side_effect": outcome} if isinstance(outcome, BaseException) else {"return_value": outcome}
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(runner, "prepare", **behavior),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            code = runner.main(["--db", str(self.database), "--output-dir", str(self.root / "unused-cli")])
        self.assertEqual(code, expected)
        self.assert_private(stdout.getvalue() + stderr.getvalue())
        if not isinstance(outcome, BaseException):
            self.assertEqual(json.loads(stdout.getvalue())["origin"], "mock")
        self.loader.assert_not_called()

    def assert_tail(self, report, start, reason):
        self.assertEqual(len(report["results"]), 9)
        for row in report["results"][start:]:
            self.assertEqual((row["status"], row["outcome"], row["not_run_reason"]), ("not_run", "not_run", reason))
            self.assertEqual(row["client_http_attempts"], 0)
            self.assertEqual(set(row["grading"].values()), {"not_run"})
        self.assertEqual((report["summary"]["semantic_families"], report["summary"]["paired_inputs"]), (3, 9))

    def native(self, family):
        oracle = self.oracle[family]
        recipe = oracle["recipe_id"]
        request_type = {"overview": OverviewRequest, "compare": CompareRequest, "breakdown": BreakdownRequest}[recipe]
        request = request_type.from_mapping(oracle["request"])
        pack = getattr(recipe_model, f"execute_{recipe}")(self.database, request)
        return RecipeInterpretation(RecipeProposal(recipe, request), pack, None, {})

    def assert_grade(self, result, family, outcome, failed_stage=None):
        actual, stages = runner.grade(result, self.oracle[family])
        self.assertEqual(actual, outcome)
        if failed_stage:
            self.assertEqual(stages[failed_stage], "failed")
            following = runner.GRADING_STAGES[runner.GRADING_STAGES.index(failed_stage) + 1:]
            self.assertTrue(all(stages[key] == "not_run" for key in following))
        return stages

    def test_fixed_nine_question_references_hashes_order_and_e10_exclusion(self):
        self.assertEqual(tuple((entry["case_id"], entry["language"]) for entry in self.entries), ORDER)
        self.assertEqual(tuple(runner.ORDER), ORDER)
        cases = {case["id"]: case["question"] for case in json.loads(
            (runner.ROOT / smoke.ASSETS[0]).read_text())["cases"]}
        translations = {case["case_id"]: case for case in json.loads(
            (runner.ROOT / smoke.ASSETS[1]).read_text())["variants"]}
        for index, (entry, persisted) in enumerate(zip(self.entries, self.manifest["inputs"])):
            family, language = ORDER[index]
            question = cases[family] if language == "zh-TW" else translations[family][language]
            self.assertEqual((entry["order"], entry["family"], entry["question"]), (index + 1, family, question))
            self.assertEqual(entry["question_sha256"], hashlib.sha256(question.encode()).hexdigest())
            self.assertEqual(entry["question_reference"], {
                "asset": smoke.ASSETS[0] if language == "zh-TW" else smoke.ASSETS[1],
                "case_id": family, "field": "question" if language == "zh-TW" else language,
            })
            self.assertEqual(persisted, {key: value for key, value in entry.items() if key != "question"})
        self.assertEqual(set(self.oracle), {"E01_overview", "E02_compare", "E03_share_denominator"})
        self.assertNotIn("E10", json.dumps(self.manifest))
        with patch.object(runner, "ORDER", tuple(reversed(ORDER))):
            with self.assertRaisesRegex(runner.RecipeSmokeError, "^source_identity_failure$"):
                runner.panel_inputs()

    def test_actual_manifest_pins_and_unchanged_p1_helpers_p26_context(self):
        identity = self.manifest["identities"]
        self.assertEqual(identity["context"], recipe_model.context_identity())
        for path in ("tools/recipe_smoke.py", runner.PANEL_ASSET, "tools/smoke.py", "grepbit/recipe_model.py",
                     "grepbit/json_diagnostics.py", "grepbit/gateway.py",
                     "requirements.in", "requirements.txt", *smoke.ASSETS):
            self.assertEqual(identity["files_sha256"][path], hashlib.sha256((runner.ROOT / path).read_bytes()).hexdigest())
        self.assertEqual(identity["runtime"]["dependencies"]["httpx"], "0.28.1")
        self.assertEqual(self.manifest["database_sha256"], hashlib.sha256(self.database.read_bytes()).hexdigest())
        for name, function in (("settings", runner.settings), ("stop_policy", runner.stop_policy)):
            self.assertEqual(self.manifest[name], function())
            self.assertEqual(self.manifest[f"{name}_sha256"], smoke._digest(model.canonical_json(function()).encode()))
        self.assertEqual((runner.MAX_ATTEMPTS, runner.PANEL_SECONDS), (9, 720))
        self.assertEqual(self.manifest["settings"]["constraints"], None)
        self.assertIs(runner.smoke, smoke)
        self.assertEqual(hashlib.sha256((runner.ROOT / "tools/smoke.py").read_bytes()).hexdigest(),
                         "91de6225de4f653b23310f29fcebdba5ce91d4e35c6ea413a5bbb73563070c42")
        self.assertEqual(model.context_identity()["context_sha256"],
                         "70545dbc5ed67b33b907301933a5556d7575d014bcc19472119d10ba11647fc6")
        # Diagnostics and generation constraints preserve the complete P2.6 semantic protocol.
        self.assertEqual(identity["context"], {
            "context_version": "learningops-recipe-context-v1",
            "output_contract": "recipe-request-json-v1",
            "instruction_version": "recipe-selection-instruction-v1",
            "catalog_sha256": "9027e2af35e49a790fd4c3e985ccff12e92868946f9398506ccfa7e623c897c5",
            "context_sha256": "7de6ed524fa5ddaeb530038c3a7b127461a7edb557749b61ef28558d359d6b87",
            "output_contract_sha256": "ac6ca4d71fbe6a69c978231458bc6d4be7fca3f5ebbee732d4cdedad0dec9a02",
            "instruction_sha256": "cbf9e613e6b2a8e42ff758f9b0ceed1d2b4227be1a4d5d17cea1aee62b1cb270",
            "system_message_sha256": "5893fb44fbad47c3e5b2f970e0165d0caaf062e75ac9af88dc80e6dcd4a2ffab",
        })
        self.assertEqual(identity["structured_output"], {
            "version": "recipe-structured-output-v1", "mode": "json_schema",
            "schema_name": "grepbit_recipe_request",
            "schema_sha256": "ac6ca4d71fbe6a69c978231458bc6d4be7fca3f5ebbee732d4cdedad0dec9a02",
            "response_format_sha256": "4333d65dede04246311681767015be7438503ff019b239d1d0c0194ab9a037ab",
        })
        with patch.object(smoke, "_source_identity", wraps=smoke._source_identity) as delegated:
            runner._source_identity()
        delegated.assert_called_once()
        self.assertEqual(smoke.settings()["max_client_http_attempts"], 12)

    def test_candidate_default_and_synthetic_accepted_clean_dev_attestation_gate(self):
        clean = {**copy.deepcopy(self.manifest["identities"]), "git_commit": FAKE_COMMIT,
                 "branch": "dev", "worktree_dirty": False}
        with patch.object(runner, "_source_identity", side_effect=lambda: copy.deepcopy(clean)):
            candidate = runner.build_manifest(self.database)
            accepted = runner.build_manifest(self.database, accepted_commit=FAKE_COMMIT)
        self.assertEqual(candidate["preparation"], {"kind": "candidate", "accepted_commit": None})
        self.assertEqual(accepted["preparation"], {"kind": "accepted", "accepted_commit": FAKE_COMMIT})
        self.assertIn("not automatic approval", accepted["acceptance_boundary"])
        for identity, commit in (
            (clean, FAKE_COMMIT[:7]), (clean, "A" * 40), (clean, None),
            ({**clean, "git_commit": "2" * 40}, FAKE_COMMIT),
            ({**clean, "branch": "feat/not-accepted"}, FAKE_COMMIT),
            ({**clean, "worktree_dirty": True}, FAKE_COMMIT),
        ):
            with self.subTest(branch=identity["branch"], commit=commit):
                with self.assertRaisesRegex(runner.RecipeSmokeError, "^accepted_commit_required$"):
                    runner._accepted(identity, commit)
        self.assertFalse(self.sent)
        self.loader.assert_not_called()

    def test_preparation_cli_is_zero_http_no_environment_and_candidate_only(self):
        out, err = io.StringIO(), io.StringIO()
        with (patch.object(runner, "GatewayClient", side_effect=AssertionError("Client creation forbidden")),
              redirect_stdout(out), redirect_stderr(err)):
            code = runner.main(["--db", str(self.database), "--output-dir", str(self.root / "dry")])
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        summary = json.loads(out.getvalue())
        self.assertEqual((summary["status"], summary["client_http_attempts"], summary["live_model_attempts"]),
                         ("prepared", 0, 0))
        report = json.loads((self.root / "dry/report.json").read_text())
        self.assertEqual(report["preparation"]["kind"], "candidate")
        self.assert_tail(report, 0, "offline_preparation")
        self.loader.assert_not_called()
        self.assertFalse(self.sent)
        self.assertNotIn(str(self.database), out.getvalue())

    async def test_all_nine_correct_native_packs_shared_messages_and_durable_reservations(self):
        observed, original = [], runner.interpret_recipe_and_execute

        async def capture(*args, **kwargs):
            self.assertEqual(set(kwargs), {"timeout_seconds", "clock"})
            self.assertIsInstance(args[0], str)
            result = await original(*args, **kwargs)
            observed.append(result)
            return result

        def respond(request):
            index = len(self.sent) - 1
            reserved = self.read_report()
            self.assertEqual(reserved["results"][index]["status"], "in_progress")
            self.assertTrue(reserved["results"][index]["attempt_may_be_in_flight"])
            self.assertEqual((reserved["client_http_attempts"], reserved["attempt_budget_used"],
                              reserved["possible_in_flight_attempts"]), (index, index + 1, 1))
            document = envelope(self.wire(request))
            document[CANARY] = KEY
            document["choices"][0]["message"]["reasoning_content"] = BASE + KEY
            return httpx.Response(200, json=document)

        before = self.database.read_bytes()
        with patch.object(runner, "interpret_recipe_and_execute", side_effect=capture):
            report = await self.run_panel(respond)
        self.assertEqual((report["status"], report["client_http_attempts"], len(self.sent)), ("complete", 9, 9))
        self.assertEqual(report["summary"]["outcomes"], {"correct": 9})
        self.assertEqual(report["summary"]["all_three_correct_families"], 3)
        self.assertEqual(report["summary"]["at_least_one_correct_families"], 3)
        self.assertEqual({type(result.analysis_pack) for result in observed},
                         {OverviewAnalysisPack, CompareAnalysisPack, BreakdownAnalysisPack})
        self.assertEqual(observed[1].analysis_pack.derived_facts[1].value, Fraction(54, 25))
        self.assertEqual(observed[2].analysis_pack.derived_facts[1].value, Fraction(64, 79))
        for entry, request, result in zip(self.entries, self.sent, observed):
            messages = json.loads(request.content)["messages"]
            self.assertEqual(messages, recipe_model.messages_for(entry["question"]))
            self.assertIsNone(result.error)
            self.assertEqual(result.evidence["client_http_attempts"], 1)
        systems = [json.loads(request.content)["messages"][0]["content"] for request in self.sent]
        self.assertEqual(len(set(systems)), 1)
        for forbidden in ("expected", "E01_overview", "E02_compare", "E03_share_denominator",
                          "siblings", "oracle", "158000", "128000", "68000"):
            self.assertNotIn(forbidden, systems[0])
        snapshots = sorted(self.output.glob("checkpoint-*.json"))
        self.assertEqual(len(snapshots), 20)
        self.assert_terminal_evidence(report)
        self.assertEqual((self.output / "report.json").stat().st_ino,
                         (self.output / "terminal-candidate.json").stat().st_ino)
        self.assertNotEqual((self.output / "report.json").stat().st_ino, snapshots[-1].stat().st_ino)
        self.assertFalse((self.output / "terminal.next.json").exists())
        self.assertEqual(self.read_report(), report)
        self.assertEqual(self.database.read_bytes(), before)
        for path in self.output.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
            text = path.read_text()
            self.assert_private(text)
            self.assertFalse(any(entry["question"] in text for entry in self.entries))

    def test_grader_roles_k_code_wrong_recipe_and_error_precedence_before_values(self):
        for family in self.oracle:
            base = self.native(family)
            self.assert_grade(base, family, "correct")
            request = base.proposal.request
            if isinstance(request, OverviewRequest):
                wrong = replace(request, center_code="CTR-A02")
            elif isinstance(request, CompareRequest):
                wrong = CompareRequest(request.baseline, request.current)
            else:
                wrong = replace(request, top_k=1)
            proposal = replace(base.proposal, request=wrong)
            # Correct original numbers cannot rescue the wrong typed intent.
            self.assert_grade(replace(base, proposal=proposal), family, "wrong_request", "request")
            self.assert_grade(replace(base, proposal=proposal, analysis_pack=None, error=ModelError("source_failure")),
                              family, "wrong_request", "request")
            other = self.native("E02_compare" if family != "E02_compare" else "E01_overview")
            self.assert_grade(replace(base, proposal=other.proposal, error=ModelError("kernel_failure")),
                              family, "wrong_recipe", "recipe")

    def test_canonical_request_accepts_equivalent_offsets_and_preserves_null_center(self):
        taipei = timezone(timedelta(hours=8))
        for family in self.oracle:
            result = self.native(family)
            request = result.proposal.request
            if isinstance(request, CompareRequest):
                equivalent = CompareRequest(*(replace(scope, start=scope.start.astimezone(taipei),
                                                       end=scope.end.astimezone(taipei))
                                               for scope in (request.current, request.baseline)))
                self.assertIsNone(runner.canonical_request(equivalent)["current"]["center_id"])
            else:
                equivalent = replace(request, start=request.start.astimezone(taipei), end=request.end.astimezone(taipei))
            self.assertEqual(runner.canonical_request(equivalent), self.oracle[family]["request"])
            self.assert_grade(replace(result, proposal=replace(result.proposal, request=equivalent)), family, "correct")

    def test_grader_requires_native_coverage_shape_binding_roles_and_fact_links(self):
        overview = self.native("E01_overview")
        pack = overview.analysis_pack
        swapped = (replace(pack.slots[0], fact_id=pack.slots[1].fact_id),
                   replace(pack.slots[1], fact_id=pack.slots[0].fact_id), *pack.slots[2:])
        changes = [
            ("partial", replace(pack, status="partial")),
            ("group_missing", replace(pack, grouped_facts=pack.grouped_facts[:1])),
            ("slot_missing", replace(pack, slots=pack.slots[:-1])),
            ("role", replace(pack, slots=(*pack.slots[:-1], replace(pack.slots[-1], role="required")))),
            ("unknown_link", replace(pack, slots=(replace(pack.slots[0], fact_id="missing"), *pack.slots[1:]))),
            ("binding", replace(pack, binding=replace(pack.binding, center_id="CB"))),
            ("swapped_role_links", replace(pack, slots=swapped)),
        ]
        for label, corrupt in changes:
            with self.subTest(case=label):
                self.assert_grade(replace(overview, analysis_pack=corrupt), "E01_overview", "wrong_coverage", "coverage")
        for family in ("E02_compare", "E03_share_denominator"):
            result = self.native(family)
            pack = result.analysis_pack
            failed = replace(pack, slots=(*pack.slots[:-1], replace(pack.slots[-1], state="unavailable")))
            self.assert_grade(replace(result, analysis_pack=failed), family, "wrong_coverage", "coverage")
            swapped = (replace(pack.slots[0], fact_id=pack.slots[1].fact_id),
                       replace(pack.slots[1], fact_id=pack.slots[0].fact_id), *pack.slots[2:])
            with self.subTest(family=family, case="swapped_role_links"):
                self.assert_grade(replace(result, analysis_pack=replace(pack, slots=swapped)),
                                  family, "wrong_coverage", "coverage")
        result = self.native("E03_share_denominator")
        for field, value in (("dimension", "category"), ("coverage", "all_observed_groups"), ("top_k", 1)):
            with self.subTest(field=field):
                group = replace(result.analysis_pack.grouped_facts[0], **{field: value})
                self.assert_grade(replace(result, analysis_pack=replace(result.analysis_pack, grouped_facts=(group,))),
                                  "E03_share_denominator", "wrong_coverage", "coverage")

    def test_grader_value_agreement_is_exact_and_fractions_are_canonical(self):
        overview = self.native("E01_overview")
        for value in (4.0, True, 5):
            with self.subTest(value=value):
                facts = list(overview.analysis_pack.facts)
                facts[1] = replace(facts[1], value=value)
                self.assert_grade(replace(overview, analysis_pack=replace(overview.analysis_pack, facts=tuple(facts))),
                                  "E01_overview", "wrong_value", "value_agreement")
        for family, ratio in (("E02_compare", Fraction(108, 50)), ("E03_share_denominator", Fraction(128, 158))):
            result = self.native(family)
            derived = result.analysis_pack.derived_facts
            same = changed(derived[1], value=ratio)
            self.assert_grade(replace(result, analysis_pack=replace(result.analysis_pack, derived_facts=(derived[0], same))),
                              family, "correct")
            wrong = changed(derived[1], value=float(ratio))
            self.assert_grade(replace(result, analysis_pack=replace(result.analysis_pack, derived_facts=(derived[0], wrong))),
                              family, "wrong_value", "value_agreement")

    async def test_semantic_failures_continue_and_cli_complete_does_not_mean_correct(self):
        def respond(request):
            index = len(self.sent) - 1
            if index < 2:
                return httpx.Response(200, json=envelope(content='{"outcome":"declined"}' if index == 0 else "{bad"))
            candidate = self.wire(request)
            if index == 2:
                candidate["request"]["top_k"] = 1
            return httpx.Response(200, json=envelope(candidate))

        report = await self.run_panel(respond)
        self.assertEqual(report["status"], "complete")
        self.assertEqual([row["outcome"] for row in report["results"][:3]],
                         ["false_refusal", "invalid_output", "wrong_request"])
        self.assertEqual(report["summary"]["outcomes"], {"false_refusal": 1, "invalid_output": 1, "wrong_request": 1, "correct": 6})
        self.assertEqual(len(self.sent), 9)
        self.assert_terminal_evidence(report)
        self.assertEqual(self.read_report(), report)
        self.assertEqual(json.loads((self.output / "terminal-candidate.json").read_text()), report)
        self.assert_mock_cli_exit(report, 0)

    async def test_missing_pack_without_adapter_error_stops_internal_failure(self):
        original = runner.interpret_recipe_and_execute

        async def missing_pack(*args, **kwargs):
            result = await original(*args, **kwargs)
            self.assertIsNone(result.error)
            evidence = copy.deepcopy(result.evidence)
            evidence.update(analysis_pack=None, pack_status=None)
            return replace(result, analysis_pack=None, evidence=evidence)

        with patch.object(runner, "interpret_recipe_and_execute", side_effect=missing_pack):
            report = await self.run_panel()
        self.assertEqual((report["status"], report["stop_reason"], len(self.sent)), ("stopped", "internal_failure", 1))
        row = report["results"][0]
        self.assertEqual((row["outcome"], row["error_code"], row["runner_error_code"]),
                         ("operational_failure", None, "internal_failure"))
        self.assertEqual(row["grading"]["execution"], "failed")
        self.assertEqual(self.read_report(), report)
        self.assert_tail(report, 1, "internal_failure")

    async def test_auth_envelope_and_token_budget_stops_are_immediate(self):
        for status, document, stop in (
            (401, {}, "configuration_failure"), (200, {"choices": []}, "envelope_incompatibility"),
            (200, {"model": MODEL, "usage": {"completion_tokens": 2049},
                   "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}]},
             "budget_exhausted"),
        ):
            with self.subTest(stop=stop):
                report = await self.run_panel(lambda _: httpx.Response(status, json=document))
                self.assertEqual((report["status"], report["stop_reason"], len(self.sent)), ("stopped", stop, 1))
                self.assertEqual(report["results"][0]["outcome"], "operational_failure")
                self.assert_tail(report, 1, stop)

    async def test_network_timeout_mixed_and_reset_streaks_use_codes_not_transport_flag(self):
        cases = (
            (("gateway_error", "rate_limited"), False, "consecutive_network_failures", 2),
            (("timeout", "timeout"), False, "consecutive_timeouts", 2),
            (("timeout", "timeout"), True, "consecutive_timeouts", 2),
            (("transport_error", "timeout", "transport_error", "timeout"), True, None, 9),
            (("timeout", None, "timeout", "timeout"), False, "consecutive_timeouts", 4),
            (("gateway_error", "invalid_json", "gateway_error", "gateway_error"), True, "consecutive_network_failures", 4),
            (("timeout", "model_declined", "timeout"), False, None, 9),
        )
        original = runner.interpret_recipe_and_execute
        for sequence, flag, stop, attempts in cases:
            with self.subTest(sequence=sequence, transport_failure=flag):
                def respond(request):
                    index = len(self.sent) - 1
                    code = sequence[index] if index < len(sequence) else None
                    if code == "timeout":
                        raise httpx.ReadTimeout(CANARY)
                    if code == "transport_error":
                        raise httpx.ConnectError(CANARY)
                    if code in ("gateway_error", "rate_limited"):
                        return httpx.Response(503 if code == "gateway_error" else 429, content=CANARY)
                    if code in ("invalid_json", "model_declined"):
                        return httpx.Response(200, json=envelope(content="{bad" if code == "invalid_json" else '{"outcome":"declined"}'))
                    return httpx.Response(200, json=envelope(self.wire(request)))

                async def alter_flag(*args, **kwargs):
                    result = await original(*args, **kwargs)
                    if result.error and result.error.code in runner.NETWORK_CODES | {"timeout"}:
                        result.error.transport_failure = flag
                        result.evidence["transport_failure"] = flag
                    return result

                with patch.object(runner, "interpret_recipe_and_execute", side_effect=alter_flag):
                    report = await self.run_panel(respond)
                self.assertEqual((report["stop_reason"], report["client_http_attempts"], len(self.sent)), (stop, attempts, attempts))
                self.assertEqual(report["status"], "stopped" if stop else "complete")
                self.assertEqual((report["network_failure_streak"], report["timeout_streak"]),
                                 (2, 0) if stop == "consecutive_network_failures" else (0, 2) if stop else (0, 0))
                if stop:
                    self.assert_tail(report, attempts, stop)

    async def test_outer_timeout_uses_recipe_evidence_and_timeout_streak(self):
        async def timed_out(question, database, client, **kwargs):
            await client.complete(recipe_model.messages_for(question))
            raise TimeoutError(CANARY)

        with patch.object(runner, "interpret_recipe_and_execute", side_effect=timed_out):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], len(self.sent)), ("consecutive_timeouts", 2))
        for row in report["results"][:2]:
            self.assertEqual(row["error_code"], "timeout")
            self.assertEqual(row["evidence"]["context_identity"], recipe_model.context_identity())
            self.assertIsNone(row["evidence"]["proposal"])
            self.assertNotIn("fact_pack", row["evidence"])
        self.assert_tail(report, 2, "consecutive_timeouts")

    async def test_accidental_default_transport_reused_client_and_extra_attempt_are_blocked(self):
        for client in (GatewayClient(GatewayConfig(BASE, KEY)), self.client()):
            if client._transport is not None:
                client.http_attempts = 1
            with self.subTest(transport_present=client._transport is not None):
                report = await self.run_panel(client=client)
                self.assertEqual(report["stop_reason"], "invalid_configuration")
                self.assertFalse(self.sent)
        original = runner.interpret_recipe_and_execute

        async def extra_call(question, database, client, **kwargs):
            result = await original(question, database, client, **kwargs)
            await client.complete(recipe_model.messages_for(question))
            return result

        with patch.object(runner, "interpret_recipe_and_execute", side_effect=extra_call):
            report = await self.run_panel()
        self.assertEqual((report["stop_reason"], report["client_http_attempts"]), ("attempt_budget", 2))
        self.assertEqual(report["results"][0]["client_http_attempts"], 2)
        self.assert_tail(report, 1, "attempt_budget")

    async def test_panel_deadline_before_during_reservation_and_after_response(self):
        validate, persist = smoke.validate_manifest, smoke._Artifacts.persist
        for phase in ("before", "reservation", "response"):
            with self.subTest(phase=phase):
                clock = Clock()

                def validated(*args):
                    validate(*args)
                    if phase in ("before", "response"):
                        clock.value = 720 if phase == "before" else 700

                def persisted(artifacts, report):
                    persist(artifacts, report)
                    if phase == "reservation" and report["possible_in_flight_attempts"]:
                        clock.value = 720

                def respond(request):
                    self.assertEqual(request.extensions["timeout"]["read"], 20)
                    clock.value = 720
                    return httpx.Response(200, json=envelope(self.wire(request)))

                with (patch.object(smoke, "validate_manifest", side_effect=validated),
                      patch.object(smoke._Artifacts, "persist", new=persisted)):
                    report = await self.run_panel(respond, clock=clock)
                attempts = int(phase == "response")
                self.assertEqual((report["stop_reason"], len(self.sent)), ("panel_budget", attempts))
                self.assertEqual((report["attempt_budget_used"], report["possible_in_flight_attempts"]), (attempts, 0))
                self.assert_tail(report, attempts, "panel_budget")
                if attempts:
                    self.assertEqual(report["results"][0]["error_code"], "timeout")

    async def test_terminal_stage_faults_never_publish_complete(self):
        # R1 replaces publish-then-correct: complete may exist only in an unpublished candidate.
        write, fdopen, atomic = smoke._Artifacts._write, os.fdopen, os.replace
        for fault, expires in (("write", None), ("flush", None), ("fsync", None),
                               ("deadline", 720.0), ("deadline", 721.0)):
            with self.subTest(fault=fault, expires=expires):
                clock, stages, faults, prior = Clock(), [], [], []

                def fail(*args, **kwargs):
                    faults.append(fault)
                    raise OSError(errno.ENOSPC, CANARY)

                @contextmanager
                def faulty_stream(*args, **kwargs):
                    with fdopen(*args, **kwargs) as stream:
                        proxy = Mock(wraps=stream)
                        getattr(proxy, fault).side_effect = fail
                        yield proxy

                def staged(artifacts, name, data):
                    if name != "terminal-candidate.json":
                        return write(artifacts, name, data)
                    stages.append(name)
                    saved = self.read_report()
                    self.assert_terminal_evidence(saved)
                    self.assertNotEqual(saved["status"], "complete")
                    prior.append(copy.deepcopy(saved["results"]))
                    with ExitStack() as injected:
                        if fault in ("write", "flush"):
                            injected.enter_context(patch.object(os, "fdopen", side_effect=faulty_stream))
                        elif fault == "fsync":
                            injected.enter_context(patch.object(os, "fsync", side_effect=fail))
                        path = write(artifacts, name, data)
                    clock.value = expires
                    return path

                def no_publication(source, target):
                    self.assertNotEqual(Path(source).name, "terminal.next.json")
                    return atomic(source, target)

                with (patch.object(smoke._Artifacts, "_write", new=staged),
                      patch.object(os, "replace", side_effect=no_publication)):
                    report = await self.run_panel(clock=clock)
                reason = "panel_budget" if fault == "deadline" else "artifact_io"
                self.assertEqual((report["status"], report["stop_reason"]), ("stopped", reason))
                self.assertEqual(stages, ["terminal-candidate.json"])
                self.assertEqual(faults, [] if fault == "deadline" else [fault])
                durable = self.read_report()
                self.assert_terminal_evidence(durable)
                self.assertNotEqual(durable["status"], "complete")
                self.assertEqual(durable["results"], prior[0])
                self.assertEqual(durable["summary"]["outcomes"], {"correct": 9})
                self.assertEqual(durable, report)
                if fault == "deadline":
                    candidate = json.loads((self.output / "terminal-candidate.json").read_text())
                    self.assertEqual(candidate["status"], "complete")
                    self.assertEqual(candidate["elapsed_seconds"], 0.0)
                self.assert_mock_cli_exit(report, 1)

    async def test_terminal_deadline_with_persistent_enospc_keeps_prior_report_safe(self):
        write, open_file, atomic = smoke._Artifacts._write, os.open, os.replace
        clock, armed, rejected, prior = Clock(), [False], [], []

        def staged(artifacts, name, data):
            path = write(artifacts, name, data)
            if name == "terminal-candidate.json":
                prior.append((self.output / "report.json").read_bytes())
                self.assertNotEqual(self.read_report()["status"], "complete")
                clock.value = 720.0
                armed[0] = True
            return path

        def disk_full(path, flags, *args, **kwargs):
            if armed[0] and flags & os.O_CREAT:
                rejected.append(Path(path).name)
                raise OSError(errno.ENOSPC, CANARY)
            return open_file(path, flags, *args, **kwargs)

        def no_publication(source, target):
            self.assertNotEqual(Path(source).name, "terminal.next.json")
            return atomic(source, target)

        with (patch.object(smoke._Artifacts, "_write", new=staged),
              patch.object(os, "open", side_effect=disk_full),
              patch.object(os, "replace", side_effect=no_publication)):
            try:
                outcome = await self.run_panel(clock=clock)
            except (runner.RecipeSmokeError, smoke.SmokeError) as error:
                self.assertEqual(error.code, "artifact_io")
                outcome = error
        self.assertTrue(armed[0])
        self.assertEqual(len(rejected), 1, "Diagnostic writes are persistent failures, not retries until success")
        self.assertTrue(rejected[0].startswith("checkpoint-"))
        self.assertEqual((self.output / "report.json").read_bytes(), prior[0])
        durable = self.read_report()
        self.assert_terminal_evidence(durable)
        self.assertEqual(durable["status"], "incomplete")
        self.assertEqual(durable["summary"]["outcomes"], {"correct": 9})
        self.assertEqual(json.loads((self.output / "terminal-candidate.json").read_text())["status"], "complete")
        if isinstance(outcome, BaseException):
            self.assert_mock_cli_exit(outcome, 2)
        else:
            self.assertNotEqual(outcome["status"], "complete")
            self.assert_mock_cli_exit(outcome, 1)

    async def test_terminal_publication_commit_and_interruption_boundaries(self):
        write, link, atomic = smoke._Artifacts._write, os.link, os.replace
        lstat, unlink = Path.lstat, os.unlink
        for fault in ("none", "replace_failure", "before_interrupt", "late_return", "after_interrupt"):
            with self.subTest(fault=fault):
                clock, committed, publications, samples, prior, candidates = Clock(), [False], [], [], [], []

                def now():
                    self.assertFalse(committed[0], "No deadline check may follow atomic publication")
                    samples.append(clock.value)
                    return clock.value

                def staged(artifacts, name, data):
                    self.assertFalse(committed[0], "No compensating checkpoint may follow publication")
                    path = write(artifacts, name, data)
                    if name == "terminal-candidate.json":
                        clock.value = 7.0
                        candidates.append(path.read_bytes())
                    return path

                def linked(source, target):
                    result = link(source, target)
                    if Path(target).name == "terminal.next.json":
                        clock.value = 10.0
                    return result

                def guarded_lstat(path, *args, **kwargs):
                    self.assertFalse(committed[0], "No post-publication ownership recheck")
                    return lstat(path, *args, **kwargs)

                def guarded_unlink(path, *args, **kwargs):
                    self.assertFalse(committed[0], "No mandatory post-publication cleanup")
                    return unlink(path, *args, **kwargs)

                def publish(source, target):
                    if Path(source).name != "terminal.next.json":
                        return atomic(source, target)
                    publications.append((Path(source), Path(target)))
                    prior.append((self.output / "report.json").read_bytes())
                    self.assertNotEqual(self.read_report()["status"], "complete")
                    self.assertEqual(samples[-1], 10.0, "Admission must follow staging and pending-link preparation")
                    if fault == "replace_failure":
                        raise OSError(errno.ENOSPC, CANARY)
                    if fault == "before_interrupt":
                        raise KeyboardInterrupt(CANARY)
                    result = atomic(source, target)
                    committed[0] = True
                    if fault == "late_return":
                        clock.value = 721.0
                    if fault == "after_interrupt":
                        raise KeyboardInterrupt(CANARY)
                    return result

                with (patch.object(smoke._Artifacts, "_write", new=staged),
                      patch.object(os, "link", side_effect=linked),
                      patch.object(os, "replace", side_effect=publish),
                      patch.object(Path, "lstat", new=guarded_lstat),
                      patch.object(os, "unlink", side_effect=guarded_unlink)):
                    try:
                        outcome = await self.run_panel(clock=now)
                    except (runner.RecipeSmokeError, smoke.SmokeError, KeyboardInterrupt) as error:
                        outcome = error
                self.assertEqual(publications, [(self.output / "terminal.next.json", self.output / "report.json")])
                durable = self.read_report()
                self.assert_terminal_evidence(durable)
                self.assertEqual(durable["summary"]["outcomes"], {"correct": 9})
                self.assertEqual(durable["results"], json.loads(prior[0])["results"])
                self.assertEqual((self.output / "terminal-candidate.json").read_bytes(), candidates[0])
                if fault in ("replace_failure", "before_interrupt"):
                    self.assertFalse(committed[0])
                    self.assertNotEqual(durable["status"], "complete")
                    self.assertEqual((self.output / "report.json").read_bytes(), prior[0])
                    if fault == "replace_failure":
                        self.assertIsInstance(outcome, (runner.RecipeSmokeError, smoke.SmokeError))
                        self.assertEqual(outcome.code, "artifact_io")
                        self.assert_mock_cli_exit(outcome, 2)
                    else:
                        self.assertIsInstance(outcome, KeyboardInterrupt)
                        self.assert_mock_cli_exit(outcome, 130)
                else:
                    self.assertTrue(committed[0])
                    self.assertEqual((durable["status"], durable["elapsed_seconds"]), ("complete", 0.0))
                    self.assertEqual((self.output / "report.json").read_bytes(), candidates[0])
                    self.assertEqual((self.output / "report.json").stat().st_ino,
                                     (self.output / "terminal-candidate.json").stat().st_ino)
                    self.assertFalse((self.output / "terminal.next.json").exists())
                    if fault == "after_interrupt":
                        self.assertIsInstance(outcome, KeyboardInterrupt)
                        self.assert_mock_cli_exit(outcome, 130)
                    else:
                        self.assertEqual(outcome, durable)
                        self.assert_mock_cli_exit(outcome, 0)
                self.assertEqual(runner.stop_policy()["version"], "p2.7-stops-v2")

    async def test_terminal_stage_names_and_owned_links_cannot_be_replaced(self):
        write, link = smoke._Artifacts._write, os.link
        for fault in ("candidate_exists", "pending_exists", "owned_report", "pending_identity"):
            with self.subTest(fault=fault):
                foreign = self.root / f"foreign-{fault}.json"
                sentinel = b'{"sentinel":"untouched"}\n'
                foreign.write_bytes(sentinel)

                def respond(request):
                    if len(self.sent) == 9 and fault in ("candidate_exists", "pending_exists"):
                        name = "terminal-candidate.json" if fault == "candidate_exists" else "terminal.next.json"
                        with (self.output / name).open("xb") as stream:
                            stream.write(sentinel)
                    return httpx.Response(200, json=envelope(self.wire(request)))

                def staged(artifacts, name, data):
                    path = write(artifacts, name, data)
                    if name == "terminal-candidate.json" and fault == "owned_report":
                        foreign.write_bytes((self.output / "report.json").read_bytes())
                        (self.output / "report.json").unlink()
                        link(foreign, self.output / "report.json")
                    return path

                def linked(source, target):
                    result = link(source, target)
                    if Path(target).name == "terminal.next.json" and fault == "pending_identity":
                        Path(target).unlink()
                        link(foreign, target)
                    return result

                with (patch.object(smoke._Artifacts, "_write", new=staged),
                      patch.object(os, "link", side_effect=linked)):
                    try:
                        outcome = await self.run_panel(respond)
                    except (runner.RecipeSmokeError, smoke.SmokeError) as error:
                        self.assertEqual(error.code, "artifact_conflict")
                        outcome = error
                durable = self.read_report()
                self.assert_terminal_evidence(durable)
                self.assertNotEqual(durable["status"], "complete")
                self.assertEqual(durable["summary"]["outcomes"], {"correct": 9})
                if fault == "owned_report":
                    self.assertEqual((self.output / "report.json").read_bytes(), foreign.read_bytes())
                    self.assertEqual((self.output / "report.json").stat().st_ino, foreign.stat().st_ino)
                else:
                    name = "terminal-candidate.json" if fault == "candidate_exists" else "terminal.next.json"
                    self.assertEqual((self.output / name).read_bytes(), sentinel)
                    self.assertEqual(foreign.read_bytes(), sentinel)
                if isinstance(outcome, BaseException):
                    self.assert_mock_cli_exit(outcome, 2)
                else:
                    self.assertEqual(outcome["stop_reason"], "artifact_conflict")
                    self.assert_mock_cli_exit(outcome, 1)

    async def test_second_question_resolution_must_match_pinned_text_metadata_and_count(self):
        original = runner.panel_inputs
        for fault in ("stale_question_hash", "family_metadata", "missing_entry"):
            with self.subTest(fault=fault):
                calls = []

                def resolved():
                    entries, oracle = original()
                    calls.append(len(entries))
                    if len(calls) == 2:
                        if fault == "stale_question_hash":
                            entries[0]["question"] += " changed"
                        elif fault == "family_metadata":
                            entries[0]["family"] = "E02_compare"
                        else:
                            entries.pop()
                    return entries, oracle

                with patch.object(runner, "panel_inputs", side_effect=resolved):
                    report = await self.run_panel()
                self.assertEqual(calls, [9, 9])
                self.assertEqual((report["status"], report["stop_reason"]), ("stopped", "manifest_drift"))
                self.assertFalse(self.sent)
                self.assertEqual((report["attempt_budget_used"], report["possible_in_flight_attempts"]), (0, 0))
                self.assert_tail(report, 0, "manifest_drift")

    async def test_changed_manifest_pins_or_order_are_zero_send(self):
        mutations = [
            lambda m: m["settings"].update(max_tokens=2049),
            lambda m: m["inputs"].reverse(),
            lambda m: m["oracle"]["E01_overview"]["values"].update(amount=68001),
            lambda m: m["identities"]["context"].update(context_sha256="0" * 64),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                path = self.write_json(self.root / f"changed-{index}.json", manifest)
                report = await self.run_panel(manifest_path=path)
                self.assertEqual(report["stop_reason"], "manifest_drift")
                self.assertFalse(self.sent)
                self.assert_tail(report, 0, "manifest_drift")

    async def test_source_and_database_drift_before_and_after_call_keep_intent_precedence(self):
        persist = smoke._Artifacts.persist
        for index, (kind, timing, wrong) in enumerate((
            ("source", "before", False), ("source", "after", False),
            ("database", "before", False), ("database", "after", False), ("database", "after", True),
        )):
            with self.subTest(kind=kind, timing=timing, wrong_intent=wrong):
                if index:
                    self.fresh_fixture(f"drift-{index}")
                identity = copy.deepcopy(self.manifest["identities"])
                flag = [False]

                def drift():
                    flag[0] = True
                    if kind == "database":
                        with closing(sqlite3.connect(self.database)) as conn, conn:
                            conn.execute("UPDATE centers SET name='changed' WHERE center_id='CA'")

                def source():
                    current = copy.deepcopy(identity)
                    if flag[0] and kind == "source":
                        current["files_sha256"]["tools/recipe_smoke.py"] = "0" * 64
                    return current

                def persisted(artifacts, report):
                    persist(artifacts, report)
                    if timing == "before" and report["possible_in_flight_attempts"] and not flag[0]:
                        drift()

                def respond(request):
                    candidate = self.wire(request)
                    if wrong:
                        candidate["request"]["center_code"] = "CTR-A02"
                    drift()
                    return httpx.Response(200, json=envelope(candidate))

                with (patch.object(runner, "_source_identity", side_effect=source),
                      patch.object(smoke._Artifacts, "persist", new=persisted)):
                    report = await self.run_panel(respond)
                reason = "manifest_drift" if kind == "source" else "database_drift"
                self.assertEqual(report["stop_reason"], reason)
                self.assertEqual((len(self.sent), report["possible_in_flight_attempts"]),
                                 (int(timing == "after"), 0))
                self.assertEqual(report["attempt_budget_used"], int(timing == "after"))
                if timing == "after":
                    row = report["results"][0]
                    self.assertEqual(row["outcome"], "wrong_request" if wrong else "operational_failure")
                    self.assertEqual(row["runner_error_code"], reason)
                    self.assertIsNone(row["error_code"])
                self.assert_tail(report, int(timing == "after"), reason)

    def test_unstable_nonseed_and_symlink_databases_never_prepare(self):
        sidecar = self.database.with_name(self.database.name + "-wal")
        sidecar.touch(exist_ok=False)
        with self.assertRaisesRegex(smoke.SmokeError, "^unstable_database$"):
            runner.build_manifest(self.database)
        sidecar.unlink()
        link = self.root / "linked.sqlite"
        link.symlink_to(self.database)
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            runner.build_manifest(link)
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute("UPDATE centers SET name='not exact seed' WHERE center_id='CA'")
        with self.assertRaisesRegex(smoke.SmokeError, "^unsupported_database$"):
            runner.build_manifest(self.database)
        self.assertFalse(self.sent)

    async def test_exclusive_outputs_manifest_symlinks_and_checkpoint_conflicts_preserve_evidence(self):
        before = (self.prepared / "report.json").read_bytes()
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            runner.prepare(self.database, self.prepared)
        self.assertEqual((self.prepared / "report.json").read_bytes(), before)
        link = self.root / "manifest-link.json"
        link.symlink_to(self.manifest_path)
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            await self.run_panel(manifest_path=link)
        self.assertFalse(self.sent)
        for sabotage in ("checkpoint", "report_symlink"):
            with self.subTest(sabotage=sabotage):
                victim = self.root / f"victim-{sabotage}"
                victim.write_text("untouched")

                def conflict(request):
                    if sabotage == "checkpoint":
                        self.write_json(self.output / "checkpoint-0002.json", {"sentinel": "untouched"})
                    else:
                        report_path = self.output / "report.json"
                        report_path.unlink()
                        report_path.symlink_to(victim)
                    return httpx.Response(200, json=envelope(self.wire(request)))

                with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
                    await self.run_panel(conflict)
                self.assertEqual(victim.read_text(), "untouched")
                reservation = json.loads((self.output / "checkpoint-0001.json").read_text())
                self.assertEqual(reservation["results"][0]["status"], "in_progress")
                self.assertEqual(reservation["possible_in_flight_attempts"], 1)
                if sabotage == "checkpoint":
                    self.assertEqual(json.loads((self.output / "checkpoint-0002.json").read_text()), {"sentinel": "untouched"})
                else:
                    self.assertTrue((self.output / "report.json").is_symlink())

    async def test_artifact_failure_after_call_retains_adapter_evidence_and_runner_failure(self):
        persist, failed = smoke._Artifacts.persist, [False]

        def once(artifacts, report):
            if report["results"][0]["status"] == "completed" and not failed[0]:
                failed[0] = True
                raise smoke.SmokeError("artifact_io")
            persist(artifacts, report)

        with patch.object(smoke._Artifacts, "persist", new=once):
            report = await self.run_panel()
        self.assertEqual(report["stop_reason"], "artifact_io")
        row = report["results"][0]
        self.assertEqual((row["outcome"], row["runner_error_code"], row["error_code"]),
                         ("operational_failure", "artifact_io", None))
        self.assertEqual(row["evidence"]["stages"]["kernel_execution"], "passed")
        self.assertEqual(report["client_http_attempts"], 1)
        self.assertEqual(self.read_report(), report)
        self.assert_tail(report, 1, "artifact_io")

    async def test_interruptions_preserve_durable_reservation_and_possible_inflight_attempt(self):
        def interrupt(request):
            if len(self.sent) == 2:
                raise KeyboardInterrupt(CANARY + KEY)
            return httpx.Response(200, json=envelope(self.wire(request)))

        report = await self.run_panel(interrupt)
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "interrupted"))
        self.assertEqual((report["client_http_attempts"], report["attempt_budget_used"],
                          report["possible_in_flight_attempts"]), (2, 2, 1))
        self.assertEqual(report["results"][0]["outcome"], "correct")
        self.assertEqual(report["results"][1]["status"], "in_progress")
        self.assertTrue(report["results"][1]["attempt_may_be_in_flight"])
        self.assert_tail(report, 2, "interrupted")
        with patch.object(runner, "interpret_recipe_and_execute", new=AsyncMock(side_effect=asyncio.CancelledError)):
            report = await self.run_panel()
        self.assertEqual((report["client_http_attempts"], report["attempt_budget_used"],
                          report["possible_in_flight_attempts"]), (0, 1, 1))
        self.assertEqual(report["results"][0]["status"], "in_progress")
        self.assert_tail(report, 1, "interrupted")

    def test_live_preflight_rejects_candidate_drift_missing_policy_or_path_before_loader(self):
        policies = dict.fromkeys(smoke.POLICY_KEYS, "disabled")
        fake_env = self.root / "never-read.env"
        with self.assertRaisesRegex(runner.RecipeSmokeError, "^accepted_commit_required$"):
            runner.live_preflight(self.manifest_path, self.manifest, gateway_policies=policies, env_file=fake_env)
        accepted = copy.deepcopy(self.manifest)
        accepted["identities"].update(git_commit=FAKE_COMMIT, branch="dev", worktree_dirty=False)
        accepted["preparation"] = {"kind": "accepted", "accepted_commit": FAKE_COMMIT}
        path = self.write_json(self.root / "synthetic-accepted-test-only.json", accepted)
        for changed_manifest, policy, env, code in (
            ({**accepted, "panel_id": "different"}, policies, fake_env, "manifest_drift"),
            (accepted, None, fake_env, "gateway_policy_required"),
            (accepted, policies, None, "invalid_configuration"),
        ):
            with self.subTest(code=code):
                with self.assertRaises((runner.RecipeSmokeError, smoke.SmokeError)) as caught:
                    runner.live_preflight(path, changed_manifest, gateway_policies=policy, env_file=env)
                self.assertEqual(caught.exception.code, code)
        self.loader.assert_not_called()
        dummy = GatewayConfig(BASE, KEY)
        with patch.object(GatewayConfig, "from_env", return_value=dummy) as mocked_loader:
            self.assertIs(runner.live_preflight(path, accepted, gateway_policies=policies,
                                               env_file=fake_env, environ={}), dummy)
        mocked_loader.assert_called_once_with(env_file=fake_env, environ={})
        self.assertFalse(fake_env.exists())
        self.assertFalse(self.sent)

    async def test_live_branch_disallows_supplied_client_and_candidate_before_any_loader(self):
        for supplied in (None, self.client()):
            with self.subTest(supplied=supplied is not None):
                self.output = self.root / f"live-denied-{supplied is not None}"
                report = await runner.run_panel(
                    self.database, self.output, manifest_path=self.manifest_path, origin="live",
                    client=supplied, env_file=self.root / "never-read.env",
                    gateway_policies=dict.fromkeys(smoke.POLICY_KEYS, "disabled"), environ={})
                self.assertEqual(report["stop_reason"], "invalid_configuration" if supplied else "accepted_commit_required")
                self.assertEqual((report["client_http_attempts"], report["live_model_attempts"]), (0, 0))
        self.loader.assert_not_called()
        self.assertFalse(self.sent)

    async def test_leakage_risk_stops_redacted_proposal_without_persisting_raw_values(self):
        def respond(request):
            candidate = self.wire(request)
            candidate["request"]["center_code"] = KEY
            return httpx.Response(200, json=envelope(candidate))

        report = await self.run_panel(respond)
        self.assertEqual(report["stop_reason"], "leakage_risk")
        row = report["results"][0]
        self.assertEqual((row["outcome"], row["error_code"], row["runner_error_code"]),
                         ("wrong_request", "kernel_failure", "leakage_risk"))
        self.assertEqual(row["proposal"]["request"]["center_code"], "[redacted]")
        for path in self.output.glob("*.json"):
            self.assert_private(path.read_text())
        artifacts = Mock()
        unsafe = runner._new_report(self.manifest, "mock")
        unsafe["extra"] = KEY
        with self.assertRaisesRegex(runner.RecipeSmokeError, "^leakage_risk$"):
            runner._persist(artifacts, unsafe, self.client())
        artifacts.persist.assert_not_called()

    async def test_unsafe_adapter_evidence_values_and_nested_keys_never_reach_checkpoints(self):
        original = runner.interpret_recipe_and_execute
        for fault in ("value", "key"):
            with self.subTest(fault=fault):
                async def unsafe_evidence(*args, **kwargs):
                    result = await original(*args, **kwargs)
                    self.assertIsNone(result.error)
                    self.assertEqual(result.evidence, json.loads(json.dumps(result.evidence)))
                    evidence = copy.deepcopy(result.evidence)
                    evidence["diagnostic"] = {"nested": [{"field": KEY} if fault == "value" else {KEY: "harmless"}]}
                    return replace(result, evidence=evidence)

                with patch.object(runner, "interpret_recipe_and_execute", side_effect=unsafe_evidence):
                    if fault == "key":
                        with self.assertRaisesRegex(runner.RecipeSmokeError, "^leakage_risk$") as caught:
                            await self.run_panel()
                        self.assert_private(repr(caught.exception))
                        previous = self.read_report()
                        self.assertEqual(previous["status"], "incomplete")
                        self.assertEqual(previous["results"][0]["status"], "in_progress")
                        self.assertEqual(previous["possible_in_flight_attempts"], 1)
                        self.assertIsNone(previous["results"][0]["evidence"])
                    else:
                        report = await self.run_panel()
                        self.assertEqual((report["status"], report["stop_reason"]), ("stopped", "leakage_risk"))
                        self.assertEqual(report["results"][0]["runner_error_code"], "leakage_risk")
                        self.assertEqual(report["results"][0]["evidence"]["diagnostic"]["nested"], [{"field": "[redacted]"}])
                        self.assert_tail(report, 1, "leakage_risk")
                self.assertEqual(len(self.sent), 1)
                for path in self.output.glob("*.json"):
                    self.assert_private(path.read_text())

    async def test_safe_errors_and_cli_argument_or_incomplete_outcomes_are_nonzero(self):
        def fail(_):
            raise RuntimeError(CANARY + BASE + KEY)

        report = await self.run_panel(fail)
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "internal_failure"))
        self.assert_private(repr(runner.RecipeSmokeError(CANARY)))
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(runner, "prepare", side_effect=RuntimeError(CANARY + KEY)),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            self.assertEqual(runner.main(["--db", str(self.database), "--output-dir", str(self.root / "unused")]), 2)
        self.assertEqual(json.loads(stderr.getvalue()), {"status": "incomplete", "error_code": "internal_failure"})
        for options in (("--manifest", str(self.manifest_path)), ("--env-file", str(self.root / "unused.env")),
                        ("--live", "--accepted-commit", FAKE_COMMIT)):
            with redirect_stderr(io.StringIO()), self.subTest(options=options):
                self.assertEqual(runner.main(["--db", str(self.database), "--output-dir", str(self.root / "unused"),
                                              *options]), 2)

        def stopped(coroutine):
            coroutine.close()
            return report

        with patch.object(runner.asyncio, "run", side_effect=stopped), redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--db", str(self.database), "--output-dir", str(self.root / "unused"),
                                          "--live"]), 1)
        self.assert_private(stdout.getvalue() + stderr.getvalue())
        self.loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
