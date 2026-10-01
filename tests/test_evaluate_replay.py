"""Replayable observations rulers (evaluation v2, #79): synthetic panels and mock transports only; no live call."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.contracts import KernelError
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate as runner, p3_assets
import registry_twin
from test_evaluate import BASE, KEY, SERVER_ANSWERED, SHA, EvaluateHarness, envelope

_OUTCOME_ACTION = {"request": "answer", "clarify": "clarify", "declined": "decline"}


class ReplayableObservationTests(EvaluateHarness):
    def cases(self):
        return p3_assets.load_panel(self.root / "development-panel-v1.json").cases

    def mixed_client(self, broken=()):
        """Scripted answers, except raw invalid JSON for the named case ids."""
        cases = self.cases()

        def respond(request):
            self.sent.append(request)
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            content = "{not json" if case.case_id in broken else json.dumps(self.by_oracle[case.oracle_id])
            return httpx.Response(200, json=envelope(content))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def scripted_run(self, repetition=None, client=None):
        packet_path = self.prepare(repetition=repetition)
        output = self.output()
        report, _ = await self.run_mock(packet_path, output, self.bind(packet_path, output),
                                        client=client or self.litellm_client(scripted=True, cases=self.cases()))
        return report, output

    # ----------------------------------------------------------------- packet v2
    def test_v2_packet_binds_repetition_into_the_run_id_and_declares_validated_action(self):
        first = json.loads(self.prepare().read_text())
        self.assertEqual(first["version"], "evaluation-packet-v2")
        self.assertEqual(first["repetition"], 1)
        self.assertTrue(first["run_id"].endswith("--r1"))
        self.assertEqual(first["observation_fields"],
                         ["clarification_kind", "clarification_choice_count", "validated_action"])
        self.assertIs(first["data_boundary"]["validated_action_persisted"], True)
        self.assertIs(first["data_boundary"]["raw_completion_or_reasoning_persisted"], False)
        second = json.loads(self.prepare(repetition=2).read_text())
        self.assertEqual(second["run_id"], first["run_id"][:-len("--r1")] + "--r2")
        self.assertEqual({k: v for k, v in second.items() if k not in ("repetition", "run_id")},
                         {k: v for k, v in first.items() if k not in ("repetition", "run_id")})
        for bad in (0, runner.MAX_REPETITION + 1, True, "2", 1.0):
            with self.subTest(repetition=bad), self.assertRaises(p3_assets.P3Error):
                self.prepare(repetition=bad)
        for field, value in (("repetition", 2), ("repetition", 0), ("data_boundary", runner.data_boundary(runner.PACKET_V1)),
                             ("observation_fields", ["clarification_kind", "clarification_choice_count"])):
            with self.subTest(field=field, value=value):
                changed = deepcopy(first)
                changed[field] = value
                with self.assertRaises(p3_assets.P3Error):
                    runner._packet_contract(changed)
        missing = deepcopy(first)
        del missing["repetition"]
        with self.assertRaises(p3_assets.P3Error):
            runner._packet_contract(missing)

    # ----------------------------------------------------------------- persisted actions
    async def test_live_run_persists_each_validated_action_and_readback_checks_it_structurally(self):
        broken = self.cases()[0].case_id
        report, output = await self.scripted_run(client=self.mixed_client(broken={broken}))
        self.assertEqual(report["report_version"], "evaluation-report-v2")
        self.assertEqual(report["status"], "complete")
        rows = {row["case_id"]: row for row in report["results"]}
        self.assertIsNone(rows[broken]["validated_action"])
        self.assertEqual(rows[broken]["outcome"], "invalid_output")
        persisted = [row for row in report["results"] if row["validated_action"] is not None]
        self.assertEqual(len(persisted), 14)
        self.assertEqual(report["summary"]["observations"]["validated_actions"], 14)
        for row in persisted:
            action = json.loads(row["validated_action"])
            self.assertEqual(row["validated_action"], json.dumps(action, sort_keys=True, ensure_ascii=False,
                                                                 separators=(",", ":")))
            # v15: an unresolved Compare orientation is persisted as the model's request behind the
            # server-built roles clarification (docs/compare-orientation-v15.md).
            derived = action["outcome"] == "request" and action.get("orientation") == "unresolved"
            # v19: a model count_basis clarification is persisted behind the server's answer (ADR #158).
            answered = action["outcome"] == "clarify" and action["clarification"]["kind"] == "count_basis"
            self.assertEqual("clarify" if derived else "answer" if answered else _OUTCOME_ACTION[action["outcome"]],
                             row["actual_action"])
            if derived:
                self.assertEqual((row["clarification_kind"], row["clarification_choice_count"]),
                                 ("comparison_roles", 2))
            if action["outcome"] == "clarify":
                self.assertEqual(set(action), {"outcome", "clarification"})
                # The server answered a count_basis clarification, so the row records no clarification (v19).
                self.assertEqual(None if answered else action["clarification"]["kind"], row["clarification_kind"])
                self.assertEqual(None if answered else len(action["clarification"]["choices"]),
                                 row["clarification_choice_count"])
            elif action["outcome"] == "request":
                self.assertEqual(set(action), {"outcome", "recipe_id", "recipe_version", "request",
                                               *(["orientation"] if action["recipe_id"] == "compare" else []),
                                               *(["count_request"] if action["recipe_id"] == "overview" else [])})
        serialized = json.dumps(report)
        self.assertNotIn("PRIVATE_REASONING_CANARY", serialized)
        self.assertNotIn(KEY, serialized)
        self.assertEqual(runner.read_report(output / "report.json"), report)
        path = output / "report.json"
        original = path.read_bytes()
        # The model's own request and clarification rows (v19 answers a count_basis clarification on the server).
        answer = next(i for i, row in enumerate(report["results"]) if row["actual_action"] == "answer"
                      and json.loads(row["validated_action"])["outcome"] == "request")
        clarify = next(i for i, row in enumerate(report["results"]) if row["actual_action"] == "clarify"
                       and json.loads(row["validated_action"])["outcome"] == "clarify")
        answer_action = json.loads(report["results"][answer]["validated_action"])
        clarify_action = json.loads(report["results"][clarify]["validated_action"])
        dropped = deepcopy(clarify_action)
        dropped["clarification"]["choices"] = dropped["clarification"]["choices"][:1]
        bad_id = deepcopy(clarify_action)
        bad_id["clarification"]["choices"][0]["id"] = "9bad"
        long_text = deepcopy(answer_action)
        long_text["request"]["extra"] = "x" * 300
        deep = deepcopy(answer_action)
        deep["request"]["nested"] = [[[[[[[[[["too deep"]]]]]]]]]]
        compact = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for label, index, value in (
                ("outcome_mismatch", answer, '{"outcome":"declined"}'),
                ("not_canonical", answer, json.dumps(answer_action, indent=1)),
                ("choice_count", clarify, compact(dropped)),
                ("choice_id", clarify, compact(bad_id)),
                ("long_string", answer, compact(long_text)),
                ("depth", answer, compact(deep)),
                ("free_text_outcome", answer, compact({**answer_action, "outcome": "note"})),
                ("not_text", answer, 5),
                ("oversized", answer, compact({**answer_action, "request": {"k": ["y" * 200] * 90}})),
                ("invalid_output_gains_action", [row["case_id"] for row in report["results"]].index(broken),
                 '{"outcome":"declined"}')):
            with self.subTest(label=label):
                tampered = json.loads(original)
                tampered["results"][index]["validated_action"] = value
                path.write_text(json.dumps(tampered))
                with self.assertRaises(p3_assets.P3Error):
                    runner.read_report(path)
        path.write_bytes(original)
        self.assertEqual(runner.read_report(path), report)

    async def test_a_stop_after_the_action_lands_keeps_the_real_stop_reason_and_a_final_report(self):
        """PR #129 review blocker: the engine's own action value never replaces a stop or its final report."""
        original, calls = runner._LiveEvidence.project, []

        def failing(policy, evidence, client):
            calls.append(1)
            if len(calls) == 2:
                raise p3_assets.P3Error("leakage_risk")
            return original(policy, evidence, client)

        with patch.object(runner._LiveEvidence, "project", failing):
            report, output = await self.scripted_run()
        self.assertEqual((report["status"], report["stop_reason"]), ("incomplete", "leakage_risk"))
        stopped = [row for row in report["results"] if row["runner_error_code"] is not None]
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0]["runner_error_code"], "leakage_risk")
        self.assertIsNone(stopped[0]["evidence"])
        self.assertIsNotNone(stopped[0]["validated_action"])
        self.assertEqual(runner.read_report(output / "report.json"), report)
        path = output / "report.json"
        original_bytes = path.read_bytes()
        tampered = json.loads(original_bytes)
        other = next(i for i, row in enumerate(tampered["results"])
                     if row["runner_error_code"] is None and row["validated_action"] is not None)
        tampered["results"][other]["evidence"] = None
        path.write_text(json.dumps(tampered))
        with self.assertRaises(p3_assets.P3Error):
            runner.read_report(path)
        path.write_bytes(original_bytes)
        replayed = await runner.replay(output / "report.json", self.database, self.root / "replay-stopped.json",
                                       panels_path=self.panels)
        self.assertEqual(next(row for row in replayed["rows"] if row["case_id"] == stopped[0]["case_id"])["class"],
                         "not_replayable")
        self.assertIsNone(replayed["comparison"])

    async def test_a_validated_action_the_leak_check_would_redact_is_stored_as_null_and_never_stops_the_run(self):
        """PR #129 re-review blocker: model-authored request strings pass the export check before they land."""
        cases = self.cases()
        leaky = next(case for case in cases if case.case_id == "E01_overview.en")
        host = httpx.URL(BASE).host

        def respond(request):
            self.sent.append(request)
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            action = deepcopy(self.by_oracle[case.oracle_id])
            if case is leaky:
                action["request"]["center_code"] = host
            return httpx.Response(200, json=envelope(json.dumps(action)))

        client = GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))
        report, output = await self.scripted_run(client=client)
        self.assertEqual((report["status"], report["stop_reason"]), ("complete", None))
        row = next(row for row in report["results"] if row["case_id"] == leaky.case_id)
        self.assertEqual(row["actual_action"], "answer")
        self.assertIsNone(row["validated_action"])
        self.assertNotIn(host, json.dumps(report))
        self.assertEqual(runner.read_report(output / "report.json"), report)

    async def test_readback_relaxes_the_evidence_checks_for_at_most_the_one_stopped_row(self):
        original, calls = runner._LiveEvidence.project, []

        def failing(policy, evidence, client):
            calls.append(1)
            if len(calls) == 3:
                raise p3_assets.P3Error("leakage_risk")
            return original(policy, evidence, client)

        with patch.object(runner._LiveEvidence, "project", failing):
            report, output = await self.scripted_run()
        path = output / "report.json"
        self.assertEqual(runner.read_report(path), report)
        tampered = json.loads(path.read_bytes())
        other = next(i for i, row in enumerate(tampered["results"])
                     if row["runner_error_code"] is None and row["validated_action"] is not None)
        tampered["results"][other].update(evidence=None, runner_error_code=tampered["stop_reason"],
                                          attempt_evidence_status="not_returned")
        runner._summarize(tampered)
        path.write_text(json.dumps(tampered))
        with self.assertRaises(p3_assets.P3Error):
            runner.read_report(path)

    # ----------------------------------------------------------------- v1 archives
    async def test_v1_archives_read_back_serve_as_baseline_and_can_no_longer_run_live(self):
        with patch.object(runner, "PACKET_VERSION", runner.PACKET_V1):
            v1_packet = self.prepare()
            output = self.output()
            report, _ = await self.run_mock(v1_packet, output, self.bind(v1_packet, output),
                                            client=self.litellm_client(scripted=True, cases=self.cases()))
        self.assertEqual(json.loads(v1_packet.read_text())["version"], "evaluation-packet-v1")
        self.assertEqual(report["report_version"], "evaluation-report-v1")
        self.assertNotIn("validated_action", report["results"][0])
        self.assertNotIn("validated_actions", report["summary"]["observations"])
        self.assertEqual(runner.read_report(output / "report.json"), report)
        self.assertEqual(runner.record(output / "report.json", runs_path=self.runs,
                                       now="2026-09-29T00:00:00Z")["correct"], 15 - len(SERVER_ANSWERED))
        baseline = json.loads(self.prepare(baseline=output / "report.json").read_text())
        self.assertEqual(baseline["version"], "evaluation-packet-v2")
        self.assertEqual(baseline["baseline"]["report_version"], "evaluation-report-v1")
        with self.assertRaises(p3_assets.P3Error) as refused:
            await runner.replay(output / "report.json", self.database, self.root / "replay-v1.json",
                                panels_path=self.panels)
        self.assertEqual((refused.exception.code, refused.exception.reason), ("manifest_drift", "report_version"))
        self.assertFalse((self.root / "replay-v1.json").exists())
        # The rebuild at validation is v2, so the archived v1 packet drifts before any credential.
        self.sent = []
        stale_output = self.output()
        with patch.object(runner, "GatewayConfig") as config_cls:
            with self.assertRaises(p3_assets.P3Error) as drift:
                await self.run_mock(v1_packet, stale_output, self.bind(v1_packet, stale_output))
            config_cls.from_env.assert_not_called()
        self.assertEqual(drift.exception.code, "manifest_drift")
        self.assertEqual(self.sent, [])

    # ----------------------------------------------------------------- replay
    async def test_replay_at_the_recording_source_reproduces_every_replayable_row_with_zero_model_calls(self):
        broken = self.cases()[0].case_id
        report, output = await self.scripted_run(client=self.mixed_client(broken={broken}))
        self.sent = []
        destination = self.root / "replay-same.json"
        replayed = await runner.replay(output / "report.json", self.database, destination, panels_path=self.panels)
        self.assertEqual(self.sent, [])
        self.assertEqual(json.loads(destination.read_text()), replayed)
        self.assertEqual(replayed["version"], "evaluation-replay-v1")
        self.assertEqual(replayed["claim"], "offline_replay_observation")
        self.assertIs(replayed["promotion_eligible"], False)
        self.assertEqual(replayed["live_model_attempts"], 0)
        self.assertEqual(replayed["mock_transport_calls"], 14)
        self.assertEqual(replayed["counts"], {"replayed_same": 14, "replayed_changed": 0, "not_replayable": 1})
        self.assertEqual(next(row for row in replayed["rows"] if row["case_id"] == broken)["class"], "not_replayable")
        self.assertEqual(replayed["source"]["run_id"], report["run_id"])
        self.assertEqual(replayed["source"]["candidate"], report["candidate"])
        self.assertEqual(replayed["archived_correct"], replayed["replayed_correct"])
        self.assertEqual(replayed["comparison"]["new_regressions"], 0)
        self.assertEqual(replayed["comparison"]["known_failures_fixed"], 0)
        self.assertIn("worktree_dirty", replayed["replay_identity"]["source_identity"])
        with self.assertRaises(p3_assets.P3Error) as again:
            await runner.replay(output / "report.json", self.database, destination, panels_path=self.panels)
        self.assertEqual(again.exception.code, "artifact_conflict")

    async def test_replay_shows_a_kernel_change_and_refuses_different_model_facing_bytes(self):
        report, output = await self.scripted_run()
        # Only executed Compare requests move with the kernel; an unresolved orientation executes nothing.
        compare_rows = [row["case_id"] for row in report["results"] if row["validated_action"] is not None
                        and json.loads(row["validated_action"]).get("recipe_id") == "compare"
                        and json.loads(row["validated_action"]).get("orientation") != "unresolved"]
        self.assertTrue(compare_rows)
        with patch.object(recipe_model, "execute_compare",
                          side_effect=KernelError("execution_failure", "synthetic kernel change")):
            replayed = await runner.replay(output / "report.json", self.database, self.root / "replay-kernel.json",
                                           panels_path=self.panels)
        changed = sorted(row["case_id"] for row in replayed["rows"] if row["class"] == "replayed_changed")
        self.assertEqual(changed, sorted(compare_rows))
        self.assertEqual(replayed["counts"]["replayed_same"], 15 - len(compare_rows))
        self.assertLess(replayed["replayed_correct"], replayed["archived_correct"])
        for row in replayed["rows"]:
            if row["class"] == "replayed_changed":
                self.assertNotEqual(row["replayed"]["outcome"], row["archived"]["outcome"])
        # Different model-facing bytes make recorded actions unrepresentative: refused before any replay.
        other = registry.load_entry("p3-bound-meaning-context-v8")
        self.assertNotEqual(other["candidate_sha256"], report["candidate"]["candidate_sha256"])
        checked = {"candidate_id": other["candidate_id"], "semantic_identity_sha256": other["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=other):
            with self.assertRaises(p3_assets.P3Error) as refused:
                await runner.replay(output / "report.json", self.database, self.root / "replay-other.json",
                                    panels_path=self.panels)
        self.assertEqual((refused.exception.code, refused.exception.reason), ("manifest_drift", "candidate_bytes"))
        self.assertFalse((self.root / "replay-other.json").exists())
        # The CLI names the closed refusal reason next to the existing safe code.
        stderr = io.StringIO()
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=other), \
                patch("sys.stdout"), patch("sys.stderr", stderr):
            code = runner.main(["--replay", "--report-path", str(output / "report.json"), "--db", str(self.database),
                                "--output", str(self.root / "replay-cli.json")])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue()), {"status": "incomplete", "error_code": "manifest_drift",
                                                         "replay_refusal": "candidate_bytes"})

    # ----------------------------------------------------------------- aggregate
    async def test_aggregate_includes_every_same_bytes_run_of_the_panel_and_route_and_classifies_inputs(self):
        cases = self.cases()
        with patch.object(runner, "PACKET_VERSION", runner.PACKET_V1):
            v1_packet = self.prepare()
            v1_output = self.output()
            await self.run_mock(v1_packet, v1_output, self.bind(v1_packet, v1_output),
                                client=self.litellm_client(scripted=True, cases=cases))
        _, first = await self.scripted_run(repetition=1)
        _, second = await self.scripted_run(repetition=2, client=self.litellm_client())
        for index, output in enumerate((v1_output, first, second)):
            runner.record(output / "report.json", runs_path=self.runs, now=f"2026-09-29T00:00:0{index}Z")
        recorded = runner.load_runs(self.runs)
        result = runner.aggregate("synthetic-dev", "litellm-31b", self.candidate, runs_path=self.runs)
        self.assertEqual(result["version"], "evaluation-aggregate-v1")
        self.assertIs(result["promotion_eligible"], False)
        self.assertEqual([run["run_id"] for run in result["runs"]], [run["run_id"] for run in recorded])
        self.assertEqual([run["report_version"] for run in result["runs"]],
                         ["evaluation-report-v1", "evaluation-report-v2", "evaluation-report-v2"])
        self.assertEqual([row["case_id"] for row in result["inputs"]], [case.case_id for case in cases])
        declines = {case.case_id for case in cases if case.expected_branch == "decline"}
        self.assertTrue(declines)
        for row in result["inputs"]:
            self.assertEqual((row["observations"], row["assessed"], row["validated_actions"]), (3, 3, 2))
            if row["case_id"] in declines:
                self.assertEqual((row["correct"], row["class"], row["distinct_validated_actions"]),
                                 (3, "stable_correct", 1))
            elif row["case_id"] in SERVER_ANSWERED:
                self.assertEqual((row["correct"], row["class"], row["distinct_validated_actions"]),
                                 (0, "stable_wrong", 2))
            else:
                self.assertEqual((row["correct"], row["class"], row["distinct_validated_actions"]), (2, "flaky", 2))
        self.assertEqual(result["class_counts"], {"stable_correct": len(declines), "stable_wrong": len(SERVER_ANSWERED),
                                                  "flaky": 15 - len(declines) - len(SERVER_ANSWERED),
                                                  "insufficient": 0})
        base = recorded[-1]
        excluded = [dict(base, run_id="other-bytes", candidate_id="p3-bound-meaning-context-v8",
                         slot=".artifacts/absent-other-bytes"),
                    dict(base, run_id="other-route", route_id="litellm-12b", slot=".artifacts/absent-other-route"),
                    dict(base, run_id="other-panel", panel_id="synthetic-regression", tier="regression",
                         claim="observed_regression", slot=".artifacts/absent-other-panel")]
        self.runs.write_text(self.runs.read_text() + "".join(json.dumps(row, sort_keys=True) + "\n" for row in excluded))
        after = runner.aggregate("synthetic-dev", "litellm-31b", self.candidate, runs_path=self.runs)
        self.assertEqual((after["runs"], after["inputs"]), (result["runs"], result["inputs"]))
        self.assertNotEqual(after["run_index_sha256"], result["run_index_sha256"])
        clean = self.runs.read_text()
        # A same-bytes run under another registered id (the twin of the current candidate) is included,
        # so a missing or altered archive fails closed instead of silently shrinking the aggregate.
        twin, sibling = registry_twin.use(self)
        self.assertEqual(registry.load_entry(twin)["candidate_sha256"], registry.load_entry(sibling)["candidate_sha256"])
        self.assertEqual(sibling, self.candidate)
        for label, row in (("missing", dict(base, run_id="same-bytes-missing", candidate_id=twin,
                                            slot=".artifacts/absent-same-bytes")),
                           ("digest", dict(base, run_id="same-bytes-digest", report_sha256="0" * 64))):
            with self.subTest(label=label):
                self.runs.write_text(clean + json.dumps(row, sort_keys=True) + "\n")
                with self.assertRaises(p3_assets.P3Error):
                    runner.aggregate("synthetic-dev", "litellm-31b", self.candidate, runs_path=self.runs)
        self.runs.write_text(clean)
        with self.assertRaises(p3_assets.P3Error):
            runner.aggregate("synthetic-dev", "litellm-12b", self.candidate, runs_path=self.runs)
        # The CLI prints the same canonical JSON from the repository index path.
        stdout = io.StringIO()
        with patch.object(runner, "RUNS", self.runs), redirect_stdout(stdout):
            code = runner.main(["--aggregate", "--panel", "synthetic-dev", "--route", "litellm-31b",
                                "--candidate", self.candidate])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["class_counts"], result["class_counts"])

    def test_cli_replay_aggregate_and_repetition_arguments_are_closed(self):
        missing = str(self.root / "missing" / "report.json")
        with patch("sys.stdout"), patch("sys.stderr"):
            for argv in (["--aggregate", "--panel", "p", "--route", "r"],
                         ["--aggregate", "--panel", "p", "--route", "r", "--candidate", "c", "--db", "x"],
                         ["--replay", "--report-path", missing, "--db", str(self.database)],
                         ["--replay", "--report-path", missing, "--db", str(self.database), "--output", "o",
                          "--candidate", "c"],
                         ["--record", "--report-path", missing, "--repetition", "2"],
                         ["--live", "--packet", "p", "--db", str(self.database), "--accepted-commit", SHA,
                          "--env-file", "e", "--gateway-retries", "disabled", "--gateway-fallback", "disabled",
                          "--gateway-cache", "disabled", "--output-dir", str(self.output()), "--repetition", "2"],
                         ["--replay", "--report-path", missing, "--db", str(self.database),
                          "--output", str(self.root / "replay.json")],
                         ["--aggregate", "--panel", "p", "--route", "r", "--candidate", "not-registered"]):
                with self.subTest(argv=argv[:2]):
                    self.assertEqual(runner.main(argv), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
